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
# What the game makes of it: an animal grazes and bolts, a person walks about
# and turns to look at you, a monster hunts you. "auto" leaves it to the game,
# which reads a monster's name ("Troll", "Dragon"…) and a person's two legs.
NATURES = ("auto", "animal", "person", "monster")


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
        # "Legs" — a loop or a group holding several — is split by where
        # each piece stands, not sent as one leg
        if "legs" in words and not (end and side):
            return "legs" + end + side
        return "leg" + end + side
    return None


def _family(role):
    return "leg" if role.startswith("leg") else (
        "wing" if role.startswith("wing") else role)


def _named_parts(root):
    """[(node, role)] — the outermost visible node per named part.

    A node whose name merely CONTAINS a part's word is not that part when
    it holds parts of another kind: a group called "Wing Beast" holding a
    Head and four legs is the beast, not a wing, and a "Legs" group holding
    "Tail" is not a leg. The same kind inside is fine — a Head's "Head top"
    is still the head."""
    found = []

    def others(node, family):
        for ch in node.children:
            if not ch.visible:
                continue
            r = role_of(ch.name)
            if r and _family(r) != family:
                return True
            if others(ch, family):
                return True
        return False

    def walk(node, hidden):
        hidden = hidden or not node.visible
        if node is not root and not hidden:
            r = role_of(node.name)
            if r and not others(node, _family(r)):
                found.append((node, r))
                return
        for ch in node.children:
            walk(ch, hidden)
    walk(root, False)
    return found


def creature_of(root):
    """The spec creature_build left on the creature's node — on *root*
    itself, or on the one node under it that carries one — or {}."""
    mark = (root.params or {}).get("creature") if root.params else None
    if mark:
        return dict(mark)
    found = [n for n in root.walk() if n is not root
             and (n.params or {}).get("creature")]
    return dict(found[0].params["creature"]) if len(found) == 1 else {}


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


class _BonePart:
    """Stands in for a named node when a part comes from an armature's
    bone (the creature's parts are keyed by node)."""

    def __init__(self, name):
        self.name = name


def _rigged_parts(root):
    """``(armature node, body triangles, {(part, role): triangles})``
    when *root* holds a visible armature whose bones are named like
    parts (Head, Tail, Left wing, Front left leg …): every triangle goes
    with its strongest bone, so a rigged monster arrives as the game's
    walking parts. None when there is no such armature."""
    from . import armature
    rig = next((n for n in root.walk() if n.type == "armature"
                and n.visible), None)
    if rig is None:
        return None
    try:
        tris, owners = armature.node_parts(rig)
    except Exception:
        return None
    roles = {b: role_of(b) for b in set(owners) if b}
    if not any(roles.values()):
        return None
    m = mesh.ancestor_matrix(rig, stop=None)
    colour = _inherited(rig) or next(
        (_rgb(n.params.get("color")) for n in rig.walk()
         if n.type == "color"), None) or DEFAULT_COLOUR
    body, groups, keys = [], {}, {}
    for tri, bone in zip(tris, owners):
        placed = tuple(tuple(mesh.mat_apply(m, p)) for p in tri)
        role = roles.get(bone)
        if not role:
            body.append((placed, colour))
            continue
        # every bone of one leg / the tail / the head joins one part
        key = keys.setdefault(role, (_BonePart(bone), role))
        groups.setdefault(key, []).append((placed, colour))
    return rig, body, groups


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


def build_creature(model, name, node=None, height=None, speed=None,
                   health=None, wild=True, nature=None, damage=None):
    """The creature dict for the document (or *node*'s subtree). A
    creature built by creature_build brings its own game numbers (speed,
    health, damage, what it is), used wherever the caller gives none."""
    mark = creature_of(node or model.root)
    speed = speed if speed is not None else (mark.get("speed") or 1.0)
    health = health if health is not None else (mark.get("health") or 10)
    damage = damage if damage is not None else mark.get("damage")
    nature = nature if nature not in (None, "") else (
        mark.get("nature") or "auto")
    nature = str(nature or "auto").lower()
    if nature not in NATURES:
        raise PlanetCraftError(
            f"{nature!r} is not a nature; use one of {', '.join(NATURES)}.")
    root = node or model.root
    named = _named_parts(root)
    rigged = _rigged_parts(root) if not named else None
    if rigged is not None:
        rig, body_rig, rig_groups = rigged
        body = _body_without(root, [(rig, None)]) + body_rig
        groups = rig_groups
    else:
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
        if r.startswith("legs"):
            # a group of several legs, dealt out by where each triangle
            # stands; whatever the name said (an end, a side) holds
            want = r[4:]
            for t in tris:
                tri = t[0]
                mx = sum(p[0] for p in tri) / 3
                my = sum(p[1] for p in tri) / 3
                end = want[:1] if want[:1] in ("F", "B") else (
                    "F" if my < cy else "B")
                side = want[-1:] if want[-1:] in ("L", "R") else (
                    "L" if mx > cx else "R")
                legs.setdefault("leg" + end + side, []).append(t)
            continue
        if r.startswith("leg"):
            if len(r) < 5:
                # "leg", "legF"/"legB" or "legL"/"legR": whatever the name
                # did not say comes from where the leg stands. (A leg named
                # "Left leg" used to read its SIDE as its end, came out as
                # "legLL", matched no joint and was dropped — a man sent
                # with named legs arrived with none.)
                bx0, by0, _bz0, bx1, by1, _bz1 = _bbox(tris)
                rest = r[3:]
                end = rest[:1] if rest[:1] in ("F", "B") else (
                    "F" if (by0 + by1) / 2 < cy else "B")
                side = rest[-1:] if rest[-1:] in ("L", "R") else (
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
    legless = mark.get("plan") in ("serpent", "slime")
    if not legs and not legless:
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
    out = dict(format=FORMAT, version=VERSION, kind="kc_" + slug(label),
               label=label, height=round(float(height), 3),
               speed=float(speed), health=int(health), wild=bool(wild),
               source="KherveCAD", auto_legs=auto,
               triangles=len(everything), parts=parts)
    if nature != "auto":
        out["nature"] = nature
    if damage is not None:
        out["damage"] = max(1, int(damage))
    if mark.get("plan"):
        out["plan"] = mark["plan"]
    return out


def summary(creature):
    roles = [p["role"] for p in creature["parts"]]
    out = {"kind": creature["kind"], "label": creature["label"],
           "height_blocks": creature["height"],
           "triangles": creature["triangles"], "parts": roles,
           "legs": sum(1 for r in roles if r.startswith("leg")),
           "auto_legs": creature["auto_legs"],
           "nature": creature.get("nature", "auto"),
           "speed": creature.get("speed"), "health": creature.get("health")}
    if creature.get("damage") is not None:
        out["damage"] = creature["damage"]
    return out


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


def export(model, name, folder=None, node=None, height=None, speed=None,
           health=None, wild=True, nature=None, damage=None):
    folder = folder or default_folder()
    creature = build_creature(model, name, node, height, speed, health,
                              wild, nature, damage)
    path = write(creature, folder)
    return dict(summary(creature), path=path, **where_to_see(
        creature["kind"]))


# ------------------------------------------------------ the game's side
#: the port PlanetCraft's own server listens on unless told otherwise
GAME_PORT = 8123


def game_running(port=GAME_PORT, timeout=0.3):
    """True when something answers on PlanetCraft's port here."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout):
            return True
    except OSError:
        return False


def where_to_see(kind=None, port=GAME_PORT):
    """Where a creature can be looked at: the game's Creatures book (menu
    ▸ Creatures, or creatures.html on its own), and whether the game is up
    to show it. A running game picks a new creature up within seconds."""
    url = f"http://localhost:{port}/creatures.html"
    if kind:
        url += "#" + kind
    running = game_running(port)
    return {"book_url": url, "game_running": running,
            "see_it": ("PlanetCraft is running: it arrives near the player "
                       "within a few seconds, and it is in the Creatures book "
                       "(menu ▸ Creatures)." if running else
                       "Start PlanetCraft: it arrives near the player, and it "
                       "is in the Creatures book (menu ▸ Creatures).")}


def list_creatures(folder=None):
    """Every creature in the game's creatures/ folder, as the game reads
    them: name, kind, what it is, size, joints, and when it was sent."""
    import time
    folder = folder or default_folder()
    if not is_game_folder(folder):
        raise PlanetCraftError(
            f"{folder!r} is not the PlanetCraft (KhervePlanet) folder — it "
            "should hold js/entities.js.")
    out_dir = os.path.join(folder, "creatures")
    rows = []
    if os.path.isdir(out_dir):
        for f in sorted(os.listdir(out_dir)):
            if not f.endswith(".json") or f == "index.json":
                continue
            path = os.path.join(out_dir, f)
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError) as exc:
                rows.append({"file": f, "error": str(exc)})
                continue
            if data.get("format") != FORMAT:
                continue
            roles = [p.get("role") for p in data.get("parts", [])]
            rows.append({
                "file": f, "name": f[:-5], "kind": data.get("kind"),
                "label": data.get("label"),
                "nature": data.get("nature", "auto"),
                "plan": data.get("plan"),
                "height_blocks": data.get("height"),
                "speed": data.get("speed"), "health": data.get("health"),
                "damage": data.get("damage"),
                "parts": roles,
                "legs": sum(1 for r in roles if str(r).startswith("leg")),
                "triangles": data.get("triangles"),
                "sent": time.strftime("%Y-%m-%d %H:%M",
                                      time.localtime(os.path.getmtime(path))),
            })
    return {"folder": out_dir, "creatures": rows, **where_to_see()}


def remove(name, folder=None):
    """Take one creature out of the game: its file, and its line in the
    index. Worlds already made keep any that are roaming them until they
    are reloaded."""
    folder = folder or default_folder()
    if not is_game_folder(folder):
        raise PlanetCraftError(
            f"{folder!r} is not the PlanetCraft (KhervePlanet) folder.")
    out_dir = os.path.join(folder, "creatures")
    stem = str(name)
    stem = stem[3:] if stem.startswith("kc_") else stem
    stem = stem[:-5] if stem.endswith(".json") else stem
    candidates = [stem, slug(stem)]
    path = next((os.path.join(out_dir, c + ".json") for c in candidates
                 if os.path.isfile(os.path.join(out_dir, c + ".json"))), None)
    if path is None:
        have = [f[:-5] for f in os.listdir(out_dir)
                if f.endswith(".json") and f != "index.json"] \
            if os.path.isdir(out_dir) else []
        raise PlanetCraftError(
            f"No creature {name!r} in the game; it has "
            f"{', '.join(have) or 'none'}.")
    os.remove(path)
    names = sorted(f[:-5] for f in os.listdir(out_dir)
                   if f.endswith(".json") and f != "index.json")
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(names, f)
    return {"removed": os.path.basename(path), "left": names}
