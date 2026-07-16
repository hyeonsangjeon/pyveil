import json

import pytest

from pyveil.integrations.anthropic import AnthropicSettings, ask_anthropic
from pyveil.integrations.openai import OpenAISettings, ask_openai


@pytest.mark.provider_contract
def test_official_openai_sdk_serializes_only_redacted_input():
    httpx = pytest.importorskip("httpx")
    openai = pytest.importorskip("openai")
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"x-request-id": "req_contract_openai"},
            json={
                "id": "resp_contract",
                "object": "response",
                "created_at": 1,
                "status": "completed",
                "model": "contract-model",
                "output": [
                    {
                        "id": "msg_contract",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "safe OpenAI contract response",
                                "annotations": [],
                                "logprobs": [],
                            }
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 21,
                    "output_tokens": 5,
                    "total_tokens": 26,
                },
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = openai.OpenAI(
        api_key="synthetic-openai-contract-key",
        base_url="https://mock.openai.test/v1",
        http_client=http_client,
    )
    try:
        result = ask_openai(
            "Contact alice@example.com or 010-1234-5678.",
            OpenAISettings(
                pyveil_secret="contract-secret",
                api_key="synthetic-openai-contract-key",
                model="contract-model",
                max_output_tokens=64,
            ),
            client=client,
        )
    finally:
        client.close()

    assert captured["path"] == "/v1/responses"
    assert captured["body"]["model"] == "contract-model"
    assert captured["body"]["max_output_tokens"] == 64
    assert "alice@example.com" not in captured["body"]["input"]
    assert "010-1234-5678" not in captured["body"]["input"]
    assert "[EMAIL:" in captured["body"]["input"]
    assert "[PHONE:" in captured["body"]["input"]
    assert result.output_text == "safe OpenAI contract response"
    assert result.input_tokens == 21
    assert result.output_tokens == 5
    assert result.total_tokens == 26
    assert result.request_id == "req_contract_openai"


@pytest.mark.provider_contract
def test_official_anthropic_sdk_serializes_only_redacted_input():
    anthropic = pytest.importorskip("anthropic")
    httpx = pytest.importorskip("httpx")
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"request-id": "req_contract_anthropic"},
            json={
                "id": "msg_contract",
                "type": "message",
                "role": "assistant",
                "model": "contract-model",
                "content": [
                    {"type": "text", "text": "safe Anthropic contract response"}
                ],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 19, "output_tokens": 4},
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = anthropic.Anthropic(
        api_key="synthetic-anthropic-contract-key",
        base_url="https://mock.anthropic.test",
        http_client=http_client,
    )
    try:
        result = ask_anthropic(
            "Contact alice@example.com or 010-1234-5678.",
            AnthropicSettings(
                pyveil_secret="contract-secret",
                api_key="synthetic-anthropic-contract-key",
                model="contract-model",
                max_tokens=64,
            ),
            client=client,
        )
    finally:
        client.close()

    assert captured["path"] == "/v1/messages"
    assert captured["body"]["model"] == "contract-model"
    assert captured["body"]["max_tokens"] == 64
    sent = captured["body"]["messages"][0]["content"]
    assert "alice@example.com" not in sent
    assert "010-1234-5678" not in sent
    assert "[EMAIL:" in sent
    assert "[PHONE:" in sent
    assert result.output_text == "safe Anthropic contract response"
    assert result.input_tokens == 19
    assert result.output_tokens == 4
    assert result.request_id == "req_contract_anthropic"
