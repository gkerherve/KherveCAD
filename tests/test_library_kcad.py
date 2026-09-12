"""The KCAD-file library: every shipped .kcad loads as one valid part,
and the sync tool lists and adds correctly.

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

from khervecad import document, library, library_kcad, mesh
from khervecad.model import CadNode, DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


KNOWN_IMPERFECT = {"Brackets and Fixings", "Cartoon Characters"}


@pytest.mark.parametrize("path", library_kcad.files(),
                         ids=lambda p: p.stem)
def test_every_shipped_kcad_is_a_valid_part(app, path):
    pid = library_kcad.part_id(path.stem)
    assert pid in library.PARTS
    assert library.PARTS[pid]["category"] == "KCAD files"
    node = library.build_part(pid, {})
    root = CadNode("root")
    root.add(node)
    errors = validate(root)
    # two documents ship with expression errors of their own (a list
    # index written as "7]"); they still load and preview. Anything
    # else with errors is a file that should not have been added
    if path.stem not in KNOWN_IMPERFECT:
        assert errors == {}, (path.name, list(errors.values()))
    assert mesh.tessellate(node), f"{path.name} previews empty"


def test_part_ids_normalise_names():
    assert library_kcad.part_id("Door Stopper") == "kcad_door_stopper"
    assert library_kcad.part_id("door_stopper.v2") == "kcad_door_stopper_v2"
    assert library_kcad.label("pen_holder") == "pen holder"


def test_inserted_kcad_part_becomes_one_object(app, tmp_path):
    m = DocumentModel()
    m.add_node("cube")
    m.add_node("sphere", dict(x=30))
    document.save_kcad(m, str(tmp_path / "Two things.kcad"))
    part = library_kcad.load_part(tmp_path / "Two things.kcad")
    assert part.name == "Two things" and len(part.children) == 2
    target = DocumentModel()
    target.root.add(part)
    comp = target.enclose_as_part(part)
    assert comp.type == "component" and validate(target.root) == {}


def test_sync_tool_lists_only_new_files_and_adds(app, tmp_path,
                                                   monkeypatch, capsys):
    from khervecad.tools import kcad_sync
    folder = tmp_path / "kcad"
    folder.mkdir()
    m = DocumentModel()
    m.add_node("cube")
    document.save_kcad(m, str(folder / "Fresh part.kcad"))
    (folder / "broken.kcad").write_text("{not json", encoding="utf-8")
    shipped = library_kcad.files()
    if shipped:                                   # a copy of one we have
        (folder / shipped[0].name).write_bytes(shipped[0].read_bytes())
    kcad_sync.cmd_list([folder])
    out = capsys.readouterr().out
    assert "NEW " in out and "Fresh part.kcad" in out
    assert "SKIP" in out and "broken.kcad" in out
    if shipped:
        assert shipped[0].name not in out.split("SKIP")[0]
    dest = tmp_path / "parts"
    monkeypatch.setattr(library_kcad, "PARTS_DIR", dest)
    kcad_sync.cmd_add([str(folder / "Fresh part.kcad"),
                       str(folder / "broken.kcad")])
    out = capsys.readouterr().out
    assert (dest / "Fresh part.kcad").exists()
    assert not (dest / "broken.kcad").exists()
    assert "1 added" in out
