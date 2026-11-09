import copy
from pathlib import Path
import importlib.util
import pytest

path=Path(__file__).resolve().parents[1]/'laboratorio/mininet/recuperacion_ovs.py'
spec=importlib.util.spec_from_file_location('recuperacion_ovs_test',str(path))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def fixture():
    profile={'nodes':[{'switch':'s1','dpid':'0000000000000001','host_port':1}], 'links':[]}
    snapshot={'bridges':[{'name':'nc1','datapath_id':'0000000000000001','ports':['p0','p1'],'controller':['c']}],
      'ports':[{'_uuid':'p0','name':'nc1','interfaces':['i0']},{'_uuid':'p1','name':'nc1-eth1','interfaces':['i1']}],
      'interfaces':[{'_uuid':'i0','name':'nc1','type':'internal','ofport':4294967294,'error':[]},
                    {'_uuid':'i1','name':'nc1-eth1','type':'','ofport':-1,'error':'No such device'}],
      'controllers':[{'_uuid':'c','target':'tcp:192.168.56.108:16653'}], 'kernel_interfaces':['lo','nc1']}
    return snapshot,profile


def candidates(s,p,owners=None):return module.orphan_candidates(s,p,'geant2','192.168.56.108',16653,owners or [])


def test_huerfano_y_alcance():
    s,p=fixture();s['bridges'].append({'name':'ajeno'})
    assert candidates(s,p)==['nc1']


def test_propietario_o_enlace_linux_impide_retirada():
    s,p=fixture()
    with pytest.raises(ValueError):candidates(s,p,[42])
    s['kernel_interfaces'].append('nc1-eth1')
    with pytest.raises(ValueError):candidates(s,p)


@pytest.mark.parametrize('case',['dpid','controlador','puerto','activo'])
def test_identidad_o_estado_dudoso_impide_retirada(case):
    s,p=fixture()
    if case=='dpid':s['bridges'][0]['datapath_id']='0000000000000002'
    if case=='controlador':s['controllers'][0]['target']='tcp:192.168.56.108:16654'
    if case=='puerto':s['ports'][1]['name']='otro'
    if case=='activo':s['interfaces'][1]['ofport']=1
    with pytest.raises(ValueError):candidates(s,p)


def test_sin_bridges_no_retirada():
    s,p=fixture();s['bridges']=[]
    assert candidates(s,p)==[]
