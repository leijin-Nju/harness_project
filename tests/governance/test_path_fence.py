from harness.governance.path_fence import PathFence
from harness.models import Action, ActionType, RiskLevel


def test_allows_workspace_relative_write(tmp_path):
    fence = PathFence(tmp_path)
    action = Action(
        type=ActionType.WRITE_FILE,
        payload={"path": "src/app.py", "content": "print('ok')"},
    )

    decision = fence.check_action(action)

    assert decision.level == RiskLevel.ALLOW
    assert decision.reasons == ["path is inside workspace"]


def test_denies_parent_directory_escape(tmp_path):
    fence = PathFence(tmp_path)
    action = Action(type=ActionType.READ_FILE, payload={"path": "../secret.txt"})

    decision = fence.check_action(action)

    assert decision.level == RiskLevel.DENY
    assert "outside workspace" in decision.reasons[0]


def test_denies_env_file_read(tmp_path):
    fence = PathFence(tmp_path)
    action = Action(type=ActionType.READ_FILE, payload={"path": ".env"})

    decision = fence.check_action(action)

    assert decision.level == RiskLevel.DENY
    assert "sensitive credential file" in decision.reasons[0]


def test_reviews_git_directory_write(tmp_path):
    fence = PathFence(tmp_path)
    action = Action(type=ActionType.WRITE_FILE, payload={"path": ".git/config", "content": "x"})

    decision = fence.check_action(action)

    assert decision.level == RiskLevel.REVIEW
    assert "git metadata" in decision.reasons[0]
