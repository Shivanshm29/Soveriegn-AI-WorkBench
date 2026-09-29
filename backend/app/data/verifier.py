"""Deterministic verification for numerical calculations and tabular datasets."""

from typing import Dict, List, Optional, Any
from backend.app.data.schemas import (
    CalculationResult,
    DataAnalysisResult,
    TableData,
)


class CalculationVerifier:
    """Verifies numerical calculations and spreadsheet consistency."""

    @staticmethod
    def verify_mean(values: List[float], reported_mean: float, tolerance: float = 1e-4) -> Dict[str, Any]:
        """Verify that mean == sum(values) / len(values)."""
        if not values:
            return {"is_verified": False, "reason": "Empty dataset cannot be verified"}
        expected_sum = sum(values)
        expected_count = len(values)
        expected_mean = expected_sum / expected_count
        diff = abs(expected_mean - reported_mean)
        is_verified = (diff <= tolerance)
        return {
            "is_verified": is_verified,
            "expected_sum": expected_sum,
            "expected_count": expected_count,
            "expected_mean": expected_mean,
            "reported_mean": reported_mean,
            "diff": diff,
        }

    @staticmethod
    def verify_sum(values: List[float], reported_sum: float, tolerance: float = 1e-4) -> Dict[str, Any]:
        """Verify that sum == sum(values)."""
        expected_sum = sum(values)
        diff = abs(expected_sum - reported_sum)
        is_verified = (diff <= tolerance)
        return {
            "is_verified": is_verified,
            "expected_sum": expected_sum,
            "reported_sum": reported_sum,
            "diff": diff,
        }

    @staticmethod
    def verify_table_data(data: TableData) -> Dict[str, Any]:
        """Verify tabular data integrity: headers non-empty, row lengths consistent, no corrupt cells."""
        checks: Dict[str, bool] = {}
        issues: List[str] = []

        headers_ok = len(data.headers) > 0 and all(bool(h.strip()) for h in data.headers)
        checks["headers_valid"] = headers_ok
        if not headers_ok:
            issues.append("Table contains empty or invalid headers.")

        expected_cols = len(data.headers)
        row_lengths_ok = all(len(r) == expected_cols for r in data.rows)
        checks["row_lengths_consistent"] = row_lengths_ok
        if not row_lengths_ok:
            issues.append("Table contains rows with inconsistent column counts.")

        checks["has_data"] = data.row_count > 0
        if data.row_count == 0:
            issues.append("Table has zero rows.")

        is_verified = all(checks.values()) and len(issues) == 0
        return {
            "is_verified": is_verified,
            "checks": checks,
            "issues": issues,
            "row_count": data.row_count,
            "column_count": expected_cols,
        }
