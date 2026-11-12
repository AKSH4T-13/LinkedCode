import copy
from unittest.mock import patch
import pytest
from backend.agents.question_generator import apply_solution_correction,SOLUTION_CORRECTION_FIELDS,run_solution_audit_loop


def original():
    return {'description':'ORIGINAL statement','examples':[{'input':'original','output':'original'}],
            'constraints':['original bounds'],'stress_test_spec':{'parameters':{'n_max':100}},
            'reference_solution':'print(1)','brute_force_solution':'print(1)',
            'time_complexity':'O(n)','space_complexity':'O(1)','brute_force_complexity':'O(n^2)'}


def solution_patch():
    return {'reference_solution':'print(2)','brute_force_solution':'print(2)',
            'time_complexity':'O(n)','space_complexity':'O(n)','brute_force_complexity':'O(n^2)'}


def test_patch_changes_solutions_without_returning_problem_fields():
    core=original();snapshot=copy.deepcopy(core)
    with patch('backend.agents.question_generator.validate_core_response') as validate:
        updated=apply_solution_correction(core,solution_patch())
    assert updated['reference_solution']=='print(2)'
    assert core==snapshot
    for field in ('description','examples','constraints','stress_test_spec'):
        assert updated[field]==snapshot[field]
        if isinstance(updated[field],(dict,list)): assert updated[field] is not core[field]
    validate.assert_called_once_with(updated)


def test_reported_rewritten_description_can_never_replace_original():
    correction=dict(solution_patch(),description='MODEL REWROTE THIS',examples=[],stress_test_spec={'parameters':{'n_max':1}})
    with patch('backend.agents.question_generator.validate_core_response'):
        updated=apply_solution_correction(original(),correction)
    assert updated['description']=='ORIGINAL statement'
    assert updated['examples']==original()['examples']
    assert updated['stress_test_spec']==original()['stress_test_spec']


@pytest.mark.parametrize('field',SOLUTION_CORRECTION_FIELDS)
def test_missing_solution_patch_fields_are_rejected(field):
    correction=solution_patch();del correction[field]
    with pytest.raises(ValueError,match='missing editable fields'):
        apply_solution_correction(original(),correction)


def test_invalid_solution_patch_still_fails_validation():
    with patch('backend.agents.question_generator.validate_core_response',side_effect=ValueError('Invalid Python')):
        with pytest.raises(ValueError,match='Invalid Python'):
            apply_solution_correction(original(),solution_patch())


def test_corrected_solution_is_audited_again_against_original_description():
    reports=[{'status':'FAIL'},{'status':'PASS'}]
    with patch('backend.agents.question_generator.validate_core_response'), \
         patch('backend.agents.question_generator.generate_phase_json',return_value=dict(solution_patch(),description='rewritten')), \
         patch('backend.agents.question_generator.audit_generated_solutions',side_effect=reports) as audit:
        updated,_=run_solution_audit_loop(original())
    assert audit.call_count==2
    assert audit.call_args_list[1].args[0]['description']=='ORIGINAL statement'
    assert updated['reference_solution']=='print(2)'
