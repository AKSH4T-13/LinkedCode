import subprocess
import sys
import tempfile
import os


# =========================================================
# EXECUTE PYTHON SOLUTION
# =========================================================

def execute_solution(solution, input_data):

    solution_path = None

    try:

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8"
        ) as file:

            file.write(solution)
            solution_path = file.name

        process = subprocess.run(
            [sys.executable, solution_path],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=5
        )

        if process.returncode != 0:

            return None, process.stderr.strip()

        return process.stdout.strip(), None

    except subprocess.TimeoutExpired:

        return None, "Execution timed out"

    except Exception as e:

        return None, str(e)

    finally:

        if solution_path and os.path.exists(solution_path):

            os.remove(solution_path)


# =========================================================
# VERIFY EXAMPLES
# =========================================================

def verify_examples(question):

    optimized = question["reference_solution"]
    examples = question.get("examples", [])

    results = []

    for index, example in enumerate(examples, start=1):

        actual_output, error = execute_solution(
            optimized,
            example["input"]
        )

        expected_output = example["output"].strip()

        passed = (
            error is None
            and actual_output == expected_output
        )

        results.append({
            "test_case": index,
            "passed": passed,
            "expected_output": expected_output,
            "actual_output": actual_output,
            "error": error
        })

    total = len(results)

    passed_count = sum(
        result["passed"]
        for result in results
    )

    return {
        "total_examples": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "is_valid": (
            total > 0
            and passed_count == total
        ),
        "results": results
    }


# =========================================================
# MAIN SOLUTION VALIDATOR
# =========================================================

def validate_solution(question):

    optimized = question["reference_solution"]
    brute_force = question["brute_force_solution"]

    test_cases = question.get("test_cases", [])

    verification_cases = question.get(
        "verification_test_cases", []
    )

    verification_approach = question.get(
        "verification_approach", {}
    )

    oracle = verification_approach.get(
        "independent_oracle"
    )

    results = []

    # =====================================================
    # STAGE 1: EXAMPLE VERIFICATION
    # =====================================================

    print("\n[VALIDATOR] Stage 1: Example Verification")

    example_report = verify_examples(question)

    for result in example_report["results"]:

        results.append({
            "test_case": result["test_case"],
            "stage": "Example Verification",
            "passed": result["passed"],
            "expected_output": result["expected_output"],
            "actual_output": result["actual_output"],
            "error": result["error"]
        })

    # =====================================================
    # STAGE 2: BRUTE FORCE EXECUTION
    # =====================================================

    print("\n[VALIDATOR] Stage 2: Brute Force Execution")

    canonical_outputs = []

    for index, test in enumerate(test_cases, start=1):

        brute_output, error = execute_solution(
            brute_force,
            test["input"]
        )

        if error:

            results.append({
                "test_case": index,
                "stage": "Brute Force Execution",
                "passed": False,
                "error": error
            })

            canonical_outputs.append(None)

            continue

        canonical_outputs.append(brute_output)

        results.append({
            "test_case": index,
            "stage": "Brute Force Execution",
            "passed": True,
            "canonical_output": brute_output
        })

    # =====================================================
    # STAGE 3: OPTIMIZED SOLUTION VERIFICATION
    # =====================================================

    print("\n[VALIDATOR] Stage 3: Optimized Solution Verification")

    for index, test in enumerate(test_cases, start=1):

        canonical_output = canonical_outputs[index - 1]

        if canonical_output is None:

            results.append({
                "test_case": index,
                "stage": "Optimized Solution Verification",
                "passed": False,
                "expected_output": None,
                "actual_output": None,
                "error": "Skipped because brute-force execution failed."
            })

            continue

        optimized_output, error = execute_solution(
            optimized,
            test["input"]
        )

        passed = (
            error is None
            and optimized_output == canonical_output
        )

        results.append({
            "test_case": index,
            "stage": "Optimized Solution Verification",
            "passed": passed,
            "expected_output": canonical_output,
            "actual_output": optimized_output,
            "error": error
        })

    # =====================================================
    # STAGE 4: DIFFERENTIAL TESTING
    # =====================================================

    print("\n[VALIDATOR] Stage 4: Differential Testing")

    for index, test in enumerate(
        verification_cases,
        start=1
    ):

        optimized_output, optimized_error = execute_solution(
            optimized,
            test["input"]
        )

        brute_output, brute_error = execute_solution(
            brute_force,
            test["input"]
        )

        passed = (
            optimized_error is None
            and brute_error is None
            and optimized_output == brute_output
        )

        results.append({
            "test_case": index,
            "stage": "Differential Testing",
            "passed": passed,
            "optimized_output": optimized_output,
            "brute_output": brute_output,
            "optimized_error": optimized_error,
            "brute_error": brute_error
        })

    # =====================================================
    # STAGE 5: INDEPENDENT ORACLE VERIFICATION
    # =====================================================

    print("\n[VALIDATOR] Stage 5: Independent Oracle Verification")

    oracle_cases = []

    # -----------------------------------------------------
    # INCLUDE EXAMPLES
    # -----------------------------------------------------

    for index, example in enumerate(
        question.get("examples", []),
        start=1
    ):

        oracle_cases.append({
            "case_type": "Example",
            "test_case": index,
            "input": example["input"],
            "expected_output": example["output"].strip()
        })

    # -----------------------------------------------------
    # INCLUDE NORMAL TEST CASES
    # -----------------------------------------------------

    for index, test in enumerate(
        test_cases,
        start=1
    ):

        oracle_cases.append({
            "case_type": "Normal",
            "test_case": index,
            "input": test["input"],
            "expected_output": test["expected_output"].strip()
        })

    # -----------------------------------------------------
    # INCLUDE VERIFICATION TEST CASES
    # -----------------------------------------------------

    for index, test in enumerate(
        verification_cases,
        start=1
    ):

        oracle_cases.append({
            "case_type": "Verification",
            "test_case": index,
            "input": test["input"],
            "expected_output": test["expected_output"].strip()
        })

    # -----------------------------------------------------
    # CHECK ORACLE AVAILABILITY
    # -----------------------------------------------------

    if not oracle:

        print("[VALIDATOR] Independent oracle is missing.")

        results.append({
            "stage": "Independent Oracle Verification",
            "passed": False,
            "error": "Independent oracle is missing."
        })

    else:

        for test in oracle_cases:

            oracle_output, oracle_error = execute_solution(
                oracle,
                test["input"]
            )

            optimized_output, optimized_error = execute_solution(
                optimized,
                test["input"]
            )

            brute_output, brute_error = execute_solution(
                brute_force,
                test["input"]
            )

            expected_output = test["expected_output"]

            # ---------------------------------------------
            # ORACLE VS EXPECTED OUTPUT
            # ---------------------------------------------

            oracle_matches_expected = (
                oracle_error is None
                and oracle_output == expected_output
            )

            # ---------------------------------------------
            # OPTIMIZED VS ORACLE
            # ---------------------------------------------

            optimized_matches_oracle = (
                oracle_error is None
                and optimized_error is None
                and optimized_output == oracle_output
            )

            # ---------------------------------------------
            # BRUTE FORCE VS ORACLE
            # ---------------------------------------------

            brute_matches_oracle = (
                oracle_error is None
                and brute_error is None
                and brute_output == oracle_output
            )

            # ---------------------------------------------
            # FINAL RESULT
            # ---------------------------------------------

            passed = (
                oracle_matches_expected
                and optimized_matches_oracle
                and brute_matches_oracle
            )

            results.append({
                "test_case": test["test_case"],
                "case_type": test["case_type"],
                "stage": "Independent Oracle Verification",
                "passed": passed,

                "expected_output": expected_output,

                "oracle_output": oracle_output,
                "optimized_output": optimized_output,
                "brute_output": brute_output,

                "oracle_matches_expected": oracle_matches_expected,
                "optimized_matches_oracle": optimized_matches_oracle,
                "brute_matches_oracle": brute_matches_oracle,

                "oracle_error": oracle_error,
                "optimized_error": optimized_error,
                "brute_error": brute_error
            })

    # =====================================================
    # FINAL VALIDATION REPORT
    # =====================================================

    total = len(results)

    passed_count = sum(
        result["passed"]
        for result in results
    )

    failed_count = total - passed_count

    return {
        "total_tests": total,
        "passed": passed_count,
        "failed": failed_count,

        "example_validation": example_report,

        "stage_summary": {
            "examples": len(example_report["results"]),
            "normal_test_cases": len(test_cases),
            "verification_test_cases": len(verification_cases),
            "oracle_test_cases": len(oracle_cases)
        },

        "is_valid": (
            total > 0
            and passed_count == total
            and example_report["is_valid"]
        ),

        "results": results
    }