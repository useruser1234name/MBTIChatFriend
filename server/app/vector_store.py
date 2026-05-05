"""ChromaDB 벡터 스토어 - RAG 기반 장기 기억 + 에피소드 기억 검색

개선 사항:
- 컬렉션 객체 캐시: list_collections() 제거, 매 검색 O(1)
- 에피소드 ID 충돌 방지: uuid4 기반
- 스레드 안전 초기화: threading.Lock
- 통계 로깅: hit/miss 카운터
"""

import logging
import math
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("chromadb 미설치. RAG 기능 비활성화.")

from .config import OPENAI_API_KEY

_store: "VectorStore | None" = None
_store_lock = threading.Lock()


def get_store() -> "VectorStore | None":
    """싱글턴 VectorStore 반환 (스레드 안전)."""
    global _store
    if not CHROMA_AVAILABLE:
        return None
    if _store is None:
        with _store_lock:
            if _store is None:  # double-checked locking
                try:
                    _store = VectorStore()
                except Exception as e:
                    logger.error(f"VectorStore 초기화 실패: {e}")
    return _store


def close_store() -> None:
    global _store
    if _store is not None:
        _store.close()
        _store = None


def get_vector_store_health() -> dict[str, Any]:
    if not CHROMA_AVAILABLE:
        return {"status": "disabled", "initialized": False}
    return {"status": "ready", "initialized": _store is not None}


class VectorStore:
    """ChromaDB 기반 벡터 스토어. 컬렉션 캐시로 반복 조회 최소화."""

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.embedding_fn: Any = None
        if OPENAI_API_KEY:
            self.embedding_fn = OpenAIEmbeddingFunction(
                api_key=OPENAI_API_KEY,
                model_name="text-embedding-3-small",
            )
        # 컬렉션 객체 캐시: {collection_name: Collection} (최대 100개)
        self._col_cache: Dict[str, Any] = {}
        self._COL_CACHE_MAX = 100
        # 존재하지 않는 컬렉션 네거티브 캐시: 불필요한 get 시도 방지
        self._neg_cache: set = set()

    def close(self) -> None:
        """Release Chroma resources explicitly for tests and shutdown paths."""
        try:
            close_fn = getattr(self.client, "close", None)
            if callable(close_fn):
                close_fn()
            elif hasattr(self.client, "_system"):
                self.client._system.stop()
        except Exception as e:
            logger.warning(f"VectorStore close failed: {e}")
        finally:
            self._col_cache.clear()
            self._neg_cache.clear()

    # ── 컬렉션 이름 생성 ─────────────────────────────────────────

    @staticmethod
    def _safe_name(prefix: str, character_id: str) -> str:
        """ChromaDB 컬렉션명: 영숫자+언더스코어, 3~63자."""
        safe = "".join(c if c.isalnum() else "_" for c in str(character_id))
        return f"{prefix}{safe}"[:63]

    def _collection_name(self, character_id: str) -> str:
        return self._safe_name("char_", character_id)

    def _episode_collection_name(self, character_id: str) -> str:
        return self._safe_name("ep_", character_id)

    # ── 캐시 컬렉션 접근 ─────────────────────────────────────────

    def _ef_kwarg(self) -> dict:
        """embedding_function 인자를 dict로 반환. 기본 임베딩 사용 시 빈 dict."""
        if self.embedding_fn and self.embedding_fn != "_USE_DEFAULT":
            return {"embedding_function": self.embedding_fn}
        return {}

    def _evict_cache_if_full(self) -> None:
        if len(self._col_cache) >= self._COL_CACHE_MAX:
            oldest_key = next(iter(self._col_cache))
            del self._col_cache[oldest_key]

    def _get_or_create(self, name: str) -> Any:
        """upsert용: 컬렉션을 가져오거나 생성. 캐시에 저장."""
        cached = self._col_cache.get(name)
        if cached is not None:
            return cached
        col = self.client.get_or_create_collection(name=name, **self._ef_kwarg())
        self._evict_cache_if_full()
        self._col_cache[name] = col
        self._neg_cache.discard(name)
        return col

    def _get_existing(self, name: str) -> Optional[Any]:
        """search용: 존재하는 컬렉션만 반환. 없으면 None."""
        cached = self._col_cache.get(name)
        if cached is not None:
            return cached
        if name in self._neg_cache:
            return None
        try:
            col = self.client.get_collection(name=name, **self._ef_kwarg())
            self._evict_cache_if_full()
            self._col_cache[name] = col
            return col
        except Exception:
            self._neg_cache.add(name)
            return None

    # ── 기억(Memory) 저장/검색 ───────────────────────────────────

    def upsert_memories(self, character_id: str, memories: list) -> None:
        """메모리 항목을 임베딩하여 Chroma에 저장.

        key 기반 upsert이므로 동일 key는 최신 value로 갱신.
        """
        if not memories or not self.embedding_fn:
            return
        try:
            collection = self._get_or_create(self._collection_name(character_id))
            documents = [f"{m.key}: {m.value}" for m in memories]
            ids = [str(m.key)[:100] for m in memories]
            now = int(time.time())
            metadatas = [
                {"timestamp": now, "type": "memory", "key": m.key}
                for m in memories
            ]
            collection.upsert(documents=documents, ids=ids, metadatas=metadatas)
            logger.info(f"Chroma upsert: {len(memories)}개 → char_{character_id}")
        except Exception as e:
            logger.error(f"Chroma upsert 실패: {e}")

    def search_relevant(
        self,
        character_id: str,
        query: str,
        n_results: int = 3,
        max_distance: float = 1.2,
    ) -> List[str]:
        """현재 메시지와 시맨틱으로 유사한 기억 검색."""
        if not self.embedding_fn:
            return []
        try:
            collection = self._get_existing(self._collection_name(character_id))
            if collection is None:
                return []

            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "distances"],
            )
            docs = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]

            filtered = []
            for doc, dist in zip(docs, distances):
                if dist <= max_distance:
                    filtered.append(doc)
            return filtered
        except Exception as e:
            logger.error(f"Chroma 검색 실패: {e}")
            return []

    # ── 에피소드(Episode) 저장/검색 ──────────────────────────────

    def upsert_episodes(self, character_id: str, episodes: List[Dict]) -> None:
        """에피소드 저장.

        episodes: [{"text": str, "emotion": str, "importance": int(1-5), "topic": str}]
        ID는 uuid4 기반으로 충돌 방지.
        """
        if not episodes or not self.embedding_fn:
            return
        try:
            collection = self._get_or_create(
                self._episode_collection_name(character_id),
            )
            now = int(time.time())
            documents = [ep["text"] for ep in episodes]
            ids = [f"ep_{uuid.uuid4().hex[:12]}" for _ in episodes]
            metadatas = [
                {
                    "timestamp": now,
                    "emotion": ep.get("emotion", "NEUTRAL"),
                    "importance": min(5, max(1, int(ep.get("importance", 3)))),
                    "topic": ep.get("topic", "")[:100],
                    "type": "episode",
                }
                for ep in episodes
            ]
            collection.upsert(documents=documents, ids=ids, metadatas=metadatas)
            logger.info(f"에피소드 저장: {len(episodes)}개 → ep_{character_id}")
        except Exception as e:
            logger.error(f"에피소드 저장 실패: {e}")

    def search_episodes(
        self,
        character_id: str,
        query: str,
        n_results: int = 3,
        time_decay: bool = True,
    ) -> List[Dict]:
        """시간 가중 에피소드 검색.

        score = semantic_similarity * time_decay * importance_weight
        반환: [{"text", "emotion", "importance", "topic", "score"}]
        """
        if not self.embedding_fn:
            return []
        try:
            collection = self._get_existing(
                self._episode_collection_name(character_id),
            )
            if collection is None:
                return []

            count = collection.count()
            if count == 0:
                return []

            fetch_n = min(n_results * 3, count)
            results = collection.query(
                query_texts=[query],
                n_results=fetch_n,
                include=["documents", "distances", "metadatas"],
            )

            docs = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            now = time.time()
            scored = []
            for doc, dist, meta in zip(docs, distances, metadatas):
                semantic_score = max(0, 1.0 - dist / 2.0)

                timestamp = meta.get("timestamp", now)
                days_ago = (now - timestamp) / 86400
                decay = math.exp(-days_ago / 30) if time_decay else 1.0

                importance = meta.get("importance", 3)
                importance_weight = 0.6 + (importance / 5) * 0.4

                final_score = semantic_score * decay * importance_weight
                scored.append({
                    "text": doc,
                    "emotion": meta.get("emotion", "NEUTRAL"),
                    "importance": importance,
                    "topic": meta.get("topic", ""),
                    "score": round(final_score, 3),
                })

            scored.sort(key=lambda x: x["score"], reverse=True)
            return scored[:n_results]

        except Exception as e:
            logger.error(f"에피소드 검색 실패: {e}")
            return []

    # ── 삭제 ─────────────────────────────────────────────────────

    def delete_character(self, character_id: str) -> None:
        """캐릭터의 기억 + 에피소드 컬렉션 삭제 (캐시도 정리)."""
        for col_name in [
            self._collection_name(character_id),
            self._episode_collection_name(character_id),
        ]:
            try:
                self.client.delete_collection(col_name)
                logger.info(f"Chroma 컬렉션 삭제: {col_name}")
            except Exception:
                pass  # 존재하지 않는 컬렉션 삭제 시도는 무시
            # 캐시 정리
            self._col_cache.pop(col_name, None)
            self._neg_cache.discard(col_name)

    def get_stats(self, character_id: str) -> Dict:
        """캐릭터별 벡터 스토어 통계."""
        stats: Dict[str, Any] = {"memories": 0, "episodes": 0}
        mem_col = self._get_existing(self._collection_name(character_id))
        if mem_col:
            stats["memories"] = mem_col.count()
        ep_col = self._get_existing(self._episode_collection_name(character_id))
        if ep_col:
            stats["episodes"] = ep_col.count()
        return stats
