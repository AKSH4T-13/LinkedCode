import asyncio
from datetime import datetime, timezone

import httpx

from backend.services.leetcode_service import fetch_recent_questions


LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql/"

HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com/"
}


async def fetch_question_details(client, title_slug):

    query = """
    query questionData($titleSlug: String!) {
        question(titleSlug: $titleSlug) {
            title
            titleSlug
            difficulty
            topicTags {
                name
                slug
            }
        }
    }
    """

    payload = {
        "query": query,
        "variables": {
            "titleSlug": title_slug
        }
    }

    try:
        response = await client.post(
            LEETCODE_GRAPHQL_URL,
            json=payload,
            headers=HEADERS
        )

        response.raise_for_status()
        data = response.json()

        if data.get("errors"):
            print("GraphQL Errors:", data["errors"])
            return None

        question_data = data.get("data", {}).get("question")

        if question_data is None:
            print(f"Question details not found: {title_slug}")

        return question_data


    except httpx.HTTPError as e:
        print(f"HTTP Error for {title_slug}: {e}")
        return None


async def analyze_questions(username: str):
    username = username.strip()

    if not username:
        raise ValueError("Username cannot be empty.")

    # Step 1: Fetch recent accepted submissions
    submission_data = await fetch_recent_questions(username)

    recent_questions = submission_data["recent_questions"]

    # Step 2: Remove duplicate questions
    unique_questions = {}

    for question in recent_questions:

        slug = question["title_slug"]

        if slug not in unique_questions:
            unique_questions[slug] = question

    unique_questions = list(unique_questions.values())

    # Step 3: Fetch difficulty and topic information
    semaphore = asyncio.Semaphore(5)

    async with httpx.AsyncClient(timeout=20.0) as client:

        async def fetch_with_limit(question):

            async with semaphore:

                details = await fetch_question_details(
                    client,
                    question["title_slug"]
                )

                return question, details

        results = await asyncio.gather(
            *[
                fetch_with_limit(question)
                for question in unique_questions
            ]
        )

    # Step 4: Combine submission and question details
    analyzed_questions = []

    topic_frequency = {}
    difficulty_frequency = {
        "Easy": 0,
        "Medium": 0,
        "Hard": 0
    }

    for submission, details in results:

        if not details:
            continue

        timestamp = int(submission["timestamp"])

        readable_date = datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc
        ).isoformat()

        difficulty = details["difficulty"]

        topics = [
            {
                "name": tag["name"],
                "slug": tag["slug"]
            }
            for tag in details.get("topicTags", [])
        ]

        difficulty_frequency[difficulty] += 1

        for topic in topics:
            topic_name = topic["name"]

            topic_frequency[topic_name] = (
                topic_frequency.get(topic_name, 0) + 1
            )

        analyzed_questions.append({

            "title": details["title"],

            "title_slug": details["titleSlug"],

            "difficulty": difficulty,

            "topics": topics,

            "submission_id": submission["submission_id"],

            "timestamp": timestamp,

            "submitted_at": readable_date

        })

    # Step 5: Sort by latest submission
    analyzed_questions.sort(
        key=lambda question: question["timestamp"],
        reverse=True
    )

    # Step 6: Generate user profile
    user_profile = {

        "username": username,

        "total_unique_questions": len(analyzed_questions),

        "difficulty_distribution": difficulty_frequency,

        "topic_frequency": topic_frequency,

        "recent_topics": list(topic_frequency.keys())

    }

    return {

        "user_profile": user_profile,

        "analyzed_questions": analyzed_questions

    }