from unittest.mock import patch

from backend.agents.question_generator import (
    generate_dsa_question
)


# =========================================================
# MOCK CORE QUESTION
# =========================================================

def create_mock_core():

    return {
        "title": "Maximum Subarray Sum",
        "difficulty": "Medium",

        "topics": ["Array", "Dynamic Programming"],

        "description": (
            "Given an integer array, find the maximum sum "
            "of any contiguous subarray. The array may contain "
            "positive and negative integers."
        ),

        "input_format": "First line N, second line array elements.",
        "output_format": "Print the maximum subarray sum.",

        "constraints": [
            "1 <= N <= 200000",
            "-100000 <= arr[i] <= 100000"
        ],

        "examples": [
            {
                "input": "5\n-2 1 -3 4 5",
                "output": "9",
                "explanation": "The subarray [4,5] has sum 9."
            },
            {
                "input": "3\n-5 -2 -8",
                "output": "-2",
                "explanation": "The maximum element is -2."
            }
        ],

        "reference_solution": """
def solve(arr):
    current = best = arr[0]

    for value in arr[1:]:
        current = max(value, current + value)
        best = max(best, current)

    print(best)
""",

        "brute_force_solution": """
def solve(arr):
    best = arr[0]

    for i in range(len(arr)):
        total = 0

        for j in range(i, len(arr)):
            total += arr[j]
            best = max(best, total)

    print(best)
""",

        "time_complexity": "O(N)",
        "brute_force_complexity": "O(N^2)",
        "space_complexity": "O(1)",

        "stress_test_spec": {
    "generator_type": "array_n",
    "input_layout": "n_then_array",
    "parameters": {
        "n_min": 1,
        "n_max": 200000,
        "value_min": -100000,
        "value_max": 100000
    },
    "constraint_bounds": {
        "n": {
            "min": 1,
            "max": 200000
        },
        "value": {
            "min": -100000,
            "max": 100000
        }
    }
},
    }


# =========================================================
# MOCK ORACLE
# =========================================================

def create_mock_oracle():

    return {
        "algorithm": "Prefix Sum with exhaustive subarray enumeration.",

        "independent_oracle": """
def solve(arr):
    prefix = [0]

    for value in arr:
        prefix.append(prefix[-1] + value)

    best = arr[0]

    for i in range(len(arr)):
        for j in range(i + 1, len(arr) + 1):
            current_sum = prefix[j] - prefix[i]
            best = max(best, current_sum)

    print(best)
"""
    }


# =========================================================
# MOCK TEST DATA
# =========================================================
def create_mock_test_data():

    return {
        "test_cases": [
            {
                "input": f"3\n{i} {i+1} {i+2}",
                "expected_output": ""
            }
            for i in range(1, 11)
        ],

        "verification_test_cases": [
            {
                "input": f"3\n{i} {i+2} {i+4}",
                "expected_output": ""
            }
            for i in range(20, 35)
        ]
    }


# =========================================================
# TEST 1: QUALITY EVALUATOR INTEGRATION
# =========================================================

def test_quality_integration():

    print("\n========== TEST 1: QUALITY INTEGRATION ==========")

    core = create_mock_core()

    oracle = create_mock_oracle()

    test_data = create_mock_test_data()

    audit = {
        "status": "PASS"
    }

    quality_report = {
        "score": 90,
        "quality": "GOOD",
        "is_acceptable": True,
        "strengths": ["Solution audit passed."],
        "issues": []
    }

    with patch(
        "backend.agents.question_generator.generate_phase_json"
    ) as mock_generate:

        mock_generate.side_effect = [
            core,
            oracle,
            test_data
        ]

        with patch(
            "backend.agents.question_generator.audit_generated_solutions",
            return_value=audit
        ):

            with patch(
                "backend.agents.question_generator.populate_expected_outputs",
                side_effect=lambda data, core, oracle: data
            ):

                with patch(
                    "backend.agents.question_generator.evaluate_problem_quality",
                    return_value=quality_report
                ):

                    question = generate_dsa_question(
                        ["Array"],
                        "Medium"
                    )

    assert "quality_report" in question

    assert question["quality_report"]["score"] == 90

    assert question["quality_report"]["is_acceptable"] is True

    print("PASS: Quality evaluator integrated successfully.")


# =========================================================
# TEST 2: QUALITY REJECTION
# =========================================================

def test_quality_rejection():

    print("\n========== TEST 2: QUALITY REJECTION ==========")

    core = create_mock_core()

    oracle = create_mock_oracle()

    test_data = create_mock_test_data()

    audit = {
        "status": "PASS"
    }

    quality_report = {
        "score": 45,
        "quality": "POOR",
        "is_acceptable": False,
        "strengths": [],
        "issues": ["Problem is too trivial."]
    }

    with patch(
        "backend.agents.question_generator.generate_phase_json"
    ) as mock_generate:

        mock_generate.side_effect = [
            core,
            oracle,
            test_data
        ]

        with patch(
            "backend.agents.question_generator.audit_generated_solutions",
            return_value=audit
        ):

            with patch(
                "backend.agents.question_generator.populate_expected_outputs",
                side_effect=lambda data, core, oracle: data
            ):

                with patch(
                    "backend.agents.question_generator.evaluate_problem_quality",
                    return_value=quality_report
                ):

                    try:

                        generate_dsa_question(
                            ["Array"],
                            "Medium"
                        )

                        raise AssertionError(
                            "Poor quality question was accepted."
                        )

                    except ValueError as error:

                        assert "failed quality evaluation" in str(error)

    print("PASS: Poor quality question rejected.")


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    tests = [
        test_quality_integration,
        test_quality_rejection
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

        print("\nALL QUALITY INTEGRATION TESTS PASSED!")

    else:

        print("\nSOME TESTS FAILED!")