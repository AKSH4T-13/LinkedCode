import copy
import pytest
import random
from backend.agents.question_generator import populate_expected_outputs


optimized_solution = """
import sys

def solve():
    data = list(map(int, sys.stdin.read().split()))
    n, k = data[0], data[1]
    arr = data[2:]

    left = 0
    current_sum = 0
    best = 0
    start = 1

    for right in range(n):
        current_sum += arr[right]

        while current_sum > k and left <= right:
            current_sum -= arr[left]
            left += 1

        length = right - left + 1

        if length > best:
            best = length
            start = left + 1

    print(best, start)

solve()
"""


brute_force_solution = """
import sys

def solve():
    data = list(map(int, sys.stdin.read().split()))
    n, k = data[0], data[1]
    arr = data[2:]

    best = 0
    start = 1

    for i in range(n):
        total = 0

        for j in range(i, n):
            total += arr[j]

            if total <= k:
                length = j - i + 1

                if length > best:
                    best = length
                    start = i + 1
            else:
                break

    print(best, start)

solve()
"""


oracle_solution = """
import sys
from bisect import bisect_right

def solve():
    data = list(map(int, sys.stdin.read().split()))
    n, k = data[0], data[1]
    arr = data[2:]

    prefix = [0]

    for x in arr:
        prefix.append(prefix[-1] + x)

    best = 0
    start = 1

    for i in range(n):
        target = prefix[i] + k

        j = bisect_right(
            prefix,
            target,
            i + 1,
            n + 1
        ) - 1

        length = j - i

        if length > best:
            best = length
            start = i + 1

    print(best, start)

solve()
"""


core = {
    "reference_solution": optimized_solution,
    "brute_force_solution": brute_force_solution
}


oracle = {
    "independent_oracle": oracle_solution
}


test_data = {
    "test_cases": [
        {"input": "3 5\n1 2 3\n", "expected_output": ""},
        {"input": "5 7\n1 2 3 4 5\n", "expected_output": ""},
        {"input": "4 3\n2 1 1 2\n", "expected_output": ""}
    ],

    "verification_test_cases": [
        {"input": "3 4\n2 2 2\n", "expected_output": ""},
        {"input": "6 10\n5 5 5 5 5 5\n", "expected_output": ""}
    ]
}


def test_three_way_cross_validation():

    data = copy.deepcopy(test_data)

    result = populate_expected_outputs(
        data,
        core,
        oracle
    )

    expected = {
        "test_cases": ["2 1", "3 1", "2 1"],
        "verification_test_cases": ["2 1", "2 1"]
    }

    for category, cases in result.items():

        for index, case in enumerate(cases):

            assert case["expected_output"] == expected[category][index]


def test_incorrect_oracle_is_rejected():

    bad_oracle = oracle_solution.replace(
        "print(best, start)",
        "print(best + 1, start)"
    )

    invalid_oracle = {
        "independent_oracle": bad_oracle
    }

    data = copy.deepcopy(test_data)

    with pytest.raises(ValueError, match="CROSS-VALIDATION FAILED"):

        populate_expected_outputs(
            data,
            core,
            invalid_oracle
        )

def test_randomized_differential_validation():

    rng = random.Random(42)

    random_cases = []

    for _ in range(100):

        n = rng.randint(1, 30)
        k = rng.randint(1, 100)

        arr = [
            rng.randint(1, 30)
            for _ in range(n)
        ]

        input_data = (
            f"{n} {k}\n"
            + " ".join(map(str, arr))
            + "\n"
        )

        random_cases.append({
            "input": input_data,
            "expected_output": ""
        })

    data = {
        "test_cases": random_cases,
        "verification_test_cases": []
    }

    result = populate_expected_outputs(
        data,
        core,
        oracle
    )

    assert len(result["test_cases"]) == 100

    for case in result["test_cases"]:
        assert case["expected_output"].strip()


def test_edge_case_validation():

    edge_cases = [
        # Single element satisfying condition
        "1 5\n5\n",

        # Every element greater than K
        "3 2\n5 6 7\n",

        # Duplicate elements
        "4 4\n2 2 2 2\n",

        # Entire array satisfies condition
        "3 10\n1 2 3\n",

        # Multiple subarrays with equal maximum length
        "4 3\n1 2 1 2\n"
    ]

    expected_outputs = [
        "1 1",
        "0 1",
        "2 1",
        "3 1",
        "2 1"
    ]

    data = {
        "test_cases": [
            {
                "input": case,
                "expected_output": ""
            }
            for case in edge_cases
        ],
        "verification_test_cases": []
    }

    result = populate_expected_outputs(
        data,
        core,
        oracle
    )

    for index, case in enumerate(result["test_cases"]):

        assert (
            case["expected_output"].strip()
            == expected_outputs[index]
        )