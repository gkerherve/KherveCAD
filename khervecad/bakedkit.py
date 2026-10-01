"""A kit for BAKED feature nodes — the creature tools (displace,
armature, hair strands, skin, shape keys) and any later node whose
surface is computed in Python and written into its call.

``make(...)`` returns a module-shaped namespace that follows the
feature contract of features.py: NODE_TYPES, LEAVES / WRAPPERS,
preamble, statement, BUILDERS, check and tess. It does what bake.py
does for its own baked wrappers — one table drives the helper, codegen,
importer, validation and cache — without growing bake.py:

* codegen writes ``kcad_<kind>(param = value, ..., points = [...],
  faces = [...]) { children }`` and the helper module draws the
  polyhedron (and, when asked, the children too, like a shrinkwrap's
  target);
* the importer takes the parameters back and ignores the baked arrays:
  the surface is recomputed from the children, so the node round-trips;
* validation refuses a baked node inside a loop or an if (one mesh
  cannot vary per iteration) and a boolean the preview only
  approximates among its children;
* the result is cached by content (the node's dict, the segment count
  and the variables in scope).

Every kit type is in COLORED, so features.tess never serves it from its
by-parameters cache (that cache does not see the children).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

#: content -> (points, faces, triangles), shared by every kit node
_CACHE = {}
CACHE_SIZE = 24


def _literal(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return '"' + value + '"'
    if isinstance(value, list):
        return "[]"
    return repr(value) if isinstance(value, float) else str(value)


def _rows_value(value, fmt, names=frozenset()) -> str:
    """A rows parameter as OpenSCAD: numbers (and expressions) through
    *fmt*, the cells of the *names* columns as quoted strings."""
    from .model import scad_str
    out = []
    for row in value:
        if not isinstance(row, list):
            continue
        cells = []
        for i, v in enumerate(row):
            if i in names:
                cells.append(scad_str(str(v)))
            elif isinstance(v, bool):
                cells.append("true" if v else "false")
            else:
                cells.append(fmt(v))
        out.append("[" + ", ".join(cells) + "]")
    return "[" + ", ".join(out) + "]"


def _unquote(value):
    if isinstance(value, str) and len(value) >= 2 and value[0] == '"' \
            and value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def _parsed(value):
    """A parsed argument back to a parameter: strings unquoted, numbers
    as floats, lists recursively, expressions kept as text."""
    from .scadparse import _num
    if isinstance(value, list):
        return [_parsed(v) for v in value]
    if isinstance(value, str) and value.startswith('"'):
        return _unquote(value)
    return _num(value, value)


def make(kind, label, icon, params, schema, compute, *, leaf=False,
         choices=None, text=(), draws_children=None, check=None,
         helper_body=None, inexact_ok=False, colour=None, names=None):
    """A baked feature node type.

    *params* are the defaults (their types drive the importer), *schema*
    the Properties rows; *compute(node, env)* returns the triangles
    (counter-clockwise, outward) in the node's frame. *choices* maps a
    parameter to its allowed strings, *text* lists parameters kept as
    text in the preview (colours, names). *draws_children(node)* says
    whether the children are drawn as well as the result; *check(node,
    env)* adds validation; *colour(node)* gives the result its own
    colour (else it inherits). *helper_body* replaces the helper's
    drawing (OpenSCAD source using ``points`` and ``faces``). *names*
    maps a rows parameter to the columns that hold names (quoted)."""
    choices = choices or {}
    names = names or {}
    order = list(params)

    def preamble(root) -> list:
        if not any(n.type == kind for n in root.walk()):
            return []
        args = ", ".join(f"{k} = {_literal(params[k])}" for k in order)
        body = helper_body or (
            "    polyhedron(points = points, faces = faces, convexity = 10);"
            + ("\n    if (show_children) children();"
               if draws_children is not None else ""))
        extra = ", show_children = false" if draws_children is not None \
            and helper_body is None else ""
        return (f"module kcad_{kind}({args}{extra}, points = [], "
                f"faces = []) {{\n{body}\n}}").split("\n")

    def baked(node, env):
        from . import document, mesh
        from . import model as model_mod
        fn = mesh._FN_OVERRIDE
        if fn is None:
            fn = model_mod._FN_OVERRIDE
        key = json.dumps([document.node_to_dict(node), fn,
                          sorted((k, repr(v)) for k, v in env.items())],
                         sort_keys=True, default=str)
        hit = _CACHE.get(key)
        if hit is None:
            from . import bake
            saved, saved_detail = mesh._FN_OVERRIDE, mesh._DETAIL
            mesh._set_fn(fn)
            mesh._DETAIL = None
            try:
                tris = compute(node, env) or []
            finally:
                mesh._set_fn(saved)
                mesh._DETAIL = saved_detail
            points, faces = bake.to_polyhedron(tris)
            hit = _CACHE[key] = (points, faces, tris)
            while len(_CACHE) > CACHE_SIZE:
                _CACHE.pop(next(iter(_CACHE)))
        return hit

    def statement(node, fmt, fn) -> str:
        from . import bake
        try:
            points, faces, _tris = baked(node, bake._codegen_env(node))
        except Exception:
            points, faces = [], []            # validation has flagged it
        args = []
        for k in order:
            value = node.params.get(k, params[k])
            if isinstance(params[k], str):
                from .model import scad_str
                args.append(f"{k} = {scad_str(str(value))}")
            elif isinstance(params[k], list):
                args.append(f"{k} = "
                            f"{_rows_value(value or [], fmt, names.get(k, ()))}")
            elif isinstance(value, bool):
                args.append(f"{k} = {'true' if value else 'false'}")
            else:
                args.append(f"{k} = {fmt(value)}")
        if draws_children is not None and helper_body is None:
            args.append("show_children = "
                        + ("true" if draws_children(node) else "false"))
        return (f"kcad_{kind}({', '.join(args)},\n"
                f"    points = {bake._rows_wrapped(points, fmt)},\n"
                f"    faces = {bake._rows_wrapped(faces, fmt)})")

    def build(parser, positional, named):
        from .model import CadNode
        from .scadparse import _num
        out = {}
        for k in order:
            default = params[k]
            value = named.get(k, default)
            if isinstance(default, bool):
                out[k] = value is True or value == "true"
            elif isinstance(default, int):
                try:
                    out[k] = int(_num(value, default))
                except (TypeError, ValueError):
                    out[k] = value if isinstance(value, str) else default
            elif isinstance(default, float):
                out[k] = _num(value, default)
            elif isinstance(default, str):
                text_value = _unquote(value) if isinstance(value, str) \
                    else default
                allowed = choices.get(k)
                out[k] = text_value if allowed is None or \
                    text_value in allowed else default
            elif isinstance(default, list):
                out[k] = _parsed(value) if isinstance(value, list) \
                    else [list(r) if isinstance(r, list) else r
                          for r in default]
            else:
                out[k] = value
        return CadNode(kind, label, out)

    def check_node(node, env):
        from . import bake
        parent = node.parent
        while parent is not None:
            if parent.type in ("for_loop", "while_loop", "if_else"):
                what = parent.type.replace("_", " ").replace(" loop", "")
                return (f"a {label.lower()} is baked into one mesh, so it "
                        f"can't sit inside a {what} — put the {what} "
                        "inside it")
            parent = parent.parent
        if not leaf and not inexact_ok:
            bad = next((n for n in node.walk() if n is not node
                        and n.visible and bake._inexact(n)), None)
            if bad is not None:
                return (f"{label}: it reshapes the preview mesh, which "
                        f"cannot cut {bad.name} ({bad.type}) right — "
                        "work on primitives, blends, extrusions, lofts")
        for k, allowed in choices.items():
            if str(node.params.get(k, params[k])) not in allowed:
                return f"{label}: {k} must be one of {', '.join(allowed)}"
        if not leaf and not node.children:
            return f"{label}: put the part it works on inside it"
        if check is not None:
            return check(node, env)
        return None

    def tess(node, env, color, sel, selected):
        from . import mesh
        try:
            _points, _faces, tris = baked(node, env)
        except Exception:                    # validation has flagged it
            tris = []
        own = colour(node) if colour is not None else None
        out = mesh._emit(tris, own if own is not None else color, selected)
        if draws_children is not None and draws_children(node):
            out.extend(mesh._children_mesh(node, env, color, sel, selected))
        elif sel and not selected:
            out.extend(item for item in mesh._children_mesh(
                node, env, color, sel, selected) if item[2])
        return out

    node_type = dict(label=label, category="3d" if leaf else "operation",
                     icon=icon, params=dict(params), schema=schema)
    types = frozenset({kind})
    return SimpleNamespace(
        NODE_TYPES={kind: node_type}, TYPES=types,
        LEAVES=types if leaf else frozenset(),
        WRAPPERS=frozenset() if leaf else types,
        COLORED=types, TEXT_PARAMS=frozenset(text),
        BUILDERS={f"kcad_{kind}": build},
        preamble=preamble, statement=statement, check=check_node,
        tess=tess, baked=baked)


def source_tris(node, env):
    """The children's preview triangles in the node's frame."""
    from . import mesh
    return [tri for tri, _c, _s in
            mesh._children_mesh(node, env, None, frozenset(), False)]


def num(node, env, key, default=0.0):
    from . import mesh
    return mesh.rv(node.params.get(key, default), env, default)


def rows(node, env, key, width=None):
    """A rows parameter with every numeric cell resolved (strings that
    are not expressions — names — kept)."""
    from . import expr, mesh
    out = []
    for row in node.params.get(key) or []:
        if not isinstance(row, list) or (width and len(row) not in
                                         (width if isinstance(width, tuple)
                                          else (width,))):
            continue
        cells = []
        for v in row:
            if isinstance(v, str):
                try:
                    cells.append(float(expr.evaluate(v, env)))
                except Exception:
                    cells.append(v)
            else:
                cells.append(mesh.rv(v, env, 0.0))
        out.append(cells)
    return out
