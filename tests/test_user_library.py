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
    assert (lib / "Hook.kcad").exists()
    assert user_library.parts()[a["part_id"]]["category"] == \
        "My library: General"
