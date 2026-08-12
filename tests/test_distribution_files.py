from pathlib import Path


def test_gitlab_ci_contains_required_unit_test_job():
    text = Path(".gitlab-ci.yml").read_text(encoding="utf-8")

    assert "unit-test:" in text
    assert "timeout 300 pip install .[dev]" in text
    assert "timeout 300 pytest -q" in text
    assert "timeout 300 ruff check src tests scripts" in text
    assert "timeout 600 docker build -t coding-agent-harness:ci ." in text


def test_dockerfile_runs_harness_cli():
    text = Path("Dockerfile").read_text(encoding="utf-8")

    assert "python:3.11" in text
    assert "timeout 300 pip install --no-cache-dir .[dev]" in text
    assert "harness" in text


def test_makefile_exposes_required_commands():
    text = Path("Makefile").read_text(encoding="utf-8")

    assert "test:" in text
    assert "lint:" in text
    assert "demo:" in text
