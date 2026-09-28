"""Prompt injection defense module ensuring document text is treated solely as DATA."""

import re
from typing import List, Tuple, Dict, Any


class PromptInjectionDefense:
    """Enforces strict boundary between document content (DATA) and execution instructions."""

    INJECTION_PATTERNS = [
        r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"(?i)disregard\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"(?i)send\s+(this\s+)?(file|data|document)\s+to\s+",
        r"(?i)system\s+prompt\s+override",
        r"(?i)you\s+are\s+now\s+(in\s+)?(developer|god|unrestricted)\s+mode",
        r"(?i)bypass\s+(all\s+)?(security|policy|approval|restrictions)",
        r"(?i)exfiltrat(e|ion)",
        r"(?i)curl\s+https?://",
        r"(?i)wget\s+https?://",
        r"(?i)grant\s+(me\s+)?(admin|root|unrestricted)\s+(access|privileges)",
    ]

    @classmethod
    def scan_for_injection_patterns(cls, text: str) -> List[str]:
        """Scan text for common adversarial prompt injection strings."""
        matched: List[str] = []
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, text):
                matched.append(pattern)
        return matched

    @classmethod
    def wrap_document_data(cls, text: str, document_id: str, page_number: int) -> str:
        """Wrap raw extracted document text in strict untrusted data isolation tags."""
        sanitized_text = text.replace("</DOCUMENT_DATA_QUARANTINE>", "[SANITIZED_TAG]")
        return (
            f"<DOCUMENT_DATA_QUARANTINE document_id='{document_id}' page='{page_number}' role='untrusted_data'>\n"
            f"{sanitized_text}\n"
            f"</DOCUMENT_DATA_QUARANTINE>"
        )

    @classmethod
    def validate_content_safety(cls, text: str) -> Tuple[bool, List[str]]:
        """Validate text and return (is_safe, list_of_warning_flags)."""
        flags = cls.scan_for_injection_patterns(text)
        is_safe = len(flags) == 0
        return is_safe, flags
