import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.models import User,GeneratedQuestion,QuestionPerformanceSuite
from backend.services.performance_judge import build_performance_inputs,get_performance_cases
from backend.services.python_runner import ExecutionUnavailable


def data():
    return {'stress_test_spec':{'generator_type':'array_n','input_layout':'N followed by N values',
            'parameters':{'n_min':1,'n_max':10000,'value_min':-100,'value_max':100}},
            'reference_solution':'print(1)'}


def test_performance_cases_reach_actual_maximum_and_stay_hidden_after_calibration():
    cases=build_performance_inputs(data())
    assert len(cases)==3
    for case in cases:
        numbers=list(map(int,case['input'].split()))
        assert numbers[0]==10000 and len(numbers)==10001
        assert min(numbers[1:])>=-100 and max(numbers[1:])<=100


@pytest.fixture
def setup():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine);factory=sessionmaker(bind=engine)
    with factory() as db:
        db.add(User(id=1,email='test@example.com',password_hash='unused'));db.flush()
        question=GeneratedQuestion(user_id=1,title='Test',difficulty='Medium',topics=['Array'],question_data=data(),validation_report={'is_valid':True})
        db.add(question);db.commit()
        runner=SimpleNamespace(url='https://judge.test',language_id=100,evaluate=AsyncMock(return_value=[{'verdict':'Executed','stdout':'1','output_truncated':False} for _ in range(3)]))
        yield question,db,runner
    engine.dispose()


def test_reference_outputs_are_cached_and_reused(setup):
    question,db,runner=setup
    first=asyncio.run(get_performance_cases(question,db,runner))
    assert len(first)==3 and all(case['hidden'] and case['expected_output']=='1' for case in first)
    assert runner.evaluate.call_args.args[0]=='print(1)'
    assert db.query(QuestionPerformanceSuite).count()==1
    second=asyncio.run(get_performance_cases(question,db,runner))
    assert first==second
    assert runner.evaluate.call_count==1


def test_cache_invalidates_if_reference_or_provider_changes(setup):
    question,db,runner=setup
    asyncio.run(get_performance_cases(question,db,runner))
    runner.url='https://different.test'
    asyncio.run(get_performance_cases(question,db,runner))
    assert runner.evaluate.call_count==2


@pytest.mark.parametrize('verdict,truncated',[('Time limit exceeded',False),('Runtime error',False),('Executed',True)])
def test_reference_failure_or_truncated_expected_output_never_creates_suite(setup,verdict,truncated):
    question,db,runner=setup
    runner.evaluate.return_value=[{'verdict':verdict,'stdout':'1','output_truncated':truncated} for _ in range(3)]
    with pytest.raises(ExecutionUnavailable,match='reference solution'):
        asyncio.run(get_performance_cases(question,db,runner))
    assert db.query(QuestionPerformanceSuite).count()==0


def test_missing_spec_never_silently_falls_back_to_small_only_judge():
    with pytest.raises(ExecutionUnavailable,match='no performance specification'):
        build_performance_inputs({})

def test_sorted_input_contract_is_preserved_in_performance_cases():
    question=data()
    question['input_format']='The second line contains n values in non\u2011decreasing order.'
    for case in build_performance_inputs(question):
        values=list(map(int,case['input'].split()))[1:]
        assert values==sorted(values)
