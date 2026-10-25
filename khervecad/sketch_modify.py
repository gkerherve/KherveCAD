"""Trim, extend, sketch fillet and chamfer (Qt-free geometry + the 2D
view's click tools), 2026-10-21 — Fusion / SolidWorks sketch MODIFY
tools from the user's "do them all".

KherveCAD's sketch lines are strokes (`line`: two ends and a width) and
its profiles are `polygon` / `rect` areas, so:

- **Trim** (a line): cut it where the other lines of its group cross
  it; the piece under the click goes — the line shortens, or splits in
  two when the piece is in the middle, or is deleted when nothing
  crosses it.
- **Extend** (a line): the end nearest the click runs on to the first
  line or circle it meets.
- **Fillet / Chamfer**: a corner of a polygon or rectangle (a rectangle
  becomes a polygon) is rounded with an arc of `radius` or cut by
  `distance`; where two LINES meet at an end, both are trimmed back to
  the tangent points and an arc stroke (a thin polygon band) joins them.

Every edit is ordinary node params, so the program stays OpenSCAD.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

TRIM, EXTEND, FILLET, CHAMFER = ("sk_trim", "sk_extend", "sk_fillet",
                                 "sk_chamfer")
#: (tool, mdi glyph, label)
TOOLS = [(TRIM, "mdi.content-cut", "Trim"),
         (EXTEND, "mdi.arrow-expand-right", "Extend"),
         (FILLET, "mdi.vector-curve", "Sketch fillet"),
         (CHAMFER, "mdi.vector-polyline", "Sketch chamfer"),
         # (no Extrude regions button: Extruded Boss/Base on overlapping
         # shapes picks the regions itself — the user, 2026-10-25)
         ("make_region", "mdi.vector-union", "Create region")]
EPS = 1e-6
ARC_STEPS = 12


def _num(v, default=0.0):
    return float(v) if isinstance(v, (int, float)) and \
        not isinstance(v, bool) else default


def _ends(line):
    p = line.params
    return ((_num(p.get("x1")), _num(p.get("y1"))),
            (_num(p.get("x2")), _num(p.get("y2"))))


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _seg_hit(a, b, c, d, ray=False):
    """Parameter t on a->b where it meets segment c->d (t may run past
    1 when *ray*), or None."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = _cross(r, s)
    if abs(den) < EPS:
        return None
    q = (c[0] - a[0], c[1] - a[1])
    t = _cross(q, s) / den
    u = _cross(q, r) / den
    if -EPS <= u <= 1 + EPS and (ray or -EPS <= t <= 1 + EPS):
        return t
    return None


def _circle_hits(a, b, centre, radius):
    d = (b[0] - a[0], b[1] - a[1])
    f = (a[0] - centre[0], a[1] - centre[1])
    A = d[0] ** 2 + d[1] ** 2
    B = 2 * (f[0] * d[0] + f[1] * d[1])
    C = f[0] ** 2 + f[1] ** 2 - radius ** 2
    disc = B * B - 4 * A * C
    if A < EPS or disc < 0:
        return []
    s = math.sqrt(disc)
    return [(-B - s) / (2 * A), (-B + s) / (2 * A)]


def _others(line):
    parent = line.parent
    return [n for n in (parent.children if parent else [])
            if n is not line and n.type in ("line", "circle")]


def cuts(line):
    """Parameters 0 < t < 1 where the group's other lines and circles
    cross *line*, sorted."""
    a, b = _ends(line)
    ts = []
    for o in _others(line):
        if o.type == "line":
            c, d = _ends(o)
            t = _seg_hit(a, b, c, d)
            if t is not None:
                ts.append(t)
        else:
            ts += _circle_hits(a, b, (_num(o.params.get("x")),
                                      _num(o.params.get("y"))),
                               _num(o.params.get("radius"), 1.0))
    return sorted(t for t in ts if EPS < t < 1 - EPS)


def _t_of(line, p):
    a, b = _ends(line)
    d = (b[0] - a[0], b[1] - a[1])
    L = d[0] ** 2 + d[1] ** 2 or EPS
    return ((p[0] - a[0]) * d[0] + (p[1] - a[1]) * d[1]) / L


def _at(line, t):
    a, b = _ends(line)
    return (round(a[0] + (b[0] - a[0]) * t, 4),
            round(a[1] + (b[1] - a[1]) * t, 4))


def trim(model, line, click):
    """Remove the piece of *line* under *click*. Returns what happened:
    'deleted', 'shortened' or 'split'."""
    ts = [0.0] + cuts(line) + [1.0]
    t = min(max(_t_of(line, click), 0.0), 1.0)
    i = max(k for k in range(len(ts) - 1) if ts[k] <= t)
    lo, hi = ts[i], ts[i + 1]
    if lo == 0.0 and hi == 1.0:
        model.remove_node(line)
        return "deleted"
    keep_a, keep_b = _at(line, lo), _at(line, hi)
    a, b = _ends(line)
    p = line.params
    if lo == 0.0:
        p["x1"], p["y1"] = keep_b
    elif hi == 1.0:
        p["x2"], p["y2"] = keep_a
    else:
        # split: this line keeps a -> lo, a copy takes hi -> b
        p["x2"], p["y2"] = keep_a
        twin = _insert(model, "line", dict(p), line)
        twin.params.update(x1=keep_b[0], y1=keep_b[1], x2=b[0], y2=b[1])
        model.node_changed.emit(line)
        return "split"
    model.node_changed.emit(line)
    return "shortened"


def extend(model, line, click):
    """Run the end of *line* nearest *click* on to the first line or
    circle it meets. Returns the new end, or None when nothing is hit."""
    a, b = _ends(line)
    far_end = _t_of(line, click) > 0.5
    if not far_end:
        a, b = b, a                 # always extend past b
    best = None
    for o in _others(line):
        if o.type == "line":
            c, d = _ends(o)
            hits = [_seg_hit(a, b, c, d, ray=True)]
        else:
            hits = _circle_hits(a, b, (_num(o.params.get("x")),
                                       _num(o.params.get("y"))),
                                _num(o.params.get("radius"), 1.0))
        for t in hits:
            if t is not None and t > 1 + EPS and (best is None or t < best):
                best = t
    if best is None:
        return None
    end = (round(a[0] + (b[0] - a[0]) * best, 4),
           round(a[1] + (b[1] - a[1]) * best, 4))
    p = line.params
    if far_end:
        p["x2"], p["y2"] = end
    else:
        p["x1"], p["y1"] = end
    model.node_changed.emit(line)
    return end


# ------------------------------------------------------ fillet / chamfer
def _corner_cut(prev, v, nxt, size, round_):
    """Points replacing corner v between prev and nxt."""
    u1 = (prev[0] - v[0], prev[1] - v[1])
    u2 = (nxt[0] - v[0], nxt[1] - v[1])
    l1, l2 = math.hypot(*u1), math.hypot(*u2)
    if l1 < EPS or l2 < EPS:
        raise ValueError("A corner needs two sides.")
    u1 = (u1[0] / l1, u1[1] / l1)
    u2 = (u2[0] / l2, u2[1] / l2)
    cosang = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
    ang = math.acos(cosang)
    if ang < 1e-3 or ang > math.pi - 1e-3:
        raise ValueError("That corner is straight: nothing to round.")
    setback = size / math.tan(ang / 2) if round_ else size
    if setback >= min(l1, l2) - EPS:
        raise ValueError("Too big for that corner: the sides are %.3g "
                         "and %.3g long." % (l1, l2))
    p1 = (v[0] + u1[0] * setback, v[1] + u1[1] * setback)
    p2 = (v[0] + u2[0] * setback, v[1] + u2[1] * setback)
    if not round_:
        return [p1, p2]
    bis = (u1[0] + u2[0], u1[1] + u2[1])
    bl = math.hypot(*bis)
    dist = size / math.sin(ang / 2)
    c = (v[0] + bis[0] / bl * dist, v[1] + bis[1] / bl * dist)
    a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
    a2 = math.atan2(p2[1] - c[1], p2[0] - c[0])
    sweep = math.remainder(a2 - a1, 2 * math.pi)
    return [(c[0] + size * math.cos(a1 + sweep * k / ARC_STEPS),
             c[1] + size * math.sin(a1 + sweep * k / ARC_STEPS))
            for k in range(ARC_STEPS + 1)]


def _polygon_points(node):
    p = node.params
    if node.type == "rect":
        x, y = _num(p.get("x")), _num(p.get("y"))
        w, h = _num(p.get("width")), _num(p.get("height"))
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], (0.0, 0.0)
    ox, oy = _num(p.get("x")), _num(p.get("y"))
    return [(_num(q[0]) + ox, _num(q[1]) + oy)
            for q in p.get("points") or []], (ox, oy)


def corner(model, node, index, size, round_=True):
    """Fillet (round_) or chamfer vertex *index* of a polygon or
    rectangle. The polygon keeps its SHARP corner point and gains a row
    in ``params["corners"]`` ([index, size, 0 round / 1 chamfer]); the
    arc is worked out from the corner whenever the shape is drawn
    (`expand`), so constraints and drags act on the corner and the arc
    follows — baked arc points were left behind by the solver. A
    rectangle becomes a polygon. Returns the node."""
    if node.type not in ("polygon", "rect"):
        raise ValueError("Fillet a polygon or rectangle corner, or where "
                         "two lines meet.")
    if node.type == "polygon" and node.params.get("paths"):
        raise ValueError("This polygon has holes (paths): edit its "
                         "points instead.")
    pts, origin = _polygon_points(node)
    n = len(pts)
    index %= n
    # checks the size fits (raises ValueError when it does not)
    _corner_cut(pts[index - 1], pts[index], pts[(index + 1) % n],
                float(size), round_)
    if node.type == "rect":
        rel = [[round(x - origin[0], 4), round(y - origin[1], 4)]
               for x, y in pts]
        node.type = "polygon"
        for k in ("width", "height", "center"):
            node.params.pop(k, None)
        node.params.update(x=0.0, y=0.0, points=rel)
        if node.name.startswith("Rectangle"):
            node.name = "Polygon" + node.name[len("Rectangle"):]
    rows = [list(r) for r in node.params.get("corners") or []
            if int(r[0]) != index]
    rows.append([index, round(float(size), 4), 0 if round_ else 1])
    node.params["corners"] = sorted(rows)
    model.structure_changed.emit()
    return node


def expand(points, corners):
    """*points* with each corner row [index, size, kind] replaced by its
    arc (kind 0) or chamfer (1). A corner that no longer fits (its sides
    got shorter than the setback) stays sharp."""
    if not corners:
        return [tuple(map(float, q)) for q in points]
    pts = [(float(q[0]), float(q[1])) for q in points]
    n = len(pts)
    by_index = {}
    for row in corners:
        try:
            by_index[int(row[0]) % n] = (float(row[1]),
                                         int(row[2]) if len(row) > 2
                                         else 0)
        except (TypeError, ValueError, IndexError):
            continue
    out = []
    for i, v in enumerate(pts):
        spec = by_index.get(i)
        if spec is None or spec[0] <= 0:
            out.append(v)
            continue
        try:
            out.extend(_corner_cut(pts[i - 1], v, pts[(i + 1) % n],
                                   spec[0], spec[1] == 0))
        except ValueError:
            out.append(v)
    return out


def line_corner(model, a, b, size, round_=True):
    """Fillet / chamfer where lines *a* and *b* share an end: both are
    trimmed back and the corner piece added as its own node. Returns
    the new node."""
    ea, eb = _ends(a), _ends(b)
    best = min(((i, j) for i in (0, 1) for j in (0, 1)),
               key=lambda ij: math.dist(ea[ij[0]], eb[ij[1]]))
    i, j = best
    if math.dist(ea[i], eb[j]) > 0.5:
        raise ValueError("The two lines do not meet at an end.")
    v = ea[i]
    new = _corner_cut(ea[1 - i], v, eb[1 - j], float(size), round_)
    # the ends no longer meet: a coincident there would pull them back
    from . import sketch_constraints
    sketch_constraints.drop_between(a.parent, a, b)
    for line, k, p in ((a, i, new[0]), (b, j, new[-1])):
        line.params["x%d" % (k + 1)] = round(p[0], 4)
        line.params["y%d" % (k + 1)] = round(p[1], 4)
        model.node_changed.emit(line)
    width = _num(a.params.get("width"), 2.0)
    if round_:
        # the arc as a thin band polygon, as wide as the line
        band = _band(new, width)
        node = _insert(model, "polygon", dict(x=0.0, y=0.0, points=band),
                       a, "Polygon [Fillet]")
    else:
        node = _insert(model, "line", dict(x1=round(new[0][0], 4),
                                           y1=round(new[0][1], 4),
                                           x2=round(new[1][0], 4),
                                           y2=round(new[1][1], 4),
                                           width=width),
                       a, "Line [Chamfer]")
    return node


def _insert(model, type_, params, after, name=""):
    """A new node right after *after* among its siblings."""
    from .model import CadNode
    node = CadNode(type_, name or model.unique_name(type_), params)
    parent = after.parent
    at = parent.children.index(after) + 1
    from . import sketch_constraints
    sketch_constraints.child_inserted(parent, at)
    parent.add(node, at)
    model.structure_changed.emit()
    return node


def _band(pts, width):
    h = width / 2
    left, right = [], []
    for k, p in enumerate(pts):
        q0 = pts[max(k - 1, 0)]
        q1 = pts[min(k + 1, len(pts) - 1)]
        d = (q1[0] - q0[0], q1[1] - q0[1])
        L = math.hypot(*d) or 1.0
        nrm = (-d[1] / L * h, d[0] / L * h)
        left.append([round(p[0] + nrm[0], 4), round(p[1] + nrm[1], 4)])
        right.append([round(p[0] - nrm[0], 4), round(p[1] - nrm[1], 4)])
    return left + right[::-1]


# ------------------------------------------------------- the 2D view
def handles(tool):
    return tool in (TRIM, EXTEND, FILLET, CHAMFER, "regions", "make_region",
                    "sk_construction")


PROMPTS = {TRIM: "Trim: click the piece of a line to remove.",
           EXTEND: "Extend: click near the end of a line to run on.",
           FILLET: "Sketch fillet: click a polygon / rectangle corner, "
                   "or two lines that meet.",
           CHAMFER: "Sketch chamfer: click a polygon / rectangle corner, "
                    "or two lines that meet.",
    "regions": "Extrude regions: click inside the regions to keep, then "
               "Enter or right-click.",
    "make_region": "Create region: click inside the regions to keep, then "
                   "Enter or right-click."}


def press(scene, event):
    from PyQt5.QtCore import Qt
    from . import sketch_constrain_ui as scu
    event.accept()
    if scene.tool in ("regions", "make_region") and \
            event.button() == Qt.RightButton:
        from . import sketch_regions
        sketch_regions.finish(scene)
        return
    if event.button() != Qt.LeftButton:
        scene._sk_first = None
        return
    pos = event.scenePos()
    tool = scene.tool
    if tool == "sk_construction":
        from . import sketch_tools2
        sketch_tools2.construction_press(scene, event)
        return
    if tool in ("regions", "make_region"):
        from . import sketch_regions
        sketch_regions.press(scene, event)
        return
    if tool in (TRIM, EXTEND):
        hit = scu.pick(scene, pos, "line")
        if hit is None or hit[0].type != "line":
            scene.status.emit(PROMPTS[tool])
            return
        node = hit[0]
        p = _frame_point(scene, node, pos)
        if tool == TRIM:
            scene.status.emit("Trim: %s." % trim(scene.model, node, p))
        else:
            end = extend(scene.model, node, p)
            scene.status.emit("Extend: nothing ahead to meet." if end is
                              None else "Extended to (%g, %g)." % end)
        return
    round_ = tool == FILLET
    hit = scu.pick(scene, pos, "point")
    first = getattr(scene, "_sk_first", None)
    if hit is not None and hit[0].type in ("polygon", "rect") and \
            hit[1].startswith("v"):
        size = _ask(scene, tool)
        if size is None:
            return
        try:
            corner(scene.model, hit[0], int(hit[1][1:]), size, round_)
        except ValueError as exc:
            scene.status.emit(str(exc))
        return
    line = scu.pick(scene, pos, "line")
    if line is None or line[0].type != "line":
        scene.status.emit(PROMPTS[tool])
        return
    if first is None or first is line[0]:
        scene._sk_first = line[0]
        scene.status.emit("Now click the other line.")
        return
    scene._sk_first = None
    size = _ask(scene, tool)
    if size is None:
        return
    try:
        line_corner(scene.model, first, line[0], size, round_)
    except ValueError as exc:
        scene.status.emit(str(exc))


def _frame_point(scene, node, pos):
    from .view2d_edit import in_frame_coords
    for it in scene.items():
        if getattr(it, "node", None) is node:
            q = in_frame_coords(it, pos)
            return (q.x(), q.y())
    return (pos.x(), pos.y())


def _ask(scene, tool):
    hook = getattr(scene, "ask_value", None)
    label = "radius" if tool == FILLET else "distance"
    if hook is not None:
        text = hook(tool, 2.0)
    else:
        from PyQt5.QtWidgets import QInputDialog
        views = scene.views()
        text, ok = QInputDialog.getText(
            views[0] if views else None, "Sketch " + label,
            "Corner %s (mm):" % label, text="2")
        if not ok:
            return None
    try:
        v = float(text)
    except (TypeError, ValueError):
        scene.status.emit("A %s is a number of mm." % label)
        return None
    return v if v > 0 else None


def drop(scene):
    scene._sk_first = None
    if getattr(scene, "_regions", None) is not None:
        from . import sketch_regions
        sketch_regions.drop(scene)


TIPS = {
    TRIM: ("Trim", "Removes the piece of a line between the lines or "
           "circles that cross it.",
           ["Click the piece to remove.", "Nothing crosses it: the whole "
            "line goes. A middle piece splits the line in two."], None),
    EXTEND: ("Extend", "Runs a line on until it meets another line or a "
             "circle.", ["Click near the end to extend."], None),
    FILLET: ("Sketch fillet", "Rounds a corner of a polygon or rectangle, "
             "or where two lines meet.",
             ["Click the corner (or one line, then the other).",
              "Type the radius."], "A rectangle becomes a polygon."),
    CHAMFER: ("Sketch chamfer", "Cuts a corner off at 45° by a distance.",
              ["Click the corner (or one line, then the other).",
               "Type the distance."], None),
    "regions": ("Extrude regions",
                "Overlapping sketch shapes split into regions; the ones "
                "you click are extruded as one solid (SolidWorks' "
                "selected contours).",
                ["Draw overlapping shapes — a rectangle and a perimeter "
                 "circle at one end make three regions.",
                 "Click inside each region to keep (click again to drop "
                 "it); they turn blue.",
                 "Press Enter or right-click: one Linear extrude of "
                 "those regions is made and the sketch shapes are "
                 "hidden."],
                "Set the height in Properties, or drag the arrow in 3D."),
    "make_region": ("Create region",
                    "Makes a Regions node from overlapping sketch shapes: "
                    "the regions you click, the shapes inside it with "
                    "their Smart Dimensions — extrude or revolve it later.",
                    ["Draw overlapping shapes (a rectangle and a circle "
                     "on it).",
                     "Click inside each region to keep; they turn blue.",
                     "Enter or right-click makes the Regions node."],
                    "Change a Smart Dimension and the region follows."),
}


def panel_actions(win):
    acts = getattr(win, "_sketch_modify_actions", None)
    if acts is not None:
        return acts
    from PyQt5.QtWidgets import QAction
    from . import icons, language, toolbars, tooltips
    tooltips.TIPS.update(TIPS)
    acts = []
    for tool, glyph, label in TOOLS:
        act = QAction(icons.icon(glyph, icons.family_color("draw")),
                      language.tr(label), win)
        act.setData(tool)
        act.setCheckable(True)
        toolbars.remember_glyph(act, glyph, "draw")
        tooltips.apply(act, tool)
        if tool in ("regions", "make_region"):
            act.triggered.connect(lambda _=False, t=tool: _regions(win, t))
        else:
            act.triggered.connect(lambda _=False, t=tool: win._set_tool(t))
        win._tool_group.addAction(act)
        acts.append(act)
    win._sketch_modify_actions = acts
    return acts


def _regions(win, tool="regions"):
    """Extrude regions: in the sketch (Fusion / SolidWorks sketch mode)
    the 2D tool; otherwise straight on the 3D view, where the user sees
    the part (2026-10-25)."""
    from . import sketch_mode, sketch_regions
    if tool == "make_region" and sketch_regions.from_selection(win):
        return                           # the selected shapes, at once
    if sketch_mode.sketching(win):
        win._set_tool(tool)
    elif not sketch_regions.start_3d(win,
                                     make_only=tool == "make_region"):
        win._set_tool(tool)


# ---------------------------------------- the OpenSCAD program, both ways
HELPER = """\
module kcad_corners(points = [], corners = []) {
    children();
}"""


def uses(root):
    return any(n.type == "polygon" and n.params.get("corners")
               for n in root.walk())


def _b_corners(parser, positional, named):
    from .model import CadNode
    node = CadNode("union", "Group", {})
    node._kcad_corners = (named.get("points"), named.get("corners"))
    return node


BUILDERS = {"kcad_corners": _b_corners}


def fold(node):
    """kcad_corners(points, corners) polygon(rounded): the polygon back
    with its sharp corners and its corner rows."""
    info = getattr(node, "_kcad_corners", None)
    if info is None:
        return None
    if len(node.children) != 1 or node.children[0].type != "polygon":
        return None
    poly = node.children[0]
    pts, rows = info
    try:
        poly.params["points"] = [[float(x), float(y)] for x, y in pts]
        poly.params["corners"] = [[int(r[0]), float(r[1]),
                                   int(r[2]) if len(r) > 2 else 0]
                                  for r in rows]
    except (TypeError, ValueError):
        return None
    node.remove(poly)
    poly.visible = node.visible and poly.visible
    return poly


# ------------------------------------------------------------------ MCP
def run_mcp(window, params):
    """The `sketch_modify` MCP tool: trim / extend a line at a point,
    fillet / chamfer a polygon or rectangle corner or where two lines
    meet. Points are in the shapes' own sketch coordinates."""
    model = window.model
    action = params.get("action")

    def node(nid):
        n = model.find(int(nid))
        if n is None:
            raise ValueError("No node with id %r." % nid)
        return n

    def point():
        p = params.get("point")
        if not (isinstance(p, (list, tuple)) and len(p) >= 2):
            raise ValueError("Give point [x, y] on the line.")
        return (float(p[0]), float(p[1]))
    if action in ("trim", "extend"):
        line = node(params["node_id"])
        if line.type != "line":
            raise ValueError("%s works on a line; %s is a %s."
                             % (action, line.name, line.type))
        if action == "trim":
            done = trim(model, line, point())
            return {"result": done,
                    "line": None if done == "deleted"
                    else dict(line.params)}
        end = extend(model, line, point())
        if end is None:
            raise ValueError("Nothing for that end to reach.")
        return {"result": "extended", "line": dict(line.params)}
    if action in ("fillet", "chamfer"):
        size = float(params.get("size", 0) or 0)
        if size <= 0:
            raise ValueError("Give size > 0 (radius or chamfer distance).")
        round_ = action == "fillet"
        ids = params.get("node_ids") or []
        if len(ids) == 2:
            new = line_corner(model, node(ids[0]), node(ids[1]), size,
                              round_)
            return {"result": action, "node_id": getattr(new, "id", None)}
        shape = node(params["node_id"])
        if shape.type not in ("polygon", "rect"):
            raise ValueError("Fillet a polygon / rectangle corner (node_id "
                             "+ vertex), or two lines (node_ids).")
        out = corner(model, shape, int(params.get("vertex", 0)), size,
                     round_)
        shape = out if hasattr(out, "params") else shape
        return {"result": action, "node_id": shape.id,
                "corners": shape.params.get("corners", [])}
    raise ValueError("action is trim, extend, fillet or chamfer.")
