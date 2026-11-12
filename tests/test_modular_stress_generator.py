from backend.services.stress_test_generator import (
    generate_stress_tests
)


# =========================================================
# TEST DATA
# =========================================================

ARRAY_N_K_SPEC = {
    "generator_type": "array_n_k",
    "input_layout": "N K followed by N array elements",
    "parameters": {
        "n_min": 1,
        "n_max": 1000,
        "k_min": 0,
        "k_max": 100000,
        "value_min": -1000,
        "value_max": 1000
    }
}


ARRAY_N_SPEC = {
    "generator_type": "array_n",
    "input_layout": "N followed by N array elements",
    "parameters": {
        "n_min": 1,
        "n_max": 1000,
        "value_min": -1000,
        "value_max": 1000
    }
}


# =========================================================
# TEST 1: ARRAY N K GENERATION
# =========================================================

def test_array_n_k():

    cases = generate_stress_tests(
        ARRAY_N_K_SPEC,
        count=7
    )

    assert len(cases) == 7

    generated_sizes = set()

    for case in cases:

        lines = case["input"].splitlines()

        n, k = map(int, lines[0].split())

        values = list(map(int, lines[1].split()))

        assert len(values) == n
        assert 1 <= n <= 1000
        assert 0 <= k <= 100000

        assert all(-1000 <= x <= 1000 for x in values)

        generated_sizes.add(n)

    assert 1 in generated_sizes
    assert 500 in generated_sizes
    assert 1000 in generated_sizes

    print("PASS: Array N K generation")


# =========================================================
# TEST 2: ARRAY N GENERATION
# =========================================================

def test_array_n():

    cases = generate_stress_tests(
        ARRAY_N_SPEC,
        count=7
    )

    assert len(cases) == 7

    generated_sizes = set()

    for case in cases:

        lines = case["input"].splitlines()

        n = int(lines[0])

        values = list(map(int, lines[1].split()))

        assert len(values) == n
        assert 1 <= n <= 1000

        assert all(-1000 <= x <= 1000 for x in values)

        generated_sizes.add(n)

    assert 1 in generated_sizes
    assert 500 in generated_sizes
    assert 1000 in generated_sizes

    print("PASS: Array N generation")


# =========================================================
# TEST 3: DETERMINISTIC GENERATION
# =========================================================

def test_deterministic_generation():

    first = generate_stress_tests(
        ARRAY_N_SPEC,
        count=5,
        seed=42
    )

    second = generate_stress_tests(
        ARRAY_N_SPEC,
        count=5,
        seed=42
    )

    assert first == second

    print("PASS: Deterministic generation")


# =========================================================
# TEST 4: INVALID GENERATOR
# =========================================================

def test_invalid_generator():

    spec = {
        "generator_type": "unknown",
        "parameters": {}
    }

    try:

        generate_stress_tests(spec)

        assert False, "Invalid generator should be rejected."

    except NotImplementedError:

        print("PASS: Invalid generator rejected")


# =========================================================
# TEST 5: INVALID COUNT
# =========================================================

def test_invalid_count():

    try:

        generate_stress_tests(
            ARRAY_N_SPEC,
            count=0
        )

        assert False, "Zero count should be rejected."

    except ValueError:

        print("PASS: Invalid count rejected")


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    tests = [
        test_array_n_k,
        test_array_n,
        test_deterministic_generation,
        test_invalid_generator,
        test_invalid_count
    ]

    passed = 0

    for test in tests:

        try:

            test()
            passed += 1

        except Exception as error:

            print(f"FAIL: {test.__name__}: {error}")

    print("\n========== FINAL REPORT ==========")

    print(f"Total: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {len(tests) - passed}")

    if passed == len(tests):
        print("\nALL TESTS PASSED!")


import pytest


# =========================================================
# ADDITIONAL EDGE CASE TESTS
# =========================================================

def test_invalid_negative_count():
    with pytest.raises(ValueError):
        generate_stress_tests(ARRAY_N_SPEC, count=-1)


def test_invalid_count_type():
    with pytest.raises(ValueError):
        generate_stress_tests(ARRAY_N_SPEC, count="5")


def test_invalid_spec_type():
    with pytest.raises(ValueError):
        generate_stress_tests(None)


def test_missing_parameters():
    with pytest.raises(ValueError):
        generate_stress_tests({
            "generator_type": "array_n",
            "parameters": None
        })


def test_invalid_n_boundaries():
    spec = {
        "generator_type": "array_n",
        "parameters": {
            "n_min": 100,
            "n_max": 1,
            "value_min": -10,
            "value_max": 10
        }
    }

    with pytest.raises(ValueError):
        generate_stress_tests(spec)


def test_invalid_value_boundaries():
    spec = {
        "generator_type": "array_n",
        "parameters": {
            "n_min": 1,
            "n_max": 10,
            "value_min": 100,
            "value_max": -100
        }
    }

    with pytest.raises(ValueError):
        generate_stress_tests(spec)


def test_fixed_size_generation():
    spec = {
        "generator_type": "array_n",
        "parameters": {
            "n_min": 5,
            "n_max": 5,
            "value_min": -10,
            "value_max": 10
        }
    }

    cases = generate_stress_tests(spec, count=3)

    assert len(cases) == 3

    for case in cases:
        numbers = list(map(int, case["input"].split()))
        assert numbers[0] == 5
        assert len(numbers[1:]) == 5


def test_invalid_k_boundaries():
    spec = {
        "generator_type": "array_n_k",
        "parameters": {
            "n_min": 1,
            "n_max": 10,
            "k_min": 100,
            "k_max": 1,
            "value_min": -10,
            "value_max": 10
        }
    }

    with pytest.raises(ValueError):
        generate_stress_tests(spec)