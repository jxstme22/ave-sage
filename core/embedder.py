"""
AVE SAGE — Embedder
Manages the ChromaDB vector store.
Handles upsert, deduplication, and retrieval of MemoryChunks.
"""

import logging
import time
from typing import Optional
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from core.chunker import MemoryChunk

logger = logging.getLogger(__name__)


class VectorStore:
    """
    ChromaDB-backed persistent vector store for AVE SAGE memory.
    Supports upsert (idempotent), semantic search, and filtered queries.
    """

    def __init__(
        self,
        persist_dir: str = "./data/chroma",
        collection_name: str = "ave_sage_memory",
        embedding_provider: str = "openai",
        embedding_model: str = "text-embedding-3-small",
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
    ):
        self.collection_name = collection_name

        # Embedding function
        if embedding_provider == "openai" and openai_api_key:
            self._embed_fn = embedding_functions.OpenAIEmbeddingFunction(
                api_key=openai_api_key,
                model_name=embedding_model,
            )
        else:
            # Fallback: local sentence-transformers (no API key needed)
            try:
                self._embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
                logger.info("[EMBEDDER] Using local SentenceTransformer (all-MiniLM-L6-v2)")
            except Exception as e:
                logger.warning(f"[EMBEDDER] SentenceTransformer unavailable ({e}), falling back to DefaultEmbeddingFunction")
                self._embed_fn = embedding_functions.DefaultEmbeddingFunction()

        # Persistent ChromaDB client
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"[EMBEDDER] Collection '{collection_name}' loaded — {self._collection.count()} docs")

    def upsert(self, chunk: MemoryChunk) -> bool:
        """Insert or update a single MemoryChunk. Idempotent by chunk.id."""
        doc = chunk.to_chroma_doc()
        try:
            self._collection.upsert(
                ids=[doc["id"]],
                documents=[doc["document"]],
                metadatas=[doc["metadata"]],
            )
            logger.debug(f"[EMBEDDER] Upserted chunk {doc['id']} ({chunk.chunk_type})")
            return True
        except Exception as e:
            logger.error(f"[EMBEDDER] Upsert failed for {doc['id']}: {e}")
            return False

    def upsert_batch(self, chunks: list[MemoryChunk]) -> int:
        """Batch upsert. Returns count of successfully stored chunks."""
        if not chunks:
            return 0
        docs = [c.to_chroma_doc() for c in chunks]
        try:
            self._collection.upsert(
                ids=[d["id"] for d in docs],
                documents=[d["document"] for d in docs],
                metadatas=[d["metadata"] for d in docs],
            )
            logger.info(f"[EMBEDDER] Batch upserted {len(docs)} chunks")
            return len(docs)
        except Exception as e:
            logger.error(f"[EMBEDDER] Batch upsert failed: {e}")
            return 0

    def query(
        self,
        query_text: str,
        n_results: int = 8,
        chain_filter: Optional[str] = None,
        token_filter: Optional[str] = None,
        chunk_type_filter: Optional[str] = None,
        min_timestamp: Optional[int] = None,
        similarity_threshold: float = 0.0,
    ) -> list[dict]:
        """
        Semantic search over the knowledge base.
        Returns list of {id, document, metadata, distance} dicts.
        Lower distance = more similar (cosine).
        """
        where_clauses = []
        if chain_filter:
            where_clauses.append({"chain": {"$eq": chain_filter}})
        if token_filter:
            where_clauses.append({"token": {"$eq": token_filter}})
        if chunk_type_filter:
            where_clauses.append({"chunk_type": {"$eq": chunk_type_filter}})
        if min_timestamp:
            where_clauses.append({"timestamp": {"$gte": min_timestamp}})

        where = None
        if len(where_clauses) == 1:
            where = where_clauses[0]
        elif len(where_clauses) > 1:
            where = {"$and": where_clauses}

        try:
            results = self._collection.query(
                query_texts=[query_text],
                n_results=min(n_results, max(self._collection.count(), 1)),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error(f"[EMBEDDER] Query failed: {e}")
            return []

        output = []
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            similarity = 1 - distance  # convert cosine distance → similarity
            if similarity < similarity_threshold:
                continue
            output.append({
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "similarity": round(similarity, 4),
            })

        return output

    def count(self) -> int:
        """Return total number of chunks stored."""
        return self._collection.count()

    def recent_chunks(self, n: int = 10) -> list[dict]:
        """Return the most recently stored chunks (by timestamp metadata), no semantic filter."""
        try:
            total = self._collection.count()
            if total == 0:
                return []
            results = self._collection.get(
                limit=min(n * 4, total),  # fetch extra then sort
                include=["documents", "metadatas"],
            )
            paired = list(zip(
                results["ids"],
                results["documents"],
                results["metadatas"],
            ))
            # Sort by timestamp descending
            paired.sort(key=lambda x: x[2].get("timestamp", 0), reverse=True)
            return [
                {"id": p[0], "document": p[1], "metadata": p[2], "similarity": 0.0}
                for p in paired[:n]
            ]
        except Exception as e:
            logger.error(f"[EMBEDDER] recent_chunks failed: {e}")
            return []

    def query_outcomes_for_signal(self, signal_type: str, chain: str, n: int = 5) -> list[dict]:
        """
        Specialized query: retrieve historical outcomes for a specific signal type on a chain.
        Used by the RAG engine to build performance statistics.
        """
        return self.query(
            query_text=f"trade outcome result for signal {signal_type} on {chain}",
            n_results=n,
            chain_filter=chain,
            chunk_type_filter="outcome_event",
        )

    def get_recent(self, chain: str, limit: int = 20, lookback_hours: int = 24) -> list[dict]:
        """Fetch recent events for a chain — used for dashboard/context building."""
        min_ts = int(time.time()) - (lookback_hours * 3600)
        try:
            results = self._collection.get(
                where={"$and": [{"chain": {"$eq": chain}}, {"timestamp": {"$gte": min_ts}}]},
                limit=limit,
                include=["documents", "metadatas"],
            )
            return [
                {"id": results["ids"][i], "document": results["documents"][i], "metadata": results["metadatas"][i],
                 "significance": results["metadatas"][i].get("significance", 0)}
                for i in range(len(results["ids"]))
            ]
        except Exception as e:
            logger.error(f"[EMBEDDER] get_recent failed: {e}")
            return []

    def stats(self) -> dict:
        """Returns summary stats for the dashboard."""
        total = self._collection.count()
        # Count by chunk_type using metadata filters
        type_counts = {}
        for ct in ["market_event", "trade_event", "pattern_event", "outcome_event"]:
            try:
                r = self._collection.get(where={"chunk_type": {"$eq": ct}}, limit=1)
                # ChromaDB doesn't natively count by filter, so we approximate
                type_counts[ct] = "?"
            except Exception:
                type_counts[ct] = "?"
        return {"total_chunks": total, "chunk_types": type_counts}
