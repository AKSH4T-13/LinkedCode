import ast
import re


# =========================================================
# COMPLEXITY EXTRACTION
# =========================================================

def extract_complexity_order(complexity):

    if not isinstance(complexity, str):
        return None

    value = complexity.upper().replace(" ", "")

    patterns = [
        (r"^O\(1\)$", 1),
        (r"^O\(LOGN\)$", 2),
        (r"^O\(N\)$", 3),
        (r"^O\(NLOGN\)$", 4),
        (r"^O\(N\^2\)$", 5),
        (r"^O\(N\^3\)$", 6),
        (r"^O\(2\^N\)$", 7),
        (r"^O\(N!\)$", 8)
    ]

    for pattern, rank in patterns:
        if re.fullmatch(pattern, value):
            return rank

    return None


# =========================================================
# SOLUTION STRUCTURE ANALYSIS
# =========================================================

def normalize_solution(solution):

    if not isinstance(solution, str):
        return None

    try:

        tree = ast.parse(solution)

        for node in ast.walk(tree):

            if isinstance(node, ast.Constant):
                node.value = None

        return ast.dump(
            tree,
            include_attributes=False
        )

    except SyntaxError:
        return None


# =========================================================
# PROBLEM QUALITY EVALUATOR
# =========================================================

def evaluate_problem_quality(core, audit=None):

    score = 100
    issues = []
    strengths = []

    # -----------------------------------------------------
    # 1. STRUCTURAL QUALITY
    # -----------------------------------------------------

    required_fields = [
        "title",
        "description",
        "constraints",
        "examples",
        "reference_solution",
        "brute_force_solution",
        "time_complexity",
        "space_complexity"
    ]

    for field in required_fields:

        if not core.get(field):

            score -= 15

            issues.append(
                f"Missing or empty field: {field}"
            )

    description = core.get("description", "")

    if len(description.split()) < 40:

        score -= 10

        issues.append(
            "Problem description is too short."
        )

    else:

        strengths.append(
            "Problem description has sufficient detail."
        )

    # -----------------------------------------------------
    # 2. CONSTRAINT QUALITY
    # -----------------------------------------------------

    constraints = core.get("constraints", [])

    if not isinstance(constraints, list) or not constraints:

        score -= 15

        issues.append(
            "Problem constraints are missing or invalid."
        )

    else:

        strengths.append(
            "Problem constraints are provided."
        )

    # -----------------------------------------------------
    # 3. EXAMPLE QUALITY
    # -----------------------------------------------------

    examples = core.get("examples", [])

    if not isinstance(examples, list) or len(examples) < 2:

        score -= 10

        issues.append(
            "At least two examples are recommended."
        )

    else:

        valid_examples = all(
            isinstance(example, dict)
            and example.get("input")
            and example.get("output") is not None
            and example.get("explanation")
            for example in examples
        )

        if valid_examples:

            strengths.append(
                "Examples contain input, output and explanation."
            )

        else:

            score -= 10

            issues.append(
                "Some examples have missing fields."
            )

    # -----------------------------------------------------
    # 4. OPTIMIZED VS BRUTE FORCE DISTINCTION
    # -----------------------------------------------------

    optimized = core.get("reference_solution", "")
    brute_force = core.get("brute_force_solution", "")

    optimized_ast = normalize_solution(optimized)
    brute_ast = normalize_solution(brute_force)

    if optimized_ast and brute_ast:

        if optimized_ast == brute_ast:

            score -= 30

            issues.append(
                "Optimized and brute-force solutions "
                "have identical AST structures."
            )

        else:

            strengths.append(
                "Optimized and brute-force implementations "
                "have different AST structures."
            )

    # -----------------------------------------------------
    # 5. COMPLEXITY DIFFERENCE
    # -----------------------------------------------------

    optimized_complexity = extract_complexity_order(
        core.get("time_complexity", "")
    )

    brute_complexity = extract_complexity_order(
        core.get("brute_force_complexity", "")
    )

    if (
        optimized_complexity is not None
        and brute_complexity is not None
    ):

        if optimized_complexity >= brute_complexity:

            score -= 20

            issues.append(
                "Optimized solution does not show "
                "a better asymptotic complexity."
            )

        else:

            strengths.append(
                "Optimized solution has better asymptotic complexity."
            )

    else:

        issues.append(
            "Could not reliably compare optimized and brute-force "
            "complexities."
        )

    # -----------------------------------------------------
    # 6. DIFFICULTY INDICATORS
    # -----------------------------------------------------

    difficulty = str(
        core.get("difficulty", "")
    ).lower()

    if difficulty not in ["easy", "medium", "hard"]:

        score -= 10

        issues.append(
            "Invalid difficulty label."
        )

    # -----------------------------------------------------
    # 7. AUDIT STATUS
    # -----------------------------------------------------

    if audit is not None:

        audit_status = str(
            audit.get("status", "")
        ).upper()

        if audit_status != "PASS":

            score -= 30

            issues.append(
                "Solution audit has not passed."
            )

        else:

            strengths.append(
                "Solution audit passed."
            )

    # -----------------------------------------------------
    # FINAL SCORE
    # -----------------------------------------------------

    score = max(0, min(100, score))

    if score >= 80:
        quality = "GOOD"

    elif score >= 60:
        quality = "NEEDS_IMPROVEMENT"

    else:
        quality = "POOR"

    return {
        "score": score,
        "quality": quality,
        "is_acceptable": score >= 80 and not any(
            "audit has not passed" in issue
            for issue in issues
        ),
        "strengths": strengths,
        "issues": issues
    }