"""SolidWorks' Deform window, Curve to curve (2026-11-15): three boxes
filled by clicking in the tree — the **initial curve** (a sketch, or its
construction line), the **target curve** (a sketch) and the **bodies to
deform** — then OK. A sketch taken for a curve gives its lines and arcs
chained end to end; if the sketch holds construction lines only those
are the curve (the rod's centre line), else every line.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import language

BOXES = ("initial", "target", "bodies")
TYPES = (("point", "Point"), ("curve", "Curve to curve"))
AXES = {"z": (0.0, 0.0, 1.0), "x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0)}


def curve_lines(nodes):
    """The line / arc nodes *nodes* stand for as a curve: the lines of a
    sketch, construction ones alone when there are any."""
    lines = []
    for n in nodes:
        for c in n.walk():
            if c.type == "line" and c not in lines:
                lines.append(c)
    construction = [c for c in lines if c.params.get("modifier") == "%"]
    return construction or lines


def curve_of(nodes):
    """The polyline (world coordinates) of a curve box, or None."""
    from . import curve_deform
    lines = curve_lines(nodes)
    return curve_deform.sketch_curve(lines) if lines else None


def _panel(window):
    return getattr(window, "_deform_panel", None)


def _trees(window):
    out = [getattr(window.builder, "tree", None)]
    tab = getattr(window.builder, "object_tab", None)
    out.append(getattr(tab, "tree", None))
    return [t for t in out if t is not None]


def _hook(window, on):
    if not hasattr(window, "_deform_tree_slot"):
        window._deform_tree_slot = lambda nodes: tree_selected(window, nodes)
    for tree in _trees(window):
        try:
            if on:
                tree.selection_changed.connect(window._deform_tree_slot)
            else:
                tree.selection_changed.disconnect(window._deform_tree_slot)
        except (TypeError, RuntimeError, AttributeError):
            pass


def start(window):
    """Open the window; nodes selected when it opens are the bodies."""
    from .tool_panel import ToolPanel
    close(window)
    tr = language.tr
    pre = [n for n in window.builder.active_tree().selected_nodes()
           if n is not window.model.root and n.type != "line"]
    st = window._deform_state = dict(
        initial=[], target=[], bodies=pre, active="initial", quiet=False,
        type="curve", point=None, point_text="", axis="z", axis_vec=None,
        axis_text="", distance=10.0, radius=30.0, shape="medium",
        reverse=False)
    panel = ToolPanel(window.view3d, tr("Deform"),
                      on_ok=lambda: ok(window),
                      on_cancel=lambda: close(window))
    panel.section(tr("Deform type"))
    panel.choice("type", tr("Type"), [(k, tr(t)) for k, t in TYPES],
                 st["type"], lambda v: set_type(window, v))
    panel.hint(tr("Point: the Origin row of the tree (or a face), the "
                  "direction, then the bodies. Curve to curve: the initial "
                  "curve, the target curve, then the bodies."))
    panel.selection("point", tr("Deform point"),
                    on_activate=lambda k: activate(window, k))
    panel.choice("axis", tr("Direction"),
                 [("z", tr("Z axis (vertical)")), ("x", tr("X axis")),
                  ("y", tr("Y axis")), ("picked", tr("Picked axis / face"))],
                 st["axis"], lambda v: _set(window, "axis", v))
    panel.selection("axis", tr("Deform direction (axis, line or face)"),
                    on_activate=lambda k: activate(window, k))
    panel.number("distance", tr("Deform distance"), st["distance"],
                 lambda v: _set(window, "distance", float(v)),
                 minimum=-10000.0, maximum=10000.0, step=1.0)
    panel.number("radius", tr("Deform radius"), st["radius"],
                 lambda v: _set(window, "radius", float(v)),
                 minimum=0.1, maximum=10000.0, step=1.0)
    panel.choice("shape", tr("Shape options"),
                 [("minimum", tr("Minimum stiffness")),
                  ("medium", tr("Medium")),
                  ("maximum", tr("Maximum stiffness"))], st["shape"],
                 lambda v: _set(window, "shape", v))
    panel.check("reverse", tr("Reverse direction"), st["reverse"],
                lambda v: _set(window, "reverse", bool(v)))
    panel.selection("initial", tr("Initial curve"),
                    on_activate=lambda k: activate(window, k))
    panel.selection("target", tr("Target curve"),
                    on_activate=lambda k: activate(window, k))
    panel.selection("bodies", tr("Bodies to deform"),
                    on_activate=lambda k: activate(window, k))
    panel.finish()
    window._deform_panel = panel
    _hook(window, True)
    refresh(window)
    panel.open()
    set_type(window, "curve")
    return panel


def set_type(window, kind):
    """Point or Curve to curve: the boxes that belong to the type show."""
    st, panel = getattr(window, "_deform_state", None), _panel(window)
    if not st or panel is None:
        return
    st["type"] = kind
    panel.set_value("type", kind)
    point = kind == "point"
    panel.boxes["point"].setVisible(point)
    for key in ("initial", "target"):
        panel.boxes[key].setVisible(not point)
    for key in ("axis", "distance", "radius", "shape", "reverse"):
        panel.show_row(key, point)
    panel.boxes["axis"].setVisible(point and st["axis"] == "picked")
    refresh(window)
    activate(window, "point" if point else "initial")
    _arm_pick(window)


def _set(window, key, value):
    st = getattr(window, "_deform_state", None)
    if not st:
        return
    st[key] = value
    if key == "axis":
        panel = _panel(window)
        panel.boxes["axis"].setVisible(value == "picked")
        if value == "picked":
            activate(window, "axis")
    refresh(window)


def origin_row(window):
    """The tree's Origin row clicked: the deform point (True when the
    window took it)."""
    st = getattr(window, "_deform_state", None)
    if not st or st["type"] != "point":
        return False
    st["point"], st["point_text"] = (0.0, 0.0, 0.0), "Origin"
    refresh(window)
    if not st["bodies"]:
        activate(window, "bodies")
    return True


def _arm_pick(window):
    """Point type: a face clicked in 3D gives the point (and, in the
    direction box, its normal)."""
    st = getattr(window, "_deform_state", None)
    view = window.view3d
    if getattr(view, "_pick_cb", None) is not None:
        view._pick_cb = None
        view._end_pick_mode()
    if not st or st["type"] != "point":
        return
    from . import meshedit_ui
    parts = meshedit_ui._parts(window) or []
    if not parts:
        return

    def picked(desc, node=None):
        if getattr(window, "_deform_state", None) is not st:
            return
        if desc is not None and desc.get("pos") is not None:
            if st["active"] == "axis" and desc.get("kind") == "face":
                st["axis"], st["axis_vec"] = "picked", tuple(desc["dir"])
                st["axis_text"] = "face normal"
                _panel(window).set_value("axis", "picked")
                _panel(window).boxes["axis"].setVisible(True)
            else:
                st["point"] = tuple(float(c) for c in desc["pos"])
                st["point_text"] = "(%.1f, %.1f, %.1f)" % st["point"]
            refresh(window)
            if st["point"] is not None and not st["bodies"]:
                activate(window, "bodies")
        from PyQt5.QtCore import QTimer
        if getattr(window, "_deform_state", None) is st:
            QTimer.singleShot(0, lambda: _arm_pick(window))

    view.start_pick(picked, groups=parts, done=False,
                    banner=language.tr(
                        "Deform: click a face for the point (or its "
                        "direction) · OK in the window deforms"))


def activate(window, key):
    st = getattr(window, "_deform_state", None)
    panel = _panel(window)
    if not st or panel is None:
        return
    st["active"] = key
    panel.set_active(key)


def _names(nodes):
    return ", ".join(n.name or n.type for n in nodes)


def refresh(window):
    st = getattr(window, "_deform_state", None)
    panel = _panel(window)
    if not st or panel is None:
        return
    empty = language.tr("Click it in the tree")
    for key in BOXES:
        panel.boxes[key].set_text(_names(st[key]) or empty)
    panel.boxes["point"].set_text(st["point_text"] or language.tr(
        "Click Origin in the tree, a point, or a face in 3D"))
    panel.boxes["axis"].set_text(st["axis_text"] or language.tr(
        "Click an axis or line in the tree, or a face in 3D"))
    if st["type"] == "point":
        panel.set_ok_enabled(bool(st["point"] is not None and st["bodies"]
                                  and (st["axis"] != "picked"
                                       or st["axis_vec"] is not None)))
    else:
        panel.set_ok_enabled(bool(st["initial"] and st["target"]
                                  and st["bodies"]))


def tree_selected(window, nodes):
    """The tree's selection fills the active box and goes on to the
    next."""
    st = getattr(window, "_deform_state", None)
    if not st or st["quiet"] or not nodes:
        return
    nodes = [n for n in nodes if n is not window.model.root]
    if not nodes:
        return
    key = st["active"]
    if st["type"] == "point":
        return _point_selected(window, st, nodes, key)
    if key in ("point", "axis"):
        return
    if key == "bodies":
        nodes = [n for n in nodes if n.type != "line"]
    st[key] = list(nodes)
    refresh(window)
    nxt = {"initial": "target", "target": "bodies"}.get(key)
    if nxt is not None and not st[nxt]:
        activate(window, nxt)


def _point_selected(window, st, nodes, key):
    """Point type: the tree's selection fills the active box — a
    reference point, a reference axis / sketch line, or the bodies."""
    if key == "point":
        pts = [n for n in nodes if n.type == "ref_point"]
        if not pts:
            return
        p = pts[-1].params
        st["point"] = (float(p.get("x", 0)), float(p.get("y", 0)),
                       float(p.get("z", 0)))
        st["point_text"] = pts[-1].name
        refresh(window)
        activate(window, "axis" if st["axis"] == "picked" else "bodies")
    elif key == "axis":
        vec = None
        for n in nodes:
            if n.type == "ref_axis":
                p = n.params
                vec = (float(p.get("dx", 0)), float(p.get("dy", 0)),
                       float(p.get("dz", 1)))
            elif n.type == "line":
                from . import mesh
                m = mesh.ancestor_matrix(n)
                a = mesh.mat_apply(m, (float(n.params.get("x1", 0)),
                                       float(n.params.get("y1", 0)), 0.0))
                b = mesh.mat_apply(m, (float(n.params.get("x2", 0)),
                                       float(n.params.get("y2", 0)), 0.0))
                vec = tuple(b[i] - a[i] for i in range(3))
            if vec is not None:
                st["axis"], st["axis_vec"] = "picked", vec
                st["axis_text"] = n.name
                _panel(window).set_value("axis", "picked")
                break
        if vec is None:
            return
        refresh(window)
        activate(window, "bodies")
    else:
        bodies = [n for n in nodes if n.type not in ("line", "ref_point",
                                                      "ref_axis")]
        if bodies:
            st["bodies"] = bodies
            refresh(window)


def ok(window):
    """Make the Deform; the node, or None (a curve that does not chain
    says so and the window stays)."""
    from . import curve_deform, point_deform
    st = getattr(window, "_deform_state", None)
    if st and st["type"] == "point":
        if st["point"] is None or not st["bodies"]:
            return None
        vec = AXES[st["axis"]] if st["axis"] != "picked" else st["axis_vec"]
        bodies = list(st["bodies"])
        parent = bodies[0].parent
        bodies = [b for b in bodies if b.parent is parent]
        args = (st["point"], vec, st["distance"], st["radius"],
                st["shape"], st["reverse"])
        close(window)
        node = point_deform.make(window.model, bodies, *args)
        if node is not None:
            window.builder.active_tree().select_nodes([node])
            window.statusBar().showMessage(language.tr(
                "Deformed about the point — distance, radius and shape "
                "are in Properties."), 7000)
        return node
    if not st or not (st["initial"] and st["target"] and st["bodies"]):
        return None
    init, targ = curve_of(st["initial"]), curve_of(st["target"])
    if init is None or targ is None:
        window.view3d.flash(language.tr(
            "Deform: a curve must be ONE chain of lines and arcs joined "
            "end to end."), 6000)
        return None
    bodies = list(st["bodies"])
    parent = bodies[0].parent
    bodies = [b for b in bodies if b.parent is parent]
    close(window)
    node = curve_deform.make(window.model, bodies, init, targ)
    if node is not None:
        window.builder.active_tree().select_nodes([node])
        window.statusBar().showMessage(language.tr(
            "Deformed from the initial curve onto the target curve — "
            "the curves are in Properties."), 7000)
    return node


def close(window):
    panel = _panel(window)
    if getattr(window, "_deform_state", None) is None and panel is None:
        return
    window._deform_state = None
    window._deform_panel = None
    _hook(window, False)
    view = window.view3d
    if getattr(view, "_pick_cb", None) is not None:
        view._pick_cb = None
        view._end_pick_mode()
    if panel is not None:
        panel.hide()
        panel.deleteLater()
