def test_tmp_path_fixture_is_writable(tmp_path):
    path = tmp_path / "probe.txt"

    path.write_text("ok", encoding="utf-8")

    assert path.read_text(encoding="utf-8") == "ok"
