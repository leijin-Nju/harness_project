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
