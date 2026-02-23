"""ChromaDB 벡터 스토어 - RAG 기반 장기 기억 검색"""

import logging
from typing import List

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
        """메모리 항목을 임베딩하여 Chroma에 저장"""
        if not memories or not self.embedding_fn:
            return
        try:
            collection = self.client.get_or_create_collection(
                name=self._collection_name(character_id),
                embedding_function=self.embedding_fn
            )
            documents = [f"{m.key}: {m.value}" for m in memories]
            # id는 key 기반 (같은 key면 upsert로 갱신)
            ids = [str(m.key)[:100] for m in memories]
            collection.upsert(documents=documents, ids=ids)
            logger.info(f"Chroma upsert: {len(memories)}개 → char_{character_id}")
        except Exception as e:
            logger.error(f"Chroma upsert 실패: {e}")

    def search_relevant(self, character_id: str, query: str, n_results: int = 3) -> List[str]:
        """현재 메시지와 시맨틱으로 유사한 기억 검색"""
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
                n_results=min(n_results, count)
            )
            return results["documents"][0] if results.get("documents") else []
        except Exception as e:
            logger.error(f"Chroma 검색 실패: {e}")
            return []

    def delete_character(self, character_id: str) -> None:
        """캐릭터 삭제 시 컬렉션 제거"""
        try:
            col_name = self._collection_name(character_id)
            existing = [c.name for c in self.client.list_collections()]
            if col_name in existing:
                self.client.delete_collection(col_name)
        except Exception as e:
            logger.error(f"Chroma 컬렉션 삭제 실패: {e}")
