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
    with window._isolated_frame(iso):
        world = mesh.selected_world_tris(root, {node.id}, fn=fn)
    env = bake._codegen_env(node)
    mesh._set_fn(fn)
    try:
        local = [t for t, _c, _s in
                 mesh._children_mesh(node, env, None, frozenset(), False)]
    finally:
        mesh._set_fn(None)
    if not world or len(world) != len(local):
        return None, None
    return world, local


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
        return len(node.params.get("edges") or [])

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
                f"{node.name}: {count()} edge(s) — the exact render "
                "shows the rounding a moment after each change; "
                "right-click the fillet ▸ Pick edges to add more.",
                8000)
            window.builder.active_tree().select_nodes([node])
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
