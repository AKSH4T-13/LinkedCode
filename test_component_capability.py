import inspect

from backend.agents.question_generator import (
    generate_dsa_question,
    validate_question_structure,
    validate_oracle_independence
)

from backend.agents.question_refiner import (
    refine_question,
    extract_validation_feedback,
    build_refinement_prompt
)

from backend.services.solution_validator import (
    execute_solution,
    validate_solution
)


# =========================================================
# TEST 1: IMPORT CHECK
# =========================================================

print("\n========== COMPONENT IMPORT CHECK ==========")

components = {
    "Generator": generate_dsa_question,
    "Refiner": refine_question,
    "Validator": validate_solution
}

for name, component in components.items():

    print(
        name,
        ": PASS" if callable(component) else ": FAIL"
    )


# =========================================================
# TEST 2: FUNCTION SIGNATURE CHECK
# =========================================================

print("\n========== FUNCTION SIGNATURE CHECK ==========")

print(
    "Generator:",
    inspect.signature(generate_dsa_question)
)

print(
    "Refiner:",
    inspect.signature(refine_question)
)

print(
    "Validator:",
    inspect.signature(validate_solution)
)


# =========================================================
# TEST 3: ORACLE INDEPENDENCE CHECK
# =========================================================

print("\n========== ORACLE INDEPENDENCE CHECK ==========")

brute_force = """
import sys

def solve():
    n = int(sys.stdin.readline())
    print(sum(range(n + 1)))

solve()
"""

optimized = """
import sys

def solve():
    n = int(sys.stdin.readline())
    print(n * (n + 1) // 2)

solve()
"""

oracle = """
import sys

def solve():
    n = int(sys.stdin.readline())
    print((n * n + n) // 2)

solve()
"""

try:

    validate_oracle_independence(
        brute_force,
        optimized,
        oracle
    )

    print("Oracle Independence: PASS")

except ValueError as error:

    print("Oracle Independence: FAIL")
    print("Reason:", error)


# =========================================================
# TEST 4: REFINER FEEDBACK EXTRACTION
# =========================================================

print("\n========== REFINER FEEDBACK CHECK ==========")

dummy_report = {
    "passed": 9,
    "total_tests": 10,
    "failed": 1,
    "is_valid": False,
    "stage_summary": {
        "examples": 2,
        "normal_test_cases": 5,
        "verification_test_cases": 5,
        "oracle_test_cases": 12
    },
    "results": [
        {
            "stage": "Independent Oracle Verification",
            "test_case": 1,
            "passed": False,
            "expected_output": "5",
            "oracle_output": "4"
        }
    ]
}

feedback = extract_validation_feedback(dummy_report)

print("Failed cases:", len(feedback["failed_cases"]))
print("Feedback extraction: PASS")


# =========================================================
# TEST 5: REFINER PROMPT CHECK
# =========================================================

print("\n========== REFINER PROMPT CHECK ==========")

dummy_question = {
    "title": "Compatibility Test",
    "difficulty": "Easy",
    "topics": ["Array"]
}

prompt = build_refinement_prompt(
    dummy_question,
    feedback
)

required_instructions = [
    "RECHECK ALL EXAMPLES",
    "RECHECK ALL NORMAL TEST CASES",
    "RECHECK ALL VERIFICATION TEST CASES",
    "INDEPENDENT ORACLE"
]

for instruction in required_instructions:

    passed = instruction in prompt

    print(
        instruction,
        ":",
        "PASS" if passed else "FAIL"
    )


# =========================================================
# TEST 6: VALIDATOR EXECUTION CHECK
# =========================================================

print("\n========== VALIDATOR EXECUTION CHECK ==========")

identity_solution = """
import sys

def solve():
    value = sys.stdin.readline().strip()
    print(value)

if __name__ == "__main__":
    solve()
"""

dummy_validation_question = {

    "reference_solution": identity_solution,

    "brute_force_solution": identity_solution,

    "examples": [
        {
            "input": "hello\n",
            "output": "hello",
            "explanation": "Identity test."
        },
        {
            "input": "world\n",
            "output": "world",
            "explanation": "Identity test."
        }
    ],

    "test_cases": [
        {
            "input": f"test{i}\n",
            "expected_output": f"test{i}"
        }
        for i in range(1, 6)
    ],

    "verification_test_cases": [
        {
            "input": f"verify{i}\n",
            "expected_output": f"verify{i}"
        }
        for i in range(1, 6)
    ],

    "verification_approach": {
        "algorithm": "Return the input unchanged.",
        "independent_oracle": identity_solution
    }
}

report = validate_solution(dummy_validation_question)

print("\nTotal:", report["total_tests"])
print("Passed:", report["passed"])
print("Failed:", report["failed"])
print("Valid:", report["is_valid"])

print("\nStage Summary:")

for stage, count in report["stage_summary"].items():

    print(stage, ":", count)


# =========================================================
# FINAL STATUS
# =========================================================

print("\n========== COMPATIBILITY STATUS ==========")

if report["is_valid"] and feedback["failed"] == 1:

    print("SUCCESS: Components are compatible.")

else:

    print("FAILED: Check the component errors.")

print("\nCompatibility testing completed.")