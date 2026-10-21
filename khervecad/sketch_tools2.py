"""More sketch CREATE tools (2026-10-21, the user: "add them all" — what
SolidCraft's sketcher has and KherveCAD lacked). They plug into
sketch_tools' tables (TOOLS, CLICKS, PROMPTS, BUILD, outline) on import,
so the clicks, the rubber band, Enter / right-click and Backspace work
as for the others:

- **construction** — not a tool but a switch (`toggle_construction`):
  OpenSCAD's own `%` modifier on the selected shapes, so OpenSCAD leaves
  them out of the solid and the program stays exact; drawn dashed, and
  constraints and dimensions use them like any shape;
- **point** — a 0.25 mm construction circle: its centre is a point to
  constrain (a hole centre, a midpoint);
- **three-point rectangle** (a side, then the depth: drawn at an angle),
  **two-point / three-point circles**, **regular polygon** (centre, a
  corner, sides asked), **polyline** (lines end to end, each joined to
  the last by a coincident constraint; Enter / right-click ends),
  **control-point spline** (a closed B-spline the points pull on, which
  it does not pass through), **tangent arc** (from a line's end, on in
  its direction), **tangent circle** (inside three lines) and **conic**
  (start, end, shoulder; rho 0.5 = a parabola).

Arcs and conics are open curves: they are drawn as a band as wide as a
line (a `polygon`), like a sketch fillet between two lines.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import sketch_tools as st

POINT, RECT_3PT, CIRCLE_2PT, CIRCLE_3PT, POLY_REG = (
    "point", "rect_3pt", "circle_2pt", "circle_3pt", "poly_reg")
POLYLINE, BSPLINE, ARC_TAN, CIRCLE_TAN, CONIC = (
    "polyline", "bspline", "arc_tangent", "circle_tangent", "conic")
CONSTRUCTION = "construction"
CONST_LINE = "construction_line"

TOOLS = [
    (CONST_LINE, "mdi.vector-line", "Construction line", ""),
    (POINT, "mdi.circle-small", "Point", ""),
    (POLYLINE, "mdi.vector-polyline", "Polyline", ""),
    (RECT_3PT, "mdi.vector-rectangle", "3-point rectangle", ""),
    (CIRCLE_2PT, "mdi.circle-outline", "2-point circle", ""),
    (CIRCLE_3PT, "mdi.circle-double", "3-point circle", ""),
    (CIRCLE_TAN, "mdi.circle-slice-8", "Tangent circle", ""),
    (ARC_TAN, "mdi.vector-curve", "Tangent arc", ""),
    (POLY_REG, "mdi.hexagon-outline", "Regular polygon", ""),
    (BSPLINE, "mdi.chart-bell-curve", "Control-point spline", ""),
    (CONIC, "mdi.vector-bezier", "Conic", ""),
]
CLICKS = {CONST_LINE: 2, POINT: 1, RECT_3PT: 3, CIRCLE_2PT: 2, CIRCLE_3PT: 3,
          POLY_REG: 2, ARC_TAN: 2, CIRCLE_TAN: 3, CONIC: 3}
#: tools that take any number of clicks (Enter / right-click ends)
VARIABLE = {POLYLINE, BSPLINE}
PROMPTS = {
    CONST_LINE: ["Click where the construction line starts (a dashed "
                 "reference: constraints use it, the solid does not).",
                 "Click where it ends."],
    POINT: ["Click where the point goes."],
    POLYLINE: ["Click points: each makes a line from the last. Enter, "
               "right-click or double-click ends; Backspace takes one "
               "back."],
    RECT_3PT: ["Click one corner.", "Click the next corner (the first "
               "side, at any angle).", "Click to set the depth."],
    CIRCLE_2PT: ["Click one end of a diameter.", "Click the other end."],
    CIRCLE_3PT: ["Click a point on the circle.", "Click a second point.",
                 "Click a third point."],
    CIRCLE_TAN: ["Click the first of three lines the circle touches.",
                 "Click the second line.", "Click the third line."],
    ARC_TAN: ["Click near the end of a line to go on from.",
              "Click where the arc ends."],
    POLY_REG: ["Click the centre.", "Click a corner."],
    BSPLINE: ["Click control points (the curve is pulled towards them). "
              "Enter, right-click or double-click ends."],
    CONIC: ["Click where the conic starts.", "Click where it ends.",
            "Click its shoulder (where the two end tangents meet)."],
}
POINT_R = 0.25
CURVE_STEPS = 24
LINE_W = 2.0


def _r(v):
    return round(v, 4)


def _band(pts, width=LINE_W):
    from .sketch_modify import _band as band
    return band(pts, width)


def _curve(pts):
    """An open curve as a line-wide band polygon."""
    if len(pts) < 2:
        return None
    return [("polygon", dict(x=0.0, y=0.0, points=_band(pts)), None)]


# ------------------------------------------------------------ geometry
def const_line(a, b):
    if math.dist(a, b) < st.MIN:
        return None
    return [("line", dict(x1=_r(a[0]), y1=_r(a[1]), x2=_r(b[0]),
                          y2=_r(b[1]), width=0.5, modifier="%"), None)]


def point(p):
    return [("circle", dict(x=_r(p[0]), y=_r(p[1]), radius=POINT_R,
                            modifier="%"), None)]


def rect_3pt_corners(a, b, c):
    ux, uy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(ux, uy)
    if L < st.MIN:
        return None
    nx, ny = -uy / L, ux / L
    d = (c[0] - b[0]) * nx + (c[1] - b[1]) * ny
    if abs(d) < st.MIN:
        return None
    return [a, b, (b[0] + nx * d, b[1] + ny * d),
            (a[0] + nx * d, a[1] + ny * d)]


def rect_3pt(a, b, c):
    pts = rect_3pt_corners(a, b, c)
    return st._polygon(pts) if pts else None


def circle_2pt(a, b):
    r = math.hypot(b[0] - a[0], b[1] - a[1]) / 2
    if r < st.MIN / 2:
        return None
    return [("circle", dict(x=_r((a[0] + b[0]) / 2), y=_r((a[1] + b[1]) / 2),
                            radius=_r(r)), None)]


def circle_3pt(a, b, c):
    o = st.circumcentre(a, b, c)
    if o is None:
        return None
    return [("circle", dict(x=_r(o[0]), y=_r(o[1]),
                            radius=_r(math.hypot(a[0] - o[0],
                                                 a[1] - o[1]))), None)]


def regular_points(c, corner, sides):
    r = math.hypot(corner[0] - c[0], corner[1] - c[1])
    a0 = math.atan2(corner[1] - c[1], corner[0] - c[0])
    return [(c[0] + r * math.cos(a0 + 2 * math.pi * i / sides),
             c[1] + r * math.sin(a0 + 2 * math.pi * i / sides))
            for i in range(sides)]


def poly_reg(c, corner, sides=6):
    if math.hypot(corner[0] - c[0], corner[1] - c[1]) < st.MIN:
        return None
    return st._polygon(regular_points(c, corner, max(3, int(sides))))


def polyline(*pts):
    pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
    if len(pts) < 2:
        return None
    return [("line", dict(x1=_r(a[0]), y1=_r(a[1]), x2=_r(b[0]),
                          y2=_r(b[1]), width=LINE_W), None)
            for a, b in zip(pts, pts[1:])]


def bspline_points(ctrl, steps=8):
    """A closed uniform cubic B-spline of the control points."""
    n = len(ctrl)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = (ctrl[(i - 1) % n], ctrl[i], ctrl[(i + 1) % n],
                          ctrl[(i + 2) % n])
        for s in range(steps):
            t = s / steps
            b0 = (1 - t) ** 3 / 6
            b1 = (3 * t ** 3 - 6 * t ** 2 + 4) / 6
            b2 = (-3 * t ** 3 + 3 * t ** 2 + 3 * t + 1) / 6
            b3 = t ** 3 / 6
            out.append(tuple(b0 * p0[k] + b1 * p1[k] + b2 * p2[k]
                             + b3 * p3[k] for k in (0, 1)))
    return out


def bspline(*pts):
    if len(pts) < 3:
        return None
    return st._polygon(bspline_points(list(pts)))


def conic_points(a, b, shoulder, rho=0.5, steps=CURVE_STEPS):
    """A rational quadratic Bezier from a to b pulled to the shoulder:
    weight w = rho / (1 - rho) (0.5 a parabola, below an ellipse arc,
    above a hyperbola)."""
    w = rho / (1.0 - rho)
    out = []
    for i in range(steps + 1):
        t = i / steps
        k0, k1, k2 = (1 - t) ** 2, 2 * t * (1 - t) * w, t * t
        den = k0 + k1 + k2
        out.append(tuple((k0 * a[j] + k1 * shoulder[j] + k2 * b[j]) / den
                         for j in (0, 1)))
    return out


def conic(a, b, shoulder):
    if math.hypot(b[0] - a[0], b[1] - a[1]) < st.MIN:
        return None
    return _curve(conic_points(a, b, shoulder))


def tangent_arc_points(start, direction, end, steps=CURVE_STEPS):
    """The arc leaving *start* along *direction* (unit) to *end*."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    nx, ny = -direction[1], direction[0]           # left normal
    chord2 = dx * dx + dy * dy
    side = dx * nx + dy * ny
    if abs(side) < 1e-9:
        return [start, end]                         # straight on
    r = chord2 / (2 * side)                         # signed radius
    c = (start[0] + nx * r, start[1] + ny * r)
    a0 = math.atan2(start[1] - c[1], start[0] - c[0])
    a1 = math.atan2(end[1] - c[1], end[0] - c[0])
    sweep = (a1 - a0) % (2 * math.pi)
    if r < 0:
        sweep -= 2 * math.pi
    R = abs(r)
    return [(c[0] + R * math.cos(a0 + sweep * i / steps),
             c[1] + R * math.sin(a0 + sweep * i / steps))
            for i in range(steps + 1)]


def _intersect(l1, l2):
    (a, b), (c, d) = l1, l2
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-9:
        return None
    t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den
    return (a[0] + r[0] * t, a[1] + r[1] * t)


def incircle(l1, l2, l3):
    """(centre, radius) of the circle inside the triangle three lines
    make, or None."""
    p = [_intersect(l1, l2), _intersect(l2, l3), _intersect(l3, l1)]
    if any(q is None for q in p):
        return None
    a = math.dist(p[1], p[2])
    b = math.dist(p[2], p[0])
    c = math.dist(p[0], p[1])
    s = a + b + c
    if s < 1e-9:
        return None
    centre = ((a * p[0][0] + b * p[1][0] + c * p[2][0]) / s,
              (a * p[0][1] + b * p[1][1] + c * p[2][1]) / s)
    area = abs((p[1][0] - p[0][0]) * (p[2][1] - p[0][1])
               - (p[2][0] - p[0][0]) * (p[1][1] - p[0][1])) / 2
    return centre, 2 * area / s


# --------------------------------------- tools that need the sketch
def _line_near(scene, xy):
    """(node, its two ends) of the line nearest a scene point, or None."""
    from PyQt5.QtCore import QPointF
    from . import sketch_constrain_ui as scu
    hit = scu.pick(scene, QPointF(*xy), "line")
    if hit is None or hit[0].type != "line":
        return None
    p = hit[0].params
    return hit[0], ((p["x1"], p["y1"]), (p["x2"], p["y2"]))


def build_tangent_arc(scene, start_click, end):
    found = _line_near(scene, start_click)
    if found is None:
        scene.status.emit("Tangent arc: start on a line's end.")
        return None
    node, (a, b) = found
    # go on from the end nearer the click, in the line's direction
    if math.dist(start_click, a) < math.dist(start_click, b):
        a, b = b, a
    L = math.dist(a, b) or 1.0
    d = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    return _curve(tangent_arc_points(b, d, end))


def build_tangent_circle(scene, c1, c2, c3):
    lines = [_line_near(scene, c) for c in (c1, c2, c3)]
    if any(x is None for x in lines):
        scene.status.emit("Tangent circle: click three lines.")
        return None
    got = incircle(*[x[1] for x in lines])
    if got is None:
        scene.status.emit("Tangent circle: those lines make no triangle.")
        return None
    (cx, cy), r = got
    return [("circle", dict(x=_r(cx), y=_r(cy), radius=_r(r)), None)]


def build_poly_reg(scene, c, corner):
    hook = getattr(scene, "ask_value", None)
    if hook is not None:
        text = hook(POLY_REG, 6)
    else:
        from PyQt5.QtWidgets import QInputDialog
        views = scene.views()
        n, ok = QInputDialog.getInt(views[0] if views else None,
                                    "Regular polygon", "Sides:", 6, 3, 64)
        if not ok:
            return None
        text = n
    try:
        sides = int(float(text))
    except (TypeError, ValueError):
        sides = 6
    return poly_reg(c, corner, sides)


BUILD = {CONST_LINE: const_line, POINT: point, RECT_3PT: rect_3pt, CIRCLE_2PT: circle_2pt,
         CIRCLE_3PT: circle_3pt, POLYLINE: polyline, BSPLINE: bspline,
         CONIC: conic}
#: builders that need the scene (lines to pick, a value to ask)
BUILD_SCENE = {ARC_TAN: build_tangent_arc, CIRCLE_TAN: build_tangent_circle,
               POLY_REG: build_poly_reg}


def outline(tool, pts):
    """The rubber band while placing (None: not one of ours)."""
    if tool not in CLICKS and tool not in VARIABLE:
        return None
    if tool == BSPLINE:
        return bspline_points(pts) if len(pts) >= 3 else list(pts)
    if tool in (POLYLINE, CONST_LINE):
        return list(pts)
    if len(pts) < 2:
        return list(pts)
    if tool == RECT_3PT:
        return (rect_3pt_corners(*pts[:3]) if len(pts) >= 3 else None) \
            or list(pts)
    if tool == CIRCLE_2PT:
        a, b = pts[0], pts[1]
        c = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        r = math.dist(a, b) / 2
        return [(c[0] + r * math.cos(2 * math.pi * i / 48),
                 c[1] + r * math.sin(2 * math.pi * i / 48))
                for i in range(48)]
    if tool == CIRCLE_3PT and len(pts) >= 3:
        o = st.circumcentre(*pts[:3])
        if o is not None:
            r = math.dist(pts[0], o)
            return [(o[0] + r * math.cos(2 * math.pi * i / 48),
                     o[1] + r * math.sin(2 * math.pi * i / 48))
                    for i in range(48)]
    if tool == POLY_REG:
        return regular_points(pts[0], pts[1], 6)
    if tool == CONIC and len(pts) >= 3:
        return conic_points(pts[0], pts[1], pts[2])
    return list(pts)


# ------------------------------------------------------ construction
def toggle_construction(model, nodes):
    """Construction on / off for the selected 2D shapes (OpenSCAD's
    `%`: shown, never part of the solid). Returns how many changed."""
    from .model import SHAPE_2D
    shapes = [n for n in nodes if n.category == SHAPE_2D]
    if not shapes:
        return 0
    on = not all(n.params.get("modifier") == "%" for n in shapes)
    for n in shapes:
        model.set_modifier(n, "%" if on else "")
    return len(shapes)


def is_construction(node):
    return node.params.get("modifier") == "%"


# ------------------------------------------------- joining the tables
def register():
    st.TOOLS.extend(TOOLS)
    st.CLICKS.update(CLICKS)
    st.PROMPTS.update(PROMPTS)
    st.BUILD.update(BUILD)


register()


TIPS = {
    CONSTRUCTION: (
        "Construction",
        "Turns the selected sketch shapes into construction geometry and "
        "back: drawn dashed, used by constraints and dimensions, never "
        "part of the solid (OpenSCAD's % modifier).",
        ["Select sketch shapes.", "Click Construction."], None),
}


def construction_action(win):
    act = getattr(win, "_construction_act", None)
    if act is not None:
        return act
    from PyQt5.QtWidgets import QAction
    from . import icons, language, toolbars, tooltips
    tooltips.TIPS.update(TIPS)
    act = QAction(icons.icon("mdi.vector-line", icons.family_color("draw")),
                  language.tr("Construction"), win)
    act.setData(CONSTRUCTION)
    toolbars.remember_glyph(act, "mdi.vector-line", "draw")
    tooltips.apply(act, CONSTRUCTION)

    def run():
        n = toggle_construction(
            win.model, win.builder.active_tree().selected_nodes())
        win.statusBar().showMessage(language.tr(
            "Construction switched on {n} shape(s).").format(n=n) if n
            else language.tr("Construction: select sketch shapes first."),
            5000)
    act.triggered.connect(lambda _=False: run())
    win._construction_act = act
    return act
