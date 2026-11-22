"""Clicking the side of a faceted cylinder gave "Edge" (a facet seam)
instead of the round face, so a revolve's axis could not be picked
(Exercise 010's Plane1)."""
from khervecad import anchors, mesh, scadparse


def test_a_smooth_facet_seam_is_not_an_edge():
    tris = mesh.tessellate(scadparse.parse_scad(
        "cylinder(r = 30, h = 40, $fn = 48);")[0])
    side = [t for t in tris if abs(t[0][2] - t[1][2]) > 1e-6 or
            abs(t[1][2] - t[2][2]) > 1e-6]
    i = tris.index(side[0])
    t = tris[i]
    # a point on a vertical facet seam (an edge of the triangle that
    # changes height), mid-height
    for p, q in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
        if abs(p[2] - q[2]) > 1e-6 and abs(p[0] - q[0]) + abs(p[1] - q[1]) < 1e-6:
            seam = [(p[k] + q[k]) / 2 for k in range(3)]
            break
    d = anchors.describe_pick(tris, i, seam, 2.0)
    assert d["kind"] == "face", d["kind"]
