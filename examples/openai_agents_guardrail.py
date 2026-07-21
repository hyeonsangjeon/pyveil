"""Redact input before the OpenAI Agents SDK can send it to a model.

Install for a live agent run (Python 3.10+ for the current SDK):

    pip install pyveil openai-agents

The Agents SDK input guardrail API validates or blocks input; it does not
replace the input passed to the model. This wrapper redacts first and only then
calls ``Runner.run``. The file itself remains keyless and runnable:

    python examples/openai_agents_guardrail.py

OpenAI Agents guardrails:
https://openai.github.io/openai-agents-python/guardrails/

pyveil cookbook and security contract:
https://github.com/hyeonsangjeon/pyveil/blob/main/docs/cookbook.md
https://github.com/hyeonsangjeon/pyveil/blob/main/SECURITY.md
"""

from __future__ import annotations

from typing import Any

from pyveil import Channel, Veil


def prepare_agent_input(user_input: Any, veil: Veil) -> Any:
    """Return the exact redacted input that may cross the model boundary."""

    return veil.redact_data(user_input, channel=Channel.PROMPT_INPUT).data


async def run_agent_redacted(
    agent: Any,
    user_input: Any,
    *,
    veil: Veil,
    runner: Any | None = None,
    **run_kwargs: Any,
) -> Any:
    """Redact input before delegating to ``agents.Runner.run``.

    ``runner`` is injectable so the boundary can be contract-tested without an
    API key, network request, or installed provider SDK.
    """

    if runner is None:
        try:
            from agents import Runner  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - optional live dependency
            raise RuntimeError("install OpenAI Agents SDK: pip install openai-agents") from exc
        runner = Runner

    safe_input = prepare_agent_input(user_input, veil)
    return await runner.run(agent, input=safe_input, **run_kwargs)


def main() -> None:
    """Run a synthetic dry-run that proves the pre-dispatch boundary."""

    veil = Veil.high(secret=b"pyveil-example-only", scope="examples/openai-agents")
    raw_input = [
        {"role": "user", "content": "Email alice@example.com about case INC-123456."}
    ]
    safe_input = prepare_agent_input(raw_input, veil)
    print("sent-to-agent:", safe_input)
    print("provider-response: skipped (keyless boundary demo)")


if __name__ == "__main__":
    main()
