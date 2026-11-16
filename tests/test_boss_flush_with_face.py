"""A boss whose arms reach the face's edges is exactly flush (88 x 50),
not 0.05 mm proud of the grown outline (88.1 x 50.1)."""
import manifold3d as m
from khervecad import regions2d, sketch_section


def test_arms_reaching_the_edges_stay_inside_the_true_outline():
    g = sketch_section.GROW
    grown = m.CrossSection([[(-44 - g, -25 - g), (44 + g, -25 - g),
                             (44 + g, 25 + g), (-44 - g, 25 + g)]])
    cross = m.CrossSection([[(-44 - g, 3), (44 + g, 3), (44 + g, 15),
                             (-44 - g, 15)]]) + m.CrossSection(
        [[(-6, -25 - g), (6, -25 - g), (6, 25 + g), (-6, 25 + g)]])
    out = regions2d.flush_to_outline(cross, grown, m)
    x0, y0, x1, y1 = out.bounds()
    assert (x0, x1) == (-44.0, 44.0) or (abs(x0 + 44) < 1e-6 and abs(x1 - 44) < 1e-6)
    assert abs(y0 + 25) < 1e-6 and abs(y1 - 25) < 1e-6
