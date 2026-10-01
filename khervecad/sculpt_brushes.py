"""The creature brushes of the sculpt node — the ones that make horns,
tentacles, muscle and a bent neck (numpy, Qt-free).

* ``snake_hook`` pulls the patch under the brush along the direction,
  in short steps that each take what the last one moved, the radius
  narrowing as it goes — a horn, a tentacle, a spike, a tail pulled
  straight out of the surface. The stretched skin is refined afterwards
  (``split_long_edges`` round the pull) so later strokes have vertices
  to work with.
* ``draw`` raises the patch along its AVERAGE normal (Blender's Draw):
  ridges and masses that keep their direction over a curve.
* ``clay_strips`` lays a square slab of clay: everything under a plane
  ``strength`` mm above the patch is lifted towards it — muscle masses
  and folds built up in layers.
* ``layer`` raises the patch by an even ``strength`` mm with a flat top:
  a plate, a scale, a scute.
* ``elastic_grab`` drags with a Kelvinlet falloff — no hard edge, the
  whole body follows a little (Blender's Elastic Deform): a jaw pulled
  forward, a belly sagging.
* ``pose`` turns a limb about a joint: centre = the joint, direction =
  the rotation axis, strength = the angle (°), and the row's three extra
  values a point on the part that MOVES (the limb's tip). The limb is
  what is joined to the tip without crossing back past the joint, so
  the other arm on the same side stays put; ``radius`` mm either side
  of the joint bends smoothly.
* ``mask`` freezes the patch (strength 0..1; negative unfreezes): every
  later stroke is weighed by what is left unmasked.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

import numpy as np

KINDS = ("snake_hook", "draw", "clay_strips", "layer", "elastic_grab",
         "pose", "mask")
#: snake hook steps no longer than this share of the radius
SNAKE_STEP = 0.25
#: and the radius narrows by this much a step (a pointed horn)
SNAKE_TAPER = 0.985
#: the stretched skin is refined to edges this share of the radius
SNAKE_REFINE = 0.35


def _unit(v):
    v = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else None


def _smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return 1.0 - t * t * (3.0 - 2.0 * t)


def _free(mesh, idx):
    """What the mask leaves of each of *idx*'s vertices (1 = free)."""
    mask = getattr(mesh, "mask", None)
    return 1.0 if mask is None else 1.0 - mask[idx]


def _patch(mesh, centre, radius):
    vs = mesh.verts
    rel = vs - centre
    d2 = np.einsum("ij,ij->i", rel, rel)
    idx = np.nonzero(d2 < radius * radius)[0]
    return idx, np.sqrt(d2[idx]) / radius


def _area_normal(mesh, idx, w):
    n = _unit((mesh.normals()[idx] * w[:, None]).sum(axis=0))
    return n if n is not None else np.array([0.0, 0.0, 1.0])


def _tangents(n):
    ref = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 \
        else np.array([0.0, 1.0, 0.0])
    t1 = _unit(np.cross(n, ref))
    return t1, np.cross(n, t1)


def apply(mesh, name, centre, radius, strength, direction, extra=None):
    """One creature-brush stroke on the _Fast *mesh* (in place). Returns
    the mesh to carry on with — a snake hook refines it into a new one."""
    c = np.asarray(centre, dtype=np.float64)
    if radius <= 0.0 or (strength == 0.0 and name != "pose"):
        return mesh
    if mesh.stale:
        mesh.moved()
    if name == "mask":
        idx, t = _patch(mesh, c, radius)
        if len(idx):
            if getattr(mesh, "mask", None) is None:
                mesh.mask = np.zeros(len(mesh.verts))
            w = _smooth(t)
            mesh.mask[idx] = np.clip(mesh.mask[idx] + strength * w, 0.0, 1.0)
        return mesh
    if name == "snake_hook":
        return _snake_hook(mesh, c, radius, strength, direction)
    if name == "elastic_grab":
        _elastic(mesh, c, radius, strength, direction)
    elif name == "pose":
        _pose(mesh, c, radius, strength, direction, extra)
    else:
        idx, t = _patch(mesh, c, radius)
        if not len(idx):
            return mesh
        vs = mesh.verts
        if name == "draw":
            w = _smooth(t) * _free(mesh, idx)
            n = _area_normal(mesh, idx, w)
            vs[idx] += n[None, :] * (strength * w)[:, None]
        elif name == "layer":
            # flat top: full height over the inner 60 %, smooth to the rim
            w = np.where(t < 0.6, 1.0, _smooth((t - 0.6) / 0.4)) \
                * _free(mesh, idx)
            vs[idx] += mesh.normals()[idx] * (strength * w)[:, None]
        elif name == "clay_strips":
            w0 = _smooth(t)
            n = _area_normal(mesh, idx, w0)
            cen = (vs[idx] * w0[:, None]).sum(axis=0) / max(w0.sum(), 1e-12)
            t1, t2 = _tangents(n)
            rel = vs[idx] - c
            # a square brush: Chebyshev distance in the patch's plane
            sq = np.maximum(np.abs(rel @ t1), np.abs(rel @ t2)) / radius
            w = _smooth((sq - 0.5) / 0.5) * _free(mesh, idx)
            plane = cen + n * strength
            h = (plane - vs[idx]) @ n
            lift = np.where(strength >= 0, np.maximum(h, 0.0),
                            np.minimum(h, 0.0))
            vs[idx] += n[None, :] * (lift * 0.6 * w)[:, None]
        else:
            return mesh
    mesh.moved()
    return mesh


def _elastic(mesh, c, radius, strength, direction):
    u = _unit(direction)
    vs = mesh.verts
    rel = vs - c
    r2 = np.einsum("ij,ij->i", rel, rel)
    # regularised Kelvinlet: 1 at the centre, ~ (R / r)^3 far away
    w = (1.0 + r2 / (radius * radius)) ** -1.5
    w = w * _free(mesh, np.arange(len(vs)))
    if u is None:
        near = np.nonzero(r2 < radius * radius)[0]
        if not len(near):
            return
        u = _area_normal(mesh, near, w[near])
    vs += u[None, :] * (strength * w)[:, None]


def _snake_hook(mesh, c, radius, strength, direction):
    from . import deform, sculpt
    d = np.asarray(direction, dtype=np.float64)
    length = float(np.linalg.norm(d))
    if length < 1e-9:                    # no direction: out of the surface
        idx, t = _patch(mesh, c, radius)
        if not len(idx):
            return mesh
        d = _area_normal(mesh, idx, _smooth(t)) * abs(strength)
        length = abs(strength)
    else:
        d = d * abs(strength)            # strength scales the pull
        length *= abs(strength)
        if length < 1e-9:
            return mesh
    u = d / length
    steps = max(1, int(math.ceil(length / (radius * SNAKE_STEP))))
    step = d / steps
    centre, r = c.copy(), radius
    lo, hi = c - radius, c + radius
    for _ in range(steps):
        vs = mesh.verts
        idx, t = _patch(mesh, centre, r)
        if len(idx):
            w = _smooth(t) * _free(mesh, idx)
            vs[idx] += step[None, :] * w[:, None]
            # draw the moved patch a little towards the pull's axis, so
            # the hook narrows to a point instead of ballooning
            rel = vs[idx] - centre - step
            radial = rel - np.outer(rel @ u, u)
            vs[idx] -= radial * (0.08 * w)[:, None]
        centre = centre + step
        r *= SNAKE_TAPER
        lo, hi = np.minimum(lo, centre - r), np.maximum(hi, centre + r)
    mesh.moved()
    # the pulled skin is long thin triangles: refine round the pull
    tris = mesh.triangles()
    region = [list(lo - radius), list(hi + radius)]
    refined = deform.split_long_edges(tris, radius * SNAKE_REFINE,
                                      region=region)
    if len(refined) == len(tris):
        return mesh
    out = sculpt._Fast(refined)
    old = getattr(mesh, "mask", None)
    if old is not None:                  # keep the mask where it was
        keys = {tuple(k): m for k, m in zip(np.round(mesh.verts, 6).tolist(),
                                             old.tolist())}
        out.mask = np.array([keys.get(tuple(k), 0.0) for k in
                             np.round(out.verts, 6).tolist()])
    return out


def _adjacency(mesh):
    e = mesh.edges
    n = len(mesh.verts)
    both = np.concatenate([e, e[:, ::-1]])
    order = np.argsort(both[:, 0], kind="stable")
    both = both[order]
    indptr = np.zeros(n + 1, dtype=np.int64)
    np.add.at(indptr, both[:, 0] + 1, 1)
    return np.cumsum(indptr), both[:, 1]


def connected(mesh, seed: int, allowed):
    """The vertices joined to *seed* through *allowed* ones (bool array)."""
    indptr, indices = _adjacency(mesh)
    seen = np.zeros(len(mesh.verts), dtype=bool)
    if not allowed[seed]:
        return seen
    seen[seed] = True
    frontier = np.array([seed])
    while len(frontier):
        starts = indptr[frontier]
        counts = indptr[frontier + 1] - starts
        total = int(counts.sum())
        if not total:
            break
        offs = np.repeat(starts - np.cumsum(counts) + counts, counts) \
            + np.arange(total)
        nb = np.unique(indices[offs])
        nb = nb[allowed[nb] & ~seen[nb]]
        seen[nb] = True
        frontier = nb
    return seen


def _rotation(axis, angles):
    """Rodrigues matrices (N, 3, 3) for one unit *axis* and N angles (rad)."""
    x, y, z = axis
    k = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])
    s, c = np.sin(angles), np.cos(angles)
    eye = np.eye(3)[None]
    return eye + s[:, None, None] * k[None] \
        + (1.0 - c)[:, None, None] * (k @ k)[None]


def _pose(mesh, pivot, radius, angle, axis, tip):
    if tip is None:
        return
    vs = mesh.verts
    tip = np.asarray(tip, dtype=np.float64)
    u = _unit(tip - pivot)
    if u is None:
        return
    a = _unit(axis)
    if a is None:                        # no axis: swing it upward
        a = _unit(np.cross(u, [0.0, 0.0, 1.0]))
        if a is None:
            a = np.array([1.0, 0.0, 0.0])
    s = (vs - pivot) @ u
    allowed = s > -radius
    seed = int(np.argmin(np.einsum("ij,ij->i", vs - tip, vs - tip)))
    limb = connected(mesh, seed, allowed)
    idx = np.nonzero(limb)[0]
    if not len(idx):
        return
    w = 1.0 - _smooth((s[idx] + radius) / (2.0 * radius))
    w = w * _free(mesh, idx)
    rot = _rotation(a, np.radians(angle) * w)
    rel = vs[idx] - pivot
    vs[idx] = pivot + np.einsum("nij,nj->ni", rot, rel)
