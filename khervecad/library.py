"""Parts library — parametric vacuum hardware built from tree nodes.

CF (ConFlat) and KF (Quick Flange) flanges, straight nipples, tees
and crosses in the conventional sizes, plus a simplified turbo pump
shell. Every part is generated as an ordinary node subtree (cylinders,
booleans and a for-loop for the bolt circle), so inserted parts stay
fully editable and the generated OpenSCAD reads like a human wrote
it. Dimensions are editable before insertion — any size works, the
tables only pre-fill the standard ones.

Dimensions are simplified (no knife edges or o-ring grooves) but
follow the conventional envelope sizes in millimetres.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                             QDoubleSpinBox, QFormLayout, QHBoxLayout,
                             QLabel, QListWidget, QSpinBox, QVBoxLayout)

from .model import CadNode, DocumentModel

#: CF (ConFlat) conventional sizes, mm.
CF_SIZES = {
    "CF16 (DN16)": dict(flange_od=34.0, thickness=7.5,
                        bolt_circle=27.0, bolts=6, bolt_hole=4.4,
                        bore=16.0, tube_od=19.1),
    "CF40 (DN40)": dict(flange_od=69.9, thickness=12.7,
                        bolt_circle=58.7, bolts=6, bolt_hole=6.6,
                        bore=35.0, tube_od=38.1),
    "CF63 (DN63)": dict(flange_od=114.3, thickness=17.5,
                        bolt_circle=92.1, bolts=8, bolt_hole=8.4,
                        bore=60.0, tube_od=63.5),
    "CF100 (DN100)": dict(flange_od=152.4, thickness=20.0,
                          bolt_circle=130.3, bolts=16, bolt_hole=8.4,
                          bore=97.0, tube_od=101.6),
    "CF160 (DN160)": dict(flange_od=203.2, thickness=22.3,
                          bolt_circle=181.0, bolts=20, bolt_hole=8.4,
                          bore=147.0, tube_od=152.4),
}

#: KF (Quick Flange / QF) conventional sizes, mm.
KF_SIZES = {
    "KF16 (DN16)": dict(flange_od=30.0, thickness=5.0, bore=16.0,
                        tube_od=20.0),
    "KF25 (DN25)": dict(flange_od=40.0, thickness=5.0, bore=24.0,
                        tube_od=28.0),
    "KF40 (DN40)": dict(flange_od=55.0, thickness=5.0, bore=38.0,
                        tube_od=44.5),
    "KF50 (DN50)": dict(flange_od=75.0, thickness=6.5, bore=50.0,
                        tube_od=57.0),
}

#: port directions as rotate([x, y, z]) mapping +Z to the port axis.
_PORTS = {
    "+X": (0.0, 90.0, 0.0), "-X": (0.0, -90.0, 0.0),
    "+Y": (-90.0, 0.0, 0.0), "-Y": (90.0, 0.0, 0.0),
    "+Z": (0.0, 0.0, 0.0), "-Z": (180.0, 0.0, 0.0),
}


def _cyl(name, radius, height, z=0.0, x=0.0, y=0.0, r2=None,
         segments=96):
    return CadNode("cylinder", name, dict(
        x=x, y=y, z=z, height=height, radius_bottom=radius,
        radius_top=radius if r2 is None else r2,
        segments=segments, center=False))


def _bolt_holes(p, z, height):
    """A for-loop of bolt holes around the bolt circle."""
    bolts = max(int(p["bolts"]), 1)
    step = 360.0 / bolts
    loop = CadNode("for_loop", "Bolt holes", dict(
        variable="a", start=0.0, end=360.0 - step / 2, step=step))
    rot = CadNode("rotate", "Around axis", dict(x=0.0, y=0.0, z="a"))
    rot.add(_cyl("Bolt hole", p["bolt_hole"] / 2.0, height,
                 z=z, x=p["bolt_circle"] / 2.0, segments=24))
    loop.add(rot)
    return loop


# ------------------------------------------------------------- flanges

def cf_flange(p, name="CF flange", tube_length=0.0) -> CadNode:
    """A ConFlat flange: disc + optional tube stub, bore and bolt
    circle subtracted."""
    solid = CadNode("union", f"{name} solid")
    solid.add(_cyl("Flange disc", p["flange_od"] / 2.0,
                   p["thickness"]))
    total = p["thickness"] + tube_length
    if tube_length > 0:
        solid.add(_cyl("Tube stub", p["tube_od"] / 2.0, tube_length,
                       z=p["thickness"]))
    part = CadNode("difference", name)
    part.add(solid)
    part.add(_cyl("Bore", p["bore"] / 2.0, total + 2.0, z=-1.0))
    part.add(_bolt_holes(p, z=-1.0, height=p["thickness"] + 2.0))
    return part


def kf_flange(p, name="KF flange", tube_length=20.0) -> CadNode:
    """A KF flange: chamfered clamp disc + tube, bore subtracted."""
    solid = CadNode("union", f"{name} solid")
    # clamp profile: short cone into the disc (simplified)
    solid.add(_cyl("Clamp face", p["flange_od"] / 2.0,
                   p["thickness"] * 0.6))
    solid.add(CadNode("cylinder", "Clamp taper", dict(
        x=0.0, y=0.0, z=p["thickness"] * 0.6,
        height=p["thickness"] * 0.4,
        radius_bottom=p["flange_od"] / 2.0,
        radius_top=p["tube_od"] / 2.0, segments=96, center=False)))
    if tube_length > 0:
        solid.add(_cyl("Tube", p["tube_od"] / 2.0, tube_length,
                       z=p["thickness"]))
    part = CadNode("difference", name)
    part.add(solid)
    part.add(_cyl("Bore", p["bore"] / 2.0,
                  p["thickness"] + tube_length + 2.0, z=-1.0))
    return part


# ---------------------------------------------------------- fittings

def cf_fitting(p, ports, name="CF fitting",
               port_length=60.0) -> CadNode:
    """A multi-port CF fitting (nipple / tee / cross): one flanged
    tube per port direction, all bores meeting at the centre."""
    part = CadNode("difference", name)
    solid = CadNode("union", f"{name} body")
    part.add(solid)
    for port in ports:
        rx, ry, rz = _PORTS[port]
        frame = CadNode("rotate", f"Port {port}",
                        dict(x=rx, y=ry, z=rz))
        frame.add(_cyl("Tube", p["tube_od"] / 2.0, port_length))
        frame.add(_cyl("Flange disc", p["flange_od"] / 2.0,
                       p["thickness"],
                       z=port_length - p["thickness"]))
        solid.add(frame)
    for port in ports:
        rx, ry, rz = _PORTS[port]
        frame = CadNode("rotate", f"Bore {port}",
                        dict(x=rx, y=ry, z=rz))
        frame.add(_cyl("Bore", p["bore"] / 2.0, port_length + 1.0,
                       z=-1.0))
        part.add(frame)
    for port in ports:
        rx, ry, rz = _PORTS[port]
        frame = CadNode("rotate", f"Bolts {port}",
                        dict(x=rx, y=ry, z=rz))
        frame.add(_bolt_holes(p, z=port_length - p["thickness"] - 1.0,
                              height=p["thickness"] + 2.0))
        part.add(frame)
    return part


# ------------------------------------------------------------ turbo pump

def turbo_pump(inlet=None, exhaust=None, body_height=110.0,
               body_od=120.0) -> CadNode:
    """A simplified turbo pump shell: CF inlet flange on top of a
    cylindrical body, conical lower housing, KF exhaust port and a
    base collar."""
    inlet = inlet or CF_SIZES["CF100 (DN100)"]
    exhaust = exhaust or KF_SIZES["KF25 (DN25)"]
    part = CadNode("difference", "Turbo pump (simplified)")
    solid = CadNode("union", "Pump body")
    part.add(solid)

    # main body with the inlet flange on top
    solid.add(_cyl("Body", body_od / 2.0, body_height))
    solid.add(_cyl("Inlet flange", inlet["flange_od"] / 2.0,
                   inlet["thickness"], z=body_height))
    # conical lower housing + motor/electronics collar
    solid.add(CadNode("cylinder", "Lower cone", dict(
        x=0.0, y=0.0, z=-30.0, height=30.0,
        radius_bottom=body_od * 0.35, radius_top=body_od / 2.0,
        segments=96, center=False)))
    solid.add(_cyl("Base collar", body_od * 0.42, 16.0, z=-46.0))
    # exhaust: KF tube + clamp flange sticking out in +X near the base
    exhaust_frame = CadNode("rotate", "Exhaust port",
                            dict(x=0.0, y=90.0, z=0.0))
    exhaust_len = body_od / 2.0 + 28.0
    exhaust_frame.add(CadNode("translate", "At base height",
                              dict(x=0.0, y=0.0, z=0.0)))
    tube = _cyl("Exhaust tube", exhaust["tube_od"] / 2.0, exhaust_len)
    tube.params["y"] = 0.0
    exhaust_frame.children[0].add(tube)
    exhaust_frame.children[0].add(
        _cyl("Exhaust flange", exhaust["flange_od"] / 2.0,
             exhaust["thickness"], z=exhaust_len))
    exhaust_lift = CadNode("translate", "Exhaust",
                           dict(x=0.0, y=0.0, z=-20.0))
    exhaust_lift.add(exhaust_frame)
    solid.add(exhaust_lift)

    # inlet bore with a simple rotor hub hinted inside
    part.add(_cyl("Inlet bore", inlet["bore"] / 2.0,
                  inlet["thickness"] + 42.0,
                  z=body_height - 40.0))
    part.add(_bolt_holes(inlet, z=body_height - 1.0,
                         height=inlet["thickness"] + 2.0))
    # exhaust bore
    ex_bore_frame = CadNode("translate", "Exhaust bore lift",
                            dict(x=0.0, y=0.0, z=-20.0))
    ex_rot = CadNode("rotate", "Exhaust bore", dict(x=0.0, y=90.0,
                                                    z=0.0))
    ex_rot.add(_cyl("Bore", exhaust["bore"] / 2.0, exhaust_len + 2.0,
                    z=body_od / 4.0))
    ex_bore_frame.add(ex_rot)
    part.add(ex_bore_frame)

    hub = CadNode("cylinder", "Rotor hub", dict(
        x=0.0, y=0.0, z=body_height - 38.0, height=30.0,
        radius_bottom=inlet["bore"] * 0.18,
        radius_top=inlet["bore"] * 0.10, segments=48, center=False))
    result = CadNode("union", "Turbo pump")
    result.add(part)
    result.add(hub)
    return result


# ----------------------------------------------------------------- parts

#: part id -> (label, size table or None, builder kwargs schema)
PARTS = {
    "cf_flange": ("CF flange (bored, with tube stub)", CF_SIZES),
    "cf_blank": ("CF blank flange (no tube)", CF_SIZES),
    "cf_nipple": ("CF nipple (straight tube)", CF_SIZES),
    "cf_tee": ("CF tee (3 ports)", CF_SIZES),
    "cf_cross": ("CF cross (4 ports)", CF_SIZES),
    "kf_flange": ("KF flange (with tube)", KF_SIZES),
    "turbo": ("Turbo pump shell (simplified)", None),
}

#: editable dimensions per size-table family.
_CF_FIELDS = [("flange_od", "Flange OD"), ("thickness", "Thickness"),
              ("bolt_circle", "Bolt circle Ø"), ("bolts", "Bolt count"),
              ("bolt_hole", "Bolt hole Ø"), ("bore", "Bore Ø"),
              ("tube_od", "Tube OD"), ("port_length", "Port length")]
_KF_FIELDS = [("flange_od", "Flange OD"), ("thickness", "Thickness"),
              ("bore", "Bore Ø"), ("tube_od", "Tube OD"),
              ("port_length", "Tube length")]


def build_part(part_id: str, dims: dict) -> CadNode:
    """Build the requested part from (possibly customised) *dims*."""
    p = dict(dims)
    length = p.pop("port_length", 60.0)
    if part_id == "cf_flange":
        return cf_flange(p, tube_length=max(length - p["thickness"],
                                            0.0))
    if part_id == "cf_blank":
        blank = dict(p)
        blank["bore"] = 0.0
        part = CadNode("difference", "CF blank flange")
        solid = CadNode("union", "Blank solid")
        solid.add(_cyl("Flange disc", p["flange_od"] / 2.0,
                       p["thickness"]))
        part.add(solid)
        part.add(_bolt_holes(p, z=-1.0, height=p["thickness"] + 2.0))
        return part
    if part_id == "cf_nipple":
        return cf_fitting(p, ["+Z", "-Z"], "CF nipple", length)
    if part_id == "cf_tee":
        return cf_fitting(p, ["+X", "-X", "+Z"], "CF tee", length)
    if part_id == "cf_cross":
        return cf_fitting(p, ["+X", "-X", "+Z", "-Z"], "CF cross",
                          length)
    if part_id == "kf_flange":
        return kf_flange(p, tube_length=max(length - p["thickness"],
                                            0.0))
    if part_id == "turbo":
        return turbo_pump()
    raise ValueError(f"unknown part: {part_id}")


# ---------------------------------------------------------------- dialog

class PartLibraryDialog(QDialog):
    """Insert > Part Library: pick a part, a standard size, tweak the
    dimensions, insert into the document."""

    def __init__(self, model: DocumentModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("Part library")
        self.resize(560, 420)

        self._parts = QListWidget()
        for part_id, (label, _sizes) in PARTS.items():
            self._parts.addItem(label)
        self._parts.setCurrentRow(0)
        self._parts.currentRowChanged.connect(self._part_changed)

        self._size = QComboBox()
        self._size.currentTextChanged.connect(self._size_changed)

        self._form = QFormLayout()
        self._fields = {}

        right = QVBoxLayout()
        right.addWidget(QLabel("Standard size:"))
        right.addWidget(self._size)
        right.addLayout(self._form)
        right.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                   | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Insert")
        buttons.accepted.connect(self._insert)
        buttons.rejected.connect(self.reject)
        right.addWidget(buttons)

        layout = QHBoxLayout(self)
        layout.addWidget(self._parts, 1)
        layout.addLayout(right, 1)
        self._part_changed(0)

    # ------------------------------------------------------------ state
    def _part_id(self):
        return list(PARTS)[self._parts.currentRow()]

    def _part_changed(self, _row):
        part_id = self._part_id()
        sizes = PARTS[part_id][1]
        self._size.blockSignals(True)
        self._size.clear()
        if sizes:
            self._size.addItems(list(sizes))
            default = 1 if len(sizes) > 1 else 0
            self._size.setCurrentIndex(default)
        self._size.setEnabled(bool(sizes))
        self._size.blockSignals(False)
        self._rebuild_form()

    def _size_changed(self, _text):
        self._load_size()

    def _rebuild_form(self):
        while self._form.count():
            item = self._form.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._fields.clear()
        part_id = self._part_id()
        sizes = PARTS[part_id][1]
        if not sizes:
            self._form.addRow(QLabel("Built-in dimensions "
                                     "(CF100 inlet, KF25 exhaust)"))
            return
        fields = _CF_FIELDS if sizes is CF_SIZES else _KF_FIELDS
        for key, label in fields:
            if key == "bolts":
                box = QSpinBox()
                box.setRange(1, 64)
            else:
                box = QDoubleSpinBox()
                box.setRange(0.0, 2000.0)
                box.setDecimals(2)
                box.setSuffix(" mm")
            self._fields[key] = box
            self._form.addRow(label, box)
        self._load_size()

    def _load_size(self):
        part_id = self._part_id()
        sizes = PARTS[part_id][1]
        if not sizes or not self._fields:
            return
        dims = dict(sizes.get(self._size.currentText(),
                              next(iter(sizes.values()))))
        dims.setdefault("port_length",
                        60.0 if sizes is CF_SIZES else 30.0)
        for key, box in self._fields.items():
            if key in dims:
                box.setValue(dims[key])

    # ------------------------------------------------------------ insert
    def _insert(self):
        part_id = self._part_id()
        dims = {key: box.value() for key, box in self._fields.items()}
        node = build_part(part_id, dims)
        size = self._size.currentText().split(" ")[0] \
            if self._size.isEnabled() else ""
        if size:
            node.name = f"{size} {node.name}" \
                if not node.name.startswith(size) else node.name
        self.model.root.add(node)
        self.model.structure_changed.emit()
        self.inserted = node
        self.accept()
