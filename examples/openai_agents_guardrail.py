"""Redact context before handing it to an agent runtime.

This example keeps the pyveil boundary independent from any specific SDK
version. Put `redact_for_agent` immediately before the call that sends context
to your agent/model client.
"""

from typing import Callable

from pyveil import Channel, Veil


def redact_for_agent(user_message: str, run_agent: Callable[[str], str]) -> str:
    veil = Veil.high(secret=b"tenant-secret", scope="tenant-123/run-456")
    safe_message = veil.redact_text(user_message, channel=Channel.PROMPT_INPUT)
    return run_agent(safe_message.text)


def demo_agent(prompt: str) -> str:
    return f"agent received: {prompt}"


if __name__ == "__main__":
    print(redact_for_agent("Email alice@example.com about case INC-123456.", demo_agent))
