import pytest
import requests
from cad_cf.terminal_bridge import TerminalBridge, ExecutionUncertain

class Transport:
    def __init__(self, failure): self.calls=[]; self.failure=failure
    def post(self,*args,**kwargs):
        self.calls.append((args,kwargs))
        if self.failure=='timeout': raise requests.ReadTimeout()
        response=requests.Response()
        response.status_code=500
        response._content=b'error'
        return response

@pytest.mark.parametrize('failure',['timeout','500'])
def test_no_double_mutation(tmp_path,failure):
    transport=Transport(failure)
    path=tmp_path/'ledger.sqlite'
    bridge=TerminalBridge('http://vm:5000','http://vm:5000',path,transport)
    with pytest.raises(ExecutionUncertain):bridge.execute(['FreeCADCmd','fixed.py'],execution_id='x')
    bridge.close()
    # Durable across process restart; no key-based replay unless the guest actually implements dedup.
    bridge=TerminalBridge('http://vm:5000','http://vm:5000',path,transport)
    with pytest.raises(ExecutionUncertain):bridge.execute(['FreeCADCmd','fixed.py'],execution_id='x')
    assert len(transport.calls)==1
    assert transport.calls[0][0][0].endswith('/execute')
    bridge.close()
