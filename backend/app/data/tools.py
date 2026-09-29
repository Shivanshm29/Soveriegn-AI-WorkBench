"""Tool declarations and registry integration for python_calculation."""

from typing import Dict, Any, Optional, List
from backend.app.schemas.tools import ToolContract
from backend.app.tools.registry import ToolRegistry
from backend.app.data.schemas import CalculationRequest
from backend.app.data.agent import DataAgent


def run_python_calculation(
    expression: Optional[str] = None,
    values: Optional[List[float]] = None,
    operation: Optional[str] = None,
    variables: Optional[Dict[str, float]] = None,
    task_id: str = "default_calc",
) -> Dict[str, Any]:
    """Execute deterministic Python calculation safely and return structured result dictionary."""
    agent = DataAgent()
    req = CalculationRequest(
        expression=expression,
        values=values,
        operation=operation,
        variables=variables or {},
        task_id=task_id,
    )
    result = agent.calculate(req)
    return result.to_dict()


def register_data_tools(registry: ToolRegistry) -> None:
    """Ensure python_calculation tool is registered in ToolRegistry."""
    tool = ToolContract(
        tool_id="python_calculation",
        name="Python Calculator",
        description="Executes deterministic analytical and mathematical calculations on structured data.",
        capabilities=["calculation", "tabular_data", "arithmetic", "statistics"],
        risk_level="MEDIUM",
        requires_approval=False,
        enabled=True,
    )
    registry.register(tool, overwrite=True)
