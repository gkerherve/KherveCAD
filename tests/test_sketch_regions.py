

def test_lines_a_hair_apart_still_close_an_area():
    # trimmed / mirrored pieces come back a few hundredths apart: the
    # area they close is still one region
    from khervecad import sketch_regions as sr
    gap = 0.012
    segs = [((0, 0), (10, 0)), ((10, 0), (10, 10)),
            ((10 + gap, 10 - gap), (0, 10)), ((0, 10), (0, 0))]
    loops = sr.arrangement(segs, [0, 1, 2, 3])
    assert len(loops) == 1


def test_a_sketch_pattern_makes_regions_too():
    # the six bolt holes of a Circular Sketch Pattern are regions of their
    # own, so leaving them unpicked leaves six holes
    from khervecad import sketch_regions as sr
    from khervecad.model import CadNode
    sketch = CadNode("union", "Sketch")
    sketch.add(CadNode("circle", "Plate", {"x": 0, "y": 0, "radius": 40}))
    loop = CadNode("for_loop", "Pattern", {"var": "i", "start": 0,
                                           "end": 5, "step": 1})
    turn = CadNode("rotate", "Turn", {"x": 0, "y": 0, "z": "i * 60"})
    turn.add(CadNode("circle", "Hole", {"x": 0, "y": 30, "radius": 5}))
    loop.add(turn)
    sketch.add(loop)
    shapes = sr.shapes_of(sketch)
    assert loop in shapes
    areas = sorted(round(f[0].area()) for f in sr.faces(shapes))
    assert len(areas) == 7 and areas[:6] == [areas[0]] * 6


def test_the_region_overlay_follows_the_picks():
    from khervecad import region_show
    assert region_show.label(set(), 5).startswith("Click")
    assert region_show.label({0, 2}, 5) == "Picked: 1, 3  (of 5)"
