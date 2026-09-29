"""Authoritative Data / Calculation Agent coordinating safe deterministic calculations and data analysis."""

import logging
from typing import Dict, List, Optional, Any, Union

from backend.app.data.schemas import (
    CalculationRequest,
    CalculationResult,
    DataAnalysisRequest,
    DataAnalysisResult,
    TableData,
)
from backend.app.data.calculator import SafeCalculator
from backend.app.data.analysis import DataAnalyzer
from backend.app.data.verifier import CalculationVerifier

logger = logging.getLogger("app.data.agent")


class DataAgent:
    """Local sovereign Data/Calculation Agent performing deterministic calculations and data transformations."""

    def __init__(
        self,
        calculator: Optional[SafeCalculator] = None,
        analyzer: Optional[DataAnalyzer] = None,
        verifier: Optional[CalculationVerifier] = None,
    ):
        self.calculator = calculator or SafeCalculator()
        self.analyzer = analyzer or DataAnalyzer()
        self.verifier = verifier or CalculationVerifier()

    def calculate(self, request: CalculationRequest) -> CalculationResult:
        """Execute a calculation request deterministically."""
        if request.expression:
            return self.calculator.evaluate_expression(
                expression=request.expression,
                variables=request.variables,
                task_id=request.task_id,
            )
        elif request.values is not None and request.operation:
            return self.calculator.calculate_statistics(
                values=request.values,
                operation=request.operation,
                task_id=request.task_id,
            )
        else:
            return CalculationResult(
                task_id=request.task_id,
                is_verified=False,
                status="INVALID_INPUT",
                error="Neither expression nor values+operation provided.",
            )

    def evaluate_formula(
        self,
        expression: str,
        variables: Optional[Dict[str, float]] = None,
        task_id: str = "formula_task",
    ) -> CalculationResult:
        """Safely evaluate an arithmetic formula."""
        return self.calculator.evaluate_expression(
            expression=expression,
            variables=variables,
            task_id=task_id,
        )

    def compute_statistics(
        self,
        values: List[float],
        operation: str = "mean",
        task_id: str = "stat_task",
    ) -> CalculationResult:
        """Compute statistical operation on numerical list with derivation trace."""
        return self.calculator.calculate_statistics(
            values=values,
            operation=operation,
            task_id=task_id,
        )

    def analyze_dataset(self, request: DataAnalysisRequest) -> DataAnalysisResult:
        """Analyze CSV or XLSX dataset with summaries, filtering, or aggregations."""
        return self.analyzer.analyze(request)

    def generate_table(self, headers: List[str], rows: List[List[Any]]) -> TableData:
        """Assemble structured table data and verify integrity."""
        data = TableData(
            headers=headers,
            rows=rows,
            row_count=len(rows),
            column_count=len(headers),
        )
        self.verifier.verify_table_data(data)
        return data
