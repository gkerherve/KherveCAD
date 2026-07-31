"""Attach / mate system — snap Objects together anchor-to-anchor.

A **mate** is a live record stored on the child Object's params:

    {"parent": name, "parent_anchor": name, "anchor": name,
     "offset": mm, "spin": deg}

Evaluating a mate computes the one rigid placement that puts the
child's anchor on the parent's anchor with the two directions
anti-aligned (face against face), then applies the extra ``offset``
along the mate axis and ``spin`` about it. The result is written into
the child's ordinary placement params (x/y/z/rx/ry/rz), so codegen,
preview and `.kcad` need nothing new — but the record stays live:
whenever the parent moves, ``refresh(model)`` re-solves every mate
(chains included, with a cycle guard), so attached parts follow.

No constraint solver: like BOSL2's ``attach()`` or Onshape's mate
connectors, the attachment tree is evaluated deterministically.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                             QDoubleSpinBox, QFormLayout, QHBoxLayout,
                             QLabel, QPushButton, QWidget)

from . import anchors

#: |value change| below this is "unchanged" — stops refresh loops.
_EPS = 1e-6


# ----------------------------------------------------------- rotations

def _rot_axis_angle(axis, angle):
    """Rodrigues: 3x3 rotation of *angle* radians about unit *axis*."""
    x, y, z = axis
    c, s = math.cos(angle), math.sin(angle)
    t = 1.0 - c
    return [[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c]]


def _rot_between(a, b):
    """Rotation taking unit vector *a* onto unit vector *b*."""
    dot = max(-1.0, min(1.0, sum(a[i] * b[i] for i in range(3))))
    if dot > 1.0 - 1e-9:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    if dot < -1.0 + 1e-9:
        # opposite: rotate pi about any axis perpendicular to a
        perp = [1.0, 0.0, 0.0] if abs(a[0]) < 0.9 else [0.0, 1.0, 0.0]
        axis = _norm(_cross(a, perp))
        return _rot_axis_angle(axis, math.pi)
    axis = _norm(_cross(a, b))
    return _rot_axis_angle(axis, math.acos(dot))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def _norm(v):
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return [c / length for c in v]


def _mat_mul3(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)]
            for i in range(3)]


def _mat_vec3(m, v):
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def _euler_zyx(m):
    """Angles (rx, ry, rz) in degrees with rotate([rx,ry,rz]) — i.e.
    Rz·Ry·Rx — reproducing the 3x3 matrix *m*."""
    sy = -m[2][0]
    sy = max(-1.0, min(1.0, sy))
    ry = math.asin(sy)
    if abs(sy) < 1.0 - 1e-9:
        rx = math.atan2(m[2][1], m[2][2])
        rz = math.atan2(m[1][0], m[0][0])
    else:                                       # gimbal: fold into rz
        rx = 0.0
        rz = math.atan2(-m[0][1], m[1][1])
    return (round(math.degrees(rx), 4), round(math.degrees(ry), 4),
            round(math.degrees(rz), 4))


# ------------------------------------------------------------ the mate

def mate_of(comp):
    """The part's mate record, or None."""
    mate = comp.params.get("mate")
    return dict(mate) if isinstance(mate, dict) and mate.get("parent") \
        else None


def definition_of(model, part):
    """The Object that defines *part*'s geometry (and carries its
    anchors): the part itself for a component, the referenced Object
    for an instance (Linked copy), None when dangling."""
    if part is not None and part.type == "reference":
        name = str(part.params.get("ref", "")).strip()
        for node in model.root.walk():
            if node.type == "component" and node.name == name:
                return node
        return None
    return part


#: node types that carry a placement + can be snapped around: Objects
#: and their instances (assembly), and groups (building a part).
_MATEABLE = ("component", "reference", "union")


def unwrap(node):
    """Look through a **colour wrapper** to the part inside.

    Colouring a part wraps it in a `color` node, and the part is then
    no longer a direct child of its container — so it dropped out of
    the assembly entirely: the Snap tool stopped seeing it ("needs at
    least two visible Objects") and no other part could mate to it.
    A colour carries no transform, so the part inside sits exactly
    where it did and is still the assembly part. Transform wrappers
    (a translate/rotate round a part) are deliberately *not* seen
    through: the mate would solve as if the wrapper were not there and
    place the part wrong."""
    while node is not None and node.type == "color" \
            and len(node.children) == 1:
        node = node.children[0]
    return node


def _scope_parts(container, types=_MATEABLE):
    """Mateable parts directly under *container*, colour wrappers seen
    through."""
    out = []
    for child in container.children:
        part = unwrap(child)
        if part is not None and part.type in types:
            out.append(part)
    return out


def _container_of(node):
    """The assembly scope a part belongs to: its parent, or what that
    parent is wrapped in (a colour is not a container of its own)."""
    container = node.parent
    while container is not None and container.type == "color" \
            and len(container.children) == 1:
        container = container.parent
    return container


def parts(model, scope=None):
    """The mateable parts at *scope*.

    ``scope=None`` — the **Main assembly**: top-level Objects plus
    instances of Objects (a hidden Object is a pure definition but
    stays mateable for backward compatibility).

    ``scope=<component>`` — the **groups inside that Object** (the
    Object tab: snap sub-parts together to build the part). Its direct
    ``union``/``component`` children, i.e. the "secondary" parts.
    """
    if scope is not None:
        return _scope_parts(scope, ("union", "component"))
    out = []
    for part in _scope_parts(model.root, ("component", "reference")):
        if part.type == "component" \
                or definition_of(model, part) is not None:
            out.append(part)
    return out


def _mate_siblings(node):
    """The parts a *node*'s mate may reference — the other mateable
    parts in the same container (the assembly root, or the Object being
    built), colour wrappers on either side seen through."""
    container = _container_of(node)
    if container is None:
        return []
    return [p for p in _scope_parts(container) if p is not node]


def find_anchor(definition, name, env=None, fn=None):
    for anchor in anchors.anchors_of(definition, env=env, fn=fn):
        if anchor["name"] == name:
            return anchor
    return None


def solve_mate(comp, parent, mate, env=None, fn=None,
               comp_def=None, parent_def=None):
    """The child placement (x, y, z, rx, ry, rz) that satisfies *mate*,
    or None when an anchor is missing. Anchors live on the parts'
    *definitions* (``comp_def`` / ``parent_def``, defaulting to the
    parts themselves); placements are the parts' own."""
    p_anchor = find_anchor(parent_def or parent,
                           mate.get("parent_anchor", ""), env, fn)
    c_anchor = find_anchor(comp_def or comp,
                           mate.get("anchor", ""), env, fn)
    if p_anchor is None or c_anchor is None:
        return None
    p_pos, p_dir = anchors.anchor_world(parent, p_anchor, env)
    p_dir = _norm(p_dir)
    target_dir = [-c for c in p_dir]              # face against face
    rot = _rot_between(_norm(list(c_anchor["dir"])), target_dir)
    spin = float(mate.get("spin", 0.0) or 0.0)
    if abs(spin) > 1e-12:
        rot = _mat_mul3(_rot_axis_angle(p_dir, math.radians(spin)), rot)
    offset = float(mate.get("offset", 0.0) or 0.0)
    anchor_target = [p_pos[i] + offset * p_dir[i] for i in range(3)]
    rotated = _mat_vec3(rot, list(c_anchor["pos"]))
    translation = [anchor_target[i] - rotated[i] for i in range(3)]
    rx, ry, rz = _euler_zyx(rot)
    return (round(translation[0], 4), round(translation[1], 4),
            round(translation[2], 4), rx, ry, rz)


def apply_mate(model, comp, env=None, fn=None) -> bool:
    """Solve the part's mate and write the placement. Returns True
    when any placement value actually changed. The mate's parent is
    looked up among the part's siblings, so an assembly Object mates
    to another Object and a group mates to a sibling group."""
    mate = mate_of(comp)
    if mate is None:
        return False
    parent = next((c for c in _mate_siblings(comp)
                   if c.name == mate["parent"]), None)
    if parent is None:
        return False
    placement = solve_mate(comp, parent, mate, env, fn,
                           definition_of(model, comp),
                           definition_of(model, parent))
    if placement is None:
        return False
    changed = False
    for key, value in zip(("x", "y", "z", "rx", "ry", "rz"), placement):
        from . import expr
        current = expr.resolve(comp.params.get(key, 0.0), None, 0.0)
        if abs(current - value) > _EPS:
            comp.params[key] = value
            changed = True
    return changed


_REFRESHING = False


def refresh(model) -> bool:
    """Re-solve every mate in dependency order (parents before their
    children, cycles broken). Emits node_changed for each moved
    Object. Returns True when anything moved."""
    global _REFRESHING
    if _REFRESHING:
        return False
    _REFRESHING = True
    try:
        env = anchors.doc_env(model)
        fn = model.effective_fn()
        # every node carrying a mate, at any depth (assembly Objects and
        # the groups inside an Object alike)
        mated = [n for n in model.root.walk() if mate_of(n)]
        moved = []
        solved = set()

        def solve(comp, stack):
            if comp.id in solved:
                return
            solved.add(comp.id)
            mate = mate_of(comp)
            if mate is not None and mate["parent"] not in stack:
                parent = next((c for c in _mate_siblings(comp)
                               if c.name == mate["parent"]), None)
                if parent is not None:
                    solve(parent, stack | {comp.name})
                if apply_mate(model, comp, env, fn):
                    moved.append(comp)
        for comp in mated:
            solve(comp, {comp.name})
        for comp in moved:
            model.node_changed.emit(comp)
        return bool(moved)
    finally:
        _REFRESHING = False


def attach(model, comp, parent_name, child_anchor, parent_anchor,
           offset=0.0, spin=0.0):
    """Create/replace the component's mate and solve it."""
    comp.params["mate"] = dict(parent=str(parent_name),
                               parent_anchor=str(parent_anchor),
                               anchor=str(child_anchor),
                               offset=float(offset), spin=float(spin))
    refresh(model)
    model.node_changed.emit(comp)


def detach(model, comp):
    if comp.params.pop("mate", None) is not None:
        model.node_changed.emit(comp)


# -------------------------------------------------------------- dialog

def _flip_spin(value):
    """*value* + a half turn, normalised into (-180, 180]."""
    v = float(value) + 180.0
    v = ((v + 180.0) % 360.0) - 180.0
    return 180.0 if v == -180.0 else v


class AttachDialog(QDialog):
    """Attach one Object to another: pick the two anchors, an offset
    along the mate axis and a spin about it. Editing an existing mate
    pre-fills; Detach removes it. Every change **previews live** in
    the viewers — OK keeps it, Cancel restores the original mate and
    placement."""

    def __init__(self, model, comp, parent=None):
        super().__init__(parent)
        self.model = model
        self.comp = comp
        self.setWindowTitle(f"Attach {comp.name}")
        env = anchors.doc_env(model)
        fn = model.effective_fn()
        mate = mate_of(comp) or {}

        # what to put back if the user cancels the live preview
        self._orig_mate = dict(mate) if mate else None
        self._orig_place = {k: comp.params.get(k)
                            for k in ("x", "y", "z", "rx", "ry", "rz")}

        form = QFormLayout(self)
        form.addRow(QLabel(
            "Snap this object onto another: the two anchors touch,\n"
            "faces against each other. Changes preview live —\n"
            "Cancel puts everything back."))
        self.parent_combo = QComboBox()
        # candidates are the part's own siblings — assembly Objects for
        # an Object, sibling groups for a group being built
        self.others = _mate_siblings(comp)
        for other in self.others:
            self.parent_combo.addItem(other.name)
        form.addRow("Attach to:", self.parent_combo)

        self.child_anchor = QComboBox()
        for anchor in anchors.anchors_of(
                definition_of(model, comp) or comp, env=env, fn=fn):
            self.child_anchor.addItem(
                f"{anchor['name']} ({anchor['kind']})", anchor["name"])
        form.addRow("This object's anchor:", self.child_anchor)

        self.parent_anchor = QComboBox()
        form.addRow("Target anchor:", self.parent_anchor)

        self.offset = QDoubleSpinBox()
        self.offset.setRange(-1e6, 1e6)
        self.offset.setDecimals(3)
        self.offset.setSuffix(" mm")
        form.addRow("Offset along axis:", self.offset)
        self.spin = QDoubleSpinBox()
        self.spin.setRange(-360.0, 360.0)
        self.spin.setDecimals(2)
        self.spin.setSuffix(" °")
        flip = QPushButton("Flip 180°")
        flip.setToolTip("Rotate the part half a turn about the mate "
                        "axis — the quick fix when it lands backwards")
        flip.clicked.connect(lambda: self.spin.setValue(
            _flip_spin(self.spin.value())))
        spin_row = QWidget()
        row = QHBoxLayout(spin_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.spin, 1)
        row.addWidget(flip)
        form.addRow("Spin about axis:", spin_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                   | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        if mate:
            detach_btn = QPushButton("Detach")
            detach_btn.clicked.connect(self._detach)
            buttons.addButton(detach_btn, QDialogButtonBox.ResetRole)
        form.addRow(buttons)

        self._env, self._fn = env, fn
        self.parent_combo.currentIndexChanged.connect(
            self._fill_parent_anchors)
        self._fill_parent_anchors()
        # pre-fill an existing mate
        if mate:
            i = self.parent_combo.findText(mate.get("parent", ""))
            if i >= 0:
                self.parent_combo.setCurrentIndex(i)
            i = self.child_anchor.findData(mate.get("anchor", ""))
            if i >= 0:
                self.child_anchor.setCurrentIndex(i)
            i = self.parent_anchor.findData(
                mate.get("parent_anchor", ""))
            if i >= 0:
                self.parent_anchor.setCurrentIndex(i)
            self.offset.setValue(float(mate.get("offset", 0.0)))
            self.spin.setValue(float(mate.get("spin", 0.0)))
        # live preview — connected after the pre-fill so opening the
        # dialog doesn't itself move anything
        self.parent_combo.currentIndexChanged.connect(self._preview)
        self.child_anchor.currentIndexChanged.connect(self._preview)
        self.parent_anchor.currentIndexChanged.connect(self._preview)
        self.offset.valueChanged.connect(self._preview)
        self.spin.valueChanged.connect(self._preview)

    def _preview(self, *_args):
        """Apply the current choices immediately so the viewers show
        the mate as it is being edited."""
        index = self.parent_combo.currentIndex()
        child = self.child_anchor.currentData()
        target = self.parent_anchor.currentData()
        if not (0 <= index < len(self.others)) or not child \
                or not target:
            return
        attach(self.model, self.comp, self.others[index].name,
               child, target, self.offset.value(), self.spin.value())

    def _restore(self):
        """Put the original mate and placement back (Cancel)."""
        if self._orig_mate is None:
            self.comp.params.pop("mate", None)
        else:
            self.comp.params["mate"] = dict(self._orig_mate)
        for key, value in self._orig_place.items():
            if value is None:
                self.comp.params.pop(key, None)
            else:
                self.comp.params[key] = value
        refresh(self.model)
        self.model.node_changed.emit(self.comp)

    def reject(self):
        self._restore()
        super().reject()

    def _fill_parent_anchors(self):
        self.parent_anchor.clear()
        index = self.parent_combo.currentIndex()
        if 0 <= index < len(self.others):
            target = self.others[index]
            definition = definition_of(self.model, target) or target
            for anchor in anchors.anchors_of(definition, env=self._env,
                                             fn=self._fn):
                self.parent_anchor.addItem(
                    f"{anchor['name']} ({anchor['kind']})",
                    anchor["name"])

    def _apply(self):
        index = self.parent_combo.currentIndex()
        if not (0 <= index < len(self.others)):
            self.reject()
            return
        attach(self.model, self.comp,
               self.others[index].name,
               self.child_anchor.currentData(),
               self.parent_anchor.currentData(),
               self.offset.value(), self.spin.value())
        self.accept()

    def _detach(self):
        detach(self.model, self.comp)
        self.accept()


class SnapTweakPopup(QDialog):
    """Tiny non-modal follow-up to a two-click snap: nudge the fresh
    mate's offset and spin (applied live), flip the part half a turn,
    or detach — the final adjustment without the context menu."""

    def __init__(self, model, comp, parent=None):
        super().__init__(parent)
        self.model = model
        self.comp = comp
        self.setWindowTitle(f"Adjust snap — {comp.name}")
        self.setModal(False)
        mate = mate_of(comp) or {}

        form = QFormLayout(self)
        form.addRow(QLabel(
            f"Snapped onto {mate.get('parent', '?')} — fine-tune it "
            f"(applies live):"))
        self.offset = QDoubleSpinBox()
        self.offset.setRange(-1e6, 1e6)
        self.offset.setDecimals(3)
        self.offset.setSuffix(" mm")
        self.offset.setSingleStep(1.0)
        self.offset.setValue(float(mate.get("offset", 0.0)))
        form.addRow("Offset along axis:", self.offset)
        self.spin = QDoubleSpinBox()
        self.spin.setRange(-360.0, 360.0)
        self.spin.setDecimals(2)
        self.spin.setSuffix(" °")
        self.spin.setSingleStep(15.0)
        self.spin.setValue(float(mate.get("spin", 0.0)))
        flip = QPushButton("Flip 180°")
        flip.setToolTip("Rotate the part half a turn about the mate "
                        "axis")
        flip.clicked.connect(lambda: self.spin.setValue(
            _flip_spin(self.spin.value())))
        spin_row = QWidget()
        row = QHBoxLayout(spin_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.spin, 1)
        row.addWidget(flip)
        form.addRow("Spin about axis:", spin_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        detach_btn = QPushButton("Detach")
        detach_btn.setToolTip("Undo this snap: remove the mate (the "
                              "part stays where it is)")
        detach_btn.clicked.connect(self._detach)
        buttons.addButton(detach_btn, QDialogButtonBox.ResetRole)
        form.addRow(buttons)

        self.offset.valueChanged.connect(self._apply)
        self.spin.valueChanged.connect(self._apply)

    def _apply(self, *_args):
        mate = mate_of(self.comp)
        if mate is None:
            return
        mate["offset"] = float(self.offset.value())
        mate["spin"] = float(self.spin.value())
        self.comp.params["mate"] = mate
        refresh(self.model)
        self.model.node_changed.emit(self.comp)

    def _detach(self):
        detach(self.model, self.comp)
        self.reject()
