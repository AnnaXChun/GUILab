from dataclasses import replace
import pytest
from cad_cf.snapshot import prove_live_isolation,InvalidPair
from cad_cf.typed_freecad import TypedFreeCAD
from cad_cf.mock_backend import initial_state
from test_ui_refresh import Session


def test_distinct_vm_attestation_required(checkpoint):
    cp=replace(checkpoint,vm_checkpoint_sha256='disk')
    gui=dict(vm_id='a',endpoint='http://a:5000',overlay='a.qcow2',source_checkpoint_sha256='disk',powered_off_source=True)
    api={**gui,'vm_id':'b','endpoint':'http://b:5000','overlay':'b.qcow2'}
    prove_live_isolation(gui,api,cp)
    with pytest.raises(InvalidPair):prove_live_isolation(gui,{**api,'endpoint':gui['endpoint']},cp)
    with pytest.raises(InvalidPair):prove_live_isolation(gui,{**api,'source_checkpoint_sha256':'other'},cp)


def test_ui_wrong_state_refused():
    class Stale(Session):
        def summary(self):return {'objects':[]}
    session=Stale()
    worker=lambda req:dict(ok=True,reopened=True,recomputed=True,state=initial_state())
    with pytest.raises(RuntimeError,match='synchronization'):
        TypedFreeCAD('/home/user/current',session,worker).execute([], '/home/user/current/in.FCStd','/home/user/current/out.FCStd')
