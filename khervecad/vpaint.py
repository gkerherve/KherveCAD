"""The `vertex_paint` wrapper (Qt-free): colour brushed onto a part by
hand — Blender's Vertex Paint. Stripes, war paint, blood, scars, a
pale belly, the dark tip of a tail.

``strokes`` rows ``[x, y, z, radius, r, g, b, strength, hardness]`` (a
dab) or the same plus ``ex, ey, ez`` (a line from (x, y, z) to there),
in the children's frame, colours 0-255, ``strength`` 0-1 how much of
the colour lands, ``hardness`` 0-1 how sharp the edge is (0 soft, 1 a
crisp disc). Each face takes the strokes over its own colour IN ORDER,
by how close its centre is, so a later stroke paints over an earlier
one. Alpha and material are kept.

Compiles to ``kcad_vertex_paint(strokes = [...]) { children }`` whose
helper renders the children unchanged — OpenSCAD has no per-face
colour; the preview, pictures and coloured exports have. Combine with
weathering above it for dirt in the creases on top of the paint.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import hashlib
import json

DAB_LEN = 9
LINE_LEN = 12
ROW_LENS = (DAB_LEN, LINE_LEN)

NODE_TYPES = {
    "vertex_paint": dict(
        label="Vertex paint (hand painting)", category="operation",
        icon="mdi.brush-variant",
        params=dict(strokes=[], base=""),
        schema=[("strokes", "Strokes (centre, radius, r g b 0-255, "
                            "strength, hardness; + end for a line)",
                 "rows", ["X", "Y", "Z", "Radius", "R", "G", "B",
                          "Strength", "Hardness", "End X", "End Y",
                          "End Z"], None),
                ("base", "Base colour (empty = the part's own)", "color",
                 None, None)]),
}
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset()
WRAPPERS = frozenset(NODE_TYPES)
COLORED = frozenset(NODE_TYPES)
TEXT_PARAMS = frozenset({"base"})

HELPER = """\
module kcad_vertex_paint(strokes = [], base = "") {
    // OpenSCAD has no per-face colour: the preview paints it
    children();
}"""


def _rgb(value, fallback=(128, 128, 128)):
    from .weathering import _rgb as rgb
    return rgb(value, fallback)


def paint(tris, colours, strokes, base=""):
    """Per-face colours ``(hex, alpha[, material])`` for *tris* (own
    colours *colours*) with *strokes* (resolved rows) brushed on."""
    import numpy as np
    if not tris:
        return []
    centres = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3).mean(1)
    out = np.empty((len(tris), 3))
    cache = {}
    default = _rgb(base or "#808080")
    for i, c in enumerate(colours):
        key = c[0] if c else None
        rgb = cache.get(key)
        if rgb is None:
            rgb = cache[key] = (_rgb(base) if base else
                                (_rgb(key, default) if key else default))
        out[i] = rgb
    for row in strokes:
        x, y, z, radius, r, g, b, strength, hardness = row[:DAB_LEN]
        if radius <= 0 or strength == 0:
            continue
        p = np.asarray([x, y, z])
        if len(row) >= LINE_LEN:
            e = np.asarray(row[9:12])
            d = e - p
            ll = float(d @ d)
            t = np.clip((centres - p) @ d / ll, 0.0, 1.0) if ll > 1e-12 \
                else np.zeros(len(centres))
            dist = np.linalg.norm(centres - p - t[:, None] * d, axis=1)
        else:
            dist = np.linalg.norm(centres - p, axis=1)
        u = np.clip(dist / radius, 0.0, 1.0)
        # hardness 1: flat to the rim; 0: smoothstep all the way
        h = min(max(float(hardness), 0.0), 0.999)
        s = np.clip((u - h) / (1.0 - h), 0.0, 1.0)
        w = (1.0 - s * s * (3.0 - 2.0 * s)) * min(abs(strength), 1.0)
        w[u >= 1.0] = 0.0
        out = out * (1.0 - w[:, None]) + np.asarray([r, g, b])[None] \
            * w[:, None]
    rgb = np.clip(np.rint(out), 0, 255).astype(int)
    result = []
    for (r, g, b), c in zip(rgb.tolist(), colours):
        alpha = c[1] if c else 1.0
        colour = f"#{r:02x}{g:02x}{b:02x}"
        result.append((colour, alpha, c[2]) if c and len(c) > 2
                      else (colour, alpha))
    return result


# ------------------------------------------------------------ contract

def preamble(root) -> list:
    if any(n.type in TYPES for n in root.walk()):
        return HELPER.split("\n")
    return []


def statement(node, fmt, fn) -> str:
    from .model import scad_str
    rows = ", ".join("[" + ", ".join(fmt(v) for v in row) + "]"
                     for row in node.params.get("strokes") or []
                     if isinstance(row, list))
    return (f"kcad_vertex_paint(strokes = [{rows}], "
            f"base = {scad_str(str(node.params.get('base', '')))})")


def _b_paint(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    rows = named.get("strokes")
    base = named.get("base", "")
    base = base[1:-1] if isinstance(base, str) and base.startswith('"') \
        else ""
    return CadNode("vertex_paint", NODE_TYPES["vertex_paint"]["label"],
                   dict(strokes=[[_num(v) for v in row] for row in rows
                                 if isinstance(row, list)]
                        if isinstance(rows, list) else [], base=base))


BUILDERS = {"kcad_vertex_paint": _b_paint}


def check(node, env):
    from .weathering import _valid_colour
    for k, row in enumerate(node.params.get("strokes") or []):
        if not isinstance(row, list) or len(row) not in ROW_LENS:
            return (f"paint stroke {k} needs {DAB_LEN} values (x, y, z, "
                    "radius, r, g, b, strength, hardness) or "
                    f"{LINE_LEN} with an end point")
    if not _valid_colour(node.params.get("base", "")):
        return "vertex paint: the base colour must be #rrggbb"
    if not node.children:
        return "vertex paint: put the part to paint inside it"
    return None


_CACHE = {}
CACHE_SIZE = 8


def resolved(node, env):
    from . import mesh
    return [[mesh.rv(v, env) for v in row]
            for row in node.params.get("strokes") or []
            if isinstance(row, list) and len(row) in ROW_LENS]


def tess(node, env, color, sel, selected):
    from . import mesh
    kids = mesh._children_mesh(node, env, color, sel, selected)
    if not kids:
        return kids
    import numpy as np
    strokes = resolved(node, env)
    base = str(node.params.get("base", "") or "")
    h = hashlib.sha1(json.dumps([strokes, base]).encode())
    h.update(np.asarray([t for t, _c, _s in kids], dtype=np.float64)
             .tobytes())
    h.update(repr([c for _t, c, _s in kids]).encode())
    key = h.hexdigest()
    painted = _CACHE.get(key)
    if painted is None:
        painted = paint([t for t, _c, _s in kids],
                        [c for _t, c, _s in kids], strokes, base)
        _CACHE[key] = painted
        while len(_CACHE) > CACHE_SIZE:
            _CACHE.pop(next(iter(_CACHE)))
    return [(tri, colour, s) for (tri, _c, s), colour in zip(kids, painted)]
