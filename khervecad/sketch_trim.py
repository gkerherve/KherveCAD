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
    sm = _sm()
    n = 0
    for line in list(lines):
        if line.parent is None or line.type != "line":
            continue
        a, b = sm._ends(line)
        t = sm._seg_hit(a, b, p, q)
        if t is None:
            continue
        sm.trim(model, line, sm._at(line, min(max(t, 0.0), 1.0)))
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
        if node.type != "line":
            return "Trim works on lines."
        return "Trim: %s." % _sm().trim(model, node, click)
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
