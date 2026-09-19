"""Photoreal rendering through Blender (photoreal.py), with a stand-in
blender that checks what it is handed and writes a PNG.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os
import stat
import struct
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import mesh, photoreal, scadparse

FAKE = r'''#!{python}
import json, struct, sys, zlib
args = json.load(open(sys.argv[sys.argv.index("--") + 1]))
assert "-b" in sys.argv and "--python" in sys.argv
glb = open(args["glb"], "rb").read()
assert glb[:4] == b"glTF"
n = struct.unpack("<I", glb[12:16])[0]
gltf = json.loads(glb[20:20 + n])
json.dump({{"args": args, "materials": gltf["materials"]}},
          open(args["out"] + ".json", "w"))
w, h = args["size"]
raw = b"".join(b"\0" + b"\x80\x80\x80" * w for _ in range(h))
def chunk(t, d):
    return (struct.pack(">I", len(d)) + t + d
            + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff))
png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h,
       8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw))
       + chunk(b"IEND", b""))
open(args["out"], "wb").write(png)
'''


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fake_blender(tmp_path, monkeypatch):
    path = tmp_path / "blender"
    path.write_text(FAKE.format(python=sys.executable))
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("KHERVECAD_BLENDER", str(path))
    return str(path)


def test_the_glb_carries_one_material_per_colour(app, tmp_path):
    rows = [(((0, 0, 0), (1, 0, 0), (0, 1, 0)), ("red", 1.0, "Metal")),
            (((0, 0, 1), (1, 0, 1), (0, 1, 1)), ("#80c0ff", 0.4, "Glass")),
            (((0, 0, 2), (1, 0, 2), (0, 1, 2)), None)]
    path = photoreal.write_glb(rows, str(tmp_path / "s.glb"))
    data = open(path, "rb").read()
    n = struct.unpack("<I", data[12:16])[0]
    gltf = json.loads(data[20:20 + n])
    mats = gltf["materials"]
    assert len(mats) == 3
    assert mats[0]["pbrMetallicRoughness"]["metallicFactor"] == 1.0
    assert "KHR_materials_transmission" in mats[1]["extensions"]
    # metres, Y up: z (mm) became y
    acc = gltf["accessors"][2]
    assert acc["max"][1] == pytest.approx(0.001)


def test_render_runs_blender_and_returns_the_png(app, tmp_path,
                                                 fake_blender):
    root, _w = scadparse.parse_scad('color("gold") cube(10);')
    rows = mesh.tessellate_colored(root)
    out = str(tmp_path / "photo.png")
    photoreal.render(rows, out, yaw=30, pitch=20, size=(64, 48),
                     samples=8)
    assert os.path.getsize(out) > 0
    seen = json.load(open(out + ".json"))
    assert seen["args"]["size"] == [64, 48]
    assert seen["args"]["samples"] == 8


def test_no_blender_is_a_clear_error(app, monkeypatch, tmp_path):
    monkeypatch.setattr(photoreal, "find_blender", lambda: None)
    with pytest.raises(RuntimeError, match="blender.org"):
        photoreal.render([(((0, 0, 0), (1, 0, 0), (0, 1, 0)), None)],
                         str(tmp_path / "x.png"))


def test_the_mcp_tool_returns_an_image(app, fake_blender):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_server import IMAGE_KEY
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": "cube(10);"})
    info = ex.execute("get_document_info", {})
    assert info["blender"]["available"]
    out = ex.execute("render_photo", {"width": 80, "height": 60,
                                      "view": "Isometric"})
    assert "error" not in out, out
    assert out[IMAGE_KEY] and out["size"] == [80, 60]


def test_the_blender_script_compiles():
    compile(photoreal.SCRIPT, "render.py", "exec")
