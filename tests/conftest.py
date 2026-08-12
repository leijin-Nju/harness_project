import hashlib
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Path:
    root = Path(__file__).parent.parent / ".test-tmp"
    root.mkdir(exist_ok=True)
    name = hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:16]
    path = root / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir()
    yield path
    shutil.rmtree(path, ignore_errors=True)
