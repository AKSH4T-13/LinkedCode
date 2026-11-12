import json

from backend.agents.question_generator import generate_dsa_question

from backend.services.solution_validator import (
    execute_solution,
    validate_solution
)


# =========================================================
# HELPER: SAVE QUESTION
# =========================================================

def save_question(question, filename):

    with open(filename, "w", encoding="utf-8") as file:

        json.dump(
            question,
            file,
            indent=4
        )

    print(f"\nQuestion saved to {filename}")


# =========================================================
# HELPER: DISPLAY VALIDATION REPORT
# =========================================================

def display_validation_report(report, title):

    print(f"\n========== {title} ==========")

    print("Total Tests:", report["total_tests"])
    print("Passed:", report["passed"])
    print("Failed:", report["failed"])
    print("Valid:", report["is_valid"])

    print("\n========== STAGE SUMMARY ==========")

    for stage, count in report["stage_summary"].items():

        print(f"{stage}: {count}")

    print("\n========== FAILED TEST DETAILS ==========")

    failed_results = [
        result
        for result in report["results"]
        if not result["passed"]
    ]

    if not failed_results:

        print("No failed tests. All validation stages passed.")

    else:

        for index, result in enumerate(
            failed_results,
            start=1
        ):

            print(f"\n========== FAILURE {index} ==========")

            print("Stage:", result.get("stage"))
            print("Test Case:", result.get("test_case"))
            print("Case Type:", result.get("case_type"))

            print("Expected:", result.get("expected_output"))
            print("Oracle:", result.get("oracle_output"))
            print("Optimized:", result.get("optimized_output"))
            print("Brute Force:", result.get("brute_output"))
            print("Actual:", result.get("actual_output"))

            print("Error:", result.get("error"))
            print("Oracle Error:", result.get("oracle_error"))
            print("Optimized Error:", result.get("optimized_error"))
            print("Brute Force Error:", result.get("brute_error"))

            print("-" * 50)


# =========================================================
# HELPER: DISPLAY SOLUTIONS
# =========================================================

def display_solutions(question):

    print("\n========== OPTIMIZED SOLUTION ==========")
    print(question["reference_solution"])

    print("\n========== BRUTE FORCE SOLUTION ==========")
    print(question["brute_force_solution"])

    print("\n========== INDEPENDENT ORACLE ==========")
    print(
        question["verification_approach"]["independent_oracle"]
    )


# =========================================================
# HELPER: INDIVIDUAL SOLUTION TESTING
# =========================================================

def test_all_solutions(question):

    solutions = {
        "Optimized": question["reference_solution"],
        "Brute Force": question["brute_force_solution"],
        "Oracle": question["verification_approach"]["independent_oracle"]
    }

    all_cases = (
        question["examples"]
        + question["test_cases"]
        + question["verification_test_cases"]
    )

    print("\n========== INDIVIDUAL SOLUTION TESTING ==========")

    for index, case in enumerate(all_cases, start=1):

        print(f"\n========== TEST {index} ==========")

        print("Input:", repr(case["input"]))
        print("Expected:", repr(case["expected_output"]))

        for name, solution in solutions.items():

            actual, error = execute_solution(
                solution,
                case["input"]
            )

            print(f"\n{name} Output:", repr(actual))
            print(f"{name} Error:", error)

            if error is None:

                result = (
                    actual.strip()
                    == case["expected_output"].strip()
                )

                print(
                    f"{name} Result:",
                    "PASS" if result else "FAIL"
                )

        print("-" * 50)


# =========================================================
# STEP 1: GENERATE QUESTION
# =========================================================

print("\n========== QUESTION GENERATION ==========")

question = None

try:

    question = generate_dsa_question(
        topics=["Array", "Binary Search"],
        difficulty="Hard"
    )

except Exception as error:

    print("\n========== GENERATION FAILED ==========")

    print("Error:", error)

    print(
        "\nCheck the debug output from question_generator.py "
        "for the generated solutions."
    )

    raise


# =========================================================
# STEP 2: SAVE GENERATED QUESTION
# =========================================================

save_question(
    question,
    "generated_question_debug.json"
)


# =========================================================
# STEP 3: DISPLAY PROBLEM DESCRIPTION
# =========================================================

print("\n========== PROBLEM DESCRIPTION ==========")

print(question["description"])


# =========================================================
# STEP 4: DISPLAY ORACLE ALGORITHM
# =========================================================

print("\n========== ORACLE ALGORITHM ==========")

print(
    question["verification_approach"]["algorithm"]
)


# =========================================================
# STEP 5: DISPLAY ALL THREE SOLUTIONS
# =========================================================

display_solutions(question)


# =========================================================
# STEP 6: INDIVIDUAL SOLUTION TESTING
# =========================================================

test_all_solutions(question)


# =========================================================
# STEP 7: FULL VALIDATION
# =========================================================

print("\n\n========== INITIAL FULL VALIDATION ==========")

report = validate_solution(question)


# =========================================================
# STEP 8: DISPLAY VALIDATION REPORT
# =========================================================

display_validation_report(
    report,
    "INITIAL VALIDATION REPORT"
)


# =========================================================
# STEP 9: FINAL VALIDATION STATUS
# =========================================================

print("\n========== FINAL STATUS ==========")

if report["is_valid"]:

    print("SUCCESS: Question passed all validation stages.")

else:

    print("FAILED: Question requires further investigation.")


print("\nGenerated Question:", question["title"])

print(
    "Final Validation:",
    "PASSED" if report["is_valid"] else "FAILED"
)

print("\nTesting completed.")