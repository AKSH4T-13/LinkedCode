import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from backend.services.stress_test_runner import run_stress_tests


# =========================================================
# MOCK QUESTION
# =========================================================

def create_question():

    return {
        "reference_solution": "optimized solution",
        "verification_approach": {
            "independent_oracle": "oracle solution"
        }
    }


# =========================================================
# TEST 1: SMALL INPUT ORACLE COMPARISON
# =========================================================

def test_oracle_comparison():

    question = create_question()

    stress_cases = [
        {
            "input": "3\n1 2 3",
            "category": "small_array",
            "oracle_check": True
        }
    ]

    def mock_execute(solution, input_data):

        if solution == "optimized solution":
            return "6", None

        if solution == "oracle solution":
            return "6", None

    with patch(
        "backend.services.stress_test_runner.execute_solution",
        side_effect=mock_execute
    ) as mocked:

        report = run_stress_tests(
            question,
            stress_cases
        )

    assert report["is_valid"] is True
    assert report["passed"] == 1
    assert report["oracle_comparisons"] == 1
    assert report["optimized_only_tests"] == 0

    assert mocked.call_count == 2

    print("PASS: Small input oracle comparison")


# =========================================================
# TEST 2: LARGE INPUT ORACLE SKIPPED
# =========================================================

def test_large_input_oracle_skipped():

    question = create_question()

    stress_cases = [
        {
            "input": "100000\n...",
            "category": "maximum_size",
            "oracle_check": False
        }
    ]

    def mock_execute(solution, input_data):

        assert solution == "optimized solution"

        return "100", None

    with patch(
        "backend.services.stress_test_runner.execute_solution",
        side_effect=mock_execute
    ) as mocked:

        report = run_stress_tests(
            question,
            stress_cases
        )

    assert report["is_valid"] is True
    assert report["passed"] == 1
    assert report["oracle_comparisons"] == 0
    assert report["optimized_only_tests"] == 1

    assert mocked.call_count == 1

    print("PASS: Large input oracle skipped")


# =========================================================
# TEST 3: OUTPUT MISMATCH DETECTED
# =========================================================

def test_output_mismatch():

    question = create_question()

    stress_cases = [
        {
            "input": "3\n1 2 3",
            "category": "small_array",
            "oracle_check": True
        }
    ]

    def mock_execute(solution, input_data):

        if solution == "optimized solution":
            return "6", None

        return "5", None

    with tempfile.TemporaryDirectory() as temp_dir:

        failure_file = Path(temp_dir) / "failure.json"

        with patch(
            "backend.services.stress_test_runner.execute_solution",
            side_effect=mock_execute
        ):

            report = run_stress_tests(
                question,
                stress_cases,
                failure_file=str(failure_file)
            )

        assert report["is_valid"] is False
        assert report["failed"] == 1

        assert failure_file.exists()

        with failure_file.open(
            "r",
            encoding="utf-8"
        ) as file:

            failure = json.load(file)

        assert failure["input"] == "3\n1 2 3"

        assert (
            failure["result"]["optimized_output"] == "6"
        )

        assert (
            failure["result"]["oracle_output"] == "5"
        )

    print("PASS: Output mismatch detected and saved")


# =========================================================
# TEST 4: OPTIMIZED SOLUTION ERROR
# =========================================================

def test_optimized_solution_error():

    question = create_question()

    stress_cases = [
        {
            "input": "100000\n...",
            "category": "maximum_size",
            "oracle_check": False
        }
    ]

    def mock_execute(solution, input_data):

        return None, "Execution timeout"

    with tempfile.TemporaryDirectory() as temp_dir:

        failure_file = Path(temp_dir) / "timeout.json"

        with patch(
            "backend.services.stress_test_runner.execute_solution",
            side_effect=mock_execute
        ):

            report = run_stress_tests(
                question,
                stress_cases,
                failure_file=str(failure_file)
            )

        assert report["is_valid"] is False
        assert report["failed"] == 1

        assert failure_file.exists()

        with failure_file.open(
            "r",
            encoding="utf-8"
        ) as file:

            failure = json.load(file)

        assert (
            failure["result"]["optimized_error"]
            == "Execution timeout"
        )

    print("PASS: Optimized execution error detected")


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    tests = [
        test_oracle_comparison,
        test_large_input_oracle_skipped,
        test_output_mismatch,
        test_optimized_solution_error
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

        print("\nALL STRESS RUNNER TESTS PASSED!")

    else:

        print("\nSOME TESTS FAILED!")