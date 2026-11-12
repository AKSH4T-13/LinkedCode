"""User-owned practice history and profile settings."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.dependencies import get_current_user
from backend.database import get_db
from backend.models import User, RecommendationHistory, SolvedQuestion, GeneratedQuestion, CodeSubmission

router = APIRouter(tags=["Practice"])


class StatusUpdate(BaseModel):
    status: Literal["recommended", "attempted", "completed", "skipped"]


class ProfileUpdate(BaseModel):
    leetcode_username: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")


@router.patch("/auth/profile")
def update_profile(body: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = db.get(User, user.id)
    record.leetcode_username = body.leetcode_username
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "LeetCode username already linked.")
    return {"id": record.id, "email": record.email, "leetcode_username": record.leetcode_username}


@router.get("/recommendations/history")
def history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(RecommendationHistory).filter_by(user_id=user.id).order_by(RecommendationHistory.recommended_at.desc(), RecommendationHistory.id.desc()).all()
    return {"success": True, "total": len(rows), "recommendations": [
        {"id": row.id, "question_slug": row.question_slug, "status": row.status,
         "recommended_at": row.recommended_at.isoformat() if row.recommended_at else None}
        for row in rows]}


@router.patch("/recommendations/{question_slug}/status")
def update_status(question_slug: str, body: StatusUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(RecommendationHistory).filter_by(user_id=user.id, question_slug=question_slug).first()
    if row is None:
        raise HTTPException(404, "Recommendation not found.")
    if row.status == "completed" and body.status != "completed":
        raise HTTPException(409, "Completed recommendations cannot be reopened.")
    row.status = body.status
    if body.status == "completed":
        solved = db.query(SolvedQuestion).filter_by(user_id=user.id, question_slug=question_slug).first()
        if solved is None:
            db.add(SolvedQuestion(user_id=user.id, question_slug=question_slug, solved_at=datetime.now(timezone.utc)))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Practice history changed. Refresh and try again.")
    return {"success": True, "question_slug": question_slug, "status": row.status}


@router.get("/practice/progress")
def progress(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    counts = {status: db.query(RecommendationHistory).filter_by(user_id=user.id, status=status).count()
              for status in ("recommended", "attempted", "completed", "skipped")}
    return {"statuses": counts,
            "generated_completed": db.query(CodeSubmission.question_id).filter(
                CodeSubmission.user_id == user.id, CodeSubmission.verdict == "Accepted",
                CodeSubmission.report["performance_status"].as_string() == "passed"
            ).distinct().count(),
            "solved": db.query(SolvedQuestion).filter_by(user_id=user.id).count(),
            "generated": db.query(GeneratedQuestion).filter_by(user_id=user.id).count()}


@router.get("/generated-questions/{question_id}")
def generated_detail(question_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(GeneratedQuestion).filter_by(id=question_id, user_id=user.id).first()
    if row is None:
        raise HTTPException(404, "Generated question not found.")
    return {"id": row.id, "title": row.title, "difficulty": row.difficulty, "topics": row.topics,
            "question_data": row.question_data, "validation_report": row.validation_report}
