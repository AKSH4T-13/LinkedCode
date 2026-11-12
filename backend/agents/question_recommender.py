from backend.llm.token_budget import invoke_budgeted
import json
import re

from backend.llm.groq_client import groq_llm


def recommend_question(user_profile, candidates):

    if not candidates:
        raise ValueError("No unsolved candidate questions available.")

    # Remove already solved questions
    solved_slugs = {
        question.get("title_slug")
        for question in user_profile.get("analyzed_questions", [])
        if question.get("title_slug")
    }

    candidates = [
        question for question in candidates
        if question.get("title_slug") not in solved_slugs
    ]

    if not candidates:
        raise ValueError("No unsolved questions available.")

    # Keep only the most relevant candidate information.
    # Candidate ranking is already handled by candidate_service.
    compact_candidates = [
        {
            "title_slug": question.get("title_slug"),
            "title": question.get("title"),
            "difficulty": question.get("difficulty"),
            "topics": question.get("topics", [])
        }
        for question in candidates[:10]
    ]

    # Remove detailed analyzed question data from the profile.
    # Keep only the useful profile information.
    compact_profile = {
        key: value
        for key, value in user_profile.items()
        if key != "analyzed_questions"
    }

    prompt = f"""
You are an expert competitive programming mentor.

Recommend exactly ONE existing LeetCode problem.

USER PROFILE:
{json.dumps(compact_profile, separators=(",", ":"))}

AVAILABLE UNSOLVED QUESTIONS:
{json.dumps(compact_candidates, separators=(",", ":"))}

RULES:
1. Select only one question from the candidates.
2. Never invent a question or title_slug.
3. Prefer topics relevant to the user's practice.
4. Consider the user's difficulty level.
5. Explain briefly why the question is suitable.
6. Return only valid JSON. No markdown or extra text.

JSON FORMAT:
{{
    "title": "Question title",
    "title_slug": "question-slug",
    "difficulty": "Medium",
    "topics": ["Array", "Hash Table"],
    "reason": "Reason for recommendation"
}}
"""

    response = invoke_budgeted(groq_llm,prompt,"Existing Question Recommendation",max_output_tokens=1200)

    content = response.content

    if isinstance(content, list):
        content = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )

    content = content.strip()

    # Remove markdown code fences if present
    content = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        content,
        flags=re.IGNORECASE
    ).strip()

    try:
        result = json.loads(content)

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from Groq: {e}")

    if not isinstance(result, dict):
        raise ValueError("Groq response must be a JSON object.")

    required_fields = [
        "title",
        "title_slug",
        "difficulty",
        "topics",
        "reason"
    ]

    for field in required_fields:
        if field not in result:
            raise ValueError(f"Missing field: {field}")

    if not isinstance(result["title_slug"], str):
        raise ValueError("Invalid title_slug returned by Groq.")

    if not isinstance(result["reason"], str):
        raise ValueError("Invalid recommendation reason.")

    if not isinstance(result["topics"], list):
        raise ValueError("Invalid topics format.")

    # Verify that the selected question exists in our catalogue.
    candidate_map = {
        question["title_slug"]: question
        for question in compact_candidates
    }

    selected_slug = result["title_slug"]

    if selected_slug not in candidate_map:
        raise ValueError(
            "Groq selected a question outside the candidate list."
        )

    # Always use trusted catalogue metadata.
    selected = candidate_map[selected_slug]

    result["title"] = selected["title"]
    result["difficulty"] = selected["difficulty"]
    result["topics"] = selected["topics"]

    return result