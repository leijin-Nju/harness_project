import os

import keyring

from harness.models import CredentialStatus


def mask_secret(value: str) -> str:
    if len(value) > 10:
        return f"{value[:4]}...{value[-4:]}"
    return "*" * len(value)


class CredentialManager:
    def __init__(self, service_name: str = "coding-agent-harness") -> None:
        self.service_name = service_name

    def get_api_key(self, provider: str = "openai") -> str | None:
        return keyring.get_password(self.service_name, provider) or os.getenv("OPENAI_API_KEY")

    def set_api_key(self, api_key: str, provider: str = "openai") -> None:
        keyring.set_password(self.service_name, provider, api_key)

    def clear_api_key(self, provider: str = "openai") -> None:
        keyring.delete_password(self.service_name, provider)

    def status(self, provider: str = "openai") -> CredentialStatus:
        api_key = keyring.get_password(self.service_name, provider)
        if api_key:
            return CredentialStatus(
                provider=provider,
                source="keyring",
                exists=True,
                masked_preview=mask_secret(api_key),
            )

        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            return CredentialStatus(
                provider=provider,
                source="env",
                exists=True,
                masked_preview=mask_secret(api_key),
            )

        return CredentialStatus(provider=provider, source="missing", exists=False)
