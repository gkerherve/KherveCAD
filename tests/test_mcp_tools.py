"""MCP tool execution against a live KherveCAD window.

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

from khervecad import mcp_schema
from khervecad.mcp_server import IMAGE_KEY, valid_png_b64
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
def ex(window):
    return McpToolExecutor(window)


def call(ex, _tool, **params):
    """Run a tool and insist it succeeded.  The tool name is passed
    positionally: several tools take a "name" of their own."""
    result = ex.execute(_tool, params)
    assert "error" not in result, f"{_tool} failed: {result.get('error')}"
    return result


def cube(ex, **params):
    """A cube at the document root, returning its id."""
    return call(ex, "add_node", type="cube", params=params or None)["created"]


# ── the contract ───────────────────────────────────────────────────

def test_every_declared_tool_has_an_implementation(ex):
    for tool in mcp_schema.TOOLS:
        assert hasattr(ex, f"_t_{tool['name']}"), \
            f"{tool['name']} is declared but not implemented"


def test_every_implementation_is_declared(ex):
    implemented = {n[3:] for n in dir(ex) if n.startswith("_t_")}
    assert implemented == set(mcp_schema.BY_NAME)


def test_an_unknown_tool_is_an_error_not_a_crash(ex):
    assert "error" in ex.execute("extrude_my_hopes", {})


def test_list_node_types_covers_the_whole_registry(ex):
    from khervecad.model import NODE_TYPES
    types = {t["type"] for t in call(ex, "list_node_types")["types"]}
    assert types == set(NODE_TYPES)


def test_node_types_can_be_filtered_by_category(ex):
    only = call(ex, "list_node_types", category="3d")["types"]
    assert {t["type"] for t in only} >= {"cube", "sphere", "cylinder"}
    assert all(t["category"] == "3d" for t in only)


# ── inspection ─────────────────────────────────────────────────────

def test_document_info_reports_the_engine_and_the_bounds(ex):
    cube(ex, width=10.0, depth=20.0, height=30.0)
    info = call(ex, "get_document_info")
    assert info["units"] == "millimetres"
    assert info["bounds_mm"]["size"] == pytest.approx([10, 20, 30])
    assert "available" in info["openscad"]


def test_a_broken_expression_is_reported_as_an_error(ex):
    ident = cube(ex)
    call(ex, "set_params", changes=[{"id": ident,
                                     "params": {"width": "not * a * size"}}])
    errors = call(ex, "get_document_info")["errors"]
    assert any(e["id"] == ident for e in errors)


def test_list_tree_nests_and_get_node_details(ex):
    ident = cube(ex, width=12.0)
    listed = call(ex, "list_tree")
    assert listed["nodes"][0]["id"] == ident
    assert listed["nodes"][0]["params"]["width"] == 12.0
    node = call(ex, "get_node", node_id=ident)
    assert node["label"] == "Cube"
    assert {s["name"] for s in node["schema"]} >= {"width", "depth",
                                                   "height", "center"}


def test_get_code_emits_openscad_for_the_document_and_one_object(ex):
    ident = cube(ex, width=7.0)
    whole = call(ex, "get_code")["code"]
    assert "cube(" in whole
    comp = call(ex, "make_object", ids=[ident], name="Widget")["object"]
    part = call(ex, "get_code", node_id=comp)["code"]
    assert "module" in part and "cube(" in part


def test_render_view_returns_a_real_png(ex, window):
    cube(ex)
    window.show()
    shot = call(ex, "render_view", orientation="Front", max_width=200)
    assert valid_png_b64(shot[IMAGE_KEY])
    assert shot["width"] <= 200


# ── building ───────────────────────────────────────────────────────

def test_add_node_lands_in_the_scope_and_accepts_expressions(ex):
    call(ex, "add_node", type="assign",
         params={"variable": "wall", "value": "4"})
    ident = cube(ex, width="wall * 5")
    node = call(ex, "get_node", node_id=ident)
    assert node["params"]["width"] == "wall * 5"
    assert "error" not in node          # the expression resolves


def test_a_misspelt_parameter_is_refused_with_the_real_names(ex):
    result = ex.execute("add_node", {"type": "cube",
                                     "params": {"widht": 10}})
    assert "widht" in result["error"] and "width" in result["error"]


def test_an_unknown_node_type_points_at_list_node_types(ex):
    result = ex.execute("add_node", {"type": "torus"})
    assert "list_node_types" in result["error"]


def test_wrap_nodes_applies_an_operation(ex):
    a, b = cube(ex), cube(ex, x=5.0)
    out = call(ex, "wrap_nodes", ids=[a, b], operation="difference")
    node = call(ex, "get_node", node_id=out["wrapper"])
    assert node["type"] == "difference"
    assert [n["id"] for n in node["nodes"]] == [a, b]
    assert "difference()" in call(ex, "get_code")["code"]


def test_wrap_refuses_nodes_that_are_not_siblings(ex):
    a = cube(ex)
    group = call(ex, "wrap_nodes", ids=[a], operation="union")["wrapper"]
    b = call(ex, "add_node", type="sphere", parent_id=group)["created"]
    outside = cube(ex)
    result = ex.execute("wrap_nodes", {"ids": [b, outside],
                                       "operation": "union"})
    assert "different parents" in result["error"]


def test_wrap_takes_the_operations_own_parameters(ex):
    ident = call(ex, "add_node", type="rect")["created"]
    out = call(ex, "wrap_nodes", ids=[ident],
               operation="linear_extrude", params={"height": 12.0})
    assert call(ex, "get_node",
                node_id=out["wrapper"])["params"]["height"] == 12.0


def test_move_node_refuses_to_make_the_tree_its_own_child(ex):
    ident = cube(ex)
    group = call(ex, "wrap_nodes", ids=[ident],
                 operation="union")["wrapper"]
    result = ex.execute("move_node", {"node_id": group,
                                      "parent_id": ident})
    assert "error" in result


def test_delete_and_ungroup(ex, window):
    a, b = cube(ex), cube(ex)
    group = call(ex, "wrap_nodes", ids=[a, b],
                 operation="union")["wrapper"]
    call(ex, "ungroup_node", node_id=group)
    assert len(window.model.root.children) == 2
    call(ex, "delete_nodes", ids=[a, b])
    assert window.model.root.children == []


def test_set_color_reuses_one_wrapper_rather_than_stacking(ex):
    ident = cube(ex)
    first = call(ex, "set_color", ids=[ident], color="#ff0000")
    second = call(ex, "set_color", ids=[ident], color="#00ff00")
    assert first["colored"] == second["colored"]
    assert "color(" in call(ex, "get_code")["code"]


def test_round_edges_wraps_in_minkowski(ex):
    ident = cube(ex)
    out = call(ex, "round_edges", ids=[ident], radius=1.5)
    node = call(ex, "get_node", node_id=out["wrapper"])
    assert node["type"] == "minkowski"
    assert any(c["type"] == "sphere" for c in node["nodes"])


# ── code in, code out ──────────────────────────────────────────────

def test_apply_code_becomes_real_editable_nodes(ex):
    call(ex, "apply_code", code="""
        wall = 3;
        difference() {
            cube([30, 20, 10]);
            translate([wall, wall, -1]) cube([30 - 2 * wall, 14, 12]);
        }
    """)
    tree = call(ex, "list_tree", depth=-1)
    kinds = {n["type"] for n in tree["nodes"]}
    assert "difference" in kinds
    # not pasted as text: a raw block would be one scad_raw leaf
    assert "scad_raw" not in kinds


def test_apply_code_round_trips_through_get_code(ex):
    call(ex, "apply_code", code="cube([10, 20, 30]);")
    once = call(ex, "get_code")["code"]
    call(ex, "apply_code", code=once, mode="replace")
    assert call(ex, "get_code")["code"] == once


def test_apply_code_replace_swaps_the_document(ex):
    cube(ex)
    call(ex, "apply_code", code="sphere(r = 4);", mode="replace")
    types = {n["type"] for n in call(ex, "list_tree")["nodes"]}
    assert types == {"sphere"}


def test_code_that_produces_nothing_is_an_error_not_a_silent_success(ex):
    """The parser skips a statement it cannot read and carries on —
    right for importing someone else's file, wrong for a program a
    client just wrote, which would otherwise report success having
    applied nothing."""
    cube(ex)
    before = call(ex, "get_code")["code"]
    result = ex.execute("apply_code", {"code": "cube([1,2,3)"})
    assert "error" in result and "no objects" in result["error"]
    assert call(ex, "get_code")["code"] == before


def test_code_the_parser_only_partly_understands_still_warns(ex):
    out = call(ex, "apply_code",
               code="cube([4,4,4]);\nnot_a_real_statement(")
    assert out["added"] == 1
    assert out["warnings"]


# ── parts and assemblies ───────────────────────────────────────────

def test_make_object_then_instance_it(ex, window):
    ident = cube(ex)
    comp = call(ex, "make_object", ids=[ident], name="Bracket")["object"]
    inst = call(ex, "add_instance", node_id=comp,
                params={"x": 40.0})["instance"]
    assert len(window.model.instances_of(window.model.find(comp))) == 1
    code = call(ex, "get_code")["code"]
    assert "module" in code and "Bracket" in code.replace("_", "")
    assert call(ex, "get_node", node_id=inst)["params"]["x"] == 40.0


def test_add_instance_refuses_something_that_is_not_an_object(ex):
    result = ex.execute("add_instance", {"node_id": cube(ex)})
    assert "not an Object" in result["error"]


def test_a_master_and_its_linked_copies(ex, window):
    ident = cube(ex)
    out = call(ex, "make_master", node_id=ident)
    assert window.model.masters_group() is not None
    call(ex, "add_linked_copy", node_id=out["master"],
         params={"x": 30.0})
    refs = [n for n in window.model.root.children
            if n.type == "reference"]
    assert len(refs) == 2               # the one left behind + the copy


def test_list_anchors_offers_bounding_box_names(ex):
    ident = cube(ex)
    comp = call(ex, "make_object", ids=[ident])["object"]
    out = call(ex, "list_anchors", node_id=comp)
    names = {a["name"] for a in out["anchors"]}
    assert {"Origin", "Top", "Bottom", "Left", "Right"} <= names


def test_attach_moves_one_part_onto_another(ex, window):
    call(ex, "make_object", ids=[cube(ex, height=10.0)], name="Base")
    lid = call(ex, "make_object", ids=[cube(ex, height=4.0)],
               name="Lid")["object"]
    out = call(ex, "attach_parts", node_id=lid, parent="Base",
               anchor="Bottom", parent_anchor="Top")
    assert out["to"] == "Base"
    assert window.model.find(lid).params["z"] != 0
    call(ex, "attach_parts", node_id=lid, detach=True)
    assert "mate" not in window.model.find(lid).params


def test_attach_names_the_anchors_it_would_accept(ex):
    call(ex, "make_object", ids=[cube(ex)], name="Base")
    lid = call(ex, "make_object", ids=[cube(ex)], name="Lid")["object"]
    result = ex.execute("attach_parts", {"node_id": lid,
                                         "parent": "Base",
                                         "anchor": "Underneath",
                                         "parent_anchor": "Top"})
    assert "list_anchors" in result["error"]


def test_insert_part_arrives_as_one_object(ex, window):
    out = call(ex, "insert_part", part_id="cf_flange", size="CF40")
    assert "CF40" in out["size"]
    comp = window.model.find(out["inserted"])
    assert comp.type == "component" and comp.children


def test_an_unknown_part_size_lists_the_real_ones(ex):
    result = ex.execute("insert_part", {"part_id": "cf_flange",
                                        "size": "CF999"})
    assert "CF16" in result["error"]


# ── document ───────────────────────────────────────────────────────

def test_new_document_refuses_to_bin_unsaved_work(ex):
    cube(ex)
    assert "unsaved" in ex.execute("new_document", {})["error"]
    info = call(ex, "new_document", discard_unsaved_changes=True)
    assert info["node_count"] == 0


def test_save_and_reopen_round_trips_the_model(ex, tmp_path):
    call(ex, "apply_code", code="cube([10, 20, 30]); sphere(r = 5);")
    path = tmp_path / "part.kcad"
    call(ex, "save_document", path=str(path))
    assert call(ex, "get_document_info")["unsaved_changes"] is False
    info = call(ex, "open_document", path=str(path),
                discard_unsaved_changes=True)
    assert info["node_count"] == 2
    assert info["path"] == str(path)


def test_saving_anything_but_kcad_points_at_export(ex, tmp_path):
    result = ex.execute("save_document",
                        {"path": str(tmp_path / "part.stl")})
    assert "export_document" in result["error"]


def test_export_scad_writes_the_program(ex, tmp_path):
    cube(ex)
    out = tmp_path / "part.scad"
    call(ex, "export_document", path=str(out))
    assert "cube(" in out.read_text()


def test_an_approximate_stl_export_says_so_loudly(ex, tmp_path, window):
    a, b = cube(ex), cube(ex, x=2.0)
    call(ex, "wrap_nodes", ids=[a, b], operation="difference")
    out = tmp_path / "part.stl"
    result = call(ex, "export_document", path=str(out))
    assert out.exists()
    if not window.engine.available:
        assert result["exact"] is False
        assert "APPROXIMATED" in result["warning"]


def test_opening_a_scad_program_imports_it_as_objects(ex, tmp_path):
    path = tmp_path / "prog.scad"
    path.write_text("cube([5, 5, 5]);\ntranslate([9,0,0]) sphere(r=3);\n")
    info = call(ex, "open_document", path=str(path),
                discard_unsaved_changes=True)
    assert info["node_count"] > 0
    assert info["objects"], "an import lands as one part in the assembly"


def test_open_refuses_a_file_it_does_not_handle(ex, tmp_path):
    junk = tmp_path / "notes.txt"
    junk.write_text("hello")
    result = ex.execute("open_document", {"path": str(junk),
                                          "discard_unsaved_changes": True})
    assert ".kcad" in result["error"]


def test_load_example_replaces_the_document(ex):
    name = call(ex, "list_examples")["examples"][0]["name"]
    out = call(ex, "load_example", name=name,
               discard_unsaved_changes=True)
    assert out["nodes"] > 0


def test_set_render_options_changes_the_segment_count(ex, window):
    out = call(ex, "set_render_options", segments=120)
    assert out["global_segments"] == 120
    assert window.model.global_fn == 120


# ── render_view: waiting and camera control ────────────────────────

class _StubEngine:
    """An OpenSCAD engine that is 'busy' for a while. Every method the
    window might call during the event pump is a harmless no-op — a
    missing one would raise inside a Qt slot and abort the run."""
    available = True

    def __init__(self, busy_polls):
        self.busy_polls = busy_polls
        self.polls = 0

    def is_idle(self):
        self.polls += 1
        return self.polls > self.busy_polls

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def test_render_view_waits_for_the_exact_render(ex, window, monkeypatch):
    cube(ex)
    window.show()
    stub = _StubEngine(busy_polls=5)
    monkeypatch.setattr(window, "engine", stub)
    shot = call(ex, "render_view", max_width=160)
    assert shot["render_complete"] is True
    assert stub.polls > 5                      # it really waited
    assert "note" not in shot


def test_render_view_gives_up_at_the_timeout(ex, window, monkeypatch):
    import time
    cube(ex)
    window.show()
    monkeypatch.setattr(window, "engine", _StubEngine(busy_polls=10**9))
    started = time.monotonic()
    shot = call(ex, "render_view", timeout=0.3, max_width=160)
    assert time.monotonic() - started < 5
    assert shot["render_complete"] is False
    assert "built-in preview" in shot["note"]
    assert valid_png_b64(shot[IMAGE_KEY])      # still a picture


def test_render_view_can_skip_the_wait(ex, window, monkeypatch):
    cube(ex)
    window.show()
    stub = _StubEngine(busy_polls=10**9)
    monkeypatch.setattr(window, "engine", stub)
    shot = call(ex, "render_view", wait_for_exact=False, max_width=160)
    assert shot["render_complete"] is False and stub.polls == 1


def test_camera_parameters_leave_the_users_view_alone(ex, window):
    cube(ex)
    window.show()
    before = window.view3d.camera_state()
    shot = call(ex, "render_view", azimuth=0, elevation=90,
                projection="Orthographic", max_width=200)
    assert window.view3d.camera_state() == before
    assert shot["camera"]["projection"] == "Orthographic"
    assert shot["camera"]["elevation"] == 90
    assert shot["width"] == 200 and valid_png_b64(shot[IMAGE_KEY])


def test_orientation_with_camera_parameters_aims_offscreen(ex, window):
    cube(ex)
    window.show()
    before = window.view3d.camera_state()
    shot = call(ex, "render_view", orientation="Right", zoom=2,
                max_width=160)
    assert window.view3d.camera_state() == before
    assert shot["camera"]["azimuth"] == 0.0     # the Right preset


def test_target_node_frames_one_part(ex, window):
    cube(ex, width=10.0, depth=10.0, height=10.0)
    far = cube(ex, x=300.0, width=10.0, depth=10.0, height=10.0)
    window.show()
    shot = call(ex, "render_view", target_node=far, max_width=200)
    assert shot["camera"]["target"][0] == pytest.approx(305.0, abs=3.0)


def test_orientations_come_back_as_one_contact_sheet(ex, window):
    cube(ex)
    window.show()
    names = ["Front", "Top", "Right", "Isometric"]
    shot = call(ex, "render_view", orientations=names, max_width=400)
    assert [t["orientation"] for t in shot["tiles"]] == names
    assert (shot["width"], shot["height"]) == (400, 300)   # 2 x 2 tiles
    assert "error" in ex.execute("render_view",
                                 {"orientations": ["Sideways"]})


def test_region_crops_a_sharp_detail(ex, window):
    cube(ex)
    window.show()
    shot = call(ex, "render_view", region=[0.25, 0.25, 0.75, 0.75],
                fit=True, max_width=300)
    assert shot["region"] == [0.25, 0.25, 0.75, 0.75]
    assert shot["width"] == 300                # rendered big, not upscaled
    for bad in ([0.5, 0.5, 0.4, 0.9], [0, 0, 2, 1], [1, 2, 3]):
        assert "error" in ex.execute("render_view", {"region": bad})


def test_bad_camera_values_are_refused(ex, window):
    cube(ex)
    window.show()
    for bad in ({"projection": "Fisheye"}, {"zoom": 0},
                {"target": [1, 2]}, {"distance": -5},
                {"target_node": 999999}):
        assert "error" in ex.execute("render_view", bad), bad


def test_set_render_options_switches_the_projection(ex, window):
    from PyQt5.QtCore import QSettings
    settings = QSettings("Kherve", "KherveCAD")
    saved = settings.value("render_projection", "Perspective")
    try:
        out = call(ex, "set_render_options", projection="Orthographic")
        assert out["projection"] == "Orthographic"
        assert window.view3d.projection == "Orthographic"
        ticked = [a.text() for a in window._proj_group.actions()
                  if a.isChecked()]
        assert ticked == ["Orthographic"]
        assert "error" in ex.execute("set_render_options",
                                     {"projection": "Fisheye"})
    finally:
        window.set_projection("Perspective")
        settings.setValue("render_projection", saved)


# ── measuring: bounds, measure, section, check_code ────────────────

def test_get_node_bounds_is_in_world_space(ex):
    ident = cube(ex, x=5.0, width=10.0, depth=20.0, height=30.0)
    out = call(ex, "get_node_bounds", node_ids=[ident])["nodes"][0]
    assert out["min"] == pytest.approx([5, 0, 0])
    assert out["max"] == pytest.approx([15, 20, 30])
    assert out["center"] == pytest.approx([10, 10, 15])
    assert out["approximate"] is False


def test_get_node_bounds_combines_several_and_flags_booleans(ex):
    a = cube(ex, width=10.0, depth=10.0, height=10.0)
    b = cube(ex, x=50.0, width=10.0, depth=10.0, height=10.0)
    out = call(ex, "get_node_bounds", node_ids=[a, b])
    assert out["combined"]["size"] == pytest.approx([60, 10, 10])
    call(ex, "apply_code", code="difference() { cube(10); cube(5); }")
    diff = [n["id"] for n in call(ex, "list_tree")["nodes"]
            if n["type"] == "difference"]
    flagged = call(ex, "get_node_bounds", node_ids=diff)
    assert flagged["nodes"][0]["approximate"] is True
    assert "note" in flagged
    assert "error" in ex.execute("get_node_bounds", {"node_ids": [987654]})


def test_measure_between_points_and_nodes(ex):
    out = call(ex, "measure", a={"point": [0, 0, 0]},
               b={"point": [3, 4, 0]})
    assert out["distance"] == pytest.approx(5.0)
    left = cube(ex, width=10.0, depth=10.0, height=10.0)
    right = cube(ex, x=20.0, width=10.0, depth=10.0, height=10.0)
    apart = call(ex, "measure", a={"node": left}, b={"node": right})
    assert apart["distance"] == pytest.approx(20.0)     # centre to centre
    assert apart["gap"][0] == pytest.approx(10.0)       # 10 mm of air
    assert apart["overlap"] is False
    assert apart["clearance"] == pytest.approx(10.0)
    touching = call(ex, "measure", a={"node": left, "at": "max"},
                    b={"node": right, "at": "min"})
    assert touching["delta"] == pytest.approx([10.0, -10.0, -10.0])


def test_measure_reports_an_overlap(ex):
    a = cube(ex, width=10.0, depth=10.0, height=10.0)
    b = cube(ex, x=6.0, width=10.0, depth=10.0, height=10.0)
    out = call(ex, "measure", a={"node": a}, b={"node": b})
    assert out["overlap"] is True and out["gap"][0] == pytest.approx(-4.0)
    assert out["clearance"] == 0.0


def test_measure_to_a_named_anchor_on_an_object(ex):
    ident = cube(ex, width=10.0, depth=10.0, height=10.0)
    obj = call(ex, "make_object", ids=[ident], name="Block")["object"]
    names = [a["name"] for a in call(ex, "list_anchors",
                                     node_id=obj)["anchors"]]
    assert names
    out = call(ex, "measure", a={"node": obj, "at": names[0]},
               b={"point": [0, 0, 0]})
    assert out["a"]["at"].endswith(names[0])
    bad = ex.execute("measure", {"a": {"node": obj, "at": "Nowhere"},
                                 "b": {"point": [0, 0, 0]}})
    assert "Nowhere" in bad["error"]
    assert "error" in ex.execute("measure", {"a": {"point": [1, 2]},
                                             "b": {"point": [0, 0, 0]}})


def test_section_cuts_the_view_into_outlines(ex, window):
    cube(ex, width=20.0, depth=10.0, height=30.0)
    window.show()
    out = call(ex, "section", axis="z", offset=15.0, max_width=300)
    assert valid_png_b64(out[IMAGE_KEY])
    assert out["plane"] == {"u": "x", "v": "y"}
    assert out["area_mm2"] == pytest.approx(200.0)
    assert len(out["outlines"]) == 1 and out["outlines"][0]["closed"]
    assert out["bounds"]["x"] == pytest.approx([0.0, 20.0])


def test_section_of_one_node_and_a_plane_that_misses(ex, window):
    ident = cube(ex, width=10.0, depth=10.0, height=10.0)
    window.show()
    out = call(ex, "section", axis="x", node_id=ident,
               include_points=True)
    assert out["offset"] == pytest.approx(5.0)          # the middle
    assert len(out["outlines"][0]["points"]) >= 4
    missed = call(ex, "section", axis="z", offset=500.0)
    assert missed["outlines"] == [] and "misses" in missed["note"]
    assert "error" in ex.execute("section", {"axis": "w"})


def test_check_code_is_a_dry_run(ex):
    before = call(ex, "get_document_info")["node_count"]
    out = call(ex, "check_code",
               code="translate([1, 2, 3]) cube(5); sphere(r = 2);")
    assert out["would_apply"] is True and out["top_level"] == 2
    assert out["types"].get("cube") == 1
    assert out["types"].get("sphere") == 1
    assert call(ex, "get_document_info")["node_count"] == before
    skipped = call(ex, "check_code", code="children(); cube(1);")
    assert skipped["warnings"]
    empty = call(ex, "check_code", code="// nothing here")
    assert empty["would_apply"] is False
