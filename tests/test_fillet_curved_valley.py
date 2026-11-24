# KherveCAD — GPL-3.0-or-later. See LICENSE.
"""A fillet strip is trimmed at each end of its edge by the faces the
edge runs into — but only by a face whose plane leaves the WHOLE edge on
its kept side. Exercise 10's valley between two arms curves from the
dome's top down the arms; a facet plane at its foot cut back across the
crease higher up, and the filler was sliced off along the valley,
leaving an open slot between the round and the crease."""
import pytest

from khervecad import analysis, csg, fillet

pytestmark = pytest.mark.skipif(not csg.available(),
                                reason="needs manifold3d")


def _box(x0, y0, z0, x1, y1, z1):
    p = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    q = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3),
         (0, 4, 6, 2), (1, 3, 7, 5)]
    tris = []
    for a, b, c, d in q:
        tris += [(p[a], p[b], p[c]), (p[a], p[c], p[d])]
    return tris


def _run():
    pts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 1.0)]
    nl, nr = (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)
    edges = [fillet.Edge(pts[k], pts[k + 1], nl, nr, 90.0, False)
             for k in range(2)]
    return dict(points=pts, edges=edges, closed=False, convex=False)


def test_a_plane_crossing_the_curved_edge_does_not_trim_the_strip():
    body = _box(-0.1, -0.2, -0.2, 2.2, 0.2, 1.2)
    # a face at the run's start leaning back over the edge: the start's
    # neighbour is kept, but the run's far end lies behind the plane
    m = fillet._unit((1.0, 0.0, -3.0))
    around = {fillet._vkey((0.0, 0.0, 0.0)): [m]}
    out = fillet._trim_ends(body, _run(), around)
    vol = analysis.mass_properties(out)["volume"]
    assert vol == pytest.approx(analysis.mass_properties(body)["volume"],
                                rel=1e-6)


def test_a_plane_the_edge_ends_on_still_trims():
    body = _box(-0.5, -0.2, -0.2, 2.2, 0.2, 1.2)
    # the face the edge stops on, square across it: what reaches past
    # the start goes
    around = {fillet._vkey((0.0, 0.0, 0.0)): [(1.0, 0.0, 0.0)]}
    out = fillet._trim_ends(body, _run(), around)
    xs = [v[0] for t in out for v in t]
    assert min(xs) == pytest.approx(0.0, abs=1e-6)


def test_a_filler_corner_is_sunk_into_the_part():
    """A filler's corner lies past the crease, on the far side from its
    round: its flat sides run under the two faces, not on them."""
    e = fillet.Edge((0, 0, 0), (0, 0, 1), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
                    90.0, False)
    t = e.direction
    dl = fillet._unit(fillet._cross(e.nl, t))
    dr = fillet._unit(fillet._cross(t, e.nr))
    mid = fillet._unit(fillet._add(dl, dr))      # towards the round
    u, v, pts = fillet.profile(e, 1.0, "round", 6)

    def along(p):
        w = [u[k] * p[0] + v[k] * p[1] for k in range(3)]
        return fillet._dot(w, mid)
    assert along(pts[0]) < -0.2                   # sunk a quarter radius
    assert all(along(p) > 0.0 for p in pts[1:])
