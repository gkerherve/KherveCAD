"""A needle triangle (a boolean's leftover, all length and no width) has
a normal that points anywhere: crease_edges read folds of 150-180
degrees off it and the fillet shredded Exercise 10's dome with shards."""
from khervecad import fillet

E = 1e-5


def _cube_with_folded_needle():
    # unit cube; on its top face the point M sits a hair beside the
    # diagonal A-C, so the needle A-M-C beside it faces down: a fold of
    # ~180 degrees in the middle of a flat face
    A, B, C, D = (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)
    M = (0.5 - E, 0.5 + E, 1)
    a, b, c, d = (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)
    return [
        (A, B, M), (B, C, M),                      # top, front of A-C
        (A, M, C),                                 # the needle
        (A, C, D),                                 # top, behind A-C
        (a, b, B), (a, B, A), (b, c, C), (b, C, B),
        (c, d, D), (c, D, C), (d, a, A), (d, A, D),
        (a, c, b), (a, d, c),
    ]


def test_a_needle_makes_no_false_crease_in_a_flat_face():
    edges = fillet.crease_edges(_cube_with_folded_needle())
    folds = [round(e.angle) for e in edges if e.angle > 100]
    assert not folds, folds


def test_the_cube_keeps_its_twelve_edges():
    edges = fillet.crease_edges(_cube_with_folded_needle())
    rims = [e for e in edges if abs(e.angle - 90) < 1]
    assert abs(sum(e.length for e in rims) - 12) < 1e-6


def test_a_crease_shorter_than_the_radius_alone_is_left_sharp():
    # a 0.1 nick of a crease, far shorter than a 0.5 round, on nothing
    # else: Exercise 10's dome tip, where the arm tops touch it, left
    # nubs and pits of that size
    from khervecad import fillet as f
    A, B = (0, 0, 0), (0.1, 0, 0)
    run = dict(points=[A, B], edges=[], closed=False, convex=True)
    assert f._too_short(run, 0.5)
    assert not f._too_short(dict(run, points=[A, (1, 0, 0)]), 0.5)
    assert not f._too_short(dict(run, closed=True), 0.5)
