from backend.agents.question_generator import generate_dsa_question

if __name__ == "__main__":

    result = generate_dsa_question(
        topics=["Array", "Hash Table"],
        difficulty="Medium"
    )

    print("\n========== GENERATED QUESTION ==========\n")

    print("Title:", result["title"])
    print("Difficulty:", result["difficulty"])
    print("Topics:", result["topics"])

    print("\nDescription:\n")
    print(result["description"])

    print("\nExamples:\n")
    for example in result["examples"]:
        print(example)

    print("\nTest Cases:")
    for test in result["test_cases"]:
        print(test)

    print("\nReference Solution:\n")
    print(result["reference_solution"])

    print("\nComplexity:")
    print("Time:", result["time_complexity"])
    print("Space:", result["space_complexity"])