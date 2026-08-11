import json
from typing import Protocol


class LLMClient(Protocol):
    def generate(self, messages: list[dict[str, str]], action_schema: dict[str, object]) -> str:
        ...


class MockLLMClient:
    def __init__(self, script: list[str | dict]) -> None:
        self._script = list(script)

    def generate(self, messages: list[dict[str, str]], action_schema: dict[str, object]) -> str:
        del messages, action_schema
        if not self._script:
            raise RuntimeError("script exhausted")
        item = self._script.pop(0)
        return item if isinstance(item, str) else json.dumps(item)


class OpenAICompatibleClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key must be nonempty")
        if not base_url.strip():
            raise ValueError("base_url must be nonempty")
        if not model.strip():
            raise ValueError("model must be nonempty")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, messages: list[dict[str, str]], action_schema: dict[str, object]) -> str:
        import httpx

        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": messages,
                "response_format": {"type": "json_schema", "json_schema": action_schema},
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
