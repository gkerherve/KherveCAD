"""SolidWorks' **Trim Entities** (2026-11-11, the user, with SolidWorks'
Trim window: Power trim, Corner, Trim away inside, Trim away outside,
Trim to closest).

The Trim tool keeps one option, chosen in its window (`tool_panel`,
beside the 2D sketch or the 3D view, whichever the sketch is drawn in):

- **Power trim** — drag across lines: every line the cursor crosses
  loses the piece it crossed (to the nearest crossings either side);
- **Corner** — click two lines: each is extended or cut back to where
  they meet, keeping the side you clicked;
- **Trim away inside** — click two boundary entities (lines or circles),
  then the lines to trim: the part between the boundaries goes;
- **Trim away outside** — the same, the part BETWEEN them is kept;
- **Trim to closest** — click a piece: it goes, up to the nearest
  crossings (what Trim always did).

The geometry is Qt-free (`corner`, `away`, `power`), on sketch `line`
nodes in their own coordinates; `sketch_modify.trim` does the closest.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

POWER, CORNER, INSIDE, OUTSIDE, CLOSEST = (
    "power", "corner", "inside", "outside", "closest")
MODES = [(POWER, "Power trim"), (CORNER, "Corner"),
         (INSIDE, "Trim away inside"), (OUTSIDE, "Trim away outside"),
         (CLOSEST, "Trim to closest")]
MESSAGES = {
    POWER: "Drag across the lines to trim: each loses the piece the "
           "cursor crosses.",
    CORNER: "Click two lines: each is extended or cut back to where they "
            "meet, keeping the side you click.",
    INSIDE: "Click two boundary entities (lines or circles), then each "
            "line to trim: the part between the boundaries goes.",
    OUTSIDE: "Click two boundary entities (lines or circles), then each "
             "line to trim: only the part between them is kept.",
    CLOSEST: "Click the piece of a line to remove, up to the nearest "
             "crossings.",
}
SETTING = "sketch/trim_mode"
EPS = 1e-9


def mode():
    try:
        from PyQt5.QtCore import QSettings
        v = str(QSettings("Kherve", "KherveCAD").value(SETTING, CLOSEST))
    except Exception:
        v = CLOSEST
    return v if v in dict(MODES) else CLOSEST


def set_mode(value):
    from PyQt5.QtCore import QSettings
    QSettings("Kherve", "KherveCAD").setValue(SETTING, value)


# ------------------------------------------------------------ geometry
def _sm():
    from . import sketch_modify
    return sketch_modify


def line_meet(l1, l2):
    """Where the two lines (run on for ever) meet, or None."""
    sm = _sm()
    a, b = sm._ends(l1)
    c, d = sm._ends(l2)
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < EPS:
        return None
    q = (c[0] - a[0], c[1] - a[1])
    t = (q[0] * s[1] - q[1] * s[0]) / den
    return (a[0] + r[0] * t, a[1] + r[1] * t)


def _end_to(model, line, click, point):
    """Move the end of *line* on the far side of *point* from *click*
    (or the nearer end) onto *point*: the clicked side is kept."""
    sm = _sm()
    tx = sm._t_of(line, point)
    tc = sm._t_of(line, click)
    p = line.params
    x, y = round(point[0], 4), round(point[1], 4)
    if tc <= tx:
        p["x2"], p["y2"] = x, y
    else:
        p["x1"], p["y1"] = x, y
    model.node_changed.emit(line)


def corner(model, l1, click1, l2, click2):
    """Both lines run to where they meet, the clicked sides kept."""
    x = line_meet(l1, l2)
    if x is None:
        raise ValueError("those lines are parallel: they never meet")
    _end_to(model, l1, click1, x)
    _end_to(model, l2, click2, x)
    return x


def _hits(line, bound):
    """Parameters on *line* (0..1) where *bound* crosses it."""
    sm = _sm()
    a, b = sm._ends(line)
    if bound.type == "line":
        c, d = sm._ends(bound)
        t = sm._seg_hit(a, b, c, d)
        return [] if t is None else [t]
    if bound.type == "circle":
        ts = sm._circle_hits(a, b, (sm._num(bound.params.get("x")),
                                    sm._num(bound.params.get("y"))),
                             sm._num(bound.params.get("radius"), 1.0))
        return [t for t in ts if -EPS <= t <= 1 + EPS]
    return []


def away(model, line, bounds, inside=True):
    """Trim *line* between (inside) or outside the two *bounds*.
    Returns 'deleted', 'split', 'shortened' or 'kept'."""
    sm = _sm()
    ts = sorted(t for b in bounds for t in _hits(line, b))
    if len(ts) < 2:
        raise ValueError("%s does not cross both boundaries" % line.name)
    t1, t2 = ts[0], ts[-1]
    a, b = sm._ends(line)
    p = line.params
    lo, hi = sm._at(line, t1), sm._at(line, t2)
    if not inside:
        p["x1"], p["y1"] = lo
        p["x2"], p["y2"] = hi
        model.node_changed.emit(line)
        return "shortened"
    left, right = t1 > EPS, t2 < 1 - EPS
    if not left and not right:
        model.remove_node(line)
        return "deleted"
    if left and right:
        p["x2"], p["y2"] = lo
        twin = sm._insert(model, "line", dict(p), line)
        twin.params.update(x1=hi[0], y1=hi[1], x2=b[0], y2=b[1])
        model.node_changed.emit(line)
        return "split"
    if left:
        p["x2"], p["y2"] = lo
    else:
        p["x1"], p["y1"] = hi
    model.node_changed.emit(line)
    return "shortened"


def power(model, lines, p, q):
    """Each of *lines* crossed by the stroke p -> q (in the lines' own
    coordinates) loses the piece it was crossed on. Returns how many."""
    n = 0
    stroke = ("seg", tuple(p), tuple(q))
    for line in list(lines):
        if line.parent is None:
            continue
        cv = curve_of(line)
        if cv is None:
            continue
        hit = None
        for x in meet_points(cv, stroke):
            if _on(stroke, x) is not None and _on(cv, x) is not None:
                hit = x
                break
        if hit is None:
            continue
        trim_piece(model, line, hit)
        n += 1
    return n


# ------------------------------------------------------- the window
def start(win):
    """The Trim Entities button: the tool and its window, beside the view
    the sketch is drawn in."""
    state.clear()
    from . import sketch_modify
    win._set_tool(sketch_modify.TRIM)
    tool = getattr(win.view3d, "edit_tool", None)
    in_3d = getattr(tool, "tool", None) == sketch_modify.TRIM
    close_panel(win.view2d if in_3d else win.view3d)
    open_panel(win.view3d if in_3d else win.view2d)


def _panel(view, create=True):
    panel = getattr(view, "_trim_panel", None)
    if panel is None and create:
        panel = view._trim_panel = _make_panel(view)
    return panel


def open_panel(view):
    panel = _panel(view)
    if panel is not None:
        panel.refresh()
        panel.open()
    return panel


def close_panel(view):
    panel = _panel(view, create=False)
    if panel is not None:
        panel.hide()


def _make_panel(view):
    from .tool_panel import ToolPanel

    def done():
        close_panel(view)
        try:                              # back to Select
            win = view.window()
            from . import stop_tool
            stop_tool.stop(win)
        except Exception:
            pass

    class TrimPanel(ToolPanel):
        def __init__(self):
            super().__init__(view, "Trim Entities", on_ok=done,
                             on_cancel=done)
            self.message = self.hint(MESSAGES[mode()])
            self.section("Options")
            self.choice("mode", "Option", MODES, mode(), self._mode)
            self.finish()

        def _mode(self, value):
            set_mode(value)
            state.clear()
            self.refresh()

        def refresh(self):
            self.set_value("mode", mode())
            self.message.setText(MESSAGES[mode()] + (
                "  (%d boundary picked)" % len(state.get("bounds", []))
                if mode() in (INSIDE, OUTSIDE) and state.get("bounds")
                else ""))
            self.adjustSize()

    return TrimPanel()


#: picks waiting for their partner (corner's first line, the boundaries)
state = {}


def pick(model, node, click):
    """One click of the Trim tool on *node* at *click* (its own coords),
    in the current option. Returns a sentence for the status bar."""
    m = mode()
    if m == CLOSEST:
        if curve_of(node) is None:
            return "Trim works on lines, arcs and circles."
        return "Trim: %s." % trim_piece(model, node, click)
    if m == CORNER:
        if node.type != "line":
            return "Corner: click two lines."
        first = state.get("first")
        if first is None or first[0] is node or first[0].parent is None:
            state["first"] = (node, click)
            return "Corner: now the other line."
        state.pop("first", None)
        corner(model, first[0], first[1], node, click)
        return "Corner: both lines meet."
    if m in (INSIDE, OUTSIDE):
        bounds = state.setdefault("bounds", [])
        bounds[:] = [b for b in bounds if b.parent is not None]
        if len(bounds) < 2:
            if node.type not in ("line", "circle") or node in bounds:
                return MESSAGES[m]
            bounds.append(node)
            return ("Boundary %d: %s. %s" % (
                len(bounds), node.name, "Now the second boundary."
                if len(bounds) < 2 else "Now click the lines to trim."))
        if node.type != "line" or node in bounds:
            return "Click a line that crosses both boundaries."
        return "Trim: %s." % away(model, node, bounds, inside=m == INSIDE)
    return MESSAGES[m]


# ------------------------------------------- lines, arcs and circles
# (2026-11-11, the user, with SolidWorks' flange: "trim some parts of
# those circles which are inside another circle" — a circle's piece
# between two crossings goes and the rest stays as an open arc; and
# "hovering … that quarter circle should be highlighted")
TWO_PI = 2 * math.pi


def curve_of(node):
    """The node as a curve: ("seg", a, b) or ("arc", cx, cy, r, a0,
    sweep) — a full circle is an arc of 2π from angle 0 — else None."""
    from . import sketch_arc
    p = node.params
    try:
        if node.type == "line":
            a = (float(p["x1"]), float(p["y1"]))
            b = (float(p["x2"]), float(p["y2"]))
            g = sketch_arc.geometry(a[0], a[1], b[0], b[1],
                                    sketch_arc.bulge_of(p))
            return ("seg", a, b) if g is None else ("arc",) + tuple(g)
        if node.type == "circle":
            sweep = math.radians(float(p.get("angle", 360) or 360))
            start = math.radians(float(p.get("start_angle", 0) or 0))
            return ("arc", float(p.get("x", 0)), float(p.get("y", 0)),
                    float(p.get("radius", 1)),
                    start if sweep < TWO_PI - 1e-9 else 0.0,
                    min(sweep, TWO_PI))
    except (KeyError, TypeError, ValueError):
        return None
    return None


def _closed(cv):
    return cv[0] == "arc" and abs(abs(cv[5]) - TWO_PI) < 1e-9


def point_at(cv, t):
    if cv[0] == "seg":
        a, b = cv[1], cv[2]
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    _k, cx, cy, r, a0, sweep = cv
    ang = a0 + sweep * t
    return (cx + r * math.cos(ang), cy + r * math.sin(ang))


def t_of(cv, p, clamp=True):
    """Parameter of the point of *cv* nearest *p* (None off an arc's
    range when not clamped)."""
    if cv[0] == "seg":
        a, b = cv[1], cv[2]
        d = (b[0] - a[0], b[1] - a[1])
        L = d[0] ** 2 + d[1] ** 2 or 1e-12
        t = ((p[0] - a[0]) * d[0] + (p[1] - a[1]) * d[1]) / L
        return min(max(t, 0.0), 1.0) if clamp else t
    _k, cx, cy, r, a0, sweep = cv
    ang = math.atan2(p[1] - cy, p[0] - cx)
    s = 1.0 if sweep >= 0 else -1.0
    u = ((ang - a0) * s) % TWO_PI
    if u > TWO_PI - 1e-7:             # the start, read a hair below 2π
        u = 0.0
    t = u / abs(sweep)
    if t <= 1.0 + 1e-6:               # the end, read a hair past it
        return min(t, 1.0)
    if not clamp:
        return None
    # past the arc's end: the nearer end
    return 1.0 if (u - abs(sweep)) < (TWO_PI - u) else 0.0


def _on(cv, p, tol=1e-6):
    """Parameter of point *p* (on cv's carrier) within cv, else None."""
    t = t_of(cv, p, clamp=False)
    if t is None or t < -tol or t > 1 + tol:
        return None
    q = point_at(cv, min(max(t, 0.0), 1.0))
    return t if math.hypot(q[0] - p[0], q[1] - p[1]) < 1e-5 * max(
        1.0, abs(p[0]) + abs(p[1])) + 1e-6 else None


def meet_points(c1, c2):
    """Points where the carriers of two curves cross (no range check)."""
    if c1[0] == "seg" and c2[0] == "seg":
        a, b = c1[1], c1[2]
        c, d = c2[1], c2[2]
        r = (b[0] - a[0], b[1] - a[1])
        s = (d[0] - c[0], d[1] - c[1])
        den = r[0] * s[1] - r[1] * s[0]
        if abs(den) < 1e-12:
            return []
        q = (c[0] - a[0], c[1] - a[1])
        t = (q[0] * s[1] - q[1] * s[0]) / den
        return [(a[0] + r[0] * t, a[1] + r[1] * t)]
    if c1[0] == "arc" and c2[0] == "seg":
        c1, c2 = c2, c1
    if c1[0] == "seg":
        a, b = c1[1], c1[2]
        _k, cx, cy, rad, _a0, _sw = c2
        d = (b[0] - a[0], b[1] - a[1])
        f = (a[0] - cx, a[1] - cy)
        A = d[0] ** 2 + d[1] ** 2
        B = 2 * (f[0] * d[0] + f[1] * d[1])
        C = f[0] ** 2 + f[1] ** 2 - rad ** 2
        disc = B * B - 4 * A * C
        if A < 1e-18 or disc < 0:
            return []
        sq = math.sqrt(disc)
        return [(a[0] + d[0] * t, a[1] + d[1] * t)
                for t in ((-B - sq) / (2 * A), (-B + sq) / (2 * A))]
    _k, x0, y0, r0, _a, _s = c1
    _k, x1, y1, r1, _a, _s = c2
    dx, dy = x1 - x0, y1 - y0
    d = math.hypot(dx, dy)
    if d < 1e-12 or d > r0 + r1 + 1e-9 or d < abs(r0 - r1) - 1e-9:
        return []
    a = (r0 * r0 - r1 * r1 + d * d) / (2 * d)
    h = math.sqrt(max(r0 * r0 - a * a, 0.0))
    mx, my = x0 + a * dx / d, y0 + a * dy / d
    return [(mx - h * dy / d, my + h * dx / d),
            (mx + h * dy / d, my - h * dx / d)]


def _cutters(node):
    """The curves of the OTHER shapes of the sketch: lines, arcs,
    circles, rectangle and polygon sides (construction ones too, as
    SolidWorks trims to a centerline)."""
    from . import sketch_constraints as sc
    out = []
    parent = node.parent
    for o in (parent.children if parent is not None else []):
        if o is node:
            continue
        cv = curve_of(o)
        if cv is not None:
            if not (o.type == "circle" and _is_point(o)):
                out.append(cv)
            continue
        if o.type in ("rect", "polygon"):
            n = 4 if o.type == "rect" else len(o.params.get("points") or [])
            for i in range(n):
                try:
                    a, b = sc._line(o, "e%d" % i, {})
                except (KeyError, ValueError, IndexError, TypeError):
                    continue
                out.append(("seg", a, b))
    return out


def _is_point(node):
    from .view2d import is_sketch_point
    try:
        return is_sketch_point(node)
    except Exception:
        return False


def cuts(node):
    """Sorted parameters (0..1) where the other shapes cross *node*."""
    cv = curve_of(node)
    if cv is None:
        return []
    ts = []
    for other in _cutters(node):
        for p in meet_points(cv, other):
            if _on(other, p) is None:
                continue
            t = _on(cv, p)
            if t is not None:
                ts.append(min(max(t, 0.0), 1.0))
    ts.sort()
    out = []
    for t in ts:
        if not out or t - out[-1] > 1e-7:
            out.append(t)
    return out


def piece(node, click):
    """(lo, hi) — the parameter range of the piece of *node* under
    *click* between the nearest crossings. For a full circle hi may be
    past 1 (it wraps); None when nothing crosses a circle."""
    cv = curve_of(node)
    if cv is None:
        return None
    t = t_of(cv, click)
    ts = cuts(node)
    if _closed(cv):
        if not ts:
            return (0.0, 1.0)
        ts = [x % 1.0 for x in ts]
        ts = sorted(set(round(x, 9) for x in ts))
        for lo, hi in zip(ts, ts[1:] + [ts[0] + 1.0]):
            tt = t if t >= lo else t + 1.0
            if lo <= tt <= hi:
                return (lo, hi)
        return (ts[-1], ts[0] + 1.0)
    edges = [0.0] + [x for x in ts if 1e-7 < x < 1 - 1e-7] + [1.0]
    for lo, hi in zip(edges, edges[1:]):
        if lo <= t <= hi:
            return (lo, hi)
    return (0.0, 1.0)


def piece_points(node, click, steps=48):
    """The piece trimming *node* at *click* would remove, as a polyline
    in the node's own coordinates (for the highlight)."""
    cv = curve_of(node)
    got = piece(node, click)
    if cv is None or got is None:
        return []
    lo, hi = got
    if cv[0] == "seg":
        return [point_at(cv, lo), point_at(cv, hi)]
    n = max(2, int(steps * (hi - lo)) + 1)
    return [point_at(cv, (lo + (hi - lo) * i / n) % 1.0
                     if _closed(cv) else lo + (hi - lo) * i / n)
            for i in range(n + 1)]


def _set_arc(params, a, b, sweep):
    from . import sketch_arc
    params.update(x1=round(a[0], 6), y1=round(a[1], 6),
                  x2=round(b[0], 6), y2=round(b[1], 6))
    params["bulge"] = round(math.tan(sweep / 4.0), 12)


def trim_piece(model, node, click):
    """Remove the piece of *node* (line, arc, circle) under *click*.
    A circle keeps the rest as an open ARC (a line with a bulge, whose
    centre and size the relations and dimensions still reach). Returns
    'deleted', 'shortened', 'split' or 'opened'."""
    from . import sketch_modify as sm
    cv = curve_of(node)
    got = piece(node, click)
    if cv is None or got is None:
        return "nothing to trim"
    lo, hi = got
    if _closed(cv):
        span = hi - lo
        if span >= 1.0 - 1e-9:
            model.remove_node(node)
            return "deleted"
        # what stays runs from hi round to lo (+1), counter-clockwise
        keep = 1.0 - span
        a, b = point_at(cv, hi % 1.0), point_at(cv, lo)
        old = node.params
        params = {k: v for k, v in old.items()
                  if k in ("modifier", "origin_point", "collection")}
        params["width"] = 0.2
        _set_arc(params, a, b, TWO_PI * keep)
        node.type = "line"
        node.params = params
        model.structure_changed.emit()
        model.node_changed.emit(node)
        return "opened"
    if lo <= 1e-9 and hi >= 1 - 1e-9:
        model.remove_node(node)
        return "deleted"
    p = node.params
    a, b = point_at(cv, 0.0), point_at(cv, 1.0)
    sweep = cv[5] if cv[0] == "arc" else 0.0

    def part(t0, t1):
        return point_at(cv, t0), point_at(cv, t1), sweep * (t1 - t0)
    if lo <= 1e-9:
        s, e, sw = part(hi, 1.0)
    elif hi >= 1 - 1e-9:
        s, e, sw = part(0.0, lo)
    else:
        s, e, sw = part(0.0, lo)
        s2, e2, sw2 = part(hi, 1.0)
        twin = sm._insert(model, "line", dict(p), node)
        if cv[0] == "arc":
            _set_arc(twin.params, s2, e2, sw2)
        else:
            twin.params.update(x1=round(s2[0], 6), y1=round(s2[1], 6),
                               x2=round(e2[0], 6), y2=round(e2[1], 6))
        _apply(p, s, e, sw, cv)
        model.node_changed.emit(node)
        model.node_changed.emit(twin)
        return "split"
    _apply(p, s, e, sw, cv)
    model.node_changed.emit(node)
    return "shortened"


def _apply(params, s, e, sweep, cv):
    if cv[0] == "arc":
        _set_arc(params, s, e, sweep)
    else:
        params.update(x1=round(s[0], 6), y1=round(s[1], 6),
                      x2=round(e[0], 6), y2=round(e[1], 6))


# ------------------------------------------------ the hover highlight
#: the piece a click would remove, as SolidWorks shows it
HOVER_INK = "#ff8c00"


def _hover_piece(node, click):
    m = mode()
    if m == CLOSEST:
        return piece_points(node, click)
    return []


def hover_2d(scene, pos):
    """The piece under the cursor (Trim to closest), kept in scene
    coordinates for paint_2d."""
    from PyQt5.QtCore import QPointF
    from . import sketch_constrain_ui as scu
    from .view2d_edit import Frame, in_frame_coords
    old = getattr(scene, "_trim_hover", None)
    pts = []
    hit = scu.pick(scene, pos, "curve") if mode() == CLOSEST else None
    if hit is not None:
        node = hit[0]
        item = next((it for it in scu._shape_items(scene)
                     if it.node is node), None)
        q = in_frame_coords(item, pos) if item is not None else pos
        local = _hover_piece(node, (q.x(), q.y()))
        frame = item.parentItem() if item is not None else None
        to_s = frame.mapToScene if isinstance(frame, Frame) else \
            (lambda p: QPointF(p))
        pts = [to_s(QPointF(x, y)) for x, y in local]
    scene._trim_hover = pts
    if pts or old:
        scene.update()


def paint_2d(view, painter):
    from PyQt5.QtGui import QColor, QPen, QPolygonF
    scene = view.scene()
    pts = getattr(scene, "_trim_hover", None)
    if not pts or getattr(scene, "tool", None) != "sk_trim":
        return
    k = abs(view.transform().m11()) or 1.0
    painter.save()
    pen = QPen(QColor(HOVER_INK), 3.0 / k)
    painter.setPen(pen)
    painter.drawPolyline(QPolygonF(pts))
    painter.restore()


def paint_3d(painter, project, group, local):
    """The piece in 3D: sketch points -> world -> screen."""
    from PyQt5.QtCore import QPointF
    from PyQt5.QtGui import QColor, QPen, QPolygonF
    from .face_sketch import to_world
    scr = []
    for x, y in local:
        s = project(to_world(group, x, y))
        if s is None or s[2] <= 0:
            continue
        scr.append(QPointF(s[0], s[1]))
    if len(scr) >= 2:
        painter.save()
        painter.setPen(QPen(QColor(HOVER_INK), 3.0))
        painter.drawPolyline(QPolygonF(scr))
        painter.restore()
