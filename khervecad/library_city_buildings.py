"""The **Buildings** library section: every City Builder building style
— cottage, house, terrace, shop, block, tower, round tower, L-shape,
church — as a Part Library piece, so a house or a block can be dropped
into any document from Library ▸ City ▸ Buildings, or placed in the City
Builder with its library-piece tool.

Each is `city_buildings.build_building` at the origin, front facing -Y:
the detailed outside (framed windows, doors, roofs with chimneys and
dormers, parapets and plant), nothing inside. Sizes give the footprint
and floors (all editable), the look combo picks the wall: the style's
own, or brick, concrete, render or stone.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import city_buildings as B

CATEGORY = "Buildings"
COUNT_FIELDS = {"floors"}

LABELS = {"cottage": "Cottage", "house": "House (hipped roof)",
          "terrace": "Terraced house", "shop": "Shop with flat above",
          "block": "Apartment block", "tower": "Office tower",
          "round tower": "Round tower", "L-shape": "L-shaped house",
          "church": "Church"}
LOOKS = ["Style default"] + [w.capitalize() for w in B.WALLS]
#: size name -> footprint scale and floors as a fraction of the range
SIZES = {"Small": (0.8, 0.0), "Standard": (1.0, 0.5), "Large": (1.3, 1.0)}


def _builder(style):
    def build(dims):
        look = (dims.get("_color") or "Style default").lower()
        spec = dict(style=style, w=dims.get("w"), d=dims.get("d"),
                    floors=dims.get("floors"),
                    floor_height=dims.get("floor_height"),
                    name=LABELS[style])
        if look in B.WALLS:
            spec["wall"] = look
        node = B.build_building(spec, 0)
        return node
    return build


def _entry(style):
    (lo, hi) = B.STYLES[style][0]
    w, d = B.DEFAULT_SIZE[style]
    sizes = {}
    for name, (k, f) in SIZES.items():
        floors = round(lo + (hi - lo) * f)
        sizes[f"{name} ({w * k / 1000:.0f} x {d * k / 1000:.0f} m, "
              f"{floors} floor{'s' if floors > 1 else ''})"] = dict(
            w=round(w * k), d=round(d * k), floors=floors,
            floor_height=B.FLOOR_HEIGHT)
    return dict(label=LABELS[style], category=CATEGORY, sizes=sizes,
                build=_builder(style), colors=list(LOOKS),
                fields=[("w", "Width (front)"), ("d", "Depth"),
                        ("floors", "Floors"),
                        ("floor_height", "Floor height")])


PARTS = {f"building_{style.replace(' ', '_').replace('-', '_').lower()}":
         _entry(style) for style in B.STYLES}
