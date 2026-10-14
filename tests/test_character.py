"""character.py: animated characters — import a skinned, animated GLB,
the bone node (code, parse, preview), attach parts to bones, pose a clip
or bone turns, and export an animated GLB with the parts bound.

The character is built here: a 1 m column of two bones (Hips at the
floor, Chest half way up), the top half skinned to Chest, and a clip
"Wave" turning Chest 90° about +Z (glTF) over one second.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import math
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import character, mesh, scadparse
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _box(x0, x1, y0, y1, z0, z1):
    v = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1)
                  for z in (z0, z1)], dtype=np.float32)
    f = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
         (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    return v, np.array(f, dtype=np.uint16)


def make_glb(path):
    """Two boxes on a two-bone skeleton, glTF Y-up, metres."""
    lo_v, lo_f = _box(-0.1, 0.1, 0.0, 0.5, -0.1, 0.1)
    hi_v, hi_f = _box(-0.1, 0.1, 0.5, 1.0, -0.1, 0.1)
    v = np.concatenate([lo_v, hi_v])
    f = np.concatenate([lo_f, hi_f + 8]).astype(np.uint16)
    joints = np.zeros((16, 4), dtype=np.uint16)
    joints[8:, 0] = 1
    weights = np.zeros((16, 4), dtype=np.float32)
    weights[:, 0] = 1.0
    ibm = np.array([np.eye(4).T.ravel(),
                    np.array([[1, 0, 0, 0], [0, 1, 0, -0.5], [0, 0, 1, 0],
                              [0, 0, 0, 1]], dtype=float).T.ravel()],
                   dtype=np.float32)
    times = np.array([0.0, 1.0], dtype=np.float32)
    s = math.sin(math.pi / 4)
    quats = np.array([[0, 0, 0, 1], [0, 0, s, s]], dtype=np.float32)
    blob = b""
    views, accs = [], []

    def add(arr, ct, typ, mm=False):
        nonlocal blob
        data = np.ascontiguousarray(arr).tobytes()
        views.append({"buffer": 0, "byteOffset": len(blob),
                      "byteLength": len(data)})
        blob += data + b"\0" * ((4 - len(data) % 4) % 4)
        a = {"bufferView": len(views) - 1, "componentType": ct,
             "count": len(arr), "type": typ}
        if mm:
            a["min"], a["max"] = arr.min(0).tolist(), arr.max(0).tolist()
        accs.append(a)
        return len(accs) - 1
    j = {
        "asset": {"version": "2.0"}, "scene": 0,
        "scenes": [{"nodes": [0, 2]}],
        "nodes": [{"name": "Hips", "children": [1]},
                  {"name": "Chest", "translation": [0, 0.5, 0]},
                  {"name": "Body", "mesh": 0, "skin": 0}],
        "meshes": [{"primitives": [{"attributes": {
            "POSITION": add(v, 5126, "VEC3", True),
            "JOINTS_0": add(joints, 5123, "VEC4"),
            "WEIGHTS_0": add(weights, 5126, "VEC4")},
            "indices": add(f.reshape(-1, 1), 5123, "SCALAR"),
            "material": 0}]}],
        "materials": [{"name": "Skin", "pbrMetallicRoughness": {
            "baseColorFactor": [0.5, 0.25, 0.1, 1]}}],
        "skins": [{"joints": [0, 1], "inverseBindMatrices":
                   add(ibm, 5126, "MAT4"), "skeleton": 0}],
        "animations": [{"name": "Armature|Wave", "samplers": [{
            "input": add(times.reshape(-1, 1), 5126, "SCALAR"),
            "output": add(quats, 5126, "VEC4")}],
            "channels": [{"sampler": 0, "target": {"node": 1,
                                                    "path": "rotation"}}]}],
    }
    j["buffers"] = [{"byteLength": len(blob)}]
    j["bufferViews"], j["accessors"] = views, accs
    js = json.dumps(j).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2,
                             12 + 8 + len(js) + 8 + len(blob)))
        fh.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        fh.write(struct.pack("<II", len(blob), 0x004E4942) + blob)
    return path


@pytest.fixture
def char(app, tmp_path):
    src = make_glb(tmp_path / "column.glb")
    doc = DocumentModel()
    comp = character.import_character(doc, src, height_mm=1000,
                                      parts_dir=tmp_path / "parts")
    return doc, comp, tmp_path


def _bounds(node):
    pts = np.array([v for t in mesh.tessellate(node) for v in t])
    return pts.min(0), pts.max(0)


def test_import_makes_a_standing_coloured_object(char):
    doc, comp, _ = char
    info = comp.params["character"]
    assert comp.type == "component"
    assert set(info["bones"]) == {"Hips", "Chest"}
    lo, hi = _bounds(comp)
    assert abs(lo[2]) < 1e-3 and abs(hi[2] - 1000) < 1e-3   # z 0..1000 mm
    assert abs(info["bones"]["Chest"][2] - 500) < 1e-3       # Z up
    parts = character.body_parts(comp)
    assert len(parts) == 1 and os.path.exists(parts[0].params["path"])
    assert parts[0].parent.params["color"].startswith("#")
    assert [c["name"] for c in character.pose(doc, comp)["clips"]] == ["Wave"]


def test_bone_node_code_round_trips(char):
    doc, comp, _ = char
    box = doc.add_node("cube", dict(width=50, depth=50, height=50,
                                    center=True, x=0, y=0, z=950),
                       parent=comp)
    (bone, name), = character.attach(doc, [box])
    assert name == "Chest" and bone.type == "bone"     # nearest bone
    code = doc.to_scad()
    assert 'kcad_bone(name = "Chest"' in code and "module kcad_bone" in code
    back, _warnings = scadparse.parse_scad(code)
    assert any(n.type == "bone" and n.params["name"] == "Chest"
               for n in back.walk())
    assert not validate(doc.root)
    # the parts keep their colours through the bone node
    doc.set_color([box], "#00ff00")
    cols = {c[0] for _t, c in mesh.tessellate_colored(bone) if c}
    assert cols == {"#00ff00"}


def test_pose_turns_body_and_parts_with_the_bone(char):
    doc, comp, _ = char
    box = doc.add_node("cube", dict(width=40, depth=40, height=40,
                                    center=True, x=0, y=0, z=1000),
                       parent=comp)
    (bone, _), = character.attach(doc, [box], "Chest")
    out = character.pose(doc, comp, "Wave", 1.0)
    assert out["bones_with_parts"] == 1
    # Chest turned 90° about glTF +Z = KherveCAD +Y: the top of the
    # column (and the box riding on it) swings sideways to -X
    lo, hi = _bounds(bone)
    centre = (lo + hi) / 2
    assert abs(centre[0] + 500) < 1.0 and abs(centre[2] - 500) < 1.0
    body = character.body_parts(comp)[0]
    assert "pose-" in body.params["path"]
    blo, bhi = _bounds(comp)
    assert blo[0] < -450 and bhi[2] < 620          # bent over at the chest
    character.pose(doc, comp)                      # back to rest
    lo, hi = _bounds(bone)
    assert abs((lo + hi)[2] / 2 - 1000) < 1.0
    assert "body-" in character.body_parts(comp)[0].params["path"]


def test_turns_without_a_clip(char):
    doc, comp, _ = char
    character.pose(doc, comp, turns={"Chest": [0, 0, 90]})
    blo, _ = _bounds(comp)
    assert blo[0] < -450


def test_export_binds_parts_and_keeps_clips(char):
    doc, comp, tmp = char
    box = doc.add_node("cube", dict(width=40, depth=40, height=40,
                                    center=True, x=0, y=0, z=1020),
                       parent=comp)
    doc.set_color([box], "#ff0000")
    loose = doc.add_node("sphere", dict(radius=30, x=0, y=0, z=100),
                         parent=comp)
    character.attach(doc, [box.parent if box.parent.type == "color"
                            else box], "Chest")
    out = character.export_glb(doc, comp, tmp / "out.glb")
    assert out["parts"] == 2 and out["clips"] == ["Wave"]
    assert set(out["bones_used"]) == {"Chest", "Hips"}  # loose -> Hips
    g = character.Glb(out["path"])
    node = next(n for n in g.nodes if n.get("name") == "KherveCAD parts")
    skin = g.json["skins"][node["skin"]]
    prims = g.json["meshes"][node["mesh"]]["primitives"]
    red = next(p for p in prims if g.json["materials"][p["material"]]
               ["name"] == "Gear #ff0000")
    pos = g.accessor(red["attributes"]["POSITION"])
    jo = g.accessor(red["attributes"]["JOINTS_0"]).astype(int)
    assert np.allclose(pos[:, 1].mean(), 1.02, atol=0.01)      # back in metres
    assert {skin["joints"][k] for k in jo[:, 0]} == {1}       # Chest only
    # posed by the clip like the body: at t = 1 the box swings to -X
    W = g.world(g.sample(0, 1.0))
    ibm = g.accessor(skin["inverseBindMatrices"]).reshape(-1, 4, 4) \
        .transpose(0, 2, 1)
    m = W[1] @ ibm[skin["joints"].index(1)]
    p = (np.c_[pos, np.ones(len(pos))] @ m.T)[:, :3].mean(0)
    assert abs(p[0] + 0.52) < 0.01 and abs(p[1] - 0.5) < 0.01
    assert loose is not None


def test_errors_say_what_to_do(char, tmp_path):
    doc, comp, _ = char
    with pytest.raises(character.CharacterError, match="no bone|No bone"):
        box = doc.add_node("cube", parent=comp)
        character.attach(doc, [box], "Tail")
    with pytest.raises(character.CharacterError, match="own body"):
        character.attach(doc, [character.body_parts(comp)[0]])
    with pytest.raises(character.CharacterError, match="No clip"):
        character.pose(doc, comp, "Dance")
    bad = tmp_path / "x.glb"
    bad.write_bytes(b"nope")
    with pytest.raises(character.CharacterError, match="not a binary"):
        character.import_character(doc, bad)


# ------------------------------------------------------------ the window

@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    yield win
    win._dirty = False          # no "discard unsaved changes?" on close
    win.close()


def _actions(win):
    return {a.text().replace("&", ""): a
            for a in win.menuBar().actions()[0].menu().actions()}


def test_file_menu_imports_poses_and_exports(window, tmp_path, monkeypatch):
    from PyQt5.QtWidgets import QFileDialog, QMessageBox
    from khervecad import character_ui
    acts = _actions(window)
    for label in ("Import Animated Character (GLB)...",
                  "Export Animated Character (GLB)...", "Pose Character..."):
        assert label in acts
    src = make_glb(tmp_path / "column.glb")
    monkeypatch.setattr(character, "default_parts_dir",
                        lambda _s: str(tmp_path / "parts"))
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(src), "")))
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "exec_", lambda self: 0)
    def fail(*a, **k):
        raise AssertionError(f"warning shown: {a[2] if len(a) > 2 else a}")
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(fail))
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Discard))
    acts["Import Animated Character (GLB)..."].trigger()
    comps = character_ui.characters(window)
    assert len(comps) == 1
    comp = comps[0]
    # pose through the panel: the Wave clip at its end
    acts["Pose Character..."].trigger()
    dlg = window._pose_dialog
    dlg.clip.setCurrentIndex(dlg.clip.findData("Wave"))
    dlg.time.setValue(dlg.STEPS)
    assert comp.params["character"]["clip"] == "Wave"
    assert abs(comp.params["character"]["time"] - 1.0) < 1e-6
    dlg.clip.setCurrentIndex(0)                       # back to rest
    assert comp.params["character"]["clip"] == ""
    dlg.close()
    # something to export, then File ▸ Export
    window.model.add_node("cube", dict(width=40, depth=40, height=40,
                                       center=True, z=1000), parent=comp)
    out_path = tmp_path / "out.glb"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(out_path), "")))
    acts["Export Animated Character (GLB)..."].trigger()
    assert out_path.exists()
    assert character.Glb(out_path).clips()[0][0] == "Wave"
