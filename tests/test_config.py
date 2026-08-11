from harness.config import HarnessConfig


def test_config_creates_harness_paths(tmp_path):
    config = HarnessConfig(workspace_root=tmp_path)

    paths = config.paths()

    assert paths["state_dir"] == tmp_path / ".harness"
    assert paths["memory"] == tmp_path / ".harness" / "memory.json"
    assert paths["approvals"] == tmp_path / ".harness" / "approvals.json"
