"""LiteLLM-style request filter example.

Use the same pattern in proxy hooks, gateway middleware, or provider adapters:
redact the message list before forwarding it to the model provider.
"""

from typing import Any, Dict, List

from pyveil import Channel, Veil


def redact_messages(messages: List[Dict[str, Any]], veil: Veil) -> List[Dict[str, Any]]:
    result = veil.redact_data(messages, channel=Channel.PROMPT_INPUT)
    return result.data


if __name__ == "__main__":
    raw_messages = [
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "Use Authorization: Bearer synthetic-token-value"},
    ]

    safe_messages = redact_messages(raw_messages, Veil.high(secret=b"proxy-secret", scope="tenant-123"))
    print(safe_messages)
