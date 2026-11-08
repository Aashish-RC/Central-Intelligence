"""Built-in Safe Mathematical Calculation Tool."""

import ast
import operator
import time
from typing import Any, Dict
from ..base import BaseTool, ToolContext, ToolResult


# Safe mathematical operators mapping
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("Only numeric constants allowed")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type in _SAFE_OPERATORS:
            left = _safe_eval(node.left)
            right = _safe_eval(node.right)
            return _SAFE_OPERATORS[op_type](left, right)
        raise ValueError(f"Unsupported binary operator: {op_type.__name__}")
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in _SAFE_OPERATORS:
            operand = _safe_eval(node.operand)
            return _SAFE_OPERATORS[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
    else:
        raise ValueError(f"Disallowed AST expression: {type(node).__name__}")


class CalculatorTool(BaseTool):
    """Safely evaluates arithmetic expressions using AST parsing."""

    name = "calculator"
    description = "Evaluates basic mathematical expressions (addition, subtraction, multiplication, division, exponentiation)."
    parameters_schema = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Mathematical expression (e.g. '(15 * 4) + 12.5')"}
        },
        "required": ["expression"]
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        start_time = time.perf_counter()
        expr = params.get("expression", "").strip()
        if not expr:
            return ToolResult(
                success=False,
                output=None,
                error="Expression cannot be empty",
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )

        # Strip common natural language prefixes like "calculate", "what is", etc.
        clean_expr = expr
        for prefix in ["calculate", "what is", "compute", "evaluate", "eval", "="]:
            if clean_expr.lower().startswith(prefix):
                clean_expr = clean_expr[len(prefix):].strip()

        try:
            tree = ast.parse(clean_expr, mode="eval")
            result = _safe_eval(tree)
            return ToolResult(
                success=True,
                output=result,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                metadata={"expression": expr}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Calculation error: {str(e)}",
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )
