"""Local index manifest store for Phase 8 RAG knowledge lifecycle management."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.app.rag.schemas import IndexManifest, IngestionStatus
from backend.app.rag.errors import StaleIndexError

logger = logging.getLogger("app.rag.manifest")

DEFAULT_MANIFEST_PATH = "data/knowledge/manifest.json"


class ManifestStore:
    """
    Persists and manages IndexManifest records for all indexed documents.
    Keyed by (source_hash, document_id) for deterministic identity.
    Local JSON file — no cloud persistence.
    """

    def __init__(self, path: str = DEFAULT_MANIFEST_PATH):
        self.path = path
        self._manifests: Dict[str, IndexManifest] = {}  # key: document_id
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                self._manifests = {
                    k: IndexManifest(**v) for k, v in raw.items()
                }
                logger.info("Manifest loaded: %d entries from %s", len(self._manifests), self.path)
            except Exception as e:
                logger.warning("Failed to load manifest from %s: %s", self.path, e)
                self._manifests = {}

    def save(self) -> None:
        """Persist manifest to local JSON file."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.model_dump() for k, v in self._manifests.items()},
                f,
                indent=2,
            )

    def upsert(self, manifest: IndexManifest) -> None:
        """Add or update a manifest entry."""
        manifest.updated_at = datetime.now(timezone.utc).isoformat()
        self._manifests[manifest.document_id] = manifest
        self.save()

    def get(self, document_id: str) -> Optional[IndexManifest]:
        return self._manifests.get(document_id)

    def get_by_hash(self, source_hash: str) -> Optional[IndexManifest]:
        for m in self._manifests.values():
            if m.source_hash == source_hash:
                return m
        return None

    def list(self) -> List[IndexManifest]:
        return list(self._manifests.values())

    def delete(self, document_id: str) -> bool:
        if document_id in self._manifests:
            del self._manifests[document_id]
            self.save()
            return True
        return False

    def mark_stale(self, document_id: str) -> None:
        m = self._manifests.get(document_id)
        if m:
            m.status = IngestionStatus.STALE
            m.updated_at = datetime.now(timezone.utc).isoformat()
            self.save()

    def detect_hash_change(self, document_id: str, new_hash: str) -> bool:
        """Return True if the document exists but has a different source_hash."""
        m = self.get(document_id)
        if m and m.source_hash != new_hash:
            return True
        return False

    def count(self) -> int:
        return len(self._manifests)
