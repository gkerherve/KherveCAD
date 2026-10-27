"""Sketch constraints and driven dimensions (Qt-free), 2026-10-21.

The user pointed at SolidCraft (solidcraft.io, an open-source Rust CAD)
and asked for its constraint work in KherveCAD. This is our own
implementation of the same ideas, not a port: a damped Gauss-Newton
solver with degree-of-freedom feedback over the 2D shapes that are
already in the tree.

A constraint lives on the CONTAINER that holds the shapes (the document
root, an Object, a Group, an extrude...) as ``params["constraints"]``:
rows ``{"kind": ..., "refs": [...], "value": ...}``. A ref is
``"<child index>.<entity>"`` relative to that container — child indices
survive undo restores, where node ids are fresh — and the entities are

- line:    ``p1``, ``p2`` (ends), ``l`` (the line itself)
- rect:    ``v0`` .. ``v3`` (corners, counter-clockwise from the lower
           left), ``e0`` .. ``e3`` (edges: bottom, right, top, left),
           ``c`` (centre)
- circle:  ``c`` (centre), ``o`` (the circle itself)
- polygon: ``v<i>`` (vertices), ``e<i>`` (edge from v<i> to v<i+1>)

The unknowns are the shapes' own numeric params (line x1..y2, rect x y
width height, circle x y radius, polygon points); a param holding an
expression is a given, never moved. Solving writes the params back, so
the program stays plain OpenSCAD — constraints only decide the numbers.

Constraints (SolidCraft's list, plus point-on-curve and the dimensions
as constraints): coincident, horizontal, vertical, parallel,
perpendicular, tangent, equal, concentric, collinear, midpoint,
symmetric, fix, point_on; dimensions distance, hdistance, vdistance,
length, point_line (distance), radius, diameter, angle. A dimension's
value may be an expression of the document's variables ("w / 2").

`refresh` re-solves every constrained container after an edit, the
edited shape weighted heavily so the REST follows it (drag a line's end
and the parallel line turns with it). A constraint that cannot be met
together with the others is refused when added (`add` raises
`Conflict`) and the sketch is left as it was.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

try:
    import numpy as np
except ImportError:                     # pragma: no cover
    np = None

KEY = "constraints"
SHAPES = ("line", "rect", "circle", "polygon")
TOL = 1e-6
MAX_ITER = 60

#: kind -> (label, what to pick, takes a value)
KINDS = {
    "coincident": ("Coincident", ["point", "point"], False),
    "horizontal": ("Horizontal", ["line"], False),
    "vertical": ("Vertical", ["line"], False),
    # a side at 45° (or 135°) to the horizontal (2026-10-21, the user:
    # a 45° polygon side was marked H — there was no such relation)
    "diagonal": ("45°", ["line"], False),
    "parallel": ("Parallel", ["line", "line"], False),
    "perpendicular": ("Perpendicular", ["line", "line"], False),
    "tangent": ("Tangent", ["curve", "circle"], False),
    "equal": ("Equal", ["curve", "curve"], False),
    "concentric": ("Concentric", ["circle", "circle"], False),
    "collinear": ("Collinear", ["line", "line"], False),
    "midpoint": ("Midpoint", ["point", "line"], False),
    "symmetric": ("Symmetric", ["point", "point", "line"], False),
    "fix": ("Fix", ["point"], False),
    "point_on": ("Point on curve", ["point", "curve"], False),
    # a point kept on an edge of the PART under the sketch (the face or
    # the section outline): the row carries the edge, ``edge`` [ax, ay,
    # bx, by] in the sketch's frame (2026-10-27, the user's rectangle
    # drawn up to a face's edge came off it at the first dimension)
    "on_edge": ("On model edge", ["point"], False),
    "distance": ("Distance", ["point", "point"], True),
    "hdistance": ("Horizontal distance", ["point", "point"], True),
    "vdistance": ("Vertical distance", ["point", "point"], True),
    "length": ("Length", ["line"], True),
    "point_line": ("Point to line distance", ["point", "line"], True),
    "radius": ("Radius", ["circle"], True),
    "diameter": ("Diameter", ["circle"], True),
    "angle": ("Angle", ["line", "line"], True),
}
#: H and V also take two points (SolidCraft's two-point alignment)
TWO_POINT = ("horizontal", "vertical")


class Conflict(ValueError):
    """A constraint that cannot hold together with the others."""


# ------------------------------------------------------------ variables
def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _vars(node, slot=False):
    """(param path, value) of a shape's free numbers. A path is a key,
    or (key, row, col) for polygon points. A line's width is free only
    when a row sizes its round end (*slot*): every plain line would
    otherwise count one more freedom."""
    p = node.params
    keys = {"line": ("x1", "y1", "x2", "y2") + (("width",) if slot
                                                 else ()),
            "rect": ("x", "y", "width", "height"),
            "circle": ("x", "y", "radius")}.get(node.type)
    out = []
    if keys:
        out = [(k, float(p.get(k, 0.0))) for k in keys if _num(p.get(k))]
    elif node.type == "polygon":
        for i, pt in enumerate(p.get("points") or []):
            for j in (0, 1):
                if len(pt) > j and _num(pt[j]):
                    out.append((("points", i, j), float(pt[j])))
    return out


def _get(node, path):
    if isinstance(path, tuple):
        return node.params[path[0]][path[1]][path[2]]
    return node.params.get(path, 0.0)


def _set(node, path, value):
    value = round(float(value), 6)
    if isinstance(path, tuple):
        node.params[path[0]][path[1]][path[2]] = value
    else:
        node.params[path] = value


def _f(node, key, vals, default=0.0):
    """A param's current value: the solver's trial value, else the
    node's own number (an expression counts as 0 — it is never free)."""
    k = (node.id, key)
    if k in vals:
        return vals[k]
    v = node.params.get(key, default)
    return float(v) if _num(v) else default


# ------------------------------------------------------------- entities
def entity(container, ref):
    """(node, entity name) for a ref, or raise KeyError."""
    idx, _, name = str(ref).partition(".")
    node = container.children[int(idx)]
    if node.type not in SHAPES:
        raise KeyError(ref)
    return node, name


def kind_of(node, name):
    """'point', 'line' or 'circle' for an entity name."""
    if name in ("p1", "p2", "c") or name.startswith("v"):
        return "point"
    if name in ("l",) or name.startswith("e"):
        return "line"
    if name in ("o", "a1", "a2"):
        return "circle"
    raise KeyError(name)


def _point(node, name, vals):
    t = node.type
    if t == "line":
        if name == "p1":
            return _f(node, "x1", vals), _f(node, "y1", vals)
        if name == "p2":
            return _f(node, "x2", vals), _f(node, "y2", vals)
    if t == "circle" and name == "c":
        return _f(node, "x", vals), _f(node, "y", vals)
    if t == "rect":
        x, y = _f(node, "x", vals), _f(node, "y", vals)
        w, h = _f(node, "width", vals), _f(node, "height", vals)
        if name == "c":
            return x + w / 2, y + h / 2
        i = int(name[1:]) % 4
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)][i]
    if t == "polygon" and name.startswith("v"):
        pts = node.params.get("points") or []
        i = int(name[1:]) % len(pts)
        ox, oy = _f(node, "x", vals), _f(node, "y", vals)
        px = vals.get((node.id, ("points", i, 0)), pts[i][0])
        py = vals.get((node.id, ("points", i, 1)), pts[i][1])
        return ox + float(px), oy + float(py)
    raise KeyError(name)


def _line(node, name, vals):
    if node.type == "line" and name == "l":
        return _point(node, "p1", vals), _point(node, "p2", vals)
    if node.type in ("rect", "polygon") and name.startswith("e"):
        i = int(name[1:])
        n = 4 if node.type == "rect" else len(node.params["points"])
        return (_point(node, "v%d" % (i % n), vals),
                _point(node, "v%d" % ((i + 1) % n), vals))
    raise KeyError(name)


def _circle(node, name, vals):
    if node.type == "circle":
        return _point(node, "c", vals), _f(node, "radius", vals, 1.0)
    if node.type == "line" and name in ("a1", "a2"):
        # a slot's round end: centred on that end, half its width
        # (SolidWorks' slot R from the end's centre, 2026-10-25)
        return (_point(node, "p" + name[1], vals),
                _f(node, "width", vals, 1.0) / 2.0)
    raise KeyError(name)


def _geom(container, ref, vals):
    node, name = entity(container, ref)
    k = kind_of(node, name)
    if k == "point":
        return k, _point(node, name, vals)
    if k == "line":
        return k, _line(node, name, vals)
    return k, _circle(node, name, vals)


# ------------------------------------------------------------ residuals
def _sub(a, b):
    return a[0] - b[0], a[1] - b[1]


def _len(v):
    return math.hypot(v[0], v[1])


def _unit(v):
    n = _len(v) or 1e-12
    return v[0] / n, v[1] / n


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _pl_dist(p, line):
    """Signed distance of p from the infinite line."""
    a, b = line
    return _cross(_unit(_sub(b, a)), _sub(p, a))


def value_of(row, env=None):
    from . import expr
    v = row.get("value")
    if _num(v):
        return float(v)
    return float(expr.resolve(v, env or {}, 0.0))


def residuals(container, row, vals, env=None):
    """The equations one row asks to be zero."""
    kind = row["kind"]
    g = [_geom(container, r, vals) for r in row["refs"]]
    kinds = [k for k, _ in g]
    geo = [x for _, x in g]
    if kind == "coincident":
        d = _sub(geo[0], geo[1])
        return [d[0], d[1]]
    if kind in TWO_POINT:
        if kinds == ["line"]:
            a, b = geo[0]
        else:
            a, b = geo[0], geo[1]
        return [b[1] - a[1]] if kind == "horizontal" else [b[0] - a[0]]
    if kind == "diagonal":
        a, b = geo[0]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy) or 1.0
        return [(dx * dx - dy * dy) / length]
    if kind in ("parallel", "perpendicular", "angle", "collinear"):
        u = _unit(_sub(geo[0][1], geo[0][0]))
        v = _unit(_sub(geo[1][1], geo[1][0]))
        if kind == "parallel":
            return [_cross(u, v)]
        if kind == "perpendicular":
            return [_dot(u, v)]
        if kind == "collinear":
            return [_cross(u, v), _pl_dist(geo[1][0], geo[0])]
        t = math.radians(value_of(row, env))
        # the turn from u to v is t (or its supplement, whichever is
        # nearer, so a reversed line does not flip the sketch)
        ang = math.atan2(_cross(u, v), _dot(u, v))
        alts = [t, -t, math.pi - t, t - math.pi]
        best = min(alts, key=lambda a: abs(math.remainder(ang - a,
                                                          2 * math.pi)))
        return [math.sin(ang - best)]
    if kind == "tangent":
        (c, r) = geo[1]
        if kinds[0] == "line":
            return [abs(_pl_dist(c, geo[0])) - r]
        c0, r0 = geo[0]
        d = _len(_sub(c, c0))
        # outside or inside, whichever is nearer now
        return [min(d - (r0 + r), d - abs(r0 - r), key=abs)]
    if kind == "equal":
        def size(k, x):
            return _len(_sub(x[1], x[0])) if k == "line" else x[1]
        return [size(kinds[0], geo[0]) - size(kinds[1], geo[1])]
    if kind == "concentric":
        d = _sub(geo[0][0], geo[1][0])
        return [d[0], d[1]]
    if kind == "midpoint":
        a, b = geo[1]
        return [geo[0][0] - (a[0] + b[0]) / 2, geo[0][1] - (a[1] + b[1]) / 2]
    if kind == "symmetric":
        p, q, line = geo
        a, b = line
        u = _unit(_sub(b, a))
        m = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        return [_dot(_sub(q, p), u), _pl_dist(m, line)]
    if kind == "fix":
        x, y = row["at"]
        return [geo[0][0] - x, geo[0][1] - y]
    if kind == "on_edge":
        ax, ay, bx, by = (float(v) for v in row["edge"][:4])
        return [_pl_dist(geo[0], ((ax, ay), (bx, by)))]
    if kind == "point_on":
        if kinds[1] == "line":
            return [_pl_dist(geo[0], geo[1])]
        c, r = geo[1]
        return [_len(_sub(geo[0], c)) - r]
    v = value_of(row, env)
    if kind == "distance":
        return [_len(_sub(geo[1], geo[0])) - v]
    if kind == "hdistance":
        return [abs(geo[1][0] - geo[0][0]) - v]
    if kind == "vdistance":
        return [abs(geo[1][1] - geo[0][1]) - v]
    if kind == "length":
        return [_len(_sub(geo[0][1], geo[0][0])) - v]
    if kind == "point_line":
        return [abs(_pl_dist(geo[0], geo[1])) - v]
    if kind == "radius":
        return [geo[0][1] - v]
    if kind == "diameter":
        return [2 * geo[0][1] - v]
    raise KeyError(kind)


# ----------------------------------------------------------------- rows
def rows(container):
    return list(container.params.get(KEY) or [])


def check_row(container, row):
    """Raise ValueError when a row names nothing it can use."""
    kind = row.get("kind")
    if kind not in KINDS:
        raise ValueError("Unknown constraint %r." % kind)
    _label, picks, takes = KINDS[kind]
    refs = list(row.get("refs") or [])
    if kind in TWO_POINT and len(refs) == 2:
        picks = ["point", "point"]
    if len(refs) != len(picks):
        raise ValueError("%s needs %d picks." % (KINDS[kind][0], len(picks)))
    for ref, want in zip(refs, picks):
        try:
            node, name = entity(container, ref)
            got = kind_of(node, name)
            {"point": _point, "line": _line,
             "circle": _circle}[got](node, name, {})   # it exists
        except (KeyError, ValueError, IndexError):
            raise ValueError("No sketch entity %r here." % ref)
        ok = (want == got or (want == "curve" and got in ("line", "circle")))
        if not ok:
            raise ValueError("%s: %r is a %s, not a %s."
                             % (KINDS[kind][0], ref, got, want))
    if takes and row.get("value") is None:
        raise ValueError("%s needs a value." % KINDS[kind][0])


def _nodes_of(container, rs):
    seen = {}
    for row in rs:
        for ref in row["refs"]:
            node, _ = entity(container, ref)
            seen[node.id] = node
    return list(seen.values())


# --------------------------------------------------------------- solver
def solve(container, rs=None, prefer=(), env=None, write=True, dof=True,
          held=()):
    """Solve *container*'s rows (or *rs*). *prefer* = node ids that
    should move as little as possible (the shape just edited). Returns a
    report: ok, residual, dof, redundant, moved. Writes the params when
    ``write`` and the solve succeeded."""
    if np is None:
        return dict(ok=False, error="numpy is needed for constraints")
    rs = rows(container) if rs is None else rs
    nodes = _nodes_of(container, rs)
    slots = set()
    for row in rs:
        for ref in row.get("refs", ()):
            idx, _, name = ref.partition(".")
            if name in ("a1", "a2"):
                slots.add(idx)
    keys, x0, w = [], [], []
    for node in nodes:
        try:
            slot = str(container.children.index(node)) in slots
        except ValueError:
            slot = False
        for path, v in _vars(node, slot):
            keys.append((node.id, path))
            x0.append(v)
            # what the user just typed or dragged is HELD (it barely
            # moves: the rest follows it), the rest of an edited shape
            # moves less than the shapes not touched
            w.append(1e-6 if (node.id, path) in held else
                     0.05 if node.id in prefer else 1.0)
    x0 = np.array(x0, float)
    W = np.array(w, float)
    by_id = {n.id: n for n in nodes}

    def F(x):
        vals = dict(zip(keys, x))
        out = []
        for row in rs:
            out.extend(residuals(container, row, vals, env))
        return np.array(out, float)

    def jac(x, f0):
        J = np.zeros((len(f0), len(x)))
        for j in range(len(x)):
            h = 1e-6 * max(1.0, abs(x[j]))
            xp = x.copy()
            xp[j] += h
            J[:, j] = (F(xp) - f0) / h
        return J

    x = x0.copy()
    f = F(x) if len(x) else np.zeros(0)
    if not len(x):
        return dict(ok=bool(np.all(np.abs(f) < TOL)), residual=0.0,
                    dof=0, redundant=0, moved=[])
    lam = 1e-9
    for _ in range(MAX_ITER):
        err = float(np.max(np.abs(f))) if len(f) else 0.0
        if err < TOL:
            break
        J = jac(x, f)
        JW = J * W                       # columns scaled by the weights
        A = JW @ J.T + lam * np.eye(len(f))
        # minimum-(weighted)-norm step: the sketch moves as little as
        # it can — what the user drew stays where it was
        step = -JW.T @ np.linalg.solve(A, f)
        xn = x + step
        fn = F(xn)
        if np.max(np.abs(fn)) < err:
            x, f = xn, fn
            lam = max(lam * 0.3, 1e-12)
        else:
            lam *= 10
            if lam > 1e6:
                break
    err = float(np.max(np.abs(f))) if len(f) else 0.0
    if dof:
        J = jac(x, f)
        rank = int(np.linalg.matrix_rank(J, tol=1e-7)) if J.size else 0
    else:
        rank = len(x)
    if err < 1e-4 and _collapsed(container, rs, dict(zip(keys, x))):
        err = float("inf")      # met only by shrinking a shape to nothing
    report = dict(ok=err < 1e-4, residual=err, dof=len(x) - rank,
                  redundant=len(f) - rank, moved=[])
    if report["ok"] and write:
        for (nid, path), v, v0 in zip(keys, x, x0):
            if abs(v - v0) > 1e-9:
                _set(by_id[nid], path, v)
                if nid not in report["moved"]:
                    report["moved"].append(nid)
    report["nodes"] = by_id
    return report


def _collapsed(container, rs, vals):
    """Does a line, edge or circle the rows use have (almost) no size?"""
    for row in rs:
        for ref in row["refs"]:
            node, name = entity(container, ref)
            k = kind_of(node, name)
            if k == "line":
                a, b = _line(node, name, vals)
                if _len(_sub(b, a)) < 1e-3:
                    return True
            elif k == "circle" and _circle(node, name, vals)[1] < 1e-3:
                return True
    return False


def status_text(report):
    if not report.get("ok"):
        return "Over-constrained: the constraints cannot all hold."
    dof = report["dof"]
    if dof == 0:
        return "Fully constrained."
    return "%d degree%s of freedom left." % (dof, "" if dof == 1 else "s")


# ---------------------------------------------------------- model glue
def containers(model):
    return [n for n in model.root.walk() if n.params.get(KEY)]


def _env(model):
    try:
        from .anchors import doc_env
        return doc_env(model)
    except Exception:                    # pragma: no cover
        return {}


def ref_of(container, node, name):
    return "%d.%s" % (container.children.index(node), name)


def add(model, container, kind, refs, value=None, edge=None):
    """Add one constraint and solve. Raises ValueError / Conflict; the
    sketch is untouched then. Returns the report."""
    row = {"kind": kind, "refs": list(refs)}
    if kind == "on_edge":
        if edge is None or len(edge) < 4:
            raise ValueError("On model edge needs the edge.")
        row["edge"] = [round(float(v), 6) for v in edge[:4]]
    if value is not None:
        row["value"] = value
    if kind == "fix":
        node, name = entity(container, refs[0])
        row["at"] = list(_point(node, name, {}))
    elif KINDS.get(kind, (0, 0, False))[2] and value is None:
        row["value"] = round(measure(container, kind, refs), 4)
    check_row(container, row)
    rs = rows(container) + [row]
    env = _env(model)
    report = solve(container, rs, env=env, write=False)
    if not report["ok"]:
        raise Conflict("%s cannot hold with the sketch's other "
                       "constraints." % KINDS[kind][0])
    report = solve(container, rs, env=env)
    container.params[KEY] = rs
    _remember(_nodes_of(container, rs))
    model._last_sketch = container          # its marks show (the 2D view)
    for nid in report["moved"]:
        model.node_changed.emit(report["nodes"][nid])
    model.node_changed.emit(container)
    return report


def measure(container, kind, refs):
    """What a dimension measures now (the value it takes by default)."""
    g = [_geom(container, r, {}) for r in refs]
    geo = [x for _, x in g]
    if kind == "distance":
        return _len(_sub(geo[1], geo[0]))
    if kind == "hdistance":
        return abs(geo[1][0] - geo[0][0])
    if kind == "vdistance":
        return abs(geo[1][1] - geo[0][1])
    if kind == "length":
        return _len(_sub(geo[0][1], geo[0][0]))
    if kind == "point_line":
        return abs(_pl_dist(geo[0], geo[1]))
    if kind == "radius":
        return geo[0][1]
    if kind == "diameter":
        return 2 * geo[0][1]
    if kind == "angle":
        u = _unit(_sub(geo[0][1], geo[0][0]))
        v = _unit(_sub(geo[1][1], geo[1][0]))
        return math.degrees(abs(math.atan2(_cross(u, v), _dot(u, v))))
    raise KeyError(kind)


def remove(model, container, index):
    rs = rows(container)
    del rs[index]
    if rs:
        container.params[KEY] = rs
    else:
        container.params.pop(KEY, None)
    model.node_changed.emit(container)


def set_value(model, container, index, value):
    rs = rows(container)
    old = rs[index].get("value")
    rs[index]["value"] = value
    report = solve(container, rs, env=_env(model), write=False)
    if not report["ok"]:
        rs[index]["value"] = old
        raise Conflict("That value cannot hold with the other "
                       "constraints.")
    container.params[KEY] = rs
    report = solve(container, rs, env=_env(model))
    _remember(_nodes_of(container, rs))
    model._last_sketch = container
    for nid in report["moved"]:
        model.node_changed.emit(report["nodes"][nid])
    model.node_changed.emit(container)
    return report


_REFRESHING = False
#: {(node id, param path): value} as the last solve left them — a value
#: that differs now is what the user changed, and is held
_SOLVED = {}


def _changed_vars(nodes):
    held = set()
    for node in nodes:
        for path, v in _vars(node):
            old = _SOLVED.get((node.id, path))
            if old is not None and abs(old - v) > 1e-9:
                held.add((node.id, path))
    return held


def _remember(nodes):
    for node in nodes:
        for path, v in _vars(node):
            _SOLVED[(node.id, path)] = v


def refresh(model, edited=()):
    """Re-solve every constrained container; the *edited* node ids
    weigh most, so the rest follows them. Rows that no longer name
    anything (a shape deleted) are dropped. Emits node_changed for what
    moved. Returns the reports by container id."""
    global _REFRESHING
    if _REFRESHING or np is None:
        return {}
    _REFRESHING = True
    out = {}
    try:
        env = _env(model)
        for cont in containers(model):
            good = []
            for row in rows(cont):
                try:
                    check_row(cont, row)
                    good.append(row)
                except ValueError:
                    pass
            if len(good) != len(rows(cont)):
                if good:
                    cont.params[KEY] = good
                else:
                    cont.params.pop(KEY, None)
                    continue
            nodes = _nodes_of(cont, good)
            report = solve(cont, good, prefer=set(edited), env=env,
                           dof=False, held=_changed_vars(nodes))
            _remember(nodes)
            out[cont.id] = report
            for nid in report["moved"]:
                model.node_changed.emit(report["nodes"][nid])
    finally:
        _REFRESHING = False
    return out


def describe(container, row):
    label = KINDS[row["kind"]][0]
    text = "%s (%s)" % (label, ", ".join(row["refs"]))
    if "value" in row:
        unit = "°" if row["kind"] == "angle" else ""
        text += " = %s%s" % (row["value"], unit)
    return text


# ------------------------------------------------------ auto constrain
def auto_constrain(model, container, tol_deg=3.0, tol_mm=0.5):
    """Beyond SolidCraft: add the constraints the drawing already looks
    like it has — nearly horizontal / vertical lines, line ends that
    meet. Returns how many were added."""
    have = {(r["kind"], tuple(r["refs"])) for r in rows(container)}
    added = 0
    pts = []
    for i, node in enumerate(container.children):
        if node.type != "line":
            continue
        (a, b) = _line(node, "l", {})
        d = _sub(b, a)
        ang = math.degrees(math.atan2(abs(d[1]), abs(d[0])))
        for kind, ok in (("horizontal", ang < tol_deg),
                         ("vertical", ang > 90 - tol_deg)):
            key = (kind, ("%d.l" % i,))
            if ok and key not in have:
                try:
                    add(model, container, kind, ["%d.l" % i])
                    added += 1
                except ValueError:
                    pass
        pts += [("%d.p1" % i, a), ("%d.p2" % i, b)]
    for j, (ra, pa) in enumerate(pts):
        for rb, pb in pts[j + 1:]:
            if ra.split(".")[0] == rb.split(".")[0]:
                continue
            if _len(_sub(pa, pb)) < tol_mm and \
                    ("coincident", (ra, rb)) not in have:
                try:
                    add(model, container, "coincident", [ra, rb])
                    added += 1
                except ValueError:
                    pass
    return added


# ------------------------------------------------- in the OpenSCAD code
HELPER = """\
module kcad_constraints(rows = "") { }"""


VARIABLE = "kcad_constraints"


def code(container):
    """The container's rows as one OpenSCAD ASSIGNMENT carrying them as
    JSON text. Not a module call: a call is a CHILD, and first in a
    difference() it became the (empty) body — the whole part rendered
    empty in OpenSCAD (2026-10-21). An assignment is no geometry."""
    import json
    text = json.dumps(rows(container), separators=(",", ":"))
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    return '%s = "%s";' % (VARIABLE, text)


def _b_constraints(parser, positional, named):
    """Parsed back as a marker child; `take` moves its rows onto the
    container (scadparse._fold_container / parse_scad for the root)."""
    import json
    from .model import CadNode
    text = str(named.get("rows", positional[0] if positional else "[]"))
    node = CadNode("union", "Group", {})
    try:
        node._kcad_constraints = json.loads(text)
    except ValueError:
        parser.warn("kcad_constraints: unreadable rows dropped")
        node._kcad_constraints = []
    return node


BUILDERS = {"kcad_constraints": _b_constraints}


def take(container):
    """Move parsed constraint rows onto *container*: the assignment
    `kcad_constraints = "…";` (or an older file's kcad_constraints(…)
    marker call)."""
    import json
    for child in list(container.children):
        found = getattr(child, "_kcad_constraints", None)
        if found is None and child.type == "assign" and \
                str(child.params.get("variable", "")) == VARIABLE:
            text = child.params.get("value", "[]")
            text = str(text).strip()
            if text.startswith('"') and text.endswith('"'):
                text = text[1:-1].encode().decode("unicode_escape")
            try:
                found = json.loads(text)
            except ValueError:
                found = []
        if found is not None:
            container.remove(child)
            if found:
                container.params[KEY] = found


def uses(root):
    """No helper module is needed any more (an assignment needs none)."""
    return False


# ------------------------------------------- keeping refs right on edits
def _rewrite(container, fn):
    """Apply *fn(ref) -> new ref | None* to every row; a row with a ref
    mapped to None is dropped (what it named is gone)."""
    rs = rows(container)
    if not rs:
        return
    out = []
    for row in rs:
        new = [fn(r) for r in row["refs"]]
        if all(n is not None for n in new):
            row = dict(row)
            row["refs"] = new
            out.append(row)
    if out:
        container.params[KEY] = out
    else:
        container.params.pop(KEY, None)


def points_replaced(node, index, count):
    """Vertex *index* of polygon *node* became *count* points (a sketch
    fillet's arc): renumber the vertices and edges after it, drop rows
    on the vertex that went (its edges into and out of it stay)."""
    parent = node.parent
    if parent is None:
        return
    me = str(parent.children.index(node))
    k = count - 1

    def fn(ref):
        idx, _, name = ref.partition(".")
        if idx != me or not name[:1] in "ve" or not name[1:].isdigit():
            return None if (idx == me and name == "c") else ref
        i = int(name[1:])
        if name[0] == "v":
            if i == index:
                return None
            return ref if i < index else f"{idx}.v{i + k}"
        # edge i runs v_i -> v_{i+1}: the one leaving the corner moves
        return ref if i < index else f"{idx}.e{i + k}"
    _rewrite(parent, fn)


def plan_wrap(parent, nodes, index):
    """Before *nodes* of *parent* are wrapped into one new child at
    *index*: (rows going into the wrapper, rows staying), re-indexed."""
    rs = rows(parent)
    if not rs:
        return None
    old = [parent.children.index(n) for n in nodes]
    inner = {o: k for k, o in enumerate(old)}
    gone = sorted(old)

    def outer(i):
        # children before *index* keep theirs, the wrapper takes *index*,
        # later ones move down by the wrapped ones before them, then +1
        if i < index:
            return i
        return i - sum(1 for g in gone if g < i) + 1
    moved, kept = [], []
    for row in rs:
        idxs = [int(r.partition(".")[0]) for r in row["refs"]]
        names = [r.partition(".")[2] for r in row["refs"]]
        if all(i in inner for i in idxs):
            moved.append(dict(row, refs=["%d.%s" % (inner[i], n)
                                         for i, n in zip(idxs, names)]))
        elif not any(i in inner for i in idxs):
            kept.append(dict(row, refs=["%d.%s" % (outer(i), n)
                                        for i, n in zip(idxs, names)]))
    return moved, kept


def apply_wrap(parent, wrapper, plan):
    if not plan:
        return
    moved, kept = plan
    if moved:
        wrapper.params[KEY] = moved
    if kept:
        parent.params[KEY] = kept
    else:
        parent.params.pop(KEY, None)


def child_inserted(parent, at):
    """A node was inserted at *at* among *parent*'s children."""
    def fn(ref):
        idx, _, name = ref.partition(".")
        i = int(idx)
        return f"{i + 1}.{name}" if i >= at else ref
    _rewrite(parent, fn)


def child_removed(parent, at):
    """Child *at* of *parent* was removed: its rows go, later indices
    move down."""
    def fn(ref):
        idx, _, name = ref.partition(".")
        i = int(idx)
        if i == at:
            return None
        return f"{i - 1}.{name}" if i > at else ref
    _rewrite(parent, fn)


def drop_between(parent, a, b, kinds=("coincident",)):
    """Remove rows of *kinds* joining nodes *a* and *b*."""
    ia, ib = (str(parent.children.index(n)) for n in (a, b))
    rs = [r for r in rows(parent) if not (
        r["kind"] in kinds and
        {x.split(".")[0] for x in r["refs"]} == {ia, ib})]
    if rs:
        parent.params[KEY] = rs
    else:
        parent.params.pop(KEY, None)


# ------------------------------------------- scale on first dimension
#: QSettings key: the first dimension of a sketch scales all of it
SCALE_FIRST = "sketch/scale_on_first_dimension"
DIMENSION_KINDS = ("distance", "hdistance", "vdistance", "length",
                   "point_line", "radius", "diameter")


def scale_first_enabled():
    try:
        from PyQt5.QtCore import QSettings
        return QSettings("Kherve", "KherveCAD").value(
            SCALE_FIRST, True, type=bool)
    except Exception:                       # pragma: no cover
        return True


def has_dimension(container):
    return any(r["kind"] in DIMENSION_KINDS for r in rows(container))


def scale_shapes(model, container, factor):
    """Scale every 2D shape of *container* about the origin by *factor*
    (SolidWorks' "scale sketch on first dimension"): positions, sizes
    and line widths stay in proportion; constraints still hold."""
    if factor <= 0 or abs(factor - 1.0) < 1e-12:
        return
    keys = {"line": ("x1", "y1", "x2", "y2"),
            "rect": ("x", "y", "width", "height"),
            "circle": ("x", "y", "radius"),
            "polygon": ("x", "y")}
    for node in container.children:
        if node.type not in keys:
            continue
        p = node.params
        for k in keys[node.type]:
            if _num(p.get(k)):
                p[k] = round(float(p[k]) * factor, 6)
        if node.type == "polygon":
            p["points"] = [[round(float(v) * factor, 6) if _num(v) else v
                            for v in pt] for pt in p.get("points") or []]
            if p.get("corners"):
                p["corners"] = [[r[0], round(float(r[1]) * factor, 6)]
                                + list(r[2:]) for r in p["corners"]]
        model.node_changed.emit(node)
    _remember(_nodes_of(container, rows(container)))


def add_dimension(model, container, kind, refs, value):
    """A sketch dimension: the FIRST one of a sketch scales the whole
    sketch to it (when the option is on and it is a length), later ones
    drive their own shapes. Returns (report, scaled)."""
    scaled = False
    # a sketch tied to the part (a point fixed on it or on its edge) is
    # never rescaled: SolidWorks scales only a free-floating sketch
    anchored = any(r["kind"] in ("fix", "on_edge")
                   for r in rows(container))
    if kind in DIMENSION_KINDS and not has_dimension(container) and \
            not anchored and scale_first_enabled():
        try:
            now = measure(container, kind, refs)
            target = float(value) if _num(value) else value_of(
                {"value": value}, _env(model))
        except (KeyError, ValueError, TypeError):
            now, target = 0.0, 0.0
        if now > 1e-9 and target > 0:
            scale_shapes(model, container, target / now)
            scaled = True
    return add(model, container, kind, refs, value), scaled
