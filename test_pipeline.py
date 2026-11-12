def main():

    result = generate_valid_question(
        topics=["Array", "Hash Table"],
        difficulty="Medium",
        max_attempts=3
    )

    print("\n========== FINAL RESULT ==========")

    print("Status:", result["status"])
    print("Attempts:", result["attempts"])

    if result["status"] == "success":

        question = result["question"]

        print("Title:", question["title"])
        print("Difficulty:", question["difficulty"])
        print("Topics:", question["topics"])
        print("Description:", question["description"])

        print("\n========== GENERATED QUESTION ==========")
        print("TITLE:", question["title"])
        print("DESCRIPTION:", question["description"])
        print("CONSTRAINTS:", question["constraints"])

        print("\n========== OPTIMIZED SOLUTION ==========")
        print(question["reference_solution"])

        print("\n========== BRUTE FORCE SOLUTION ==========")
        print(question["brute_force_solution"])

        print("\n========== TEST CASES ==========")
        print(question["test_cases"])

        print("\n========== VERIFICATION CASES ==========")
        print(question["verification_test_cases"])

    else:
        print(result["message"])
        print(result["last_validation"])


if __name__ == "__main__":
    main()