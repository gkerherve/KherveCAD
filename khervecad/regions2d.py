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
    return [c for c in node.children if c.category == SHAPE_2D
            and c.params.get("modifier") != "%"]


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
    cs = sr.union_of(face_list, picked)
    if cs is not None and node.params.get("fuse"):
        cs = _fused(node, cs)
    return cs, face_list, picked


def _fused(node, cs):
    """A boss closed with the model's edges, pushed into the part along
    them (2026-11-01: the user's rib stood 0.05 mm off the block and the
    plate — the section is grown that much — a separate solid). Only
    where the area meets the kept "Model edges" polygon: its free edges
    (the user's line) stay where they are."""
    from . import sketch_section
    import manifold3d as m
    loops = []
    for s in shapes(node):
        if not sketch_section.is_section(s):
            continue
        pts = s.params.get("points") or []
        paths = s.params.get("paths") or [list(range(len(pts)))]
        loops += [[(float(pts[i][0]), float(pts[i][1])) for i in path]
                  for path in paths]
    if not loops:
        return cs
    section = m.CrossSection(loops, m.FillRule.EvenOdd)
    # only what stands OUTSIDE the part is pushed into it: an area drawn
    # on a face lies inside the outline, and growing all of it made a
    # 60 mm boss 60.3 wide (2026-11-10)
    outside = cs - section
    if outside.is_empty():
        return cs
    pushed = _push_into(outside, loops, 3 * sketch_section.GROW, m)
    if pushed is None:                   # as before: grown and clipped
        return cs + (outside.offset(3 * sketch_section.GROW,
                                    m.JoinType.Miter) ^ section)
    return cs + pushed


def _push_into(outside, loops, depth, m):
    """*outside* with its edges that lie on the part's (grown) outline
    moved *depth* into the part, and a free edge meeting the outline
    EXTENDED along its own line to that depth — so a rib's slope runs on,
    one flat face, into the wall and the base. Growing the whole area and
    clipping it (the first way) made the corners spike past the slope:
    0.05 mm steps above it at the wall and at its foot, which a fillet
    rounded into a lip (2026-11-10, the user). None when it cannot."""
    import math
    segs = []
    for loop in loops:
        n = len(loop)
        segs += [(loop[i], loop[(i + 1) % n]) for i in range(n)]

    def on_outline(p):
        for a, b in segs:
            dx, dy = b[0] - a[0], b[1] - a[1]
            L2 = dx * dx + dy * dy
            if L2 < 1e-18:
                continue
            t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2
            if -1e-6 <= t <= 1 + 1e-6:
                q = (a[0] + t * dx, a[1] + t * dy)
                if math.hypot(p[0] - q[0], p[1] - q[1]) < 1e-5:
                    return True
        return False

    def meet(p, d, q, e):
        """Where line p + s d meets line q + t e (or None)."""
        det = d[0] * e[1] - d[1] * e[0]
        if abs(det) < 1e-12:
            return None
        s = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / det
        return (p[0] + s * d[0], p[1] + s * d[1])

    out = []
    for poly in outside.to_polygons():
        loop = [(float(x), float(y)) for x, y in poly]
        n = len(loop)
        if n < 3:
            continue
        on_edge = []
        for i in range(n):
            a, b = loop[i], loop[(i + 1) % n]
            on_edge.append(on_outline(((a[0] + b[0]) / 2,
                                       (a[1] + b[1]) / 2)))
        new = []
        for i in range(n):
            v = loop[i]
            prev_on, next_on = on_edge[i - 1], on_edge[i]
            if not (prev_on or next_on):
                new.append(v)
                continue
            a, b = loop[i - 1], loop[(i + 1) % n]
            d_in, d_out = (v[0] - a[0], v[1] - a[1]), (b[0] - v[0],
                                                     b[1] - v[1])

            def into(d):
                # the part lies on the RIGHT of an outline edge of the
                # area (its inside is on the left)
                L = math.hypot(*d) or 1.0
                return (d[1] / L * depth, -d[0] / L * depth)
            if prev_on and next_on:
                ia, ib = into(d_in), into(d_out)
                got = meet((a[0] + ia[0], a[1] + ia[1]), d_in,
                           (v[0] + ib[0], v[1] + ib[1]), d_out)
            elif prev_on:                 # the free edge leaves v
                ia = into(d_in)
                got = meet(v, (-d_out[0], -d_out[1]),
                           (a[0] + ia[0], a[1] + ia[1]), d_in)
            else:                         # the free edge arrives at v
                ib = into(d_out)
                got = meet(v, d_in, (v[0] + ib[0], v[1] + ib[1]), d_out)
            if got is None or math.hypot(got[0] - v[0], got[1] - v[1]) > \
                    depth * 20:
                new.append(v)             # a grazing line: leave it
            else:
                new.append(got)
        out.append(new)
    if not out:
        return None
    try:
        return m.CrossSection(out, m.FillRule.Positive)
    except Exception:
        return None


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
