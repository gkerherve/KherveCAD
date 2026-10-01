"""The `weathering` wrapper (Qt-free): colours a surface by its age —
Blender's Dirty Vertex Colors, plus mottling, spots and tints.

A solid of one colour reads as plastic however finely it is shaped:
old skin, worn leather, a weathered statue, a rusty casting all show
their age in COLOUR as much as in form — dirt and shadow settle in the
creases, the crests rub pale, the surface is blotched and spotted.
This node gives every face of its children such a colour, worked out
from the geometry itself, so the sculpted wrinkles of a face darken by
themselves and its brow and knuckles catch the light:

* ``cavity`` — how far a face sits below the smoothed surface round it
  (``reach`` mm across), up to ``depth`` mm for the full
  ``cavity_color``: wrinkles, pores, seams, the inside of an ear;
* ``edge`` — the same above it, towards ``edge_color``: ridges, worn
  edges, the bridge of a nose;
* ``mottle`` — seeded fractal blotches ``mottle_scale`` mm across,
  towards ``mottle_color``: uneven skin, patina, stains;
* ``spots`` — a coverage 0..1 of sharp spots ``spot_size`` mm across in
  ``spot_color``: age spots, freckles, rust pits, lichen;
* ``tints`` rows ``[x, y, z, radius, r, g, b, strength]`` in the
  children's frame: a reddened eye rim, a darker nose tip, a sun-burnt
  ear — fading smoothly to nothing at the radius.

The base is each face's own colour (so a coloured part keeps its hue and
material), or ``base`` when it has none. Compiles to
``kcad_weathering(...) { children }`` whose helper renders the children
unchanged — OpenSCAD has no per-face colour; the preview, pictures and
exports to coloured formats have. Computed with numpy over the welded
mesh and cached by content, so a slider elsewhere does not redo it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import hashlib
import json

NODE_TYPES = {
    "weathering": dict(
        label="Weathering (age, dirt and wear)", category="operation",
        icon="mdi.texture-box",
        params=dict(base="", cavity_color="#2c3016", cavity=0.7,
                    edge_color="#d9d4a2", edge=0.3, depth=0.6, reach=3.0,
                    mottle_color="#5b6b30", mottle=0.25, mottle_scale=14.0,
                    spot_color="#5a4527", spots=0.0, spot_size=3.0,
                    seed=1, tints=[]),
        schema=[("base", "Base colour (empty = the part's own)", "color",
                 None, None),
                ("cavity_color", "Crease colour (dirt, shadow)", "color",
                 None, None),
                ("cavity", "Crease strength (0-1)", "float", 0.0, 1.0),
                ("edge_color", "Crest colour (wear, highlight)", "color",
                 None, None),
                ("edge", "Crest strength (0-1)", "float", 0.0, 1.0),
                ("depth", "Full colour at this depth (mm)", "float",
                 0.001, 1e4),
                ("reach", "Measured over (mm)", "float", 0.01, 1e4),
                ("mottle_color", "Blotch colour", "color", None, None),
                ("mottle", "Blotches (0-1)", "float", 0.0, 1.0),
                ("mottle_scale", "Blotch size (mm)", "float", 0.01, 1e5),
                ("spot_color", "Spot colour", "color", None, None),
                ("spots", "Spot coverage (0-1)", "float", 0.0, 1.0),
                ("spot_size", "Spot size (mm)", "float", 0.01, 1e5),
                ("seed", "Seed", "int", 0, 1000000),
                ("tints", "Tints (centre, radius, r g b 0-255, strength)",
                 "rows", ["X", "Y", "Z", "Radius", "R", "G", "B",
                          "Strength"], None)]),
}
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset()
WRAPPERS = frozenset(NODE_TYPES)
#: its faces carry their own colours: never cache it colourless
COLORED = frozenset(NODE_TYPES)
#: params the preview keeps as text (colours)
TEXT_PARAMS = frozenset({"base", "cavity_color", "edge_color",
                         "mottle_color", "spot_color"})
_COLOURS = ("base", "cavity_color", "edge_color", "mottle_color",
            "spot_color")
_NUMBERS = ("cavity", "edge", "depth", "reach", "mottle", "mottle_scale",
            "spots", "spot_size", "seed")
TINT_LEN = 8
#: most smoothing passes measuring the surface (each one edge ring)
MAX_PASSES = 80

HELPER = """\
module kcad_weathering(base = "", cavity_color = "#2c3016", cavity = 0.7,
                       edge_color = "#d9d4a2", edge = 0.3, depth = 0.6,
                       reach = 3, mottle_color = "#5b6b30", mottle = 0.25,
                       mottle_scale = 14, spot_color = "#5a4527",
                       spots = 0, spot_size = 3, seed = 1, tints = []) {
    // OpenSCAD has no per-face colour: the preview paints it
    children();
}"""


# ------------------------------------------------------------- colours

def _rgb(value, fallback=(128, 128, 128)):
    s = str(value or "").strip()
    if s.startswith("#") and len(s) == 7:
        try:
            return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            return fallback
    if s.startswith("#") and len(s) == 4:
        try:
            return tuple(int(c * 2, 16) for c in s[1:])
        except ValueError:
            return fallback
    if not s:
        return fallback
    try:                 # a named colour, read the way the preview reads it
        from PyQt5.QtGui import QColor
        q = QColor(s)
        if q.isValid():
            return (q.red(), q.green(), q.blue())
    except Exception:
        pass
    return fallback


def _valid_colour(value) -> bool:
    s = str(value or "").strip()
    if not s:
        return True
    return s.startswith("#") and len(s) in (4, 7) and all(
        c in "0123456789abcdefABCDEF" for c in s[1:])


# ------------------------------------------------------------- the maths

def measure(verts, faces, reach: float):
    """Signed depth (mm) of every vertex below the surface smoothed over
    *reach* mm — positive in a crease, negative on a crest — and the
    vertex normals. *verts* (V, 3) and *faces* (F, 3) numpy arrays."""
    import numpy as np
    v = verts
    n = np.cross(v[faces[:, 1]] - v[faces[:, 0]], v[faces[:, 2]] - v[faces[:, 0]])
    normals = np.zeros_like(v)
    for k in range(3):
        np.add.at(normals, faces[:, k], n)
    length = np.linalg.norm(normals, axis=1)
    length[length < 1e-12] = 1.0
    normals /= length[:, None]
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]],
                            faces[:, [2, 0]]])
    edges = np.unique(np.sort(edges, axis=1), axis=0)
    a, b = edges[:, 0], edges[:, 1]
    edge_len = float(np.linalg.norm(v[a] - v[b], axis=1).mean()) \
        if len(edges) else 1.0
    degree = np.maximum(np.bincount(edges.ravel(), minlength=len(v)), 1)
    # Laplacian smoothing spreads about one edge a pass, and a feature
    # w wide fades after (w / edge)^2 passes
    passes = int(min(max(round((reach / max(edge_len, 1e-9)) ** 2), 1),
                     MAX_PASSES))
    smooth = v.copy()
    for _ in range(passes):
        acc = np.zeros_like(smooth)
        np.add.at(acc, a, smooth[b])
        np.add.at(acc, b, smooth[a])
        smooth = 0.5 * smooth + 0.5 * acc / degree[:, None]
    depth = np.einsum("ij,ij->i", smooth - v, normals)
    # the part's own curvature shrinks a smoothed copy everywhere — a
    # whole head would read as one crest. Take away the depth's own
    # average over twice the reach: only what is SMALLER than the reach
    # (a wrinkle, a pore, a knuckle's crease, a vein) is left
    level = depth.copy()
    for _ in range(min(passes * 4, MAX_PASSES * 4)):
        acc = np.zeros_like(level)
        np.add.at(acc, a, level[b])
        np.add.at(acc, b, level[a])
        level = 0.5 * level + 0.5 * acc / degree
    return depth - level, normals


def weather(tris, colours, params) -> list:
    """Per-face colours ``(hex, alpha, material)`` for *tris* (whose own
    colours are *colours*, entries ``(colour, alpha[, material])`` or
    None), weathered by *params* (resolved)."""
    import numpy as np
    from .sculpt import value_noise
    if not tris:
        return []
    arr = np.asarray(tris, dtype=np.float64).reshape(-1, 3)
    uniq, inverse = np.unique(np.round(arr, 5), axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3)
    depth, _normals = measure(uniq, faces, float(params["reach"]))
    ref = max(float(params["depth"]), 1e-9)
    face_depth = depth[faces].mean(axis=1)
    centres = arr.reshape(-1, 3, 3).mean(axis=1)
    seed = int(params["seed"])
    base_default = _rgb(params.get("base") or "#808080")
    base = np.empty((len(tris), 3))
    cache = {}
    for i, c in enumerate(colours):
        key = c[0] if c else None
        rgb = cache.get(key)
        if rgb is None:
            rgb = cache[key] = (_rgb(params["base"]) if params.get("base")
                                else (_rgb(key, base_default) if key
                                      else base_default))
        base[i] = rgb
    out = base

    def mix(target, weight):
        nonlocal out
        w = np.clip(weight, 0.0, 1.0)[:, None]
        out = out * (1.0 - w) + np.asarray(target, dtype=float)[None, :] * w

    if params["mottle"] > 0:
        m = value_noise(centres, float(params["mottle_scale"]), seed, 3)
        mix(_rgb(params["mottle_color"]),
            params["mottle"] * np.clip(m * 1.4 + 0.5, 0.0, 1.0))
    if params["spots"] > 0:
        s = value_noise(centres, float(params["spot_size"]) * 1.6, seed + 7, 2)
        threshold = 1.0 - 2.0 * float(params["spots"])
        mix(_rgb(params["spot_color"]),
            np.clip((s - threshold) / 0.12, 0.0, 1.0) * 0.85)
    if params["edge"] > 0:
        mix(_rgb(params["edge_color"]),
            params["edge"] * np.clip(-face_depth / ref, 0.0, 1.0))
    if params["cavity"] > 0:
        mix(_rgb(params["cavity_color"]),
            params["cavity"] * np.clip(face_depth / ref, 0.0, 1.0) ** 0.8)
    for row in params.get("tints") or []:
        cx, cy, cz, radius, r, g, b, strength = row
        if radius <= 0:
            continue
        d = np.linalg.norm(centres - np.asarray([cx, cy, cz]), axis=1)
        t = np.clip(d / radius, 0.0, 1.0)
        mix((r, g, b), strength * (1.0 - t * t * (3.0 - 2.0 * t)))
    rgb = np.clip(np.rint(out), 0, 255).astype(int)
    result = []
    for (r, g, b), c in zip(rgb.tolist(), colours):
        alpha = c[1] if c else 1.0
        material = c[2] if c and len(c) > 2 else "Skin"
        result.append((f"#{r:02x}{g:02x}{b:02x}", alpha, material))
    return result


# ------------------------------------------------------------ contract

def preamble(root) -> list:
    if any(n.type in TYPES for n in root.walk()):
        return HELPER.split("\n")
    return []


def statement(node, fmt, fn) -> str:
    from .model import scad_str
    p = node.params
    defaults = NODE_TYPES["weathering"]["params"]
    parts = []
    for key in _COLOURS:
        parts.append(f"{key} = {scad_str(str(p.get(key, defaults[key])))}")
    for key in _NUMBERS:
        parts.append(f"{key} = {fmt(p.get(key, defaults[key]))}")
    rows = ", ".join("[" + ", ".join(fmt(v) for v in row) + "]"
                     for row in p.get("tints") or []
                     if isinstance(row, list))
    parts.append(f"tints = [{rows}]")
    return "kcad_weathering(" + ", ".join(parts) + ")"


def _text(value) -> str:
    value = str(value)
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _b_weathering(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    defaults = NODE_TYPES["weathering"]["params"]
    params = {}
    for key in _COLOURS:
        params[key] = _text(named.get(key, defaults[key]))
    for key in _NUMBERS:
        params[key] = _num(named.get(key, defaults[key]), defaults[key])
    params["seed"] = int(params["seed"])
    rows = named.get("tints")
    params["tints"] = [[_num(v) for v in row] for row in rows
                       if isinstance(row, list)] \
        if isinstance(rows, list) else []
    return CadNode("weathering", NODE_TYPES["weathering"]["label"], params)


BUILDERS = {"kcad_weathering": _b_weathering}


def check(node, env):
    from . import mesh
    p = node.params
    for key in _COLOURS:
        if not _valid_colour(p.get(key, "")):
            return f"weathering: {key} must be #rrggbb"
    try:
        r = mesh.rp(node, env)
    except Exception as exc:
        return f"weathering: {exc}"
    if r.get("depth", 1.0) <= 0 or r.get("reach", 1.0) <= 0:
        return "weathering: depth and reach must be more than 0"
    for number, row in enumerate(p.get("tints") or []):
        if not isinstance(row, list) or len(row) != TINT_LEN:
            return (f"tint {number} needs {TINT_LEN} values: x, y, z, "
                    "radius, r, g, b, strength")
    if not node.children:
        return "weathering: put the part to weather inside it"
    return None


#: weathered colours by content (the children's mesh + the params): an
#: unchanged part is a lookup, not a re-measure
_CACHE = {}
CACHE_SIZE = 8


def _resolved(node, env):
    from . import mesh
    p = mesh.rp(node, env)
    out = {key: node.params.get(key, NODE_TYPES["weathering"]["params"][key])
           for key in _COLOURS}
    for key in _NUMBERS:
        out[key] = float(p.get(key, NODE_TYPES["weathering"]["params"][key]))
    out["tints"] = [[mesh.rv(v, env) for v in row]
                    for row in node.params.get("tints") or []
                    if isinstance(row, list) and len(row) == TINT_LEN]
    return out


def tess(node, env, color, sel, selected):
    from . import mesh
    kids = mesh._children_mesh(node, env, color, sel, selected)
    if not kids:
        return kids
    try:
        import numpy as np
    except Exception:              # pragma: no cover - numpy is a dep
        return kids
    params = _resolved(node, env)
    h = hashlib.sha1(json.dumps(params, sort_keys=True).encode())
    h.update(np.asarray([t for t, _c, _s in kids], dtype=np.float64)
             .tobytes())
    h.update(repr([c for _t, c, _s in kids]).encode())
    key = h.hexdigest()
    painted = _CACHE.get(key)
    if painted is None:
        painted = weather([t for t, _c, _s in kids],
                          [c for _t, c, _s in kids], params)
        _CACHE[key] = painted
        while len(_CACHE) > CACHE_SIZE:
            _CACHE.pop(next(iter(_CACHE)))
    return [(tri, colour, s) for (tri, _c, s), colour in zip(kids, painted)]
