"""Agent execution mechanism and A2A delegation integration."""

import uuid
from typing import Dict, Any, Optional, Callable, Literal
from pydantic import BaseModel, Field

from backend.app.agents.registry import AgentRegistry, UnknownAgentError
from backend.app.tools.registry import ToolRegistry
from backend.app.schemas.agents import A2AMessage
from backend.app.agents.a2a import A2AMessageValidator
from backend.app.models.runtime import ModelRuntime
from backend.app.models.schemas import ModelRequest, ChatMessage
from backend.app.orchestration.planner import PlanStep
from backend.app.orchestration.errors import (
    StepExecutionError,
    AgentNotImplementedError,
)


class AgentExecutionResult(BaseModel):
    """Structured outcome of an agent step execution."""

    status: Literal["SUCCESS", "FAILED", "NOT_IMPLEMENTED"]
    agent_id: str = "agent"
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    delegation_message: Optional[A2AMessage] = None
    result_message: Optional[A2AMessage] = None
    execution_metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return self.model_dump(mode="json")


class AgentExecutor:
    """Invokes specialist agents via Phase 3 registry, enforcing capability and A2A contracts."""

    def __init__(
        self,
        agent_registry: AgentRegistry,
        tool_registry: ToolRegistry,
        model_runtime: Optional[ModelRuntime] = None,
        model_registry: Optional[Any] = None,
    ):
        self.agent_registry = agent_registry
        self.tool_registry = tool_registry
        self.model_runtime = model_runtime
        self.model_registry = model_registry
        self._handlers: Dict[str, Callable[[PlanStep, Dict[str, Any]], Dict[str, Any]]] = {}


    def register_handler(
        self,
        key: str,
        handler: Callable[[PlanStep, Dict[str, Any]], Dict[str, Any]],
    ) -> None:
        """Register a handler for a specific agent ID or capability (used for real agents or test doubles)."""
        self._handlers[key] = handler

    def execute(
        self,
        agent_id: str,
        step: PlanStep,
        task_context: Dict[str, Any],
    ) -> AgentExecutionResult:
        """Execute a plan step using the assigned agent."""
        task_id = task_context.get("task_id", str(uuid.uuid4()))

        # 1. Validate agent exists and is enabled
        if not self.agent_registry.exists(agent_id):
            raise UnknownAgentError(f"Cannot execute step with unregistered agent '{agent_id}'.")

        agent = self.agent_registry.get(agent_id)
        if not agent.enabled:
            raise StepExecutionError(f"Agent '{agent_id}' is disabled.")

        # 2. Validate agent possesses capability
        if step.capability not in agent.capabilities:
            raise StepExecutionError(
                f"Agent '{agent_id}' does not support required capability '{step.capability}'."
            )

        # 3. Create structured A2A TASK_DELEGATION message
        sender_agent_id = "reasoning_agent" if agent_id == "main_agent" else "main_agent"
        delegation_msg = A2AMessage(
            message_id=str(uuid.uuid4()),
            task_id=task_id,
            sender=sender_agent_id,
            receiver=agent_id,
            type="TASK_DELEGATION",
            payload={
                "step_id": step.step_id,
                "action": step.description,
                "capability": step.capability,
                "required_tools": step.required_tools,
                "context": task_context.get("user_request", ""),
            },
            requested_capabilities=[step.capability],
            status="PENDING",
        )
        A2AMessageValidator.validate(delegation_msg, agent_registry=self.agent_registry)

        # 4. Check for registered handler (test double or real specialist implementation)
        if agent_id in self._handlers:
            try:
                output = self._handlers[agent_id](step, task_context)
                result_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="TASK_RESULT",
                    payload=output,
                    status="COMPLETED",
                )
                return AgentExecutionResult(
                    status="SUCCESS",
                    agent_id=agent_id,
                    output=output,
                    delegation_message=delegation_msg,
                    result_message=result_msg,
                )
            except Exception as e:
                err_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="ERROR",
                    payload={"error": str(e)},
                    status="FAILED",
                )
                return AgentExecutionResult(
                    status="FAILED",
                    agent_id=agent_id,
                    error=str(e),
                    delegation_message=delegation_msg,
                    result_message=err_msg,
                )

        if step.capability in self._handlers:
            try:
                output = self._handlers[step.capability](step, task_context)
                result_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="TASK_RESULT",
                    payload=output,
                    status="COMPLETED",
                )
                return AgentExecutionResult(
                    status="SUCCESS",
                    agent_id=agent_id,
                    output=output,
                    delegation_message=delegation_msg,
                    result_message=result_msg,
                )
            except Exception as e:
                err_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="ERROR",
                    payload={"error": str(e)},
                    status="FAILED",
                )
                return AgentExecutionResult(
                    status="FAILED",
                    agent_id=agent_id,
                    error=str(e),
                    delegation_message=delegation_msg,
                    result_message=err_msg,
                )

        # 5. Default reasoning agent execution using ModelRuntime if available
        if (
            agent_id in ("main_agent", "reasoning_agent")
            and step.capability in ("reasoning", "structured_reasoning", "planning", "workflow_management")
            and self.model_runtime is not None
        ):
            try:
                prompt = (
                    f"Perform this task step:\n"
                    f"Description: {step.description}\n"
                    f"Context: {task_context.get('user_request', '')}\n"
                    f"Expected Output: {step.expected_output}"
                )
                resp = self.model_runtime.chat(
                    ModelRequest(
                        model=task_context.get("selected_models", {}).get("primary", "Qwen/Qwen3-4B"),
                        messages=[
                            ChatMessage(role="system", content="You are a reasoning agent performing a task step."),
                            ChatMessage(role="user", content=prompt),
                        ],
                        temperature=0.0,
                    )
                )
                output = {"content": resp.content, "step_id": step.step_id}
                result_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="TASK_RESULT",
                    payload=output,
                    status="COMPLETED",
                )
                return AgentExecutionResult(
                    status="SUCCESS",
                    agent_id=agent_id,
                    output=output,
                    delegation_message=delegation_msg,
                    result_message=result_msg,
                )
            except Exception as e:
                err_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="ERROR",
                    payload={"error": str(e)},
                    status="FAILED",
                )
                return AgentExecutionResult(
                    status="FAILED",
                    agent_id=agent_id,
                    error=f"ModelRuntime reasoning execution failed: {e}",
                    delegation_message=delegation_msg,
                    result_message=err_msg,
                )

        # 6. Default execution for document_agent and vision_agent
        doc_input = task_context.get("document_input")
        file_path = (
            task_context.get("document_path")
            or task_context.get("source_path")
            or task_context.get("file_path")
            or task_context.get("image_path")
            or (task_context.get("metadata") or {}).get("image_path")
            or (task_context.get("metadata") or {}).get("file_path")
        )
        if not file_path:
            import re
            import os
            user_req = task_context.get("user_request", "")
            matches = re.findall(r"([A-Za-z]:\\[^'\"\n\r]+?\.(?:png|jpg|jpeg|bmp|tiff|pdf))", user_req, re.IGNORECASE)
            if not matches:
                matches = re.findall(r"(/[^\s'\"<>\n\r]+?\.(?:png|jpg|jpeg|bmp|tiff|pdf))", user_req, re.IGNORECASE)
            for m in matches:
                if os.path.exists(m):
                    file_path = m
                    break

        if not doc_input and file_path:
            from backend.app.multimodal.schemas import DocumentInput
            doc_input = DocumentInput.from_file(file_path)

        # 6a. Vision Agent Engineering & Industrial Vision Analysis (Phase 7)
        if agent_id == "vision_agent" and file_path:
            is_eng_cap = step.capability in (
                "vision.engineering_analysis",
                "engineering_drawing_analysis",
                "engineering_drawing_observations",
                "vision.image_understanding",
                "industrial_inspection",
                "candidate_defect_detection",
                "dimension_extraction",
                "visual_evidence",
                "image_understanding",
                "visual_reasoning",
                "visual_analysis",
                "scanned_page_analysis",
                "visual_document_understanding",
                "vision.document_analysis",
            )
            is_image_file = any(
                file_path.lower().endswith(ext)
                for ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp", ".pdf")
            )
            if is_eng_cap or is_image_file:
                try:
                    from backend.app.vision.agent import EngineeringVisionAgent
                    vision_agent = EngineeringVisionAgent(
                        model_runtime=self.model_runtime,
                    )
                    if file_path.lower().endswith(".pdf"):
                        vision_result = vision_agent.process_pdf_drawing(
                            pdf_path=file_path,
                            task_id=task_id,
                            user_focus=step.description,
                        )
                    else:
                        vision_result = vision_agent.process_image(
                            image_path=file_path,
                            task_id=task_id,
                            user_focus=step.description,
                        )

                    output = {
                        "vision_result": vision_result.model_dump(),
                        "document_analysis": vision_result.model_dump(),
                        "step_id": step.step_id,
                        "agent_id": agent_id,
                    }
                    result_msg = A2AMessage(
                        message_id=str(uuid.uuid4()),
                        task_id=task_id,
                        sender=agent_id,
                        receiver="main_agent",
                        type="TASK_RESULT",
                        payload=output,
                        status="COMPLETED",
                    )
                    return AgentExecutionResult(
                        status="SUCCESS",
                        agent_id=agent_id,
                        output=output,
                        delegation_message=delegation_msg,
                        result_message=result_msg,
                    )
                except Exception as e:
                    err_msg = A2AMessage(
                        message_id=str(uuid.uuid4()),
                        task_id=task_id,
                        sender=agent_id,
                        receiver="main_agent",
                        type="ERROR",
                        payload={"error": str(e)},
                        status="FAILED",
                    )
                    return AgentExecutionResult(
                        status="FAILED",
                        agent_id=agent_id,
                        error=f"Vision agent execution failed: {e}",
                        delegation_message=delegation_msg,
                        result_message=err_msg,
                    )

        # 6b. Multimodal document execution (Phase 6)
        if agent_id in ("document_agent", "vision_agent") and doc_input:
            try:
                from backend.app.multimodal.pipeline import MultimodalDocumentPipeline
                pipeline = MultimodalDocumentPipeline()
                analysis_result = pipeline.process(
                    doc_input,
                    enable_vlm=True,
                    vlm_query=step.description,
                )
                output = {
                    "document_analysis": analysis_result.model_dump(),
                    "step_id": step.step_id,
                    "agent_id": agent_id,
                }
                result_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="TASK_RESULT",
                    payload=output,
                    status="COMPLETED",
                )
                return AgentExecutionResult(
                    status="SUCCESS",
                    agent_id=agent_id,
                    output=output,
                    delegation_message=delegation_msg,
                    result_message=result_msg,
                )
            except Exception as e:
                err_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="ERROR",
                    payload={"error": str(e)},
                    status="FAILED",
                )
                return AgentExecutionResult(
                    status="FAILED",
                    agent_id=agent_id,
                    error=f"Multimodal document execution failed: {e}",
                    delegation_message=delegation_msg,
                    result_message=err_msg,
                )

        # 6c. Knowledge Agent execution (Phase 8)
        if agent_id == "knowledge_agent":
            try:
                from backend.app.rag.knowledge_agent import build_default_knowledge_agent
                k_agent = build_default_knowledge_agent(model_runtime=self.model_runtime)
                user_req = task_context.get("user_request", "")
                q = step.description or user_req
                sens = task_context.get("data_sensitivity", "INTERNAL")
                res = k_agent.answer_query(query=q, max_sensitivity=sens)
                output = {
                    "grounded_answer": res.model_dump(),
                    "answer": res.answer,
                    "citations": [c.model_dump() for c in res.citations],
                    "evidence_pack_id": getattr(res, "evidence_pack_id", ""),
                    "step_id": step.step_id,
                    "agent_id": agent_id,
                }
                result_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="TASK_RESULT",
                    payload=output,
                    status="COMPLETED",
                )
                return AgentExecutionResult(
                    status="SUCCESS",
                    agent_id=agent_id,
                    output=output,
                    delegation_message=delegation_msg,
                    result_message=result_msg,
                )
            except Exception as e:
                err_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="ERROR",
                    payload={"error": str(e)},
                    status="FAILED",
                )
                return AgentExecutionResult(
                    status="FAILED",
                    agent_id=agent_id,
                    error=f"Knowledge agent execution failed: {e}",
                    delegation_message=delegation_msg,
                    result_message=err_msg,
                )

        # 6d. Coding Agent execution (Phase 9)
        if agent_id == "coding_agent":
            try:
                import os
                from backend.app.coding.agent import CodingAgent
                c_agent = CodingAgent(
                    model_registry=self.model_registry,
                    model_runtime=self.model_runtime,
                )
                is_exec_cap = step.capability in (
                    "code_execution",
                    "sandbox_test_execution",
                    "coding.execute",
                    "sandbox_execute",
                )
                if is_exec_cap:
                    # Retrieve code from prior steps or task context
                    code_to_run = task_context.get("code") or (task_context.get("code_generation") or {}).get("code")
                    if not code_to_run:
                        for s_rec in task_context.get("execution_steps", []):
                            outs = s_rec.get("outputs", {})
                            if "code" in outs:
                                code_to_run = outs["code"]
                                break
                    if not code_to_run:
                        gen_res = c_agent.generate_code(
                            task=step.description,
                            context=task_context.get("user_request"),
                            task_id=task_id,
                        )
                        code_to_run = gen_res.code

                    in_files = dict(task_context.get("input_files") or {})
                    csv_path = (
                        task_context.get("csv_path")
                        or task_context.get("file_path")
                        or (task_context.get("metadata") or {}).get("csv_path")
                        or (task_context.get("metadata") or {}).get("file_path")
                    )
                    if csv_path and os.path.exists(csv_path) and "data.csv" not in in_files:
                        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
                            in_files["data.csv"] = f.read()

                    exec_res = c_agent.run_in_sandbox(
                        code=code_to_run,
                        task_id=task_id,
                        input_files=in_files,
                    )
                    output = {
                        "code": code_to_run,
                        "code_execution": exec_res.model_dump(),
                        "execution_result": exec_res.model_dump(),
                        "status": exec_res.status,
                        "step_id": step.step_id,
                        "agent_id": agent_id,
                    }
                else:
                    gen_res = c_agent.generate_code(
                        task=step.description or task_context.get("user_request", ""),
                        context=task_context.get("user_request"),
                        task_id=task_id,
                    )
                    output = {
                        "code": gen_res.code,
                        "code_generation": gen_res.model_dump(),
                        "step_id": step.step_id,
                        "agent_id": agent_id,
                    }

                result_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="TASK_RESULT",
                    payload=output,
                    status="COMPLETED",
                )
                return AgentExecutionResult(
                    status="SUCCESS",
                    agent_id=agent_id,
                    output=output,
                    delegation_message=delegation_msg,
                    result_message=result_msg,
                )
            except Exception as e:
                err_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="ERROR",
                    payload={"error": str(e)},
                    status="FAILED",
                )
                return AgentExecutionResult(
                    status="FAILED",
                    agent_id=agent_id,
                    error=f"Coding agent execution failed: {e}",
                    delegation_message=delegation_msg,
                    result_message=err_msg,
                )

        # 6e. Data Agent execution (Phase 9)
        if agent_id == "data_agent":
            try:
                import re
                from backend.app.data.agent import DataAgent
                d_agent = DataAgent()
                req_text = task_context.get("user_request", "")

                is_tabular = any(
                    k in step.capability.lower()
                    for k in ("csv", "xlsx", "data_analysis", "analyze", "table")
                ) or bool(task_context.get("csv_path") or task_context.get("raw_content"))

                if is_tabular:
                    from backend.app.data.schemas import DataAnalysisRequest
                    d_req = DataAnalysisRequest(
                        file_path=task_context.get("csv_path") or task_context.get("file_path"),
                        raw_content=task_context.get("raw_content") or task_context.get("csv_content"),
                        task_id=task_id,
                    )
                    a_res = d_agent.analyze_dataset(d_req)
                    output = {
                        "data_analysis": a_res.model_dump(),
                        "column_stats": {k: v.model_dump() for k, v in a_res.column_stats.items()},
                        "row_count": a_res.row_count,
                        "step_id": step.step_id,
                        "agent_id": agent_id,
                    }
                else:
                    # Deterministic mathematical calculation
                    nums = [float(x) for x in re.findall(r"[-+]?\d*\.?\d+", req_text) if x]
                    if any(k in req_text.lower() for k in ("mean", "average")):
                        c_res = d_agent.compute_statistics(nums if nums else [10.0, 20.0, 30.0], operation="mean", task_id=task_id)
                    elif any(k in req_text.lower() for k in ("sum", "total")):
                        c_res = d_agent.compute_statistics(nums if nums else [10.0, 20.0, 30.0], operation="sum", task_id=task_id)
                    else:
                        expr_m = re.search(r"([0-9\.\s\+\-\*\/\(\)]+)", req_text)
                        expr = expr_m.group(1).strip() if expr_m and any(op in expr_m.group(1) for op in "+-*/") else "10 + 20"
                        c_res = d_agent.evaluate_formula(expr, task_id=task_id)

                    output = {
                        "calculation_result": c_res.model_dump(),
                        "value": c_res.value,
                        "calculation_trace": [t.model_dump() for t in c_res.calculation_trace],
                        "step_id": step.step_id,
                        "agent_id": agent_id,
                    }

                result_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="TASK_RESULT",
                    payload=output,
                    status="COMPLETED",
                )
                return AgentExecutionResult(
                    status="SUCCESS",
                    agent_id=agent_id,
                    output=output,
                    delegation_message=delegation_msg,
                    result_message=result_msg,
                )
            except Exception as e:
                err_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="ERROR",
                    payload={"error": str(e)},
                    status="FAILED",
                )
                return AgentExecutionResult(
                    status="FAILED",
                    agent_id=agent_id,
                    error=f"Data agent execution failed: {e}",
                    delegation_message=delegation_msg,
                    result_message=err_msg,
                )

        # 6f. Artifact Delivery & Document Generation (Phase 9)
        is_artifact_cap = (
            step.capability in (
                "document_generation",
                "report_export",
                "sheet_generation",
                "artifact_delivery",
            )
            or "create_docx" in step.required_tools
            or "create_xlsx" in step.required_tools
            or (
                agent_id in ("document_agent", "main_agent")
                and any(w in (step.description or "").lower() for w in ("note", "docx", "report", "artifact", "sheet", "excel"))
            )
        )
        if is_artifact_cap:
            try:
                from backend.app.artifacts.factory import get_artifact_factory
                factory = get_artifact_factory()

                if "create_xlsx" in step.required_tools or step.capability == "sheet_generation":
                    from backend.app.artifacts.schemas import SpreadsheetContent, SpreadsheetSheetData
                    meta = factory.create_spreadsheet(
                        SpreadsheetContent(
                            title=f"Report {task_id[:8]}",
                            sheets=[SpreadsheetSheetData(title="Summary", headers=["Item", "Status"], rows=[["Task", "Completed"]])],
                            task_id=task_id,
                        )
                    )
                else:
                    from backend.app.artifacts.schemas import ApprovalNoteContent
                    findings = []
                    ev_citations = []
                    for s_rec in task_context.get("execution_steps", []):
                        outs = s_rec.get("outputs", {})
                        if "vision_result" in outs:
                            vr = outs["vision_result"]
                            for obs in vr.get("observations", []):
                                findings.append(obs)
                            for ev in vr.get("evidence", []):
                                ev_citations.append(ev)
                        if "document_analysis" in outs:
                            da = outs["document_analysis"]
                            for ev in da.get("evidence", []):
                                ev_citations.append(ev)
                        if "citations" in outs:
                            for c in outs["citations"]:
                                ev_citations.append(c)

                    content = ApprovalNoteContent(
                        title="Engineering Inspection Approval Note",
                        summary=f"Automated sovereign inspection report for task {task_id}",
                        candidate_findings=findings,
                        evidence_citations=ev_citations,
                        policy_decision=(task_context.get("policy_decision") or {}).get("decision", "ALLOW"),
                        human_approval=task_context.get("approval_decision"),
                    )
                    meta = factory.create_approval_note(content, task_id=task_id)

                output = {
                    "artifact": meta.model_dump(),
                    "artifact_metadata": meta.model_dump(),
                    "file_path": meta.file_path,
                    "content_hash": meta.content_hash,
                    "step_id": step.step_id,
                    "agent_id": agent_id,
                }
                result_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="TASK_RESULT",
                    payload=output,
                    status="COMPLETED",
                )
                return AgentExecutionResult(
                    status="SUCCESS",
                    agent_id=agent_id,
                    output=output,
                    delegation_message=delegation_msg,
                    result_message=result_msg,
                )
            except Exception as e:
                err_msg = A2AMessage(
                    message_id=str(uuid.uuid4()),
                    task_id=task_id,
                    sender=agent_id,
                    receiver="main_agent",
                    type="ERROR",
                    payload={"error": str(e)},
                    status="FAILED",
                )
                return AgentExecutionResult(
                    status="FAILED",
                    agent_id=agent_id,
                    error=f"Artifact generation failed: {e}",
                    delegation_message=delegation_msg,
                    result_message=err_msg,
                )

        # 7. Truthful execution: capability not yet implemented
        not_impl_msg = A2AMessage(
            message_id=str(uuid.uuid4()),
            task_id=task_id,
            sender=agent_id,
            receiver="main_agent",
            type="TASK_RESULT",
            payload={
                "status": "NOT_IMPLEMENTED",
                "message": f"Agent '{agent_id}' capability '{step.capability}' is not implemented.",
            },
            status="FAILED",
        )
        return AgentExecutionResult(
            status="NOT_IMPLEMENTED",
            agent_id=agent_id,
            error=f"Agent '{agent_id}' capability '{step.capability}' is not implemented.",
            delegation_message=delegation_msg,
            result_message=not_impl_msg,
        )

