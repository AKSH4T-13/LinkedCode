from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    JSON
)

from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from backend.database import Base


# =========================================================
# USER MODEL
# =========================================================

class User(Base):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = Column(
        String,
        nullable=False
    )

    leetcode_username = Column(
        String,
        unique=True,
        nullable=True,
        index=True
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    solved_questions = relationship(
        "SolvedQuestion",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    recommendations = relationship(
        "RecommendationHistory",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    generated_questions = relationship(
        "GeneratedQuestion",
        back_populates="user",
        cascade="all, delete-orphan"
    )


# =========================================================
# SOLVED QUESTION MODEL
# =========================================================

class SolvedQuestion(Base):

    __tablename__ = "solved_questions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    question_slug = Column(String, nullable=False)

    difficulty = Column(String)

    solved_at = Column(DateTime, nullable=True)

    user = relationship(
        "User",
        back_populates="solved_questions"
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "question_slug",
            name="unique_user_solved_question"
        ),
    )


# =========================================================
# RECOMMENDATION HISTORY MODEL
# =========================================================

class RecommendationHistory(Base):

    __tablename__ = "recommendation_history"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "question_slug",
            name="unique_user_recommendation"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    question_slug = Column(String, nullable=False)

    recommended_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    status = Column(
        String,
        default="recommended"
    )

    user = relationship(
        "User",
        back_populates="recommendations"
    )


# =========================================================
# GENERATED QUESTION MODEL
# =========================================================

class GeneratedQuestion(Base):

    __tablename__ = "generated_questions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    title = Column(
        String,
        nullable=False
    )

    difficulty = Column(
        String,
        nullable=False
    )

    topics = Column(
        JSON,
        nullable=False
    )

    question_data = Column(
        JSON,
        nullable=False
    )

    validation_report = Column(
        JSON,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    user = relationship(
        "User",
        back_populates="generated_questions"
    )

class CodeSubmission(Base):
    __tablename__ = 'code_submissions'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey('generated_questions.id', ondelete='CASCADE'), nullable=False, index=True)
    code = Column(String, nullable=False)
    verdict = Column(String, nullable=False)
    passed = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    report = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class QuestionPerformanceSuite(Base):
    __tablename__ = 'question_performance_suites'
    question_id = Column(Integer, ForeignKey('generated_questions.id', ondelete='CASCADE'), primary_key=True)
    signature = Column(String(64), nullable=False)
    cases = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
