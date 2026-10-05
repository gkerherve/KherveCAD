"""Exact parts in the window: right-click ▸ Make Exact, and Fillet /
Chamfer Edges by clicking them on the part (Qt side of brep.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from . import brep, icons, language


def add_menu(menu, window, nodes):
    """The tree's right-click entries for exact parts."""
    if len(nodes) != 1:
        return
    node = nodes[0]
    exact = next((n for n in node.walk() if n.type == "brep"), None)
    if exact is not None:
        menu.addSeparator()
        menu.addAction(icons.icon("mdi.rounded-corner"),
                       language.tr("Fillet Edges (exact)..."),
                       lambda: start(window, exact, "fillets"))
        menu.addAction(icons.icon("mdi.vector-square"),
                       language.tr("Chamfer Edges (exact)..."),
                       lambda: start(window, exact, "chamfers"))
    elif brep.convertible(node) is not None:
        menu.addSeparator()
        menu.addAction(icons.icon("mdi.cube-scan"),
                       language.tr("Make Exact (edit as B-rep)"),
                       lambda: make_exact(window, node))


def make_exact(window, node):
    try:
        exact = brep.make_exact(window.model, node)
    except ValueError as exc:
        window.statusBar().showMessage(language.tr(str(exc)), 8000)
        return None
    window.builder.active_tree().select_nodes([exact])
    window.statusBar().showMessage(language.tr(
        "Now an exact part: right-click it ▸ Fillet Edges or Chamfer "
        "Edges and click the edges on the part."), 10000)
    return exact


def start(window, node, key="fillets", size=None):
    """Ask the radius (or size), then pick edges until Esc."""
    from PyQt5.QtWidgets import QInputDialog
    from PyQt5.QtCore import QSettings
    from . import mesh
    word = "radius" if key == "fillets" else "size"
    settings = QSettings("Kherve", "KherveCAD")
    if size is None:
        last = float(settings.value(f"brep/{key}", 2.0))
        size, ok = QInputDialog.getDouble(
            window, language.tr("Fillet edges" if key == "fillets"
                                else "Chamfer edges"),
            language.tr("Fillet radius (mm):" if key == "fillets"
                        else "Chamfer size (mm):"), last, 0.01, 1e4, 2)
        if not ok:
            return False
        settings.setValue(f"brep/{key}", size)
    view = window.view3d
    model = window.model
    world = [tuple(tuple(mesh.mat_apply(mesh.ancestor_matrix(node), v))
                   for v in t) for t in mesh.tessellate(node)]
    if not world:
        window.statusBar().showMessage(language.tr(
            "This exact part has nothing to pick yet."), 6000)
        return False
    added = []

    def on_pick(desc, _key):
        if desc is None:
            window.builder.active_tree().select_nodes([node])
            window.statusBar().showMessage(language.tr(
                "{n} edge(s) {done}. They are listed in Properties, where "
                "a row can be changed or removed.").format(
                n=len(added), done=language.tr(
                    "filleted" if key == "fillets" else "chamfered")),
                8000)
            return
        if desc.get("kind") != "edge":
            window.statusBar().showMessage(language.tr(
                "Click ON an edge — the line where two faces meet."), 4000)
            arm()
            return
        a, b = desc["seg"]
        mid = [(a[k] + b[k]) / 2 for k in range(3)]
        local = brep.to_local(node, mid)
        rows = [list(r) for r in node.params.get(key) or []]
        rows.append(local + [round(float(size), 4)])
        model.set_param(node, key, rows)
        from .model import validate
        problem = validate(model.root).get(node.id)
        if problem:
            rows.pop()
            model.set_param(node, key, rows)
            window.statusBar().showMessage(language.tr(problem), 8000)
        else:
            added.append(local)
        arm()

    def arm():
        view.start_pick(
            on_pick, groups=[(node, world)],
            banner=language.tr(
                "{what}: click edges · {n} so far · Esc or right-click "
                "when done").format(
                what=language.tr("Fillet" if key == "fillets"
                                 else "Chamfer"), n=len(added)),
            labeler=lambda d, _k: language.tr(
                "Edge — click to {verb}").format(verb=language.tr(
                    "round it" if key == "fillets" else "chamfer it"))
            if d.get("kind") == "edge" else language.tr(
                "Face — aim at an edge"))

    arm()
    return True
