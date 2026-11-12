import json
import time
from pathlib import Path

from backend.services.solution_validator import execute_solution


# =========================================================
# CONFIGURATION
# =========================================================

ORACLE_MAX_SIZE = 2000


# =========================================================
# PERFORMANCE CONFIGURATION
# =========================================================

OPTIMIZED_MAX_RUNTIME = 3.0

ORACLE_MAX_RUNTIME = 5.0


# =========================================================
# EXECUTE AND MEASURE
# =========================================================

def execute_and_measure(solution, input_data):

    start_time = time.perf_counter()

    output, error = execute_solution(
        solution,
        input_data
    )

    execution_time = time.perf_counter() - start_time

    return {
        "output": output.strip() if output is not None else None,
        "error": error,
        "execution_time": round(execution_time, 4)
    }


# =========================================================
# SAVE FAILURE DETAILS
# =========================================================

def save_stress_failure(
    failure,
    filename="stress_test_failure.json"
):

    path = Path(filename)

    with path.open("w", encoding="utf-8") as file:

        json.dump(
            failure,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(f"\n[STRESS TEST] Failure saved to {path}")


# =========================================================
# STRESS TEST RUNNER
# =========================================================

def run_stress_tests(
    question,
    stress_cases,
    failure_file="stress_test_failure.json"
):

    optimized_solution = question["reference_solution"]

    oracle_solution = (
        question.get("verification_approach", {}).get("independent_oracle")
    )

    if any(case.get("oracle_check", True) for case in stress_cases):
        if not isinstance(oracle_solution, str) or not oracle_solution.strip():
            raise ValueError(
                "Oracle solution is required when oracle_check is enabled."
            )

    report = {
        "total_tests": len(stress_cases),
        "passed": 0,
        "failed": 0,
        "oracle_comparisons": 0,
        "optimized_only_tests": 0,
        "performance_failures": 0,
        "oracle_performance_failures": 0,
        "average_optimized_time": 0,
        "max_optimized_time": 0,
        "average_oracle_time": 0,
        "max_oracle_time": 0,
        "results": [],
        "is_valid": False
    }

    optimized_times = []
    oracle_times = []

    print("\n========== STRESS TESTING ==========")

    for index, case in enumerate(stress_cases, start=1):

        print(
            f"\n[STRESS TEST] Running "
            f"{index}/{len(stress_cases)}"
        )

        input_data = case["input"]

        category = case.get(
            "category",
            "custom"
        )

        oracle_check = case.get(
            "oracle_check",
            True
        )

        # -------------------------------------------------
        # RUN OPTIMIZED SOLUTION
        # -------------------------------------------------

        optimized_result = execute_and_measure(
            optimized_solution,
            input_data
        )

        optimized_times.append(
            optimized_result["execution_time"]
        )

        optimized_performance_ok = (
            optimized_result["error"] is None
            and optimized_result["execution_time"]
            <= OPTIMIZED_MAX_RUNTIME
        )

        if not optimized_performance_ok:

            report["performance_failures"] += 1

        oracle_result = None

        # -------------------------------------------------
        # RUN ORACLE ONLY WHEN REQUIRED
        # -------------------------------------------------

        if oracle_check:

            report["oracle_comparisons"] += 1

            oracle_result = execute_and_measure(
                oracle_solution,
                input_data
            )

            oracle_times.append(
                oracle_result["execution_time"]
            )

            oracle_performance_ok = (
                oracle_result["error"] is None
                and oracle_result["execution_time"]
                <= ORACLE_MAX_RUNTIME
            )

            if not oracle_performance_ok:

                report["oracle_performance_failures"] += 1

            passed = (
                optimized_performance_ok
                and oracle_performance_ok
                and optimized_result["output"]
                == oracle_result["output"]
            )

        else:

            report["optimized_only_tests"] += 1

            passed = optimized_performance_ok

        # -------------------------------------------------
        # BUILD RESULT
        # -------------------------------------------------

        result = {
            "test_case": index,
            "category": category,
            "oracle_checked": oracle_check,
            "passed": passed,

            "optimized_output": optimized_result["output"],
            "optimized_error": optimized_result["error"],
            "optimized_time": optimized_result["execution_time"],
            "optimized_performance_ok": optimized_performance_ok,

            "oracle_output": (
                oracle_result["output"]
                if oracle_result else None
            ),

            "oracle_error": (
                oracle_result["error"]
                if oracle_result else None
            ),

            "oracle_time": (
                oracle_result["execution_time"]
                if oracle_result else None
            ),

            "oracle_performance_ok": (
                oracle_performance_ok
                if oracle_result else None
            )
        }

        report["results"].append(result)

        # -------------------------------------------------
        # HANDLE FAILURE
        # -------------------------------------------------

        if not passed:

            report["failed"] += 1

            print("Result: FAIL")

            if not optimized_performance_ok:

                print(
                    "[STRESS TEST] Optimized solution "
                    "exceeded runtime limit or failed."
                )

            if oracle_result and not oracle_performance_ok:

                print(
                    "[STRESS TEST] Oracle exceeded runtime "
                    "limit or failed."
                )

            if (
                oracle_result
                and optimized_result["error"] is None
                and oracle_result["error"] is None
                and optimized_result["output"]
                != oracle_result["output"]
            ):

                print("[STRESS TEST] Output mismatch detected.")

            save_stress_failure(
                {
                    "test_case": index,
                    "category": category,
                    "input": input_data,
                    "result": result
                },
                failure_file
            )

            print("[STRESS TEST] Stopping after first failure.")

            break

        # -------------------------------------------------
        # HANDLE SUCCESS
        # -------------------------------------------------

        report["passed"] += 1

        print("Result: PASS")

        print(
            "Optimized Time:",
            optimized_result["execution_time"],
            "seconds"
        )

        if oracle_result:

            print(
                "Oracle Time:",
                oracle_result["execution_time"],
                "seconds"
            )

    # =====================================================
    # PERFORMANCE SUMMARY
    # =====================================================

    if optimized_times:

        report["average_optimized_time"] = round(
            sum(optimized_times) / len(optimized_times),
            4
        )

        report["max_optimized_time"] = round(
            max(optimized_times),
            4
        )

    if oracle_times:

        report["average_oracle_time"] = round(
            sum(oracle_times) / len(oracle_times),
            4
        )

        report["max_oracle_time"] = round(
            max(oracle_times),
            4
        )

    # =====================================================
    # FINAL VALIDATION STATUS
    # =====================================================

    report["is_valid"] = (
        report["failed"] == 0
        and report["passed"] == report["total_tests"]
    )

    # =====================================================
    # FINAL REPORT
    # =====================================================

    print("\n========== STRESS TEST REPORT ==========")

    print("Total:", report["total_tests"])
    print("Passed:", report["passed"])
    print("Failed:", report["failed"])

    print(
        "Oracle Comparisons:",
        report["oracle_comparisons"]
    )

    print(
        "Optimized Only:",
        report["optimized_only_tests"]
    )

    print(
        "Performance Failures:",
        report["performance_failures"]
    )

    print(
        "Oracle Performance Failures:",
        report["oracle_performance_failures"]
    )

    print("\n========== PERFORMANCE SUMMARY ==========")

    print(
        "Average Optimized Time:",
        report["average_optimized_time"],
        "seconds"
    )

    print(
        "Maximum Optimized Time:",
        report["max_optimized_time"],
        "seconds"
    )

    print(
        "Average Oracle Time:",
        report["average_oracle_time"],
        "seconds"
    )

    print(
        "Maximum Oracle Time:",
        report["max_oracle_time"],
        "seconds"
    )

    print("\nValid:", report["is_valid"])

    return report