import pytest

from unittest.mock import patch

from backend.agents.question_generator import (
    validate_oracle_response
)


@pytest.fixture
def valid_oracle():

    return {
        "algorithm": "Use an independent mathematical approach.",
        "independent_oracle": (
            "import sys\n"
            "data = list(map(int, sys.stdin.read().split()))\n"
            "print(sum(data))"
        )
    }


@pytest.fixture
def valid_core():

    return {
        "reference_solution": "optimized solution code",
        "brute_force_solution": "brute force solution code"
    }


def test_valid_oracle(valid_oracle, valid_core):

    with patch(
        "backend.agents.question_generator.validate_python_code"
    ), patch(
        "backend.agents.question_generator.validate_oracle_independence"
    ):

        result = validate_oracle_response(
            valid_oracle,
            valid_core
        )

        assert result is True


def test_oracle_must_be_dictionary(valid_core):

    with pytest.raises(ValueError, match="dictionary"):

        validate_oracle_response(
            "invalid",
            valid_core
        )


@pytest.mark.parametrize(
    "oracle",
    [
        {},
        {"algorithm": "Valid algorithm"},
        {"independent_oracle": "print(1)"},
        {"algorithm": "", "independent_oracle": "print(1)"},
        {"algorithm": "Valid", "independent_oracle": ""}
    ]
)
def test_missing_or_invalid_fields(oracle, valid_core):

    with pytest.raises(ValueError):

        validate_oracle_response(
            oracle,
            valid_core
        )


def test_invalid_python_syntax(valid_oracle, valid_core):

    with patch(
        "backend.agents.question_generator.validate_python_code",
        side_effect=ValueError("Invalid Python syntax")
    ):

        with pytest.raises(ValueError, match="Invalid Python syntax"):

            validate_oracle_response(
                valid_oracle,
                valid_core
            )


def test_independence_validation_is_called(
    valid_oracle,
    valid_core
):

    with patch(
        "backend.agents.question_generator.validate_python_code"
    ), patch(
        "backend.agents.question_generator.validate_oracle_independence"
    ) as independence_mock:

        validate_oracle_response(
            valid_oracle,
            valid_core
        )

        independence_mock.assert_called_once_with(
            valid_core["brute_force_solution"],
            valid_core["reference_solution"],
            valid_oracle["independent_oracle"]
        )


def test_similar_oracle_is_rejected(valid_oracle, valid_core):

    with patch(
        "backend.agents.question_generator.validate_python_code"
    ), patch(
        "backend.agents.question_generator.validate_oracle_independence",
        side_effect=ValueError("Oracle implementations are too similar")
    ):

        with pytest.raises(ValueError, match="too similar"):

            validate_oracle_response(
                valid_oracle,
                valid_core
            )