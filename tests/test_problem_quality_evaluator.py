from backend.services.problem_quality_evaluator import (
    evaluate_problem_quality,
    extract_complexity_order,
    normalize_solution
)

import pytest


# =========================================================
# SAMPLE VALID QUESTION
# =========================================================

def create_valid_question():

    return {
        "title": "Maximum Subarray Sum",
        "difficulty": "Medium",

        "description": (
            "Given an integer array of size N, find the "
            "maximum sum among all contiguous subarrays. "
            "The array may contain both positive and negative "
            "integers. Return the maximum possible subarray sum."
        ),

        "constraints": [
            "1 <= N <= 200000",
            "-1000000000 <= A[i] <= 1000000000"
        ],

        "examples": [
            {
                "input": "5\n-2 1 -3 4 5",
                "output": "9",
                "explanation": "The subarray [4, 5] has sum 9."
            },
            {
                "input": "3\n-5 -2 -8",
                "output": "-2",
                "explanation": "The maximum subarray contains -2."
            }
        ],

        "reference_solution": """
def solve(arr):
    current = best = arr[0]

    for value in arr[1:]:
        current = max(value, current + value)
        best = max(best, current)

    return best
""",

        "brute_force_solution": """
def solve(arr):
    best = arr[0]

    for i in range(len(arr)):
        total = 0

        for j in range(i, len(arr)):
            total += arr[j]
            best = max(best, total)

    return best
""",

        "time_complexity": "O(N)",
        "brute_force_complexity": "O(N^2)",
        "space_complexity": "O(1)"
    }


# =========================================================
# TEST 1: COMPLEXITY EXTRACTION
# =========================================================

def test_complexity_extraction():

    assert extract_complexity_order("O(1)") == 1
    assert extract_complexity_order("O(log N)") == 2
    assert extract_complexity_order("O(N)") == 3
    assert extract_complexity_order("O(N log N)") == 4
    assert extract_complexity_order("O(N^2)") == 5

    print("PASS: Complexity extraction")


# =========================================================
# TEST 2: AST NORMALIZATION
# =========================================================

def test_ast_normalization():

    solution_1 = """
def solve():
    x = 10
    print(x)
"""

    solution_2 = """
def solve():
    x = 50
    print(x)
"""

    solution_3 = """
def solve():
    for i in range(10):
        print(i)
"""

    assert normalize_solution(solution_1) == normalize_solution(
        solution_2
    )

    assert normalize_solution(solution_1) != normalize_solution(
        solution_3
    )

    print("PASS: AST normalization")


# =========================================================
# TEST 3: GOOD QUESTION
# =========================================================

def test_good_question():

    question = create_valid_question()

    audit = {
        "status": "PASS"
    }

    result = evaluate_problem_quality(
        question,
        audit
    )

    assert result["score"] >= 80
    assert result["quality"] == "GOOD"
    assert result["is_acceptable"] is True

    print("PASS: Good question accepted")
    print("Score:", result["score"])


# =========================================================
# TEST 4: MISSING DESCRIPTION
# =========================================================

def test_missing_description():

    question = create_valid_question()

    question["description"] = ""

    result = evaluate_problem_quality(question)

    assert result["is_acceptable"] is False
    assert len(result["issues"]) > 0

    print("PASS: Missing description detected")


# =========================================================
# TEST 5: IDENTICAL SOLUTIONS
# =========================================================

def test_identical_solutions():

    question = create_valid_question()

    question["brute_force_solution"] = (
        question["reference_solution"]
    )

    result = evaluate_problem_quality(question)

    assert result["score"] < 80

    assert any(
        "identical AST" in issue
        for issue in result["issues"]
    )

    print("PASS: Identical solutions detected")


# =========================================================
# TEST 6: AUDIT FAILURE
# =========================================================

def test_audit_failure():

    question = create_valid_question()

    audit = {
        "status": "FAIL"
    }

    result = evaluate_problem_quality(
        question,
        audit
    )

    assert result["is_acceptable"] is False

    print("PASS: Audit failure detected")


# =========================================================
# TEST 7: INVALID DIFFICULTY
# =========================================================

def test_invalid_difficulty():

    question = create_valid_question()

    question["difficulty"] = "Super Hard"

    result = evaluate_problem_quality(question)

    assert any(
        "Invalid difficulty" in issue
        for issue in result["issues"]
    )

    print("PASS: Invalid difficulty detected")


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    tests = [
        test_complexity_extraction,
        test_ast_normalization,
        test_good_question,
        test_missing_description,
        test_identical_solutions,
        test_audit_failure,
        test_invalid_difficulty
    ]

    passed = 0

    for test in tests:

        try:
            test()
            passed += 1

        except Exception as error:
            print(f"FAIL: {test.__name__}: {error}")

    failed = len(tests) - passed

    print("\n========== FINAL REPORT ==========")
    print("Total:", len(tests))
    print("Passed:", passed)
    print("Failed:", failed)

    if failed == 0:
        print("\nALL QUALITY EVALUATOR TESTS PASSED!")
    else:
        print("\nSOME TESTS FAILED!")


@pytest.mark.parametrize(
    "complexity, expected",
    [
        ("O(1)", 1),
        ("O(log n)", 2),
        ("O(n)", 3),
        ("O(n log n)", 4),
        ("O(n^2)", 5),
        ("O(n^3)", 6),
        ("O(2^n)", 7),
        ("O(n!)", 8),
        ("o(n)", 3),
        ("O(Nonsense)", None),
        ("O(n) extra text", None),
        ("Linear", None),
        ("", None),
        (None, None),
        (123, None),
    ]
)
def test_extract_complexity_order(complexity, expected):
    assert extract_complexity_order(complexity) == expected