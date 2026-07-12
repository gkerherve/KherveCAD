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
    # clamp the domain-sensitive functions so float noise (e.g. a range
    # endpoint landing at -1e-16) yields a sane value instead of a
    # "math domain error", matching OpenSCAD's forgiving numerics.
    "asin": lambda a: math.degrees(math.asin(max(-1.0, min(1.0, a)))),
    "acos": lambda a: math.degrees(math.acos(max(-1.0, min(1.0, a)))),
    "atan": lambda a: math.degrees(math.atan(a)),
    "atan2": lambda a, b: math.degrees(math.atan2(a, b)),
    "sqrt": lambda a: math.sqrt(a) if a > 0 else 0.0,
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
    "concat": lambda *a: [x for arg in a
                          for x in (arg if isinstance(arg, (list, tuple))
                                    else [arg])],
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


def _read_paren(s):
    """*s* starts at '('; return (inner, remainder-after-matching-')')."""
    depth, i = 0, 0
    for i, c in enumerate(s):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return s[1:i], s[i + 1:]
    return s[1:], ""


def _word_at(s, word):
    """True if *s* begins with *word* as a whole word (not a prefix of a
    longer identifier)."""
    if not s.startswith(word):
        return False
    tail = s[len(word):].lstrip()
    return tail.startswith("(")


def _comp_to_python(inner):
    """OpenSCAD list comprehension body `for (v = r) [let (..)] [if (c)]
    elt` -> a Python comprehension. `let (a = x)` becomes `for a in [x]`
    so a single machinery covers generators, bindings and filters."""
    clauses, tail = [], inner.strip()
    while True:
        if _word_at(tail, "for"):
            content, tail = _read_paren(tail[3:].lstrip())
            for gen in _split_top(content, ","):
                eq = _find_top(gen, "=")
                clauses.append(f"for {gen[:eq].strip()} in "
                               f"{_translate_listcomp(gen[eq + 1:].strip())}")
        elif _word_at(tail, "let"):
            content, tail = _read_paren(tail[3:].lstrip())
            for bind in _split_top(content, ","):
                eq = _find_top(bind, "=")
                clauses.append(f"for {bind[:eq].strip()} in "
                               f"[{_translate_listcomp(bind[eq + 1:].strip())}]")
        elif _word_at(tail, "if"):
            content, tail = _read_paren(tail[2:].lstrip())
            clauses.append(f"if {_translate_listcomp(content.strip())}")
        else:
            break
        tail = tail.lstrip()
    elt = _translate_listcomp(tail.strip()) or "None"
    return "[" + elt + " " + " ".join(clauses) + "]"


def _translate_listcomp(s):
    """Rewrite OpenSCAD list comprehensions `[for (..) ..]` as Python
    comprehensions, recursing into nested brackets."""
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
        inner = s[i:j][1:] if j < n else s[i + 1:]
        if _word_at(inner.lstrip(), "for"):
            out.append(_comp_to_python(inner))
        else:
            out.append("[" + _translate_listcomp(inner) + "]")
        i = j + 1
    return "".join(out)


def evaluate(expression, env: dict = None):
    """Evaluate *expression* (number or OpenSCAD-ish string) with the
    variables in *env*. Raises ExprError on failure."""
    if isinstance(expression, bool) or expression is None:
        return expression
    if isinstance(expression, (int, float)):
        return expression
    text = str(expression).strip()
    # OpenSCAD expressions may span several lines; collapse whitespace so
    # a newline mid-expression does not end it in Python's eval mode.
    text = re.sub(r"\s+", " ", text)
    # OpenSCAD uses ^ for power; ranges, comprehensions and ?: aren't
    # Python, so rewrite them before parsing.
    text = text.replace("^", "**")
    text = _translate_logical(text)
    text = _translate_listcomp(_expand_ranges(text))
    text = _translate_ternary(text).strip()
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
    if isinstance(node, ast.ListComp):
        return _eval_comp(node.elt, node.generators, 0, env)
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
        args = [_eval(a, env) for a in node.args]
        kwargs = {kw.arg: _eval(kw.value, env) for kw in node.keywords}
        # user-defined functions live in the env as callables; built-ins
        # fall back to the FUNCTIONS table
        func = env.get(node.func.id)
        if not callable(func):
            func = FUNCTIONS.get(node.func.id)
        if func is None:
            raise ExprError(f"unknown function: {node.func.id}")
        return func(*args, **kwargs)
    raise ExprError(f"unsupported syntax: {ast.dump(node)[:40]}")


def _bind_target(target, value, env):
    """Bind a comprehension target (a name or a tuple/list of names)."""
    if isinstance(target, ast.Name):
        env[target.id] = value
    elif isinstance(target, (ast.Tuple, ast.List)):
        for sub, item in zip(target.elts, value):
            _bind_target(sub, item, env)
    else:
        raise ExprError("unsupported comprehension target")


def _eval_comp(elt, generators, gi, env):
    """Evaluate a (possibly multi-generator) list comprehension."""
    if gi == len(generators):
        return [_eval(elt, env)]
    gen = generators[gi]
    iterable = _eval(gen.iter, env)
    out = []
    for item in iterable:
        scope = dict(env)
        _bind_target(gen.target, item, scope)
        if all(_eval(cond, scope) for cond in gen.ifs):
            out.extend(_eval_comp(elt, generators, gi + 1, scope))
    return out


def resolve(value, env: dict = None, default: float = 0.0) -> float:
    """Best-effort numeric value: evaluate expressions, fall back to
    *default* when a variable is unknown (e.g. loop var outside its
    loop, previewing at design time)."""
    try:
        result = evaluate(value, env)
        return float(result) if result is not None else default
    except (ExprError, TypeError, ValueError):
        return default
