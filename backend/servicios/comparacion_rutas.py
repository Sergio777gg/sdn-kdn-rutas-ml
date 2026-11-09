"""Calculo puro: costos adimensionales, direcciones y resumen de caminos."""
import math
from backend.algoritmos.dijkstra import calcular_ruta
from backend.algoritmos.pesos import calcular_costo_capacidad
from backend.servicios.sdn_vivo_runtime_v1 import route_inputs

DEFAULT_WEIGHTS = {'delay': 0.5, 'loss': 0.35, 'capacity': 0.15, 'load': 0.0}
DEFAULT_SCALES = {'delay_ms': 50.0, 'loss_ratio': 0.01, 'capacity_mbps': 1.0}
TARGETS = {
    'u_to_v': ('target_throughput_u_to_v_mbps', 'target_u_to_v_delay_avg_ms', 'target_u_to_v_loss_ratio'),
    'v_to_u': ('target_throughput_v_to_u_mbps', 'target_v_to_u_delay_avg_ms', 'target_v_to_u_loss_ratio'),
}
CRITERIA = (
    ('hops', 'Menor número de saltos', 'saltos'),
    ('delay', 'Menor retardo configurado', 'ms configurados'),
    ('capacity', 'Inversa de capacidad nominal', 'Σ 1/Mbps'),
    ('ml', 'Inteligente ML', 'QoS normalizado'),
)
METRICS = (
    ('saltos', 'saltos', False),
    ('retardo_configurado_ms', 'retardo configurado', False),
    ('costo_referencia', 'costo por inversa de capacidad', False),
    ('costo_qos', 'costo QoS previsto', False),
    ('delay_previsto_ms', 'delay previsto', False),
    ('loss_previsto_ratio', 'loss previsto', False),
    ('capacidad_minima_mbps', 'capacidad mínima nominal', True),
)


def finite(value, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (value <= 0 if positive else value < 0):
        raise ValueError('Valores numericos finitos y no negativos requeridos')
    return float(value)


def parameters(weights=None, scales=None):
    weights = dict(DEFAULT_WEIGHTS if weights is None else weights)
    scales = dict(DEFAULT_SCALES if scales is None else scales)
    if set(weights) != set(DEFAULT_WEIGHTS) or set(scales) != set(DEFAULT_SCALES):
        raise ValueError('Parametros QoS incompletos')
    weights = {k: finite(v) for k,v in weights.items()}
    total = sum(weights.values())
    if not math.isfinite(total) or total <= 0:
        raise ValueError('La suma de pesos debe ser positiva y finita')
    return {k:v/total for k,v in weights.items()}, {k:finite(v, True) for k,v in scales.items()}


def directional_cost(capacity, throughput, delay, loss, weights, scales):
    c, t, d, l = finite(capacity, True), finite(throughput), finite(delay), finite(loss)
    if l > 1:
        raise ValueError('Loss fuera del intervalo [0,1]')
    # Formas estables de x/(x+escala), sin sumar valores grandes.
    components = {'delay': 1/(1+scales['delay_ms']/d) if d else 0.0,
                  'loss': 1/(1+scales['loss_ratio']/l) if l else 0.0,
                  'capacity': 1/(1+c/scales['capacity_mbps']),
                  'load': 1/(1+c/t) if t else 0.0}
    return sum(weights[k]*components[k] for k in weights), components


def conventional(snapshot, request):
    args = route_inputs(snapshot, request.topology_instance_id, request.graph_version,
                        request.origen, request.destino, 'capacity', calcular_costo_capacidad)
    path, _ = calcular_ruta(**args)
    return args, summarize(snapshot, path)


def summarize(snapshot, path, directed=None):
    profile = snapshot['topology_document']['topologies'][snapshot['topologia']]
    pairs = {}
    for e in profile['links']:
        pairs[(e['switch_u'],e['switch_v'])] = pairs[(e['switch_v'],e['switch_u'])] = e
    edges = [pairs[(a,b)] for a,b in zip(path,path[1:])]
    delays = [e.get('configured_delay_ms') for e in edges]
    configured_delay = None
    if all(isinstance(d,(int,float)) and not isinstance(d,bool) and math.isfinite(d) and d>=0 for d in delays):
        configured_delay = finite(sum(delays))
    result = {'ruta':path, 'saltos':len(edges), 'edge_ids':[e['link_id'] for e in edges],
              'costo_referencia':finite(sum(calcular_costo_capacidad(e['capacity_mbps']) for e in edges)),
              'capacidad_minima_mbps':min(e['capacity_mbps'] for e in edges),
              'retardo_configurado_ms':configured_delay,
              'costo_qos':None, 'delay_previsto_ms':None, 'loss_previsto_ratio':None,
              'predicciones_enlaces':[]}
    if directed is not None:
        values = [directed[(a,b)] for a,b in zip(path,path[1:])]
        result.update(costo_qos=sum(v['costo_qos'] for v in values),
                      delay_previsto_ms=finite(sum(v['delay_ms'] for v in values)),
                      loss_previsto_ratio=1-math.prod(1-v['loss_ratio'] for v in values),
                      predicciones_enlaces=values)
    return result


def prediction_graph(snapshot, predictions, weights, scales):
    active = {e['id'] for e in snapshot['links_runtime'] if e.get('state') == 'up'}
    profile = snapshot['topology_document']['topologies'][snapshot['topologia']]
    directed, weighted = {}, []
    for edge in profile['links']:
        if edge['link_id'] not in active:
            continue
        p = predictions[edge['link_id']]['predicciones']
        u,v = edge['switch_u'], edge['switch_v']
        for direction,a,b in [('u_to_v',u,v),('v_to_u',v,u)]:
            t,d,l = (p[k] for k in TARGETS[direction])
            cost, components = directional_cost(edge['capacity_mbps'],t,d,l,weights,scales)
            directed[(a,b)] = {'link_id':edge['link_id'], 'origen':a, 'destino':b,
                'direccion':direction, 'throughput_rx_mbps':t, 'delay_ms':d, 'loss_ratio':l,
                'costo_qos':cost, 'componentes':components}
            weighted.append({'origen':a,'destino':b,'costo':cost})
    return directed,weighted


def compare(snapshot, request, predictions, weights, scales):
    args, _ = conventional(snapshot, request)
    directed,weighted = prediction_graph(snapshot,predictions,weights,scales)
    conventional_path,_ = calcular_ruta(**args)
    intelligent_path,_ = calcular_ruta(nodos=args['nodos'], enlaces=weighted,
        origen=request.origen,destino=request.destino,dirigido=True)
    return summarize(snapshot,conventional_path,directed), summarize(snapshot,intelligent_path,directed)


def all_criteria(snapshot,request,predictions=None,weights=None,scales=None):
    """Una alternativa por criterio; mismo snapshot y predicciones para todas."""
    directed,weighted = prediction_graph(snapshot,predictions,weights,scales) if predictions is not None else (None,None)
    routes=[]
    for policy,label,unit in CRITERIA:
        item={'id':policy,'nombre':label,'unidad_optimizacion':unit,'status':'unavailable',
              'ruta':[],'edge_ids':[],'predicciones_enlaces':[],'ventajas':[],'desventajas':[],'mejores_en':[]}
        if policy=='ml' and predictions is None:
            item['motivo']='Faltan predicciones válidas y recientes.'
            routes.append(item);continue
        try:
            args=route_inputs(snapshot,request.topology_instance_id,request.graph_version,
                              request.origen,request.destino,'hops' if policy=='ml' else policy,calcular_costo_capacidad)
            if policy=='ml':args.update(enlaces=weighted,dirigido=True)
            path,cost=calcular_ruta(**args)
            item.update(summarize(snapshot,path,directed),status='available',costo_optimizacion=finite(cost))
        except (ValueError,KeyError,TypeError,OverflowError) as error:
            if policy!='delay':raise
            item['motivo']='No se puede evaluar el retardo configurado: '+str(error)
        routes.append(item)
    reference=next(r for r in routes if r['id']=='capacity')
    if reference['status']!='available':raise ValueError('La referencia de capacidad no está disponible.')
    for route in routes:
        if route['status']!='available':continue
        route['coincide_con']=[r['id'] for r in routes if r['id']!=route['id'] and r['status']=='available' and r['ruta']==route['ruta']]
        route['diferencias_vs_capacidad']={}
        for key,label,higher in METRICS:
            value,base=route.get(key),reference.get(key)
            if value is None or base is None:continue
            route['diferencias_vs_capacidad'][key]=value-base
            if route['id']=='capacity' or math.isclose(value,base,rel_tol=1e-9,abs_tol=1e-10):continue
            better=value>base if higher else value<base
            phrase=(('Más ' if value>base else 'Menos ')+label) if key=='saltos' else (('Mayor ' if value>base else 'Menor ')+label)
            route['ventajas' if better else 'desventajas'].append(phrase)
    rankings=[]
    for key,label,higher in METRICS:
        valid=[r for r in routes if r['status']=='available' and r.get(key) is not None]
        if not valid:continue
        best=(max if higher else min)(r[key] for r in valid)
        winners=[r for r in valid if math.isclose(r[key],best,rel_tol=1e-9,abs_tol=1e-10)]
        for route in winners:route['mejores_en'].append(key)
        rankings.append({'metrica':key,'nombre':label,'mejor_valor':best,'mayor_es_mejor':higher,
                         'criterios':[r['id'] for r in winners],'empate':len(winners)>1})
    return routes,rankings
