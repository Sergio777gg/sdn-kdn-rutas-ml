"""Red sintetica con una alternativa distinta por criterio; no son datos reales."""
import time
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from backend.servicios.comparacion_rutas import all_criteria,parameters,TARGETS
from backend.api.sdn_comparacion import comparison,ComparisonRequest


def fixture():
    paths=[(['s1','s2','s9'],1,50,80,.05),
           (['s1','s3','s4','s9'],2,1,30,.01),
           (['s1','s5','s6','s9'],20,30,50,.02),
           (['s1','s7','s8','s10','s9'],5,10,.5,0)]
    nodes=[];edges=[];predictions={}
    for path,capacity,configured,delay,loss in paths:
        for node in path:
            if node not in nodes:nodes.append(node)
        for a,b in zip(path,path[1:]):
            lid=a+'-'+b
            edges.append({'link_id':lid,'switch_u':a,'switch_v':b,
                          'capacity_mbps':capacity,'configured_delay_ms':configured})
            values={}
            for targets in TARGETS.values():values.update(dict(zip(targets,[.1,delay,loss])))
            predictions[lid]={'predicciones':values}
    snapshot={'ready':True,'source_url':'http://127.0.0.1:8769','topologia':'nsfnet','session_id':'synthetic',
        'topology_instance_id':'test','graph_version':'g','selection_revision':1,'observed_utc':'test',
        'topology_document':{'topologies':{'nsfnet':{'nodes':[{'switch':n} for n in nodes],'links':edges}}},
        'links_runtime':[{'id':e['link_id'],'state':'up'} for e in edges]}
    req=SimpleNamespace(topology_instance_id='test',graph_version='g',origen='s1',destino='s9')
    return snapshot,predictions,req


def test_each_criterion_optimizes_its_own_function_and_shares_qos_evaluation():
    s,p,req=fixture();w,sc=parameters();routes,ranking=all_criteria(s,req,p,w,sc)
    by={r['id']:r for r in routes}
    assert by['hops']['ruta']==['s1','s2','s9']
    assert by['delay']['ruta']==['s1','s3','s4','s9']
    assert by['capacity']['ruta']==['s1','s5','s6','s9']
    assert by['ml']['ruta']==['s1','s7','s8','s10','s9']
    assert by['delay']['costo_optimizacion']==3
    assert by['capacity']['costo_optimizacion']==pytest.approx(.15)
    assert by['ml']['costo_qos']==pytest.approx(by['ml']['costo_optimizacion'])
    assert all(by['ml']['costo_qos']<=r['costo_qos'] for r in routes)
    assert by['capacity']['capacidad_minima_mbps']>by['ml']['capacidad_minima_mbps']
    assert 'Más saltos' in by['ml']['desventajas']
    assert 'Menor capacidad mínima nominal' in by['ml']['desventajas']
    assert next(r for r in ranking if r['metrica']=='saltos')['criterios']==['hops']
    assert next(r for r in ranking if r['metrica']=='retardo_configurado_ms')['criterios']==['delay']


def test_without_ml_three_conventional_paths_remain_without_fake_predictions():
    s,_,req=fixture();routes,ranking=all_criteria(s,req)
    assert [r['status'] for r in routes]==['available']*3+['unavailable']
    assert all(r['costo_qos'] is None and not r['predicciones_enlaces'] for r in routes[:3])
    assert not any(r['metrica'] in ['costo_qos','delay_previsto_ms','loss_previsto_ratio'] for r in ranking)


def test_missing_delay_does_not_remove_edges_or_hide_other_criteria():
    s,p,req=fixture();s['topology_document']['topologies']['nsfnet']['links'][2].pop('configured_delay_ms')
    w,sc=parameters();routes,_=all_criteria(s,req,p,w,sc)
    assert [r['status'] for r in routes]==['available','unavailable','available','available']


def test_directions_and_down_links():
    s,p,req=fixture();w,sc=parameters()
    for lid in ['s1-s7','s7-s8','s8-s10','s10-s9']:
        p[lid]['predicciones']['target_v_to_u_delay_avg_ms']=100
        p[lid]['predicciones']['target_v_to_u_loss_ratio']=.05
    req.origen,req.destino='s9','s1'
    routes,_=all_criteria(s,req,p,w,sc)
    assert routes[-1]['ruta']!=['s9','s10','s8','s7','s1']
    s['links_runtime'][0]['state']='down'
    routes,_=all_criteria(s,req,p,w,sc)
    assert all('s1-s2' not in r['edge_ids'] for r in routes)


def test_equal_paths_and_metrics_are_reported_as_real_ties():
    s,p,req=fixture();profile=s['topology_document']['topologies']['nsfnet']
    profile['links']=profile['links'][:2];s['links_runtime']=s['links_runtime'][:2]
    w,sc=parameters();routes,ranking=all_criteria(s,req,p,w,sc)
    assert len({tuple(r['ruta']) for r in routes})==1
    assert all(len(r['coincide_con'])==3 for r in routes)
    assert all(r['empate'] and len(r['criterios'])==4 for r in ranking)


@pytest.mark.parametrize('available',[True,False])
def test_endpoint_predicts_only_once_preserves_legacy_and_handles_missing_ml(available):
    from backend.api import sdn_selector_v2 as selector
    s,p,req=fixture()
    body=ComparisonRequest(**vars(req),selection_revision=1)
    meta={'feature_start_epoch_s':time.time()-25,'feature_end_epoch_s':time.time()-5,
          'max_age_s':120,'modelo_id':'synthetic'}
    with patch.object(selector.original,'network') as net,patch('backend.api.sdn_comparacion.predict_snapshot') as predict:
        net.snapshot.return_value=s
        if available:predict.return_value=(p,meta)
        else:predict.side_effect=HTTPException(424,'sin entradas')
        result=comparison(body)
        predict.assert_called_once()
        assert len(result['alternativas'])==4
        assert result['convencional']['ruta']==result['alternativas'][2]['ruta']
        if available:assert result['inteligente']['ruta']==result['alternativas'][3]['ruta']
        else:assert result['inteligente'] is None and all(r['costo_qos'] is None for r in result['alternativas'][:3])


def test_expiration_discards_predictions_for_all_four_paths_together():
    from backend.api import sdn_selector_v2 as selector
    s,p,req=fixture();body=ComparisonRequest(**vars(req),selection_revision=1)
    meta={'feature_start_epoch_s':100,'feature_end_epoch_s':120,'max_age_s':120,'modelo_id':'test'}
    with patch.object(selector.original,'network') as net,patch('backend.api.sdn_comparacion.predict_snapshot',return_value=(p,meta)),patch('backend.api.sdn_comparacion.time.time',return_value=241):
        net.snapshot.return_value=s;result=comparison(body)
    assert result['ml']['status']=='unavailable' and result['inteligente'] is None
    assert all(r['costo_qos'] is None for r in result['alternativas'][:3])


def test_unavailable_delay_never_claims_all_four_paths_coincide():
    from backend.api import sdn_selector_v2 as selector
    s,p,req=fixture();s['topology_document']['topologies']['nsfnet']['links']=s['topology_document']['topologies']['nsfnet']['links'][:2]
    s['links_runtime']=s['links_runtime'][:2]
    s['topology_document']['topologies']['nsfnet']['links'][0].pop('configured_delay_ms')
    body=ComparisonRequest(**vars(req),selection_revision=1)
    meta={'feature_start_epoch_s':time.time()-25,'feature_end_epoch_s':time.time()-5,'max_age_s':120,'modelo_id':'test'}
    with patch.object(selector.original,'network') as net,patch('backend.api.sdn_comparacion.predict_snapshot',return_value=(p,meta)):
        net.snapshot.return_value=s;result=comparison(body)
    assert result['alternativas'][1]['status']=='unavailable'
    assert result['todas_coinciden'] is False
