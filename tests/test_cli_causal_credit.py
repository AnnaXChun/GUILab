import copy
import json

import pytest

from cad_cf.cli_causal_credit import candidate_code,evaluate,expected,freeze,messages,observation_checks
from scripts.run_cli_causal_credit import restored_worker

PAD="body=doc.getObject('Body')\nsketch=doc.getObject('Sketch')\npad=body.newObject('PartDesign::Pad','Pad')\npad.Profile=sketch\npad.Length=12\nbody.Tip=pad\n"


def spec(task='freecad-part-001'):
    return {'task_id':task,'pad_length':12 if task.endswith('001') else 10,
            'binding':{'body':'Body','sketch':'Sketch','radius':5 if task.endswith('001') else 10.25,
                'center_local':[0,0,0] if task.endswith('001') else [0,-2.25,0],
                'normal_global':[0,-1,0],'sketch_placement':[1,0,0,0,0,0,-1,0,0,1,0,0,0,0,0,1]}}


def observed(s,probe=None):
    x=expected(s,probe)
    shape={k:x[k] for k in ('area','volume','bbox','com')};shape.update(valid=True,solids=1)
    return {**{k:x[k] for k in ('radius','pad_length','pocket_depth')},'final':{'type_id':'PartDesign::Pocket' if s['task_id'].endswith('014') else 'PartDesign::Pad','shape':shape,'errors':[]},
        'pad':{'type_id':'PartDesign::Pad'},'guard':{'shape':{'volume':72 if probe and probe['id']=='guard' else 60}},
        'audit_volume':x['volume'] if s['task_id'].endswith('001') else None}


def fixture_pair():
    s=spec()
    return freeze({'id':'fixture','classification':'MOCK_ONLY','intent':{'instruction':'public'},'spec':s,
        'probes':[{'id':'zero','factor':1},{'id':'pad-length-1.2','factor':1.2},{'id':'guard','factor':1.2}],
        'continuation':'fixed','candidates':{'A':PAD,'B':PAD}})


def fixture_observation(pair,branch):
    row={'seed_sha256':'seed','seed_state_sha256':'state','native_reopen_equal':True,'source_seed_unchanged':True,
         'probes_from_artifact_copies':True,'protected_source_preserved':True,'candidate_executions':1,
         'artifact_sha256':'artifact-'+branch,'pid':1 if branch=='A' else 2,'workdir':'/mock/'+branch,
         'reopened':observed(pair['spec']),'probes':[]}
    row.update({k:v[branch] if k=='candidate_sha256' else v for k,v in pair['hashes'].items()})
    row['probes']=[{'id':p['id'],'observation':observed(pair['spec'],p),'source_artifact_sha256':row['artifact_sha256'],
        'candidate_reexecuted':False,'suffix_reexecuted':False} for p in pair['probes']]
    return row


def test_rotated_offset_profile_contract_uses_supplied_geometry():
    s=spec('freecad-part-014');x=expected(s)
    assert x['bbox']==pytest.approx([-10.25,-10,-12.5,10.25,0,8])
    assert x['com'][2]==pytest.approx(-2.25)
    assert observation_checks(observed(s),s)==(1,[])
    bad=observed(s);bad['final']['shape']['com'][2]=0
    assert 'geometry_com' in observation_checks(bad,s)[1]


def test_same_initial_shape_but_stale_parameter_response_is_distinguished():
    p=fixture_pair();a=fixture_observation(p,'A');b=fixture_observation(p,'B')
    # Explicit synthetic stale geometry; never used as a real model result.
    b['probes'][1]['observation']['final']['shape']=copy.deepcopy(b['reopened']['final']['shape'])
    r=evaluate(p,a,b)
    assert r['pair_valid'] and r['credit']==1 and r['response_discriminating']
    assert r['A']['initial_proxy_q']==r['B']['initial_proxy_q']==1


@pytest.mark.parametrize('mutate',[lambda x:x.update(seed_sha256='other'),lambda x:x.update(spec_sha256='other'),
    lambda x:x.update(candidate_executions=2),lambda x:x.update(pid=1),
    lambda x:x['probes'][0].update(suffix_reexecuted=True),lambda x:x['probes'][0].update(source_artifact_sha256='other')])
def test_bad_pair_proof_keeps_credit_unknown(mutate):
    p=fixture_pair();a=fixture_observation(p,'A');b=fixture_observation(p,'B');mutate(b)
    r=evaluate(p,a,b);assert not r['pair_valid'] and r['credit'] is None


def test_irrelevant_note_does_not_change_quality():
    p=fixture_pair();a=fixture_observation(p,'A');b=fixture_observation(p,'B')
    a['reopened']['audit_note_text']='control-A';b['reopened']['audit_note_text']='control-B'
    assert evaluate(p,a,b)['credit']==0


def test_missing_compound_mass_metrics_are_unknown():
    s=spec();row=observed(s);row['final']['shape']['com']=None
    assert observation_checks(row,s)==(None,['unsupported_final_shape_metrics'])


def test_model_block_keeps_original_text_and_bindings():
    assert candidate_code('```json\n'+json.dumps({'code':PAD})+'\n```')==PAD
    for code in (PAD.replace("'Body'","'Guard'"),PAD+"sketch.Placement.Base.x=3",PAD+"doc.saveAs('file')",PAD+"body.Placement=pad.Placement",PAD+"pad=sketch",'import os'):
        with pytest.raises(ValueError):candidate_code(json.dumps({'code':code}))


def test_model_input_excludes_trusted_results_and_worker_compiles():
    p=fixture_pair();seed={'spec':p['spec'],'native_state':{'objects':[]},'seed_sha256':'seed','seed_state_sha256':'state',
                        'trusted_test':{'answer':'PRIVATE_VERIFIER_OUTPUT'}}
    msg=messages(p,seed)
    assert 'PRIVATE_VERIFIER_OUTPUT' not in json.dumps(msg)
    assert msg==messages(p,seed)
    compile(restored_worker({'seeds':{}}),'worker','exec')
