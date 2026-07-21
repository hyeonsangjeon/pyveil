import asyncio
from typing import Any, Dict, List

from examples.litellm_proxy_filter import (
    PyVeilProxyHook,
    completion_with_redaction,
    redact_messages,
)
from examples.openai_agents_guardrail import prepare_agent_input, run_agent_redacted
from pyveil import Veil


def _veil(scope: str) -> Veil:
    return Veil.high(secret=b"synthetic-test-secret", scope=scope)


def test_openai_agents_input_is_redacted_before_runner() -> None:
    class FakeRunner:
        received_input: Any = None

        @classmethod
        async def run(cls, agent: Any, *, input: Any, **kwargs: Any) -> Dict[str, Any]:
            cls.received_input = input
            return {"agent": agent, "input": input, "kwargs": kwargs}

    raw_input = [{"role": "user", "content": "Email alice@example.com."}]
    result = asyncio.run(
        run_agent_redacted(
            "support-agent",
            raw_input,
            veil=_veil("agents/test"),
            runner=FakeRunner,
            max_turns=2,
        )
    )

    assert raw_input[0]["content"] == "Email alice@example.com."
    assert "alice@example.com" not in str(FakeRunner.received_input)
    assert "[EMAIL:" in str(FakeRunner.received_input)
    assert result["kwargs"] == {"max_turns": 2}


def test_openai_agents_prepare_input_preserves_message_shape() -> None:
    raw_input = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "Call 010-1234-5678."},
    ]

    safe_input = prepare_agent_input(raw_input, _veil("agents/shape"))

    assert isinstance(safe_input, list)
    assert [item["role"] for item in safe_input] == ["system", "user"]
    assert "010-1234-5678" not in str(safe_input)
    assert "[PHONE:" in str(safe_input)


def test_litellm_completion_receives_only_redacted_messages() -> None:
    captured: Dict[str, Any] = {}

    def fake_completion(**kwargs: Any) -> Dict[str, str]:
        captured.update(kwargs)
        return {"status": "ok"}

    raw_messages: List[Dict[str, Any]] = [
        {"role": "user", "content": "Email alice@example.com."}
    ]
    result = completion_with_redaction(
        model="synthetic/model",
        messages=raw_messages,
        veil=_veil("litellm/sdk"),
        completion=fake_completion,
        temperature=0,
    )

    assert result == {"status": "ok"}
    assert captured["model"] == "synthetic/model"
    assert captured["temperature"] == 0
    assert "alice@example.com" not in str(captured["messages"])
    assert "[EMAIL:" in str(captured["messages"])
    assert raw_messages[0]["content"] == "Email alice@example.com."


def test_litellm_proxy_hook_returns_redacted_payload_copy() -> None:
    hook = PyVeilProxyHook(_veil("litellm/proxy"))
    raw_data: Dict[str, Any] = {
        "model": "synthetic/model",
        "messages": [{"role": "user", "content": "Call 010-1234-5678."}],
    }

    safe_data = asyncio.run(hook.async_pre_call_hook(None, None, raw_data, "completion"))

    assert safe_data is not raw_data
    assert safe_data["model"] == raw_data["model"]
    assert "010-1234-5678" not in str(safe_data["messages"])
    assert "[PHONE:" in str(safe_data["messages"])
    assert "010-1234-5678" in str(raw_data["messages"])


def test_litellm_redact_messages_preserves_roles() -> None:
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "Email alice@example.com."},
    ]

    safe_messages = redact_messages(messages, _veil("litellm/shape"))

    assert [message["role"] for message in safe_messages] == ["system", "user"]
    assert "alice@example.com" not in str(safe_messages)
