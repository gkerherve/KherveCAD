"""Open ARCS in the sketch (2026-10-29, the user: "I need to create arcs
incomplete ... a 3-point arc should show just the 3 points and an arc ...
a spline, a polyline, a tangent arc, a conic should all be unfinished
objects, just like a line, which we then can create regions from").

An arc is a ``line`` with a ``bulge`` — the DXF polyline's way of
storing one: ``bulge = tan(sweep / 4)``, positive when the arc turns
counter-clockwise from (x1, y1) to (x2, y2). 0 is the straight line, so
every line drawn before reads and writes as it did, and everything a
line already does — its two ends, Coincident, Fix, Smart Dimension,
trimming, closing areas with other edges for Regions — an arc does too.
Its third handle sits ON the arc and sets the bulge.

The code: ``kcad_arc(p1 = [...], p2 = [...], bulge = b, d = width);``,
a band along the arc with round ends, as a straight line is the hull of
two circles. The importer folds it back into the line.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

#: points per full turn along an arc (the preview and the helper)
STEPS_PER_TURN = 72
MIN_BULGE = 1e-9


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        from .expr import resolve
        return resolve(v, {}, default)


def bulge_of(params) -> float:
    return _num(params.get("bulge", 0.0))


def is_arc(node) -> bool:
    return node.type == "line" and abs(bulge_of(node.params)) > MIN_BULGE


def geometry(x1, y1, x2, y2, bulge):
    """(cx, cy, r, start angle, sweep) in radians — sweep signed, CCW
    positive — or None for a straight line."""
    if abs(bulge) <= MIN_BULGE:
        return None
    dx, dy = x2 - x1, y2 - y1
    chord = math.hypot(dx, dy)
    if chord < 1e-12:
        return None
    sweep = 4.0 * math.atan(bulge)
    r = chord / (2.0 * math.sin(abs(sweep) / 2.0))
    # centre: from the chord's middle along its left normal
    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    nx, ny = -dy / chord, dx / chord
    h = r * math.cos(sweep / 2.0)
    s = 1.0 if sweep > 0 else -1.0
    cx, cy = mx + nx * h * s, my + ny * h * s
    a0 = math.atan2(y1 - cy, x1 - cx)
    return cx, cy, r, a0, sweep


def points(x1, y1, x2, y2, bulge, steps=None):
    """The arc (or line) from end to end as a polyline."""
    g = geometry(x1, y1, x2, y2, bulge)
    if g is None:
        return [(x1, y1), (x2, y2)]
    cx, cy, r, a0, sweep = g
    n = steps or max(4, int(math.ceil(abs(sweep) / (2 * math.pi)
                                      * STEPS_PER_TURN)))
    out = [(cx + r * math.cos(a0 + sweep * i / n),
            cy + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]
    out[0], out[-1] = (x1, y1), (x2, y2)
    return out


def node_points(node, env=None, steps=None):
    p = node.params
    return points(_num(p["x1"]), _num(p["y1"]), _num(p["x2"]),
                  _num(p["y2"]), bulge_of(p), steps)


def middle(x1, y1, x2, y2, bulge):
    """The point halfway along the arc (the third handle)."""
    g = geometry(x1, y1, x2, y2, bulge)
    if g is None:
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
    cx, cy, r, a0, sweep = g
    a = a0 + sweep / 2.0
    return cx + r * math.cos(a), cy + r * math.sin(a)


def bulge_through(a, b, m):
    """The bulge of the arc from *a* to *b* through *m* (0 when the three
    lie on a line). The bulge's sagitta is signed by the side m is on."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    chord = math.hypot(dx, dy)
    if chord < 1e-12:
        return 0.0
    # circle through the three points
    d = 2 * (a[0] * (b[1] - m[1]) + b[0] * (m[1] - a[1])
             + m[0] * (a[1] - b[1]))
    if abs(d) < 1e-12:
        return 0.0
    a2, b2, m2 = (a[0] ** 2 + a[1] ** 2, b[0] ** 2 + b[1] ** 2,
                  m[0] ** 2 + m[1] ** 2)
    cx = (a2 * (b[1] - m[1]) + b2 * (m[1] - a[1]) + m2 * (a[1] - b[1])) / d
    cy = (a2 * (m[0] - b[0]) + b2 * (a[0] - m[0]) + m2 * (b[0] - a[0])) / d
    ang = [math.atan2(q[1] - cy, q[0] - cx) for q in (a, m, b)]
    ccw = (ang[2] - ang[0]) % (2 * math.pi)
    through = (ang[1] - ang[0]) % (2 * math.pi)
    sweep = ccw if through < ccw else ccw - 2 * math.pi
    return math.tan(sweep / 4.0)


def bulge_for_sweep(sweep_deg):
    return math.tan(math.radians(sweep_deg) / 4.0)


def band(pts, width):
    """The stroke's outline: both offsets of the polyline and round
    caps, counter-clockwise — what the helper draws."""
    h = width / 2.0
    if len(pts) < 2 or h <= 0:
        return []
    left, right = [], []
    for k, p in enumerate(pts):
        q0, q1 = pts[max(k - 1, 0)], pts[min(k + 1, len(pts) - 1)]
        d = (q1[0] - q0[0], q1[1] - q0[1])
        L = math.hypot(*d) or 1.0
        nx, ny = -d[1] / L * h, d[0] / L * h
        left.append((p[0] + nx, p[1] + ny))
        right.append((p[0] - nx, p[1] - ny))

    def cap(p, q, start):
        a = math.atan2(q[1] - p[1], q[0] - p[0])
        base = a + math.pi / 2 if start else a - math.pi / 2
        return [(p[0] + h * math.cos(base + math.pi * i / 8),
                 p[1] + h * math.sin(base + math.pi * i / 8))
                for i in range(1, 8)]
    out = (right + cap(pts[-1], pts[-2], False) + left[::-1]
           + cap(pts[0], pts[1], True))
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1)
               in zip(out, out[1:] + out[:1]))
    return out if area > 0 else out[::-1]


def outline(node, env=None):
    p = node.params
    return band(node_points(node, env), _num(p.get("width", 2.0), 2.0))


# ------------------------------------------------------------- codegen
HELPER = """\
module kcad_arc(p1 = [0, 0], p2 = [10, 0], bulge = 0, d = 2) {
    sw = 4 * atan(bulge);
    ch = norm(p2 - p1);
    r = ch / (2 * sin(abs(sw) / 2));
    m = (p1 + p2) / 2;
    n = [-(p2[1] - p1[1]), p2[0] - p1[0]] / ch;
    c = m + n * r * cos(sw / 2) * sign(sw);
    a0 = atan2(p1[1] - c[1], p1[0] - c[0]);
    k = max(4, ceil(abs(sw) / 360 * 72));
    pts = [for (i = [0 : k]) c + r * [cos(a0 + sw * i / k),
                                       sin(a0 + sw * i / k)]];
    for (i = [0 : k - 1]) hull() {
        translate(pts[i]) circle(d = d, $fn = 16);
        translate(pts[i + 1]) circle(d = d, $fn = 16);
    }
}"""


def uses(root):
    return any(is_arc(n) for n in root.walk())


def statement(node, fmt):
    p = node.params
    return (f"kcad_arc(p1 = [{fmt(p['x1'])}, {fmt(p['y1'])}], "
            f"p2 = [{fmt(p['x2'])}, {fmt(p['y2'])}], "
            f"bulge = {bulge_of(p):.10g}, d = {fmt(p['width'])})")


def _b_arc(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num as num

    def pair(v, default):
        if isinstance(v, list) and len(v) >= 2:
            return num(v[0]), num(v[1])
        return default
    a = pair(named.get("p1"), (0.0, 0.0))
    b = pair(named.get("p2"), (10.0, 0.0))
    return CadNode("line", "Arc", dict(
        x1=a[0], y1=a[1], x2=b[0], y2=b[1],
        width=num(named.get("d", 2.0), 2.0),
        bulge=num(named.get("bulge", 0.0))))


BUILDERS = {"kcad_arc": _b_arc}


# ------------------------------------------------- the drawing tools
def _r(v):
    return round(v, 4)


def arc_spec(a, b, bulge, name="Arc"):
    """One open arc (or straight line) from *a* to *b*, as a tool's
    build spec ("line", params, None)."""
    params = dict(x1=_r(a[0]), y1=_r(a[1]), x2=_r(b[0]), y2=_r(b[1]),
                  width=2.0)
    if abs(bulge) > MIN_BULGE:
        params["bulge"] = round(bulge, 10)
    return ("line", params, None)


def through(pts):
    """Open arcs through *pts* two spans at a time — p0 -> p2 through
    p1, p2 -> p4 through p3… — so every point given lies on the curve
    and the curve shows as a few arcs, not dozens of points."""
    if len(pts) < 2:
        return None
    if len(pts) == 2:
        return [arc_spec(pts[0], pts[1], 0.0)]
    if len(pts) % 2 == 0:                     # an even count: halve the
        a, b = pts[-2], pts[-1]               # last span with its middle
        pts = pts[:-1] + [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), b]
    return [arc_spec(pts[i], pts[i + 2],
                     bulge_through(pts[i], pts[i + 2], pts[i + 1]))
            for i in range(0, len(pts) - 2, 2)]


def catmull_open(pts, steps=2):
    """An OPEN Catmull-Rom curve through *pts* (ends doubled), *steps*
    points a span — what the spline tool draws."""
    if len(pts) < 3:
        return list(pts)
    ext = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[k] + (p2[k] - p0[k]) * t
                                    + (2 * p0[k] - 5 * p1[k] + 4 * p2[k]
                                       - p3[k]) * t2
                                    + (3 * p1[k] - p0[k] - 3 * p2[k]
                                       + p3[k]) * t3) for k in (0, 1)))
    out.append(tuple(pts[-1]))
    return out


def end_tangent(params):
    """Unit direction a line / arc is heading at its second end."""
    x1, y1 = _num(params["x1"]), _num(params["y1"])
    x2, y2 = _num(params["x2"]), _num(params["y2"])
    g = geometry(x1, y1, x2, y2, bulge_of(params))
    if g is None:
        L = math.hypot(x2 - x1, y2 - y1) or 1.0
        return ((x2 - x1) / L, (y2 - y1) / L)
    cx, cy, r, a0, sweep = g
    a1 = a0 + sweep
    s = 1.0 if sweep > 0 else -1.0
    return (-math.sin(a1) * s, math.cos(a1) * s)


def tangent_bulge(start, direction, end):
    """The bulge of the arc leaving *start* along *direction* to *end*:
    the sweep is twice the turn from the direction to the chord."""
    cx, cy = end[0] - start[0], end[1] - start[1]
    if math.hypot(cx, cy) < 1e-12:
        return 0.0
    turn = math.atan2(direction[0] * cy - direction[1] * cx,
                      direction[0] * cx + direction[1] * cy)
    return math.tan(2.0 * turn / 4.0)
