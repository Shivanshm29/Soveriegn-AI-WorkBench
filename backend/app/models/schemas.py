"""Runtime request and response schemas for ModelRuntime layer."""

from typing import List, Optional, Dict, Any, Union, Literal
from pydantic import BaseModel, Field


class ContentPart(BaseModel):
    """Part of a multimodal message (text or image)."""

    type: Literal["text", "image_url", "image_path"] = "text"
    text: Optional[str] = None
    image_url: Optional[Dict[str, Any]] = None
    image_path: Optional[str] = None


class FunctionCall(BaseModel):
    """Function call detail inside a tool call."""

    name: str
    arguments: str


class ToolCall(BaseModel):
    """Tool invocation produced by a model."""

    id: str
    type: Literal["function"] = "function"
    function: FunctionCall


class ChatMessage(BaseModel):
    """Normalized chat message supporting multimodal content and tool calling."""

    role: Literal["system", "user", "assistant", "tool"]
    content: Union[str, List[ContentPart]] = ""
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None


class ToolDefinition(BaseModel):
    """Specification of a tool passed in a model request."""

    type: Literal["function"] = "function"
    function: Dict[str, Any]


class UsageMetadata(BaseModel):
    """Token usage counters returned by the runtime."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ModelRequest(BaseModel):
    """Generic request to a model runtime."""

    model_id: str
    messages: List[ChatMessage]
    modality: List[str] = Field(default_factory=lambda: ["text"])
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    response_format: Optional[Dict[str, Any]] = None
    stream: bool = False


class ModelResponse(BaseModel):
    """Structured response returned by a model runtime."""

    model_id: str
    content: Optional[str] = None
    finish_reason: Optional[str] = None
    usage: Optional[UsageMetadata] = None
    tool_calls: Optional[List[ToolCall]] = None
    raw_response_metadata: Optional[Dict[str, Any]] = None
