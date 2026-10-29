"""The part CUT by the sketch plane, shown in the 2D sketch (2026-10-27,
the user: "when I select the front plane I'm expecting to see a cut
through my part so that I can draw that triangle between the part" — a
rib in the middle of an L bracket).

On a main plane (Front XZ / Top XY / Side YZ) the 2D view drew the parts
only as their projected silhouettes, so nothing at the plane itself could
be seen or snapped to. `segments(tris, plane)` (Qt-free) is where the
plane cuts the solids (`section.cut`); a plane lying ON a face (a part
extruded from y = 0) is cut a hair inside the material, so the face's
own outline shows. `update(window)` hands it to the scene as its
``face_outline`` — the grey outline the face sketch already uses, with
the same snaps (corners, middles, arc centres, on-edge) for every sketch
tool, Line and Polygon included. A face sketch's own outline wins while
one is open.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

AXIS = {"Front (XZ)": "y", "Top (XY)": "z", "Side (YZ)": "x"}
NUDGE = 1e-3                      # mm inside the material on a face
MAX_TRIS = 400000
DELAY_MS = 150


def segments(tris, plane, offset=0.0):
    """[((u, v), (u, v))] where *plane*'s cut meets the solids, in the 2D
    view's coordinates for that plane, or []."""
    from . import section
    axis = AXIS.get(plane)
    if axis is None or not tris:
        return []
    # just in front of and just behind the plane, joined: a part the
    # plane crosses shows in both, a part lying ON it (extruded from
    # the plane) in one — exactly at the plane a face's triangles cut
    # into slivers
    groups = [section.cut(tris, axis, offset + NUDGE),
              section.cut(tris, axis, offset - NUDGE)]
    return merged(groups=groups) if any(groups) else []


def merged(segs=None, groups=None):
    """The cut outlines as ONE region (Manifold CrossSection): parts that
    overlap — a base and its upright — meet in a real corner, and the
    slivers a cut along a face leaves fall away. Without Manifold, the
    raw segments. *groups*: separate cuts (just in front of and just
    behind the plane), each chained into loops ON ITS OWN — chained
    together, their pieces mixed where the plane ran through mesh points
    (a pin hole's top and bottom) and the loops broke: the clevis's
    middle fell out of its section (2026-10-29)."""
    from . import section
    groups = groups if groups is not None else [segs or []]
    raw = [(tuple(a), tuple(b)) for g in groups for a, b in g]
    try:
        import manifold3d as m
    except ImportError:                              # pragma: no cover
        return raw
    loops = [pts for g in groups if g for pts, closed in section.chain(g)
             if closed and len(pts) >= 3]
    if not loops:
        return raw
    try:
        # one section of every loop, filled where the winding is
        # positive: overlapping solids join, a hole (clockwise) stays out
        cs = m.CrossSection([[(float(x), float(y)) for x, y in loop]
                             for loop in loops], m.FillRule.Positive)
        cs = cs.simplify(1e-3)
        polys = cs.to_polygons()
    except Exception:
        return raw
    out = []
    for poly in polys:
        pts = [(round(float(x), 4) + 0.0, round(float(y), 4) + 0.0)
               for x, y in poly]
        for i, a in enumerate(pts):
            b = pts[(i + 1) % len(pts)]
            if a != b:
                out.append((a, b))
    return out or raw


def plane_segments(tris, origin, normal, right, up):
    """Where ANY plane (origin, unit normal; its in-plane axes right /
    up) cuts the solids, in (right, up) coordinates, merged. Each
    segment runs with the solid on its left (direction n × N)."""
    def dot(a, b):
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    def sub(a, b):
        return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0])
    groups = []
    for nudge in (NUDGE, -NUDGE):
        out = []
        groups.append(out)
        o = tuple(origin[i] + normal[i] * nudge for i in range(3))
        for tri in tris:
            d = [dot(sub(p, o), normal) for p in tri]
            pts = []
            for i in range(3):
                a, b = tri[i], tri[(i + 1) % 3]
                da, db = d[i], d[(i + 1) % 3]
                if (da < 0) != (db < 0):
                    t = da / (da - db)
                    pts.append(tuple(a[k] + (b[k] - a[k]) * t
                                     for k in range(3)))
            if len(pts) != 2:
                continue
            tn = cross(sub(tri[1], tri[0]), sub(tri[2], tri[0]))
            a, b = pts
            if dot(sub(b, a), cross(normal, tn)) < 0:
                a, b = b, a
            rel_a, rel_b = sub(a, origin), sub(b, origin)
            out.append(((round(dot(rel_a, right), 6),
                         round(dot(rel_a, up), 6)),
                        (round(dot(rel_b, right), 6),
                         round(dot(rel_b, up), 6))))
    return merged(groups=groups) if any(groups) else []


def for_group(window, group):
    """The cut at a face sketch's plane, in its own frame — for a sketch
    on a reference plane that no face lies in (face_outline then found
    nothing)."""
    from . import face_outline, face_sketch, meshedit_ui
    o = face_sketch.to_world(group, 0.0, 0.0)
    ex = face_sketch.to_world(group, 1.0, 0.0)
    ey = face_sketch.to_world(group, 0.0, 1.0)
    r = [ex[i] - o[i] for i in range(3)]
    u = [ey[i] - o[i] for i in range(3)]
    n = face_sketch._normal_of(group)
    tris = [t for node, ts in meshedit_ui._parts(window)
            if node is not group for t in ts]
    if not tris or len(tris) > MAX_TRIS:
        return []
    segs = plane_segments(tris, o, n, r, u)
    if segs:
        window.view2d.scene().face_outline = {
            "segments": segs, "points": face_outline.snap_points(segs),
            "section": True}
    return segs


# =================================================================== Qt

def schedule(window):
    from PyQt5.QtCore import QTimer
    timer = getattr(window, "_section_timer", None)
    if timer is None:
        timer = window._section_timer = QTimer(window)
        timer.setSingleShot(True)
        timer.setInterval(DELAY_MS)
        timer.timeout.connect(lambda: update(window))
    timer.start()


def update(window):
    """Show the cut for the 2D view's plane (unless a face sketch is
    open: its own face outline is what matters then)."""
    from . import face_outline, meshedit_ui
    scene = window.view2d.scene()
    if getattr(window, "_face_sketch", None) is not None:
        return None
    info = getattr(scene, "face_outline", None)
    if info and not info.get("section"):
        return None                       # someone else's outline
    plane = getattr(scene, "plane", None)
    segs = []
    if plane in AXIS:
        try:
            tris = [t for _n, ts in meshedit_ui._parts(window) for t in ts]
            if len(tris) <= MAX_TRIS:
                segs = segments(tris, plane)
        except Exception:                 # never stop the sketch
            import traceback
            traceback.print_exc()
            segs = []
    if segs:
        scene.face_outline = {"segments": segs,
                              "points": face_outline.snap_points(segs),
                              "section": True}
    else:
        scene.face_outline = None
    window.view2d.viewport().update()
    return segs
