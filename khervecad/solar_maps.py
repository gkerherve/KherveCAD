"""Coarse surface maps for `solar_surface.map_shells` (Qt-free): the
Earth at 5° cells, 36 rows from the north pole down and 72 columns from
180° W eastwards, hand-drawn from an atlas — the continents, the big
islands, the deserts, taiga and ice — good enough to recognise at a
glance on a 60 mm globe, not a coastline.

Classes: "." ocean (left to the base sphere), "g" green land, "t"
taiga and tundra, "d" desert and steppe, "i" ice.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

COLS = 72          # 5° of longitude each, from 180° W
ROWS = 36          # 5° of latitude each, from the north pole


def _row(*spans) -> str:
    """A map row from inclusive column spans (first, last, char);
    later spans overwrite earlier ones."""
    cells = ["."] * COLS
    for first, last, char in spans:
        for c in range(first, last + 1):
            cells[c] = char
    return "".join(cells)


#: the Earth, 90° N at the top; column c spans longitude -180 + 5c
EARTH = [
    _row(),                                                    # 85-90 N
    _row((18, 31, "i"), (46, 48, "i")),                        # 80-85
    _row((12, 32, "i"), (38, 41, "i"), (47, 48, "i"), (55, 56, "i"),
         (64, 65, "i")),                                       # 75-80
    _row((3, 7, "t"), (11, 22, "t"), (25, 31, "i"), (39, 45, "t"),
         (46, 47, "i"), (49, 50, "t"), (52, 57, "t"), (62, 71, "t")),
    _row((2, 19, "t"), (22, 23, "t"), (25, 31, "i"), (38, 71, "t")),
    _row((3, 16, "t"), (21, 23, "t"), (25, 27, "i"), (31, 33, "t"),
         (37, 64, "t"), (67, 68, "t")),                        # 60-65
    _row((3, 9, "t"), (10, 16, "g"), (21, 23, "t"), (34, 35, "g"),
         (38, 39, "g"), (41, 64, "t"), (67, 68, "t")),         # 55-60
    _row((10, 16, "g"), (20, 24, "g"), (34, 55, "g"), (56, 63, "t"),
         (64, 64, "t"), (67, 67, "t")),                        # 50-55
    _row((11, 16, "g"), (19, 25, "g"), (35, 47, "g"), (48, 59, "d"),
         (60, 62, "g"), (64, 64, "t")),                        # 45-50
    _row((11, 11, "g"), (12, 14, "d"), (15, 23, "g"), (34, 40, "g"),
         (43, 44, "g"), (47, 59, "d"), (60, 61, "g"), (64, 64, "g")),
    _row((11, 11, "g"), (12, 15, "d"), (16, 20, "g"), (34, 35, "g"),
         (41, 44, "g"), (47, 55, "d"), (56, 59, "g"), (61, 64, "g")),
    _row((12, 15, "d"), (16, 20, "g"), (34, 47, "d"), (48, 50, "d"),
         (51, 51, "g"), (52, 56, "d"), (57, 59, "g"), (62, 62, "g")),
    _row((13, 16, "d"), (19, 19, "g"), (33, 47, "d"), (49, 50, "d"),
         (51, 51, "g"), (52, 54, "d"), (55, 59, "g")),         # 25-30
    _row((4, 4, "g"), (14, 16, "d"), (19, 20, "g"), (32, 42, "d"),
         (44, 47, "d"), (50, 50, "d"), (51, 53, "g"), (54, 60, "g")),
    _row((4, 4, "g"), (15, 18, "g"), (21, 21, "g"), (32, 47, "d"),
         (50, 52, "g"), (54, 57, "g"), (60, 60, "g")),         # 15-20
    _row((17, 19, "g"), (21, 23, "g"), (32, 44, "g"), (45, 46, "d"),
         (51, 51, "g"), (55, 57, "g"), (60, 60, "g")),         # 10-15
    _row((20, 24, "g"), (33, 45, "g"), (52, 52, "g"), (56, 56, "g"),
         (58, 61, "g")),                                       # 5-10
    _row((20, 25, "g"), (37, 44, "g"), (45, 45, "d"), (55, 60, "g")),
    _row((20, 27, "g"), (38, 44, "g"), (56, 56, "g"), (58, 60, "g"),
         (62, 65, "g")),                                       # 0-5 S
    _row((20, 28, "g"), (38, 43, "g"), (57, 58, "g"), (63, 65, "g")),
    _row((20, 28, "g"), (38, 43, "g"), (62, 64, "g")),         # 10-15 S
    _row((21, 28, "g"), (38, 38, "d"), (39, 43, "g"), (44, 45, "g"),
         (58, 63, "d"), (64, 65, "g")),                        # 15-20 S
    _row((22, 22, "d"), (23, 27, "g"), (38, 40, "d"), (41, 43, "g"),
         (44, 45, "g"), (58, 65, "d"), (66, 66, "g")),         # 20-25 S
    _row((21, 22, "d"), (23, 26, "g"), (39, 41, "d"), (42, 42, "g"),
         (58, 64, "d"), (65, 66, "g")),                        # 25-30 S
    _row((21, 25, "g"), (39, 41, "g"), (59, 59, "g"), (60, 62, "d"),
         (63, 65, "g")),                                       # 30-35 S
    _row((21, 24, "g"), (64, 65, "g"), (70, 71, "g")),         # 35-40 S
    _row((21, 23, "g"), (65, 65, "g"), (69, 70, "g")),         # 40-45 S
    _row((21, 22, "t"), (69, 69, "t")),                        # 45-50 S
    _row((21, 24, "t")),                                       # 50-55 S
    _row((22, 22, "t")),                                       # 55-60 S
    _row((23, 24, "i")),                                       # 60-65 S
    _row((22, 23, "i"), (36, 67, "i")),                        # 65-70 S
    _row((16, 23, "i"), (32, 67, "i")),                        # 70-75 S
    _row((0, 67, "i")),                                        # 75-80 S
    _row((0, 71, "i")),                                        # 80-85 S
    _row((0, 71, "i")),                                        # 85-90 S
]

#: class -> (colour, relief factor)
EARTH_PALETTE = {"g": ("#4f8f3c", 1.0), "t": ("#5d7d4b", 1.0),
                 "d": ("#c9a862", 1.0), "i": ("#f3f6f8", 1.3)}

EARTH_OCEAN = "#1f4f9c"
