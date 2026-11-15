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
    st = window._deform_state = dict(initial=[], target=[], bodies=pre,
                                     active="initial", quiet=False)
    panel = ToolPanel(window.view3d, tr("Deform"),
                      on_ok=lambda: ok(window),
                      on_cancel=lambda: close(window))
    panel.hint(tr("Curve to curve: click the INITIAL curve (a sketch or "
                  "its construction line) in the tree, then the TARGET "
                  "curve, then the bodies to bend. The initial curve's "
                  "ends land on the target's ends."))
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
    activate(window, "initial")
    return panel


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
    if key == "bodies":
        nodes = [n for n in nodes if n.type != "line"]
    st[key] = list(nodes)
    refresh(window)
    nxt = {"initial": "target", "target": "bodies"}.get(key)
    if nxt is not None and not st[nxt]:
        activate(window, nxt)


def ok(window):
    """Make the Deform; the node, or None (a curve that does not chain
    says so and the window stays)."""
    from . import curve_deform
    st = getattr(window, "_deform_state", None)
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
    if panel is not None:
        panel.hide()
        panel.deleteLater()
