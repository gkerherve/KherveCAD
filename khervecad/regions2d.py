"""The **Regions** node (SolidWorks' Selected Contours as a tree node,
2026-10-25 — the user: "the regions should have the rectangle and circle
inside … smart dimension needs to work also in regions").

A 2D wrapper holding the sketch shapes it is made from (a rectangle and
a perimeter circle) and drawing the UNION of the regions picked among
them. A pick is remembered as a point inside the region and the shapes
it lies in (`seeds`, `inside`), so the regions are found again however
the shapes are resized — the Smart Dimensions live on this node (its
`params["constraints"]`, the children are their entities) and drive the
outline. The shapes inside may be hidden; what the node draws does not
depend on it.

OpenSCAD cannot cut a sketch into regions, so codegen writes
`kcad_regions(seeds =, inside =, points =, paths =) { shapes }` whose
helper draws the computed outline and ignores the shapes; the importer
rebuilds the node from seeds, inside and the shapes (the outline is
recomputed, never read back).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

NODE_TYPES = {
    "regions": dict(
        label="Regions", category="operation", icon="mdi.texture-box",
        params=dict(seeds=[], inside=[]),
        schema=[("seeds", "Region points", "rows", ["X", "Y"], None),
                ("inside", "In shapes", "rows", None, None)]),
}
TYPES = frozenset(NODE_TYPES)
WRAPPERS = frozenset(NODE_TYPES)
LEAVES = frozenset()

HELPER = """\
module kcad_regions(seeds = [], inside = [], points = [], paths = []) {
    // the picked regions of the sketch inside, worked out by KherveCAD
    polygon(points = points, paths = paths);
}"""


def shapes(node):
    """The sketch shapes the regions are cut from (hidden ones too)."""
    from .model import SHAPE_2D
    return [c for c in node.children if c.category == SHAPE_2D]


def _cs(node):
    """The picked regions' union as a Manifold CrossSection, or None."""
    from . import sketch_regions as sr
    face_list = sr.faces(shapes(node), any_state=True)
    insides = node.params.get("inside") or []
    picked = set()
    for k, p in enumerate(node.params.get("seeds") or []):
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            continue
        want = insides[k] if k < len(insides) else None
        picked.add(sr._match(face_list, (float(p[0]), float(p[1])), want))
    picked.discard(None)
    return sr.union_of(face_list, picked), face_list, picked


def outlines(node, env=None):
    """The outline loops (solids counter-clockwise, holes clockwise)."""
    try:
        cs, _f, _p = _cs(node)
    except Exception:                  # no Manifold, odd shapes
        return []
    if cs is None:
        return []
    return [[(float(p[0]), float(p[1])) for p in loop]
            for loop in cs.to_polygons() if len(loop) >= 3]


def track(node):
    """Re-seed the picks where their regions are now (a region that
    moved away from its old point is still found by its shapes)."""
    from . import sketch_regions as sr
    try:
        _cs_, face_list, picked = _cs(node)
    except Exception:
        return
    # only when EVERY pick is still found: half way through a move (the
    # rectangle in, the circle not yet) the circle's pick was dropped
    # ... and each in the SAME shapes as remembered: half way through
    # the move a pick inside the part's section fell on the box of lines
    # alone (the section not in yet) and was saved there — the clevis's
    # bottom cut then cut only air (2026-10-29)
    insides = node.params.get("inside") or []
    found = sorted(face_list[i][2] for i in picked)
    if insides and found != sorted(list(x) for x in insides):
        return
    if picked and len(picked) == len(node.params.get("seeds") or []):
        node.params["seeds"] = [sr.seed(face_list[i][0])
                                for i in sorted(picked)]
        node.params["inside"] = [face_list[i][2] for i in sorted(picked)]


def preamble(root) -> list:
    if any(n.type in TYPES for n in root.walk()):
        return HELPER.split("\n")
    return []


def _rows(rows, fmt):
    return "[" + ", ".join("[" + ", ".join(fmt(v) for v in r) + "]"
                           for r in rows if isinstance(r, (list, tuple))) \
        + "]"


def statement(node, fmt, fn) -> str:
    loops = outlines(node)
    points, paths = [], []
    for loop in loops:
        paths.append(list(range(len(points), len(points) + len(loop))))
        points.extend(loop)
    p = node.params
    return ("kcad_regions(seeds = %s, inside = %s,\n    points = %s,\n"
            "    paths = %s)" % (
                _rows(p.get("seeds") or [], fmt),
                _rows(p.get("inside") or [], fmt),
                _rows([[round(x, 4), round(y, 4)] for x, y in points], fmt),
                _rows(paths, fmt)))


def _b_regions(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num

    def rows(value):
        out = []
        for row in value or []:
            if isinstance(row, list):
                out.append([_num(v, 0.0) for v in row])
        return out
    seeds = [r[:2] for r in rows(named.get("seeds")) if len(r) >= 2]
    inside = [[int(v) for v in r] for r in rows(named.get("inside"))]
    return CadNode("regions", "Regions", {"seeds": seeds,
                                          "inside": inside})


BUILDERS = {"kcad_regions": _b_regions}


def check(node, env):
    if not shapes(node):
        return "Regions: put the sketch shapes inside it"
    if not outlines(node):
        return ("Regions: none of its regions is found — pick them again "
                "(Extrude regions)")
    return None


def tess(node, env, color, sel, selected):
    """Drawn flat like any 2D shape, when it stands outside an extrude."""
    from . import mesh
    loops = outlines(node)
    tris = []
    for solid, holes in mesh.outline_regions(loops):
        tris.extend(((a[0], a[1], 0.0), (b[0], b[1], 0.0),
                     (c[0], c[1], 0.0))
                    for a, b, c in mesh._caps(solid, holes))
    return mesh._emit(tris, color, selected)
