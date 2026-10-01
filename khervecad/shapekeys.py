"""The `shape_keys` wrapper (Qt-free): morph targets — Blender's shape
keys — for a mouth that opens, an eye that blinks, a snarl, a breath.

A key is a named set of SCULPT strokes (sculpt.py's brushes, rows in
the children's frame) applied to the base surface; the node keeps each
key's displacement and blends them: every vertex is the base plus the
sum of ``value × (key − base)``. ``keys`` rows ``[name, value]`` — a
value may be an expression, so ``[["blink", "blink"]]`` reads a
document variable, and a Customizer slider on that variable moves the
eyelid (play_motion sweeps it). ``strokes`` rows ``[key, kind, x, y,
z, radius, strength, dx, dy, dz]`` (13 values for a pose stroke),
*key* the key's index; ``mirror`` repeats every stroke across a plane.

A key must keep the mesh's vertices — so no snake hook (it refines the
skin) — and ``detail`` refines the base once for all keys. The
displacement of each key is cached by content, so dragging a slider is
one weighted sum, not a re-sculpt. Baked through bakedkit:
``kcad_shape_keys(keys = [...], strokes = [...], ..., points, faces) {
children }``.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import copy
import hashlib
import json

from . import bakedkit

KEY_LEN = 2
STROKE_LENS = (10, 13)
#: per (base, key strokes): the base _Fast and the key's offsets
_OFFSETS = {}
CACHE_SIZE = 32


def _base(tris, detail):
    from . import deform, sculpt
    if detail > 0:
        tris = deform.split_long_edges(tris, detail)
    return sculpt._Fast(tris)


def _key_offset(base, rows, mirror):
    """The displacement (V, 3) the stroke *rows* (sculpt rows, no key
    index) make on a copy of *base*."""
    from . import sculpt
    fast = copy.copy(base)
    fast.verts = base.verts.copy()
    fast._normals = None
    fast.stale = False
    fast.mask = None
    axis = sculpt.MIRRORS.index(mirror) - 1 if mirror in sculpt.MIRRORS \
        else -1
    for use in sculpt._rows(rows, axis):
        if sculpt.KINDS[int(use[0])] == "snake_hook":
            continue                     # it would change the vertices
        fast = sculpt._fast_stroke(
            fast, int(use[0]), use[1:4], use[4], use[5], use[6:9],
            use[9:12] if len(use) >= sculpt.POSE_LEN else None)
    if len(fast.verts) != len(base.verts):
        return None
    return fast.verts - base.verts


def blend(tris, keys, strokes, mirror="none", detail=0.0):
    """The triangles of *tris* with the shape keys mixed in. *keys*
    ``[(name, value)]``, *strokes* rows ``[key, kind, x, y, z, radius,
    strength, dx, dy, dz(, tip)]`` (resolved)."""
    import numpy as np
    if not tris:
        return []
    h = hashlib.sha1(np.asarray(tris, dtype=np.float64).tobytes())
    h.update(repr((detail, mirror)).encode())
    base_key = h.hexdigest()
    hit = _OFFSETS.get(base_key)
    if hit is None:
        hit = _OFFSETS[base_key] = {"base": _base(tris, detail)}
    base = hit["base"]
    out = base.verts.copy()
    for k, (_name, value) in enumerate(keys):
        if not value:
            continue
        rows = [row[1:] for row in strokes if int(row[0]) == k]
        if not rows:
            continue
        sig = json.dumps(rows) + mirror
        offset = hit.get(sig)
        if offset is None:
            offset = hit[sig] = _key_offset(base, rows, mirror)
        if offset is not None:
            out += float(value) * offset
    while len(_OFFSETS) > CACHE_SIZE:
        _OFFSETS.pop(next(iter(_OFFSETS)))
    fast = copy.copy(base)
    fast.verts = out
    return fast.triangles()


def _resolved(node, env):
    keys = [(str(r[0]), float(r[1]) if not isinstance(r[1], str) else 0.0)
            for r in bakedkit.rows(node, env, "keys", KEY_LEN, (0,))]
    strokes = [r for r in bakedkit.rows(node, env, "strokes", STROKE_LENS)
               if all(not isinstance(v, str) for v in r)]
    return keys, strokes


def _compute(node, env):
    keys, strokes = _resolved(node, env)
    return blend(bakedkit.source_tris(node, env), keys, strokes,
                 str(node.params.get("mirror", "none")),
                 bakedkit.num(node, env, "detail", 0.0))


def _check(node, env):
    from . import expr, sculpt
    keys = node.params.get("keys") or []
    names = []
    for k, row in enumerate(keys):
        if not isinstance(row, list) or len(row) != KEY_LEN:
            return f"key {k} is [name, value]"
        names.append(str(row[0]))
        if isinstance(row[1], str):
            try:
                expr.evaluate(row[1], env)
            except expr.ExprError as exc:
                return f"key {row[0]}: {exc}"
    if len(set(names)) != len(names):
        return "two shape keys have the same name"
    for k, row in enumerate(node.params.get("strokes") or []):
        if not isinstance(row, list) or len(row) not in STROKE_LENS:
            return (f"stroke {k} is [key, kind, x, y, z, radius, strength, "
                    "dx, dy, dz] (13 values for a pose)")
        try:
            index, kind = int(float(row[0])), int(float(row[1]))
        except (TypeError, ValueError):
            return f"stroke {k}: the key and the kind are numbers"
        if not 0 <= index < len(keys):
            return f"stroke {k} belongs to key {index}, which does not exist"
        if not 0 <= kind < len(sculpt.KINDS):
            return f"stroke {k}: kind must be 0-{len(sculpt.KINDS) - 1}"
        if sculpt.KINDS[kind] == "snake_hook":
            return (f"stroke {k}: a shape key keeps the vertices, and a "
                    "snake hook adds some — sculpt the horn first")
    return None


KIT = bakedkit.make(
    "shape_keys", "Shape keys (morph targets)", "mdi.emoticon-outline",
    dict(keys=[], strokes=[], mirror="none", detail=0.0),
    [("keys", "Keys (name, value 0-1 — or a variable)", "rows",
      ["Name", "Value"], None),
     ("strokes", "Key strokes (key, kind, centre, radius, strength, "
                 "direction)", "rows",
      ["Key", "Kind", "X", "Y", "Z", "Radius", "Strength", "dX", "dY",
       "dZ"], None),
     ("mirror", "Mirror strokes across", "choice",
      ["none", "x", "y", "z"], None),
     ("detail", "Refine to edge first (mm, 0 = as is)", "float", 0.0, 1e4)],
    _compute, choices={"mirror": ("none", "x", "y", "z")},
    names={"keys": {0}}, check=_check)
