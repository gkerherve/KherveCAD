# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""**Set Origin Here** in the sketch (2026-11-12, the user: "define the
real 0 0 0, redefine it"): a click in the 2D sketch — snapped to a corner,
a centre, the middle of a side, the origin or the grid — becomes the
Object's origin 0, 0, 0. Everything inside shifts so nothing moves on
screen or in the assembly (`anchors.set_origin`: the contents under an
"Origin shift" move, the placement the other way); the axes, planes,
relations and dimensions then read from the new point.

Only inside an Object (the Object tab): the Main assembly's origin is the
document's own.
"""

TOOL = "sk_origin"
PROMPT = ("Set Origin Here: click the point that becomes 0, 0, 0 — a "
          "corner, centre or middle snaps.")


def object_of(scene):
    """The Object being edited, or None."""
    node = scene.isolation_resolver() if scene.isolation_resolver else None
    while node is not None and node.type != "component":
        node = node.parent
    return node


def local_point(scene, comp, x, y):
    """The sketch point (x, y) of the scene in *comp*'s own frame."""
    from . import mesh
    from .view2d import PLANES
    iso = scene.isolation_resolver() if scene.isolation_resolver else None
    if iso is not None and iso is not comp:
        # a face / plane sketch: its own frame inside the Object
        m = mesh.mat_mul(mesh.ancestor_matrix(iso, {}, stop=comp),
                         mesh.node_matrix(iso, {}))
        return mesh.mat_apply(m, (x, y, 0.0))
    (i, j), _names = PLANES.get(scene.plane, PLANES["Top (XY)"])
    p = [0.0, 0.0, 0.0]
    p[i], p[j] = x, y
    return p


def press(scene, event):
    from PyQt5.QtCore import Qt
    event.accept()
    if event.button() != Qt.LeftButton:
        return
    comp = object_of(scene)
    if comp is None:
        scene.status.emit("Set Origin Here works inside an Object: open "
                          "it in the Object tab first.")
        return
    pt, _on = scene.snap_feature(event.scenePos())
    pos = local_point(scene, comp, pt.x(), pt.y())
    set_origin(scene.model, comp, pos)
    scene.status.emit("Origin moved: that point is now 0, 0, 0 of %s."
                      % comp.name)


def set_origin(model, comp, pos):
    """*comp* re-based on its local *pos*, its sketch relations carried
    into the Origin shift with its children."""
    from . import anchors, sketch_constraints as sc
    rows = [dict(r) for r in sc.rows(comp)]
    had_shift = len(comp.children) == 1 and \
        comp.children[0].type == "translate" and \
        comp.children[0].name == "Origin shift"
    anchors.set_origin(model, comp, pos)
    if rows and not had_shift and comp.children and \
            comp.children[0].name == "Origin shift":
        # the children moved one level down, in order: their rows too
        comp.children[0].params[sc.KEY] = rows
        comp.params.pop(sc.KEY, None)
    model.structure_changed.emit()
