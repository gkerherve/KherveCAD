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

A picked face, or a main plane (the PART's Front / Top / Right, i.e. the
scope's), is given in the scope's frame; it is carried into the
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
    # a normal goes world -> local by the inverse-transpose of the
    # world -> local map, i.e. M's own transpose (inv(M)^T turned it the
    # wrong way: invisible until the frame was rotated, as a face
    # sketch's is)
    n = m[:3, :3].T @ np.array(normal, dtype=float)
    ln = float(np.linalg.norm(n)) or 1.0
    return tuple(float(v) for v in p[:3]), tuple(float(v) / ln for v in n)


#: the main planes by the key the tree rows and plane_pick use
MAIN = {"Front (XZ)": (0.0, 1.0, 0.0), "Top (XY)": (0.0, 0.0, 1.0),
        "Side (YZ)": (1.0, 0.0, 0.0)}
_BY_NAME = {"Front Plane (XZ)": "Front (XZ)", "Top Plane (XY)": "Top (XY)",
            "Right Plane (YZ)": "Side (YZ)"}


def plane_in_scope(window, spec):
    """``(point, normal)`` of a plane choice in the scope's frame. *spec*:
    ``("main", "Side (YZ)")``, ``("face", point, normal)`` (already in the
    scope's frame) or ``("ref", ref_plane node)``."""
    kind = spec[0]
    if kind == "main":
        return (0.0, 0.0, 0.0), MAIN[spec[1]]
    if kind == "face":
        return tuple(spec[1]), tuple(spec[2])
    import numpy as np
    from . import mesh, refgeom
    node = spec[1]
    origin, normal = refgeom.plane_of(node)
    scope = window._render_scope()[0]
    stop = None if scope is window.model.root else scope
    m = np.array(mesh.ancestor_matrix(node, {}, stop=stop), dtype=float)
    p = m @ np.array([origin[0], origin[1], origin[2], 1.0])
    n = np.linalg.inv(m[:3, :3]).T @ np.array(normal, dtype=float)
    ln = float(np.linalg.norm(n)) or 1.0
    return tuple(float(v) for v in p[:3]), tuple(float(v) / ln for v in n)


def mirror(window, nodes, spec):
    """Mirror *nodes* about the plane *spec* (see `plane_in_scope`): one
    Mirror per parent, each given the plane in its own frame. The new
    nodes."""
    point, normal = plane_in_scope(window, spec)
    groups = {}
    for n in nodes:
        if n.parent is not None and n is not window.model.root:
            groups.setdefault(id(n.parent), []).append(n)
    made = []
    for group in groups.values():
        p, nrm = _to_parent(window, group[0].parent, point, normal)
        node = apply(window.model, group, nrm, p)
        if node is not None:
            made.append(node)
    return made


def spec_text(spec):
    from . import language, plane_pick
    if spec is None:
        return ""
    if spec[0] == "main":
        return language.tr(plane_pick.name_of(spec[1]))
    if spec[0] == "face":
        return language.tr("A face")
    return spec[1].name or language.tr("Plane")


# =================================================================== Qt
def _view(window):
    return window.view3d


def _panel(window):
    return getattr(window, "_mirror_panel", None)


def start(window):
    """SolidWorks' Mirror window (2026-11-13, the user: "similar to
    extrude"): box 1 what to mirror — the tree's selection, rows clicked
    in the tree, parts clicked in 3D; box 2 the plane — Front / Top /
    Right Plane in the tree or in 3D, a flat face, or a reference plane
    of the tree. OK makes the Mirror, Cancel / Esc leaves nothing."""
    from . import language, meshedit_ui
    close(window)
    nodes = [n for n in window.builder.active_tree().selected_nodes()
             if n is not window.model.root]
    if not nodes and not meshedit_ui._parts(window):
        window.statusBar().showMessage(language.tr("Nothing to mirror."),
                                       5000)
        return None
    st = window._mirror_state = dict(nodes=[], plane=None, active=None,
                                     quiet=False)
    for n in nodes:
        if n.type == "ref_plane":
            st["plane"] = ("ref", n)
        else:
            st["nodes"].append(n)
    panel = _make_panel(window)
    window._mirror_panel = panel
    _hook_trees(window, True)
    _refresh(window)
    panel.open()
    _activate(window, "plane" if st["nodes"] and st["plane"] is None
              else "nodes")
    return panel


def _make_panel(window):
    from . import language
    from .tool_panel import ToolPanel
    panel = ToolPanel(window.view3d, language.tr("Mirror"),
                      on_ok=lambda: ok(window),
                      on_cancel=lambda: cancel(window))
    panel.hint(language.tr(
        "1. What to mirror: click features in the tree (History) or parts "
        "in the 3D view.\n2. The plane: Front, Top or Right Plane at the "
        "top of the tree or in the 3D view, a reference plane, or a flat "
        "face of the part."))
    panel.selection("nodes", language.tr("Features / bodies to mirror"),
                    on_activate=lambda k: _activate(window, k))
    panel.selection("plane", language.tr("Mirror plane / face"),
                    on_activate=lambda k: _activate(window, k))
    panel.finish()
    return panel


def _refresh(window):
    from . import language
    st = getattr(window, "_mirror_state", None)
    panel = _panel(window)
    if not st or panel is None:
        return
    names = [_shown_name(window, n) for n in st["nodes"]]
    panel.boxes["nodes"].set_text(
        ", ".join(names) if names else
        language.tr("Click features in the tree or parts in 3D"))
    panel.boxes["plane"].set_text(
        spec_text(st["plane"]) or language.tr(
            "Click Front / Top / Right Plane (tree or 3D) or a face"))
    panel.set_ok_enabled(bool(st["nodes"]) and st["plane"] is not None)
    pp = getattr(window, "_plane_pick", None)
    if pp is not None:
        plane = st["plane"]
        pp["chosen"] = plane[1] if plane and plane[0] == "main" else None
    window.view3d.update()


def _shown_name(window, node):
    """What the tree calls *node* ("Boss-Extrude 3" in History)."""
    from PyQt5.QtWidgets import QTreeWidgetItemIterator
    from .tree_history import ROLE_SHOWN
    try:
        tree = window.builder.active_tree()
        it = QTreeWidgetItemIterator(tree)
        while it.value() is not None:
            item = it.value()
            if tree.node_of(item) is node:
                return (item.data(0, ROLE_SHOWN) or item.text(0)).strip()
            it += 1
    except Exception:                          # pragma: no cover
        pass
    return node.name or node.type


def _drop_pick(window):
    """End the 3D pick WITHOUT its callback (switching boxes)."""
    view = _view(window)
    if view._pick_cb is not None:
        view._pick_cb = None
        view._end_pick_mode()


def _activate(window, key):
    from . import plane_pick
    st = getattr(window, "_mirror_state", None)
    panel = _panel(window)
    if not st or panel is None:
        return
    st["active"] = key
    panel.set_active(key)
    _drop_pick(window)
    if key == "plane":
        # the three planes drawn and clickable, as for a sketch
        window._plane_pick = {"half": plane_pick._half(window),
                              "hover": None, "on_plane": None,
                              "mirror": True}
    elif getattr(window, "_plane_pick", None) and \
            window._plane_pick.get("mirror"):
        window._plane_pick = None
    _refresh(window)
    _arm(window)


def _face_depth(view, point):
    eye, _r, _u, forward = view._camera()
    return sum((point[i] - eye[i]) * forward[i] for i in range(3))


def _arm(window):
    from . import language, meshedit_ui, plane_pick
    st = window._mirror_state
    view = _view(window)
    parts = meshedit_ui._parts(window) or []
    plane_box = st["active"] == "plane"

    def picked(desc, node=None):
        if getattr(window, "_mirror_state", None) is not st:
            return
        pp = getattr(window, "_plane_pick", None)
        if pp:
            pp.pop("pos", None)
        pos = st.pop("pos", None)               # where the click landed
        if desc is None and pos is None:        # Esc: Cancel
            cancel(window)
            return
        if not plane_box:
            if node is not None:
                if node in st["nodes"]:
                    st["nodes"].remove(node)
                else:
                    st["nodes"].append(node)
                _select(window, st["nodes"])
            _refresh(window)
            _arm(window)
            return
        plane = plane_pick.hit(window, pos) if pos is not None else None
        face = desc if desc is not None and desc.get("kind") == "face" \
            else None
        if face is not None and plane is not None:
            # the nearer of the two under the cursor
            depth = plane_pick._depths(window, pos).get(plane)
            hit_at = face.get("point") or face.get("pos")
            if depth is not None and _face_depth(view, hit_at) > depth:
                face = None
            else:
                plane = None
        if face is not None:
            st["plane"] = ("face", tuple(face["pos"]), tuple(face["dir"]))
            view.set_pick_pinned(face, language.tr("Mirror plane"))
        elif plane is not None:
            st["plane"] = ("main", plane)
            view.set_pick_pinned(None)
        elif desc is not None:
            window.statusBar().showMessage(language.tr(
                "Mirror: click a flat FACE (not an edge), or a plane."),
                5000)
        _refresh(window)
        _arm(window)

    if plane_box:
        banner = language.tr("Mirror: click Front, Top or Right Plane, or a "
                             "flat face · OK in the window mirrors · Esc "
                             "cancels")
    else:
        banner = language.tr("Mirror: click the parts to mirror ({n} "
                             "chosen) · then the plane box").format(
            n=len(st["nodes"]))
    view.start_pick(picked, groups=parts, banner=banner, done=False,
                    labeler=lambda desc, n: getattr(n, "name", ""))


def _select(window, nodes):
    st = window._mirror_state
    st["quiet"] = True
    try:
        window.builder.active_tree().select_nodes(list(nodes))
    except Exception:                          # pragma: no cover
        pass
    finally:
        st["quiet"] = False


# ------------------------------------------------- the tree feeds it
def _trees(window):
    out = [getattr(window.builder, "tree", None)]
    tab = getattr(window.builder, "object_tab", None)
    out.append(getattr(tab, "tree", None))
    return [t for t in out if t is not None]


def _hook_trees(window, on):
    if not hasattr(window, "_mirror_tree_slot"):
        window._mirror_tree_slot = lambda nodes: tree_selected(window,
                                                               nodes)

        def note(pos):
            # where a click lands (the pick callback has no position): a
            # click on empty space is not Esc
            st = getattr(window, "_mirror_state", None)
            if st is not None:
                st["pos"] = pos
            return False
        view = _view(window)
        view.release_hooks = list(getattr(view, "release_hooks", ())) + \
            [note]
    for tree in _trees(window):
        try:
            if on:
                tree.selection_changed.connect(window._mirror_tree_slot)
            else:
                tree.selection_changed.disconnect(window._mirror_tree_slot)
        except (TypeError, RuntimeError, AttributeError):
            pass


def tree_selected(window, nodes):
    """The tree's selection changed while the window is open: a reference
    plane is the plane, anything else what to mirror."""
    st = getattr(window, "_mirror_state", None)
    if not st or st["quiet"] or not nodes:
        return
    planes = [n for n in nodes if n.type == "ref_plane"]
    rest = [n for n in nodes if n.type != "ref_plane"
            and n is not window.model.root]
    if planes:
        st["plane"] = ("ref", planes[-1])
    if rest:
        st["nodes"] = rest
    _refresh(window)
    if rest and st["plane"] is None and st["active"] == "nodes":
        _activate(window, "plane")


def plane_row(window, plane):
    """Front / Top / Right Plane clicked in the tree: the mirror plane.
    True when the window took it."""
    st = getattr(window, "_mirror_state", None)
    if not st:
        return False
    st["plane"] = ("main", plane)
    _view(window).set_pick_pinned(None)
    if st["active"] != "plane":
        _activate(window, "plane")
    _refresh(window)
    return True


# ------------------------------------------------------------ finish
def ok(window):
    st = getattr(window, "_mirror_state", None)
    if not st or not st["nodes"] or st["plane"] is None:
        return []
    nodes, spec = list(st["nodes"]), st["plane"]
    close(window)
    made = mirror(window, nodes, spec)
    _done(window, made, spec_text(spec))
    return made


def cancel(window):
    close(window)


def close(window):
    st = getattr(window, "_mirror_state", None)
    panel = _panel(window)
    if st is None and panel is None:
        return
    window._mirror_state = None
    window._mirror_panel = None
    _hook_trees(window, False)
    view = _view(window)
    _drop_pick(window)
    view.set_pick_pinned(None)
    pp = getattr(window, "_plane_pick", None)
    if pp and pp.get("mirror"):
        window._plane_pick = None
    if panel is not None:
        panel.hide()
        panel.deleteLater()
    view.update()


def _done(window, made, plane):
    if not made:
        return
    window.builder.active_tree().select_nodes(made)
    window.statusBar().showMessage(
        "Mirrored about %s — the original is kept; the plane is in "
        "Properties." % plane, 7000)
