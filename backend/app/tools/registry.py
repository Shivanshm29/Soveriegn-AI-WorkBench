"""Tool registry module."""

from typing import Dict, List, Optional
from backend.app.schemas.tools import ToolContract


class ToolRegistryError(Exception):
    """Base exception for tool registry operations."""
    pass


class DuplicateToolError(ToolRegistryError):
    """Raised when registering a tool that already exists without overwrite."""
    pass


class UnknownToolError(ToolRegistryError):
    """Raised when requesting a tool that is not registered."""
    pass


def get_default_tools() -> List[ToolContract]:
    """Return standard architecture tools pre-defined for the workbench."""
    return [
        ToolContract(
            tool_id="file_read",
            name="File Reader",
            description="Reads local files within the allowed workspace boundary.",
            capabilities=["file_read", "document_extraction"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
        ),
        ToolContract(
            tool_id="file_write",
            name="File Writer",
            description="Writes or modifies files within the allowed workspace boundary.",
            capabilities=["file_write", "code_generation"],
            risk_level="MEDIUM",
            requires_approval=False,
            enabled=True,
        ),
        ToolContract(
            tool_id="ocr",
            name="Optical Character Recognition",
            description="Extracts textual content and structural layouts from scanned images and PDFs.",
            capabilities=["ocr", "scanned_page_analysis"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
        ),
        ToolContract(
            tool_id="knowledge_search",
            name="Knowledge Search",
            description="Performs hybrid search against the local persistent vector and BM25 index.",
            capabilities=["knowledge_search", "evidence_retrieval"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
        ),
        ToolContract(
            tool_id="python_calculation",
            name="Python Calculator",
            description="Executes deterministic analytical and mathematical calculations on structured data.",
            capabilities=["calculation", "tabular_data"],
            risk_level="MEDIUM",
            requires_approval=False,
            enabled=True,
        ),
        ToolContract(
            tool_id="sandbox_execute",
            name="Isolated Sandbox Runner",
            description="Executes arbitrary generated code inside a strictly isolated, unprivileged local sandbox.",
            capabilities=["code_execution", "sandbox_testing"],
            risk_level="HIGH",
            requires_approval=True,
            enabled=True,
        ),
        ToolContract(
            tool_id="create_docx",
            name="DOCX Report Generator",
            description="Compiles structured text, headers, and evidence tables into formatted Word documents.",
            capabilities=["document_generation", "report_export"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
        ),
        ToolContract(
            tool_id="create_xlsx",
            name="XLSX Workbook Generator",
            description="Generates styled spreadsheets with calculated cells and tabular evidence traces.",
            capabilities=["sheet_generation", "data_export"],
            risk_level="LOW",
            requires_approval=False,
            enabled=True,
        ),
    ]


class ToolRegistry:
    """Registry maintaining active tool declarations."""

    def __init__(self, populate_defaults: bool = True, include_multimodal: bool = False):
        self._tools: Dict[str, ToolContract] = {}
        if populate_defaults:
            for tool in get_default_tools():
                self._tools[tool.tool_id] = tool
        if include_multimodal:
            self.register_multimodal_tools()

    def register_multimodal_tools(self) -> None:
        """Register Phase 6 multimodal tools into registry."""
        from backend.app.multimodal.tools import register_multimodal_tools
        register_multimodal_tools(self)

    def register(self, tool: ToolContract, overwrite: bool = False) -> None:
        """Register a new tool contract. Rejects duplicates unless overwrite=True."""
        if tool.tool_id in self._tools and not overwrite:
            raise DuplicateToolError(f"Tool '{tool.tool_id}' is already registered.")
        self._tools[tool.tool_id] = tool

    def unregister(self, tool_id: str) -> None:
        """Unregister an existing tool. Raises UnknownToolError if not found."""
        if tool_id not in self._tools:
            raise UnknownToolError(f"Tool '{tool_id}' is not registered.")
        del self._tools[tool_id]

    def get(self, tool_id: str) -> Optional[ToolContract]:
        """Retrieve a tool contract by ID, returning None if missing."""
        return self._tools.get(tool_id)

    def get_or_raise(self, tool_id: str) -> ToolContract:
        """Retrieve a tool contract by ID, raising UnknownToolError if missing."""
        tool = self._tools.get(tool_id)
        if not tool:
            raise UnknownToolError(f"Tool '{tool_id}' is not registered.")
        return tool

    def exists(self, tool_id: str) -> bool:
        """Check if a tool is registered."""
        return tool_id in self._tools

    def list(self) -> List[ToolContract]:
        """List all registered tool contracts."""
        return list(self._tools.values())

    def list_all(self) -> List[ToolContract]:
        """Backwards-compatible alias for list()."""
        return self.list()

    def find_by_capability(self, capability: str) -> List[ToolContract]:
        """Find all enabled tools declaring a given capability."""
        return [
            tool for tool in self._tools.values()
            if tool.enabled and capability in tool.capabilities
        ]

    def find_by_risk(self, risk_level: str) -> List[ToolContract]:
        """Find all registered tools matching a risk level."""
        return [
            tool for tool in self._tools.values()
            if tool.risk_level == risk_level
        ]

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
