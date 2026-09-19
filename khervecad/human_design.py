"""A dressed, posed person from a few choices (Qt-free): the model behind
Library ▸ People & characters ▸ Human Builder, the character presets and
the MCP tools `list_character_options` / `build_character`.

A **spec** is a dict of choices — every key optional::

    {"name": "Doctor", "gender": "Female", "age": "Adult",
     "build": "Average", "stature": 1680, "skin": "Medium",
     "gesture": "Arms down", "stance": "Standing",
     "hair": "Bob", "hair_colour": "Black", "beard": "None",
     "top": "Long-sleeve shirt", "top_colour": "Light blue",
     "bottom": "Trousers", "bottom_colour": "Navy",
     "coat": "Lab coat", "coat_colour": "White",
     "shoes": "Shoes", "shoes_colour": "Black", "gloves": "None",
     "hat": "None", "hat_colour": "Navy", "glasses": "Glasses",
     "garments": [["hand", "#1d1e22", "Rubber"]]}

and `build(spec)` turns it into ordinary nodes: an `outfit` (garments
by body part — they follow any pose) round the `human`, and solids for
what stands off the body — hair, beard, hat, glasses, a skirt's or a
coat's flare, a hood, a cape — placed from the posed body's own
landmarks and part extents (`measure`), so they fit any height or
build. Colours are names from `COLOURS` / `SKIN_TONES` / `HAIR_COLOURS`
or ``#rrggbb``; ``garments`` rows (see `outfit`) are applied last, which
is how an assistant invents clothes the catalogue lacks.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import copy
import math

from . import outfit

# ----------------------------------------------------------- catalogues
GENDERS = {"Male": 1.0, "Female": 0.0, "Androgynous": 0.5}
AGES = {"Young adult": 0.0, "Adult": 0.3, "Middle-aged": 0.6,
        "Senior": 1.0}
BUILDS = {"Slim": -0.6, "Average": 0.0, "Stocky": 0.4, "Heavy": 0.85}
STATURE = {"Male": 1780.0, "Female": 1650.0, "Androgynous": 1720.0}

SKIN_TONES = {"Very light": "#f3d5c0", "Light": "#e8b995",
              "Medium": "#d19a73", "Olive": "#b98560", "Brown": "#8d5a3b",
              "Dark": "#5e3a24", "Zombie": "#8fa47a", "Alien blue":
              "#7fa6d9"}
HAIR_COLOURS = {"Black": "#15161a", "Dark brown": "#3b2a1e",
                "Brown": "#5a3a22", "Auburn": "#7b3a1e", "Red": "#a4452a",
                "Blonde": "#d8b36a", "Platinum": "#e6dcc0",
                "Grey": "#9a9a9a", "White": "#e8e8e8", "Blue": "#2f6db5",
                "Pink": "#e87fb0", "Green": "#3f9a5a"}
COLOURS = {"White": "#f2f2ee", "Black": "#1d1e22", "Navy": "#23324f",
           "Denim": "#3a5a8c", "Light blue": "#9cc3e6", "Royal blue":
           "#2f5fbf", "Grey": "#8a8f96", "Charcoal": "#3c3f44",
           "Beige": "#cdb892", "Khaki": "#a8996a", "Brown": "#6b4a30",
           "Tan": "#b98a5e", "Red": "#c0392b", "Burgundy": "#7a1f2b",
           "Coral": "#d6685f", "Orange": "#e67e22", "Yellow": "#f1c40f",
           "Hi-vis yellow": "#d7f000", "Green": "#2e8b57", "Olive":
           "#6b7a3a", "Teal": "#1f8a8a", "Pink": "#e8a0b4", "Purple":
           "#7d3fb0", "Cream": "#efe6d2", "Silver": "#c9ccd0", "Gold":
           "#d4af37"}

#: arm gestures: rows of the human rig's ``[bone, rx, ry, rz]`` (checked
#: from the front and the side: upperarm ry lowers / raises the arm,
#: rz swings it forward, lowerarm rx lifts the forearm)
GESTURES = {
    "Arms down": [["upperarm01.L", 12, 24, 0], ["upperarm01.R", 12, -24, 0]],
    "Relaxed (A-pose)": [],
    "T-pose": [["upperarm01.L", 0, -45, 0], ["upperarm01.R", 0, 45, 0]],
    "Hands on hips": [["upperarm01.L", 35, 5, 0], ["upperarm01.R", 35, -5, 0],
                      ["lowerarm01.L", 0, 70, 0], ["lowerarm01.R", 0, -70, 0]],
    "Waving": [["upperarm01.L", 12, 24, 0], ["upperarm01.R", 0, 70, 0],
               ["lowerarm01.R", 0, 60, 0]],
    "Cheering": [["upperarm01.L", 0, -100, 0], ["upperarm01.R", 0, 100, 0]],
    "Hands up": [["upperarm01.L", 0, 30, -20], ["upperarm01.R", 0, -30, 20],
                 ["lowerarm01.L", -95, 0, -35], ["lowerarm01.R", -95, 0, 35]],
    "Pointing": [["upperarm01.L", 12, 24, 0], ["upperarm01.R", 0, 45, 50]],
    "Arms forward": [["upperarm01.L", 0, -45, -50],
                     ["upperarm01.R", 0, 45, 50]],
    "Offering": [["upperarm01.L", -5, 32, -10], ["upperarm01.R", -5, -32, 10],
                 ["lowerarm01.L", -40, 0, -40], ["lowerarm01.R", -40, 0, 40]],
    "Thinking": [["upperarm01.L", 0, 30, -15], ["upperarm01.R", 12, -24, 0],
                 ["lowerarm01.L", -70, 0, -85]],
    "Hand raised": [["upperarm01.L", 12, 24, 0], ["upperarm01.R", 0, -10, 20],
                    ["lowerarm01.R", -120, 0, 40]],
    "Hands on chest": [["upperarm01.L", 0, 32, -15],
                       ["upperarm01.R", 0, -32, 15],
                       ["lowerarm01.L", -70, 0, -85],
                       ["lowerarm01.R", -70, 0, 85]],
}
#: leg stances (added to the gesture's rows)
STANCES = {
    "Standing": [],
    "Feet apart": [["upperleg01.L", 0, -4, 0], ["upperleg01.R", 0, 4, 0]],
    "Walking": [["upperleg01.L", 20, 0, 0], ["upperleg01.R", -20, 0, 0],
                ["lowerleg01.R", 20, 0, 0]],
    "Sitting": [["upperleg01.L", -85, 0, 0], ["upperleg01.R", -85, 0, 0],
                ["lowerleg01.L", 85, 0, 0], ["lowerleg01.R", 85, 0, 0]],
}

HAIR = ("Bald", "Buzz cut", "Short", "Quiff", "Side part", "Bob", "Long",
        "Ponytail", "Bun", "Afro", "Mohawk")
BEARDS = ("None", "Moustache", "Goatee", "Beard", "Full beard")
GLASSES = ("None", "Glasses", "Sunglasses")
HATS = ("None", "Baseball cap", "Beanie", "Top hat", "Hard hat",
        "Chef hat", "Sun hat", "Beret")
GLOVES = ("None", "Gloves")

#: tops: parts covered, default colour, and extras ("skirt": a dress's
#: skirt length, "hood")
TOPS = {
    "Bare chest": dict(parts=[], colour="White"),
    "T-shirt": dict(parts=["torso", "shoulder"], colour="White"),
    "Polo shirt": dict(parts=["torso", "shoulder"], colour="Navy"),
    "Tank top": dict(parts=["torso"], colour="Grey"),
    "Long-sleeve shirt": dict(parts=["torso", "arm"], colour="Light blue"),
    "Sweater": dict(parts=["torso", "arm"], colour="Burgundy"),
    "Hoodie": dict(parts=["torso", "arm"], colour="Grey", hood=True),
    "Turtleneck": dict(parts=["torso", "arm", "neck"], colour="Black"),
    "Blouse": dict(parts=["torso", "shoulder", "upper_arm"],
                   colour="Cream"),
    "Crop top": dict(parts=["chest"], colour="Pink"),
    "Swimsuit": dict(parts=["torso", "hips"], colour="Teal"),
    "Dress": dict(parts=["torso", "hips", "shoulder"], colour="Red",
                  skirt="Knee"),
    "Long dress": dict(parts=["torso", "hips", "shoulder"],
                       colour="Burgundy", skirt="Long"),
}
BOTTOMS = {
    "Underwear": dict(parts=["hips"], colour="White"),
    "Jeans": dict(parts=["hips", "leg"], colour="Denim"),
    "Trousers": dict(parts=["hips", "leg"], colour="Charcoal"),
    "Chinos": dict(parts=["hips", "leg"], colour="Khaki"),
    "Leggings": dict(parts=["hips", "leg"], colour="Black"),
    "Joggers": dict(parts=["hips", "leg"], colour="Grey"),
    "Shorts": dict(parts=["hips", "upper_thigh"], colour="Khaki"),
    "Knee shorts": dict(parts=["hips", "upper_thigh", "thigh"],
                        colour="Olive"),
    "Mini skirt": dict(parts=["hips", "upper_thigh"], colour="Black",
                       skirt="Mini"),
    "Skirt": dict(parts=["hips", "upper_thigh"], colour="Navy",
                  skirt="Knee"),
    "Long skirt": dict(parts=["hips", "upper_thigh", "thigh"],
                       colour="Olive", skirt="Long"),
}
COATS = {
    "None": dict(parts=[], colour="Charcoal"),
    "Lab coat": dict(parts=["torso", "arm"], colour="White",
                     tails="Knee"),
    "Trench coat": dict(parts=["torso", "arm"], colour="Beige",
                        tails="Knee"),
    "Raincoat": dict(parts=["torso", "arm"], colour="Yellow",
                     tails="Thigh"),
    "Suit jacket": dict(parts=["torso", "arm"], colour="Navy",
                        tails="Hip"),
    "Denim jacket": dict(parts=["torso", "arm"], colour="Denim"),
    "Leather jacket": dict(parts=["torso", "arm"], colour="Black"),
    "Puffer jacket": dict(parts=["torso", "arm"], colour="Red",
                          tails="Hip"),
    "Waistcoat": dict(parts=["torso"], colour="Black"),
    "Hi-vis vest": dict(parts=["torso"], colour="Hi-vis yellow"),
    "Cape": dict(parts=[], colour="Red", cape=True),
}
SHOES = {
    "Barefoot": dict(parts=[], colour="Black"),
    "Trainers": dict(parts=["foot"], colour="White"),
    "Shoes": dict(parts=["foot"], colour="Black"),
    "Sandals": dict(parts=["foot"], colour="Tan"),
    "Boots": dict(parts=["foot", "ankle"], colour="Brown"),
    "Knee boots": dict(parts=["foot", "ankle", "shin"], colour="Black"),
    "Socks": dict(parts=["foot", "ankle"], colour="White"),
}

DEFAULTS = {
    "name": "Person", "gender": "Male", "age": "Adult", "build": "Average",
    "stature": 0.0, "skin": "Light", "gesture": "Arms down",
    "stance": "Standing", "hair": "Short", "hair_colour": "Brown",
    "beard": "None", "top": "T-shirt", "top_colour": "",
    "bottom": "Jeans", "bottom_colour": "", "coat": "None",
    "coat_colour": "", "shoes": "Trainers", "shoes_colour": "",
    "gloves": "None", "gloves_colour": "Black", "hat": "None",
    "hat_colour": "Navy", "glasses": "None", "garments": [],
}
#: which catalogue each choice comes from (the builder's combo boxes)
CHOICES = {"gender": GENDERS, "age": AGES, "build": BUILDS,
           "skin": SKIN_TONES, "gesture": GESTURES, "stance": STANCES,
           "hair": HAIR, "hair_colour": HAIR_COLOURS, "beard": BEARDS,
           "top": TOPS, "bottom": BOTTOMS, "coat": COATS, "shoes": SHOES,
           "gloves": GLOVES, "hat": HATS, "glasses": GLASSES}
COLOUR_KEYS = ("top_colour", "bottom_colour", "coat_colour",
               "shoes_colour", "gloves_colour", "hat_colour")


class SpecError(ValueError):
    pass


def colour(value, table=COLOURS, fallback="#888888") -> str:
    """A catalogue name or ``#rrggbb`` as ``#rrggbb``."""
    value = str(value or "").strip()
    if value.startswith("#") and len(value) == 7:
        return value
    for key, hexcol in table.items():
        if key.lower() == value.lower():
            return hexcol
    for key, hexcol in COLOURS.items():
        if key.lower() == value.lower():
            return hexcol
    return fallback


def _pick(value, table, key):
    names = list(table)
    for name in names:
        if name.lower() == str(value).strip().lower():
            return name
    raise SpecError(f"{key}: '{value}' is not one of " + ", ".join(names))


def normalise(spec=None) -> dict:
    """*spec* over the defaults (a ``preset`` name first), every choice
    checked against its catalogue."""
    spec = dict(spec or {})
    out = copy.deepcopy(DEFAULTS)
    preset = spec.pop("preset", None)
    if preset:
        name = _pick(preset, PRESETS, "preset")
        out.update(copy.deepcopy(PRESETS[name]))
        out.setdefault("name", name)
    out.update({k: v for k, v in spec.items() if v is not None})
    unknown = set(out) - set(DEFAULTS)
    if unknown:
        raise SpecError("unknown keys: " + ", ".join(sorted(unknown))
                        + " (see list_character_options)")
    for key, table in CHOICES.items():
        if key in ("skin", "hair_colour") and str(out[key]).startswith("#"):
            continue
        out[key] = _pick(out[key], table, key)
    for row in out.get("garments") or []:
        if not isinstance(row, (list, tuple)) or len(row) < 2 \
                or not outfit.known(row[0]):
            raise SpecError(f"garment {row!r}: [part, colour, material] "
                            "with a part from list_character_options")
    return out


# --------------------------------------------------------------- body
def body_args(spec) -> dict:
    """The human node's parameters for a normalised *spec*."""
    stature = float(spec.get("stature") or 0.0) or STATURE[spec["gender"]]
    if spec["age"] == "Senior":
        stature -= 40.0
    pose = [list(r) for r in GESTURES[spec["gesture"]]]
    pose += [list(r) for r in STANCES[spec["stance"]]]
    return dict(gender=GENDERS[spec["gender"]], age=AGES[spec["age"]],
                weight=BUILDS[spec["build"]],
                height=0.2 if spec["gender"] != "Female" else 0.1,
                stature=stature, targets=[], warp=[], warp_radius=45.0,
                pose=pose)


def garment_rows(spec) -> list:
    """The outfit rows: bottom, top, coat, shoes, gloves, then the
    spec's own ``garments``."""
    rows = []

    def add(parts, hexcol, material="Default"):
        rows.extend([p, hexcol, material] for p in parts)
    top = TOPS[spec["top"]]
    if "skirt" not in top:
        bottom = BOTTOMS[spec["bottom"]]
        add(bottom["parts"], colour(spec["bottom_colour"] or
                                    bottom["colour"]))
        if bottom.get("skirt") and spec["stance"] == "Sitting":
            add(["upper_thigh", "thigh"], colour(spec["bottom_colour"]
                                                 or bottom["colour"]))
    else:
        add(["hips"], "#f2f2ee")
    add(top["parts"], colour(spec["top_colour"] or top["colour"]))
    coat = COATS[spec["coat"]]
    add(coat["parts"], colour(spec["coat_colour"] or coat["colour"]),
        "Matte")
    shoes = SHOES[spec["shoes"]]
    add(shoes["parts"], colour(spec["shoes_colour"] or shoes["colour"]),
        "Rubber" if spec["shoes"] in ("Trainers", "Boots", "Knee boots")
        else "Default")
    if spec["gloves"] != "None":
        add(["hand"], colour(spec["gloves_colour"]), "Rubber")
    rows.extend([list(r[:2]) + [r[2] if len(r) > 2 else "Default"]
                 for r in spec.get("garments") or []])
    return rows


def measure(args) -> dict:
    """What the loose pieces are placed by: the posed body's face
    landmarks and each part's extents (and a slice at the waist)."""
    from . import human
    pts = human.points(**{k: v for k, v in args.items()})
    labels = outfit.vertex_parts()
    box = {}
    for i, p in enumerate(pts[:len(labels)]):
        part = labels[i].split(".")[0]
        b = box.get(part)
        if b is None:
            box[part] = [list(p), list(p)]
        else:
            for k in range(3):
                b[0][k] = min(b[0][k], p[k])
                b[1][k] = max(b[1][k], p[k])
    marks = {name: list(pts[i]) for name, i in human.landmarks().items()
             if 0 <= i < len(pts)}
    waist_z = box["hips"][1][2] - 15.0
    ring = [p for i, p in enumerate(pts[:len(labels)])
            if labels[i].split(".")[0] in ("hips", "waist", "upper_thigh")
            and abs(p[2] - (waist_z - 60.0)) < 60.0]
    half_x = max((abs(p[0]) for p in ring), default=160.0)
    ys = [p[1] for p in ring] or [-100.0, 100.0]
    belt = [p for i, p in enumerate(pts[:len(labels)])
            if labels[i].split(".")[0] in ("hips", "waist")
            and abs(p[2] - waist_z) < 25.0]
    waist_half = max((abs(p[0]) for p in belt), default=half_x * 0.9)
    return dict(box=box, marks=marks, waist_z=waist_z, hip_half=half_x,
                waist_half=waist_half,
                hip_y=(min(ys) + max(ys)) / 2.0,
                hip_depth=(max(ys) - min(ys)) / 2.0,
                knee_z=box["thigh"][0][2] + 40.0,
                ankle_z=box["ankle"][0][2] + 40.0,
                shoulder_z=box["chest"][1][2],
                back_y=box["chest"][1][1],
                shoulder_half=max(abs(box["shoulder"][0][0]),
                                  abs(box["shoulder"][1][0])))


# ------------------------------------------------------ loose pieces
def _f(v) -> str:
    return f"{v:.1f}"


def _v(p) -> str:
    return "[" + ", ".join(_f(c) for c in p) + "]"


def _ell(c, r) -> str:
    return f"kcad_ellipsoid(c = {_v(c)}, r = {_v(r)});"


def _head(m):
    k = m["marks"]
    ear = k["ear_l"]
    top = k["head_top"][2]
    fore = k["forehead"]
    H = max(top - ear[2], 60.0)
    return dict(ex=abs(ear[0]), ey=ear[1], ez=ear[2], top=top, H=H,
                s=H / 118.0, fy=fore[1], fz=fore[2], depth=ear[1] - fore[1],
                chin=k["chin"], eye_l=k["eye_l"], eye_r=k["eye_r"],
                bridge=k["nose_bridge"], mouth_l=k["mouth_l"],
                mouth_r=k["mouth_r"], jaw_l=k["jaw_l"], jaw_r=k["jaw_r"],
                lip=k["lip_bottom"], lip_top=k["lip_top"],
                nose=k["nose_tip"])


def hair_code(style, hexcol, m) -> str:
    if style == "Bald":
        return ""
    h = _head(m)
    ex, ey, ez, top, H, s = h["ex"], h["ey"], h["ez"], h["top"], h["H"], h["s"]
    d = h["depth"]
    cap = _ell([0, ey - s, ez + 0.42 * H], [ex * 1.05, d * 1.04, 0.68 * H])
    front = _ell([0, h["fy"] + 42 * s, top - 30 * s], [ex * 0.82, 48 * s,
                                                        34 * s])
    parts = {"Buzz cut": [_ell([0, ey, ez + 0.4 * H],
                               [ex * 1.0, d * 0.99, 0.63 * H])],
             "Short": [cap, front],
             "Quiff": [cap, _ell([0, h["fy"] + 40 * s, top - 14 * s],
                                 [ex * 0.8, 58 * s, 46 * s])],
             "Side part": [cap, _ell([28 * s, h["fy"] + 45 * s, top - 26 * s],
                                     [ex * 0.75, 50 * s, 36 * s])],
             "Afro": [_ell([0, ey + 25 * s, ez + 0.45 * H],
                           [ex * 1.5, d * 1.08 + 10 * s, 0.95 * H])],
             "Mohawk": [f"hull() {{ {_ell([0, h['fy'] + 40 * s, top - 4 * s], [14 * s, 30 * s, 36 * s])} "
                        f"{_ell([0, ey + 62 * s, ez + 40 * s], [14 * s, 30 * s, 36 * s])} }}"],
             }
    shoulder = m["shoulder_z"]
    chin_z = h["chin"][2]
    if style == "Bob":
        lobes = []
        for sx in (1, -1):
            lobes.append(f"hull() {{ {_ell([sx * ex * 0.88, ey, ez + 25 * s], [26 * s, 70 * s, 55 * s])} "
                         f"{_ell([sx * ex * 0.92, ey + 6 * s, chin_z + 8 * s], [22 * s, 58 * s, 22 * s])} }}")
        lobes.append(f"hull() {{ {_ell([0, ey + 45 * s, ez + 30 * s], [ex * 0.9, 45 * s, 55 * s])} "
                     f"{_ell([0, ey + 48 * s, chin_z + 5 * s], [ex * 0.95, 40 * s, 24 * s])} }}")
        parts["Bob"] = [cap, front] + lobes
    if style == "Long":
        parts["Long"] = [cap, front,
                         f"hull() {{ {_ell([0, ey + 15 * s, ez + 15 * s], [ex * 0.95, 70 * s, 60 * s])} "
                         f"{_ell([0, m['back_y'] + 8 * s, shoulder - 170 * s], [ex * 1.05, 40 * s, 40 * s])} }}"]
    if style == "Ponytail":
        tie = [0, ey + 78 * s, ez + 25 * s]
        parts["Ponytail"] = [cap, front, _ell(tie, [20 * s, 20 * s, 20 * s]),
                             f"hull() {{ {_ell([tie[0], tie[1] + 8 * s, tie[2] - 10 * s], [24 * s, 22 * s, 24 * s])} "
                             f"{_ell([0, m['back_y'] + 20 * s, shoulder - 90 * s], [16 * s, 16 * s, 26 * s])} }}"]
    if style == "Bun":
        parts["Bun"] = [cap, front, _ell([0, ey + 55 * s, top - 18 * s],
                                         [40 * s, 38 * s, 36 * s])]
    body = "\n  ".join(parts.get(style, [cap, front]))
    return f'color("{hexcol}") union() {{  // Hair\n  {body}\n}}\n'


def beard_code(style, hexcol, m) -> str:
    if style == "None":
        return ""
    h = _head(m)
    s = h["s"]
    chin, jl, jr = h["chin"], h["jaw_l"], h["jaw_r"]
    ml, mr, lip, lt = h["mouth_l"], h["mouth_r"], h["lip"], h["lip_top"]
    z = lt[2] + 5 * s
    tache = (f"kcad_capsule(a = {_v([ml[0] + 2 * s, lt[1] + 2 * s, z])}, "
             f"b = {_v([mr[0] - 2 * s, lt[1] + 2 * s, z])}, r = {_f(5 * s)});")
    goatee = _ell([chin[0], chin[1] - 4 * s, chin[2] + 8 * s],
                  [22 * s, 16 * s, 24 * s])
    full = ("hull() { " + " ".join(_ell(p, [r * s] * 3) for p, r in (
        ([jl[0] - 4 * s, jl[1] - 6 * s, jl[2] - 4 * s], 16),
        ([jr[0] + 4 * s, jr[1] - 6 * s, jr[2] - 4 * s], 16),
        ([chin[0], chin[1] - 8 * s, chin[2] - 6 * s], 24),
        ([lip[0], lip[1] - 3 * s, lip[2] - 12 * s], 12))) + " }")
    pieces = {"Moustache": [tache], "Goatee": [tache, goatee],
              "Beard": [full], "Full beard": [full, tache]}[style]
    return (f'color("{hexcol}") union() {{  // Beard\n  '
            + "\n  ".join(pieces) + "\n}\n")


def hat_code(style, hexcol, m) -> str:
    if style == "None":
        return ""
    h = _head(m)
    ex, ey, ez, top, H, s, d = (h["ex"], h["ey"], h["ez"], h["top"], h["H"],
                                h["s"], h["depth"])
    crown = _ell([0, ey - 4 * s, ez + 0.55 * H],
                 [ex * 1.1, d * 1.1, 0.6 * H])
    pieces = {
        "Baseball cap": [crown, f"translate({_v([0, h['fy'] - 25 * s, ez + 0.24 * H])}) "
                         f"scale([1, 1.45, 1]) cylinder(h = {_f(5 * s)}, r = {_f(ex * 0.72)});"],
        "Beanie": [_ell([0, ey - 2 * s, ez + 0.5 * H],
                        [ex * 1.12, d * 1.1, 0.72 * H])],
        "Top hat": [f"translate({_v([0, ey - 10 * s, top - 0.15 * H])}) "
                    f"scale([1, {_f(d / ex)}, 1]) cylinder(h = {_f(0.95 * H)}, r1 = {_f(ex * 0.95)}, r2 = {_f(ex * 1.0)});",
                    f"translate({_v([0, ey - 10 * s, top - 0.15 * H])}) "
                    f"scale([1, {_f(d / ex)}, 1]) cylinder(h = {_f(5 * s)}, r = {_f(ex * 1.45)});"],
        "Hard hat": [crown, f"translate({_v([0, ey - 12 * s, ez + 0.3 * H])}) "
                     f"scale([1, {_f(d / ex)}, 1]) cylinder(h = {_f(6 * s)}, r = {_f(ex * 1.32)});"],
        "Chef hat": [f"translate({_v([0, ey - 10 * s, top - 0.42 * H])}) "
                     f"cylinder(h = {_f(0.75 * H)}, r = {_f(ex * 1.05)});",
                     _ell([0, ey - 10 * s, top + 0.4 * H],
                          [ex * 1.3, ex * 1.3, 0.42 * H])],
        "Sun hat": [crown, f"translate({_v([0, ey - 10 * s, ez + 0.32 * H])}) "
                    f"cylinder(h = {_f(4 * s)}, r = {_f(ex * 2.1)});"],
        "Beret": [f"translate({_v([12 * s, ey - 10 * s, top - 0.12 * H])}) rotate([0, -12, 0]) "
                  + _ell([0, 0, 0], [ex * 1.25, d * 1.1, 0.3 * H])],
    }[style]
    return (f'color("{hexcol}") union() {{  // Hat\n  '
            + "\n  ".join(pieces) + "\n}\n")


def glasses_code(style, m) -> str:
    if style == "None":
        return ""
    h = _head(m)
    s = h["s"]
    y = h["bridge"][1] - 6 * s
    r = 19 * s
    lens = ("#20242a", 0.85) if style == "Sunglasses" else ("#cfe8ff", 0.3)
    rims, lenses = [], []
    for eye in (h["eye_l"], h["eye_r"]):
        c = [eye[0], y, eye[2] - 2 * s]
        rims.append(f"translate({_v(c)}) rotate([90, 0, 0]) rotate_extrude($fn = 24) "
                    f"translate([{_f(r)}, 0]) square([{_f(2.4 * s)}, {_f(3 * s)}]);")
        lenses.append(f"translate({_v(c)}) rotate([90, 0, 0]) cylinder(h = {_f(1)}, r = {_f(r)}, $fn = 24);")
    el, er, ex = h["eye_l"], h["eye_r"], h["ex"]
    arms = [f"kcad_capsule(a = {_v([el[0] - r * 0.7, y, el[2]])}, b = {_v([er[0] + r * 0.7, y, er[2]])}, r = {_f(1.6 * s)});"]
    for sx, eye in ((1, el), (-1, er)):
        arms.append(f"kcad_capsule(a = {_v([eye[0] + sx * (r + 2 * s), y, eye[2]])}, "
                    f"b = {_v([sx * ex * 0.98, h['ey'] + 4 * s, h['ez'] + 8 * s])}, r = {_f(1.6 * s)});")
    return ('color("#1d1e22") union() {  // Glasses frame\n  '
            + "\n  ".join(rims + arms) + "\n}\n"
            + f'color("{lens[0]}", {lens[1]}) union() {{  // Lenses\n  '
            + "\n  ".join(lenses) + "\n}\n")


def _flare(m, bottom_z, flare, hexcol, label, top_z=None, grow=1.04):
    """A skirt / coat-tail cone from the waist down to *bottom_z*: its
    top hugs the waist, and it opens out past the hips."""
    top_z = m["waist_z"] if top_z is None else top_z
    rt = m["waist_half"] * grow
    rb = max(m["hip_half"] * grow, rt) * flare
    depth = max(m["hip_depth"] / max(m["hip_half"], 1.0), 0.5) * grow
    h = top_z - bottom_z
    if h <= 20:
        return ""
    return (f'color("{hexcol}") translate({_v([0, m["hip_y"], bottom_z])}) '
            f"scale([1, {depth:.3f}, 1]) cylinder(h = {_f(h)}, r1 = {_f(rb)}, "
            f"r2 = {_f(rt)}, $fn = 48);  // {label}\n")


def skirt_code(length, hexcol, m) -> str:
    waist, knee, ankle = m["waist_z"], m["knee_z"], m["ankle_z"]
    bottom = {"Mini": waist - (waist - knee) * 0.45,
              "Knee": knee + 20.0,
              "Long": ankle + 30.0}[length]
    flare = {"Mini": 1.2, "Knee": 1.35, "Long": 1.55}[length]
    return _flare(m, bottom, flare, hexcol, f"{length} skirt")


def tails_code(length, hexcol, m) -> str:
    """A coat below the waist: a flaring shell OPEN AT THE FRONT (a
    300° revolve of a slanted wall), so the legs show between its
    edges — a closed cone reads as a dress."""
    waist, knee = m["waist_z"], m["knee_z"]
    bottom = {"Hip": waist - (waist - knee) * 0.3,
              "Thigh": waist - (waist - knee) * 0.7,
              "Knee": knee - 30.0}[length]
    h = waist - bottom
    rt = m["waist_half"] * 1.05
    rb = m["hip_half"] * 1.3
    depth = max(m["hip_depth"] / max(m["hip_half"], 1.0), 0.5) * 1.09
    wall = [[rb, 0], [rb + 5, 0], [rt + 5, h], [rt, h]]
    return (f'color("{hexcol}") translate({_v([0, m["hip_y"], bottom])}) '
            f"scale([1, {depth:.3f}, 1]) rotate([0, 0, 300]) "
            f"rotate_extrude(angle = 300, $fn = 48) polygon(points = "
            f"[{', '.join(_v(p) for p in wall)}]);  // Coat tails\n")


def hood_code(hexcol, m) -> str:
    h = _head(m)
    s = h["s"]
    return (f'color("{hexcol}") ' + _ell(
        [0, m["back_y"] - 6 * s, m["shoulder_z"] + 18 * s],
        [h["ex"] * 1.15, 42 * s, 52 * s]) + "  // Hood\n")


def cape_code(hexcol, m) -> str:
    top_z = m["shoulder_z"] - 30.0
    top_y = m["back_y"] - 8.0
    bottom_z = m["knee_z"] - 180.0
    low_y = top_y + 220.0
    length = math.hypot(top_z - bottom_z, low_y - top_y)
    tilt = math.degrees(math.atan2(low_y - top_y, top_z - bottom_z))
    tw, bw = m["shoulder_half"] * 1.6, m["shoulder_half"] * 3.6
    pts = [[-tw / 2, 0], [tw / 2, 0], [bw / 2, -length], [-bw / 2, -length]]
    return (f'color("{hexcol}") translate({_v([0, top_y, top_z])}) '
            f"rotate([{90 + tilt:.2f}, 0, 0]) translate([0, 0, -4]) "
            f"linear_extrude(height = 8) polygon(points = "
            f"[{', '.join(_v(p) for p in pts)}]);  // Cape\n")


# --------------------------------------------------------------- build
def build(spec=None):
    """The person as ONE node: the dressed body and its loose pieces."""
    from . import scadparse
    from .model import CadNode
    spec = normalise(spec)
    args = body_args(spec)
    body = CadNode("human", "Body", copy.deepcopy(args))
    dress = CadNode("outfit", "Outfit", dict(
        skin=colour(spec["skin"], SKIN_TONES), garments=garment_rows(spec)))
    dress.add(body)
    m = measure({k: args[k] for k in ("gender", "age", "weight", "height",
                                       "stature", "targets", "pose")})
    hair_hex = colour(spec["hair_colour"], HAIR_COLOURS)
    code = hair_code(spec["hair"], hair_hex, m) \
        if spec["hat"] in ("None", "Sun hat", "Baseball cap") \
        or spec["hair"] in ("Long", "Ponytail", "Bob") else ""
    code += beard_code(spec["beard"], hair_hex, m)
    code += hat_code(spec["hat"], colour(spec["hat_colour"]), m)
    code += glasses_code(spec["glasses"], m)
    top = TOPS[spec["top"]]
    sitting = spec["stance"] == "Sitting"
    if top.get("skirt") and not sitting:
        code += skirt_code(top["skirt"], colour(spec["top_colour"]
                                               or top["colour"]), m)
    elif not top.get("skirt"):
        bottom = BOTTOMS[spec["bottom"]]
        if bottom.get("skirt") and not sitting:
            code += skirt_code(bottom["skirt"], colour(
                spec["bottom_colour"] or bottom["colour"]), m)
    if top.get("hood") and spec["coat"] in ("None", "Waistcoat",
                                            "Hi-vis vest"):
        code += hood_code(colour(spec["top_colour"] or top["colour"]), m)
    coat = COATS[spec["coat"]]
    coat_hex = colour(spec["coat_colour"] or coat["colour"])
    if coat.get("tails") and not sitting:
        code += tails_code(coat["tails"], coat_hex, m)
    if coat.get("cape"):
        code += cape_code(coat_hex, m)
    group = CadNode("union", spec["name"] or "Person")
    group.add(dress)
    if code:
        root, _warnings = scadparse.parse_scad(code)
        for child in list(root.children):
            group.add(child)
    return group


def insert(model, spec=None, x=None, y=0.0, rz=0.0, replace=None):
    """Add the person to *model* as one Object (to the right of what is
    there, or where *replace* stood) carrying its spec in
    ``params["character"]``, so the Human Builder can update it."""
    spec = normalise(spec)
    node = build(spec)
    if replace is not None:
        x = float(replace.params.get("x", 0.0))
        y = float(replace.params.get("y", 0.0))
        rz = float(replace.params.get("rz", 0.0))
        model.remove_node(replace)
    elif x is None:
        x = free_x(model)
    model.root.add(node)
    part = model.enclose_as_part(node, spec["name"] or "Person")
    part.params.update(x=float(x), y=float(y), rz=float(rz))
    part.params["character"] = spec
    model.structure_changed.emit()
    return part


def free_x(model) -> float:
    from . import mesh
    tris = mesh.tessellate(model.root, fn=8)
    if not tris:
        return 0.0
    return max(p[0] for t in tris for p in t) + 800.0


# ------------------------------------------------------------- presets
def _p(name, **kw):
    kw["name"] = name
    return kw


PRESETS = {p["name"]: p for p in (
    _p("Casual man", gender="Male", top="Polo shirt", bottom="Jeans",
       shoes="Shoes", shoes_colour="Brown", hair="Short",
       hair_colour="Dark brown"),
    _p("Casual woman", gender="Female", top="T-shirt", top_colour="Coral",
       bottom="Trousers", bottom_colour="Black", shoes="Shoes",
       hair="Long", hair_colour="Brown"),
    _p("Office worker", gender="Male", top="Long-sleeve shirt",
       bottom="Trousers", shoes="Shoes", hair="Side part",
       hair_colour="Black"),
    _p("Businesswoman", gender="Female", top="Blouse", bottom="Skirt",
       coat="Suit jacket", shoes="Shoes", hair="Bob", hair_colour="Black",
       gesture="Hands on hips", stance="Feet apart"),
    _p("Doctor", gender="Female", age="Middle-aged", top="Long-sleeve shirt",
       top_colour="Light blue", bottom="Trousers", bottom_colour="Navy",
       coat="Lab coat", shoes="Shoes", hair="Ponytail",
       hair_colour="Auburn", glasses="Glasses", gesture="Offering"),
    _p("Scientist", gender="Male", age="Adult", top="Sweater",
       top_colour="Teal", bottom="Chinos", coat="Lab coat", shoes="Shoes",
       hair="Short", hair_colour="Black", glasses="Glasses",
       gesture="Thinking", skin="Brown"),
    _p("Chef", gender="Male", top="Long-sleeve shirt", top_colour="White",
       bottom="Trousers", bottom_colour="Black", shoes="Shoes", hat="Chef hat",
       hat_colour="White", beard="Moustache", hair_colour="Black",
       gesture="Hands on hips", skin="Olive"),
    _p("Construction worker", gender="Male", build="Stocky", top="T-shirt",
       top_colour="Navy", coat="Hi-vis vest", bottom="Jeans", shoes="Boots",
       gloves="Gloves", gloves_colour="Tan", hat="Hard hat",
       hat_colour="Yellow", beard="Beard", hair_colour="Brown",
       gesture="Hands on hips", stance="Feet apart", skin="Medium"),
    _p("Runner", gender="Female", age="Young adult", build="Slim",
       top="Tank top", top_colour="Pink", bottom="Shorts",
       bottom_colour="Black", shoes="Trainers", hair="Ponytail",
       hair_colour="Blonde", stance="Walking", gesture="Arms down"),
    _p("Tourist", gender="Male", age="Middle-aged", build="Stocky",
       top="T-shirt", top_colour="Orange", bottom="Knee shorts",
       bottom_colour="Beige", shoes="Sandals", hat="Sun hat",
       hat_colour="Cream", glasses="Sunglasses", gesture="Pointing",
       hair_colour="Grey"),
    _p("Student", gender="Female", age="Young adult", top="Hoodie",
       top_colour="Purple", bottom="Jeans", shoes="Trainers", hair="Afro",
       hair_colour="Black", skin="Brown", gesture="Hand raised"),
    _p("Grandmother", gender="Female", age="Senior", build="Stocky",
       top="Sweater", top_colour="Pink", bottom="Long skirt",
       bottom_colour="Grey", shoes="Shoes", hair="Bun", hair_colour="White",
       glasses="Glasses", gesture="Hands on chest"),
    _p("Grandfather", gender="Male", age="Senior", top="Long-sleeve shirt",
       top_colour="Cream", coat="Waistcoat", coat_colour="Brown",
       bottom="Trousers", bottom_colour="Grey", shoes="Shoes",
       hair="Buzz cut", hair_colour="White", beard="Full beard",
       glasses="Glasses"),
    _p("Swimmer", gender="Female", build="Slim", top="Swimsuit",
       top_colour="Royal blue", bottom="Underwear",
       bottom_colour="Royal blue", shoes="Barefoot", hair="Buzz cut",
       hair_colour="Dark brown", gesture="Cheering", skin="Olive"),
    _p("Rock musician", gender="Male", age="Young adult", build="Slim",
       top="T-shirt", top_colour="Black", coat="Leather jacket",
       bottom="Jeans", bottom_colour="Black", shoes="Boots",
       shoes_colour="Black", hair="Long", hair_colour="Black",
       gesture="Hands up"),
    _p("Farmer", gender="Male", age="Middle-aged", top="Long-sleeve shirt",
       top_colour="Red", bottom="Jeans", shoes="Boots", hat="Sun hat",
       hat_colour="Tan", beard="Beard", hair_colour="Brown",
       gesture="Hands on hips", skin="Medium"),
    _p("Teacher", gender="Female", age="Middle-aged", top="Blouse",
       top_colour="Green", bottom="Trousers", bottom_colour="Grey",
       shoes="Shoes", hair="Bob", hair_colour="Red", glasses="Glasses",
       gesture="Pointing"),
    _p("Waiter", gender="Male", top="Long-sleeve shirt", top_colour="White",
       coat="Waistcoat", bottom="Trousers", bottom_colour="Black",
       shoes="Shoes", hair="Quiff", hair_colour="Black",
       gesture="Offering", skin="Dark"),
    _p("Hiker", gender="Female", age="Adult", top="Long-sleeve shirt",
       top_colour="Olive", coat="Puffer jacket", coat_colour="Orange",
       bottom="Trousers", bottom_colour="Khaki", shoes="Boots",
       hat="Beanie", hat_colour="Teal", hair="Ponytail",
       hair_colour="Brown", stance="Walking"),
    _p("Party guest", gender="Female", age="Young adult", top="Long dress",
       top_colour="Red", shoes="Shoes", hair="Long", hair_colour="Blonde",
       gesture="Waving"),
    _p("Office worker (sitting)", gender="Female", top="Blouse",
       top_colour="White", bottom="Skirt", bottom_colour="Charcoal",
       shoes="Shoes", hair="Bob", hair_colour="Dark brown",
       stance="Sitting", skin="Olive"),
    _p("Dancer", gender="Female", age="Young adult", build="Slim",
       top="Swimsuit", top_colour="Purple", bottom="Leggings",
       shoes="Barefoot", hair="Bun", hair_colour="Black", gesture="T-pose",
       skin="Brown"),
    _p("Zombie", gender="Male", top="T-shirt", top_colour="Grey",
       bottom="Jeans", bottom_colour="Charcoal", shoes="Barefoot",
       hair="Short", hair_colour="Black", skin="Zombie",
       gesture="Arms forward", stance="Walking",
       garments=[["forearm.R", "#8fa47a", "Default"]]),
    _p("Rain walker", gender="Male", top="Sweater", coat="Raincoat",
       bottom="Jeans", shoes="Knee boots", shoes_colour="Green",
       hair="Short", hair_colour="Auburn", stance="Walking"),
    _p("Security guard", gender="Male", build="Stocky",
       top="Long-sleeve shirt", top_colour="Navy", bottom="Trousers",
       bottom_colour="Navy", shoes="Boots", shoes_colour="Black",
       hat="Baseball cap", hat_colour="Navy", hair="Buzz cut",
       hair_colour="Black", gesture="Hands on chest", skin="Dark"),
    _p("Caped hero", gender="Male", build="Average", top="Long-sleeve shirt",
       top_colour="Royal blue", bottom="Leggings", bottom_colour="Royal blue",
       coat="Cape", coat_colour="Red", shoes="Knee boots", shoes_colour="Red",
       hair="Quiff", hair_colour="Black", gesture="Hands on hips",
       stance="Feet apart", garments=[["hips", "#c0392b", "Default"]]),
)}


def options() -> dict:
    """The whole catalogue, for the builder and the MCP."""
    return {
        "gender": list(GENDERS), "age": list(AGES), "build": list(BUILDS),
        "skin": list(SKIN_TONES), "gesture": list(GESTURES),
        "stance": list(STANCES), "hair": list(HAIR),
        "hair_colour": list(HAIR_COLOURS), "beard": list(BEARDS),
        "top": {k: v["parts"] for k, v in TOPS.items()},
        "bottom": {k: v["parts"] for k, v in BOTTOMS.items()},
        "coat": {k: v["parts"] for k, v in COATS.items()},
        "shoes": {k: v["parts"] for k, v in SHOES.items()},
        "gloves": list(GLOVES), "hat": list(HATS), "glasses": list(GLASSES),
        "colours": dict(COLOURS),
        "body_parts": {k: list(v) for k, v in outfit.PARTS.items()},
        "part_groups": {k: list(v) for k, v in outfit.GROUPS.items()},
        "materials": list(outfit.MATERIALS),
        "presets": list(PRESETS),
        "defaults": dict(DEFAULTS),
    }
