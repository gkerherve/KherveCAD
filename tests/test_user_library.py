"""My Library (user_library.py): an Object saved with a title and a
description lands in the user's folder as a standalone .kcad, lists in
the Library under "My library: <section>", is found by its description,
and builds back — with the Objects it instances.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json

import pytest

from khervecad import library, mesh, user_library
from khervecad.model import CadNode, validate


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setenv("KHERVECAD_USER_LIBRARY", str(tmp_path))
    yield tmp_path
    monkeypatch.undo()          # back to the session's empty folder first
    user_library.refresh(library.PARTS)


def _hook_object():
    part = CadNode("component", "Bike hook")
    part.add(CadNode("cube", "Plate", dict(x=0.0, y=0.0, z=0.0, width=40.0,
                                          depth=10.0, height=120.0,
                                          center=False)))
    return part


def test_a_saved_part_lists_with_its_description_and_builds(lib):
    root = CadNode("root", "root")
    obj = _hook_object()
    root.add(obj)
    saved = user_library.save(obj, "Wall-mounted bike hook, 120 mm",
                              "Holds a bicycle by its front wheel; two "
                              "screw holes 80 mm apart.", "Garage",
                              ["bicycle", "velo"], root=root)
    path = lib / "Garage" / "Wall-mounted bike hook, 120 mm.kcad"
    assert saved["path"] == str(path) and path.exists()
    data = json.loads(path.read_text())
    assert data["library"]["description"].startswith("Holds a bicycle")
    mine = user_library.refresh(library.PARTS)
    spec = mine[saved["part_id"]]
    assert spec["category"] == "My library: Garage"
    assert library.PARTS[saved["part_id"]] is spec
    assert user_library.matches(spec, saved["part_id"], ["velo"])
    assert user_library.matches(spec, saved["part_id"], ["front", "wheel"])
    node = library.build_part(saved["part_id"], {})
    assert node.name == "Wall-mounted bike hook, 120 mm"
    assert not validate(node) and mesh.tessellate(node, fn=8)


def test_an_instance_saves_the_objects_it_needs(lib):
    root = CadNode("root", "root")
    screw = CadNode("component", "Screw")
    screw.visible = False
    screw.add(CadNode("cylinder", "Shank", dict(
        x=0.0, y=0.0, z=0.0, height=30.0, radius_bottom=2.0,
        radius_top=2.0, segments=12, center=False)))
    hook = _hook_object()
    hook.add(CadNode("reference", "Screw 1", dict(ref="Screw")))
    root.add(screw)
    root.add(hook)
    placed = CadNode("reference", "Hook placed", dict(ref="Bike hook",
                                                       x=500.0))
    root.add(placed)
    saved = user_library.save(placed, "Hook with screw", "A test.",
                              root=root)
    tree = json.loads(open(saved["path"]).read())["tree"]
    names = [c["name"] for c in tree["children"]]
    assert names == ["Screw", "Bike hook"]
    assert tree["children"][-1]["visible"] is True
    assert tree["children"][0]["visible"] is False


def test_a_title_is_required_and_resaving_updates(lib):
    obj = _hook_object()
    with pytest.raises(ValueError):
        user_library.save(obj, "  ", "x")
    a = user_library.save(obj, "Hook", "first")
    b = user_library.save(obj, "Hook", "second")
    assert a["path"] == b["path"]
    assert user_library.read_info(b["path"])["description"] == "second"
    # no area given: "hook" files it with the fasteners and brackets
    assert (lib / "Fasteners & brackets" / "Hook.kcad").exists()
    assert user_library.parts()[a["part_id"]]["category"] == \
        "My library: Fasteners & brackets"


def test_parts_are_filed_by_area_and_a_new_area_makes_a_folder(lib):
    obj = _hook_object()
    cases = [("sports", "Stadium seat", "Sport"),
             ("Unit cells", "Quartz cell", "Unit cells & crystals"),
             ("trees and plants", "Oak", "Trees & plants"),
             ("football", "Corner flag", "Sport"),
             ("MOLECULES", "Caffeine", "Molecules"),
             ("Astronomy", "Telescope mount", "Astronomy"),
             ("astronomy", "Star map", "Astronomy"),          # reused
             ("", "Four-poster bed, 2 m, oak frame", "House & home"),
             ("", "Wibble", "General")]
    for section, title, folder_name in cases:
        saved = user_library.save(obj, title, "desc", section)
        assert saved["category"] == f"My library: {folder_name}", (
            section, title)
    assert (lib / "Astronomy").is_dir()
    assert not (lib / "astronomy").exists() or \
        (lib / "astronomy").samefile(lib / "Astronomy")
    assert "Sport" in user_library.existing_sections()


def test_manage_sections_and_parts(lib):
    obj = _hook_object()
    a = user_library.save(obj, "Bracket A", "one", "Brackets")
    user_library.add_section("Drafts")
    moved = user_library.move(a["path"], "Drafts")
    assert moved.parent.name == "Drafts"
    edited = user_library.update_info(moved, "Bracket B", "new text",
                                      ["x"])
    assert edited.name == "Bracket B.kcad"
    assert user_library.read_info(edited)["description"] == "new text"
    user_library.rename_section("Drafts", "Old drafts")
    assert (lib / "Old drafts" / "Bracket B.kcad").exists()
    user_library.remove(lib / "Old drafts")
    assert not (lib / "Old drafts").exists()
    assert a["uid"] in user_library.ignored()
    with pytest.raises(ValueError):
        user_library.remove(lib)
    other = lib.parent / "outside.kcad"
    other.write_text("{}")
    with pytest.raises(ValueError):
        user_library.remove(other)
    src = lib.parent / "import_me.kcad"
    src.write_text(open(user_library.save(obj, "Tmp", "t", "X")["path"])
                   .read())
    dst = user_library.import_file(src, "Imported")
    assert dst.parent.name == "Imported"


def test_autosave_keeps_designs_not_library_parts(lib):
    obj = _hook_object()
    saved = user_library.autosave(obj)
    assert saved and saved["category"] == "My library: Fasteners & brackets"
    meta = obj.params["library"]
    assert meta["uid"] == saved["uid"] and "generated" in \
        user_library.read_info(saved["path"])["description"]
    obj.name = "Garage bike hook"                 # renamed: file follows
    again = user_library.autosave(obj)
    assert again["uid"] == saved["uid"]
    assert not (lib / "Fasteners & brackets" / "Bike hook.kcad").exists()
    assert (lib / "Fasteners & brackets" / "Garage bike hook.kcad").exists()
    user_library.remove(again["path"])            # deleted: stays gone
    assert user_library.autosave(obj) is None
    generic = _hook_object()
    generic.name = "Object 3"
    assert user_library.autosave(generic) is None
    wrapped = CadNode("component", "Sofa")
    inner = library.build_part("home_sofa", library.default_dims(
        "home_sofa"))
    wrapped.add(inner)
    assert user_library.autosave(wrapped) is None


def test_the_autosaver_saves_new_objects_but_not_the_opened_ones(lib):
    from PyQt5.QtWidgets import QApplication
    from khervecad.model import DocumentModel
    from khervecad import user_library_dialog as D
    QApplication.instance() or QApplication([])

    class Win:
        def __init__(self):
            self.model = DocumentModel()

        def statusBar(self):
            raise RuntimeError("no status bar in the test")
    win = Win()
    old = _hook_object()
    old.name = "Old shelf"
    win.model.root.add(old)
    win._path, win._dirty = "/tmp/opened.kcad", False   # opened from a file
    saver = D.AutoSaver.__new__(D.AutoSaver)
    D.QObject.__init__(saver)
    saver.window, saver.model = win, win.model
    saver._timer = D.QTimer()
    saver._rebaseline()
    new = _hook_object()
    new.name = "New coat hook, 3 pegs"
    win.model.root.add(new)
    saved = saver.flush()
    assert [s["title"] for s in saved] == ["New coat hook, 3 pegs"]
    assert saver.flush() == []                     # unchanged since


def test_saving_a_document_keeps_the_whole_design(lib, tmp_path_factory):
    from PyQt5.QtWidgets import QApplication
    from khervecad.model import DocumentModel
    QApplication.instance() or QApplication([])
    model = DocumentModel()
    bench = library.build_part("park_bench", library.default_dims(
        "park_bench"))
    model.root.add(bench)                         # a Library part ...
    model.root.add(CadNode("cube", "Wall", dict(   # ... and loose geometry
        x=0.0, y=0.0, z=0.0, width=5000.0, depth=200.0, height=3000.0,
        center=False)))
    doc = tmp_path_factory.mktemp("docs") / "School.kcad"
    first = user_library.save_design(model, doc)
    assert first["section"] == "Buildings"         # "school" -> Buildings
    assert first["title"] == "School"
    node = library.build_part(first["part_id"], {}) if first["part_id"] \
        in user_library.refresh(library.PARTS) else None
    assert node is not None and len(node.children) == 2
    # the user files it elsewhere and describes it: a later save keeps that
    edited = user_library.update_info(first["path"], "Village school",
                                      "Two classrooms and a playground.")
    user_library.move(edited, "Education")
    again = user_library.save_design(model, doc)
    assert again["title"] == "Village school"
    assert again["section"] == "Education"
    assert len([p for p in user_library.files()
                if user_library.read_info(p).get("uid") == first["uid"]]) == 1
    user_library.remove(again["path"])
    assert user_library.save_design(model, doc) is None


def test_the_title_decides_the_area_before_the_description():
    assert user_library.choose_section(
        "", "School", "Built with the House Builder: tables, benches, "
                      "a house-shaped roof") == "Buildings"



def test_a_new_document_filled_at_once_is_still_saved(lib):
    """An assistant makes a new document and builds in it before the
    autosaver has seen the new tree: nothing there is 'old'."""
    from PyQt5.QtWidgets import QApplication
    from khervecad.model import DocumentModel
    from khervecad import user_library_dialog as D
    QApplication.instance() or QApplication([])

    class Win:
        _path, _dirty = None, True

        def __init__(self):
            self.model = DocumentModel()

        def statusBar(self):
            raise RuntimeError
    win = Win()
    saver = D.AutoSaver.__new__(D.AutoSaver)
    D.QObject.__init__(saver)
    saver.window, saver.model = win, win.model
    saver._timer = D.QTimer()
    saver._rebaseline()
    fresh = CadNode("root", "root")                # new_document ...
    porch = _hook_object()
    porch.name = "Classical porch"
    fresh.add(porch)                               # ... filled at once
    win.model.root = fresh
    saver._changed()
    saved = saver.flush()
    assert [s["title"] for s in saved] == ["Classical porch"]
    assert saved[0]["section"] == "Garden & outdoor"
