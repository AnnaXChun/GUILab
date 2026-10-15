import copy
import zipfile
from cad_cf.mock_backend import initial_state
from cad_cf.artifact_state import digest, container_check, dependency_closure

def test_object_order_and_volatile_metadata():
    a=initial_state()
    b=copy.deepcopy(a)
    b['objects'].reverse()
    b['zip_timestamp']='different'
    assert digest(a)==digest(b)
    b['objects'][0]['properties']['Length']=100
    assert digest(a)!=digest(b)

def test_dependency_closure():
    assert dependency_closure(initial_state(),'Sketch') == {'Sketch','Pad'}

def test_container_valid_does_not_imply_geometry(tmp_path):
    p=tmp_path/'dummy.zip'
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('Document.xml','<Document/>')
    assert container_check(p)['value'] is True
    p.write_bytes(b'broken')
    assert container_check(p)['value'] is False
