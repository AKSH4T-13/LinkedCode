
import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.database import Base, get_db
from backend.models import User
from backend.core.security import create_access_token


# ==================================================
# TEST DATABASE
# ==================================================

SQLALCHEMY_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)

Base.metadata.create_all(bind=test_engine)


# ==================================================
# FIXTURES
# ==================================================

@pytest.fixture
def db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    database = TestingSessionLocal()

    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client(client, db):
    user = User(
        email="test@example.com",
        password_hash="dummy_hash",
        leetcode_username="testuser"
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        data={"sub": str(user.id)}
    )

    client.headers.update({
        "Authorization": f"Bearer {token}"
    })

    return client


@pytest.fixture
def unlinked_client(client, db):
    user = User(
        email="unlinked@example.com",
        password_hash="dummy_hash",
        leetcode_username=None
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        data={"sub": str(user.id)}
    )

    client.headers.update({
        "Authorization": f"Bearer {token}"
    })

    return client


# ==================================================
# BASIC ROUTES
# ==================================================

def test_home(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["message"] == "LinkedCode Backend Running!"


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


# ==================================================
# RECENT LEETCODE QUESTIONS
# ==================================================

def test_recent_questions_success(authenticated_client, monkeypatch):
    mock_result = {
        "username": "testuser",
        "total_fetched": 1,
        "recent_questions": [
            {
                "submission_id": "123",
                "title": "Two Sum",
                "title_slug": "two-sum",
                "timestamp": "1700000000"
            }
        ]
    }

    mock_fetch = AsyncMock(return_value=mock_result)

    monkeypatch.setattr(
        "backend.main.fetch_recent_questions",
        mock_fetch
    )

    response = authenticated_client.get("/leetcode/recent")

    assert response.status_code == 200
    assert response.json() == mock_result

    mock_fetch.assert_awaited_once_with("testuser")


def test_recent_questions_unlinked_user(unlinked_client):
    response = unlinked_client.get("/leetcode/recent")

    assert response.status_code == 400
    assert "link your LeetCode account" in response.json()["detail"]


def test_recent_questions_value_error(authenticated_client, monkeypatch):
    mock_fetch = AsyncMock(
        side_effect=ValueError("Invalid LeetCode username.")
    )

    monkeypatch.setattr(
        "backend.main.fetch_recent_questions",
        mock_fetch
    )

    response = authenticated_client.get("/leetcode/recent")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid LeetCode username."


def test_recent_questions_server_error(authenticated_client, monkeypatch):
    mock_fetch = AsyncMock(
        side_effect=Exception("Internal error")
    )

    monkeypatch.setattr(
        "backend.main.fetch_recent_questions",
        mock_fetch
    )

    response = authenticated_client.get("/leetcode/recent")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to fetch LeetCode submissions."


# ==================================================
# LEETCODE PROFILE ANALYSIS
# ==================================================

def test_analyze_questions_success(authenticated_client, monkeypatch):
    mock_result = {
        "user_profile": {
            "username": "testuser",
            "total_unique_questions": 1,
            "difficulty_distribution": {
                "Easy": 1,
                "Medium": 0,
                "Hard": 0
            },
            "topic_frequency": {
                "Array": 1
            },
            "recent_topics": ["Array"]
        },
        "analyzed_questions": []
    }

    mock_analyze = AsyncMock(return_value=mock_result)

    monkeypatch.setattr(
        "backend.main.analyze_questions",
        mock_analyze
    )

    response = authenticated_client.get("/leetcode/analyze")

    assert response.status_code == 200
    assert response.json() == mock_result

    mock_analyze.assert_awaited_once_with("testuser")


def test_analyze_questions_unlinked_user(unlinked_client):
    response = unlinked_client.get("/leetcode/analyze")

    assert response.status_code == 400
    assert "link your LeetCode account" in response.json()["detail"]


def test_analyze_questions_value_error(authenticated_client, monkeypatch):
    mock_analyze = AsyncMock(
        side_effect=ValueError("Username cannot be empty.")
    )

    monkeypatch.setattr(
        "backend.main.analyze_questions",
        mock_analyze
    )

    response = authenticated_client.get("/leetcode/analyze")

    assert response.status_code == 400
    assert response.json()["detail"] == "Username cannot be empty."


def test_analyze_questions_server_error(authenticated_client, monkeypatch):
    mock_analyze = AsyncMock(
        side_effect=Exception("Internal error")
    )

    monkeypatch.setattr(
        "backend.main.analyze_questions",
        mock_analyze
    )

    response = authenticated_client.get("/leetcode/analyze")

    assert response.status_code == 500
    assert response.json()["detail"] == "Unable to analyze LeetCode profile."


# ==================================================
# RECOMMENDATION GENERATION
# ==================================================

def test_generate_recommendations_success(authenticated_client, monkeypatch):
    mock_result = {
        "final_recommendations": {
            "existing_question": {
                "title": "Valid Parentheses"
            },
            "generated_question": {
                "title": "Custom Array Challenge"
            }
        }
    }

    mock_invoke = AsyncMock(return_value=mock_result)

    monkeypatch.setattr(
        "backend.main.linkedcode_graph.ainvoke",
        mock_invoke
    )

    response = authenticated_client.post(
        "/recommendations/generate"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["username"] == "testuser"
    assert data["recommendations"] == mock_result["final_recommendations"]

    mock_invoke.assert_awaited_once_with({
        "user_id": 1,
        "username": "testuser",
        "errors": []
    })


def test_generate_recommendations_unlinked_user(unlinked_client):
    response = unlinked_client.post(
        "/recommendations/generate"
    )

    assert response.status_code == 400
    assert "link your LeetCode account" in response.json()["detail"]


def test_generate_recommendations_server_error(authenticated_client, monkeypatch):
    mock_invoke = AsyncMock(
        side_effect=Exception("Workflow failure")
    )

    monkeypatch.setattr(
        "backend.main.linkedcode_graph.ainvoke",
        mock_invoke
    )

    response = authenticated_client.post(
        "/recommendations/generate"
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to generate recommendations."


# ==================================================
# AUTHENTICATION PROTECTION
# ==================================================

def test_recent_questions_without_token(client):
    response = client.get("/leetcode/recent")

    assert response.status_code == 401


def test_analyze_without_token(client):
    response = client.get("/leetcode/analyze")

    assert response.status_code == 401


def test_generate_without_token(client):
    response = client.post("/recommendations/generate")

    assert response.status_code == 401


def test_generate_budget_error_returns_clear_service_response(authenticated_client, monkeypatch):
    from backend.llm.token_budget import LLMBudgetExceeded
    mock_invoke = AsyncMock(side_effect=LLMBudgetExceeded("Token budget exceeded"))
    monkeypatch.setattr("backend.main.linkedcode_graph.ainvoke", mock_invoke)
    response = authenticated_client.post("/recommendations/generate")
    assert response.status_code == 503
    assert response.json()["detail"] == "Token budget exceeded"
