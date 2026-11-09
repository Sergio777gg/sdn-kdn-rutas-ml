#!/usr/bin/env python3
"""Inicia o verifica las dos redes; recuperacion de huerfanos explicitamente opt-in."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from recuperacion_ovs import inspect_ovs,orphan_candidates,active_owners,backup_and_remove


def http(url):
    with urlopen(url,timeout=5) as r:return json.load(r)


def observed(base,name,port):
    try:data=http('http://192.168.56.103:{}/snapshot'.format(port))
    except OSError:return None
    if data.get('schema_version')!=1 or data.get('observer_version')!='sdn-vivo-1':
        raise ValueError('Otro servicio ocupa el puerto '+str(port))
    networks=[n for n in data.get('networks',[]) if n.get('topologia')==name and n.get('capture',{}).get('alive')]
    if len(networks)>1:raise ValueError('Varias sesiones activas de '+name)
    return networks[0] if networks else None


def ready(network,count):
    if not network:return False
    metrics=network.get('metrics',{})
    if metrics.get('status')!='fresh' or len(metrics.get('links',{}))!=count:return False
    for lid,link in metrics['links'].items():
        ml=link.get('ml',{})
        if (ml.get('status')!='inputs_ready' or ml.get('link_id')!=lid
                or ml.get('session_id')!=network['session_id'] or ml.get('topologia')!=network['topologia']
                or len(ml.get('features',{}))!=60):return False
        age=time.time()-ml.get('feature_end_epoch_s',0)
        if not 0<=age<=120:return False
    return True


def start(base,name,recover,logs):
    port=8768 if name=='geant2' else 8769
    config=json.loads((base/name/'perfil.json').read_text())
    profile=config['topologies'][name];count=len(profile['links'])
    network=observed(base,name,port)
    child=None
    if network is None:
        if active_owners(name,base):raise ValueError('Ya hay un proceso de '+name+'; no se inicia otro.')
        sock=socket.socket()
        try:sock.bind(('192.168.56.103',port))
        finally:sock.close()
        snapshot=inspect_ovs()
        candidates=orphan_candidates(snapshot,profile,name,config['ryu_ip'],config['of_port'],active_owners(name,base))
        if candidates:
            if not recover:raise ValueError('Restos OVS verificados. Repetir con --recuperar-huerfanos para respaldar y retirar solo esos restos.')
            if active_owners(name,base):raise ValueError('Aparecio un propietario; se conserva la red.')
            backup=backup_and_remove(base,snapshot,candidates)
            print(name+': retirados '+str(len(candidates))+' bridges huerfanos. Respaldo: '+backup,flush=True)
        limit=time.monotonic()+12
        while http(config['rest_url']+'/stats/switches'):
            if time.monotonic()>limit:raise ValueError('El controlador aun tiene switches. Se conserva el resto de la configuracion.')
            time.sleep(.5)
        with (logs/(name+'.log')).open('ab') as log:
            child=subprocess.Popen([sys.executable,str(base/'iniciar.py'),name,'--arrancar-red'],
                stdout=log,stderr=log,start_new_session=True)
        print(name+': arrancando; esperando la primera ventana completa...',flush=True)
    else:print(name+': sesion existente; se comprueba sin reiniciarla.',flush=True)
    limit=time.monotonic()+180
    while time.monotonic()<limit:
        if child is not None and child.poll() is not None:
            raise ValueError(name+' no arranco: '+(logs/(name+'.log')).read_text(errors='replace')[-3500:])
        network=observed(base,name,port)
        if ready(network,count):
            print(name+': ACTIVA, '+str(len(profile['nodes']))+' nodos, '+str(count)+' enlaces con 60 entradas recientes.',flush=True)
            return {'topologia':name,'session_id':network['session_id'],'observer_port':port,'links':count}
        time.sleep(1)
    raise ValueError('La telemetria de '+name+' no quedo lista en 180 s. Registro: '+str(logs/(name+'.log')))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recuperar-huerfanos',action='store_true',help='Respalda y retira exclusivamente restos verificados sin enlaces Linux ni recolector propietario')
    args=parser.parse_args()
    if os.geteuid()!=0:raise SystemExit('Usar sudo python3 para el arranque de Mininet.')
    base=Path(__file__).resolve().parent
    logs=base/'arranques'/datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ')
    logs.mkdir(parents=True)
    with (base/'arranque.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise SystemExit('Ya hay un arranque en curso. No se duplica.')
        for name in ('geant2','nsfnet'):
            cfg=json.loads((base/name/'perfil.json').read_text())
            health=http(cfg['model_url']+'/health')
            if health.get('modelo_id')!=cfg['model_id'] or health.get('estado')!='modelo_cargado':
                raise ValueError('El modelo esperado no esta disponible; iniciar primero RYU y ML.')
            http(cfg['rest_url']+'/stats/switches')
        results=[start(base,name,args.recuperar_huerfanos,logs) for name in ('geant2','nsfnet')]
        (logs/'resultado.json').write_text(json.dumps(results,indent=2))
        print('Ambas redes listas. Puedes cerrar esta terminal; los recolectores siguen activos.',flush=True)


if __name__=='__main__':main()
