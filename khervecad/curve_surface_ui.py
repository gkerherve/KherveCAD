"""Surfaces from curves in the window: the tree's right-click menu, the
Tools menu and the status line that says what to select (Qt side of
curve_surface.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from . import curve_surface, icons, language


def add_menu(menu, window, nodes):
    """A "Make Surface from Curves" submenu when *nodes* hold curves."""
    if not curve_surface.gather_curves(nodes):
        return None
    sub = menu.addMenu(icons.icon("mdi.vector-curve"),
                       language.tr("Make Surface from Curves"))
    sub.setToolTipsVisible(True)
    for kind, label in curve_surface.KIND_LABELS:
        act = sub.addAction(language.tr(label))
        act.triggered.connect(
            lambda _=False, k=kind: make(window, nodes, k))
    return sub


def from_selection(window, kind):
    """Tools ▸ Surface from Curves: the curves selected in the tree."""
    tree = window.builder.active_tree()
    make(window, tree.selected_nodes() if hasattr(tree, "selected_nodes")
         else [], kind)


def make(window, nodes, kind):
    model = window.model
    try:
        surf = curve_surface.make_surface(model, nodes, kind)
    except ValueError as exc:
        window.statusBar().showMessage(language.tr(
            "Surface from curves: {why}. Select the curves in the tree "
            "first (Ctrl+click for several, in order).").format(
            why=language.tr(str(exc))), 8000)
        return None
    try:
        window.builder.active_tree().select_nodes([surf])
    except Exception:                               # pragma: no cover
        pass
    from .model import validate
    problem = validate(model.root).get(surf.id)
    window.statusBar().showMessage(
        language.tr("Surface made. {problem}").format(
            problem=language.tr(problem)) if problem else language.tr(
            "Surface made — change Make, Wall thickness and the rest in "
            "Properties; the curves are inside it, so editing a curve "
            "reshapes the surface."), 12000)
    return surf
