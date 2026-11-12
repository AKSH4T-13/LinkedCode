from backend.agents.question_generator import generate_dsa_question
from backend.services.solution_validator import validate_solution


def main():

    question = generate_dsa_question(
        topics=["Array", "Hash Table"],
        difficulty="Medium"
    )

    print("\nGenerated:", question["title"])

    result = validate_solution(question)

    print("\n========== VALIDATION REPORT ==========")

    print("Total Tests:", result["total_tests"])
    print("Passed:", result["passed"])
    print("Failed:", result["failed"])
    print("Valid:", result["is_valid"])

    for test in result["results"]:

        if not test["passed"]:
            print("\nFAILED:", test)


if __name__ == "__main__":
    main()