

from backend.agents.question_generator import (
    build_core_prompt,
    validate_core_response,
    validate_stress_spec_constraints
)

import pytest


def test_core_prompt_contains_required_fields():
    prompt = build_core_prompt(["Array", "Hash Table"], "Medium")

    assert "brute_force_complexity" in prompt
    assert "stress_test_spec" in prompt


def test_core_validator_rejects_missing_brute_force_complexity():
    core = {
        "title": "Test Problem",
        "difficulty": "Medium",
        "topics": ["Array"],
        "description": "A test problem description.",
        "input_format": "Integer array",
        "output_format": "Integer",
        "constraints": ["1 <= n <= 100"],
        "examples": [{"input": "1", "output": "1", "explanation": "Test"}],
        "reference_solution": "def solve():\n    pass",
        "brute_force_solution": "def solve():\n    pass",
        "time_complexity": "O(n)",
        "space_complexity": "O(1)",
        "stress_test_spec": {
            "generator_type": "array_n",
            "input_layout": "N followed by N array elements",
            "parameters": {
                "n_min": 1,
                "n_max": 100,
                "value_min": 0,
                "value_max": 100
            }
        }
    }

    with pytest.raises(ValueError, match="brute_force_complexity"):
        validate_core_response(core)

def test_core_validator_rejects_empty_brute_force_complexity():
    core = {
        "title": "Test Problem",
        "difficulty": "Medium",
        "topics": ["Array"],
        "description": "A test problem description.",
        "input_format": "Integer array",
        "output_format": "Integer",
        "constraints": ["1 <= n <= 100"],
        "examples": [
            {"input": "1", "output": "1", "explanation": "Test"}
        ],
        "reference_solution": "def solve():\n    pass",
        "brute_force_solution": "def solve():\n    pass",
        "time_complexity": "O(n)",
        "brute_force_complexity": "",
        "space_complexity": "O(1)",
        "stress_test_spec": {
            "generator_type": "array_n",
            "input_layout": "N followed by N array elements",
            "parameters": {
                "n_min": 1,
                "n_max": 100,
                "value_min": 0,
                "value_max": 100
            }
        }
    }

    with pytest.raises(ValueError, match="Invalid brute_force_complexity"):
        validate_core_response(core)

def test_core_validator_rejects_non_string_brute_force_complexity():
    core = {
        "title": "Test Problem",
        "difficulty": "Medium",
        "topics": ["Array"],
        "description": "A test problem description.",
        "input_format": "Integer array",
        "output_format": "Integer",
        "constraints": ["1 <= n <= 100"],
        "examples": [
            {"input": "1", "output": "1", "explanation": "Test"}
        ],
        "reference_solution": "def solve():\n    pass",
        "brute_force_solution": "def solve():\n    pass",
        "time_complexity": "O(n)",
        "brute_force_complexity": 123,
        "space_complexity": "O(1)",
        "stress_test_spec": {
            "generator_type": "array_n",
            "input_layout": "N followed by N array elements",
            "parameters": {
                "n_min": 1,
                "n_max": 100,
                "value_min": 0,
                "value_max": 100
            }
        }
    }

    with pytest.raises(ValueError, match="Invalid brute_force_complexity"):
        validate_core_response(core)


def test_core_validator_rejects_invalid_brute_force_complexity():
    core = {
        "title": "Test Problem",
        "difficulty": "Medium",
        "topics": ["Array"],
        "description": "A test problem description.",
        "input_format": "Integer array",
        "output_format": "Integer",
        "constraints": ["1 <= n <= 100"],
        "examples": [
            {"input": "1", "output": "1", "explanation": "Test"}
        ],
        "reference_solution": "def solve():\n    pass",
        "brute_force_solution": "def solve():\n    pass",
        "time_complexity": "O(n)",
        "brute_force_complexity": "Random complexity",
        "space_complexity": "O(1)",
        "stress_test_spec": {
            "generator_type": "array_n",
            "input_layout": "N followed by N array elements",
            "parameters": {
                "n_min": 1,
                "n_max": 100,
                "value_min": 0,
                "value_max": 100
            }
        }
    }

    with pytest.raises(ValueError, match="Invalid brute_force_complexity notation"):
        validate_core_response(core)


def test_core_validator_rejects_invalid_time_complexity():
    core = {
        "title": "Test Problem",
        "difficulty": "Medium",
        "topics": ["Array"],
        "description": "A test problem description.",
        "input_format": "Integer array",
        "output_format": "Integer",
        "constraints": ["1 <= n <= 100"],
        "examples": [
            {"input": "1", "output": "1", "explanation": "Test"}
        ],
        "reference_solution": "def solve():\n    pass",
        "brute_force_solution": "def solve():\n    pass",
        "time_complexity": "Linear time",
        "brute_force_complexity": "O(n^2)",
        "space_complexity": "O(1)",
        "stress_test_spec": {
            "generator_type": "array_n",
            "input_layout": "N followed by N array elements",
            "parameters": {
                "n_min": 1,
                "n_max": 100,
                "value_min": 0,
                "value_max": 100
            }
        }
    }

    with pytest.raises(ValueError, match="Invalid time_complexity notation"):
        validate_core_response(core)


def create_valid_core(generator_type="array_n"):
    parameters = {
        "n_min": 1,
        "n_max": 100,
        "value_min": 0,
        "value_max": 100
    }

    if generator_type == "array_n_k":
        parameters.update({
            "k_min": 0,
            "k_max": 100
        })

    return {
        "title": "Test Problem",
        "difficulty": "Medium",
        "topics": ["Array"],
        "description": "A test problem.",
        "input_format": "Integer array",
        "output_format": "Integer",
        "constraints": ["1 <= n <= 100"],
        "examples": [
            {
                "input": "1 1\n1" if generator_type == "array_n_k" else "1\n1",
                "output": "1",
                "explanation": "Test"
            },
            {
                "input": "1 1\n2" if generator_type == "array_n_k" else "1\n2",
                "output": "1",
                "explanation": "Second example"
            }
        ],
        "reference_solution": "print(1)",
        "brute_force_solution": "print(1)",
        "time_complexity": "O(n)",
        "brute_force_complexity": "O(n^2)",
        "space_complexity": "O(1)",
        "stress_test_spec": {
            "generator_type": generator_type,
            "input_layout": "N followed by N array elements",
            "parameters": parameters
        }
    }


@pytest.mark.parametrize(
    "generator_type",
    ["string", "graph", "tree", "matrix", "custom"]
)
def test_core_validator_rejects_unsupported_generator_types(generator_type):
    core = create_valid_core(generator_type)

    with pytest.raises(ValueError, match="Unsupported generator type"):
        validate_core_response(core)


@pytest.mark.parametrize(
    "generator_type",
    ["array_n", "array_n_k"]
)
def test_core_validator_accepts_supported_generator_types(generator_type):
    core = create_valid_core(generator_type)

    validate_core_response(core)

def create_stress_spec(generator_type="array_n"):

    params = {
        "n_min": 1,
        "n_max": 100,
        "value_min": -100,
        "value_max": 100
    }

    bounds = {
        "n": {"min": 1, "max": 100},
        "value": {"min": -100, "max": 100}
    }

    if generator_type == "array_n_k":
        params.update({
            "k_min": 0,
            "k_max": 1000
        })

        bounds["k"] = {
            "min": 0,
            "max": 1000
        }

    return {
        "generator_type": generator_type,
        "input_layout": "N followed by array elements",
        "parameters": params,
        "constraint_bounds": bounds
    }


def test_valid_array_n_stress_spec():
    spec = create_stress_spec("array_n")
    assert validate_stress_spec_constraints(
    [
        "1 <= n <= 100",
        "-100 <= arr[i] <= 100",
        "0 <= k <= 1000"
    ],
    spec
) is True


def test_valid_array_n_k_stress_spec():
    spec = create_stress_spec("array_n_k")
    assert validate_stress_spec_constraints(
    [
        "1 <= n <= 100",
        "-100 <= arr[i] <= 100",
        "0 <= k <= 1000"
    ],
    spec
) is True


def test_reject_mismatched_n_boundaries():
    spec = create_stress_spec()
    spec["parameters"]["n_max"] = 200

    with pytest.raises(ValueError, match="does not match"):
        validate_stress_spec_constraints(
            [
                "1 <= n <= 100",
                "-100 <= arr[i] <= 100",
                "0 <= k <= 1000"
            ],
            spec
        )


def test_reject_mismatched_value_boundaries():
    spec = create_stress_spec()
    spec["parameters"]["value_min"] = -200

    with pytest.raises(ValueError, match="does not match"):
        validate_stress_spec_constraints(
            [
                "1 <= n <= 100",
                "-100 <= arr[i] <= 100",
                "0 <= k <= 1000"
            ],
            spec
        )


def test_reject_mismatched_k_boundaries():
    spec = create_stress_spec("array_n_k")
    spec["parameters"]["k_max"] = 2000

    with pytest.raises(ValueError, match="does not match"):
        validate_stress_spec_constraints(
            [
                "1 <= n <= 100",
                "-100 <= arr[i] <= 100",
                "0 <= k <= 1000"
            ],
            spec
        )


def test_reject_missing_constraint_bounds():
    spec = create_stress_spec()
    del spec["constraint_bounds"]

    with pytest.raises(ValueError, match="constraint_bounds"):
        validate_stress_spec_constraints(
            [
                "1 <= n <= 100",
                "-100 <= arr[i] <= 100",
                "0 <= k <= 1000"
            ],
            spec
        )


def test_reject_invalid_boundary_order():
    spec = create_stress_spec()
    spec["constraint_bounds"]["n"]["min"] = 200

    with pytest.raises(ValueError, match="Invalid boundaries"):
        validate_stress_spec_constraints(
            [
                "1 <= n <= 100",
                "-100 <= arr[i] <= 100",
                "0 <= k <= 1000"
            ],
            spec
        )

VALID_ARRAY_N_CONSTRAINTS = [
    "1 <= n <= 100",
    "-100 <= arr[i] <= 100"
]

VALID_ARRAY_N_K_CONSTRAINTS = [
    "1 <= n <= 100",
    "0 <= k <= 1000",
    "-100 <= arr[i] <= 100"
]


def test_accept_negative_value_boundaries():
    spec = create_stress_spec("array_n")

    assert validate_stress_spec_constraints(
        VALID_ARRAY_N_CONSTRAINTS,
        spec
    ) is True


def test_accept_whitespace_variations():
    spec = create_stress_spec("array_n")

    constraints = [
        "1   <=   n   <=   100",
        "-100  <=  arr[i]  <=  100"
    ]

    assert validate_stress_spec_constraints(
        constraints,
        spec
    ) is True


def test_reject_missing_array_value_constraint():
    spec = create_stress_spec("array_n")

    with pytest.raises(ValueError, match="array-value|value"):
        validate_stress_spec_constraints(
            ["1 <= n <= 100"],
            spec
        )


def test_reject_incorrect_textual_n_boundary():
    spec = create_stress_spec("array_n")

    constraints = [
        "1 <= n <= 200",
        "-100 <= arr[i] <= 100"
    ]

    with pytest.raises(ValueError, match="Textual constraints"):
        validate_stress_spec_constraints(constraints, spec)


def test_reject_incorrect_textual_value_boundary():
    spec = create_stress_spec("array_n")

    constraints = [
        "1 <= n <= 100",
        "-200 <= arr[i] <= 100"
    ]

    with pytest.raises(ValueError, match="Textual constraints"):
        validate_stress_spec_constraints(constraints, spec)



def test_array_n_k_requires_k_constraint():
    spec = create_stress_spec("array_n_k")

    constraints = [
        "1 <= n <= 100",
        "-100 <= arr[i] <= 100"
    ]

    with pytest.raises(ValueError, match="k"):
        validate_stress_spec_constraints(constraints, spec)


def test_array_n_k_accepts_valid_constraints():
    spec = create_stress_spec("array_n_k")

    assert validate_stress_spec_constraints(
        VALID_ARRAY_N_K_CONSTRAINTS,
        spec
    ) is True


@pytest.mark.parametrize(
    "variable",
    ["arr", "nums", "a", "values", "prices", "numbers"]
)
def test_accept_different_array_variable_names(variable):

    spec = create_stress_spec("array_n")

    constraints = [
        "1 <= n <= 100",
        f"-100 <= {variable}[i] <= 100"
    ]

    assert validate_stress_spec_constraints(
        constraints,
        spec
    ) is True


@pytest.mark.parametrize(
    "constraints",
    [
        ["1 <= len(arr) <= 100", "-100 <= arr[i] <= 100"],
        ["1 <= n <= 100", "arr[i] >= -100", "arr[i] <= 100"],
        ["1 <= len(nums) <= 100", "nums[i] >= -100", "nums[i] <= 100"],
        ["1 <= n <= 100", "-100 <= values[i] <= 100"]
    ]
)
def test_accept_alternative_constraint_formats(constraints):

    spec = create_stress_spec("array_n")

    assert validate_stress_spec_constraints(
        constraints,
        spec
    ) is True


def test_reject_incomplete_separate_value_constraints():

    spec = create_stress_spec("array_n")

    constraints = [
        "1 <= n <= 100",
        "arr[i] >= -100"
    ]

    with pytest.raises(ValueError, match="value"):
        validate_stress_spec_constraints(constraints, spec)

@pytest.mark.parametrize("generator_type", ["array_n", "array_n_k"])
def test_core_validator_rejects_wrong_example_layout(generator_type):
    core = create_valid_core(generator_type)
    core["examples"][0]["input"] = "1\n1" if generator_type == "array_n_k" else "1 2\n1"
    with pytest.raises(ValueError, match="input does not match"):
        validate_core_response(core)


def test_core_rejects_single_example_before_expensive_phases():
    core = create_valid_core()
    core["examples"] = core["examples"][:1]
    with pytest.raises(ValueError, match="at least 2 examples"):
        validate_core_response(core)
