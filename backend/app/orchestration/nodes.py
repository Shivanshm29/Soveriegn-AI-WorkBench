"""LangGraph nodes for workbench orchestration lifecycle."""

import logging
import uuid
from typing import Dict, Any, Optional

logger = logging.getLogger("app.orchestration")

from backend.app.config.settings import get_settings
from backend.app.models.registry import ModelRegistry
from backend.app.models.runtime import ModelRuntime
from backend.app.agents.registry import AgentRegistry
from backend.app.tools.registry import ToolRegistry
from backend.app.state.store import StateStore
from backend.app.state.events import TaskEvent, EventType
from backend.app.state.task_state import TaskStatus
from backend.app.orchestration.state import OrchestrationState, sync_orchestration_to_task_state
from backend.app.orchestration.understanding import understand_task, TaskUnderstanding
from backend.app.orchestration.routing import TaskRouter
from backend.app.orchestration.planner import (
    PlanStep,
    PlanValidator,
    create_default_plan_for_capabilities,
)
from backend.app.orchestration.policy import PolicyEvaluator
from backend.app.security.risk import RiskAssessment, RiskLevel, RiskFactor, RiskEngine
from backend.app.security.data_sensitivity import DataSensitivity, parse_data_sensitivity
from backend.app.security.policy_engine import PolicyDecision, PolicyOutcome, PolicyEngine
from backend.app.security.approval import (
    ApprovalRequest,
    ApprovalDecision,
    ApprovalManager,
    ApprovalStatus,
    compute_plan_hash,
)
from backend.app.orchestration.execution import AgentExecutor
from backend.app.orchestration.observation import ObservationEvaluator
from backend.app.orchestration.verification import PlanVerifier
from backend.app.orchestration.errors import (
    OrchestrationError,
    MaxRetriesExceededError,
    MaxStepsExceededError,
)


class OrchestrationNodes:
    """Encapsulates LangGraph node callables with injected dependencies."""

    def __init__(
        self,
        model_registry: ModelRegistry,
        agent_registry: AgentRegistry,
        tool_registry: ToolRegistry,
        model_runtime: Optional[ModelRuntime] = None,
        agent_executor: Optional[AgentExecutor] = None,
        state_store: Optional[StateStore] = None,
    ):
        self.model_registry = model_registry
        self.agent_registry = agent_registry
        self.tool_registry = tool_registry
        self.model_runtime = model_runtime
        self.state_store = state_store

        self.router = TaskRouter(agent_registry, model_registry)
        self.plan_validator = PlanValidator(agent_registry, tool_registry)
        self.policy_evaluator = PolicyEvaluator(tool_registry=tool_registry, agent_registry=agent_registry)
        self.agent_executor = agent_executor or AgentExecutor(
            agent_registry, tool_registry, model_runtime
        )

    def _record_event(
        self,
        task_id: str,
        event_type: EventType,
        message: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        step_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> None:
        """Helper to emit Phase 3 lifecycle events to store and non-confidential audit log."""
        logger.info(
            "OrchestrationEvent: task_id=%s step_id=%s agent_id=%s event=%s message=%s",
            task_id,
            step_id or "-",
            agent_id or "-",
            event_type.value,
            message or "",
        )
        if self.state_store is not None:
            event = TaskEvent(
                task_id=task_id,
                event_type=event_type,
                step_id=step_id,
                agent_id=agent_id,
                message=message,
                payload=payload or {},
            )
            self.state_store.record_event(event)

    def understand_node(self, state: OrchestrationState) -> OrchestrationState:
        """Analyze raw user request into structured TaskUnderstanding."""
        new_state = dict(state)
        task_id = new_state["task_id"]

        if new_state.get("understanding"):
            return new_state

        self._record_event(
            task_id,
            EventType.TASK_CREATED,
            message="Task initialized in workbench orchestrator",
            payload={"user_request": new_state.get("user_request", "")},
        )
        new_state["task_status"] = TaskStatus.UNDERSTANDING.value
        self._record_event(
            task_id,
            EventType.TASK_STATUS_CHANGED,
            message="Task status changed to UNDERSTANDING",
            payload={"from_status": TaskStatus.CREATED.value, "to_status": TaskStatus.UNDERSTANDING.value},
        )

        try:
            if new_state.get("metadata", {}).get("required_capabilities"):
                req_caps = new_state["metadata"]["required_capabilities"]
                understanding = TaskUnderstanding(
                    intent="Task requested with specified capabilities",
                    capabilities=req_caps,
                    modalities=["text"],
                    complexity="MEDIUM" if "code_execution" in req_caps else "LOW",
                    output_type="analysis",
                )
            elif self.model_runtime is not None:
                understanding = understand_task(
                    new_state["user_request"],
                    self.model_runtime,
                    self.model_registry,
                )
            else:
                # Deterministic fallback when runtime is not passed
                req_lower = new_state.get("user_request", "").lower()
                has_image = bool(
                    new_state.get("image_path")
                    or new_state.get("file_path")
                    or (new_state.get("metadata") or {}).get("image_path")
                    or (new_state.get("metadata") or {}).get("file_path")
                )
                if "sandbox" in req_lower or "code" in req_lower or "script" in req_lower or "python" in req_lower:
                    caps = ["code_execution"]
                    comp = "MEDIUM"
                elif has_image or any(k in req_lower for k in ("visual", "image", "drawing", "dimension", "blueprint", "diagram", "turbine casing")):
                    caps = ["visual_reasoning"]
                    comp = "MEDIUM"
                elif any(k in req_lower for k in ("search", "retrieve", "knowledge", "px-417", "pump", "manual", "sop", "finding", "recommend")):
                    caps = ["knowledge_search"]
                    comp = "MEDIUM"
                else:
                    caps = ["reasoning"]
                    comp = "LOW"
                understanding = TaskUnderstanding(
                    intent="General user task request",
                    capabilities=caps,
                    modalities=["text"],
                    complexity=comp,
                    output_type="analysis",
                )

            new_state["understanding"] = understanding.to_dict()
            new_state["required_capabilities"] = understanding.capabilities

        except Exception as e:
            new_state["errors"].append(f"Understanding failed: {e}")
            new_state["task_status"] = TaskStatus.FAILED.value
            self._record_event(
                task_id,
                EventType.TASK_ERROR,
                message=f"Understanding failed: {e}",
            )

        sync_orchestration_to_task_state(new_state, self.state_store)
        return new_state

    def route_node(self, state: OrchestrationState) -> OrchestrationState:
        """Resolve candidate agents and models based on capabilities."""
        new_state = dict(state)
        task_id = new_state["task_id"]

        if new_state.get("task_status") == TaskStatus.FAILED.value or new_state.get("selected_agents"):
            return new_state

        caps = new_state.get("required_capabilities", [])
        modalities = new_state.get("understanding", {}).get("modalities", ["text"]) if new_state.get("understanding") else ["text"]

        try:
            decision = self.router.route(capabilities=caps, modalities=modalities)
            new_state["selected_agents"] = decision.selected_agents
            new_state["selected_models"] = decision.selected_models

            for cap, ag in decision.selected_agents.items():
                self._record_event(
                    task_id,
                    EventType.AGENT_DELEGATED,
                    message=f"AGENT_SELECTED: Selected agent '{ag}' for capability '{cap}'",
                    payload={"capability": cap, "agent_id": ag},
                    agent_id=ag,
                )
            for cap, m in decision.selected_models.items():
                self._record_event(
                    task_id,
                    EventType.AGENT_DELEGATED,
                    message=f"MODEL_SELECTED: Selected model '{m}' for capability '{cap}'",
                    payload={"capability": cap, "model_id": m},
                )

        except Exception as e:
            new_state["errors"].append(f"Routing failed: {e}")
            new_state["task_status"] = TaskStatus.FAILED.value
            self._record_event(
                task_id,
                EventType.TASK_ERROR,
                message=f"Routing failed: {e}",
            )

        sync_orchestration_to_task_state(new_state, self.state_store)
        return new_state

    def plan_node(self, state: OrchestrationState) -> OrchestrationState:
        """Construct and validate execution plan."""
        new_state = dict(state)
        task_id = new_state["task_id"]

        if new_state.get("task_status") == TaskStatus.FAILED.value:
            return new_state

        new_state["task_status"] = TaskStatus.PLANNING.value
        self._record_event(
            task_id,
            EventType.TASK_STATUS_CHANGED,
            message="Task status changed to PLANNING",
            payload={"to_status": TaskStatus.PLANNING.value},
        )

        if new_state.get("plan"):
            sync_orchestration_to_task_state(new_state, self.state_store)
            return new_state

        caps = new_state.get("required_capabilities", ["reasoning"])
        selected_agents = new_state.get("selected_agents", {})

        try:
            steps = create_default_plan_for_capabilities(
                user_request=new_state.get("user_request", ""),
                capabilities=caps,
                selected_agents=selected_agents,
                agent_registry=self.agent_registry,
                tool_registry=self.tool_registry,
            )
            # Validate generated plan against registries and DAG rules
            self.plan_validator.validate(steps)

            new_state["plan"] = [s.to_dict() for s in steps]
            new_state["current_step_index"] = 0

        except Exception as e:
            new_state["errors"].append(f"Planning failed: {e}")
            new_state["task_status"] = TaskStatus.FAILED.value
            self._record_event(
                task_id,
                EventType.TASK_ERROR,
                message=f"Planning failed: {e}",
            )

        sync_orchestration_to_task_state(new_state, self.state_store)
        return new_state

    def risk_assessment_node(self, state: OrchestrationState) -> OrchestrationState:
        """Deterministically assess plan risk factors, scores, and sensitivity."""
        new_state = dict(state)
        task_id = new_state["task_id"]

        if new_state.get("task_status") == TaskStatus.FAILED.value:
            return new_state

        plan_steps = [PlanStep.model_validate(s) for s in new_state.get("plan", [])]
        plan_id = new_state.get("plan_id", f"plan-{task_id[:8]}")
        sensitivity = parse_data_sensitivity(new_state.get("data_sensitivity", "INTERNAL"))

        risk_assessment = self.policy_evaluator.engine.risk_engine.assess_plan(
            task_id=task_id,
            plan_id=plan_id,
            plan_steps=plan_steps,
            data_sensitivity=sensitivity,
            metadata=new_state.get("metadata", {}),
        )

        new_state["risk_assessment"] = risk_assessment.to_dict()
        self._record_event(
            task_id,
            EventType.RISK_ASSESSMENT_CREATED,
            message=f"Deterministic risk assessed: Level={risk_assessment.risk_level.value}, Score={risk_assessment.risk_score}",
            payload=risk_assessment.to_dict(),
        )

        sync_orchestration_to_task_state(new_state, self.state_store)
        return new_state

    def policy_node(self, state: OrchestrationState) -> OrchestrationState:
        """Evaluate pre-execution risk, policy, and human authorization requirements."""
        new_state = dict(state)
        task_id = new_state["task_id"]

        if new_state.get("task_status") == TaskStatus.FAILED.value:
            return new_state

        try:
            plan_steps = [PlanStep.model_validate(s) for s in new_state.get("plan", [])]
        except Exception as e:
            new_state["errors"].append(f"Plan validation failed: {e}")
            new_state["task_status"] = TaskStatus.FAILED.value
            self._record_event(
                task_id,
                EventType.TASK_ERROR,
                message=f"Plan validation failed: {e}",
            )
            sync_orchestration_to_task_state(new_state, self.state_store)
            return new_state

        plan_id = new_state.get("plan_id", f"plan-{task_id[:8]}")
        sensitivity = parse_data_sensitivity(new_state.get("data_sensitivity", "INTERNAL"))

        # Assess risk if not yet assessed
        if not new_state.get("risk_assessment"):
            risk_assessment = self.policy_evaluator.engine.risk_engine.assess_plan(
                task_id=task_id,
                plan_id=plan_id,
                plan_steps=plan_steps,
                data_sensitivity=sensitivity,
                metadata=new_state.get("metadata", {}),
            )
            new_state["risk_assessment"] = risk_assessment.to_dict()
            self._record_event(
                task_id,
                EventType.RISK_ASSESSMENT_CREATED,
                message=f"Deterministic risk assessed: Level={risk_assessment.risk_level.value}, Score={risk_assessment.risk_score}",
                payload=risk_assessment.to_dict(),
            )
        else:
            risk_assessment = RiskAssessment.model_validate(new_state["risk_assessment"])

        decision, _ = self.policy_evaluator.engine.evaluate_plan(
            plan_steps=plan_steps,
            task_id=task_id,
            plan_id=plan_id,
            data_sensitivity=sensitivity,
            metadata=new_state.get("metadata", {}),
        )
        new_state["policy_decision"] = decision.to_dict()
        self._record_event(
            task_id,
            EventType.POLICY_EVALUATED,
            message=f"Policy evaluated: {decision.decision.value} (Reason: {decision.reason})",
            payload=decision.to_dict(),
        )

        if decision.decision == PolicyOutcome.DENY:
            new_state["errors"].append(f"Policy denied execution: {decision.reason}")
            new_state["task_status"] = TaskStatus.FAILED.value
            self._record_event(
                task_id,
                EventType.TASK_ERROR,
                message=f"Policy denied execution: {decision.reason}",
            )
        elif decision.decision == PolicyOutcome.REQUIRE_APPROVAL:
            # Check if an approval decision is already present (e.g. from resume)
            existing_decision_dict = new_state.get("approval_decision")
            existing_request_dict = new_state.get("approval_request")

            if existing_decision_dict and existing_request_dict:
                req_obj = ApprovalRequest.model_validate(existing_request_dict)
                dec_obj = ApprovalDecision.model_validate(existing_decision_dict)

                is_valid, val_reason, status_res = ApprovalManager.validate_approval(
                    req_obj, dec_obj, plan_steps
                )
                if is_valid:
                    req_obj.status = ApprovalStatus.APPROVED
                    new_state["approval_request"] = req_obj.to_dict()
                    new_state["task_status"] = TaskStatus.EXECUTING.value
                    self._record_event(
                        task_id,
                        EventType.APPROVAL_APPROVED,
                        message=val_reason,
                        payload=dec_obj.to_dict(),
                    )
                    self._record_event(
                        task_id,
                        EventType.APPROVAL_GRANTED,
                        message=val_reason,
                        payload=dec_obj.to_dict(),
                    )
                    self._record_event(
                        task_id,
                        EventType.TASK_STATUS_CHANGED,
                        message="Task status changed to EXECUTING (authorized)",
                        payload={"to_status": TaskStatus.EXECUTING.value},
                    )
                else:
                    if status_res == ApprovalStatus.EXPIRED:
                        self._record_event(task_id, EventType.APPROVAL_EXPIRED, message=val_reason)
                    elif status_res == ApprovalStatus.REJECTED:
                        self._record_event(task_id, EventType.APPROVAL_REJECTED, message=val_reason)

                    new_state["errors"].append(f"Approval validation failed: {val_reason}")
                    new_state["task_status"] = TaskStatus.FAILED.value
                    self._record_event(
                        task_id,
                        EventType.TASK_ERROR,
                        message=f"Approval validation failed: {val_reason}",
                    )
            else:
                # Create ApprovalRequest and pause workflow in WAITING_APPROVAL
                req = ApprovalManager.create_request(
                    task_id=task_id,
                    plan_id=plan_id,
                    risk_assessment=risk_assessment,
                    plan_steps=plan_steps,
                    policy_version=self.policy_evaluator.engine.policy_version,
                )
                new_state["approval_request"] = req.to_dict()
                new_state["task_status"] = TaskStatus.WAITING_APPROVAL.value
                self._record_event(
                    task_id,
                    EventType.APPROVAL_REQUESTED,
                    message=f"Human approval requested: {req.action_summary}",
                    payload=req.to_dict(),
                )
                self._record_event(
                    task_id,
                    EventType.TASK_STATUS_CHANGED,
                    message="Task status changed to WAITING_APPROVAL",
                    payload={"to_status": TaskStatus.WAITING_APPROVAL.value},
                )
        else:
            # ALLOW
            new_state["task_status"] = TaskStatus.EXECUTING.value
            self._record_event(
                task_id,
                EventType.TASK_STATUS_CHANGED,
                message="Task status changed to EXECUTING",
                payload={"to_status": TaskStatus.EXECUTING.value},
            )

        sync_orchestration_to_task_state(new_state, self.state_store)
        return new_state

    def execute_node(self, state: OrchestrationState) -> OrchestrationState:
        """Execute the current plan step with execution safety enforcement."""
        new_state = dict(state)
        task_id = new_state["task_id"]

        if new_state.get("task_status") == TaskStatus.FAILED.value:
            return new_state

        plan = new_state.get("plan", [])
        idx = new_state.get("current_step_index", 0)

        if idx >= len(plan):
            # All steps finished, proceed to verify
            new_state["task_status"] = TaskStatus.VERIFYING.value
            return new_state

        step_data = plan[idx]
        step = PlanStep.model_validate(step_data)

        # ---------------------------------------------------------
        # EXECUTION SAFETY CHECKS (Section 22)
        # ---------------------------------------------------------
        policy_dec = new_state.get("policy_decision", {})
        if policy_dec.get("requires_approval") or policy_dec.get("decision") == "REQUIRE_APPROVAL":
            app_dec = new_state.get("approval_decision")
            app_req = new_state.get("approval_request")
            if not app_dec or app_dec.get("decision") != "APPROVED" or not app_req:
                new_state["errors"].append("Execution safety violation: Protected execution attempted without valid approval.")
                new_state["task_status"] = TaskStatus.FAILED.value
                self._record_event(task_id, EventType.TASK_ERROR, message="Execution safety violation: Missing approval")
                sync_orchestration_to_task_state(new_state, self.state_store)
                return new_state

            req_obj = ApprovalRequest.model_validate(app_req)
            if req_obj.is_expired():
                new_state["errors"].append("Execution safety violation: Approval request has expired.")
                new_state["task_status"] = TaskStatus.FAILED.value
                self._record_event(task_id, EventType.APPROVAL_EXPIRED, message="Approval expired")
                self._record_event(task_id, EventType.TASK_ERROR, message="Execution safety violation: Expired approval")
                sync_orchestration_to_task_state(new_state, self.state_store)
                return new_state

            current_plan_hash = compute_plan_hash(plan)
            if current_plan_hash != req_obj.plan_hash:
                new_state["errors"].append("Execution safety violation: Plan was modified after approval was granted.")
                new_state["task_status"] = TaskStatus.FAILED.value
                self._record_event(task_id, EventType.TASK_ERROR, message="Execution safety violation: Plan altered after approval")
                sync_orchestration_to_task_state(new_state, self.state_store)
                return new_state

        # Verify tool existence
        for tool_id in step.required_tools:
            if not self.tool_registry.get(tool_id):
                new_state["errors"].append(f"Execution safety violation: Unknown tool '{tool_id}'")
                new_state["task_status"] = TaskStatus.FAILED.value
                self._record_event(task_id, EventType.TASK_ERROR, message=f"Unknown tool '{tool_id}'")
                sync_orchestration_to_task_state(new_state, self.state_store)
                return new_state

        # Verify agent existence
        if not self.agent_registry.get(step.agent_id):
            new_state["errors"].append(f"Execution safety violation: Unknown agent '{step.agent_id}'")
            new_state["task_status"] = TaskStatus.FAILED.value
            self._record_event(task_id, EventType.TASK_ERROR, message=f"Unknown agent '{step.agent_id}'")
            sync_orchestration_to_task_state(new_state, self.state_store)
            return new_state

        # Check maximum agent step limit
        new_state["step_count"] = new_state.get("step_count", 0) + 1
        max_steps = new_state.get("max_agent_steps", 20)
        if new_state["step_count"] > max_steps:
            new_state["errors"].append(
                f"Maximum agent steps ({max_steps}) exceeded."
            )
            new_state["task_status"] = TaskStatus.FAILED.value
            self._record_event(
                task_id,
                EventType.TASK_ERROR,
                message=f"Step limit {max_steps} exceeded",
            )
            sync_orchestration_to_task_state(new_state, self.state_store)
            return new_state

        self._record_event(
            task_id,
            EventType.STEP_STARTED,
            message=f"Started execution of step '{step.step_id}' by agent '{step.agent_id}'",
            step_id=step.step_id,
            agent_id=step.agent_id,
        )

        result = self.agent_executor.execute(
            agent_id=step.agent_id,
            step=step,
            task_context=new_state,
        )

        status_val = "COMPLETED" if getattr(result, "status", "") == "SUCCESS" else "FAILED"
        outputs_val = result.output if isinstance(getattr(result, "output", None), dict) else {}
        error_val = str(result.error) if getattr(result, "error", None) is not None else None
        exec_step = {
            "step_id": step.step_id,
            "task_id": task_id,
            "assigned_agent": step.agent_id,
            "action": step.description,
            "status": status_val,
            "inputs": {"context": new_state.get("user_request", "")},
            "outputs": outputs_val,
            "error": error_val,
        }
        new_state["execution_steps"].append(exec_step)
        new_state["last_execution_result"] = result.to_dict() if hasattr(result, "to_dict") else {
            "status": status_val,
            "agent_id": step.agent_id,
            "output": outputs_val,
            "error": error_val,
        }

        sync_orchestration_to_task_state(new_state, self.state_store)
        return new_state

    def observe_node(self, state: OrchestrationState) -> OrchestrationState:
        """Interpret latest step execution result."""
        new_state = dict(state)
        task_id = new_state["task_id"]

        if new_state.get("task_status") == TaskStatus.FAILED.value:
            return new_state

        plan = new_state.get("plan", [])
        idx = new_state.get("current_step_index", 0)

        if idx >= len(plan):
            new_state["task_status"] = TaskStatus.VERIFYING.value
            return new_state

        step = PlanStep.model_validate(plan[idx])
        from backend.app.orchestration.execution import AgentExecutionResult
        last_result_dict = new_state.get("last_execution_result")
        if not last_result_dict and new_state.get("execution_steps"):
            last_step = new_state["execution_steps"][-1]
            last_result_dict = {
                "status": "SUCCESS" if last_step.get("status") == "COMPLETED" else "FAILED",
                "agent_id": last_step.get("assigned_agent", step.agent_id),
                "output": last_step.get("outputs", {}),
                "error": last_step.get("error"),
            }
        elif not last_result_dict:
            last_result_dict = {
                "status": "FAILED",
                "agent_id": step.agent_id,
                "error": "No execution result recorded.",
            }
        result = AgentExecutionResult.model_validate(last_result_dict)


        observation = ObservationEvaluator.evaluate(step, result)
        new_state["observations"].append(observation.to_dict())

        if observation.outcome == "SUCCESS":
            self._record_event(
                task_id,
                EventType.STEP_COMPLETED,
                message=f"Step '{step.step_id}' completed successfully",
                step_id=step.step_id,
                agent_id=step.agent_id,
            )
            # Advance to next step
            new_state["current_step_index"] = idx + 1
            if new_state["current_step_index"] >= len(plan):
                new_state["task_status"] = TaskStatus.VERIFYING.value
            else:
                new_state["task_status"] = TaskStatus.EXECUTING.value
        elif observation.outcome == "RECOVERABLE_FAILURE":
            self._record_event(
                task_id,
                EventType.STEP_FAILED,
                message=f"Step '{step.step_id}' encountered recoverable failure: {observation.error}",
                step_id=step.step_id,
                agent_id=step.agent_id,
            )
            new_state["task_status"] = "REPLAN"
        else:
            # Fatal failure
            self._record_event(
                task_id,
                EventType.STEP_FAILED,
                message=f"Step '{step.step_id}' encountered fatal failure: {observation.error}",
                step_id=step.step_id,
                agent_id=step.agent_id,
            )
            new_state["errors"].append(observation.error or "Fatal execution error")
            new_state["task_status"] = TaskStatus.FAILED.value

        sync_orchestration_to_task_state(new_state, self.state_store)
        return new_state

    def replan_node(self, state: OrchestrationState) -> OrchestrationState:
        """Handle failure recovery and enforce retry limits."""
        new_state = dict(state)
        task_id = new_state["task_id"]

        new_state["retry_count"] = new_state.get("retry_count", 0) + 1
        max_retries = new_state.get("max_retries", 2)

        if new_state["retry_count"] > max_retries:
            new_state["errors"].append(
                f"Retry limit exceeded ({max_retries} retries)."
            )
            new_state["task_status"] = TaskStatus.FAILED.value
            self._record_event(
                task_id,
                EventType.TASK_ERROR,
                message=f"Max retries ({max_retries}) exceeded.",
            )
        else:
            # Retry current step
            new_state["task_status"] = TaskStatus.EXECUTING.value
            self._record_event(
                task_id,
                EventType.TASK_STATUS_CHANGED,
                message=f"Replanning attempt {new_state['retry_count']} of {max_retries}",
                payload={"retry_count": new_state["retry_count"]},
            )

        sync_orchestration_to_task_state(new_state, self.state_store)
        return new_state

    def verify_node(self, state: OrchestrationState) -> OrchestrationState:
        """Verify plan execution results."""
        new_state = dict(state)
        task_id = new_state["task_id"]

        self._record_event(
            task_id,
            EventType.VERIFICATION_STARTED,
            message="Starting verification of plan execution",
        )

        verification = PlanVerifier.verify(
            plan=new_state.get("plan", []),
            execution_steps=new_state.get("execution_steps", []),
            observations=new_state.get("observations", []),
        )
        new_state["verification_results"] = verification.to_dict()

        self._record_event(
            task_id,
            EventType.VERIFICATION_COMPLETED,
            message=f"Verification complete. Verified={verification.is_verified}",
            payload=verification.to_dict(),
        )

        if verification.is_verified:
            new_state["task_status"] = TaskStatus.COMPLETED.value
        else:
            # If verification failed, check if replanning is possible
            if new_state.get("retry_count", 0) < new_state.get("max_retries", 2):
                new_state["task_status"] = "REPLAN"
            else:
                new_state["errors"].extend(verification.errors)
                new_state["task_status"] = TaskStatus.FAILED.value

        sync_orchestration_to_task_state(new_state, self.state_store)
        return new_state

    def deliver_node(self, state: OrchestrationState) -> OrchestrationState:
        """Finalize task, compile outputs, and store terminal state."""
        new_state = dict(state)
        task_id = new_state["task_id"]

        # Aggregate outputs
        outputs: Dict[str, Any] = {}
        for s in new_state.get("execution_steps", []):
            if s.get("status") == "COMPLETED" and s.get("outputs"):
                outputs.update(s["outputs"])

        if new_state.get("task_status") == TaskStatus.WAITING_APPROVAL.value:
            new_state["final_result"] = {
                "status": "WAITING_APPROVAL",
                "approval_request": new_state.get("approval_request"),
            }
        elif new_state.get("task_status") == TaskStatus.FAILED.value:
            new_state["final_result"] = {
                "status": "FAILED",
                "errors": new_state.get("errors", []),
                "partial_outputs": outputs,
            }
            self._record_event(
                task_id,
                EventType.TASK_STATUS_CHANGED,
                message="TASK_FAILED: Task execution failed",
                payload={"to_status": TaskStatus.FAILED.value},
            )
            self._record_event(
                task_id,
                EventType.TASK_ERROR,
                message="Task ended in FAILED state",
                payload=new_state["final_result"],
            )
        else:
            new_state["task_status"] = TaskStatus.COMPLETED.value
            new_state["final_result"] = {
                "status": "COMPLETED",
                "outputs": outputs,
                "step_count": len(new_state.get("execution_steps", [])),
            }
            self._record_event(
                task_id,
                EventType.TASK_STATUS_CHANGED,
                message="TASK_COMPLETED: Task completed successfully",
                payload={"to_status": TaskStatus.COMPLETED.value},
            )
            self._record_event(
                task_id,
                EventType.STEP_COMPLETED,
                message="Task delivery completed successfully",
                payload=new_state["final_result"],
            )

        sync_orchestration_to_task_state(new_state, self.state_store)
        return new_state
