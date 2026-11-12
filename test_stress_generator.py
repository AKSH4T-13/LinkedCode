from backend.services.stress_test_generator import (
    generate_array_n_k_stress_tests
)


def test_stress_generator():

    tests = generate_array_n_k_stress_tests(
        params={
            "n_min": 1,
            "n_max": 100,
            "k_min": 1,
            "k_max": 100,
            "value_min": -100,
            "value_max": 100
        },
        count=7,
        seed=42
    )

    assert len(tests) == 7

    for case in tests:

        lines = case["input"].splitlines()

        n, k = map(int, lines[0].split())
        values = list(map(int, lines[1].split()))

        assert len(values) == n
        assert 1 <= n <= 100
        assert 1 <= k <= 100
        assert all(-100 <= x <= 100 for x in values)
        assert "category" in case