"""Mesh from a photo: the GLB reader/writer, the three generation
backends (network faked), the STL conversion, the import paths, the
dialog and the mesh_from_photo MCP tool.

Run with: python -m pytest tests/  (offscreen Qt).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import io
import json
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import engine, photo3d


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _tetra():
    a, b, c, d = (0, 0, 0), (10, 0, 0), (0, 10, 0), (0, 0, 10)
    return [(a, c, b), (a, b, d), (a, d, c), (b, c, d)]


@pytest.fixture
def picture(tmp_path, app):
    from PyQt5.QtGui import QColor, QImage
    image = QImage(32, 32, QImage.Format_ARGB32)
    image.fill(QColor("#8899aa"))
    path = tmp_path / "queen.png"
    image.save(str(path))
    return str(path)


# ── GLB ────────────────────────────────────────────────────────────

def test_glb_round_trips_and_applies_node_transforms(tmp_path):
    path = photo3d.write_glb(_tetra(), tmp_path / "t.glb")
    assert photo3d.parse_glb(path) == [tuple(tuple(float(c) for c in v)
                                              for v in t) for t in _tetra()]
    # a scene node moving the mesh: rewrite the JSON chunk with a
    # translation and a child instancing the same mesh, scaled
    data = Path(path).read_bytes()
    length = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + length].decode())
    gltf["nodes"] = [{"mesh": 0, "translation": [5, 0, 0],
                      "children": [1]},
                     {"mesh": 0, "scale": [2, 2, 2]}]
    js = json.dumps(gltf).encode()
    js += b" " * (-len(js) % 4)
    rest = data[20 + length:]
    total = 12 + 8 + len(js) + len(rest)
    moved = tmp_path / "moved.glb"
    moved.write_bytes(struct.pack("<III", 0x46546C67, 2, total)
                      + struct.pack("<II", len(js), 0x4E4F534A) + js + rest)
    tris = photo3d.parse_glb(moved)
    assert len(tris) == 8
    xs = sorted({v[0] for t in tris for v in t})
    assert xs == pytest.approx([5, 15, 25])       # moved 5; child 2x then +5
    bad = tmp_path / "bad.glb"
    bad.write_bytes(b"nope")
    with pytest.raises(photo3d.Photo3DError):
        photo3d.parse_glb(bad)


def test_parse_mesh_reads_glb_z_up_and_to_stl_scales_and_stands(tmp_path):
    path = photo3d.write_glb(_tetra(), tmp_path / "t.glb")
    tris = engine.parse_mesh(path)                 # Y-up -> Z-up
    assert max(v[2] for t in tris for v in t) == pytest.approx(10)
    assert min(v[1] for t in tris for v in t) == pytest.approx(-10)
    stl = photo3d.to_stl(path, size_mm=50)
    assert Path(stl).suffix == ".stl"
    back = engine.parse_mesh(stl)
    lo = [min(v[c] for t in back for v in t) for c in range(3)]
    hi = [max(v[c] for t in back for v in t) for c in range(3)]
    assert max(h - l for h, l in zip(hi, lo)) == pytest.approx(50, abs=0.01)
    assert lo[2] == pytest.approx(0)               # stood on the floor
    assert lo[0] == pytest.approx(-hi[0], abs=0.01)  # centred in x
    assert ".glb" in engine.MESH_EXTS


# ── backends with the network faked ────────────────────────────────

class _Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _opener(script, glb_bytes):
    """A fake urlopen: *script* maps (method, url-suffix) -> reply."""
    calls = []

    def open_(req, timeout=None):
        calls.append((req.get_method(), req.full_url, req.data))
        for (method, suffix), reply in script:
            if req.get_method() == method and req.full_url.endswith(suffix):
                body = reply(calls) if callable(reply) else reply
                return _Reply(json.dumps(body).encode()
                              if isinstance(body, dict) else body)
        raise AssertionError(f"unexpected request {req.full_url}")
    open_.calls = calls
    return open_


def test_tripo_uploads_starts_polls_and_downloads(tmp_path, picture):
    glb = Path(photo3d.write_glb(_tetra(), tmp_path / "g.glb")).read_bytes()
    polls = []
    script = [
        (("POST", "/upload"), {"code": 0, "data": {"image_token": "tok"}}),
        (("POST", "/task"), {"code": 0, "data": {"task_id": "t1"}}),
        (("GET", "/task/t1"), lambda calls: (polls.append(1) or {
            "code": 0, "data": {"status": "running", "progress": 40}})
            if len(polls) < 2 else {"code": 0, "data": {
                "status": "success", "output": {"pbr_model":
                                                "https://cdn/x/model.glb"}}}),
        (("GET", "model.glb"), glb),
    ]
    opener = _opener(script, glb)
    seen = []
    out = photo3d.generate(picture, tmp_path, "tripo", key="k",
                           opener=opener, sleep=lambda s: None,
                           progress=seen.append)
    assert Path(out).name == "queen_tripo.glb"
    assert Path(out).read_bytes() == glb
    assert seen and seen[0]["status"] == "running"
    upload = opener.calls[0]
    assert b'name="file"' in upload[2] and upload[1].endswith("/upload")
    task = json.loads(opener.calls[1][2])
    assert task == {"type": "image_to_model",
                    "file": {"type": "png", "file_token": "tok"}}
    with pytest.raises(photo3d.Photo3DError):
        photo3d.generate(picture, tmp_path, "tripo", key="",
                         opener=opener)


def test_meshy_sends_a_data_uri_and_downloads_the_glb(tmp_path, picture):
    glb = Path(photo3d.write_glb(_tetra(), tmp_path / "g.glb")).read_bytes()
    script = [
        (("POST", "/image-to-3d"), {"result": "m1"}),
        (("GET", "/image-to-3d/m1"), {"status": "SUCCEEDED",
                                      "model_urls": {"glb": "https://c/m.glb"}}),
        (("GET", "m.glb"), glb),
    ]
    opener = _opener(script, glb)
    out = photo3d.generate(picture, tmp_path, "meshy", key="k",
                           opener=opener, sleep=lambda s: None)
    assert Path(out).name == "queen_meshy.glb"
    body = json.loads(opener.calls[0][2])
    assert body["image_url"].startswith("data:image/png;base64,")
    assert opener.calls[0][1].endswith("/openapi/v1/image-to-3d")
    failed = _opener([(("POST", "/image-to-3d"), {"result": "m2"}),
                      (("GET", "/image-to-3d/m2"), {"status": "FAILED"})],
                     glb)
    with pytest.raises(photo3d.Photo3DError):
        photo3d.generate(picture, tmp_path, "meshy", key="k", opener=failed,
                         sleep=lambda s: None)


def test_local_command_writes_the_output_it_is_told(tmp_path, picture):
    script = tmp_path / "gen.py"
    script.write_text(
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "from khervecad import photo3d\n"
        "photo3d.write_glb([((0,0,0),(1,0,0),(0,1,0))], sys.argv[2])\n"
        % str(Path(__file__).resolve().parent.parent))
    command = f"{sys.executable} {script} {{image}} {{output}}"
    out = photo3d.generate(picture, tmp_path, "local", command=command)
    assert Path(out).name == "queen_generated.glb"
    assert len(photo3d.parse_glb(out)) == 1
    with pytest.raises(photo3d.Photo3DError):
        photo3d.generate(picture, tmp_path, "local", command="echo hi")
    with pytest.raises(photo3d.Photo3DError):
        photo3d.generate(picture, tmp_path, "local",
                         command=f"{sys.executable} -c 'import sys; sys.exit(3)' {{output}}")
    with pytest.raises(photo3d.Photo3DError):
        photo3d.generate(picture, tmp_path, "nowhere")
    with pytest.raises(photo3d.Photo3DError):
        photo3d.generate(str(tmp_path / "missing.png"), tmp_path, "local",
                         command=command)


# ── the app: import, dialog, tool ──────────────────────────────────

@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


def test_a_glb_imports_as_a_part_through_a_sibling_stl(window, tmp_path):
    path = photo3d.write_glb(_tetra(), tmp_path / "scan.glb")
    window.open_any(path)
    parts = [n for n in window.model.root.children if n.type == "component"]
    assert [p.name for p in parts] == ["scan"]
    node = parts[0].children[0]
    assert node.type == "stl_import"
    assert Path(node.params["path"]).name == "scan_from_glb.stl"
    assert (tmp_path / "scan_from_glb.stl").is_file()


def test_the_tool_generates_locally_and_imports_at_size(window, tmp_path,
                                                         picture):
    from khervecad.mcp_tools import McpToolExecutor
    from khervecad import mcp_bridge
    assert "mesh_from_photo" in mcp_bridge._FILE_TOOLS
    script = tmp_path / "gen.py"
    script.write_text(
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "from khervecad import photo3d\n"
        "a,b,c,d=(0,0,0),(1,0,0),(0,1,0),(0,0,1)\n"
        "photo3d.write_glb([(a,c,b),(a,b,d),(a,d,c),(b,c,d)], sys.argv[2])\n"
        % str(Path(__file__).resolve().parent.parent))
    ex = McpToolExecutor(window)
    out = ex.execute("mesh_from_photo", {
        "image_path": picture, "backend": "local", "size_mm": 40,
        "command": f"{sys.executable} {script} {{image}} {{output}}",
        "name": "Head scan"})
    assert "error" not in out, out
    assert out["name"] == "Head scan" and out["imported"].endswith(".stl")
    tris = engine.parse_mesh(out["imported"])
    assert max(v[2] for t in tris for v in t) == pytest.approx(40, abs=0.01)
    assert "error" in ex.execute("mesh_from_photo", {"image_path": "/nope.png"})
    assert "error" in ex.execute("mesh_from_photo", {"image_path": picture,
                                                     "backend": "moon"})
    bad = ex.execute("mesh_from_photo", {"image_path": picture,
                                         "backend": "local",
                                         "command": "echo {output}"})
    assert "error" in bad and "wrote no file" in bad["error"]


def test_the_dialog_opens_and_remembers_the_command(window, picture):
    from PyQt5.QtCore import QSettings
    from khervecad import photo3d_dialog
    settings = QSettings("Kherve", "KherveCAD")
    saved = settings.value("photo3d/command")
    try:
        dialog = photo3d_dialog.open_photo3d(window)
        assert dialog is photo3d_dialog.open_photo3d(window)
        dialog.backend.setCurrentIndex(2)          # local
        assert dialog.command.isEnabled() and not dialog.key.isEnabled()
        dialog.image.setText(picture)
        dialog.command.setText("echo {output}")
        dialog.generate()                          # starts the worker
        dialog.worker.wait(10000)
        app = QApplication.instance()
        app.processEvents()
        assert photo3d_dialog.get_command() == "echo {output}"
        assert "Failed" in dialog.log.toPlainText()
        dialog.close()
    finally:
        if saved is None:
            settings.remove("photo3d/command")
        else:
            settings.setValue("photo3d/command", saved)
