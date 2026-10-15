from cad_cf.mock_backend import initial_state
from cad_cf.typed_freecad import TypedFreeCAD

class Session:
    def __init__(self):self.events=[]
    def commit_close(self,path):self.events.append('close');return {'closed':True,'saved':True}
    def reopen(self,path):self.events.append('reopen')
    def refresh_screenshot(self):self.events.append('screenshot');return b'NEW'
    def summary(self):return initial_state()

def test_ui_refresh():
    s=Session()
    def worker(request):
        assert s.events==['close']
        s.events.append('api')
        return dict(ok=True,reopened=True,recomputed=True,state=initial_state())
    result=TypedFreeCAD('/home/user/current',s,worker).execute([], '/home/user/current/in.FCStd','/home/user/current/out.FCStd')
    assert s.events==['close','api','reopen','screenshot']
    assert result['screenshot']==b'NEW'


def test_known_invalid_shape_is_measured_failure():
    session=Session()
    worker=lambda request:dict(ok=False,reopened=True,recomputed=True,state=initial_state())
    result=TypedFreeCAD('/home/user/current',session,worker).execute([], '/home/user/current/in.FCStd','/home/user/current/out.FCStd')
    assert result['result']['ok'] is False
    assert session.events==['close','reopen','screenshot']
