"""VectorStore 단위 테스트 - 기본 임베딩으로 구조/캐시 동작 검증."""

import os

import pytest

if os.name == "nt" and os.getenv("RUN_CHROMA_TESTS") != "1":
    pytest.skip(
        "ChromaDB PersistentClient tests can hang at process shutdown on Windows; set RUN_CHROMA_TESTS=1 to run explicitly.",
        allow_module_level=True,
    )

# chromadb가 설치되어 있어야 테스트 실행
chromadb = pytest.importorskip("chromadb")

from app.vector_store import VectorStore


class _MemoryItem:
    """MemoryItem 모방 객체."""

    def __init__(self, key: str, value: str):
        self.key = key
        self.value = value


@pytest.fixture
def store(tmp_path):
    """임시 디렉토리에 VectorStore 생성.

    ChromaDB 기본 임베딩(all-MiniLM-L6-v2) 사용 — OpenAI API 불필요.
    embedding_fn을 sentinel 값으로 설정하여 guard 통과 + 기본 임베딩 사용.
    """
    s = VectorStore(persist_dir=str(tmp_path / "chroma_test"))
    # sentinel: truthy이지만 get_or_create에는 넘기지 않도록 _USE_DEFAULT로 표시
    s.embedding_fn = "_USE_DEFAULT"
    try:
        yield s
    finally:
        s.close()


# ── 컬렉션 이름 ─────────────────────────────────────────────


class TestCollectionNaming:
    def test_memory_collection_name(self, store):
        assert store._collection_name("abc123") == "char_abc123"

    def test_episode_collection_name(self, store):
        assert store._episode_collection_name("abc123") == "ep_abc123"

    def test_special_chars_sanitized(self, store):
        name = store._collection_name("user@test.com/char-1")
        assert "@" not in name
        assert "/" not in name
        assert "-" not in name
        assert name.startswith("char_")

    def test_max_length_63(self, store):
        name = store._collection_name("a" * 200)
        assert len(name) <= 63


# ── 기억(Memory) CRUD ────────────────────────────────────────


class TestMemories:
    def test_upsert_and_search(self, store):
        memories = [
            _MemoryItem("직업", "대학생"),
            _MemoryItem("취미", "독서"),
        ]
        store.upsert_memories("char1", memories)
        results = store.search_relevant("char1", "직업이 뭐야?", n_results=5, max_distance=999)
        assert len(results) == 2
        assert any("직업" in r for r in results)

    def test_search_empty_returns_empty(self, store):
        results = store.search_relevant("nonexistent", "hello")
        assert results == []

    def test_upsert_updates_existing_key(self, store):
        store.upsert_memories("char1", [_MemoryItem("이름", "김철수")])
        store.upsert_memories("char1", [_MemoryItem("이름", "김영희")])
        results = store.search_relevant("char1", "이름", n_results=5, max_distance=999)
        # 같은 key로 upsert했으므로 1개만 존재
        assert len(results) == 1
        assert "김영희" in results[0]

    def test_different_characters_isolated(self, store):
        store.upsert_memories("char_a", [_MemoryItem("이름", "A캐릭터")])
        store.upsert_memories("char_b", [_MemoryItem("이름", "B캐릭터")])
        results_a = store.search_relevant("char_a", "이름", n_results=5, max_distance=999)
        results_b = store.search_relevant("char_b", "이름", n_results=5, max_distance=999)
        assert len(results_a) == 1
        assert "A캐릭터" in results_a[0]
        assert "B캐릭터" in results_b[0]

    def test_no_embedding_fn_skips(self, store):
        store.embedding_fn = None
        store.upsert_memories("char1", [_MemoryItem("k", "v")])
        assert store.search_relevant("char1", "k") == []


# ── 에피소드(Episode) CRUD ───────────────────────────────────


class TestEpisodes:
    def test_upsert_and_search(self, store):
        episodes = [
            {"text": "첫 만남에서 수줍게 인사했다", "emotion": "SHY", "importance": 4, "topic": "첫만남"},
            {"text": "같이 카페에서 커피를 마셨다", "emotion": "HAPPY", "importance": 3, "topic": "카페"},
        ]
        store.upsert_episodes("char1", episodes)
        results = store.search_episodes("char1", "첫 만남", n_results=5)
        assert len(results) == 2
        assert all("text" in r and "emotion" in r and "score" in r for r in results)

    def test_search_empty_returns_empty(self, store):
        results = store.search_episodes("nonexistent", "hello")
        assert results == []

    def test_episode_ids_unique(self, store):
        """같은 초에 여러 번 호출해도 ID 충돌 없음."""
        ep = [{"text": "test", "emotion": "NEUTRAL", "importance": 3, "topic": "t"}]
        store.upsert_episodes("char1", ep)
        store.upsert_episodes("char1", ep)
        store.upsert_episodes("char1", ep)
        col = store._get_existing(store._episode_collection_name("char1"))
        assert col is not None
        # uuid 기반이므로 3개 모두 별도 저장
        assert col.count() == 3

    def test_importance_clamped(self, store):
        episodes = [
            {"text": "low", "emotion": "NEUTRAL", "importance": -10, "topic": ""},
            {"text": "high", "emotion": "NEUTRAL", "importance": 99, "topic": ""},
        ]
        store.upsert_episodes("char1", episodes)
        results = store.search_episodes("char1", "test", n_results=5)
        importances = [r["importance"] for r in results]
        assert all(1 <= i <= 5 for i in importances)

    def test_score_decreases_with_distance(self, store):
        """시간 감쇄 없이 검색 시 시맨틱 유사도만 반영."""
        episodes = [
            {"text": "짧은 텍스트", "emotion": "HAPPY", "importance": 3, "topic": ""},
            {"text": "매우 긴 텍스트" * 20, "emotion": "SAD", "importance": 3, "topic": ""},
        ]
        store.upsert_episodes("char1", episodes)
        results = store.search_episodes("char1", "짧은", n_results=5, time_decay=False)
        assert len(results) >= 1
        # 결과가 score 내림차순
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)


# ── 삭제 ─────────────────────────────────────────────────────


class TestDeletion:
    def test_delete_clears_memories_and_episodes(self, store):
        store.upsert_memories("char1", [_MemoryItem("k", "v")])
        store.upsert_episodes("char1", [
            {"text": "ep", "emotion": "NEUTRAL", "importance": 3, "topic": ""},
        ])
        store.delete_character("char1")
        assert store.search_relevant("char1", "k") == []
        assert store.search_episodes("char1", "ep") == []

    def test_delete_nonexistent_no_error(self, store):
        store.delete_character("nonexistent")  # 예외 없이 통과

    def test_delete_clears_cache(self, store):
        store.upsert_memories("char1", [_MemoryItem("k", "v")])
        col_name = store._collection_name("char1")
        assert col_name in store._col_cache
        store.delete_character("char1")
        assert col_name not in store._col_cache


# ── 캐시 동작 ────────────────────────────────────────────────


class TestCaching:
    def test_negative_cache_prevents_repeated_get(self, store):
        """존재하지 않는 컬렉션 조회 후 네거티브 캐시에 등록."""
        result = store._get_existing("nonexistent_col")
        assert result is None
        assert "nonexistent_col" in store._neg_cache

    def test_upsert_clears_negative_cache(self, store):
        """upsert로 컬렉션 생성 시 네거티브 캐시 제거."""
        # 먼저 검색해서 네거티브 캐시에 등록
        store.search_relevant("new_char", "hello")
        col_name = store._collection_name("new_char")
        assert col_name in store._neg_cache

        # upsert하면 네거티브 캐시에서 제거
        store.upsert_memories("new_char", [_MemoryItem("k", "v")])
        assert col_name not in store._neg_cache

    def test_collection_cached_after_get(self, store):
        store.upsert_memories("char1", [_MemoryItem("k", "v")])
        col_name = store._collection_name("char1")
        assert col_name in store._col_cache


# ── 통계 ─────────────────────────────────────────────────────


class TestStats:
    def test_stats_empty(self, store):
        stats = store.get_stats("nonexistent")
        assert stats == {"memories": 0, "episodes": 0}

    def test_stats_with_data(self, store):
        store.upsert_memories("char1", [_MemoryItem("k", "v")])
        store.upsert_episodes("char1", [
            {"text": "ep1", "emotion": "HAPPY", "importance": 3, "topic": ""},
            {"text": "ep2", "emotion": "SAD", "importance": 2, "topic": ""},
        ])
        stats = store.get_stats("char1")
        assert stats["memories"] == 1
        assert stats["episodes"] == 2
