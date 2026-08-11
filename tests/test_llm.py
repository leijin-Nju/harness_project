import pytest

from harness.llm import MockLLMClient, OpenAICompatibleClient


def test_mock_llm_returns_scripted_steps():
    client = MockLLMClient([
        {"type": "read_file", "payload": {"path": "README.md"}},
        '{"type": "request_done", "payload": {"summary": "done"}}',
    ])

    assert "read_file" in client.generate([], {})
    assert "request_done" in client.generate([], {})


def test_mock_llm_raises_when_script_exhausted():
    client = MockLLMClient([])

    with pytest.raises(RuntimeError, match="script exhausted"):
        client.generate([], {})


def test_openai_client_requires_nonempty_key():
    with pytest.raises(ValueError, match="api_key"):
        OpenAICompatibleClient(api_key="", base_url="https://api.example.test/v1", model="gpt-test")


def test_openai_client_posts_wrapped_action_schema(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"type": "request_done"}'}}]}

    def post(url, *, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return FakeResponse()

    monkeypatch.setitem(__import__("sys").modules, "httpx", type("FakeHttpx", (), {"post": post}))
    client = OpenAICompatibleClient(
        api_key="test-key",
        base_url="https://api.example.test/v1/",
        model="gpt-test",
        timeout_seconds=12.5,
    )
    messages = [{"role": "user", "content": "choose an action"}]
    action_schema = {"type": "object", "properties": {"type": {"enum": ["request_done"]}}}

    result = client.generate(messages, action_schema)

    assert result == '{"type": "request_done"}'
    assert len(calls) == 1
    assert calls[0] == (
        "https://api.example.test/v1/chat/completions",
        {"Authorization": "Bearer test-key"},
        {
            "model": "gpt-test",
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "action", "schema": action_schema},
            },
        },
        12.5,
    )
