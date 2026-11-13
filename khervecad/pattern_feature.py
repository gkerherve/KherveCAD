# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""SolidWorks' **Circular Pattern** and **Linear Pattern** of features and
bodies (2026-11-13, the user: "as nice as the circular sketch pattern ...
a pop-up window, and you select — in the tree, the part, the Extruded
Boss or the Extruded Cut — and we make it circular through a point").

Each is a ToolPanel (tool_panel.py) beside the view, built like the Mirror
window:

- **Features / bodies to pattern** — the tree's selection, rows clicked in
  the tree (History: Boss-Extrude, Cut-Extrude...) or parts clicked in 3D;
- **Axis** (circular) — a round face (its axis through its centre), a
  flat face (its normal through the click), an edge, Front / Top / Right
  Plane (in the tree or in 3D: its normal through the origin) or a
  reference axis / plane of the tree; **Centre point** — a point clicked
  on the part, a reference point, or typed X / Y / Z: the axis passes
  through it;
- **Direction** (linear) — an edge, a face's normal, a plane's normal or
  a reference axis; optional **Direction 2**;
- angle / spacing, instances, equal spacing, reverse.

The copies show at once (the pattern node is made as soon as there is
something to pattern, and follows every change); OK keeps it, Cancel or
Esc takes it away. What is made is the ordinary `pattern` node (polar:
any axis through any centre, pattern.py), one per parent, the axis
carried into that parent's frame like Mirror's plane — so a feature
sketched on a turned face patterns about the PART's axis. The window's
choices ride on the node (`params["pattern_feature"]`): pressing the
button with that pattern selected opens it again to edit.
"""

import math

KEY = "pattern_feature"
CIRCULAR, LINEAR = "circular", "linear"
#: the main planes' normals by plane_pick key
MAIN = {"Front (XZ)": (0.0, 1.0, 0.0), "Top (XY)": (0.0, 0.0, 1.0),
        "Side (YZ)": (1.0, 0.0, 0.0)}
TITLE = {CIRCULAR: "Circular Pattern", LINEAR: "Linear Pattern"}

TIPS = {
    "circular_pattern": (
        "Circular Pattern",
        "Copies of features or bodies round an axis — bolt holes round a "
        "flange, spokes, ribs. The copies follow every edit of the "
        "original.",
        ["Click Circular Pattern — its window opens beside the view.",
         "Features / bodies: click their rows in the tree (History) or "
         "the parts in the 3D view (the tree's selection is taken at "
         "once).",
         "Axis: click a round face (its own axis), a flat face or an "
         "edge, or Front / Top / Right Plane in the tree or the 3D view "
         "(its normal); Centre point: click a point, or type X Y Z.",
         "Set the angle and the instances (Equal spacing spreads them "
         "over the angle); the copies show at once. OK keeps them."],
        "Select the pattern and click the button again to change it."),
    "linear_pattern": (
        "Linear Pattern",
        "Copies of features or bodies in a row (and a second row with "
        "Direction 2) — a line of holes, a grid of bosses.",
        ["Click Linear Pattern — its window opens beside the view.",
         "Features / bodies: rows in the tree or parts in the 3D view.",
         "Direction: click an edge, a face (its normal) or Front / Top / "
         "Right Plane; set the spacing and the instances.",
         "Tick Direction 2 for a grid and click its direction. OK keeps "
         "it."],
        "Select the pattern and click the button again to change it."),
}


def _unit(v):
    ln = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(float(c) / ln for c in v)


def _r(v):
    return round(float(v), 6)


# ----------------------------------------------------------- the model
def _frame(window, parent):
    """The 4x4 matrix from *parent*'s frame to the scope's."""
    import numpy as np
    from . import mesh
    scope = window._render_scope()[0]
    stop = None if scope is window.model.root else scope
    return np.array(mesh.mat_mul(mesh.ancestor_matrix(parent, {}, stop=stop),
                                 mesh.node_matrix(parent, {})), dtype=float)


def _to_parent(window, parent, point, direction):
    """(point, unit direction, handedness) of a line in the scope's frame,
    in *parent*'s own frame; handedness -1 when that frame is mirrored
    (a turn then goes the other way round)."""
    import numpy as np
    m = _frame(window, parent)
    p = np.linalg.inv(m) @ np.array([point[0], point[1], point[2], 1.0])
    d = np.linalg.solve(m[:3, :3], np.array(direction, dtype=float))
    hand = -1.0 if np.linalg.det(m[:3, :3]) < 0 else 1.0
    return tuple(float(v) for v in p[:3]), _unit(d), hand


def circular_params(window, parent, st):
    """The polar pattern's params in *parent*'s frame."""
    centre, d, hand = _to_parent(window, parent, st["centre"], st["axis"])
    n = max(1, int(st["count"]))
    a = float(st["angle"])
    if not st["equal"]:
        step = a
        a = step * (n - 1) if abs(step * (n - 1)) < 360 else step * n
    if st["reverse"]:
        a = -a
    return dict(kind="polar", count=n, angle=_r(a * hand), axis="custom",
                vx=_r(d[0]), vy=_r(d[1]), vz=_r(d[2]),
                cx=_r(centre[0]), cy=_r(centre[1]), cz=_r(centre[2]),
                dz=0.0)


def linear_params(window, parent, direction, spacing, count, reverse):
    _p, d, _h = _to_parent(window, parent, (0.0, 0.0, 0.0), direction)
    s = -spacing if reverse else spacing
    return dict(kind="linear", count=max(1, int(count)),
                dx=_r(d[0] * s), dy=_r(d[1] * s), dz=_r(d[2] * s))


def make(window, nodes, st):
    """The pattern node(s) for *nodes* (one per parent; Direction 2 a
    second pattern round the first). The outermost node of each."""
    model = window.model
    groups = {}
    for n in nodes:
        if n.parent is not None and n is not model.root:
            groups.setdefault(id(n.parent), []).append(n)
    made = []
    for group in groups.values():
        parent = group[0].parent
        node = model.wrap_nodes(group, "pattern")
        if node is None:
            continue
        node.name = TITLE[st["kind"]]
        _fill(window, node, parent, st)
        made.append(node)
    return made


def _fill(window, node, parent, st):
    """Set *node* (and its Direction 2 partner) from the window's state."""
    model = window.model
    if st["kind"] == CIRCULAR:
        node.params.update(circular_params(window, parent, st))
    else:
        inner = node.children[0] if _is_second(node) else node
        inner.params.update(linear_params(
            window, parent, st["dir"], st["spacing"], st["count"],
            st["reverse"]))
        if st["use2"] and st.get("dir2") is not None and \
                not _is_second(node):
            outer = model.wrap_nodes([node], "pattern")
            outer.name = TITLE[LINEAR] + " (Direction 2)"
            outer.params["second"] = True
            node = outer
        if _is_second(node):
            if st["use2"] and st.get("dir2") is not None:
                node.params.update(linear_params(
                    window, parent, st["dir2"], st["spacing2"],
                    st["count2"], st["reverse2"]))
            else:
                inner = node.children[0]
                model.ungroup(node)
                node = inner
    node.params[KEY] = _spec(st)
    model.node_changed.emit(node)
    return node


def _is_second(node):
    return node.type == "pattern" and bool(node.params.get("second"))


def _spec(st):
    keep = ("kind", "axis", "centre", "angle", "count", "equal", "reverse",
            "dir", "spacing", "use2", "dir2", "spacing2", "count2",
            "reverse2", "axis_text", "centre_text", "dir_text", "dir2_text")
    return {k: (list(v) if isinstance(v, tuple) else v)
            for k, v in st.items() if k in keep}


def _defaults(kind):
    return dict(kind=kind, nodes=[], made=[], active="nodes", quiet=False,
                axis=(0.0, 0.0, 1.0), centre=(0.0, 0.0, 0.0), angle=360.0,
                count=4, equal=True, reverse=False,
                dir=(1.0, 0.0, 0.0), spacing=20.0,
                use2=False, dir2=(0.0, 1.0, 0.0), spacing2=20.0, count2=2,
                reverse2=False, axis_text="Z axis (Top Plane's normal)",
                centre_text="Origin", dir_text="X (Right Plane's normal)",
                dir2_text="Y (Front Plane's normal)")


# ================================================================== Qt
def actions(win):
    acts = getattr(win, "_pattern_actions", None)
    if acts is not None:
        return acts
    from PyQt5.QtWidgets import QAction
    from . import icons, language, toolbars, tooltips
    tooltips.TIPS.update(TIPS)
    acts = []
    for key, glyph, kind in (
            ("circular_pattern", "mdi.rotate-3d-variant", CIRCULAR),
            ("linear_pattern", "mdi.dots-horizontal", LINEAR)):
        act = QAction(icons.icon(glyph, icons.family_color("transform")),
                      language.tr(TIPS[key][0]), win)
        act.setData(key)
        toolbars.remember_glyph(act, glyph, "transform")
        tooltips.apply(act, key)
        act.triggered.connect(lambda _=False, k=kind: start(win, k))
        acts.append(act)
    win._pattern_actions = acts
    return acts


def _panel(window):
    return getattr(window, "_pattern_panel", None)


def start(window, kind):
    """The window, with the tree's selection as what to pattern — or, a
    pattern of ours selected, that pattern to change."""
    from . import language, meshedit_ui
    close(window)
    picked = [n for n in window.builder.active_tree().selected_nodes()
              if n is not window.model.root]
    st = _defaults(kind)
    if len(picked) == 1 and picked[0].parent is not None and \
            _is_second(picked[0].parent):
        picked = [picked[0].parent]          # Direction 2 holds it
    if len(picked) == 1 and picked[0].type == "pattern" and \
            isinstance(picked[0].params.get(KEY), dict) and \
            picked[0].params[KEY].get("kind") == kind:
        node = picked[0]
        spec = node.params[KEY]
        st.update({k: tuple(v) if isinstance(v, list) else v
                   for k, v in spec.items()})
        st["made"] = [node]
        inner = node.children[0] if _is_second(node) else node
        st["nodes"] = list(inner.children)
        st["editing"] = True
    else:
        if not picked and not meshedit_ui._parts(window):
            window.statusBar().showMessage(language.tr(
                "Nothing to pattern — add a part first."), 5000)
            return None
        _take(window, st, picked)
    window._pattern_state = st
    panel = _make_panel(window, kind)
    window._pattern_panel = panel
    _hooks(window, True)
    panel.open()
    _activate(window, "axis" if st["nodes"] and kind == CIRCULAR
              else "dir" if st["nodes"] else "nodes")
    _preview(window)
    return panel


def _take(window, st, nodes):
    """Tree rows into the boxes: reference geometry to the axis /
    direction / centre, everything else to what is patterned."""
    from . import refgeom
    rest = []
    for n in nodes:
        if n.type == "ref_axis":
            p, d = _scope_line(window, n, refgeom.axis_of(n))
            _set_axis(st, p, d, n.name or "Axis")
        elif n.type == "ref_plane":
            p, d = _scope_line(window, n, refgeom.plane_of(n))
            _set_axis(st, p, d, n.name or "Plane")
        elif n.type == "ref_point":
            from . import mesh
            q = mesh.rp(n, {})
            p, _d = _scope_line(window, n, ((float(q.get("x", 0)),
                                             float(q.get("y", 0)),
                                             float(q.get("z", 0))),
                                            (0.0, 0.0, 1.0)))
            st["centre"], st["centre_text"] = p, n.name or "Point"
        else:
            rest.append(n)
    if rest:
        st["nodes"] = rest


def _scope_line(window, node, pd):
    """A reference's (point, direction) — or (point, _) — in the scope."""
    import numpy as np
    if not isinstance(pd[0], (list, tuple)):
        pd = (pd, (0.0, 0.0, 1.0))
    point, d = pd
    m = _frame(window, node.parent) if node.parent is not None else \
        np.eye(4)
    p = m @ np.array([point[0], point[1], point[2], 1.0])
    v = m[:3, :3] @ np.array(d, dtype=float)
    return tuple(float(c) for c in p[:3]), _unit(v)


def _set_axis(st, point, direction, text):
    if st["kind"] == CIRCULAR:
        st["axis"], st["centre"] = _unit(direction), tuple(point)
        st["axis_text"], st["centre_text"] = text, "On " + text
    else:
        key = "dir2" if st["active"] == "dir2" else "dir"
        st[key], st[key + "_text"] = _unit(direction), text


def _make_panel(window, kind):
    from . import language
    from .tool_panel import ToolPanel
    st = window._pattern_state
    panel = ToolPanel(window.view3d, language.tr(TITLE[kind]),
                      on_ok=lambda: ok(window),
                      on_cancel=lambda: cancel(window))
    act = lambda k: _activate(window, k)              # noqa: E731
    panel.selection("nodes", language.tr("Features / bodies to pattern"),
                    on_activate=act)
    if kind == CIRCULAR:
        panel.section(language.tr("Axis"))
        panel.selection("axis", language.tr("Axis"), on_activate=act)
        panel.selection("centre", language.tr("Centre point"),
                        on_activate=act)
        for i, c in enumerate("XYZ"):
            panel.number("c" + c, language.tr("Centre ") + c,
                         st["centre"][i],
                         lambda v, i=i: _typed_centre(window, i, v),
                         minimum=-1e6)
        panel.section(language.tr("Parameters"))
        panel.number("angle", language.tr("Angle"), st["angle"],
                     lambda v: _set(window, "angle", v), suffix=" °",
                     minimum=-3600, maximum=3600)
        panel.number("count", language.tr("Instances"), st["count"],
                     lambda v: _set(window, "count", int(v)), suffix="",
                     minimum=1, maximum=1000, decimals=0)
        panel.check("equal", language.tr("Equal spacing"), st["equal"],
                    lambda on: _set(window, "equal", bool(on)))
        panel.check("reverse", language.tr("Reverse direction"),
                    st["reverse"], lambda on: _set(window, "reverse",
                                                   bool(on)))
    else:
        panel.section(language.tr("Direction 1"))
        panel.selection("dir", language.tr("Direction"), on_activate=act)
        panel.number("spacing", language.tr("Spacing"), st["spacing"],
                     lambda v: _set(window, "spacing", v), minimum=-1e6)
        panel.number("count", language.tr("Instances"), st["count"],
                     lambda v: _set(window, "count", int(v)), suffix="",
                     minimum=1, maximum=1000, decimals=0)
        panel.check("reverse", language.tr("Reverse direction"),
                    st["reverse"], lambda on: _set(window, "reverse",
                                                   bool(on)))
        panel.check("use2", language.tr("Direction 2"), st["use2"],
                    lambda on: _set(window, "use2", bool(on)))
        panel.selection("dir2", language.tr("Direction 2"),
                        on_activate=act)
        panel.number("spacing2", language.tr("Spacing 2"), st["spacing2"],
                     lambda v: _set(window, "spacing2", v), minimum=-1e6)
        panel.number("count2", language.tr("Instances 2"), st["count2"],
                     lambda v: _set(window, "count2", int(v)), suffix="",
                     minimum=1, maximum=1000, decimals=0)
        panel.check("reverse2", language.tr("Reverse direction 2"),
                    st["reverse2"], lambda on: _set(window, "reverse2",
                                                    bool(on)))
    panel.finish()
    return panel


def _shown_name(window, node):
    from .mirror_feature import _shown_name as shown
    return shown(window, node)


def _refresh(window):
    from . import language
    st = getattr(window, "_pattern_state", None)
    panel = _panel(window)
    if not st or panel is None:
        return
    names = [_shown_name(window, n) for n in st["nodes"]]
    panel.boxes["nodes"].set_text(", ".join(names) if names else
                                  language.tr("Click features in the tree "
                                              "or parts in 3D"))
    if st["kind"] == CIRCULAR:
        panel.boxes["axis"].set_text(st["axis_text"])
        panel.boxes["centre"].set_text(
            "%s  (%.4g, %.4g, %.4g)" % ((st["centre_text"],) +
                                        tuple(st["centre"])))
        for i, c in enumerate("XYZ"):
            panel.set_value("c" + c, st["centre"][i])
    else:
        panel.boxes["dir"].set_text(st["dir_text"])
        panel.boxes["dir2"].set_text(st["dir2_text"])
        for key in ("dir2", "spacing2", "count2", "reverse2"):
            if key == "dir2":
                panel.boxes[key].setVisible(st["use2"])
            else:
                panel.show_row(key, st["use2"])
    panel.set_ok_enabled(bool(st["made"]))
    window.view3d.update()


def _set(window, key, value):
    st = getattr(window, "_pattern_state", None)
    if not st:
        return
    st[key] = value
    _preview(window)


def _typed_centre(window, i, v):
    st = getattr(window, "_pattern_state", None)
    if not st:
        return
    c = list(st["centre"])
    c[i] = float(v)
    st["centre"], st["centre_text"] = tuple(c), "Typed"
    _preview(window)


def _preview(window):
    """Make or follow the pattern node(s) so the copies show now."""
    st = getattr(window, "_pattern_state", None)
    if not st:
        return
    st["quiet"] = True
    try:
        if st["nodes"] and not st["made"]:
            st["made"] = make(window, st["nodes"], st)
        else:
            out = []
            for node in st["made"]:
                if node.parent is None:
                    continue
                # (a pattern node adds no frame: its parent's is the one
                # the patterned nodes stood in)
                out.append(_fill(window, node, node.parent, st))
            st["made"] = out
    finally:
        st["quiet"] = False
    _refresh(window)


def _unmake(window):
    """Take the preview's pattern node(s) away, what they held kept."""
    st = window._pattern_state
    st["quiet"] = True
    try:
        for node in st["made"]:
            if node.parent is None:
                continue
            if _is_second(node):
                inner = node.children[0]
                window.model.ungroup(node)
                node = inner
            window.model.ungroup(node)
    finally:
        st["quiet"] = False
    st["made"] = []


def set_nodes(window, nodes):
    st = window._pattern_state
    if st.get("editing"):
        return                       # (the pattern being changed keeps them)
    if [n.id for n in nodes] == [n.id for n in st["nodes"]]:
        return
    _unmake(window)
    st["nodes"] = list(nodes)
    _preview(window)


# ------------------------------------------------------- 3D picking
def _drop_pick(window):
    view = window.view3d
    if view._pick_cb is not None:
        view._pick_cb = None
        view._end_pick_mode()


def _activate(window, key):
    from . import plane_pick
    st = getattr(window, "_pattern_state", None)
    panel = _panel(window)
    if not st or panel is None:
        return
    st["active"] = key
    panel.set_active(key)
    _drop_pick(window)
    if key in ("axis", "dir", "dir2"):
        window._plane_pick = {"half": plane_pick._half(window),
                              "hover": None, "on_plane": None,
                              "pattern": True}
    elif getattr(window, "_plane_pick", None) and \
            window._plane_pick.get("pattern"):
        window._plane_pick = None
    _refresh(window)
    _arm(window)


def _parts(window):
    from . import meshedit_ui
    st = window._pattern_state
    made = {id(n) for n in st["made"]}
    out = []
    for node, tris in meshedit_ui._parts(window) or []:
        out.append((node, tris))
    # a part already wrapped by the preview is clicked as what it holds
    return [(n.children[0] if id(n) in made and len(n.children) == 1
             else n, t) for n, t in out]


def _arm(window):
    from . import language, plane_pick
    st = window._pattern_state
    view = window.view3d
    parts = _parts(window)
    by_node = {id(n): t for n, t in parts}
    box = st["active"]

    def picked(desc, node=None):
        if getattr(window, "_pattern_state", None) is not st:
            return
        pp = getattr(window, "_plane_pick", None)
        if pp:
            pp.pop("pos", None)
        pos = st.pop("pos", None)
        if desc is None and pos is None:          # Esc: Cancel
            cancel(window)
            return
        if box == "nodes":
            if node is not None:
                nodes = list(st["nodes"])
                if node in nodes:
                    nodes.remove(node)
                else:
                    nodes.append(node)
                set_nodes(window, nodes)
            _arm(window)
            return
        if box == "centre":
            if desc is not None:
                st["centre"] = tuple(desc.get("pos") or desc.get("point"))
                st["centre_text"] = "Clicked point"
                _preview(window)
            _arm(window)
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
        if desc is not None:
            _from_pick(window, st, desc, by_node.get(id(node), []))
        elif plane is not None:
            _set_axis(st, (0.0, 0.0, 0.0), MAIN[plane],
                      plane_pick.name_of(plane) + "'s normal")
        if st["active"] == "dir2":
            st["use2"] = True
            panel = _panel(window)
            if panel is not None:
                panel.set_value("use2", True)
        _preview(window)
        _arm(window)

    banners = {
        "nodes": "{t}: click the features or parts to pattern ({n} chosen)",
        "axis": "{t}: click a round face (its axis), a face, an edge, or "
                "Front / Top / Right Plane",
        "centre": "{t}: click the point the axis passes through",
        "dir": "{t}: click an edge, a face or a plane for the direction",
        "dir2": "{t}: click an edge, a face or a plane for Direction 2"}
    view.start_pick(picked, groups=parts, done=False,
                    banner=language.tr(banners[box]).format(
                        t=language.tr(TITLE[st["kind"]]),
                        n=len(st["nodes"])),
                    labeler=lambda desc, n: getattr(n, "name", ""))


def _from_pick(window, st, desc, tris):
    """A clicked face / edge as the axis or a direction."""
    from . import refgeom, refgeom_ui
    if desc.get("kind") == "edge" and desc.get("seg"):
        a, b = desc["seg"]
        d = tuple(b[i] - a[i] for i in range(3))
        if math.sqrt(sum(c * c for c in d)) > 1e-9:
            mid = tuple((a[i] + b[i]) / 2 for i in range(3))
            _set_axis(st, mid, d, "Edge")
        return
    if desc.get("kind") != "face":
        return
    try:
        region = refgeom_ui.smooth_region(tris, desc["pos"])
        if len(region) < 3:
            raise ValueError
        p, d = refgeom.axis_of_cylinder(region)
        _set_axis(st, p, d, "Round face's axis")
    except (ValueError, Exception):
        _set_axis(st, desc["pos"], desc["dir"], "Face's normal")


# --------------------------------------------------- the tree feeds it
def _hooks(window, on):
    if not hasattr(window, "_pattern_tree_slot"):
        window._pattern_tree_slot = lambda nodes: tree_selected(window,
                                                                nodes)

        def note(pos):
            st = getattr(window, "_pattern_state", None)
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
                tree.selection_changed.connect(window._pattern_tree_slot)
            else:
                tree.selection_changed.disconnect(
                    window._pattern_tree_slot)
        except (TypeError, RuntimeError, AttributeError):
            pass


def tree_selected(window, nodes):
    st = getattr(window, "_pattern_state", None)
    if not st or st["quiet"] or not nodes:
        return
    made = {id(n) for n in st["made"]}
    nodes = [n for n in nodes if id(n) not in made
             and n is not window.model.root]
    refs = [n for n in nodes if n.type in ("ref_axis", "ref_plane",
                                           "ref_point")]
    rest = [n for n in nodes if n not in refs]
    if refs:
        _take(window, st, refs)
    if rest:
        set_nodes(window, rest)
    _preview(window)
    if rest and st["active"] == "nodes":
        _activate(window, "axis" if st["kind"] == CIRCULAR else "dir")


def plane_row(window, plane):
    """Front / Top / Right Plane clicked in the tree. True when taken."""
    from . import plane_pick
    st = getattr(window, "_pattern_state", None)
    if not st:
        return False
    if st["active"] not in ("axis", "dir", "dir2"):
        _activate(window, "axis" if st["kind"] == CIRCULAR else "dir")
    _set_axis(st, (0.0, 0.0, 0.0), MAIN[plane],
              plane_pick.name_of(plane) + "'s normal")
    if st["active"] == "dir2":
        st["use2"] = True
    _preview(window)
    return True


# ---------------------------------------------------------- the view
def paint(window, painter, project):
    """The axis (circular) through its centre, or the direction arrows
    (linear), in orange while the window is open."""
    st = getattr(window, "_pattern_state", None)
    if not st:
        return
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QColor, QPen
    from . import plane_pick
    half = plane_pick._half(window)
    painter.save()
    try:
        painter.setRenderHint(painter.Antialiasing, True)
        ink = QColor(230, 120, 20)
        if st["kind"] == CIRCULAR:
            c, d = st["centre"], st["axis"]
            a = project(tuple(c[i] - d[i] * half for i in range(3)))
            b = project(tuple(c[i] + d[i] * half for i in range(3)))
            if a is not None and b is not None:
                painter.setPen(QPen(ink, 2.0, Qt.DashDotLine))
                painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
            q = project(tuple(c))
            if q is not None:
                painter.setPen(QPen(ink, 2.0))
                painter.setBrush(QColor(255, 255, 255))
                painter.drawEllipse(QPointF(q[0], q[1]), 5, 5)
        else:
            dirs = [("dir", "reverse", "spacing", "count")]
            if st["use2"]:
                dirs.append(("dir2", "reverse2", "spacing2", "count2"))
            for dk, rk, sk, ck in dirs:
                d = st[dk]
                s = st[sk] * (-1 if st[rk] else 1) * max(1, st[ck] - 1)
                a = project((0.0, 0.0, 0.0))
                b = project(tuple(d[i] * s for i in range(3)))
                if a is None or b is None:
                    continue
                painter.setPen(QPen(ink, 2.0))
                painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
                ang = math.atan2(b[1] - a[1], b[0] - a[0])
                for side in (-1, 1):
                    t = ang + math.pi + side * 0.45
                    painter.drawLine(QPointF(b[0], b[1]), QPointF(
                        b[0] + 10 * math.cos(t), b[1] + 10 * math.sin(t)))
    finally:
        painter.restore()


# ------------------------------------------------------------ finish
def ok(window):
    st = getattr(window, "_pattern_state", None)
    if not st or not st["made"]:
        return []
    made = [n for n in st["made"] if n.parent is not None]
    close(window, keep=True)
    if made:
        window.builder.active_tree().select_nodes(made)
        window.statusBar().showMessage(
            "%s made — select it and click the button again to change it."
            % TITLE[st["kind"]], 7000)
    return made


def cancel(window):
    st = getattr(window, "_pattern_state", None)
    if st and not st.get("editing"):
        _unmake(window)
    close(window, keep=True)


def close(window, keep=False):
    st = getattr(window, "_pattern_state", None)
    panel = _panel(window)
    if st is None and panel is None:
        return
    window._pattern_state = None
    window._pattern_panel = None
    _hooks(window, False)
    _drop_pick(window)
    pp = getattr(window, "_plane_pick", None)
    if pp and pp.get("pattern"):
        window._plane_pick = None
    if panel is not None:
        panel.hide()
        panel.deleteLater()
    window.view3d.update()
