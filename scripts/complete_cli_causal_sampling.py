#!/usr/bin/env python3
"""Complete the unsampled task using the same four-call ledger and frozen prompt."""
import argparse
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cad_cf.batch_budget import BatchBudget
from cad_cf.cli_causal_credit import candidate_code,freeze,messages
from scripts.run_cli_model_pair import collect_candidates
from scripts.run_structural_credit_diagnostic import save


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();source=a.source.resolve();output=a.output.resolve();output.mkdir(parents=True,exist_ok=False)
    config=json.loads((source/'config.json').read_text());plan=json.loads((source/'plan.json').read_text())
    proof=json.loads((source/'pre_request_control_proof.json').read_text())
    assert proof['status']=='PASS' and len(proof['completed_controls'])==2
    ledger=source/'model_batch.sqlite';batch=BatchBudget(ledger,4,8192);before=batch.status();batch.close()
    assert before['requests']==2 and before['remaining_calls']==2 and not before['blocked']
    pair=copy.deepcopy(next(x for x in plan['pairs'] if x['id']=='freecad-part-014'))
    assert not (source/'freecad-part-014-model').exists()
    prepared=json.loads((source/'prepare/observation.json').read_text());seed=prepared['seeds'][pair['id']]
    save(output/'source_reference.json',{'source_run':str(source),'shared_ledger':str(ledger),'prior_requests':2,
        'remaining_requests':2,'same_prompt_protocol':True,'no_new_s0':True,'control_proof':proof})
    folder=output/'freecad-part-014-model';folder.mkdir();save(folder/'captured_s0.json',seed)
    b=seed['spec']['binding'];cfg={'model':config['candidate_generation']['model'],'temperature':.7,'max_model_calls':4,
         'max_model_output_tokens':8192,'per_call_tokens':2048,'model_timeout_seconds':110,'model_wall_seconds':600}
    try:
        collect_candidates(pair,seed,folder,cfg,code_parser=lambda text:candidate_code(text,body_name=b['body'],sketch_name=b['sketch']),
                           message_builder=messages,budget_path=ledger)
    except RuntimeError as exc:
        if str(exc).startswith('CANDIDATE_REJECTED:'):pair['candidate_interface_rejected']=True
        else:raise
    freeze(pair);save(output/'pair.json',pair)
    batch=BatchBudget(ledger,4,8192);after=batch.status();batch.close();save(output/'shared_budget_final.json',after)
    save(output/'summary.json',{'status':'CANDIDATE_REJECTED' if pair.get('candidate_interface_rejected') else 'READY_FOR_NATIVE_EXECUTION',
        'new_requests':2,'total_batch_requests':after['requests'],'native_dispatches':0,'model_code_edited':False,'training_rows':0})
    print((output/'summary.json').read_text(),flush=True)


if __name__=='__main__':main()
