# Phase 4 Implementation Report — LangGraph Orchestration

## Executive Summary
Phase 4 of the Sovereign On-Premise Agentic AI Workbench implements the central stateful agent execution workflow using LangGraph (`langgraph==1.2.12`). This orchestration layer binds together the foundational components from Phases 0–3 (`ModelRegistry`, `AgentRegistry`, `ToolRegistry`, `ModelRuntime`, `SovereigntyPolicy`, `TaskState`, `LocalStateStore`, and `A2AMessage`) into an autonomous, resilient, and verifiable execution pipeline.

All operations strictly honor the zero-egress air-gap invariant (`SOVEREIGN_MODE=True`). In accordance with architectural boundaries, Phase 4 implements the orchestration framework and truthful execution dispatch while cleanly delegating risk/human approvals to Phase 5.

---

## 1. LangGraph Architecture

The orchestration engine is structured as a compiled LangGraph `StateGraph`:

```
           +-----------+
           |   START   |
           +-----+-----+
                 |
                 v
          +-------------+
          | UNDERSTAND  |
          +------+------+
                 |
                 v
          +-------------+
          |    ROUTE    |
          +------+------+
                 |
                 v
          +-------------+
          |    PLAN     |
          +------+------+
                 |
                 v
          +-------------+
          |   POLICY    |
          +------+------+
                 |
                 v
          +-------------+  recoverable failure
          |   EXECUTE   |<--------------------+
          +------+------+                     |
                 |                            |
                 v                            |
          +-------------+                     |
          |   OBSERVE   |                     |
          +------+------+                     |
                 |                            |
        +--------+--------+                   |
        |                 |                   |
     success      recoverable failure         |
        |                 |                   |
        v                 v                   |
  +-----------+     +-----------+             |
  |  VERIFY   |     |  REPLAN   +-------------+
  +-----+-----+     +-----------+
        |
        v
  +-----------+
  |  DELIVER  |
  +-----+-----+
        |
        v
   +---------+
   |   END   |
   +---------+
```

### Component Structure (`backend/app/orchestration/`)
- [`__init__.py`](file:///c:/Users/shiva/Desktop/college/sih/sih2/sih-sovereign-workbench-initial/backend/app/orchestration/__init__.py): Central package exports.
- [`state.py`](file:///c:/Users/shiva/Desktop/college/sih/sih2/sih-sovereign-workbench-initial/backend/app/orchestration/state.py): OrchestrationState definition and bidirectional synchronization with Phase 3 `TaskState`.
- [`errors.py`](file:///c:/Users/shiva/Desktop/college/sih/sih2/sih-sovereign-workbench-initial/backend/app/orchestration/errors.py): Structured orchestration exception hierarchy.
- [`understanding.py`](file:///c:/Users/shiva/Desktop/college/sih/sih2/sih-sovereign-workbench-initial/backend/app/orchestration/understanding.py): Intent extraction, capabilities mapping, and Pydantic schema validation.
- [`routing.py`](file:///c:/Users/shiva/Desktop/college/sih/sih2/sih-sovereign-workbench-initial/backend/app/orchestration/routing.py): Capability-based routing delegating to `AgentRegistry` and `ModelRegistry`.
- [`planner.py`](file:///c:/Users/shiva/Desktop/college/sih/sih2/sih-sovereign-workbench-initial/backend/app/orchestration/planner.py): Structured DAG plan creation and strict validation against registries.
- [`policy.py`](file:///c:/Users/shiva/Desktop/college/sih/sih2/sih-sovereign-workbench-initial/backend/app/orchestration/policy.py): Policy checkpoint evaluator representing `allowed`, `blocked`, and `requires_approval`.
- [`execution.py`](file:///c:/Users/shiva/Desktop/college/sih/sih2/sih-sovereign-workbench-initial/backend/app/orchestration/execution.py): Step execution dispatcher, A2A delegation packaging, and truthful `NOT_IMPLEMENTED` reporting.
- [`observation.py`](file:///c:/Users/shiva/Desktop/college/sih/sih2/sih-sovereign-workbench-initial/backend/app/orchestration/observation.py): Execution result evaluation and classification (`SUCCESS`, `RECOVERABLE_FAILURE`, `FATAL_FAILURE`).
- [`verification.py`](file:///c:/Users/shiva/Desktop/college/sih/sih2/sih-sovereign-workbench-initial/backend/app/orchestration/verification.py): Generic output and completion verifier.
- [`nodes.py`](file:///c:/Users/shiva/Desktop/college/sih/sih2/sih-sovereign-workbench-initial/backend/app/orchestration/nodes.py): LangGraph node handler implementations with dependency injection and state persistence.
- [`graph.py`](file:///c:/Users/shiva/Desktop/college/sih/sih2/sih-sovereign-workbench-initial/backend/app/orchestration/graph.py): StateGraph compilation and `WorkbenchOrchestrator` lifecycle runner.
- [`diagnostics.py`](file:///c:/Users/shiva/Desktop/college/sih/sih2/sih-sovereign-workbench-initial/backend/app/orchestration/diagnostics.py): Topology and edge inspector CLI.

---

## 2. Graph State (`OrchestrationState`)

The orchestration state inherits from `TypedDict` for complete LangGraph schema compliance while bridging cleanly to Phase 3 `TaskState`:

```python
class OrchestrationState(TypedDict, total=False):
    task_id: str
    user_request: str
    task_status: str
    required_capabilities: List[str]
    selected_agents: List[str]
    selected_models: Dict[str, str]
    plan: List[Dict[str, Any]]
    current_step: int
    execution_steps: List[Dict[str, Any]]
    last_execution_result: Optional[Dict[str, Any]]
    observations: List[Dict[str, Any]]
    errors: List[str]
    verification_results: Dict[str, Any]
    retry_count: int
    max_retries: int
    max_agent_steps: int
    policy_decision: Dict[str, Any]
    final_result: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]
```

### State Synchronization
- `create_initial_orchestration_state(task_id, user_request, ...)` initializes the state dictionary with runtime configurations (`max_retries`, `max_agent_steps`).
- `sync_to_task_state(state, task_state)` transfers progress, steps, outputs, and errors back into the authoritative Phase 3 `TaskState`.
- `sync_from_task_state(task_state, state)` populates runtime dictionaries from persisted state records.

---

## 3. Graph Nodes

The pipeline is composed of 9 specialized nodes in `backend/app/orchestration/nodes.py`:

1. **`understand`**:
   - Calls the local `ModelRuntime` using the general reasoning model resolved from `ModelRegistry`.
   - Parses model outputs into a typed `TaskUnderstanding` schema (`intent`, `required_capabilities`, `input_types`, `expected_output`, `complexity`, `risk_indicators`).
   - Rejects malformed JSON/structure with a structured `TaskUnderstandingError`.

2. **`route`**:
   - Matches required capabilities against `AgentRegistry` and `ModelRegistry`.
   - Emits `AGENT_SELECTED` and `MODEL_SELECTED` events.
   - Raises `RoutingError` if any mandatory capability cannot be satisfied by registered agents.

3. **`plan`**:
   - Generates a DAG of `PlanStep` elements.
   - Strictly validates each step against `AgentRegistry` and `ToolRegistry`.
   - Verifies agent capabilities, tool permissions, step dependencies, and acyclicity (via DFS graph coloring).

4. **`policy`**:
   - Evaluates security constraints and human approval requirements via `PolicyEvaluator`.
   - Outputs structured `PolicyDecision` (`allowed`, `blocked`, or `requires_approval`).
   - Halts execution with `PolicyBlockedError` if blocked.

5. **`execute`**:
   - Dispatches the current step to `AgentExecutor`.
   - Packages context into an authoritative `A2AMessage` (`TASK_DELEGATION`).
   - If an agent has a registered handler or is a general reasoning agent, executes locally using `ModelRuntime`.
   - If a real agent implementation does not exist, truthfully returns `AgentExecutionResult` with `status="not_implemented"` and `error="NOT_IMPLEMENTED"`.

6. **`observe`**:
   - Interprets the execution result via `ObservationEvaluator`.
   - Records structured `StepObservation` (`status`, `agent_id`, `output`, `error_message`, `is_recoverable`).
   - Determines the next routing branch (`SUCCESS`, `RECOVERABLE_FAILURE`, or `FATAL_FAILURE`).

7. **`replan`**:
   - Handles recoverable errors without exceeding `max_retries` or `max_agent_steps`.
   - Increments `retry_count` and modifies or re-queues the step for re-execution.
   - Fails permanently if limits are exceeded.

8. **`verify`**:
   - Generic verification of plan fulfillment.
   - Confirms all planned steps reached completion and required outputs exist.

9. **`deliver`**:
   - Consolidates results into `final_result`.
   - Updates task status to `COMPLETED` (or `FAILED` if errors were encountered).
   - Emits `TASK_COMPLETED` or `TASK_FAILED` audit events.

---

## 4. Edges & Routing Conditions

Graph transitions are established in `build_orchestration_graph()`:
- `START` -> `understand` -> `route` -> `plan` -> `policy` -> `execute` -> `observe`
- **Conditional Branch from `observe`**:
  - `route_after_observe(state)` inspects the latest observation:
    - If `FATAL_FAILURE` or limits exceeded: routes to `deliver`.
    - If `RECOVERABLE_FAILURE`: routes to `replan`.
    - If `SUCCESS` and remaining steps exist: routes back to `execute`.
    - If `SUCCESS` and all steps completed: routes to `verify`.
- **Branch from `replan`**:
  - If retry limits or max agent steps exceeded: routes to `deliver`.
  - Otherwise: routes back to `execute`.
- `verify` -> `deliver` -> `END`

---

## 5. Retry and Replan Limits

Infinite cycles are strictly prevented at both the observation and replan levels:
1. `retry_count >= max_retries`: Replan marks the task as failed with `MaxRetriesExceededError` and routes to `deliver`.
2. `current_step >= max_agent_steps`: Replan halts execution with `MaxStepsExceededError` and routes to `deliver`.
3. Fatal errors (e.g., unknown agents, unrecoverable exceptions) bypass retries and route directly to `deliver`.

---

## 6. Truthful Agent Invocation & A2A Integration

### Truthful Execution Principle
Phase 4 does not fake tool or agent execution. Agents are invoked through `AgentExecutor`:
- If an agent is not found: raises `UnknownAgentError`.
- If an agent lacks required capability: raises `StepExecutionError`.
- If an agent does not have a real execution handler or is not a registered reasoning model: returns `AgentExecutionResult(status="not_implemented", error="Capability '...' on agent '...' is not implemented")`.

### A2A Integration
Inter-agent communication utilizes Phase 3 `A2AMessage` contracts:
- Delegation: Creates `A2AMessage` with `type=A2AMessageType.REQUEST` or `TASK_DELEGATION`.
- Result: Records `A2AMessage` with `type=A2AMessageType.RESPONSE` or `TASK_RESULT`.
- Full provenance metadata (`task_id`, `step_id`, `sender="orchestrator"`, `receiver=agent_id`) is attached.

---

## 7. State Persistence & Audit Events

At every critical checkpoint (`understand`, `route`, `plan`, `execute`, `verify`, `deliver`):
1. **State Persistence**:
   - `LocalStateStore` saves the `TaskState` to disk via atomic file replacement (`.tmp` -> replace).
2. **Audit Events**:
   - Uses Phase 3 `TaskEvent` and `TaskEventType`:
     - `TASK_CREATED`, `STATE_CHANGED`, `AGENT_SELECTED`, `MODEL_SELECTED`,
     - `STEP_STARTED`, `STEP_COMPLETED`, `STEP_FAILED`,
     - `VERIFICATION_STARTED`, `VERIFICATION_COMPLETED`,
     - `TASK_COMPLETED`, `TASK_FAILED`.
   - All events are appended to the task history and persisted to `task_state.events`.

---

## 8. Sovereignty & Air-Gap Compliance

Phase 4 maintains strict adherence to the zero-egress architecture:
- All LLM queries route through `ModelRuntime` to localhost/loopback addresses.
- No third-party network APIs or cloud SDKs are called.
- Diagnostic logs sanitize inputs and never log confidential documents or prompts.
- All Phase 2 sovereignty tests continue to pass with 0 egress violations.

---

## 9. Test Results

### Complete Test Suite Summary
```text
======================= 201 passed, 1 skipped in 10.95s =======================
```

### Breakdown by Phase & Component:
1. **Phase 0 & Foundation**:
   - `test_config.py`, `test_dependencies.py`, `test_model_registry.py`: **Passed**
2. **Phase 1 & Local Runtime**:
   - `test_model_runtime.py`, `test_model_availability.py`, `test_model_health.py`: **Passed**
3. **Phase 2 & Sovereignty**:
   - `test_sovereignty.py`, `test_egress_guard.py`, `test_sovereign_status.py`: **Passed**
4. **Phase 3 & Registries, State, A2A**:
   - `test_agent_registry.py`, `test_tool_registry.py`, `test_task_state.py`, `test_state_store.py`, `test_a2a.py`, `test_registry_snapshot.py`: **Passed**
5. **Phase 4 & LangGraph Orchestration**:
   - `test_graph_construction.py` (Test A): **Passed**
   - `test_orchestration_understanding.py` (Test B): **Passed**
   - `test_orchestration_routing.py` (Test C): **Passed**
   - `test_orchestration_planning.py` (Test D): **Passed**
   - `test_orchestration_policy.py` (Test E): **Passed**
   - `test_orchestration_execution.py` (Test F): **Passed**
   - `test_orchestration_observation.py` (Test G): **Passed**
   - `test_orchestration_replan.py` (Test H): **Passed**
   - `test_orchestration_retry_limits.py` (Test I): **Passed**
   - `test_orchestration_verification.py` (Test J): **Passed**
   - `test_orchestration_deliver.py` (Test K): **Passed**
   - `test_orchestration_isolation.py` (Test L): **Passed**
   - `test_orchestration_persistence.py` (Test M): **Passed**
   - `test_orchestration_sovereignty.py` (Test N): **Passed**
   - `test_end_to_end_orchestration.py` (Simple E2E task): **Passed**
   - `test_phase_4_acceptance.py` (Comprehensive Acceptance): **Passed**

---

## 10. Known Limitations & Next Phase

### Phase 4 Boundaries
- **No Human-in-the-Loop UI**: The policy checkpoint supports `requires_approval`, but human interaction interfaces and approval wait queues are scheduled for Phase 5.
- **Truthful Unimplemented Agents**: Specialist agents (e.g., `vision_agent`, `coding_agent`) return structured `NOT_IMPLEMENTED` statuses until their respective phases implement OCR, sandboxing, and multimodal processing.
- **RAG & Multimodal Unimplemented**: Document parsers (PDF/DOCX), PaddleOCR, and Qdrant vector retrieval will be integrated in subsequent phases.

### Transition to Phase 5
- **Next Phase**: `PHASE 5 — RISK / POLICY / HUMAN APPROVAL`
- Implementation of Phase 5 will expand the `policy` checkpoint with risk classification, dynamic policy rule sets, and human authorization interrupts.
