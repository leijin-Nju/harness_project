import json

from typer.testing import CliRunner

from harness.cli import app

runner = CliRunner()


def test_demo_runs_without_api_key(tmp_path):
    result = runner.invoke(app, ["demo", "--workspace", str(tmp_path)])

    assert result.exit_code == 0
    assert "COMPLETED" in result.stdout


def test_run_accepts_mock_script(tmp_path):
    script = tmp_path / "script.json"
    script.write_text(
        json.dumps([{"type": "request_done", "payload": {"summary": "done"}}]),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["run", "finish", "--workspace", str(tmp_path), "--mock-script", str(script)],
    )

    assert result.exit_code == 0
    assert "request_done" in result.stdout


def test_credentials_status_does_not_show_plaintext(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-abcdefghijklmnopqrstuvwxyz")

    result = runner.invoke(app, ["credentials", "status"])

    assert result.exit_code == 0
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in result.stdout
    assert "sk-a...wxyz" in result.stdout
