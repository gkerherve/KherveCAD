"""The tree's History view and its fixed folders (2026-10-21, the user
asked for SolidWorks' FeatureManager feel without losing their own tree).

Two ways of drawing the SAME nodes — nothing in the document changes:

- **Structure** (default): the tree as built, each operation holding
  what it acts on (the OpenSCAD program's own shape).
- **History**: SolidWorks' feature list — features in the order they were
  made, numbered by kind ("Extrude 1", "Cut 2"), the 2D shapes a feature
  uses tucked under it like SolidWorks' sketch under its extrude, and
  the user's Groups kept as FOLDERS of their features. A rolled-back
  container shows the rollback bar where its active features end.

History starts with the fixed rows SolidWorks has (Structure stays
exactly the tree as built): **Origin** (Front /
Top / Right planes — a double-click shows that plane in the 2D view) and
**Material** (click to set it on every part in view); a click on
Origin shows / hides the origin axes, a double-click on a plane turns
the 3D view to it and opens a sketch there.

Rows carry the node id, so selection, Properties, the right-click menu
and renaming work as in Structure; only drag and drop is off in History.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import language

SETTING = "tree/history"
#: role of a fixed row: "origin", "plane:<view2d plane>", "material"
ROLE_FIXED = 0x0100 + 21
#: role holding the text a History row shows (a rename edits the name)
ROLE_SHOWN = 0x0100 + 22

#: (label, view2d plane) — SolidWorks' names and its order
PLANES = [("Front Plane", "Front (XZ)"), ("Top Plane", "Top (XY)"),
          ("Right Plane", "Side (YZ)")]

#: short feature names by node type (anything else: its type label)
FEATURE = {
    "linear_extrude": "Extrude", "rotate_extrude": "Revolve",
    "difference": "Cut", "intersection": "Intersect", "hull": "Hull",
    "minkowski": "Round", "fillet": "Fillet", "bevel": "Bevel",
    "shell": "Shell", "translate": "Move", "rotate": "Rotate",
    "scale": "Scale", "mirror": "Mirror", "pattern": "Pattern",
    "for_loop": "Repeat", "color": "Appearance", "sweep": "Sweep",
    "loft": "Loft", "section_loft": "Loft", "offset": "Offset",
    "push_pull": "Push-pull", "cube": "Box", "sphere": "Sphere",
    "cylinder": "Cylinder",
}
#: shown as folders holding their features
FOLDERS = ("union", "variables")


def enabled():
    try:
        from PyQt5.QtCore import QSettings
        return QSettings("Kherve", "KherveCAD").value(SETTING, False,
                                                      type=bool)
    except Exception:                          # pragma: no cover
        return False


def set_enabled(on):
    from PyQt5.QtCore import QSettings
    QSettings("Kherve", "KherveCAD").setValue(SETTING, bool(on))


# ----------------------------------------------------------- fixed rows
def build_fixed(tree):
    """Origin (with the three planes) and Material, at the top."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QTreeWidgetItem
    from . import icons

    def row(parent, text, glyph, role, tip):
        item = QTreeWidgetItem(parent)
        item.setText(0, language.tr(text))
        item.setIcon(0, icons.icon(glyph))
        item.setData(0, ROLE_FIXED, role)
        item.setToolTip(0, language.tr(tip))
        item.setFlags((item.flags() | Qt.ItemIsSelectable)
                      & ~(Qt.ItemIsEditable | Qt.ItemIsDragEnabled
                          | Qt.ItemIsDropEnabled | Qt.ItemIsUserCheckable))
        return item
    root = tree.invisibleRootItem()
    origin = row(root, "Origin", "mdi.axis-arrow", "origin",
                 "The origin and the three main planes")
    for label, plane in PLANES:
        row(origin, label, "mdi.square-outline", "plane:" + plane,
            "Double-click to sketch on this plane in the 2D view")
    origin.setExpanded(tree._expand_state.get("__origin__", False))
    text = language.tr("Material <{m}>").format(m=material_text(tree))
    mat = row(root, "Material", "mdi.texture-box", "material",
              "Right-click to set the material of every part in view")
    mat.setText(0, text)


def _parts(tree):
    return [n for n in tree._top_nodes() if n.type != "variables"
            and n.type != "assign" and n.type != "scad_use"]


def material_text(tree):
    found = set()
    for n in _parts(tree):
        found.add(n.params.get("material") if n.type == "color"
                  else None)
    if len(found) == 1:
        m = next(iter(found))
        if m and m != "Default":
            return language.tr(m)
    return language.tr("not specified") if found <= {None, "Default"} \
        else language.tr("mixed")


def fixed_menu(tree, item, pos):
    """Right-click on a fixed row. True when it handled the click."""
    role = item.data(0, ROLE_FIXED) if item is not None else None
    if not role:
        return False
    from PyQt5.QtWidgets import QMenu
    menu = QMenu(tree)
    if role == "material":
        from .model import MATERIALS
        for m in MATERIALS:
            menu.addAction(language.tr(m),
                           lambda _=False, m=m: set_material(tree, m))
    elif role.startswith("plane:"):
        menu.addAction(language.tr("Sketch on this plane"),
                       lambda: sketch_on(tree, role[6:]))
    elif role == "origin":
        view = getattr(tree.window(), "view3d", None)
        if view is None:
            return True
        act = menu.addAction(language.tr("Show origin axes in 3D"))
        act.setCheckable(True)
        act.setChecked(bool(view.axes))
        act.toggled.connect(lambda on: _axes(tree, on))
    else:
        return True
    menu.exec_(tree.viewport().mapToGlobal(pos))
    return True


def set_material(tree, material):
    """Every part in view takes *material* (its colour kept)."""
    parts = _parts(tree)
    if not parts:
        return
    keep = [(n, n.params.get("color", "#c8c8c8"),
             n.params.get("alpha", 1.0)) for n in parts]
    for node, colour, alpha in keep:
        tree.model.set_color([node], colour or "#c8c8c8", alpha,
                             material=material)
    tree.rebuild()                    # the Material row reads it again


def double_clicked(tree, item):
    role = item.data(0, ROLE_FIXED) if item is not None else None
    if not role:
        return False
    if role.startswith("plane:"):
        sketch_on(tree, role[6:])
    return True


def sketch_on(tree, plane):
    """Sketch on a main plane: the 3D view turns square on to it and the
    sketch opens there, as Sketch Mode does (the user: the Origin rows
    "did nothing" — switching the hidden 2D view's plane showed nothing
    in the SolidWorks layout)."""
    win = tree.window()
    tree.plane_picked.emit(plane)
    try:
        from . import normal_to
        normal_to.turn_to(win, plane)
    except Exception:
        pass


def _axes(tree, on):
    view = getattr(tree.window(), "view3d", None)
    if view is not None:
        view.set_axes(on)
        view.update()


def clicked(tree, item):
    """A single click on a fixed row: Origin shows / hides the origin
    axes in 3D, Material opens its list, a plane says what it does."""
    role = item.data(0, ROLE_FIXED) if item is not None else None
    if not role:
        return False
    win = tree.window()
    if role == "origin":
        view = getattr(win, "view3d", None)
        if view is not None:
            _axes(tree, not view.axes)
            if hasattr(win, "statusBar"):
                win.statusBar().showMessage(language.tr(
                    "Origin axes shown in 3D" if view.axes else
                    "Origin axes hidden"), 3000)
    elif role == "material":
        fixed_menu(tree, item, tree.visualItemRect(item).bottomLeft())
    elif role.startswith("plane:") and hasattr(win, "statusBar"):
        win.statusBar().showMessage(language.tr(
            "Double-click (or right-click) to sketch on this plane"), 4000)
    return True


# --------------------------------------------------------------- history
def build_history(tree, selected):
    """The scope's features in order, groups as folders."""
    counts = {}
    for node in tree._top_nodes():
        _features(tree, node, tree.invisibleRootItem(), selected, counts)
    _rollback_bar(tree)


def _is_2d(node):
    from .model import SHAPE_2D
    return node.category == SHAPE_2D


def _label(node, counts):
    from .model import NODE_TYPES
    base = FEATURE.get(node.type) or language.tr(
        NODE_TYPES[node.type]["label"])
    counts[base] = counts.get(base, 0) + 1
    shown = "%s %d" % (language.tr(base), counts[base])
    plain = NODE_TYPES[node.type]["label"]
    import re
    default = any(re.fullmatch(re.escape(p) + r"( \d+)?", node.name or "")
                  for p in (plain, language.tr(plain)))
    if node.name and not default:
        shown += "  (%s)" % node.name
    return shown


def _row(tree, node, parent_item, selected, text):
    from PyQt5.QtCore import Qt
    item = tree._new_item(parent_item, node)
    item.setData(0, Qt.UserRole, node.id)
    tree._decorate(item, node)
    item.setText(0, text)
    item.setData(0, ROLE_SHOWN, text)
    item.setFlags(item.flags() & ~(Qt.ItemIsDragEnabled
                                   | Qt.ItemIsDropEnabled))
    if node.id in selected:
        item.setSelected(True)
    return item


def _features(tree, node, parent_item, selected, counts):
    """Rows for *node*: what it holds first (earlier features), then the
    node itself with the 2D shapes it uses under it."""
    if node.type in FOLDERS or node.type == "assign":
        if node.type == "assign":
            _row(tree, node, parent_item, selected, node.name)
            return
        folder = _row(tree, node, parent_item, selected, node.name)
        for child in node.children:
            _features(tree, child, folder, selected, counts)
        folder.setExpanded(tree._expand_state.get(node.id, True))
        return
    if tree._is_opaque(node) or node.type == "reference":
        _row(tree, node, parent_item, selected, node.name)
        return
    if _is_2d(node) and not node.children:
        # a sketch shape nobody uses yet: a sketch of its own
        _row(tree, node, parent_item, selected, _sketch(node, counts))
        return
    sketch = [c for c in node.children if _is_2d(c)]
    for child in node.children:
        if child not in sketch:
            _features(tree, child, parent_item, selected, counts)
    item = _row(tree, node, parent_item, selected, _label(node, counts))
    if sketch:
        holder = item
        for shape in sketch:
            _row(tree, shape, holder, selected, shape.name)
        item.setExpanded(tree._expand_state.get(node.id, False))


def _sketch(node, counts):
    counts["Sketch"] = counts.get("Sketch", 0) + 1
    return "%s %d  (%s)" % (language.tr("Sketch"), counts["Sketch"],
                            node.name)


def _rollback_bar(tree):
    """A bar under the last active top-level feature when the scope's
    container is rolled back (right-click a row ▸ Roll back to here)."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QTreeWidgetItem
    from . import suppress
    tops = tree._top_nodes()
    if not tops:
        return
    container = tops[0].parent
    k = container.params.get(suppress.ROLLBACK) \
        if container is not None else None
    if not isinstance(k, int) or k >= len(container.children):
        return
    stop = container.children[k]
    root = tree.invisibleRootItem()
    at = root.childCount()
    for i in range(root.childCount()):
        if root.child(i).data(0, Qt.UserRole) == stop.id:
            # the first row belonging to the first rolled-back node
            at = i
            break
    else:
        # the stop node's own row comes after its contents: find any row
        ids = {n.id for n in stop.walk()}
        for i in range(root.childCount()):
            if root.child(i).data(0, Qt.UserRole) in ids:
                at = i
                break
    bar = QTreeWidgetItem()
    bar.setText(0, "━━━━  " + language.tr("Rollback") + "  ━━━━")
    bar.setData(0, ROLE_FIXED, "rollback")
    bar.setToolTip(0, language.tr(
        "Everything below is rolled back — right-click a row ▸ Roll "
        "forward to bring it back"))
    bar.setFlags(Qt.ItemIsEnabled)
    root.insertChild(at, bar)
