

def test_lines_a_hair_apart_still_close_an_area():
    # trimmed / mirrored pieces come back a few hundredths apart: the
    # area they close is still one region
    from khervecad import sketch_regions as sr
    gap = 0.012
    segs = [((0, 0), (10, 0)), ((10, 0), (10, 10)),
            ((10 + gap, 10 - gap), (0, 10)), ((0, 10), (0, 0))]
    loops = sr.arrangement(segs, [0, 1, 2, 3])
    assert len(loops) == 1
