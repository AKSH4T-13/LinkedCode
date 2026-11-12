import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
import backend.agents.question_generator as qg

REPORTED=['1 \u2264 N \u2264 100000','-1 \u2264 P[i] < i for all i > 1','The input describes a valid rooted tree.']


def test_reported_parent_tree_is_not_misdiagnosed_as_value_notation():
    with pytest.raises(ValueError,match='Unsupported input structure'):
        qg.validate_generated_core_response({'constraints':REPORTED,'input_format':'N and a parent array P.'})


@pytest.mark.parametrize('format', ['N followed by a parent array.','N followed by an edge list.','The next n-1 edges describe the tree.'])
def test_structural_inputs_cannot_masquerade_as_independent_arrays(format):
    with pytest.raises(ValueError,match='Unsupported input structure'):
        qg.validate_supported_input_contract({'constraints':['1 <= n <= 100'], 'input_format':format})


def test_tree_topics_remain_supported_with_implicit_structure():
    qg.validate_supported_input_contract({'topics':['Tree'],'constraints':['1 <= n <= 100000','-1000 <= arr[i] <= 1000'],
                                        'input_format':'N followed by N weights of an implicit complete binary tree.'})


def test_core_prompt_requires_valid_independent_arrays_for_tree_history():
    prompt=qg.build_core_prompt(['Tree','Depth-First Search'],'Medium')
    assert 'P[i] < i' in prompt
    assert 'implicitly COMPLETE BINARY' in prompt
    assert 'Every combination' in prompt
    assert 'Never invent fake value bounds' in prompt


def test_unsupported_tree_feedback_can_recover_to_supported_problem_in_same_phase():
    bad={'constraints':REPORTED,'input_format':'N and parent indices.'}
    good={'topics':['Tree'],'constraints':['1 <= n <= 100000','-1000 <= arr[i] <= 1000'],
          'input_format':'N followed by N weights of an implicit complete binary tree.','stress_test_spec':{}}
    def response(data):return SimpleNamespace(content=json.dumps(data),response_metadata={},usage_metadata={})
    with patch.object(qg,'generator_llm') as llm, patch.object(qg,'validate_core_response'),patch.object(qg,'validate_stress_spec_constraints'):
        llm.invoke.side_effect=[response(bad),response(good)]
        result=qg.generate_phase_json(qg.build_core_prompt(['Tree'],'Medium'),'Core Problem Generation',validator=qg.validate_generated_core_response)
        assert result==good
        assert llm.invoke.call_count==2
        assert 'Unsupported input structure' in llm.invoke.call_args.args[0]
