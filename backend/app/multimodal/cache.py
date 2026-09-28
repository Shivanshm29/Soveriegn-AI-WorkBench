"""Local hash-based cache for multimodal document extraction results."""

import json
import os
from typing import Dict, Any, List, Optional
from backend.app.multimodal.schemas import DocumentEvidence

DEFAULT_CACHE_DIR = os.path.abspath(os.path.join("data", "cache", "evidence"))


class DocumentCache:
    """Safe local cache keyed by cryptographic source_hash, page_number, and extraction_method."""

    def __init__(self, cache_dir: str = DEFAULT_CACHE_DIR):
        self.cache_dir = cache_dir
        self._memory_cache: Dict[str, List[DocumentEvidence]] = {}
        os.makedirs(self.cache_dir, exist_ok=True)

    def _build_key(
        self,
        source_hash: str,
        page_number: int,
        extraction_method: str,
        profile: str = "default",
    ) -> str:
        """Construct deterministic cache key. Never uses file path or filename."""
        return f"{source_hash}_p{page_number}_{extraction_method}_{profile}"

    def get(
        self,
        source_hash: str,
        page_number: int,
        extraction_method: str,
        profile: str = "default",
    ) -> Optional[List[DocumentEvidence]]:
        """Retrieve cached evidence if source hash matches."""
        key = self._build_key(source_hash, page_number, extraction_method, profile)

        # 1. Memory check
        if key in self._memory_cache:
            return self._memory_cache[key]

        # 2. Disk check
        file_path = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                evidence = [DocumentEvidence.model_validate(item) for item in data]
                self._memory_cache[key] = evidence
                return evidence
            except Exception:
                return None

        return None

    def put(
        self,
        source_hash: str,
        page_number: int,
        extraction_method: str,
        evidence: List[DocumentEvidence],
        profile: str = "default",
    ) -> None:
        """Store evidence in memory and disk keyed by source hash."""
        key = self._build_key(source_hash, page_number, extraction_method, profile)
        self._memory_cache[key] = evidence

        file_path = os.path.join(self.cache_dir, f"{key}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump([item.model_dump(mode="json") for item in evidence], f, indent=2)
        except Exception:
            pass

    def clear(self) -> None:
        """Clear memory cache."""
        self._memory_cache.clear()
