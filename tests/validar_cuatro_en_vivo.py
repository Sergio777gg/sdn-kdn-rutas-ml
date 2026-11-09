"""Opt-in: cuatro criterios sobre una misma ventana, usando redes reales existentes."""
import json,os,math
from pathlib import Path
from urllib.request import Request,urlopen
BASE=os.getenv('SDN_TEST_API','http://127.0.0.1:8003')
def request(path,body=None):
    req=Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=90) as r:return json.load(r)

def main():
    results=[]
    for topology in ['nsfnet','geant2']:
        request('/api/sdn/seleccionar',{'topologia':topology})
        snapshot=request('/api/sdn/estado')
        assert snapshot['ready'] and snapshot['topologia']==topology
        body={k:snapshot[k] for k in ['topology_instance_id','graph_version','selection_revision']}
        body.update(origen='s5',destino='s2')
        data=request('/api/sdn/rutas/comparar',body)
        assert data['ml']['status']=='available',data['ml']
        assert data['ml']['input_age_s']<=120 and data['rules_installed'] is False
        assert [r['id'] for r in data['alternativas']]==['hops','delay','capacity','ml']
        assert all(r['status']=='available' for r in data['alternativas'])
        for r in data['alternativas']:
            assert math.isfinite(r['costo_qos'])
            assert data['inteligente']['costo_qos']<=r['costo_qos']+1e-10
            if r['id']!='ml':
                old=request('/api/sdn/rutas',dict(topology_instance_id=body['topology_instance_id'],
                    graph_version=body['graph_version'],origen='s5',destino='s2',criterio=r['id']))
                assert old['ruta']==r['ruta']
                assert math.isclose(old['costo_total'],r['costo_optimizacion'],rel_tol=1e-10)
        assert data['convencional']['ruta']==data['alternativas'][2]['ruta']
        assert data['inteligente']['ruta']==data['alternativas'][3]['ruta']
        results.append(data)
        print(topology,json.dumps([{k:r[k] for k in ['id','ruta','saltos','costo_qos','delay_previsto_ms','capacidad_minima_mbps']} for r in data['alternativas']]),flush=True)
    output=Path('validacion_rutas_ml/cuatro_criterios_reales.json');output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(results,indent=2,ensure_ascii=False))
    print('Cuatro criterios reales, compatibilidad y ventana comun: OK')
if __name__=='__main__':main()
