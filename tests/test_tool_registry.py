"""Tests for ToolRegistry in Phase 3."""

import pytest
from backend.app.schemas.tools import ToolContract
from backend.app.tools.registry import (
    ToolRegistry,
    DuplicateToolError,
    UnknownToolError,
)


def test_tool_registry_prepopulated_defaults():
    """Verify that ToolRegistry pre-populates all 8 standard tools."""
    registry = ToolRegistry()
    expected_tools = [
        "file_read",
        "file_write",
        "ocr",
        "knowledge_search",
        "python_calculation",
        "sandbox_execute",
        "create_docx",
        "create_xlsx",
    ]
    for tool_id in expected_tools:
        assert registry.exists(tool_id), f"Expected tool {tool_id} to be registered"
        tool = registry.get(tool_id)
        assert tool is not None
        assert tool.tool_id == tool_id
        assert len(tool.capabilities) > 0


def test_tool_registry_registration_and_retrieval():
    """Verify dynamic tool registration and retrieval."""
    registry = ToolRegistry(populate_defaults=False)
    tool = ToolContract(
        tool_id="custom_tool",
        name="Custom Tool",
        description="Custom helper tool",
        capabilities=["custom_cap"],
        risk_level="LOW",
    )
    registry.register(tool)

    assert registry.exists("custom_tool")
    assert registry.get("custom_tool") == tool
    assert registry.get_or_raise("custom_tool") == tool


def test_tool_registry_duplicate_rejection():
    """Verify duplicate tool registration raises DuplicateToolError."""
    registry = ToolRegistry(populate_defaults=False)
    tool = ToolContract(
        tool_id="tool_1",
        name="Tool 1",
        description="First tool",
    )
    registry.register(tool)

    with pytest.raises(DuplicateToolError):
        registry.register(tool)

    # Overwrite works when enabled
    tool_updated = ToolContract(
        tool_id="tool_1",
        name="Tool 1 Updated",
        description="Updated tool",
    )
    registry.register(tool_updated, overwrite=True)
    assert registry.get("tool_1").name == "Tool 1 Updated"


def test_tool_registry_unknown_tool_error():
    """Verify querying non-existent tool raises UnknownToolError when required."""
    registry = ToolRegistry(populate_defaults=False)
    assert registry.get("non-existent") is None
    assert not registry.exists("non-existent")

    with pytest.raises(UnknownToolError):
        registry.get_or_raise("non-existent")

    with pytest.raises(UnknownToolError):
        registry.unregister("non-existent")


def test_tool_registry_find_by_capability():
    """Verify tool discovery by capability."""
    registry = ToolRegistry()
    calc_tools = registry.find_by_capability("calculation")
    assert any(t.tool_id == "python_calculation" for t in calc_tools)

    search_tools = registry.find_by_capability("evidence_retrieval")
    assert any(t.tool_id == "knowledge_search" for t in search_tools)


def test_tool_registry_find_by_risk():
    """Verify tool discovery by risk level."""
    registry = ToolRegistry()
    high_risk = registry.find_by_risk("HIGH")
    assert any(t.tool_id == "sandbox_execute" for t in high_risk)
    for tool in high_risk:
        assert tool.risk_level == "HIGH"
