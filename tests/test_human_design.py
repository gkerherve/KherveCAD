"""The Human Builder's model (human_design.py) and the outfit node
(outfit.py): every preset builds, clothes follow body parts in any
pose, custom garment rows, specs, the builder window and the MCP tools.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from khervecad import human_design as D
from khervecad import library, mcp_schema, mesh, outfit, scadparse
from khervecad.model import CadNode, validate


def _colours(node):
    return [c[0] for _t, c, *_ in mesh.tessellate_colored(node) if c]


def test_every_bone_belongs_to_a_part():
    from khervecad import human
    for bone in human.skeleton()["weights"]:
        assert outfit.part_of_bone(bone).split(".")[0] in outfit.PARTS


def test_groups_and_sides_expand():
    assert set(outfit.expand("arm")) >= {"forearm.L", "shoulder.R"}
    assert outfit.expand("hand.R") == ["hand.R"]
    assert not outfit.known("tail")


@pytest.mark.parametrize("name", list(D.PRESETS))
def test_every_preset_builds_clean(name):
    node = D.build({"preset": name})
    assert not validate(node), name
    assert any(n.type == "outfit" for n in node.walk())


def test_a_sleeve_stays_on_the_arm_whatever_the_pose():
    red = "#c0392b"
    for gesture in ("Arms down", "Waving", "Cheering"):
        node = D.build({"top": "Long-sleeve shirt", "top_colour": red,
                        "gesture": gesture, "hair": "Bald"})
        dress = next(n for n in node.walk() if n.type == "outfit")
        body = next(n for n in dress.walk() if n.type == "human")
        items = mesh.tessellate_colored(dress)
        parts = outfit.face_parts([t for t, *_ in items],
                                  outfit._human_args(dress, {}))
        forearm = [c[0] for (_t, c, *_), p in zip(items, parts)
                   if p.startswith("forearm")]
        assert forearm and all(c == red for c in forearm), gesture
        assert body.params["pose"]


def test_custom_garment_rows_win_and_round_trip():
    node = D.build({"garments": [["hand.R", "#123456", "Rubber"]],
                    "hair": "Bald"})
    assert "#123456" in _colours(node)
    dress = next(n for n in node.walk() if n.type == "outfit")
    root = CadNode("union", "R")
    root.add(dress)
    back, warnings = scadparse.parse_scad(root.to_scad())
    again = next(n for n in back.walk() if n.type == "outfit")
    assert again.params["garments"] == dress.params["garments"]


def test_bad_choices_are_refused_with_the_list():
    with pytest.raises(D.SpecError, match="Waving"):
        D.normalise({"gesture": "Juggling"})
    with pytest.raises(D.SpecError):
        D.normalise({"garments": [["tail", "#000000"]]})
    with pytest.raises(D.SpecError, match="unknown keys"):
        D.normalise({"shirt": "T-shirt"})


def test_skirts_and_coats_fit_the_body():
    m = D.measure(D.body_args(D.normalise({"gender": "Female"})))
    assert m["knee_z"] < m["waist_z"] < m["shoulder_z"]
    assert D.skirt_code("Knee", "#000000", m)
    assert "rotate_extrude(angle = 300" in D.tails_code("Knee", "#fff", m)


def test_presets_are_library_parts_and_mcp_tools_exist():
    for name in D.PRESETS:
        assert any(spec.get("label") == name or name.startswith("Casual")
                   for spec in library.PARTS.values())
    names = {t["name"] for t in mcp_schema.TOOLS}
    assert {"list_character_options", "build_character"} <= names
    opts = D.options()
    assert "Waving" in opts["gesture"] and "hand" in opts["body_parts"]


def test_insert_keeps_the_spec_for_update():
    from khervecad.model import DocumentModel
    model = DocumentModel()
    part = D.insert(model, {"preset": "Chef"})
    assert part.params["character"]["name"] == "Chef"
    again = D.insert(model, {"preset": "Chef", "top_colour": "Red"},
                     replace=part)
    assert again.params["character"]["top_colour"] == "Red"
    assert sum(1 for n in model.root.children
               if (n.params or {}).get("character")) == 1


def test_builder_window_builds_its_views():
    import time
    from PyQt5.QtWidgets import QApplication
    from khervecad import human_dialog
    from khervecad.mainwindow import MainWindow
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    assert app is not None
    panel = human_dialog.open_builder(win)
    panel.set_spec(D.PRESETS["Doctor"])
    deadline = time.time() + 90
    while time.time() < deadline:
        QApplication.processEvents()
        pix = panel._views[0].pixmap()
        if pix is not None and not pix.isNull():
            break
        time.sleep(0.05)
    assert pix is not None and not pix.isNull()
    assert panel.spec()["coat"] == "Lab coat"
    panel._apply(None)
    assert human_dialog.selected_character(win) is not None
    panel.close()
    panel.shutdown()
