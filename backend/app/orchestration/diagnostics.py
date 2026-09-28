"""Diagnostic utility for inspecting compiled LangGraph orchestration topology."""

from backend.app.orchestration.graph import WorkbenchOrchestrator


def get_graph_ascii() -> str:
    """Generate pure ASCII representation of the compiled orchestration state graph."""
    return """
============================================================
SOVEREIGN WORKBENCH ORCHESTRATION GRAPH TOPOLOGY
============================================================

         [START]
            |
            v
      [UNDERSTAND]
            |
            v
         [ROUTE]
            |
            v
         [PLAN]
            |
            v
     [RISK / POLICY]
            +---------------------+---------------------+
            |                     |                     |
            v (ALLOW)             v (REQUIRE_APPROVAL)  v (DENY)
        [EXECUTE] <---+       [WAITING_APPROVAL]    [FAILED]
            |         |           |                     |
            v         |           v (PAUSE / RESUME)    v
        [OBSERVE]     |       [DELIVER]             [DELIVER]
         +--> [REPLAN]+           |                     |
         |      |                 v                     v
         |      v               [END]                 [END]
         |   [DELIVER] ---> [END]
         |
         +--> [VERIFY]
         |      +--> [DELIVER (COMPLETED)] ---> [END]
         |      +--> [REPLAN]
         |
         +--> (fatal error) ---> [DELIVER (FAILED)] ---> [END]
============================================================
"""


def inspect_compiled_graph():
    """Inspect nodes and edges of the actual compiled LangGraph object."""
    orchestrator = WorkbenchOrchestrator()
    compiled_graph = orchestrator.graph.get_graph()

    print(get_graph_ascii())
    print("Compiled Nodes:")
    for node_id in sorted(compiled_graph.nodes.keys()):
        print(f"  - {node_id}")

    print("\nCompiled Edges:")
    for edge in compiled_graph.edges:
        source = edge.source
        target = edge.target
        cond = f" [cond={edge.data}]" if hasattr(edge, "data") and edge.data else ""
        print(f"  {source} ---> {target}{cond}")


if __name__ == "__main__":
    inspect_compiled_graph()
