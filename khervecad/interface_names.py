# KherveCAD — the commands' names in the Fusion / SolidWorks styles.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""The commands under the names the imitated program gives them
(2026-10-24, the user: "if they are called Rotate Extrude they should
be called Revolved, Swept, Lofted ... Extruded Boss as well").

Keyed by an action's `data()` (the tool key), so the menu item, the
ribbon button and the tool-group copy of one command all change
together. The classic text is kept on the action (`kc_classic_text`)
and put back for the KherveCAD style; `interface_menus.index` reads
that classic text, so the layouts' paths keep resolving whatever the
action shows. Applied BEFORE the ribbon is built: its buttons take
their names from the actions."""

SOLIDWORKS = {
    # Features: Boss/Base and Cut
    "linear_extrude": "Extruded Boss/Base",
    "rotate_extrude": "Revolved Boss/Base",
    "sweep": "Swept Boss/Base",
    "section_loft": "Lofted Boss/Base",
    "difference": "Combine: Subtract",
    "union": "Combine: Add",
    "intersection": "Combine: Common",
    "fillet": "Fillet",
    "bevel": "Chamfer",
    "shell": "Shell",
    "bisect": "Split",
    "push_pull": "Move Face",
    "mirror": "Mirror",
    "pattern": "Linear / Circular Pattern",
    "translate": "Move/Copy Bodies",
    "rotate": "Rotate Bodies",
    "scale": "Scale",
    "hole": "Hole",
    "thread": "Thread",
    "sheet_metal": "Base Flange/Tab",
    "curve": "3D Sketch Curve",
    "draw_curve": "3D Sketch",
    # sketch
    "rect": "Corner Rectangle",
    "rect_center": "Center Rectangle",
    "rect_3pt": "3 Point Corner Rectangle",
    "arc_center": "Centerpoint Arc",
    "arc_3pt": "3 Point Arc",
    "circle_3pt": "Perimeter Circle",
    "slot": "Straight Slot",
    "poly_reg": "Polygon",
    "polygon": "Polygon (free)",
    "construction_line": "Centerline",
    "bspline": "Style Spline",
    "sk_trim": "Trim Entities",
    "sk_extend": "Extend Entities",
    "con_list": "Display/Delete Relations",
    "con_auto": "Fully Define Sketch",
    "con_dimension": "Smart Dimension",
    "con_point_on": "Coincident (on curve)",
    "dimension": "Smart Dimension",
    "measure": "Measure",
}

FUSION = {
    "linear_extrude": "Extrude",
    "rotate_extrude": "Revolve",
    "sweep": "Sweep",
    "section_loft": "Loft",
    "difference": "Combine: Cut",
    "union": "Combine: Join",
    "intersection": "Combine: Intersect",
    "fillet": "Fillet",
    "bevel": "Chamfer",
    "shell": "Shell",
    "bisect": "Split Body",
    "push_pull": "Press Pull",
    "mirror": "Mirror",
    "pattern": "Pattern",
    "translate": "Move/Copy",
    "rotate": "Rotate",
    "scale": "Scale",
    "hole": "Hole",
    "thread": "Thread",
    "rect": "2-Point Rectangle",
    "rect_3pt": "3-Point Rectangle",
    "arc_center": "Center Point Arc",
    "poly_reg": "Polygon",
    "bspline": "Control Point Spline",
    "sk_trim": "Trim",
    "sk_extend": "Extend",
    "dimension": "Sketch Dimension",
    "measure": "Measure",
}

NAMES = {"SolidWorks": SOLIDWORKS, "Fusion": FUSION}

#: the object tree's names: what the program's own feature tree calls
#: the node (SolidWorks "Boss-Extrude1", Fusion "Extrude1")
TREE = {
    "SolidWorks": {
        "linear_extrude": "Boss-Extrude", "rotate_extrude": "Revolve",
        "sweep": "Sweep", "section_loft": "Loft", "loft": "Loft",
        "difference": "Combine-Subtract", "union": "Combine-Add",
        "intersection": "Combine-Common", "fillet": "Fillet",
        "bevel": "Chamfer", "shell": "Shell", "mirror": "Mirror",
        "pattern": "Pattern", "translate": "Body-Move/Copy",
        "rotate": "Body-Rotate", "scale": "Scale", "hole": "Hole",
        "push_pull": "Move Face", "bisect": "Split", "thread": "Thread",
        "sheet_metal": "Base-Flange", "curve": "3DSketch",
    },
    "Fusion": {
        "linear_extrude": "Extrude", "rotate_extrude": "Revolve",
        "sweep": "Sweep", "section_loft": "Loft", "loft": "Loft",
        "difference": "Combine (Cut)", "union": "Combine (Join)",
        "intersection": "Combine (Intersect)", "fillet": "Fillet",
        "bevel": "Chamfer", "shell": "Shell", "mirror": "Mirror",
        "pattern": "Pattern", "translate": "Move", "rotate": "Rotate",
        "scale": "Scale", "hole": "Hole", "push_pull": "Press Pull",
        "bisect": "Split Body", "thread": "Thread",
    },
}

#: the style whose names are in use (the help reads it)
CURRENT = None


def name_for(key):
    """*key*'s name in the style in use, or None in the classic style."""
    return NAMES.get(CURRENT, {}).get(key)


def tree_base(type_):
    """The style's tree name for a node type, or None."""
    return TREE.get(CURRENT, {}).get(type_)


def tree_text(node):
    """*node*'s row text: a name the user left at its default ("Linear
    extrude", "Linear extrude 2", "Linear extrude [Body]") reads as the
    style's feature name; a name the user typed is kept."""
    import re
    styled = tree_base(node.type)
    name = node.name or ""
    if not styled:
        return name
    from .model import NODE_TYPES
    label = NODE_TYPES.get(node.type, {}).get("label", "")
    match = re.fullmatch(re.escape(label) + r"(?P<rest>( \d+)?( \[.*\])?)",
                         name)
    return styled + match.group("rest") if match else name


def classic_text(act):
    """The text the action had before any style renamed it."""
    text = act.property("kc_classic_text")
    return act.text() if text is None else text


def apply(win, style):
    """Every action named as *style* names it (classic: as built)."""
    from PyQt5.QtWidgets import QAction
    global CURRENT
    CURRENT = style
    names = NAMES.get(style, {})
    for act in win.findChildren(QAction):
        key = act.data()
        if not isinstance(key, str):
            continue
        name = names.get(key)
        old = act.property("kc_classic_text")
        if name is None:
            if old is not None:
                act.setText(old)
            continue
        if old is None:
            act.setProperty("kc_classic_text", act.text())
        act.setText(name)
    # the tree's rows follow
    builder = getattr(win, "builder", None)
    for tree in (getattr(builder, "tree", None),
                 getattr(getattr(builder, "object_tab", None), "tree",
                         None)):
        if tree is not None and hasattr(tree, "rebuild"):
            tree.rebuild()
    # the help follows: tooltip, status tip (tooltips.entry reads CURRENT)
    from . import tooltips
    keys = set().union(*NAMES.values())
    for act in win.findChildren(QAction):
        key = act.data()
        if isinstance(key, str) and key in keys:
            tooltips.apply(act, key, act.shortcut().toString())
