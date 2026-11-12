import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.main import app
from backend.database import Base,get_db
from backend.models import User,GeneratedQuestion,CodeSubmission
from backend.core.security import create_access_token
from backend.routers.execution import active_users,recent_runs
from backend.services.python_runner import ExecutionUnavailable


@pytest.fixture
def setup(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);factory=sessionmaker(bind=engine)
    question={'examples':[{'input':'2 3','output':'5'}],
              'test_cases':[{'input':'2 3','expected_output':'5'}],
              'verification_test_cases':[{'input':'0 0','expected_output':'0'}]}
    with factory() as db:
        db.add_all([User(id=1,email='one@example.com',password_hash='unused'),User(id=2,email='two@example.com',password_hash='unused')]);db.flush()
        db.add(GeneratedQuestion(id=1,user_id=1,title='Sum',difficulty='Easy',topics=['Array'],question_data=question,validation_report={'is_valid':True}));db.commit()
    def dependency():
        with factory() as db:yield db
    app.dependency_overrides[get_db]=dependency
    active_users.clear();recent_runs.clear()
    runner=AsyncMock(return_value=[{'case':1,'verdict':'Accepted','passed':True,'hidden':False}])
    monkeypatch.setattr('backend.routers.execution.PythonRunner.evaluate',runner)
    monkeypatch.setattr('backend.routers.execution.get_performance_cases',AsyncMock(return_value=[{'input':'100000\n0','expected_output':'0','hidden':True,'kind':'performance'}]))
    with TestClient(app) as client:
        client.headers['Authorization']='Bearer '+create_access_token({'sub':'1'})
        yield client,factory,runner
    app.dependency_overrides.clear();active_users.clear();recent_runs.clear();engine.dispose()


def test_ownership_precedes_execution(setup):
    client,_,runner=setup
    client.headers['Authorization']='Bearer '+create_access_token({'sub':'2'})
    assert client.post('/generated-questions/1/execute',json={'code':'print(5)'}).status_code==404
    assert client.get('/generated-questions/1/submissions').status_code==404
    runner.assert_not_awaited()
    client.headers.pop('Authorization')
    assert client.post('/generated-questions/1/execute',json={'code':'print(5)'}).status_code==401


def test_example_run_uses_server_expected_outputs(setup):
    client,factory,runner=setup
    result=client.post('/generated-questions/1/execute',json={'code':'print(5)'}).json()
    assert result['accepted'] is True
    assert runner.call_args.args[1]==[{'input':'2 3','expected_output':'5'}]
    with factory() as db:assert db.query(CodeSubmission).count()==0


def test_submit_persists_and_counts_progress(setup):
    client,factory,runner=setup
    runner.side_effect=[[{'case':1,'passed':True,'verdict':'Accepted','hidden':False},{'case':2,'passed':True,'verdict':'Accepted','hidden':True}],[{'case':1,'passed':True,'verdict':'Accepted','hidden':True}]]
    result=client.post('/generated-questions/1/execute',json={'code':'print(5)','mode':'submit'}).json()
    assert result['accepted'] is True and result['total']==3
    assert runner.call_args_list[0].args[1][1]=={'input':'0 0','expected_output':'0','hidden':True}
    assert client.get('/generated-questions/1/submissions').json()['submissions'][0]['passed']==3
    assert client.get('/practice/progress').json()['generated_completed']==1
    with factory() as db:assert db.query(CodeSubmission).one().code=='print(5)'


def test_provider_failure_does_not_record_attempt_or_hold_lock(setup):
    client,factory,runner=setup;runner.side_effect=ExecutionUnavailable('Service unavailable')
    assert client.post('/generated-questions/1/execute',json={'code':'print(5)','mode':'submit'}).status_code==503
    assert 1 not in active_users
    with factory() as db:assert db.query(CodeSubmission).count()==0


def test_custom_and_rate_limits(setup):
    client,_,runner=setup;runner.return_value=[{'case':1,'passed':None,'verdict':'Executed','stdout':'hello','hidden':False}]
    result=client.post('/generated-questions/1/execute',json={'code':'print(input())','mode':'custom','stdin':'hello'}).json()
    assert result['accepted'] is False and result['passed'] is None
    assert runner.call_args.args[1]==[{'input':'hello'}]
    assert client.post('/generated-questions/1/execute',json={'code':'pass'}).status_code==429


def test_requests_cannot_supply_cases_or_runtime_configuration(setup):
    client,_,runner=setup
    for data in ({'code':' '},{'code':'x'*40001},{'code':'pass','expected_output':'5'},{'code':'pass','language_id':71}):
        assert client.post('/generated-questions/1/execute',json=data).status_code==422
    runner.assert_not_awaited()


def test_concurrent_run_rejected(setup):
    client,_,runner=setup;active_users.add(1)
    assert client.post('/generated-questions/1/execute',json={'code':'pass'}).status_code==409
    runner.assert_not_awaited()

def test_wrong_submission_is_saved_without_solved_credit(setup):
    client,factory,runner=setup
    runner.return_value=[{'case':1,'passed':False,'verdict':'Wrong answer','hidden':False},{'case':2,'passed':True,'verdict':'Accepted','hidden':True}]
    result=client.post('/generated-questions/1/execute',json={'code':'print(0)','mode':'submit'}).json()
    assert result['verdict']=='Wrong answer' and result['passed']==1 and result['accepted'] is False
    assert client.get('/practice/progress').json()['generated_completed']==0
    with factory() as db:assert db.query(CodeSubmission).one().verdict=='Wrong answer'


def test_incomplete_provider_results_never_become_accepted(setup):
    client,factory,runner=setup;runner.return_value=[]
    assert client.post('/generated-questions/1/execute',json={'code':'pass','mode':'submit'}).status_code==503
    with factory() as db:assert db.query(CodeSubmission).count()==0


def test_brute_force_timeout_on_large_case_is_not_accepted(setup):
    client,factory,runner=setup
    runner.side_effect=[
        [{'case':1,'passed':True,'verdict':'Accepted','hidden':False},{'case':2,'passed':True,'verdict':'Accepted','hidden':True}],
        [{'case':1,'passed':False,'verdict':'Time limit exceeded','hidden':True}],
    ]
    result=client.post('/generated-questions/1/execute',json={'code':'pass','mode':'submit'}).json()
    assert result['accepted'] is False
    assert result['verdict']=='Time limit exceeded'
    assert result['performance_status']=='failed'
    assert result['results'][-1]['kind']=='performance'
    assert result['results'][-1]['case']==3
    assert client.get('/practice/progress').json()['generated_completed']==0


def test_bad_reference_does_not_mark_learner_wrong(setup,monkeypatch):
    client,factory,runner=setup
    runner.return_value=[{'passed':True,'verdict':'Accepted'},{'passed':True,'verdict':'Accepted'}]
    monkeypatch.setattr('backend.routers.execution.get_performance_cases',AsyncMock(side_effect=ExecutionUnavailable('Reference needs review')))
    response=client.post('/generated-questions/1/execute',json={'code':'pass','mode':'submit'})
    assert response.status_code==503
    with factory() as db:assert db.query(CodeSubmission).count()==0

def test_legacy_small_only_accepted_run_does_not_claim_performance_solved(setup):
    client,factory,_=setup
    with factory() as db:
        db.add(CodeSubmission(user_id=1,question_id=1,code='pass',verdict='Accepted',passed=2,total=2,report={'accepted':True}))
        db.commit()
    assert client.get('/practice/progress').json()['generated_completed']==0
    row=client.get('/generated-questions/1/submissions').json()['submissions'][0]
    assert row['performance_status']=='not_checked'

