import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from backend.agents.question_generator import audit_generated_solutions


def core():
    return {
        'title': 'Array Sum', 'difficulty': 'Easy', 'topics': ['Array'],
        'description': 'Print the sum.', 'constraints': ['1 <= n <= 100'],
        'examples': [], 'reference_solution': 'print(1)',
        'brute_force_solution': 'print(1)',
        'time_complexity': 'O(n)', 'space_complexity': 'O(1)', 'brute_force_complexity': 'O(n^2)',
    }


def report():
    return {
        'status': 'PASS',
        'optimized_analysis': 'Correct.',
        'brute_force_analysis': 'Correct.',
        'complexity_analysis': 'O(n) time and O(1) space.',
        'issues': [],
        'counterexamples': [],
        'correction_guidance': 'No corrections required.',
    }


def response(data):
    return SimpleNamespace(content=json.dumps(data), response_metadata={}, usage_metadata={})


@pytest.mark.parametrize('invalid', ['', {}, None])
def test_malformed_audit_is_retried(invalid):
    bad = report()
    bad['complexity_analysis'] = invalid
    with patch('backend.agents.question_generator.generator_llm') as llm:
        llm.invoke.side_effect = [response(bad), response(report())]
        assert audit_generated_solutions(core())['status'] == 'PASS'
        assert llm.invoke.call_count == 2
        assert 'Invalid solution audit field: complexity_analysis' in llm.invoke.call_args.args[0]


def test_malformed_audit_exhausts_bounded_retry_budget():
    bad = report()
    bad['complexity_analysis'] = {}
    with patch('backend.agents.question_generator.generator_llm') as llm:
        llm.invoke.return_value = response(bad)
        with pytest.raises(ValueError, match='Solution Audit failed after 2 attempts'):
            audit_generated_solutions(core())
        assert llm.invoke.call_count == 2

def test_correction_ignores_immutable_field_changes():
    from backend.agents.question_generator import run_solution_audit_loop
    original = core()
    bad = dict(original, examples=[{'input': 'changed'}])
    failed = dict(report(), status='FAIL', issues=['Incorrect solution.'])
    with patch('backend.agents.question_generator.audit_generated_solutions', side_effect=[failed, report()]), \
         patch('backend.agents.question_generator.validate_core_response'), \
         patch('backend.agents.question_generator.generator_llm') as llm:
        llm.invoke.side_effect = [response(bad), response(original)]
        corrected, audit = run_solution_audit_loop(original)
        assert corrected['examples'] == original['examples']
        assert audit['status'] == 'PASS'
        assert llm.invoke.call_count == 1
