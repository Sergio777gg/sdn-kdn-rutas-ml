"""Comparacion de solo calculo; reutiliza el contrato real del predictor."""
import hashlib
import json
import math
import threading
import time
from collections import OrderedDict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from backend.api.sdn_modelo_comun_v1 import consultar
from backend.api.sdn_predicciones_enlace_v1 import (
    SolicitudPrediccionEnlaceV1, _entrada, _validar_salida, _predecir,
)
from backend.servicios.comparacion_rutas import (
    DEFAULT_WEIGHTS, DEFAULT_SCALES, TARGETS, parameters, conventional, all_criteria,
)

router = APIRouter(prefix='/api/sdn', tags=['Comparacion de rutas'])
_cache, _lock = OrderedDict(), threading.RLock()


class Weights(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    delay: float = Field(default=0.5, ge=0)
    loss: float = Field(default=0.35, ge=0)
    capacity: float = Field(default=0.15, ge=0)
    load: float = Field(default=0.0, ge=0)


class Scales(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    delay_ms: float = Field(default=50, gt=0)
    loss_ratio: float = Field(default=0.01, gt=0, le=1)
    capacity_mbps: float = Field(default=1, gt=0)


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    topology_instance_id: str = Field(min_length=1, max_length=240)
    graph_version: str = Field(min_length=1, max_length=240)
    selection_revision: int = Field(ge=0)
    origen: str = Field(min_length=1, max_length=64)
    destino: str = Field(min_length=1, max_length=64)
    pesos: Weights = Field(default_factory=Weights)
    escalas: Scales = Field(default_factory=Scales)


def identity(s):
    return tuple(s.get(k) for k in ('source_url','topologia','session_id','topology_instance_id','graph_version','selection_revision'))


def predict_snapshot(snapshot):
    health, schema = consultar('/health'), consultar('/schema')
    targets = {k for triple in TARGETS.values() for k in triple}
    if (health.get('estado') != 'modelo_cargado' or health.get('evaluacion') != 'test_completado'
            or not health.get('modelo_id') or health.get('features') != 60 or health.get('targets') != 6
            or len(schema.get('features', [])) != 60 or len(set(schema['features'])) != 60
            or set(schema.get('targets', [])) != targets or len(schema['targets']) != 6
            or schema.get('antiguedad_maxima_s') != 120):
        raise HTTPException(424, 'El contrato del modelo no confirma 60 entradas, seis salidas y limite de 120 s.')
    result, entries = {}, {}
    for edge in snapshot['links_runtime']:
        if edge.get('state') != 'up':
            continue
        ml = snapshot.get('metrics', {}).get('links', {}).get(edge['id'], {}).get('ml', {})
        fin = ml.get('feature_end_epoch_s')
        if not isinstance(fin,(int,float)) or isinstance(fin,bool) or not math.isfinite(fin) or fin <= 0:
            raise HTTPException(424,'Falta una ventana de entrada valida en '+edge['id'])
        request = SolicitudPrediccionEnlaceV1(topology_instance_id=snapshot['topology_instance_id'],
            graph_version=snapshot['graph_version'],link_id=edge['id'],feature_end_epoch_s=fin)
        entries[edge['id']] = _entrada(snapshot,request,schema['features'])
    windows = {(e['feature_start_epoch_s'],e['feature_end_epoch_s']) for e in entries.values()}
    if len(windows) != 1:
        raise HTTPException(424,'Los enlaces no comparten una misma ventana temporal.')
    profile = snapshot['topology_document']['topologies'][snapshot['topologia']]
    nominal = {e['link_id']:e for e in profile['links']}
    for link_id,entry in entries.items():
        if link_id not in nominal or entry['features'].get('capacity_mbps') != nominal[link_id]['capacity_mbps']:
            raise HTTPException(424,'La capacidad de entrada no coincide con el grafo.')
        digest = hashlib.sha256(json.dumps(entry,sort_keys=True,allow_nan=False).encode()).hexdigest()
        key = (identity(snapshot),health['modelo_id'],digest)
        with _lock:
            response = _cache.get(key)
        if response is None:
            response = _predecir(entry)
            _validar_salida(response,entry,schema['targets'],health['modelo_id'])
            with _lock:
                _cache[key] = response
                while len(_cache)>256:
                    _cache.popitem(last=False)
        _validar_salida(response,entry,schema['targets'],health['modelo_id'])
        result[link_id] = response
    start,end = next(iter(windows))
    age = time.time()-end
    if not -5 <= age <= 120:
        raise HTTPException(424,'Las entradas expiraron durante el calculo.')
    return result, {'modelo_id':health['modelo_id'],'feature_start_epoch_s':start,
        'feature_end_epoch_s':end,'input_age_s':age,'max_age_s':120,'objetivo':'siguiente_ventana',
        'links_predicted':len(result)}


@router.post('/rutas/comparar')
def comparison(request: ComparisonRequest):
    from backend.api import sdn_selector_v2 as selector
    network = selector.original.network
    snapshot = network.snapshot(force=True)
    if not snapshot.get('ready') or snapshot.get('selection_revision') != request.selection_revision:
        raise HTTPException(409,'Cambio la seleccion o la red no esta verificada.')
    try:
        weights, scales = parameters(request.pesos.model_dump(),request.escalas.model_dump())
        _, reference = conventional(snapshot,request)
        nominal_routes,nominal_rankings = all_criteria(snapshot,request)
    except ValueError as error:
        code = 409 if (snapshot.get('topology_instance_id') != request.topology_instance_id or
                       snapshot.get('graph_version') != request.graph_version) else 422
        raise HTTPException(code,str(error))
    result = {k:snapshot[k] for k in ('topologia','session_id','topology_instance_id','graph_version','selection_revision','observed_utc')}
    result.update(convencional=reference,inteligente=None,ml={'status':'unavailable'},
        alternativas=nominal_routes,mejores_por_metrica=nominal_rankings,
        pesos=weights,escalas=scales,criterio='QoS normalizado direccional',rules_installed=False,
        formula='w_delay*d/(d+D) + w_loss*l/(l+L) + w_capacity*C/(C+c) + w_load*t/(t+c)',
        advertencias=['Delay: suma de predicciones por enlace, no medicion extremo a extremo.',
            'Loss: 1-producto(1-loss); aproximacion de perdidas sucesivas. Incluye rechazos locales de sondas.',
            'Throughput RX por enlace no se suma ni demuestra capacidad disponible.'])
    try:
        predictions, metadata = predict_snapshot(snapshot)
        routes,rankings = all_criteria(snapshot,request,predictions,weights,scales)
        ref=next(r for r in routes if r['id']=='capacity')
        intelligent=next(r for r in routes if r['id']=='ml')
        qos_ranking=next(r for r in rankings if r['metrica']=='costo_qos')
        labels={r['id']:r['nombre'] for r in routes}
        result.update(convencional=ref,inteligente=intelligent,ml=dict(metadata,status='available'),
            alternativas=routes,mejores_por_metrica=rankings,
            rutas_iguales=ref['ruta']==intelligent['ruta'],
            todas_coinciden=all(r['status']=='available' for r in routes) and len({tuple(r['ruta']) for r in routes})==1,
            recomendacion=('Menor costo QoS previsto: '+', '.join(labels[k] for k in qos_ranking['criterios'])+
                ('. Hay empate bajo esta fórmula.' if qos_ranking['empate'] else '.')+
                ' Revisa los otros indicadores: no implica ventaja en todas las métricas ni una mejora medida.'))
        if weights['load']:
            result['advertencias'].append('Carga RX habilitada como proxy de trafico cursado; puede subestimar congestion con perdidas. No estima ancho de banda libre.')
    except HTTPException as error:
        if error.status_code == 409:
            raise
        result['ml'] = {'status':'unavailable','motivo':str(error.detail)}
        result['recomendacion'] = 'Ruta inteligente no disponible: faltan predicciones validas y recientes.'
    except (ValueError, OverflowError) as error:
        result['ml'] = {'status':'unavailable','motivo':'Las metricas derivadas no son validas: '+str(error)}
        result['recomendacion'] = 'Ruta inteligente no disponible: faltan predicciones validas y recientes.'
    actual = network.snapshot(force=True)
    if not actual.get('ready') or identity(actual) != identity(snapshot):
        raise HTTPException(409,'Cambio la sesion, seleccion o grafo durante el calculo. Vuelve a comparar.')
    if result['inteligente']:
        age = time.time()-result['ml']['feature_end_epoch_s']
        if not -5 <= age <= 120:
            result.update(convencional=reference,inteligente=None,
                alternativas=nominal_routes,mejores_por_metrica=nominal_rankings,
                ml={'status':'unavailable','motivo':'Las entradas expiraron durante la validacion final.'},
                recomendacion='Ruta inteligente no disponible: faltan predicciones validas y recientes.')
            result.pop('rutas_iguales',None)
            result.pop('todas_coinciden',None)
        else:
            result['ml']['input_age_s'] = age
    result['comparison_id'] = hashlib.sha256(json.dumps(result,sort_keys=True,allow_nan=False).encode()).hexdigest()[:24]
    return result
