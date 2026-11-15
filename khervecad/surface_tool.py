"""The surface tools' windows — Trim, Knit, Planar, Boundary, Thicken and
Fillet (Qt side of surface_edit.py).

`start(window, op)`: the surfaces selected in the tree are wrapped in a
`surface_edit` node (so the result shows at once), and a tool window
like Extruded Boss's opens beside the 3D view:

* **Trim**      — Standard / Mutual, then click the PIECES to remove in
                  the 3D view (each click toggles one; "Keep selections"
                  keeps them instead).
* **Knit**      — one tick: make a solid when the surfaces close.
* **Planar / Boundary surface** — click an open EDGE of the surface (a
                  planar surface fills the whole loop it belongs to, a
                  boundary surface closes a round edge by its chord).
* **Thicken**   — the wall in mm.
* **Fillet**    — the radius, then click the edges.

Every click is stored as a point in the node's own frame (what
surface_edit looks the piece / edge up by), so the tree keeps working
after later edits. OK keeps the node, Cancel / Esc takes it apart.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from . import language, mesh

#: op -> (window title, tree name, the rows parameter the clicks fill,
#:        banner sentence)
OPS = {
    "trim": ("Trim Surface", "Surface-Trim", "remove",
             "Trim: click the pieces to REMOVE · OK in the window trims "
             "· Esc cancels"),
    "knit": ("Knit Surface", "Surface-Knit", None, ""),
    "planar": ("Planar Surface", "Surface-Plane", "points",
               "Planar surface: click an open edge — its whole loop is "
               "filled flat · OK in the window · Esc cancels"),
    "boundary": ("Boundary Surface", "Boundary-Surface", "points",
                 "Boundary surface: click a round open edge — it is "
                 "closed by its chord · OK in the window · Esc cancels"),
    "thicken": ("Thicken", "Thicken", None, ""),
    "fillet": ("Surface Fillet", "Fillet", "fillets",
               "Fillet: click the edges to round · OK in the window · "
               "Esc cancels"),
}

SURFACE_TYPES = ("curve_surface", "surface_edit")


def _state(window):
    return getattr(window, "_surface_state", None)


def selected(window):
    tree = window.builder.active_tree()
    nodes = tree.selected_nodes() if hasattr(tree, "selected_nodes") \
        else []
    return [n for n in nodes if n.type in SURFACE_TYPES
            or n.type == "curve"]


def start(window, op):
    """Open the window for *op* on the selected surfaces. The panel, or
    None when nothing usable is selected."""
    close(window)
    nodes = selected(window)
    if not nodes:
        window.statusBar().showMessage(language.tr(
            "{tool}: select the surface(s) in the tree first (Ctrl+click "
            "for several — the first is the one trimmed or filled)."
        ).format(tool=language.tr(OPS[op][0])), 8000)
        return None
    parent = nodes[0].parent
    if any(n.parent is not parent for n in nodes):
        window.statusBar().showMessage(language.tr(
            "Select surfaces that sit side by side in the tree."), 6000)
        return None
    from . import surface_edit
    node = window.model.wrap_nodes(nodes, "surface_edit")
    node.params.update(surface_edit._DEFAULTS, op=op)
    node.name = _name(window.model, OPS[op][1])
    window.model.node_changed.emit(node)
    st = window._surface_state = dict(node=node, op=op)
    panel = _make_panel(window, st)
    window._surface_panel = panel
    st["panel"] = panel
    _refresh(window)
    panel.open()
    if OPS[op][2]:
        _arm(window)
    return panel


def _name(model, base):
    """"Surface-Trim1", "Surface-Trim2"… as SolidWorks numbers them."""
    taken = {n.name for n in model.root.walk()}
    i = 1
    while f"{base}{i}" in taken:
        i += 1
    return f"{base}{i}"


def _make_panel(window, st):
    from .tool_panel import ToolPanel
    op, node = st["op"], st["node"]
    title = language.tr(OPS[op][0])
    panel = ToolPanel(window.view3d, title, on_ok=lambda: ok(window),
                      on_cancel=lambda: cancel(window))
    model = window.model

    def setp(key):
        return lambda v: model.set_param(node, key, v)

    if op == "trim":
        panel.hint(language.tr(
            "1. Select the surfaces in the tree (the first is trimmed by "
            "the rest in Standard).\n2. Click the pieces to remove in the "
            "3D view."))
        panel.choice("mutual", language.tr("Trim type"),
                     [(False, language.tr("Standard")),
                      (True, language.tr("Mutual"))],
                     bool(node.params.get("mutual")), setp("mutual"))
        panel.selection("picks", language.tr("Pieces to remove"))
        panel.check("keep", language.tr("Keep selections instead"),
                    node.params.get("keep"), setp("keep"))
    elif op == "knit":
        panel.hint(language.tr("The selected surfaces are sewn into one "
                               "body."))
        panel.check("solid", language.tr("Create solid when closed"),
                    node.params.get("solid"), setp("solid"))
    elif op in ("planar", "boundary"):
        panel.hint(language.tr(
            "Click an open edge of the surface in the 3D view."))
        panel.selection("picks", language.tr("Edges"))
    elif op == "thicken":
        panel.number("thickness", language.tr("Thickness"),
                     node.params.get("thickness", 2.0), setp("thickness"),
                     minimum=-1e4, maximum=1e4)
    elif op == "fillet":
        panel.hint(language.tr("Set the radius, then click the edges to "
                               "round."))
        panel.number("radius", language.tr("Radius"),
                     node.params.get("radius", 5.0), setp("radius"))
        panel.selection("picks", language.tr("Edges to round"))
    panel.finish()
    return panel


def _rows(st):
    key = OPS[st["op"]][2]
    return list(st["node"].params.get(key) or []) if key else []


def _refresh(window):
    st = _state(window)
    if not st or "panel" not in st:
        return
    box = st["panel"].boxes.get("picks")
    if box is not None:
        n = len(_rows(st))
        box.set_text(language.tr("{n} picked").format(n=n) if n else
                     language.tr("Click in the 3D view"))
    from .model import validate
    problem = validate(window.model.root).get(st["node"].id)
    st["panel"].set_ok_enabled(problem is None)


def _own_meshes(window, node):
    """(world_tris, matrix): the node's own result where the view shows
    it, and the matrix from its frame to the world."""
    from . import bake
    env = bake._codegen_env(node)
    from . import surface_edit
    local = list(surface_edit.KIT.triangles(node, env)[0])
    root = window._render_scope()[0]
    iso = root if root is not window.model.root else None
    with window._isolated_frame(iso):
        m = mesh.ancestor_matrix(node, env, stop=iso)
        m = mesh.mat_mul(m, mesh.node_matrix(node, env))
    world = [tuple(mesh.mat_apply(m, v) for v in t) for t in local]
    return world, m


def _arm(window):
    st = _state(window)
    if st is None:
        return
    node, op = st["node"], st["op"]
    try:
        world, m = _own_meshes(window, node)
    except Exception:
        world, m = [], None
    if not world:
        window.statusBar().showMessage(language.tr(
            "Nothing to pick on yet — the surfaces do not make a result."
        ), 6000)
        return
    st["matrix"] = m
    view = window.view3d

    def picked(desc, _key=None):
        if _state(window) is not st:
            return
        if desc is None:                      # Esc / right click
            cancel(window)
            return
        point = desc.get("pos") or desc.get("point")
        _add(window, st, point)
        _arm(window)

    view.start_pick(picked, groups=[(node, world)],
                    banner=language.tr(OPS[op][3]), done=False)


def to_local(m, point):
    """A world point in the node's own frame."""
    import numpy as np
    inv = np.linalg.inv(np.asarray(m, dtype=float))
    return [round(float(v), 4) for v in mesh.mat_apply(inv.tolist(),
                                                       tuple(point))]


def _add(window, st, world_point):
    """A click: add its point to the node's rows (toggling for a trim)."""
    key = OPS[st["op"]][2]
    local = to_local(st["matrix"], world_point)
    rows = _rows(st)
    if st["op"] == "fillet":
        local = local + [float(st["node"].params.get("radius", 5.0))]
    near = [r for r in rows if sum((float(r[i]) - local[i]) ** 2
                                   for i in range(3)) < 1.0]
    if near and st["op"] == "trim":
        rows = [r for r in rows if r not in near]   # a second click undoes
    else:
        rows.append(local)
    window.model.set_param(st["node"], key, rows)
    _refresh(window)


# ----------------------------------------------------------- finishing

def ok(window):
    st = _state(window)
    if st is None:
        return
    node = st["node"]
    _close_panel(window)
    window.statusBar().showMessage(language.tr(
        "{name} made — its settings are in Properties.").format(
        name=node.name), 8000)
    try:
        window.builder.active_tree().select_nodes([node])
    except Exception:                                  # pragma: no cover
        pass


def cancel(window):
    st = _state(window)
    if st is None:
        return
    node = st["node"]
    _close_panel(window)
    if node.parent is not None:
        window.model.ungroup(node)


def close(window):
    if _state(window) is not None:
        cancel(window)


def _close_panel(window):
    st = _state(window)
    panel = getattr(window, "_surface_panel", None)
    window._surface_state = None          # first: cancel_pick calls back
    window._surface_panel = None
    window.view3d.cancel_pick()
    if panel is not None:
        panel.hide()
        panel.deleteLater()
    return st
