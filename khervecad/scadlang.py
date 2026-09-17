"""OpenSCAD language statements that are not shapes: resize, multmatrix,
render, intersection_for, let, echo and assert.

KherveCAD shows as a tree what OpenSCAD writes as code, and reads code
back into that tree. These statements used to be skipped on import, so
a file that sized a part with ``resize()``, placed it with a
``multmatrix()`` (every .csg file does) or bound helpers with ``let()``
lost that geometry. Each is now a node:

- **resize** — scales its children to an absolute size; 0 keeps an
  axis, or with *auto* follows the others (``resize([40, 0, 0], auto =
  true)`` keeps the proportions);
- **multmatrix** — an affine 4x4 (or 3x4) matrix, the general transform
  every translate / rotate / scale / mirror is a case of;
- **render** — asks OpenSCAD to compute its children as a mesh (a
  preview hint, ``convexity`` included); geometry is unchanged;
- **intersection_for** — a for loop whose iterations are intersected
  instead of unioned;
- **let** — binds names for its children (``let (r = d / 2) { ... }``);
- **echo** — prints to OpenSCAD's console; shown as a leaf in the tree;
- **assert** — stops the program when a condition is false; the node
  turns red with the message.

Unlike the ``kcad_*`` nodes these compile to OpenSCAD's own statements,
so no helper module is emitted and any OpenSCAD reads the program.
Registered from organic.py; no package imports at module level.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import re

OPERATION = "op"
CONTROL = "ctl"

_IDENTITY = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
             [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]

NODE_TYPES = {
    "resize": dict(
        label="Resize (absolute size)", category=OPERATION,
        icon="mdi.resize",
        params=dict(x=0.0, y=0.0, z=0.0, auto_x=False, auto_y=False,
                    auto_z=False),
        schema=[("x", "New size X (0 = keep)", "float", 0.0, 1e6),
                ("y", "New size Y (0 = keep)", "float", 0.0, 1e6),
                ("z", "New size Z (0 = keep)", "float", 0.0, 1e6),
                ("auto_x", "Auto X (follow the others)", "bool", None, None),
                ("auto_y", "Auto Y (follow the others)", "bool", None, None),
                ("auto_z", "Auto Z (follow the others)", "bool", None,
                 None)]),
    "multmatrix": dict(
        label="Matrix transform (multmatrix)", category=OPERATION,
        icon="mdi.matrix",
        params=dict(matrix=[list(r) for r in _IDENTITY]),
        schema=[("matrix", "Matrix rows (4 x 4; last row 0 0 0 1)",
                 "rows", ["c0", "c1", "c2", "c3 (move)"], None)]),
    "render": dict(
        label="Render (cache as mesh)", category=OPERATION,
        icon="mdi.cube-scan",
        params=dict(convexity=1),
        schema=[("convexity", "Convexity", "int", 1, 100)]),
    "intersection_for": dict(
        label="Intersection for", category=CONTROL,
        icon="mdi.set-center",
        params=dict(variable="i", start=0.0, end=2.0, step=1.0, values=""),
        schema=[("variable", "Variable", "str", None, None),
                ("start", "From", "float", -1e6, 1e6),
                ("end", "To", "float", -1e6, 1e6),
                ("step", "Step", "float", -1e6, 1e6),
                ("values", "Values (overrides range)", "str", None, None)]),
    "let": dict(
        label="Let (local variables)", category=CONTROL,
        icon="mdi.code-parentheses",
        params=dict(bindings="r = 5"),
        schema=[("bindings", "Bindings (a = 1, b = a * 2)", "str", None,
                 None)]),
    "echo": dict(
        label="Echo (print)", category=CONTROL, icon="mdi.console-line",
        params=dict(args='"value = ", 1'),
        schema=[("args", "Arguments", "str", None, None)]),
    "assert": dict(
        label="Assert (check)", category=CONTROL,
        icon="mdi.alert-decagram-outline",
        params=dict(condition="true", message=""),
        schema=[("condition", "Condition", "str", None, None),
                ("message", "Message (expression)", "str", None, None)]),
}
TYPES = frozenset(NODE_TYPES)
WRAPPERS = frozenset({"resize", "multmatrix", "render", "intersection_for",
                      "let"})
LEAVES = frozenset({"echo", "assert"})
#: params kept as text by mesh.rp
TEXT_PARAMS = frozenset({"bindings", "args", "message"})
#: nodes the preview draws approximately (the first iteration)
APPROXIMATED = frozenset({"intersection_for"})


def preamble(root) -> list:
    return []                      # OpenSCAD's own statements: no helpers


# ---------------------------------------------------------------- helpers

def split_args(text):
    """*text* split at its top-level commas, brackets and "strings"
    (with their escapes) respected."""
    parts, depth, quote, start, i = [], 0, False, 0, 0
    text = str(text or "")
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == '"':
                quote = False
        elif c == '"':
            quote = True
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append(text[start:i])
            start = i + 1
        i += 1
    parts.append(text[start:])
    return [p.strip() for p in parts if p.strip()]


_NAMED = re.compile(r"^(\$?[A-Za-z_]\w*)\s*=(?!=)\s*(.*)$", re.S)


def _split_bindings(text):
    """``a = 1, b = [1, 2]`` -> [("a", "1"), ("b", "[1, 2]")]."""
    out = []
    for chunk in split_args(text):
        match = _NAMED.match(chunk)
        if match and match.group(2).strip():
            out.append((match.group(1), match.group(2).strip()))
    return out


def scope(node, env):
    """The environment *node*'s children see (a let's bindings, or an
    intersection_for's first value), for the preview and validation."""
    from . import expr
    scoped = dict(env or {})
    if node.type == "let":
        for name, value in _split_bindings(node.params.get("bindings")):
            try:
                scoped[name] = expr.evaluate(value, scoped)
            except expr.ExprError:
                pass
    elif node.type == "intersection_for":
        values = loop_values(node, env)
        var = str(node.params.get("variable", "i")) or "i"
        scoped[var] = values[0] if values else 0.0
    return scoped


def loop_values(node, env):
    """The values an intersection_for iterates (a for loop's rules)."""
    from . import expr
    from .model import MAX_WHILE_ITERATIONS, split_values
    p = node.params
    if str(p.get("values", "")).strip():
        chunks = split_values(str(p["values"]))
        out = []
        for chunk in chunks:
            try:
                value = expr.evaluate(chunk, env)
            except expr.ExprError:
                value = 0.0
            if len(chunks) == 1 and isinstance(value, (list, tuple)):
                out.extend(value)
            else:
                out.append(value)
        return out
    start = expr.resolve(p.get("start", 0.0), env, 0.0)
    end = expr.resolve(p.get("end", 0.0), env, 0.0)
    step = expr.resolve(p.get("step", 1.0), env, 1.0) or 1.0
    values, v = [], start
    while (step > 0 and v <= end + 1e-9) or (step < 0 and v >= end - 1e-9):
        values.append(v)
        v += step
        if len(values) >= MAX_WHILE_ITERATIONS:
            break
    return values


def matrix_of(node, env):
    """A multmatrix node's 4x4 matrix with every cell resolved (a 3x4
    matrix gets the 0 0 0 1 row)."""
    from . import expr
    rows = [list(r) for r in (node.params.get("matrix") or [])
            if isinstance(r, (list, tuple))]
    m = [list(r) for r in _IDENTITY]
    for i, row in enumerate(rows[:4]):
        for j, cell in enumerate(row[:4]):
            m[i][j] = expr.resolve(cell, env, _IDENTITY[i][j])
    return m


def _bbox(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] if len(p) > 2 else 0.0 for p in points]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def resize_factors(node, env, size):
    """Scale per axis that takes a box of *size* to the resize's target,
    OpenSCAD's rules: a set axis is scaled to it; an auto axis left at 0
    takes the largest factor of the set ones; anything else stays."""
    from . import mesh
    p = node.params
    target = [mesh.rv(p.get(k, 0.0), env, 0.0) for k in ("x", "y", "z")]
    auto = [bool(p.get(k, False)) for k in ("auto_x", "auto_y", "auto_z")]
    factors = [1.0, 1.0, 1.0]
    set_factors = []
    for i in range(3):
        if target[i] > 0 and size[i] > 1e-12:
            factors[i] = target[i] / size[i]
            set_factors.append(factors[i])
    if set_factors:
        grow = max(set_factors)
        for i in range(3):
            if auto[i] and target[i] <= 0:
                factors[i] = grow
    return factors


# ---------------------------------------------------------------- codegen

def statement(node, fmt, fn) -> str:
    from .model import scad_str
    p = node.params
    t = node.type
    if t == "resize":
        size = f"[{fmt(p['x'])}, {fmt(p['y'])}, {fmt(p['z'])}]"
        auto = [bool(p.get(k)) for k in ("auto_x", "auto_y", "auto_z")]
        if not any(auto):
            return f"resize({size})"
        flags = ", ".join("true" if a else "false" for a in auto)
        return f"resize({size}, auto = [{flags}])"
    if t == "multmatrix":
        rows = [r for r in (p.get("matrix") or []) if isinstance(r, list)]
        body = ", ".join("[" + ", ".join(fmt(c) for c in r) + "]"
                         for r in rows)
        return f"multmatrix([{body}])"
    if t == "render":
        return f"render(convexity = {fmt(p.get('convexity', 1))})"
    if t == "intersection_for":
        var = str(p.get("variable", "i")) or "i"
        values = str(p.get("values", "")).strip()
        if values:
            return f"intersection_for ({var} = [{values}])"
        return (f"intersection_for ({var} = [{fmt(p['start'])} : "
                f"{fmt(p['step'])} : {fmt(p['end'])}])")
    if t == "let":
        binds = ", ".join(f"{n} = {v}"
                          for n, v in _split_bindings(p.get("bindings")))
        return f"let ({binds})"
    if t == "echo":
        return f"echo({str(p.get('args', '')).strip()})"
    if t == "assert":
        message = str(p.get("message", "")).strip()
        cond = str(p.get("condition", "true")).strip() or "true"
        return f"assert({cond}, {message})" if message \
            else f"assert({cond})"
    raise ValueError(f"not a scadlang type: {t}")   # pragma: no cover


# ----------------------------------------------------------------- import

def _b_resize(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    size = named.get("newsize", positional[0] if positional else [0, 0, 0])
    if not isinstance(size, list):
        size = [size, size, size]
    size = (list(size) + [0.0, 0.0, 0.0])[:3]
    auto = named.get("auto", positional[1] if len(positional) > 1 else False)
    if not isinstance(auto, list):
        auto = [auto, auto, auto]
    auto = (list(auto) + [False, False, False])[:3]
    return CadNode("resize", "Resize", dict(
        x=_num(size[0]), y=_num(size[1]), z=_num(size[2]),
        auto_x=bool(auto[0]), auto_y=bool(auto[1]), auto_z=bool(auto[2])))


def _b_multmatrix(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    m = named.get("m", positional[0] if positional else None)
    if isinstance(m, str):
        from . import expr
        try:
            m = expr.evaluate(m, parser.scope)
        except Exception:
            m = None
    rows = []
    if isinstance(m, list):
        for row in m[:4]:
            if isinstance(row, list):
                rows.append([_num(c) for c in (list(row) + [0.0] * 4)[:4]])
    if not rows:
        parser.warn("multmatrix matrix could not be read — identity used")
        rows = [list(r) for r in _IDENTITY]
    while len(rows) < 4:
        rows.append(list(_IDENTITY[len(rows)]))
    return CadNode("multmatrix", "Matrix", dict(matrix=rows))


def _b_render(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    conv = _num(named.get("convexity", positional[0] if positional else 1),
                1.0)
    return CadNode("render", "Render", dict(
        convexity=conv if isinstance(conv, str) else max(int(conv), 1)))


BUILDERS = {"resize": _b_resize, "multmatrix": _b_multmatrix,
            "render": _b_render}


def raw_arguments(parser):
    """The source text inside a call's parentheses, verbatim — for let /
    echo / assert, whose arguments are expressions to keep as written
    (parsing them would fold ``b = a * 2`` into a number)."""
    open_tok = parser.expect("(")
    depth = 1
    close = open_tok
    while parser.peek() is not None:
        tok = parser.next()
        if tok[1] in "([{":
            depth += 1
        elif tok[1] in ")]}":
            depth -= 1
            if depth == 0:
                close = tok
                break
    return parser.text[open_tok[3]:close[2]].strip()


def parse_statement(parser, word):
    """let / echo / assert / intersection_for statements (scadparse calls
    this for those words). Returns the node, children attached."""
    from .model import CadNode
    from . import expr
    parser.next()                                   # the word
    if word == "intersection_for":
        loop = parser._parse_loop_header()
        var, params = loop
        params["variable"] = var
        params.pop("while", None)
        node = CadNode("intersection_for", f"Intersection for {var}",
                       params)
        parser._children_into(node)
        return node
    args = raw_arguments(parser)
    if word == "let":
        binds = _split_bindings(args)
        node = CadNode("let", "Let", dict(
            bindings=", ".join(f"{n} = {v}" for n, v in binds)))
        saved = parser.scope
        parser.scope = dict(saved)
        for name, value in binds:
            try:
                parser.scope[name] = expr.evaluate(value, parser.scope)
            except Exception:
                pass
        parser._children_into(node)
        parser.scope = saved
        return node
    if word == "echo":
        node = CadNode("echo", "Echo", dict(args=args))
    else:
        parts = split_args(args) or ["true"]
        node = CadNode("assert", "Assert", dict(
            condition=parts[0], message=", ".join(parts[1:])))
    # `assert(c) cube();` — the statement it prefixes follows as a sibling
    if parser.peek() is not None and parser.peek()[1] == ";":
        parser.next()
    return node


STATEMENTS = ("let", "echo", "assert", "intersection_for")


# ------------------------------------------------------------- validation

def check(node, env):
    from . import expr
    p = node.params
    t = node.type
    if t == "let":
        scoped = dict(env or {})
        binds = _split_bindings(p.get("bindings"))
        if not binds:
            return "let: write bindings like  a = 1, b = a * 2"
        for name, value in binds:
            if not re.fullmatch(r"\$?[A-Za-z_]\w*", name):
                return f"let: invalid variable name {name!r}"
            try:
                scoped[name] = expr.evaluate(value, scoped)
            except expr.ExprError as exc:
                return f"let {name}: {exc}"
        return None
    if t == "intersection_for":
        var = str(p.get("variable", "")).strip()
        if not re.fullmatch(r"\$?[A-Za-z_]\w*", var or ""):
            return f"invalid variable name: {var!r}"
        if not loop_values(node, env):
            return "intersection_for: no values to iterate"
        return None
    if t == "multmatrix":
        rows = p.get("matrix") or []
        if not rows or any(not isinstance(r, list) or len(r) < 4
                           for r in rows[:3]):
            return "multmatrix: three or four rows of four numbers"
        m = matrix_of(node, env)
        det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
               - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
               + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
        if abs(det) < 1e-12:
            return "multmatrix: the matrix flattens its children (det 0)"
        return None
    if t == "echo":
        try:
            _echo_text(node, env)
        except expr.ExprError as exc:
            return f"echo: {exc}"
        return None
    if t == "assert":
        try:
            ok = expr.evaluate(str(p.get("condition", "true")) or "true", env)
        except expr.ExprError as exc:
            return f"assert condition: {exc}"
        if not ok:
            message = str(p.get("message", "")).strip()
            if message:
                try:
                    message = expr._str_value(expr.evaluate(message, env))
                except expr.ExprError:
                    pass
            return "assertion failed" + (f": {message}" if message else
                                         f": {p.get('condition')}")
        return None
    if t == "resize":
        from . import mesh
        if all(mesh.rv(p.get(k, 0.0), env, 0.0) <= 0 for k in "xyz"):
            return "resize: set at least one size above 0"
    return None


def _echo_text(node, env):
    """What OpenSCAD would print for an echo: ECHO: a = 1, "text"."""
    from . import expr
    parts = []
    for chunk in split_args(node.params.get("args", "")):
        match = _NAMED.match(chunk)
        if match:
            value = expr.evaluate(match.group(2), env)
            parts.append(f"{match.group(1)} = "
                         f"{expr._str_value(value, False)}")
        else:
            parts.append(expr._str_value(expr.evaluate(chunk, env), False))
    return ", ".join(parts)


def echo_text(node, env=None):
    """ECHO line for the tree tooltip, or the error."""
    from . import expr
    try:
        return "ECHO: " + _echo_text(node, env)
    except expr.ExprError as exc:
        return f"ECHO: ({exc})"


# ----------------------------------------------------------- tessellation

def tess(node, env, color, sel, selected):
    from . import mesh
    t = node.type
    if t in LEAVES:
        return []
    if t == "let":
        return mesh._children_mesh(node, scope(node, env), color, sel,
                                   selected)
    if t == "intersection_for":
        # the intersection of every iteration is the engine's job; the
        # preview shows the first, like a difference shows its first
        # operand
        return mesh._children_mesh(node, scope(node, env), color, sel,
                                   selected)
    kids = mesh._children_mesh(node, env, color, sel, selected)
    if t == "render" or not kids:
        return kids
    if t == "multmatrix":
        return mesh._transform_colored(matrix_of(node, env), kids)
    lo, hi = _bbox([v for tri, _c, _s in kids for v in tri])
    size = [hi[i] - lo[i] for i in range(3)]
    fx, fy, fz = resize_factors(node, env, size)
    # OpenSCAD scales about the origin, not the box
    return mesh._transform_colored(mesh.mat_scale(fx, fy, fz), kids)


def outlines(node, env):
    """2D outlines through these nodes (inside an extrude)."""
    from . import mesh
    t = node.type
    if t in LEAVES:
        return []
    if t in ("let", "intersection_for"):
        return mesh._children_outlines(node, scope(node, env))
    base = mesh._children_outlines(node, env)
    if t == "render" or not base:
        return base
    if t == "multmatrix":
        m = matrix_of(node, env)
        flip = m[0][0] * m[1][1] - m[0][1] * m[1][0] < 0
        out = []
        for o in base:
            pts = [(m[0][0] * x + m[0][1] * y + m[0][3],
                    m[1][0] * x + m[1][1] * y + m[1][3]) for x, y in o]
            out.append(pts[::-1] if flip else pts)
        return out
    pts = [(x, y, 0.0) for o in base for x, y in o]
    lo, hi = _bbox(pts)
    fx, fy, _fz = resize_factors(node, env, [hi[0] - lo[0], hi[1] - lo[1],
                                             0.0])
    return [[(x * fx, y * fy) for x, y in o] for o in base]
