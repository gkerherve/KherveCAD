"""The Printables upload bundle.

The engine is disabled in the suite (KHERVECAD_DISABLE_ENGINE), so
these run the no-OpenSCAD path: the tessellated STL, the screen-grab
previews, and the warnings that say so.

Run with: python -m pytest tests/  (offscreen Qt).

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
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import printables
from khervecad.mcp_schema import BY_NAME, FORMATS
from khervecad.mcp_tools import McpToolExecutor


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


@pytest.fixture
def cube_window(window):
    from khervecad.model import CadNode
    window.model.root.add(CadNode("assign", "wall"))
    window.model.root.children[-1].params.update(
        {"variable": "wall", "value": "3"})
    window.model.root.add(CadNode("cube", "Cube"))
    window.model.structure_changed.emit()
    return window


# ── naming ──────────────────────────────────────────────────────

def test_slug_is_a_filename():
    assert printables.slug("Door Stopper (v2)!") == "Door-Stopper-v2"


def test_slug_never_empty():
    assert printables.slug("!!!") == "model"


# ── the credit ──────────────────────────────────────────────────

def test_credit_names_the_app_and_the_site():
    text = printables.credit()
    assert "KherveCAD" in text
    assert printables.TOOLS_URL in text
    assert "Claude" in text


def test_credit_only_promises_source_it_ships():
    both = printables.credit(("stl", "scad", "kcad"))
    assert "`.scad` and `.kcad`" in both
    mesh_only = printables.credit(("stl",))
    assert ".scad" not in mesh_only
    assert ".kcad" not in mesh_only
    assert "KherveCAD" in mesh_only


# ── the generated description ───────────────────────────────────

def test_description_reports_size_and_parameters(cube_window):
    text = printables.default_description(cube_window, "Cube")
    assert "# Cube" in text
    assert "## Size" in text
    assert "`wall` = 3" in text
    assert "Print settings" in text
    assert printables.TOOLS_URL in text


# ── the bundle ──────────────────────────────────────────────────

def test_bundle_writes_every_requested_file(cube_window, tmp_path):
    bundle = printables.build_bundle(
        cube_window, tmp_path / "out", title="My Cube",
        formats=("stl", "scad", "kcad"), views=("Isometric", "Front"))
    names = {Path(f).name for f in bundle["files"]}
    assert {"My-Cube.stl", "My-Cube.scad", "My-Cube.kcad",
            "description.md", "printables.json"} <= names
    assert len(bundle["images"]) == 2
    for path in bundle["files"]:
        assert Path(path).stat().st_size > 0


def test_bundle_only_writes_what_was_asked_for(cube_window, tmp_path):
    bundle = printables.build_bundle(
        cube_window, tmp_path / "out", title="Cube",
        formats=("scad",), views=())
    names = {Path(f).name for f in bundle["files"]}
    assert "Cube.scad" in names
    assert not any(n.endswith((".stl", ".kcad", ".3mf")) for n in names)
    assert bundle["images"] == []


def test_bundle_keeps_a_supplied_description_and_adds_the_credit(
        cube_window, tmp_path):
    bundle = printables.build_bundle(
        cube_window, tmp_path / "out", title="Cube",
        description="# Mine\n\nA cube.", formats=("scad",), views=())
    body = bundle["description"]
    assert body.startswith("# Mine")
    assert printables.TOOLS_URL in body
    assert body.count("## Made with") == 1


def test_credit_is_not_duplicated(cube_window, tmp_path):
    once = printables.default_description(cube_window, "Cube")
    bundle = printables.build_bundle(
        cube_window, tmp_path / "out", title="Cube",
        description=once, formats=("scad",), views=())
    assert bundle["description"].count("## Made with") == 1


def test_metadata_records_where_it_came_from(cube_window, tmp_path):
    import json
    printables.build_bundle(cube_window, tmp_path / "out", title="Cube",
                            tags=["one", "two"], formats=("scad",),
                            views=())
    meta = json.loads((tmp_path / "out" / "printables.json")
                      .read_text())
    assert meta["title"] == "Cube"
    assert meta["tags"] == ["one", "two"]
    assert meta["made_with"]["app"] == "KherveCAD"
    assert meta["upload_url"] == printables.UPLOAD_URL


def test_no_openscad_is_a_warning_not_a_failure(cube_window, tmp_path):
    bundle = printables.build_bundle(
        cube_window, tmp_path / "out", title="Cube",
        formats=("stl", "3mf"), views=())
    assert any("3MF" in w for w in bundle["warnings"])
    assert not any(f.endswith(".3mf") for f in bundle["files"])
    assert any(f.endswith(".stl") for f in bundle["files"])


# ── the MCP tool ────────────────────────────────────────────────

def test_tool_is_in_the_schema():
    tool = BY_NAME["publish_to_printables"]
    assert "title" in tool["input_schema"]["required"]
    # the description is prompt text: it has to say what it cannot do
    assert "no upload api" in tool["description"].lower()


def test_tool_builds_a_bundle(cube_window, tmp_path):
    result = McpToolExecutor(cube_window).execute(
        "publish_to_printables",
        {"title": "Cube", "description": "# Cube\n\nA cube.",
         "folder": str(tmp_path / "out"), "formats": ["scad"],
         "views": []})
    assert "error" not in result
    assert result["published"] is False
    assert "Cube.scad" in result["files"]
    assert printables.UPLOAD_URL in result["next_step"]


def test_tool_requires_a_title(cube_window):
    result = McpToolExecutor(cube_window).execute(
        "publish_to_printables", {})
    assert "title" in result["error"].lower()


def test_tool_rejects_an_unknown_format(cube_window, tmp_path):
    result = McpToolExecutor(cube_window).execute(
        "publish_to_printables",
        {"title": "Cube", "folder": str(tmp_path / "out"),
         "formats": ["step"]})
    assert "step" in result["error"]


def test_tool_rejects_an_unknown_view(cube_window, tmp_path):
    result = McpToolExecutor(cube_window).execute(
        "publish_to_printables",
        {"title": "Cube", "folder": str(tmp_path / "out"),
         "views": ["Sideways"]})
    assert "Sideways" in result["error"]


def test_tool_never_opens_the_browser_unasked(cube_window, tmp_path,
                                              monkeypatch):
    opened = []
    monkeypatch.setattr(printables, "open_upload_page",
                        lambda: opened.append(True))
    monkeypatch.setattr(printables, "reveal", lambda p: None)
    McpToolExecutor(cube_window).execute(
        "publish_to_printables",
        {"title": "Cube", "folder": str(tmp_path / "out"),
         "formats": ["scad"], "views": []})
    assert opened == []


def test_the_bundle_formats_match_the_schema():
    assert set(FORMATS) == {"stl", "3mf", "scad", "kcad"}
