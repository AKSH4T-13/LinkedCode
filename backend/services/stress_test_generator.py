import random


# =========================================================
# COMMON VALIDATION
# =========================================================

def validate_array_parameters(params):

    if not isinstance(params, dict):
        raise ValueError("Parameters must be a dictionary.")

    required = {
        "n_min",
        "n_max",
        "value_min",
        "value_max"
    }

    missing = required - params.keys()

    if missing:
        raise ValueError(
            f"Missing array parameters: {missing}"
        )

    for key in required:
        if not isinstance(params[key], int) or isinstance(params[key], bool):
            raise ValueError(f"{key} must be an integer.")

    if params["n_min"] < 1:
        raise ValueError("n_min must be at least 1.")

    if params["n_min"] > params["n_max"]:
        raise ValueError("Invalid N boundaries.")

    if params["value_min"] > params["value_max"]:
        raise ValueError("Invalid value boundaries.")


# =========================================================
# COMMON ARRAY PATTERN GENERATOR
# =========================================================

def generate_array_patterns(params, count, seed):

    validate_array_parameters(params)

    if count < 1:
        raise ValueError("count must be at least 1.")

    rng = random.Random(seed)

    n_min = params["n_min"]
    n_max = params["n_max"]

    v_min = params["value_min"]
    v_max = params["value_max"]

    n_mid = (n_min + n_max) // 2

    cases = []

    def add_case(values, category):

        cases.append({
            "values": values,
            "category": category
        })

    # CASE 1: Minimum boundary

    add_case(
        [v_min] * n_min,
        "minimum_boundary"
    )

    # CASE 2: Medium-sized random input

    add_case(
        [
            rng.randint(v_min, v_max)
            for _ in range(n_mid)
        ],
        "medium_random"
    )

    # CASE 3: Maximum size with minimum values

    add_case(
        [v_min] * n_max,
        "maximum_size_minimum_values"
    )

    # CASE 4: Maximum size with maximum values

    add_case(
        [v_max] * n_max,
        "maximum_size_maximum_values"
    )

    # CASE 5: Duplicate-heavy input

    duplicate = rng.randint(v_min, v_max)

    add_case(
        [duplicate] * n_max,
        "duplicate_heavy"
    )

    # CASE 6: Alternating minimum and maximum values

    alternating = [
        v_min if i % 2 == 0 else v_max
        for i in range(n_max)
    ]

    add_case(
        alternating,
        "alternating_extremes"
    )

    # CASE 7: Sorted input

    sorted_values = sorted(
        rng.randint(v_min, v_max)
        for _ in range(n_max)
    )

    add_case(
        sorted_values,
        "sorted_array"
    )

    # CASE 8: Reverse sorted input

    add_case(
        sorted_values[::-1],
        "reverse_sorted_array"
    )

    # CASE 9: Maximum-size random input

    add_case(
        [
            rng.randint(v_min, v_max)
            for _ in range(n_max)
        ],
        "maximum_random"
    )

    return cases[:count]


# =========================================================
# ARRAY + K GENERATOR
# =========================================================

def generate_array_n_k_stress_tests(
    params,
    count=7,
    seed=42
):

    validate_array_parameters(params)

    required = {"k_min", "k_max"}

    if not required.issubset(params):
        raise ValueError("Missing K boundaries.")

    if (
        not isinstance(params["k_min"], int)
        or isinstance(params["k_min"], bool)
        or not isinstance(params["k_max"], int)
        or isinstance(params["k_max"], bool)
    ):
        raise ValueError("K boundaries must be integers.")

    if params["k_min"] > params["k_max"]:
        raise ValueError("Invalid K boundaries.")

    rng = random.Random(seed)

    k_min = params["k_min"]
    k_max = params["k_max"]

    patterns = generate_array_patterns(
        params,
        count=9,
        seed=seed
    )

    k_values = [
        k_min,
        (k_min + k_max) // 2,
        k_max,
        k_min,
        k_max,
        (k_min + k_max) // 2,
        k_min,
        k_max,
        rng.randint(k_min, k_max)
    ]

    cases = []

    for index, pattern in enumerate(patterns):

        values = pattern["values"]
        k = k_values[index]

        n = len(values)

        cases.append({
            "input": (
                f"{n} {k}\n"
                + " ".join(map(str, values))
            ),
            "category": pattern["category"],
            "oracle_check": n <= 2000
        })

    return cases[:count]


# =========================================================
# ARRAY N GENERATOR
# =========================================================

def generate_array_n_stress_tests(
    params,
    count=7,
    seed=42
):

    patterns = generate_array_patterns(
        params,
        count=count,
        seed=seed
    )

    cases = []

    for pattern in patterns:

        values = pattern["values"]

        n = len(values)

        cases.append({
            "input": (
                f"{n}\n"
                + " ".join(map(str, values))
            ),
            "category": pattern["category"],
            "oracle_check": n <= 2000
        })

    return cases


# =========================================================
# STRESS TEST DISPATCHER
# =========================================================

def validate_generated_stress_cases(stress_cases, generator_type, params):
    if not isinstance(stress_cases, list):
        raise ValueError("Generated stress cases must be a list.")

    if not stress_cases:
        raise ValueError("No stress cases generated.")

    n_min = params["n_min"]
    n_max = params["n_max"]
    value_min = params["value_min"]
    value_max = params["value_max"]

    k_min = params.get("k_min")
    k_max = params.get("k_max")

    for index, case in enumerate(stress_cases, start=1):

        if not isinstance(case, dict):
            raise ValueError(f"Stress case {index} must be a dictionary.")

        input_data = case.get("input")

        if not isinstance(input_data, str) or not input_data.strip():
            raise ValueError(f"Stress case {index} has invalid input.")

        try:
            tokens = input_data.split()
            numbers = [int(token) for token in tokens]
        except (ValueError, TypeError):
            raise ValueError(
                f"Stress case {index} contains non-integer input."
            )

        if generator_type == "array_n_k":
            if len(numbers) < 2:
                raise ValueError(f"Stress case {index} is incomplete.")

            n, k = numbers[0], numbers[1]
            values = numbers[2:]

            if not isinstance(k_min, int) or not isinstance(k_max, int):
                raise ValueError("Invalid K boundaries.")

            if k_min > k_max:
                raise ValueError("Invalid K boundary order.")

            if not k_min <= k <= k_max:
                raise ValueError(
                    f"Stress case {index}: K is outside allowed boundaries."
                )

        else:
            if not numbers:
                raise ValueError(f"Stress case {index} is incomplete.")

            n = numbers[0]
            values = numbers[1:]

        if not n_min <= n <= n_max:
            raise ValueError(
                f"Stress case {index}: N is outside allowed boundaries."
            )

        if len(values) != n:
            raise ValueError(
                f"Stress case {index}: Expected {n} array elements, "
                f"got {len(values)}."
            )

        for value in values:
            if not value_min <= value <= value_max:
                raise ValueError(
                    f"Stress case {index}: Array value {value} "
                    "is outside allowed boundaries."
                )

    return True


def generate_stress_tests(
    stress_test_spec,
    count=7,
    seed=42
):
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValueError("count must be a positive integer.")

    if not isinstance(stress_test_spec, dict):
        raise ValueError("Invalid stress_test_spec.")

    generator_type = stress_test_spec.get("generator_type")
    params = stress_test_spec.get("parameters")

    if not isinstance(params, dict):
        raise ValueError("Invalid generator parameters.")

    generators = {
        "array_n_k": generate_array_n_k_stress_tests,
        "array_n": generate_array_n_stress_tests
    }

    generator = generators.get(generator_type)

    if generator is None:
        raise NotImplementedError(
            f"Generator not implemented yet: {generator_type}"
        )

    stress_cases = generator(
        params=params,
        count=count,
        seed=seed
    )

    validate_generated_stress_cases(
        stress_cases,
        generator_type,
        params
    )

    if len(stress_cases) != count:
        raise ValueError(
            f"Expected {count} stress cases, generated {len(stress_cases)}."
        )

    return stress_cases