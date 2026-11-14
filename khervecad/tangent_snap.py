# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""A line's end snapping TANGENT to a circle or arc (2026-11-14, Exercise
6's Rib2: SolidWorks draws the line from the base's corner and moves the
cursor on until the tangent symbol shows). Qt-free.

Circles come from the sketch (circles, arcs = bulged lines) and from the
part under it (`drawing.find_circles` on the section / face outline —
the R30 full round is such an arc). From the line's START, each circle
has two tangent points; the end snaps to one when the cursor is within
the snap distance of it, and only where the circle really is (an arc's
sweep).
"""

from __future__ import annotations

import math


def tangent_points(start, centre, r):
    """The two points where a line from *start* touches the circle."""
    dx, dy = start[0] - centre[0], start[1] - centre[1]
    L = math.hypot(dx, dy)
    if L <= r + 1e-9:
        return []
    a = math.acos(r / L)
    base = math.atan2(dy, dx)
    return [(centre[0] + r * math.cos(base + s * a),
             centre[1] + r * math.sin(base + s * a)) for s in (1, -1)]


def _on_arc(c, p):
    if c.get("closed", True) or c.get("sweep", 360.0) >= 359.0:
        return True
    ang = math.degrees(math.atan2(p[1] - c["centre"][1],
                                  p[0] - c["centre"][0]))
    rel = (ang - c["start"]) % 360.0
    return rel <= c["sweep"] + 1.0 or rel >= 359.0


def snap(start, cursor, circles, tol):
    """(point, circle) of the tangent point within *tol* of *cursor*,
    nearest first, or None. *circles*: dicts with centre, r and, for an
    arc, start / sweep (degrees, counter-clockwise) and closed False."""
    best = None
    for c in circles:
        for p in tangent_points(start, c["centre"], c["r"]):
            if not _on_arc(c, p):
                continue
            d = math.hypot(p[0] - cursor[0], p[1] - cursor[1])
            if d <= tol and (best is None or d < best[0]):
                best = (d, p, c)
    return (best[1], best[2]) if best else None


def circles_of(shapes, outline_segments=()):
    """The circles and arcs to be tangent to: sketch circles (params x, y,
    radius), arcs (lines with a bulge) and the round edges among the
    part's outline segments."""
    out = []
    for s in shapes:
        p = s.params
        try:
            if s.type == "circle" and float(p.get("angle", 360)) >= 360:
                out.append({"centre": (float(p["x"]), float(p["y"])),
                            "r": float(p["radius"]), "closed": True,
                            "node": s})
            elif s.type == "line" and float(p.get("bulge") or 0) != 0:
                from . import sketch_arc
                g = sketch_arc.geometry(float(p["x1"]), float(p["y1"]),
                                        float(p["x2"]), float(p["y2"]),
                                        float(p["bulge"]))
                if g is None:
                    continue
                cx, cy, r, a0, sweep = g
                start = math.degrees(a0 if sweep > 0 else a0 + sweep)
                out.append({"centre": (cx, cy), "r": r, "closed": False,
                            "start": start % 360.0,
                            "sweep": abs(math.degrees(sweep)), "node": s})
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    if outline_segments:
        try:
            from . import drawing
            for c in drawing.find_circles(
                    [(tuple(a), tuple(b)) for a, b in outline_segments]):
                out.append(dict(c, node=None))
        except Exception:
            pass
    return out
