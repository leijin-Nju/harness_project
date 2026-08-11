import json

import pytest

from harness.memory import JsonMemoryStore, MySQLMemoryStore
from harness.models import MemoryEntry, MemoryKind


def test_add_and_search_memory_by_keyword(tmp_path):
    store = JsonMemoryStore(tmp_path / "memory.json")
    store.add(
        MemoryEntry(
            kind=MemoryKind.CONVENTION, text="Do not use SQLite", keywords=["memory", "json"]
        )
    )
    store.add(
        MemoryEntry(
            kind=MemoryKind.DECISION,
            text="Governance is the main contribution",
            keywords=["governance"],
        )
    )

    results = store.search("memory json", limit=1)

    assert len(results) == 1
    assert results[0].text == "Do not use SQLite"


def test_search_filters_by_kind(tmp_path):
    store = JsonMemoryStore(tmp_path / "memory.json")
    store.add(MemoryEntry(kind=MemoryKind.CONVENTION, text="Use JSON memory", keywords=["memory"]))
    store.add(
        MemoryEntry(kind=MemoryKind.FAILURE_SUMMARY, text="pytest failed", keywords=["memory"])
    )

    results = store.search("memory", kinds={MemoryKind.FAILURE_SUMMARY})

    assert [item.kind for item in results] == [MemoryKind.FAILURE_SUMMARY]


def test_corrupt_memory_file_is_backed_up(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(ValueError, match="memory file is not valid JSON"):
        JsonMemoryStore(path).search("anything")

    assert (tmp_path / "memory.json.bak").exists()


def test_memory_file_never_contains_api_key_marker(tmp_path):
    store = JsonMemoryStore(tmp_path / "memory.json")
    store.add(
        MemoryEntry(
            kind=MemoryKind.DECISION,
            text="OPENAI_API_KEY=sk-secret",
            keywords=["secret"],
        )
    )

    raw = json.loads((tmp_path / "memory.json").read_text(encoding="utf-8"))

    assert "sk-secret" not in json.dumps(raw)
    assert "[redacted]" in json.dumps(raw)


def test_memory_file_redacts_project_api_key_in_text(tmp_path):
    store = JsonMemoryStore(tmp_path / "memory.json")
    secret = "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890"
    store.add(MemoryEntry(kind=MemoryKind.DECISION, text=secret))

    raw = (tmp_path / "memory.json").read_text(encoding="utf-8")

    assert secret not in raw
    assert "[redacted]" in raw


def test_memory_file_redacts_project_api_key_in_keywords(tmp_path):
    store = JsonMemoryStore(tmp_path / "memory.json")
    secret = "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890"
    store.add(MemoryEntry(kind=MemoryKind.DECISION, text="key", keywords=[secret]))

    raw = (tmp_path / "memory.json").read_text(encoding="utf-8")

    assert secret not in raw
    assert "[redacted]" in raw


def test_mysql_adapter_is_explicitly_future_work():
    with pytest.raises(NotImplementedError, match="future adapter"):
        MySQLMemoryStore()
