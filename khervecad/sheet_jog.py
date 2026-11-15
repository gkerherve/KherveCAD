"""The Jog feature of the SHEET METAL tab, and cut-outs (holes, slots) in
a sheet metal body (2026-11-15, Exercise "Jog Feature in SolidWorks Sheet
Metal").

A jog is two opposite bends made from ONE sketched line: the sheet is cut
at the line, the side that stays FIXED keeps its place, the other side is
raised (or lowered) by an offset through a sloped web and two bends,
ending parallel to the fixed side. Like SolidWorks' Jog it ADDS material:
the flat blank is the original plate with the web (bend, web, bend) put
in where it was cut.

A row of `jogs`: [x1, y1, x2, y2, offset, angle, radius, dim, pos, side,
dir] — the sketch line, the jog offset (mm), the web's angle with the
fixed face (degrees), the bend radius (0 = the body's), the dimension
position (0 outside: outer face to outer face of the two flats, 1 inside:
inner to inner, 2 total: outside to outside counting the thickness), the
jog position (0 bend centre line, 1 material inside, 2 material outside,
3 bend outside — where the line falls on the first bend), which side of
the line (looking from its first point to its second: 1 left, -1 right)
stays fixed, and the direction (1 up, toward the sheet's top, -1 down).

`holes` [x, y, diameter] and `slots` [x1, y1, x2, y2, width] are in the
flat plate's own coordinates (before any jog) and follow the panel they
lie on.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

JOG_TAG = "jog"
DIM_MODES = ("outside", "inside", "total")
POSITIONS = ("bend centre line", "material inside", "material outside",
             "bend outside")
CIRCLE_SIDES = 32


def plan(offset, angle, radius, t, dim=0, pos=3):
    """The jog's numbers: (rise of the mid surface, web length, x extent
    of the jog on the sheet, start of the first bend relative to the
    line along the moving direction, error or None)."""
    th = math.radians(abs(angle))
    if not 0 < abs(angle) < 90:
        return 0.0, 0.0, 0.0, 0.0, "the jog angle must be between 0 and 90"
    rm = radius + t / 2
    rise = {0: offset, 1: offset + t, 2: offset - t}.get(int(dim), offset)
    web = (rise - 2 * rm * (1 - math.cos(th))) / math.sin(th)
    if rise <= 0 or web <= 1e-6:
        return rise, web, 0.0, 0.0, ("the offset is too small for two "
                                     f"bends of radius {radius:g}")
    extent = 2 * rm * math.sin(th) + web * math.cos(th)
    half = math.tan(th / 2)
    start = {0: -extent / 2, 1: -radius * half,
             2: -(radius + t) * half}.get(int(pos), 0.0)
    return rise, web, extent, start, None


def _hole_loop(x, y, d, sides=CIRCLE_SIDES):
    r = d / 2
    return [(x + r * math.cos(2 * math.pi * i / sides),
             y + r * math.sin(2 * math.pi * i / sides))
            for i in range(sides)]


def slot_loop(p, q, w, sides=12):
    """A capsule: the segment p-q, width w (a polygon, CCW)."""
    r = w / 2
    ang = math.atan2(q[1] - p[1], q[0] - p[0])
    out = []
    for i in range(sides + 1):
        a = ang - math.pi / 2 + math.pi * i / sides
        out.append((q[0] + r * math.cos(a), q[1] + r * math.sin(a)))
    for i in range(sides + 1):
        a = ang + math.pi / 2 + math.pi * i / sides
        out.append((p[0] + r * math.cos(a), p[1] + r * math.sin(a)))
    return out


def inside(poly, q):
    hit = False
    n = len(poly)
    for i in range(n):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
        if (ay > q[1]) != (by > q[1]) and \
                q[0] < ax + (q[1] - ay) * (bx - ax) / (by - ay):
            hit = not hit
    return hit


class Cut:
    """Where a cut-out of the design (flat plate) coordinates lands: one
    panel, with the map from design to panel coordinates."""

    def __init__(self, panel, to_panel, member):
        self.panel, self.to_panel, self.member = panel, to_panel, member


def jogs(body, base, rows, t, k, r0, sb):
    """Cut the base at every jog line and return (fixed polygon + tags,
    pieces) — *sb* is the sheet_body module (its panels, clip and
    bend_child are used from here, not imported at the top)."""
    out = []
    for j, row in enumerate(rows):
        row = list(row) + [0.0] * (11 - len(row))
        x1, y1, x2, y2, offset, angle, radius, dim, pos, side, direction \
            = row[:11]
        radius = radius if radius > 0 else r0
        d = (x2 - x1, y2 - y1)
        ln = math.hypot(*d)
        if ln < 1e-9:
            body.errors.append(f"jog {j + 1}: its line has no length")
            continue
        rise, web, extent, start_d, err = plan(offset, angle, radius, t,
                                               dim, pos)
        if err:
            body.errors.append(f"jog {j + 1}: {err}")
            continue
        left = (-d[1] / ln, d[0] / ln)
        keep_n = left if side >= 0 else (-left[0], -left[1])
        m = (-keep_n[0], -keep_n[1])                 # toward the moving side
        start = (x1 + m[0] * start_d, y1 + m[1] * start_d)
        tag = JOG_TAG + str(j)
        fixed, ftags = sb.clip(base.poly, base.tags, start, keep_n, tag)
        far, _ft = sb.clip(base.poly, base.tags, start, m, tag)
        if len(fixed) < 3 or len(far) < 3:
            body.errors.append(f"jog {j + 1}: its line misses the sheet "
                               "or leaves nothing on one side")
            continue
        base.poly, base.tags = fixed, ftags
        out.append(dict(j=j, row=row, radius=radius, web=web, extent=extent,
                        start=start, keep_n=keep_n, m=m, far=far,
                        sign=1.0 if direction >= 0 else -1.0,
                        theta=abs(angle)))
    return out


def panels(body, base, pieces, t, k, sb):
    """The web and the far panel of every jog, and its two bends."""
    for jg in pieces:
        j, start, keep_n, m = jg["j"], jg["start"], jg["keep_n"], jg["m"]
        th, r, sign = jg["theta"], jg["radius"], jg["sign"]
        e2 = (keep_n[1], -keep_n[0])
        found = base.edge(JOG_TAG + str(j))
        if found is None:
            continue
        ea, eb, _ln = found
        da = (ea[0] - start[0]) * e2[0] + (ea[1] - start[1]) * e2[1]
        db = (eb[0] - start[0]) * e2[0] + (eb[1] - start[1]) * e2[1]
        lo, hi = min(da, db), max(da, db)
        for q in jg["far"]:                       # the far side may be wider
            al = (q[0] - start[0]) * e2[0] + (q[1] - start[1]) * e2[1]
            lo, hi = min(lo, al), max(hi, al)
        a = start
        b = (start[0] + e2[0], start[1] + e2[1])
        ba = sb._allowance(th, r, t, k)
        frame, fe, fw, fa, axis, e, w = sb.bend_child(
            base, a, b, sign * th, r, t)
        flat_o = (fa[0] + fw[0] * ba, fa[1] + fw[1] * ba)
        web_len = jg["web"]
        tags = [JOG_TAG + "w" + str(j)] * 4
        web = sb.Panel([(-hi, 0.0), (-lo, 0.0), (-lo, web_len),
                        (-hi, web_len)], tags, frame,
                       (flat_o, (-fe[0], -fe[1]), fw))
        body.extra.append(web)
        body.bends.append(dict(
            kind="jog", parent=0, edge=JOG_TAG + str(j), angle=sign * th,
            radius=r, length=hi - lo, allowance=ba, frame=base.frame, e=e,
            w=w, axis=axis, a=sb._add(base.frame.at(a), sb._mul(e, lo)),
            span=hi - lo, flat=(fa, fe, fw, lo, hi)))
        # second bend: off the web's far edge, the other way
        a2, b2 = (-lo, web_len), (-hi, web_len)
        frame2, fe2, fw2, fa2, axis2, e_2, w_2 = sb.bend_child(
            web, a2, b2, -sign * th, r, t)
        flat_o2 = (fa2[0] + fw2[0] * ba, fa2[1] + fw2[1] * ba)
        poly = []
        for q in jg["far"]:
            dx, dy = q[0] - start[0], q[1] - start[1]
            along = dx * e2[0] + dy * e2[1]
            out = dx * m[0] + dy * m[1]
            poly.append((-(along - lo), max(out, 0.0)))
        if sb._area2(poly) < 0:
            poly.reverse()
        far = sb.Panel(poly, [JOG_TAG + "f" + str(j)] * len(poly), frame2,
                       (flat_o2, (-fe2[0], -fe2[1]), fw2))
        body.extra.append(far)
        body.bends.append(dict(
            kind="jog", parent=0, edge=JOG_TAG + "b" + str(j),
            angle=-sign * th, radius=r, length=hi - lo, allowance=ba,
            frame=web.frame, e=e_2, w=w_2,
            axis=axis2, a=sb._add(web.frame.at(a2), (0.0, 0.0, 0.0)),
            span=hi - lo, flat=(fa2, fe2, fw2, 0.0, hi - lo)))
        jg["web_panel"], jg["far_panel"] = web, far
        jg["lo"], jg["e2"] = lo, e2


def place_cuts(body, base, pieces, holes, slots, sb):
    """Put every hole and slot (design coordinates) on its panel as a
    loop in panel coordinates; one that lies across a cut or outside
    the sheet is an error."""
    targets = []
    for jg in pieces[:1]:
        start, m, e2, lo = jg["start"], jg["m"], jg["e2"], jg["lo"]
        far = jg["far_panel"]

        def to_far(q, start=start, m=m, e2=e2, lo=lo):
            dx, dy = q[0] - start[0], q[1] - start[1]
            return (-((dx * e2[0] + dy * e2[1]) - lo),
                    dx * m[0] + dy * m[1])
        targets.append((far, to_far,
                        lambda q, s=start, mm=m:
                        (q[0] - s[0]) * mm[0] + (q[1] - s[1]) * mm[1] > 0))
    targets.append((base, lambda q: q, lambda q: True))

    def where(points):
        for panel, to_panel, member in targets:
            if all(member(q) for q in points):
                loops = [to_panel(q) for q in points]
                if all(inside(panel.poly, q) for q in loops):
                    return panel, to_panel
        return None, None

    for i, row in enumerate(holes):
        x, y, dia = row[:3]
        loop = _hole_loop(x, y, dia)
        panel, to_panel = where(loop)
        if panel is None:
            body.errors.append(f"hole {i + 1}: it lies off the sheet or "
                               "across a bend or a cut")
            continue
        panel.cuts.append([to_panel(q) for q in loop])
    for i, row in enumerate(slots):
        loop = slot_loop((row[0], row[1]), (row[2], row[3]), row[4])
        panel, to_panel = where(loop)
        if panel is None:
            body.errors.append(f"slot {i + 1}: it lies off the sheet or "
                               "across a bend or a cut")
            continue
        panel.cuts.append([to_panel(q) for q in loop])
