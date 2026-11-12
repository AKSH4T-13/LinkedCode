import asyncio

from backend.services.leetcode_service import fetch_all_solved_questions
from backend.services.solved_history_service import save_solved_questions
from backend.database import SessionLocal


async def main():

    username = "Vansh1306"

    print("\nFetching complete LeetCode solved history...")

    questions = await fetch_all_solved_questions(username)

    print("Fetched:", len(questions))

    db = SessionLocal()

    try:
        result = save_solved_questions(
            db=db,
            username=username,
            solved_questions=questions
        )

        print("\n========== DATABASE SYNC ==========")

        print("Username:", result["username"])
        print("New questions added:", result["new_questions_added"])
        print("Total solved questions:", result["total_solved_questions"])

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())