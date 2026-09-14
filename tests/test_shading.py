"""Cavity shading and edge lines (shading.py) in the 3D preview.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from khervecad import bsp, mesh, shading


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _box(x0, y0, z0, w, d, h):
    x1, y1, z1 = x0 + w, y0 + d, z0 + h
    quads = [((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)),
             ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),
             ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),
             ((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)),
             ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)),
             ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))]
    return [t for a, b, c, d_ in quads for t in ((a, b, c), (a, c, d_))]


def _cylinder(n=32, r=10.0, h=20.0):
    tris = []
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        p0 = (r * math.cos(a0), r * math.sin(a0))
        p1 = (r * math.cos(a1), r * math.sin(a1))
        tris.append(((0.0, 0.0, h), (p0[0], p0[1], h), (p1[0], p1[1], h)))
        tris.append(((0.0, 0.0, 0.0), (p1[0], p1[1], 0.0), (p0[0], p0[1], 0.0)))
        tris.append(((p0[0], p0[1], 0.0), (p1[0], p1[1], 0.0),
                     (p1[0], p1[1], h)))
        tris.append(((p0[0], p0[1], 0.0), (p1[0], p1[1], h),
                     (p0[0], p0[1], h)))
    return tris


def test_a_cube_has_twelve_creases_and_a_cylinder_two_rims():
    info = shading.analyse(_box(0, 0, 0, 10, 10, 10))
    segs = {tuple(sorted(s)) for lst in info.creases.values() for s in lst}
    assert len(segs) == 12
    cyl = shading.analyse(_cylinder())
    segs = {tuple(sorted(s)) for lst in cyl.creases.values() for s in lst}
    assert len(segs) == 64                          # two rims, no facets
    assert all(abs(p[2] - q[2]) < 1e-9 for p, q in segs)


def test_cavity_darkens_a_valley_and_lightens_a_ridge():
    # an L: the inside corner between the floor and the wall is a valley
    floor = _box(0, 0, 0, 30, 20, 5)
    info = shading.analyse(floor)
    assert all(t > 0 for t in info.cavity)         # a box is all ridge
    # a narrow groove, cut as one mesh by extruding a profile: its floor
    # has two long concave edges and only two short convex ends
    from khervecad import mesh
    from khervecad.model import DocumentModel
    doc = DocumentModel()
    doc.set_global_fn(False)
    ext = doc.add_node("linear_extrude", dict(height=40.0))
    doc.add_node("polygon", dict(points=[[0, 0], [30, 0], [30, 20],
                                         [16, 20], [16, 10], [14, 10],
                                         [14, 20], [0, 20]]),
                 parent=ext)
    tris = mesh.tessellate(doc.root)
    info = shading.analyse(tris)
    floor = [info.cavity[i] for i, t in enumerate(tris)
             if all(abs(v[1] - 10) < 1e-9 for v in t)]
    assert floor and max(floor) < 0                 # a valley
    top = [info.cavity[i] for i, t in enumerate(tris)
           if all(abs(v[2] - 40) < 1e-9 for v in t)]
    assert top and min(top) > 0                     # a ridge
    assert shading.multiplier(-1.0, 0.5) < 1.0 < shading.multiplier(1.0, 0.5)


def test_silhouette_edges_separate_front_from_back():
    info = shading.analyse(_box(0, 0, 0, 10, 10, 10))
    front = [n[2] > 0 or n[0] > 0 for n in info.normals]   # top and +x
    sil = shading.silhouette(info, front)
    segs = {tuple(sorted(s)) for lst in sil.values() for s in lst}
    assert len(segs) == 6                            # the outline
    assert all(any(f for f in front) for _ in [0])


def test_bsp_pieces_remember_their_parent():
    tris = _box(0, 0, 0, 10, 10, 10) + _box(5, 5, 5, 10, 10, 10)
    tree = bsp.build(tris, budget=10)
    assert tree is not None and len(tree.parents) == len(tree.tris)
    assert set(tree.parents) <= set(range(len(tris)))
    assert len(tree.tris) > len(tris)              # something was split


def test_edge_lines_darken_the_edge_pixels(app):
    from khervecad.view3d import View3D
    view = View3D()
    view.resize(400, 300)
    view.background = "Light"
    view.style = "Matte"
    view.set_mesh(_box(0, 0, 0, 20, 20, 20), "test")
    view.wait_for_bsp()
    view.yaw, view.pitch = 35.0, 25.0
    view.fit()
    eye, right, up, forward = view._camera()

    def lightness(at):
        img = view.grab().toImage()
        x, y, _ = view._project(eye, right, up, forward, at)
        return img.pixelColor(int(x), int(y)).lightnessF()
    edge_point = (20.0, 20.0, 10.0)             # the front vertical edge
    face_point = (20.0, 17.0, 10.0)
    plain_edge, plain_face = lightness(edge_point), lightness(face_point)
    view.edges = True                            # attribute: not persisted
    lined_edge, lined_face = lightness(edge_point), lightness(face_point)
    assert lined_edge < plain_edge - 0.05
    assert abs(lined_face - plain_face) < 0.05
    view.cavity = True
    assert view._mesh_info() is not None
    view.grab()                                  # paints without error


def test_settings_persist_and_the_snapshot_copies_them(app):
    from PyQt5.QtCore import QSettings
    from khervecad.view3d import View3D
    settings = QSettings("Kherve", "KherveCAD")
    view = View3D()
    view.set_cavity(True)
    view.set_edges(True)
    try:
        assert View3D().cavity and View3D().edges
        view.set_mesh(_box(0, 0, 0, 10, 10, 10), "test")
        img, _state = view.snapshot(120, 90, frame=True)
        assert img.width() == 120
    finally:
        settings.remove("render_cavity")
        settings.setValue("render_edges", False)   # the session's neutral


def test_edge_lines_are_on_by_default():
    from PyQt5.QtCore import QSettings
    from khervecad.view3d import View3D
    settings = QSettings("Kherve", "KherveCAD")
    settings.remove("render_edges")
    try:
        assert View3D().edges is True
        assert View3D().hardware is True       # OpenGL, on already
    finally:
        settings.setValue("render_edges", False)   # the session's neutral


def test_an_open_border_edge_is_drawn():
    # one lone triangle: every edge is a border, so all three are lines
    info = shading.analyse([((0, 0, 0), (1, 0, 0), (0, 1, 0))])
    assert len(info.creases[0]) == 3


def test_piece_segments_keep_only_what_lies_on_the_piece():
    crease = [((0.0, 0.0, 0.0), (10.0, 0.0, 0.0))]
    piece = ((2.0, 0.0, 0.0), (6.0, 0.0, 0.0), (4.0, 3.0, 0.0))
    assert shading.piece_segments(piece, crease) == [
        ((2.0, 0.0, 0.0), (6.0, 0.0, 0.0))]
    off = ((2.0, 1.0, 0.0), (6.0, 1.0, 0.0), (4.0, 3.0, 0.0))
    assert shading.piece_segments(off, crease) == []


# ── smooth shading: a normal per vertex ─────────────────────────────

def test_vertex_normals_smooth_a_sphere_and_keep_a_cube_sharp():
    from khervecad import glrender
    from khervecad.model import CadNode
    root = CadNode("root", "root")
    root.add(CadNode("sphere", "s", dict(radius=10.0, segments=24)))
    sphere = mesh.tessellate(root)
    vn = shading.vertex_normals(sphere)
    assert len(vn) == len(sphere)
    for tri, normals in zip(sphere, vn):
        for v, n in zip(tri, normals):
            length = math.sqrt(sum(c * c for c in n))
            assert length == pytest.approx(1.0, abs=1e-6)
            # on a sphere the smooth normal points along the radius
            radial = [c / 10.0 for c in v]
            assert sum(a * b for a, b in zip(n, radial)) > 0.97
    # a cube's vertex normals are its face normals: the edges are creases
    box = CadNode("root", "root")
    box.add(CadNode("cube", "c", dict(width=10.0, depth=10.0, height=10.0)))
    cube = mesh.tessellate(box)
    for tri, normals in zip(cube, shading.vertex_normals(cube)):
        face = shading._normal(tri)
        for n in normals:
            assert n == pytest.approx(face, abs=1e-9)
    # packed for OpenGL, the sphere's three vertices carry three normals
    from khervecad.view3d import View3D
    view = View3D()
    view.smooth = True
    data, _trans = glrender.build_vertices(view, sphere, None)
    stride = glrender.STRIDE
    first = [tuple(data[k * stride + 3:k * stride + 6]) for k in range(3)]
    assert len(set(first)) == 3
    view.smooth = False
    flat, _trans = glrender.build_vertices(view, sphere, None)
    first = [tuple(flat[k * stride + 3:k * stride + 6]) for k in range(3)]
    assert len(set(first)) == 1


def test_smooth_shading_toggle_persists_and_reaches_the_menu(app):
    from PyQt5.QtCore import QSettings
    settings = QSettings("Kherve", "KherveCAD")
    saved = settings.value("render_smooth")
    try:
        from khervecad.view3d import View3D
        view = View3D()
        seen = []
        view.look_toggled.connect(lambda key, on: seen.append((key, on)))
        view.set_smooth(False)
        assert seen == [("smooth", False)] and not View3D().smooth
        view.set_smooth(True)
        assert View3D().smooth
    finally:
        if saved is None:
            settings.remove("render_smooth")
        else:
            settings.setValue("render_smooth", saved)
