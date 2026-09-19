"""Vitamins (library_vitamins.py), Lego Technic and generative panels
(library_generative.py)."""

import math

import pytest

from khervecad import (analysis, library, library_generative,
                       library_vitamins, mesh)
from khervecad.model import DocumentModel, validate
from khervecad.scadparse import parse_scad

PART_IDS = sorted(list(library_vitamins.PARTS)
                  + list(library_generative.PARTS))


@pytest.mark.parametrize("part_id", PART_IDS)
def test_part_builds_valid_and_round_trips(part_id):
    model = DocumentModel()
    model.root.add(library.build_part(part_id, {}))
    assert validate(model.root) == {}
    assert mesh.tessellate(model.root)
    code = model.to_scad()
    again = DocumentModel()
    again.root, warnings = parse_scad(code)
    assert not warnings and again.to_scad() == code


def test_nema17_face_pattern():
    node = library.build_part("vit_nema", {"_size": "NEMA 17 (40 mm)"})
    holes = [n for n in node.walk() if n.type == "hole"]
    xs = sorted({round(n.parent.params["x"], 2) for n in holes})
    assert xs == [-15.5, 15.5]                       # 31 mm pattern


def test_technic_beam_pitch():
    node = library.build_part("technic_beam", {"holes": 5})
    holes = [n for n in node.walk() if n.name.startswith("Hole")]
    assert [n.params["x"] for n in holes] == [0, 8, 16, 24, 32]


def test_delaunay_and_voronoi_cover_the_panel():
    cells = library_generative.voronoi_cells(100, 70, 20, 7, 0.0)
    area = sum(abs(mesh.polygon_area(c)) for c in cells)
    assert area == pytest.approx(100 * 70, rel=1e-6)   # no gaps, no overlap
    walled = library_generative.voronoi_cells(100, 70, 20, 7, 2.0)
    assert sum(abs(mesh.polygon_area(c)) for c in walled) < area


def test_maze_is_a_spanning_tree():
    opened = library_generative.maze_walls(8, 6, 1)
    assert len(opened) == 8 * 6 - 1                   # a perfect maze


def test_maze_runs_join_segments_and_rebuild_every_maze():
    seeds = [3, 4, 5]
    runs = library_generative.maze_runs(10, 10, seeds)
    for frame, seed in enumerate(seeds):
        want = library_generative._maze_segments(
            10, 10, library_generative.maze_walls(10, 10, seed))
        got = {(a, line, i) for a, line, first, last, on in runs if on[frame]
               for i in range(first, last + 1)}
        assert got == want                     # each maze exactly
    # a still maze: straight runs are one wall, not one per cell
    assert len(library_generative.maze_runs(10, 10, [3])) < 10 * 9 - 10


def test_maze_is_new_at_every_insert_unless_seeded():
    model = DocumentModel()
    parts = [library_generative.insert_maze(model, {})[0] for _ in range(3)]
    assert len({p.name for p in parts}) == 3
    assert len({p.children[0].children[0].to_scad() for p in parts}) == 3
    seed = int(parts[0].name.split("seed ")[1].rstrip(")"))
    again = library_generative.build_maze({"seed": seed})
    assert again.children[0].to_scad() == parts[0].children[0].children[0] \
        .to_scad()                                     # the name rebuilds it


def test_rounded_maze_uses_rounded_boxes_sunk_into_the_base():
    node = library_generative.build_maze({"rounding": 0.6})
    boxes = [n for n in node.walk() if n.type == "rounded_box"]
    assert boxes and not [n for n in node.walk() if n.type == "cube"]
    base = next(b for b in boxes if b.name == "Base")
    walls = [b for b in boxes if b.name != "Base"]
    assert all(w.params["z"] == pytest.approx(2.0 - 1.2) for w in walls)
    assert base.params["radius"] == pytest.approx(0.6)


def _tops(node, t):
    var = next(n for n in node.walk() if n.type == "assign"
               and n.params["variable"] == "maze_t")
    var.params["value"] = str(t)
    model = DocumentModel()
    model.root.add(node)
    return sorted(round(max(v[2] for v in tri), 3)
                  for tri in mesh.tessellate(model.root))


def test_changing_maze_morphs_on_its_slider_and_loops():
    node = library_generative.build_maze({"mazes": 3, "cols": 6, "rows": 6,
                                          "seed": 3})
    assert node.children[0].name == "Changing maze (seed 3)"
    first, half, second = _tops(node, 0), _tops(node, 0.5), _tops(node, 1)
    assert first != second and half not in (first, second)
    assert _tops(node, 3) == first             # the third step loops back
    code = node.to_scad()
    assert "maze_t = 3;  // [0:0.05:3]" in code


def test_changing_maze_inserts_its_slider_for_play_motion():
    from khervecad import motion_play
    model = DocumentModel()
    one = library_generative.insert_maze(model, {"mazes": 2})
    two = library_generative.insert_maze(model, {"mazes": 4})
    assert [c.type for c in one + two] == ["component", "component"]
    names = [a.params["variable"] for a in model.global_assigns()]
    assert "maze_t" in names and "maze2_t" in names
    assert "[maze2_k]" in model.to_scad()      # the second reads its own
    assert motion_play.pick(model, "maze2_t").params["variable"] == "maze2_t"
    assert not validate(model.root)


def test_hilbert_visits_every_cell_once_in_unit_steps():
    pts = library_generative.hilbert(3)
    assert len(set(pts)) == 64
    assert all(math.dist(a, b) == 1 for a, b in zip(pts, pts[1:]))
