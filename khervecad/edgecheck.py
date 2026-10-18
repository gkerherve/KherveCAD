"""Sharp-edge check (Qt-free): the edges of a part that would cut a
hand or chip — creases whose faces meet at less than a face angle
(default 135°, so a 90° box corner is sharp and a 45° chamfer's two
135° creases are not) and that no fillet, bevel or chamfer has rounded.

A rounded edge has no crease of its own: a fillet's facets turn a few
degrees each, so it never shows up here. Edges come from
`fillet.crease_edges` and are joined into runs by `fillet.chain`, so a
box reports 12 chains and a cylinder's two rims 2, and every chain
carries the `seed` that `fillet_edges` / the fillet node take.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import fillet

#: an edge is sharp when its two faces meet at less than this (degrees,
#: the angle INSIDE the material: 90 for a box corner, 180 flat)
DEFAULT_FACE_ANGLE = 135.0
#: what the Blueprint note says
NOTE_TEXT = "BREAK ALL SHARP EDGES 0.5 × 45°"
#: chains listed in full (a knurl has thousands)
MAX_LISTED = 60


def _strip(e, width):
    """Two thin triangles each side of edge *e*, lying in its faces, so
    the 3D view can tint the edge itself."""
    d = e.direction
    in_l = fillet._unit(fillet._cross(e.nl, d))
    in_r = fillet._unit(fillet._cross(e.nr, fillet._mul(d, -1.0)))
    out = []
    for inward in (in_l, in_r):
        off = fillet._mul(inward, width)
        a2, b2 = fillet._add(e.a, off), fillet._add(e.b, off)
        out += [(e.a, e.b, b2), (e.a, b2, a2)]
    return out


def sharp_edges(tris, face_angle: float = DEFAULT_FACE_ANGLE,
                concave: bool = False) -> dict:
    """The report: ``status`` pass / warn, ``count`` chains, ``length``
    total, ``chains`` (fillet.chains-shaped dicts, longest first, each
    with its face ``angle``), ``tris`` to highlight and ``message``.
    Inside corners (``concave``) are only counted when asked — they do
    not cut, but they concentrate stress."""
    if not tris:
        return dict(status="pass", count=0, length=0.0, chains=[],
                    tris=[], message="Nothing to check.")
    dihedral = max(0.0, 180.0 - float(face_angle))
    edges = [e for e in fillet.crease_edges(tris, dihedral + 1e-6)
             if e.convex or concave]
    size = fillet.mesh_size(tris)
    width = max(size * 0.006, 1e-6)
    chains, seen, strips = [], set(), []
    for e in edges:
        run = fillet.chain(edges, e)
        key = frozenset(fillet._vkey(p) for p in run["points"])
        if key in seen:
            continue
        seen.add(key)
        pts = run["points"]
        length = sum(x.length for x in run["edges"])
        mean = sum(x.angle for x in run["edges"]) / len(run["edges"])
        centre = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
        chains.append(dict(
            seed=[round(v, 4) for v in (*e.a, *e.b)],
            start=[round(v, 4) for v in pts[0]],
            end=[round(v, 4) for v in pts[-1]],
            centre=[round(v, 3) for v in centre],
            length=round(length, 3), segments=len(run["edges"]),
            face_angle=round(180.0 - mean, 1),
            convex=run["convex"], closed=run["closed"]))
        for x in run["edges"]:
            strips += _strip(x, width)
    chains.sort(key=lambda c: (-c["length"], c["centre"]))
    total = round(sum(c["length"] for c in chains), 3)
    if chains:
        status = "warn"
        message = (f"{len(chains)} sharp edge run(s), {total:g} long in "
                   f"all, meet at under {face_angle:g}° — round or chamfer "
                   "them, or note 'break sharp edges' on the drawing.")
    else:
        status = "pass"
        message = f"No edge sharper than {face_angle:g}°."
    return dict(status=status, count=len(chains), length=total,
                chains=chains, tris=strips, message=message,
                face_angle=float(face_angle))


def local_seeds(local_tris, face_angle: float = DEFAULT_FACE_ANGLE):
    """Fillet seeds of the sharp convex edges of a part's LOCAL mesh —
    what a fillet node wrapped round it takes as ``edges``."""
    return [c["seed"] for c in sharp_edges(local_tris, face_angle)["chains"]
            if c["convex"]]
