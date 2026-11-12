import pytest

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from jose import jwt

from backend.main import app
from backend.database import Base, get_db
from backend.core.security import SECRET_KEY, ALGORITHM
from backend.models import User


# =========================================================
# TEST DATABASE
# =========================================================

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


@pytest.fixture
def db():
    Base.metadata.create_all(bind=test_engine)

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# =========================================================
# REGISTRATION TESTS
# =========================================================

def test_successful_registration(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "password": "password123",
            "leetcode_username": "testuser"
        }
    )

    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"
    assert response.json()["leetcode_username"] == "testuser"


def test_duplicate_email(client):
    payload = {
        "email": "test@example.com",
        "password": "password123"
    }

    first_response = client.post("/auth/register", json=payload)
    second_response = client.post("/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 400


def test_password_minimum_length(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "short@example.com",
            "password": "123"
        }
    )

    assert response.status_code == 422


def test_username_whitespace_normalization(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "space@example.com",
            "password": "password123",
            "leetcode_username": "  testuser  "
        }
    )

    assert response.status_code == 201
    assert response.json()["leetcode_username"] == "testuser"


# =========================================================
# LOGIN TESTS
# =========================================================

def test_successful_login(client):
    registration = client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "password": "password123"
        }
    )

    assert registration.status_code == 201

    response = client.post(
        "/auth/login",
        json={
            "email": "login@example.com",
            "password": "password123"
        }
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_incorrect_password(client):
    registration = client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "password": "password123"
        }
    )

    assert registration.status_code == 201

    response = client.post(
        "/auth/login",
        json={
            "email": "login@example.com",
            "password": "wrongpassword"
        }
    )

    assert response.status_code == 401


def test_nonexistent_user_login(client):
    response = client.post(
        "/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "password123"
        }
    )

    assert response.status_code == 401


# =========================================================
# JWT AUTHENTICATION TESTS
# =========================================================

def test_valid_jwt(client):
    registration = client.post(
        "/auth/register",
        json={
            "email": "jwt@example.com",
            "password": "password123"
        }
    )

    assert registration.status_code == 201

    login = client.post(
        "/auth/login",
        json={
            "email": "jwt@example.com",
            "password": "password123"
        }
    )

    token = login.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "jwt@example.com"


def test_invalid_jwt(client):
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalidtoken"}
    )

    assert response.status_code == 401


def test_missing_jwt(client):
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_expired_jwt(client, db):
    user = User(
        email="expired@example.com",
        password_hash="dummy_hash"
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    expired_token = jwt.encode(
        {
            "sub": str(user.id),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401


def test_nonexistent_user_jwt(client):
    token = jwt.encode(
        {
            "sub": "999999",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401