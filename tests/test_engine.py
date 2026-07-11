"""Tests for STL read/write in the engine module.

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

from khervecad import engine

TRIS = [((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (0.0, 1.0, 1.0))]


def test_binary_stl_roundtrip(tmp_path):
    path = tmp_path / "out.stl"
    engine.write_stl(TRIS, str(path))
    mesh = engine.parse_stl(str(path))
    assert mesh == [tuple(tuple(pytest.approx(c) for c in v)
                          for v in tri) for tri in TRIS] or mesh == TRIS


def test_ascii_stl_parse(tmp_path):
    path = tmp_path / "a.stl"
    path.write_text("""solid test
facet normal 0 0 1
 outer loop
  vertex 0 0 0
  vertex 2 0 0
  vertex 0 2 0
 endloop
endfacet
endsolid test
""")
    mesh = engine.parse_stl(str(path))
    assert mesh == [((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0))]


def test_find_openscad_returns_string():
    assert isinstance(engine.find_openscad(), str)
