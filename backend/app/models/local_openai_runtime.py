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
from backend.app.security.sovereignty_policy import (
    SovereigntyPolicy,
    get_sovereignty_policy,
)
from backend.app.security.network_policy import SovereigntyViolationError


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
        policy: Optional[SovereigntyPolicy] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.health_timeout = health_timeout
        self.sovereign_mode = sovereign_mode
        self.runtime_name = runtime_name
        self.policy = policy or get_sovereignty_policy()

        # Enforce sovereign boundary through central policy before allowing connection
        self._validate_endpoint(self.base_url)

    def _validate_endpoint(self, url: str) -> None:
        """Validate URL under central sovereign policy."""
        try:
            self.policy.validate_endpoint(url, component="model_runtime")
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

        target_model = request.model_id
        alias_map = {
            "Qwen/Qwen3-4B": "qwen2.5:3b",
            "qwen3:4b": "qwen3:4b",
            "Qwen/Qwen3-VL-4B-Instruct": "qwen3-vl:4b",
            "Qwen/Qwen3-VL-8B-Instruct": "qwen3-vl:8b",
            "Qwen/Qwen2.5-Coder-3B-Instruct": "qwen2.5-coder:3b",
            "Qwen/Qwen2.5-Coder-7B-Instruct": "qwen2.5-coder:3b",
            "Qwen/Qwen3-Coder": "qwen3-coder:latest",
            "qwen3-small": "qwen2.5:3b",
            "qwen3-vl-small": "qwen3-vl:4b",
            "qwen-coder-small": "qwen2.5-coder:3b",
        }
        if target_model in alias_map:
            target_model = alias_map[target_model]

        payload: Dict[str, Any] = {
            "model": target_model,
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
            model_lower = (target_model or "").lower()
            if "11434" in self.base_url and "qwen3" in model_lower:
                pass
            else:
                payload["response_format"] = request.response_format

        # Disable Qwen3 "thinking" mode to prevent empty-output errors.
        model_lower = (target_model or "").lower()
        if "qwen3" in model_lower or "qwen2.5" in model_lower:
            payload["chat_template_kwargs"] = {"enable_thinking": False}

        endpoint_url = f"{self.base_url}/chat/completions"

        try:
            with httpx.Client(timeout=self.timeout, trust_env=False) as client:
                resp = client.post(endpoint_url, json=payload, headers=headers)
                # Redirect protection
                if resp.is_redirect and "location" in resp.headers:
                    redirect_url = str(resp.url.join(resp.headers["location"]))
                    self.policy.validate_endpoint(redirect_url, component="model_runtime:redirect")
        except SovereigntyViolationError as e:
            raise ModelConfigurationError(str(e), details={"endpoint_url": endpoint_url}) from e
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
        except ModelRuntimeError:
            raise
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
            # Attempt to surface a cleaner error from JSON body if available
            error_detail = resp.text
            try:
                err_body = resp.json()
                if isinstance(err_body, dict):
                    if "error" in err_body and isinstance(err_body["error"], dict):
                        error_detail = err_body["error"].get("message", resp.text)
                    elif "message" in err_body:
                        error_detail = err_body["message"]
            except Exception:
                pass
            raise ModelRuntimeError(
                f"Local model server error HTTP {resp.status_code}: {error_detail}",
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

        # Normalise: some servers return empty string instead of None
        if content == "":
            content = None

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
                import re
                m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
                if not m:
                    m = re.search(r"(\{.*\})", content, re.DOTALL)
                if m:
                    try:
                        json.loads(m.group(1))
                    except Exception:
                        raise ModelResponseError(
                            f"Model returned invalid JSON for structured output request: {content[:200]}",
                            details={"content": content, "error": str(e)},
                        ) from e
                else:
                    raise ModelResponseError(
                        f"Model returned invalid JSON for structured output request: {content[:200]}",
                        details={"content": content, "error": str(e)},
                    ) from e

        # Final guard: if both content and tool_calls are absent, use empty string
        # so downstream consumers receive a valid (if empty) response instead of crashing.
        if content is None and not tool_calls:
            content = ""

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
            with httpx.Client(timeout=self.health_timeout, trust_env=False) as client:
                resp = client.get(endpoint_url, headers=headers)
        except SovereigntyViolationError as e:
            return RuntimeHealth(
                status=HealthStatus.MISCONFIGURED,
                runtime=self.runtime_name,
                base_url=self.base_url,
                error=f"Sovereignty violation: {str(e)}",
            )
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
