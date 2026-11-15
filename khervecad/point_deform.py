"""SolidWorks' **Deform ▸ Point** (2026-11-15, the "Deform feature" video:
the fan cover's grille pushed up into a dome by a point at the origin,
15 mm along the axis, over a radius of 40 mm, then a second push down).

The node holds the bodies (its children) and one push: a *point*, a
*direction*, a *distance* (mm, along the direction) and a *radius*. Every
vertex within *radius* of the point moves along the direction by
``distance · f(d / radius)`` — d is its distance from the point, f falls
smoothly from 1 at the point to 0 at the radius, its stiffness chosen by
the *shape*: ``minimum`` (a bell, (1-t^2)^2), ``medium`` (a plateau
dome, (1-t^4)^3 — the video's two pushes, which with this falloff leave a
ring ridge round a distinct central dimple) or ``maximum`` (a broad
table, (1-t^6)^3). A vertex is moved by where it IS, so a closed solid
stays closed, holes keep their shape and what lies beyond the radius is
not touched. Meshes are first refined (``detail`` mm, 0 = automatic) so
the surface can curve.

Baked like the other kit wrappers: ``kcad_point_deform(px, py, pz, dx,
dy, dz, distance, radius, shape, detail, points=, faces=) { bodies }``.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import bakedkit

SHAPES = ["minimum", "medium", "maximum"]
_DEFAULTS = {"px": 0.0, "py": 0.0, "pz": 0.0, "dx": 0.0, "dy": 0.0,
             "dz": 1.0, "distance": 10.0, "radius": 30.0,
             "shape": "medium", "detail": 0.0}
#: cap on the refined mesh (triangles)
MAX_TRIS = 250_000


def falloff(t, shape="medium"):
    """The share of the push at t = distance / radius (numpy arrays
    too): 1 at the point, 0 from the radius on."""
    import numpy as np
    t = np.clip(np.asarray(t, float), 0.0, 1.0)
    if shape == "minimum":
        return (1.0 - t * t) ** 2          # a bell: the surface by the point
    if shape == "maximum":
        return (1.0 - t ** 6) ** 3         # a broad table, steep at the rim
    return (1.0 - t ** 4) ** 3             # a plateau dome (the video's)


def push(verts, point, direction, distance, radius, shape="medium"):
    """The vertices (n x 3) after the push."""
    import numpy as np
    v = np.asarray(verts, float)
    d = np.asarray(direction, float)
    n = np.linalg.norm(d)
    if n < 1e-12 or radius <= 0:
        return v
    d = d / n
    dist = np.linalg.norm(v - np.asarray(point, float), axis=1)
    amount = distance * falloff(dist / radius, shape)
    return v + amount[:, None] * d[None, :]


def _compute(node, env):
    from . import deform
    import numpy as np
    tris = bakedkit.source_tris(node, env)
    num = lambda k: bakedkit.num(node, env, k, _DEFAULTS[k])    # noqa: E731
    radius, distance = num("radius"), num("distance")
    tris = [tuple(t[:3]) for t in tris]
    if not tris or radius <= 0 or abs(distance) < 1e-12:
        return tris
    detail = num("detail")
    if detail <= 0:
        detail = max(radius / 20.0, 0.5)
    fine = tris
    for _ in range(8):
        fine = deform.split_long_edges(tris, detail)
        if len(fine) <= MAX_TRIS:
            break
        detail *= 1.5
    verts = {}
    for t in fine:
        for v in t:
            verts.setdefault(v, len(verts))
    keys = list(verts)
    moved = push(np.array(keys, float), (num("px"), num("py"), num("pz")),
                 (num("dx"), num("dy"), num("dz")), distance, radius,
                 str(node.params.get("shape", "medium")))
    pt = [tuple(float(c) for c in m) for m in moved]
    return [tuple(pt[verts[v]] for v in t) for t in fine]


def _check(node, env):
    if bakedkit.num(node, env, "radius", 0.0) <= 0:
        return "Deform: the radius must be greater than 0"
    if math.sqrt(sum(bakedkit.num(node, env, k, 0.0) ** 2
                     for k in ("dx", "dy", "dz"))) < 1e-9:
        return "Deform: the direction needs a length"
    return None


KIT = bakedkit.make(
    "point_deform", "Deform (point)", "mdi.arrow-collapse-up", _DEFAULTS,
    [("px", "Point X", "float", -1e6, 1e6),
     ("py", "Point Y", "float", -1e6, 1e6),
     ("pz", "Point Z", "float", -1e6, 1e6),
     ("dx", "Direction X", "float", -1e6, 1e6),
     ("dy", "Direction Y", "float", -1e6, 1e6),
     ("dz", "Direction Z", "float", -1e6, 1e6),
     ("distance", "Deform distance (mm)", "float", -1e6, 1e6),
     ("radius", "Deform radius (mm)", "float", 0.0, 1e6),
     ("shape", "Shape (stiffness)", "choice", SHAPES, None),
     ("detail", "Refine to (mm, 0 = automatic)", "float", 0.0, 1e6)],
    _compute, check=_check, inexact_ok=True,
    choices={"shape": SHAPES}, text=("shape",))


def make(model, bodies, point, direction, distance, radius,
         shape="medium", reverse=False):
    """Wrap *bodies* in a Point Deform. *point* and *direction* are in
    WORLD coordinates (the scope's frame). The node."""
    import numpy as np
    from . import mesh
    node = model.wrap_nodes(list(bodies), "point_deform")
    if node is None:
        return None
    m = np.array(mesh.ancestor_matrix(node), float)
    inv = np.linalg.inv(m)
    p = (inv @ np.array([point[0], point[1], point[2], 1.0]))[:3]
    d = np.linalg.inv(m[:3, :3]) @ np.array(direction, float)
    n = np.linalg.norm(d) or 1.0
    d = d / n * (-1.0 if reverse else 1.0)
    node.params.update(
        px=round(float(p[0]), 4), py=round(float(p[1]), 4),
        pz=round(float(p[2]), 4), dx=round(float(d[0]), 6),
        dy=round(float(d[1]), 6), dz=round(float(d[2]), 6),
        distance=float(distance), radius=float(radius), shape=shape)
    node.name = "Deform (point)"
    model.node_changed.emit(node)
    return node
