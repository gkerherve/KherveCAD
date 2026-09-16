"""World building styles for the City Builder (Qt-free): a mosque and
houses in Arabic, Chinese, Japanese, American, Indian and Pakistani
traditions.

Same contract as `city_buildings`: the OUTSIDE only, centred on the
origin with the front facing -Y, built from boxes, cylinders, spheres
and hulls (no booleans, so the preview is exact). Each builder takes the
resolved spec (`city_buildings.resolve`) and returns the unplaced body;
`city_buildings.build_building` turns and places it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from . import city_buildings as B
from .city_buildings import (GLASS, METAL, SILL, WHITE, Facade, _hull,
                             _num, box, color, cyl, group, loop, move,
                             pitched_roof, turn)
from .model import CadNode

GOLD = "#c9a54a"
DARK = "#2b2622"
TIMBER = "#5a3b26"
RED = "#9e2a22"
MARBLE = "#ece8e0"
GREEN_DOME = "#3f7f6a"

#: style -> (floors range, roof, glazing, wall material) — merged into
#: city_buildings.STYLES
STYLES = {
    "mosque": ((1, 2), "flat", "arches", "render"),
    "arabic house": ((1, 3), "flat", "arches", "render"),
    "chinese house": ((1, 2), "hip", "screens", "brick"),
    "japanese house": ((1, 2), "hip", "screens", "render"),
    "american house": ((2, 2), "gable", "windows", "render"),
    "indian house": ((2, 3), "flat", "arches", "render"),
    "pakistani house": ((2, 3), "flat", "windows", "render"),
}

DEFAULT_SIZE = {"mosque": (24000, 24000), "arabic house": (13000, 12000),
                "chinese house": (15000, 10000),
                "japanese house": (12000, 9000),
                "american house": (12000, 10000),
                "indian house": (12000, 11000),
                "pakistani house": (12000, 15000)}

LABELS = {"mosque": "Mosque", "arabic house": "Arabic house",
          "chinese house": "Chinese house (courtyard hall)",
          "japanese house": "Japanese house (minka)",
          "american house": "American house (porch)",
          "indian house": "Indian house (haveli)",
          "pakistani house": "Pakistani house"}

#: style -> (wall palette, roof palette) used when no colour is given
PALETTES = {
    "mosque": (["#f4f1ea", "#efe6d2", "#e8dcc4"], [GREEN_DOME, GOLD,
                                                  "#e9e6df"]),
    "arabic house": (["#e8d2b0", "#dcc39a", "#efe0c4", "#d9b98f"],
                     ["#d9c7a4"]),
    "chinese house": (["#8f9296", "#9da0a3", "#7f8286"],
                      ["#3f4449", "#4a4f55"]),
    "japanese house": (["#f1ede3", "#ece5d6"], ["#3a3d42", "#4e5156"]),
    "american house": (["#f4f1ea", "#b7c4c9", "#d6c38f", "#cfdcc8",
                        "#e3b7a0"], ["#4e5156", "#5a5f66", "#7a3b2e"]),
    "indian house": (["#e8a86a", "#e3b7a0", "#f0c987", "#d98c6a"],
                     ["#f4f1ea"]),
    "pakistani house": (["#f4f1ea", "#e8d2b0", "#dcd6cc"], ["#b9b6b0"]),
}


def sphere(name, x, y, z, r, seg=24):
    return CadNode("sphere", name, dict(x=x, y=y, z=z, radius=r,
                                        segments=seg))


def scaled(node, x=1.0, y=1.0, z=1.0, name="Scale"):
    s = CadNode("scale", name, dict(x=x, y=y, z=z))
    s.add(node)
    return s


def dome(name, x, y, z, r, rise=1.0, onion=False, seg=24):
    """A dome sitting on z: a (squashed) sphere, pointed when onion."""
    body = move(scaled(sphere(name, 0, 0, 0, r, seg), z=rise), x, y, z, name)
    if not onion:
        return body
    return _hull(name, [body, cyl("Tip", x, y, z + r * rise, r * 0.9, r * 0.25,
                                  1.0, seg=12)])


def finial(x, y, z, h=1400.0, crescent=False):
    parts = [cyl("Finial rod", x, y, z, h, 60, 40),
             sphere("Finial ball", x, y, z + h * 0.4, 160, 12)]
    if crescent:
        parts.append(move(turn(cyl("Crescent", 0, 0, -30, 60, 380, seg=16),
                               x=90.0), x, y, z + h + 250, "Crescent"))
    return color(group("Finial", parts), GOLD, "Gold")


def arch_front(name, x, yface, z, w, h, proud=40.0, depth=60.0):
    """An arched opening on a -Y facing wall: a box with a round head."""
    r = w / 2.0
    head = move(turn(cyl("Arch head", 0, 0, 0, depth, r, seg=16), x=-90.0),
                x, yface - proud, z + h - r, "Arch head")
    return group(name, [box("Arch", x - r, yface - proud, z, w, depth,
                            h - r), head])


def arcade_front(name, x0, x1, yface, z, h, pitch=2600.0, w=1500.0,
                 proud=40.0):
    n = max(1, int((x1 - x0) // pitch))
    step = (x1 - x0) / n
    return group(name, [arch_front("Arch", x0 + step * (k + 0.5), yface, z, w,
                                   h, proud) for k in range(n)])


def _walls(b, x0, y0, w, d, H, name="Walls"):
    wall_mat = B.WALLS[b["wall"]][0]
    return [color(box(name, x0, y0, 0.0, w, d, H), b["color"], wall_mat),
            color(box("Plinth", x0 - 60, y0 - 60, 0.0, w + 120, d + 120, 500),
                  "#7b766e", "Stone")]


def _parapet(w, d, H, ph=900.0, t=250.0, col="#e8dcc4", crenel=False):
    parts = [box("Parapet", -w / 2, -d / 2, H, w, t, ph),
             box("Parapet", -w / 2, d / 2 - t, H, w, t, ph),
             box("Parapet", -w / 2, -d / 2, H, t, d, ph),
             box("Parapet", w / 2 - t, -d / 2, H, t, d, ph)]
    if crenel:
        for (length, side) in ((w, "x"), (d, "y")):
            n = int(length // 1200)
            for k in range(n):
                u = -length / 2 + (k + 0.5) * length / n - 250
                for s in (-1, 1):
                    if side == "x":
                        parts.append(box("Merlon", u, s * d / 2 - (t if s > 0
                                                                   else 0),
                                         H + ph, 500, t, 500))
                    else:
                        parts.append(box("Merlon", s * w / 2 - (t if s > 0
                                                                else 0), u,
                                         H + ph, t, 500, 500))
    return color(group("Parapet", parts), col, "Render")


def _windows(b, w, d, floors, fh, z0=900.0, skip_door=True):
    out = []
    for side in ("front", "back", "left", "right"):
        lp, _ = B.punched_windows(Facade(side, -w / 2, -d / 2, w, d), floors,
                                  fh, z0=z0, skip_door=skip_door and
                                  side == "front")
        if lp is not None:
            out.append(lp)
    return out


# ----------------------------------------------------------- the styles
def mosque(b):
    w, d, fh = b["w"], b["d"], b["floor_height"]
    H = max(b["floors"], 1) * fh * 1.6
    g = group(b["name"])
    for p in _walls(b, -w / 2, -d / 2, w, d, H):
        g.add(p)
    g.add(_parapet(w, d, H, 700, col=B.TRIM, crenel=True))
    g.add(color(box("Roof slab", -w / 2, -d / 2, H, w, d, 200), "#8a8580",
                "Concrete"))
    # arched windows on every side, a tall arched portal on the front
    for side in ("front", "back", "left", "right"):
        f = Facade(side, -w / 2, -d / 2, w, d)
        n = max(1, int(f.length // 3500))
        step = f.length / n
        arches = []
        for k in range(n):
            u = -f.length / 2 + step * (k + 0.5)
            if side == "front" and abs(u) < 3000:
                continue
            arches.append(f.box("Window", u - 600, H * 0.3, 1200, H * 0.45,
                                50, 60))
            arches.append(f.box("Window head", u - 400, H * 0.75, 800, 500,
                                50, 60))
        g.add(color(group(f"{side.capitalize()} windows", arches), GLASS,
                    "Plastic"))
    pw, ph = 5200.0, H + 2500.0
    g.add(color(box("Portal", -pw / 2 - 700, -d / 2 - 1500, 0.0, pw + 1400,
                    1500, ph), b["color"], B.WALLS[b["wall"]][0]))
    g.add(color(arch_front("Portal arch", 0.0, -d / 2 - 1500, 0.0, pw * 0.7,
                           ph - 1200, 30, 80), "#1f5f73", "Matte"))
    g.add(color(box("Portal frieze", -pw / 2 - 700, -d / 2 - 1560, ph - 700,
                    pw + 1400, 80, 450), GOLD, "Gold"))
    # drum and the main dome, four small corner domes
    r = min(w, d) * 0.3
    g.add(color(cyl("Drum", 0, 0, H, r * 0.45, r * 1.02, seg=32), b["color"],
                "Render"))
    g.add(color(loop("Drum windows", "k", 12, [
        turn(box("Drum window", r * 1.0, -250, H + r * 0.1, 80, 500,
                 r * 0.25), z="k * 30")]), GLASS, "Plastic"))
    top = H + r * 0.45
    g.add(color(dome("Main dome", 0, 0, top, r, 1.05, onion=True, seg=32),
                b["roof_color"], "Metal"))
    g.add(finial(0, 0, top + r * 1.05 + r * 0.9 - 200, 1800, crescent=True))
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * w * 0.32, sy * d * 0.32
            g.add(color(cyl("Small drum", cx, cy, H, 900, r * 0.3, seg=16),
                        b["color"], "Render"))
            g.add(color(dome("Small dome", cx, cy, H + 900, r * 0.3, 1.0,
                             onion=True, seg=16), b["roof_color"], "Metal"))
    # minarets on the front corners
    mh = H * 3.2
    for sx in (-1, 1):
        mx, my = sx * (w / 2 + 1400), -d / 2 + 1400
        mr = 1100.0
        m = [color(cyl("Minaret base", mx, my, 0, mh * 0.25, mr * 1.3, mr * 1.2,
                       seg=8), b["color"], "Render"),
             color(cyl("Minaret shaft", mx, my, mh * 0.25, mh * 0.7, mr,
                       mr * 0.85, seg=16), b["color"], "Render")]
        for k, zb in enumerate((mh * 0.55, mh * 0.9)):
            m.append(color(cyl("Balcony", mx, my, zb, 250, mr * 1.6, seg=16),
                           B.TRIM, "Stone"))
            m.append(color(cyl("Balcony corbel", mx, my, zb - 600, 600, mr,
                               mr * 1.6, seg=16), B.TRIM, "Stone"))
            m.append(color(cyl("Railing", mx, my, zb + 250, 700, mr * 1.55,
                               seg=16), "#d8d2c4", "Glass", 0.6))
        m.append(color(cyl("Lantern", mx, my, mh * 0.95, 1500, mr * 0.7,
                           seg=8), b["color"], "Render"))
        m.append(color(cyl("Minaret cone", mx, my, mh * 0.95 + 1500, 3200,
                           mr * 0.85, 0.0, seg=16), b["roof_color"], "Metal"))
        g.add(group("Minaret", m))
        g.add(finial(mx, my, mh * 0.95 + 4700, 1200, crescent=True))
    return g


def arabic_house(b):
    w, d, fh, n = b["w"], b["d"], b["floor_height"], b["floors"]
    H = n * fh
    g = group(b["name"])
    for p in _walls(b, -w / 2, -d / 2, w, d, H):
        g.add(p)
    g.add(color(box("Roof slab", -w / 2, -d / 2, H, w, d, 200), "#b8a888",
                "Concrete"))
    g.add(_parapet(w, d, H, 1000, col=b["color"], crenel=True))
    # small deep windows with arched heads
    wins = []
    for side in ("front", "back", "left", "right"):
        f = Facade(side, -w / 2, -d / 2, w, d)
        cols = max(1, int(f.length // 3200))
        step = f.length / cols
        for fl in range(n):
            for c in range(cols):
                u = -f.length / 2 + step * (c + 0.5)
                if side == "front" and fl == 0 and abs(u) < 1800:
                    continue
                z = 1100 + fl * fh
                wins.append(f.box("Window", u - 450, z, 900, 1200, 40, 50))
                wins.append(f.box("Window head", u - 300, z + 1200, 600, 300,
                                  40, 50))
    g.add(color(group("Windows", wins), DARK, "Matte"))
    # the carved wooden door in an arch and a mashrabiya on the upper floor
    g.add(color(arch_front("Door arch", 0.0, -d / 2, 0.0, 2600, 3300, 120,
                           140), SILL, "Stone"))
    g.add(color(arch_front("Door", 0.0, -d / 2, 0.0, 1900, 2900, 150, 60),
                TIMBER, "Matte"))
    g.add(color(group("Door studs", [
        box("Stud", x, -d / 2 - 170, z, 80, 30, 80)
        for x in (-600, -200, 200, 600) for z in (600, 1300, 2000)]),
        GOLD, "Gold"))
    if n >= 2:
        mw, mz = min(4200.0, w * 0.4), fh + 700
        m = [box("Mashrabiya box", -mw / 2, -d / 2 - 900, mz, mw, 900, 2000),
             box("Mashrabiya corbel", -mw / 2 + 200, -d / 2 - 700, mz - 400,
                 mw - 400, 700, 400),
             box("Mashrabiya hood", -mw / 2 - 150, -d / 2 - 1050, mz + 2000,
                 mw + 300, 1050, 200)]
        g.add(color(group("Mashrabiya", m), TIMBER, "Matte"))
        bars = [box("Lattice bar", -mw / 2 + 150, -d / 2 - 930,
                    f"{_num(mz + 200)} + k * 250", mw - 300, 40, 50)
                for _ in (0,)]
        bars.append(box("Lattice post", f"{_num(-mw / 2 + 150)} + k * 250",
                        -d / 2 - 930, mz + 150, 50, 40, 1700))
        g.add(color(loop("Lattice", "k", int((mw - 300) // 250) + 1, bars),
                    "#8a6240", "Matte"))
    # a barjeel wind tower on the roof
    tx, ty, tw = w / 2 - 2600, d / 2 - 2600, 2000.0
    th = 4200.0
    g.add(color(box("Wind tower", tx - tw / 2, ty - tw / 2, H, tw, tw, th),
                b["color"], "Render"))
    vents = []
    for side in ("front", "back", "left", "right"):
        f = Facade(side, tx - tw / 2, ty - tw / 2, tw, tw)
        vents.append(f.box("Vent slot", -600, th - 2200 + H, 300, 1800, 30,
                           40))
        vents.append(f.box("Vent slot", 300, th - 2200 + H, 300, 1800, 30,
                           40))
    g.add(color(group("Wind tower vents", vents), DARK, "Matte"))
    g.add(color(box("Wind tower cap", tx - tw / 2 - 150, ty - tw / 2 - 150,
                    H + th, tw + 300, tw + 300, 250), SILL, "Stone"))
    return g


def _upturned_hip_roof(w, d, H, col, mat, e=1400.0, lift=900.0):
    """A hip roof with swept eaves: a flat hipped hull plus lifted
    corners — the Chinese and Japanese silhouette."""
    t, rise = 220.0, min(w, d) * 0.42
    rl = max(w - d, 1000.0) if w >= d else 1000.0
    parts = [_hull("Hipped roof", [
        box("Eaves", -w / 2 - e, -d / 2 - e, H, w + 2 * e, d + 2 * e, t),
        box("Ridge", -rl / 2, -300, H + rise, rl, 600, t)])]
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * (w / 2 + e), sy * (d / 2 + e)
            parts.append(_hull("Swept corner", [
                box("Corner low", cx - (1800 if sx > 0 else 0),
                    cy - (1800 if sy > 0 else 0), H, 1800, 1800, t),
                box("Corner tip", cx - (200 if sx > 0 else 0) + sx * 300,
                    cy - (200 if sy > 0 else 0) + sy * 300, H + lift, 200, 200,
                    t)]))
    return color(group("Roof", parts), col, mat), rise, rl


def chinese_house(b):
    w, d, fh, n = b["w"], b["d"], b["floor_height"], b["floors"]
    H = n * fh + 400
    g = group(b["name"])
    g.add(color(box("Stone platform", -w / 2 - 1500, -d / 2 - 2200, 0.0,
                    w + 3000, d + 3700, 700), "#a8a39a", "Stone"))
    g.add(color(box("Steps", -1800, -d / 2 - 3000, 0.0, 3600, 800, 350),
                "#a8a39a", "Stone"))
    g.add(color(box("Walls", -w / 2, -d / 2, 700, w, d, H - 700), b["color"],
                "Brick"))
    # red columns along a front veranda, red lattice screens between them
    n_col = max(3, int(w // 3000) + 1)
    step = w / (n_col - 1)
    g.add(color(loop("Columns", "k", n_col, [
        cyl("Column", f"{_num(-w / 2)} + k * {_num(step)}", -d / 2 - 1600, 700,
            H - 700, 260, seg=12)]), RED, "Matte"))
    g.add(color(box("Lintel beam", -w / 2 - 300, -d / 2 - 1900, H - 700,
                    w + 600, 600, 700), RED, "Matte"))
    g.add(color(box("Painted frieze", -w / 2 - 300, -d / 2 - 1960, H - 650,
                    w + 600, 60, 400), "#2f6f8f", "Matte"))
    screens = []
    for k in range(n_col - 1):
        x0 = -w / 2 + k * step + 400
        sw = step - 800
        screens.append(box("Screen panel", x0, -d / 2 - 60, 900, sw, 60,
                           H - 1900))
    g.add(color(group("Lattice screens", screens), RED, "Matte"))
    g.add(color(group("Screen lattice", [
        loop("Lattice rows", "r", int((H - 1900) // 450), [
            box("Rail", -w / 2 + 400, -d / 2 - 100, f"1100 + r * 450",
                w - 800, 40, 40)])]), GOLD, "Gold"))
    g.add(color(box("Door", -900, -d / 2 - 90, 700, 1800, 40, 2600), "#6b1f1a",
                "Matte"))
    roof, rise, rl = _upturned_hip_roof(w + 1600, d + 3200, H, b["roof_color"],
                                        "Roof tiles", e=900, lift=1100)
    g.add(move(roof, 0, -800, 0, "Roof"))
    g.add(color(group("Ridge ornaments", [
        box("Ridge crest", -rl / 2 - 300, -1150, H + rise + 150, rl + 600, 700,
            500),
        _hull("Ridge beast", [box("Base", -rl / 2 - 700, -1100, H + rise + 150,
                                  700, 600, 400),
                              box("Tail", -rl / 2 - 500, -1050,
                                  H + rise + 1300, 300, 500, 300)]),
        _hull("Ridge beast", [box("Base", rl / 2, -1100, H + rise + 150, 700,
                                  600, 400),
                              box("Tail", rl / 2 + 200, -1050, H + rise + 1300,
                                  300, 500, 300)])]), "#2e3236", "Slate"))
    lanterns = [cyl("Lantern", x, -d / 2 - 1300, H - 1900, 600, 280, seg=12)
                for x in (-step, step)]
    g.add(color(group("Red lanterns", lanterns), "#d0342c", "Emissive"))
    return g


def japanese_house(b):
    w, d, fh, n = b["w"], b["d"], b["floor_height"], b["floors"]
    H = n * fh
    lift = 600.0
    g = group(b["name"])
    g.add(color(loop("Stilts", "k", 4, [
        box("Foundation stone", f"{_num(-w / 2)} + k * {_num((w - 400) / 3)}",
            -d / 2, 0, 400, d, lift)]), "#8a857c", "Stone"))
    g.add(color(box("Walls", -w / 2, -d / 2, lift, w, d, H), b["color"],
                "Render"))
    # timber frame: posts and a beam per floor on every face
    posts, beams = [], []
    for side in ("front", "back", "left", "right"):
        f = Facade(side, -w / 2, -d / 2, w, d)
        m = max(2, int(f.length // 1800))
        stp = f.length / m
        posts.append(loop(f"{side} posts", "k", m + 1, [
            f.box("Post", f"{_num(-f.length / 2 - 90)} + k * {_num(stp)}",
                  lift, 180, H, 60)]))
        beams.append(loop(f"{side} beams", "fl", n + 1, [
            f.box("Beam", -f.length / 2 - 100, f"{_num(lift - 100)} + fl * "
                  f"{_num(fh)}", f.length + 200, 220, 70)]))
    g.add(color(group("Timber frame", posts + beams), TIMBER, "Matte"))
    # shoji screens on the front and a wooden engawa veranda
    f = Facade("front", -w / 2, -d / 2, w, d)
    sw = 900.0
    ns = int((w - 1800) // sw)
    g.add(color(loop("Shoji", "k", ns, [
        f.box("Shoji paper", f"{_num(-ns * sw / 2 + 40)} + k * {_num(sw)}",
              lift + 150, sw - 80, 2100, 40, 20)]), "#f7f3e6", "Matte"))
    g.add(color(loop("Shoji grid", "r", 5, [
        f.box("Kumiko", -ns * sw / 2, f"{_num(lift + 500)} + r * 400",
              ns * sw, 35, 55, 15)]), "#7a5a3c", "Matte"))
    g.add(color(box("Engawa deck", -w / 2 - 300, -d / 2 - 1500, lift - 150,
                    w + 600, 1500, 150), "#8f6b4e", "Matte"))
    g.add(color(box("Step stone", -900, -d / 2 - 2300, 0, 1800, 800, 300),
                "#9b9993", "Stone"))
    # irimoya: a swept hip below, a small gable on top
    roof, rise, rl = _upturned_hip_roof(w, d, lift + H, b["roof_color"],
                                        "Slate", e=1200, lift=500)
    g.add(roof)
    gz = lift + H + rise * 0.55
    g.add(move(pitched_roof("gable", max(rl, w * 0.45), d * 0.45, gz,
                            b["roof_color"], "Slate", TIMBER, "Matte",
                            chimney=False, pitch=40), 0, 0, 0, "Gable"))
    if n >= 2:
        g.add(color(box("Hisashi", -w / 2 - 900, -d / 2 - 900, lift + fh, w +
                        1800, 900, 180), b["roof_color"], "Slate"))
    return g


def american_house(b):
    w, d, fh, n = b["w"], b["d"], b["floor_height"], b["floors"]
    H = n * fh
    g = group(b["name"])
    g.add(color(box("Walls", -w / 2, -d / 2, 0.0, w, d, H), b["color"],
                "Render"))
    g.add(color(box("Foundation", -w / 2 - 60, -d / 2 - 60, 0, w + 120,
                    d + 120, 600), "#8a857c", "Concrete"))
    # clapboard siding: a shadow line every 250 mm, all four sides
    g.add(color(loop("Clapboard", "k", int((H - 600) // 250), [
        _hull("Board lap", [box("Lap", -w / 2 - 25, -d / 2 - 25,
                                f"650 + k * 250", w + 50, d + 50, 20)])]),
        "#d9d6cf", "Matte", alpha=0.9))
    g.add(color(group("Corner boards", [
        box("Corner board", sx * w / 2 - 110, sy * d / 2 - 110, 600, 220, 220,
            H - 600) for sx in (-1, 1) for sy in (-1, 1)]), WHITE, "Matte"))
    for lp in _windows(b, w, d, n, fh):
        g.add(lp)
    # shutters beside the front windows
    f = Facade("front", -w / 2, -d / 2, w, d)
    cols = int((w - 900.0) // 2800)
    start = -(cols - 1) * 2800 / 2.0 - 600
    g.add(color(loop("Shutters", "fl", n, [loop("Columns", "c", cols, [
        f.box("Shutter", f"{_num(start - 750)} + c * 2800",
              "830 + fl * %s" % _num(fh), 600, 1640, 80),
        f.box("Shutter", f"{_num(start + 1350)} + c * 2800",
              "830 + fl * %s" % _num(fh), 600, 1640, 80)])]), "#2c3e50",
        "Matte"))
    g.add(B.door(f, 0.0, b["color"]))
    # a full-width front porch: deck, steps, columns, railing and roof
    pd = 2600.0
    g.add(color(box("Porch deck", -w / 2, -d / 2 - pd, 0, w, pd, 650),
                "#9b8a74", "Matte"))
    g.add(color(box("Porch steps", -1200, -d / 2 - pd - 900, 0, 2400, 900,
                    350), "#9b8a74", "Matte"))
    ncol = max(3, int(w // 3000) + 1)
    cstep = (w - 400) / (ncol - 1)
    g.add(color(loop("Porch columns", "k", ncol, [
        box("Porch column", f"{_num(-w / 2)} + k * {_num(cstep)}",
            -d / 2 - pd + 50, 650, 250, 250, fh - 650)]), WHITE, "Matte"))
    g.add(color(group("Porch railing", [
        box("Rail", -w / 2, -d / 2 - pd + 100, 1500, w / 2 - 1200, 60, 80),
        box("Rail", 1200, -d / 2 - pd + 100, 1500, w / 2 - 1200, 60, 80),
        loop("Balusters", "k", int((w / 2 - 1200) // 150), [
            box("Baluster", f"{_num(-w / 2)} + k * 150", -d / 2 - pd + 110,
                650, 40, 40, 850),
            box("Baluster", f"1200 + k * 150", -d / 2 - pd + 110, 650, 40,
                40, 850)])]), WHITE, "Matte"))
    g.add(color(_hull("Porch roof", [
        box("Porch eave", -w / 2 - 300, -d / 2 - pd - 400, fh, w + 600, 1,
            150),
        box("Porch head", -w / 2 - 300, -d / 2 - 1, fh + 900, w + 600, 1,
            150)]), b["roof_color"], "Slate"))
    g.add(pitched_roof("gable", w, d, H, b["roof_color"], "Slate", b["color"],
                       "Render", chimney=True, dormer=True, pitch=38))
    g.add(color(box("Mailbox post", -w / 2 + 500, -d / 2 - pd - 4000, 0, 100,
                    100, 1100), WHITE, "Matte"))
    g.add(color(box("Mailbox", -w / 2 + 400, -d / 2 - pd - 4250, 1100, 300,
                    500, 250), "#2c3e50", "Metal"))
    return g


def indian_house(b):
    w, d, fh, n = b["w"], b["d"], b["floor_height"], b["floors"]
    H = n * fh
    g = group(b["name"])
    for p in _walls(b, -w / 2, -d / 2, w, d, H):
        g.add(p)
    g.add(color(box("Roof slab", -w / 2, -d / 2, H, w, d, 200), "#b9b6b0",
                "Concrete"))
    g.add(_parapet(w, d, H, 900, col=MARBLE))
    g.add(color(loop("Floor bands", "fl", n, [
        box("Band", -w / 2 - 120, -d / 2 - 120, f"{_num(fh - 200)} + fl * "
            f"{_num(fh)}", w + 240, d + 240, 250)]), MARBLE, "Stone"))
    # cusped arched windows with a marble frame
    wins, frames = [], []
    for side in ("front", "back", "left", "right"):
        f = Facade(side, -w / 2, -d / 2, w, d)
        cols = max(1, int(f.length // 3000))
        step = f.length / cols
        for fl in range(n):
            for c in range(cols):
                u = -f.length / 2 + step * (c + 0.5)
                if side == "front" and (fl == 0 and abs(u) < 1800 or
                                        fl == 1 and abs(u) < 2600):
                    continue
                z = 900 + fl * fh
                frames.append(f.box("Arch frame", u - 700, z - 120, 1400, 1900,
                                    50))
                wins.append(f.box("Window", u - 500, z, 1000, 1300, 70, 40))
                wins.append(f.box("Window head", u - 300, z + 1300, 600, 350,
                                  70, 40))
    g.add(color(group("Arch frames", frames), MARBLE, "Stone"))
    g.add(color(group("Windows", wins), "#1f4f5f", "Plastic"))
    g.add(color(arch_front("Doorway", 0, -d / 2, 0, 2200, 3000, 120, 140),
                MARBLE, "Stone"))
    g.add(color(arch_front("Door", 0, -d / 2, 0, 1600, 2700, 150, 40),
                TIMBER, "Matte"))
    g.add(color(box("Toran", -1100, -d / 2 - 170, 2750, 2200, 30, 150),
                "#e0782c", "Matte"))
    # a jharokha: a projecting balcony window with a little domed canopy
    if n >= 2:
        jw, jz = 2600.0, fh + 800
        g.add(color(group("Jharokha", [
            box("Jharokha base", -jw / 2, -d / 2 - 1100, jz - 300, jw, 1100,
                300),
            _hull("Jharokha corbel", [
                box("Corbel top", -jw / 2 + 200, -d / 2 - 900, jz - 300,
                    jw - 400, 900, 1),
                box("Corbel tip", -300, -d / 2 - 100, jz - 1400, 600, 100, 1)]),
            loop("Jharokha pillars", "k", 4, [
                cyl("Pillar", f"{_num(-jw / 2 + 150)} + k * {_num((jw - 300) / 3)}",
                    -d / 2 - 950, jz, 1800, 90, seg=8)]),
            box("Jharokha eave", -jw / 2 - 300, -d / 2 - 1400, jz + 1800,
                jw + 600, 1400, 200)]), MARBLE, "Stone"))
        g.add(color(dome("Jharokha dome", 0, -d / 2 - 700, jz + 2000, 1100,
                         0.9, onion=True, seg=16), MARBLE, "Stone"))
    # chhatris on the roof corners
    for sx, sy in ((-1, -1), (1, -1)):
        cx, cy, cr = sx * (w / 2 - 1300), sy * (d / 2 - 1300), 1000.0
        g.add(color(group("Chhatri", [
            box("Chhatri base", cx - cr, cy - cr, H + 200, 2 * cr, 2 * cr, 300),
            group("Chhatri pillars", [
                cyl("Pillar", cx + px * (cr - 150), cy + py * (cr - 150),
                    H + 500, 1600, 80, seg=8) for px in (-1, 1)
                for py in (-1, 1)]),
            box("Chhatri eave", cx - cr - 250, cy - cr - 250, H + 2100,
                2 * cr + 500, 2 * cr + 500, 180)]), MARBLE, "Stone"))
        g.add(color(dome("Chhatri dome", cx, cy, H + 2280, cr * 0.9, 1.0,
                         onion=True, seg=16), MARBLE, "Stone"))
        g.add(finial(cx, cy, H + 2280 + cr * 1.7, 700))
    return g


def pakistani_house(b):
    w, d, fh, n = b["w"], b["d"], b["floor_height"], b["floors"]
    H = n * fh
    setback = min(3500.0, d * 0.25)
    bd = d - setback                         # the house behind a front yard
    y0 = -d / 2 + setback
    g = group(b["name"])
    for p in _walls(b, -w / 2 + 300, y0, w - 600, bd, H):
        g.add(p)
    g.add(move(group("Windows", _windows(b, w - 600, bd, n, fh)), 0,
               y0 + bd / 2, 0, "Windows"))
    g.add(color(box("Roof slab", -w / 2 + 300, y0, H, w - 600, bd, 250),
                "#b9b6b0", "Concrete"))
    g.add(color(loop("Floor slabs", "fl", n - 1, [
        box("Slab edge", -w / 2 + 150, y0 - 150, f"{_num(fh)} + fl * "
            f"{_num(fh)}", w - 300, bd + 300, 220)]), "#dcd6cc", "Concrete"))
    # stone cladding on the ground floor front, a marble door surround
    g.add(color(box("Stone cladding", -w / 2 + 300, y0 - 60, 0, w - 600, 60,
                    fh), "#b8a888", "Stone"))
    g.add(color(box("Door surround", -1100, y0 - 150, 0, 2200, 90, 2900),
                MARBLE, "Stone"))
    g.add(color(box("Door", -800, y0 - 170, 0, 1600, 40, 2600), TIMBER,
                "Matte"))
    # a cantilevered car porch slab and first-floor balcony with a jaali
    g.add(color(box("Car porch slab", -w / 2 + 300, y0 - setback + 600, fh,
                    w * 0.5, setback - 600, 250), "#dcd6cc", "Concrete"))
    if n >= 2:
        bw = w * 0.4
        g.add(color(box("Balcony slab", w / 2 - 300 - bw, y0 - 1400, fh, bw,
                        1400, 200), "#dcd6cc", "Concrete"))
        g.add(color(loop("Balcony railing", "k", int(bw // 150), [
            box("Rail bar", f"{_num(w / 2 - 300 - bw)} + k * 150", y0 - 1400,
                fh + 200, 40, 40, 1000)]), METAL, "Metal"))
        g.add(color(box("Jaali panel", w / 2 - 300 - bw - 1500, y0 - 80,
                        fh + 400, 1200, 60, 2200), "#8a6240", "Matte"))
    # roof: parapet with steel railing, stair tower and water tank
    g.add(move(_parapet(w - 600, bd, H + 250, 1000, col=b["color"]), 0,
               y0 + bd / 2, 0, "Parapet"))
    g.add(color(box("Mumty (stair tower)", w / 2 - 300 - 3200, d / 2 - 3600,
                    H + 250, 3000, 3200, 2700), b["color"], "Render"))
    g.add(color(box("Tank stand", -w / 2 + 1500, d / 2 - 3000, H + 250, 1800,
                    1800, 900), "#b9b6b0", "Concrete"))
    g.add(color(cyl("Water tank", -w / 2 + 2400, d / 2 - 2100, H + 1150, 1500,
                    850, seg=16), "#1c1c1c", "Plastic"))
    # a boundary wall along the front with a steel gate
    gw = w * 0.45
    g.add(color(group("Boundary wall", [
        box("Front wall", -w / 2, -d / 2, 0, w / 2 - gw / 2, 250, 2100),
        box("Front wall", gw / 2, -d / 2, 0, w / 2 - gw / 2, 250, 2100),
        box("Side wall", -w / 2, -d / 2, 0, 250, setback, 2100),
        box("Side wall", w / 2 - 250, -d / 2, 0, 250, setback, 2100)]),
        b["color"], "Render"))
    g.add(color(group("Gate", [
        box("Gate leaf", -gw / 2, -d / 2 + 60, 0, gw, 80, 2000),
        loop("Gate bars", "k", int(gw // 200), [
            box("Gate bar", f"{_num(-gw / 2)} + k * 200", -d / 2 + 20, 200, 60,
                60, 1700)])]), "#2d3136", "Metal"))
    return g


BUILDERS = {"mosque": mosque, "arabic house": arabic_house,
            "chinese house": chinese_house, "japanese house": japanese_house,
            "american house": american_house, "indian house": indian_house,
            "pakistani house": pakistani_house}
