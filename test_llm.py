import time
from backend.llm.groq_client import groq_llm


def test_groq():

    start_time = time.perf_counter()

    try:
        response = groq_llm.invoke(
            "Reply with only: Groq working"
        )

        end_time = time.perf_counter()

        print("\nResponse:", response.content)
        print(f"Execution Time: {end_time - start_time:.2f} seconds")

    except Exception as e:
        print("Groq Error:", str(e))


if __name__ == "__main__":
    test_groq()