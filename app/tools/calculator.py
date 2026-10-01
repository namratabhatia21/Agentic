import ast
import math
import operator

from pydantic import BaseModel, Field

from app.tools.base import Tool, ToolContext, ToolError

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {
    name: getattr(math, name)
    for name in (
        "sqrt",
        "log",
        "log10",
        "log2",
        "exp",
        "sin",
        "cos",
        "tan",
        "asin",
        "acos",
        "atan",
        "floor",
        "ceil",
        "factorial",
        "fabs",
    )
} | {"abs": abs, "round": round, "min": min, "max": max}
_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def safe_eval(expression: str) -> float | int:
    """Evaluate an arithmetic expression without exec/eval."""

    def ev(node: ast.AST):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                raise ToolError("Exponent too large")
            return _BIN_OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](ev(node.operand))
        if isinstance(node, ast.Name) and node.id in _CONSTS:
            return _CONSTS[node.id]
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _FUNCS
            and not node.keywords
        ):
            return _FUNCS[node.func.id](*[ev(a) for a in node.args])
        raise ToolError(f"Unsupported expression element: {ast.dump(node)[:80]}")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ToolError(f"Syntax error: {e.msg}") from e
    try:
        return ev(tree)
    except (ZeroDivisionError, ValueError, OverflowError) as e:
        raise ToolError(f"Math error: {e}") from e


class CalculatorInput(BaseModel):
    expression: str = Field(
        description="Arithmetic expression, e.g. '(3.5 * 12) / sqrt(2)'. Supports + - * / // % "
        "**, math functions (sqrt, log, exp, sin, ...) and constants pi, e, tau.",
        max_length=500,
    )


async def _calculate(inp: CalculatorInput, ctx: ToolContext) -> str:
    return str(safe_eval(inp.expression))


calculator = Tool(
    name="calculator",
    description="Evaluate an arithmetic expression exactly. Use for any non-trivial math "
    "instead of computing in your head.",
    input_model=CalculatorInput,
    handler=_calculate,
)
