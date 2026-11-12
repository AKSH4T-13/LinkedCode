from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.models import User, SolvedQuestion


def save_solved_questions(
    db: Session,
    username: str,
    solved_questions: list
):
    """
    Store a user's solved LeetCode questions in SQLite.
    """

    username = username.strip()

    user = db.query(User).filter(
        User.leetcode_username == username
    ).first()

    if not user:
        user = User(leetcode_username=username)
        db.add(user)
        db.commit()
        db.refresh(user)

    existing_slugs = {
        slug
        for (slug,) in db.query(
            SolvedQuestion.question_slug
        ).filter(
            SolvedQuestion.user_id == user.id
        ).all()
    }

    added_count = 0

    for question in solved_questions:

        slug = question.get("title_slug")

        if not slug or slug in existing_slugs:
            continue

        solved_at = question.get("solved_at")

        if isinstance(solved_at, str):
            try:
                solved_at = datetime.fromtimestamp(
                    int(solved_at),
                    tz=timezone.utc
                )
            except (ValueError, TypeError):
                solved_at = None

        record = SolvedQuestion(
            user_id=user.id,
            question_slug=slug,
            difficulty=question.get("difficulty"),
            solved_at=solved_at
        )

        db.add(record)
        existing_slugs.add(slug)
        added_count += 1

    db.commit()

    return {
        "username": username,
        "new_questions_added": added_count,
        "total_solved_questions": len(existing_slugs)
    }


def get_solved_question_slugs(
    db: Session,
    username: str
):
    """
    Retrieve all solved question slugs for a user.
    """

    user = db.query(User).filter(
        User.leetcode_username == username.strip()
    ).first()

    if not user:
        return set()

    records = db.query(
        SolvedQuestion.question_slug
    ).filter(
        SolvedQuestion.user_id == user.id
    ).all()

    return {slug for (slug,) in records}