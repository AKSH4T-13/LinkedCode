import json
import asyncio
import httpx

from pathlib import Path
from datetime import datetime, timedelta, timezone

from backend.database import SessionLocal
from backend.models import (
    User,
    SolvedQuestion,
    RecommendationHistory,
    GeneratedQuestion
)


LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql/"

HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com/",
    "User-Agent": "Mozilla/5.0"
}

CACHE_DIR = Path("backend/data")
CACHE_FILE = CACHE_DIR / "leetcode_catalogue.json"

CACHE_HOURS = 24
PAGE_SIZE = 100


QUERY = """
query problemsetQuestionListV2(
    $filters: QuestionFilterInput,
    $limit: Int,
    $searchKeyword: String,
    $skip: Int,
    $sortBy: QuestionSortByInput,
    $categorySlug: String
) {
    problemsetQuestionListV2(
        filters: $filters,
        limit: $limit,
        searchKeyword: $searchKeyword,
        skip: $skip,
        sortBy: $sortBy,
        categorySlug: $categorySlug
    ) {
        questions {
            id
            titleSlug
            title
            questionFrontendId
            paidOnly
            difficulty
            topicTags {
                name
                slug
            }
        }
        totalLength
        hasMore
    }
}
"""


# --------------------------------------------------
# FETCH CATALOGUE PAGE
# --------------------------------------------------

async def fetch_catalogue_page(client, skip):

    filters = {
        "filterCombineType": "ALL",
        "statusFilter": {
            "questionStatuses": [],
            "operator": "IS"
        },
        "difficultyFilter": {
            "difficulties": [],
            "operator": "IS"
        },
        "languageFilter": {
            "languageSlugs": [],
            "operator": "IS"
        },
        "topicFilter": {
            "topicSlugs": [],
            "operator": "IS"
        },
        "acceptanceFilter": {},
        "frequencyFilter": {},
        "frontendIdFilter": {},
        "lastSubmittedFilter": {},
        "publishedFilter": {},
        "companyFilter": {
            "companySlugs": [],
            "operator": "IS"
        },
        "premiumFilter": {
            "premiumStatus": [],
            "operator": "IS"
        }
    }

    payload = {
        "operationName": "problemsetQuestionListV2",
        "query": QUERY,
        "variables": {
            "skip": skip,
            "limit": PAGE_SIZE,
            "categorySlug": "all-code-essentials",
            "searchKeyword": "",
            "filters": filters,
            "sortBy": {
                "sortField": "CUSTOM",
                "sortOrder": "ASCENDING"
            }
        }
    }

    response = await client.post(
        LEETCODE_GRAPHQL_URL,
        json=payload,
        headers=HEADERS
    )

    if response.status_code != 200:
        raise ValueError(
            f"LeetCode API Error {response.status_code}: "
            f"{response.text[:1000]}"
        )

    data = response.json()

    if data.get("errors"):
        raise ValueError(f"GraphQL errors: {data['errors']}")

    result = data.get("data", {}).get(
        "problemsetQuestionListV2"
    )

    if result is None:
        raise ValueError("Problem catalogue not found in response.")

    return result


# --------------------------------------------------
# FETCH ALL PROBLEMS
# --------------------------------------------------

async def fetch_all_problems():

    all_problems = []
    skip = 0

    async with httpx.AsyncClient(timeout=30.0) as client:

        while True:

            result = await fetch_catalogue_page(client, skip)

            questions = result.get("questions", [])

            for question in questions:

                if question.get("paidOnly"):
                    continue

                all_problems.append({
                    "question_id": question["questionFrontendId"],
                    "title": question["title"],
                    "title_slug": question["titleSlug"],
                    "difficulty": question["difficulty"],
                    "topics": [
                        tag["name"]
                        for tag in question.get("topicTags", [])
                    ]
                })

            print(f"Fetched {len(all_problems)} problems so far.")

            if not result.get("hasMore"):
                break

            if not questions:
                break

            skip += PAGE_SIZE

            await asyncio.sleep(0.3)

    return all_problems


# --------------------------------------------------
# SAVE CATALOGUE
# --------------------------------------------------

def save_catalogue(problems):

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cache_data = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "problems": problems
    }

    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        json.dump(cache_data, file, indent=2)

    print("Catalogue cached successfully.")


# --------------------------------------------------
# LOAD CACHED CATALOGUE
# --------------------------------------------------

def load_cached_catalogue():

    if not CACHE_FILE.exists():
        return None

    try:

        with open(CACHE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        fetched_at = datetime.fromisoformat(data["fetched_at"])

        if (
            datetime.now(timezone.utc) - fetched_at
            > timedelta(hours=CACHE_HOURS)
        ):
            return None

        return data["problems"]

    except (ValueError, KeyError, json.JSONDecodeError):
        return None


# --------------------------------------------------
# GET PROBLEM CATALOGUE
# --------------------------------------------------

async def get_problem_catalogue():

    cached_problems = load_cached_catalogue()

    if cached_problems is not None:
        print("Using cached LeetCode catalogue.")
        return cached_problems

    print("Fetching fresh LeetCode catalogue...")

    problems = await fetch_all_problems()

    save_catalogue(problems)

    return problems


# --------------------------------------------------
# GET USER EXCLUSION HISTORY FROM SQLITE
# --------------------------------------------------

def get_user_exclusion_slugs(user_id: int):

    db = SessionLocal()

    try:
        user = db.query(User).filter(
            User.id == user_id
        ).first()

        if not user:
            raise ValueError("User not found.")

        solved_slugs = {
            slug
            for (slug,) in db.query(
                SolvedQuestion.question_slug
            ).filter(
                SolvedQuestion.user_id == user_id
            ).all()
        }

        recommended_slugs = {
            slug
            for (slug,) in db.query(
                RecommendationHistory.question_slug
            ).filter(
                RecommendationHistory.user_id == user_id,
                RecommendationHistory.status.in_([
                    "recommended",
                    "attempted",
                    "completed",
                    "skipped"
                ])
            ).all()
        }

        return solved_slugs, recommended_slugs

    finally:
        db.close()


# --------------------------------------------------
# FILTER AND RANK CANDIDATES
# --------------------------------------------------

def get_unsolved_candidates(
    user_profile,
    catalogue,
    max_candidates=30,
    solved_slugs=None,
    recommended_slugs=None,
    difficulty=None,
    topics=None
):

    analyzed_questions = user_profile.get(
        "analyzed_questions", []
    )

    # Recent solved submissions act as an additional safeguard
    recent_solved_slugs = {
        question["title_slug"]
        for question in analyzed_questions
        if question.get("title_slug")
    }

    solved_slugs = solved_slugs or set()
    recommended_slugs = recommended_slugs or set()

    # Combine all exclusion sources
    excluded_slugs = (
        solved_slugs
        | recent_solved_slugs
        | recommended_slugs
    )

    # Identify recently practised topics
    topic_frequency = user_profile.get(
        "topic_frequency", {}
    )

    if isinstance(topic_frequency, dict):

        user_topics = {
            topic.lower()
            for topic in topic_frequency
        }

    else:

        user_topics = {
            str(topic).lower()
            for topic in topic_frequency
        }

    # Remove solved and previously recommended questions
    candidates = [
        question
        for question in catalogue
        if question["title_slug"] not in excluded_slugs
        and (not difficulty or question["difficulty"].lower() == difficulty.lower())
        and (not topics or {topic.lower() for topic in topics}.intersection(
            topic.lower() for topic in question["topics"]))
    ]

    # Rank by topic relevance
    def calculate_relevance(question):

        question_topics = {
            topic.lower()
            for topic in question["topics"]
        }

        plan = user_profile.get("practice_plan", {})
        focus = {topic.lower() for topic in plan.get("topics", [])}
        return (
            question.get("difficulty", "").lower() == plan.get("difficulty", "").lower(),
            len(focus.intersection(question_topics)),
            len(user_topics.intersection(question_topics)),
        )

    candidates.sort(
        key=calculate_relevance,
        reverse=True
    )

    return candidates[:max_candidates]


# --------------------------------------------------
# MAIN CANDIDATE FETCHING FUNCTION
# --------------------------------------------------

async def fetch_unsolved_candidates(
    user_profile,
    user_id: int,
    max_candidates=30,
    difficulty=None,
    topics=None
):

    if not user_id:
        raise ValueError("User ID missing.")

    username = user_profile.get("username")

    if not username:
        raise ValueError("Username missing from user profile.")

    catalogue = await get_problem_catalogue()

    solved_slugs, recommended_slugs = (
        get_user_exclusion_slugs(user_id)
    )

    print("\n========== DATABASE HISTORY ==========")
    print("User ID:", user_id)
    print("Solved questions:", len(solved_slugs))
    print("Previously recommended:", len(recommended_slugs))

    candidates = get_unsolved_candidates(
        user_profile=user_profile,
        catalogue=catalogue,
        max_candidates=max_candidates,
        solved_slugs=solved_slugs,
        recommended_slugs=recommended_slugs,
        difficulty=difficulty,
        topics=topics
    )

    print("\n========== CANDIDATE FILTERING ==========")
    print("Total catalogue questions:", len(catalogue))
    print("Final candidates:", len(candidates))

    return candidates


# --------------------------------------------------
# SAVE RECOMMENDATION
# --------------------------------------------------

def save_recommendation(user_id: int, recommendation, db_session=None):

    db = db_session or SessionLocal()

    try:
        user = db.query(User).filter(
            User.id == user_id
        ).first()

        if not user:
            raise ValueError("User not found.")

        slug = recommendation["title_slug"]

        # Check if already solved
        solved = db.query(SolvedQuestion).filter(
            SolvedQuestion.user_id == user_id,
            SolvedQuestion.question_slug == slug
        ).first()

        if solved:
            raise ValueError(
                f"Cannot recommend already solved question: {slug}"
            )

        # Check duplicate recommendation
        existing = db.query(RecommendationHistory).filter(
            RecommendationHistory.user_id == user_id,
            RecommendationHistory.question_slug == slug
        ).first()

        if existing:
            return {
                "saved": False,
                "message": "Question was already recommended."
            }

        record = RecommendationHistory(
            user_id=user_id,
            question_slug=slug,
            status="recommended"
        )

        db.add(record)
        if db_session is None:
            db.commit()
        else:
            db.flush()

        return {
            "saved": True,
            "message": "Recommendation saved successfully."
        }

    except Exception:
        db.rollback()
        raise

    finally:
        if db_session is None:
            db.close()


# --------------------------------------------------
# UPDATE RECOMMENDATION STATUS
# --------------------------------------------------

def update_recommendation_status(
    user_id: int,
    question_slug: str,
    new_status: str
):

    allowed_statuses = {
        "recommended",
        "attempted",
        "completed",
        "skipped"
    }

    if new_status not in allowed_statuses:
        raise ValueError(
            f"Invalid status. Allowed: {allowed_statuses}"
        )

    db = SessionLocal()

    try:
        user = db.query(User).filter(
            User.id == user_id
        ).first()

        if not user:
            raise ValueError("User not found.")

        recommendation = db.query(RecommendationHistory).filter(
            RecommendationHistory.user_id == user_id,
            RecommendationHistory.question_slug == question_slug
        ).first()

        if not recommendation:
            raise ValueError("Recommendation not found.")

        recommendation.status = new_status

        # Add completed question to solved history
        if new_status == "completed":

            existing_solved = db.query(SolvedQuestion).filter(
                SolvedQuestion.user_id == user_id,
                SolvedQuestion.question_slug == question_slug
            ).first()

            if not existing_solved:
                db.add(
                    SolvedQuestion(
                        user_id=user_id,
                        question_slug=question_slug
                    )
                )

        db.commit()

        return {
            "success": True,
            "question_slug": question_slug,
            "status": new_status
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# --------------------------------------------------
# SAVE GENERATED QUESTION
# --------------------------------------------------

def save_generated_question(
    user_id: int,
    question: dict,
    validation_report: dict = None,
    db_session=None
):

    db = db_session or SessionLocal()

    try:
        user = db.query(User).filter(
            User.id == user_id
        ).first()

        if not user:
            raise ValueError("User not found.")

        title = question.get("title")
        difficulty = question.get("difficulty", "Medium")
        topics = question.get("topics", [])

        if not title:
            raise ValueError("Generated question title is missing.")

        record = GeneratedQuestion(
            user_id=user_id,
            title=title,
            difficulty=difficulty,
            topics=topics,
            question_data=question,
            validation_report=validation_report
        )

        db.add(record)
        if db_session is None:
            db.commit()
        else:
            db.flush()
        db.refresh(record)

        return {
            "saved": True,
            "generated_question_id": record.id,
            "message": "Generated question saved successfully."
        }

    except Exception:
        db.rollback()
        raise

    finally:
        if db_session is None:
            db.close()
