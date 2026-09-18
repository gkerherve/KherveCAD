"""Every Lego piece as its own Library item.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from khervecad import library, library_lego_parts as parts, mesh
from khervecad.model import CadNode, validate


def _extent(node):
    pts = [v for t in mesh.tessellate(node) for v in t]
    return [(round(min(p[i] for p in pts), 2),
             round(max(p[i] for p in pts), 2)) for i in range(3)]


@pytest.mark.parametrize("pid", list(parts.PARTS))
def test_every_piece_builds_alone_and_sits_on_the_grid(pid):
    node = library.build_part(pid, {})
    root = CadNode("root")
    root.add(node)
    assert validate(root) == {}
    assert node.type == "color"
    (x0, x1), (y0, y1), (z0, _z1) = _extent(node)
    assert x0 == pytest.approx(0.1) and z0 == pytest.approx(0.0)
    assert (x1 + 0.1) % 8 == pytest.approx(0.0, abs=1e-6)
    if "side stud" not in pid.replace("_", " "):
        assert y0 == pytest.approx(0.1)


def test_every_piece_is_its_own_menu_item_in_a_known_group():
    assert len(parts.PARTS) > 90
    labels = [spec["label"] for spec in parts.PARTS.values()]
    assert len(set(labels)) == len(labels)
    for label in labels:
        assert parts.group_of(label) in parts.GROUP_ORDER
    assert parts.group_of("Brick") == "Any size (customise)"


def test_a_technic_brick_has_its_pin_holes_open():
    node = parts.technic_brick("T", 4)
    tris = mesh.tessellate(node)
    # nothing inside the first hole's bore, at x = 7.9, z = 5.8
    inside = [v for t in tris for v in t
              if abs(v[0] - 7.9) < 1.5 and abs(v[2] - 5.8) < 1.5
              and 1.0 < v[1] < 7.0]
    assert not inside
