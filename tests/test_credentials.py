from harness.credentials import CredentialManager, mask_secret


class FakeKeyring:
    def __init__(self):
        self.values = {}

    def get_password(self, service, username):
        return self.values.get((service, username))

    def set_password(self, service, username, password):
        self.values[(service, username)] = password

    def delete_password(self, service, username):
        self.values.pop((service, username), None)


def test_mask_secret_never_returns_plaintext():
    assert mask_secret("sk-abcdefghijklmnopqrstuvwxyz") == "sk-a...wxyz"
    assert mask_secret("") == ""


def test_credential_manager_uses_keyring(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr("harness.credentials.keyring", fake)
    manager = CredentialManager(service_name="test-harness")

    manager.set_api_key("sk-abcdefghijklmnopqrstuvwxyz")

    assert manager.get_api_key() == "sk-abcdefghijklmnopqrstuvwxyz"
    status = manager.status()
    assert status.exists is True
    assert status.masked_preview == "sk-a...wxyz"
