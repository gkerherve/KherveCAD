"""What a sketch is LOCKED to, and what in it is still free (2026-11-10,
the user, on a boss whose length grew both ways: "I do not know what it
is locked to ... why is he using this centre").

It was locked to no centre: nothing held it sideways. Its front edge lay
on the part's edge and its sizes were dimensioned, but no dimension
reached the part's corner, so the whole outline could still slide along
that edge — and a solver that moves everything as little as it can grows
a free line equally at both ends. SolidWorks says so with a "(-)" before
an under defined sketch; here nothing did.

`describe(model, container)` reads a sketch's rows:

- ``ties``  — what holds it to the part: points on the part's edges,
  points pinned to a corner / the middle of an edge / a face's centre,
  dimensions to a reference copied from the part or another sketch, the
  origin, a plain Fix;
- ``free``  — how it can still move, from the solver's null space: the
  whole sketch sliding left / right or up / down, else the shapes that
  can still change;
- ``dof``, ``defined``.

`text` is the sentence the History row's tooltip and the feature's
Properties show; `marker` the "(-)" of an under defined sketch.

Qt-free. Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import sketch_constraints as sc

#: a null-space vector's parts within this of each other move together
SAME = 1e-3
X_KEYS = ("x", "x1", "x2")
Y_KEYS = ("y", "y1", "y2")


def container_of(node):
    """The node holding the sketch rows of feature / sketch *node*."""
    if node is None:
        return None
    if node.params.get(sc.KEY):
        return node
    for n in node.walk():
        if n.params.get(sc.KEY):
            return n
    return None


def _is_reference(node):
    p = node.params
    return bool(p.get("ref_source") or p.get("ref_world") or
                p.get("ref_face")) or str(node.name).startswith("Reference")


def _plural(n, one, many=None):
    return "%d %s" % (n, one if n == 1 else (many or one + "s"))


def ties(container):
    """[sentence] what holds the sketch to the part."""
    rows = sc.rows(container)
    out = []
    on_edge = [r for r in rows if r.get("kind") == "on_edge"]
    if on_edge:
        out.append("%s on the part's edge" % _plural(len(on_edge), "point"))
    pins = {"corner": 0, "middle of an edge": 0, "face centre": 0,
            "edge": 0, "fixed": 0}
    ref_ids = set()
    for i, n in enumerate(container.children):
        if n.type in sc.SHAPES and _is_reference(n):
            ref_ids.add(str(i))
    used_refs = set()
    for r in rows:
        refs = [str(x).partition(".")[0] for x in r.get("refs", ())]
        if r.get("kind") == "fix":
            if refs and refs[0] in ref_ids:
                continue                   # the reference's own pin
            m = r.get("model")
            key = {True: "corner", "mid": "middle of an edge",
                   "centre": "face centre", "on": "edge"}.get(m, "fixed")
            pins[key] += 1
        elif any(x in ref_ids for x in refs) and \
                not all(x in ref_ids for x in refs):
            used_refs.update(x for x in refs if x in ref_ids)
    if pins["corner"]:
        out.append("%s pinned to a corner of the part"
                   % _plural(pins["corner"], "point"))
    if pins["middle of an edge"]:
        out.append("%s pinned to the middle of an edge"
                   % _plural(pins["middle of an edge"], "point"))
    if pins["face centre"]:
        out.append("%s pinned to the centre of the face"
                   % _plural(pins["face centre"], "point"))
    if pins["edge"]:
        out.append("%s riding on an edge of the part"
                   % _plural(pins["edge"], "point"))
    if pins["fixed"]:
        out.append("%s fixed in place" % _plural(pins["fixed"], "point"))
    for x in sorted(used_refs, key=int):
        node = container.children[int(x)]
        what = {"Reference point": "a point of the part",
                "Reference edge": "an edge of the part",
                "Reference face": "a face of the part",
                "Reference circle": "a circle of another sketch"}.get(
            str(node.name).rstrip(" 0123456789"), "a reference")
        if node.params.get("ref_source"):
            what = "%s of another sketch" % (
                "a point" if node.type == "circle" else "a line")
        out.append("dimensioned or related to %s" % what)
    return out


def _axis(key):
    if key in X_KEYS or (isinstance(key, tuple) and key[2] == 0):
        return 0
    if key in Y_KEYS or (isinstance(key, tuple) and key[2] == 1):
        return 1
    return None


def free_moves(container, vectors):
    """[sentence] how the sketch can still move, from the solver's null
    space *vectors* ({(node id, param): amount} each): the whole sketch
    sliding along X or Y when that slide lies in the space, then the
    shapes whatever is left can still change."""
    import numpy as np
    if not vectors:
        return []
    keys = list(vectors[0])
    by_id = {n.id: n for n in container.children}
    N = np.array([[v.get(k, 0.0) for k in keys] for v in vectors], float)
    own = [k for k in keys if k[0] in by_id
           and not _is_reference(by_id[k[0]])]
    several = len({k[0] for k in own}) > 1
    out, slides = [], []
    for axis, words in ((0, "left / right (along the sketch's X)"),
                        (1, "up / down (along the sketch's Y)")):
        t = np.array([1.0 if k in own and _axis(k[1]) == axis else 0.0
                      for k in keys])
        norm = float(np.linalg.norm(t))
        if norm < 1e-9:
            continue
        t = t / norm
        if float(np.linalg.norm(N.T @ (N @ t) - t)) < 1e-3:
            slides.append(t)
            out.append("%s can slide %s" % (
                "the whole sketch" if several else "it", words))
    rest = N.copy()
    for t in slides:
        rest = rest - np.outer(rest @ t, t)
    if rest.size:
        sv = np.linalg.svd(rest, compute_uv=False)
        left = int((sv > 1e-3).sum())
    else:
        left = 0
    if left:
        _u, _s, vt = np.linalg.svd(rest)
        basis = vt[:left]
        moving = []
        for col, k in enumerate(keys):
            if float(np.abs(basis[:, col]).max()) > 1e-2 and k[0] in by_id:
                node = by_id[k[0]]
                if not _is_reference(node) and node.name not in moving:
                    moving.append(node.name)
        if moving:
            shown = ", ".join(moving[:4]) + (" …" if len(moving) > 4 else "")
            out.append("%s can still change (%s of freedom)"
                       % (shown, _plural(left, "degree")))
    return out


def describe(model, container):
    """{defined, dof, ties, free} of the sketch in *container*."""
    out = dict(defined=False, dof=None, ties=[], free=[])
    if container is None:
        return out
    out["ties"] = ties(container)
    try:
        report = sc.solve(container, env=sc._env(model), write=False)
    except Exception:
        return out
    if not report.get("ok"):
        return out
    out["dof"] = int(report.get("dof") or 0)
    out["defined"] = out["dof"] == 0
    try:
        out["free"] = free_moves(container, report.get("free") or [])
    except Exception:
        out["free"] = []
    return out


_CACHE = {}


def of(model, node):
    """`describe` for the sketch of feature / sketch *node*, or None when
    it has no relations at all; remembered while the sketch is unchanged."""
    cont = container_of(node)
    if cont is None:
        return None
    import json
    try:
        key = json.dumps([sc.rows(cont),
                          [(c.type, c.name, c.params) for c in cont.children]],
                         sort_keys=True, default=str)
    except (TypeError, ValueError):
        key = None
    hit = _CACHE.get(cont.id)
    if key is not None and hit is not None and hit[0] == key:
        return hit[1]
    info = describe(model, cont)
    if key is not None:
        if len(_CACHE) > 400:
            _CACHE.clear()
        _CACHE[cont.id] = (key, info)
    return info


def marker(info):
    """SolidWorks' prefix of an under defined sketch."""
    return "(-) " if info.get("dof") else ""


def text(info):
    """The sentences for a tooltip / the Properties."""
    held = "; ".join(info["ties"]) if info["ties"] else \
        "nothing of the part — it is only where it was drawn"
    if info.get("dof") is None:
        return "Held by: %s." % held
    if info["defined"]:
        return "Fully defined. Held by: %s." % held
    free = "; ".join(info["free"]) or "something in it can still move"
    return ("Under defined (%s of freedom): %s. Held by: %s. Add a Smart "
            "Dimension or relation from it to the part (a corner, an edge, "
            "the origin) to lock it."
            % (_plural(info["dof"], "degree"), free, held))
