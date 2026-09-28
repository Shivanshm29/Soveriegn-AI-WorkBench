"""Test N: Zero External Egress during Orchestration Execution."""

import socket
import pytest
from unittest.mock import patch
from backend.app.orchestration.graph import WorkbenchOrchestrator


def test_orchestration_executes_with_zero_external_network_access():
    """Verify graph execution operates entirely locally without external sockets."""
    orchestrator = WorkbenchOrchestrator()
    orchestrator.nodes.agent_executor.register_handler(
        "reasoning_agent",
        lambda step, ctx: {"findings": ["Air-gap preserved", "Zero outbound packets"]},
    )

    with patch.object(socket, "socket", side_effect=RuntimeError("Unexpected external network egress")):
        final_state = orchestrator.run("Verify zero egress execution")

    assert final_state["task_status"] == "COMPLETED"
    assert "findings" in final_state["final_result"]["outputs"]
