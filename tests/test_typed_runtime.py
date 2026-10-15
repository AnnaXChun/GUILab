import pytest
from cad_cf.freecad_worker import execute
from cad_cf.tool_protocol import TypedAction

class Obj:
    Name='Pad'
    TypeId='PartDesign::Pad'
    PropertiesList=['Length']
    ExpressionEngine=[]
    Length=10.
    def getTypeIdOfProperty(self,key):return self.property_type
    def getEditorMode(self,key):return 0
class Doc:
    def __init__(self,obj):self.obj=obj
    def getObject(self,name):return self.obj if name=='Pad' else None

@pytest.mark.parametrize('wrong',['type','missing','expression','property_type'])
def test_native_introspection_rejects_wrong_preconditions(monkeypatch,wrong):
    import sys
    monkeypatch.setitem(sys.modules,'FreeCAD',object())
    obj=Obj();obj.property_type='App::PropertyLength'
    args=dict(object_name='Pad',type_id='PartDesign::Pad',property='Length',value=12.)
    if wrong=='type':args['type_id']='PartDesign::Pocket'
    if wrong=='missing':args['object_name']='Absent'
    if wrong=='expression':obj.ExpressionEngine=[('Length','Sketch.Radius')]
    if wrong=='property_type':obj.property_type='App::PropertyString'
    with pytest.raises((ValueError,TypeError)):
        execute(Doc(obj),TypedAction('set_object_property',args),'/home/user/current')
    assert obj.Length==10.
