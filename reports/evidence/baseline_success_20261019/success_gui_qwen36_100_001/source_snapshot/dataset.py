"""P4 input boundary: export only real, audited, non-tie TRAIN preferences."""
from collections import Counter
import math


def preference_rows(pairs, splits):
    rows, rejected = [], Counter()
    train = set(splits['splits']['train'])
    for pair in pairs:
        reason = None
        if pair.get('synthetic') is not False:reason='synthetic_or_unknown_origin'
        elif not pair.get('pair_valid'):reason='invalid_pair'
        elif pair.get('task_split') != 'train' or pair.get('task_id') not in train:reason='not_train'
        elif pair.get('label') not in ('gui','api') or pair.get('credit_delta') is None:reason='tie_or_unknown_credit'
        elif not math.isfinite(pair['credit_delta']) or (pair['credit_delta'] > 0) != (pair['label'] == 'api') or pair['credit_delta'] == 0:reason='inconsistent_credit'
        elif pair.get('label_source') != 'public_contract_only' or not pair.get('leakage_audit_passed'):reason='audit_failed'
        elif set(pair.get('branches',{})) != {'gui','api'}:reason='incomplete_pair'
        else:
            for branch in pair['branches'].values():
                if not {'validity','target_progress','preservation','editability'} <= set(branch.get('checks',{})):
                    reason='incomplete_checks'
                if branch.get('state_before') != pair['s0']['canonical_state_digest']:
                    reason='different_S0'
                for check in branch.get('checks',{}).values():
                    if check['applicable'] and (check['value'] is None or check['confidence'] < .9):
                        reason='uncertain_quality'
                if not branch.get('checks',{}).get('target_progress',{}).get('applicable'):
                    reason='unknown_target'
        if reason:
            rejected[reason]+=1
            continue
        rows.append({k:pair[k] for k in ('pair_id','task_id','intent','s0','label','credit_delta','label_source')})
    return rows,dict(rejected)
