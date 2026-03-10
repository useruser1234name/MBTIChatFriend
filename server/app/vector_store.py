"""ChromaDB 벡터 스토어 - RAG 기반 장기 기억 + 에피소드 기억 검색"""

import logging
import math
import time
from typing import Dict, List, Optional

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


def get_store() -> "VectorStore | None":
    global _store
    if not CHROMA_AVAILABLE:
        return None
    if _store is None:
        try:
            _store = VectorStore()
        except Exception as e:
            logger.error(f"VectorStore 초기화 실패: {e}")
    return _store


class VectorStore:
    def __init__(self, persist_dir: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.embedding_fn = None
        if OPENAI_API_KEY:
            self.embedding_fn = OpenAIEmbeddingFunction(
                api_key=OPENAI_API_KEY,
                model_name="text-embedding-3-small"
            )

    def _collection_name(self, character_id: str) -> str:
        """ChromaDB 컬렉션명: 영숫자+언더스코어, 3~63자 제한"""
        safe = "".join(c if c.isalnum() else "_" for c in str(character_id))
        return f"char_{safe}"[:63]

    def upsert_memories(self, character_id: str, memories: list) -> None:
        """메모리 항목을 임베딩하여 Chroma에 저장 (메타데이터 포함)"""
        if not memories or not self.embedding_fn:
            return
        try:
            collection = self.client.get_or_create_collection(
                name=self._collection_name(character_id),
                embedding_function=self.embedding_fn
            )
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
        """현재 메시지와 시맨틱으로 유사한 기억 검색 (유사도 임계값 필터링)"""
        if not self.embedding_fn:
            return []
        try:
            col_name = self._collection_name(character_id)
            existing = [c.name for c in self.client.list_collections()]
            if col_name not in existing:
                return []
            collection = self.client.get_collection(
                name=col_name,
                embedding_function=self.embedding_fn
            )
            count = collection.count()
            if count == 0:
                return []
            results = collection.query(
                query_texts=[query],
                n_results=min(n_results, count),
                include=["documents", "distances"],
            )
            docs = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]

            # 유사도 임계값 필터링: distance가 너무 큰(관련 없는) 결과 제외
            filtered = []
            for doc, dist in zip(docs, distances):
                if dist <= max_distance:
                    filtered.append(doc)
                else:
                    logger.debug(f"Chroma 결과 제외 (distance={dist:.2f}): {doc[:50]}")
            return filtered
        except Exception as e:
            logger.error(f"Chroma 검색 실패: {e}")
            return []

    # ── 에피소드 기억 ──────────────────────────────────────────────

    def _episode_collection_name(self, character_id: str) -> str:
        """에피소드 전용 컬렉션명"""
        safe = "".join(c if c.isalnum() else "_" for c in str(character_id))
        return f"ep_{safe}"[:63]

    def upsert_episodes(self, character_id: str, episodes: List[Dict]) -> None:
        """에피소드 저장 (감정, 중요도 메타데이터 포함).

        episodes: [{"text": str, "emotion": str, "importance": int(1-5), "topic": str}]
        """
        if not episodes or not self.embedding_fn:
            return
        try:
            collection = self.client.get_or_create_collection(
                name=self._episode_collection_name(character_id),
                embedding_function=self.embedding_fn,
            )
            now = int(time.time())
            documents = [ep["text"] for ep in episodes]
            ids = [f"ep_{now}_{i}" for i in range(len(episodes))]
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
        """시간 가중 에피소드 검색 - 최근 기억이 더 강하게.

        반환: [{"text": str, "emotion": str, "importance": int, "score": float}]
        """
        if not self.embedding_fn:
            return []
        try:
            col_name = self._episode_collection_name(character_id)
            existing = [c.name for c in self.client.list_collections()]
            if col_name not in existing:
                return []
            collection = self.client.get_collection(
                name=col_name,
                embedding_function=self.embedding_fn,
            )
            count = collection.count()
            if count == 0:
                return []

            # 더 많이 검색해서 시간 가중 후 상위 n개 선택
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
                # 시맨틱 유사도 (distance가 낮을수록 유사)
                semantic_score = max(0, 1.0 - dist / 2.0)

                # 시간 감쇄: exp(-days_ago / 30)
                timestamp = meta.get("timestamp", now)
                days_ago = (now - timestamp) / 86400
                decay = math.exp(-days_ago / 30) if time_decay else 1.0

                # 중요도 가중치
                importance = meta.get("importance", 3)
                importance_weight = 0.6 + (importance / 5) * 0.4  # 0.8 ~ 1.4

                final_score = semantic_score * decay * importance_weight

                scored.append({
                    "text": doc,
                    "emotion": meta.get("emotion", "NEUTRAL"),
                    "importance": importance,
                    "topic": meta.get("topic", ""),
                    "score": round(final_score, 3),
                })

            # 점수 순 정렬 후 상위 n개
            scored.sort(key=lambda x: x["score"], reverse=True)
            return scored[:n_results]

        except Exception as e:
            logger.error(f"에피소드 검색 실패: {e}")
            return []

    def delete_character(self, character_id: str) -> None:
        """캐릭터 삭제 시 컬렉션 제거 (기억 + 에피소드)"""
        try:
            existing = [c.name for c in self.client.list_collections()]
            for col_name in [
                self._collection_name(character_id),
                self._episode_collection_name(character_id),
            ]:
                if col_name in existing:
                    self.client.delete_collection(col_name)
        except Exception as e:
            logger.error(f"Chroma 컬렉션 삭제 실패: {e}")
