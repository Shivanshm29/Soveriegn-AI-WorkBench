"""Test Group D: Mocked runtime unit tests."""

from unittest.mock import patch, MagicMock
import httpx
import pytest

from backend.app.models.local_openai_runtime import LocalOpenAIRuntime
from backend.app.models.schemas import (
    ModelRequest,
    ChatMessage,
    ContentPart,
    ToolCall,
)
from backend.app.models.errors import (
    ModelRuntimeError,
    ModelUnavailableError,
    ModelTimeoutError,
    ModelNotFoundError,
    ModelResponseError,
)


@pytest.fixture
def runtime():
    return LocalOpenAIRuntime(
        base_url="http://127.0.0.1:8000/v1",
        timeout=10.0,
    )


def test_successful_response(runtime):
    """Test standard successful chat completion response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "chatcmpl-123",
        "model": "Qwen/Qwen3-4B",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Local model output text.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 8,
            "total_tokens": 20,
        },
    }

    with patch.object(httpx.Client, "post", return_value=mock_response):
        req = ModelRequest(
            model_id="Qwen/Qwen3-4B",
            messages=[ChatMessage(role="user", content="Hello")],
        )
        resp = runtime.generate(req)

        assert resp.content == "Local model output text."
        assert resp.model_id == "Qwen/Qwen3-4B"
        assert resp.finish_reason == "stop"
        assert resp.usage.total_tokens == 20
        assert resp.usage.prompt_tokens == 12
        assert resp.usage.completion_tokens == 8


def test_timeout_error(runtime):
    """Test request timeout raises ModelTimeoutError."""
    with patch.object(
        httpx.Client,
        "post",
        side_effect=httpx.TimeoutException("Timeout occurred"),
    ):
        req = ModelRequest(
            model_id="Qwen/Qwen3-4B",
            messages=[ChatMessage(role="user", content="Hello")],
        )
        with pytest.raises(ModelTimeoutError) as exc_info:
            runtime.generate(req)
        assert "timed out" in str(exc_info.value)


def test_connection_refused_error(runtime):
    """Test connection refused raises ModelUnavailableError."""
    with patch.object(
        httpx.Client,
        "post",
        side_effect=httpx.ConnectError("Connection refused"),
    ):
        req = ModelRequest(
            model_id="Qwen/Qwen3-4B",
            messages=[ChatMessage(role="user", content="Hello")],
        )
        with pytest.raises(ModelUnavailableError) as exc_info:
            runtime.generate(req)
        assert "unreachable" in str(exc_info.value)


def test_http_404_model_not_found(runtime):
    """Test HTTP 404 raises ModelNotFoundError."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Model not found"

    with patch.object(httpx.Client, "post", return_value=mock_response):
        req = ModelRequest(
            model_id="unknown-model",
            messages=[ChatMessage(role="user", content="Hello")],
        )
        with pytest.raises(ModelNotFoundError):
            runtime.generate(req)


def test_http_500_runtime_error(runtime):
    """Test HTTP 500 raises ModelRuntimeError."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal CUDA Out of Memory"

    with patch.object(httpx.Client, "post", return_value=mock_response):
        req = ModelRequest(
            model_id="Qwen/Qwen3-4B",
            messages=[ChatMessage(role="user", content="Hello")],
        )
        with pytest.raises(ModelRuntimeError) as exc_info:
            runtime.generate(req)
        assert "500" in str(exc_info.value)


def test_malformed_json_response(runtime):
    """Test server returning non-JSON raises ModelResponseError."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON string")
    mock_response.text = "<HTML>502 Bad Gateway</HTML>"

    with patch.object(httpx.Client, "post", return_value=mock_response):
        req = ModelRequest(
            model_id="Qwen/Qwen3-4B",
            messages=[ChatMessage(role="user", content="Hello")],
        )
        with pytest.raises(ModelResponseError):
            runtime.generate(req)


def test_missing_choices_response(runtime):
    """Test server returning JSON without choices raises ModelResponseError."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "ok"}  # No choices key

    with patch.object(httpx.Client, "post", return_value=mock_response):
        req = ModelRequest(
            model_id="Qwen/Qwen3-4B",
            messages=[ChatMessage(role="user", content="Hello")],
        )
        with pytest.raises(ModelResponseError) as exc_info:
            runtime.generate(req)
        assert "choices" in str(exc_info.value)


def test_structured_output_json_valid(runtime):
    """Test structured output request with valid JSON response passes."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "model": "Qwen/Qwen3-4B",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"verdict": "APPROVED", "confidence": 0.95}',
                },
                "finish_reason": "stop",
            }
        ],
    }

    with patch.object(httpx.Client, "post", return_value=mock_response):
        req = ModelRequest(
            model_id="Qwen/Qwen3-4B",
            messages=[ChatMessage(role="user", content="Give json")],
            response_format={"type": "json_object"},
        )
        resp = runtime.generate(req)
        assert resp.content == '{"verdict": "APPROVED", "confidence": 0.95}'


def test_structured_output_json_invalid(runtime):
    """Test structured output request with invalid JSON response raises ModelResponseError."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "model": "Qwen/Qwen3-4B",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Not valid JSON: { broken }",
                },
                "finish_reason": "stop",
            }
        ],
    }

    with patch.object(httpx.Client, "post", return_value=mock_response):
        req = ModelRequest(
            model_id="Qwen/Qwen3-4B",
            messages=[ChatMessage(role="user", content="Give json")],
            response_format={"type": "json_object"},
        )
        with pytest.raises(ModelResponseError) as exc_info:
            runtime.generate(req)
        assert "invalid JSON" in str(exc_info.value)


def test_tool_calling_response_parsing(runtime):
    """Test parsing of tool_calls in assistant response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "model": "Qwen/Qwen3-4B",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": '{"path": "report.pdf"}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }

    with patch.object(httpx.Client, "post", return_value=mock_response):
        req = ModelRequest(
            model_id="Qwen/Qwen3-4B",
            messages=[ChatMessage(role="user", content="Read report.pdf")],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "description": "Read file contents",
                    },
                }
            ],
        )
        resp = runtime.generate(req)
        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].id == "call_abc123"
        assert resp.tool_calls[0].function.name == "read_file"
        assert resp.tool_calls[0].function.arguments == '{"path": "report.pdf"}'


def test_multimodal_request_formatting(runtime):
    """Test formatting of multimodal content messages."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "model": "Qwen/Qwen3-VL-4B-Instruct",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Image contains an inspection certificate.",
                },
                "finish_reason": "stop",
            }
        ],
    }

    captured_payload = {}

    def fake_post(url, json=None, **kwargs):
        captured_payload.update(json)
        return mock_response

    with patch.object(httpx.Client, "post", side_effect=fake_post):
        req = ModelRequest(
            model_id="Qwen/Qwen3-VL-4B-Instruct",
            messages=[
                ChatMessage(
                    role="user",
                    content=[
                        ContentPart(type="text", text="What is in this image?"),
                        ContentPart(type="image_path", image_path="/data/drawing.png"),
                    ],
                )
            ],
        )
        resp = runtime.generate(req)
        assert resp.content == "Image contains an inspection certificate."
        # Verify captured payload structure
        messages_sent = captured_payload["messages"]
        assert len(messages_sent) == 1
        assert isinstance(messages_sent[0]["content"], list)
        assert messages_sent[0]["content"][0]["type"] == "text"
        assert messages_sent[0]["content"][1]["type"] == "image_url"
        assert messages_sent[0]["content"][1]["image_url"]["url"] == "file:///data/drawing.png"
