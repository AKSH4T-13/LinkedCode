import asyncio

from backend.graph.workflow import linkedcode_graph


async def main():

    username = "Vansh1306"

    print("\n========== LINKEDCODE WORKFLOW ==========")

    initial_state = {
        "username": username,
        "errors": []
    }

    result = await linkedcode_graph.ainvoke(initial_state)

    print("\n========== FINAL RECOMMENDATIONS ==========")

    recommendations = result["final_recommendations"]

    existing = recommendations["existing_question"]
    generated = recommendations["generated_question"]

    print("\n--- EXISTING LEETCODE QUESTION ---")

    print("Title:", existing["title"])
    print("Difficulty:", existing["difficulty"])
    print("Topics:", existing["topics"])
    print("Reason:", existing["reason"])

    print("\n--- ORIGINAL GENERATED QUESTION ---")

    print("Title:", generated["title"])
    print("Difficulty:", generated["difficulty"])
    print("Topics:", generated["topics"])
    print("Description:", generated["description"])

    print("\n========== VALIDATION ==========")

    validation = result["validation_report"]

    print(
        f"Passed: {validation['passed']}/"
        f"{validation['total_tests']}"
    )

    print("\nWorkflow completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())