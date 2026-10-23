#!/usr/bin/env python3
"""Model-free clone/contract audit after the rejected Pocket batch; no candidate repair."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cad_cf.cli_causal_credit import freeze
from cad_cf.cli_pocket_credit import evaluate_isolated
from scripts.run_cli_pocket_credit import verify_prepared, run_branch, file_sha
from scripts.run_structural_credit_diagnostic import save


def probe_worker(source):
    source = source.rsplit("if __name__=='__main__':", 1)[0]
    source += '''
original_execute=execute
def execute(request):
    result=original_execute(request)
    doc=App.openDocument(request['seed']['path'])
    try:
        pocket=doc.getObject('Pocket')
        contract={'length_property_type':pocket.getTypeIdOfProperty('Length'),
                  'depth_property_present':'Depth' in pocket.PropertiesList,
                  'type_enumerations':list(pocket.getEnumerationsOfProperty('Type')),
                  'base_feature_name':pocket.BaseFeature.Name}
        circle=Part.Circle()
        circle.Radius=4
        circle.Location=App.Vector(0,1,0)
        contract['local_circle_mutation_supported']=circle.Radius==4 and circle.Center.y==1
        try:App.Units.Quantity('6','mm')
        except Exception as exc:contract['two_string_quantity_status']=type(exc).__name__
        else:contract['two_string_quantity_status']='ACCEPTED'
        result['generic_native_contract']=contract
    finally:App.closeDocument(doc.Name)
    return result
if __name__=='__main__':
    request=json.loads(os.environ['STRUCTURAL_DIAGNOSTIC_REQUEST'])
    print(json.dumps(execute(request),allow_nan=False))
'''
    compile(source, 'clone_contract_probe_worker', 'exec')
    return source


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepared',type=Path,required=True)
    p.add_argument('--runtime-config',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    captured,disk,sha=verify_prepared(a.prepared.resolve())
    seed=captured['seeds']['pocket-control']
    original=json.loads((a.prepared/'frozen_pair_before_requests.json').read_text())
    original.update(id='clone-control',control=True,classification='synthetic_isolated_clone_contract_probe',
                    continuation='doc.recompute()',candidates={b:"doc.getObject('AuditNote').Text="+repr('control-'+b) for b in ('A','B')},
                    candidate_origins={b:'trusted_synthetic_control' for b in ('A','B')})
    freeze(original)
    output=a.output.resolve();output.mkdir(parents=True,exist_ok=False)
    save(output/'pair.json',original)
    worker=probe_worker((a.prepared/'deployed_worker.py').read_text())
    (output/'deployed_worker.py').write_text(worker)
    save(output/'source_manifest.json',{'scripts/probe_cli_pocket_clones.py':file_sha(Path(__file__).resolve()),
         'prepared_worker_sha256':file_sha(a.prepared/'deployed_worker.py'),
         'deployed_worker.py':file_sha(output/'deployed_worker.py'),'snapshot_sha256':sha})
    runtime=json.loads(a.runtime_config.read_text());runtime.update(base=str(disk),base_sha=sha)
    observations={}
    try:
        for b in ('A','B'):
            observations[b]=run_branch(original,seed,b,runtime,output/('branch_'+b),worker,sha)
    finally:
        row=evaluate_isolated(original,observations.get('A',{}),observations.get('B',{}))
        save(output/'pairs.json',[row])
        (output/'pair_trace.jsonl').write_text(json.dumps(row,allow_nan=False)+'\n')
        result={'status':'PASS_ISOLATED_CLONE_PROBE' if row['pair_valid'] and row['credit']==0 and row['A']['q']==row['B']['q']==1 else 'FAILED_ISOLATED_CLONE_PROBE',
                'model_calls':0,'synthetic_pair':True,'natural_pairs_added':0,'credit':row['credit'],
                'prepared_snapshot_unchanged':file_sha(disk)==sha,
                'contract':{b:observations[b].get('generic_native_contract') for b in observations},'training_rows':0}
        save(output/'summary.json',result)
        print(json.dumps(result),flush=True)
    return 0 if result['status']=='PASS_ISOLATED_CLONE_PROBE' else 1


if __name__=='__main__':raise SystemExit(main())
