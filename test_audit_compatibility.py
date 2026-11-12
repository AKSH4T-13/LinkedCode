import inspect

from backend.agents.question_generator import (
    build_audit_prompt,
    audit_generated_solutions,
    build_solution_correction_prompt,
    generate_dsa_question
)

dummy_core = {
    "title": "Test Problem",
    "difficulty": "Easy",
    "topics": ["Array"],
    "description": "Find the maximum element in an array.",
    "input_format": "An array of integers.",
    "output_format": "Maximum element.",
    "constraints": ["1 <= n <= 100"],
    "examples": [],
    "reference_solution": "def solve():\n    pass",
    "brute_force_solution": "def solve():\n    pass",
    "time_complexity": "O(n)",
    "space_complexity": "O(1)"
}

dummy_audit = {
    "status": "FAIL",
    "optimized_analysis": "Test analysis",
    "brute_force_analysis": "Test analysis",
    "complexity_analysis": "Test analysis",
    "issues": ["Test issue"],
    "counterexamples": [],
    "correction_guidance": "Fix the issue"
}

print("Checking audit prompt...")
audit_prompt = build_audit_prompt(dummy_core)
assert isinstance(audit_prompt, str) and len(audit_prompt) > 0

print("Checking correction prompt...")
correction_prompt = build_solution_correction_prompt(
    dummy_core, dummy_audit
)
assert isinstance(correction_prompt, str) and len(correction_prompt) > 0

print("Checking audit function...")
assert callable(audit_generated_solutions)

print("Checking generator integration...")
generator_source = inspect.getsource(generate_dsa_question)

assert "run_solution_audit_loop" in generator_source
assert "run_solution_audit_loop" in generator_source
assert "validate_generated_core_response" in generator_source

print("\nALL COMPATIBILITY CHECKS PASSED!")