"""Smart Dimension to a FACE of the part (2026-11-10, the user: "shall I
not be able to also fix the distance between one face to another face?
... that is not possible").

SolidWorks takes a flat face seen edge-on from the sketch as the line
where it meets the sketch plane. Here a click on a face (away from its
edges) with Smart Dimension gives, in this order:

- the SKETCH LINE that made the face (a boss's side is its sketch's
  line, extruded): the dimension then drives that sketch — two faces of
  two features are dimensioned as their two sketch lines;
- else a fixed construction "Reference face" line in the sketch being
  dimensioned: where the face's plane cuts the sketch plane, as long as
  the face. It carries ``ref_face`` [x, y, z, nx, ny, nz] (a point of
  the face and its facing) and ``ref_owner`` (the feature the face
  belongs to, as face_owner), and `world` finds the face again after
  every model edit (model_refs.follow_references), so the dimension
  holds when the face moves.

A face lying IN the sketch plane's direction (parallel to it) has no
distance in the sketch: that is the extrude's depth.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

#: a face this near perpendicular to the sketch plane (|cos|) is a line
#: in it
EDGE_ON = 0.02
#: points this near a plane (mm) lie on it
ON_PLANE = 2e-3
NAME = "Reference face"


def _normal(t):
    u = [t[1][i] - t[0][i] for i in range(3)]
    v = [t[2][i] - t[0][i] for i in range(3)]
    c = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
         u[0] * v[1] - u[1] * v[0]]
    length = math.sqrt(sum(x * x for x in c))
    return [x / length for x in c] if length > 1e-12 else None


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def face_points(tris, seed, normal):
    """The corners of the flat face of *tris* facing *normal* whose
    plane is nearest *seed*: (points, offset moved along the normal)."""
    d0 = _dot(seed, normal)
    planes = {}
    for t in tris:
        nt = _normal(t)
        if nt is None or _dot(nt, normal) < 0.9995:
            continue
        d = _dot(t[0], normal)
        planes.setdefault(round(d, 3), []).extend(t[:3])
    if not planes:
        return None, 0.0
    d = min(planes, key=lambda k: abs(k - d0))
    return planes[d], d - d0


def line_in_sketch(matrix, points, normal):
    """Where the face through *points* (facing *normal*) cuts the sketch
    plane of numpy *matrix*: ((x, y), (x, y)) in the sketch, as long as
    the face — or None when the face is not edge-on to the sketch."""
    import numpy as np
    m = np.array(matrix, float)
    ns = m[:3, 2] / (np.linalg.norm(m[:3, 2]) or 1.0)
    if abs(float(ns @ np.array(normal, float))) > EDGE_ON:
        return None
    inv = np.linalg.inv(m)
    flat = [(inv @ np.array([*p, 1.0]))[:2] for p in points]
    nf = (inv[:3, :3] @ np.array(normal, float))[:2]
    length = float(np.linalg.norm(nf)) or 1.0
    along = np.array([-nf[1], nf[0]]) / length
    ts = [float(p @ along) for p in flat]
    a, b = flat[ts.index(min(ts))], flat[ts.index(max(ts))]
    if float(np.linalg.norm(b - a)) < 1e-6:
        return None
    return ((round(float(a[0]), 6), round(float(a[1]), 6)),
            (round(float(b[0]), 6), round(float(b[1]), 6)))


def _tris(window, cont, owner):
    from . import face_owner, plane_refs, sketch_section
    node = plane_refs._node(window, owner) if isinstance(owner, int) \
        else None
    if node is not None:
        try:
            got = face_owner._world(window, node)
            if got:
                return got
        except Exception:
            pass
    return sketch_section.built_before(window, cont)


def owner_of(window, cont, seed, normal):
    """The feature_order of the feature whose face holds *seed*."""
    from . import face_owner, feature_list
    feature_list.stamp(window.model)
    try:
        for node in face_owner._before(window, cont):
            if any(face_owner._holds(t, seed, normal)
                   for t in face_owner._world(window, node)):
                return node.params[feature_list.ORDER]
    except Exception:
        pass
    return None


def world(window, cont, node):
    """The two WORLD ends of reference *node*'s line now (its face found
    again), or None. Moves the node's ``ref_face`` onto the face."""
    import numpy as np
    from . import model_refs
    ref = node.params.get("ref_face")
    if not ref:
        return None
    seed, normal = list(ref[:3]), list(ref[3:6])
    tris = _tris(window, cont, node.params.get("ref_owner"))
    if not tris:
        return None
    points, moved = face_points(tris, seed, normal)
    if not points:
        return None
    m = model_refs.sketch_matrix(window, cont)
    line = line_in_sketch(m, points, normal)
    if line is None:
        return None
    if abs(moved) > 1e-9:
        node.params["ref_face"] = [round(seed[i] + normal[i] * moved, 6)
                                   for i in range(3)] + normal
    return [(m @ np.array([p[0], p[1], 0.0, 1.0]))[:3].tolist()
            for p in line]


def reference(tool, cont, face):
    """A "Reference face" line in sketch *cont* for the picked *face*
    {pos, dir, tris}: a pick (node, entity, kind), or None when the face
    is not edge-on to the sketch."""
    from . import model_refs
    window = tool.window
    seed, normal = list(face["pos"]), list(face["dir"])
    points = [p for t in face.get("tris") or [] for p in t[:3]]
    if not points:
        points, _d = face_points(_tris(window, cont, None), seed, normal)
    if not points:
        return None
    line = line_in_sketch(model_refs.sketch_matrix(window, cont),
                          points, normal)
    if line is None:
        return None
    for n in cont.children:                # the same face, used again
        old = n.params.get("ref_face")
        if old and n.type == "line" and \
                _dot(old[3:6], normal) > 0.9995 and \
                abs(_dot([old[i] - seed[i] for i in range(3)], normal)) \
                < ON_PLANE:
            return n, "l", "line"
    tag = dict(ref_face=[round(float(v), 6) for v in (*seed, *normal)])
    owner = owner_of(window, cont, seed, normal)
    if owner is not None:
        tag["ref_owner"] = owner
    made = tool._add_reference(cont, "line", list(line), tag)
    try:
        window.model.rename(made[0], NAME)
    except Exception:
        made[0].name = NAME
    return made


def _edge_on(window, cont, normal):
    """Is a face facing *normal* seen edge-on from *cont*'s sketch?"""
    from . import model_refs
    try:
        m = model_refs.sketch_matrix(window, cont)
    except Exception:
        return False
    ns = [float(m[i][2]) for i in range(3)]
    length = math.sqrt(sum(c * c for c in ns)) or 1.0
    return abs(_dot(ns, normal)) / length <= EDGE_ON


def sketch_line(tool, face):
    """The sketch line that MADE the picked face — it lies in the face's
    plane, under the face — as a pick, or None."""
    seed, normal = list(face["pos"]), list(face["dir"])
    pts = [p for t in face.get("tris") or [] for p in t[:3]]
    best = None
    seen = set()
    for node, name, kind, g in tool.entities():
        if kind != "line" or (id(node), name) in seen:
            continue
        if node.params.get("modifier") == "%":
            continue                        # construction makes no face
        seen.add((id(node), name))          # its own plane's level only
        if not _edge_on(tool.window, node.parent, normal):
            continue                        # the sketch lies IN the face
        a, b = g
        if any(abs(_dot([p[i] - seed[i] for i in range(3)], normal))
               > ON_PLANE for p in (a, b)):
            continue
        if math.dist(a, b) < 1e-6:
            continue
        # the face stands over the line: its corners, dropped along the
        # line, fall within the line's length
        d = [(b[i] - a[i]) / math.dist(a, b) for i in range(3)]
        L = math.dist(a, b)
        ts = [_dot([p[i] - a[i] for i in range(3)], d) for p in pts] or [0]
        if max(ts) < -ON_PLANE or min(ts) > L + ON_PLANE:
            continue
        over = min(max(ts), L) - max(min(ts), 0.0)
        if best is None or over > best[0]:
            best = (over, (node, name, "line"))
    return best[1] if best else None


def run_mcp(window, cont, params):
    """MCP `sketch_constraint` action ``face_reference``: the flat face
    of the part at world ``point`` (from probe_surface) as a fixed
    "Reference face" line in the sketch *cont*; answers its ref, to use
    in a point_line / angle / parallel row."""
    from . import constrain3d, face_owner, sketch_constraints as sc, \
        sketch_section
    point = [float(v) for v in params["point"]]
    tris = sketch_section.built_before(window, cont)
    face = None
    for t in tris:
        nt = _normal(t)
        if nt is not None and face_owner._holds(t, point, nt):
            face = dict(pos=point, dir=nt, tris=[])
            # a normal given picks between two faces meeting at the point
            want = params.get("normal")
            if not want or _dot(nt, [float(v) for v in want]) > 0.9:
                break
    if face is None:
        raise ValueError("No flat face of the part at %s." % point)
    face["tris"] = [[list(p) for p in t[:3]] for t in tris
                    if (_normal(t) or [0, 0, 0]) and
                    _dot(_normal(t) or [0, 0, 0], face["dir"]) > 0.9995 and
                    abs(_dot([t[0][i] - point[i] for i in range(3)],
                             face["dir"])) < ON_PLANE]

    class _Tool:
        _add_reference = constrain3d.Constrain3D._add_reference
        _make_reference = constrain3d.Constrain3D._make_reference

        def __init__(self, w):
            self.window = w
    made = reference(_Tool(window), cont, face)
    if made is None:
        raise ValueError(
            "That face lies flat to the sketch: its distance is the "
            "extrude's depth, not a sketch dimension.")
    node = made[0]
    return {"reference": sc.ref_of(cont, node, "l"), "name": node.name,
            "line": [node.params[k] for k in ("x1", "y1", "x2", "y2")],
            "follows_the_face": True}
