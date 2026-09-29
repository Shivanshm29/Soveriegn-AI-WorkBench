"""Local Coding Agent package."""

from backend.app.coding.schemas import (
    CodingTask,
    CodeGenerationResult,
    CodeInspectionResult,
    CodeRepairResult,
)
from backend.app.coding.agent import CodingAgent
from backend.app.coding.tools import register_coding_tools, get_default_coding_agent

__all__ = [
    "CodingTask",
    "CodeGenerationResult",
    "CodeInspectionResult",
    "CodeRepairResult",
    "CodingAgent",
    "register_coding_tools",
    "get_default_coding_agent",
]
