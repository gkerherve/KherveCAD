"""Exploded views — every part of an assembly pushed away from its
centre, so you can see how it goes together.

A display, never an edit: the object tree is untouched. Each top-level
part (an Object, an instance, a coloured group...) is tessellated on
its own — with the document's variables and its own colours, and with
the exact OpenSCAD mesh the preview already holds for it — then moved
along the line from the assembly's centre to the part's centre:

- **Radial** — outwards in every direction (the classic exploded view);
- **X / Y / Z** — along one axis only (a stack of plates, a row of
  parts), keeping the other two coordinates.

*amount* scales the move: 1.0 pushes each part as far again as it
already sits from the centre. View ▸ Exploded View shows it in the 3D
view; `showing()` switches it on for as long as a picture is taken
(File ▸ Export PNG, the Printables bundle's exploded stills).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from contextlib import contextmanager

MODES = ("Radial", "X", "Y", "Z")
AMOUNTS = (0.5, 1.0, 1.5, 2.0, 3.0)
DEFAULT_AMOUNT, DEFAULT_MODE = 1.0, "Radial"
SKIP = ("assign", "variables", "masters")


def part_meshes(root, env=None, fn=None) -> list:
    """[(part node, [(triangle, colour)])] — one entry per top-level
    part of *root* (the document, or the Object being edited) that has
    geometry, each tessellated on its own."""
    from . import mesh
    env = dict(env or {})
    base = None
    if root.type != "root" and root.params.get("color"):
        base = (str(root.params["color"]),
                float(root.params.get("alpha", 1.0) or 1.0))
    mesh._set_fn(fn)
    mesh._set_refs(root)
    out = []
    try:
        for child in root.children:
            if child.type == "assign":
                mesh._apply_assign(child, env)
                continue
            if child.type == "variables":
                for grand in child.children:
                    if grand.type == "assign":
                        mesh._apply_assign(grand, env)
                continue
            if child.type in SKIP or not child.visible:
                continue
            items = [(t, c) for t, c, _s in
                     mesh._tess(child, dict(env), base, frozenset(), False)]
            if items:
                out.append((child, items))
    finally:
        mesh._set_fn(None)
        mesh._clear_refs()
    return out


def _box(tris):
    pts = [v for tri in tris for v in tri]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return lo, hi


def _centre(box):
    lo, hi = box
    return [(lo[i] + hi[i]) / 2.0 for i in range(3)]


def offsets(boxes, amount=DEFAULT_AMOUNT, mode=DEFAULT_MODE) -> list:
    """The move of each part (bounding boxes in, [dx, dy, dz] out):
    along centre-of-assembly -> centre-of-part, times *amount*, kept to
    one axis unless *mode* is Radial."""
    if not boxes:
        return []
    lo = [min(b[0][i] for b in boxes) for i in range(3)]
    hi = [max(b[1][i] for b in boxes) for i in range(3)]
    whole = [(lo[i] + hi[i]) / 2.0 for i in range(3)]
    axes = {"X": (0,), "Y": (1,), "Z": (2,)}.get(mode, (0, 1, 2))
    moves = []
    for box in boxes:
        c = _centre(box)
        moves.append([(c[i] - whole[i]) * float(amount) if i in axes else 0.0
                      for i in range(3)])
    return moves


def exploded_colored(root, env=None, fn=None, amount=DEFAULT_AMOUNT,
                     mode=DEFAULT_MODE) -> list:
    """[(triangle, colour)] of *root* with every part moved out — what
    the 3D view draws in an exploded view."""
    parts = part_meshes(root, env, fn)
    if len(parts) < 2:                       # nothing to pull apart
        return [item for _p, items in parts for item in items]
    moves = offsets([_box([t for t, _c in items]) for _p, items in parts],
                    amount, mode)
    out = []
    for (_part, items), (dx, dy, dz) in zip(parts, moves):
        for tri, colour in items:
            out.append((tuple((v[0] + dx, v[1] + dy, v[2] + dz) for v in tri),
                        colour))
    return out


def part_count(root, env=None, fn=None) -> int:
    return len(part_meshes(root, env, fn))


@contextmanager
def showing(window, amount=DEFAULT_AMOUNT, mode=DEFAULT_MODE):
    """The 3D view exploded for the duration — a picture of it can be
    taken — and put back as it was afterwards."""
    before = dict(window.explode_state())
    window.set_explode(True, amount, mode)
    try:
        yield
    finally:
        window.set_explode(before["on"], before["amount"], before["mode"])
