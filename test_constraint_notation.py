import pytest
from backend.agents.question_generator import validate_stress_spec_constraints


def spec():
    return {'generator_type': 'array_n_k',
            'parameters': {'n_min': 1, 'n_max': 100000, 'k_min': 1, 'k_max': 100,
                           'value_min': -1000, 'value_max': 1000},
            'constraint_bounds': {'n': {'min': 1, 'max': 100000},
                                  'k': {'min': 1, 'max': 100},
                                  'value': {'min': -1000, 'max': 1000}}}


def test_unicode_and_power_bounds_match():
    assert validate_stress_spec_constraints(
        ['1 \u2264 N \u2264 10^5', '1 <= K <= 100', '\u221210**3 \u2264 arr[i] \u2264 10^3'], spec())


def test_unicode_bounds_still_reject_mismatch():
    with pytest.raises(ValueError, match='do not match'):
        validate_stress_spec_constraints(
            ['1 \u2264 n \u2264 10^4', '1 <= k <= 100', '-1000 <= arr[i] <= 1000'], spec())

@pytest.mark.parametrize('value_constraint', [
    '|arr[i]| <= 1000',
    'abs(nums[i]) <= 10^3',
    '|a[i]| \u2264 1e3',
    '1000 >= values[i] >= -1000',
    '-10^{3} <= `nums[i]` <= 10^{3}',
    '-1000 <= arr[i-1] <= 1000',
    'arr[i] >= -1000, arr[i] <= 1000',
])
def test_alternative_array_value_constraints(value_constraint):
    assert validate_stress_spec_constraints(['1 <= n <= 100000', '1 <= k <= 100', value_constraint], spec())


@pytest.mark.parametrize('value_constraint', ['|arr[i]| <= 100', '100 >= arr[i] >= -100', '-10 <= arr[i] <= 1000'])
def test_alternative_value_notation_still_rejects_wrong_bounds(value_constraint):
    with pytest.raises(ValueError,match='do not match'):
        validate_stress_spec_constraints(['1 <= n <= 100000', '1 <= k <= 100', value_constraint],spec())


def test_different_arrays_cannot_supply_each_others_missing_bound():
    with pytest.raises(ValueError,match='Cannot extract.*value'):
        validate_stress_spec_constraints(['1 <= n <= 100000','1 <= k <= 100','arr[i] >= -1000','nums[i] <= 1000'],spec())


def test_decimal_value_bounds_cannot_be_truncated_to_integers():
    with pytest.raises(ValueError,match='Cannot extract.*value'):
        validate_stress_spec_constraints(['1 <= n <= 100000','1 <= k <= 100','-1000 <= arr[i] <= 1000.5'],spec())

def test_textual_bounds_failures_are_corrected_inside_core_phase():
    import json
    from types import SimpleNamespace
    from unittest.mock import patch
    import backend.agents.question_generator as qg
    bad={'constraints':['1 <= n <= 100000','1 <= k <= 100','array values are small'],'stress_test_spec':spec()}
    good={'constraints':['1 <= n <= 100000','1 <= k <= 100','|arr[i]| <= 1000'],'stress_test_spec':spec()}
    def response(data):
        return SimpleNamespace(content=json.dumps(data),response_metadata={},usage_metadata={})
    with patch.object(qg,'validate_core_response'), patch.object(qg,'generator_llm') as llm:
        llm.invoke.side_effect=[response(bad),response(good)]
        result=qg.generate_phase_json('Generate a problem','Core Problem Generation',validator=qg.validate_generated_core_response)
        assert result==good
        assert llm.invoke.call_count==2
        assert 'Cannot extract textual constraint bounds for value' in llm.invoke.call_args.args[0]
        assert 'array values are small' in llm.invoke.call_args.args[0]

@pytest.mark.parametrize('variable',['a_i','a_{i}','nums_i','arr_{i-1}','a_0'])
def test_reported_mathematical_subscript_constraints(variable):
    stress=spec()
    stress['parameters'].update(k_min=-1000000000,k_max=1000000000,value_min=-1000000000,value_max=1000000000)
    stress['constraint_bounds'].update(k={'min':-1000000000,'max':1000000000},value={'min':-1000000000,'max':1000000000})
    constraints=['1 <= N <= 100000','-10^9 <= K <= 10^9',f'-10^9 <= {variable} <= 10^9']
    assert validate_stress_spec_constraints(constraints,stress)


def test_subscript_and_bracket_notation_share_the_same_bounds():
    assert validate_stress_spec_constraints(['1 <= n <= 100000','1 <= k <= 100','a_i >= -1000','a[i] <= 1000'],spec())


def test_subscript_bounds_still_reject_mismatch():
    with pytest.raises(ValueError,match='do not match'):
        validate_stress_spec_constraints(['1 <= n <= 100000','1 <= k <= 100','-100 <= a_i <= 100'],spec())


def test_scalar_underscore_names_are_not_array_elements():
    with pytest.raises(ValueError,match='Cannot extract.*value'):
        validate_stress_spec_constraints(['1 <= n <= 100000','1 <= k <= 100','-1000 <= value_min <= 1000'],spec())
