import asyncio

from backend.services.candidate_service import (
    get_problem_catalogue,
    get_unsolved_candidates
)


async def main():

    catalogue = await get_problem_catalogue()

    print("\nTotal problems:", len(catalogue))

    # Temporary test profile
    user_profile = {
        "analyzed_questions": [
            {
                "title_slug": "two-sum"
            },
            {
                "title_slug": "valid-parentheses"
            }
        ],
        "topic_frequency": {
            "Array": 8,
            "Tree": 7,
            "Hash Table": 3
        }
    }

    candidates = get_unsolved_candidates(
        user_profile,
        catalogue,
        max_candidates=100
    )

    print("\nUnsolved candidates:", len(candidates))

    print("\nTop 10 recommendations candidates:\n")

    for question in candidates[:10]:
        print(
            question["title"],
            "|",
            question["difficulty"],
            "|",
            question["topics"]
        )


if __name__ == "__main__":
    asyncio.run(main())