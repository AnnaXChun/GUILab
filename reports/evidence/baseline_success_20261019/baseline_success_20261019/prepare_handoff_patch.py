"""Build current JSON handoff from offline evidence; stdout is an apply_patch input."""
from pathlib import Path
import datetime
import json

root=Path.cwd();base=root/'results/baseline_success_20261019'
s=json.loads((base/'campaign_summary.json').read_text())
episodes=s['episodes'];gui=next(row for row in episodes if row['run_id']=='success_gui_qwen122_001')
gui_score_ok=gui['strict']==1.0
native=s.get('native_gui_audit')
native_ok=bool(native and native['status']=='PASS_NATIVE_ARTIFACT_AUDIT')
cli122_native=s.get('native_cli122_audit')
cli122_native_ok=bool(cli122_native and cli122_native['status']=='PASS_NATIVE_ARTIFACT_AUDIT')
evidence='reports/evidence/baseline_success_20261019/baseline_success_20261019/campaign_summary.json'
latest={
 'classification':'bounded_baseline_continuation','evidence':evidence,'reference_kvm_gate_passed':False,
 'models':sorted({row['model'] for row in episodes}),'attempts':len(episodes),
 'evaluated_episodes':sum(row['strict'] is not None for row in episodes),
 'run_errors':sum(row['strict'] is None for row in episodes),'real_pairs':0,
 'episodes':[{key:row.get(key) for key in ('run_id','kind','model','coordinate_history_protocol','task_id','status','strict','upstream_raw_score','model_calls','known_output_tokens','artifact_count')} for row in episodes],
 'official_cli_single_task_success':True,'official_gui_with_coordinate_adapter_single_task_success':gui_score_ok,
 'native_cli36_artifact_status':'FAIL_NATIVE_ARTIFACT_AUDIT',
 'native_gui_artifact_status':native['status'] if native else ('NOT_RUN_NO_ARTIFACT' if gui['artifact_count']==0 else 'UNAVAILABLE_AUDITOR_ERROR'),
 'native_cli122_artifact_status':cli122_native['status'] if cli122_native else 'UNAVAILABLE_AUDITOR_ERROR',
 'project_tests':s['project_tests'],'upstream_cli_tests':7,
 'generation_calls_total_including_history':s['generation_calls_total_including_history'],
 'known_output_tokens_total_including_history':s['known_output_tokens_total_including_history'],
 'known_input_tokens_total_including_history':s['known_input_tokens_total_including_history'],
 'unknown_output_reservation_total':s['unknown_output_reservation_total'],
 'total_output_tokens':None,'total_cost_usd':None,'paper_reproduced':False,
 'all_vms_stopped':s['all_continuation_vms_stopped'] and s['all_audit_vms_stopped'],
 'budget_snapshots':[{k:v for k,v in row.items() if k!='request_records'} for row in s['budgets']],
 'pooled_success_rate':None,'pooled_success_rate_reason':s['success_rate_reason']}
handoff=json.loads((root/'handoff.json').read_text())
handoff.update(updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 read_first=['AGENTS.md','reports/BASELINE_SUCCESS_SMOKE.md','HANDOFF.md'],
 next_phase='P0',next_action='Run model-free GUI attachment-panel/event-loop diagnostics, then accept formal TypedWorker/Qt bridge save-reopen synchronization and same-S0 double-clone restore. Follow docs/NEXT_ACTC_VALIDATION.md; no new inference or pair/training GO yet.',
 execution_location='Authorized local Mac native QEMU/TCG continuation; remote must validate its own assets, environment and secrets.',
 baseline_smoke=latest,baseline_continuation_authorized=True)
handoff['baseline_history_first_batch']=json.loads((root/'reports/evidence/baseline_runtime_20261019/campaign_summary.json').read_text())['batch_status']
handoff['historical_evidence'].update(real_tasks=2,real_episodes=3)
handoff['known_constraints']=[
 'All earlier ledgers, failed requests and unknown usage reservations retained; do not replay completed campaigns.',
 'Reference Linux/KVM gate not passed; user cannot provide KVM; do not request it again.',
 'Qwen normalized-coordinate GUI adapter v1 mixed pixel execution in online history; v2 fixes units; report protocols separately.',
 'Qwen3.6 CLI score=1 but saved Sketch.Invalid/attachment error; exclude that artifact from valid training data.',
 'Qwen3.5-122B CLI score=1 and native audit PASS; agent terminated at turn_limit, not finish.',
 'sketch-061 was repeatedly used for debugging/model selection; not an unseen held-out result.',
 'No full 405-package upstream sync; no model weights downloaded.',
 'Formal TypedWorker/GUI bridge/same-S0 paired runtime not yet validated; real ACTC pairs=0.',
 'Provider aliases do not prove backend weight identity; price/initial HTTP500 usage unknown.']
handoff['go_no_go']={'baseline_infrastructure':'GO','official_cli_single_task':'GO',
 'model_free_gui_diagnostics':'GO',
 'gui_coordinate_adapter_single_task':'GO' if gui_score_ok else 'NO-GO',
 'native_valid_gui_artifact':'GO' if native_ok else 'NO-GO',
 'native_valid_cli122_artifact':'GO' if cli122_native_ok else 'NO-GO',
 'paper_reproduction':'NO-GO','more_generation_in_completed_batches':'NO-GO','actc_pairs':'NO-GO','P4_training':'NO-GO'}
handoff['mac_infrastructure_result'].update(paper_reproduced=False,official_cli_single_task_success=True,
 model_calls=s['generation_calls_total_including_history'],all_qemu_stopped=latest['all_vms_stopped'])
handoff['mac_infrastructure_result']['model_calls_scope']='Combined baseline/probe evidence, not the trusted infrastructure macro itself.'
handoff['mac_infrastructure_result']['evidence']=evidence
handoff['vm_asset_observed']['verified_on']='2026-10-19'
handoff['environment_route']['next_guide']='docs/NEXT_ACTC_VALIDATION.md'
handoff['baseline_smoke']['attempts_including_first_batch']=len(episodes)+3
handoff['baseline_smoke']['evaluated_episodes_including_first_batch']=latest['evaluated_episodes']+3
handoff['baseline_smoke']['held_out_estimate']=False
handoff['authorized_real_smoke']['scope']='Historical initial batch, already consumed; continuation scope is in explicit campaign configs and baseline_smoke.'
stages=json.loads((root/'reports/stages.json').read_text())
stages['P0'].update(evidence=evidence,go=False)
stages['P1'].update(live_status='NOT_RUN_P0_GATE',native_save_reopen='NOT_RUN_FORMAL_WORKER',go=False)
stages['P2'].update(live_status='NOT_RUN_P1_GATE',real_pairs=0,go=False)
stages['P3'].update(live_status='NOT_RUN_P2_GATE',smoke_real_valid_pairs=0,go=False)
stages['exploratory_tcg_first_batch']=stages['exploratory_tcg']
stages['exploratory_tcg']=latest
print('*** Begin Patch')
for path,data in [('handoff.json',handoff),('reports/stages.json',stages)]:
 print('*** Update File: '+str(root/path));print('@@')
 for line in (root/path).read_text().splitlines():print('-'+line)
 for line in json.dumps(data,ensure_ascii=False,indent=2).splitlines():print('+'+line)
print('*** End Patch')
