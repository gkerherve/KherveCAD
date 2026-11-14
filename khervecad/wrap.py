"""SolidWorks' **Wrap** (2026-11-14, the user: the Features tab's tools
KherveCAD lacked — "the Wrap, the Dome"): a flat 2D sketch — text, a
logo, any outline — wrapped round a cylindrical part, **embossed** (it
stands out by `depth`) or **debossed** (cut in by `depth`).

The node holds the PART first and the 2D shapes after it, drawn flat:
the sketch's x is the distance AROUND the cylinder (mm along the
surface, from `angle`), its y the height UP the cylinder's axis (Z,
from z = 0 of the part's frame). The cylinder's axis and radius are the
part's own (the middle and half the width of its XY box) unless
`radius` is given (then `cx`, `cy` place the axis).

How: the sketch is one Manifold CrossSection, extruded into a thin
band, refined along its length, and WARPED round the axis — x to the
angle x / R, the band's thickness to the radius — so it lies on the
curved face (read from outside, as drawn). Emboss = the part ∪ the band
(from just inside the face out to R + depth), deboss = the part − the
band (from R − depth to just outside). Baked like the other kit
wrappers: `kcad_wrap(kind=, depth=, radius=, cx=, cy=, angle=,
points=, faces=) { part; 2D shapes }`.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import bakedkit

_DEFAULTS = {"kind": "emboss", "depth": 1.0, "radius": 0.0, "cx": 0.0,
             "cy": 0.0, "angle": 0.0}
#: how far the band reaches past the face on its other side (mm), so the
#: union / cut has real overlap
OVERLAP = 0.05


def _parts(node):
    from .model import SHAPE_2D
    kids = [c for c in node.children if c.visible]
    body = next((c for c in kids if c.category != SHAPE_2D), None)
    shapes = [c for c in kids if c is not body]
    return body, shapes


def _axis(node, env, tris):
    """(cx, cy, R) of the wrap's cylinder."""
    r = bakedkit.num(node, env, "radius", 0.0)
    if r > 0:
        return (bakedkit.num(node, env, "cx", 0.0),
                bakedkit.num(node, env, "cy", 0.0), r)
    xs = [p[0] for t in tris for p in t]
    ys = [p[1] for t in tris for p in t]
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
            max(max(xs) - min(xs), max(ys) - min(ys)) / 2)


def band(shapes, env, cx, cy, R, depth, kind, angle0):
    """The sketch bent round the axis as one Manifold, or None."""
    import manifold3d as m
    import numpy as np
    from . import mesh
    loops = []
    for s in shapes:
        loops.extend(mesh.collect_outlines(s, env))
    loops = [np.array([(float(p[0]), float(p[1])) for p in lp], float)
             for lp in loops if len(lp) >= 3]
    if not loops:
        return None
    cs = m.CrossSection(loops, m.FillRule.Positive)
    if cs.is_empty():
        return None
    if kind == "deboss":
        r0, thick = R - depth, depth + OVERLAP
    else:
        r0, thick = R - OVERLAP, depth + OVERLAP
    flat = m.Manifold.extrude(cs, thick)
    # fine enough along the circumference to bend smoothly
    flat = flat.refine_to_length(max(R * 2 * math.pi / 180, 0.2))
    a0 = math.radians(angle0)

    def bend(v):
        x, y, z = v[:, 0], v[:, 1], v[:, 2]
        th = a0 + x / R
        r = r0 + z
        return np.stack([cx + r * np.cos(th), cy + r * np.sin(th), y],
                        axis=1)
    return flat.warp_batch(bend)


def _compute(node, env):
    from . import csg, mesh
    body, shapes = _parts(node)
    if body is None:
        return []
    tris = [tuple(t[:3]) for t in mesh.tessellate(body, env)]
    if not tris or not shapes or not csg.available():
        return tris
    cx, cy, R = _axis(node, env, tris)
    depth = bakedkit.num(node, env, "depth", 1.0)
    kind = str(node.params.get("kind", "emboss"))
    b = band(shapes, env, cx, cy, R, depth, kind,
             bakedkit.num(node, env, "angle", 0.0))
    solid = csg.to_manifold([(t, None, False) for t in tris], {})
    if b is None or solid is None:
        return tris
    out = solid - b if kind == "deboss" else solid + b
    return csg.to_triangles(out)


def _check(node, env):
    body, shapes = _parts(node)
    if body is None:
        return "Wrap: put the round part first, then the 2D sketch"
    if not shapes:
        return "Wrap: add the 2D sketch (text or shapes) after the part"
    if bakedkit.num(node, env, "depth", 1.0) <= 0:
        return "Wrap: the depth must be more than 0"
    return None


KIT = bakedkit.make(
    "wrap", "Wrap", "mdi.format-text-wrapping-wrap", _DEFAULTS,
    [("kind", "Type", "choice", ["emboss", "deboss"], None),
     ("depth", "Depth (mm)", "float", 0.0, 1e6),
     ("angle", "Start angle round the axis (°)", "float", -360.0, 360.0),
     ("radius", "Radius (0 = the part's own)", "float", 0.0, 1e6),
     ("cx", "Axis X (with a radius)", "float", -1e6, 1e6),
     ("cy", "Axis Y (with a radius)", "float", -1e6, 1e6)],
    _compute, choices={"kind": ["emboss", "deboss"]}, check=_check,
    text=("kind",), inexact_ok=True)


def wrap_text(model, part, text, size=8.0, kind="emboss", depth=1.0):
    """Wrap *part* with a text: the Wrap round it, the text centred
    across the cylinder's front (−Y) half way up. Returns the Wrap."""
    from . import mesh
    tris = mesh.tessellate(part)
    zs = [p[2] for t in tris for p in t]
    w = model.wrap_nodes([part], "wrap")
    if w is None:
        return None
    w.params.update(kind=kind, depth=float(depth), angle=-90.0)
    model.add_node("text", dict(text=text, size=float(size),
                                halign="center", valign="center",
                                x=0.0, y=round((min(zs) + max(zs)) / 2, 3)),
                   parent=w, name="Wrap sketch")
    model.node_changed.emit(w)
    return w
