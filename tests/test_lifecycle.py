from unittest.mock import MagicMock, patch
import pytest

from backend.services.candidate_service import update_recommendation_status


@pytest.mark.parametrize(
    "status, query_results",
    [
        ("attempted", [MagicMock(), MagicMock()]),
        ("completed", [MagicMock(), MagicMock(), None])
    ]
)
def test_update_recommendation_status(status, query_results):

    user_id = 1
    question_slug = "valid-sudoku"

    db_mock = MagicMock()
    query_mock = MagicMock()

    db_mock.query.return_value = query_mock
    query_mock.filter.return_value = query_mock
    query_mock.first.side_effect = query_results

    with patch(
        "backend.services.candidate_service.SessionLocal",
        return_value=db_mock
    ):

        result = update_recommendation_status(
            user_id,
            question_slug,
            status
        )

    assert result["success"] is True
    assert result["question_slug"] == question_slug
    assert result["status"] == status

    db_mock.commit.assert_called_once()
    db_mock.close.assert_called_once()
    db_mock.rollback.assert_not_called()

    if status == "completed":
        db_mock.add.assert_called_once()
    else:
        db_mock.add.assert_not_called()


def test_update_recommendation_status_invalid_status():

    with pytest.raises(ValueError, match="Invalid status"):
        update_recommendation_status(
            1,
            "valid-sudoku",
            "invalid"
        )