"""Deterministic query processor for Phase 8 RAG."""

import re
from typing import Any, Dict, List, Optional

from backend.app.rag.schemas import QueryAnalysis

# Identifiers: part numbers, equipment IDs (PX-417, ISO 9001, etc.)
_IDENTIFIER_RE = re.compile(
    r"\b([A-Z]{1,5}[\-_]?\d{2,8}(?:[\-_][A-Z0-9]+)*)\b"
    r"|\b(ISO|IEC|ANSI|ASTM|DIN|BS|EN)\s*\d[\d\.\-]*\b",
    re.IGNORECASE,
)

# Numeric values with units
_NUMERIC_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mm|cm|m|in|kg|lb|bar|psi|rpm|Hz|kW|V|A|°C|°F)\b",
    re.IGNORECASE,
)

# Stop words for keyword extraction
_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "and", "or", "but", "if",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "this",
    "that", "these", "those", "what", "which", "who", "how", "when", "where",
}

# Sensitivity mapping (simple heuristic from query context)
_RESTRICTED_KEYWORDS = {"restricted", "classified", "secret", "confidential"}
_PUBLIC_KEYWORDS = {"public", "open", "standard"}


class QueryProcessor:
    """
    Performs deterministic query analysis for hybrid retrieval.
    No LLM is required for basic query normalization.
    """

    def analyze(
        self,
        query: str,
        sensitivity_scope: str = "INTERNAL",
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> QueryAnalysis:
        """Analyze a raw query string into structured QueryAnalysis."""
        normalized = query.strip().lower()

        # Extract exact identifiers (part numbers, standards, equipment IDs)
        identifiers = list({
            m.group(0).upper()
            for m in _IDENTIFIER_RE.finditer(query)
        })

        # Extract measurement values
        measurements = list({
            m.group(0)
            for m in _NUMERIC_RE.finditer(query)
        })
        entities = identifiers + measurements

        # Extract meaningful keywords (excluding stop words)
        raw_tokens = re.findall(r"[a-zA-Z]{3,}", normalized)
        keywords = list({
            t for t in raw_tokens
            if t not in _STOP_WORDS and len(t) >= 3
        })

        # Determine sensitivity scope from query context
        scope = sensitivity_scope
        q_lower = query.lower()
        if any(k in q_lower for k in _RESTRICTED_KEYWORDS):
            scope = "RESTRICTED"
        elif any(k in q_lower for k in _PUBLIC_KEYWORDS):
            scope = "PUBLIC"

        return QueryAnalysis(
            original_query=query,
            normalized_query=normalized,
            keywords=keywords[:20],
            exact_identifiers=identifiers[:10],
            entities=entities[:15],
            filters=metadata_filters or {},
            sensitivity_scope=scope,
        )

    def build_augmented_query(self, analysis: QueryAnalysis) -> str:
        """
        Build an augmented query string that boosts exact identifiers.
        Used for BM25 to improve recall on technical identifiers.
        """
        parts = [analysis.original_query]
        # Repeat identifiers to boost their BM25 weight
        for ident in analysis.exact_identifiers:
            parts.append(ident)
        return " ".join(parts)
