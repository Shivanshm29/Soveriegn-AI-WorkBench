"""Pydantic schemas for deterministic data analysis and calculation operations."""

import uuid
from typing import Dict, List, Optional, Any, Union, Literal
from pydantic import BaseModel, Field


class CalculationRequest(BaseModel):
    """Request for a deterministic mathematical or statistical calculation."""

    operation: Optional[str] = None
    expression: Optional[str] = None
    values: Optional[List[float]] = None
    variables: Dict[str, float] = Field(default_factory=dict)
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    verify_result: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CalculationTraceStep(BaseModel):
    """Individual mathematical derivation or verification step."""

    step: str
    formula: str
    inputs: Dict[str, Any]
    output: Any


class CalculationResult(BaseModel):
    """Structured calculation result with full mathematical trace and verification."""

    calculation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    value: Optional[Union[float, int, List[float]]] = None
    expression: Optional[str] = None
    operation: Optional[str] = None
    is_verified: bool = True
    calculation_trace: List[CalculationTraceStep] = Field(default_factory=list)
    verification_checks: Dict[str, bool] = Field(default_factory=dict)
    status: Literal["SUCCESS", "FAILED", "INVALID_INPUT"] = "SUCCESS"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert calculation result to dictionary."""
        return self.model_dump(mode="json")


class ColumnStats(BaseModel):
    """Statistical summary of a single tabular column."""

    name: str
    dtype: str
    total_count: int
    null_count: int
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    sum_value: Optional[float] = None


class TableData(BaseModel):
    """Normalized tabular dataset representation."""

    headers: List[str]
    rows: List[List[Any]]
    row_count: int
    column_count: int


class DataAnalysisRequest(BaseModel):
    """Request to inspect, summarize, filter, or aggregate CSV or XLSX data."""

    file_path: Optional[str] = None
    raw_content: Optional[str] = None
    file_type: Literal["csv", "xlsx"] = "csv"
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    operations: List[str] = Field(default_factory=lambda: ["summarize"])
    filter_column: Optional[str] = None
    filter_value: Optional[Any] = None
    filter_operator: Optional[str] = "=="
    group_by_column: Optional[str] = None
    aggregate_column: Optional[str] = None
    aggregate_function: Optional[str] = "mean"
    max_rows: int = 50_000
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DataAnalysisResult(BaseModel):
    """Structured outcome of tabular data analysis."""

    analysis_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    file_type: str
    row_count: int
    column_count: int
    columns: List[str]
    column_stats: Dict[str, ColumnStats] = Field(default_factory=dict)
    aggregated_results: Dict[str, Any] = Field(default_factory=dict)
    filtered_row_count: Optional[int] = None
    filtered_rows_sample: Optional[List[Dict[str, Any]]] = None
    calculation_traces: List[CalculationTraceStep] = Field(default_factory=list)
    status: Literal["SUCCESS", "FAILED"] = "SUCCESS"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert data analysis result to dictionary."""
        return self.model_dump(mode="json")
