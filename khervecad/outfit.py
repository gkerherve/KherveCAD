"""The `outfit` wrapper (Qt-free): clothes a `human` figure by BODY PART.

Every face of the figure inside it takes the colour of the garment
covering the body part under it — the part being where MakeHuman's skin
weights put the nearest vertex (its dominant bone, grouped into parts:
chest, waist, hips, upper arm, forearm, hand, thigh, shin, foot...). So
a sleeve stays on the arm and a trouser leg on the leg in ANY pose,
which a picture projected from the front cannot do, and a sculpted body
(the face positions move a little) still finds its parts.

``garments`` rows are ``[part, colour, material]``, applied in order (a
later row wins), a part optionally ending in ``.L`` / ``.R`` for one
side only; ``skin`` colours every part no row covers. That is ALL a
garment is, so an assistant can dress a figure in anything: a vest is
chest + waist, a glove is hand, a sock is ankle + foot. Loose clothes
(a skirt, a coat's tails, a hat) are ordinary solids beside the body
(`human_design` builds them).

Compiles to ``kcad_outfit(skin = "...", garments = [...]) { children }``
whose helper renders the children unchanged (OpenSCAD has no per-face
colour); the importer rebuilds the node from it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

NODE_TYPES = {
    "outfit": dict(
        label="Outfit (clothes by body part)", category="operation",
        icon="mdi.tshirt-crew-outline",
        params=dict(skin="#e0ac8a", garments=[]),
        schema=[("skin", "Skin colour", "color", None, None),
                ("garments", "Garments (part, colour, material)", "rows",
                 ["Part", "Colour", "Material"], None)]),
}
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset()
WRAPPERS = frozenset(NODE_TYPES)
#: the outfit's faces carry their own colours: never cache it colourless
COLORED = frozenset(NODE_TYPES)

_FACE = ("head", "jaw", "eye", "oculi", "orbicularis", "levator",
         "risorius", "oris", "temporalis", "tongue", "special")
#: body part -> the bone-name prefixes whose vertices it holds (sides
#: ".L" / ".R" come with the bone)
PARTS = {
    "head": _FACE,
    "neck": ("neck",),
    "chest": ("spine01", "spine02", "clavicle", "shoulder01", "breast"),
    "waist": ("spine03", "spine04"),
    "hips": ("spine05", "pelvis", "root"),
    "shoulder": ("upperarm01",),
    "upper_arm": ("upperarm02",),
    "forearm": ("lowerarm01", "lowerarm02"),
    "hand": ("wrist", "metacarpal", "finger"),
    "upper_thigh": ("upperleg01",),
    "thigh": ("upperleg02",),
    "shin": ("lowerleg01",),
    "ankle": ("lowerleg02",),
    "foot": ("foot", "toe"),
}
#: what a part name in a garment row may also say: groups of parts
GROUPS = {
    "torso": ("chest", "waist"),
    "arm": ("shoulder", "upper_arm", "forearm"),
    "leg": ("upper_thigh", "thigh", "shin", "ankle"),
    "body": ("chest", "waist", "hips"),
    "all": tuple(PARTS),
}
MATERIALS = ("Default", "Plastic", "Matte", "Metal", "Rubber", "Glass",
             "Gold", "Emissive")

HELPER = """\
module kcad_outfit(skin = "#e0ac8a", garments = []) {
    children();
}"""


def part_of_bone(bone: str) -> str:
    """The body part a bone belongs to, side included ("forearm.L")."""
    name, side = bone, ""
    if bone.endswith((".L", ".R")):
        name, side = bone[:-2], bone[-2:]
    for part, prefixes in PARTS.items():
        if name.startswith(prefixes):
            return part + side
    return "chest" + side


def expand(part: str) -> list:
    """Every concrete part (with side) a garment row's *part* covers."""
    part = str(part).strip()
    side = ""
    if part.endswith((".L", ".R")):
        part, side = part[:-2], part[-2:]
    names = GROUPS.get(part, (part,) if part in PARTS else ())
    sides = (side,) if side else ("", ".L", ".R")
    return [n + s for n in names for s in sides]


def known(part: str) -> bool:
    return bool(expand(part))


_VERTEX_PARTS = None


def vertex_parts() -> list:
    """The body part of every vertex of the base mesh (its heaviest
    bone)."""
    global _VERTEX_PARTS
    if _VERTEX_PARTS is None:
        from . import human
        best = {}
        for bone, rows in human.skeleton()["weights"].items():
            for i, w in rows:
                if w > best.get(i, (0.0, ""))[0]:
                    best[i] = (w, bone)
        n = max(best) + 1 if best else 0
        _VERTEX_PARTS = [part_of_bone(best[i][1]) if i in best else "chest"
                         for i in range(n)]
    return _VERTEX_PARTS


_PARTS_CACHE = {}


def _human_args(node, env):
    """The human figure inside *node* and the arguments that pose it."""
    from . import mesh
    for n in node.walk():
        if n.type == "human" and n.visible:
            p = mesh.rp(n, env)
            return dict(
                gender=p.get("gender", 0.0), age=p.get("age", 0.0),
                weight=p.get("weight", 0.0), height=p.get("height", 0.0),
                stature=p.get("stature", 1700.0),
                targets=n.params.get("targets") or [],
                pose=[[r[0]] + [mesh.rv(v, env) for v in r[1:4]]
                      for r in n.params.get("pose") or []
                      if isinstance(r, list) and len(r) == 4],
                warp=[[mesh.rv(v, env) for v in r]
                      for r in n.params.get("warp") or []
                      if isinstance(r, list) and len(r) == 6],
                warp_radius=p.get("warp_radius", 45.0))
    return None


def face_parts(tris, args) -> list:
    """The body part under each triangle: the part of the posed body's
    vertex nearest its centre (a hashed grid, 40 mm cells)."""
    from . import human
    key = (repr(sorted((k, repr(v)) for k, v in args.items())), len(tris),
           tris[0] if tris else None)
    hit = _PARTS_CACHE.get(key)
    if hit is not None:
        return hit
    pts = human.points(**args)
    labels = vertex_parts()
    cell = 40.0
    grid = {}
    for i, p in enumerate(pts):
        if i >= len(labels):
            break
        grid.setdefault((int(p[0] // cell), int(p[1] // cell),
                         int(p[2] // cell)), []).append(i)
    out = []
    for tri in tris:
        cx = (tri[0][0] + tri[1][0] + tri[2][0]) / 3.0
        cy = (tri[0][1] + tri[1][1] + tri[2][1]) / 3.0
        cz = (tri[0][2] + tri[1][2] + tri[2][2]) / 3.0
        gx, gy, gz = int(cx // cell), int(cy // cell), int(cz // cell)
        best, best_d = None, None
        for reach in (1, 2, 4):
            for dx in range(-reach, reach + 1):
                for dy in range(-reach, reach + 1):
                    for dz in range(-reach, reach + 1):
                        for i in grid.get((gx + dx, gy + dy, gz + dz), ()):
                            p = pts[i]
                            d = ((p[0] - cx) ** 2 + (p[1] - cy) ** 2
                                 + (p[2] - cz) ** 2)
                            if best_d is None or d < best_d:
                                best, best_d = i, d
            if best is not None:
                break
        out.append(labels[best] if best is not None else "chest")
    if len(_PARTS_CACHE) > 16:
        _PARTS_CACHE.pop(next(iter(_PARTS_CACHE)))
    _PARTS_CACHE[key] = out
    return out


def colours(skin, garments) -> dict:
    """part (with side) -> (colour, material): skin first, then every
    garment row in order."""
    table = {part: (str(skin), "Skin")
             for base in PARTS for part in (base, base + ".L", base + ".R")}
    for row in garments or []:
        if not isinstance(row, list) or len(row) < 2:
            continue
        material = str(row[2]) if len(row) > 2 and row[2] else "Default"
        for part in expand(row[0]):
            table[part] = (str(row[1]), material)
    return table


# ------------------------------------------------------------ contract
def preamble(root) -> list:
    if any(n.type in TYPES for n in root.walk()):
        return HELPER.split("\n")
    return []


def statement(node, fmt, fn) -> str:
    from .model import scad_str
    p = node.params
    rows = ", ".join(
        "[" + ", ".join(scad_str(str(v)) for v in row[:3]) + "]"
        for row in p.get("garments") or [] if isinstance(row, list))
    return (f"kcad_outfit(skin = {scad_str(str(p.get('skin', '#e0ac8a')))}, "
            f"garments = [{rows}])")


def _text(value) -> str:
    value = str(value)
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _b_outfit(parser, positional, named):
    from .model import CadNode
    rows = named.get("garments")
    garments = [[_text(v) for v in row[:3]] for row in rows
                if isinstance(row, list) and len(row) >= 2] \
        if isinstance(rows, list) else []
    return CadNode("outfit", "Outfit", dict(
        skin=_text(named.get("skin", "#e0ac8a")), garments=garments))


BUILDERS = {"kcad_outfit": _b_outfit}


def check(node, env):
    if not any(n.type == "human" for n in node.walk()):
        return "outfit: put a human figure inside it"
    for number, row in enumerate(node.params.get("garments") or []):
        if not isinstance(row, list) or len(row) < 2:
            return f"garment {number}: needs a part and a colour"
        if not known(row[0]):
            return (f"garment {number}: no body part '{row[0]}' — use "
                    + ", ".join(list(PARTS) + list(GROUPS)))
        colour = str(row[1])
        if not (colour.startswith("#") and len(colour) in (4, 7)):
            return f"garment {number}: colour must be #rrggbb"
    return None


def tess(node, env, color, sel, selected):
    from . import mesh
    kids = mesh._children_mesh(node, env, color, sel, selected)
    args = _human_args(node, env)
    if args is None or not kids:
        return kids
    table = colours(node.params.get("skin", "#e0ac8a"),
                    node.params.get("garments"))
    parts = face_parts([t for t, _c, _s in kids], args)
    out = []
    for (tri, colour, sel_), part in zip(kids, parts):
        hexcol, material = table.get(part, (None, None))
        if hexcol is None:
            out.append((tri, colour, sel_))
            continue
        alpha = colour[1] if colour else 1.0
        out.append((tri, (hexcol, alpha, material), sel_))
    return out
