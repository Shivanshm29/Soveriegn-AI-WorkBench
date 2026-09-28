"""Test B: Task Understanding Node and Model Integration."""

import json
import pytest
from unittest.mock import MagicMock

from backend.app.models.registry import ModelRegistry
from backend.app.models.runtime import ModelRuntime
from backend.app.models.schemas import ModelResponse
from backend.app.orchestration.understanding import (
    TaskUnderstanding,
    understand_task,
    extract_json_from_text,
)
from backend.app.orchestration.errors import TaskUnderstandingError


def test_structured_understanding_from_valid_json():
    """Verify parsing and schema validation of valid model response."""
    raw_response = json.dumps({
        "intent": "Summarize financial inspection report",
        "capabilities": ["document_extraction", "reasoning"],
        "modalities": ["text"],
        "complexity": "MEDIUM",
        "output_type": "summary",
        "risk_indicators": [],
        "input_references": ["report.pdf"],
    })

    mock_runtime = MagicMock(spec=ModelRuntime)
    mock_runtime.chat.return_value = ModelResponse(
        content=raw_response,
        model="Qwen/Qwen3-4B",
    )
    registry = ModelRegistry()

    result = understand_task(
        user_request="Please summarize this inspection report: report.pdf",
        runtime=mock_runtime,
        model_registry=registry,
    )

    assert isinstance(result, TaskUnderstanding)
    assert result.intent == "Summarize financial inspection report"
    assert "document_extraction" in result.capabilities
    assert "reasoning" in result.capabilities
    assert result.complexity == "MEDIUM"
    assert result.input_references == ["report.pdf"]


def test_understanding_extracts_markdown_codeblocks():
    """Verify JSON extraction when wrapped in markdown code fence."""
    raw_output = """```json
    {
        "intent": "Extract drawing features",
        "capabilities": ["visual_reasoning"],
        "modalities": ["image"],
        "complexity": "HIGH",
        "output_type": "spatial_data"
    }
    ```"""
    parsed = extract_json_from_text(raw_output)
    assert parsed["intent"] == "Extract drawing features"
    assert parsed["complexity"] == "HIGH"


def test_malformed_model_output_raises_structured_error():
    """Verify malformed model output fails cleanly with TaskUnderstandingError."""
    mock_runtime = MagicMock(spec=ModelRuntime)
    mock_runtime.chat.return_value = ModelResponse(
        content="I am unable to output JSON: This is pure conversational text.",
        model="Qwen/Qwen3-4B",
    )
    registry = ModelRegistry()

    with pytest.raises(TaskUnderstandingError):
        understand_task(
            user_request="Analyze data",
            runtime=mock_runtime,
            model_registry=registry,
        )


def test_empty_user_request_raises_error():
    """Verify empty user queries are rejected immediately."""
    mock_runtime = MagicMock(spec=ModelRuntime)
    registry = ModelRegistry()

    with pytest.raises(TaskUnderstandingError):
        understand_task("", runtime=mock_runtime, model_registry=registry)
