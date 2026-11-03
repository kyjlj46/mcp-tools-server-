"""기본 도구 구현 - 현재 시각, 계산기."""

import ast
import math
import operator
import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .web import ToolInputError

WEEKDAYS = "월화수목금토일"


def current_time(timezone: str = "Asia/Seoul") -> str:
    try:
        now = datetime.now(ZoneInfo(timezone))
    except (ZoneInfoNotFoundError, ValueError):
        raise ToolInputError(f"알 수 없는 시간대입니다: {timezone} (예: Asia/Seoul, UTC, America/New_York)") from None
    return (f"{now:%Y-%m-%d %H:%M:%S} ({WEEKDAYS[now.weekday()]}요일) {timezone} UTC{now:%z}\n"
            f"ISO: {now.isoformat(timespec='seconds')}")


# ── 계산기: eval 대신 AST를 직접 계산해 임의 코드 실행을 막는다 ──────────

_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {name: getattr(math, name) for name in (
    "sqrt", "log", "log10", "log2", "exp", "sin", "cos", "tan", "asin", "acos", "atan",
    "floor", "ceil", "factorial", "radians", "degrees", "gcd", "hypot")}
_FUNCS.update(abs=abs, round=round, min=min, max=max)
_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _eval(node: ast.AST) -> float:
    match node:
        case ast.Constant(value=v) if isinstance(v, (int, float)) and not isinstance(v, bool):
            return v
        case ast.Name(id=name) if name in _CONSTS:
            return _CONSTS[name]
        case ast.BinOp(left=l, op=op, right=r) if type(op) in _BINOPS:
            left, right = _eval(l), _eval(r)
            if isinstance(op, ast.Pow) and abs(right) > 1000:
                raise ToolInputError("지수가 너무 큽니다.")
            return _BINOPS[type(op)](left, right)
        case ast.UnaryOp(op=op, operand=x) if type(op) in _UNARY:
            return _UNARY[type(op)](_eval(x))
        case ast.Call(func=ast.Name(id=name), args=args, keywords=[]) if name in _FUNCS:
            values = [_eval(a) for a in args]
            if name == "factorial" and values and values[0] > 1000:
                raise ToolInputError("factorial 인자가 너무 큽니다.")
            return _FUNCS[name](*values)
    raise ToolInputError(f"지원하지 않는 식입니다: {ast.unparse(node)}")


def calculate(expression: str) -> str:
    expr = expression.strip().replace("^", "**").replace("×", "*").replace("÷", "/")
    expr = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", expr)  # 천 단위 쉼표(1,234)만 제거, 함수 인자 쉼표는 유지
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        raise ToolInputError(f"수식을 해석할 수 없습니다: {expression}") from None
    try:
        result = _eval(tree.body)
    except ZeroDivisionError:
        raise ToolInputError("0으로 나눌 수 없습니다.") from None
    if isinstance(result, float) and result.is_integer() and abs(result) < 1e15:
        result = int(result)
    return f"{expression.strip()} = {result}"
