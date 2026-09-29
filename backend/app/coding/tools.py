"""Coding Agent tools and registry integration."""

from typing import Dict, Any, Optional
from backend.app.schemas.tools import ToolContract
from backend.app.tools.registry import ToolRegistry
from backend.app.coding.agent import CodingAgent


def register_coding_tools(registry: ToolRegistry) -> None:
    """Register coding agent tools into ToolRegistry."""
    # Ensure sandbox_execute is registered
    from backend.app.sandbox.tools import register_sandbox_tools
    register_sandbox_tools(registry)


def get_default_coding_agent() -> CodingAgent:
    """Initialize and return a default CodingAgent instance."""
    return CodingAgent()
