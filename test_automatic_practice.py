from unittest.mock import patch
import pytest
import backend.agents.question_generator as qg
from backend.services.practice_plan import build_practice_plan
from backend.services.candidate_service import get_unsolved_candidates


def test_plan_uses_last_twenty_questions_not_manual_preferences():
    questions=[{'difficulty':'Easy','topics':[{'name':'Array'}]} for _ in range(20)]
    questions.append({'difficulty':'Hard','topics':[{'name':'Graph'}]})
    plan=build_practice_plan({'analyzed_questions':questions,'difficulty_distribution':{'Hard':100}})
    assert plan['difficulty']=='Easy'
    assert plan['topics']==['Array']
    assert plan['sample_size']==20


def test_empty_history_has_automatic_starter_plan():
    plan=build_practice_plan({})
    assert plan['difficulty']=='Easy'
    assert plan['topics']==['Array']


def test_existing_candidates_rank_by_history_plan():
    profile={'practice_plan':{'difficulty':'Easy','topics':['Array']}}
    catalogue=[{'title_slug':'hard','difficulty':'Hard','topics':['Array']},
               {'title_slug':'easy','difficulty':'Easy','topics':['Array']}]
    assert get_unsolved_candidates(profile,catalogue,max_candidates=1)[0]['title_slug']=='easy'


def test_failed_audit_gets_one_new_draft_and_passes_profile_context():
    failure={'status':'FAIL','issues':['Incorrect invariant']}
    first={'title':'Bad'}; second={'title':'Fresh'}
    with patch.object(qg,'validate_generated_core_response'), patch.object(qg,'build_core_prompt',return_value='base'), \
         patch.object(qg,'run_solution_audit_loop',side_effect=[qg.SolutionAuditFailure(failure),(second,{'status':'PASS'})]) as audit, \
         patch.object(qg,'generate_phase_json',side_effect=[first,second,RuntimeError('reached oracle')]) as generate:
        with pytest.raises(RuntimeError,match='reached oracle'):
            qg.generate_dsa_question(['Array'],'Easy',user_profile={'analyzed_questions':[{'title':'Recent solved'}]})
        assert audit.call_count==2
        assert 'Recent solved' in generate.call_args_list[0].args[0]
        assert 'Incorrect invariant' in generate.call_args_list[1].args[0]
        assert generate.call_args_list[2].args[1]=='Oracle Generation'


def test_two_failed_drafts_stop_before_oracle():
    failure=qg.SolutionAuditFailure({'status':'FAIL','issues':['Wrong']})
    with patch.object(qg,'validate_generated_core_response'), patch.object(qg,'build_core_prompt',return_value='base'), \
         patch.object(qg,'run_solution_audit_loop',side_effect=failure), \
         patch.object(qg,'generate_phase_json',return_value={'title':'Bad'}) as generate:
        with pytest.raises(qg.SolutionAuditFailure):
            qg.generate_dsa_question(['Array'],'Easy')
        assert generate.call_count==2
