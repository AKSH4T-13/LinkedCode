from unittest.mock import patch
from langchain_core.messages import AIMessage

import backend.agents.question_generator as qg


# ==========================================
# FAKE GROQ CLIENT
# ==========================================

class FakeGroq:

    def __init__(self, responses):
        self.responses = iter(responses)
        self.call_count = 0

    def invoke(self, prompt, **kwargs):
        self.call_count += 1

        result = next(self.responses)

        if isinstance(result, Exception):
            raise result

        return result


class FakeRateLimitError(Exception):
    status_code = 429


class FakeRequestTooLargeError(Exception):
    status_code = 413


success_response = AIMessage(
    content='{"status": "PASS"}',
    response_metadata={},
    usage_metadata={
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15
    }
)


# ==========================================
# TEST 1: TPM RETRY
# ==========================================

print("\n========== TEST 1: TPM RETRY ==========")

fake_client = FakeGroq([
    FakeRateLimitError(
        "Rate limit reached. Please try again in 0.01s"
    ),
    success_response
])

with patch.object(qg, "generator_llm", fake_client):

    with patch.object(qg.time, "sleep") as mock_sleep:

        result = qg.generate_phase_json(
            "Test prompt",
            "TPM Test"
        )

        assert result == {"status": "PASS"}
        assert fake_client.call_count == 2
        mock_sleep.assert_called_once()

print("PASS: 429 retry successful.")


# ==========================================
# TEST 2: REQUEST TOO LARGE
# ==========================================

print("\n========== TEST 2: REQUEST TOO LARGE ==========")

fake_client = FakeGroq([
    FakeRequestTooLargeError("Request too large")
])

with patch.object(qg, "generator_llm", fake_client):

    try:

        qg.generate_phase_json(
            "Test prompt",
            "413 Test"
        )

        raise AssertionError("Expected RuntimeError")

    except RuntimeError as error:

        assert "Request too large" in str(error)
        assert fake_client.call_count == 1

print("PASS: 413 handled without unnecessary retries.")


# ==========================================
# FINAL RESULT
# ==========================================

print("\nALL TPM TESTS PASSED!")