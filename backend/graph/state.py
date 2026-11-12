from typing import TypedDict, List, Dict, Any


class LinkedCodeState(TypedDict, total=False):

    # Authenticated user information
    user_id: int
    username: str

    # LeetCode profile
    user_profile: Dict[str, Any]

    # Candidate questions for Agent 1
    candidates: List[Dict[str, Any]]

    # Agent 1 output
    existing_recommendation: Dict[str, Any]

    # Agent 2 output
    generated_question: Dict[str, Any]

    # Agent 2 validation
    validation_report: Dict[str, Any]

    # Agent 2 refinement attempts
    refinement_attempts: int

    # Final combined output
    final_recommendations: Dict[str, Any]

    # Error tracking
    errors: List[str]
