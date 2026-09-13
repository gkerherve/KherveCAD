"""The Printables upload bundle.

The engine is disabled in the suite (KHERVECAD_DISABLE_ENGINE), so
these run the no-OpenSCAD path: the tessellated STL, the built-in
renderer's previews, and the warnings that say so.

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
    assert ".scad and .kcad" in both
    mesh_only = printables.credit(("stl",))
    assert ".scad" not in mesh_only
    assert ".kcad" not in mesh_only
    assert "KherveCAD" in mesh_only


# ── the generated description ───────────────────────────────────

def test_description_reports_size_and_parameters(cube_window):
    text = printables.default_description(cube_window, "Cube")
    assert "CUBE" in text
    assert "SIZE" in text
    assert "wall = 3" in text
    assert "PRINT SETTINGS" in text
    assert printables.TOOLS_URL in text


def test_the_description_opens_with_prose_not_a_placeholder(
        cube_window):
    """The opening line used to be a note to the author, and it went
    out unedited. It has to read as a finished sentence."""
    text = printables.default_description(cube_window, "Cube")
    assert "One or two sentences" not in text
    first = text.splitlines()[2]
    assert first.startswith("Cube is a 20 x 20 x 20 mm part")
    assert first.endswith(".")


def test_the_opening_counts_what_the_model_is_made_of(cube_window):
    from khervecad.model import CadNode
    cube_window.model.root.add(CadNode("difference", "Difference"))
    text = printables.opening(cube_window, "Cube")
    assert "1 boolean" in text
    assert "1 dimension is named" in text


def test_description_is_plain_text_not_markdown(cube_window):
    """Printables' description box shows Markdown back as literal
    hashes and backticks, so the draft must not contain any."""
    text = printables.default_description(cube_window, "Cube")
    assert "#" not in text
    assert "`" not in text
    assert "](" not in text


# ── the bundle ──────────────────────────────────────────────────

def test_bundle_writes_every_requested_file(cube_window, tmp_path):
    bundle = printables.build_bundle(
        cube_window, tmp_path / "out", title="My Cube",
        formats=("stl", "scad", "kcad"), views=("Isometric", "Front"))
    names = {Path(f).name for f in bundle["files"]}
    assert {"My-Cube.stl", "My-Cube.scad", "My-Cube.kcad",
            "description.txt", "upload-form.txt",
            "printables.json"} <= names
    assert len(bundle["images"]) == 2
    for path in bundle["files"]:
        assert Path(path).stat().st_size > 0


def test_bundle_zips_the_source_files(cube_window, tmp_path):
    import zipfile
    bundle = printables.build_bundle(
        cube_window, tmp_path / "out", title="My Cube",
        formats=("stl", "scad", "kcad"), views=())
    path = tmp_path / "out" / "My-Cube-source.zip"
    assert str(path) in bundle["files"]
    with zipfile.ZipFile(path) as z:
        assert sorted(z.namelist()) == ["My-Cube.kcad", "My-Cube.scad"]
        assert z.read("My-Cube.scad").decode().strip()
    bare = printables.build_bundle(cube_window, tmp_path / "stl",
                                   title="Cube", formats=("stl",),
                                   views=())
    assert not any(f.endswith(".zip") for f in bare["files"])


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
        description="Mine\n\nA cube.", formats=("scad",), views=())
    body = bundle["description"]
    assert body.startswith("Mine")
    assert printables.TOOLS_URL in body
    assert body.count(printables.CREDIT_HEADING) == 1


def test_credit_is_not_duplicated(cube_window, tmp_path):
    once = printables.default_description(cube_window, "Cube")
    bundle = printables.build_bundle(
        cube_window, tmp_path / "out", title="Cube",
        description=once, formats=("scad",), views=())
    assert bundle["description"].count(
        printables.CREDIT_HEADING) == 1


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
        {"title": "Cube", "description": "CUBE\n\nA cube.",
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


# ── the upload form ─────────────────────────────────────────────

def test_summary_fits_printables_limit(cube_window):
    text = printables.default_summary(cube_window, "A cube with a "
                                                   "very long name " * 4)
    assert len(text) <= printables.SUMMARY_LIMIT


def test_summary_names_the_model_and_its_size(cube_window):
    text = printables.default_summary(cube_window, "Cube")
    assert text.startswith("Cube")
    assert "20 x 20 x 20 mm" in text


def test_form_answers_every_required_field(cube_window):
    text = printables.form_answers(
        cube_window, title="Cube", summary="A cube",
        tags=["cube", "test"], category="Household",
        license="CC BY 4.0")
    for field in ("Model name", "Summary", "Main category",
                  "Additional tags", "Model origin", "Licence"):
        assert field in text
    assert "Cube" in text and "A cube" in text
    assert "Household" in text
    assert "cube test" in text
    assert printables.DEFAULT_ORIGIN in text


def test_bundle_records_the_form_answers(cube_window, tmp_path):
    import json
    bundle = printables.build_bundle(
        cube_window, tmp_path / "out", title="Cube", summary="A cube",
        category="Household", formats=("scad",), views=())
    meta = json.loads((tmp_path / "out" / "printables.json")
                      .read_text())
    assert meta["summary"] == "A cube"
    assert meta["category"] == "Household"
    assert meta["origin"] == printables.DEFAULT_ORIGIN
    assert bundle["summary"] == "A cube"
    assert "Household" in Path(bundle["form"]).read_text()


def test_a_long_summary_is_trimmed_with_a_warning(cube_window,
                                                  tmp_path):
    bundle = printables.build_bundle(
        cube_window, tmp_path / "out", title="Cube", summary="x" * 300,
        formats=("scad",), views=())
    assert len(bundle["summary"]) <= printables.SUMMARY_LIMIT
    assert any("summary" in w for w in bundle["warnings"])


def test_the_cover_render_comes_first(cube_window, tmp_path):
    bundle = printables.build_bundle(
        cube_window, tmp_path / "out", title="Cube", formats=("scad",),
        views=("Front", "Isometric"))
    names = [Path(p).name for p in bundle["images"]]
    assert names[0] == "Cube-1-isometric.png"


def test_tool_rejects_an_unknown_category(cube_window, tmp_path):
    result = McpToolExecutor(cube_window).execute(
        "publish_to_printables",
        {"title": "Cube", "folder": str(tmp_path / "out"),
         "category": "Spaceships"})
    assert "Spaceships" in result["error"]


def test_a_render_is_cropped_to_the_model(tmp_path):
    """OpenSCAD frames the bounding sphere, so a small part sits in a
    sea of background — the cover has to be trimmed to it."""
    from PyQt5.QtGui import QColor, QImage
    image = QImage(800, 600, QImage.Format_RGB32)
    image.fill(QColor("white"))
    for y in range(290, 310):
        for x in range(390, 410):
            image.setPixelColor(x, y, QColor("black"))
    path = tmp_path / "shot.png"
    image.save(str(path))

    assert printables.trim_to_content(str(path))
    out = QImage(str(path))
    assert out.width() < 800
    assert out.width() >= 800 * 0.45      # never trimmed to a stamp
    assert abs(out.width() / out.height() - 4 / 3.0) < 0.05


def test_a_full_frame_render_is_left_alone(tmp_path):
    from PyQt5.QtGui import QColor, QImage
    image = QImage(800, 600, QImage.Format_RGB32)
    image.fill(QColor("black"))
    image.setPixelColor(0, 0, QColor("white"))
    path = tmp_path / "full.png"
    image.save(str(path))
    assert not printables.trim_to_content(str(path))
    assert QImage(str(path)).width() == 800


def test_print_settings_can_be_overridden(cube_window, tmp_path):
    """The block is an answer on the form, so a model that wants PETG
    has to be able to say PETG rather than shipping the default."""
    import json
    bundle = printables.build_bundle(
        cube_window, tmp_path / "out", title="Cube",
        formats=("scad",), views=(),
        print_settings={"Filament": "PETG", "Supports": "yes"})
    form = Path(bundle["form"]).read_text()
    assert "Filament: PETG" in form
    assert "Supports: yes" in form
    assert "Infill: 20%" in form            # the rest still defaults
    meta = json.loads((tmp_path / "out" / "printables.json")
                      .read_text())
    assert meta["print_settings"]["Filament"] == "PETG"


def test_the_form_never_tells_the_author_to_fill_it_in(cube_window):
    text = printables.form_answers(cube_window, title="Cube")
    assert "adjust to what you actually printed" not in text.lower()


def test_an_assembly_gets_one_stl_per_object(window, tmp_path):
    from khervecad.model import CadNode
    m = window.model
    for name, x in (("Base plate", 0.0), ("Lid", 50.0)):
        comp = m.new_component(name)
        comp.params["x"] = x
        m.add_node("cube", parent=comp)
    hidden = m.new_component("Draft", visible=False)
    m.add_node("sphere", parent=hidden)
    bundle = printables.build_bundle(window, tmp_path / "out",
                                     title="Box", formats=("stl",),
                                     views=())
    names = sorted(Path(f).name for f in bundle["files"]
                   if f.endswith(".stl"))
    assert names == ["Box-Base-plate.stl", "Box-Lid.stl", "Box.stl"]
    # each part at its own origin, not where it sits in the assembly
    from khervecad import engine
    lid = engine.parse_mesh(str(tmp_path / "out" / "Box-Lid.stl"))
    assert min(v[0] for t in lid for v in t) == pytest.approx(0.0)
    # a single-Object document writes the whole-model STL only
    m.clear()
    m.add_node("cube")
    single = printables.build_bundle(window, tmp_path / "one",
                                     title="Cube", formats=("stl",),
                                     views=())
    assert not any(Path(f).name.startswith("Cube-") and f.endswith(".stl")
                   for f in single["files"])


def test_the_texts_say_vibe_designed(cube_window):
    assert "Vibe designed in KherveCAD" in printables.credit()
    assert "vibe designed in KherveCAD" in printables.default_summary(
        cube_window, "Cube")
    assert "vibe designed in KherveCAD" in printables.opening(
        cube_window, "Cube")
