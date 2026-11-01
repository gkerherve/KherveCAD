"""The 3D view's right-click menu (2026-11-01, the user: "the middle
button is for dragging the model around ... the right click will be
some of the properties, like deleting the smart dimension").

SolidWorks' context menu, as far as KherveCAD has the commands: what is
under the cursor comes first — a Smart Dimension (Edit value, Delete) or
the part (it is selected, as SolidWorks selects what you right-click:
Edit Sketch, Sketch on a face, fillet / chamfer / push-pull, Edit
vertices, Measure, Hide, Delete) — then the view (Zoom to Fit, Zoom to
Selection, the standard orientations). A right DRAG still pans; the
middle drag pans too.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import language

#: the standard orientations offered, in SolidWorks' order
ORIENTATIONS = ["Front", "Back", "Left", "Right", "Top", "Bottom",
                "Isometric"]


def dimension_at(window, pos):
    """``(chip rect, sketch, row index)`` of the Smart Dimension value
    under *pos*, else None."""
    for hit in getattr(window, "_dims3d_hits", []):
        rect = hit[0]
        if rect.adjusted(-3, -3, 3, 3).contains(pos.x(), pos.y()):
            return hit[:3]
    return None


def relation_at(window, pos):
    """``(mark rect, sketch, row index)`` of the relation mark under
    *pos*, else None."""
    for hit in getattr(window, "_relation_hits", []):
        if hit[0].adjusted(-2, -2, 2, 2).contains(pos.x(), pos.y()):
            return hit
    return None


def part_at(window, pos):
    """The part (a child of the scope) drawn under *pos*, else None."""
    from . import anchors, meshedit_ui
    view = window.view3d
    eye, right, up, forward = view._camera()

    def projector(v):
        return view._project(eye, right, up, forward, v)
    best, best_depth = None, None
    try:
        parts = meshedit_ui._parts(window)
    except Exception:                    # never break the menu
        return None
    for node, tris in parts:
        index, point = anchors.pick(tris, projector, pos.x(), pos.y())
        if index is None:
            continue
        depth = projector(point)[2]
        if best_depth is None or depth < best_depth:
            best, best_depth = node, depth
    return best


def delete_dimension(window, cont, index):
    from . import sketch_constraints as sc
    sc.remove(window.model, cont, index)
    window.view3d.update()


def context_menu(window, pos):
    """Right-click (a click, not a drag) in the 3D view."""
    from PyQt5.QtWidgets import QMenu
    from . import icons, round_ui, sketch_dims3d
    view = window.view3d
    if getattr(view, "edit_tool", None) is not None:
        return None
    if getattr(view, "_pick_cb", None) is not None:
        view.cancel_pick()
    tr = language.tr
    menu = QMenu(view)
    dim = dimension_at(window, pos)
    if dim is not None:
        rect, cont, index = dim
        menu.addSection(tr("Smart Dimension"))
        menu.addAction(icons.icon("mdi.pencil"), tr("Edit value…"),
                       lambda: sketch_dims3d.edit(window, rect, cont, index))
        menu.addAction(icons.icon("mdi.delete"), tr("Delete dimension"),
                       lambda: delete_dimension(window, cont, index))
    elif relation_at(window, pos) is not None:
        _rect, cont, index = relation_at(window, pos)
        menu.addSection(tr("Relation"))
        menu.addAction(icons.icon("mdi.delete"), tr("Delete constraint"),
                       lambda: delete_dimension(window, cont, index))
    else:
        node = part_at(window, pos)
        tree = window.builder.active_tree()
        if node is not None:
            tree.select_nodes([node])
            menu.addSection(node.name or tr("Part"))
            from . import normal_to
            menu.addAction(normal_to.action(window))
            menu.addAction(icons.icon("mdi.draw"), tr("Sketch on a face"),
                           lambda: _sketch_on_face(window))
            menu.addSeparator()
        for op, kind, label, glyph in round_ui.ACTIONS:
            menu.addAction(icons.icon(glyph), tr(label),
                           lambda o=op, k=kind: round_ui.start(window, o, k))
        menu.addAction(icons.icon("mdi.vector-polyline-edit"),
                       tr("Edit vertices (Edit Mode)"),
                       lambda: window.set_edit_mode(True))
        menu.addAction(icons.icon("mdi.ruler"), tr("Measure"),
                       lambda: _measure(window))
        if node is not None:
            menu.addSeparator()
            menu.addAction(icons.icon("mdi.eye-off"), tr("Hide"),
                           lambda: window.model.set_visible(node, False))
            menu.addAction(icons.icon("mdi.delete"), tr("Delete"),
                           lambda: _delete(window, node))
    menu.addSeparator()
    from . import viewnav
    menu.addAction(icons.icon("mdi.fit-to-page-outline"), tr("Zoom to Fit"),
                   lambda: _fit(view))
    menu.addAction(icons.icon("mdi.magnify-scan"), tr("Zoom to Selection"),
                   lambda: viewnav.focus_3d(view))
    views = menu.addMenu(icons.icon("mdi.cube-scan"),
                         tr("View Orientation"))
    for name in ORIENTATIONS:
        views.addAction(tr(name), lambda n=name: view.set_view(n))
    menu.exec_(view.mapToGlobal(pos))
    return menu


def _fit(view):
    view.fit()
    view.user_moved = True
    view.update()


def _sketch_on_face(window):
    from . import face_sketch
    face_sketch.start(window)


def _measure(window):
    from . import measure3d
    measure3d.start(window)


def _delete(window, node):
    from . import delete_ui
    delete_ui.delete_nodes(window, window.model, [node])
