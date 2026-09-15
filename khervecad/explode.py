"""Exploded views — every part of an assembly pushed away from its
centre, so you can see how it goes together.

A display, never an edit: the object tree is untouched. Each part (an
Object, an instance, a coloured group...) is tessellated on its own —
with the document's variables and its own colours, and with the exact
OpenSCAD mesh the preview already holds for it — then moved along the
line from the assembly's centre to the part's centre:

- **Radial** — outwards in every direction (the classic exploded view);
- **X / Y / Z** — along one axis only (a stack of plates, a row of
  parts), keeping the other two coordinates.

Which parts come apart (`plan`):

- with a part **selected**, the nearest assembly that holds it — the
  part itself when it holds two or more parts, else the Group or
  Object it sits in, so selecting one leaf of a hinge takes the hinge
  apart;
- with nothing selected, the parts of the scope (the document, or the
  Object being edited) — and a lone Group, Object or colour at the top
  is looked into, since a library part or Make Object wraps a whole
  assembly in one. Before, such a document had "one part" and the
  view silently did nothing.

Only containers that place and colour their children (`STRUCTURAL`)
are looked into or pulled apart: a boolean, a loop or an extrusion is
one solid, and pulling a bore out of its plate would show nothing
true. Everything else stays where it is, and the selection tint moves
with its part (`highlight`).

*amount* scales the move: 1.0 pushes each part as far again as it
already sits from the centre. View ▸ Exploded View shows it in the 3D
view; `showing()` switches it on for as long as a picture is taken
(File ▸ Export PNG, the Printables bundle's exploded stills), and a
picture shows the whole assembly whatever is selected.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from contextlib import contextmanager

MODES = ("Radial", "X", "Y", "Z")
AMOUNTS = (0.5, 1.0, 1.5, 2.0, 3.0)
DEFAULT_AMOUNT, DEFAULT_MODE = 1.0, "Radial"
SKIP = ("assign", "variables", "masters")
#: containers that only place and colour what they hold — the ones an
#: exploded view may look into or pull apart
STRUCTURAL = frozenset({"root", "union", "component", "color", "reference",
                        "translate", "rotate", "scale", "mirror"})


class Plan:
    """What an exploded view shows. *group* is the node whose parts come
    apart (None when nothing can), *path* the ids from the scope down to
    the node that holds those parts, *pieces* each part with its move,
    *items* the coloured triangles to draw, *note* a status-bar line."""

    def __init__(self, group=None, path=(), pieces=(), items=(), note=""):
        self.group = group
        self.path = list(path)
        self.pieces = list(pieces)
        self.items = list(items)
        self.note = note


def _index(scope):
    """{name: node} from the document root, as the tessellator resolves
    an instance's Object."""
    top = scope
    while top.parent is not None:
        top = top.parent
    index = {}
    for node in top.walk():
        index.setdefault(node.name, node)
    return index


def _target(node, index):
    """The node whose children *node* holds — an instance holds its
    Object's; None for an instance of anything but an Object."""
    if node.type != "reference":
        return node
    target = index.get(str(node.params.get("ref", "")).strip())
    return target if target is not None and target.type == "component" \
        else None


def _openable(node, index):
    return node.type in STRUCTURAL and _target(node, index) is not None


def _kids(node, index):
    """The visible parts directly inside *node*."""
    holder = _target(node, index)
    out = []
    for child in (holder.children if holder is not None else ()):
        if child.type == "variables":
            out += [g for g in child.children
                    if g.type not in SKIP and g.visible]
        elif child.type not in SKIP and child.visible:
            out.append(child)
    return out


def _enter(node, env, colour, matrix, index):
    """Step into *node*: its placement and colour apply to what it holds
    (read in the scope it sits in, as the tessellator reads them), then
    its variables join the environment."""
    from . import mesh
    matrix = mesh.mat_mul(matrix, mesh.node_matrix(node, env))
    if node.type == "color":
        colour = (str(node.params.get("color", "#4a90d9")),
                  mesh.rv(node.params.get("alpha", 1.0), env, 1.0))
        material = str(node.params.get("material") or "Default")
        if material != "Default":
            colour += (material,)
    elif node.type in ("union", "component", "reference"):
        col = str(node.params.get("color", "")).strip()
        if col:
            colour = (col, mesh.rv(node.params.get("alpha", 1.0), env, 1.0))
    env = dict(env)
    holder = _target(node, index)
    for child in (holder.children if holder is not None else ()):
        if child.type == "assign":
            mesh._apply_assign(child, env)
        elif child.type == "variables":
            for grand in child.children:
                if grand.type == "assign":
                    mesh._apply_assign(grand, env)
    return env, colour, matrix


def _chain(scope, node):
    """[scope, ..., node], or None when *node* is not inside *scope*."""
    path, probe = [], node
    while probe is not None and probe is not scope:
        path.append(probe)
        probe = probe.parent
    return None if probe is None else [scope] + path[::-1]


def _candidates(scope, selected, index):
    """(group, path to the parts' holder, parts) to try, nearest first:
    up from each selected node, then the scope itself. A group is only
    reached through containers that place and colour."""
    chains = [c for c in (_chain(scope, n) for n in selected) if c]
    chains.append([scope])
    seen = set()
    for chain in chains:
        for i in range(len(chain) - 1, -1, -1):
            group = chain[i]
            if group.id in seen:
                continue
            seen.add(group.id)
            if not all(_openable(n, index) for n in chain[:i + 1]):
                continue
            path = chain[:i + 1]
            kids = _kids(group, index)
            # a lone Group / Object / colour holding the assembly
            while len(kids) == 1 and _openable(kids[0], index):
                path.append(kids[0])
                kids = _kids(kids[0], index)
            yield group, path, kids


def _piece_meshes(scope, path, kids, env, fn, index):
    """[(part, [(triangle, colour)])] in the scope's frame, each part
    tessellated alone (cached and exact meshes kept) and placed by the
    containers above it."""
    from . import mesh
    frame_env, colour, matrix = env, None, mesh.mat_identity()
    for node in path:
        frame_env, colour, matrix = _enter(node, frame_env, colour, matrix,
                                           index)
    mesh._set_fn(fn)
    mesh._set_refs(scope)
    out = []
    try:
        for kid in kids:
            marked = mesh._tess(kid, dict(frame_env), colour, frozenset(),
                                False)
            if marked:
                placed = mesh._transform_colored(matrix, marked)
                out.append((kid, [(t, c) for t, c, _s in placed]))
    finally:
        mesh._set_fn(None)
        mesh._clear_refs()
    return out


def _rest(scope, group, env, fn):
    """Everything in *scope* but *group*, where it stands."""
    from . import mesh
    saved = group.visible
    group.visible = False
    try:
        return mesh.tessellate_colored(scope, env, fn)
    finally:
        group.visible = saved


def plan(scope, env=None, fn=None, amount=DEFAULT_AMOUNT,
         mode=DEFAULT_MODE, selected=()) -> Plan:
    """The exploded view of *scope* (the document root, or the Object
    being edited), pulling apart the assembly *selected* belongs to."""
    from . import mesh
    env = dict(env or {})
    index = _index(scope)
    for group, path, kids in _candidates(scope, list(selected), index):
        if len(kids) < 2:
            continue
        pieces = _piece_meshes(scope, path, kids, env, fn, index)
        if len(pieces) < 2:
            continue
        moves = offsets([_box([t for t, _c in items])
                         for _p, items in pieces], amount, mode)
        items = [] if group is scope else _rest(scope, group, env, fn)
        for (_part, tris), (dx, dy, dz) in zip(pieces, moves):
            items += [(tuple((v[0] + dx, v[1] + dy, v[2] + dz) for v in tri),
                       c) for tri, c in tris]
        holder = path[-1]
        name = "the assembly" if holder.type == "root" else holder.name
        return Plan(group, [n.id for n in path],
                    [(part, move) for (part, _i), move in zip(pieces, moves)],
                    items, f"the {len(pieces)} parts of {name}")
    return Plan(items=mesh.tessellate_colored(scope, env, fn),
                note="Nothing to pull apart — only one part is shown")


def highlight(scope, sel_ids, the_plan, fn=None) -> list:
    """World triangles of the selection in an exploded view: a moved
    part's tint moves with it (it was drawn where the part used to be),
    and selecting the assembly itself tints every part where it went."""
    from . import mesh
    by_id = {n.id: n for n in scope.walk()}
    moves = {part.id: move for part, move in the_plan.pieces}

    def shifted(ids, move):
        dx, dy, dz = move
        return [tuple((v[0] + dx, v[1] + dy, v[2] + dz) for v in tri)
                for tri in mesh.selected_world_tris(scope, ids, fn=fn)]
    out = []
    for nid in sel_ids:
        node = by_id.get(nid)
        if node is None:
            continue
        if nid in the_plan.path:
            for part, move in the_plan.pieces:
                out += shifted({part.id}, move)
            continue
        probe, move = node, None
        while probe is not None and move is None:
            move = moves.get(probe.id)
            probe = probe.parent
        out += shifted({nid}, move or (0.0, 0.0, 0.0))
    return out


def _box(tris):
    pts = [v for tri in tris for v in tri]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return lo, hi


def _centre(box):
    lo, hi = box
    return [(lo[i] + hi[i]) / 2.0 for i in range(3)]


def offsets(boxes, amount=DEFAULT_AMOUNT, mode=DEFAULT_MODE) -> list:
    """The move of each part (bounding boxes in, [dx, dy, dz] out):
    along centre-of-assembly -> centre-of-part, times *amount*, kept to
    one axis unless *mode* is Radial."""
    if not boxes:
        return []
    lo = [min(b[0][i] for b in boxes) for i in range(3)]
    hi = [max(b[1][i] for b in boxes) for i in range(3)]
    whole = [(lo[i] + hi[i]) / 2.0 for i in range(3)]
    axes = {"X": (0,), "Y": (1,), "Z": (2,)}.get(mode, (0, 1, 2))
    moves = []
    for box in boxes:
        c = _centre(box)
        moves.append([(c[i] - whole[i]) * float(amount) if i in axes else 0.0
                      for i in range(3)])
    return moves


def exploded_colored(root, env=None, fn=None, amount=DEFAULT_AMOUNT,
                     mode=DEFAULT_MODE, selected=()) -> list:
    """[(triangle, colour)] of *root* with the parts moved out — what
    the 3D view draws in an exploded view."""
    return plan(root, env, fn, amount, mode, selected).items


def part_count(root, env=None, fn=None) -> int:
    """How many parts an exploded view of *root* pulls apart (1 when it
    cannot, 0 when nothing is drawn)."""
    the_plan = plan(root, env, fn)
    return len(the_plan.pieces) or (1 if the_plan.items else 0)


@contextmanager
def showing(window, amount=DEFAULT_AMOUNT, mode=DEFAULT_MODE):
    """The 3D view exploded for the duration — a picture of it can be
    taken — and put back as it was afterwards. The picture shows the
    whole assembly, whatever happens to be selected."""
    before = dict(window.explode_state())
    whole = getattr(window, "_explode_whole", False)
    window._explode_whole = True
    window.set_explode(True, amount, mode)
    try:
        yield
    finally:
        window._explode_whole = whole
        window.set_explode(before["on"], before["amount"], before["mode"])
