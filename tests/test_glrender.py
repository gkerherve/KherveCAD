"""OpenGL face rendering (glrender.py) and its hand-over to the painter.

The offscreen Qt platform the suite runs on has no OpenGL, so the GL
path itself is exercised only where a context exists (skipped
otherwise); the vertex packing and the fallback are tested everywhere.

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
from PyQt5.QtWidgets import QApplication

from khervecad import glrender, mesh
from khervecad.model import CadNode
from khervecad.view3d import View3D


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _scene():
    root = CadNode("root")
    glass = CadNode("color", "g", dict(color="#3b9ad9", alpha=0.5,
                                       material="Glass"))
    glass.add(CadNode("cube", "c", dict(width=20, depth=20, height=20)))
    red = CadNode("color", "r", dict(color="#c91a09"))
    red.add(CadNode("cube", "d", dict(x=30, width=20, depth=20,
                                      height=20)))
    root.add(glass)
    root.add(red)
    colored = mesh.tessellate_colored(root)
    return [t for t, _c in colored], [c for _t, c in colored]


def test_vertices_pack_opaque_and_translucent_apart(app):
    tris, colors = _scene()
    view = View3D()
    data, trans = glrender.build_vertices(view, tris, colors)
    assert len(data) == 12 * 3 * glrender.STRIDE       # the red cube
    assert len(trans) == 12                            # the glass one
    alpha = data[9]
    assert alpha == 1.0
    # the red cube's colour survives the Shaded style's saturation boost
    r, g, b = data[6], data[7], data[8]
    assert r > 0.7 and g < 0.2 and b < 0.2
    assert all(tail[6] < 0.99 for _tri, tail in trans)  # glass alpha


def test_materials_follow_the_painter_styles():
    amb, dif, gloss, power, sat, _v = glrender.material("Brushed metal")
    assert gloss > 0.5 and power >= 16 and sat < 0.3
    assert glrender.material("Emissive")[1] == 0.0      # unshaded
    assert glrender.material("Nonsense") == glrender.material("Shaded")


def test_painter_styles_never_go_to_gl(app):
    view = View3D()
    view.hardware = True
    view.style = "Wireframe"
    assert not view._gl_active()
    view.style = "X-ray"
    assert not view._gl_active()


def test_hardware_off_uses_the_painter_and_builds_a_tree(app):
    tris, colors = _scene()
    view = View3D()
    view.hardware = False
    view.set_mesh(tris, "t", colors)
    assert view.wait_for_bsp() is not None
    view.resize(300, 200)
    view.repaint()
    assert not view._gl_drew


def test_the_gl_path_when_a_context_exists(app):
    r = glrender.renderer()
    if not r.available():
        pytest.skip(f"no OpenGL here: {r.error}")
    tris, colors = _scene()
    view = View3D()
    view.hardware = True
    view.resize(320, 240)
    view.set_mesh(tris, "t", colors)
    view.show()
    view.repaint()
    assert view._gl_drew
    assert view._bsp is None                           # not needed
