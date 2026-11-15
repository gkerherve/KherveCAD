"""The Fill Pattern window (2026-11-15): SolidWorks' PropertyManager for
`fill_pattern` — click the face, choose the layout, spacing, margin,
direction (a sketch line of the tree, or an angle) and the seed cut; the
fill is made at once and follows every change; OK keeps it, Cancel (or
Esc) takes it away.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import fill_pattern as fp
from . import language

TIP = ("Fill Pattern",
       "SolidWorks' Fill Pattern: click a flat face and it is filled with "
       "copies of a seed cut — a square, circle, diamond or polygon — in "
       "loops (Circular), a grid (Square) or staggered rows "
       "(Perforation), held in by a margin and turned to a direction.",
       ["Click Fill Pattern (Features tab, beside Linear Pattern).",
        "Click the face to fill: it lights and the fill appears.",
        "Choose Layout, Loop spacing, Instance spacing, Margin.",
        "Direction: click a sketch line in the tree, or type an angle; "
        "Reverse direction turns it round.",
        "Seed cut: shape and size. OK keeps the fill, Cancel / Esc "
        "removes it."],
       "The count is shown as it fills; Properties of the Fill Pattern "
       "feature reopen it with the button.")

NUMBERS = (("loop_spacing", "Loop spacing", " mm", 0.1),
           ("spacing", "Instance spacing", " mm", 0.1),
           ("margin", "Margin", " mm", 0.0),
           ("angle", "Direction angle", " °", None),
           ("size", "Size", " mm", 0.1),
           ("rotation", "Rotation", " °", None),
           ("depth", "Depth", " mm", 0.1))


def action(window):
    act = getattr(window, "_fill_pattern_act", None)
    if act is not None:
        return act
    from PyQt5.QtWidgets import QAction
    from . import icons, toolbars, tooltips
    tooltips.TIPS.setdefault("fill_pattern", TIP)
    act = QAction(icons.icon("mdi.dots-grid",
                             icons.family_color("transform")),
                  language.tr("Fill Pattern"), window)
    act.setData("fill_pattern")
    toolbars.remember_glyph(act, "mdi.dots-grid", "transform")
    tooltips.apply(act, "fill_pattern")
    act.triggered.connect(lambda _=False: start(window))
    window._fill_pattern_act = act
    return act


def _state(window):
    return getattr(window, "_fill_state", None)


def _panel(window):
    return getattr(window, "_fill_panel", None)


def start(window, feature=None):
    """Open the window (a Fill Pattern feature selected: change that
    one). Armed for the face click."""
    from . import meshedit_ui
    close(window, keep=True)
    if feature is None:
        for n in window.builder.active_tree().selected_nodes():
            probe = n
            while probe is not None and fp.KEY not in probe.params:
                probe = probe.parent
            if probe is not None:
                feature = probe
                break
    if feature is None and not meshedit_ui._parts(window):
        window.statusBar().showMessage(language.tr(
            "Nothing to fill — add a part first."), 5000)
        return None
    st = window._fill_state = dict(
        spec=fp.spec_of(None), feature=None, part=None, made=False,
        dir_node=None, active="face", edit=False, quiet=False)
    if feature is not None:
        st["spec"] = fp.spec_of(feature.params[fp.KEY])
        st["feature"], st["edit"] = feature, True
        st["part"] = feature.parent.children[0]
    panel = window._fill_panel = _make_panel(window)
    _hooks(window, True)
    panel.open()
    _refresh(window)
    _activate(window, "direction" if feature is not None else "face")
    if feature is None:
        _arm(window)
    return panel


def _make_panel(window):
    from .tool_panel import ToolPanel
    panel = ToolPanel(window.view3d, language.tr("Fill Pattern"),
                      on_ok=lambda: ok(window),
                      on_cancel=lambda: cancel(window))
    panel.hint(language.tr(
        "Click the flat face to fill; then choose the layout, the "
        "spacing and margin, the direction and the seed cut."))
    panel.selection("face", language.tr("Fill boundary (face)"),
                    on_activate=lambda k: _activate(window, k))
    panel.selection("direction", language.tr("Pattern direction"),
                    on_activate=lambda k: _activate(window, k))
    spec = _state(window)["spec"]
    panel.section(language.tr("Pattern layout"))
    panel.choice("layout", language.tr("Layout"),
                 [(k, language.tr(t)) for k, t in fp.LAYOUTS],
                 spec["layout"], lambda v: _set(window, "layout", v))
    for key, cap, suffix, lo in NUMBERS[:3]:
        panel.number(key, language.tr(cap), spec[key],
                     lambda v, k=key: _set(window, k, float(v)),
                     suffix=suffix, minimum=lo, maximum=10000.0,
                     step=0.5)
    panel.number("angle", language.tr("Direction angle"), spec["angle"],
                 lambda v: _set(window, "angle", float(v)), suffix=" °",
                 minimum=-360.0, maximum=360.0, step=5.0)
    panel.check("reverse", language.tr("Reverse direction"),
                spec["reverse"], lambda v: _set(window, "reverse", bool(v)))
    panel.section(language.tr("Seed cut"))
    panel.choice("shape", language.tr("Shape"),
                 [(k, language.tr(t)) for k, t in fp.SHAPES],
                 spec["shape"], lambda v: _set(window, "shape", v))
    panel.number("size", language.tr("Size"), spec["size"],
                 lambda v: _set(window, "size", float(v)), minimum=0.05,
                 maximum=10000.0, step=0.5)
    panel.number("rotation", language.tr("Rotation"), spec["rotation"],
                 lambda v: _set(window, "rotation", float(v)),
                 suffix=" °", minimum=-360.0, maximum=360.0, step=5.0)
    panel.number("sides", language.tr("Sides"), spec["sides"],
                 lambda v: _set(window, "sides", int(v)), suffix="",
                 minimum=3, maximum=64, step=1, decimals=0)
    panel.choice("end", language.tr("End condition"),
                 [("Through all", language.tr("Through all")),
                  ("Blind", language.tr("Blind"))], spec["end"],
                 lambda v: _set(window, "end", v))
    panel.number("depth", language.tr("Depth"), spec["depth"],
                 lambda v: _set(window, "depth", float(v)),
                 minimum=0.1, maximum=10000.0, step=0.5)
    panel.count = panel.hint("")
    panel.finish()
    return panel


def _set(window, key, value):
    st = _state(window)
    if st is None or st["quiet"]:
        return
    st["spec"][key] = value
    _rebuild(window)
    _refresh(window)


def _refresh(window):
    st, panel = _state(window), _panel(window)
    if st is None or panel is None:
        return
    spec = st["spec"]
    panel.boxes["face"].set_text(
        (st["part"].name if st["part"] is not None else "") + " · face"
        if st["feature"] is not None else
        language.tr("Click a flat face of a part"))
    if st["dir_node"] is not None:
        text = st["dir_node"].name
    elif spec.get("direction"):
        text = language.tr("a picked sketch line")
    else:
        text = language.tr("Click a sketch line in the tree, or type an "
                           "angle below")
    panel.boxes["direction"].set_text(text)
    panel.show_row("sides", spec["shape"] == "polygon")
    panel.show_row("depth", spec["end"] == "Blind")
    n = st.get("count")
    panel.count.setText(
        language.tr("{n} instances").format(n=n) if n is not None else "")
    panel.set_ok_enabled(st["feature"] is not None)
    window.view3d.update()


def _scope_frame(window):
    return window._render_scope()[0]


def _rebuild(window):
    """Fill again with the settings of the moment (creating the feature
    on the first face click)."""
    st = _state(window)
    if st is None or st["feature"] is None:
        return
    model = window.model
    feature = st["feature"]
    spec = st["spec"]
    if st["dir_node"] is not None:
        spec["direction"] = fp.line_vector(model, st["dir_node"], feature,
                                           _scope_frame(window))
    st["quiet"] = True          # the tree rebuilding is not the user
    try:
        st["count"] = fp.update_feature(model, feature, spec)
        window.builder.active_tree().select_nodes([feature])
    finally:
        st["quiet"] = False


def _arm(window):
    st = _state(window)
    if st is None:
        return
    from . import meshedit_ui
    view = window.view3d
    parts = meshedit_ui._parts(window) or []
    if getattr(view, "_pick_cb", None) is not None:
        view._pick_cb = None
        view._end_pick_mode()

    def picked(desc, node=None):
        if _state(window) is not st:
            return
        pos = st.pop("pos", None)
        if desc is None and pos is None:           # Esc
            cancel(window)
            return
        if desc is not None and desc.get("kind") == "face" and \
                node is not None:
            _face(window, desc, node)
        elif desc is not None:
            window.statusBar().showMessage(language.tr(
                "Fill Pattern: click a flat FACE, not an edge."), 5000)
        from PyQt5.QtCore import QTimer
        if st["feature"] is None:
            QTimer.singleShot(0, lambda: _arm(window))

    view.start_pick(picked, groups=parts, done=False,
                    banner=language.tr(
                        "Fill Pattern: click the face to fill · OK in "
                        "the window keeps it · Esc cancels"),
                    labeler=lambda desc, n: getattr(n, "name", ""))


def _face(window, desc, node):
    """The face clicked: make the feature and fill it."""
    from . import round_ui
    st = _state(window)
    model = window.model
    part = round_ui.solid_of(window, node)
    scope = _scope_frame(window)
    if st["feature"] is not None:
        _discard(window)
    spec = st["spec"]
    if st["dir_node"] is not None:
        spec["direction"] = None
    feature, n, made = fp.add_fill(model, part, desc["pos"], desc["dir"],
                                   spec, scope=scope)
    st.update(feature=feature, part=feature.parent.children[0], made=made,
              count=n, spec=fp.spec_of(feature.params[fp.KEY]))
    if st["dir_node"] is not None:
        _rebuild(window)
    window.view3d.set_pick_pinned(None)
    window.builder.active_tree().select_nodes([feature])
    window.statusBar().showMessage(language.tr(
        "Fill Pattern: {n} instances — OK keeps it").format(n=n), 6000)
    _refresh(window)
    _activate(window, "direction")


def _discard(window):
    """Take the feature just made away again."""
    st = _state(window)
    feature = st["feature"] if st else None
    if feature is None or feature.parent is None:
        return
    model = window.model
    diff = feature.parent
    model.remove_node(feature)
    if st["made"] and diff.parent is not None and \
            len(diff.children) == 1:
        model.ungroup(diff)
    st["feature"], st["made"] = None, False


def _activate(window, key):
    st, panel = _state(window), _panel(window)
    if not st or panel is None:
        return
    st["active"] = key
    panel.set_active(key)
    if key == "face" and st["feature"] is not None:
        _discard(window)
        st["count"] = None
        _refresh(window)
        _arm(window)


# ------------------------------------------------- the tree feeds it
def _trees(window):
    from .mirror_feature import _trees
    return _trees(window)


def _hooks(window, on):
    if not hasattr(window, "_fill_tree_slot"):
        window._fill_tree_slot = lambda nodes: tree_selected(window, nodes)

        def note(pos):
            st = _state(window)
            if st is not None:
                st["pos"] = pos
            return False
        view = window.view3d
        view.release_hooks = list(getattr(view, "release_hooks", ())) + \
            [note]
    for tree in _trees(window):
        try:
            if on:
                tree.selection_changed.connect(window._fill_tree_slot)
            else:
                tree.selection_changed.disconnect(window._fill_tree_slot)
        except (TypeError, RuntimeError, AttributeError):
            pass


def tree_selected(window, nodes):
    """A sketch line picked in the tree is the pattern direction."""
    st = _state(window)
    if not st or st["quiet"] or st["feature"] is None:
        return
    lines = [n for n in nodes if n.type == "line"]
    if not lines:
        return
    st["dir_node"] = lines[-1]
    _rebuild(window)
    _refresh(window)


# ------------------------------------------------------------ finish
def ok(window):
    st = _state(window)
    if not st or st["feature"] is None:
        return None
    feature = st["feature"]
    close(window, keep=True)
    window.builder.active_tree().select_nodes([feature])
    return feature


def cancel(window):
    st = _state(window)
    if st is None:
        return
    if not st["edit"]:
        _discard(window)
    close(window, keep=True)


def close(window, keep=False):
    st, panel = _state(window), _panel(window)
    if st is None and panel is None:
        return
    window._fill_state = None
    window._fill_panel = None
    _hooks(window, False)
    view = window.view3d
    if getattr(view, "_pick_cb", None) is not None:
        view._pick_cb = None
        view._end_pick_mode()
    view.set_pick_pinned(None)
    if panel is not None:
        panel.hide()
        panel.deleteLater()
    view.update()
