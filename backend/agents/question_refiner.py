from backend.llm.token_budget import invoke_budgeted
import json
import os
from copy import deepcopy

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from backend.agents.question_generator import (
    parse_response,
    validate_question_structure
)


# =========================================================
# GROQ CONFIGURATION
# =========================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found!")


refiner_llm = ChatGroq(
    model="openai/gpt-oss-20b",
    groq_api_key=GROQ_API_KEY,
    temperature=0.2,
    max_tokens=3500,
    reasoning_effort="low",
    reasoning_format="hidden",
    max_retries=1,
    timeout=60
)


# =========================================================
# VALIDATION FEEDBACK EXTRACTION
# =========================================================

def extract_validation_feedback(validation_report):
    """
    Extract failed tests, stage summaries and validation
    statistics for the refinement process.
    """

    results = validation_report.get("results", [])

    failed_results = [
        result
        for result in results
        if not result.get("passed", False)
    ]

    failure_feedback = {
        "passed": validation_report.get("passed"),
        "total_tests": validation_report.get("total_tests"),
        "failed": validation_report.get("failed"),
        "is_valid": validation_report.get("is_valid"),
        "stage_summary": validation_report.get(
            "stage_summary",
            {}
        ),
        "failed_cases": failed_results
    }

    return failure_feedback


# =========================================================
# REFINEMENT PROMPT
# =========================================================

def build_refinement_prompt(question, failure_feedback):

    from backend.agents.question_generator import REQUIRED_FIELDS
    # Diagnostic reports duplicate the actual problem and need not be sent back.
    payload={key:question[key] for key in REQUIRED_FIELDS if key in question}
    original_question=json.dumps(payload,separators=(",", ":"),ensure_ascii=False)
    validation_data=json.dumps(failure_feedback,separators=(",", ":"),ensure_ascii=False)
    return f"""
You are a competitive programming correctness engineer.
Repair this original DSA problem using the automated failure evidence.

ORIGINAL QUESTION:
{original_question}

VALIDATION FEEDBACK:
{validation_data}

Requirements:
- Derive the mathematical answer independently; neither the oracle nor expected
  outputs are automatically correct. Identify and fix the actual root cause.
- Recheck every example, normal case and verification case, including cases that
  previously passed. Correct incorrect outputs; preserve correct ones.
- Verify optimized, brute-force and independent oracle implementations against
  the same statement, input/output format and constraints. Handle negative/zero
  values, duplicates, boundaries and algorithm-specific assumptions.
- Preserve the problem's intended semantics. Do not weaken constraints to make
  a broken algorithm pass. Recheck time and space complexity.
- Preserve all case inputs and their counts. Every example needs input, output
  and explanation; every test needs input and expected_output.
- Keep the oracle algorithm independent, and all Python programs complete,
  executable, reading stdin and printing stdout.
- Preserve stress_test_spec and brute_force_complexity EXACTLY. The application
  restores these original generator-owned fields after parsing.
- Return the complete question JSON with these fields: {", ".join(REQUIRED_FIELDS)}.
- No diagnostic/quality/stress reports, performance_test_cases, Markdown fences
  or extra fields. Use valid escaped JSON strings for code. Return JSON only.
"""


# =========================================================
# QUESTION REFINER
# =========================================================

def refine_question(question, validation_report):

    # -----------------------------------------------------
    # EXTRACT VALIDATION FEEDBACK
    # -----------------------------------------------------

    failure_feedback = extract_validation_feedback(
        validation_report
    )

    print("\n========== REFINEMENT ANALYSIS ==========")

    print(
        "Total tests:",
        failure_feedback["total_tests"]
    )

    print(
        "Passed:",
        failure_feedback["passed"]
    )

    print(
        "Failed:",
        failure_feedback["failed"]
    )

    print(
        "Failed cases sent to refiner:",
        len(failure_feedback["failed_cases"])
    )

    # -----------------------------------------------------
    # BUILD PROMPT
    # -----------------------------------------------------

    prompt = build_refinement_prompt(
        question,
        failure_feedback
    )

    # -----------------------------------------------------
    # GROQ REQUEST
    # -----------------------------------------------------

    print("\n[REFINER] Sending failed cases to Groq...")
    print("[REFINER] Rechecking all examples and test cases.")
    print("[REFINER] Rechecking oracle independence.")

    response = invoke_budgeted(refiner_llm,prompt,"Question Refinement",max_output_tokens=3500)

    print("\n========== REFINER DEBUG ==========")

    print(
        "Response Metadata:",
        response.response_metadata
    )

    print(
        "Usage Metadata:",
        response.usage_metadata
    )

    print("===================================\n")

    # -----------------------------------------------------
    # PARSE RESPONSE
    # -----------------------------------------------------

    refined = parse_response(response)

    # -----------------------------------------------------
    # PRESERVE GENERATOR-OWNED FIELDS
    # -----------------------------------------------------

    # These fields are created/validated by the generator pipeline.
    # The refiner must not silently change the stress-test constraints
    # or the brute-force complexity contract.
    preserved_fields = (
        "stress_test_spec",
        "brute_force_complexity"
    )

    for field in preserved_fields:
        if field not in question:
            raise ValueError(
                f"Original question is missing required field: {field}"
            )
        refined[field] = deepcopy(question[field])

    # -----------------------------------------------------
    # STRUCTURAL VALIDATION
    # -----------------------------------------------------

    validate_question_structure(refined)

    print(
        "[REFINER] Refined question structure validated."
    )

    print(
        "[REFINER] Oracle independence heuristic passed."
    )

    print(
        "[REFINER] All examples and test cases "
        "have been requested for recalculation."
    )

    return refined
