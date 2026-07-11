"""Parts library — parametric vacuum hardware built from tree nodes.

CF (ConFlat) and KF (Quick Flange) flanges, straight nipples, tees
and crosses in the conventional sizes, threaded fasteners (hex bolts,
socket head cap screws and hex nuts with real helical ISO threads),
plus a simplified turbo pump shell. Every part is generated as an
ordinary node subtree, so inserted parts stay fully editable and the
generated OpenSCAD reads like a human wrote it. Dimensions are
editable before insertion — any size works, the tables only pre-fill
the standard ones.

CF flanges are modelled from the manufacturer cross-section drawings
(Kurt J. Lesker / VACGen style): the whole flange is one revolved
profile with the recessed sealing face, the **knife edge** at the
gasket seal diameter, the gasket seat wall and the edge chamfers —
then the bolt circle is subtracted with a for-loop.

Threads use the OpenSCAD twist-extrude idiom: a thread-form
cross-section (root flat, 60° flanks, crest flat between the minor
and major radii) extruded with ``twist = -360 * length / pitch``
yields a true single-start helical V-thread. Nuts subtract the same
solid with clearance, so nuts really thread onto their bolts.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                             QDoubleSpinBox, QFormLayout, QHBoxLayout,
                             QLabel, QListWidget, QSpinBox, QVBoxLayout)

from .model import CadNode, DocumentModel

#: CF (ConFlat) conventional sizes, mm (gasket_od = copper gasket
#: outer diameter, which locates the knife edge and the recess).
CF_SIZES = {
    "CF16 (DN16)": dict(flange_od=34.0, thickness=7.5,
                        bolt_circle=27.0, bolts=6, bolt_hole=4.4,
                        bore=16.0, tube_od=19.1, gasket_od=21.3),
    "CF40 (DN40)": dict(flange_od=69.9, thickness=12.7,
                        bolt_circle=58.7, bolts=6, bolt_hole=6.6,
                        bore=35.0, tube_od=38.1, gasket_od=48.3),
    "CF63 (DN63)": dict(flange_od=114.3, thickness=17.5,
                        bolt_circle=92.1, bolts=8, bolt_hole=8.4,
                        bore=60.0, tube_od=63.5, gasket_od=82.6),
    "CF100 (DN100)": dict(flange_od=152.4, thickness=20.0,
                          bolt_circle=130.3, bolts=16, bolt_hole=8.4,
                          bore=97.0, tube_od=101.6, gasket_od=120.7),
    "CF160 (DN160)": dict(flange_od=203.2, thickness=22.3,
                          bolt_circle=181.0, bolts=20, bolt_hole=8.4,
                          bore=147.0, tube_od=152.4, gasket_od=171.5),
}

#: ISO metric coarse fasteners, mm (DIN 933 hex head / DIN 912 socket
#: head / DIN 934 nut). af = across flats, socket = hex key size.
BOLT_SIZES = {
    "M3": dict(d=3.0, pitch=0.5, af=5.5, head_h=2.0, socket=2.5,
               nut_h=2.4, length=12.0),
    "M4": dict(d=4.0, pitch=0.7, af=7.0, head_h=2.8, socket=3.0,
               nut_h=3.2, length=16.0),
    "M5": dict(d=5.0, pitch=0.8, af=8.0, head_h=3.5, socket=4.0,
               nut_h=4.0, length=20.0),
    "M6": dict(d=6.0, pitch=1.0, af=10.0, head_h=4.0, socket=5.0,
               nut_h=5.0, length=20.0),
    "M8": dict(d=8.0, pitch=1.25, af=13.0, head_h=5.3, socket=6.0,
               nut_h=6.5, length=25.0),
    "M10": dict(d=10.0, pitch=1.5, af=17.0, head_h=6.4, socket=8.0,
                nut_h=8.0, length=30.0),
    "M12": dict(d=12.0, pitch=1.75, af=19.0, head_h=7.5, socket=10.0,
                nut_h=10.0, length=40.0),
    "M16": dict(d=16.0, pitch=2.0, af=24.0, head_h=10.0, socket=14.0,
                nut_h=13.0, length=50.0),
    "M20": dict(d=20.0, pitch=2.5, af=30.0, head_h=12.5, socket=17.0,
                nut_h=16.0, length=60.0),
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


# -------------------------------------------------------------- threads

#: ISO 60-degree thread form as fractions of one pitch around the
#: cross-section: root flat, rising flank, crest flat, falling flank.
_THREAD_FORM = (0.25, 0.3125, 0.125, 0.3125)


def thread_profile(d_major: float, pitch: float, n: int = 72):
    """Cross-section polygon for a twist-extruded helical thread: a
    circle whose radius traces the ISO thread form (minor radius at
    the root, 60° flanks, flat crest at the major radius) once around.
    Extruded with twist = -360*L/pitch this sweeps a true V-thread."""
    depth = 0.6134 * pitch                    # ISO: 5H/8 engagement
    r_minor = d_major / 2.0 - depth
    root, rise, crest, fall = _THREAD_FORM

    def radius(u):
        if u < root:
            return r_minor
        u -= root
        if u < rise:
            return r_minor + depth * (u / rise)
        u -= rise
        if u < crest:
            return d_major / 2.0
        u -= crest
        return d_major / 2.0 - depth * (u / fall)
    return [[round(radius(i / n) * math.cos(2 * math.pi * i / n), 4),
             round(radius(i / n) * math.sin(2 * math.pi * i / n), 4)]
            for i in range(n)]


def thread_solid(d: float, pitch: float, length: float,
                 clearance: float = 0.0, name: str = "Thread") -> CadNode:
    """A threaded cylinder: thread-form polygon + twisted extrusion.
    *clearance* grows the major diameter (for the hole in a nut)."""
    turns = length / pitch
    ext = CadNode("linear_extrude", name, dict(
        height=length, twist=round(-360.0 * turns, 2), scale=1.0,
        center=False, segments=max(int(turns * 8), 16)))
    ext.add(CadNode("polygon", f"{name} profile", dict(
        x=0.0, y=0.0,
        points=thread_profile(d + 2.0 * clearance, pitch))))
    return ext


def _hex(name, af, height, z=0.0):
    """Hexagonal prism: a 6-segment cylinder with the circumradius
    that gives *af* across flats."""
    return _cyl(name, round(af / math.sqrt(3.0), 3), height, z=z,
                segments=6)


def hex_bolt(p, length: float) -> CadNode:
    """DIN 933 style hex head bolt, fully threaded."""
    part = CadNode("union", "Hex bolt")
    part.add(thread_solid(p["d"], p["pitch"], length))
    part.add(_hex("Hex head", p["af"], p["head_h"], z=length))
    return part


def socket_screw(p, length: float) -> CadNode:
    """DIN 912 style socket head cap screw with hex socket."""
    part = CadNode("difference", "Socket head screw")
    solid = CadNode("union", "Screw body")
    solid.add(thread_solid(p["d"], p["pitch"], length))
    solid.add(_cyl("Cap head", 0.75 * p["d"], p["d"], z=length,
                   segments=48))
    part.add(solid)
    part.add(_hex("Hex socket", p["socket"], 0.6 * p["d"] + 1.0,
                  z=length + 0.4 * p["d"]))
    return part


def hex_nut(p) -> CadNode:
    """DIN 934 style hex nut — the threaded hole is the bolt thread
    subtracted with clearance, so it really mates."""
    part = CadNode("difference", "Hex nut")
    part.add(_hex("Nut body", p["af"], p["nut_h"]))
    hole = CadNode("translate", "Thread hole", dict(x=0.0, y=0.0,
                                                    z=-1.0))
    hole.add(thread_solid(p["d"], p["pitch"], p["nut_h"] + 2.0,
                          clearance=0.15, name="Internal thread"))
    part.add(hole)
    return part


# ------------------------------------------------------------- flanges

#: CF sealing face constants (from manufacturer drawings), mm.
_CF_RECESS_DEPTH = 1.6       # sealing-face counterbore depth
_CF_KNIFE_HEIGHT = 1.1       # knife edge rise above the recess floor
_CF_KNIFE_SETBACK = 0.9      # knife tip radius inside the gasket OD
_CF_SEAT_CLEARANCE = 0.3     # recess wall outside the gasket OD
_CF_CHAMFER = 1.0            # outer edge chamfers


def cf_profile(p, tube_length: float = 0.0):
    """The revolved cross-section of a ConFlat flange, as (radius, z)
    points — the same view a Lesker/VACGen drawing shows. z = 0 is
    the flange back, z = thickness the sealing face; the tube extends
    below z = 0. Features, from the bore outward: recess floor, the
    knife edge (70° ridge at the gasket seal diameter), recess wall
    (gasket seat) and chamfered outer edge."""
    r_od = p["flange_od"] / 2.0
    t = p["thickness"]
    r_bore = max(p["bore"], 0.0) / 2.0
    r_tube = p["tube_od"] / 2.0
    r_seat = p["gasket_od"] / 2.0 + _CF_SEAT_CLEARANCE
    r_knife = p["gasket_od"] / 2.0 - _CF_KNIFE_SETBACK
    floor = t - _CF_RECESS_DEPTH
    tip = floor + _CF_KNIFE_HEIGHT
    half_base = _CF_KNIFE_HEIGHT * math.tan(math.radians(35.0))
    cham = min(_CF_CHAMFER, t / 4.0)

    points = [(r_bore, floor)]               # bore meets the recess
    if tube_length > 0 and r_tube > r_bore:
        points += [(r_bore, -tube_length), (r_tube, -tube_length),
                   (r_tube, 0.0)]
    else:
        points += [(r_bore, 0.0)]
    points += [
        (r_od - cham, 0.0), (r_od, cham),     # back edge chamfer
        (r_od, t - cham), (r_od - cham, t),   # face edge chamfer
        (r_seat, t),                          # face in to the recess
        (r_seat, floor),                      # gasket seat wall
        (r_knife + half_base, floor),         # floor to the knife
        (r_knife, tip),                       # knife edge tip
        (r_knife - half_base, floor),         # back to the floor
    ]
    return [[round(x, 4), round(z, 4)] for x, z in points]


def cf_flange_solid(p, tube_length: float = 0.0,
                    name: str = "CF flange") -> CadNode:
    """The revolved (knife-edged) flange body without bolt holes."""
    revolve = CadNode("rotate_extrude", f"{name} revolve",
                      dict(angle=360.0, segments=128))
    revolve.add(CadNode("polygon", f"{name} profile", dict(
        x=0.0, y=0.0, points=cf_profile(p, tube_length))))
    return revolve


def cf_flange(p, name="CF flange", tube_length=0.0) -> CadNode:
    """A ConFlat flange with the true sealing geometry — recessed
    face, knife edge, gasket seat — and the bolt circle subtracted."""
    part = CadNode("difference", name)
    part.add(cf_flange_solid(p, tube_length, name))
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
        lift = CadNode("translate", "Flange position", dict(
            x=0.0, y=0.0, z=port_length - p["thickness"]))
        lift.add(cf_flange_solid(p, 0.0, f"Flange {port}"))
        frame.add(lift)
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

#: editable dimensions per family.
_CF_FIELDS = [("flange_od", "Flange OD"), ("thickness", "Thickness"),
              ("bolt_circle", "Bolt circle Ø"), ("bolts", "Bolt count"),
              ("bolt_hole", "Bolt hole Ø"), ("bore", "Bore Ø"),
              ("tube_od", "Tube OD"), ("gasket_od", "Gasket OD"),
              ("port_length", "Port length")]
_KF_FIELDS = [("flange_od", "Flange OD"), ("thickness", "Thickness"),
              ("bore", "Bore Ø"), ("tube_od", "Tube OD"),
              ("port_length", "Tube length")]
_BOLT_FIELDS = [("d", "Thread Ø"), ("pitch", "Pitch"),
                ("length", "Length"), ("af", "Across flats"),
                ("head_h", "Head height")]
_SCREW_FIELDS = [("d", "Thread Ø"), ("pitch", "Pitch"),
                 ("length", "Length"), ("socket", "Hex key size")]
_NUT_FIELDS = [("d", "Thread Ø"), ("pitch", "Pitch"),
               ("af", "Across flats"), ("nut_h", "Thickness")]

#: part id -> label, size table, editable fields.
PARTS = {
    "cf_flange": dict(label="CF flange (knife edge, tube stub)",
                      sizes=CF_SIZES, fields=_CF_FIELDS),
    "cf_blank": dict(label="CF blank flange (knife edge)",
                     sizes=CF_SIZES, fields=_CF_FIELDS),
    "cf_nipple": dict(label="CF nipple (straight tube)",
                      sizes=CF_SIZES, fields=_CF_FIELDS),
    "cf_tee": dict(label="CF tee (3 ports)", sizes=CF_SIZES,
                   fields=_CF_FIELDS),
    "cf_cross": dict(label="CF cross (4 ports)", sizes=CF_SIZES,
                     fields=_CF_FIELDS),
    "kf_flange": dict(label="KF flange (with tube)", sizes=KF_SIZES,
                      fields=_KF_FIELDS),
    "bolt_hex": dict(label="Hex bolt, threaded (DIN 933)",
                     sizes=BOLT_SIZES, fields=_BOLT_FIELDS),
    "bolt_socket": dict(label="Socket head cap screw (DIN 912)",
                        sizes=BOLT_SIZES, fields=_SCREW_FIELDS),
    "nut_hex": dict(label="Hex nut, threaded (DIN 934)",
                    sizes=BOLT_SIZES, fields=_NUT_FIELDS),
    "turbo": dict(label="Turbo pump shell (simplified)", sizes=None,
                  fields=[]),
}


def build_part(part_id: str, dims: dict) -> CadNode:
    """Build the requested part from (possibly customised) *dims*."""
    p = dict(dims)
    length = p.pop("port_length", 60.0)
    if part_id in ("bolt_hex", "bolt_socket", "nut_hex"):
        defaults = dict(BOLT_SIZES["M6"])
        defaults.update(p)
        p = defaults
    if part_id == "cf_flange":
        return cf_flange(p, tube_length=max(length - p["thickness"],
                                            0.0))
    if part_id == "cf_blank":
        blank = dict(p)
        blank["bore"] = 0.0
        return cf_flange(blank, "CF blank flange", tube_length=0.0)
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
    if part_id == "bolt_hex":
        return hex_bolt(p, p["length"])
    if part_id == "bolt_socket":
        return socket_screw(p, p["length"])
    if part_id == "nut_hex":
        return hex_nut(p)
    if part_id == "turbo":
        return turbo_pump()
    raise ValueError(f"unknown part: {part_id}")


# ---------------------------------------------------------------- dialog

class PartLibraryDialog(QDialog):
    """Insert > Part Library: pick a part, a standard size, tweak the
    dimensions, insert into the document. Non-modal — it stays open
    while you keep working in the main window."""

    part_inserted = pyqtSignal(object)        # the inserted CadNode

    def __init__(self, model: DocumentModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("Part library")
        self.setModal(False)
        self.resize(560, 420)

        self._parts = QListWidget()
        for part_id, spec in PARTS.items():
            self._parts.addItem(spec["label"])
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

        buttons = QDialogButtonBox(QDialogButtonBox.Apply
                                   | QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Apply).setText("Insert")
        buttons.button(QDialogButtonBox.Apply).setDefault(True)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(
            self._insert)
        buttons.rejected.connect(self.close)
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
        sizes = PARTS[part_id]["sizes"]
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
        spec = PARTS[part_id]
        if not spec["sizes"]:
            self._form.addRow(QLabel("Built-in dimensions "
                                     "(CF100 inlet, KF25 exhaust)"))
            return
        for key, label in spec["fields"]:
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
        sizes = PARTS[part_id]["sizes"]
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
        self.part_inserted.emit(node)
