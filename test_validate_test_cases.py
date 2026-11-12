import copy

from backend.agents.question_generator import (
    validate_test_case_response
)


# =========================================================
# HELPER: CREATE VALID TEST DATA
# =========================================================

def create_valid_data():

    return {
        "test_cases": [
            {
                "input": f"2 10\n{i} {i + 1}",
                "expected_output": ""
            }
            for i in range(10)
        ],

        "verification_test_cases": [
            {
                "input": f"3 5\n{i} {i + 1} {i + 2}",
                "expected_output": ""
            }
            for i in range(15)
        ]
    }


# =========================================================
# HELPER: RUN TEST
# =========================================================

def run_test(name, data, should_pass):

    print(f"\n========== {name} ==========")

    try:

        result = validate_test_case_response(data)

        if should_pass:
            print("PASS: Valid data accepted.")
            return True

        print("FAIL: Invalid data was accepted.")
        return False

    except ValueError as error:

        if should_pass:
            print("FAIL:", error)
            return False

        print("PASS: Invalid data rejected.")
        print("Reason:", error)
        return True


# =========================================================
# TEST 1: VALID RESPONSE
# =========================================================

def test_valid_response():

    data = create_valid_data()

    assert run_test(
        "TEST 1: VALID RESPONSE",
        data,
        True
    ) is True


# =========================================================
# TEST 2: INCORRECT CASE COUNT
# =========================================================

def test_incorrect_count():

    data = create_valid_data()

    data["test_cases"].pop()

    assert run_test(
        "TEST 2: INCORRECT CASE COUNT",
        data,
        False
    ) is True


# =========================================================
# TEST 3: EMPTY INPUT
# =========================================================

def test_empty_input():

    data = create_valid_data()

    data["test_cases"][0]["input"] = ""

    assert run_test(
        "TEST 3: EMPTY INPUT",
        data,
        False
    ) is True


# =========================================================
# TEST 4: DUPLICATE INPUT
# =========================================================

def test_duplicate_input():

    data = create_valid_data()

    data["test_cases"][1]["input"] = (
        data["test_cases"][0]["input"]
    )

    assert run_test(
        "TEST 4: DUPLICATE INPUT",
        data,
        False
    ) is True


# =========================================================
# TEST 5: NON-EMPTY EXPECTED OUTPUT
# =========================================================

def test_non_empty_expected_output():

    data = create_valid_data()

    data["test_cases"][0]["expected_output"] = "10"

    assert run_test(
        "TEST 5: NON-EMPTY EXPECTED OUTPUT",
        data,
        False
    ) is True


# =========================================================
# TEST 6: EXTRA FIELD
# =========================================================

def test_extra_field():

    data = create_valid_data()

    data["test_cases"][0]["extra"] = "unexpected"

    assert run_test(
        "TEST 6: EXTRA FIELD",
        data,
        False
    ) is True


# =========================================================
# TEST 7: INVALID INPUT TYPE
# =========================================================

def test_invalid_input_type():

    data = create_valid_data()

    data["test_cases"][0]["input"] = 123

    assert run_test(
        "TEST 7: INVALID INPUT TYPE",
        data,
        False
    ) is True


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    tests = [
        test_valid_response,
        test_incorrect_count,
        test_empty_input,
        test_duplicate_input,
        test_non_empty_expected_output,
        test_extra_field,
        test_invalid_input_type
    ]

    passed = 0

    for test in tests:

        if test():
            passed += 1

    failed = len(tests) - passed

    print("\n========== FINAL TEST REPORT ==========")

    print("Total Tests:", len(tests))
    print("Passed:", passed)
    print("Failed:", failed)

    if failed == 0:
        print("\nALL VALIDATOR TESTS PASSED!")
    else:
        print("\nSOME VALIDATOR TESTS FAILED!")