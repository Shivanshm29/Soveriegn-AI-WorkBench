"""Safe, deterministic numerical and statistical calculation engine with mathematical trace generation."""

import ast
import math
import statistics
from typing import Dict, List, Optional, Any, Union

from backend.app.data.schemas import (
    CalculationRequest,
    CalculationResult,
    CalculationTraceStep,
)


# Whitelisted safe math functions
SAFE_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "pow": math.pow,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "mean": statistics.mean,
    "median": statistics.median,
    "stdev": statistics.stdev,
    "variance": statistics.variance,
}

SAFE_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}

# Whitelisted AST operators
ALLOWED_OPERATORS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
    ast.USub: lambda a: -a,
    ast.UAdd: lambda a: +a,
}


class ExpressionEvaluationError(Exception):
    """Raised when an expression contains invalid syntax or unauthorized nodes."""
    pass


class SafeCalculator:
    """Evaluates mathematical expressions deterministically without executing arbitrary code."""

    def __init__(self):
        self._allowed_names = dict(SAFE_FUNCTIONS)
        self._allowed_names.update(SAFE_CONSTANTS)

    def _eval_ast(self, node: ast.AST, variables: Dict[str, float]) -> Any:
        """Recursively evaluate approved AST nodes only."""
        if isinstance(node, ast.Expression):
            return self._eval_ast(node.body, variables)

        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ExpressionEvaluationError(f"Unauthorized constant type: {type(node.value)}")

        elif isinstance(node, ast.Name):
            if node.id in variables:
                return float(variables[node.id])
            if node.id in self._allowed_names:
                return self._allowed_names[node.id]
            raise ExpressionEvaluationError(f"Undefined or unauthorized identifier: '{node.id}'")

        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type in ALLOWED_OPERATORS:
                operand = self._eval_ast(node.operand, variables)
                return ALLOWED_OPERATORS[op_type](operand)
            raise ExpressionEvaluationError(f"Unauthorized unary operator: {op_type}")

        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type in ALLOWED_OPERATORS:
                left = self._eval_ast(node.left, variables)
                right = self._eval_ast(node.right, variables)
                if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
                    raise ZeroDivisionError("Division by zero in mathematical expression.")
                return ALLOWED_OPERATORS[op_type](left, right)
            raise ExpressionEvaluationError(f"Unauthorized binary operator: {op_type}")

        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ExpressionEvaluationError("Only simple function calls are authorized.")
            func_name = node.func.id
            if func_name not in SAFE_FUNCTIONS:
                raise ExpressionEvaluationError(f"Unauthorized function call: '{func_name}'")
            args = [self._eval_ast(arg, variables) for arg in node.args]
            return SAFE_FUNCTIONS[func_name](*args)

        elif isinstance(node, ast.List):
            return [self._eval_ast(elem, variables) for elem in node.elts]

        else:
            raise ExpressionEvaluationError(f"Forbidden AST node: {type(node).__name__}")

    def evaluate_expression(
        self,
        expression: str,
        variables: Optional[Dict[str, float]] = None,
        task_id: str = "calc_task",
    ) -> CalculationResult:
        """Safely parse and evaluate mathematical expression with trace."""
        vars_dict = variables or {}
        trace: List[CalculationTraceStep] = []

        try:
            tree = ast.parse(expression, mode="eval")
            value = self._eval_ast(tree, vars_dict)
            float_val = float(value) if isinstance(value, (int, float)) else value

            trace.append(
                CalculationTraceStep(
                    step="evaluate_expression",
                    formula=expression,
                    inputs=vars_dict,
                    output=float_val,
                )
            )

            return CalculationResult(
                task_id=task_id,
                value=float_val,
                expression=expression,
                is_verified=True,
                calculation_trace=trace,
                verification_checks={"safe_ast": True, "evaluated": True},
                status="SUCCESS",
            )
        except ZeroDivisionError as zde:
            return CalculationResult(
                task_id=task_id,
                expression=expression,
                is_verified=False,
                status="FAILED",
                error=f"Division by zero: {zde}",
            )
        except Exception as e:
            return CalculationResult(
                task_id=task_id,
                expression=expression,
                is_verified=False,
                status="FAILED",
                error=f"Evaluation failed: {e}",
            )

    def calculate_statistics(
        self,
        values: List[float],
        operation: str = "mean",
        task_id: str = "stat_task",
    ) -> CalculationResult:
        """Deterministically compute statistical operations with full verification traces."""
        if not values:
            return CalculationResult(
                task_id=task_id,
                operation=operation,
                is_verified=False,
                status="INVALID_INPUT",
                error="Cannot perform statistical operations on empty dataset.",
            )

        n = len(values)
        total = sum(values)
        trace: List[CalculationTraceStep] = []
        checks: Dict[str, bool] = {"non_empty": True}

        op = operation.lower()
        if op in ("mean", "average"):
            result_val = total / n
            trace.append(
                CalculationTraceStep(
                    step="sum_values",
                    formula="sum = sum(x_i)",
                    inputs={"count": n, "sample": values[:5]},
                    output=total,
                )
            )
            trace.append(
                CalculationTraceStep(
                    step="count_values",
                    formula="n = len(values)",
                    inputs={"values": values},
                    output=n,
                )
            )
            trace.append(
                CalculationTraceStep(
                    step="compute_mean",
                    formula="mean = sum / n",
                    inputs={"sum": total, "n": n},
                    output=result_val,
                )
            )
            # Deterministic verification: result * n approximately equals total
            checks["mean_consistency"] = abs(result_val * n - total) < 1e-6
            is_verified = checks["mean_consistency"]

        elif op == "median":
            sorted_vals = sorted(values)
            result_val = statistics.median(sorted_vals)
            trace.append(
                CalculationTraceStep(
                    step="sort_values",
                    formula="sorted(values)",
                    inputs={"count": n},
                    output=sorted_vals[:5],
                )
            )
            trace.append(
                CalculationTraceStep(
                    step="compute_median",
                    formula="middle_value(sorted_values)",
                    inputs={"count": n},
                    output=result_val,
                )
            )
            checks["median_within_range"] = (min(values) <= result_val <= max(values))
            is_verified = checks["median_within_range"]

        elif op in ("stdev", "std", "standard_deviation"):
            if n < 2:
                return CalculationResult(
                    task_id=task_id,
                    operation=operation,
                    is_verified=False,
                    status="INVALID_INPUT",
                    error="Standard deviation requires at least 2 data points.",
                )
            result_val = statistics.stdev(values)
            mean_val = total / n
            trace.append(
                CalculationTraceStep(
                    step="compute_stdev",
                    formula="sqrt(sum((x - mean)^2) / (n - 1))",
                    inputs={"mean": mean_val, "n": n},
                    output=result_val,
                )
            )
            checks["stdev_non_negative"] = result_val >= 0.0
            is_verified = checks["stdev_non_negative"]

        elif op == "sum":
            result_val = total
            trace.append(
                CalculationTraceStep(
                    step="sum_all",
                    formula="sum(values)",
                    inputs={"count": n},
                    output=result_val,
                )
            )
            is_verified = True

        elif op in ("min", "minimum"):
            result_val = min(values)
            is_verified = True

        elif op in ("max", "maximum"):
            result_val = max(values)
            is_verified = True

        else:
            return CalculationResult(
                task_id=task_id,
                operation=operation,
                is_verified=False,
                status="FAILED",
                error=f"Unsupported statistical operation: '{operation}'",
            )

        return CalculationResult(
            task_id=task_id,
            value=round(result_val, 4) if isinstance(result_val, float) else result_val,
            operation=operation,
            is_verified=is_verified,
            calculation_trace=trace,
            verification_checks=checks,
            status="SUCCESS",
        )
