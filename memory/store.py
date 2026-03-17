"""
StockX — Memory Store
Primary: ChromaDB (vector similarity search)
Fallback: aiofiles JSONL (non-blocking line-based log)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

import aiofiles

logger = logging.getLogger(__name__)

_JSONL_PATH = Path(os.getenv("MEMORY_JSONL_PATH", "memory/memory.jsonl"))
_CHROMA_DIR = os.getenv("MEMORY_CHROMA_DIR", "memory/chroma_db")
_COLLECTION = "agentx_memory"

# Deduplication: skip adding if cosine distance < this threshold (very similar)
_DEDUP_DISTANCE_THRESHOLD = 0.03
# Max entries to keep in JSONL before pruning on startup
_JSONL_MAX_ENTRIES = int(os.getenv("MEMORY_JSONL_MAX_ENTRIES", "500"))


class MemoryStore:
    def __init__(self) -> None:
        self._chroma_ok = False
        self._collection: Any = None
        self._jsonl_lock = asyncio.Lock()
        self._init_chroma()
        # Schedule JSONL pruning lazily — will run on first event loop iteration
        self._prune_scheduled = False

    def _init_chroma(self) -> None:
        try:
            import chromadb
            from chromadb.config import Settings

            client = chromadb.PersistentClient(
                path=_CHROMA_DIR,
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = client.get_or_create_collection(
                name=_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
            self._chroma_ok = True
            logger.info("ChromaDB initialised at %s", _CHROMA_DIR)
        except Exception as exc:
            logger.warning("ChromaDB unavailable (%s) — using JSONL fallback", exc)
            self._chroma_ok = False

    # ------------------------------------------------------------------
    async def _ensure_pruned(self) -> None:
        """Run startup JSONL pruning once on the first async call."""
        if not self._prune_scheduled:
            self._prune_scheduled = True
            await self._jsonl_prune_on_startup()

    async def add(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        await self._ensure_pruned()
        metadata = metadata or {}
        metadata["ts"] = time.time()
        doc_id = str(uuid.uuid4())

        if self._chroma_ok and self._collection is not None:
            try:
                # Deduplication: check if a nearly identical document already exists
                if await self._is_duplicate_chroma(text):
                    logger.debug("Skipping duplicate memory entry (ChromaDB)")
                    return

                self._collection.add(
                    documents=[text],
                    metadatas=[metadata],
                    ids=[doc_id],
                )
                return
            except Exception as exc:
                logger.warning("ChromaDB add failed (%s) — writing to JSONL", exc)

        await self._jsonl_append({"id": doc_id, "text": text, "metadata": metadata})

    async def _is_duplicate_chroma(self, text: str) -> bool:
        """Return True if a very similar document already exists in ChromaDB."""
        try:
            count = self._collection.count()
            if count == 0:
                return False
            results = self._collection.query(
                query_texts=[text],
                n_results=1,
            )
            distances = results.get("distances", [[]])[0]
            if distances and distances[0] < _DEDUP_DISTANCE_THRESHOLD:
                return True
        except Exception as exc:
            logger.debug("Dedup check failed: %s", exc)
            self._chroma_ok  = False
            self._collection = None
        return False

    # ------------------------------------------------------------------
    async def search(self, query: str, top_k: int = 3) -> list[str]:
        await self._ensure_pruned()
        if self._chroma_ok and self._collection is not None:
            try:
                results = self._collection.query(
                    query_texts=[query],
                    n_results=top_k,
                )
                docs: list[str] = results.get("documents", [[]])[0]
                return docs
            except Exception as exc:
                logger.warning("ChromaDB search failed (%s) — using JSONL fallback", exc)
                # Permanently disable ChromaDB so subsequent add() calls don't
                # attempt _is_duplicate_chroma() against a potentially corrupted client.
                self._chroma_ok  = False
                self._collection = None

        return await self._jsonl_search(query, top_k)

    # ------------------------------------------------------------------
    async def cleanup(self, max_entries: int = 500) -> int:
        """
        Remove the oldest entries from ChromaDB or JSONL to stay within max_entries.
        Returns the number of entries deleted.
        """
        if self._chroma_ok and self._collection is not None:
            return await self._cleanup_chroma(max_entries)
        return await self._cleanup_jsonl(max_entries)

    async def _cleanup_chroma(self, max_entries: int) -> int:
        try:
            count = self._collection.count()
            if count <= max_entries:
                return 0
            # Fetch all entries sorted by timestamp, delete oldest
            results = self._collection.get(include=["metadatas"])
            ids = results.get("ids", [])
            metadatas = results.get("metadatas", [])
            # Sort by timestamp ascending (oldest first)
            paired = sorted(
                zip(ids, metadatas),
                key=lambda x: x[1].get("ts", 0) if x[1] else 0,
            )
            to_delete = len(paired) - max_entries
            if to_delete <= 0:
                return 0
            delete_ids = [id_ for id_, _ in paired[:to_delete]]
            self._collection.delete(ids=delete_ids)
            logger.info("ChromaDB cleanup: deleted %d old entries", to_delete)
            return to_delete
        except Exception as exc:
            logger.warning("ChromaDB cleanup failed: %s", exc)
            return 0

    async def _cleanup_jsonl(self, max_entries: int) -> int:
        if not _JSONL_PATH.exists():
            return 0
        async with self._jsonl_lock:
            try:
                async with aiofiles.open(_JSONL_PATH, "r", encoding="utf-8") as f:
                    lines = [line async for line in f if line.strip()]
                if len(lines) <= max_entries:
                    return 0
                keep = lines[-max_entries:]
                async with aiofiles.open(_JSONL_PATH, "w", encoding="utf-8") as f:
                    await f.write("".join(keep))
                deleted = len(lines) - max_entries
                logger.info("JSONL cleanup: deleted %d old entries", deleted)
                return deleted
            except Exception as exc:
                logger.warning("JSONL cleanup failed: %s", exc)
                return 0

    async def _jsonl_prune_on_startup(self) -> None:
        """Silently prune JSONL on startup if over the limit."""
        try:
            if _JSONL_PATH.exists():
                await self._cleanup_jsonl(_JSONL_MAX_ENTRIES)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # JSONL helpers (non-blocking via aiofiles)
    # ------------------------------------------------------------------
    async def _jsonl_append(self, record: dict[str, Any]) -> None:
        _JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
        async with self._jsonl_lock:
            async with aiofiles.open(_JSONL_PATH, "a", encoding="utf-8") as f:
                await f.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def _jsonl_search(self, query: str, top_k: int) -> list[str]:
        if not _JSONL_PATH.exists():
            return []
        results: list[str] = []
        query_lower = query.lower()
        try:
            async with aiofiles.open(_JSONL_PATH, "r", encoding="utf-8") as f:
                async for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        text: str = record.get("text", "")
                        if any(word in text.lower() for word in query_lower.split()):
                            results.append(text)
                    except json.JSONDecodeError:
                        continue
        except Exception as exc:
            logger.warning("JSONL read error: %s", exc)
        # Return most-recent matches (last lines are newest)
        return results[-top_k:]
