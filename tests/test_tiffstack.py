"""TIFF image stacks as solids (tiffstack.py, tiffstack_ui.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import struct
import zlib
from collections import Counter

import numpy as np
import pytest

from khervecad import tiffstack


def write_tiff(path, pages, *, compress=False, predictor=False, big=False,
               description=None, resolution=None, rgb=False,
               thumbnail=False):
    """A minimal TIFF writer for the tests: each page one strip."""
    bo = "<"
    out = bytearray(b"II" + (struct.pack("<HHHQ", 43, 8, 0, 0) if big
                             else struct.pack("<HI", 42, 0)))
    ifds = []
    all_pages = list(pages) + ([pages[0][::4, ::4]] if thumbnail else [])
    for page in all_pages:
        arr = np.asarray(page)
        h, w = arr.shape[:2]
        spp = 3 if rgb else 1
        if predictor:
            arr = np.concatenate([arr[:, :1], np.diff(arr, axis=1)], axis=1)
        raw = arr.astype(bo + arr.dtype.str[1:]).tobytes()
        data = zlib.compress(raw) if compress else raw
        doff = len(out)
        out += data
        extra = {}
        if description:
            extra["desc"] = len(out)
            out += description.encode() + b"\0"
        if resolution:
            extra["res"] = len(out)
            num, den = resolution
            out += struct.pack("<IIII", num, den, num, den)
        if len(out) % 2:
            out += b"\0"
        bits = arr.dtype.itemsize * 8
        fmt = {"f": 3, "i": 2}.get(arr.dtype.kind, 1)
        entries = [(256, 4, 1, w), (257, 4, 1, h),
                   (258, 3, 1, bits), (259, 3, 1, 8 if compress else 1),
                   (262, 3, 1, 2 if rgb else 1), (273, 4, 1, doff),
                   (277, 3, 1, spp), (278, 4, 1, h), (279, 4, 1, len(data)),
                   (339, 3, 1, fmt)]
        if predictor:
            entries.append((317, 3, 1, 2))
        if description:
            entries.append((270, 2, len(description) + 1, extra["desc"]))
        if resolution:
            entries += [(282, 5, 1, extra["res"]),
                        (283, 5, 1, extra["res"] + 8), (296, 3, 1, 1)]
        entries.sort()
        ifds.append(len(out))
        if big:
            out += struct.pack("<Q", len(entries))
            for tag, typ, n, val in entries:
                if typ == 3 and n == 1:
                    out += struct.pack("<HHQHHI", tag, typ, n, val, 0, 0)
                elif typ == 5 or typ == 2 or n > 1:
                    out += struct.pack("<HHQQ", tag, typ, n, val)
                else:
                    out += struct.pack("<HHQII", tag, typ, n, val, 0)
            out += struct.pack("<Q", 0)
        else:
            out += struct.pack("<H", len(entries))
            for tag, typ, n, val in entries:
                if typ == 3 and n == 1:
                    out += struct.pack("<HHIHH", tag, typ, n, val, 0)
                else:
                    out += struct.pack("<HHII", tag, typ, n, val)
            out += struct.pack("<I", 0)
    if big:
        struct.pack_into("<Q", out, 8, ifds[0])
        for a, b in zip(ifds, ifds[1:]):
            n = struct.unpack_from("<Q", out, a)[0]
            struct.pack_into("<Q", out, a + 8 + 20 * n, b)
    else:
        struct.pack_into("<I", out, 4, ifds[0])
        for a, b in zip(ifds, ifds[1:]):
            n = struct.unpack_from("<H", out, a)[0]
            struct.pack_into("<I", out, a + 2 + 12 * n, b)
    path.write_bytes(bytes(out))
    return path


def sphere(n=40, r=15, dtype=np.uint16, high=1000, low=50):
    z, y, x = np.mgrid[0:n, 0:n + 10, 0:n + 4]
    c = n / 2.0
    inside = (x - c - 2) ** 2 + (y - c - 5) ** 2 + (z - c) ** 2 < r * r
    return np.where(inside, high, low).astype(dtype)


def _volume(tris):
    a = np.asarray(tris, dtype=np.float64)
    return abs(np.einsum("ij,ij->i", a[:, 0],
                         np.cross(a[:, 1], a[:, 2])).sum() / 6.0)


def test_a_multipage_16bit_stack_reads_with_its_imagej_spacing(tmp_path):
    vol = sphere()
    f = write_tiff(tmp_path / "s.tif", list(vol), compress=True,
                   description="ImageJ=1.53\nimages=40\nunit=micron\n"
                               "spacing=2.0\n", resolution=(2, 1))
    st = tiffstack.read_stack(f)
    assert st.shape == (44, 50, 40)
    assert st.bits == 16
    # 2 pixels a micron -> 0.5 µm; slices 2 µm apart; in mm
    assert st.spacing == pytest.approx((0.0005, 0.0005, 0.002))
    # flipped so +y is up: image row 0 is the TOP of the slice
    assert np.array_equal(st.values[7], vol[7][::-1].astype(np.float32))


@pytest.mark.parametrize("kind", ["uint8_predictor", "bigtiff", "float",
                                  "rgb", "int64", "float16"])
def test_other_tiff_flavours_read(tmp_path, kind):
    vol = sphere(n=12, r=4)
    if kind == "uint8_predictor":
        f = write_tiff(tmp_path / "a.tif", list(vol.astype(np.uint8) % 251),
                       predictor=True)
        want = (vol.astype(np.uint8) % 251).astype(np.float32)
    elif kind == "bigtiff":
        f = write_tiff(tmp_path / "a.tif", list(vol), big=True,
                       compress=True)
        want = vol.astype(np.float32)
    elif kind == "float":
        f = write_tiff(tmp_path / "a.tif", list(vol.astype(np.float32)))
        want = vol.astype(np.float32)
    elif kind in ("int64", "float16"):
        # tifffile writes numpy's own types: an SEM stack came as int64
        dt = np.int64 if kind == "int64" else np.float16
        f = write_tiff(tmp_path / "a.tif", list(vol.astype(dt)))
        want = vol.astype(np.float32)
    else:
        rgb = np.repeat((vol // 4).astype(np.uint8)[..., None], 3, axis=3)
        f = write_tiff(tmp_path / "a.tif", list(rgb), rgb=True)
        want = (vol // 4).astype(np.float32)
    st = tiffstack.read_stack(f)
    assert np.allclose(st.values, want[:, ::-1, :], atol=0.01)


def test_thumbnails_are_skipped_and_folders_stack_in_order(tmp_path):
    vol = sphere(n=12, r=4)
    write_tiff(tmp_path / "t.tif", list(vol), thumbnail=True)
    assert tiffstack.read_stack(tmp_path / "t.tif").shape == (16, 22, 12)
    folder = tmp_path / "slices"
    folder.mkdir()
    for k, page in enumerate(vol):              # slice2 before slice10
        write_tiff(folder / f"slice{k}.tif", [page])
    st = tiffstack.read_stack(folder)
    assert st.shape == (16, 22, 12)
    assert np.array_equal(st.values, vol[:, ::-1, :].astype(np.float32))


def test_the_surface_is_a_closed_sphere_of_the_right_size(tmp_path):
    f = write_tiff(tmp_path / "s.tif", list(sphere()))
    st = tiffstack.read_stack(f)
    t = tiffstack.otsu(st.values)
    assert 300 < t < 800                         # between the two levels
    tris = tiffstack.surface(st, t, spacing=(1, 1, 1), smooth=False)
    assert _volume(tris) == pytest.approx(4 / 3 * np.pi * 15 ** 3,
                                          rel=0.03)
    arr = np.asarray(tris)
    assert arr[..., 2].min() == pytest.approx(0)          # on the floor
    keys = Counter()
    for tri in np.round(arr, 6).tolist():
        pts = [tuple(p) for p in tri]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            keys[frozenset((pts[a], pts[b]))] += 1
    assert set(keys.values()) == {2}                       # closed
    # the voxel size scales it, the step coarsens it
    half = tiffstack.surface(st, t, spacing=(0.5, 0.5, 0.5), smooth=False)
    assert _volume(half) == pytest.approx(_volume(tris) / 8, rel=0.01)
    coarse = tiffstack.surface(st, t, step=2, smooth=False)
    assert len(coarse) < len(tris) / 2


def test_an_object_touching_the_edge_still_closes(tmp_path):
    vol = np.full((6, 8, 8), 100, np.uint16)    # solid all through
    st = tiffstack.read_stack(write_tiff(tmp_path / "b.tif", list(vol)))
    tris = tiffstack.surface(st, 50, smooth=False)
    assert _volume(tris) == pytest.approx(8 * 8 * 6, rel=0.25)
    with pytest.raises(tiffstack.StackError):
        tiffstack.read_stack(tmp_path / "missing")


def test_write_stl_reads_back(tmp_path):
    from khervecad.engine import parse_mesh
    st = tiffstack.read_stack(write_tiff(tmp_path / "s.tif",
                                         list(sphere(n=12, r=4))))
    tris = tiffstack.surface(st, 500)
    tiffstack.write_stl(tris, str(tmp_path / "s.stl"))
    back = parse_mesh(str(tmp_path / "s.stl"))
    assert len(back) == len(tris)
    assert np.allclose(np.asarray(back), np.asarray(tris), atol=1e-4)


def test_auto_step_keeps_the_grid_small():
    assert tiffstack.auto_step((100, 100, 100)) == 1
    step = tiffstack.auto_step((1024, 1024, 400))
    gx, gy, gz = tiffstack.grid_size((1024, 1024, 400), step)
    assert gx * gy * gz <= tiffstack.TARGET_VOXELS


@pytest.fixture(scope="module")
def app():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    yield win
    win._dirty = False
    win.close()


def test_mcp_imports_a_stack_as_an_object(window, tmp_path):
    from khervecad.mcp_tools import McpToolExecutor
    f = write_tiff(tmp_path / "cells.tif", list(sphere()))
    out = McpToolExecutor(window).execute(
        "import_image_stack", {"path": str(f), "voxel_size": 0.5})
    assert out["triangles"] > 1000 and not out["scale_from_file"]
    assert out["size_mm"][0] == pytest.approx(15, abs=1.5)  # Ø30 x 0.5
    assert out["unit"] == "mm"
    node = window.model.find(out["node_id"])
    assert node.type == "stl_import" and node.parent.type == "component"
    assert node.params["volume"]["spacing"] == [0.5, 0.5, 0.5]
    assert (tmp_path / out["stl"]).exists() or \
        __import__("pathlib").Path(out["stl"]).exists()
    from khervecad import mesh
    assert mesh.tessellate(window.model.root)       # the preview sees it


def test_a_micron_stack_switches_an_empty_document_to_um(window,
                                                        tmp_path):
    from khervecad.mcp_tools import McpToolExecutor
    f = write_tiff(tmp_path / "cells.tif", list(sphere()),
                   description="ImageJ=1.53\nunit=micron\nspacing=1\n",
                   resolution=(1, 1))
    out = McpToolExecutor(window).execute("import_image_stack",
                                          {"path": str(f)})
    assert window.model.unit == "um" and out["unit"] == "um"
    assert out["size"][0] == pytest.approx(30, abs=2)        # 30 µm
    assert out["size_mm"][0] == pytest.approx(0.03, abs=0.002)


def test_the_dialog_previews_and_rebuilds_in_place(window, tmp_path):
    from khervecad import tiffstack_ui
    f = write_tiff(tmp_path / "s.tif", list(sphere()))
    st = tiffstack.read_stack(f)
    settings = tiffstack_ui.default_settings(st)
    dlg = tiffstack_ui.StackDialog(st, settings, window)
    assert not dlg.picture.pixmap().isNull()
    dlg.thr.setValue(600)
    dlg.invert.setChecked(True)
    got = dlg.settings()
    assert got["threshold"] == 600 and got["invert"]
    node, info = tiffstack_ui.build(window.model, st, dict(got,
                                                           invert=False))
    first = node.params["path"]
    node2, _info = tiffstack_ui.build(window.model, st,
                                      dict(got, invert=False, step=2), node)
    assert node2 is node and node.params["path"] != first
    assert node.params["volume"]["step"] == 2
    dlg.close()
