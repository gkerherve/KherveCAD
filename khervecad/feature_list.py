"""The History view as a FEATURE LIST (2026-11-10, the user: "we have
two modes, tree and history ... you believe they are the same but no").

History used to be the structure redrawn: a part made by clicking read

    Sketch on Top Plane ▸ Boss-Extrude 1 · Cut sketch ▸ Cut-Extrude 1 ·
    Combine-Subtract 1 · Regions 1 · Body-Rotate 1 ...

in the order the nodes NEST — the cut made last stood second, because
its Difference wraps the base. SolidWorks' FeatureManager is one row a
feature, in the order they were MADE, each with its sketch under it:

    Boss-Extrude 1 ▸ Sketch 1
    Boss-Extrude 2 ▸ Sketch 2
    Cut-Extrude 1  ▸ Sketch 3

So, Qt-free:

- `is_plumbing` — nodes that only carry a feature and get no row: the
  sketch Group round its extrude, the Difference a cut put round the
  part, the turn that lays a revolve's axis in its sketch, the frame a
  nested cut is carried into;
- `flatten` / `ordered` — the feature nodes under some nodes, plumbing
  looked through, in the order they were made;
- `stamp` — that order is a number on each feature node
  (``params["feature_order"]``), given once, the first time the model
  is seen with the node in it (MainWindow._model_edited). A file from
  before, or a program imported from .scad, has none: its features are
  numbered as they stand in the tree, which is what History showed;
- `roll_back_to` / `rolled` — SolidWorks' rollback bar on that list:
  every feature made after the one named is off (``suppress.ROLLED``),
  wherever it stands in the tree.

The Structure view is untouched: it stays the program's own shape.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

ORDER = "feature_order"
EXTRUDES = ("linear_extrude", "rotate_extrude")
#: never features: scope, variables, code
_SCOPE = {"root", "variables", "assign", "masters", "scad_use"}


def _is_2d(node):
    from .model import SHAPE_2D
    return node.category == SHAPE_2D


def is_sketch_group(node):
    from . import face_sketch
    return node.type == "union" and bool(node.params.get(face_sketch.KEY))


def _flat(node):
    """Sketch content: a 2D shape, or a Regions nothing extrudes yet."""
    return _is_2d(node) or node.type == "regions"


def _tool(node):
    """What a feature's Difference cuts with: its sketch, a Hole Wizard
    feature, or one of them carried into the part's frame."""
    if is_sketch_group(node) or node.params.get("hole_wizard"):
        return True
    return node.type == "multmatrix" and bool(node.children) and \
        all(_tool(c) for c in node.children)


def is_plumbing(node):
    """Carries a feature, is not one: no row in History."""
    if is_sketch_group(node):
        return any(not _flat(c) for c in node.children)
    if node.type == "difference":
        return len(node.children) >= 2 and \
            all(_tool(c) for c in node.children[1:])
    if node.type in ("rotate", "translate", "for_loop") and \
            node.parent is not None:
        # a Sketch Pattern's turn / move (and its Direction 2 loop):
        # the inside of the pattern, not a feature (2026-11-11, the user:
        # "body rotate should go inside repeat — we should not see it")
        from . import sketch_pattern
        p = node.parent
        if p.type == "for_loop" and \
                isinstance(p.params.get(sketch_pattern.KEY), dict):
            return True
        if node.type != "for_loop" and p.type == "for_loop" and \
                p.parent is not None and isinstance(
                    p.parent.params.get(sketch_pattern.KEY), dict):
            return True
    if node.type == "rotate":
        return (node.name or "").endswith("(about the sketch's Y axis)")
    if node.type == "multmatrix":
        return (node.name or "").endswith("(to the part's frame)")
    return False


def flatten(nodes):
    """*nodes* with the plumbing looked through, in tree order."""
    out = []
    for n in nodes:
        if is_plumbing(n):
            out.extend(flatten(n.children))
        else:
            out.append(n)
    return out


def ordered(nodes):
    """`flatten`, in the order the features were made. A node with no
    number keeps its place after the one before it."""
    flat = flatten(nodes)
    keyed, last = [], 0.0
    for i, n in enumerate(flat):
        k = n.params.get(ORDER)
        if isinstance(k, (int, float)) and not isinstance(k, bool):
            last = float(k)
        else:
            last = last + 1e-6            # just after its neighbour
        keyed.append((last, i, n))
    keyed.sort(key=lambda t: (t[0], t[1]))
    return [n for _k, _i, n in keyed]


def _numbered(node):
    """Does *node* take a place in the order? Features do; sketch shapes,
    scope and plumbing do not."""
    return node.type not in _SCOPE and not _is_2d(node) and \
        node.type != "regions" and not is_plumbing(node) and \
        node.parent is not None


def stamp(model):
    """Number the features that have no number yet (tree order among
    themselves, after every one numbered before). True when any was."""
    fresh, top = [], 0
    for n in model.root.walk():
        k = n.params.get(ORDER)
        if isinstance(k, int) and not isinstance(k, bool):
            top = max(top, k)
        elif _numbered(n):
            fresh.append(n)
    for n in fresh:
        top += 1
        n.params[ORDER] = top
    return bool(fresh)


def sketch_of(feature):
    """(the node standing for the feature's sketch, its shapes) — the
    sketch Group when it has one, else its Regions, else (None, the
    extrude's own 2D shapes). The part's outline kept in a sketch and a
    Regions node are not shapes the user drew."""
    from . import face_sketch, sketch_section
    shapes, regions = [], None
    for c in feature.children:
        if c.type == "regions":
            regions = regions or c
            shapes += [k for k in c.children if _is_2d(k)]
        elif _is_2d(c):
            shapes.append(c)
    shapes = [s for s in shapes if not sketch_section.is_section(s)]
    group = face_sketch.group_of(feature)
    if group is not None and not is_plumbing(group):
        group = None
    return (group or regions), shapes


def features(model, scope=None):
    """Every feature of the scope in the order made (folders opened)."""
    def walk(nodes):
        out = []
        for n in ordered(nodes):
            if n.type in ("union", "variables") and not \
                    n.params.get("hole_wizard") and not is_sketch_group(n):
                out.extend(walk(n.children))
            elif n.type not in _SCOPE:
                out.append(n)
        return out
    root = scope if scope is not None else model.root
    return walk(root.children)


def rolled(node):
    from . import suppress
    return bool(node.params.get(suppress.ROLLED))


def roll_back_to(model, node, scope=None):
    """The rollback bar under *node* in the feature list: every feature
    made after it is off, wherever it stands in the tree. Returns how
    many were rolled back."""
    from . import suppress
    suppress.roll_forward(model, quiet=True)
    listed = features(model, scope)
    at = None
    for i, f in enumerate(listed):
        if f is node or node in f.walk() or \
                sketch_of(f)[0] is node:
            at = i
    if at is None:
        model.structure_changed.emit()
        return 0
    later = listed[at + 1:]
    for f in later:
        f.params[suppress.ROLLED] = True
    model.structure_changed.emit()
    return len(later)


def describe(model, scope=None):
    """The History list for an assistant: the features in the order
    made, each with its sketch's shapes."""
    from . import suppress
    out = []
    for i, f in enumerate(features(model, scope), 1):
        holder, shapes = sketch_of(f) if f.type in EXTRUDES else (None, [])
        row = dict(step=i, id=f.id, type=f.type, name=f.name)
        if f.type in EXTRUDES:
            from . import extrude_panel
            row["cut"] = bool(extrude_panel.is_cut(f))
        if holder is not None:
            row["sketch_id"] = holder.id
        if shapes:
            row["sketch"] = [dict(id=s.id, type=s.type, name=s.name)
                             for s in shapes]
        if suppress.is_off(f):
            row["off"] = "suppressed" if f.params.get(suppress.KEY) \
                else "rolled back"
        out.append(row)
    return out
