"""Test A: Graph Construction and Compilation."""

import pytest
from backend.app.orchestration.graph import (
    WorkbenchOrchestrator,
    build_orchestration_graph,
)
from backend.app.orchestration.nodes import OrchestrationNodes
from backend.app.models.registry import ModelRegistry
from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry


def test_graph_compiles_successfully():
    """Verify that StateGraph compiles without errors."""
    nodes = OrchestrationNodes(
        model_registry=ModelRegistry(),
        agent_registry=AgentRegistry(),
        tool_registry=ToolRegistry(),
    )
    compiled_graph = build_orchestration_graph(nodes)
    assert compiled_graph is not None


def test_required_nodes_exist():
    """Verify all 9 lifecycle nodes exist in the compiled graph."""
    orchestrator = WorkbenchOrchestrator()
    graph_obj = orchestrator.graph.get_graph()

    expected_nodes = {
        "__start__",
        "understand",
        "route",
        "plan",
        "policy",
        "execute",
        "observe",
        "replan",
        "verify",
        "deliver",
        "__end__",
    }
    actual_nodes = set(graph_obj.nodes.keys())
    for node in expected_nodes:
        assert node in actual_nodes, f"Missing required node: {node}"


def test_expected_edges_exist_and_end_is_reachable():
    """Verify edges connect lifecycle stages and lead to END."""
    orchestrator = WorkbenchOrchestrator()
    graph_obj = orchestrator.graph.get_graph()

    edge_pairs = {(e.source, e.target) for e in graph_obj.edges}

    # Verify sequential edges
    assert ("__start__", "understand") in edge_pairs
    assert ("understand", "route") in edge_pairs
    assert ("route", "plan") in edge_pairs
    assert ("plan", "policy") in edge_pairs
    assert ("policy", "execute") in edge_pairs
    assert ("execute", "observe") in edge_pairs
    assert ("deliver", "__end__") in edge_pairs

    # Verify branching edges
    assert ("observe", "verify") in edge_pairs
    assert ("observe", "replan") in edge_pairs
    assert ("observe", "deliver") in edge_pairs
    assert ("replan", "execute") in edge_pairs
    assert ("replan", "deliver") in edge_pairs
    assert ("verify", "deliver") in edge_pairs
