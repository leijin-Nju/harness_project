from pathlib import Path

REQUIRED_README_SECTIONS = [
    "## Installation",
    "## Usage",
    "## Docker Distribution",
    "## API Key Security",
    "## Directory Structure",
    "## Security Boundaries",
]


def test_required_course_documents_exist():
    documents = [
        "SPEC.md",
        "PLAN.md",
        "SPEC_PROCESS.md",
        "AGENT_LOG.md",
        "REFLECTION.md",
        "README.md",
    ]
    for name in documents:
        assert Path(name).exists(), f"{name} is missing"


def test_readme_contains_required_sections():
    text = Path("README.md").read_text(encoding="utf-8")

    for section in REQUIRED_README_SECTIONS:
        assert section in text


def test_plan_mentions_tdd_and_mock_llm():
    text = Path("PLAN.md").read_text(encoding="utf-8")

    assert "TDD" in text
    assert "mock LLM" in text
