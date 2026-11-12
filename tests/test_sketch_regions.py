

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


def test_each_picked_region_is_the_one_extruded():
    # the user: "the region I select is not the one that extruded" — a
    # sketch pattern counted when picking but not once inside the Regions
    from khervecad import sketch_regions as sr, regions2d
    from khervecad.model import CadNode, DocumentModel

    def sketch():
        m = DocumentModel()
        c = CadNode("union", "Sketch")
        m.root.add(c)
        c.add(CadNode("circle", "Plate", {"x": 0, "y": 0, "radius": 40}))
        c.add(CadNode("circle", "Bore", {"x": 0, "y": 0, "radius": 15}))
        loop = CadNode("for_loop", "Pattern", {"var": "i", "start": 0,
                                               "end": 5, "step": 1})
        turn = CadNode("rotate", "Turn", {"x": 0, "y": 0, "z": "i * 60"})
        turn.add(CadNode("circle", "Hole", {"x": 0, "y": 28, "radius": 4}))
        loop.add(turn)
        c.add(loop)
        return m, c

    m, c = sketch()
    count = len(sr.faces(sr.shapes_of(c)))
    assert count == 8
    for k in range(count):
        m, c = sketch()
        shapes = sr.shapes_of(c)
        fl = sr.faces(shapes)
        want = fl[k][0].area()
        ext = sr.extrude(m, c, fl, {k}, hide=shapes)
        reg = next(n for n in ext.walk() if n.type == "regions")
        assert abs(regions2d._cs(reg)[0].area() - want) < 0.5, k


def test_a_second_extrude_reuses_the_same_sketch():
    # the user: once one region was extruded the others disappeared, so
    # no other thickness could be made from the same sketch
    from khervecad import sketch_regions as sr, regions2d
    from khervecad.model import CadNode, DocumentModel
    m = DocumentModel()
    c = CadNode("union", "Sketch")
    m.root.add(c)
    c.add(CadNode("circle", "Plate", {"x": 0, "y": 0, "radius": 40}))
    c.add(CadNode("circle", "Boss", {"x": 0, "y": 0, "radius": 20}))
    shapes = sr.shapes_of(c)
    fl = sr.faces(shapes)
    ring = next(i for i, f in enumerate(fl) if f[0].area() > 3000)
    first = sr.extrude(m, c, fl, {ring}, hide=shapes)
    reg1 = first.children[0]
    again = sr.faces(sr.shapes_of(reg1))
    assert len(again) == 2                          # still both regions
    disc = next(i for i, f in enumerate(again) if f[0].area() < 3000)
    second = sr.extrude(m, reg1, again, {disc})
    reg2 = second.children[0]
    assert regions2d.sketch_source(reg2) is reg1
    assert abs(regions2d._cs(reg2)[0].area() - again[disc][0].area()) < 0.5
    assert abs(regions2d._cs(reg1)[0].area() - fl[ring][0].area()) < 0.5
    m.rename(reg1, "Plate sketch")                 # the link follows
    assert regions2d.sketch_source(reg2) is reg1


def test_an_older_plain_extrude_offers_its_sketch_again():
    # Exercises 1-3: extrudes holding their shapes directly (no Regions)
    # showed no regions at all
    from khervecad import sketch_regions as sr, regions2d
    from khervecad.model import CadNode, DocumentModel
    m = DocumentModel()
    ext = CadNode("linear_extrude", "Boss", {"height": 10})
    m.root.add(ext)
    ext.add(CadNode("square", "Base", {"width": 40, "height": 20})
            if "square" in __import__("khervecad.model").model.NODE_TYPES
            else CadNode("rect", "Base", {"x": 0, "y": 0, "width": 40,
                                          "height": 20}))
    ext.add(CadNode("circle", "Boss circle", {"x": 20, "y": 10,
                                              "radius": 5}))
    assert sr._regions_of(ext) is ext
    fl = sr.faces(sr.shapes_of(ext))
    assert len(fl) == 2
    disc = min(range(2), key=lambda i: fl[i][0].area())
    second = sr.extrude(m, ext, fl, {disc})
    reg = second.children[0]
    assert regions2d.sketch_source(reg) is ext
    assert abs(regions2d._cs(reg)[0].area() - fl[disc][0].area()) < 0.5
    assert second.parent is ext.parent
