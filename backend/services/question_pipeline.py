from backend.agents.question_generator import generate_dsa_question
from backend.agents.question_refiner import refine_question
from backend.services.solution_validator import validate_solution


def generate_valid_question(topics, difficulty="Medium", max_attempts=3, user_profile=None):

    question = generate_dsa_question(topics, difficulty, **({"user_profile": user_profile} if user_profile is not None else {}))

    for attempt in range(1, max_attempts + 1):

        print(f"\nValidation attempt: {attempt}")

        report = validate_solution(question)

        print(
            f"Passed: {report['passed']}/{report['total_tests']}"
        )

        if report["is_valid"]:

            return {
                "status": "success",
                "attempts": attempt,
                "question": question,
                "validation": report
            }

        if attempt == max_attempts:
            break

        print("\nQuestion failed. Sending feedback to Groq...")

        question = refine_question(question, report)

    return {
        "status": "failed",
        "attempts": max_attempts,
        "message": "Unable to generate a valid question.",
        "last_validation": report
    }
