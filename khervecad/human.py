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
import math
from pathlib import Path

DATA = Path(__file__).resolve().parent / "human"
FACE_DIR = DATA / "face"
#: slider file pairs: the negative weight uses the first suffix; the
#: direction pairs get an axis word, since `nose-trans` has in/out,
#: down/up AND backward/forward files
_PAIRS = (("decr", "incr", ""), ("in", "out", "-side"),
          ("down", "up", "-vert"), ("backward", "forward", "-depth"),
          ("concave", "convex", ""), ("compress", "uncompress", ""))
DEFAULT_WARP_RADIUS = 45.0
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


# ------------------------------------------------------ face targets

_FACE = {}
_SLIDERS = None


def _read_target(path) -> dict:
    rows = {}
    with gzip.open(path, "rt") as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            i, dx, dy, dz = line.split()[:4]
            rows[int(i)] = (float(dx), float(dy), float(dz))
    return rows


def face_target(name) -> dict:
    """The sparse offsets of one shipped face target file (no .target)."""
    rows = _FACE.get(name)
    if rows is None:
        path = FACE_DIR / f"{name}.target.gz"
        rows = _FACE[name] = _read_target(path) if path.is_file() else {}
    return rows


def sliders() -> dict:
    """The face sliders: name -> [(negative file, positive file)], one
    pair per side for the l-/r- targets. ``nose-scale-horiz`` runs
    ``nose-scale-horiz-decr`` at -1 to ``-incr`` at +1; a direction
    pair carries its axis (``nose-trans-side`` in/out, ``-vert``
    down/up, ``-depth`` backward/forward); ``eye-scale`` moves both
    eyes, ``l-eye-scale`` one; a shape such as ``head-oval`` has no
    negative side (0 .. 1)."""
    global _SLIDERS
    if _SLIDERS is not None:
        return _SLIDERS
    files = set()
    if FACE_DIR.is_dir():
        for f in FACE_DIR.iterdir():
            if f.name.endswith(".target.gz"):
                files.add(f.name[:-len(".target.gz")])
    out = {}
    done = set()
    for f in sorted(files):
        if f in done:
            continue
        stem, suffix = f.rsplit("-", 1) if "-" in f else (f, "")
        pair, axis = None, ""
        for neg, pos, word in _PAIRS:
            if suffix == neg and f"{stem}-{pos}" in files:
                pair, axis = (f, f"{stem}-{pos}"), word
            elif suffix == pos and f"{stem}-{neg}" in files:
                pair, axis = (f"{stem}-{neg}", f), word
            if pair:
                break
        if pair:
            out[stem + axis] = [pair]
            done.update(pair)
        else:
            out[f] = [(None, f)]
            done.add(f)
    # both sides at once for the l-/r- pairs
    for name in list(out):
        if name.startswith("l-") and "r-" + name[2:] in out:
            out[name[2:]] = out[name] + out["r-" + name[2:]]
    _SLIDERS = out
    return out


def target_weights(targets) -> dict:
    """file -> weight to add, from ``[[slider, weight], ...]``."""
    table = sliders()
    out = {}
    for row in targets or []:
        try:
            name, w = str(row[0]).strip(), float(row[1])
        except (TypeError, ValueError, IndexError):
            continue
        for neg, pos in table.get(name, ()):
            f = pos if w > 0 else neg
            if f and w:
                out[f] = out.get(f, 0.0) + min(abs(w), 1.0)
    return out


# ---------------------------------------------------------- warping

def _solve(a, b):
    """Gaussian elimination with partial pivoting; a is n x n."""
    n = len(a)
    m = [list(row) + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            continue
        m[col], m[piv] = m[piv], m[col]
        for r in range(n):
            if r != col and m[r][col]:
                k = m[r][col] / m[col][col]
                for c in range(col, n + 1):
                    m[r][c] -= k * m[col][c]
    return [m[i][n] / m[i][i] if abs(m[i][i]) > 1e-12 else 0.0
            for i in range(n)]


def rbf_warp(points, warp, radius=DEFAULT_WARP_RADIUS) -> list:
    """*points* moved by a smooth field that carries each warp row's
    centre exactly by its displacement (Gaussian radial basis functions
    of *radius*, coefficients solved so the centres land where asked)
    and fades to nothing a few radii away."""
    rows = []
    for r in warp or []:
        try:
            v = [float(x) for x in r]
        except (TypeError, ValueError):
            continue
        if len(v) == 6:
            rows.append(v)
    if not rows or radius <= 0:
        return points
    r2 = float(radius) ** 2
    n = len(rows)
    centres = [r[:3] for r in rows]

    def phi(a, b):
        d2 = sum((a[k] - b[k]) ** 2 for k in range(3))
        return math.exp(-d2 / r2)
    kernel = [[phi(centres[i], centres[j]) + (1e-6 if i == j else 0.0)
               for j in range(n)] for i in range(n)]
    coef = [_solve(kernel, [rows[i][3 + k] for i in range(n)])
            for k in range(3)]
    cutoff = 9.0 * r2                        # exp(-9) is nothing
    out = []
    for p in points:
        dx = dy = dz = 0.0
        for i, c in enumerate(centres):
            d2 = (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2
            if d2 > cutoff:
                continue
            w = math.exp(-d2 / r2)
            dx += coef[0][i] * w
            dy += coef[1][i] * w
            dz += coef[2][i] * w
        out.append((p[0] + dx, p[1] + dy, p[2] + dz))
    return out


# ------------------------------------------------------------- rig

_SKELETON = None


def skeleton() -> dict:
    """MakeHuman's default rig: ``bones`` (parent, head/tail joint
    names), ``joints`` (the 8 helper vertices each, raw frame),
    ``joint_offsets`` (how the macro targets move those helpers) and
    ``weights`` (bone -> [[vertex, weight]])."""
    global _SKELETON
    if _SKELETON is None:
        import json
        path = DATA / "skeleton.json.gz"
        if path.is_file():
            with gzip.open(path, "rt") as fh:
                _SKELETON = json.load(fh)
        else:
            _SKELETON = {"bones": {}, "joints": {}, "joint_offsets": {},
                         "weights": {}}
    return _SKELETON


def bone_names() -> list:
    return sorted(skeleton()["bones"])


def joint_position(name, macro) -> list:
    """A joint's centre (raw frame, mm) under the macro *macro*
    (target file -> weight): the helper cube's corners move with the
    body the way MakeHuman moves them."""
    sk = skeleton()
    helpers = sk["joints"].get(name)
    if not helpers:
        return [0.0, 0.0, 0.0]
    acc = [0.0, 0.0, 0.0]
    for k, base in enumerate(helpers):
        p = list(base)
        for target, w in macro.items():
            off = sk["joint_offsets"].get(target, {}).get(name, {}).get(str(k))
            if off:
                p[0] += off[0] * w
                p[1] += off[1] * w
                p[2] += off[2] * w
        for i in range(3):
            acc[i] += p[i]
    return [v / len(helpers) for v in acc]


def _rot(rx, ry, rz):
    from .mesh import mat_rotate
    return mat_rotate(rx, ry, rz)


def _mul(a, b):
    from .mesh import mat_mul
    return mat_mul(a, b)


def _translate(x, y, z):
    from .mesh import mat_translate
    return mat_translate(x, y, z)


def bone_matrices(pose, macro) -> dict:
    """bone -> 4x4 world matrix for the *pose* rows ``[bone, rx, ry,
    rz]`` (degrees, about the bone's head, in the body's axes), each
    bone carrying its parent's motion: the tree is the armature."""
    sk = skeleton()
    bones = sk["bones"]
    angles = {}
    for row in pose or []:
        try:
            name = str(row[0]).strip()
            a = [float(v) for v in row[1:4]]
        except (TypeError, ValueError, IndexError):
            continue
        if name in bones and len(a) == 3 and any(a):
            angles[name] = a
    if not angles:
        return {}
    heads = {}
    done = {}
    identity = [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]

    def matrix(name):
        if name in done:
            return done[name]
        b = bones[name]
        parent = matrix(b["parent"]) if b.get("parent") in bones else identity
        local = identity
        if name in angles:
            if name not in heads:
                heads[name] = joint_position(b["head"], macro)
            hx, hy, hz = heads[name]
            rx, ry, rz = angles[name]
            local = _mul(_translate(hx, hy, hz),
                         _mul(_rot(rx, ry, rz), _translate(-hx, -hy, -hz)))
        m = parent if local is identity else _mul(parent, local)
        done[name] = m
        return m
    for name in bones:
        matrix(name)
    return {n: m for n, m in done.items() if m is not identity}


def pose_points(pts, pose, macro) -> list:
    """*pts* (raw frame) skinned to *pose*: every vertex moves by its
    bones' matrices weighted by MakeHuman's skin weights (linear blend
    skinning)."""
    mats = bone_matrices(pose, macro)
    if not mats:
        return pts
    sk = skeleton()
    moved = [None] * len(pts)
    total = [0.0] * len(pts)
    for bone, rows in sk["weights"].items():
        m = mats.get(bone)
        for i, w in rows:
            if i >= len(pts):
                continue
            p = pts[i]
            if m is None:
                q = p
            else:
                q = (m[0][0] * p[0] + m[0][1] * p[1] + m[0][2] * p[2] + m[0][3],
                     m[1][0] * p[0] + m[1][1] * p[1] + m[1][2] * p[2] + m[1][3],
                     m[2][0] * p[0] + m[2][1] * p[1] + m[2][2] * p[2] + m[2][3])
            acc = moved[i]
            if acc is None:
                moved[i] = [q[0] * w, q[1] * w, q[2] * w]
            else:
                acc[0] += q[0] * w
                acc[1] += q[1] * w
                acc[2] += q[2] * w
            total[i] += w
    out = []
    for i, p in enumerate(pts):
        acc = moved[i]
        if acc is None or total[i] <= 1e-9:
            out.append(p)
        else:
            t = total[i]
            out.append((acc[0] / t, acc[1] / t, acc[2] / t))
    return out


# ------------------------------------------------------- landmarks

_LANDMARKS = None


def landmarks() -> dict:
    """name -> vertex index of the face landmarks on the base body."""
    global _LANDMARKS
    if _LANDMARKS is None:
        import json
        path = DATA / "landmarks.json"
        _LANDMARKS = json.load(open(path)) if path.is_file() else {}
    return _LANDMARKS


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


def points(gender=0.0, age=0.0, weight=0.0, height=0.0,
           stature=DEFAULT_STATURE, targets=None, warp=None,
           warp_radius=DEFAULT_WARP_RADIUS, pose=None) -> list:
    """The body's vertices (Z-up millimetres, standing on Z = 0,
    centred on X, *stature* tall): the macro blend, then the face
    *targets* (``[[slider, weight], ...]``), the *pose* (``[[bone, rx,
    ry, rz], ...]``, skinned), then the *warp* rows (``[x, y, z, dx,
    dy, dz]`` in this very frame) as a smooth field."""
    verts, faces, macro = _load()
    pts = [list(v) for v in verts]
    macro_weights = weights(gender, age, weight, height)
    adds = dict(macro_weights)
    for name, k in target_weights(targets).items():
        adds[name] = adds.get(name, 0.0) + k
    for name, k in adds.items():
        rows = macro.get(name)
        if rows is None:
            rows = face_target(name)
        for i, (dx, dy, dz) in rows.items():
            p = pts[i]
            p[0] += dx * k
            p[1] += dy * k
            p[2] += dz * k
    # MakeHuman: Y up, facing +Z, decimetres -> Z up, facing -Y, mm
    pts = [(p[0] * 100.0, -p[2] * 100.0, p[1] * 100.0) for p in pts]
    # stand, scale and centre from the REST pose, so a raised arm
    # changes nothing below it
    lo_z = min(p[2] for p in pts)
    hi_z = max(p[2] for p in pts)
    scale = float(stature) / (hi_z - lo_z) if hi_z > lo_z and stature \
        else 1.0
    cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2.0
    if pose:
        pts = pose_points(pts, pose, macro_weights)
    pts = [((p[0] - cx) * scale, p[1] * scale, (p[2] - lo_z) * scale)
           for p in pts]
    if warp:
        pts = rbf_warp(pts, warp, warp_radius)
    return pts


def landmark_points(**kw) -> dict:
    """name -> [x, y, z] of every landmark on the body built with the
    same arguments as points()."""
    pts = points(**kw)
    return {name: list(pts[i]) for name, i in landmarks().items()
            if 0 <= i < len(pts)}


def build(gender=0.0, age=0.0, weight=0.0, height=0.0,
          stature=DEFAULT_STATURE, targets=None, warp=None,
          warp_radius=DEFAULT_WARP_RADIUS, pose=None) -> list:
    """Triangles of the body (CCW, outward), Z-up millimetres, standing
    on Z = 0 and centred on X, *stature* mm tall."""
    _verts, faces, _macro = _load()
    pts = points(gender, age, weight, height, stature, targets, warp,
                 warp_radius, pose)
    tris = []
    for face in faces:
        ring = [pts[i] for i in face]
        for k in range(1, len(ring) - 1):
            tris.append((ring[0], ring[k], ring[k + 1]))
    return tris
