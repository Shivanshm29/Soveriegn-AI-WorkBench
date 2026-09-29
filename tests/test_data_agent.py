"""Unit tests for Data / Calculation Agent, safe arithmetic, traces, and dataset analysis."""

import pytest
from backend.app.agents.registry import AgentRegistry
from backend.app.data import (
    DataAgent,
    SafeCalculator,
    DataAnalyzer,
    CalculationVerifier,
    CalculationRequest,
    DataAnalysisRequest,
    run_python_calculation,
)
from tests.fixtures.phase_9_fixtures import (
    SAMPLE_CSV_CONTENT,
    create_sample_csv_file,
    create_sample_xlsx_file,
)


def test_data_agent_registered_in_registry():
    """Verify data_agent is registered with calculation and data analysis capabilities."""
    registry = AgentRegistry()
    assert registry.exists("data_agent")
    contract = registry.get("data_agent")
    assert contract is not None
    assert "calculation" in contract.capabilities
    assert "data_analysis" in contract.capabilities
    assert "arithmetic" in contract.capabilities
    assert "statistics" in contract.capabilities
    assert "python_calculation" in contract.allowed_tools
    assert contract.risk_class == "LOW"


def test_safe_calculator_arithmetic_and_precedence():
    """Verify safe formula evaluation handles precedence and mathematical operations."""
    calc = SafeCalculator()
    res = calc.evaluate_expression("(10 + 20) * 3 - 5 / 2")
    assert res.is_verified is True
    assert res.value == 87.5
    assert len(res.calculation_trace) > 0


def test_safe_calculator_blocks_arbitrary_code():
    """Verify dangerous functions and imports are rejected by safe AST evaluator."""
    calc = SafeCalculator()
    res1 = calc.evaluate_expression("__import__('os').system('dir')")
    assert res1.status == "FAILED"

    res2 = calc.evaluate_expression("eval('2 + 2')")
    assert res2.status == "FAILED"

    res3 = calc.evaluate_expression("open('secret.txt')")
    assert res3.status == "FAILED"


def test_safe_calculator_division_by_zero():
    """Verify division by zero is handled safely without unhandled exception."""
    calc = SafeCalculator()
    res = calc.evaluate_expression("100 / 0")
    assert res.status == "FAILED"
    assert "Division by zero" in (res.error or "")


def test_safe_calculator_statistical_mean_and_trace():
    """Verify statistical mean computation generates step-by-step derivation trace."""
    calc = SafeCalculator()
    vals = [10.0, 20.0, 30.0, 40.0]
    res = calc.calculate_statistics(vals, operation="mean")
    assert res.status == "SUCCESS"
    assert res.value == 25.0
    assert res.is_verified is True
    # Verify trace steps
    step_names = [t.step for t in res.calculation_trace]
    assert "sum_values" in step_names
    assert "count_values" in step_names
    assert "compute_mean" in step_names


def test_safe_calculator_statistical_stdev_and_median():
    """Verify median and standard deviation calculations."""
    calc = SafeCalculator()
    vals = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    res_med = calc.calculate_statistics(vals, operation="median")
    assert res_med.value == 4.5

    res_std = calc.calculate_statistics(vals, operation="stdev")
    assert res_std.value is not None
    assert res_std.value > 0


def test_data_analyzer_csv_summarize(tmp_path):
    """Verify CSV reading and column statistical summaries."""
    csv_file = str(tmp_path / "equipment_vibration.csv")
    create_sample_csv_file(csv_file)

    analyzer = DataAnalyzer()
    req = DataAnalysisRequest(file_path=csv_file)
    res = analyzer.analyze(req)

    assert res.status == "SUCCESS"
    assert res.row_count == 6
    assert "vibration_mms" in res.column_stats
    assert res.column_stats["vibration_mms"].min_value == 1.8
    assert res.column_stats["vibration_mms"].max_value == 5.2


def test_data_analyzer_filtering_and_grouping(tmp_path):
    """Verify row filtering and group aggregation."""
    csv_file = str(tmp_path / "equipment_vibration.csv")
    create_sample_csv_file(csv_file)

    analyzer = DataAnalyzer()
    req = DataAnalysisRequest(
        file_path=csv_file,
        filter_column="vibration_mms",
        filter_operator=">",
        filter_value=3.0,
        group_by_column="equipment_id",
        aggregate_column="temperature_c",
        aggregate_function="mean",
    )
    res = analyzer.analyze(req)

    assert res.status == "SUCCESS"
    assert res.filtered_row_count == 2
    assert "PX-417" in res.aggregated_results
    assert res.aggregated_results["PX-417"] > 70.0


def test_data_analyzer_xlsx_reading(tmp_path):
    """Verify XLSX reading and analysis."""
    xlsx_file = str(tmp_path / "equipment.xlsx")
    create_sample_xlsx_file(xlsx_file)

    analyzer = DataAnalyzer()
    req = DataAnalysisRequest(file_path=xlsx_file, file_type="xlsx")
    res = analyzer.analyze(req)

    assert res.status == "SUCCESS"
    assert res.row_count == 6
    assert "pressure_bar" in res.column_stats


def test_calculation_verifier():
    """Verify CalculationVerifier checks math consistency and flags mismatches."""
    vals = [10.0, 20.0, 30.0]
    # Correct mean
    v1 = CalculationVerifier.verify_mean(vals, reported_mean=20.0)
    assert v1["is_verified"] is True

    # Fabricated / incorrect mean
    v2 = CalculationVerifier.verify_mean(vals, reported_mean=99.9)
    assert v2["is_verified"] is False


def test_python_calculation_tool_execution():
    """Verify python_calculation tool execution function."""
    out = run_python_calculation(expression="25 * 4 + 10")
    assert out["status"] == "SUCCESS"
    assert out["value"] == 110.0
    assert out["is_verified"] is True
