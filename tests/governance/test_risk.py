from harness.governance.risk import RiskClassifier
from harness.models import Action, ActionType, RiskLevel


def classify(command: str):
    action = Action(type=ActionType.RUN_COMMAND, payload={"command": command})
    return RiskClassifier().classify(action)


def test_allows_pytest_and_ruff():
    assert classify("pytest").level == RiskLevel.ALLOW
    assert classify("ruff check src tests").level == RiskLevel.ALLOW


def test_reviews_git_push_and_dependency_install():
    assert classify("git push origin main").level == RiskLevel.REVIEW
    assert classify("pip install requests").level == RiskLevel.REVIEW


def test_reviews_long_running_server_commands():
    assert classify("uvicorn harness.web:app --host 0.0.0.0").level == RiskLevel.REVIEW


def test_denies_destructive_or_secret_commands():
    assert classify("rm -rf /").level == RiskLevel.DENY
    assert classify("cat .env").level == RiskLevel.DENY
    assert classify("psql -c 'DROP DATABASE prod'").level == RiskLevel.DENY


def test_non_command_actions_default_allow():
    action = Action(type=ActionType.REQUEST_DONE, payload={"summary": "done"})

    decision = RiskClassifier().classify(action)

    assert decision.level == RiskLevel.ALLOW
