"""Structured task understanding using ModelRuntime via ModelRegistry."""

import json
import re
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field, ValidationError

from backend.app.models.runtime import ModelRuntime
from backend.app.models.registry import ModelRegistry
from backend.app.models.schemas import ModelRequest, ChatMessage
from backend.app.orchestration.errors import TaskUnderstandingError


class TaskUnderstanding(BaseModel):
    """Structured understanding of a user task request."""

    intent: str
    capabilities: List[str] = Field(default_factory=list)
    modalities: List[str] = Field(default_factory=lambda: ["text"])
    complexity: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"
    output_type: str = "text"
    risk_indicators: List[str] = Field(default_factory=list)
    input_references: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert understanding to dict."""
        return self.model_dump(mode="json")


UNDERSTANDING_SYSTEM_PROMPT = """You are a task analysis specialist in a sovereign on-premise AI workbench.
Analyze the user query and provide a structured JSON assessment with exact keys:
- "intent": clear summary of user intent
- "capabilities": list of required capabilities from: [workflow_management, planning, reasoning, structured_reasoning, document_extraction, pdf_ingestion, visual_reasoning, image_understanding, knowledge_search, knowledge_retrieval, code_generation, code_execution, calculation, data_analysis]
- "modalities": list containing "text", "image", etc.
- "complexity": "LOW", "MEDIUM", or "HIGH"
- "output_type": e.g., "summary", "report", "code", "table", "analysis"
- "risk_indicators": list of risk indicators if any (e.g. "code_execution", "privileged_file_access")
- "input_references": list of file paths or document names mentioned

Respond strictly with valid JSON and nothing else."""


def extract_json_from_text(text: str) -> Dict[str, Any]:
    """Extract and parse JSON from model response text."""
    clean_text = text.strip()
    # Remove markdown code blocks if present
    if clean_text.startswith("```"):
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_text, re.DOTALL)
        if match:
            clean_text = match.group(1)
        else:
            clean_text = re.sub(r"^```[a-zA-Z]*\n?", "", clean_text)
            clean_text = re.sub(r"\n?```$", "", clean_text).strip()

    try:
        return json.loads(clean_text)
    except json.JSONDecodeError as e:
        # Try extracting first outer JSON object
        match = re.search(r"(\{.*\})", clean_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        raise TaskUnderstandingError(f"Failed to parse JSON from model output: {e}. Output was: {text[:200]}") from e


def understand_task(
    user_request: str,
    runtime: ModelRuntime,
    model_registry: ModelRegistry,
) -> TaskUnderstanding:
    """Analyze a user request using the configured local ModelRuntime."""
    if not user_request or not user_request.strip():
        raise TaskUnderstandingError("User request is empty.")

    # 1. Resolve reasoning model via ModelRegistry
    try:
        selection = model_registry.resolve(
            capabilities=["reasoning"],
            slot_hint="general_reasoning",
        )
        model_name = selection.selected_model_name
    except Exception as e:
        # Fallback to configured model name or active general model
        model_def = model_registry.get_model_definition("general_reasoning")
        if model_def:
            model_name = model_def.model_name
        else:
            raise TaskUnderstandingError(f"Failed to resolve model for understanding: {e}") from e

    # 2. Invoke local ModelRuntime
    req = ModelRequest(
        model=model_name,
        messages=[
            ChatMessage(role="system", content=UNDERSTANDING_SYSTEM_PROMPT),
            ChatMessage(role="user", content=f"Analyze this task:\n{user_request}"),
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    try:
        response = runtime.chat(req)
        content = response.content
    except Exception as e:
        raise TaskUnderstandingError(f"Model runtime error during task understanding: {e}") from e

    # 3. Parse and validate structured output
    parsed = extract_json_from_text(content)

    try:
        return TaskUnderstanding.model_validate(parsed)
    except ValidationError as e:
        raise TaskUnderstandingError(f"Model output violates TaskUnderstanding schema: {e}") from e
