"""Dressing a `car_body.Body` (Qt-free): glass and pillars, wheel
wells, shut lines, sills, the face (lamps, grille, intakes, plate), the
tail, mirrors, wings and exhausts.

Everything sits ON the body: regions of the body's own surface
(`Body.patch`) or outlines projected onto it (`Body.decal`), a few
millimetres proud, so lamps and grilles follow the curve of the nose
they are set in.

A face item is a dict, placed in the FACE BOX — the front (or rear) of
the body seen head on: ``u`` across, as a fraction of the half width
there, ``v`` up, as a fraction from the bottom of the face to its top.
``view: "top"`` lays an item on the bonnet instead (``v`` is then the
station, a fraction of the length). Kinds:

- ``lamp`` — ``shape`` round (``r`` mm) or rect (``w``, ``h``, ``rad``,
  ``slant`` mm) or poly (``pts`` in face fractions), a housing (``rim``
  colour) and a lens (``colour``); ``inner`` adds a projector;
- ``panel`` — a flat piece of ``colour`` (an intake, a grille), with
  ``slats`` bars ``dir`` "h" / "v" / "mesh" in ``slat_colour``;
- ``plate`` — a number plate; ``badge`` — a round badge (``r``).

``mirror`` (default True for anything off the centre line) repeats an
item on the other side.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .car_body import ellipse, polygon, rounded_rect

GLASS = "#10161d"
TRIM = "#1b1c1f"
WELL = "#0d0e10"
CHROME = "#d9dde2"
LAMP = "#eef3f7"
LENS = "#c9d3dc"
AMBER = "#e8901e"
TAIL = "#b8101a"
TAIL_DARK = "#5c0a0f"
PLATE = "#f2f2ee"
INK = "#2a2c30"
MESH = "#121315"


def dress(kit, car, paint):
    glass(kit, car)
    wells(kit, car)
    sides(kit, car)
    front(kit, car)
    rear(kit, car)
    mirrors(kit, car, paint)
    wing(kit, car, paint)
    exhausts(kit, car)


# ------------------------------------------------------------- glass

def glass(kit, car):
    b, d = car.body, car.d
    if d["open"]:
        cockpit(kit, car)
        return
    g = kit.mesh(GLASS, "Plastic")
    frame = kit.mesh(CHROME if d["bumpers"] == "chrome" else TRIM,
                     "Metal" if d["bumpers"] == "chrome" else "Plastic")
    c, m = b.col, b.m
    rf, rr = d["roof"]
    cs, _ = d["cowl"]
    ds, _ = d["deck"]
    edge = c["roof"] - 1            # the roof rail
    # windscreen and rear glass, between their pillars
    b.patch(g, cs + 0.004, rf - 0.004, edge + 1.1, m - edge - 1.1, out=2.5)
    if d["rear_glass"]:
        b.patch(g, rr + 0.010, ds - 0.006, edge + 1.6, m - edge - 1.6,
                out=2.5)
    if d["engine_cover"]:
        louvres(kit, car, rr + 0.012 if not d["rear_glass"] else ds + 0.01,
                d["engine_cover_to"])
    # side glass: a frame, then the glass inside it
    q = d["quarter"] or ds - 0.02
    s0 = cs + d["pillar"]
    lo, hi = c["glass"] + 0.55, edge - 0.30
    if d["open"]:
        return
    b.mirror_patch(frame, s0 - 0.006, q + 0.006, lo - 0.25, hi + 0.22,
                   out=1.5)
    bp = d["b_pillar"]
    if bp:
        w = 0.012
        b.mirror_patch(g, s0, bp - w / 2, lo, hi, out=2.6)
        b.mirror_patch(g, bp + w / 2, q, lo, hi, out=2.6)
        if not d["black_pillars"]:
            pass
    else:
        b.mirror_patch(g, s0, q, lo, hi, out=2.6)


def louvres(kit, car, s0, s1):
    """A slatted engine cover over the deck: dark vents between
    body-coloured slats running across the car."""
    b, d = car.body, car.d
    c, m = b.col, b.m
    j0 = c["roof"] + 0.8
    b.patch(kit.mesh(MESH, "Matte"), s0, s1, j0, m - j0, out=1.5,
            inside=2.0)
    n = max(4, int((s1 - s0) * b.L / 70))
    slat = kit.mesh(car.paint(), "Plastic")
    for k in range(n):
        s = s0 + (s1 - s0) * (k + 0.5) / n
        w = 0.32 * (s1 - s0) / n
        b.patch(slat, s - w, s + w, j0 + 0.2, m - j0 - 0.2, out=6.0,
                inside=2.0)


def cockpit(kit, car):
    """An open car: a dark cockpit in the top, two seats, a steering
    wheel and a raked windscreen in a chrome frame."""
    b, d = car.body, car.d
    c, m = b.col, b.m
    cs = d["cowl"][0]
    ce = d["cockpit_to"]
    inner = kit.mesh(d["interior"], "Matte")
    b.patch(inner, cs + 0.01, ce, c["glass"] + 1.2, m - c["glass"] - 1.2,
            out=1.5, inside=2.0)
    # seats
    for side in (-1, 1):
        x = side * b.W * 0.20
        s1 = ce - 0.03
        y1 = b.y(s1)
        z0 = float(b.point(b.station_index(s1), c["top"])[2])
        pts = []
        for k in range(12):
            t = 2 * math.pi * k / 12
            for dz, sc in ((-150, 1.0), (0, 1.0), (330, 0.85), (420, 0.6)):
                pts.append((x + 230 * math.cos(t) * sc,
                            y1 - 60 + 55 * math.sin(t) * sc, z0 + dz))
        kit.solid(pts, d["interior_seat"], "Matte")
    # steering wheel
    sw = b.y(cs + 0.05)
    zc = float(b.point(b.station_index(cs + 0.02), c["top"])[2])
    xw = -b.W * 0.20
    ring = [(xw + 190 * math.cos(2 * math.pi * k / 24), sw + 40,
             zc + 40 + 190 * math.sin(2 * math.pi * k / 24) * 0.9)
            for k in range(25)]
    kit.path(ring, 12, TRIM, "Plastic", sides=8)
    # windscreen
    s0 = cs + 0.004
    i0 = b.station_index(s0)
    a = float(b.point(i0, c["glass"])[0]) * 0.92
    z0 = float(b.point(i0, c["top"])[2])
    y0 = b.y(s0)
    h = d["screen_h"]
    rake = math.radians(d["screen_rake"])
    dy, dz = h * math.sin(rake), h * math.cos(rake)
    pts = []
    for k in range(13):
        x = -a + 2 * a * k / 12
        bend = 60 * (x / a) ** 2
        pts.append((x, y0 + bend, z0))
    top = [(x * 0.94, y + dy, z0 + dz) for x, y, _ in pts]
    glass_m = kit.mesh(GLASS, "Glass")
    rings = [[p, (p[0], p[1] + 6, p[2]), (q[0], q[1] + 6, q[2]), q]
             for p, q in zip(pts, top)]
    from .car_wheels import closed_grid
    closed_grid(glass_m, rings, wrap_points=True)
    kit.path(top, 9, CHROME, "Metal", sides=8)
    kit.path([pts[0], top[0]], 11, CHROME, "Metal", sides=8)
    kit.path([pts[-1], top[-1]], 11, CHROME, "Metal", sides=8)


def wells(kit, car):
    b = car.body
    w = kit.mesh(WELL, "Matte")
    for i, sa in enumerate(b.s_axle):
        R = (b.wheels[i][2] / 2 + b.d["arch_gap"]) / b.L
        b.mirror_patch(w, sa - R - 0.004, sa + R + 0.004, 1.0,
                       b.col["flank"] - 0.15, out=1.2, inside=2.0)
    # the underside, dark from end to end so the car sits on its shadow
    edge = b.col["well"] + 2.5
    b.patch(w, 0.015, 0.985, -edge, edge, out=1.0, inside=2.0, nj=8,
            ns=60)


def sides(kit, car):
    """Shut lines of the doors and a dark sill or side skirt."""
    b, d = car.body, car.d
    line = kit.mesh(TRIM, "Matte")
    c = b.col
    doors = d["doors"]
    if doors is None:
        cs = d["cowl"][0]
        doors = (cs + 0.02, (d["b_pillar"] or d["roof"][1]) + 0.01)
    w = 5.0 / b.L
    lo = c["flank"] + 0.6
    hi = c["glass"] + 0.3
    for s in doors:
        b.mirror_patch(line, s - w / 2, s + w / 2, lo, hi, out=0.8,
                       inside=1.5, nj=8)
    # bottom of the door
    b.mirror_patch(line, doors[0], doors[-1], lo - 0.05, lo + 0.18, out=0.8,
                   inside=1.5)
    # door handle
    s = doors[-1] - 0.035
    hz = c["shoulder"] - 0.6
    b.mirror_patch(kit.mesh(CHROME if d["bumpers"] == "chrome" else TRIM,
                            "Metal"), s - 110 / b.L, s, hz - 0.5, hz,
                   out=4.0, inside=2.0)
    if d["sill"] and d.get("skirt"):
        b.mirror_patch(kit.mesh(TRIM, "Matte"), b.s_axle[0] + 0.07,
                       b.s_axle[1] - 0.07, c["well"] + 3, c["flank"] + 0.3,
                       out=1.5, inside=2.0)
    # a side intake ahead of the rear wheel (mid-engined cars)
    kind = d["side_intake"]
    if kind:
        sa = b.s_axle[1]
        R = b.wheels[1][2] / 2 / b.L
        s1 = sa - R - 0.02
        s0 = s1 - (0.10 if kind == "strakes" else 0.07)
        if d["scallop"] and kind == "scoop":
            # the intake is the deep end of the cove
            s1 = d["scallop"][1] + 0.012
            s0 = s1 - 0.035
        j0, j1 = c["flank"] + 2.0, c["shoulder"] + (1.0 if kind == "strakes"
                                                     else 0.0)
        if kind == "naca":
            j0, j1 = c["shoulder"] + 0.5, c["glass"] + 0.3
        b.mirror_patch(kit.mesh(MESH, "Matte"), s0, s1,
                       lambda s: j0 + (s1 - s) / (s1 - s0) * 0.8, j1,
                       out=1.5, inside=2.0)
        if kind == "strakes":
            n = 5
            for k in range(n):
                jj = j0 + 0.4 + (j1 - j0 - 0.6) * (k + 0.5) / n
                b.mirror_patch(kit.mesh(car.paint(), "Plastic"),
                               s0 - 0.005, s1 + 0.004, jj - 0.12, jj + 0.12,
                               out=6.0, inside=2.0, nj=2)


# ------------------------------------------------------------ the face

def face_box(b, front=True, s=None):
    """(half width, bottom z, top z, station) of the face."""
    s = s if s is not None else (0.035 if front else 0.965)
    ring = b.ring(s)
    xs = [p[0] for p in ring]
    a = max(xs)
    zb = min(p[2] for p in ring)
    zt = max(p[2] for p in ring if abs(p[0]) < 0.65 * a)
    return a, zb, zt, s


def _outline(item, a, zb, zt, flip=1.0):
    """The item's outline in projection coordinates (mm)."""
    span = zt - zb
    u = flip * item.get("u", 0.0) * a
    v = zb + item.get("v", 0.5) * span
    shape = item.get("shape", "rect")
    if shape == "round":
        r = item["r"]
        return ellipse(u, v, r * item.get("sx", 1.0), r, 28)
    if shape == "poly":
        pts = [(flip * pu * a, zb + pv * span) for pu, pv in item["pts"]]
        return polygon(pts, 4)
    return rounded_rect(u, v, item["w"], item["h"], item.get("rad", 20),
                        slant=flip * item.get("slant", 0.0))


def _top_outline(item, b, flip=1.0):
    a = b.W / 2
    u = flip * item.get("u", 0.0) * a
    v = b.y(item["v"])
    shape = item.get("shape", "rect")
    if shape == "round":
        return ellipse(u, v, item["r"], item["r"] * item.get("sy", 1.0), 28)
    if shape == "poly":
        return polygon([(flip * pu * a, b.y(pv)) for pu, pv in item["pts"]],
                       4)
    return rounded_rect(u, v, item["w"], item["h"], item.get("rad", 20),
                        slant=flip * item.get("slant", 0.0))


def _grow(outline, by):
    cu = sum(p[0] for p in outline) / len(outline)
    cv = sum(p[1] for p in outline) / len(outline)
    out = []
    for u, v in outline:
        du, dv = u - cu, v - cv
        ln = math.hypot(du, dv) or 1.0
        out.append((u + du / ln * by, v + dv / ln * by))
    return out


def place(kit, b, items, front=True):
    a, zb, zt, _s = face_box(b, front)
    view = "front" if front else "rear"
    for item in items:
        flips = [1.0]
        if item.get("mirror", abs(item.get("u", 0.0)) > 1e-6 or
                    item.get("shape") == "poly"):
            if item.get("u", 0.0) != 0.0 or item.get("shape") == "poly":
                flips = [1.0, -1.0]
        for flip in flips:
            if item.get("view") == "nose":
                ol, v = _nose_outline(item, b, front, flip)
                if ol is None:
                    continue
            elif item.get("view") == "top":
                ol = _top_outline(item, b, flip)
                v = "top"
            else:
                ol = _outline(item, a, zb, zt, flip)
                v = view
            if v == "rear":
                ol = ol[::-1]
            _item(kit, b, item, ol, v)


def _nose_outline(item, b, front, flip):
    """An item on the rounded corner of the nose (or tail), placed by
    station ``s`` (from its own end) and ``u`` (of the half width there)
    and seen from ``tilt`` degrees above the horizon."""
    s = item["s"] if front else 1.0 - item["s"]
    x = flip * item.get("u", 0.0) * b.half_width(s)
    far = 4 * (b.L + b.H)
    hit = b.cast([(x, b.y(s), far)], (0.0, 0.0, -1.0))[0]
    if hit != hit:
        return None, None
    z = far - hit
    tilt = item.get("tilt", 35.0)
    _dvec, ev = b.oblique(tilt, front)
    cu = x
    cv = ev[1] * b.y(s) + ev[2] * z
    shape = item.get("shape", "rect")
    if shape == "round":
        ol = ellipse(cu, cv, item["r"] * item.get("sx", 1.0), item["r"], 28)
    else:
        ol = rounded_rect(cu, cv, item["w"], item["h"], item.get("rad", 20),
                          slant=flip * item.get("slant", 0.0))
    if not front:
        ol = ol[::-1]
    return ol, (tilt, front)


def _item(kit, b, item, ol, view):
    kind = item.get("k", "lamp")
    lift = item.get("lift", 0.0)
    if kind == "lamp":
        rim = item.get("rim", TRIM)
        if rim:
            b.decal(kit.mesh(rim, "Metal" if rim == CHROME else "Plastic"),
                    _grow(ol, item.get("rim_w", 10)), view, out=2.5 + lift)
        colour = item.get("colour", LAMP)
        b.decal(kit.mesh(colour, "Emissive" if item.get("glow") else
                         "Plastic"), ol, view, out=4.5 + lift)
        inner = item.get("inner")
        if inner:
            cu = sum(p[0] for p in ol) / len(ol)
            cv = sum(p[1] for p in ol) / len(ol)
            for du in inner:
                b.decal(kit.mesh(LAMP, "Emissive"),
                        ellipse(cu + du, cv, item.get("inner_r", 28),
                                item.get("inner_r", 28), 20), view,
                        out=6.5 + lift)
    elif kind == "panel":
        colour = item.get("colour", MESH)
        material = item.get("material", "Matte")
        frame = item.get("frame")
        if frame:
            b.decal(kit.mesh(frame, "Metal" if frame == CHROME else
                             "Plastic"), _grow(ol, item.get("frame_w", 12)),
                    view, out=2.0 + lift)
        b.decal(kit.mesh(colour, material), ol, view, out=3.5 + lift)
        n = item.get("slats", 0)
        if n:
            _slats(kit, b, ol, view, n, item.get("dir", "h"),
                   item.get("slat_colour", frame or TRIM), lift)
    elif kind == "plate":
        b.decal(kit.mesh(INK, "Matte"), _grow(ol, 10), view, out=2.5 + lift)
        b.decal(kit.mesh(PLATE, "Matte"), ol, view, out=4.0 + lift)
    elif kind == "badge":
        b.decal(kit.mesh(item.get("colour", CHROME), "Metal"), ol, view,
                out=5.0 + lift)


def _slats(kit, b, ol, view, n, direction, colour, lift):
    us = [p[0] for p in ol]
    vs = [p[1] for p in ol]
    u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
    mesh = kit.mesh(colour, "Metal" if colour == CHROME else "Plastic")
    dirs = ("h", "v") if direction == "mesh" else (direction,)
    for dd in dirs:
        for k in range(n):
            t = (k + 0.5) / n
            if dd == "h":
                v = v0 + (v1 - v0) * t
                th = max(5.0, (v1 - v0) / n * 0.32)
                w = (u1 - u0) * _span_at(ol, v, axis=1) * 0.94
                cu = _mid_at(ol, v, axis=1)
                shape = rounded_rect(cu, v, w, th, 2, n=2)
            else:
                u = u0 + (u1 - u0) * t
                tw = max(5.0, (u1 - u0) / n * 0.30)
                h = (v1 - v0) * _span_at(ol, u, axis=0) * 0.92
                cv = _mid_at(ol, u, axis=0)
                shape = rounded_rect(u, cv, tw, h, 2, n=2)
            if min(shape[0][0], shape[0][1]) is not None:
                b.decal(mesh, shape, view, out=5.0 + lift, rings=1)


def _chord(ol, c, axis):
    """Where the line (u or v) = c crosses the outline."""
    hits = []
    n = len(ol)
    for k in range(n):
        p, q = ol[k], ol[(k + 1) % n]
        a, bb = p[axis], q[axis]
        if (a - c) * (bb - c) <= 0 and a != bb:
            t = (c - a) / (bb - a)
            hits.append(p[1 - axis] + (q[1 - axis] - p[1 - axis]) * t)
    return (min(hits), max(hits)) if hits else (0.0, 0.0)


def _span_at(ol, c, axis):
    lo, hi = _chord(ol, c, axis)
    others = [p[1 - axis] for p in ol]
    full = max(others) - min(others)
    return (hi - lo) / full if full else 0.0


def _mid_at(ol, c, axis):
    lo, hi = _chord(ol, c, axis)
    return (lo + hi) / 2


# ---------------------------------------------------- generic faces

def default_face(car):
    """A face from the catalogue's light / grille kinds, placed by the
    design's ``lamp_*`` / ``grille_*`` / ``plate_v`` numbers."""
    spec, d, W = car.spec, car.d, car.body.W
    a, zb, zt, _s = face_box(car.body, True)
    span = zt - zb
    lu, lv, ls = d["lamp_u"], d["lamp_v"], d["lamp_scale"]
    out = []
    lights = d["lights"] or spec["lights"]
    if lights == "round":
        r = min(0.085 * W, 0.24 * span, 90.0) * ls
        out.append(dict(k="lamp", shape="round", u=lu, v=lv, r=r,
                        rim=CHROME, rim_w=12, colour=LENS, inner=[0],
                        inner_r=r * 0.45))
    elif lights == "twin":
        r = min(0.05 * W, 0.17 * span, 68.0) * ls
        for u in (lu, lu - 2.4 * r / a):
            out.append(dict(k="lamp", shape="round", u=u, v=lv, r=r,
                            rim=CHROME, colour=LENS, inner=[0],
                            inner_r=r * 0.45))
    elif lights == "slim" and d["lamp_view"] == "nose":
        w, h = 0.36 * a * ls, max(80.0, 0.14 * span) * ls
        out.append(dict(k="lamp", view="nose", s=d["lamp_s"], u=lu,
                        tilt=d["lamp_tilt"], w=w, h=h, rad=0.45 * h,
                        slant=d["lamp_slant"] * a, rim=TRIM, rim_w=8,
                        colour=LENS, inner=[-0.22 * w, 0.0, 0.22 * w],
                        inner_r=0.22 * h))
    elif lights == "slim":
        w, h = 0.40 * a * ls, 0.13 * span * ls
        out.append(dict(k="lamp", shape="rect", u=lu, v=lv, w=w, h=h,
                        rad=0.3 * h, slant=d["lamp_slant"] * a, rim=TRIM,
                        rim_w=8, colour=LENS,
                        inner=[-0.22 * w, 0.0, 0.22 * w], inner_r=0.22 * h))
    elif lights == "popup":
        out.append(dict(k="panel", view="top", u=0.60, v=d["popup_s"],
                        w=0.34 * a, h=0.05 * car.body.L, rad=10,
                        colour=car.paint(), material="Plastic",
                        frame=TRIM, frame_w=4))
        out.append(dict(k="lamp", shape="rect", u=lu, v=lv,
                        w=0.30 * a, h=0.10 * span, rad=10, rim=TRIM,
                        colour=LENS))
    # indicators
    if lights in ("round", "twin") and d["indicators"]:
        out.append(dict(k="lamp", shape="rect", u=lu + 0.04,
                        v=d["indicator_v"], w=0.15 * a, h=0.07 * span,
                        rad=10, rim=CHROME, rim_w=5, colour=AMBER))
    grille = d["grille"] or spec["grille"]
    gv = d["grille_v"]
    if grille == "kidney":
        out.append(dict(k="panel", u=0.12, v=gv, w=0.19 * a,
                        h=0.36 * span, rad=0.07 * a, colour=MESH,
                        frame=CHROME, slats=6, dir="v",
                        slat_colour=CHROME))
    elif grille == "star":
        out.append(dict(k="panel", u=0.0, v=gv, w=d["grille_w"] * a,
                        h=0.34 * span, rad=0.05 * a, colour=MESH,
                        frame=CHROME, slats=4, dir="h", slat_colour=CHROME))
        out.append(dict(k="badge", shape="round", u=0.0, v=gv,
                        r=min(0.09 * span, 60.0), mirror=False, lift=2))
    elif grille == "horseshoe":
        out.append(dict(k="panel", shape="poly", mirror=False, pts=[
            (-0.19, gv - 0.26), (0.19, gv - 0.26), (0.21, gv + 0.02),
            (0.16, gv + 0.18), (0.0, gv + 0.24), (-0.16, gv + 0.18),
            (-0.21, gv + 0.02)], colour=MESH, frame=CHROME, frame_w=14,
            slats=6, dir="mesh", slat_colour="#3a3d42"))
    elif grille == "oval":
        out.append(dict(k="panel", shape="round", u=0.0, v=gv,
                        r=0.24 * span, sx=d["grille_w"] * a / (0.24 * span),
                        colour=MESH, frame=CHROME, slats=5, dir="h",
                        slat_colour=CHROME, mirror=False))
    elif grille == "aston":
        out.append(dict(k="panel", shape="poly", mirror=False, pts=[
            (-0.24, gv - 0.16), (0.24, gv - 0.16), (0.27, gv + 0.02),
            (0.16, gv + 0.16), (-0.16, gv + 0.16), (-0.27, gv + 0.02)],
            colour=MESH, frame=CHROME, frame_w=12, slats=5, dir="v",
            slat_colour=CHROME))
    elif grille == "audi":
        out.append(dict(k="panel", shape="poly", mirror=False, pts=[
            (-0.26, gv - 0.22), (0.26, gv - 0.22), (0.34, gv + 0.06),
            (0.30, gv + 0.18), (-0.30, gv + 0.18), (-0.34, gv + 0.06)],
            colour=MESH, frame="#8a8d92", frame_w=8, slats=4, dir="mesh",
            slat_colour="#2e3034"))
        out.append(dict(k="badge", shape="round", u=0.0, v=gv + 0.11,
                        r=0.03 * span, mirror=False, lift=3))
    elif grille == "intake":
        out.append(dict(k="panel", u=0.0, v=gv, w=d["grille_w"] * a,
                        h=0.24 * span, rad=0.10 * span, colour=MESH,
                        slats=3, dir="h", slat_colour="#2e3034"))
    for u, v, w, h in d["intakes"]:
        out.append(dict(k="panel", u=u, v=v, w=w * a, h=h * span,
                        rad=0.04 * span, colour=MESH, slats=3, dir="h",
                        slat_colour="#2e3034"))
    if d["lower_intake"]:
        out.append(dict(k="panel", u=0.0, v=0.14, w=d["lower_intake"] * a,
                        h=0.12 * span, rad=0.05 * span, colour=MESH,
                        slats=2, dir="h"))
    if d["plate_v"] is not None:
        out.append(dict(k="plate", u=0.0, v=d["plate_v"],
                        w=min(520.0, 0.95 * a), h=110.0, rad=8))
    return out + list(d["face_extra"])


def default_tail(car):
    spec, d, W = car.spec, car.d, car.body.W
    a, zb, zt, _s = face_box(car.body, False)
    span = zt - zb
    out = []
    kind = d["tails"] or spec["tails"]
    tu, tv, ts = d["tail_u"], d["tail_v"], d["tail_scale"]
    if kind == "round":
        r = min(0.05 * W, 0.16 * span, 62.0) * ts
        for u in (tu, tu - 2.5 * r / a):
            out.append(dict(k="lamp", shape="round", u=u, v=tv, r=r,
                            rim=TRIM, rim_w=8, colour=TAIL, glow=True,
                            inner=[0], inner_r=r * 0.35))
    elif kind == "slim":
        h = 0.13 * span * ts
        out.append(dict(k="lamp", shape="rect", u=tu, v=tv,
                        w=0.44 * a * ts, h=h, rad=0.35 * h,
                        slant=-0.04 * a, rim=TRIM, rim_w=8, colour=TAIL,
                        glow=True))
    elif kind == "vertical":
        out.append(dict(k="lamp", shape="rect", u=tu, v=tv,
                        w=0.16 * a * ts, h=0.36 * span * ts, rad=20,
                        rim=CHROME, colour=TAIL, glow=True))
    else:                                           # a full-width bar
        out.append(dict(k="lamp", shape="rect", u=0.0, v=tv,
                        w=1.80 * a * tu, h=0.11 * span * ts,
                        rad=0.04 * span, rim=TRIM, colour=TAIL, glow=True,
                        mirror=False))
    if d["rear_plate_v"] is not None:
        out.append(dict(k="plate", u=0.0, v=d["rear_plate_v"],
                        w=min(520.0, 0.95 * a), h=110.0, rad=8))
    if d["diffuser"]:
        out.append(dict(k="panel", u=0.0, v=0.15, w=d["diffuser"] * a,
                        h=0.20 * span, rad=0.05 * span, colour=MESH,
                        slats=5, dir="v", slat_colour="#2a2c30"))
    return out + list(d["tail_extra"])


def front(kit, car):
    place(kit, car.body, car.d.get("face") or default_face(car), True)
    if car.d["bumpers"] == "chrome":
        bumper(kit, car, True)


def rear(kit, car):
    place(kit, car.body, car.d.get("tail") or default_tail(car), False)
    if car.d["bumpers"] == "chrome":
        bumper(kit, car, False)


def bumper(kit, car, front_end=True):
    """A classic's chrome bar, following the nose a little proud of
    it."""
    b = car.body
    a, zb, zt, _s = face_box(b, front_end)
    z = zb + car.d["bumper_v"][0 if front_end else 1] * (zt - zb)
    xs = [a * (-0.98 + 1.96 * k / 24) for k in range(25)]
    view = (0.0, 1.0, 0.0) if front_end else (0.0, -1.0, 0.0)
    far = 4 * b.L
    origins = [(x, -far if front_end else far, z) for x in xs]
    dist = b.cast(origins, view)
    pts = []
    for (x, y, zz), dd in zip(origins, dist):
        if dd == dd:
            yy = y + dd * view[1] - view[1] * 26
            pts.append((x * 1.01, yy, zz))
    if len(pts) > 3:
        kit.path(pts, 30, CHROME, "Metal", sides=12)


# ------------------------------------------------------------ fittings

def mirrors(kit, car, paint):
    b, d = car.body, car.d
    s = d["cowl"][0] + d["pillar"] + 0.03
    i = b.station_index(s)
    j = b.col["glass"] + 1.0
    p = b.point(i, j)
    x, y, z = float(p[0]), float(p[1]), float(p[2])
    for side in (-1, 1):
        cx = side * (x + 120)
        pts = []
        for k in range(16):
            t = 2 * math.pi * k / 16
            for zz, sc in ((-38, 0.75), (0, 1.0), (40, 0.8)):
                pts.append((cx + side * 70 * math.cos(t) * sc,
                            y + 35 + 55 * math.sin(t) * sc, z + 70 + zz))
        kit.solid(pts, paint, "Plastic")
        kit.solid([(cx + side * 60, y + 2, z + 40), (cx + side * 60,
                    y + 2, z + 100), (cx - side * 55, y + 2, z + 40),
                   (cx - side * 55, y + 2, z + 100), (cx, y - 1, z + 70)],
                  GLASS, "Metal")
        kit.bar((side * (x - 20), y + 40, z + 20), (cx, y + 40, z + 62), 14,
                TRIM)


def wing(kit, car, paint):
    b, d = car.body, car.d
    kind = d["wing"] or car.spec["wing"]
    s = 0.955
    i = b.station_index(s)
    top = b.point(i, b.col["top"])
    y_t, z_t = float(top[1]), float(top[2])
    a = b.half_width(s) * 0.92
    if kind in ("wing", "hoop"):
        h = d["wing_h"] if kind == "wing" else 70.0
        chord = d["wing_chord"]
        zw = z_t + h
        yc = y_t - 20
        prof = _airfoil(chord, 0.13, 8.0)
        span = [x * a for x in (-1.0, 1.0)]
        rings = [[(x, yc + py, zw + pz) for py, pz in prof] for x in span]
        from .car_wheels import closed_grid
        closed_grid(kit.mesh(TRIM if kind == "wing" else paint, "Plastic"),
                    rings)
        for side in (-1, 1):
            # end plates
            kit.box(side * a - 6 * side, yc - chord * 0.6, zw - 70,
                    side * a, yc + chord * 0.55, zw + 60, TRIM, "Plastic")
            x = side * a * 0.62
            kit.solid([(x - 8, yc - 70, z_t - 30), (x + 8, yc - 70, z_t - 30),
                       (x - 8, yc + 50, z_t - 30), (x + 8, yc + 50, z_t - 30),
                       (x - 8, yc - 40, zw + 5), (x + 8, yc - 40, zw + 5),
                       (x - 8, yc + 30, zw + 5), (x + 8, yc + 30, zw + 5)],
                      TRIM, "Plastic")
    elif kind in ("ducktail", "whale"):
        w = a * (0.86 if kind == "ducktail" else 0.97)
        depth = 0.10 if kind == "ducktail" else 0.15
        rise = 75.0 if kind == "ducktail" else 115.0
        s0 = 1.0 - depth - 0.02
        i0 = b.station_index(s0)
        za = float(b.point(i0, b.col["top"])[2])
        ya = b.y(s0)
        y1 = b.y(0.985)
        z1 = float(b.point(b.station_index(0.985), b.col["top"])[2])
        kit.solid([(-w, ya, za - 30), (w, ya, za - 30), (-w * 0.98, y1, z1 - 40),
                   (w * 0.98, y1, z1 - 40), (-w, y1 + 20, z1 + rise),
                   (w, y1 + 20, z1 + rise), (-w * 0.9, ya + 30, za + 8),
                   (w * 0.9, ya + 30, za + 8)], paint, "Plastic")
        if kind == "whale":
            kit.box(-w, y1 + 5, z1 + rise - 12, w, y1 + 40, z1 + rise + 8,
                    TRIM, "Rubber")
    elif kind == "lip":
        s0 = 0.975
        i0 = b.station_index(s0)
        z0 = float(b.point(i0, b.col["top"])[2])
        y0 = b.y(s0)
        w = b.half_width(s0) * 0.80
        kit.solid([(-w, y0 - 90, z0 - 6), (w, y0 - 90, z0 - 6),
                   (-w, y0 + 40, z0 - 6), (w, y0 + 40, z0 - 6),
                   (-w, y0 + 40, z0 + 40), (w, y0 + 40, z0 + 40)],
                  paint, "Plastic")


def _airfoil(chord, thick, camber):
    """A closed wing section (y along the chord, z up), leading edge
    forward (-y)."""
    pts = []
    n = 10
    for k in range(n + 1):
        t = k / n
        x = (1 - math.cos(math.pi * t)) / 2
        yt = 5 * thick * (0.2969 * math.sqrt(x) - 0.126 * x - 0.3516 * x * x
                          + 0.2843 * x ** 3 - 0.1036 * x ** 4) * chord
        yc = camber * 4 * x * (1 - x)
        pts.append((x, yc + yt))
    lower = []
    for k in range(n - 1, 0, -1):
        t = k / n
        x = (1 - math.cos(math.pi * t)) / 2
        yt = 5 * thick * (0.2969 * math.sqrt(x) - 0.126 * x - 0.3516 * x * x
                          + 0.2843 * x ** 3 - 0.1036 * x ** 4) * chord
        yc = camber * 4 * x * (1 - x)
        lower.append((x, yc - yt))
    prof = pts + lower
    return [(-chord / 2 + x * chord, z) for x, z in prof]


def exhausts(kit, car):
    b, d = car.body, car.d
    a, zb, zt, _s = face_box(b, False)
    z = zb + d["exhaust_v"] * (zt - zb)
    us = d["exhausts"]
    for u in us:
        x = u * a
        dist = b.cast([(x, 4 * b.L, z)], (0.0, -1.0, 0.0))[0]
        if dist != dist:
            continue
        y = 4 * b.L - dist
        r = d["exhaust_r"]
        kit.path([(x, y - 140, z), (x, y + 25, z)], r, CHROME, "Metal",
                 sides=18)
        kit.path([(x, y - 60, z), (x, y + 27, z)], r - 7, "#0b0b0c",
                 "Matte", sides=18)
