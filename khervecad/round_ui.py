"""Rounding an edge or pushing a face straight from the 3D view
(2026-10-21, the user: "I cannot find where we can round an edge or a
face from 3D or 2D view, which will then create an item in the tree").

The fillet / chamfer / push-pull nodes already existed, but they wrapped
the SELECTION and then asked for clicks — with nothing selected they
only said "select something", so they were never found. Here:

- `start(window, op, kind)`: with a selection, the old path (wrap, then
  pick); with none, the 3D view asks for a click ON AN EDGE (or face) of
  any part — that part is wrapped in a Fillet / Push-pull item in the
  tree, the clicked edge is already its first, and the pick stays armed
  for more (Esc finishes).
- `context_menu(window, pos)`: right-click in the 3D view ▸ Round edges
  (fillet) / Chamfer edges / Push or pull a face — the part under the
  cursor is selected and the same flow starts.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import language

#: (op, fillet kind, label, mdi glyph)
ACTIONS = [("fillet", "round", "Round edges (fillet)…", "mdi.rounded-corner"),
           ("fillet", "chamfer", "Chamfer edges…", "mdi.vector-polyline"),
           ("push_pull", None, "Push / pull a face…",
            "mdi.arrow-expand-vertical")]


def _wrap(window, node, op, kind):
    model = window.model
    wrapper = model.wrap_nodes([node], op)
    if wrapper is None:
        return None
    if op == "fillet" and kind:
        model.set_param(wrapper, "kind", kind)
    window.builder.active_tree().select_nodes([wrapper])
    return wrapper


def _first_edge(window, wrapper, desc):
    """Give a new fillet the edge that was clicked to make it."""
    from . import fillet_pick
    try:
        world, local = fillet_pick.meshes(window, wrapper)
        face = fillet_pick.face_from_pick(desc, world, local) \
            if world else None
        seeds = [] if face is not None or not world else \
            fillet_pick.seeds_from_pick(desc, world, local)
    except Exception:                       # a pick the mesh cannot map
        face, seeds = None, []
    if face is not None:
        window.model.set_param(wrapper, "faces", [face])
    elif seeds:
        window.model.set_param(wrapper, "edges", [list(s) for s in seeds])


def solid_of(window, node):
    """The part a selection belongs to, for rounding: a 2D shape has no
    edges (the user had Polygon 2 selected, so Fillet wrapped a flat
    polygon and nothing happened) — climb to the scope's top-level part
    holding it (the Difference / extrude that makes the solid)."""
    from .model import SHAPE_2D
    scope = window._render_scope()[0]
    probe = node
    while probe.parent is not None and probe.parent is not scope and \
            probe.parent is not window.model.root:
        probe = probe.parent
    if node.category == SHAPE_2D or probe is not node:
        return probe
    return node


def start(window, op="fillet", kind="round"):
    tree = window.builder.active_tree()
    if tree.selected_nodes():
        picked = []
        for n in tree.selected_nodes():
            s = solid_of(window, n)
            if s not in picked:
                picked.append(s)
        tree.select_nodes(picked)
        window._apply_operation(op)
        wrapper = (tree.selected_nodes() or [None])[0]
        if op == "fillet" and kind and wrapper is not None and \
                wrapper.type == "fillet":
            window.model.set_param(wrapper, "kind", kind)
        return
    from . import meshedit_ui
    parts = meshedit_ui._parts(window)
    if not parts:
        window.statusBar().showMessage(language.tr(
            "There is no solid in view to round — add a part first."), 6000)
        return
    word = {"round": language.tr("round"),
            "chamfer": language.tr("chamfer")}.get(kind, "")

    def picked(desc, node):
        if desc is None or node is None:
            window.statusBar().showMessage(language.tr("Cancelled."), 3000)
            return
        wrapper = _wrap(window, node, op, kind)
        if wrapper is None:
            return
        if op == "fillet":
            if desc.get("kind") == "edge" or desc.get("kind") == "face":
                _first_edge(window, wrapper, desc)
            window.start_fillet_pick(wrapper)
        else:
            from . import faceedit_ui
            faceedit_ui.start(window, wrapper)

    if op == "fillet":
        banner = language.tr(
            "Click the edge to {word} (a face: all its edges) · Esc "
            "cancels").format(word=word)
    else:
        banner = language.tr("Click the part whose face to push or pull "
                             "· Esc cancels")
    window.view3d.start_pick(
        picked, groups=parts, banner=banner,
        labeler=lambda desc, node: "%s · %s" % (
            getattr(node, "name", ""),
            language.tr("Edge") if desc.get("kind") == "edge"
            else language.tr("Face")))


def context_menu(window, pos):
    """Right-click in the 3D view."""
    from PyQt5.QtWidgets import QMenu
    from . import icons
    view = window.view3d
    if getattr(view, "edit_tool", None) is not None:
        return
    if getattr(view, "_pick_cb", None) is not None:
        view.cancel_pick()
    menu = QMenu(view)
    for op, kind, label, glyph in ACTIONS:
        menu.addAction(icons.icon(glyph), language.tr(label),
                       lambda o=op, k=kind: start(window, o, k))
    menu.addSeparator()
    menu.addAction(icons.icon("mdi.vector-polyline-edit"),
                   language.tr("Edit vertices (Edit Mode)"),
                   lambda: window.set_edit_mode(True))
    menu.exec_(view.mapToGlobal(pos))
