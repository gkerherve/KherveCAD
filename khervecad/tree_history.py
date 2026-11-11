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


def planes_shown():
    """Origin / planes / Material over the Structure tree too (on by
    default; the test setup turns it off — older tests read row 0)."""
    try:
        from PyQt5.QtCore import QSettings
        return QSettings("Kherve", "KherveCAD").value(
            "tree/planes", True, type=bool)
    except Exception:                          # pragma: no cover
        return True


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
            "Select it and click Sketch, or double-click, to sketch on "
            "this plane")
    origin.setExpanded(tree._expand_state.get("__origin__", False))
    text = language.tr("Material <{m}>").format(m=material_text(tree))
    mat = row(root, "Material", "mdi.texture-box", "material",
              "Right-click to set the material of every part in view")
    mat.setText(0, text)


def _parts(tree):
    return [n for n in tree._top_nodes() if n.type != "variables"
            and n.type != "assign" and n.type != "scad_use"]


def material_text(tree):
    from . import analysis, massbar
    chosen = tree.model.root.params.get(massbar.KEY)
    if chosen in analysis.MATERIALS:
        return language.tr(chosen)
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
        from . import massbar
        from .model import MATERIALS
        massbar.fill_menu(menu, massbar.material_of(tree.model),
                          lambda m: set_physical(tree, m))
        menu.addSeparator()
        looks = menu.addMenu(language.tr("Appearance only"))
        for m in MATERIALS:
            looks.addAction(language.tr(m),
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


def set_physical(tree, material):
    """What the part IS made of: its mass, and the look that goes with
    it (its colour kept). Undefined leaves the look alone."""
    from . import analysis, massbar
    root = tree.model.root
    if material in analysis.MATERIALS:
        root.params[massbar.KEY] = material
    else:
        root.params.pop(massbar.KEY, None)
    tree.model.node_changed.emit(root)
    look = analysis.appearance_of(material)
    if look:
        set_material(tree, look)
    else:
        tree.rebuild()


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
            "Click Sketch (or double-click) to sketch on this plane"),
            4000)
    return True


# --------------------------------------------------------------- history
#: names a feature is given by the tool that made it: not shown again
#: beside "Boss-Extrude 2"
_AUTO_NAMES = {"Extrude regions", "Extruded Boss/Base", "Extruded Cut",
               "Revolved Cut", "Revolved Boss/Base", "Revolve"}


def build_history(tree, selected):
    """SolidWorks' feature list: one row a feature, in the order they
    were made, its sketch under it; the user's Groups as folders
    (feature_list.py says what gets no row)."""
    from . import feature_list
    feature_list.stamp(tree.model)
    counts = {}
    for node in feature_list.ordered(tree._top_nodes()):
        _features(tree, node, tree.invisibleRootItem(), selected, counts)
    _rollback_bar(tree)


def _is_2d(node):
    from .model import SHAPE_2D
    return node.category == SHAPE_2D


def _label(node, counts):
    from .model import NODE_TYPES
    from .interface_names import tree_base
    base = tree_base(node.type) or FEATURE.get(node.type) or language.tr(
        NODE_TYPES[node.type]["label"])
    if node.type in ("linear_extrude", "rotate_extrude"):
        # SolidWorks calls an extrude that cuts Cut-Extrude (every cut
        # read "Boss-Extrude 2 (Extruded Cut)")
        from . import extrude_panel
        if extrude_panel.is_cut(node):
            base = {"Boss-Extrude": "Cut-Extrude",
                    "Revolve": "Cut-Revolve"}.get(base, base)
    counts[base] = counts.get(base, 0) + 1
    shown = "%s %d" % (language.tr(base), counts[base])
    plain = NODE_TYPES[node.type]["label"]
    import re
    default = any(re.fullmatch(re.escape(p) + r"( \d+)?", node.name or "")
                  for p in (plain, language.tr(plain)))
    if node.name and not default and node.name not in _AUTO_NAMES:
        shown += "  (%s)" % node.name
    return shown


def _row(tree, node, parent_item, selected, text):
    from PyQt5.QtCore import Qt
    item = tree._new_item(parent_item, node)
    item.setData(0, Qt.UserRole, node.id)
    item.setData(0, ROLE_SHOWN, text)
    tree._decorate(item, node)
    item.setText(0, text)
    item.setFlags(item.flags() & ~(Qt.ItemIsDragEnabled
                                   | Qt.ItemIsDropEnabled))
    if node.id in selected:
        item.setSelected(True)
    return item


def _features(tree, node, parent_item, selected, counts):
    """Rows for *node*: what it holds first (earlier features), then the
    node itself with its sketch under it."""
    from . import feature_list
    if node.params.get("hole_wizard"):
        _row(tree, node, parent_item, selected, node.name)
        return
    if feature_list.is_sketch_group(node):
        # a sketch nothing uses yet: a Sketch of its own, its shapes in it
        item = _row(tree, node, parent_item, selected,
                    _sketch(node, counts))
        for shape in node.children:
            _row(tree, shape, item, selected, shape.name)
        item.setExpanded(tree._expand_state.get(node.id, False))
        return
    if node.type in FOLDERS or node.type == "assign":
        if node.type == "assign":
            _row(tree, node, parent_item, selected, node.name)
            return
        folder = _row(tree, node, parent_item, selected, node.name)
        for child in feature_list.ordered(node.children):
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
    holder, sketch = (None, [c for c in node.children if _is_2d(c)])
    if node.type in feature_list.EXTRUDES:
        holder, sketch = feature_list.sketch_of(node)
    inner = [c for c in node.children if not _is_2d(c)
             and not (node.type in feature_list.EXTRUDES
                      and c.type == "regions")]
    from . import sketch_pattern
    if sketch_pattern.loop_of(node) is node:
        # a Sketch Pattern: ONE row, the shapes it repeats under it — its
        # turn / move is its inside, not an earlier feature (the user)
        sketch = [n for n in node.walk() if n is not node and _is_2d(n)]
        inner = []
    for child in feature_list.ordered(inner):
        _features(tree, child, parent_item, selected, counts)
    item = _row(tree, node, parent_item, selected, _label(node, counts))
    under = item
    if holder is not None and sketch:
        counts["Sketch"] = counts.get("Sketch", 0) + 1
        # SolidWorks' "(-)" on an under defined sketch; the tooltip says
        # what it is held by and how it can still move (sketch_lock)
        from . import sketch_lock
        try:
            lock = sketch_lock.of(tree.model, holder)
        except Exception:
            lock = None
        under = _row(tree, holder, item, selected,
                     "%s%s %d" % (sketch_lock.marker(lock) if lock else "",
                                  language.tr("Sketch"), counts["Sketch"]))
        if lock:
            tip = sketch_lock.text(lock)
            under.setToolTip(0, tip)
            item.setToolTip(0, tip)
        under.setExpanded(tree._expand_state.get(holder.id, False))
    for shape in sketch:
        _row(tree, shape, under, selected, shape.name)
    if sketch:
        item.setExpanded(tree._expand_state.get(node.id, False))


def _sketch(node, counts):
    counts["Sketch"] = counts.get("Sketch", 0) + 1
    return "%s %d  (%s)" % (language.tr("Sketch"), counts["Sketch"],
                            node.name)


def _rollback_bar(tree):
    """The bar above the first feature that is rolled back (right-click
    a row ▸ Roll back to here)."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QTreeWidgetItem
    from . import suppress
    root = tree.invisibleRootItem()
    at = None
    for i in range(root.childCount()):
        item = root.child(i)
        if item.data(0, ROLE_FIXED):
            continue
        node = tree.model.find(item.data(0, Qt.UserRole)) \
            if hasattr(tree.model, "find") else tree.node_of(item)
        if node is not None and not node.params.get(suppress.KEY) and (
                node.params.get(suppress.ROLLED)
                or suppress.rolled_back(node)):
            at = i
            break
    if at is None:
        return
    bar = QTreeWidgetItem()
    bar.setText(0, "━━━━  " + language.tr("Rollback") + "  ━━━━")
    bar.setData(0, ROLE_FIXED, "rollback")
    bar.setToolTip(0, language.tr(
        "Everything below is rolled back — right-click a row ▸ Roll "
        "forward to bring it back"))
    bar.setFlags(Qt.ItemIsEnabled)
    root.insertChild(at, bar)
