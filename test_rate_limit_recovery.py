from unittest.mock import patch

import pytest
import backend.agents.question_generator as qg
from langchain_core.messages import AIMessage


class RateLimit(Exception):
    status_code = 429


def test_repeated_rate_limits_resume_same_phase():
    reply = AIMessage(content='{"ok": true}')
    with patch.object(qg, 'generator_llm') as llm, patch.object(qg.time, 'sleep') as sleep:
        llm.invoke.side_effect = [RateLimit('try again in 4s'), RateLimit('try again in 7s'), reply]
        assert qg.generate_phase_json('original prompt', 'Oracle') == {'ok': True}
        assert llm.invoke.call_count == 3
        assert [c.args[0] for c in sleep.call_args_list] == [10, 20]
        assert all(c.args[0] == 'original prompt' for c in llm.invoke.call_args_list)


def test_rate_limit_retry_budget_is_bounded():
    with patch.object(qg, 'generator_llm') as llm, patch.object(qg.time, 'sleep') as sleep:
        llm.invoke.side_effect = RateLimit('try again in 1s')
        with pytest.raises(RuntimeError, match='after 3 retries'):
            qg.generate_phase_json('prompt', 'Oracle')
        assert llm.invoke.call_count == 4
        assert sleep.call_count == 3
