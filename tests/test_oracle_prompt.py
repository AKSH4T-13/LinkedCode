from backend.agents.question_generator import build_oracle_prompt


def test_oracle_prompt_contains_correctness_requirements():

    core = {
        "title": "Test Problem",
        "description": "Count valid pairs.",
        "reference_solution": "optimized code",
        "brute_force_solution": "brute force code"
    }

    prompt = build_oracle_prompt(core)

    assert "MATHEMATICAL SELF-VERIFICATION" in prompt
    assert "Manually trace the algorithm" in prompt
    assert "Correctness is more important" in prompt
    assert "independent_oracle" in prompt
    assert "standard input" in prompt


def test_oracle_prompt_includes_problem_data():

    core = {
        "title": "Pair Sum",
        "description": "Count pairs with sum K."
    }

    prompt = build_oracle_prompt(core)

    assert "Pair Sum" in prompt
    assert "Count pairs with sum K." in prompt