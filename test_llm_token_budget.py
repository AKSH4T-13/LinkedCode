from unittest.mock import Mock
import pytest
from backend.llm.token_budget import invoke_budgeted,LLMBudgetExceeded
from backend.agents.question_refiner import build_refinement_prompt


class TooLarge(Exception):
    status_code=413


def test_reported_8110_request_reduces_reservation_and_retries_same_prompt():
    client=Mock()
    client.invoke.side_effect=[TooLarge('TPM: Limit 8000, Requested 8110'), 'success']
    assert invoke_budgeted(client,'complete code and constraints','Audit',3500)=='success'
    calls=client.invoke.call_args_list
    assert [call.args[0] for call in calls]==['complete code and constraints']*2
    assert calls[0].kwargs['max_tokens']==3500
    assert calls[1].kwargs['max_tokens']==3134


def test_completion_reservation_is_bounded_for_large_prompt():
    client=Mock(return_value=None)
    invoke_budgeted(client,'x'*12000,'Refinement',6000)
    assert client.invoke.call_args.kwargs['max_tokens'] < 6000
    assert client.invoke.call_args.args[0]=='x'*12000


def test_repeated_413_stops_without_sleeping_or_truncating():
    client=Mock();client.invoke.side_effect=TooLarge('Limit 8000, Requested 8110')
    with pytest.raises(LLMBudgetExceeded):invoke_budgeted(client,'original source','Phase',3500)
    assert client.invoke.call_count==2


def test_non_budget_error_is_not_retried_here():
    client=Mock();client.invoke.side_effect=RuntimeError('network failure')
    with pytest.raises(RuntimeError,match='network'):invoke_budgeted(client,'prompt','Phase')
    assert client.invoke.call_count==1


def test_refinement_prompt_keeps_problem_and_failures_but_omits_diagnostics():
    question={'title':'Keep me','reference_solution':'print(123)','test_cases':[{'input':'1','expected_output':'123'}],
              'stress_test_spec':{'generator_type':'array_n'},'brute_force_complexity':'O(n^2)',
              'quality_report':{'diagnostic':'DO_NOT_REPEAT_QUALITY'},'stress_test_report':{'diagnostic':'DO_NOT_REPEAT_STRESS'}}
    prompt=build_refinement_prompt(question,{'failed_cases':[{'input':'1','error':'wrong output'}]})
    assert all(text in prompt for text in ('Keep me','print(123)','wrong output','stress_test_spec','O(n^2)'))
    assert 'DO_NOT_REPEAT_QUALITY' not in prompt and 'DO_NOT_REPEAT_STRESS' not in prompt
    assert len(prompt)<4000
