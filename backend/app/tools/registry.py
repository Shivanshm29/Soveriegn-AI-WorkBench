"""Tool registry module."""

from typing import Dict, List, Optional
from backend.app.schemas.tools import ToolContract


class ToolRegistry:
    """Registry maintaining active tool declarations."""

    def __init__(self):
        self._tools: Dict[str, ToolContract] = {}

    def register(self, tool: ToolContract) -> None:
        self._tools[tool.tool_id] = tool

    def get(self, tool_id: str) -> Optional[ToolContract]:
        return self._tools.get(tool_id)

    def list_all(self) -> List[ToolContract]:
        return list(self._tools.values())
