import re
from pathlib import Path

REQUIRED_README_SECTIONS = [
    "## Installation",
    "## Usage",
    "## Docker Distribution",
    "## API Key Security",
    "## Directory Structure",
    "## Security Boundaries",
    "## Project Documents",
    "## CI/CD And Submission Evidence",
]

REQUIRED_REFLECTION_TOPICS = [
    "Superpowers",
    "TDD",
    "Subagent-driven",
    "SPEC",
    "PLAN",
    "prompt/context",
    "凭据",
    "分发",
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


def test_readme_contains_exact_required_headings():
    lines = Path("README.md").read_text(encoding="utf-8").splitlines()

    for section in REQUIRED_README_SECTIONS:
        assert lines.count(section) == 1


def test_plan_mentions_tdd_and_mock_llm():
    text = Path("PLAN.md").read_text(encoding="utf-8")

    assert "TDD" in text
    assert "mock LLM" in text


def test_spec_user_stories_follow_required_format_and_priority():
    text = Path("SPEC.md").read_text(encoding="utf-8")
    story_pattern = re.compile(r"^作为 .+，我希望 .+，以便 .+。$", re.MULTILINE)
    priority_pattern = re.compile(
        r"^优先级：(Must|Should|Could|Won't)$",
        re.MULTILINE,
    )

    assert len(story_pattern.findall(text)) == 10
    assert len(priority_pattern.findall(text)) == 10
    assert len(re.findall(r"^验收标准：$", text, re.MULTILINE)) == 10
    assert not re.search(r"^[ \t]+验收标准：$", text, re.MULTILINE)


def test_docs_describe_json_memory_without_sqlite_dependency():
    spec = Path("SPEC.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    for text in [spec, readme]:
        assert "本地 JSON" in text
        assert "不使用 SQLite" in text
        assert re.search(r"MySQL.{0,40}(未来|预留|不是 MVP 依赖)", text)


def test_reflection_contains_final_course_topics():
    text = Path("REFLECTION.md").read_text(encoding="utf-8")

    assert len(text) > 1500
    assert "# Reflection" not in text
    for topic in REQUIRED_REFLECTION_TOPICS:
        assert topic in text


def test_spec_uses_local_webui_and_accurate_docker_verification_wording():
    text = Path("SPEC.md").read_text(encoding="utf-8")

    assert "本地 WebUI 启动说明" in text
    assert "http://120.27.140.93/" in text
    assert "可访问 WebUI URL" not in text
    assert "Docker 构建验证通过" not in text
    assert "服务器 `docker load` 部署" in text


def test_readme_lists_final_submission_evidence():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "## CI/CD And Submission Evidence" in text
    assert "https://github.com/leijin-Nju/harness_project" in text
    assert "http://120.27.140.93/" in text
    assert "最后一次 CI/CD pass 记录链接" in text
    assert "docker save" in text
    assert "docker load" in text


def test_course_documents_have_required_structure():
    required_headings = {
        "SPEC.md": ["## 1. 问题陈述", "## 2. 用户故事", "## 13. 验收标准"],
        "PLAN.md": ["### Task 1:", "### Task 15:"],
        "SPEC_PROCESS.md": ["## Brainstorming Key Nodes", "## Cold-Start Trial Record"],
        "AGENT_LOG.md": ["| Time | Task | Superpowers Skill |"],
    }

    for name, markers in required_headings.items():
        text = Path(name).read_text(encoding="utf-8")
        assert len(text.strip()) > 100
        for marker in markers:
            assert marker in text
