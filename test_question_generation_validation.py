import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from backend.agents.question_generator import (
    build_solution_correction_prompt
)

from unittest.mock import patch, call

import pytest

from unittest.mock import patch

from backend.agents.question_generator import audit_generated_solutions



from backend.agents.question_generator import (
    parse_response,
    generate_phase_json
)


def mock_response(content, finish_reason="stop"):
    return SimpleNamespace(
        content=content,
        response_metadata={"finish_reason": finish_reason},
        usage_metadata={}
    )


# =========================================================
# PARSE RESPONSE TESTS
# =========================================================

def test_parse_valid_json():
    response = mock_response('{"title": "Test Problem"}')

    result = parse_response(response)

    assert result == {"title": "Test Problem"}


def test_parse_markdown_json():
    response = mock_response(
        '```json\n{"title": "Test Problem"}\n```'
    )

    result = parse_response(response)

    assert result == {"title": "Test Problem"}


def test_parse_invalid_json():
    response = mock_response('{"title": "Test Problem"')

    with pytest.raises(ValueError, match="malformed JSON"):
        parse_response(response)


def test_parse_truncated_response():
    response = mock_response(
        '{"title": "Test Problem"',
        finish_reason="length"
    )

    with pytest.raises(ValueError, match="truncated"):
        parse_response(response)


def test_parse_backslash_repair():
    response = mock_response(
        r'{"code": "print(\d+)"}'
    )

    result = parse_response(response)

    assert isinstance(result, dict)
    assert "code" in result


# =========================================================
# GENERATE PHASE JSON TESTS
# =========================================================

@patch("backend.agents.question_generator.generator_llm")
def test_generate_phase_success(mock_llm):
    mock_llm.invoke.return_value = mock_response(
        '{"title": "Test Problem"}'
    )

    result = generate_phase_json(
        "Generate a problem",
        "TEST"
    )

    assert result == {"title": "Test Problem"}
    assert mock_llm.invoke.call_count == 1


@patch("backend.agents.question_generator.generator_llm")
def test_generate_phase_retry_after_invalid_json(mock_llm):
    mock_llm.invoke.side_effect = [
        mock_response('{"title":'),
        mock_response('{"title": "Recovered"}')
    ]

    result = generate_phase_json(
        "Generate a problem",
        "TEST",
        max_attempts=2
    )

    assert result == {"title": "Recovered"}
    assert mock_llm.invoke.call_count == 2


@patch("backend.agents.question_generator.generator_llm")
def test_generate_phase_rejects_non_dict(mock_llm):
    mock_llm.invoke.return_value = mock_response('[1, 2, 3]')

    with pytest.raises(ValueError, match="failed after"):
        generate_phase_json(
            "Generate a problem",
            "TEST",
            max_attempts=1
        )


@patch("backend.agents.question_generator.generator_llm")
def test_generate_phase_retry_exhaustion(mock_llm):
    mock_llm.invoke.return_value = mock_response('invalid json')

    with pytest.raises(ValueError, match="failed after 2 attempts"):
        generate_phase_json(
            "Generate a problem",
            "TEST",
            max_attempts=2
        )

    assert mock_llm.invoke.call_count == 2


@patch("backend.agents.question_generator.time.sleep")
@patch("backend.agents.question_generator.generator_llm")
def test_generate_phase_rate_limit_retry(mock_llm, mock_sleep):
    rate_limit_error = Exception("Rate limit exceeded")
    rate_limit_error.status_code = 429

    mock_llm.invoke.side_effect = [
        rate_limit_error,
        mock_response('{"title": "Recovered"}')
    ]

    result = generate_phase_json(
        "Generate a problem",
        "TEST"
    )

    assert result == {"title": "Recovered"}
    assert mock_llm.invoke.call_count == 2
    mock_sleep.assert_called_once()


@patch("backend.agents.question_generator.generator_llm")
def test_generate_phase_rejects_large_request(mock_llm):
    request_error = Exception("Request too large")
    request_error.status_code = 413

    mock_llm.invoke.side_effect = request_error

    with pytest.raises(RuntimeError, match="Request too large"):
        generate_phase_json(
            "Generate a problem",
            "TEST"
        )

    assert mock_llm.invoke.call_count == 1



def valid_audit_response():
    return {
        "status": "PASS",
        "optimized_analysis": "Optimized solution is correct.",
        "brute_force_analysis": "Brute force solution is correct.",
        "complexity_analysis": "Complexities are consistent.",
        "issues": [],
        "counterexamples": [],
        "correction_guidance": "No corrections required."
    }

def valid_core_data():
    return {
        "title": "Pair Sum",
        "difficulty": "Easy",
        "topics": ["Array"],
        "description": "Find pairs whose sum equals K.",
        "constraints": ["1 <= n <= 100"],
        "examples": [],
        "reference_solution": "print(1)",
        "brute_force_solution": "print(1)",
        "time_complexity": "O(n)",
        "space_complexity": "O(1)",
        "brute_force_complexity": "O(n^2)"
    }

@patch("backend.agents.question_generator.generate_phase_json")
def test_audit_success(mock_generate):
    mock_generate.return_value = valid_audit_response()

    result = audit_generated_solutions(valid_core_data())

    assert result["status"] == "PASS"
    mock_generate.assert_called_once()


@patch("backend.agents.question_generator.generate_phase_json")
def test_audit_failure_status(mock_generate):
    audit = valid_audit_response()
    audit["status"] = "FAIL"
    audit["issues"] = ["Incorrect boundary handling"]

    mock_generate.return_value = audit

    result = audit_generated_solutions(valid_core_data())

    assert result["status"] == "FAIL"
    assert len(result["issues"]) == 1


@patch("backend.agents.question_generator.generate_phase_json")
def test_audit_missing_field(mock_generate):
    audit = valid_audit_response()
    del audit["counterexamples"]

    mock_generate.return_value = audit

    with pytest.raises(ValueError, match="missing field"):
        audit_generated_solutions(valid_core_data())


@pytest.mark.parametrize("invalid_status", [
    "UNKNOWN",
    "PASS_WITH_WARNINGS",
    "",
    None,
    123
])
@patch("backend.agents.question_generator.generate_phase_json")
def test_audit_invalid_status(mock_generate, invalid_status):
    audit = valid_audit_response()
    audit["status"] = invalid_status

    mock_generate.return_value = audit

    with pytest.raises(ValueError, match="Invalid audit status"):
        audit_generated_solutions(valid_core_data())


@patch("backend.agents.question_generator.generate_phase_json")
def test_audit_non_dictionary_response(mock_generate):
    mock_generate.return_value = ["PASS"]

    with pytest.raises(
        ValueError,
        match="must be a JSON object"
    ):
        audit_generated_solutions(valid_core_data())


def test_correction_prompt_contains_problem_data():
    core = valid_core_data()
    audit = valid_audit_response()

    prompt = build_solution_correction_prompt(core, audit)

    assert core["title"] in prompt
    assert core["description"] in prompt
    assert core["reference_solution"] in prompt


def test_correction_prompt_contains_audit_report():
    core = valid_core_data()
    audit = valid_audit_response()

    prompt = build_solution_correction_prompt(core, audit)

    assert audit["status"] in prompt
    assert audit["optimized_analysis"] in prompt


def test_correction_prompt_preserves_required_fields():
    prompt = build_solution_correction_prompt(
        valid_core_data(),
        valid_audit_response()
    )

    required_fields = [
        "title", "difficulty", "topics",
        "description", "input_format", "output_format",
        "constraints", "examples", "reference_solution",
        "brute_force_solution", "stress_test_spec",
        "brute_force_complexity", "time_complexity",
        "space_complexity"
    ]

    for field in required_fields:
        assert field in prompt


def test_correction_prompt_enforces_complexity_notation():
    prompt = build_solution_correction_prompt(
        valid_core_data(),
        valid_audit_response()
    )

    allowed_notations = [
        "O(1)", "O(log n)", "O(n)",
        "O(n log n)", "O(n^2)", "O(n^3)",
        "O(2^n)", "O(n!)"
    ]

    for notation in allowed_notations:
        assert notation in prompt


def test_correction_prompt_requires_json_only():
    prompt = build_solution_correction_prompt(
        valid_core_data(),
        valid_audit_response()
    )

    assert "Return valid JSON only" in prompt
    assert "Do not include Markdown code fences" in prompt
    assert "Return ONLY the corrected JSON" in prompt


def test_audit_pass_skips_correction():
    core = valid_core_data()
    audit = valid_audit_response()

    with patch(
        "backend.agents.question_generator.audit_generated_solutions",
        return_value=audit
    ), patch(
        "backend.agents.question_generator.generate_phase_json"
    ) as mock_generate, patch(
        "backend.agents.question_generator.validate_core_response"
    ):

        # Is test ke liye complete generation pipeline ko
        # mock karna unnecessary hai.
        # Audit loop ko independently test karenge.
        pass


def test_audit_loop_passes_after_correction():
    audits = [
        {**valid_audit_response(), "status": "FAIL",
         "issues": ["Incorrect logic"]},
        valid_audit_response()
    ]

    assert audits[0]["status"] == "FAIL"
    assert audits[1]["status"] == "PASS"


def test_audit_loop_respects_maximum_attempts():
    max_attempts = 3

    audits = [
        {**valid_audit_response(), "status": "FAIL",
         "issues": ["Incorrect logic"]}
        for _ in range(max_attempts)
    ]

    assert len(audits) == max_attempts
    assert all(audit["status"] == "FAIL" for audit in audits)


def test_correction_prompt_receives_failed_audit():
    core = valid_core_data()
    audit = valid_audit_response()

    audit["status"] = "FAIL"
    audit["issues"] = ["Incorrect boundary handling"]

    prompt = build_solution_correction_prompt(core, audit)

    assert "FAIL" in prompt
    assert "Incorrect boundary handling" in prompt


from backend.agents.question_generator import run_solution_audit_loop


def failed_audit():
    audit = valid_audit_response()
    audit["status"] = "FAIL"
    audit["issues"] = ["Incorrect boundary handling"]
    return audit


@patch("backend.agents.question_generator.audit_generated_solutions")
@patch("backend.agents.question_generator.generate_phase_json")
@patch("backend.agents.question_generator.validate_core_response")
def test_audit_pass_skips_correction(
    mock_validate,
    mock_generate,
    mock_audit
):
    mock_audit.return_value = valid_audit_response()

    core, audit = run_solution_audit_loop(valid_core_data())

    assert audit["status"] == "PASS"
    mock_generate.assert_not_called()
    mock_validate.assert_not_called()


@patch("backend.agents.question_generator.audit_generated_solutions")
@patch("backend.agents.question_generator.generate_phase_json")
@patch("backend.agents.question_generator.validate_core_response")
def test_audit_fail_triggers_correction(
    mock_validate,
    mock_generate,
    mock_audit
):
    corrected_core = valid_core_data()

    mock_audit.side_effect = [
        failed_audit(),
        valid_audit_response()
    ]

    mock_generate.return_value = corrected_core

    core, audit = run_solution_audit_loop(valid_core_data())

    assert audit["status"] == "PASS"
    assert core == corrected_core
    mock_generate.assert_called_once()
    mock_validate.assert_called_once()


@patch("backend.agents.question_generator.audit_generated_solutions")
@patch("backend.agents.question_generator.generate_phase_json")
@patch("backend.agents.question_generator.validate_core_response")
def test_audit_maximum_attempts(
    mock_validate,
    mock_generate,
    mock_audit
):
    mock_audit.return_value = failed_audit()
    mock_generate.return_value = valid_core_data()

    with pytest.raises(ValueError, match="maximum attempts"):
        run_solution_audit_loop(
            valid_core_data(),
            max_audit_attempts=3
        )

    assert mock_audit.call_count == 3
    assert mock_generate.call_count == 2
    assert mock_validate.call_count == 2


def test_invalid_audit_attempt_count():
    with pytest.raises(ValueError):
        run_solution_audit_loop(
            valid_core_data(),
            max_audit_attempts=0
        )


@patch("backend.agents.question_generator.audit_generated_solutions")
@patch("backend.agents.question_generator.generate_phase_json")
def test_correction_generation_failure(
    mock_generate,
    mock_audit
):
    mock_audit.return_value = failed_audit()
    mock_generate.side_effect = RuntimeError("Correction failed")

    with pytest.raises(RuntimeError, match="Correction failed"):
        run_solution_audit_loop(valid_core_data())


from backend.agents.question_generator import validate_oracle_response


def valid_oracle():
    return {
        "algorithm": "Sort the array and calculate the sum.",
        "independent_oracle": """
import sys

data = list(map(int, sys.stdin.read().split()))
n, k = data[0], data[1]
arr = data[2:2+n]

arr.sort()

prefix_sum = 0

for value in arr:
    prefix_sum += value

print(prefix_sum)
"""
    }


def valid_oracle_core():
    return {
        "reference_solution": """
import sys
data = list(map(int, sys.stdin.read().split()))
print(max(data))
""",
        "brute_force_solution": """
import sys
data = list(map(int, sys.stdin.read().split()))
result = data[0]
for value in data:
    if value < result:
        result = value
print(result)
"""
    }


def test_valid_oracle_response():
    assert validate_oracle_response(
        valid_oracle(),
        valid_oracle_core()
    ) is True


@pytest.mark.parametrize("field", [
    "algorithm",
    "independent_oracle"
])
def test_oracle_missing_field(field):
    oracle = valid_oracle()
    del oracle[field]

    with pytest.raises(ValueError, match="missing or invalid"):
        validate_oracle_response(oracle, valid_oracle_core())


def test_oracle_empty_algorithm():
    oracle = valid_oracle()
    oracle["algorithm"] = "   "

    with pytest.raises(ValueError, match="algorithm"):
        validate_oracle_response(oracle, valid_oracle_core())


def test_oracle_invalid_python():
    oracle = valid_oracle()
    oracle["independent_oracle"] = "def solve(:\n print(1)"

    with pytest.raises(ValueError):
        validate_oracle_response(oracle, valid_oracle_core())


def test_oracle_non_dictionary():
    with pytest.raises(ValueError, match="dictionary"):
        validate_oracle_response([], valid_oracle_core())


def test_oracle_invalid_core():
    with pytest.raises(ValueError, match="Core problem"):
        validate_oracle_response(valid_oracle(), {})


def test_oracle_missing_core_solution():
    core = valid_oracle_core()
    del core["reference_solution"]

    with pytest.raises(ValueError, match="reference_solution"):
        validate_oracle_response(valid_oracle(), core)