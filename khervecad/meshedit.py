"""Editing a polyhedron vertex by vertex — Blender's Edit Mode, as
geometry.

Blender keeps every object as a mesh you can open (Tab) and work on
point by point: drag vertices, add more where the shape needs them,
extrude a face out, subdivide a patch, merge, relax. KherveCAD's
objects are parametric instead, so Edit Mode works on OpenSCAD's own
``polyhedron`` node — points plus faces, exactly what the program
writes — and anything else is first CONVERTED into one (Blender's
Convert to Mesh): its preview triangles welded, coplanar neighbours
merged back into quads and convex polygons, so a cube opens as 8
vertices and 6 faces, not 12 triangles.

Faces are stored like the node stores them: point indices CLOCKWISE
seen from outside (OpenSCAD's rule). Every operation here keeps that
winding and keeps a closed surface closed — an edge split is written
into both faces that share the edge, a subdivided patch's border
midpoints are added to the neighbours too, an extrusion bridges its
rim with side quads — so the result always passes the polyhedron
validation and renders in OpenSCAD.

Pure geometry, Qt-free: `meshedit_ui.py` is the 3D view's side and the
MCP ``edit_mesh`` tool calls these functions directly.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

#: digits a coordinate is kept to — what the program is written with
DIGITS = 4
#: refuse to open a mesh bigger than this (a tree, a scan): thousands
#: of handles are not editable by hand — Decimate it first
MAX_POINTS = 40000
MIRRORS = ("none", "x", "y", "z")
#: how proportional editing fades with distance (Blender's names)
FALLOFFS = ("smooth", "linear", "sharp", "root", "sphere", "constant")


# ------------------------------------------------------------- vectors

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-15 else (0.0, 0.0, 0.0)


def _round(v):
    return [round(float(v[0]), DIGITS), round(float(v[1]), DIGITS),
            round(float(v[2]), DIGITS)]


def _copy(points, faces):
    return ([list(p) for p in points], [list(f) for f in faces])


# --------------------------------------------------------------- faces

def face_normal(points, face):
    """Outward unit normal of *face* (clockwise from outside) by
    Newell's method, so a slightly warped quad still has one."""
    nx = ny = nz = 0.0
    n = len(face)
    for k in range(n):
        a, b = points[face[k]], points[face[(k + 1) % n]]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    # Newell gives the counter-clockwise normal: ours run clockwise
    return _unit((-nx, -ny, -nz))


def face_centre(points, face):
    n = float(len(face))
    return (sum(points[i][0] for i in face) / n,
            sum(points[i][1] for i in face) / n,
            sum(points[i][2] for i in face) / n)


def edges(faces):
    """Every edge once, as ``(a, b)`` with a < b, in a stable order."""
    seen, out = set(), []
    for face in faces:
        n = len(face)
        for k in range(n):
            a, b = face[k], face[(k + 1) % n]
            key = (a, b) if a < b else (b, a)
            if key not in seen:
                seen.add(key)
                out.append(key)
    return out


def selected_faces(faces, selection) -> list:
    """Indices of the faces whose every vertex is selected — Blender's
    vertex-mode rule for which faces a selection holds."""
    sel = set(selection)
    return [i for i, f in enumerate(faces) if f and all(v in sel for v in f)]


def neighbours(points, faces):
    """Vertex -> set of vertices sharing an edge with it."""
    out = [set() for _ in points]
    for face in faces:
        n = len(face)
        for k in range(n):
            a, b = face[k], face[(k + 1) % n]
            out[a].add(b)
            out[b].add(a)
    return out


def compact(points, faces, selection=()):
    """Drop points no face uses; returns ``(points, faces, selection)``
    with every index renumbered."""
    used = sorted({v for f in faces for v in f})
    remap = {old: new for new, old in enumerate(used)}
    return ([list(points[i]) for i in used],
            [[remap[v] for v in f] for f in faces],
            sorted(remap[v] for v in selection if v in remap))


# ------------------------------------------------------------ convert

def triangles_to_mesh(tris, merge: bool = True):
    """``(points, faces)`` from counter-clockwise triangles: vertices
    welded at DIGITS, faces turned clockwise-from-outside, collapsed
    ones dropped and — with *merge* — coplanar neighbours joined into
    quads and convex polygons, the way Blender shows a cube."""
    index, points, faces = {}, [], []
    for tri in tris:
        ids = []
        for v in tri:
            key = (round(v[0], DIGITS), round(v[1], DIGITS),
                   round(v[2], DIGITS))
            i = index.get(key)
            if i is None:
                i = index[key] = len(points)
                points.append([key[0], key[1], key[2]])
            ids.append(i)
        if len(set(ids)) == 3:
            faces.append([ids[0], ids[2], ids[1]])
    if merge:
        faces = merge_coplanar(points, faces)
        points, faces, _ = compact(points, faces)   # cap centres went
    return points, faces


def _plane_key(points, face):
    n = face_normal(points, face)
    return n, _dot(n, points[face[0]])


def _loop_of(faces_in_group):
    """The one boundary loop of a group of faces (directed edges kept
    from the faces, so it runs clockwise too), or None when the group
    has holes, several loops or a vertex the boundary passes twice.
    Points inside the group (a cap's centre) are not on it: every face
    round them is in the group, so the merged polygon drops them."""
    directed = set()
    for face in faces_in_group:
        n = len(face)
        for k in range(n):
            directed.add((face[k], face[(k + 1) % n]))
    nxt = {}
    for a, b in directed:
        if (b, a) in directed:
            continue
        if a in nxt:
            return None                       # pinched boundary
        nxt[a] = b
    if not nxt:
        return None
    start = next(iter(nxt))
    loop, v = [start], nxt[start]
    while v != start:
        if v not in nxt or len(loop) > len(nxt):
            return None
        loop.append(v)
        v = nxt[v]
    if len(loop) != len(nxt):
        return None                           # more than one loop
    return loop


def _convex_loop(points, loop, normal):
    """*loop* (clockwise from outside) rotated to start on a real
    corner, or None when it is not convex. Collinear points are fine —
    they are shared with a neighbour and must stay."""
    n = len(loop)
    corners = []
    for k in range(n):
        a = points[loop[k - 1]]
        b = points[loop[k]]
        c = points[loop[(k + 1) % n]]
        turn = _dot(_cross(_sub(b, a), _sub(c, b)), normal)
        span = _norm(_sub(b, a)) * _norm(_sub(c, b)) or 1.0
        t = turn / span
        if t > 1e-6:          # clockwise ring: a convex corner turns -n
            return None
        if t < -1e-6:
            corners.append(k)
    if len(corners) < 3:
        return None
    k = corners[0]
    return loop[k:] + loop[:k]


def merge_coplanar(points, faces):
    """Join edge-connected faces lying in one plane into one convex
    polygon each (a quad from two triangles, a box side, a cylinder
    facet). A region that would not be convex, or has a vertex inside
    it, keeps its faces as they are."""
    count = len(faces)
    keys = [_plane_key(points, f) for f in faces]
    by_edge = {}
    for i, face in enumerate(faces):
        n = len(face)
        for k in range(n):
            by_edge[(face[k], face[(k + 1) % n])] = i
    group = [-1] * count
    out = []
    for i in range(count):
        if group[i] >= 0:
            continue
        ni, di = keys[i]
        members, stack = [], [i]
        group[i] = i
        while stack:
            j = stack.pop()
            members.append(j)
            face = faces[j]
            n = len(face)
            for k in range(n):
                o = by_edge.get((face[(k + 1) % n], face[k]))
                if o is None or group[o] >= 0:
                    continue
                no, do = keys[o]
                if _dot(no, ni) > 1.0 - 1e-9 and abs(do - di) < 1e-6:
                    group[o] = i
                    stack.append(o)
        if len(members) == 1:
            out.append(list(faces[i]))
            continue
        loop = _loop_of([faces[j] for j in members])
        ring = _convex_loop(points, loop, ni) if loop else None
        if ring is None:
            out.extend(list(faces[j]) for j in sorted(members))
        else:
            out.append(ring)
    return out


# --------------------------------------------------------------- move

def falloff(t: float, kind: str = "smooth") -> float:
    """Weight for a vertex at fraction *t* (0 at the brush centre, 1 at
    its edge) of the proportional radius."""
    if t >= 1.0:
        return 0.0
    s = 1.0 - max(0.0, t)
    if kind == "linear":
        return s
    if kind == "sharp":
        return s * s
    if kind == "root":
        return math.sqrt(s)
    if kind == "sphere":
        return math.sqrt(max(0.0, 1.0 - (1.0 - s) ** 2))
    if kind == "constant":
        return 1.0
    return s * s * (3.0 - 2.0 * s)            # smooth


def weights(points, selection, proportional: float = 0.0,
            kind: str = "smooth") -> dict:
    """Vertex -> how much of a move it takes: 1 for the selection, a
    falloff over *proportional* mm round it (Blender's proportional
    editing, O), nothing beyond."""
    sel = [i for i in dict.fromkeys(selection) if 0 <= i < len(points)]
    out = {i: 1.0 for i in sel}
    r = float(proportional or 0.0)
    if r <= 0.0 or not sel:
        return out
    anchors = [points[i] for i in sel]
    for i, p in enumerate(points):
        if i in out:
            continue
        d = min(_norm(_sub(p, a)) for a in anchors)
        if d < r:
            w = falloff(d / r, kind)
            if w > 0.0:
                out[i] = w
    return out


def mirror_partners(points, axis) -> dict:
    """Vertex -> its mirror image across the plane *axis* = 0 (x, y or
    z), for those that have one (a vertex ON the plane is its own)."""
    k = "xyz".find(str(axis))
    if k < 0:
        return {}
    at = {}
    for i, p in enumerate(points):
        at.setdefault(tuple(round(v, 3) for v in p), i)
    out = {}
    for i, p in enumerate(points):
        q = list(p)
        q[k] = -q[k]
        j = at.get(tuple(round(v, 3) for v in q))
        if j is not None:
            out[i] = j
    return out


def displace(points, offsets: dict, mirror: str = "none"):
    """Points with each ``index -> (dx, dy, dz)`` of *offsets* added —
    and, when *mirror* names an axis (Blender's X-mirror), the mirror
    image of every moved vertex moved by the reflected offset; a vertex
    ON the mirror plane keeps to it. The general form behind move,
    scale and rotate."""
    pts = [list(p) for p in points]
    k = "xyz".find(str(mirror))
    partners = mirror_partners(points, mirror) if k >= 0 else {}
    out = {}
    for i, d in offsets.items():
        d = list(d)
        if k >= 0 and partners.get(i) == i:
            d[k] = 0.0                       # on the mirror plane
        out[i] = d
    for i, d in list(out.items()):
        j = partners.get(i)
        if j is not None and j != i and j not in offsets:
            m = list(d)
            m[k] = -m[k]
            out[j] = m
    for i, d in out.items():
        pts[i] = _round([pts[i][0] + d[0], pts[i][1] + d[1],
                         pts[i][2] + d[2]])
    return pts


def move(points, selection, delta, proportional: float = 0.0,
         mirror: str = "none", kind: str = "smooth"):
    """Points with the selection moved by *delta* (mm), dragging its
    surroundings along with *proportional* (a radius, mm), mirrored
    across *mirror* (x, y, z or none)."""
    w = weights(points, selection, proportional, kind)
    return displace(points, {i: _scale(delta, wi) for i, wi in w.items()},
                    mirror)


def transform(points, selection, fn, proportional: float = 0.0,
              mirror: str = "none", kind: str = "smooth"):
    """Points with *fn* (point -> new point, the node's own frame)
    applied to the selection — a scale or a rotation about a pivot —
    and to its proportional surroundings by their weight."""
    w = weights(points, selection, proportional, kind)
    offsets = {}
    for i, wi in w.items():
        p = points[i]
        q = fn(p)
        offsets[i] = _scale(_sub(q, p), wi)
    return displace(points, offsets, mirror)


def set_position(points, index, position):
    """Points with vertex *index* put exactly at *position*."""
    pts = [list(p) for p in points]
    pts[index] = _round(position)
    return pts


# ------------------------------------------------------- adding points

def split_edge(points, faces, a, b, t: float = 0.5):
    """A new vertex on edge a-b at fraction *t* from a, written into
    every face that has the edge, so the surface stays closed. Returns
    ``(points, faces, new_index)``; new_index is None when a-b is not
    an edge."""
    pts, fcs = _copy(points, faces)
    t = min(max(float(t), 0.0), 1.0)
    pa, pb = points[a], points[b]
    new = len(pts)
    found = False
    for face in fcs:
        n = len(face)
        for k in range(n):
            u, v = face[k], face[(k + 1) % n]
            if (u, v) in ((a, b), (b, a)):
                face.insert(k + 1, new)
                found = True
                break
    if not found:
        return [list(p) for p in points], [list(f) for f in faces], None
    pts.append(_round(_add(pa, _scale(_sub(pb, pa), t))))
    return pts, fcs, new


def subdivide(points, faces, selection, cuts: int = 1):
    """Blender's Subdivide on the faces the selection holds: every edge
    of them cut at its middle, a triangle into four, a quad or polygon
    into quads round a new centre point. A neighbour sharing a cut
    edge gets the midpoint too (no crack). *cuts* repeats it. Returns
    ``(points, faces, selection)`` — the selection grown to the new
    points, so it can be subdivided again or dragged."""
    pts, fcs = _copy(points, faces)
    sel = set(selection)
    for _ in range(max(1, int(cuts))):
        chosen = set(selected_faces(fcs, sel))
        if not chosen:
            break
        mid = {}

        def midpoint(a, b):
            key = (a, b) if a < b else (b, a)
            i = mid.get(key)
            if i is None:
                i = mid[key] = len(pts)
                pa, pb = pts[a], pts[b]
                pts.append(_round(_scale(_add(pa, pb), 0.5)))
            return i

        out = []
        for i, face in enumerate(fcs):
            n = len(face)
            if i in chosen:
                m = [midpoint(face[k], face[(k + 1) % n]) for k in range(n)]
                if n == 3:
                    out.append([face[0], m[0], m[2]])
                    out.append([face[1], m[1], m[0]])
                    out.append([face[2], m[2], m[1]])
                    out.append([m[0], m[1], m[2]])
                else:
                    c = len(pts)
                    pts.append(_round(face_centre(pts, face)))
                    sel.add(c)
                    for k in range(n):
                        out.append([face[k], m[k], c, m[k - 1]])
                sel.update(m)
            else:
                out.append(list(face))
        # neighbours of the patch: take the midpoints of their cut edges
        final = []
        for face in out:
            ring = []
            n = len(face)
            for k in range(n):
                a, b = face[k], face[(k + 1) % n]
                ring.append(a)
                key = (a, b) if a < b else (b, a)
                m = mid.get(key)
                if m is not None and m not in face:
                    ring.append(m)
            final.append(ring)
        fcs = final
    return pts, fcs, sorted(sel)


def extrude(points, faces, selection, distance: float = 0.0):
    """Blender's Extrude (E) on the faces the selection holds: the
    region is copied, joined to where it was by side quads along its
    rim, and pushed *distance* mm along its mean normal. Returns
    ``(points, faces, selection, normal)`` with the selection on the
    moved copy — or None when the selection holds no faces, or every
    face (there is no rim to bridge)."""
    region = set(selected_faces(faces, selection))
    if not region or len(region) == len(faces):
        return None
    pts, fcs = _copy(points, faces)
    directed = {}
    for i in region:
        face = faces[i]
        n = len(face)
        for k in range(n):
            directed[(face[k], face[(k + 1) % n])] = i
    rim = [(a, b) for (a, b) in directed if (b, a) not in directed]
    verts = sorted({v for i in region for v in faces[i]})
    normal = (0.0, 0.0, 0.0)
    for i in region:
        normal = _add(normal, face_normal(points, faces[i]))
    normal = _unit(normal)
    copy = {}
    for v in verts:
        copy[v] = len(pts)
        pts.append(_round(_add(points[v], _scale(normal, distance))))
    for i in region:
        fcs[i] = [copy[v] for v in faces[i]]
    for a, b in rim:
        fcs.append([a, b, copy[b], copy[a]])
    pts, fcs, sel = compact(pts, fcs, [copy[v] for v in verts])
    return pts, fcs, sel, normal


def merge(points, faces, selection, at=None):
    """Blender's Merge at Center (M): the selection collapsed into one
    vertex at its centroid (or *at*); faces left with fewer than three
    corners disappear. Returns ``(points, faces, selection)``."""
    sel = [i for i in dict.fromkeys(selection) if 0 <= i < len(points)]
    if len(sel) < 2:
        return _copy(points, faces) + (list(sel),)
    pts, _ = _copy(points, [])
    if at is None:
        n = float(len(sel))
        at = (sum(points[i][0] for i in sel) / n,
              sum(points[i][1] for i in sel) / n,
              sum(points[i][2] for i in sel) / n)
    keep = sel[0]
    pts[keep] = _round(at)
    gone = set(sel[1:])
    out = []
    for face in faces:
        ring = []
        for v in face:
            v = keep if v in gone else v
            if not ring or ring[-1] != v:
                ring.append(v)
        while len(ring) > 1 and ring[0] == ring[-1]:
            ring.pop()
        if len(set(ring)) >= 3 and len(set(ring)) == len(ring):
            out.append(ring)
    pts, out, new_sel = compact(pts, out, [keep])
    return pts, out, new_sel


def smooth(points, faces, selection, factor: float = 0.5,
           passes: int = 1):
    """Blender's Smooth Vertices: each selected vertex moved *factor* of
    the way to the mean of its neighbours, *passes* times."""
    pts = [list(p) for p in points]
    near = neighbours(points, faces)
    sel = [i for i in dict.fromkeys(selection) if 0 <= i < len(points)]
    for _ in range(max(1, int(passes))):
        new = {}
        for i in sel:
            ring = near[i]
            if not ring:
                continue
            n = float(len(ring))
            m = (sum(pts[j][0] for j in ring) / n,
                 sum(pts[j][1] for j in ring) / n,
                 sum(pts[j][2] for j in ring) / n)
            new[i] = _round(_add(pts[i], _scale(_sub(m, pts[i]), factor)))
        for i, p in new.items():
            pts[i] = p
    return pts


def select_linked(faces, selection) -> list:
    """Blender's Select Linked (Ctrl+L): every vertex joined to the
    selection through edges."""
    near = {}
    for face in faces:
        n = len(face)
        for k in range(n):
            a, b = face[k], face[(k + 1) % n]
            near.setdefault(a, set()).add(b)
            near.setdefault(b, set()).add(a)
    seen = set(selection)
    stack = list(seen)
    while stack:
        v = stack.pop()
        for w in near.get(v, ()):
            if w not in seen:
                seen.add(w)
                stack.append(w)
    return sorted(seen)


def check(points, faces):
    """None when *points*/*faces* form a closed, consistently wound
    polyhedron; else the message the node's validation would give."""
    from .bake import _check_polyhedron
    return _check_polyhedron(dict(points=points, faces=faces))


def dissolve(points, faces, selection):
    """Blender's Dissolve Vertices: each selected vertex removed and the
    faces round it joined into one polygon through its neighbours, so
    the surface stays closed. A vertex on the rim of an open fan, or
    whose faces do not close round it, is left alone. Returns
    ``(points, faces, selection)`` (selection emptied)."""
    pts, fcs = _copy(points, faces)
    for v in dict.fromkeys(selection):
        around = [i for i, f in enumerate(fcs) if v in f]
        if len(around) < 3:
            continue
        directed = {}
        for i in around:
            f = fcs[i]
            n = len(f)
            for k in range(n):
                a, b = f[k], f[(k + 1) % n]
                if v not in (a, b):
                    directed[a] = b
        if not directed:
            continue
        start = next(iter(directed))
        ring, w = [start], directed[start]
        while w != start and w in directed and len(ring) <= len(directed):
            ring.append(w)
            w = directed[w]
        if w != start or len(ring) != len(directed) or len(ring) < 3:
            continue
        keep = [f for i, f in enumerate(fcs) if i not in set(around)]
        # the new face may not repeat an edge a neighbour already has
        # running the same way (a vertex inside a thin sliver)
        used = {(f[k], f[(k + 1) % len(f)]) for f in keep
                for k in range(len(f))}
        if any((ring[k], ring[(k + 1) % len(ring)]) in used
               for k in range(len(ring))):
            continue
        fcs = keep + [ring]
    pts, fcs, _ = compact(pts, fcs)
    return pts, fcs, []


def poke(points, faces, face_index, at=None):
    """A new vertex inside face *face_index* (at its centre, or *at*),
    the face replaced by a fan of triangles to it — Blender's Poke, a
    way to add a vertex anywhere on a face. Returns ``(points, faces,
    new_index)``."""
    pts, fcs = _copy(points, faces)
    face = fcs[face_index]
    new = len(pts)
    pts.append(_round(at if at is not None else face_centre(pts, face)))
    n = len(face)
    fan = [[face[k], face[(k + 1) % n], new] for k in range(n)]
    fcs[face_index:face_index + 1] = fan
    return pts, fcs, new


# ------------------------------------------- the node Edit Mode opens

#: wrappers Edit Mode looks through to find the polyhedron inside —
#: what converting an Object or a coloured part leaves round it
TRANSPARENT = frozenset({"color", "translate", "rotate", "scale", "mirror",
                         "multmatrix", "union", "component"})
#: a part placed per iteration cannot be one mesh
_LOOPS = frozenset({"for_loop", "while_loop", "pattern", "intersection_for"})


def find_editable(node):
    """The polyhedron Edit Mode edits for *node*: itself, or the only
    solid inside a chain of single-child wrappers (an Object, a colour,
    a move) — or None, and the node needs converting first."""
    probe = node
    while probe is not None:
        if probe.type == "polyhedron":
            return probe
        kids = [c for c in probe.children
                if c.type not in ("assign", "variables")]
        if probe.type not in TRANSPARENT or len(kids) != 1:
            return None
        probe = kids[0]
    return None


def convertible(node):
    """None when *node* can become an editable mesh, else why not."""
    if node is None or node.parent is None:
        return "select a solid first"
    if node.type == "reference":
        return ("an instance places its Object — open the Object "
                "itself to edit its vertices")
    probe = node.parent
    while probe is not None:
        if probe.type in _LOOPS:
            return ("inside a loop it is a different solid every "
                    "iteration — convert the loop instead")
        probe = probe.parent
    return None


def convert(model, node, fn=None):
    """Blender's Convert to Mesh: *node* replaced by ONE polyhedron of
    its preview surface — or, for an Object or a Group, its contents,
    so the part keeps its name, placement and colour. A single colour
    inside survives as a colour node round the polyhedron. Returns
    ``(polyhedron, None)`` or ``(None, reason)``. One structure change:
    one undo step."""
    from . import bake, mesh
    from .model import CadNode
    found = find_editable(node)
    if found is not None:
        return found, None
    why = convertible(node)
    if why:
        return None, why
    env = bake._codegen_env(node)
    if node.type in ("component", "union"):
        parent = node
        items = [c for c in node.children if c.visible
                 and c.type not in ("assign", "variables")]
        index = min((c.index() for c in items), default=len(node.children))
        env = dict(env)
        for c in node.children:
            if c.type == "assign":
                mesh._apply_assign(c, env)
    else:
        parent, items, index = node.parent, [node], node.index()
    tris, colours = [], set()
    for item in items:
        for tri, colour in mesh.tessellate_colored(item, env, fn=fn):
            tris.append(tri)
            colours.add(colour)
    if not tris:
        return None, "it has no 3D surface to edit (a 2D shape, or hidden)"
    points, faces = triangles_to_mesh(tris)
    if len(points) > MAX_POINTS:
        return None, (f"{len(points)} vertices is too many to edit by "
                      f"hand (the limit is {MAX_POINTS}) — Decimate it "
                      "first")
    why = check(points, faces)
    if why:
        return None, ("its surface is not one closed solid (" + why
                      + ") — Remesh it first")
    name = node.name if parent is node.parent else f"{node.name} mesh"
    poly = CadNode("polyhedron", name, dict(points=points, faces=faces))
    top = poly
    if len(colours) == 1 and None not in colours:
        colour = next(iter(colours))
        params = dict(color=colour[0], alpha=colour[1])
        if len(colour) > 2:
            params["material"] = colour[2]
        top = CadNode("color", model.unique_name("color"), params)
        top.add(poly)
    for item in items:
        parent.remove(item)
    parent.add(top, min(index, len(parent.children)))
    model.structure_changed.emit()
    return poly, None


def frame(node, stop=None):
    """4x4 matrix taking *node*'s coordinates to the view's frame
    (*stop* = the Object the Object tab isolates, else the document)."""
    from . import bake, mesh
    return mesh.ancestor_matrix(node, bake._codegen_env(node), stop=stop)


def apply(matrix, p):
    m = matrix
    return (m[0][0] * p[0] + m[0][1] * p[1] + m[0][2] * p[2] + m[0][3],
            m[1][0] * p[0] + m[1][1] * p[1] + m[1][2] * p[2] + m[1][3],
            m[2][0] * p[0] + m[2][1] * p[1] + m[2][2] * p[2] + m[2][3])


def linear_inverse(matrix):
    """Inverse of the matrix's 3x3 linear part (a world move -> a local
    move), or None when it is singular (a scale of zero)."""
    a, b, c = matrix[0][:3], matrix[1][:3], matrix[2][:3]
    det = (a[0] * (b[1] * c[2] - b[2] * c[1])
           - a[1] * (b[0] * c[2] - b[2] * c[0])
           + a[2] * (b[0] * c[1] - b[1] * c[0]))
    if abs(det) < 1e-12:
        return None
    inv = [[(b[1] * c[2] - b[2] * c[1]) / det,
            (a[2] * c[1] - a[1] * c[2]) / det,
            (a[1] * b[2] - a[2] * b[1]) / det],
           [(b[2] * c[0] - b[0] * c[2]) / det,
            (a[0] * c[2] - a[2] * c[0]) / det,
            (a[2] * b[0] - a[0] * b[2]) / det],
           [(b[0] * c[1] - b[1] * c[0]) / det,
            (a[1] * c[0] - a[0] * c[1]) / det,
            (a[0] * b[1] - a[1] * b[0]) / det]]
    return inv


def local_delta(inverse, delta):
    """*delta* (a world move) in the node's own frame."""
    if inverse is None:
        return tuple(delta)
    return tuple(inverse[r][0] * delta[0] + inverse[r][1] * delta[1]
                 + inverse[r][2] * delta[2] for r in range(3))
