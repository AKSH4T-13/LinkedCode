import pytest

from unittest.mock import AsyncMock, Mock

from backend.graph.workflow import build_linkedcode_graph
import backend.graph.nodes as nodes


# =========================================================
# MOCK DATA
# =========================================================

def create_initial_state():

    return {
        "user_id": 101,
        "username": "test_user"
    }


def create_mock_profile():

    return {
        "user_profile": {
            "username": "test_user",
            "total_unique_questions": 2,
            "difficulty_distribution": {
                "Easy": 1,
                "Medium": 1,
                "Hard": 0
            },
            "topic_frequency": {
                "Array": 2,
                "Hash Table": 1
            },
            "recent_topics": ["Array", "Hash Table"]
        },
        "analyzed_questions": [
            {
                "title": "Two Sum",
                "title_slug": "two-sum",
                "difficulty": "Easy",
                "topics": [
                    {"name": "Array", "slug": "array"}
                ],
                "submission_id": "101",
                "timestamp": 1700000000,
                "submitted_at": "2023-11-14T22:13:20+00:00"
            }
        ]
    }


def create_mock_candidates():

    return [
        {
            "question_id": 1,
            "title": "Two Sum",
            "difficulty": "Easy"
        },
        {
            "question_id": 2,
            "title": "Maximum Subarray",
            "difficulty": "Medium"
        }
    ]


def create_mock_recommendation():

    return {
        "question_id": 2,
        "title": "Maximum Subarray",
        "difficulty": "Medium"
    }


def create_mock_generated_question():

    return {
        "title": "Subarray Frequency",
        "difficulty": "Medium",
        "topics": ["Array"]
    }


# =========================================================
# MOCK DEPENDENCIES
# =========================================================

def setup_mocks(monkeypatch, execution_order=None):

    if execution_order is None:
        execution_order = []

    async def mock_analyze_questions(username):

        execution_order.append("profile")

        return create_mock_profile()

    async def mock_fetch_candidates(
        user_profile,
        user_id,
        max_candidates
    ):

        execution_order.append("candidates")

        assert user_id == 101
        assert user_profile["username"] == "test_user"
        assert max_candidates == 30

        return create_mock_candidates()

    def mock_recommend_question(
        user_profile,
        candidates
    ):

        execution_order.append("agent_1")

        return create_mock_recommendation()

    def mock_generate_valid_question(
        topics,
        difficulty,
        max_attempts,
        user_profile=None
    ):

        execution_order.append("agent_2")

        return {
            "status": "success",
            "question": create_mock_generated_question(),
            "validation": {
                "is_valid": True
            },
            "attempts": 1
        }

    def mock_save_recommendation(
        user_id,
        recommendation,
        db_session=None
    ):

        execution_order.append("save")

        return {
            "message": "Recommendation saved successfully."
        }

    def mock_save_generated_question(
        user_id,
        question,
        validation_report=None,
        db_session=None
    ):

        execution_order.append("save_generated")

        assert user_id == 101
        assert question == create_mock_generated_question()
        assert validation_report == {"is_valid": True}

        return {
            "saved": True,
            "generated_question_id": 1,
            "message": "Generated question saved successfully."
        }

    monkeypatch.setattr(
        nodes,
        "analyze_questions",
        mock_analyze_questions
    )

    monkeypatch.setattr(
        nodes,
        "fetch_unsolved_candidates",
        mock_fetch_candidates
    )

    monkeypatch.setattr(
        nodes,
        "recommend_question",
        mock_recommend_question
    )

    monkeypatch.setattr(
        nodes,
        "generate_valid_question",
        mock_generate_valid_question
    )

    monkeypatch.setattr(
        nodes,
        "save_recommendation",
        mock_save_recommendation
    )

    monkeypatch.setattr(
        nodes,
        "save_generated_question",
        mock_save_generated_question
    )

    return execution_order


# =========================================================
# TEST 1: GRAPH COMPILATION
# =========================================================

def test_graph_compilation():

    graph = build_linkedcode_graph()

    assert graph is not None

    assert hasattr(graph, "ainvoke")

    print("[PASS] Graph compilation successful.")


# =========================================================
# TEST 2: SEQUENTIAL NODE EXECUTION
# =========================================================

def test_sequential_execution(monkeypatch):

    execution_order = []

    setup_mocks(
        monkeypatch,
        execution_order
    )

    graph = build_linkedcode_graph()

    result = __import__("asyncio").run(
        graph.ainvoke(create_initial_state())
    )

    assert execution_order.index("profile") < (
        execution_order.index("candidates")
    )

    assert result["user_profile"]["username"] == "test_user"

    assert len(result["candidates"]) == 2

    assert "save" in execution_order
    assert "save_generated" in execution_order

    print("[PASS] Sequential execution successful.")


# =========================================================
# TEST 3: PARALLEL AGENT EXECUTION
# =========================================================

def test_parallel_agent_execution(monkeypatch):

    execution_order = []

    setup_mocks(
        monkeypatch,
        execution_order
    )

    graph = build_linkedcode_graph()

    result = __import__("asyncio").run(
        graph.ainvoke(create_initial_state())
    )

    assert "agent_1" in execution_order

    assert "agent_2" in execution_order

    assert execution_order.index("candidates") < (
        execution_order.index("agent_1")
    )

    assert execution_order.index("candidates") < (
        execution_order.index("agent_2")
    )

    print("[PASS] Both agents executed successfully.")


# =========================================================
# TEST 4: STATE MERGING AND FINAL OUTPUT
# =========================================================

def test_final_state_merging(monkeypatch):

    execution_order = []

    setup_mocks(
        monkeypatch,
        execution_order
    )

    graph = build_linkedcode_graph()

    result = __import__("asyncio").run(
        graph.ainvoke(create_initial_state())
    )

    assert "existing_recommendation" in result

    assert "generated_question" in result

    assert "validation_report" in result

    assert "final_recommendations" in result

    final_output = result["final_recommendations"]

    assert (
        final_output["existing_question"]
        == create_mock_recommendation()
    )

    assert (
        final_output["generated_question"]
        == create_mock_generated_question()
    )

    assert result["refinement_attempts"] == 1

    assert "save" in execution_order
    assert "save_generated" in execution_order

    print("[PASS] State merging successful.")


# =========================================================
# TEST 5: AGENT FAILURE PROPAGATION
# =========================================================

def test_agent_failure_propagation(monkeypatch):

    setup_mocks(monkeypatch)

    def failing_recommender(
        user_profile,
        candidates
    ):

        raise RuntimeError(
            "Simulated recommender failure."
        )

    monkeypatch.setattr(
        nodes,
        "recommend_question",
        failing_recommender
    )

    graph = build_linkedcode_graph()

    with pytest.raises(RuntimeError):

        __import__("asyncio").run(
            graph.ainvoke(create_initial_state())
        )

    print("[PASS] Agent failure propagated correctly.")