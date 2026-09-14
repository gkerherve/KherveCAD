"""A realistic human body: the MakeHuman base mesh with its macro
targets, as one parametric node.

Capsules and lofts never give correct anatomy; MakeHuman's CC0 base
mesh (13,380 vertices, closed, quads) does. The ``human`` node blends
it: ``gender`` (0 female .. 1 male) and ``age`` (0 young .. 1 old)
weight the four macro targets, ``weight`` (-1 thin .. 1 heavy) and
``height`` (-1 short-limbed .. 1 long-limbed proportions) add the
universal weight and height targets, and ``stature`` scales the result
to a height in millimetres. The body stands on Z = 0, centred, facing
-Y, arms in the A-pose the base mesh has.

Targets are sparse vertex offsets in decimetres (MakeHuman's unit),
the base is Y-up; both are turned into KherveCAD's Z-up millimetres
here. The data lives in ``khervecad/human/`` (gzipped, ~1 MB; see its
LICENSE.txt) and is loaded once. Pure geometry, Qt-free; bake.py bakes
the node like the other computed meshes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import gzip
from pathlib import Path

DATA = Path(__file__).resolve().parent / "human"
#: the macro targets shipped, by the key build() looks them up under
TARGETS = ("female-young", "female-old", "male-young", "male-old",
           "female-maxweight", "female-minweight", "male-maxweight",
           "male-minweight", "female-maxheight", "female-minheight",
           "male-maxheight", "male-minheight")
DEFAULT_STATURE = 1700.0

_DATA = None


def _load():
    global _DATA
    if _DATA is not None:
        return _DATA
    verts, faces = [], []
    with gzip.open(DATA / "base_body.obj.gz", "rt") as fh:
        for line in fh:
            if line.startswith("v "):
                verts.append(tuple(float(v) for v in line.split()[1:4]))
            elif line.startswith("f "):
                faces.append(tuple(int(v) - 1 for v in line.split()[1:]))
    targets = {}
    for name in TARGETS:
        rows = {}
        with gzip.open(DATA / f"{name}.target.gz", "rt") as fh:
            for line in fh:
                if line.startswith("#") or not line.strip():
                    continue
                i, dx, dy, dz = line.split()[:4]
                rows[int(i)] = (float(dx), float(dy), float(dz))
        targets[name] = rows
    _DATA = (verts, faces, targets)
    return _DATA


def available() -> bool:
    return (DATA / "base_body.obj.gz").is_file()


def _clamp(v, lo, hi):
    return max(lo, min(hi, float(v)))


def weights(gender=0.0, age=0.0, weight=0.0, height=0.0) -> dict:
    """How much of each target the parameters ask for (MakeHuman's
    macro blend: gender × age over the ethnic targets, weight and
    height per gender on top)."""
    g = _clamp(gender, 0.0, 1.0)
    a = _clamp(age, 0.0, 1.0)
    w = _clamp(weight, -1.0, 1.0)
    h = _clamp(height, -1.0, 1.0)
    out = {}
    for sex, sw in (("female", 1.0 - g), ("male", g)):
        if sw <= 0.0:
            continue
        out[f"{sex}-young"] = sw * (1.0 - a)
        out[f"{sex}-old"] = sw * a
        if w:
            out[f"{sex}-{'max' if w > 0 else 'min'}weight"] = sw * abs(w)
        if h:
            out[f"{sex}-{'max' if h > 0 else 'min'}height"] = sw * abs(h)
    return {k: v for k, v in out.items() if v > 0.0}


def build(gender=0.0, age=0.0, weight=0.0, height=0.0,
          stature=DEFAULT_STATURE) -> list:
    """Triangles of the body (CCW, outward), Z-up millimetres, standing
    on Z = 0 and centred on X, *stature* mm tall."""
    verts, faces, targets = _load()
    pts = [list(v) for v in verts]
    for name, k in weights(gender, age, weight, height).items():
        for i, (dx, dy, dz) in targets[name].items():
            p = pts[i]
            p[0] += dx * k
            p[1] += dy * k
            p[2] += dz * k
    # MakeHuman: Y up, facing +Z, decimetres -> Z up, facing -Y, mm
    pts = [(p[0] * 100.0, -p[2] * 100.0, p[1] * 100.0) for p in pts]
    lo_z = min(p[2] for p in pts)
    hi_z = max(p[2] for p in pts)
    scale = float(stature) / (hi_z - lo_z) if hi_z > lo_z and stature \
        else 1.0
    cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2.0
    pts = [((p[0] - cx) * scale, p[1] * scale, (p[2] - lo_z) * scale)
           for p in pts]
    tris = []
    for face in faces:
        ring = [pts[i] for i in face]
        for k in range(1, len(ring) - 1):
            tris.append((ring[0], ring[k], ring[k + 1]))
    return tris
