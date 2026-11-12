from backend.database import SessionLocal
from backend.services.practice_plan import build_practice_plan
from backend.services.question_analyzer import analyze_questions

from backend.services.candidate_service import (
    fetch_unsolved_candidates,
    save_recommendation,
    save_generated_question
)

from backend.agents.question_recommender import recommend_question
from backend.services.question_pipeline import generate_valid_question


# =========================================================
# NODE 1: USER PROFILE
# =========================================================

async def profile_node(state):

    username = state["username"]
    user_id = state["user_id"]

    print("\n[PROFILE NODE] Fetching user profile...")

    analysis = await analyze_questions(username)

    user_profile = analysis["user_profile"]

    user_profile["username"] = username
    user_profile["analyzed_questions"] = analysis["analyzed_questions"]
    user_profile["practice_plan"] = build_practice_plan(user_profile)

    print("[PROFILE NODE] Profile analysis completed.")

    return {
        "user_id": user_id,
        "username": username,
        "user_profile": user_profile
    }


# =========================================================
# NODE 2: FETCH CANDIDATES
# =========================================================

async def candidate_node(state):

    print("\n[CANDIDATE NODE] State received:", state.keys())

    user_profile = state["user_profile"]
    user_id = state.get("user_id")

    if user_id is None:
        raise ValueError(
            f"user_id missing in candidate_node. Available keys: {list(state.keys())}"
        )

    print("\n[CANDIDATE NODE] Fetching unsolved questions...")

    candidates = await fetch_unsolved_candidates(
        user_profile=user_profile,
        user_id=user_id,
        max_candidates=30
    )
    if not candidates:
        raise ValueError("No unsolved candidate questions are currently available.")

    print(
        f"[CANDIDATE NODE] Retrieved {len(candidates)} candidates."
    )

    return {
        "candidates": candidates
    }


# =========================================================
# AGENT 1: EXISTING QUESTION RECOMMENDER
# =========================================================

def recommender_node(state):

    user_profile = state["user_profile"]
    candidates = state["candidates"]

    print("\n[AGENT 1] Recommending existing LeetCode question...")

    recommendation = recommend_question(
        user_profile,
        candidates
    )

    print("[AGENT 1] Recommendation completed.")

    return {
        "existing_recommendation": recommendation
    }


# =========================================================
# AGENT 2: ORIGINAL QUESTION GENERATOR
# =========================================================

def generator_node(state):

    user_profile = state["user_profile"]

    print("\n[AGENT 2] Generating original DSA question...")

    topic_frequency = user_profile.get(
        "topic_frequency",
        {}
    )

    if isinstance(topic_frequency, dict):
        topics = list(topic_frequency.keys())[:5]
    else:
        topics = list(topic_frequency)[:5]

    if not topics:
        topics = ["Array", "Hash Table"]

    plan = user_profile.get("practice_plan") or build_practice_plan(user_profile)
    topics = plan["topics"]

    result = generate_valid_question(
        topics=topics,
        difficulty=plan["difficulty"],
        max_attempts=3,
        user_profile=user_profile
    )

    if result["status"] != "success":
        raise RuntimeError(
            f"Question generation failed: {result.get('message')}"
        )

    print("[AGENT 2] Question generated and validated.")

    return {
        "generated_question": result["question"],
        "validation_report": result["validation"],
        "refinement_attempts": result["attempts"]
    }


# =========================================================
# NODE 5: COMBINE AND SAVE
# =========================================================

def combine_node(state):

    print("\n[COMBINE NODE] Combining recommendations...")

    user_id = state["user_id"]

    existing_recommendation = state["existing_recommendation"]
    generated_question = state["generated_question"]
    validation_report = state.get("validation_report")

    # -----------------------------------------------------
    # SAVE AGENT 1 RECOMMENDATION
    # -----------------------------------------------------

    print("\n[COMBINE NODE] Saving existing recommendation...")

    # Persist both agents' results atomically: a failed generated save must
    # not leave an unrelated recommendation committed.
    with SessionLocal() as db:
        with db.begin():
            recommendation_save_result = save_recommendation(
                user_id=user_id,
                recommendation=existing_recommendation,
                db_session=db,
            )
            generated_save_result = save_generated_question(
                user_id=user_id,
                question=generated_question,
                validation_report=validation_report,
                db_session=db,
            )

    print("[COMBINE NODE] Agent 1:", recommendation_save_result["message"])
    print("[COMBINE NODE] Agent 2:", generated_save_result["message"])

    # -----------------------------------------------------
    # FINAL RECOMMENDATIONS
    # -----------------------------------------------------

    final_recommendations = {
        "existing_question": existing_recommendation,
        "generated_question": generated_question
    }

    print("\n[COMBINE NODE] Both questions saved successfully.")
    print("[COMBINE NODE] Final recommendations ready.")

    return {
        "final_recommendations": final_recommendations
    }
