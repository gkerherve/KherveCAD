# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Faces NAMED by what made them — the answer to CAD's "topological
naming problem" for fillets and chamfers (2026-11-10, the user: "rerun
the process ... everything above in the tree should be redone", not a
guess at where the clicked edge went).

The tree is always rebuilt from the sketches up; what a fillet needed was
to know WHICH new edge is the one the user clicked. Coordinates cannot
say that once a Smart Dimension moved it. SolidWorks names every face by
the feature and sketch entity that generated it; so does this module:

- a Linear extrude's side swept by a sketch entity — "<feature>:<shape
  index>.<entity>" (a rectangle's e2, a polygon's e4, a line, a circle's
  rim "o"; a Regions outline segment by the sketch shape it lies on) —
  and its caps "<feature>:cap0" / ":cap1";
- a Rotate extrude's surface swept by a profile segment the same way;
- a cube's six faces, a cylinder's side and caps.

`<feature>` is the node's `feature_order` (stable, saved; feature_list),
else its name. `names(root, env, tris)` gives one name (or None) per
triangle of *tris*, given in *root*'s own frame — whatever booleans
Manifold did on the way, a face stays in the plane / on the surface it
was made on, which is what is tested. An edge is then named by the two
faces meeting at it; fillet.py keeps those names beside the clicked
coordinates and, after a rebuild, takes every crease between faces of
the same names. Meshes and imports have no names: the coordinates stay
their fallback.
"""

import math

#: distance from a generating surface that still counts as on it, as a
#: fraction of the part's size (plus an absolute floor in mm)
TOL_FRAC = 1e-4
TOL_MIN = 1e-3


def _key(node):
    order = node.params.get("feature_order")
    return str(order) if order is not None else "n:%s" % node.name


def _inverse(m):
    import numpy as np
    return np.linalg.inv(np.array(m, float))


def _num(node, key, env, default):
    from . import expr
    try:
        return float(expr.resolve(node.params.get(key, default), env,
                                  default))
    except (TypeError, ValueError):
        return default


class _Surface:
    """One generating surface: *test(local centroid, local normal)* in
    the generator's frame, *inv* maps root coordinates into it."""
    __slots__ = ("name", "inv", "test")

    def __init__(self, name, inv, test):
        self.name, self.inv, self.test = name, inv, test


def _shape_segments(container, env, hidden_ok=False):
    """[(name, a, b, circle)] of the 2D shapes directly in *container*
    (or in its Regions / plain groups), in the container's frame: each
    straight entity once; a circle's rim as (centre, radius)."""
    from . import mesh, sketch_constraints as sc, sketch_section
    out = []
    for index, shape in enumerate(container.children):
        if shape.params.get("modifier") == "%" or \
                (not shape.visible and not hidden_ok) or \
                sketch_section.is_section(shape):
            continue                   # (the kept model edges: no entity)
        t = shape.type
        try:
            m = mesh.node_matrix(shape, env)
        except Exception:
            m = None
        if t == "circle":
            c = (_num(shape, "x", env, 0.0), _num(shape, "y", env, 0.0))
            out.append(("%d.o" % index, c, _num(shape, "radius", env, 1.0),
                        True))
        elif t == "line" and not shape.params.get("bulge"):
            try:
                a, b = sc._line(shape, "l", {})
            except (KeyError, ValueError, TypeError):
                continue
            # a sketch line is a band: the Regions outline runs along
            # its EDGE, half its width (+ the section's grow) off it
            out.append(("%d.l" % index, a, b,
                        max(0.0, _num(shape, "width", env, 0.0)) / 2.0
                        + 0.06))
        elif t in ("rect", "polygon"):
            n = 4 if t == "rect" else len(shape.params.get("points") or [])
            for i in range(n):
                try:
                    a, b = sc._line(shape, "e%d" % i, {})
                except (KeyError, ValueError, IndexError, TypeError):
                    continue
                out.append(("%d.e%d" % (index, i), a, b, False))
        elif t in ("union", "regions") and m is not None:
            # (a Regions hides the shapes it was cut from: they still
            # name its sides)
            for name, a, b, circle in _shape_segments(
                    shape, env, hidden_ok or t == "regions"):
                out.append(("%d/%s" % (index, name), a, b, circle))
    return out


def _sides(c2, segs, tol, unset, out, key):
    """Name the triangles (centroids *c2*, N x 2, in the profile's plane)
    lying on each sketch entity's swept side; *unset* masks the ones
    still to name."""
    import numpy as np
    for name, a, b, circle in segs:
        if not unset.any():
            return
        if circle is True:
            r = float(b)
            d = np.abs(np.hypot(c2[:, 0] - a[0], c2[:, 1] - a[1]) - r)
            hit = unset & (d < max(tol, r * 0.03))
        else:
            ax, ay = float(a[0]), float(a[1])
            dx, dy = float(b[0]) - ax, float(b[1]) - ay
            n2 = dx * dx + dy * dy
            if n2 < 1e-18:
                continue
            t = ((c2[:, 0] - ax) * dx + (c2[:, 1] - ay) * dy) / n2
            d = np.abs(dx * (c2[:, 1] - ay) - dy * (c2[:, 0] - ax)) / \
                math.sqrt(n2)
            band = 0.0 if circle is False else float(circle)
            reach = band / math.sqrt(n2) + 1e-3     # past its round ends
            hit = unset & (d < tol + band) & (t >= -reach) & \
                (t <= 1 + reach)
        if hit.any():
            out[hit] = "%s:%s" % (key, name)
            unset &= ~hit


def _extrude_surfaces(node, root, env, tol):
    from . import mesh
    if _num(node, "twist", env, 0.0) or \
            abs(_num(node, "scale", env, 1.0) - 1.0) > 1e-9:
        return []                       # sides no longer planar
    m = mesh.mat_mul(mesh.ancestor_matrix(node, env, stop=root),
                     mesh.node_matrix(node, env))
    inv = _inverse(m)
    h = _num(node, "height", env, 10.0)
    h2 = _num(node, "height2", env, 0.0)
    if node.params.get("center"):
        z0, z1 = -h / 2.0, h / 2.0
    else:
        z0, z1 = -max(h2, 0.0), h
    if z1 < z0:
        z0, z1 = z1, z0
    segs = _shape_segments(node, env)
    key = _key(node)

    def test(c, n, unset, out):
        import numpy as np
        flat = np.abs(n[:, 2]) > 0.99
        for z, word in ((z0, "cap0"), (z1, "cap1")):
            hit = unset & flat & (np.abs(c[:, 2] - z) < tol)
            out[hit] = "%s:%s" % (key, word)
            unset &= ~hit
        side = unset & (np.abs(n[:, 2]) < 0.05) & (c[:, 2] > z0 - tol) & \
            (c[:, 2] < z1 + tol)
        _sides(c[:, :2], segs, tol, side, out, key)
        unset &= ~(out != None)  # noqa: E711 (numpy object compare)
    return [_Surface(key, inv, test)]


def _revolve_surfaces(node, root, env, tol):
    from . import mesh
    m = mesh.ancestor_matrix(node, env, stop=root)
    inv = _inverse(m)
    segs = _shape_segments(node, env)
    key = _key(node)

    def test(c, n, unset, out):
        import numpy as np
        r = np.hypot(c[:, 0], c[:, 1])
        rz = np.stack([r, c[:, 2]], axis=1)
        mine = unset.copy()
        _sides(rz, segs, max(tol, float(r.max()) * 0.005 if len(r) else
                             tol), mine, out, key)
        unset &= ~(out != None)  # noqa: E711
    return [_Surface(key, inv, test)]


def _cube_surfaces(node, root, env, tol):
    from . import mesh
    m = mesh.ancestor_matrix(node, env, stop=root)
    inv = _inverse(m)
    w = _num(node, "width", env, 10.0)
    d = _num(node, "depth", env, w)
    h = _num(node, "height", env, w)
    lo = [0.0, 0.0, 0.0]
    if node.params.get("center"):
        lo = [-w / 2.0, -d / 2.0, -h / 2.0]
    hi = [lo[0] + w, lo[1] + d, lo[2] + h]
    key = _key(node)

    def test(c, n, unset, out):
        import numpy as np
        for axis, word in enumerate("xyz"):
            flat = np.abs(n[:, axis]) > 0.99
            for v, sign in ((lo[axis], "-"), (hi[axis], "+")):
                hit = unset & flat & (np.abs(c[:, axis] - v) < tol)
                out[hit] = "%s:%s%s" % (key, word, sign)
                unset &= ~hit
    return [_Surface(key, inv, test)]


def _cylinder_surfaces(node, root, env, tol):
    from . import mesh
    m = mesh.ancestor_matrix(node, env, stop=root)
    inv = _inverse(m)
    h = _num(node, "height", env, 10.0)
    z0 = -h / 2.0 if node.params.get("center") else 0.0
    key = _key(node)

    def test(c, n, unset, out):
        import numpy as np
        flat = np.abs(n[:, 2]) > 0.99
        for z, word in ((z0, "cap0"), (z0 + h, "cap1")):
            hit = unset & flat & (np.abs(c[:, 2] - z) < tol)
            out[hit] = "%s:%s" % (key, word)
            unset &= ~hit
        hit = unset & ~flat & (c[:, 2] > z0 - tol) & (c[:, 2] < z0 + h + tol)
        out[hit] = "%s:side" % key
        unset &= ~hit
    return [_Surface(key, inv, test)]


_MAKERS = {"linear_extrude": _extrude_surfaces,
           "rotate_extrude": _revolve_surfaces,
           "cube": _cube_surfaces, "cylinder": _cylinder_surfaces}


def surfaces(root, env, tol):
    """Every generating surface under *root*, latest feature first (a
    face a later feature lies flush on is that feature's)."""
    out = []
    for node in root.walk():
        if node is root or not node.visible:
            continue
        maker = _MAKERS.get(node.type)
        if maker is None:
            continue
        try:
            out.extend(maker(node, root, env, tol))
        except Exception:                 # never stop a fillet
            continue
    out.reverse()
    return out


def names(root, env, tris):
    """One face name (or None) per triangle of *tris* (in *root*'s
    frame)."""
    import numpy as np
    if not tris:
        return []
    pts = np.array([v for t in tris for v in t], float).reshape(-1, 3, 3)
    flat = pts.reshape(-1, 3)
    size = float(np.max(flat.max(0) - flat.min(0)))
    tol = max(TOL_MIN, size * TOL_FRAC)
    surfs = surfaces(root, env, tol)
    out = np.full(len(tris), None, dtype=object)
    if not surfs:
        return list(out)
    cen = pts.mean(axis=1)
    nrm = np.cross(pts[:, 1] - pts[:, 0], pts[:, 2] - pts[:, 0])
    for s in surfs:
        unset = np.array([v is None for v in out], dtype=bool)
        if not unset.any():
            break
        lin = s.inv[:3, :3]
        lc = cen @ lin.T + s.inv[:3, 3]
        # a normal goes through the inverse transpose of the point map:
        # as a row vector, n · inv(lin)
        ln = nrm @ np.linalg.inv(lin)
        ln = ln / np.maximum(np.linalg.norm(ln, axis=1, keepdims=True),
                             1e-30)
        try:
            s.test(lc, ln, unset, out)
        except Exception:                 # never stop a fillet
            continue
    return list(out)
