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
import functools
import math
import operator
import random
import re


def _is_list(v):
    return isinstance(v, (list, tuple))


def _is_matrix(v):
    return _is_list(v) and len(v) > 0 and all(_is_list(r) for r in v)


def _elementwise(op, a, b):
    """OpenSCAD + and -: numbers, or vectors of the same shape element by
    element (the shorter length wins, as OpenSCAD truncates)."""
    la, lb = _is_list(a), _is_list(b)
    if la and lb:
        return [_elementwise(op, x, y) for x, y in zip(a, b)]
    if la or lb:
        return None                                  # undef
    if a is None or b is None or isinstance(a, str) or isinstance(b, str):
        return None
    return op(a, b)


def _mul(a, b):
    """OpenSCAD *: scalar x scalar, scalar x vector, dot product,
    matrix x vector, vector x matrix and matrix x matrix."""
    la, lb = _is_list(a), _is_list(b)
    if not la and not lb:
        if a is None or b is None or isinstance(a, str) or isinstance(b, str):
            return None
        return a * b
    if la and not lb:
        return [_mul(x, b) for x in a]
    if lb and not la:
        return [_mul(a, y) for y in b]
    ma, mb = _is_matrix(a), _is_matrix(b)
    if not ma and not mb:                           # dot product
        if len(a) != len(b):
            return None
        return sum(x * y for x, y in zip(a, b))
    if ma and not mb:                               # matrix * column
        return [sum(x * y for x, y in zip(row, b)) for row in a]
    if mb and not ma:                               # row * matrix
        cols = len(b[0])
        return [sum(a[i] * b[i][j] for i in range(min(len(a), len(b))))
                for j in range(cols)]
    cols = len(b[0])
    return [[sum(row[k] * b[k][j] for k in range(min(len(row), len(b))))
             for j in range(cols)] for row in a]


def _div(a, b):
    if _is_list(a) and not _is_list(b):
        return [_div(x, b) for x in a]
    if _is_list(a) or _is_list(b) or a is None or b is None:
        return None
    if b == 0:
        return math.nan if a == 0 else (math.inf if a > 0 else -math.inf)
    return a / b


def _mod(a, b):
    if _is_list(a) or _is_list(b) or a is None or b is None:
        return None
    if b == 0:
        return math.nan
    return math.fmod(a, b)                    # the sign of the dividend


def _pow(a, b):
    if _is_list(a) or _is_list(b) or a is None or b is None:
        return None
    try:
        return math.pow(a, b)
    except (ValueError, OverflowError):
        return math.nan


_BINOPS = {
    ast.Add: lambda a, b: _elementwise(operator.add, a, b),
    ast.Sub: lambda a, b: _elementwise(operator.sub, a, b),
    ast.Mult: _mul,
    ast.Div: _div,
    ast.Mod: _mod,
    ast.Pow: _pow,
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
    "pow": _pow,
    "exp": math.exp,
    "ln": math.log,
    "log": lambda a, b=None: (math.log10(a) if b is None
                              else math.log(b) / math.log(a)),
    "min": lambda *a: min(a[0]) if len(a) == 1 and _is_list(a[0]) else min(a),
    "max": lambda *a: max(a[0]) if len(a) == 1 and _is_list(a[0]) else max(a),
    "floor": math.floor,
    "ceil": math.ceil,
    # OpenSCAD rounds halves AWAY from zero; Python's round() goes to
    # the even neighbour, so round(2.5) was 2 in the preview and 3 in
    # the exact render
    "round": lambda a: int(math.copysign(math.floor(abs(a) + 0.5), a)),
    "sign": lambda a: (a > 0) - (a < 0),
    "norm": lambda *a: math.sqrt(sum(v * v for v in (
        a[0] if len(a) == 1 and _is_list(a[0]) else a))),
    "len": lambda a: len(a) if isinstance(a, (list, tuple, str)) else None,
    "concat": lambda *a: [x for arg in a
                          for x in (arg if isinstance(arg, (list, tuple))
                                    else [arg])],
    "__range": lambda a, s, b: _range_list(a, s, b),
}

CONSTANTS = {"PI": math.pi, "undef": None, "true": True, "false": False,
             "INF": math.inf, "NAN": math.nan}

#: special variables' values when the document does not set them —
#: OpenSCAD's defaults ($t is the animation time, 0 when not animating)
SPECIAL_DEFAULTS = {"$fn": 0, "$fa": 12, "$fs": 2, "$t": 0,
                    "$preview": True, "$vpr": [55, 0, 25],
                    "$vpt": [0, 0, 0], "$vpd": 140, "$vpf": 22.5,
                    "$children": 0, "$parent_modules": 0}


def _str_value(v, top=True):
    """OpenSCAD's str() formatting of one value."""
    if v is None:
        return "undef"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return v if top else '"' + v.replace('"', '\\"') + '"'
    if isinstance(v, (int, float)):
        if isinstance(v, float) and math.isnan(v):
            return "nan"
        if isinstance(v, float) and math.isinf(v):
            return "inf" if v > 0 else "-inf"
        if float(v) == int(v) and abs(v) < 1e15:
            return str(int(v))
        return "%g" % v
    if _is_list(v):
        return "[" + ", ".join(_str_value(x, False) for x in v) + "]"
    if callable(v):
        return "function"
    return str(v)


def _lookup(key, table):
    """Linear interpolation in a [[key, value], ...] table, clamped at
    both ends (OpenSCAD's lookup)."""
    rows = sorted((r for r in table if _is_list(r) and len(r) >= 2),
                  key=lambda r: r[0])
    if not rows:
        return None
    if key <= rows[0][0]:
        return rows[0][1]
    if key >= rows[-1][0]:
        return rows[-1][1]
    for (k0, v0), (k1, v1) in zip(((r[0], r[1]) for r in rows),
                                  ((r[0], r[1]) for r in rows[1:])):
        if k0 <= key <= k1:
            if k1 == k0:
                return v1
            return v0 + (v1 - v0) * (key - k0) / (k1 - k0)
    return rows[-1][1]


def _rands(lo, hi, count, seed=None):
    """rands(min, max, count[, seed]). Unseeded calls are seeded from
    their own arguments: OpenSCAD draws new numbers every render, but a
    preview that changed on every redraw would flicker."""
    rng = random.Random(seed if seed is not None else f"{lo}:{hi}:{count}")
    return [rng.uniform(lo, hi) for _ in range(max(int(count), 0))]


def _cross(a, b):
    if len(a) == 2 and len(b) == 2:
        return a[0] * b[1] - a[1] * b[0]
    if len(a) != 3 or len(b) != 3:
        return None
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def _chr(*args):
    out = []
    for a in args:
        for code in (a if _is_list(a) else [a]):
            try:
                out.append(chr(int(code)))
            except (TypeError, ValueError, OverflowError):
                pass
    return "".join(out)


def _search(match, data, num_returns=1, index_col=0):
    """OpenSCAD's search(): the index(es) of *match* in a string or in
    a vector (column *index_col* of each row when the rows are lists)."""
    def element(item):
        if _is_list(item):
            return item[index_col] if index_col < len(item) else None
        return item

    def hits(value):
        found = [i for i, item in enumerate(data) if element(item) == value]
        return found if num_returns == 0 else found[:int(num_returns)]
    if isinstance(match, (int, float)) and not isinstance(match, bool):
        return hits(match)
    items = list(match) if isinstance(match, str) else list(match or [])
    out = []
    for value in items:
        found = hits(value)
        if num_returns == 1:
            out.extend(found)
        else:
            out.append(found)
    return out


def _assert(condition, message=None):
    if not condition:
        raise ExprError(f"assertion failed{': ' + str(message) if message else ''}")
    return True


FUNCTIONS.update({
    "lookup": _lookup,
    "rands": _rands,
    "str": lambda *a: "".join(_str_value(v) for v in a),
    "chr": _chr,
    "ord": lambda s: ord(s) if isinstance(s, str) and len(s) == 1 else None,
    "cross": _cross,
    "search": _search,
    "is_undef": lambda v: v is None,
    "is_bool": lambda v: isinstance(v, bool),
    "is_num": lambda v: (isinstance(v, (int, float)) and not isinstance(v, bool)
                         and not math.isnan(v)),
    "is_string": lambda v: isinstance(v, str),
    "is_list": _is_list,
    "is_function": callable,
    "is_object": lambda v: False,
    "version": lambda: [2021, 1, 0],
    "version_num": lambda: 20210100,
    "__assert": _assert,
})

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


_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


def _unescape(body):
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt in _ESCAPES:
                out.append(_ESCAPES[nxt])
                i += 2
                continue
            if nxt == "x" and i + 3 < len(body) + 1:
                try:
                    out.append(chr(int(body[i + 2:i + 4], 16)))
                    i += 4
                    continue
                except ValueError:
                    pass
            if nxt in "uU":
                width = 4 if nxt == "u" else 6
                try:
                    out.append(chr(int(body[i + 2:i + 2 + width], 16)))
                    i += 2 + width
                    continue
                except ValueError:
                    pass
        out.append(c)
        i += 1
    return "".join(out)


def _mask_strings(text):
    """Swap every "string" for a placeholder name, so the syntax
    rewrites below (^, !, :, ?) never touch the inside of a string."""
    strings = []

    def swap(match):
        strings.append(_unescape(match.group(1)))
        return f" __S{len(strings) - 1}__ "
    return _STRING.sub(swap, text), strings


def _prefix_end(s, start):
    """Where the body of a `let(...)` / `assert(...)` / `echo(...)` /
    `function(...)` prefix starting at *start* ends: an unmatched
    closer, a comma at its own depth, or a ':' no '?' of its own
    claims."""
    depth, pending = 0, 0
    for i in range(start, len(s)):
        c = s[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                return i
            depth -= 1
        elif depth == 0:
            if c in ",;":
                return i
            if c == "?":
                pending += 1
            elif c == ":":
                if pending == 0:
                    return i
                pending -= 1
    return len(s)


_PREFIX = re.compile(r"(?<![\w.])(let|assert|echo|function)\s*\(")


def _translate_prefixes(s):
    """Expression-level `let (a = x) body`, `assert (c, m) body`,
    `echo (...) body` and function literals `function (x) body` ->
    Python the AST can evaluate."""
    match = _PREFIX.search(s)
    if match is None:
        return s
    word = match.group(1)
    inner, _ = _read_paren(s[match.end() - 1:])
    body_start = match.end() - 1 + len(inner) + 2
    body_end = _prefix_end(s, body_start)
    body = _translate_prefixes(s[body_start:body_end]).strip() or "None"
    inner = _translate_prefixes(inner)
    if word == "let":
        clauses = []
        for bind in _split_top(inner, ","):
            eq = _find_top(bind, "=")
            if eq < 0:
                continue
            clauses.append(f"for {bind[:eq].strip()} in [({bind[eq + 1:]})]")
        replacement = f"([({body}) {' '.join(clauses)}][0])" if clauses \
            else f"({body})"
    elif word == "assert":
        replacement = f"(({body}) if __assert({inner}) else None)"
    elif word == "echo":
        replacement = f"({body})"
    else:
        replacement = f"(lambda {inner}: ({body}))"
    return (s[:match.start()] + replacement
            + _translate_prefixes(s[body_end:]))


@functools.lru_cache(maxsize=8192)
def _compile(text):
    """The parsed AST of one expression string, cached: the preview
    evaluates the same parameters on every redraw."""
    masked, strings = _mask_strings(text)
    # OpenSCAD expressions may span several lines; collapse whitespace so
    # a newline mid-expression does not end it in Python's eval mode.
    masked = re.sub(r"\s+", " ", masked)
    # special variables ($fn, $t) are not Python names
    masked = re.sub(r"\$([A-Za-z_]\w*)", r"__D_\1", masked)
    # OpenSCAD uses ^ for power; ranges, comprehensions and ?: aren't
    # Python, so rewrite them before parsing.
    masked = masked.replace("^", "**")
    masked = _translate_logical(masked)
    masked = _translate_listcomp(_expand_ranges(masked))
    masked = _translate_prefixes(masked)
    masked = _translate_ternary(masked).strip()
    for i, value in enumerate(strings):
        masked = masked.replace(f"__S{i}__", repr(value))
    return ast.parse(masked, mode="eval").body


def evaluate(expression, env: dict = None):
    """Evaluate *expression* (number or OpenSCAD-ish string) with the
    variables in *env*. Raises ExprError on failure."""
    if isinstance(expression, bool) or expression is None:
        return expression
    if isinstance(expression, (int, float)):
        return expression
    text = str(expression).strip()
    try:
        tree = _compile(text)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise ExprError(f"bad expression: {expression!r}") from exc
    try:
        return _eval(tree, env or {})
    except (ZeroDivisionError, OverflowError, RecursionError) as exc:
        raise ExprError(f"{exc} in {expression!r}") from exc


def _eval(node, env):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, bool, str)):
            return node.value
        if node.value is None:
            return None
        raise ExprError(f"unsupported constant: {node.value!r}")
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        if node.id in CONSTANTS:
            return CONSTANTS[node.id]
        if node.id.startswith("__D_"):
            name = "$" + node.id[4:]
            return env.get(name, SPECIAL_DEFAULTS.get(name))
        if node.id in FUNCTIONS:
            return FUNCTIONS[node.id]             # a function as a value
        raise ExprError(f"unknown variable: {node.id}")
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval(node.left, env),
                                      _eval(node.right, env))
    if isinstance(node, ast.UnaryOp):
        value = _eval(node.operand, env)
        if isinstance(node.op, ast.USub):
            return _mul(-1, value)
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
    if isinstance(node, ast.Call):
        args = [_eval(a, env) for a in node.args]
        kwargs = {kw.arg: _eval(kw.value, env) for kw in node.keywords}
        if isinstance(node.func, ast.Name):
            # user-defined functions live in the env as callables;
            # built-ins fall back to the FUNCTIONS table
            func = env.get(node.func.id)
            if not callable(func):
                func = FUNCTIONS.get(node.func.id)
            if func is None:
                raise ExprError(f"unknown function: {node.func.id}")
        else:                              # (function (x) x * 2)(3)
            func = _eval(node.func, env)
            if not callable(func):
                raise ExprError("call of a value that is not a function")
        return func(*args, **kwargs)
    if isinstance(node, ast.Lambda):
        return _closure(node, env)
    raise ExprError(f"unsupported syntax: {ast.dump(node)[:40]}")


def _closure(node, env):
    """A function literal as a callable over the scope it was written
    in (OpenSCAD captures by value, as a copy of the scope does)."""
    names = [a.arg for a in node.args.args]
    defaults = node.args.defaults
    first_default = len(names) - len(defaults)
    scope = dict(env)

    def call(*args, **kwargs):
        local = dict(scope)
        for i, name in enumerate(names):
            if i < len(args):
                local[name] = args[i]
            elif name in kwargs:
                local[name] = kwargs[name]
            elif i >= first_default:
                local[name] = _eval(defaults[i - first_default], local)
            else:
                local[name] = None                # undef, as OpenSCAD
        return _eval(node.body, local)
    return call


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
    except (ExprError, TypeError, ValueError, IndexError, KeyError):
        return default
