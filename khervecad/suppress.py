"""Suppress and roll back features (Qt-free), 2026-10-21 — SolidWorks'
Suppress and rollback bar, from the user's "do them all" of the
SolidWorks gap list.

The tree is already the feature history, so:

- **Suppress** a node: ``params["suppressed"] = True``. The feature is
  switched off without being deleted — a wrapper (move, extrude, fillet,
  colour...) passes its children through untouched, a ``difference``
  keeps only its body (the cuts are switched off), a leaf draws nothing.
- **Roll back** a container: ``params["rollback"] = k`` — its children
  from index k on are switched off the same way, as if the history
  stopped there. Roll forward removes it.

Codegen writes a switched-off node as real OpenSCAD:
``kcad_off("<its own statement>", "all"|"first"|"none"[, rolled = true])
{ children }`` — the helper renders the children it keeps, and the
importer rebuilds the original node from the quoted statement, so a
suppressed feature survives export and import.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

KEY = "suppressed"
ROLLBACK = "rollback"
#: nodes that cannot be switched off (they are scope, not features)
NEVER = {"root", "variables", "assign", "masters", "scad_use",
         "component", "reference", "if_else", "scad_raw"}

HELPER = """\
module kcad_off(statement = "", keep = "all", rolled = false) {
    if (keep == "all") children();
    else if (keep == "first" && $children > 0) children(0);
}"""


def rolled_back(node) -> bool:
    parent = node.parent
    if parent is None:
        return False
    r = parent.params.get(ROLLBACK)
    if not isinstance(r, int) or isinstance(r, bool):
        return False
    try:
        return parent.children.index(node) >= r
    except ValueError:
        return False


#: on a wrapper applied AFTER the feature the history is rolled back to
#: (a fillet, a move round it): off until rolled forward
ROLLED = "rolled_off"
#: what groups features rather than being one applied to them
_GROUPS = {"root", "union", "difference", "intersection", "component",
           "hull", "minkowski"}
#: wrappers that belong to a sketch's own feature, never rolled away
_OWN = {"linear_extrude", "rotate_extrude", "sweep", "section_loft",
        "regions", "offset", "color"}


def is_off(node) -> bool:
    if node.type in NEVER:
        return False
    return bool(node.params.get(KEY) or node.params.get(ROLLED)) \
        or rolled_back(node)


def keep_of(node) -> str:
    if rolled_back(node) and not node.params.get(KEY):
        # past the rollback bar: not built yet, so nothing of it shows.
        # (A rolled-back Group still passed its contents through — a
        # cut's sketch Group went on cutting.)
        return "none"
    if node.type == "difference":
        return "first"
    if node.type in ("linear_extrude", "rotate_extrude", "sweep",
                     "section_loft") or node.params.get("hole_wizard") \
            or node.params.get("face_sketch"):
        # a feature that makes its own solid: off, nothing of it shows
        # (a switched-off extrude passed its flat sketch on, into the
        # Difference it cut)
        return "none"
    return "all" if node.is_container() else "none"


def kept_children(node):
    keep = keep_of(node)
    if keep == "all":
        return list(node.children)
    if keep == "first":
        return node.children[:1]
    return []


def uses(root) -> bool:
    return any(is_off(n) for n in root.walk())


def emit(node, lines, indent, spans):
    """Write a switched-off node (called from CadNode.emit)."""
    pad = "    " * indent
    stmt = node._statement().replace("\\", "\\\\").replace('"', '\\"')
    stmt = stmt.replace("\n", " ")
    rolled = ", rolled = true" if (rolled_back(node)
                                   and not node.params.get(KEY)) else ""
    from .model import name_tag
    tag = name_tag(node.name)
    note = f"  // {tag}" if tag else ""
    head = f'{pad}kcad_off("{stmt}", "{keep_of(node)}"{rolled})'
    if not node.children:
        lines.append((head + ";" + note, node))
        return
    lines.append((head + " {" + note, node))
    for child in node.children:
        child.emit(lines, indent + 1, spans)
    lines.append((pad + "}", node))


# ----------------------------------------------------------------- edits
def set_suppressed(model, nodes, on=True):
    for n in nodes:
        if n.type in NEVER:
            continue
        if on:
            n.params[KEY] = True
        else:
            n.params.pop(KEY, None)
        model.node_changed.emit(n)


def roll_back_to(model, node):
    """Roll the history back to *node*: everything built after it is
    off. Among its siblings that is what follows it — and, as features
    made by clicking NEST (each cut a Difference round the part so far,
    a fillet round that), also what follows at every level above, and
    each wrapper applied on top. It used to stop at the siblings: in a
    part made with Extruded Cut there were none, and rolling back did
    nothing (2026-11-10)."""
    if node.parent is None:
        return
    roll_forward(model, quiet=True)
    child = node
    while child.parent is not None:
        parent = child.parent
        index = parent.children.index(child)
        if index + 1 < len(parent.children):
            parent.params[ROLLBACK] = index + 1
        if parent.type in ("root", "component"):
            break                         # the scope: its history ends here
        if parent.type not in _GROUPS and parent.type not in _OWN and \
                parent.type not in NEVER:
            parent.params[ROLLED] = True  # applied on top: off as well
        child = parent
    model.structure_changed.emit()


def any_rollback(root) -> bool:
    return any(isinstance(n.params.get(ROLLBACK), int) or
               n.params.get(ROLLED) for n in root.walk())


def roll_forward(model, container=None, quiet=False):
    """Remove the rollback of *container* (every one when None)."""
    nodes = [container] if container is not None else list(
        model.root.walk())
    for n in nodes:
        n.params.pop(ROLLBACK, None)
        n.params.pop(ROLLED, None)
    if not quiet:
        model.structure_changed.emit()


def state(root):
    return dict(
        suppressed=[dict(id=n.id, name=n.name) for n in root.walk()
                    if n.params.get(KEY)],
        rolled=[dict(id=n.id, name=n.name) for n in root.walk()
                if n.params.get(ROLLED)],
        rollbacks=[dict(id=n.id, name=n.name, at=n.params[ROLLBACK],
                        of=len(n.children)) for n in root.walk()
                   if isinstance(n.params.get(ROLLBACK), int)])


# --------------------------------------------------------------- import
def _b_off(parser, positional, named):
    from .model import CadNode
    node = CadNode("union", "Group", {})
    node._kcad_off = (str(named.get("statement", positional[0] if
                                     positional else "")),
                      _flag(parser, named.get("rolled", False)))
    return node


BUILDERS = {"kcad_off": _b_off}


def fold(node):
    """Turn a parsed kcad_off wrapper back into the node it stood for,
    suppressed (or rolled back). None when *node* is not one."""
    info = getattr(node, "_kcad_off", None)
    if info is None:
        return None
    stmt, rolled = info
    from .scadparse import Parser
    stmt = stmt.strip().lstrip("*")
    try:
        # no pruning: the empty "translate() { }" stands for the node
        sub = Parser(stmt + (" { }" if node.children else ";"),
                     None).parse_program()
    except Exception:
        sub = None
    real = None
    if sub is not None and sub.children:
        real = sub.children[0]
        # an imported "translate() { }" may fold into nothing: take the
        # deepest single node
        sub.remove(real)
    if real is None:
        return None
    real.name = node.name if node.name != "Group" else real.name
    for child in list(node.children):
        node.remove(child)
        real.add(child)
    if rolled:
        real._rolled_back = True
    else:
        real.params[KEY] = True
    return real


def restore_rollbacks(root):
    """After an import: a run of rolled-back children becomes their
    parent's rollback index again."""
    for n in root.walk():
        idx = [i for i, c in enumerate(n.children)
               if getattr(c, "_rolled_back", False)]
        if idx:
            n.params[ROLLBACK] = min(idx)


def _flag(parser, value, default=False):
    from .scadparse import flag
    return flag(parser, value, default)
