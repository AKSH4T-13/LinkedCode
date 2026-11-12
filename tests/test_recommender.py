import asyncio

from backend.services.question_analyzer import analyze_questions
from backend.services.candidate_service import (
    fetch_unsolved_candidates,
    save_recommendation
)
from backend.agents.question_recommender import recommend_question


async def main():

    username = "Vansh1306"

    print("\nFetching user profile...")

    user_profile = await analyze_questions(username)
    user_profile["username"] = username

    print("Profile fetched successfully.")

    print("\nFetching unsolved candidates...")

    candidates = await fetch_unsolved_candidates(
        user_profile,
        max_candidates=30
    )

    print("Candidates:", len(candidates))

    print("\nSending candidates to Groq...")

    recommendation = recommend_question(
        user_profile,
        candidates
    )

    print("\n========== RECOMMENDED QUESTION ==========")

    print("Title:", recommendation["title"])
    print("Difficulty:", recommendation["difficulty"])
    print("Topics:", recommendation["topics"])

    print("\nWhy recommended:")
    print(recommendation["reason"])

    print(
        "\nLeetCode URL: https://leetcode.com/problems/"
        + recommendation["title_slug"]
    )

    save_result = save_recommendation(
        username,
        recommendation
    )

    print("\n========== DATABASE SAVE ==========")
    print(save_result["message"])


if __name__ == "__main__":
    asyncio.run(main())