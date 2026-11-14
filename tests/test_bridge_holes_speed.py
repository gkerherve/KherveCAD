"""Capping an extruded plate full of holes stays quick (Exercise 49,
2026-11-14: a 279 mm plate with seven holes and fine arcs took minutes
to re-preview on every sketch edit — every outline vertex was tested for
sight of every hole before the nearest was chosen).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import time

from khervecad import mesh


def _plate():
    n = 2000
    solid = [(300 * math.cos(2 * math.pi * i / n),
              150 * math.sin(2 * math.pi * i / n)) for i in range(n)]
    holes = [[(x + 7 * math.cos(-2 * math.pi * k / 64),
               7 * math.sin(-2 * math.pi * k / 64)) for k in range(64)]
             for x in range(-200, 201, 50)]
    return solid, holes


def test_bridging_many_holes_is_quick():
    solid, holes = _plate()
    t = time.time()
    merged = mesh._bridge_holes(solid, holes)
    assert time.time() - t < 1.5
    assert merged is not None
    assert len(merged) == len(solid) + sum(len(h) + 2 for h in holes)
    # the cap still has the plate's area less the holes'
    tris = mesh.triangulate(merged)
    area = sum(abs((b[0] - a[0]) * (c[1] - a[1]) -
                   (c[0] - a[0]) * (b[1] - a[1])) / 2 for a, b, c in tris)
    want = mesh.polygon_area(solid) + sum(mesh.polygon_area(h)
                                          for h in holes)
    assert abs(area - want) < 1e-6 * want
