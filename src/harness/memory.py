import json
import re
import shutil
from pathlib import Path
from typing import Protocol

from harness.models import MemoryEntry, MemoryKind


class MemoryStore(Protocol):
    def add(self, entry: MemoryEntry) -> MemoryEntry:
        ...

    def search(
        self,
        query: str,
        kinds: set[MemoryKind] | None = None,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        ...


class JsonMemoryStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def add(self, entry: MemoryEntry) -> MemoryEntry:
        entries = self._load()
        entries.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                [self._redact(item.model_dump(mode="json")) for item in entries], ensure_ascii=True
            ),
            encoding="utf-8",
        )
        return entry

    def search(
        self,
        query: str,
        kinds: set[MemoryKind] | None = None,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        tokens = query.lower().split()
        matches = []
        for entry in self._load():
            if kinds is not None and entry.kind not in kinds:
                continue
            searchable = f"{entry.text.lower()} {' '.join(entry.keywords).lower()}"
            score = sum(token in searchable for token in tokens)
            if score:
                matches.append((score, entry.created_at, entry))
        matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in matches[:limit]]

    def _load(self) -> list[MemoryEntry]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            shutil.copyfile(self.path, self.path.with_name(f"{self.path.name}.bak"))
            raise ValueError("memory file is not valid JSON") from error
        return [MemoryEntry.model_validate(item) for item in data]

    @staticmethod
    def _redact(value):
        if isinstance(value, str):
            value = re.sub(r"OPENAI_API_KEY=[^\s\"']+", "[redacted]", value)
            return re.sub(r"sk-[A-Za-z0-9]{8,}", "[redacted]", value)
        if isinstance(value, list):
            return [JsonMemoryStore._redact(item) for item in value]
        if isinstance(value, dict):
            return {key: JsonMemoryStore._redact(item) for key, item in value.items()}
        return value


class MySQLMemoryStore:
    def __init__(self):
        raise NotImplementedError("MySQLMemoryStore is reserved for a future adapter")
