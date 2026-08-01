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


# ------------------------------------------- stale renders never land

class _FakeProcess:
    """Stands in for the finished QProcess _finished() inspects."""

    def exitStatus(self):
        from PyQt5.QtCore import QProcess
        return QProcess.NormalExit

    def exitCode(self):
        return 0

    def readAllStandardError(self):
        return b""


@pytest.fixture
def scad_engine(qt_app, tmp_path):
    eng = engine.ScadEngine()
    eng.binary = "openscad"                    # pretend one was found
    return eng


@pytest.fixture(scope="session")
def qt_app():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _launch(eng, code):
    """Request a render and do _start's bookkeeping by hand, so the
    engine believes OpenSCAD is running without spawning it."""
    eng.request_render(code)
    eng._timer.stop()
    eng._pending_code = None
    eng._running_generation = eng._generation
    eng._process = _FakeProcess()


def _run(eng, code, stl_path):
    """One render, launched and finished."""
    _launch(eng, code)
    eng._finished(str(stl_path))


def test_cancelled_render_never_reaches_the_view(scad_engine, tmp_path):
    """A render requested before the document was coloured must not
    land afterwards and wipe the colour preview."""
    path = tmp_path / "model.stl"
    engine.write_stl(TRIS, str(path))
    got = []
    scad_engine.mesh_ready.connect(got.append)

    _launch(scad_engine, "cube(1);")
    scad_engine.cancel()                        # ...the model changed
    scad_engine._finished(str(path))
    assert got == []                            # dropped, not painted

    # and the engine still works for the next render
    _run(scad_engine, "cube(2);", path)
    assert len(got) == 1


def test_superseded_render_is_dropped(scad_engine, tmp_path):
    """While one render runs, a newer request supersedes it: the old
    mesh is of the old model, so it must not be painted."""
    path = tmp_path / "model.stl"
    engine.write_stl(TRIS, str(path))
    got = []
    scad_engine.mesh_ready.connect(got.append)

    _launch(scad_engine, "cube(1);")
    scad_engine.request_render("cube(9);")      # newer model
    scad_engine._timer.stop()
    scad_engine._finished(str(path))
    assert got == []
    assert scad_engine._pending_code == "cube(9);"   # still queued


def test_completed_render_reaches_the_view(scad_engine, tmp_path):
    path = tmp_path / "model.stl"
    engine.write_stl(TRIS, str(path))
    got = []
    scad_engine.mesh_ready.connect(got.append)
    _run(scad_engine, "cube(1);", path)
    assert len(got) == 1 and len(got[0]) == 2


# --------------------------------------------- per-part render queue

def test_part_renders_are_queued_once_and_keyed(scad_engine):
    """Parts are queued by content key: the same part asked for twice
    runs once, and a key already running is not queued again."""
    scad_engine.request_part_render("key-a", "cube(1);")
    scad_engine.request_part_render("key-a", "cube(1);")
    scad_engine.request_part_render("key-b", "sphere(1);")
    assert list(scad_engine._part_queue) == ["key-a", "key-b"]

    scad_engine._timer.stop()
    scad_engine._start_part()                    # key-a is now running
    assert scad_engine._running_part == "key-a"
    scad_engine.request_part_render("key-a", "cube(1);")
    assert list(scad_engine._part_queue) == ["key-b"]


def test_part_result_is_emitted_with_its_key(scad_engine, tmp_path):
    path = tmp_path / "part.stl"
    engine.write_stl(TRIS, str(path))
    got = []
    scad_engine.part_ready.connect(lambda k, m: got.append((k, len(m))))
    scad_engine.request_part_render("key-a", "cube(1);")
    scad_engine._timer.stop()
    scad_engine._start_part()
    scad_engine._process = _FakeProcess()
    scad_engine._part_finished("key-a", str(path))
    assert got == [("key-a", 2)]


def test_cancelling_the_document_render_keeps_part_renders(scad_engine):
    """A multi-coloured document cancels the whole-document render —
    the per-part renders are exactly what makes it exact, so they must
    survive (and stay scheduled)."""
    scad_engine.request_render("cube(1);")
    scad_engine.request_part_render("key-a", "cube(1);")
    scad_engine.cancel()
    assert scad_engine._pending_code is None
    assert list(scad_engine._part_queue) == ["key-a"]
    assert scad_engine._timer.isActive()


def test_bundled_openscad_is_found_beside_a_frozen_app(tmp_path, monkeypatch):
    """The installer ships OpenSCAD in an openscad/ subfolder of the app
    directory. If this lookup breaks, an installed copy silently falls
    back to the approximate built-in preview — the exact thing bundling
    it is meant to prevent."""
    app = tmp_path / "app"
    (app / "openscad").mkdir(parents=True)
    exe = app / "openscad" / engine._OPENSCAD_EXE
    exe.write_bytes(b"")
    monkeypatch.setattr(engine.sys, "frozen", True, raising=False)
    monkeypatch.setattr(engine.sys, "executable", str(app / "KherveCAD.exe"))
    assert engine.bundled_openscad() == str(exe)


def test_no_bundle_means_no_bundled_path(tmp_path, monkeypatch):
    monkeypatch.setattr(engine.sys, "frozen", True, raising=False)
    monkeypatch.setattr(engine.sys, "executable", str(tmp_path / "KherveCAD.exe"))
    monkeypatch.setattr(engine, "__file__", str(tmp_path / "khervecad" / "engine.py"))
    assert engine.bundled_openscad() == ""


def test_a_located_binary_still_wins_over_the_bundle(tmp_path, monkeypatch):
    """Edit > Locate OpenSCAD must keep working in an installed build."""
    chosen = tmp_path / "custom-openscad.exe"
    chosen.write_bytes(b"")
    monkeypatch.setattr(engine, "bundled_openscad", lambda: str(tmp_path / "bundled.exe"))
    monkeypatch.delenv("KHERVECAD_DISABLE_ENGINE", raising=False)
    monkeypatch.setattr(engine.QSettings, "value",
                        lambda self, key, default="": str(chosen))
    assert engine.find_openscad() == str(chosen)
