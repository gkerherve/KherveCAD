"""Imported meshes (the `stl_import` node): where the file is, how big
it is, and the one-click fixes a downloaded STL usually needs.

- **Paths** stay absolute in memory — the preview, validation and the
  OpenSCAD engine (which renders from a temporary folder) all need one
  that works from anywhere — but are saved RELATIVE to the .kcad when
  the mesh lives in or under the document's folder, so a project folder
  can be moved, zipped or shared and still open. An absolute path that
  no longer exists is looked for by name beside the document before it
  is reported missing (that is where it usually went).
- **Placement**: centre on the origin, or centre and stand on the floor,
  from the mesh's own bounding box (its rotation and scale applied).
- **Units**: an STL carries none. One drawn in inches, centimetres or
  metres arrives 25.4x, 10x or 1000x too small; the size shown on
  import makes that obvious and the Units menu fixes it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
from pathlib import Path, PureWindowsPath

#: the units a mesh file may have been drawn in: (label, scale to mm)
UNITS = [("Millimetres (×1)", 1.0), ("Centimetres (×10)", 10.0),
         ("Metres (×1000)", 1000.0), ("Inches (×25.4)", 25.4)]


def mesh_nodes(nodes):
    """The stl_import nodes among *nodes* or anywhere inside them (an
    imported mesh arrives wrapped in an Object, which is the row the
    user right-clicks in Main)."""
    seen, out = set(), []
    for node in nodes:
        for n in node.walk():
            if n.type == "stl_import" and n.id not in seen:
                seen.add(n.id)
                out.append(n)
    return out


def local_bounds(node, env=None):
    """(lo, hi) of the mesh with its own rotation and scale applied but
    not its x/y/z offset, or None when the file cannot be read."""
    from . import mesh
    try:
        p = dict(mesh.rp(node, env), x=0.0, y=0.0, z=0.0)
    except Exception:
        return None
    tris = mesh.stl_mesh(p)
    if not tris:
        return None
    pts = [v for tri in tris for v in tri]
    lo = tuple(min(v[i] for v in pts) for i in range(3))
    hi = tuple(max(v[i] for v in pts) for i in range(3))
    return lo, hi


def size_text(node, env=None) -> str:
    """" (40 × 41.5 × 73 mm)" — the mesh's size, for the status bar."""
    box = local_bounds(node, env)
    if box is None:
        return ""
    dims = " × ".join(f"{b - a:.4g}" for a, b in zip(*box))
    return f" ({dims} mm)"


def place(model, node, floor=False, env=None) -> bool:
    """Move the mesh so its bounding box is centred on its origin — or,
    with *floor*, centred in X/Y and standing on Z = 0. One undo step
    (the model captures once per event-loop turn)."""
    box = local_bounds(node, env)
    if box is None:
        return False
    lo, hi = box
    centre = [(a + b) / 2.0 for a, b in zip(lo, hi)]
    if floor:
        centre[2] = lo[2]
    for key, c in zip(("x", "y", "z"), centre):
        model.set_param(node, key, round(-c, 6) + 0.0)   # never -0.0
    return True


def set_scale(model, node, factor: float):
    """Scale the mesh by *factor* (the unit it was drawn in → mm)."""
    model.set_param(node, "scale", float(factor))


# ------------------------------------------------------------------ paths

def relative_for_save(data: dict, doc_path: str):
    """In the node dicts about to be written to *doc_path*, rewrite each
    mesh path that lies in or under the document's folder as a path
    relative to it (forward slashes, so it reads on every OS). Anything
    elsewhere — or on another drive — stays absolute. The dicts share
    their params with the live nodes, so a changed one is copied, never
    edited in place."""
    folder = Path(doc_path).resolve().parent
    stack = [data]
    while stack:
        d = stack.pop()
        stack.extend(d.get("children", []))
        if d.get("type") != "stl_import":
            continue
        raw = str(d.get("params", {}).get("path", "")).strip()
        if not raw or not os.path.isabs(raw):
            continue
        try:
            rel = Path(raw).resolve().relative_to(folder)
        except (ValueError, OSError):
            continue
        d["params"] = dict(d["params"], path=rel.as_posix())


def resolve_paths(root, base_dir: str):
    """Make every mesh path under *root* absolute. A relative one is read
    against *base_dir* — the .kcad's folder, or a .scad file's (OpenSCAD
    reads import() paths the same way). An absolute one that no longer
    exists, including a Windows path read on another OS, is looked for
    by file name in *base_dir*."""
    base = os.path.abspath(base_dir)
    for n in root.walk():
        if n.type != "stl_import":
            continue
        raw = str(n.params.get("path", "")).strip()
        if not raw:
            continue
        foreign = bool(PureWindowsPath(raw).drive) or raw.startswith("\\\\")
        if not foreign and not os.path.isabs(raw):
            n.params["path"] = os.path.normpath(os.path.join(base, raw))
            continue
        if os.path.exists(raw):
            continue
        beside = os.path.join(base, PureWindowsPath(raw).name)
        if os.path.exists(beside):
            n.params["path"] = beside
