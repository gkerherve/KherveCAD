"""Send a model to PlanetCraft as a walking creature (Qt-free).

PlanetCraft (the KhervePlanet game) reads creatures from its
``creatures/`` folder at start-up (its js/creatures.js): one JSON file
each, listed in ``creatures/index.json``. A creature is coloured triangle
PARTS, each with the joint it turns about, and the game runs them through
its animal code — they trot, graze, bolt, sit and roam the wild herds.

`export(model, ...)` builds that file from the document (or one node):

- **parts by name**: a node (Object, group, anything) whose name holds
  *head*, *tail*, *wing* or *leg* becomes that part — a leg's side and end
  from the words front/fore/back/hind/rear and left/right, else from where
  it stands; everything else is the body. Name the pieces and the joints
  are exactly where you meant them.
- **legs found by themselves** when none are named: the triangles low
  down (under `LEG_FRACTION` of the height) split by quadrant round the
  middle, if the middle underneath is clear — a table, a horse or a robot
  gets its legs; a statue on a plinth does not, and bobs along instead.
- **size**: millimetres to blocks (one block ~ 1 m), real size unless a
  `height` in blocks is given; centred, feet on 0.
- **axes**: KherveCAD is Z up with the front facing -Y; PlanetCraft is Y up
  with the front at -Z: game = (-x, z, y), a proper rotation, so winding
  and handedness survive.
- joints: a leg turns at the top of its box, the head at the back of its
  base (the neck), a tail at its front top, a wing at its inner top edge.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
import os
import re

from . import mesh

FORMAT = "kherveCAD-creature"
VERSION = 1
LEG_FRACTION = 0.38
MAX_TRIANGLES = 60000
SEGMENTS = 16
DEFAULT_COLOUR = (0.78, 0.78, 0.78)
ROLES = ("head", "tail", "wingL", "wingR", "legFL", "legFR", "legBL",
         "legBR")


class PlanetCraftError(ValueError):
    """The model cannot be sent (the message says why)."""


# ------------------------------------------------------------- finding
def default_folder():
    """The KhervePlanet project beside KherveCAD's, when it is there."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for cand in (os.path.join(os.path.dirname(here), "KhervePlanet"),
                 os.path.expanduser("~/Documents/PycharmProjects/"
                                    "KhervePlanet")):
        if is_game_folder(cand):
            return cand
    return ""


def is_game_folder(folder):
    return bool(folder) and os.path.isfile(
        os.path.join(folder, "js", "entities.js"))


def slug(name):
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(name)).strip("_").lower()
    return s[:40] or "creature"


def role_of(name):
    """The part a node's name asks for, or None ('leg' alone -> 'leg')."""
    n = str(name).lower()
    words = set(re.findall(r"[a-z]+", n))
    if "head" in words:
        return "head"
    if "tail" in words:
        return "tail"
    if words & {"wing", "wings"}:
        if words & {"left", "l"}:
            return "wingL"
        if words & {"right", "r"}:
            return "wingR"
        return "wing"
    if words & {"leg", "legs"}:
        end = "F" if words & {"front", "fore", "fl", "fr"} else (
            "B" if words & {"back", "hind", "rear", "bl", "br"} else "")
        side = "L" if words & {"left", "l", "fl", "bl"} else (
            "R" if words & {"right", "r", "fr", "br"} else "")
        return "leg" + end + side
    return None


def _named_parts(root):
    """[(node, role)] — the outermost visible node per named part."""
    found = []

    def walk(node, hidden):
        hidden = hidden or not node.visible
        if node is not root and not hidden:
            r = role_of(node.name)
            if r:
                found.append((node, r))
                return
        for ch in node.children:
            walk(ch, hidden)
    walk(root, False)
    return found


# ------------------------------------------------------------ geometry
def _rgb(value):
    s = str(value or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    try:
        return tuple(int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return None


def _inherited(node):
    p = node
    while p is not None:
        if p.type == "color":
            return _rgb(p.params.get("color"))
        p = p.parent
    return None


def _coloured_world(node, root, default):
    """[(triangle in document mm, rgb)] of a subtree, placed."""
    m = mesh.ancestor_matrix(node, stop=None) if node is not root else None
    out = []
    for tri, c in mesh.tessellate_colored(node, fn=SEGMENTS):
        rgb = _rgb(c[0]) if c else None
        if m is not None:
            tri = tuple(tuple(mesh.mat_apply(m, p)) for p in tri)
        out.append((tri, rgb or default))
    return out


def _body_without(root, parts):
    """The document's triangles with the named parts hidden."""
    was = [(n, n.visible) for n, _r in parts]
    try:
        for n, _r in parts:
            n.visible = False
        return _coloured_world(root, root, DEFAULT_COLOUR)
    finally:
        for n, v in was:
            n.visible = v


def _bbox(tris):
    xs = [p[0] for t, _c in tris for p in t]
    ys = [p[1] for t, _c in tris for p in t]
    zs = [p[2] for t, _c in tris for p in t]
    return min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)


def _auto_legs(body, box):
    """Split low triangles into quadrant legs if the middle underneath is
    clear. Returns (body_rest, {role: tris}) — no legs when it does not
    look like something standing on legs."""
    x0, y0, z0, x1, y1, z1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    limit = z0 + (z1 - z0) * LEG_FRACTION
    low, rest = [], []
    for t in body:
        (tri, _c) = t
        (low if sum(p[2] for p in tri) / 3 <= limit else rest).append(t)
    if len(low) < 8:
        return body, {}
    hx, hy = (x1 - x0) / 2 or 1.0, (y1 - y0) / 2 or 1.0
    middle = sum(1 for tri, _c in low
                 if abs(sum(p[0] for p in tri) / 3 - cx) < hx * 0.18
                 and abs(sum(p[1] for p in tri) / 3 - cy) < hy * 0.18)
    if middle > len(low) * 0.05:
        return body, {}
    quad = {}
    for t in low:
        tri = t[0]
        mx = sum(p[0] for p in tri) / 3
        my = sum(p[1] for p in tri) / 3
        # KherveCAD +x is the creature's LEFT once the game turns it
        side = "L" if mx > cx else "R"
        end = "F" if my < cy else "B"
        quad.setdefault(end + side, []).append(t)
    if len(quad) < 2:
        return body, {}
    ends = {k[0] for k in quad}
    legs = {}
    if len(ends) == 1:                       # a biped: two legs, one row
        for k, tris in quad.items():
            legs["legF" + k[1]] = tris
    else:
        for k, tris in quad.items():
            legs["leg" + k] = tris
    return rest, legs


def _to_game(p, scale, cx, cy, z0):
    x, y, z = p
    return (-(x - cx) * scale, (z - z0) * scale, (y - cy) * scale)


def _pivot(role, tris):
    xs = [p[0] for t, _c in tris for p in t]
    ys = [p[1] for t, _c in tris for p in t]
    zs = [p[2] for t, _c in tris for p in t]
    bx0, bx1, by0, by1, bz0, bz1 = min(xs), max(xs), min(ys), max(ys), \
        min(zs), max(zs)
    mx, mz = (bx0 + bx1) / 2, (bz0 + bz1) / 2
    if role.startswith("leg"):
        return (mx, by1, mz)
    if role == "head":
        return (mx, by0 + (by1 - by0) * 0.3, bz1)
    if role == "tail":
        return (mx, by1, bz0)
    if role in ("wingL", "wingR"):
        inner = bx0 if abs(bx0) < abs(bx1) else bx1
        return (inner, by1, mz)
    return (0.0, 0.0, 0.0)


def _part(name, role, game_tris):
    pv = _pivot(role, game_tris)
    positions, colors = [], []
    for tri, rgb in game_tris:
        for p in tri:
            positions += [round(p[0] - pv[0], 4), round(p[1] - pv[1], 4),
                          round(p[2] - pv[2], 4)]
            colors += [round(rgb[0], 3), round(rgb[1], 3), round(rgb[2], 3)]
    xs = [p[0] for t, _c in game_tris for p in t]
    ys = [p[1] for t, _c in game_tris for p in t]
    zs = [p[2] for t, _c in game_tris for p in t]
    return dict(name=name, role=role, pivot=[round(v, 4) for v in pv],
                size=[round(max(xs) - min(xs), 4), round(max(ys) - min(ys), 4),
                      round(max(zs) - min(zs), 4)],
                positions=positions, colors=colors)


def build_creature(model, name, node=None, height=None, speed=1.0,
                   health=10, wild=True):
    """The creature dict for the document (or *node*'s subtree)."""
    root = node or model.root
    named = _named_parts(root)
    body = _body_without(root, named) if named else _coloured_world(
        root, root, DEFAULT_COLOUR)
    groups = {}
    for n, r in named:
        groups.setdefault((n, r), _coloured_world(
            n, root, _inherited(n) or DEFAULT_COLOUR))
    everything = body + [t for tris in groups.values() for t in tris]
    if not everything:
        raise PlanetCraftError("There is nothing visible to send.")
    if len(everything) > MAX_TRIANGLES:
        raise PlanetCraftError(
            f"{len(everything)} triangles is too many for a creature (at "
            f"most {MAX_TRIANGLES}); simplify it or send one part.")
    box = _bbox(everything)
    x0, y0, z0, x1, y1, z1 = box
    tall = z1 - z0
    if tall <= 0:
        raise PlanetCraftError("The model is flat; a creature needs height.")
    if height is None:
        height = tall / 1000.0
        if not 0.25 <= height <= 12.0:
            height = 1.2
    scale = float(height) / tall
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    # legs: named ones, sided by position when the name did not say
    legs = {}
    others = []
    for (n, r), tris in groups.items():
        if r.startswith("leg"):
            if len(r) < 5:
                bx0, by0, _bz0, bx1, by1, _bz1 = _bbox(tris)
                end = r[3:4] or ("F" if (by0 + by1) / 2 < cy else "B")
                side = r[4:5] if len(r) == 5 else (
                    "L" if (bx0 + bx1) / 2 > cx else "R")
                r = "leg" + end + side
            legs.setdefault(r, []).extend(tris)
        elif r == "wing":
            bx0, _by0, _bz0, bx1, _by1, _bz1 = _bbox(tris)
            others.append((n.name, "wingL" if (bx0 + bx1) / 2 > cx
                           else "wingR", tris))
        else:
            others.append((n.name, r, tris))
    auto = False
    if not legs:
        body, legs = _auto_legs(body, box)
        auto = bool(legs)

    def game(tris):
        return [(tuple(_to_game(p, scale, cx, cy, z0) for p in tri), rgb)
                for tri, rgb in tris]

    parts = []
    if body:
        parts.append(_part("Body", "body", game(body)))
    for role in ("legFL", "legFR", "legBL", "legBR"):
        if legs.get(role):
            parts.append(_part(role, role, game(legs[role])))
    seen = set()
    for pname, role, tris in others:
        role = role if role not in seen else "extra"
        seen.add(role)
        parts.append(_part(pname, role, game(tris)))
    label = str(name).strip() or "Creature"
    return dict(format=FORMAT, version=VERSION, kind="kc_" + slug(label),
                label=label, height=round(float(height), 3),
                speed=float(speed), health=int(health), wild=bool(wild),
                source="KherveCAD", auto_legs=auto,
                triangles=len(everything), parts=parts)


def summary(creature):
    roles = [p["role"] for p in creature["parts"]]
    return {"kind": creature["kind"], "label": creature["label"],
            "height_blocks": creature["height"],
            "triangles": creature["triangles"], "parts": roles,
            "legs": sum(1 for r in roles if r.startswith("leg")),
            "auto_legs": creature["auto_legs"]}


def write(creature, folder):
    """Write creatures/<slug>.json and rebuild creatures/index.json the way
    the game's server does. Returns the file path."""
    if not is_game_folder(folder):
        raise PlanetCraftError(
            f"{folder!r} is not the PlanetCraft (KhervePlanet) folder — it "
            "should hold js/entities.js.")
    out = os.path.join(folder, "creatures")
    os.makedirs(out, exist_ok=True)
    name = creature["kind"][3:]
    path = os.path.join(out, name + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(creature, f, separators=(",", ":"))
    names = sorted(f[:-5] for f in os.listdir(out)
                   if f.endswith(".json") and f != "index.json")
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as f:
        json.dump(names, f)
    return path


def export(model, name, folder=None, node=None, height=None, speed=1.0,
           health=10, wild=True):
    folder = folder or default_folder()
    creature = build_creature(model, name, node, height, speed, health,
                              wild)
    path = write(creature, folder)
    return dict(summary(creature), path=path)
