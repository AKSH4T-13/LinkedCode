import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.main import app
from backend.database import Base, get_db
from backend.models import User, RecommendationHistory, SolvedQuestion, GeneratedQuestion
from backend.core.security import create_access_token
from backend.graph.nodes import combine_node


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add_all([User(id=1,email='one@example.com',password_hash='unused',leetcode_username='one'),User(id=2,email='two@example.com',password_hash='unused',leetcode_username='two')])
        db.add_all([RecommendationHistory(user_id=1,question_slug='two-sum'),RecommendationHistory(user_id=2,question_slug='private-problem')])
        db.add(GeneratedQuestion(id=1,user_id=1,title='Private generated',difficulty='Easy',topics=['Array'],question_data={'title':'Private generated'},validation_report={'is_valid':True}))
        db.commit()
    def dependency():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = dependency
    monkeypatch.setattr('backend.main.SessionLocal',factory)
    monkeypatch.setattr('backend.graph.nodes.SessionLocal',factory)
    with TestClient(app) as client:
        client.headers['Authorization'] = 'Bearer ' + create_access_token({'sub':'1'})
        yield client,factory
    app.dependency_overrides.clear()
    engine.dispose()


def test_history_and_generated_isolation(setup):
    client,factory=setup
    history=client.get('/recommendations/history').json()
    assert [q['question_slug'] for q in history['recommendations']] == ['two-sum']
    assert client.get('/generated-questions/1').status_code == 200
    client.headers['Authorization']='Bearer '+create_access_token({'sub':'2'})
    assert client.get('/generated-questions/1').status_code == 404
    assert client.get('/generated-questions').json()['total'] == 0
    assert client.patch('/recommendations/two-sum/status',json={'status':'completed'}).status_code == 404


@pytest.mark.parametrize('status',['attempted','skipped','recommended'])
def test_practice_statuses(setup,status):
    client,_=setup
    assert client.patch('/recommendations/two-sum/status',json={'status':status}).json()['status']==status
    assert client.get('/practice/progress').json()['statuses'][status] == 1


def test_completion_is_atomic_and_idempotent(setup):
    client,factory=setup
    for _ in range(2):
        assert client.patch('/recommendations/two-sum/status',json={'status':'completed'}).status_code==200
    with factory() as db:
        assert db.query(SolvedQuestion).filter_by(user_id=1).count()==1
        assert db.query(SolvedQuestion).first().solved_at is not None
    assert client.patch('/recommendations/two-sum/status',json={'status':'skipped'}).status_code==409
    assert client.get('/practice/progress').json()['solved']==1


def test_invalid_status_and_unauthenticated(setup):
    client,_=setup
    assert client.patch('/recommendations/two-sum/status',json={'status':'invalid'}).status_code==422
    client.headers.pop('Authorization')
    for path in ['/recommendations/history','/practice/progress','/generated-questions/1']:
        assert client.get(path).status_code==401


def test_profile_update_and_conflict(setup):
    client,_=setup
    assert client.patch('/auth/profile',json={'leetcode_username':'new_profile'}).status_code==200
    assert client.get('/auth/me').json()['leetcode_username']=='new_profile'
    assert client.patch('/auth/profile',json={'leetcode_username':'two'}).status_code==409
    assert client.patch('/auth/profile',json={'leetcode_username':'  '}).status_code==422


def test_combine_rollback_on_second_save_failure(setup):
    _,factory=setup
    with pytest.raises(ValueError,match='title'):
        combine_node({'user_id':1,'existing_recommendation':{'title_slug':'never-commit'},'generated_question':{},'validation_report':{}})
    with factory() as db:
        assert db.query(RecommendationHistory).filter_by(question_slug='never-commit').count()==0


def test_combine_persists_both_results(setup):
    _,factory=setup
    result=combine_node({'user_id':1,'existing_recommendation':{'title_slug':'new-question'},'generated_question':{'title':'New','topics':['Array'],'difficulty':'Medium'},'validation_report':{'is_valid':True}})
    assert result['final_recommendations']['generated_question']['title']=='New'
    with factory() as db:
        assert db.query(RecommendationHistory).filter_by(question_slug='new-question').count()==1
        assert db.query(GeneratedQuestion).filter_by(title='New').count()==1


def test_frontend_and_cors(setup):
    client,_=setup
    assert client.get('/app/').status_code==200
    response=client.options('/auth/login',headers={'Origin':'http://localhost:5500','Access-Control-Request-Method':'POST'})
    assert response.headers['access-control-allow-origin']=='http://localhost:5500'

def test_generation_uses_history_without_manual_overrides(setup,monkeypatch):
    from unittest.mock import AsyncMock
    client,_=setup
    invoke=AsyncMock(return_value={'final_recommendations':{}})
    monkeypatch.setattr('backend.main.linkedcode_graph.ainvoke',invoke)
    response=client.post('/recommendations/generate',json={'difficulty':'Hard','topics':['Graph']})
    assert response.status_code==200
    assert invoke.call_args.args[0]=={'user_id':1,'username':'one','errors':[]}


def test_candidate_filters_apply_before_pool_limit():
    from backend.services.candidate_service import get_unsolved_candidates
    catalogue=[{'title_slug':str(i),'difficulty':'Easy','topics':['Array']} for i in range(35)]
    catalogue.append({'title_slug':'target','difficulty':'Hard','topics':['Graph']})
    result=get_unsolved_candidates({},catalogue,max_candidates=1,difficulty='Hard',topics=['graph'])
    assert [q['title_slug'] for q in result]==['target']
    assert not get_unsolved_candidates({},catalogue,difficulty='Hard',topics=['Graph'],solved_slugs={'target'})
