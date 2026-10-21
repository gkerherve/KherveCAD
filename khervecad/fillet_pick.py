"""Picking the edges of a fillet by clicking them in the 3D view.

`start(window, node)` arms the 3D view's pick mode on the fillet's own
part (the mesh of its children, in the frame the view shows) and keeps
it armed: every click on an edge adds that edge to the node, a click on
a face adds every crease edge bounding that face, Esc or a right click
finishes. The picked edge is stored in the part's LOCAL frame — the
one the fillet's children live in — so the fillet survives moving,
rotating or placing the part: the world mesh the view shows and the
local mesh the fillet computes on are the same tessellation in the same
order, so a picked world vertex maps to its local twin by index.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import fillet, mesh


def _vkey(v):
    return (round(v[0], 5), round(v[1], 5), round(v[2], 5))


def meshes(window, node):
    """``(world_tris, local_tris)`` of the fillet's children as the
    view shows them and as the fillet computes on them — same length
    and order — or ``(None, None)`` when they cannot be matched."""
    from . import bake
    root = window._render_scope()[0]
    iso = root if root is not window.model.root else None
    fn = window.model.effective_fn()
    env = bake._codegen_env(node)
    mesh._set_fn(fn)
    try:
        local = [t for t, _c, _s in
                 mesh._children_mesh(node, env, None, frozenset(), False)]
    finally:
        mesh._set_fn(None)
    if not local:
        return None, None
    # the world copy is the SAME uncut triangles placed where the view
    # shows the part: the fillet's own (cut) mesh has other triangles
    # once a first edge or face is rounded, so a second pick could not
    # match them up and refused to start
    with window._isolated_frame(iso):
        m = mesh.ancestor_matrix(node, env, stop=iso)
        m = mesh.mat_mul(m, mesh.node_matrix(node, env))
    world = [tuple(_apply(m, v) for v in t) for t in local]
    return world, local


def _apply(m, v):
    x, y, z = v[0], v[1], v[2]
    return (m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
            m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
            m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3])


def seeds_from_pick(desc, world, local) -> list:
    """The edge seeds (6-number rows, local frame) a pick means: the
    clicked edge, or every crease edge bounding the clicked face."""
    w2l = {}
    for wt, lt in zip(world, local):
        for wv, lv in zip(wt, lt):
            w2l[_vkey(wv)] = lv
    if desc.get("kind") == "edge":
        a, b = desc["seg"]
        la, lb = w2l.get(_vkey(a)), w2l.get(_vkey(b))
        if la is None or lb is None:
            return []
        return [[round(v, 4) for v in (*la, *lb)]]
    if desc.get("kind") == "face":
        index_of = {}
        for i, wt in enumerate(world):
            index_of[tuple(_vkey(v) for v in wt)] = i
        face = set()
        for wt in desc.get("tris", ()):
            i = index_of.get(tuple(_vkey(v) for v in wt))
            if i is not None:
                face.add(i)
        if not face:
            return []
        # crease edges with exactly one side on the face
        tri_of = {}
        for i, lt in enumerate(local):
            keys = [_vkey(v) for v in lt]
            for k in range(3):
                tri_of[(keys[k], keys[(k + 1) % 3])] = i
        seeds = []
        for e in fillet.crease_edges(local):
            ka, kb = _vkey(e.a), _vkey(e.b)
            sides = [tri_of.get((ka, kb)), tri_of.get((kb, ka))]
            if sum(1 for s in sides if s in face) == 1:
                seeds.append([round(v, 4) for v in (*e.a, *e.b)])
        return seeds
    return []


def face_from_pick(desc, world, local):
    """A face click as a fillet `faces` row [x, y, z, nx, ny, nz] in the
    local frame — the FACE is kept, so its edges (holes cut later
    included) are found again on every rebuild. None if not a face."""
    if desc.get("kind") != "face" or not desc.get("tris"):
        return None
    w2l = {}
    for wt, lt in zip(world, local):
        for wv, lv in zip(wt, lt):
            w2l[_vkey(wv)] = lv
    tri = [w2l.get(_vkey(v)) for v in desc["tris"][0]]
    if any(v is None for v in tri):
        return None
    a, b, c = tri
    n = fillet._unit(fillet._cross(fillet._sub(b, a), fillet._sub(c, a)))
    centre = [(a[i] + b[i] + c[i]) / 3.0 for i in range(3)]
    return [round(v, 4) for v in centre] + [round(v, 6) for v in n]


def start(window, node) -> bool:
    """Arm the pick for *node* (a fillet). Returns False when the part
    has nothing to pick on."""
    world, local = meshes(window, node)
    if world is None:
        window.statusBar().showMessage(
            f"{node.name}: nothing to pick edges on yet — put a solid "
            "inside it first.", 6000)
        return False
    view = window.view3d
    model = window.model

    def count():
        return len(node.params.get("edges") or []) + \
            len(node.params.get("faces") or [])

    def banner():
        n = count()
        picked = f" · {n} picked" if n else ""
        return (f"Fillet: click an edge to round it (a face rounds all "
                f"its edges){picked} · Esc or right-click when done")

    def labeler(desc, _key):
        return ("Edge — click to fillet" if desc.get("kind") == "edge"
                else "Face — click to fillet every edge round it")

    def on_pick(desc, _key):
        if desc is None:                     # finished / cancelled
            window.statusBar().showMessage(
                f"{node.name}: {count()} edge(s) / face(s) — the exact "
                "render "
                "shows the rounding a moment after each change; "
                "right-click the fillet ▸ Pick edges to add more.",
                8000)
            window.builder.active_tree().select_nodes([node])
            return
        row = face_from_pick(desc, world, local)
        if row is not None:
            faces = [list(r) for r in (node.params.get("faces") or [])]
            same = any(all(abs(float(a) - float(b)) < 1e-3
                           for a, b in zip(row[3:], f[3:])) and
                       abs(sum((float(row[i]) - float(f[i])) * float(row[3 + i])
                               for i in range(3))) < 1e-3
                       for f in faces)       # same plane, same way
            if same:
                window.statusBar().showMessage(
                    "That face is already in the fillet.", 3000)
            else:
                faces.append(row)
                model.set_param(node, "faces", faces)
            arm()
            return
        seeds = seeds_from_pick(desc, world, local)
        have = [list(r) for r in (node.params.get("edges") or [])]
        new = [s for s in seeds if not any(
            all(abs(float(a) - float(b)) < 1e-3 for a, b in zip(s, h))
            for h in have)]
        if new:
            model.set_param(node, "edges", have + new)
        else:
            window.statusBar().showMessage(
                "That edge is already in the fillet.", 3000)
        arm()

    def arm():
        view.start_pick(on_pick, groups=[(node, world)], banner=banner(),
                        labeler=labeler)

    arm()
    return True
