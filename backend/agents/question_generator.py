from backend.llm.token_budget import invoke_budgeted
import ast
import json
import os
import copy
import time
import re



from unittest.mock import patch, call

from difflib import SequenceMatcher
from backend.services.problem_quality_evaluator import (
    evaluate_problem_quality,
    extract_complexity_order
)
from backend.services.solution_validator import execute_solution

from backend.services.stress_test_generator import generate_stress_tests

from backend.services.stress_test_runner import run_stress_tests

from dotenv import load_dotenv
from langchain_groq import ChatGroq


# =========================================================
# GROQ CONFIGURATION
# =========================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env file!")


generator_llm = ChatGroq(
    model="openai/gpt-oss-20b",
    groq_api_key=GROQ_API_KEY,
    temperature=0.3,
    max_tokens=3500,
    reasoning_effort="low",
    reasoning_format="hidden",
    max_retries=0,
    timeout=60
)


# =========================================================
# REQUIRED JSON FIELDS
# =========================================================

REQUIRED_FIELDS = [
    "title",
    "difficulty",
    "topics",
    "description",
    "input_format",
    "output_format",
    "constraints",
    "examples",
    "test_cases",
    "reference_solution",
    "brute_force_solution",
    "verification_test_cases",
    "verification_approach",
    "time_complexity",
    "space_complexity",
    "stress_test_spec",
    "brute_force_complexity"
]


# =========================================================
# JSON UTILITIES
# =========================================================

def extract_response_text(response):
    """Extract plain text from Groq response."""

    content = response.content

    if not content:
        raise ValueError("Groq returned an empty response.")

    if isinstance(content, list):

        parts = []

        for item in content:

            if isinstance(item, dict):
                parts.append(item.get("text", ""))
            else:
                parts.append(str(item))

        content = "".join(parts)

    content = str(content).strip()

    if not content:
        raise ValueError("Groq response contains no text.")

    content = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        content,
        flags=re.IGNORECASE
    )

    content = re.sub(
        r"\s*```\s*$",
        "",
        content
    )

    return content.strip()


def escape_invalid_json_backslashes(content):
    """
    Escape invalid backslashes inside JSON strings.
    Valid JSON escapes are preserved.
    """

    valid_escapes = {
        '"', "\\", "/", "b",
        "f", "n", "r", "t", "u"
    }

    output = []
    inside_string = False
    index = 0

    while index < len(content):

        char = content[index]

        if not inside_string:

            output.append(char)

            if char == '"':
                inside_string = True

            index += 1
            continue

        if char == '"':

            output.append(char)
            inside_string = False
            index += 1
            continue

        if char == "\\":

            if index + 1 >= len(content):

                output.append("\\\\")
                index += 1
                continue

            next_char = content[index + 1]

            if next_char in valid_escapes:

                if next_char == "u":

                    hex_part = content[index + 2:index + 6]

                    if (
                        len(hex_part) == 4
                        and all(
                            c in "0123456789abcdefABCDEF"
                            for c in hex_part
                        )
                    ):

                        output.append(content[index:index + 6])
                        index += 6
                        continue

                    output.append("\\\\u")
                    index += 2
                    continue

                output.append(content[index:index + 2])
                index += 2
                continue

            output.append("\\\\")
            index += 1
            continue

        if char == "\n":
            output.append("\\n")

        elif char == "\r":
            output.append("\\r")

        else:
            output.append(char)

        index += 1

    return "".join(output)


def parse_response(response):
    """Parse Groq response into a JSON object."""

    finish_reason = response.response_metadata.get(
        "finish_reason"
    )

    if finish_reason == "length":

        raise ValueError(
            "Groq response was truncated because it reached "
            "the output-token limit."
        )

    content = extract_response_text(response)

    try:

        return json.loads(content)

    except json.JSONDecodeError as original_error:

        sanitized_content = escape_invalid_json_backslashes(
            content
        )

        try:

            result = json.loads(sanitized_content)

            print(
                "[GENERATOR] JSON parsed after repairing "
                "invalid backslash escapes."
            )

            return result

        except json.JSONDecodeError as sanitized_error:

            print("\n========== JSON ERROR DEBUG ==========")
            print("Original error:", original_error)
            print("Sanitized error:", sanitized_error)

            lines = content.splitlines()

            error_line = (
                lines[original_error.lineno - 1]
                if original_error.lineno <= len(lines)
                else "Line unavailable"
            )

            print("Problematic line:", repr(error_line))
            print("======================================\n")

            raise ValueError(
                "Groq returned malformed JSON. "
                f"Original error: {original_error}. "
                f"Sanitized error: {sanitized_error}."
            ) from sanitized_error


# =========================================================
# PYTHON CODE VALIDATION
# =========================================================

def validate_python_code(code, field_name, require_print=False):
    """
    Validate whether a generated string contains valid
    executable Python code.
    """

    if not isinstance(code, str) or not code.strip():

        raise ValueError(
            f"{field_name} must contain non-empty Python code."
        )

    try:

        parsed_code = ast.parse(code)

        compile(
            parsed_code,
            f"<{field_name}>",
            "exec"
        )

    except SyntaxError as error:

        raise ValueError(
            f"{field_name} contains invalid Python syntax: "
            f"{error}"
        ) from error

    if require_print:

        has_print = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
            for node in ast.walk(parsed_code)
        )

        if not has_print:

            raise ValueError(
                f"{field_name} must print its result using print()."
            )

    return True


# =========================================================
# ORACLE INDEPENDENCE VALIDATION
# =========================================================

def get_ast_fingerprint(code):
    """
    Generate a normalized AST fingerprint.

    Preserves:
    - Variable names
    - Function names
    - Operators
    - Control flow
    - Constant values
    - Function calls

    Ignores:
    - Formatting
    - Source locations
    """

    if not isinstance(code, str) or not code.strip():
        raise ValueError("Code must be a non-empty string.")

    try:
        tree = ast.parse(code)

    except SyntaxError as error:
        raise ValueError(
            f"Cannot generate AST fingerprint: {error}"
        ) from error

    fingerprint = ast.dump(
        tree,
        annotate_fields=True,
        include_attributes=False
    )

    return fingerprint

def validate_oracle_independence(
    brute_force_code,
    optimized_code,
    oracle_code
):
    """
    Detect exact duplicate implementations.

    Structural similarity is reported for debugging,
    but is not treated as proof of algorithmic similarity.
    """

    implementations = {
        "brute-force solution": brute_force_code,
        "optimized solution": optimized_code
    }

    for name, code in {
        **implementations,
        "independent oracle": oracle_code
    }.items():

        if not isinstance(code, str) or not code.strip():
            raise ValueError(
                f"{name} must be a non-empty string."
            )

    try:
        oracle_tree = ast.dump(
            ast.parse(oracle_code),
            include_attributes=False
        )
    except SyntaxError as error:
        raise ValueError(
            f"Invalid oracle syntax: {error}"
        ) from error

    for name, implementation_code in implementations.items():

        try:
            implementation_tree = ast.dump(
                ast.parse(implementation_code),
                include_attributes=False
            )
        except SyntaxError as error:
            raise ValueError(
                f"Invalid {name} syntax: {error}"
            ) from error

        if oracle_tree == implementation_tree:
            raise ValueError(
                f"Oracle is an exact structural duplicate "
                f"of the {name}."
            )

        similarity = SequenceMatcher(
            None,
            implementation_tree,
            oracle_tree,
            autojunk=False
        ).ratio()

        print(
            f"[GENERATOR] Oracle vs {name} "
            f"structural similarity: {similarity:.2%}"
        )

        if similarity >= 0.92:
            print(
                f"[WARNING] High structural similarity with "
                f"{name}; execution-based validation is required."
            )

    print(
        "[GENERATOR] Oracle duplicate check passed."
    )

    return True

# =========================================================
# STRUCTURAL VALIDATION
# =========================================================

def validate_stress_spec_constraints(constraints, stress_spec):

    import re

    if not isinstance(stress_spec, dict):
        raise ValueError("Invalid stress_test_spec.")

    if not isinstance(constraints, list) or not constraints:
        raise ValueError("Invalid constraints.")

    generator_type = stress_spec.get("generator_type")
    params = stress_spec.get("parameters")
    bounds = stress_spec.get("constraint_bounds")

    if generator_type not in {"array_n", "array_n_k"}:
        raise ValueError("Unsupported stress generator type.")

    if not isinstance(params, dict):
        raise ValueError("Invalid stress test parameters.")

    if not isinstance(bounds, dict):
        raise ValueError("constraint_bounds must be a dictionary.")

    mappings = {
        "n": ("n_min", "n_max"),
        "value": ("value_min", "value_max")
    }

    if generator_type == "array_n_k":
        mappings["k"] = ("k_min", "k_max")

    if set(bounds.keys()) != set(mappings.keys()):
        raise ValueError("Missing or unexpected constraint_bounds.")

    for group, (min_key, max_key) in mappings.items():

        group_bounds = bounds[group]

        if not isinstance(group_bounds, dict):
            raise ValueError(f"Invalid constraint_bounds.{group}")

        if set(group_bounds.keys()) != {"min", "max"}:
            raise ValueError(f"Invalid boundaries for {group}.")

        minimum = group_bounds["min"]
        maximum = group_bounds["max"]

        for value in (minimum, maximum):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    f"Invalid numerical boundaries for {group}."
                )

        if minimum > maximum:
            raise ValueError(f"Invalid boundaries for {group}.")

        if min_key not in params or max_key not in params:
            raise ValueError(f"Missing parameters for {group}.")

        if params[min_key] != minimum:
            raise ValueError(f"{min_key} does not match constraint_bounds.")

        if params[max_key] != maximum:
            raise ValueError(f"{max_key} does not match constraint_bounds.")

    # -------------------------------------------------
    # TEXTUAL CONSTRAINT VALIDATION
    # -------------------------------------------------

    normalized_constraints = [
        re.sub(r"\s+", "", constraint).lower()
        .replace("≤", "<=").replace("≥", ">=").replace("−", "-").replace("`", "")
        for constraint in constraints
        if isinstance(constraint, str)
    ]

    if len(normalized_constraints) != len(constraints):
        raise ValueError("Every constraint must be a string.")

    # Expand common integer powers without evaluating arbitrary expressions.
    normalized_constraints = [
        re.sub(
            r"(?<![\w.])10(?:\^|\*\*)\{?([0-9]{1,2})\}?(?![0-9])",
            lambda match: str(10 ** int(match.group(1))),
            constraint,
        )
        for constraint in normalized_constraints
    ]

    normalized_constraints = [
        re.sub(r"(?<![\w.])([+-]?\d+)[e]\+?([0-9]{1,2})(?![0-9])",
               lambda match: str(int(match.group(1)) * 10 ** int(match.group(2))), constraint)
        for constraint in normalized_constraints
    ]

    # Mathematical subscripts are equivalent to indexed array notation.
    # Normalize only clear indices; scalar names such as value_min stay scalar.
    normalized_constraints = [
        re.sub(
            r"\b([a-z][a-z0-9_]*?)_(?:\{([a-z0-9_+\-]+)\}|([ij]|[0-9]+))(?![a-z0-9_])",
            lambda match: f"{match.group(1)}[{match.group(2) or match.group(3)}]",
            constraint,
        )
        for constraint in normalized_constraints
    ]

    parsed_bounds = {}

    # N boundary: supports n and len(array)
    n_patterns = [
        r"(-?\d+)<=n<=(-?\d+)",
        r"(-?\d+)<=len\([a-z_][a-z0-9_]*\)<=(-?\d+)"
    ]

    # K boundary
    k_pattern = r"(-?\d+)<=k<=(-?\d+)"

    # Indexed array values may use i, i-1, a numeric index, or brackets
    # wrapped in Markdown. Parse their mathematical bounds, never declared defaults.
    element = r"[a-z_][a-z0-9_]*\[[a-z0-9_+\-]+\]"
    integer = r"(-?\d+)(?![\d.e^*])"
    value_pattern = rf"{integer}<=({element})<={integer}"
    reversed_value_pattern = rf"{integer}>=({element})>={integer}"
    absolute_value_pattern = rf"(?:\|({element})\||abs\(({element})\))<={integer}"
    separate_value_pattern = rf"({element})(>=|<=){integer}"
    separate_reversed_pattern = rf"{integer}(>=|<=)({element})"

    # Parse N boundaries
    for constraint in normalized_constraints:

        for pattern in n_patterns:

            match = re.search(pattern, constraint)

            if match:
                parsed_bounds["n"] = (
                    int(match.group(1)),
                    int(match.group(2))
                )
                break

        if "n" in parsed_bounds:
            break

    # Parse K boundaries
    for constraint in normalized_constraints:

        match = re.search(k_pattern, constraint)

        if match:
            parsed_bounds["k"] = (
                int(match.group(1)),
                int(match.group(2))
            )
            break

    # Collect intervals per element, then intersect all explicit restrictions.
    # This also catches conflicting declarations instead of accepting the first.
    value_intervals = {}
    def add_value_bound(variable, lower=None, upper=None):
        interval = value_intervals.setdefault(variable, [None, None])
        if lower is not None:
            interval[0] = lower if interval[0] is None else max(interval[0], lower)
        if upper is not None:
            interval[1] = upper if interval[1] is None else min(interval[1], upper)

    for constraint in normalized_constraints:
        for match in re.finditer(value_pattern, constraint):
            add_value_bound(match.group(2), int(match.group(1)), int(match.group(3)))
        for match in re.finditer(reversed_value_pattern, constraint):
            add_value_bound(match.group(2), int(match.group(3)), int(match.group(1)))
        for match in re.finditer(absolute_value_pattern, constraint):
            limit = int(match.group(3))
            if limit < 0:
                raise ValueError("Absolute value constraint cannot have a negative upper bound.")
            add_value_bound(match.group(1) or match.group(2), -limit, limit)
        for match in re.finditer(separate_value_pattern, constraint):
            value = int(match.group(3))
            add_value_bound(match.group(1), lower=value if match.group(2) == ">=" else None,
                            upper=value if match.group(2) == "<=" else None)
        for match in re.finditer(separate_reversed_pattern, constraint):
            value = int(match.group(1))
            add_value_bound(match.group(3), lower=value if match.group(2) == "<=" else None,
                            upper=value if match.group(2) == ">=" else None)

    complete_intervals = [tuple(interval) for interval in value_intervals.values() if None not in interval]
    if complete_intervals:
        if len(set(complete_intervals)) != 1:
            raise ValueError("Conflicting textual constraint bounds for value.")
        parsed_bounds["value"] = complete_intervals[0]

    # Compare extracted boundaries with declared bounds
    for group in mappings:

        if group not in parsed_bounds:
            raise ValueError(
                f"Cannot extract textual constraint bounds for {group}. "
                f"Use explicit integer inequalities such as -1000 <= arr[i] <= 1000. "
                f"Received: {constraints!r}"
            )

        textual_min, textual_max = parsed_bounds[group]

        expected_min = bounds[group]["min"]
        expected_max = bounds[group]["max"]

        if (
                textual_min != expected_min
                or textual_max != expected_max
        ):
            raise ValueError(
                f"Textual constraints do not match constraint_bounds for {group}."
            )
    print(
        "[VALIDATOR] Stress parameters and textual constraints match."
    )

    return True

def validate_question_structure(result):

    if not isinstance(result, dict):

        raise ValueError(
            "Generated response must be a JSON object."
        )

    # -----------------------------------------------------
    # REQUIRED FIELDS
    # -----------------------------------------------------

    missing_fields = [
        field
        for field in REQUIRED_FIELDS
        if field not in result
    ]

    if missing_fields:

        raise ValueError(
            f"Missing required fields: {missing_fields}"
        )

    # -----------------------------------------------------
    # NON-EMPTY FIELDS
    # -----------------------------------------------------

    for field in REQUIRED_FIELDS:

        value = result[field]

        if value is None:

            raise ValueError(
                f"Field '{field}' cannot be null."
            )

        if isinstance(value, str) and not value.strip():

            raise ValueError(
                f"Field '{field}' cannot be empty."
            )

    # -----------------------------------------------------
    # LIST VALIDATION
    # -----------------------------------------------------

    list_fields = [
        "topics",
        "constraints",
        "examples",
        "test_cases",
        "verification_test_cases"
    ]

    for field in list_fields:

        if not isinstance(result[field], list):

            raise ValueError(
                f"Field '{field}' must be a list."
            )

    if not result["topics"]:

        raise ValueError("At least one topic is required.")

    if not result["constraints"]:

        raise ValueError("At least one constraint is required.")

    # -----------------------------------------------------
    # SOLUTION PYTHON SYNTAX VALIDATION
    # -----------------------------------------------------

    validate_python_code(
        result["reference_solution"],
        "reference_solution",
        require_print=True
    )

    validate_python_code(
        result["brute_force_solution"],
        "brute_force_solution",
        require_print=True
    )

    # -----------------------------------------------------
    # TEST CASE COUNT VALIDATION
    # -----------------------------------------------------

    if len(result["test_cases"]) < 5:

        raise ValueError(
            "At least 5 test cases are required."
        )

    if len(result["verification_test_cases"]) < 5:

        raise ValueError(
            "At least 5 verification test cases are required."
        )

    if len(result["examples"]) < 2:

        raise ValueError(
            "Expected at least 2 examples."
        )

    # -----------------------------------------------------
    # TEST CASE STRUCTURE
    # -----------------------------------------------------

    for field in [
        "test_cases",
        "verification_test_cases"
    ]:

        for index, case in enumerate(
            result[field],
            start=1
        ):

            if not isinstance(case, dict):

                raise ValueError(
                    f"{field}[{index - 1}] must be an object."
                )

            if (
                "input" not in case
                or "expected_output" not in case
            ):

                raise ValueError(
                    f"{field}[{index - 1}] must contain "
                    "'input' and 'expected_output'."
                )

            if (
                not isinstance(case["input"], str)
                or not case["input"].strip()
            ):

                raise ValueError(
                    f"{field}[{index - 1}] has invalid input."
                )

            if not isinstance(case["expected_output"], str):

                raise ValueError(
                    f"{field}[{index - 1}] has invalid expected_output."
                )

    # -----------------------------------------------------
    # EXAMPLE VALIDATION
    # -----------------------------------------------------

    for index, example in enumerate(
        result["examples"],
        start=1
    ):

        if not isinstance(example, dict):

            raise ValueError(
                f"Example {index} must be an object."
            )

        for field in [
            "input",
            "output",
            "explanation"
        ]:

            if field not in example:

                raise ValueError(
                    f"Example {index} is missing '{field}'."
                )

            if (
                not isinstance(example[field], str)
                or not example[field].strip()
            ):

                raise ValueError(
                    f"Example {index} has an invalid '{field}'."
                )

    # -----------------------------------------------------
    # TEXTUAL METADATA
    # -----------------------------------------------------

    text_fields = [
        "title",
        "difficulty",
        "description",
        "input_format",
        "output_format",
        "time_complexity",
        "space_complexity"
    ]

    for field in text_fields:

        if (
            not isinstance(result[field], str)
            or not result[field].strip()
        ):

            raise ValueError(
                f"Field '{field}' must be a non-empty string."
            )

    # -----------------------------------------------------
    # TOPIC AND CONSTRAINT TYPES
    # -----------------------------------------------------

    for topic in result["topics"]:

        if not isinstance(topic, str) or not topic.strip():

            raise ValueError(
                "Every topic must be a non-empty string."
            )

    for constraint in result["constraints"]:

        if (
            not isinstance(constraint, str)
            or not constraint.strip()
        ):

            raise ValueError(
                "Every constraint must be a non-empty string."
            )

    # -----------------------------------------------------
    # STRESS SPECIFICATION CONSISTENCY
    # -----------------------------------------------------

    validate_stress_spec_constraints(
        result["constraints"],
        result["stress_test_spec"]
    )

    # =====================================================
    # INDEPENDENT VERIFICATION STRUCTURE
    # =====================================================

    verification = result["verification_approach"]

    if not isinstance(verification, dict):

        raise ValueError(
            "verification_approach must be a dictionary."
        )

    required_verification_fields = [
        "algorithm",
        "independent_oracle"
    ]

    for field in required_verification_fields:

        if field not in verification:

            raise ValueError(
                f"verification_approach missing '{field}'."
            )

        if (
            not isinstance(verification[field], str)
            or not verification[field].strip()
        ):

            raise ValueError(
                f"verification_approach.{field} "
                "must be a non-empty string."
            )

    # -----------------------------------------------------
    # ORACLE PYTHON SYNTAX VALIDATION
    # -----------------------------------------------------

    validate_python_code(
        verification["independent_oracle"],
        "independent_oracle",
        require_print=True
    )

    # -----------------------------------------------------
    # ORACLE INDEPENDENCE CHECK
    # -----------------------------------------------------

    validate_oracle_independence(
        result["brute_force_solution"],
        result["reference_solution"],
        verification["independent_oracle"]
    )

    print(
        "[GENERATOR] Optimized, brute-force and oracle "
        "Python syntax validated."
    )

    return True

# =========================================================
# GENERATION PROMPT
# =========================================================

# =========================================================
# MODULAR GENERATION PROMPTS
# =========================================================

def build_core_prompt(topics, difficulty):

    return f"""
You are an expert competitive programming problem setter.

Generate ONE original DSA problem.

Topics: {topics}
Difficulty: {difficulty}

Return one valid JSON object with EXACTLY these fields:

title, difficulty, topics, description, input_format,
output_format, constraints, examples, reference_solution,
brute_force_solution, time_complexity, space_complexity,
brute_force_complexity, stress_test_spec.

REQUIREMENTS:

1. Create an original, unambiguous problem.
2. Both solutions must solve exactly the same problem.
3. Optimized solution must satisfy the constraints.
4. Brute-force solution must use a simpler approach.
5. Both solutions must be complete executable Python 3 programs.
6. Both programs must read stdin and print stdout.
7. Include at least 2 correct examples with explanations.
8. Handle duplicates, negative values and boundary cases where relevant.
9. Derive complexity from the actual implementation.
10. Use only these complexity formats:
    O(1), O(log n), O(n), O(n log n),
    O(n^2), O(n^3), O(2^n), O(n!).

ALGORITHM RULES:

- Binary search: use only when the predicate is monotonic.
- Sliding window: ensure pointer movements preserve the window invariant.
- Greedy: justify the optimal choice.
- Prefix sums: handle indexing and boundaries correctly.
- Hashing: handle duplicate frequencies correctly.
- Cross-check optimized and brute-force logic on small inputs.

STRESS TEST SPECIFICATION:

Only supported generator types:
- array_n: input contains N followed by exactly N array integers.
- array_n_k: input contains N and K followed by exactly N array integers.
INPUT CONTRACT — mandatory, even when the history contains Tree/Graph topics:
Every combination of N, optional K, and N integer values inside the declared
independent numerical bounds must be a VALID problem input.
Do not require parent arrays, edge lists, a valid rooted tree, connectivity,
permutations, distinctness, sortedness, null markers or index-dependent bounds
such as P[i] < i. The stress generator cannot enforce those structures.
For Tree topics, use N arbitrary node weights in an implicitly COMPLETE BINARY
TREE (parent of node i is floor(i/2)), or a tree deterministically derived from
ANY integer array (e.g. a Cartesian tree with an explicit duplicate tie rule).
For Graph topics, use an implicit graph whose edges are defined by indices,
not supplied by the user. Keep the learning topic but adapt its representation.
Never invent fake value bounds to hide a structurally unsupported problem.

If the problem needs any additional scalar (K, target, modulus, etc.),
choose array_n_k and call that scalar K. Match every example to this layout.

Include:
- generator_type
- input_layout
- parameters
- constraint_bounds

For array_n, parameters must contain:
n_min, n_max, value_min, value_max.

For array_n_k, parameters must contain:
n_min, n_max, k_min, k_max,
value_min, value_max.

constraint_bounds must contain matching numerical
min/max values for n, value and k where applicable.

All boundaries must exactly match the actual problem constraints.
Write textual bounds as literal decimal integer inequalities:
"1 <= n <= 100000", "1 <= k <= 100", "-1000 <= arr[i] <= 1000".
Use n, k and arr[i] as applicable, and include both lower and upper bounds.
Do not generate unsupported input structures.

OUTPUT FORMAT:

{{
    "title": "...",
    "difficulty": "{difficulty}",
    "topics": [],
    "description": "...",
    "input_format": "...",
    "output_format": "...",
    "constraints": [],
    "examples": [
        {{"input": "...", "output": "...", "explanation": "..."}},
        {{"input": "...", "output": "...", "explanation": "..."}}
    ],
    "reference_solution": "...",
    "brute_force_solution": "...",
    "time_complexity": "O(n)",
    "brute_force_complexity": "O(n^2)",
    "space_complexity": "O(n)",
    "stress_test_spec": {{
        "generator_type": "array_n",
        "input_layout": "N followed by N array elements",
        "parameters": {{
            "n_min": 1,
            "n_max": 100000,
            "value_min": -100000,
            "value_max": 100000
        }},
        "constraint_bounds": {{
            "n": {{"min": 1, "max": 100000}},
            "value": {{"min": -100000, "max": 100000}}
        }}
    }}
}}

The JSON above is an example. Generate boundaries
appropriate to the actual problem.

Return ONLY valid JSON. No Markdown.
"""

# =========================================================
# SOLUTION AUDIT PROMPT
# =========================================================

def build_audit_prompt(core):

    problem_data = {
        "title": core["title"],
        "difficulty": core["difficulty"],
        "topics": core["topics"],
        "description": core["description"],
        "constraints": core["constraints"],
        "examples": core["examples"],
        "optimized_solution": core["reference_solution"],
        "brute_force_solution": core["brute_force_solution"],
        "time_complexity": core["time_complexity"],
        "space_complexity": core["space_complexity"]
    }

    problem_json = json.dumps(
        problem_data,
        separators=(",", ":"),
        ensure_ascii=False
    )

    return f"""
You are a rigorous competitive programming correctness auditor.

Audit the problem statement and BOTH implementations independently.

PROBLEM AND SOLUTIONS:

{problem_json}

1. MATHEMATICAL CORRECTNESS

- Derive the mathematical definition of the required answer.
- Verify that both algorithms implement this definition.
- Never assume the optimized solution is correct.
- Never assume the brute-force solution is correct.
- Check negative numbers, zero, duplicates and boundary values.
- Identify assumptions that are not guaranteed by constraints.

2. SLIDING WINDOW VERIFICATION

If the optimized solution uses sliding window:

- Prove that expanding and shrinking the window preserves correctness.
- Verify whether the objective function is monotonic.
- Check whether negative array elements invalidate greedy shrinking.
- Verify that every potentially optimal subarray is considered.
- Check whether a shorter valid window can have a better sum.
- If correctness cannot be mathematically established, return FAIL.

3. OTHER ALGORITHM VERIFICATION

- Binary Search: Prove predicate monotonicity.
- Greedy: Establish optimality.
- Prefix Sum: Verify indexing and boundaries.
- Hashing: Verify duplicate handling.
- Dynamic Programming: Verify state transitions and base cases.
- Trees and Graphs: Verify traversal and visited-state handling.

4. COUNTEREXAMPLE ANALYSIS

- Construct small counterexamples wherever necessary.
- Prefer arrays of length 1 to 6 for array problems.
- Include negative, zero and duplicate values.
- Manually calculate the expected result.
- Compare both implementations against the mathematical result.

5. COMPLEXITY VERIFICATION

Verify actual time and auxiliary space complexity.

6. PASS / FAIL RULES

Return FAIL if:

- Either solution is logically incorrect.
- An algorithm relies on an unproven assumption.
- An edge case violates correctness.
- The optimized solution cannot satisfy the constraints.

Return PASS only if both implementations are mathematically correct.

optimized_analysis, brute_force_analysis, complexity_analysis and
correction_guidance must each be non-empty JSON strings, never objects or lists.
Keep each analysis concise (at most 120 words); report concrete issues and small counterexamples.
For PASS, use "No corrections required." as correction_guidance.
Always explain time and space complexity in complexity_analysis.

An explanation that merely sounds convincing is NOT proof of correctness.

Return ONLY valid JSON:

{{
    "status": "PASS or FAIL",
    "optimized_analysis": "...",
    "brute_force_analysis": "...",
    "complexity_analysis": "...",
    "issues": [],
    "counterexamples": [],
    "correction_guidance": "..."
}}
"""

def build_solution_correction_prompt(core, audit):

    return f"""
You are a senior competitive programming algorithm engineer.

The following problem failed a rigorous correctness audit.

ORIGINAL PROBLEM AND SOLUTIONS:

{json.dumps(core, separators=(",", ":"), ensure_ascii=False)}

AUDIT REPORT:

{json.dumps(audit, separators=(",", ":"), ensure_ascii=False)}

YOUR TASK:

Correct every logical error identified in the audit.

MATHEMATICAL CORRECTION REQUIREMENTS:

1. Derive the correct mathematical definition of the answer.
2. Identify why the existing optimized algorithm fails.
3. Examine every counterexample in the audit report.
4. Do not preserve an incorrect algorithm merely to retain its structure.
5. Handle negative numbers, zero, duplicates and boundary cases.
6. Ensure the optimized solution is correct for ALL valid inputs.
7. Ensure brute-force solution directly implements the mathematical definition.
8. Independently verify both corrected implementations.
9. Do not assume that the audit report is infallible.
10. If the problem statement itself is ambiguous, preserve it and report the ambiguity rather than silently changing its meaning.

ALGORITHM-SPECIFIC RULES:

- Sliding Window: Never use ordinary shrinking logic for a maximum-sum objective with negative values without proving correctness.
- Binary Search: Prove predicate monotonicity.
- Greedy: Establish an optimality argument.
- Dynamic Programming: Verify state transitions and base cases.
- Prefix Sum: Verify indexing and boundary conditions.

STRICT MODIFICATION RULES:

1. Do NOT modify title.
2. Do NOT modify difficulty.
3. Do NOT modify topics.
4. Do NOT modify description.
5. Do NOT modify input_format or output_format.
6. Do NOT modify constraints or examples.
7. Modify only:
   reference_solution,
   brute_force_solution,
   time_complexity,
   space_complexity,
   brute_force_complexity.
8. Preserve stress_test_spec.
9. Return ONLY the five editable fields listed above as a JSON patch.
   Do not return title, difficulty, topics, description, input_format,
   output_format, constraints, examples or stress_test_spec.
   The backend copies these immutable fields from the original problem.

COMPLEXITY NOTATION:

Use only:
O(1), O(log n), O(n), O(n log n),
O(n^2), O(n^3), O(2^n), O(n!)

JSON REQUIREMENTS:

- Return valid JSON only.
- Do not include Markdown code fences.
- Include every editable field, with complete executable solution code.
- Complexity fields must be strings.

REQUIRED RESPONSE FIELDS (and no others):
reference_solution, brute_force_solution,
time_complexity, space_complexity, brute_force_complexity.

Return ONLY the corrected JSON.
"""

# =========================================================
# SOLUTION AUDIT
# =========================================================

def validate_solution_audit_response(audit):
    """Reject malformed audit reports before the phase retry budget is exhausted."""

    # Validate response type
    if not isinstance(audit, dict):
        raise ValueError(
            "Solution audit response must be a JSON object."
        )

    # Validate required fields
    required_fields = [
        "status",
        "optimized_analysis",
        "brute_force_analysis",
        "complexity_analysis",
        "issues",
        "counterexamples",
        "correction_guidance"
    ]

    missing_fields = [
        field for field in required_fields
        if field not in audit
    ]

    if missing_fields:
        raise ValueError(
            f"Solution audit missing fields: {missing_fields}"
        )

    # Validate status
    if audit["status"] not in ["PASS", "FAIL"]:
        raise ValueError("Invalid audit status.")

    # Validate textual fields
    text_fields = [
        "optimized_analysis",
        "brute_force_analysis",
        "complexity_analysis",
        "correction_guidance"
    ]

    for field in text_fields:
        if not isinstance(audit[field], str) or not audit[field].strip():
            raise ValueError(
                f"Invalid solution audit field: {field}"
            )

    # Validate list fields
    for field in ["issues", "counterexamples"]:
        if not isinstance(audit[field], list):
            raise ValueError(
                f"Solution audit field '{field}' must be a list."
            )

    if audit["status"] == "PASS" and audit["issues"]:
        raise ValueError(
            "Audit cannot PASS while reporting unresolved issues."
        )


def audit_generated_solutions(core):

    print("\n========== SOLUTION AUDIT ==========")

    if not isinstance(core, dict):
        raise ValueError("Core problem data must be a dictionary.")

    prompt = build_audit_prompt(core)

    audit = generate_phase_json(
        prompt,
        "Solution Audit",
        max_attempts=2,
        validator=validate_solution_audit_response
    )

    validate_solution_audit_response(audit)

    print("\nAudit Status:", audit["status"])
    print("\nOptimized Analysis:", audit["optimized_analysis"])
    print("\nBrute Force Analysis:", audit["brute_force_analysis"])
    print("\nComplexity Analysis:", audit["complexity_analysis"])
    print("\nIssues:", audit["issues"])

    return audit

def build_oracle_prompt(core):

    core_data = {
        "title": core.get("title", ""),
        "description": core.get("description", ""),
        "input_format": core.get("input_format", ""),
        "output_format": core.get("output_format", ""),
        "constraints": core.get("constraints", []),
        "examples": core.get("examples", []),
        "optimized_solution": core.get("reference_solution", ""),
        "brute_force_solution": core.get("brute_force_solution", "")
    }

    problem_json = json.dumps(
        core_data,
        separators=(",", ":"),
        ensure_ascii=False
    )

    return f"""
You are an expert competitive programming oracle.

Analyze the problem and both provided solutions:

{problem_json}

Your task:

1. Independently derive the correct expected output for every test case.
2. Verify the optimized solution against the problem statement.
3. Verify the brute-force solution independently.
4. Check edge cases, duplicates, negative values, and boundary conditions.
5. Do not assume either solution is correct.
6. Do not invent expected outputs.
7. Ensure all outputs follow the exact problem requirements.

MATHEMATICAL SELF-VERIFICATION:

1. Independently derive the expected output mathematically.
2. Verify the result using a separate calculation or reasoning path.
3. Cross-check the derived result against both implementations.
4. If the results disagree, investigate before producing the output.
5. Never blindly trust either provided solution.
6. Manually trace the algorithm step by step using the given input.
7. Correctness is more important than speed or generating an output quickly.
8. Use an independent_oracle to derive expected outputs without relying on either provided solution.
9. Interpret all test cases using standard input and derive outputs according to the problem's input format.

ORACLE REQUIREMENTS:

1. Derive the solution independently from the problem statement.
2. Do not call or copy the optimized solution.
3. Do not call or copy the brute-force solution.
4. Implement a complete standalone Python 3 program.
5. Read input from standard input.
6. Print output to standard output.
7. Follow the exact input/output format.
8. Use a fundamentally different approach wherever possible.
9. Do not generate expected_outputs. Python will calculate
   expected outputs by executing the oracle.
   
Return ONLY valid JSON in this format:

{{
    "algorithm": "Explain the independent mathematical approach.",
    "independent_oracle": "Complete executable Python 3 program."
}}
"""

def build_test_cases_prompt(core):

    problem_data = {
        "title": core["title"],
        "description": core["description"],
        "input_format": core["input_format"],
        "output_format": core["output_format"],
        "constraints": core["constraints"],
        "examples": core["examples"]
    }

    return f"""
You are an expert competitive programming test engineer.

PROBLEM:
{json.dumps(problem_data, separators=(",", ":"), ensure_ascii=False)}

TASK:
Generate exactly:
- 10 normal test cases.
- 15 verification test cases.

REQUIREMENTS:
1. Every input must be a complete, valid input string.
2. Every expected_output must be an empty string.
3. Do not calculate expected outputs.
4. Follow the exact input format and constraints.
5. Avoid duplicate inputs.
6. Include boundary cases, edge cases, duplicates,
   minimum/maximum values and varied patterns.
7. Verification cases must be small enough for brute-force execution.
8. Do not generate stress-test inputs.
9. Do not repeat the provided examples.
10. Use literal strings only. No Python or JavaScript expressions,
    concatenation, multiplication, repeat(), trim(), placeholders or ellipses.
11. Keep every input small (at most 20 elements when allowed by constraints).
    Large-scale performance is tested separately with generated stress tests.
12. Count the completed entries before returning: exactly 10 in test_cases
    and exactly 15 in verification_test_cases. Do not stop at 14.

STRICT JSON:
- Return ONLY valid JSON.
- No Markdown or explanations.
- Represent line breaks using escaped \\n.
- Do not include trailing commas.

OUTPUT:
{{
    "test_cases": [
        {{"input": "...", "expected_output": ""}}
    ],
    "verification_test_cases": [
        {{"input": "...", "expected_output": ""}}
    ]
}}

Verify exactly 10 normal cases and 15 verification cases.
"""

# =========================================================
# MODULAR GROQ INVOCATION
# =========================================================
def generate_phase_json(
    prompt,
    phase_name,
    max_attempts=2,
    validator=None
):

    last_error = None
    max_rate_retries = 3

    for attempt in range(1, max_attempts + 1):

        print(
            f"\n[GENERATOR] {phase_name}: "
            f"Attempt {attempt}/{max_attempts}"
        )

        current_prompt = prompt

        if last_error:
            current_prompt += f"""

Your previous response failed validation:

{str(last_error)[:500]}

Correct ALL identified issues.

Return the complete corrected JSON.
Do not omit any required fields.
Return ONLY valid JSON.
"""

        response = None

        # -----------------------------------------
        # GROQ API REQUEST + RATE LIMIT HANDLING
        # -----------------------------------------

        for rate_attempt in range(max_rate_retries + 1):

            try:
                response = invoke_budgeted(
                    generator_llm, current_prompt, phase_name,
                    max_output_tokens={"Solution Audit":1800, "Oracle Generation":2500,
                                       "Test Case Generation":2500}.get(phase_name,3500)
                )
                break

            except Exception as error:

                error_message = str(error)

                status_code = getattr(
                    error,
                    "status_code",
                    None
                )

                if status_code is None and getattr(
                    error, "response", None
                ):
                    status_code = getattr(
                        error.response,
                        "status_code",
                        None
                    )

                # Request too large
                if (
                    status_code == 413
                    or "request too large" in error_message.lower()
                ):
                    raise RuntimeError(
                        f"{phase_name}: Request too large. "
                        "Reduce prompt size or output tokens."
                    ) from error

                # Rate limit handling
                if status_code == 429:

                    if rate_attempt >= max_rate_retries:
                        raise RuntimeError(
                            f"{phase_name}: Groq rate limit exceeded "
                            f"after {max_rate_retries} retries."
                        ) from error

                    match = re.search(
                        r"try again in ([\d.]+)s",
                        error_message,
                        re.IGNORECASE
                    )

                    if match:
                        wait_time = max(float(match.group(1)) + 2, 10 * (2 ** rate_attempt))
                    else:
                        wait_time = min(
                            10 * (2 ** rate_attempt),
                            40
                        )

                    print(
                        f"[GENERATOR] Rate limit reached. "
                        f"Retrying in {wait_time:.2f}s..."
                    )

                    time.sleep(wait_time)
                    continue

                raise

        if response is None:
            raise RuntimeError(
                f"{phase_name}: Groq returned no response."
            )

        # -----------------------------------------
        # RESPONSE DEBUG
        # -----------------------------------------

        print("\n========== GROQ DEBUG ==========")
        print(
            "Response Metadata:",
            response.response_metadata
        )
        print(
            "Usage Metadata:",
            response.usage_metadata
        )
        print("================================\n")

        # -----------------------------------------
        # JSON PARSING + PHASE VALIDATION
        # -----------------------------------------

        try:

            result = parse_response(response)

            if not isinstance(result, dict):
                raise ValueError(
                    "Groq response must be a JSON object."
                )

            # Execute phase-specific validation
            if validator is not None:
                validator(result)

            print(
                f"[GENERATOR] {phase_name} "
                "completed and validated successfully."
            )

            return result

        except Exception as error:

            last_error = error

            print(
                f"[GENERATOR] {phase_name} validation failed: "
                f"{str(error)[:300]}"
            )

            if attempt == max_attempts:
                break

    raise ValueError(
        f"{phase_name} failed after {max_attempts} attempts. "
        f"Last error: {last_error}"
    )


# =========================================================
# PHASE VALIDATION
# =========================================================


def validate_stress_test_spec(spec):

    if not isinstance(spec, dict):
        raise ValueError("stress_test_spec must be a dictionary.")

    required_fields = {
        "generator_type",
        "input_layout",
        "parameters"
    }

    if not required_fields.issubset(spec.keys()):
        raise ValueError("Missing fields in stress_test_spec.")

    allowed_types = {
        "array_n_k",
        "array_n"
    }

    generator_type = spec["generator_type"]

    if generator_type not in allowed_types:
        raise ValueError(
            f"Unsupported generator type: {generator_type}"
        )

    if not isinstance(spec["input_layout"], str) or not spec["input_layout"].strip():
        raise ValueError("Invalid input_layout.")

    params = spec["parameters"]

    if not isinstance(params, dict):
        raise ValueError("parameters must be a dictionary.")

    if not params:
        raise ValueError("parameters cannot be empty.")

    for key, value in params.items():

        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"Invalid parameter: {key}")

    if "n_min" in params and "n_max" in params:

        if params["n_min"] < 1 or params["n_min"] > params["n_max"]:
            raise ValueError("Invalid N boundaries.")

    if "value_min" in params and "value_max" in params:

        if params["value_min"] > params["value_max"]:
            raise ValueError("Invalid value boundaries.")

    if generator_type == "array_n_k":

        required_params = {
            "n_min", "n_max",
            "k_min", "k_max",
            "value_min", "value_max"
        }

        if not required_params.issubset(params.keys()):
            raise ValueError(
                "Missing parameters for array_n_k generator."
            )

        if params["k_min"] > params["k_max"]:
            raise ValueError("Invalid K boundaries.")

    return True


def validate_stress_input_layout(core):
    """Ensure the declared generator can reproduce the examples' input shape."""
    generator_type = core["stress_test_spec"]["generator_type"]
    header_size = 2 if generator_type == "array_n_k" else 1
    for index, example in enumerate(core["examples"], start=1):
        try:
            tokens = list(map(int, example["input"].split()))
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise ValueError(f"Example {index} must contain integer array input.") from error
        if not tokens or tokens[0] < 1 or len(tokens) != tokens[0] + header_size:
            raise ValueError(
                f"Example {index} input does not match {generator_type}: "
                "use array_n for N plus N values; array_n_k for N, K plus N values."
            )


def validate_core_response(core):
    if not isinstance(core, dict):
        raise ValueError("Core response must be a dictionary.")
    required = [
        "title",
        "difficulty",
        "topics",
        "description",
        "input_format",
        "output_format",
        "constraints",
        "examples",
        "reference_solution",
        "brute_force_solution",
        "time_complexity",
        "space_complexity",
        "stress_test_spec",
        "brute_force_complexity"
    ]


    missing = [
        field for field in required
        if field not in core
    ]

    if missing:
        raise ValueError(
            f"Core generation missing fields: {missing}"
        )

    empty = [
        field for field in required
        if field != "brute_force_complexity"
           and (
                   core[field] is None
                   or (
                           isinstance(core[field], str)
                           and not core[field].strip()
                   )
           )
    ]

    if empty:
        raise ValueError(
            f"Core generation contains empty fields: {empty}"
        )

    if not isinstance(core["brute_force_complexity"], str) or not core["brute_force_complexity"].strip():
        raise ValueError("Invalid brute_force_complexity")

    if extract_complexity_order(core["brute_force_complexity"]) is None:
        raise ValueError("Invalid brute_force_complexity notation")

    if extract_complexity_order(core["time_complexity"]) is None:
        raise ValueError("Invalid time_complexity notation")


    if not isinstance(core["examples"], list) or len(core["examples"]) < 2:
        raise ValueError("Expected at least 2 examples.")
    for index, example in enumerate(core["examples"], start=1):
        if not isinstance(example, dict) or any(
            not isinstance(example.get(key), str) or not example[key].strip()
            for key in ("input", "output", "explanation")
        ):
            raise ValueError(f"Example {index} needs non-empty input, output and explanation strings.")

    # Validate optimized solution
    validate_python_code(
        core["reference_solution"],
        "reference_solution",
        require_print=True
    )

    # Validate brute-force solution
    validate_python_code(
        core["brute_force_solution"],
        "brute_force_solution",
        require_print=True
    )

    # Validate stress-test specification
    validate_stress_test_spec(
        core["stress_test_spec"]
    )

    validate_stress_input_layout(core)

    print("[VALIDATOR] Core response validated successfully.")
    print("[VALIDATOR] Stress test specification validated.")


def validate_oracle_response(oracle, core):

    if not isinstance(oracle, dict):
        raise ValueError(
            "Oracle response must be a dictionary."
        )

    if not isinstance(core, dict):
        raise ValueError(
            "Core problem data must be a dictionary."
        )

    required_core_fields = [
        "brute_force_solution",
        "reference_solution"
    ]

    for field in required_core_fields:
        if (
            field not in core
            or not isinstance(core[field], str)
            or not core[field].strip()
        ):
            raise ValueError(
                f"Core problem missing or invalid field: {field}"
            )

    for field in ["algorithm", "independent_oracle"]:

        if (
            field not in oracle
            or not isinstance(oracle[field], str)
            or not oracle[field].strip()
        ):
            raise ValueError(
                f"Oracle response missing or invalid field: {field}"
            )

    validate_python_code(
        oracle["independent_oracle"],
        "independent_oracle",
        require_print=True
    )

    validate_oracle_independence(
        core["brute_force_solution"],
        core["reference_solution"],
        oracle["independent_oracle"]
    )

    print(
        "[GENERATOR] Oracle syntax and independence "
        "validation passed."
    )

    return True

def validate_test_case_response(test_data):

    if not isinstance(test_data, dict):
        raise ValueError(
            "Test case response must be a dictionary."
        )

    required_fields = {
        "test_cases",
        "verification_test_cases"
    }

    if set(test_data.keys()) != required_fields:
        raise ValueError(
            f"Response must contain exactly these fields: "
            f"{required_fields}"
        )

    for field, expected_count in [
        ("test_cases", 10),
        ("verification_test_cases", 15)
    ]:

        cases = test_data.get(field)

        if not isinstance(cases, list):
            raise ValueError(
                f"{field} must be a list."
            )

        if len(cases) != expected_count:
            raise ValueError(
                f"{field} must contain exactly "
                f"{expected_count} cases. "
                f"Received: {len(cases)}"
            )

        seen_inputs = set()

        for index, case in enumerate(cases):

            if not isinstance(case, dict):
                raise ValueError(
                    f"{field}[{index}] must be an object."
                )

            if set(case.keys()) != {
                "input",
                "expected_output"
            }:
                raise ValueError(
                    f"{field}[{index}] must contain "
                    f"exactly input and expected_output."
                )

            input_data = case["input"]
            expected_output = case["expected_output"]

            if not isinstance(input_data, str):
                raise ValueError(
                    f"{field}[{index}] input must be a string."
                )

            if not input_data.strip():
                raise ValueError(
                    f"{field}[{index}] input cannot be empty."
                )

            if not isinstance(expected_output, str):
                raise ValueError(
                    f"{field}[{index}] expected_output "
                    f"must be a string."
                )

            if expected_output != "":
                raise ValueError(
                    f"{field}[{index}] expected_output "
                    f"must be empty. Oracle will calculate it."
                )

            normalized_input = input_data.strip()

            if normalized_input in seen_inputs:
                raise ValueError(
                    f"{field}[{index}] contains duplicate input."
                )

            seen_inputs.add(normalized_input)

    print(
        "\n[VALIDATOR] Test case structure validated successfully."
    )

    print("[VALIDATOR] Normal cases: 10")
    print("[VALIDATOR] Verification cases: 15")
    print("[VALIDATOR] Duplicate inputs: None")
    print("[VALIDATOR] Expected outputs: All empty")

    return True


# =========================================================
# FINAL QUESTION ASSEMBLY
# =========================================================

def assemble_question(core, oracle, test_data):

    if not isinstance(core, dict):
        raise ValueError("Invalid core problem data.")

    if not isinstance(oracle, dict):
        raise ValueError("Invalid oracle data.")

    if not isinstance(test_data, dict):
        raise ValueError("Invalid test case data.")

    required_oracle = [
        "algorithm",
        "independent_oracle"
    ]

    for field in required_oracle:
        if field not in oracle:
            raise ValueError(f"Oracle missing field: {field}")

    required_test_data = [
        "test_cases",
        "verification_test_cases"
    ]

    for field in required_test_data:
        if field not in test_data:
            raise ValueError(f"Test data missing field: {field}")

    question = {
        **core,

        "test_cases": test_data["test_cases"],

        "verification_test_cases":
            test_data["verification_test_cases"],

        "verification_approach": {
            "algorithm": oracle["algorithm"],
            "independent_oracle": oracle["independent_oracle"]
        }
    }

    return question

def populate_expected_outputs(test_data, core, oracle):

    oracle_code = oracle["independent_oracle"]
    brute_force_code = core["brute_force_solution"]
    optimized_code = core["reference_solution"]

    total_cases = 0
    brute_force_checks = 0

    for category in ["test_cases", "verification_test_cases"]:

        for index, case in enumerate(test_data[category], start=1):

            input_data = case["input"]

            # 1. Execute Independent Oracle
            oracle_output, oracle_error = execute_solution(
                oracle_code, input_data
            )

            if oracle_error is not None:
                raise ValueError(
                    f"Oracle failed: {category}, "
                    f"case {index}: {oracle_error}"
                )

            # 2. Execute Optimized Solution
            optimized_output, optimized_error = execute_solution(
                optimized_code, input_data
            )

            if optimized_error is not None:
                raise ValueError(
                    f"Optimized solution failed: {category}, "
                    f"case {index}: {optimized_error}"
                )

            oracle_output = oracle_output.strip()
            optimized_output = optimized_output.strip()

            # 3. Compare Oracle and Optimized Solution
            if oracle_output != optimized_output:
                raise ValueError(
                    f"\nORACLE-OPTIMIZED VALIDATION FAILED!"
                    f"\nCategory: {category}"
                    f"\nCase: {index}"
                    f"\nInput:\n{input_data}"
                    f"\nOracle Output: {oracle_output}"
                    f"\nOptimized Output: {optimized_output}"
                )

            # 4. Execute Brute Force only on verification cases
            if category == "verification_test_cases":

                brute_output, brute_error = execute_solution(
                    brute_force_code, input_data
                )

                if brute_error is not None:
                    raise ValueError(
                        f"Brute-force failed: {category}, "
                        f"case {index}: {brute_error}"
                    )

                brute_output = brute_output.strip()

                # 5. Compare Oracle and Brute Force
                if oracle_output != brute_output:
                    raise ValueError(
                        f"\nBRUTE-FORCE VALIDATION FAILED!"
                        f"\nCategory: {category}"
                        f"\nCase: {index}"
                        f"\nInput:\n{input_data}"
                        f"\nOracle Output: {oracle_output}"
                        f"\nOptimized Output: {optimized_output}"
                        f"\nBrute Force Output: {brute_output}"
                    )

                brute_force_checks += 1

            # 6. Store Expected Output
            case["expected_output"] = oracle_output
            total_cases += 1

    print(
        f"\n[GENERATOR] Cross-validation successful: "
        f"{total_cases}/{total_cases} cases"
    )

    print(
        f"[GENERATOR] Brute-force verification: "
        f"{brute_force_checks} cases"
    )

    return test_data
def validate_supported_input_contract(core):
    """Reject structures that the independent-array stress generator cannot build."""
    constraints = core.get("constraints") or []
    contract = " ".join(str(item) for item in constraints)
    input_format = str(core.get("input_format", ""))
    # A bound tied to an index is not a global bound on independent values.
    indexed = r"(?:[a-z_][a-z0-9_]*\[[^\]]+\]|[a-z_][a-z0-9_]*_\{?[ij]\}?)"
    dependent = re.search(
        rf"{indexed}\s*(?:<=|>=|<|>|≤|≥)\s*(?:i|j|n|k)\b",
        contract, re.IGNORECASE,
    )
    structural = re.search(
        r"parent[- ]?(?:array|indices|index|list)|edge[- ]?list|(?:n\s*[-−]\s*1|n-1)\s+edges",
        input_format, re.IGNORECASE,
    )
    if dependent or structural:
        raise ValueError(
            "Unsupported input structure: parent arrays, edge lists and index-dependent "
            "value bounds cannot use the array stress generator. Discard this draft. "
            "For Tree topics, generate N independently bounded integer node weights in "
            "an implicit complete binary tree, or derive a Cartesian tree from any array. "
            "Use literal bounds such as -1000 <= arr[i] <= 1000; do not add fake bounds to this draft."
        )


def validate_generated_core_response(core):
    """Check textual bounds while a bad draft can still be corrected cheaply."""
    if isinstance(core, dict):
        validate_supported_input_contract(core)
    validate_core_response(core)
    validate_stress_spec_constraints(core["constraints"], core["stress_test_spec"])


class SolutionAuditFailure(ValueError):
    """Both audit attempts rejected a problem; retain feedback for a fresh draft."""
    def __init__(self, audit):
        self.audit = audit
        super().__init__("Solution audit failed after maximum attempts.")


SOLUTION_CORRECTION_FIELDS = (
    "reference_solution", "brute_force_solution", "time_complexity",
    "space_complexity", "brute_force_complexity",
)


def apply_solution_correction(core, correction):
    """Apply a solution-only patch; model text can never replace the statement."""
    if not isinstance(correction, dict):
        raise ValueError("Solution correction must be a JSON object.")
    missing = [field for field in SOLUTION_CORRECTION_FIELDS if field not in correction]
    if missing:
        raise ValueError(f"Solution correction missing editable fields: {missing}")
    candidate = copy.deepcopy(core)
    for field in SOLUTION_CORRECTION_FIELDS:
        candidate[field] = copy.deepcopy(correction[field])
    # Extra fields in a legacy/full-object response are deliberately ignored.
    # Audit still evaluates the corrected implementations against the ORIGINAL
    # problem and examples, so a semantic change cannot silently pass.
    validate_core_response(candidate)
    return candidate


def run_solution_audit_loop(core, max_audit_attempts=2):

    if not isinstance(core, dict):
        raise ValueError("Core problem data must be a dictionary.")

    if (
        not isinstance(max_audit_attempts, int)
        or isinstance(max_audit_attempts, bool)
        or max_audit_attempts < 1
    ):
        raise ValueError("max_audit_attempts must be a positive integer.")

    audit = None

    for attempt in range(1, max_audit_attempts + 1):

        print(
            f"\n[GENERATOR] Audit attempt "
            f"{attempt}/{max_audit_attempts}"
        )

        audit = audit_generated_solutions(core)

        if not isinstance(audit, dict):
            raise ValueError("Invalid audit response.")

        status = audit.get("status")

        if status == "PASS":
            print("[GENERATOR] Solution audit passed.")
            return core, audit

        if status != "FAIL":
            raise ValueError(f"Invalid audit status: {status}")

        print("[GENERATOR] Solution audit failed.")

        if attempt == max_audit_attempts:
            break

        print("[GENERATOR] Correcting generated solutions...")

        correction_prompt = build_solution_correction_prompt(
            core,
            audit
        )

        correction = generate_phase_json(
            correction_prompt,
            "Solution Correction",
            validator=lambda result: apply_solution_correction(core, result)
        )
        core = apply_solution_correction(core, correction)

    raise SolutionAuditFailure(audit)

# =========================================================
# MAIN QUESTION GENERATOR
# =========================================================
def generate_dsa_question(topics, difficulty="Medium", user_profile=None):

    # =====================================================
    # PHASE 1: CORE PROBLEM GENERATION
    # =====================================================

    print("\n========== PHASE 1: CORE PROBLEM ==========")

    prompt = build_core_prompt(topics, difficulty)
    if user_profile is not None:
        recent = user_profile.get("analyzed_questions", [])[:20]
        history = {
            "difficulty_distribution": user_profile.get("difficulty_distribution", {}),
            "topic_frequency": user_profile.get("topic_frequency", {}),
            "practice_plan": user_profile.get("practice_plan", {}),
            "recent_questions": [
                {"problem": question.get("title") or question.get("title_slug"),
                 "difficulty": question.get("difficulty"),
                 "topics": [topic.get("name") if isinstance(topic, dict) else topic
                            for topic in question.get("topics", [])]}
                for question in recent
            ],
        }
        prompt += (
            "\nRECENT ACCEPTED-SUBMISSION HISTORY:\n"
            + json.dumps(history, ensure_ascii=False, separators=(",", ":"))
            + "\nUse this history to create a suitable next practice problem at the selected level. "
              "Do not copy a previously solved problem. Focus on a coherent topic combination. "
              "Accepted submissions show exposure, not proven weaknesses. "
              "The supported independent-array input contract still takes priority over the "
              "formats of these past questions. Tree topics must use implicit complete trees "
              "or trees derived from arbitrary arrays, never parent arrays or supplied edges."
        )

    # An uncorrectable draft should not terminate the entire request immediately.
    # Allow one fresh problem, preserving every correctness gate and bounding cost.
    for draft_attempt in range(1, 3):
        core = generate_phase_json(
            prompt,
            "Core Problem Generation",
            validator=validate_generated_core_response
        )
        validate_generated_core_response(core)
        print("\n========== PHASE 2: SOLUTION AUDIT + CORRECTION ==========")
        try:
            core, audit = run_solution_audit_loop(core, max_audit_attempts=2)
            break
        except SolutionAuditFailure as error:
            import logging
            logging.getLogger(__name__).warning(
                "Draft %s rejected after correction | Title: %s | Audit: %s",
                draft_attempt, core.get("title"), json.dumps(error.audit, ensure_ascii=True)
            )
            if draft_attempt == 2:
                raise
            prompt += (
                "\nThe previous draft could not pass correctness auditing. "
                "Generate a DIFFERENT original problem with an easier-to-prove optimized algorithm. "
                "Keep the requested difficulty and history-based learning focus. "
                "Avoid these previous correctness issues:\n"
                + json.dumps({"previous_title": core.get("title"),
                              "issues": error.audit.get("issues", []),
                              "counterexamples": error.audit.get("counterexamples", []),
                              "correction_guidance": error.audit.get("correction_guidance", "")},
                             ensure_ascii=False, separators=(",", ":"))
            )

    # =====================================================
    # PHASE 3: INDEPENDENT ORACLE GENERATION
    # =====================================================

    print("\n========== PHASE 3: ORACLE GENERATION ==========")

    oracle = generate_phase_json(
        build_oracle_prompt(core),
        "Oracle Generation",
        validator=lambda result: validate_oracle_response(
            result,
            core
        )
    )
    validate_oracle_response(oracle, core)

    # =====================================================
    # PHASE 4: TEST CASE GENERATION
    # =====================================================

    print("\n========== PHASE 4: TEST CASE GENERATION ==========")

    test_data = generate_phase_json(
        build_test_cases_prompt(core),
        "Test Case Generation",
        max_attempts=3,
        validator=validate_test_case_response
    )

    validate_test_case_response(test_data)

    # =====================================================
    # PHASE 4.5: EXPECTED OUTPUT GENERATION
    # =====================================================

    print(
        "\n========== PHASE 4.5: "
        "ORACLE OUTPUT GENERATION =========="
    )

    test_data = populate_expected_outputs(
        test_data,
        core,
        oracle
    )

    # =====================================================
    # PHASE 5: ASSEMBLY
    # =====================================================

    print("\n========== PHASE 5: ASSEMBLY ==========")

    question = assemble_question(
        core,
        oracle,
        test_data
    )

    validate_question_structure(question)

    # Preserve stress specification
    question["stress_test_spec"] = core["stress_test_spec"]

    # =====================================================
    # PHASE 6: PROBLEM QUALITY EVALUATION
    # =====================================================

    print("\n========== PHASE 6: QUALITY EVALUATION ==========")

    quality_report = evaluate_problem_quality(
        core,
        audit
    )

    print("\nQuality Score:", quality_report["score"])
    print("Quality:", quality_report["quality"])

    print("\nStrengths:")

    for strength in quality_report["strengths"]:
        print("-", strength)

    print("\nIssues:")

    for issue in quality_report["issues"]:
        print("-", issue)

    question["quality_report"] = quality_report

    if not quality_report["is_acceptable"]:

        raise ValueError(
            "Generated question failed quality evaluation. "
            f"Score: {quality_report['score']}. "
            f"Issues: {quality_report['issues']}"
        )

    # =====================================================
    # PHASE 7: STRESS TEST GENERATION
    # =====================================================

    print("\n========== PHASE 7: STRESS TEST GENERATION ==========")

    stress_cases = generate_stress_tests(
        core["stress_test_spec"],
        count=9,
        seed=42
    )

    print(
        f"[GENERATOR] Generated {len(stress_cases)} stress cases."
    )

    # =====================================================
    # PHASE 8: STRESS TEST EXECUTION
    # =====================================================

    print("\n========== PHASE 8: STRESS TEST EXECUTION ==========")

    stress_report = run_stress_tests(
        question,
        stress_cases
    )

    question["stress_test_report"] = stress_report

    if not isinstance(stress_report, dict) or stress_report.get("is_valid") is not True:
        raise ValueError(
            "Generated question failed stress testing."
        )

    # =====================================================
    # FINAL SUCCESS
    # =====================================================

    print("\n========== GENERATION COMPLETE ==========")

    print("[GENERATOR] Solution audit passed.")
    print("[GENERATOR] Quality evaluation passed.")
    print("[GENERATOR] Stress testing passed.")

    print(
        "[GENERATOR] Complete modular generation successful."
    )

    return question

