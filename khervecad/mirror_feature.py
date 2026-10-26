"""SolidWorks' **Mirror** (2026-10-25, the user: "select the part to
mirror — from the tree or the 3D — keep the original, choose a plane:
XY, XZ, YZ or any plane of the design").

`start(window)`: the parts selected in the tree, else click them in the
3D view (each click adds one, Done / Esc goes on); then the plane — Top
(XY), Front (XZ), Right (YZ) through the origin, or a flat face picked
in the 3D view. The parts are wrapped in a `symmetry` node (organic.py:
`kcad_symmetry(n, c) { children }` draws them AND their mirror image
about the plane through c square to n), named "Mirror" — the original
stays, the copy follows every edit of it, and the plane is in the
node's Properties.

A picked face is given in the scope's frame; it is carried into the
frame the parts live in (`_to_parent`), so a part inside an Object's
groups mirrors about the face that was clicked.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

#: the standard planes: (name, normal)
PLANES = [("Front Plane (XZ)", (0.0, 1.0, 0.0)),
          ("Top Plane (XY)", (0.0, 0.0, 1.0)),
          ("Right Plane (YZ)", (1.0, 0.0, 0.0))]
FACE = "Pick a face in the 3D view…"


def apply(model, nodes, normal, point=(0.0, 0.0, 0.0)):
    """Wrap *nodes* (one parent) in a Mirror about the plane through
    *point* (their parent's frame) square to *normal*. The node."""
    nodes = [n for n in nodes if n.parent is not None]
    if not nodes:
        return None
    parent = nodes[0].parent
    nodes = [n for n in nodes if n.parent is parent]
    node = model.wrap_nodes(nodes, "symmetry")
    if node is None:
        return None
    node.params.update(x=round(float(normal[0]), 6),
                       y=round(float(normal[1]), 6),
                       z=round(float(normal[2]), 6),
                       cx=round(float(point[0]), 6),
                       cy=round(float(point[1]), 6),
                       cz=round(float(point[2]), 6))
    node.name = "Mirror"
    model.node_changed.emit(node)
    return node


def _to_parent(window, parent, point, normal):
    """A plane given in the scope's frame, in *parent*'s own frame."""
    import numpy as np
    from . import mesh
    scope = window._render_scope()[0]
    stop = None if scope is window.model.root else scope
    m = np.array(mesh.mat_mul(mesh.ancestor_matrix(parent, {}, stop=stop),
                              mesh.node_matrix(parent, {})), dtype=float)
    inv = np.linalg.inv(m)
    p = inv @ np.array([point[0], point[1], point[2], 1.0])
    n = np.linalg.inv(m[:3, :3]).T @ np.array(normal, dtype=float)
    ln = float(np.linalg.norm(n)) or 1.0
    return tuple(float(v) for v in p[:3]), tuple(float(v) / ln for v in n)


# =================================================================== Qt
def ask_plane(window):
    """Which plane: a little menu at the cursor (tests set
    `window.mirror_plane_hook`)."""
    hook = getattr(window, "mirror_plane_hook", None)
    if hook is not None:
        return hook()
    from PyQt5.QtGui import QCursor
    from PyQt5.QtWidgets import QMenu
    from . import language
    menu = QMenu(window)
    menu.addSection(language.tr("Mirror about"))
    acts = {}
    for name, _n in PLANES:
        acts[menu.addAction(language.tr(name))] = name
    menu.addSeparator()
    acts[menu.addAction(language.tr(FACE))] = FACE
    chosen = menu.exec_(QCursor.pos())
    return acts.get(chosen)


def _finish(window, nodes):
    from . import language
    choice = ask_plane(window)
    if choice is None:
        return None
    if choice != FACE:
        normal = dict(PLANES)[choice]
        node = apply(window.model, nodes, normal)
        _done(window, node, choice)
        return node
    from . import meshedit_ui
    parts = meshedit_ui._parts(window)

    def picked(desc, _node):
        if desc is None:
            return
        window.view3d.cancel_pick()
        if desc.get("kind") != "face":
            window.statusBar().showMessage(language.tr(
                "Mirror: click a flat FACE for the plane."), 5000)
            return
        point, normal = _to_parent(window, nodes[0].parent, desc["pos"],
                                   desc["dir"])
        node = apply(window.model, nodes, normal, point)
        _done(window, node, language.tr("the face"))
    window.view3d.start_pick(
        picked, groups=parts,
        banner=language.tr("Mirror: click the face to mirror about · Esc "
                           "cancels"),
        labeler=lambda desc, n: getattr(n, "name", ""))
    return None


def _done(window, node, plane):
    if node is None:
        return
    window.builder.active_tree().select_nodes([node])
    window.statusBar().showMessage(
        "Mirrored about %s — the original is kept; the plane is in "
        "Properties." % plane, 7000)


def start(window):
    """Mirror: the selection, else parts clicked in 3D; then a plane."""
    from . import language, meshedit_ui
    nodes = window.builder.active_tree().selected_nodes()
    if nodes:
        return _finish(window, nodes)
    parts = meshedit_ui._parts(window)
    if not parts:
        window.statusBar().showMessage(language.tr("Nothing to mirror."),
                                       5000)
        return None
    chosen = []

    def picked(desc, node):
        if desc is None:                      # Done / Esc: go on
            if chosen:
                _finish(window, chosen)
            return
        if node is not None and node not in chosen:
            chosen.append(node)
        arm()

    def arm():
        window.view3d.start_pick(
            picked, groups=parts,
            banner=language.tr("Mirror: click the parts to mirror ({n} "
                               "chosen) · Done or Esc goes on").format(
                n=len(chosen)),
            labeler=lambda desc, n: getattr(n, "name", ""))
    arm()
    return None
