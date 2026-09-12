"""Pattern: linear, polar and grid copies of its children — Blender's
Array modifier, SolidWorks' linear / circular pattern.

A ``pattern`` wraps whatever it holds and places *count* copies of it:

- **linear** — every copy moved on by the step ``(dx, dy, dz)``: a row
  of holes, a straight stair when dz is set too;
- **polar** — copies turned about ``axis`` through the origin. With
  ``angle`` = 360 (or more) the copies are spread evenly at
  ``angle * i / count`` so the last one never lands on the first — a
  bolt circle; below 360 the copies SPAN the angle, ``angle * i /
  (count - 1)``, so the first sits at 0° and the last at ``angle`` — a
  fan of five ribs over 90°. ``dz`` is the rise per copy along the
  axis, so a spring or a spiral stair is one pattern;
- **grid** — ``count_x × count_y × count_z`` copies at the step.

Like the organic nodes (organic.py, which registers this module) it
compiles to ONE call of a ``kcad_pattern`` helper module whose
definition goes at the top of the program — real OpenSCAD with
``children()`` and for loops, nothing baked, so every number may be an
expression or a loop variable, and an assistant can write
``kcad_pattern(kind = "polar", count = 6) { bolt(); }`` directly. The
importer knows the name and rebuilds the same node.

No package imports at module level (see organic.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

OPERATION = "op"

KINDS = ("linear", "polar", "grid")
AXES = ("x", "y", "z")

#: the most copies one pattern may make (model.MAX_WHILE_ITERATIONS)
MAX_COPIES = 1000

NODE_TYPES = {
    "pattern": dict(
        label="Pattern (linear / polar / grid)", category=OPERATION,
        icon="mdi.dots-grid",
        params=dict(kind="linear", count=4, dx=20.0, dy=0.0, dz=0.0,
                    angle=360.0, axis="z", count_x=3, count_y=3,
                    count_z=1),
        schema=[("kind", "Kind", "choice", list(KINDS), None),
                ("count", "Count (linear, polar)", "int", 1, MAX_COPIES),
                ("dx", "Step X (mm)", "float", -1e6, 1e6),
                ("dy", "Step Y (mm)", "float", -1e6, 1e6),
                ("dz", "Step Z / polar rise per copy (mm)", "float",
                 -1e6, 1e6),
                ("angle", "Polar angle° (360 = full circle)", "float",
                 -3600.0, 3600.0),
                ("axis", "Polar axis", "choice", list(AXES), None),
                ("count_x", "Grid count X", "int", 1, MAX_COPIES),
                ("count_y", "Grid count Y", "int", 1, MAX_COPIES),
                ("count_z", "Grid count Z", "int", 1, MAX_COPIES)]),
}
TYPES = frozenset(NODE_TYPES)
WRAPPERS = frozenset(NODE_TYPES)

#: the helper module — the same rules as matrices() below, run by
#: OpenSCAD at render time (keep the two in step)
HELPER = """\
module kcad_pattern(kind = "linear", count = 1, step = [0, 0, 0],
                    angle = 360, axis = "z", rise = 0,
                    counts = [1, 1, 1]) {
    if (kind == "polar") {
        n = max(floor(count + 0.5), 1);
        per = n < 2 ? 0 : abs(angle) >= 360 ? angle / n : angle / (n - 1);
        v = axis == "x" ? [1, 0, 0] : axis == "y" ? [0, 1, 0] : [0, 0, 1];
        for (i = [0 : n - 1])
            translate(v * rise * i) rotate(a = per * i, v = v) children();
    } else if (kind == "grid") {
        for (ix = [0 : max(floor(counts[0] + 0.5), 1) - 1],
             iy = [0 : max(floor(counts[1] + 0.5), 1) - 1],
             iz = [0 : max(floor(counts[2] + 0.5), 1) - 1])
            translate([ix * step[0], iy * step[1], iz * step[2]])
                children();
    } else {
        for (i = [0 : max(floor(count + 0.5), 1) - 1])
            translate(step * i) children();
    }
}"""


def preamble(root) -> list:
    """Helper-module source lines, when the tree holds a pattern."""
    if any(n.type == "pattern" for n in root.walk()):
        return HELPER.split("\n")
    return []


def _whole(value) -> int:
    """OpenSCAD's floor(x + 0.5) — never Python's round-half-even."""
    return int(math.floor(float(value) + 0.5))


# ---------------------------------------------------------------- codegen

def statement(node, fmt, fn) -> str:
    """The node's one statement (head only): the arguments the kind
    uses, so the program reads as what it does."""
    p = node.params
    kind = str(p.get("kind", "linear"))
    if kind == "polar":
        axis = str(p.get("axis", "z"))
        axis = axis if axis in AXES else "z"
        return (f'kcad_pattern(kind = "polar", count = {fmt(p["count"])}, '
                f'angle = {fmt(p["angle"])}, axis = "{axis}", '
                f'rise = {fmt(p["dz"])})')
    step = f'[{fmt(p["dx"])}, {fmt(p["dy"])}, {fmt(p["dz"])}]'
    if kind == "grid":
        return (f'kcad_pattern(kind = "grid", counts = [{fmt(p["count_x"])}, '
                f'{fmt(p["count_y"])}, {fmt(p["count_z"])}], step = {step})')
    return f'kcad_pattern(kind = "linear", count = {fmt(p["count"])}, ' \
           f'step = {step})'


# ----------------------------------------------------------------- import

def _vec3(value, default):
    from .scadparse import _num
    if not isinstance(value, list):
        if value is None:
            return list(default)
        value = [value] * 3
    value = list(value) + list(default[len(value):])
    return [_num(v, d) for v, d in zip(value[:3], default)]


def _count(value, default):
    """A count as the node keeps it: a whole number, or the expression
    string it was written as."""
    from .scadparse import _num
    value = _num(value, default)
    return value if isinstance(value, str) else _whole(value)


def build(parser, positional, named):
    """kcad_pattern(...) -> the pattern node; the children follow in
    the call's block."""
    from .model import CadNode
    from .scadparse import _num
    d = NODE_TYPES["pattern"]["params"]
    kind = str(named.get("kind", positional[0] if positional else "linear"))
    if kind not in KINDS:
        parser.warn(f"unknown pattern kind {kind!r} — kept as linear")
        kind = "linear"
    step = _vec3(named.get("step"), (d["dx"], d["dy"], d["dz"]))
    counts = _vec3(named.get("counts"),
                   (d["count_x"], d["count_y"], d["count_z"]))
    axis = str(named.get("axis", d["axis"]))
    params = dict(
        kind=kind, count=_count(named.get("count", d["count"]), d["count"]),
        dx=step[0], dy=step[1], dz=step[2],
        angle=_num(named.get("angle", d["angle"]), d["angle"]),
        axis=axis if axis in AXES else d["axis"],
        count_x=_count(counts[0], d["count_x"]),
        count_y=_count(counts[1], d["count_y"]),
        count_z=_count(counts[2], d["count_z"]))
    if kind == "polar" and "rise" in named:
        params["dz"] = _num(named["rise"], 0.0)
    if kind == "polar" and "step" not in named:
        params["dx"], params["dy"] = 0.0, 0.0
    return CadNode("pattern", "Pattern", params)


BUILDERS = {"kcad_pattern": build}


# ------------------------------------------------------------- validation

def check(node, env):
    """An error message for a broken pattern, else None."""
    from . import expr
    p = node.params
    kind = str(p.get("kind", "linear"))
    if kind not in KINDS:
        return f"kind must be linear, polar or grid, not {kind!r}"
    if str(p.get("axis", "z")) not in AXES:
        return f"axis must be x, y or z, not {p.get('axis')!r}"

    def whole(key, default):
        value = p.get(key, default)
        if isinstance(value, str):
            value = expr.evaluate(value, env)     # ExprError -> caller
        return _whole(value)
    try:
        if kind == "grid":
            keys = ("count_x", "count_y", "count_z")
            counts = [whole(k, 1) for k in keys]
            for key, n in zip(keys, counts):
                if n < 1:
                    return f"{key} must be at least 1"
            total = counts[0] * counts[1] * counts[2]
        else:
            total = whole("count", 1)
            if total < 1:
                return "count must be at least 1"
        for key in ("dx", "dy", "dz", "angle"):
            value = p.get(key, 0.0)
            if isinstance(value, str):
                expr.evaluate(value, env)
    except expr.ExprError as exc:
        return f"{exc}"
    if total > MAX_COPIES:
        return (f"{total} copies — a pattern is capped at {MAX_COPIES}; "
                "lower the count")
    return None


# ----------------------------------------------------------- tessellation

def matrices(node, env) -> list:
    """The placement matrix of every copy, the first the identity —
    the preview's copy of the helper's rules, capped at MAX_COPIES."""
    from . import mesh
    p = node.params

    def num(key, default=0.0):
        return mesh.rv(p.get(key, default), env, default)

    def whole(key, default=1):
        return max(_whole(mesh.rv(p.get(key, default), env, default)), 1)
    kind = str(p.get("kind", "linear"))
    out = []
    if kind == "polar":
        n = min(whole("count"), MAX_COPIES)
        angle = num("angle", 360.0)
        per = 0.0 if n < 2 else (angle / n if abs(angle) >= 360
                                 else angle / (n - 1))
        rise = num("dz")
        axis = str(p.get("axis", "z"))
        axis = axis if axis in AXES else "z"
        for i in range(n):
            spin = [0.0, 0.0, 0.0]
            spin[AXES.index(axis)] = per * i
            lift = [0.0, 0.0, 0.0]
            lift[AXES.index(axis)] = rise * i
            out.append(mesh.mat_mul(mesh.mat_translate(*lift),
                                    mesh.mat_rotate(*spin)))
        return out
    dx, dy, dz = num("dx"), num("dy"), num("dz")
    if kind == "grid":
        nx, ny, nz = (whole(k) for k in ("count_x", "count_y", "count_z"))
        for ix in range(nx):
            for iy in range(ny):
                for iz in range(nz):
                    if len(out) >= MAX_COPIES:
                        return out
                    out.append(mesh.mat_translate(ix * dx, iy * dy, iz * dz))
        return out
    for i in range(min(whole("count"), MAX_COPIES)):
        out.append(mesh.mat_translate(i * dx, i * dy, i * dz))
    return out


def tess(node, env, color, sel, selected):
    """The children's preview mesh, once per copy (the selection flag
    rides along, so a selected child glows in every copy)."""
    from . import mesh
    kids = mesh._children_mesh(node, env, color, sel, selected)
    if not kids:
        return []
    out = []
    for i, m in enumerate(matrices(node, env)):
        out.extend(kids if i == 0 else mesh._transform_colored(m, kids))
    return out


def outlines(node, env) -> list:
    """The children's 2D outlines, once per copy (a pattern of holes
    inside an extrude): the copy's matrix applied in the plane."""
    from . import mesh
    base = mesh._children_outlines(node, env)
    out = []
    for m in matrices(node, env):
        for outline in base:
            out.append([(m[0][0] * x + m[0][1] * y + m[0][3],
                         m[1][0] * x + m[1][1] * y + m[1][3])
                        for x, y in outline])
    return out
