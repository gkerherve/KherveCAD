"""The parametric feature nodes of the libraries OpenSCAD users reach
for — gears, threads, holes, polyhedra, rounded and curved 2D shapes,
knurls, honeycombs — registered in one place.

Each module listed in `MODULES` follows the organic-node contract:
``NODE_TYPES``, ``LEAVES`` (and optionally ``WRAPPERS``), ``preamble(root)``
(its ``kcad_*`` helper module, real OpenSCAD run at render time),
``statement(node, fmt, fn)``, ``BUILDERS`` (the importer), ``check(node,
env)``, ``tess(node, env, color, sel, selected)`` (the preview, the same
formulas in Python) and, for a 2D shape, ``outlines(node, env)``.
organic.py hooks this module into the registry, codegen, parser,
validation and tessellator exactly once.

No package imports at module level beyond the feature modules, which
keep the same rule.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from . import curves2d, gears, holes, solids, textured, textures, threads

MODULES = [gears, threads, holes, solids, curves2d, textures,
           textured]

NODE_TYPES = {}
LEAVES = frozenset()
WRAPPERS = frozenset()
BUILDERS = {}
_OWNER = {}
for _mod in MODULES:
    NODE_TYPES.update(_mod.NODE_TYPES)
    LEAVES = LEAVES | frozenset(getattr(_mod, "LEAVES", ()))
    WRAPPERS = WRAPPERS | frozenset(getattr(_mod, "WRAPPERS", ()))
    BUILDERS.update(_mod.BUILDERS)
    for _t in _mod.NODE_TYPES:
        _OWNER[_t] = _mod
TYPES = frozenset(NODE_TYPES)
#: 2D feature types whose outlines mesh.node_outlines asks for
SHAPES_2D = frozenset(t for t, d in NODE_TYPES.items()
                      if d["category"] == "2d")
#: 2D feature types whose nested loops are holes (mesh._oriented)
NESTED_2D = frozenset().union(*(getattr(m, "NESTED_2D", frozenset())
                                for m in MODULES))
#: params the preview keeps as text
TEXT_PARAMS = frozenset().union(*(getattr(m, "TEXT_PARAMS", frozenset())
                                  for m in MODULES))


def preamble(root) -> list:
    lines = []
    for mod in MODULES:
        lines.extend(mod.preamble(root))
    return lines


def statement(node, fmt, fn) -> str:
    return _OWNER[node.type].statement(node, fmt, fn)


def check(node, env):
    return _OWNER[node.type].check(node, env)


#: meshes of feature nodes by their resolved parameters: a gear that only
#: turns (its rotation lives on a parent) keeps its mesh — re-triangulating
#: 240-point tooth outlines on every slider tick was most of a frame
_MESH_CACHE = {}
MESH_CACHE_SIZE = 256


def tess(node, env, color, sel, selected):
    from . import mesh
    try:
        resolved = mesh.rp(node, env)
        key = (node.type, repr(sorted(resolved.items())),
               repr(sorted((k, v) for k, v in node.params.items()
                           if isinstance(v, str))),
               mesh._FN_OVERRIDE, mesh._DETAIL)
    except Exception:
        key = None
    if key is not None:
        tris = _MESH_CACHE.get(key)
        if tris is None:
            tris = [t for t, _c, _s in
                    _OWNER[node.type].tess(node, env, None, frozenset(),
                                           False)]
            if len(_MESH_CACHE) >= MESH_CACHE_SIZE:
                _MESH_CACHE.pop(next(iter(_MESH_CACHE)))
            _MESH_CACHE[key] = tris
        return mesh._emit(tris, color, selected)
    return _OWNER[node.type].tess(node, env, color, sel, selected)


def outlines(node, env):
    return _OWNER[node.type].outlines(node, env)


# ------------------------------------------------------ shared helpers

def extrude(loops, height, twist=0.0, scale=1.0, slices=0, center=False):
    """A preview solid: 2D *loops* (outer outlines and holes, nesting
    decides which) extruded exactly as linear_extrude would — through a
    transient node, so twist, scale and caps are the tessellator's own."""
    from . import mesh
    from .model import CadNode
    ext = CadNode("linear_extrude", "", dict(
        height=float(height), twist=float(twist), scale=float(scale),
        center=bool(center), segments=int(slices)))
    ext.add(polygon_node(loops))
    return mesh.linear_extrude_mesh(ext)


def stations_solid(loops, stations):
    """A closed solid through *stations* — (z, turn°, scale) — of the 2D
    *loops*: one continuous wall where two extrusions would meet cap to
    cap (a herringbone's halves), so the preview stays watertight. The
    turn follows linear_extrude's sense (clockwise for positive)."""
    import math
    from . import mesh
    loops = mesh._oriented(polygon_node(loops), [list(l) for l in loops])
    out = []
    for solid, holes in mesh.outline_regions(loops):
        rings_of = []
        for loop in [solid] + holes:
            rings = []
            for z, turn, s in stations:
                a = -math.radians(turn)
                ca, sa = math.cos(a), math.sin(a)
                rings.append([((x * s) * ca - (y * s) * sa,
                               (x * s) * sa + (y * s) * ca, z)
                              for x, y in loop])
            rings_of.append(rings)
            n = len(loop)
            for lower, upper in zip(rings, rings[1:]):
                for i in range(n):
                    j = (i + 1) % n
                    out.append((lower[i], lower[j], upper[j]))
                    out.append((lower[i], upper[j], upper[i]))
        z0, z1 = stations[0][0], stations[-1][0]
        bottom = [[(p[0], p[1]) for p in rings[0]] for rings in rings_of]
        top = [[(p[0], p[1]) for p in rings[-1]] for rings in rings_of]
        for a, b, c in mesh._caps(bottom[0], bottom[1:]):
            out.append(((a[0], a[1], z0), (c[0], c[1], z0), (b[0], b[1], z0)))
        for a, b, c in mesh._caps(top[0], top[1:]):
            out.append(((a[0], a[1], z1), (b[0], b[1], z1), (c[0], c[1], z1)))
    return out


def polygon_node(loops):
    """One polygon node holding *loops* as paths."""
    from .model import CadNode
    points, paths = [], []
    for loop in loops:
        start = len(points)
        points.extend([float(x), float(y)] for x, y in loop)
        paths.append(list(range(start, len(points))))
    return CadNode("polygon", "", dict(x=0.0, y=0.0, points=points,
                                       paths=paths))


def num(node, env, key, default=0.0):
    from . import mesh
    return mesh.rv(node.params.get(key, default), env, default)
