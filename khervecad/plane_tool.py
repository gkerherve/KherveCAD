# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""SolidWorks' **Plane** (2026-11-13, the user: "where we create a plane
we click on a face or a plane or somewhere on the things, and it creates
the plane ... as easy as the one for Extruded Boss"). One window, up to
three references clicked in the 3D view or the tree, and the plane they
make shown at once:

- a face / plane            -> offset from it by the Distance (Flip)
- two parallel planes        -> the mid-plane between them
- two planes at an angle     -> the plane that bisects them
- a plane + an edge / axis   -> through the edge at the Angle to the plane
                                (when the edge crosses the plane: through
                                the edge, square to the plane)
- a plane + a point          -> parallel to the plane through the point
- an edge / axis             -> square to it through the point clicked
- an edge + a point          -> containing both
- two edges                  -> containing both
- two points                 -> square to the line between them, halfway
- three points               -> through the three

A face gives a plane, a ROUND face its axis, an edge a line — or a point
when the click lands near one of its ends — Front / Top / Right Plane
(tree rows or the planes drawn in 3D) and reference planes a plane, a
reference axis a line, a reference point or Origin a point. OK adds an
ordinary ref_plane (refgeom_ui.add_plane). `compute` is the Qt-free rule.
"""

import math

KINDS = ("plane", "line", "point")
#: how near an edge's end a click counts as that corner (screen px)
CORNER_PX = 12.0

TIPS = {
    "ref_plane_tool": (
        "Plane",
        "A reference plane from what you click — a face or plane (offset), "
        "two of them (between them), a face and an edge (at an angle), "
        "edges, points. Sketch on it, mirror about it, cut up to it.",
        ["Click Plane — its window opens beside the view.",
         "Click a face, a plane (Front / Top / Right in the tree or the "
         "3D view), an edge or a corner: up to three references.",
         "The plane shows at once; set the Distance or the Angle.",
         "OK adds it to the tree."],
        "Click a reference box to replace that reference."),
}


# --------------------------------------------------------------- maths
def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _add(a, b):
    return [a[i] + b[i] for i in range(3)]


def _mul(a, k):
    return [c * k for c in a]


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def _len(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _len(a)
    if n < 1e-12:
        raise ValueError("zero direction")
    return [c / n for c in a]


def _tidy(v):
    return [round(float(c), 6) + 0.0 for c in v]


def compute(refs, distance=10.0, flip=False, angle=90.0):
    """``(origin, normal, description)`` of the plane *refs* make —
    refs: [{"kind": plane|line|point, "point": [x, y, z], "dir": [...],
    "text": "..."}] — or ``(None, None, what is missing)``."""
    from . import refgeom
    refs = [r for r in refs if r]
    if not refs:
        return None, None, "Click a face, a plane, an edge or a point."
    planes = [r for r in refs if r["kind"] == "plane"]
    lines = [r for r in refs if r["kind"] == "line"]
    points = [r for r in refs if r["kind"] == "point"]
    try:
        if len(points) >= 3:
            o, n = refgeom.plane_three_points(*[p["point"]
                                                for p in points[:3]])
            return _tidy(o), _tidy(n), "Through three points"
        if planes and not lines and not points[:1] and len(planes) == 1:
            n = _unit(planes[0]["dir"])
            d = -distance if flip else distance
            o = _add(planes[0]["point"], _mul(n, d))
            return _tidy(o), _tidy(n), "Offset %g mm from %s" % (
                d, planes[0]["text"])
        if len(planes) >= 2:
            a, b = planes[0], planes[1]
            n1, n2 = _unit(a["dir"]), _unit(b["dir"])
            if _len(_cross(n1, n2)) < 1e-6:
                # parallel: halfway between, along the first's normal
                mid = _mul(_add(a["point"], b["point"]), 0.5)
                o = _add(a["point"], _mul(n1, _dot(_sub(mid, a["point"]),
                                                   n1)))
                return _tidy(o), _tidy(n1), "Mid-plane of %s and %s" % (
                    a["text"], b["text"])
            p, _d = refgeom.axis_of_planes(a["point"], n1, b["point"], n2)
            # the bisector BETWEEN two faces: their normals point away
            # from each other, so it is the difference that lies between
            diff, summ = _sub(n1, n2), _add(n1, n2)
            n = _unit(diff if _len(diff) >= _len(summ) else summ)
            return _tidy(p), _tidy(n), "Bisects %s and %s" % (
                a["text"], b["text"])
        if planes and lines:
            pl, ln = planes[0], lines[0]
            n = _unit(pl["dir"])
            d = _unit(ln["dir"])
            a = ln["point"]
            if abs(_dot(d, n)) < 1e-3:
                b = _add(a, d)
                o, nn = refgeom.plane_at_angle(a, b, n, angle)
                return _tidy(o), _tidy(nn), "Through %s at %g° to %s" % (
                    ln["text"], angle, pl["text"])
            o, nn = refgeom.plane_from_axis(a, d, n)
            return _tidy(o), _tidy(nn), "Through %s, square to %s" % (
                ln["text"], pl["text"])
        if planes and points:
            n = _unit(planes[0]["dir"])
            return _tidy(points[0]["point"]), _tidy(n), \
                "Parallel to %s through %s" % (planes[0]["text"],
                                               points[0]["text"])
        if len(lines) >= 2:
            a, b = lines[0], lines[1]
            n = _cross(a["dir"], b["dir"])
            if _len(n) < 1e-9:                       # parallel lines
                n = _cross(a["dir"], _sub(b["point"], a["point"]))
            return _tidy(a["point"]), _tidy(_unit(n)), \
                "Through %s and %s" % (a["text"], b["text"])
        if lines and points:
            ln, pt = lines[0], points[0]
            n = _cross(ln["dir"], _sub(pt["point"], ln["point"]))
            if _len(n) < 1e-9:       # the point is on the line: square to it
                return _tidy(pt["point"]), _tidy(_unit(ln["dir"])), \
                    "Square to %s at %s" % (ln["text"], pt["text"])
            return _tidy(ln["point"]), _tidy(_unit(n)), \
                "Through %s and %s" % (ln["text"], pt["text"])
        if lines:
            ln = lines[0]
            return _tidy(ln["point"]), _tidy(_unit(ln["dir"])), \
                "Square to %s" % ln["text"]
        if len(points) == 2:
            a, b = points[0]["point"], points[1]["point"]
            return _tidy(_mul(_add(a, b), 0.5)), _tidy(_unit(_sub(b, a))), \
                "Halfway between %s and %s, square to them" % (
                    points[0]["text"], points[1]["text"])
    except ValueError as exc:
        return None, None, "These references make no plane (%s)." % exc
    return None, None, "Add a face, a plane or an edge to that point."


# ================================================================== Qt
def action(win):
    act = getattr(win, "_plane_tool_action", None)
    if act is not None:
        return act
    from PyQt5.QtWidgets import QAction
    from . import icons, language, toolbars, tooltips
    tooltips.TIPS.update(TIPS)
    act = QAction(icons.icon("mdi.square-outline"), language.tr("Plane"),
                  win)
    act.setData("ref_plane_tool")
    toolbars.remember_glyph(act, "mdi.square-outline", "transform")
    tooltips.apply(act, "ref_plane_tool")
    act.triggered.connect(lambda _=False: start(win))
    win._plane_tool_action = act
    return act


def _panel(window):
    return getattr(window, "_plane_tool_panel", None)


BOXES = ("ref1", "ref2", "ref3")
CAPTIONS = ("First reference", "Second reference", "Third reference")


def start(window):
    from . import language
    close(window)
    st = window._plane_tool = dict(refs=[None, None, None], active="ref1",
                                   distance=10.0, flip=False, angle=90.0,
                                   result=None)
    for n in window.builder.active_tree().selected_nodes():
        ref = _ref_of_node(window, n)
        if ref is not None:
            _put(st, ref)
    from .tool_panel import ToolPanel
    panel = ToolPanel(window.view3d, language.tr("Plane"),
                      on_ok=lambda: ok(window),
                      on_cancel=lambda: close(window))
    panel.hint(language.tr("Click faces, planes, edges or corners — in "
                           "3D or the tree."))
    for key, cap in zip(BOXES, CAPTIONS):
        panel.selection(key, language.tr(cap),
                        on_activate=lambda k: _activate(window, k))
    panel.section(language.tr("Plane"))
    panel.result = panel.hint("")
    panel.number("distance", language.tr("Distance"), st["distance"],
                 lambda v: _set(window, "distance", v), minimum=-1e6)
    panel.check("flip", language.tr("Flip offset"), False,
                lambda on: _set(window, "flip", bool(on)))
    panel.number("angle", language.tr("Angle"), st["angle"],
                 lambda v: _set(window, "angle", v), suffix=" °",
                 minimum=-360, maximum=360)
    panel.finish()
    window._plane_tool_panel = panel
    _hooks(window, True)
    panel.open()
    _activate(window, _next_box(st))
    return panel


def _next_box(st):
    for key, r in zip(BOXES, st["refs"]):
        if r is None:
            return key
    return BOXES[-1]


def _put(st, ref):
    i = BOXES.index(st["active"])
    st["refs"][i] = ref
    st["active"] = _next_box(st)


def _set(window, key, value):
    st = getattr(window, "_plane_tool", None)
    if st:
        st[key] = value
        _refresh(window)


def _refresh(window):
    from . import language
    st = getattr(window, "_plane_tool", None)
    panel = _panel(window)
    if not st or panel is None:
        return
    for key, r in zip(BOXES, st["refs"]):
        panel.boxes[key].set_text(
            "%s (%s)" % (r["text"], language.tr(r["kind"])) if r else
            language.tr("Face, plane, edge or point"))
    o, n, text = compute(st["refs"], st["distance"], st["flip"],
                         st["angle"])
    st["result"] = (o, n) if o is not None else None
    panel.result.setText(language.tr(text))
    kinds = [r["kind"] for r in st["refs"] if r]
    offset = kinds == ["plane"]
    angled = "plane" in kinds and "line" in kinds and \
        "Through" in text and "°" in text
    panel.show_row("distance", offset)
    panel.show_row("flip", offset)
    panel.show_row("angle", angled)
    panel.set_ok_enabled(st["result"] is not None)
    panel.adjustSize()
    window.view3d.update()


def _activate(window, key):
    from . import plane_pick
    st = getattr(window, "_plane_tool", None)
    panel = _panel(window)
    if not st or panel is None:
        return
    st["active"] = key
    panel.set_active(key)
    view = window.view3d
    if view._pick_cb is not None:
        view._pick_cb = None
        view._end_pick_mode()
    window._plane_pick = {"half": plane_pick._half(window), "hover": None,
                          "on_plane": None, "plane_tool": True}
    _refresh(window)
    _arm(window)


# ----------------------------------------------------- the references
def _main_plane(plane):
    from . import plane_pick, refgeom
    for _n, key, o, n in refgeom.MAIN_PLANES:
        if key == plane:
            return dict(kind="plane", point=list(o), dir=list(n),
                        text=plane_pick.name_of(plane))
    return None


def _ref_of_node(window, node):
    """A reference plane / axis / point of the tree as a reference."""
    import numpy as np
    from . import mesh, refgeom
    if node.type not in ("ref_plane", "ref_axis", "ref_point"):
        return None
    scope = window._render_scope()[0]
    stop = None if scope is window.model.root else scope
    m = np.array(mesh.ancestor_matrix(node, {}, stop=stop), dtype=float)

    def pt(p):
        return [float(c) for c in (m @ np.array([p[0], p[1], p[2], 1.0])
                                   )[:3]]

    def vec(v):
        return [float(c) for c in m[:3, :3] @ np.array(v, dtype=float)]
    name = node.name or node.type
    if node.type == "ref_plane":
        o, n = refgeom.plane_of(node)
        nn = np.linalg.inv(m[:3, :3]).T @ np.array(n, dtype=float)
        return dict(kind="plane", point=pt(o), dir=[float(c) for c in nn],
                    text=name)
    if node.type == "ref_axis":
        p, d = refgeom.axis_of(node)
        return dict(kind="line", point=pt(p), dir=vec(d), text=name)
    q = mesh.rp(node, {})
    return dict(kind="point", point=pt((float(q.get("x", 0)),
                                        float(q.get("y", 0)),
                                        float(q.get("z", 0)))), text=name)


def _ref_of_pick(window, desc, tris):
    """A clicked face / edge as a reference: a flat face a plane, a round
    one its axis, an edge a line — or its corner, clicked near it."""
    from . import refgeom, refgeom_ui
    kind = desc.get("kind")
    if kind == "edge" and desc.get("seg"):
        a, b = [list(p) for p in desc["seg"]]
        hit = list(desc.get("point") or desc.get("pos"))
        view = window.view3d
        try:
            mm_px = view.distance / max(view._focal(), 1e-6)
        except Exception:
            mm_px = 0.25
        end = min((a, b), key=lambda e: math.dist(e, hit))
        if math.dist(end, hit) <= CORNER_PX * mm_px:
            return dict(kind="point", point=end, text="Corner")
        d = _sub(b, a)
        if _len(d) < 1e-9:
            return None
        return dict(kind="line", point=hit, dir=d, text="Edge")
    if kind != "face":
        return None
    region = refgeom_ui.smooth_region(tris, desc["pos"]) if tris else []
    if len(region) >= 6:
        try:
            normals = []
            for t in region:
                n = _cross(_sub(t[1], t[0]), _sub(t[2], t[0]))
                if _len(n) > 1e-12:
                    normals.append(_unit(n))
            turn = max(math.degrees(math.acos(max(-1.0, min(1.0, _dot(
                normals[0], q))))) for q in normals)
            if turn > 5.0:
                p, d = refgeom.axis_of_cylinder(region)
                return dict(kind="line", point=list(p), dir=list(d),
                            text="Round face's axis")
        except (ValueError, IndexError):
            pass
    return dict(kind="plane", point=list(desc.get("pos")),
                dir=list(desc["dir"]), text="Face")


def _arm(window):
    from . import language, meshedit_ui, plane_pick
    st = window._plane_tool
    view = window.view3d
    parts = meshedit_ui._parts(window) or []
    by_node = {id(n): t for n, t in parts}

    def picked(desc, node=None):
        if getattr(window, "_plane_tool", None) is not st:
            return
        pp = getattr(window, "_plane_pick", None)
        if pp:
            pp.pop("pos", None)
        pos = st.pop("pos", None)
        if desc is None and pos is None:          # Esc: Cancel
            close(window)
            return
        plane = plane_pick.hit(window, pos) if pos is not None else None
        if desc is not None and plane is not None:
            depth = plane_pick._depths(window, pos).get(plane)
            at = desc.get("point") or desc.get("pos")
            eye, _r, _u, fwd = view._camera()
            near = sum((at[i] - eye[i]) * fwd[i] for i in range(3))
            if depth is not None and near > depth:
                desc = None
            else:
                plane = None
        ref = None
        if desc is not None:
            ref = _ref_of_pick(window, desc, by_node.get(id(node), []))
        elif plane is not None:
            ref = _main_plane(plane)
        if ref is not None:
            _put(st, ref)
            panel = _panel(window)
            if panel is not None:
                panel.set_active(st["active"])
        _refresh(window)
        _arm(window)

    view.start_pick(picked, groups=parts, done=False,
                    banner=language.tr("Plane: click a face, a plane, an "
                                       "edge or a corner · OK in its "
                                       "window adds it"),
                    labeler=lambda desc, n: getattr(n, "name", ""))


def plane_row(window, plane):
    st = getattr(window, "_plane_tool", None)
    if not st:
        return False
    _put(st, _main_plane(plane))
    _activate(window, st["active"])
    return True


def origin_row(window):
    st = getattr(window, "_plane_tool", None)
    if not st:
        return False
    _put(st, dict(kind="point", point=[0.0, 0.0, 0.0], text="Origin"))
    _activate(window, st["active"])
    return True


def tree_selected(window, nodes):
    st = getattr(window, "_plane_tool", None)
    if not st:
        return
    for n in nodes:
        ref = _ref_of_node(window, n)
        if ref is not None:
            _put(st, ref)
    _activate(window, st["active"])


def _hooks(window, on):
    if not hasattr(window, "_plane_tool_slot"):
        window._plane_tool_slot = lambda nodes: tree_selected(window, nodes)

        def note(pos):
            st = getattr(window, "_plane_tool", None)
            if st is not None:
                st["pos"] = pos
            return False
        view = window.view3d
        view.release_hooks = list(getattr(view, "release_hooks", ())) + \
            [note]
        view.overlay_painters.append(
            lambda painter, project: paint(window, painter, project))
    from .mirror_feature import _trees
    for tree in _trees(window):
        try:
            if on:
                tree.selection_changed.connect(window._plane_tool_slot)
            else:
                tree.selection_changed.disconnect(window._plane_tool_slot)
        except (TypeError, RuntimeError, AttributeError):
            pass


def paint(window, painter, project):
    """The plane the references make, orange and see-through."""
    st = getattr(window, "_plane_tool", None)
    if not st or not st.get("result"):
        return
    from PyQt5.QtCore import QPointF
    from PyQt5.QtGui import QColor, QPen, QPolygonF
    from . import refgeom_ui
    o, n = st["result"]
    size = refgeom_ui._half(window) * 1.2
    corners = refgeom_ui.plane_corners(o, n, size)
    pts = [project(c) for c in corners]
    if any(p is None for p in pts):
        return
    painter.save()
    try:
        painter.setRenderHint(painter.Antialiasing, True)
        painter.setPen(QPen(QColor(230, 120, 20), 2.0))
        painter.setBrush(QColor(240, 150, 40, 70))
        painter.drawPolygon(QPolygonF([QPointF(p[0], p[1]) for p in pts]))
    finally:
        painter.restore()


def ok(window):
    from . import refgeom_ui
    st = getattr(window, "_plane_tool", None)
    if not st or not st.get("result"):
        return None
    o, n = st["result"]
    close(window)
    return refgeom_ui.add_plane(window, o, n)


def close(window):
    st = getattr(window, "_plane_tool", None)
    panel = _panel(window)
    if st is None and panel is None:
        return
    window._plane_tool = None
    window._plane_tool_panel = None
    _hooks(window, False)
    view = window.view3d
    if view._pick_cb is not None:
        view._pick_cb = None
        view._end_pick_mode()
    pp = getattr(window, "_plane_pick", None)
    if pp and pp.get("plane_tool"):
        window._plane_pick = None
    if panel is not None:
        panel.hide()
        panel.deleteLater()
    view.update()
