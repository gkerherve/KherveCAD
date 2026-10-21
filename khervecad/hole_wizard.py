"""The Hole Wizard (2026-10-21, the user: "build the Hole button like
SolidWorks").

SolidWorks' way: choose the hole (type, standard size, fit, end
condition), then click the FACE — every click one hole, square to that
face — and the holes are one feature in the tree.

Here a feature is a Group named like SolidWorks' ("M6 Clearance Hole")
holding one placed `hole` node per click (translate · rotate · hole: the
hole's +Z turned onto the face's outward normal), inside a Difference
that cuts it from the part; the first hole on a part makes that
Difference, the next ones join the same feature. The spec rides on the
Group as `params["hole_wizard"]`, so "Update" re-sizes every hole of the
feature at once. Plain nodes all the way, so the program is OpenSCAD.

`spec_params` is the size table (ISO 273 clearance close / normal /
loose, tap drill = d − pitch, ISO 4762 counterbores, 90° countersinks).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import language

TYPES = ["Clearance", "Tapped (drill)", "Counterbore", "Countersink",
         "Nut trap"]
FITS = ["Close", "Normal", "Loose"]
ENDS = ["Through all", "Blind"]
#: ISO 273 clearance holes (close, normal, loose)
CLEARANCE = {"M3": (3.2, 3.4, 3.6), "M4": (4.3, 4.5, 4.8),
             "M5": (5.3, 5.5, 5.8), "M6": (6.4, 6.6, 7.0),
             "M8": (8.4, 9.0, 10.0), "M10": (10.5, 11.0, 12.0),
             "M12": (13.0, 13.5, 14.5), "M16": (17.0, 17.5, 18.5),
             "M20": (21.0, 22.0, 24.0)}
#: ISO 4762 socket-head counterbore diameters
COUNTERBORE = {"M3": 6.5, "M4": 8.0, "M5": 10.0, "M6": 11.0, "M8": 15.0,
               "M10": 18.0, "M12": 20.0, "M16": 26.0, "M20": 33.0}
SIZES = list(CLEARANCE)
DEFAULT = dict(type="Clearance", size="M6", fit="Normal",
               end="Through all", depth=10.0)
KEY = "hole_wizard"


def _bolt(size):
    from .library import BOLT_SIZES
    return BOLT_SIZES[size]


def spec_params(spec, through=None):
    """The `hole` node params for *spec*; *through* = the depth that
    goes through the part (Through all)."""
    spec = dict(DEFAULT, **(spec or {}))
    size = spec["size"]
    b = _bolt(size)
    fit = FITS.index(spec["fit"]) if spec["fit"] in FITS else 1
    clear = CLEARANCE[size][fit]
    depth = float(through) if spec["end"] == "Through all" and through \
        else float(spec["depth"])
    p = dict(kind="plain", diameter=clear, depth=round(depth, 4),
             extra=1.0)
    kind = spec["type"]
    if kind == "Tapped (drill)":
        p["diameter"] = round(b["d"] - b["pitch"], 3)
    elif kind == "Counterbore":
        p.update(kind="counterbore", head_diameter=COUNTERBORE[size],
                 head_depth=round(b["cap_h"] + 0.4, 3))
    elif kind == "Countersink":
        p.update(kind="countersink", head_diameter=round(2 * b["d"] + 0.4,
                                                         3),
                 countersink_angle=90.0)
    elif kind == "Nut trap":
        p.update(kind="nut_trap", nut_width=round(b["af"] + 0.3, 3),
                 nut_height=round(b["nut_h"] + 0.2, 3))
    return p


def title(spec):
    spec = dict(DEFAULT, **(spec or {}))
    kind = {"Clearance": "Clearance Hole", "Tapped (drill)": "Tapped Hole",
            "Counterbore": "Counterbore", "Countersink": "Countersink",
            "Nut trap": "Nut Trap"}[spec["type"]]
    return "%s %s" % (spec["size"], kind)


def _turn(normal):
    """rotate([0, ry, rz]) taking +Z onto *normal*."""
    nx, ny, nz = normal
    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    nx, ny, nz = nx / length, ny / length, nz / length
    ry = math.degrees(math.acos(max(-1.0, min(1.0, nz))))
    rz = math.degrees(math.atan2(ny, nx)) if abs(nz) < 0.999999 else 0.0
    return round(ry, 6), round(rz, 6)


def _through(model, part):
    """A depth that crosses the whole part from any face."""
    from . import mesh
    try:
        tris = mesh.tessellate(part)
    except Exception:
        tris = []
    if not tris:
        return 100.0
    pts = [p for t in tris for p in t]
    span = [max(p[i] for p in pts) - min(p[i] for p in pts)
            for i in range(3)]
    return round(math.sqrt(sum(s * s for s in span)) + 2.0, 3)


def feature_of(part):
    """The hole feature a part already has (its Difference's Group with
    our spec), or None."""
    parent = part.parent
    if parent is not None and parent.type == "difference" and \
            parent.children and parent.children[0] is part:
        for child in parent.children[1:]:
            if child.type == "union" and KEY in child.params:
                return child
    return None


def body_of(model, part):
    """What to drill: an Object (or an instance's Object) is drilled
    INSIDE — its one body, or its pieces grouped into one — so the
    assembly keeps one part row; a body we drilled before is found
    again under its Difference."""
    from . import mates
    if part.type == "reference":
        part = mates.definition_of(model, part) or part
    if part.type != "component":
        return part
    kids = [c for c in part.children]
    if len(kids) > 1:
        body = model.group_nodes(kids) if hasattr(model, "group_nodes") \
            else model.wrap_nodes(kids, "union")
        return body
    if not kids:
        return part
    body = kids[0]
    if body.type == "difference" and body.children and any(
            KEY in c.params for c in body.children[1:]):
        return body.children[0]
    return body


def add_hole(model, part, point, normal, spec, scope=None):
    """One hole on *part* at the scope-frame *point* (on a face whose
    outward normal is *normal*). Returns the feature Group."""
    from . import mesh
    import numpy as np
    spec = dict(DEFAULT, **(spec or {}))
    stop = scope if scope is not None and scope is not model.root \
        else None
    if part.type in ("component", "reference"):
        # the click is in the assembly: bring it into the Object's own
        # frame (an instance's placement taken off), then drill inside
        from . import anchors, mates
        env = anchors.doc_env(model)
        point = anchors.to_local(part, point, env)
        normal = anchors.dir_to_local(part, normal, env)
        stop = mates.definition_of(model, part) or part \
            if part.type == "reference" else part
    part = body_of(model, part)
    feature = feature_of(part)
    if feature is None or feature.params.get(KEY) != spec:
        diff = part.parent if part.parent is not None and \
            part.parent.type == "difference" and \
            part.parent.children[0] is part else \
            model.wrap_nodes([part], "difference")
        feature = model.add_node("union", {}, parent=diff)
        feature.params[KEY] = dict(spec)
        model.rename(feature, title(spec))
    m = np.array(mesh.ancestor_matrix(feature, stop=stop), dtype=float)
    inv = np.linalg.inv(m)
    p = inv @ np.array([point[0], point[1], point[2], 1.0])
    # a normal maps by the inverse-transpose of the linear part
    n = np.linalg.inv(m[:3, :3]).T @ np.array(normal, dtype=float)
    ry, rz = _turn(n)
    move = model.add_node("translate", dict(
        x=round(float(p[0]), 4), y=round(float(p[1]), 4),
        z=round(float(p[2]), 4)), parent=feature)
    turn = model.add_node("rotate", dict(x=0.0, y=ry, z=rz), parent=move)
    hole = model.add_node("hole", spec_params(spec, _through(model, part)),
                          parent=turn)
    model.rename(hole, title(spec))
    return feature


def update(model, feature, spec):
    """Re-size every hole of *feature* to *spec*."""
    spec = dict(DEFAULT, **(spec or {}))
    feature.params[KEY] = dict(spec)
    body = feature.parent.children[0] if feature.parent is not None \
        else None
    params = spec_params(spec, _through(model, body) if body else None)
    for node in feature.walk():
        if node.type == "hole":
            for k, v in params.items():
                model.set_param(node, k, v)
            model.rename(node, title(spec))
    model.rename(feature, title(spec))


# ------------------------------------------------------------------ UI
TIP = ("Hole Wizard",
       "SolidWorks' Hole Wizard: choose the hole — type (clearance, "
       "tapped, counterbore, countersink, nut trap), standard size M3-M20, "
       "fit and end condition — then click the faces of a part: every "
       "click drills one hole square to that face. The holes are one "
       "feature in the tree.",
       ["Click Hole Wizard (Features tab).",
        "Choose type, size, fit and Through all / Blind in the panel.",
        "Click a face of a part — one hole per click, as many as you "
        "like.",
        "Esc or Done finishes. Select the feature later and press "
        "Update to re-size all its holes."],
       "The holes stay ordinary nodes, so the OpenSCAD program cuts them.")


def action(window):
    act = getattr(window, "_hole_wizard_act", None)
    if act is not None:
        return act
    from PyQt5.QtWidgets import QAction
    from . import icons, toolbars, tooltips
    tooltips.TIPS.setdefault("hole_wizard", TIP)
    act = QAction(icons.icon("mdi.circle-slice-8"),
                  language.tr("Hole Wizard"), window)
    act.setData("hole_wizard")
    toolbars.remember_glyph(act, "mdi.circle-slice-8", "measure")
    tooltips.apply(act, "hole_wizard")
    act.triggered.connect(lambda _=False: open_panel(window))
    window._hole_wizard_act = act
    return act


def open_panel(window):
    panel = getattr(window, "_hole_panel", None)
    if panel is None:
        panel = window._hole_panel = HolePanel(window)
    panel.show()
    panel.raise_()
    panel.arm()
    return panel


def _make_panel_class():
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox,
                                 QFormLayout, QHBoxLayout, QLabel,
                                 QPushButton, QVBoxLayout)

    class HolePanel(QDialog):
        """The wizard's settings beside the model; while open, clicks on
        faces drill holes."""

        def __init__(self, window):
            super().__init__(window, Qt.Tool)
            self.window_ = window
            self.setWindowTitle(language.tr("Hole Wizard"))
            lay = QVBoxLayout(self)
            form = QFormLayout()
            self.type = QComboBox()
            self.type.addItems([language.tr(t) for t in TYPES])
            self.size = QComboBox()
            self.size.addItems(SIZES)
            self.size.setCurrentText(DEFAULT["size"])
            self.fit = QComboBox()
            self.fit.addItems([language.tr(f) for f in FITS])
            self.fit.setCurrentIndex(1)
            self.end = QComboBox()
            self.end.addItems([language.tr(e) for e in ENDS])
            self.depth = QDoubleSpinBox()
            self.depth.setRange(0.1, 10000)
            self.depth.setValue(DEFAULT["depth"])
            self.depth.setSuffix(" mm")
            self.depth.setEnabled(False)
            self.end.currentIndexChanged.connect(
                lambda i: self.depth.setEnabled(i == 1))
            form.addRow(language.tr("Type"), self.type)
            form.addRow(language.tr("Size"), self.size)
            form.addRow(language.tr("Fit"), self.fit)
            form.addRow(language.tr("End"), self.end)
            form.addRow(language.tr("Depth"), self.depth)
            lay.addLayout(form)
            self.info = QLabel()
            self.info.setWordWrap(True)
            lay.addWidget(self.info)
            row = QHBoxLayout()
            upd = QPushButton(language.tr("Update selected"))
            upd.setToolTip(language.tr("Re-size every hole of the selected "
                                       "hole feature to these settings"))
            upd.clicked.connect(self.update_selected)
            done = QPushButton(language.tr("Done"))
            done.clicked.connect(self.close)
            row.addWidget(upd)
            row.addStretch()
            row.addWidget(done)
            lay.addLayout(row)
            for w in (self.type, self.size, self.fit, self.end):
                w.currentIndexChanged.connect(self._describe)
            self.depth.valueChanged.connect(self._describe)
            self._describe()

        def spec(self):
            return dict(type=TYPES[self.type.currentIndex()],
                        size=self.size.currentText(),
                        fit=FITS[self.fit.currentIndex()],
                        end=ENDS[self.end.currentIndex()],
                        depth=float(self.depth.value()))

        def _describe(self, *_):
            p = spec_params(self.spec(), through=None)
            text = language.tr("{title}: Ø{d:g} mm").format(
                title=title(self.spec()), d=p["diameter"])
            if "head_diameter" in p and p["kind"] != "plain":
                text += language.tr(", head Ø{h:g}").format(
                    h=p["head_diameter"])
            self.info.setText(text + "\n" + language.tr(
                "Click a face of a part to drill — one hole per click."))

        def arm(self):
            from . import meshedit_ui
            win = self.window_
            parts = meshedit_ui._parts(win)
            if not parts:
                win.statusBar().showMessage(language.tr(
                    "No part to drill — add a solid first."), 6000)
                return
            win.view3d.start_pick(
                self._picked, groups=parts,
                banner=language.tr("Click a face to drill a hole · Esc "
                                   "or Done finishes"),
                labeler=lambda desc, node: "%s · %s" % (
                    getattr(node, "name", ""), title(self.spec())))

        def _picked(self, desc, node):
            win = self.window_
            if desc is None or node is None:
                self.close()
                return
            if desc.get("kind") not in ("face", "edge"):
                self.arm()
                return
            from . import round_ui
            part = round_ui.solid_of(win, node)
            scope = win._render_scope()[0]
            feature = add_hole(win.model, part, desc["pos"], desc["dir"],
                               self.spec(), scope=scope)
            win.statusBar().showMessage(language.tr(
                "{title} drilled — click another face, or Esc").format(
                title=feature.name), 5000)
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, self.arm)        # stays armed

        def update_selected(self):
            win = self.window_
            nodes = win.builder.active_tree().selected_nodes()
            features = []
            for n in nodes:
                probe = n
                while probe is not None and KEY not in probe.params:
                    probe = probe.parent
                if probe is not None and probe not in features:
                    features.append(probe)
            if not features:
                win.statusBar().showMessage(language.tr(
                    "Select a hole feature in the tree first."), 5000)
                return
            for f in features:
                update(win.model, f, self.spec())

        def closeEvent(self, event):
            view = self.window_.view3d
            if getattr(view, "_pick_cb", None) is not None:
                view.cancel_pick()
            super().closeEvent(event)

    return HolePanel


class _Lazy:
    cls = None


def HolePanel(window):                                # noqa: N802
    if _Lazy.cls is None:
        _Lazy.cls = _make_panel_class()
    return _Lazy.cls(window)


def run_mcp(window, params):
    """MCP `hole_wizard`: drill holes at world points on a part's face
    (normal = the face's outward normal, from probe_surface), or
    re-size a feature (action update)."""
    model = window.model
    spec = {k: params[k] for k in ("type", "size", "fit", "end", "depth")
            if k in params}
    bad = [v for k, v in spec.items() if k in ("type", "size", "fit",
                                                "end")
           and v not in dict(type=TYPES, size=SIZES, fit=FITS,
                             end=ENDS)[k]]
    if bad:
        raise ValueError("Unknown choice %r (type %s; size %s; fit %s; "
                         "end %s)." % (bad[0], TYPES, SIZES, FITS, ENDS))
    node = model.find(int(params["node_id"]))
    if node is None:
        raise ValueError("No node with id %r." % params["node_id"])
    if params.get("action") == "update":
        feature = node
        while feature is not None and KEY not in feature.params:
            feature = feature.parent
        if feature is None:
            raise ValueError("%s is not in a hole feature." % node.name)
        update(model, feature, dict(feature.params[KEY], **spec))
    else:
        points = params.get("points") or []
        if not points:
            raise ValueError("Give points [[x, y, z], ...] on the face.")
        normal = params.get("normal") or [0, 0, 1]
        scope = window._render_scope()[0]
        feature = None
        for pt in points:
            feature = add_hole(model, node, pt, normal, spec, scope=scope)
    return dict(feature_id=feature.id, name=feature.name,
                spec=feature.params[KEY],
                holes=[h.id for h in feature.walk() if h.type == "hole"],
                hole=spec_params(feature.params[KEY]))
