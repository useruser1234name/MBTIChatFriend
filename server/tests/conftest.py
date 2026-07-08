from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path() -> Path:
    base_dir = Path(tempfile.gettempdir()) / "mbtichatfriend-pytest"
    base_dir.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=base_dir))
    yield path


def pytest_collection_modifyitems(config, items) -> None:
    if os.name != "nt" or os.getenv("RUN_CHROMA_TESTS") == "1":
        return

    skip_chroma = pytest.mark.skip(
        reason="ChromaDB PersistentClient tests can hang at process shutdown on Windows; set RUN_CHROMA_TESTS=1 to run them explicitly."
    )
    for item in items:
        path = str(item.path).replace("\\", "/")
        if path.endswith("test_vector_store.py") or path.endswith("test_legacy_vector_cleanup.py"):
            item.add_marker(skip_chroma)
