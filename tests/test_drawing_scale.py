"""A small part fills its sheet (2026-11-15, found filming Exercise 7:
a 92 x 68 x 18 plate was drawn at 1:5 on A4, a postage stamp in a
frame). The room between views was counted as 35 % of the SUM of the
views' widths times each gap, instead of one gap per space.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from khervecad import drawing


def _box(a, b, c):
    p = [(x, y, z) for x in (0, a) for y in (0, b) for z in (0, c)]
    q = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3),
         (0, 4, 6, 2), (1, 3, 7, 5)]
    tris = []
    for f in q:
        tris.append((p[f[0]], p[f[1]], p[f[2]]))
        tris.append((p[f[0]], p[f[2]], p[f[3]]))
    return tris


def test_a_plate_is_drawn_at_a_readable_scale():
    lay = drawing.layout(_box(92, 68, 18), sheet="A4")
    assert lay["scale"] >= 0.5, lay["scale"]
    # and every view still lies inside the sheet
    w, h = lay["sheet_size"] if "sheet_size" in lay else (297, 210)
    for v in lay.get("views", []):
        x0, y0, x1, y1 = v.get("box", (0, 0, 0, 0))
        assert 0 <= x0 and x1 <= w and 0 <= y0 and y1 <= h


def test_radii_measured_off_facets_read_round():
    from khervecad.blueprint_scene import nice_radius
    assert nice_radius(12.04) == 12 and nice_radius(11.99) == 12
    assert nice_radius(42.98) == 43 or nice_radius(42.98) == 43.0
    assert nice_radius(7.3) == 7.3          # a real odd size stays
