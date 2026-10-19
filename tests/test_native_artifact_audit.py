from scripts.audit_native_artifact import review_audit


def test_native_invalid_flag_overrides_valid_shape_and_zero_solver():
    record={'native_tree_restored':True,'native_open_recompute_reopen':True,'saved_file_unchanged':True,
        'reopened_objects':[{'name':'Sketch','state':['Touched','Invalid'],'shape_valid':True,'solver_return':0}]}
    result=review_audit(record)
    assert result['status']=='FAIL_NATIVE_ARTIFACT_AUDIT' and not result['native_state_valid']
    assert result['native_errors'][0]['reason']=='native_object_state'


def test_touched_without_invalid_is_not_an_error():
    record={'native_tree_restored':True,'native_open_recompute_reopen':True,'saved_file_unchanged':True,
        'reopened_objects':[{'name':'Sketch','state':['Touched'],'shape_valid':True,'solver_return':0}]}
    assert review_audit(record)['status']=='PASS_NATIVE_ARTIFACT_AUDIT'


def test_failed_parameter_edit_is_not_reported_as_full_audit_pass():
    record={'native_tree_restored':True,'native_open_recompute_reopen':True,'saved_file_unchanged':True,
        'reopened_objects':[{'name':'Sketch','state':['Up-to-date'],'shape_valid':True,'solver_return':0}],
        'parameter_edit_probe':{'applicable':True,'changed':False,'solver_return':0}}
    reviewed=review_audit(record)
    assert reviewed['native_state_valid']
    assert reviewed['parameter_editability']=='FAIL' and reviewed['status']=='FAIL_NATIVE_ARTIFACT_AUDIT'
