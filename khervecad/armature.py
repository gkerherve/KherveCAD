"""The `armature` wrapper (Qt-free): bones for ANY mesh, with automatic
weights — Blender's Armature modifier with "With Automatic Weights".

Joints turn rigid pieces; a blended or sculpted monster is one skin and
must BEND at the elbow. An armature holds:

* ``bones`` rows ``[name, parent, hx, hy, hz, tx, ty, tz]`` — each bone
  from its head to its tail in the children's frame, ``parent`` the name
  of the bone it hangs from ("" for a root);
* ``pose`` rows ``[bone, rx, ry, rz]`` — degrees about the bone's head
  in the part's own axes (rotate([x, y, z]) order), carried down to
  every bone below it, exactly like the human figure's rig.

Weights are automatic: each vertex is bound to the bones nearest it
(inverse distance to the bone SEGMENT to the power ``falloff``, the four
strongest kept), then the weights are relaxed over the mesh ``smooth``
times so a joint bends as a smooth sleeve, not a crease. A vertex is
moved by linear blend skinning. ``detail`` refines the surface first
(long triangles bend badly). Baked through bakedkit: ``kcad_armature(
bones = [...], pose = [...], ..., points, faces) { children }``.

ArmatureRig gives ik.reach a chain of these bones, and the PlanetCraft
export reads the bone names (planetcraft.role_of) to cut a rigged body
into walking parts.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import bakedkit

BONE_LEN = 8
POSE_LEN = 4
#: strongest bones kept per vertex
INFLUENCES = 4


# ------------------------------------------------------------ the bones

def parse_bones(rows):
    """{name: (parent, head, tail)} in order, from bone rows (resolved).
    A parent that is not a bone becomes a root."""
    bones = {}
    for row in rows:
        if not isinstance(row, list) or len(row) != BONE_LEN:
            continue
        name = str(row[0]).strip()
        if not name:
            continue
        try:
            head = [float(v) for v in row[2:5]]
            tail = [float(v) for v in row[5:8]]
        except (TypeError, ValueError):
            continue
        bones[name] = (str(row[1]).strip(), head, tail)
    return {n: ((p if p in bones and p != n else ""), h, t)
            for n, (p, h, t) in bones.items()}


def parse_pose(rows):
    out = {}
    for row in rows or []:
        if not isinstance(row, list) or len(row) != POSE_LEN:
            continue
        try:
            a = [float(v) for v in row[1:4]]
        except (TypeError, ValueError):
            continue
        out[str(row[0]).strip()] = a
    return out


def euler(rx, ry, rz):
    """rotate([rx, ry, rz]) as a 3x3 matrix: Rz · Ry · Rx."""
    cx, sx = math.cos(math.radians(rx)), math.sin(math.radians(rx))
    cy, sy = math.cos(math.radians(ry)), math.sin(math.radians(ry))
    cz, sz = math.cos(math.radians(rz)), math.sin(math.radians(rz))
    return [[cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
            [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
            [-sy, cy * sx, cy * cx]]


def _mul4(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)]
            for r in range(4)]


def bone_matrices(bones, pose):
    """bone -> 4x4 matrix moving the rest skin to the posed one: the
    parent's matrix times a turn about this bone's REST head."""
    done = {}
    eye = [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]

    def matrix(name, depth=0):
        if name in done:
            return done[name]
        parent, head, _tail = bones[name]
        m = matrix(parent, depth + 1) if parent and depth < 256 else eye
        a = pose.get(name)
        if a and any(a):
            r = euler(*a)
            hx, hy, hz = head
            turn = [[r[0][0], r[0][1], r[0][2], 0.0],
                    [r[1][0], r[1][1], r[1][2], 0.0],
                    [r[2][0], r[2][1], r[2][2], 0.0],
                    [0.0, 0.0, 0.0, 1.0]]
            to = [[1, 0, 0, hx], [0, 1, 0, hy], [0, 0, 1, hz], [0, 0, 0, 1]]
            back = [[1, 0, 0, -hx], [0, 1, 0, -hy], [0, 0, 1, -hz],
                    [0, 0, 0, 1]]
            m = _mul4(m, _mul4(to, _mul4(turn, back)))
        done[name] = m
        return m
    return {name: matrix(name) for name in bones}


def segment_distance(points, head, tail):
    """Distance from each of the (N, 3) *points* to the segment."""
    import numpy as np
    a = np.asarray(head, dtype=float)
    d = np.asarray(tail, dtype=float) - a
    ll = float(d @ d)
    rel = points - a
    t = np.clip(rel @ d / ll, 0.0, 1.0) if ll > 1e-18 else \
        np.zeros(len(points))
    return np.linalg.norm(rel - t[:, None] * d, axis=1)


def auto_weights(verts, edges, bones, falloff=4.0, smooth=3):
    """(N, B) weights, rows summing to 1, for the welded vertices."""
    import numpy as np
    names = list(bones)
    if not names:
        return np.zeros((len(verts), 0)), names
    dist = np.stack([segment_distance(verts, h, t)
                     for _p, h, t in bones.values()], axis=1)
    near = dist.min(axis=1, keepdims=True)
    # relative to the nearest bone: scale free, and the nearest is 1
    w = ((near + 1e-6) / (dist + 1e-6)) ** float(falloff)
    if w.shape[1] > INFLUENCES:
        cut = np.partition(w, -INFLUENCES, axis=1)[:, -INFLUENCES][:, None]
        w = np.where(w >= cut, w, 0.0)
    w /= w.sum(axis=1, keepdims=True)
    if smooth > 0 and len(edges):
        a, b = edges[:, 0], edges[:, 1]
        deg = np.maximum(np.bincount(edges.ravel(), minlength=len(verts)),
                         1)[:, None]
        for _ in range(int(smooth)):
            acc = np.zeros_like(w)
            np.add.at(acc, a, w[b])
            np.add.at(acc, b, w[a])
            w = 0.5 * w + 0.5 * acc / deg
        w /= np.maximum(w.sum(axis=1, keepdims=True), 1e-12)
    return w, names


def skin(tris, bones, pose, falloff=4.0, smooth=3, detail=0.0):
    """The triangles of *tris* posed by the armature."""
    return skin_parts(tris, bones, pose, falloff, smooth, detail)[0]


def skin_parts(tris, bones, pose, falloff=4.0, smooth=3, detail=0.0):
    """``(posed triangles, bone per triangle)`` — the bone with the most
    weight on the triangle's corners (None without bones)."""
    import numpy as np
    from . import deform, sculpt
    if not tris:
        return [], []
    if detail > 0:
        tris = deform.split_long_edges(tris, detail)
    if not bones:
        return [tuple(t) for t in tris], [None] * len(tris)
    fast = sculpt._Fast(tris)
    w, names = auto_weights(fast.verts, fast.edges, bones, falloff, smooth)
    owner = [names[k] for k in
             w[fast.faces].sum(axis=1).argmax(axis=1).tolist()]
    if not any(any(a) for a in pose.values()):
        return fast.triangles(), owner
    mats = bone_matrices(bones, pose)
    v = fast.verts
    out = np.zeros_like(v)
    for k, name in enumerate(names):
        m = np.asarray(mats[name], dtype=float)
        col = w[:, k]
        if not col.any():
            continue
        out += col[:, None] * (v @ m[:3, :3].T + m[:3, 3])
    fast.verts = out
    return fast.triangles(), owner


def node_parts(node, env=None):
    """``(posed triangles, bone per triangle)`` of an armature node in
    its own frame, as the preview tessellates its children."""
    env = env or {}
    bones = parse_bones(bakedkit.rows(node, env, "bones", BONE_LEN,
                                      (0, 1)))
    pose = parse_pose(bakedkit.rows(node, env, "pose", POSE_LEN, (0,)))
    return skin_parts(bakedkit.source_tris(node, env), bones, pose,
                      bakedkit.num(node, env, "falloff", 4.0),
                      int(bakedkit.num(node, env, "smooth", 3)),
                      bakedkit.num(node, env, "detail", 0.0))


def bones_from_skin(nodes):
    """Bone rows from a skin node's skeleton (rows [x, y, z, radius,
    parent]): one bone from each node's parent to it, named after its
    index (``b3``), parented to the bone ending where it starts."""
    rows = []
    for i, row in enumerate(nodes):
        p = int(row[4]) if len(row) > 4 else -1
        if not 0 <= p < len(nodes) or p == i:
            continue
        pp = int(nodes[p][4]) if len(nodes[p]) > 4 else -1
        parent = f"b{p}" if 0 <= pp < len(nodes) and pp != p else ""
        rows.append([f"b{i}", parent] + [float(v) for v in nodes[p][:3]]
                    + [float(v) for v in row[:3]])
    return rows


# ------------------------------------------------------------- IK rig

class ArmatureRig:
    """A chain of an armature's bones for ik.solve: the effector is the
    TAIL of *effector* (a bone name), turned by *chain* bones up the
    hierarchy (default: it and its two parents)."""

    def __init__(self, node, effector, chain=None, env=None):
        from .mesh import ancestor_matrix
        self.node = node
        self.env = env or {}
        self.bones = parse_bones(bakedkit.rows(node, self.env, "bones",
                                               BONE_LEN, (0, 1)))
        if effector not in self.bones:
            raise ValueError(f"No bone {effector!r}: the armature has "
                             f"{', '.join(self.bones) or 'none'}")
        self.effector_bone = effector
        if isinstance(chain, (list, tuple)):
            self.chain = [str(b) for b in chain]
        else:
            count = int(chain or 3)
            self.chain, b = [], effector
            while b and len(self.chain) < count:
                self.chain.insert(0, b)
                b = self.bones[b][0]
        for b in self.chain:
            if b not in self.bones:
                raise ValueError(f"No bone named {b!r}")
        self.rows = parse_pose(node.params.get("pose"))
        self.world = ancestor_matrix(node, self.env)

    def angles(self):
        return {b: list(self.rows.get(b, [0.0, 0.0, 0.0]))
                for b in self.chain}

    def limits(self, name):
        return (-170.0, 170.0)

    def forward(self, angles):
        from .ik import _linear, _mm
        from .mesh import mat_apply
        pose = dict(self.rows)
        pose.update(angles)
        mats = bone_matrices(self.bones, pose)
        wlin = _linear(self.world)
        pivots, frames = {}, {}
        for b in self.chain:
            parent, head, _tail = self.bones[b]
            pivots[b] = mat_apply(self.world, mat_apply(mats[b], head))
            frames[b] = _mm(wlin, _linear(mats[parent])) if parent else wlin
        tail = self.bones[self.effector_bone][2]
        effector = mat_apply(self.world,
                             mat_apply(mats[self.effector_bone], tail))
        return {"pivots": pivots, "frames": frames, "effector": effector}

    def length(self, state):
        pts = [state["pivots"][b] for b in self.chain] + [state["effector"]]
        return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))

    def pose_rows(self, angles):
        rows = dict(self.rows)
        rows.update({b: [round(v, 3) for v in a] for b, a in angles.items()})
        return [[b] + a for b, a in rows.items() if any(a)]


def armature_in(node):
    return next((n for n in node.walk() if n.type == "armature"), None)


# ------------------------------------------------------------- the node

def _compute(node, env):
    bones = parse_bones(bakedkit.rows(node, env, "bones", BONE_LEN,
                                      (0, 1)))
    pose = parse_pose(bakedkit.rows(node, env, "pose", POSE_LEN, (0,)))
    return skin(bakedkit.source_tris(node, env), bones, pose,
                bakedkit.num(node, env, "falloff", 4.0),
                int(bakedkit.num(node, env, "smooth", 3)),
                bakedkit.num(node, env, "detail", 0.0))


def _check(node, env):
    rows = node.params.get("bones") or []
    if not rows:
        return ("armature: give it bones — rows [name, parent, head x, y, "
                "z, tail x, y, z]")
    names = set()
    for k, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != BONE_LEN:
            return (f"bone {k} needs {BONE_LEN} values: name, parent, head "
                    "x, y, z, tail x, y, z")
        name = str(row[0]).strip()
        if not name:
            return f"bone {k} needs a name"
        if name in names:
            return f"two bones are called {name!r}"
        names.add(name)
    bones = parse_bones(bakedkit.rows(node, env, "bones", BONE_LEN,
                                      (0, 1)))
    for name in bones:                         # no loops in the hierarchy
        seen, b = set(), name
        while b:
            if b in seen:
                return f"bone {name!r} is its own ancestor"
            seen.add(b)
            b = bones[b][0]
    for k, row in enumerate(node.params.get("pose") or []):
        if not isinstance(row, list) or len(row) != POSE_LEN:
            return f"pose row {k} is [bone, rx, ry, rz]"
        if str(row[0]).strip() not in names:
            return f"pose row {k}: no bone called {row[0]!r}"
    return None


KIT = bakedkit.make(
    "armature", "Armature (bones, auto weights)", "mdi.bone",
    dict(bones=[], pose=[], falloff=4.0, smooth=3, detail=0.0),
    [("bones", "Bones (name, parent, head, tail — mm)", "rows",
      ["Name", "Parent", "Head X", "Head Y", "Head Z", "Tail X", "Tail Y",
       "Tail Z"], None),
     ("pose", "Pose (bone, rx, ry, rz °)", "rows",
      ["Bone", "rX", "rY", "rZ"], None),
     ("falloff", "Weight falloff (higher = stiffer)", "float", 0.5, 32.0),
     ("smooth", "Weight smoothing passes", "int", 0, 200),
     ("detail", "Refine to edge first (mm, 0 = as is)", "float", 0.0, 1e4)],
    _compute, names={"bones": {0, 1}, "pose": {0}}, check=_check)
