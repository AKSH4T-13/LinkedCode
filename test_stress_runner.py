from backend.services.stress_test_runner import run_stress_tests
from backend.services.stress_test_generator import generate_array_n_k_stress_tests


def test_stress_runner():

    optimized_solution = """
import sys

def solve():
    data = list(map(int, sys.stdin.read().split()))

    if not data:
        return

    n, k = data[0], data[1]
    arr = data[2:2+n]

    print(max(arr))

if __name__ == "__main__":
    solve()
"""

    oracle_solution = """
import sys

def solve():
    data = list(map(int, sys.stdin.read().split()))

    if not data:
        return

    n, k = data[0], data[1]
    arr = data[2:2+n]

    answer = arr[0]

    for value in arr:
        if value > answer:
            answer = value

    print(answer)

if __name__ == "__main__":
    solve()
"""

    question = {
        "reference_solution": optimized_solution,
        "verification_approach": {
            "independent_oracle": oracle_solution
        }
    }

    stress_cases = generate_array_n_k_stress_tests(
        params={
            "n_min": 1,
            "n_max": 200000,
            "k_min": 0,
            "k_max": 10**12,
            "value_min": -10**9,
            "value_max": 10**9
        },
        count=5,
        seed=42
    )

    report = run_stress_tests(question, stress_cases)

    assert report["total_tests"] == 5
    assert report["passed"] == 5
    assert report["failed"] == 0
    assert report["is_valid"] is True

import pytest


def create_question(optimized, oracle=None):
    question = {
        "reference_solution": optimized,
        "verification_approach": {}
    }

    if oracle is not None:
        question["verification_approach"]["independent_oracle"] = oracle

    return question


def test_oracle_output_mismatch():
    optimized = """
import sys
data = list(map(int, sys.stdin.read().split()))
print(max(data[2:]))
"""

    oracle = """
import sys
data = list(map(int, sys.stdin.read().split()))
print(min(data[2:]))
"""

    question = create_question(optimized, oracle)

    cases = [{
        "input": "3 5\n1 9 4",
        "oracle_check": True
    }]

    report = run_stress_tests(question, cases)

    assert report["failed"] == 1
    assert report["is_valid"] is False


def test_optimized_solution_runtime_failure():
    optimized = """
while True:
    pass
"""

    question = create_question(optimized)

    cases = [{
        "input": "1 0\n5",
        "oracle_check": False
    }]

    report = run_stress_tests(question, cases)

    assert report["failed"] == 1
    assert report["is_valid"] is False


def test_oracle_runtime_failure():
    optimized = """
import sys
data = list(map(int, sys.stdin.read().split()))
print(max(data[2:]))
"""

    oracle = """
while True:
    pass
"""

    question = create_question(optimized, oracle)

    cases = [{
        "input": "3 5\n1 9 4",
        "oracle_check": True
    }]

    report = run_stress_tests(question, cases)

    assert report["failed"] == 1
    assert report["is_valid"] is False


def test_optimized_only_case():
    optimized = """
import sys
data = list(map(int, sys.stdin.read().split()))
print(max(data[2:]))
"""

    question = create_question(optimized)

    cases = [{
        "input": "3 5\n1 9 4",
        "oracle_check": False
    }]

    report = run_stress_tests(question, cases)

    assert report["passed"] == 1
    assert report["oracle_comparisons"] == 0
    assert report["optimized_only_tests"] == 1


def test_failure_report_contains_diagnostics(tmp_path):
    optimized = """
import sys
data = list(map(int, sys.stdin.read().split()))
print(min(data[2:]))
"""

    oracle = """
import sys
data = list(map(int, sys.stdin.read().split()))
print(max(data[2:]))
"""

    question = create_question(optimized, oracle)

    cases = [{
        "input": "3 5\n1 9 4",
        "oracle_check": True
    }]

    failure_file = tmp_path / "stress_failure.json"

    report = run_stress_tests(
        question,
        cases,
        failure_file=str(failure_file)
    )

    assert report["is_valid"] is False
    assert failure_file.exists()

    import json

    with open(failure_file, "r", encoding="utf-8") as file:
        failure_data = json.load(file)

    assert failure_data