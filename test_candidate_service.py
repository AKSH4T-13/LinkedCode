import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models import User, GeneratedQuestion
import backend.services.candidate_service as candidate_service


# =========================================================
# TEST DATABASE FIXTURE
# =========================================================

@pytest.fixture
def test_db(monkeypatch):

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )

    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(
        candidate_service,
        "SessionLocal",
        TestingSessionLocal
    )

    db = TestingSessionLocal()

    user = User(
        email="test@example.com",
        password_hash="test_hash",
        leetcode_username="test_user"
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    yield db, user.id

    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# =========================================================
# MOCK GENERATED QUESTION
# =========================================================

def create_question():

    return {
        "title": "Subarray Frequency",
        "difficulty": "Medium",
        "topics": ["Array", "Hash Table"],
        "description": "Find the frequency of elements.",
        "examples": [
            {
                "input": "[1, 2, 2]",
                "output": "{1: 1, 2: 2}"
            }
        ]
    }


# =========================================================
# TEST 1: SAVE GENERATED QUESTION
# =========================================================

def test_save_generated_question(test_db):

    db, user_id = test_db

    question = create_question()

    validation = {
        "is_valid": True,
        "total_tests": 10,
        "passed": 10
    }

    result = candidate_service.save_generated_question(
        user_id=user_id,
        question=question,
        validation_report=validation
    )

    assert result["saved"] is True

    record = db.query(GeneratedQuestion).filter(
        GeneratedQuestion.user_id == user_id
    ).first()

    assert record is not None
    assert record.title == "Subarray Frequency"
    assert record.difficulty == "Medium"
    assert record.topics == ["Array", "Hash Table"]
    assert record.question_data == question
    assert record.validation_report == validation

    print("[PASS] Generated question saved successfully.")


# =========================================================
# TEST 2: INVALID USER
# =========================================================

def test_save_generated_question_invalid_user(test_db):

    question = create_question()

    with pytest.raises(ValueError, match="User not found"):

        candidate_service.save_generated_question(
            user_id=9999,
            question=question
        )

    print("[PASS] Invalid user rejected correctly.")


# =========================================================
# TEST 3: USER DATA ISOLATION
# =========================================================

def test_generated_question_user_isolation(test_db):

    db, user_id = test_db

    candidate_service.save_generated_question(
        user_id=user_id,
        question=create_question()
    )

    records = db.query(GeneratedQuestion).filter(
        GeneratedQuestion.user_id == 9999
    ).all()

    assert len(records) == 0

    print("[PASS] User data isolation verified.")