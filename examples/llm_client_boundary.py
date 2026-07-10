"""Redact messages before they cross an LLM provider boundary.

This example is intentionally provider-neutral. Keep `call_with_redaction`
unchanged and swap `call_llm` for OpenAI, Azure OpenAI, Anthropic, Gemini,
LiteLLM, a proxy, or an internal gateway.
"""

from typing import Callable, Dict, List, cast

from pyveil import Channel, Veil

Message = Dict[str, str]
LLMCall = Callable[[List[Message]], str]


def call_with_redaction(messages: List[Message], call_llm: LLMCall, veil: Veil) -> str:
    safe = veil.redact_data(messages, channel=Channel.PROMPT_INPUT)
    return call_llm(cast(List[Message], safe.data))


def demo_llm(messages: List[Message]) -> str:
    """Stand in for a real provider SDK call."""
    return "provider received: " + messages[-1]["content"]


def main() -> None:
    raw_messages: List[Message] = [
        {"role": "system", "content": "You are concise."},
        {
            "role": "user",
            "content": (
                "Email alice@example.com about my API key "
                "sk-proj-abcdefghijklmnopqrstuvwxyz123456."
            ),
        },
    ]

    veil = Veil.high(secret=b"tenant-or-run-secret", scope="tenant/session")
    print(call_with_redaction(raw_messages, demo_llm, veil))


if __name__ == "__main__":
    main()
