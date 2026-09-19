"""Voxel remesh — any mesh as one clean closed solid (Blender's Remesh).

A union of overlapping pieces, an imported scan with inner walls, a
sculpt that folded, a soup no boolean will take: the `remesh` wrapper
rebuilds its children as ONE watertight surface of even triangles, the
way Blender's voxel Remesh does, so it prints, bevels, shrinkwraps and
cuts again.

1. **Inside** is decided per voxel by the WINDING NUMBER along a ray up
   each grid column (every face the ray crosses counts +1 going in, -1
   coming out, from the sign of its normal) — overlapping solids union,
   inner walls cancel out, a small hole in a scan does not flood it.
2. The occupancy is averaged over each 2 x 2 x 2 block of voxels and
   meshed at the half level by marching tetrahedra (sdf.mesh_values),
   which is watertight by construction.
3. With ``snap`` every new vertex is moved to the nearest point of the
   original surface (shrinkwrap.Target), so the result keeps the
   original's size and shape to within the voxel, not a staircase.

``voxel`` is the cell size in mm; a grid past `MAX_CELLS` coarsens
itself. Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import numpy as np

#: a grid never has more samples than this (the voxel grows instead)
MAX_CELLS = 2_500_000


def occupancy(tris, lo, cell, dims):
    """Boolean (nx, ny, nz) grid: sample centre inside by winding."""
    nx, ny, nz = dims
    t = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    a, b, c = t[:, 0], t[:, 1], t[:, 2]
    nzc = ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1])
           - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0]))   # 2 x signed area
    keep = np.abs(nzc) > 1e-15
    a, b, c, nzc = a[keep], b[keep], c[keep], nzc[keep]
    xy_lo = np.minimum(np.minimum(a, b), c)[:, :2]
    xy_hi = np.maximum(np.maximum(a, b), c)[:, :2]
    # sample columns at cell centres: x_i = lo + (i + 0.5) * cell
    i0 = np.clip(np.ceil((xy_lo[:, 0] - lo[0]) / cell - 0.5), 0, nx)
    i1 = np.clip(np.floor((xy_hi[:, 0] - lo[0]) / cell - 0.5), -1, nx - 1)
    j0 = np.clip(np.ceil((xy_lo[:, 1] - lo[1]) / cell - 0.5), 0, ny)
    j1 = np.clip(np.floor((xy_hi[:, 1] - lo[1]) / cell - 0.5), -1, ny - 1)
    ni = (i1 - i0 + 1).astype(np.int64)
    nj = (j1 - j0 + 1).astype(np.int64)
    ok = (ni > 0) & (nj > 0)
    delta = np.zeros((nx, ny, nz + 1), dtype=np.int32)
    idx = np.nonzero(ok)[0]
    # expand (triangle, column) pairs in chunks to bound memory
    chunk = 20000
    for s in range(0, len(idx), chunk):
        tid = idx[s:s + chunk]
        cnt = ni[tid] * nj[tid]
        rep = np.repeat(tid, cnt)
        start = np.repeat(np.cumsum(cnt) - cnt, cnt)
        k = np.arange(len(rep)) - start
        ii = (i0[rep] + k % ni[rep]).astype(np.int64)
        jj = (j0[rep] + k // ni[rep]).astype(np.int64)
        px = lo[0] + (ii + 0.5) * cell
        py = lo[1] + (jj + 0.5) * cell
        A, B, C = a[rep], b[rep], c[rep]
        d = nzc[rep]
        # barycentric in the xy projection (half-open edges: a ray on
        # a shared edge counts once)
        w0 = ((B[:, 0] - px) * (C[:, 1] - py)
              - (B[:, 1] - py) * (C[:, 0] - px)) / d
        w1 = ((C[:, 0] - px) * (A[:, 1] - py)
              - (C[:, 1] - py) * (A[:, 0] - px)) / d
        w2 = 1.0 - w0 - w1
        eps = 1e-12
        hit = (w0 >= -eps) & (w1 >= -eps) & (w2 > eps)
        hit &= ~((w0 < eps) & (w1 < eps))
        if not hit.any():
            continue
        z = (w0 * A[:, 2] + w1 * B[:, 2] + w2 * C[:, 2])[hit]
        sign = np.where(d[hit] > 0, -1, 1)       # up-facing = leaving
        kz = np.clip(np.ceil((z - lo[2]) / cell - 0.5), 0, nz).astype(
            np.int64)
        np.add.at(delta, (ii[hit], jj[hit], kz), sign)
    wind = np.cumsum(delta, axis=2)[:, :, :nz]
    return wind > 0


def remesh(tris, voxel=1.0, snap=True):
    """*tris* rebuilt as one closed surface at *voxel* mm."""
    from . import sdf
    tris = list(tris)
    if not tris:
        return []
    pts = np.asarray(tris, dtype=np.float64).reshape(-1, 3)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    cell = max(float(voxel), 1e-6)
    while True:
        dims = tuple(int(np.ceil((hi[i] - lo[i]) / cell)) + 4
                     for i in range(3))
        if dims[0] * dims[1] * dims[2] <= MAX_CELLS:
            break
        cell *= 1.25
    origin = lo - 2 * cell
    occ = occupancy(tris, origin, cell, dims).astype(np.float64)
    if not occ.any():
        return []
    # corner samples = mean of the 8 voxels round each lattice point
    pad = np.pad(occ, 1)
    corner = (pad[:-1, :-1, :-1] + pad[1:, :-1, :-1] + pad[:-1, 1:, :-1]
              + pad[:-1, :-1, 1:] + pad[1:, 1:, :-1] + pad[1:, :-1, 1:]
              + pad[:-1, 1:, 1:] + pad[1:, 1:, 1:]) / 8.0
    vals = 0.5 - corner
    vals[vals == 0.0] = 1e-9
    xs = [origin[0] + i * cell for i in range(dims[0] + 1)]
    ys = [origin[1] + j * cell for j in range(dims[1] + 1)]
    zs = [origin[2] + k * cell for k in range(dims[2] + 1)]
    flat = vals.transpose(2, 1, 0).ravel().tolist()     # x fastest
    out = sdf.mesh_values(flat, xs, ys, zs)
    if snap and out:
        out = _snap(out, tris, cell)
    return out


def _snap(out, tris, cell):
    """Every vertex onto the original surface, never farther than a
    cell (a stray vertex over a gap stays where the voxels put it)."""
    from .decimate import triangles, weld
    from .shrinkwrap import Target
    points, faces = weld(out)
    p = np.asarray(points)
    q, _t = Target(tris).nearest(p)
    d = np.linalg.norm(q - p, axis=1)
    near = d <= 1.5 * cell
    p[near] = q[near]
    moved = triangles([tuple(v) for v in p.tolist()], faces)
    # snapping can squash a triangle flat; drop the degenerate ones
    keep = []
    for tri in moved:
        a, b, c = (np.asarray(v) for v in tri)
        if np.linalg.norm(np.cross(b - a, c - a)) > 1e-12:
            keep.append(tri)
    return keep
