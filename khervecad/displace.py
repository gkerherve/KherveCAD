"""The `displace` wrapper (Qt-free): moves every vertex of its children
along its normal by a PATTERN — Blender's Displace modifier with a
texture, the thing that gives a creature real skin instead of random
bumps.

Patterns, each ``scale`` mm across, ``strength`` mm high:

* ``scales`` — round Voronoi plates with grooves between them (a
  lizard's belly, a snake's head, dragon hide);
* ``shingles`` — overlapping scales along ``axis``: each cell rises
  towards its back edge and drops at the next one (fish, pangolin,
  a dragon's back);
* ``cracks`` — thin deep grooves along the cell borders (dried mud,
  cracked hide, old stone);
* ``warts`` — sparse round bumps of mixed sizes (``density`` 0-1 of
  the cells carry one): toads, trolls, goblins;
* ``chitin`` — flat-topped plates with bevelled seams (insects,
  crustaceans, armoured beasts);
* ``ridges`` — sharp ridged fractal (wrinkled elephant skin, bark);
* ``noise`` — smooth fractal bumps (lumpy skin, a cast texture);
* ``image`` — a greyscale picture projected on an axis plane (white
  out, black in), placed like a reference image.

``midlevel`` is the pattern value that stays put (0 = everything
raises, 0.5 = half in, half out); ``within`` (two corners) keeps it to
a region, fading over a cell; ``detail`` refines the surface first to
that edge length (0 = an eighth of the scale, capped so the part stays
under MAX_TRIS). The mesh is welded once, so a closed solid stays
closed. Baked like the deformers (bakedkit): ``kcad_displace(...,
points, faces) { children }``.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import bakedkit

PATTERNS = ("scales", "shingles", "cracks", "warts", "chitin", "ridges",
            "noise", "image")
AXES = ("+x", "-x", "+y", "-y", "+z", "-z")
PLANES = ("Top (XY)", "Front (XZ)", "Side (YZ)")
#: the refinement is coarsened so a displaced part stays under this
MAX_TRIS = 400000


# ------------------------------------------------------------ the maths

def _hash3(ix, iy, iz, seed, k):
    """Repeatable pseudo-random values in [0, 1) per lattice cell."""
    import numpy as np
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) \
        ^ ((seed * 2654435761 + k * 40503) & 0xFFFFFFFF)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF).astype(np.float64) / float(0x1000000)


def voronoi(points, scale, seed=1):
    """``(f1, f2, cell_centre, cell_id)`` per point: the distances to
    the nearest and second-nearest feature points of a jittered grid
    ``scale`` mm across (in cells), the nearest one's position (mm)
    and a value in [0, 1) naming its cell."""
    import numpy as np
    q = points / scale
    base = np.floor(q).astype(np.int64)
    f1 = np.full(len(q), np.inf)
    f2 = np.full(len(q), np.inf)
    near = np.zeros_like(q)
    cid = np.zeros(len(q))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = base + np.array([dx, dy, dz])
                jit = np.stack([_hash3(c[:, 0], c[:, 1], c[:, 2], seed, k)
                                for k in range(3)], axis=1)
                feat = c + 0.1 + 0.8 * jit
                d = np.linalg.norm(q - feat, axis=1)
                closer = d < f1
                f2 = np.where(closer, f1, np.minimum(f2, d))
                near[closer] = feat[closer]
                cid = np.where(closer, _hash3(c[:, 0], c[:, 1], c[:, 2],
                                              seed, 7), cid)
                f1 = np.where(closer, d, f1)
    return f1, f2, near * scale, cid


def pattern(points, normals, params):
    """The pattern value (about 0..1) at every point."""
    import numpy as np
    from .sculpt import value_noise
    name = params["pattern"]
    scale = max(float(params["scale"]), 1e-6)
    seed = int(params["seed"])
    if name == "noise":
        return np.clip(value_noise(points, scale, seed, 4) * 0.8 + 0.5,
                       0.0, 1.0)
    if name == "ridges":
        n = value_noise(points, scale, seed, 4)
        return np.clip(1.0 - np.abs(n) * 2.2, 0.0, 1.0) ** 2
    if name == "image":
        return _image(points, params)
    f1, f2, centre, cid = voronoi(points, scale, seed)
    edge = f2 - f1                     # 0 on a border, ~0.5 mid-cell
    if name == "scales":
        dome = np.clip(1.0 - f1 * 1.1, 0.0, 1.0) ** 0.6
        groove = np.clip(edge / 0.12, 0.0, 1.0)
        return dome * groove
    if name == "cracks":
        return np.clip(edge / 0.06, 0.0, 1.0) ** 0.5
    if name == "chitin":
        return np.clip(edge / 0.18, 0.0, 1.0)
    if name == "warts":
        density = float(params.get("density", 0.35))
        # the surface is a slice through the 3D grid, so a feature point
        # is often well off it: the bumps reach most of a cell
        size = 0.5 + 0.4 * _hash3((cid * 1e6).astype(np.int64), 3, 5,
                                  seed, 11)
        has = cid < density
        bump = np.clip(1.0 - (f1 / size) ** 2, 0.0, 1.0)
        return np.where(has, np.sqrt(bump), 0.0)
    if name == "shingles":
        axis = _axis(params["axis"])
        # each scale rises from its front towards its back edge, then the
        # next one starts low: a sawtooth across the cell along the axis
        rel = (points - centre) / scale @ axis
        lift = np.clip(0.5 - rel * 1.2, 0.0, 1.0)
        rim = np.clip(edge / 0.08, 0.0, 1.0)
        return lift * (0.3 + 0.7 * rim)
    return np.zeros(len(points))


def _axis(name):
    import numpy as np
    v = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0),
         "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}.get(
             str(name), (0, 0, -1))
    return np.asarray(v, dtype=float)


def _image(points, params):
    import numpy as np
    from . import paint
    picture = paint.load(params.get("image", ""))
    if picture is None:
        return np.zeros(len(points))
    u, v, _n = paint.PLANES.get(params["plane"], paint.PLANES["Front (XZ)"])
    width = max(float(params["image_width"]), 1e-6)
    height = float(params["image_height"]) or width * picture.aspect
    s = (points[:, u] - float(params["image_x"])) / width
    t = (points[:, v] - float(params["image_y"])) / height
    rows = np.asarray(picture.rows, dtype=float)       # (H, W, 3)
    lum = (rows[..., 0] * 0.299 + rows[..., 1] * 0.587
           + rows[..., 2] * 0.114) / 255.0
    inside = (s >= 0) & (s <= 1) & (t >= 0) & (t <= 1)
    x = np.clip((s * picture.width).astype(int), 0, picture.width - 1)
    y = np.clip(((1.0 - t) * picture.height).astype(int), 0,
                picture.height - 1)
    return np.where(inside, lum[y, x], float(params["midlevel"]))


def _area(tris):
    import numpy as np
    t = np.asarray(tris, dtype=float).reshape(-1, 3, 3)
    return float(np.linalg.norm(np.cross(t[:, 1] - t[:, 0],
                                         t[:, 2] - t[:, 0]), axis=1).sum()
                 / 2.0)


def refine_edge(tris, scale, detail):
    """The edge length to refine to: *detail*, or an eighth of the scale,
    raised until the result stays under MAX_TRIS."""
    edge = float(detail) if detail > 0 else float(scale) / 8.0
    area = _area(tris)
    # an equilateral mesh of edge e has about area / (0.433 e^2) faces
    floor = math.sqrt(area / (0.433 * MAX_TRIS)) if area > 0 else 0.0
    return max(edge, floor)


def displace(tris, params):
    """The triangles of *tris* displaced by *params* (resolved)."""
    import numpy as np
    from . import deform, sculpt
    if not tris:
        return []
    within = params.get("within") or []
    region = within if len(within) == 2 else None
    edge = refine_edge(tris, params["scale"], params["detail"])
    src = deform.split_long_edges(tris, edge, region=region)
    fast = sculpt._Fast(src)
    if not len(fast.faces):
        return []
    v = fast.verts
    n = fast.normals()
    h = pattern(v, n, params) - float(params["midlevel"])
    if region is not None:
        lo = np.minimum(region[0], region[1])
        hi = np.maximum(region[0], region[1])
        fade = max(float(params["scale"]), 1e-6)
        out = np.maximum(np.maximum(lo - v, v - hi), 0.0).max(axis=1)
        inside = np.all((v >= lo - fade) & (v <= hi + fade), axis=1)
        w = np.clip(1.0 - out / fade, 0.0, 1.0)
        h = h * np.where(inside, w * w * (3.0 - 2.0 * w), 0.0)
    fast.verts = v + n * (h * float(params["strength"]))[:, None]
    return fast.triangles()


# ------------------------------------------------------------- the node

_DEFAULTS = dict(pattern="scales", strength=0.6, scale=4.0, seed=1,
                 midlevel=0.0, density=0.35, axis="-z", detail=0.0,
                 within=[], image="", plane="Front (XZ)", image_x=0.0,
                 image_y=0.0, image_width=100.0, image_height=0.0)


def _resolved(node, env):
    p = node.params
    out = {}
    for k, d in _DEFAULTS.items():
        if isinstance(d, str):
            out[k] = str(p.get(k, d))
        elif isinstance(d, list):
            out[k] = bakedkit.rows(node, env, k, 3)
        else:
            out[k] = bakedkit.num(node, env, k, d)
    return out


def _compute(node, env):
    return displace(bakedkit.source_tris(node, env), _resolved(node, env))


def _check(node, env):
    p = node.params
    if bakedkit.num(node, env, "scale", 4.0) <= 0:
        return "displace: the pattern size must be more than 0"
    within = p.get("within") or []
    if within and (len(within) != 2 or any(
            not isinstance(r, list) or len(r) != 3 for r in within)):
        return "displace: 'within' is two corners [x, y, z], or empty"
    if str(p.get("pattern")) == "image":
        from . import paint
        if not str(p.get("image", "")).strip():
            return "displace: pick the picture for the image pattern"
        if paint.load(p.get("image")) is None:
            return f"displace: cannot read the picture {p.get('image')}"
    return None


KIT = bakedkit.make(
    "displace", "Displace (scales, cracks, warts)", "mdi.texture",
    _DEFAULTS,
    [("pattern", "Pattern", "choice", list(PATTERNS), None),
     ("strength", "Height (mm, negative = in)", "float", -1e4, 1e4),
     ("scale", "Pattern size (mm)", "float", 0.01, 1e5),
     ("seed", "Seed", "int", 0, 1000000),
     ("midlevel", "Stays put at (0 = all raise, 0.5 = half in)", "float",
      0.0, 1.0),
     ("density", "Warts: share of cells with one (0-1)", "float", 0.0, 1.0),
     ("axis", "Shingles overlap towards", "choice", list(AXES), None),
     ("detail", "Refine to edge (mm, 0 = an eighth of the size)", "float",
      0.0, 1e4),
     ("within", "Only inside (two corners, mm)", "rows", ["X", "Y", "Z"],
      None),
     ("image", "Image: picture (white out, black in)", "str", None, None),
     ("plane", "Image: plane", "choice", list(PLANES), None),
     ("image_x", "Image: left edge (mm)", "float", -1e6, 1e6),
     ("image_y", "Image: bottom edge (mm)", "float", -1e6, 1e6),
     ("image_width", "Image: width (mm)", "float", 0.01, 1e6),
     ("image_height", "Image: height (mm, 0 = from aspect)", "float",
      0.0, 1e6)],
    _compute,
    choices={"pattern": PATTERNS, "axis": AXES, "plane": PLANES},
    text=("image",), check=_check)
