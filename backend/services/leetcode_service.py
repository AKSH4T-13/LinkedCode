import os
import httpx

from dotenv import load_dotenv

load_dotenv()

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql/"

HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com/"
}


# --------------------------------------------------
# FETCH RECENT ACCEPTED SUBMISSIONS
# --------------------------------------------------

async def fetch_recent_questions(username: str):

    query = """
    query recentAcSubmissionList($username: String!) {
        recentAcSubmissionList(username: $username, limit: 20) {
            id
            title
            titleSlug
            timestamp
        }
    }
    """

    payload = {
        "query": query,
        "variables": {
            "username": username
        }
    }

    async with httpx.AsyncClient(timeout=20.0) as client:

        response = await client.post(
            LEETCODE_GRAPHQL_URL,
            json=payload,
            headers=HEADERS
        )

        response.raise_for_status()
        data = response.json()

    if data.get("errors"):
        raise ValueError(data["errors"])

    user_data = data.get("data", {}).get(
        "recentAcSubmissionList"
    )

    if user_data is None:
        raise ValueError(
            "Unable to fetch LeetCode submissions."
        )

    questions = []

    for question in user_data:

        questions.append({
            "submission_id": question["id"],
            "title": question["title"],
            "title_slug": question["titleSlug"],
            "timestamp": question["timestamp"]
        })

    return {
        "username": username,
        "total_fetched": len(questions),
        "recent_questions": questions
    }


# --------------------------------------------------
# FETCH COMPLETE SOLVED QUESTION HISTORY
# --------------------------------------------------

async def fetch_all_solved_questions(username: str):

    session = os.getenv("LEETCODE_SESSION")
    csrf_token = os.getenv("LEETCODE_CSRF_TOKEN")

    if not session or not csrf_token:
        raise ValueError(
            "LEETCODE_SESSION or LEETCODE_CSRF_TOKEN "
            "missing from .env"
        )

    query = """
    query userProgressQuestionList(
        $filters: UserProgressQuestionListInput
    ) {
        userProgressQuestionList(filters: $filters) {
            totalNum
            questions {
                frontendId
                title
                titleSlug
                difficulty
                lastSubmittedAt
                topicTags {
                    name
                }
            }
        }
    }
    """

    all_questions = []

    skip = 0
    limit = 100

    cookies = {
        "LEETCODE_SESSION": session,
        "csrftoken": csrf_token
    }

    headers = {
        **HEADERS,
        "x-csrftoken": csrf_token,
        "origin": "https://leetcode.com"
    }

    async with httpx.AsyncClient(
        timeout=30.0,
        cookies=cookies,
        headers=headers
    ) as client:

        while True:

            payload = {
                "query": query,
                "variables": {
                    "filters": {
                        "questionStatus": "SOLVED",
                        "skip": skip,
                        "limit": limit
                    }
                }
            }

            response = await client.post(
                LEETCODE_GRAPHQL_URL,
                json=payload
            )

            response.raise_for_status()

            result = response.json()

            if result.get("errors"):
                raise ValueError(
                    f"LeetCode API error: {result['errors']}"
                )

            data = (
                result.get("data", {})
                .get("userProgressQuestionList")
            )

            if data is None:
                raise ValueError(
                    "Unable to retrieve solved-question history. "
                    "Check the GraphQL query and session credentials."
                )

            questions = data.get("questions", [])
            total = data.get("totalNum", 0)

            if not questions:
                break

            all_questions.extend(questions)

            print(
                f"Fetched {len(all_questions)}/{total} "
                "solved questions"
            )

            if len(all_questions) >= total:
                break

            skip += limit

    # Remove duplicate slugs
    unique_questions = {}

    for question in all_questions:

        slug = question.get("titleSlug")

        if not slug:
            continue

        unique_questions[slug] = {
            "title": question.get("title"),
            "title_slug": slug,
            "difficulty": question.get("difficulty"),
            "solved_at": question.get("lastSubmittedAt")
        }

    return list(unique_questions.values())