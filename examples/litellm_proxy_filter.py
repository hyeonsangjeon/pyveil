"""Redact LiteLLM SDK requests and Proxy payloads before provider dispatch.

Install the path you use:

    pip install pyveil litellm
    pip install pyveil "litellm[proxy]"

For the Python SDK, call ``completion_with_redaction`` instead of
``litellm.completion`` directly. For LiteLLM Proxy, register the module-level
``proxy_handler_instance`` as a custom callback and set ``PYVEIL_SECRET``:

    litellm_settings:
      callbacks: examples.litellm_proxy_filter.proxy_handler_instance

Run this file without LiteLLM, credentials, or a network request:

    python examples/litellm_proxy_filter.py

LiteLLM documentation:
https://docs.litellm.ai/

pyveil cookbook and security contract:
https://github.com/hyeonsangjeon/pyveil/blob/main/docs/cookbook.md
https://github.com/hyeonsangjeon/pyveil/blob/main/SECURITY.md
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict

from pyveil import Channel, Veil

try:
    from litellm.integrations.custom_logger import CustomLogger  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional live dependency

    class CustomLogger:  # type: ignore[no-redef]
        """Fallback base that keeps the keyless example importable."""


Message = Dict[str, Any]
Completion = Callable[..., Any]


def redact_messages(messages: list[Message], veil: Veil) -> list[Message]:
    """Preserve the message structure while redacting provider-bound content."""

    result = veil.redact_data(messages, channel=Channel.PROMPT_INPUT)
    safe_messages = result.data
    if not isinstance(safe_messages, list):  # pragma: no cover - Veil preserves list shape
        raise TypeError("pyveil did not preserve the LiteLLM message list")
    return safe_messages


def completion_with_redaction(
    *,
    model: str,
    messages: list[Message],
    veil: Veil,
    completion: Completion | None = None,
    **kwargs: Any,
) -> Any:
    """Redact messages immediately before ``litellm.completion``."""

    if completion is None:
        try:
            from litellm import completion as litellm_completion  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - optional live dependency
            raise RuntimeError("install LiteLLM: pip install litellm") from exc
        completion = litellm_completion

    safe_messages = redact_messages(messages, veil)
    return completion(model=model, messages=safe_messages, **kwargs)


class PyVeilProxyHook(CustomLogger):
    """LiteLLM Proxy pre-call hook that returns a redacted payload copy."""

    def __init__(self, veil: Veil | None = None) -> None:
        super().__init__()
        self._veil = veil

    def _get_veil(self) -> Veil:
        if self._veil is not None:
            return self._veil
        secret = os.environ.get("PYVEIL_SECRET")
        if not secret:
            raise RuntimeError("PYVEIL_SECRET is required by the pyveil LiteLLM proxy hook")
        scope = os.environ.get("PYVEIL_SCOPE", "litellm/proxy")
        return Veil.high(secret=secret, scope=scope)

    async def async_pre_call_hook(
        self,
        user_api_key_dict: Any,
        cache: Any,
        data: dict[str, Any],
        call_type: str,
    ) -> dict[str, Any]:
        """Redact ``messages`` before LiteLLM forwards a completion request."""

        del user_api_key_dict, cache, call_type
        messages = data.get("messages")
        if not isinstance(messages, list):
            return data

        safe_data = dict(data)
        safe_data["messages"] = redact_messages(messages, self._get_veil())
        return safe_data


# LiteLLM resolves this dotted path from ``litellm_settings.callbacks``.
proxy_handler_instance = PyVeilProxyHook()


def main() -> None:
    """Run the same pure transformation used by both integration paths."""

    messages: list[Message] = [
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "Email alice@example.com about this request."},
    ]
    veil = Veil.high(secret=b"pyveil-example-only", scope="examples/litellm")
    print("sent-to-litellm:", redact_messages(messages, veil))
    print("provider-response: skipped (keyless boundary demo)")


if __name__ == "__main__":
    main()
