"""Safe evaluation of OpenSCAD-style expressions.

Numeric parameters may hold expression strings ("i * 10 + 2") instead
of plain numbers, so objects inside `for` loops can depend on the loop
variable. This module evaluates such expressions with OpenSCAD
semantics — trigonometry in **degrees** — using a whitelisted AST, so
no arbitrary Python can run.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import ast
import math
import operator
import re

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
}

_CMPOPS = {
    ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
}

#: OpenSCAD-compatible functions (trig in degrees).
FUNCTIONS = {
    "sin": lambda a: math.sin(math.radians(a)),
    "cos": lambda a: math.cos(math.radians(a)),
    "tan": lambda a: math.tan(math.radians(a)),
    "asin": lambda a: math.degrees(math.asin(a)),
    "acos": lambda a: math.degrees(math.acos(a)),
    "atan": lambda a: math.degrees(math.atan(a)),
    "atan2": lambda a, b: math.degrees(math.atan2(a, b)),
    "sqrt": math.sqrt,
    "abs": abs,
    "pow": math.pow,
    "exp": math.exp,
    "ln": math.log,
    "log": math.log10,
    "min": min,
    "max": max,
    "floor": math.floor,
    "ceil": math.ceil,
    "round": round,
    "sign": lambda a: (a > 0) - (a < 0),
    "norm": lambda *a: math.sqrt(sum(v * v for v in a)),
    "len": len,
    "__range": lambda a, s, b: _range_list(a, s, b),
}

CONSTANTS = {"PI": math.pi, "undef": None, "true": True, "false": False}

_MAX_RANGE = 100000


def _range_list(start, step, end):
    """OpenSCAD range [start : step : end] as a concrete list."""
    if step == 0:
        return [start]
    out, v, n = [], start, 0
    while (step > 0 and v <= end + 1e-9) or (step < 0 and v >= end - 1e-9):
        out.append(v)
        v += step
        n += 1
        if n >= _MAX_RANGE:
            break
    return out


class ExprError(ValueError):
    """Raised when an expression cannot be evaluated."""


def _split_top(text, sep):
    """Split *text* on *sep* only at bracket-depth 0."""
    parts, depth, start = [], 0, 0
    for i, c in enumerate(text):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts


def _find_top(text, ch):
    depth = 0
    for i, c in enumerate(text):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == ch and depth == 0:
            return i
    return -1


def _expand_ranges(s):
    """Rewrite OpenSCAD range literals `[a:b]` / `[a:s:b]` as
    `__range(a,1,b)` / `__range(a,s,b)` so the AST can evaluate them."""
    out, i, n = [], 0, len(s)
    while i < n:
        if s[i] != "[":
            out.append(s[i])
            i += 1
            continue
        depth, j = 0, i
        while j < n:
            if s[j] == "[":
                depth += 1
            elif s[j] == "]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        inner = s[i + 1:j]
        parts = _split_top(inner, ":")
        if len(parts) == 2:
            out.append("__range(%s,1,%s)" % (_expand_ranges(parts[0]),
                                             _expand_ranges(parts[1])))
        elif len(parts) == 3:
            out.append("__range(%s,%s,%s)" % tuple(
                _expand_ranges(p) for p in parts))
        else:                                   # a plain list / subscript
            out.append("[" + _expand_ranges(inner) + "]")
        i = j + 1
    return "".join(out)


def _translate_logical(s):
    """OpenSCAD boolean operators -> Python: `&&`->`and`, `||`->`or`,
    and a prefix `!` (but not `!=`) -> `not`."""
    s = s.replace("&&", " and ").replace("||", " or ")
    return re.sub(r"!(?!=)", " not ", s)


def _translate_groups(s):
    """Translate ternaries nested inside top-level (...) / [...] groups."""
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in "([{":
            depth, j = 0, i
            while j < n:
                if s[j] in "([{":
                    depth += 1
                elif s[j] in ")]}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            out.append(c + _translate_ternary(s[i + 1:j]) + s[j])
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _translate_ternary(s):
    """OpenSCAD `cond ? a : b` -> Python `(a) if (cond) else (b)`,
    recursing into parenthesised sub-expressions."""
    q = _find_top(s, "?")
    if q < 0:
        return _translate_groups(s)
    cond, rest = s[:q], s[q + 1:]
    c = _find_top(rest, ":")
    if c < 0:
        return _translate_groups(s)
    return "(({0}) if ({1}) else ({2}))".format(
        _translate_ternary(rest[:c]), _translate_ternary(cond),
        _translate_ternary(rest[c + 1:]))


def evaluate(expression, env: dict = None):
    """Evaluate *expression* (number or OpenSCAD-ish string) with the
    variables in *env*. Raises ExprError on failure."""
    if isinstance(expression, bool) or expression is None:
        return expression
    if isinstance(expression, (int, float)):
        return expression
    text = str(expression).strip()
    # OpenSCAD uses ^ for power; ranges and ?: aren't Python, so rewrite.
    text = text.replace("^", "**")
    text = _translate_logical(text)
    text = _translate_ternary(_expand_ranges(text)).strip()
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ExprError(f"bad expression: {expression!r}") from exc
    return _eval(tree.body, env or {})


def _eval(node, env):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, bool)):
            return node.value
        raise ExprError(f"unsupported constant: {node.value!r}")
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        if node.id in CONSTANTS:
            return CONSTANTS[node.id]
        raise ExprError(f"unknown variable: {node.id}")
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval(node.left, env),
                                      _eval(node.right, env))
    if isinstance(node, ast.UnaryOp):
        value = _eval(node.operand, env)
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return +value
        if isinstance(node.op, ast.Not):
            return not value
        raise ExprError("unsupported unary operator")
    if isinstance(node, ast.BoolOp):
        values = [_eval(v, env) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        return any(values)
    if isinstance(node, ast.Compare):
        left = _eval(node.left, env)
        for op, right_node in zip(node.ops, node.comparators):
            if type(op) not in _CMPOPS:
                raise ExprError("unsupported comparison")
            right = _eval(right_node, env)
            if not _CMPOPS[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        return _eval(node.body, env) if _eval(node.test, env) \
            else _eval(node.orelse, env)
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval(e, env) for e in node.elts]
    if isinstance(node, ast.Attribute):
        # OpenSCAD vector swizzle: v.x / v.y / v.z -> v[0] / v[1] / v[2].
        # A scalar reads as [s, s, s], so `cube(size)` works whether the
        # variable holds a number or a vector.
        target = _eval(node.value, env)
        idx = {"x": 0, "y": 1, "z": 2}.get(node.attr)
        if idx is None:
            raise ExprError(f"bad vector accessor .{node.attr}")
        if not isinstance(target, (list, tuple)):
            return target
        if idx >= len(target):
            raise ExprError(f"vector too short for .{node.attr}")
        return target[idx]
    if isinstance(node, ast.Subscript):
        target = _eval(node.value, env)
        index = node.slice.value if isinstance(node.slice, ast.Index) \
            else node.slice                 # py3.9+: slice is the expr
        try:
            return target[int(_eval(index, env))]
        except (TypeError, IndexError, ValueError) as exc:
            raise ExprError(f"bad index into {target!r}") from exc
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        func = FUNCTIONS.get(node.func.id)
        if func is None:
            raise ExprError(f"unknown function: {node.func.id}")
        return func(*[_eval(a, env) for a in node.args])
    raise ExprError(f"unsupported syntax: {ast.dump(node)[:40]}")


def resolve(value, env: dict = None, default: float = 0.0) -> float:
    """Best-effort numeric value: evaluate expressions, fall back to
    *default* when a variable is unknown (e.g. loop var outside its
    loop, previewing at design time)."""
    try:
        result = evaluate(value, env)
        return float(result) if result is not None else default
    except (ExprError, TypeError, ValueError):
        return default
