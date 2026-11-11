"""Properties of a Linear / Circular Sketch Pattern (2026-11-11, the
user: "the i * 60 does not seem to be editable … one turn is 360 and
then how many, so the value would be 360 / i, but you do not write
that").

A selected pattern loop — or the rotate / translate inside it — shows
the window's own numbers (Instances, Total angle, Equal spacing, Centre;
Spacing and Direction 2 for a linear one) instead of the loop's From /
To and a rotate's expression; a change rewrites the loop and the
`i * 360 / 6` turn through `sketch_pattern.update`.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import sketch_pattern as sp

#: (key, label, kind, minimum, maximum) per pattern kind
CIRCULAR_ROWS = [("count", "Instances", "int", 1, sp.MAX_COPIES),
                 ("angle", "Total angle (°, 360 = one turn)", "float",
                  -360.0, 360.0),
                 ("equal", "Equal spacing", "bool", None, None),
                 ("cx", "Centre X (mm)", "float", -1e6, 1e6),
                 ("cy", "Centre Y (mm)", "float", -1e6, 1e6)]
LINEAR_ROWS = [("count1", "Instances", "int", 1, sp.MAX_COPIES),
               ("spacing1", "Spacing (mm)", "float", -1e6, 1e6),
               ("angle1", "Direction (°)", "float", -360.0, 360.0),
               ("dir2", "Direction 2", "bool", None, None),
               ("count2", "Instances 2", "int", 1, sp.MAX_COPIES),
               ("spacing2", "Spacing 2 (mm)", "float", -1e6, 1e6),
               ("angle2", "Direction 2 (°)", "float", -360.0, 360.0)]


def loop_for(node):
    """The pattern loop a Properties node shows the numbers of: the loop
    itself, or the turn / move straight inside it."""
    if node is None:
        return None
    if node.type == "for_loop" and isinstance(node.params.get(sp.KEY),
                                              dict):
        return node
    if node.type in ("rotate", "translate", "for_loop"):
        loop = sp.loop_of(node.parent)
        if loop is not None:
            return loop
    return None


def rows(loop):
    kind = (loop.params.get(sp.KEY) or {}).get("kind")
    return CIRCULAR_ROWS if kind == sp.CIRCULAR else LINEAR_ROWS


def build(panel, form, loop):
    from PyQt5.QtWidgets import QCheckBox, QDoubleSpinBox, QLabel, QSpinBox
    from . import language
    tr = language.tr
    st = panel._pattern = {"loop": loop}
    kind = loop.params[sp.KEY].get("kind")
    head = QLabel("<i>%s</i>" % tr(sp.LABEL.get(kind, "Pattern")))
    form.addRow(head)

    def change(key):
        def run(value):
            if not panel._updating and st["loop"].parent is not None:
                if isinstance(value, bool):
                    v = value
                else:
                    v = int(value) if key.startswith("count") else \
                        float(value)
                sp.update(panel.model, st["loop"], key, v)
        return run
    for key, label, kind_, lo, hi in rows(loop):
        if kind_ == "bool":
            w = QCheckBox(tr(label))
            w.toggled.connect(change(key))
            form.addRow("", w)
        else:
            w = QSpinBox() if kind_ == "int" else QDoubleSpinBox()
            w.setRange(int(lo) if kind_ == "int" else lo,
                       int(hi) if kind_ == "int" else hi)
            if kind_ == "float":
                w.setDecimals(3)
            w.setKeyboardTracking(False)
            w.valueChanged.connect(change(key))
            form.addRow(tr(label), w)
        st[key] = w
    note = QLabel(tr("Select the loop and press the pattern button to "
                     "open its window again."))
    note.setWordWrap(True)
    note.setEnabled(False)
    form.addRow(note)


def load(panel):
    st = getattr(panel, "_pattern", None)
    if not st or st["loop"].parent is None:
        return
    from PyQt5.QtWidgets import QCheckBox
    state = sp.state_of(st["loop"])
    values = dict(state, cx=state["centre"][0], cy=state["centre"][1])
    for key, w in st.items():
        if key == "loop" or key not in values:
            continue
        if isinstance(w, QCheckBox):
            w.setChecked(bool(values[key]))
        else:
            w.setValue(values[key])
    if "dir2" in st:
        on = bool(values["dir2"])
        for key in ("count2", "spacing2", "angle2"):
            w = st[key]
            w.setEnabled(on)
