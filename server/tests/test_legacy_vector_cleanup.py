import pytest

chromadb = pytest.importorskip("chromadb")

from app.legacy_vector_cleanup import (
    STATUS_ACTIVE_SCOPED,
    STATUS_LEGACY_GLOBAL_CANDIDATE,
    STATUS_UNKNOWN,
    delete_named_collections,
    inspect_vector_store,
    list_collection_names,
    load_known_room_ids,
)
from app.vector_store import VectorStore


@pytest.fixture
def store_and_dir(tmp_path):
    persist_dir = str(tmp_path / "chroma_cleanup_test")
    store = VectorStore(persist_dir=persist_dir)
    store.embedding_fn = "_USE_DEFAULT"
    try:
        yield store, persist_dir
    finally:
        store.close()


def test_inspect_classifies_active_legacy_and_unknown(store_and_dir):
    store, persist_dir = store_and_dir
    active_name = store._collection_name("user123:7")
    legacy_name = store._episode_collection_name("6")
    store.client.get_or_create_collection(name=active_name)
    store.client.get_or_create_collection(name=legacy_name)
    store.client.get_or_create_collection(name="misc_notes")

    report = inspect_vector_store(persist_dir, known_room_ids={"user123:7"})
    by_name = {item["name"]: item for item in report["collections"]}

    assert by_name[active_name]["status"] == STATUS_ACTIVE_SCOPED
    assert by_name[active_name]["matched_room_id"] == "user123:7"
    assert by_name[legacy_name]["status"] == STATUS_LEGACY_GLOBAL_CANDIDATE
    assert by_name["misc_notes"]["status"] == STATUS_UNKNOWN


def test_delete_refuses_non_legacy_without_force(store_and_dir):
    store, persist_dir = store_and_dir
    active_name = store._collection_name("user123:7")
    store.client.get_or_create_collection(name=active_name)

    result = delete_named_collections(
        persist_dir,
        [active_name],
        known_room_ids={"user123:7"},
        apply=True,
    )

    assert result["deleted"] == []
    assert result["skipped"][0]["reason"].startswith("refusing_non_legacy_status:")
    assert active_name in list_collection_names(persist_dir)


def test_delete_removes_explicit_legacy_collection(store_and_dir):
    store, persist_dir = store_and_dir
    legacy_name = store._episode_collection_name("6")
    store.client.get_or_create_collection(name=legacy_name)

    result = delete_named_collections(
        persist_dir,
        [legacy_name],
        known_room_ids={"user123:7"},
        apply=True,
    )

    assert result["deleted"] == [legacy_name]
    assert legacy_name not in list_collection_names(persist_dir)


def test_load_known_room_ids_parses_room_memory_keys(monkeypatch):
    monkeypatch.setattr("app.legacy_vector_cleanup.postgres_enabled", lambda: True)

    def fake_fetchall(query, params=None):
        if "conversation_memory" in query:
            return [{"memory_key": "room:user_a:7"}]
        return [{"room_id": "user_b:9"}, {"room_id": ""}]

    monkeypatch.setattr("app.legacy_vector_cleanup.fetchall", fake_fetchall)

    room_ids, status = load_known_room_ids()

    assert status == "available"
    assert room_ids == {"user_a:7", "user_b:9"}
