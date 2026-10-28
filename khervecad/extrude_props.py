"""Properties of an extrude in the words of its window (2026-10-28, the
user: the Properties panel of a Boss / Cut extrude should have "this same
type of properties ... as the property window just opened").

`build` lays out, for a `linear_extrude` node: Profiles (what it
extrudes), Direction (One side / Two sides / Symmetric), End condition
(Blind / Through all / Up to an object), Distance, Distance 2 (two
sides), Reverse direction — the same rules as `extrude_panel` — then the
extrude's own Twist, Scale and Slices (kept: the user), and the Up to
fields when that end condition is chosen. `load` refreshes them.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import extrude_panel as ep

EXTENTS = [("", "Blind"), ("through_all", "Through all"),
           ("up_to", "Up to object"), ("up_to_face", "Up to face")]
#: the extrude's own params shown as they are, after the window's
KEPT = ("twist", "scale", "segments")
UP_TO = ("up_to", "up_to_side", "up_to_offset")


def title(node):
    return "Extruded Cut" if ep.is_cut(node) else "Extruded Boss"


def build(panel, form, node):
    """Rows of *panel* (a PropertiesPanel) for the extrude *node*."""
    from PyQt5.QtWidgets import QCheckBox, QComboBox, QLabel
    from . import language
    model = panel.model
    tr = language.tr
    st = panel._extrude = {}

    profiles = QLabel()
    profiles.setWordWrap(True)
    form.addRow(tr("Profiles"), profiles)
    st["profiles"] = profiles

    def guard(fn):
        def run(*a):
            if not panel._updating and panel.node is node:
                fn(*a)
        return run

    direction = QComboBox()
    for v, text in ep.DIRECTIONS:
        direction.addItem(tr(text), v)
    direction.currentIndexChanged.connect(guard(
        lambda _i: ep.set_direction(model, node, direction.currentData())))
    form.addRow(tr("Direction"), direction)
    st["direction"] = direction

    extent = QComboBox()
    for v, text in EXTENTS:
        extent.addItem(tr(text), v)
    extent.currentIndexChanged.connect(guard(
        lambda _i: model.set_param(node, "extent", extent.currentData())))
    form.addRow(tr("End condition"), extent)
    st["extent"] = extent

    schema = {row[0]: row for row in
              panel_schema(node)}

    def field(key, label):
        _k, _l, kind, lo, hi = schema[key]
        editor = panel._make_editor(key, kind, lo, hi)
        panel._editors[key] = editor
        head = QLabel(tr(label))
        form.addRow(head, editor)
        st["row:" + key] = (head, editor)
        return editor
    field("height", "Distance")
    field("height2", "Distance 2")

    reverse = QCheckBox(tr("Reverse direction"))
    def flip(on):
        ep.set_reversed(model, node, on)
        # Reverse wraps the extrude in a mirror: keep IT selected, so
        # these properties stay on screen
        win = panel.window()
        builder = getattr(win, "builder", None)
        if builder is not None:
            tree = builder.active_tree()
            if tree.selected_nodes() != [node]:
                tree.select_nodes([node])
        # the rows were rebuilt half way (the mirror made, not yet
        # marked): show the finished state
        if panel.node is node:
            panel._updating = True
            try:
                load(panel)
            finally:
                panel._updating = False
    reverse.toggled.connect(guard(flip))
    form.addRow("", reverse)
    st["reverse"] = reverse

    for key in UP_TO:
        field(key, schema[key][1])
    for key in KEPT:
        field(key, schema[key][1])


def panel_schema(node):
    from .model import NODE_TYPES
    return NODE_TYPES[node.type]["schema"]


def _row(st, key, on):
    for w in st.get("row:" + key, ()):
        w.setVisible(on)


def load(panel):
    """The window's fields as the extrude is now."""
    node, st = panel.node, getattr(panel, "_extrude", None)
    if node is None or not st:
        return
    st["profiles"].setText(ep.profiles_text(node))
    d = ep.direction_of(node)
    for key, value in (("direction", d),
                       ("extent", node.params.get("extent") or "")):
        box = st[key]
        box.blockSignals(True)
        i = box.findData(value)
        box.setCurrentIndex(i if i >= 0 else 0)
        box.blockSignals(False)
    st["reverse"].blockSignals(True)
    st["reverse"].setChecked(ep.is_reversed(node))
    st["reverse"].blockSignals(False)
    kind = node.params.get("extent") or ""
    _row(st, "height2", d == ep.TWO)
    for key in UP_TO:
        _row(st, key, kind == "up_to")
    height = st.get("row:height")
    if height:
        height[1].setEnabled(kind in ("", None))
