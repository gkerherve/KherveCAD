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


def classic_text(act):
    """The text the action had before any style renamed it."""
    text = act.property("kc_classic_text")
    return act.text() if text is None else text


def apply(win, style):
    """Every action named as *style* names it (classic: as built)."""
    from PyQt5.QtWidgets import QAction
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
