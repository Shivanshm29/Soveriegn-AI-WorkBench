"""Schemas for local coding agent operations, code generation, and repairs."""

import uuid
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field


class CodingTask(BaseModel):
    """Specification of a coding task delegated to the Coding Agent."""

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    language: str = "python"
    input_files: Dict[str, Union[str, bytes]] = Field(default_factory=dict)
    requirements: List[str] = Field(default_factory=list)
    tests: Optional[str] = None
    context: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CodeGenerationResult(BaseModel):
    """Outcome of code generation through local ModelRouter / ModelRuntime."""

    task_id: str
    code: str
    model_id: str
    model_name: str
    explanation: Optional[str] = None
    status: str = "GENERATED"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CodeInspectionResult(BaseModel):
    """Static and structural analysis of generated code."""

    is_valid_syntax: bool
    syntax_error: Optional[str] = None
    imports: List[str] = Field(default_factory=list)
    functions: List[str] = Field(default_factory=list)
    classes: List[str] = Field(default_factory=list)
    security_flags: List[str] = Field(default_factory=list)
    analysis: str = ""


class CodeRepairResult(BaseModel):
    """Result of code debugging and repair attempt after failure."""

    task_id: str
    repaired_code: str
    original_code: str
    changes_made: str
    strategy: str
    iteration: int = 1
