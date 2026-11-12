from unittest.mock import patch

from backend.agents import question_generator as qg


# =========================================================
# MOCK DATA
# =========================================================

def create_mock_core():

    return {
        "title": "Maximum Subarray Sum",
        "difficulty": "Medium",
        "topics": ["Array"],
        "description": "Find the maximum sum of a contiguous subarray.",
        "input_format": "N followed by array elements.",
        "output_format": "Print maximum subarray sum.",
        "constraints": ["1 <= N <= 1000", "-1000 <= arr[i] <= 1000"],
        "examples": [
            {
                "input": "3\n1 2 3",
                "output": "6",
                "explanation": "All elements form the maximum subarray."
            },
            {
                "input": "3\n-1 -2 -3",
                "output": "-1",
                "explanation": "The maximum subarray contains -1."
            }
        ],
        "reference_solution": "optimized",
        "brute_force_solution": "brute_force",
        "time_complexity": "O(N)",
        "space_complexity": "O(1)",
        "stress_test_spec": {
            "generator_type": "array_n",
            "input_layout": "N followed by N array elements",
            "constraint_bounds": {
                "n": {"min": 1, "max": 1000},
                "value": {"min": -1000, "max": 1000}
            },
            "parameters": {
                "n_min": 1,
                "n_max": 1000,
                "value_min": -1000,
                "value_max": 1000
            }
        }
    }


def create_mock_oracle():

    return {
        "algorithm": "Independent brute-force enumeration.",
        "independent_oracle": "oracle"
    }


def create_mock_test_data():

    return {
        "test_cases": [],
        "verification_test_cases": []
    }


def create_mock_question():

    return {
        "title": "Maximum Subarray Sum",
        "reference_solution": "optimized",
        "verification_approach": {
            "independent_oracle": "oracle"
        }
    }


def create_quality_report():

    return {
        "score": 90,
        "quality": "GOOD",
        "is_acceptable": True,
        "strengths": ["Audit passed."],
        "issues": []
    }


# =========================================================
# COMMON MOCK SETUP
# =========================================================

def setup_pipeline_mocks(stack, stress_report):

    core = create_mock_core()

    oracle = create_mock_oracle()

    test_data = create_mock_test_data()

    quality = create_quality_report()

    stress_cases = [
        {
            "input": "3\n1 2 3",
            "category": "small_array",
            "oracle_check": True
        }
    ]

    stack.enter_context(
        patch.object(
            qg,
            "generate_phase_json",
            side_effect=[core, oracle, test_data]
        )
    )

    stack.enter_context(
        patch.object(
            qg,
            "validate_core_response"
        )
    )

    stack.enter_context(
        patch.object(
            qg,
            "audit_generated_solutions",
            return_value={"status": "PASS"}
        )
    )

    stack.enter_context(
        patch.object(
            qg,
            "validate_oracle_response"
        )
    )

    stack.enter_context(
        patch.object(
            qg,
            "validate_test_case_response"
        )
    )

    stack.enter_context(
        patch.object(
            qg,
            "populate_expected_outputs",
            return_value=test_data
        )
    )

    stack.enter_context(
        patch.object(
            qg,
            "assemble_question",
            return_value=create_mock_question()
        )
    )

    stack.enter_context(
        patch.object(
            qg,
            "validate_question_structure"
        )
    )

    stack.enter_context(
        patch.object(
            qg,
            "evaluate_problem_quality",
            return_value=quality
        )
    )

    generator_mock = stack.enter_context(
        patch.object(
            qg,
            "generate_stress_tests",
            return_value=stress_cases
        )
    )

    runner_mock = stack.enter_context(
        patch.object(
            qg,
            "run_stress_tests",
            return_value=stress_report
        )
    )

    return generator_mock, runner_mock


# =========================================================
# TEST 1: SUCCESSFUL STRESS PIPELINE
# =========================================================

def test_stress_pipeline_success():

    from contextlib import ExitStack

    print("\n========== TEST 1: PIPELINE SUCCESS ==========")

    successful_report = {
        "total_tests": 1,
        "passed": 1,
        "failed": 0,
        "is_valid": True,
        "results": []
    }

    with ExitStack() as stack:

        generator_mock, runner_mock = setup_pipeline_mocks(
            stack,
            successful_report
        )

        question = qg.generate_dsa_question(
            ["Array"],
            "Medium"
        )

        assert "stress_test_report" in question

        assert question["stress_test_report"]["is_valid"] is True

        assert "quality_report" in question

        generator_mock.assert_called_once()

        runner_mock.assert_called_once()

    print("PASS: Successful stress pipeline")


# =========================================================
# TEST 2: STRESS FAILURE REJECTS QUESTION
# =========================================================

def test_stress_pipeline_failure():

    from contextlib import ExitStack

    print("\n========== TEST 2: PIPELINE FAILURE ==========")

    failed_report = {
        "total_tests": 7,
        "passed": 5,
        "failed": 1,
        "is_valid": False,
        "results": []
    }

    with ExitStack() as stack:

        generator_mock, runner_mock = setup_pipeline_mocks(
            stack,
            failed_report
        )

        try:

            qg.generate_dsa_question(
                ["Array"],
                "Medium"
            )

            raise AssertionError(
                "Failed stress test was accepted."
            )

        except ValueError as error:

            assert "failed stress testing" in str(error).lower()

        generator_mock.assert_called_once()

        runner_mock.assert_called_once()

    print("PASS: Failed stress test rejected")


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    tests = [
        test_stress_pipeline_success,
        test_stress_pipeline_failure
    ]

    passed = 0

    for test in tests:

        try:

            test()
            passed += 1

        except Exception as error:

            print(f"FAIL: {test.__name__}: {error}")

    print("\n========== FINAL REPORT ==========")

    print("Total:", len(tests))
    print("Passed:", passed)
    print("Failed:", len(tests) - passed)

    if passed == len(tests):

        print("\nALL STRESS PIPELINE TESTS PASSED!")

    else:

        print("\nSOME TESTS FAILED!")