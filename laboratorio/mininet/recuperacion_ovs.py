"""Retirada limitada de restos OVS sin enlaces Linux ni procesos propietarios."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess


def decode(value):
    if isinstance(value,list) and len(value)==2 and value[0] in ('uuid','named-uuid'):
        return value[1]
    if isinstance(value,list) and len(value)==2 and value[0]=='set':
        return [decode(v) for v in value[1]]
    if isinstance(value,list) and len(value)==2 and value[0]=='map':
        return {decode(k):decode(v) for k,v in value[1]}
    return value


def values(value):
    return value if isinstance(value,list) else [value]


def table(kind,columns):
    data=json.loads(subprocess.check_output(['ovs-vsctl','--format=json','--columns='+columns,'list',kind],universal_newlines=True))
    rows=[dict(zip(data['headings'],[decode(v) for v in row])) for row in data['data']]
    return sorted(rows,key=lambda row:row.get('name',row.get('_uuid','')))


def inspect_ovs():
    return {'bridges':table('Bridge','name,datapath_id,ports,controller'),
        'ports':table('Port','_uuid,name,interfaces'),
        'interfaces':table('Interface','_uuid,name,type,ofport,error'),
        'controllers':table('Controller','_uuid,target'),
        'kernel_interfaces':sorted(p.name for p in Path('/sys/class/net').iterdir())}


def active_owners(topology,base):
    result=[]
    worker='telemetria_geant_v1.py' if topology=='geant2' else 'telemetria_nsf_v1.py'
    common={'sdn_noche_capturar.py','topologia_dual_sdn.py','topologia_nsfnet.py'}
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args=path.read_bytes().decode().split('\0')
        except (OSError,UnicodeError):continue
        names={Path(a).name for a in args if a}
        if worker in names or names.intersection(common) or ('iniciar.py' in names and topology in args and str(base/'iniciar.py') in args):
            result.append(int(path.parent.name))
    return result


def orphan_candidates(snapshot,profile,topology,controller_ip,openflow_port,owners):
    """Devuelve solo bridges del perfil; cualquier identidad dudosa aborta todo."""
    prefix='nc' if topology=='geant2' else 'ns'
    expected={prefix+n['switch'][1:]:n for n in profile['nodes']}
    bridges=[b for b in snapshot['bridges'] if b['name'] in expected]
    if not bridges:return []
    if owners:raise ValueError('Hay un proceso propietario; se conserva la red: '+str(owners))
    ports={p['_uuid']:p for p in snapshot['ports']}
    interfaces={i['_uuid']:i for i in snapshot['interfaces']}
    controllers={c['_uuid']:c for c in snapshot['controllers']}
    kernel=set(snapshot['kernel_interfaces'])
    if any(re.fullmatch(prefix+r'[0-9]+-eth[0-9]+',name) for name in kernel):
        raise ValueError('Existen interfaces Linux de esta topologia; no es una red huerfana.')
    for bridge in bridges:
        name=bridge['name'];node=expected[name]
        if str(bridge['datapath_id']).lower()!=node['dpid'].lower():
            raise ValueError('DPID diferente en '+name)
        configured=values(bridge['controller'])
        if not configured or any(controllers[c]['target']!='tcp:{}:{}'.format(controller_ip,openflow_port) for c in configured):
            raise ValueError('Controlador diferente en '+name)
        allowed={name,name+'-eth'+str(node['host_port'])}
        for edge in profile['links']:
            for side in ('u','v'):
                if edge['switch_'+side]==node['switch']:
                    allowed.add(name+'-eth'+str(edge['port_'+side]))
        for pid in values(bridge['ports']):
            port=ports[pid]
            if port['name'] not in allowed:raise ValueError('Puerto no reconocido en '+name)
            for iid in values(port['interfaces']):
                interface=interfaces[iid]
                if interface['name']!=port['name']:raise ValueError('Identidad de interfaz distinta en '+name)
                if interface['name']==name:
                    if interface['type']!='internal':raise ValueError('Interfaz local no reconocida')
                elif (interface['name'] in kernel or interface['type'] not in ('','system')
                      or interface['ofport']!=-1 or not interface['error']):
                    raise ValueError('Puerto activo o estado dudoso en '+name)
    return sorted(b['name'] for b in bridges)


def backup_and_remove(base,snapshot,names):
    if not names:return None
    # La lista procede de la validacion completa anterior, nunca de un comodin del shell.
    if any(not re.fullmatch(r'(?:nc|ns)[1-9][0-9]*',n) for n in names):raise ValueError('Nombre fuera del alcance')
    stamp=datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ')
    directory=base.parents[1]/'backups'/('recuperacion_ovs_'+stamp)
    directory.mkdir(parents=True,mode=0o700)
    data=subprocess.check_output(['ovsdb-client','backup','unix:/var/run/openvswitch/db.sock','Open_vSwitch'])
    file=directory/'ovsdb.backup';file.write_bytes(data);file.chmod(0o600)
    (directory/'inspeccion.json').write_text(json.dumps(snapshot,indent=2))
    (directory/'retirada.json').write_text(json.dumps({'bridges':names,'backup_sha256':hashlib.sha256(data).hexdigest()},indent=2))
    # Rechaza cambios concurrentes antes de ejecutar la transaccion.
    if inspect_ovs()!=snapshot:raise ValueError('OVS cambio durante la comprobacion; se conserva todo.')
    args=['ovs-vsctl']
    for name in names:args+=['--','--if-exists','del-br',name]
    subprocess.check_call(args)
    return str(directory)
