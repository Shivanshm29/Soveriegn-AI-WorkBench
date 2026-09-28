"""Local OpenAI-compatible model runtime adapter (e.g., vLLM)."""

import json
from typing import List, Optional, Dict, Any
import httpx

from backend.app.models.runtime import ModelRuntime
from backend.app.models.schemas import (
    ModelRequest,
    ModelResponse,
    ChatMessage,
    ContentPart,
    ToolCall,
    FunctionCall,
    UsageMetadata,
)
from backend.app.models.health import RuntimeHealth, HealthStatus
from backend.app.models.errors import (
    ModelRuntimeError,
    ModelUnavailableError,
    ModelTimeoutError,
    ModelNotFoundError,
    ModelConfigurationError,
    ModelResponseError,
    ModelCapabilityError,
)
from backend.app.security.network_policy import (
    validate_sovereign_url,
    SovereigntyViolationError,
)


class LocalOpenAIRuntime(ModelRuntime):
    """Adapter for local OpenAI-compatible endpoints (vLLM / llama.cpp / local model servers).

    Adheres strictly to sovereign isolation: rejects external cloud hosts and requires
    no remote credentials or internet connectivity.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000/v1",
        api_key: str = "local-only",
        timeout: float = 120.0,
        health_timeout: float = 5.0,
        sovereign_mode: bool = True,
        runtime_name: str = "vllm",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.health_timeout = health_timeout
        self.sovereign_mode = sovereign_mode
        self.runtime_name = runtime_name

        # Enforce sovereign boundary before allowing connection
        self._validate_endpoint(self.base_url)

    def _validate_endpoint(self, url: str) -> None:
        """Validate URL under sovereign policy."""
        try:
            validate_sovereign_url(url, sovereign_mode=self.sovereign_mode)
        except SovereigntyViolationError as e:
            raise ModelConfigurationError(str(e), details={"base_url": url}) from e

    def capabilities(self) -> List[str]:
        """Return supported capabilities of the local OpenAI-compatible runtime."""
        return ["text", "multimodal", "tool_calling", "structured_output"]

    def _format_messages(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """Format normalized ChatMessages into OpenAI-compatible payload format."""
        formatted: List[Dict[str, Any]] = []
        for msg in messages:
            entry: Dict[str, Any] = {"role": msg.role}

            if isinstance(msg.content, str):
                entry["content"] = msg.content
            elif isinstance(msg.content, list):
                # Multimodal content parts
                parts: List[Dict[str, Any]] = []
                for part in msg.content:
                    if part.type == "text" and part.text is not None:
                        parts.append({"type": "text", "text": part.text})
                    elif part.type == "image_url" and part.image_url is not None:
                        parts.append({"type": "image_url", "image_url": part.image_url})
                    elif part.type == "image_path" and part.image_path is not None:
                        parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"file://{part.image_path}"}
                        })
                entry["content"] = parts

            if msg.name:
                entry["name"] = msg.name
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]

            formatted.append(entry)
        return formatted

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Send chat completion request to the local endpoint."""
        self._validate_endpoint(self.base_url)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload: Dict[str, Any] = {
            "model": request.model_id,
            "messages": self._format_messages(request.messages),
            "temperature": request.temperature,
        }

        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.tools is not None:
            payload["tools"] = request.tools
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice
        if request.response_format is not None:
            payload["response_format"] = request.response_format

        endpoint_url = f"{self.base_url}/chat/completions"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(endpoint_url, json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise ModelTimeoutError(
                f"Model request to {endpoint_url} timed out after {self.timeout}s",
                details={"model_id": request.model_id, "timeout": self.timeout},
            ) from e
        except (httpx.ConnectError, httpx.NetworkError) as e:
            raise ModelUnavailableError(
                f"Local model server at {self.base_url} is unreachable: {str(e)}",
                details={"base_url": self.base_url, "model_id": request.model_id},
            ) from e
        except Exception as e:
            raise ModelRuntimeError(
                f"Unexpected connection error contacting {self.base_url}: {str(e)}",
                details={"base_url": self.base_url},
            ) from e

        # Handle HTTP status codes
        if resp.status_code == 404:
            raise ModelNotFoundError(
                f"Model '{request.model_id}' or endpoint not found at {endpoint_url} (HTTP 404)",
                details={"status_code": 404, "body": resp.text},
            )
        elif resp.status_code >= 400:
            raise ModelRuntimeError(
                f"Local model server error HTTP {resp.status_code}: {resp.text}",
                details={"status_code": resp.status_code, "body": resp.text},
            )

        # Parse response body
        try:
            data = resp.json()
        except Exception as e:
            raise ModelResponseError(
                f"Malformed JSON returned by model server: {resp.text[:200]}",
                details={"raw_body": resp.text},
            ) from e

        if not isinstance(data, dict) or "choices" not in data or not data["choices"]:
            raise ModelResponseError(
                "Missing 'choices' in model server response",
                details={"raw_response": data},
            )

        choice = data["choices"][0]
        msg = choice.get("message", {})
        content = msg.get("content")
        finish_reason = choice.get("finish_reason")

        # Parse tool calls if present
        tool_calls: Optional[List[ToolCall]] = None
        raw_tool_calls = msg.get("tool_calls")
        if raw_tool_calls and isinstance(raw_tool_calls, list):
            tool_calls = []
            for tc in raw_tool_calls:
                func = tc.get("function", {})
                tool_calls.append(
                    ToolCall(
                        id=tc.get("id", ""),
                        type=tc.get("type", "function"),
                        function=FunctionCall(
                            name=func.get("name", ""),
                            arguments=func.get("arguments", "{}"),
                        ),
                    )
                )

        # Parse token usage
        usage_data = data.get("usage", {})
        usage = UsageMetadata(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        # Validate structured output if requested
        if request.response_format and request.response_format.get("type") == "json_object":
            if content is None:
                raise ModelResponseError(
                    "Structured output requested but model returned empty content",
                    details={"raw_response": data},
                )
            try:
                json.loads(content)
            except Exception as e:
                raise ModelResponseError(
                    f"Model returned invalid JSON for structured output request: {content[:200]}",
                    details={"content": content, "error": str(e)},
                ) from e

        return ModelResponse(
            model_id=data.get("model", request.model_id),
            content=content,
            finish_reason=finish_reason,
            usage=usage,
            tool_calls=tool_calls,
            raw_response_metadata=data,
        )

    def health_check(self) -> RuntimeHealth:
        """Perform a real local runtime health check via GET /models."""
        try:
            self._validate_endpoint(self.base_url)
        except ModelConfigurationError as e:
            return RuntimeHealth(
                status=HealthStatus.MISCONFIGURED,
                runtime=self.runtime_name,
                base_url=self.base_url,
                error=str(e),
                details=e.details,
            )

        headers = {"Authorization": f"Bearer {self.api_key}"}
        endpoint_url = f"{self.base_url}/models"

        try:
            with httpx.Client(timeout=self.health_timeout) as client:
                resp = client.get(endpoint_url, headers=headers)
        except httpx.TimeoutException as e:
            return RuntimeHealth(
                status=HealthStatus.TIMEOUT,
                runtime=self.runtime_name,
                base_url=self.base_url,
                error=f"Health check timed out after {self.health_timeout}s",
            )
        except (httpx.ConnectError, httpx.NetworkError) as e:
            return RuntimeHealth(
                status=HealthStatus.UNAVAILABLE,
                runtime=self.runtime_name,
                base_url=self.base_url,
                error=f"Connection refused or server unreachable: {str(e)}",
            )
        except Exception as e:
            return RuntimeHealth(
                status=HealthStatus.UNKNOWN_ERROR,
                runtime=self.runtime_name,
                base_url=self.base_url,
                error=f"Unexpected health check failure: {str(e)}",
            )

        if resp.status_code != 200:
            return RuntimeHealth(
                status=HealthStatus.MISCONFIGURED,
                runtime=self.runtime_name,
                base_url=self.base_url,
                error=f"Endpoint returned HTTP status {resp.status_code}",
                details={"body": resp.text},
            )

        try:
            data = resp.json()
            models_list = [
                m["id"]
                for m in data.get("data", [])
                if isinstance(m, dict) and "id" in m
            ]
            return RuntimeHealth(
                status=HealthStatus.HEALTHY,
                runtime=self.runtime_name,
                base_url=self.base_url,
                models=models_list,
            )
        except Exception as e:
            return RuntimeHealth(
                status=HealthStatus.UNKNOWN_ERROR,
                runtime=self.runtime_name,
                base_url=self.base_url,
                error=f"Failed to parse /models response: {str(e)}",
            )

    def model_available(self, model_name: str) -> bool:
        """Determine whether a configured model is actually installed and available."""
        health = self.health_check()
        if health.status != HealthStatus.HEALTHY:
            return False
        return model_name in health.models
