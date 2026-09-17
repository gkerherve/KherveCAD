"""X-ray sources for XPS: a detailed twin-anode source and focusing
monochromators on a Rowland circle, for the Part Library.

A monochromator (XM1000 / µ-FOCUS 600 / MX650 class) is laid out from
its geometry: the sample, the ellipsoidal quartz crystal and the anode
all sit on the Rowland circle. Al Kα reflects off quartz (10-10) at the
Bragg angle θB = 78.5°, so the crystal lies D = d·sin θB from the sample
along the port axis (d the circle's diameter) and the anode D from the
crystal, turned 2·(90° − θB) = 23° off that axis. What is drawn: the
exit nozzle into the chamber, the exit tube to the crystal housing (its
drum, viewport, crystal and the three adjusting micrometers on the back
plate), the tube back to the anode housing with its HV connector,
cooling water, a small ion pump and valve, and the support struts.

Port-mounted like every part here: CF sealing face at z = 0 looking
down, the sample *reach* below it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .library import CF_SIZES, KF_SIZES, _cyl, _kf_flange_head, _micrometer, \
    bellows, cf_flange
from .library_manip import _bag, _box, _hcyl_x, _objects, _scale
from .library_uhv import (COPPER, GLASS, HOSE_BLUE, HOSE_RED, _blank_mount,
                          _mount, _open_mount, between)
from .library_vacuum import (_around, _cube, _entry, _group, _move, _object,
                             _paint, _ring, _turn, _union)
from .model import CadNode

CATEGORY = "Vacuum"
BRAGG = 78.5            # Al Kα on quartz (10-10), degrees
QUARTZ = "#efe8f4"
FOIL = "#dfe3e8"


def _hose(name, points, colour, r=4.0):
    """A cooling-water hose along a polyline."""
    runs = [between(name, r, a, b, segments=16)
            for a, b in zip(points, points[1:])]
    joints = [CadNode("sphere", "Bend", dict(x=p[0], y=p[1], z=p[2],
                                             radius=r, segments=16))
              for p in points[1:-1]]
    return _object(name, _paint(_union(name, *runs, *joints), colour,
                                "Rubber"))


def _hv_connector(name, x, y, z, tilt=0.0, r=9.0):
    """A high-voltage cable connector with its cable boot, leaning *tilt*
    degrees from +Z towards +X."""
    body = _union(name, _cyl("Connector nut", r, 18.0, segments=6),
                  _cyl("Connector body", r * 0.8, 30.0, z=18.0, segments=32),
                  _cyl("Cable boot", r * 0.55, 40.0, z=48.0, r2=r * 0.35,
                       segments=24))
    return _move(_turn(body, y=tilt), x, y, z)


# ── twin anode source, in detail ────────────────────────────────────

TWIN_SIZES = {
    "Twin anode Al/Mg, 400 W (CF40)": dict(mount="CF40 (DN40)",
                                           reach=110.0, lift=50.0),
    "Twin anode Al/Ag, 600 W (CF63)": dict(mount="CF63 (DN63)",
                                           reach=120.0, lift=50.0),
}


def build_twin_source(dims):
    """A water-cooled twin-anode X-ray source: in vacuum the shroud and
    its thin aluminium window 15 mm from the sample; outside a linear
    retraction (bellows between two plates, three guide rods, a drive
    screw with handwheel and a scale), the head housing with the anode
    HV and filament connectors, the water fittings and hoses, and a KF16
    differential pumping port."""
    e = _entry(TWIN_SIZES, dims, "Twin anode Al/Mg, 400 W (CF40)")
    p = _mount(e, dims)
    t, fr = p["thickness"], p["flange_od"] / 2.0
    R, lift = float(e["reach"]), float(e["lift"])
    r = min(p["bore"] / 2.0 - 1.5, 22.0)
    tip = -(R - 15.0)
    bag = _bag()
    bag["steel"] += [_blank_mount(p),
                     _cyl("Shroud", r, -tip - 14.0, z=tip + 14.0,
                          segments=64),
                     _cyl("Window cap", r * 0.6, 14.0, z=tip, r2=r,
                          segments=64),
                     _move(bellows(r * 0.8, 6.0, lift, 10), z=t + 10.0)]
    bag["alu"] += [_cyl("Lower plate", fr, 10.0, z=t, segments=96),
                   _cyl("Upper plate", fr, 14.0, z=t + 10.0 + lift,
                        segments=96)]
    for k in range(3):
        a = math.radians(90.0 + 120.0 * k)
        x, y = (fr - 8.0) * math.cos(a), (fr - 8.0) * math.sin(a)
        bag["steel"] += [_cyl("Guide rod", 4.0, lift + 40.0, x=x, y=y, z=t,
                              segments=16),
                         _cyl("Bushing", 7.0, 20.0, x=x, y=y,
                              z=t + 7.0 + lift, segments=24)]
    bag["dark"].append(_cyl("Retraction handwheel", 20.0, 10.0,
                            x=fr - 8.0, z=t + lift + 24.0, segments=48))
    _scale(bag, 0.0, -fr - 2.0, t, lift + 24.0, step=5.0)
    zh = t + lift + 24.0
    bag["alu"] += [_cyl("Head housing", 32.0, 110.0, z=zh, segments=96),
                   _ring("Label band", 32.0, 33.0, 20.0, z=zh + 40.0)]
    bag["steel"] += [_cyl("Head cap", 34.0, 10.0, z=zh + 110.0, segments=96),
                     _hcyl_x("Pump port tube", 8.0, 30.0, -62.0, 0.0,
                             zh + 20.0, 24),
                     _move(_turn(_kf_flange_head(KF_SIZES["KF16 (DN16)"],
                                                 "KF16 pump port"), y=-90.0),
                           -62.0, 0.0, zh + 20.0)]
    for k, zz in enumerate((zh + 70.0, zh + 90.0)):
        bag["steel"].append(_move(_turn(_cyl("Water fitting", 6.0, 14.0,
                                             segments=6), y=90.0),
                                  32.0, -10.0 + 20.0 * k, zz))
    extra = [
        _object("Anode HV connector", _paint(
            _hv_connector("HV connector", 10.0, 0.0, zh + 120.0, 20.0),
            "#1d1f22", "Plastic")),
        _object("Filament connector", _paint(
            _hv_connector("Filament connector", -14.0, 8.0, zh + 120.0,
                          -15.0, r=6.0), "#1d1f22", "Plastic")),
        _object("Window foil", _paint(_cyl("Al window", r * 0.58, 0.3,
                                           z=tip - 0.3, segments=48),
                                      FOIL)),
        _hose("Water in", [(46.0, -10.0, zh + 70.0), (70.0, -10.0,
                                                      zh + 70.0),
                           (70.0, -10.0, zh + 250.0)], HOSE_BLUE),
        _hose("Water out", [(46.0, 10.0, zh + 90.0), (84.0, 10.0,
                                                     zh + 90.0),
                            (84.0, 10.0, zh + 250.0)], HOSE_RED)]
    return _objects("Twin-anode X-ray source", bag, extra)


# ── monochromator ───────────────────────────────────────────────────

MONO_SIZES = {
    "Rowland Ø500 mm, Al Kα (XM1000 class, CF63)": dict(
        mount="CF63 (DN63)", rowland=500.0, reach=160.0, drum=100.0),
    "Rowland Ø600 mm, Al Kα (µ-FOCUS 600 class, CF63)": dict(
        mount="CF63 (DN63)", rowland=600.0, reach=170.0, drum=110.0),
    "Rowland Ø650 mm, Al Kα (MX650 class, CF100)": dict(
        mount="CF100 (DN100)", rowland=650.0, reach=180.0, drum=120.0),
}


def geometry(rowland, reach):
    """(crystal, anode) positions in the part's frame for a Rowland
    circle of diameter *rowland* with the sample *reach* below the
    face."""
    D = rowland * math.sin(math.radians(BRAGG))
    two_a = math.radians(2.0 * (90.0 - BRAGG))
    crystal = (0.0, 0.0, D - reach)
    anode = (D * math.sin(two_a), 0.0, crystal[2] - D * math.cos(two_a))
    return crystal, anode


def build_monochromator(dims):
    """A focusing quartz-crystal monochromator on a Rowland circle."""
    e = _entry(MONO_SIZES, dims, "Rowland Ø500 mm, Al Kα (XM1000 class, "
                                 "CF63)")
    p = _mount(e, dims)
    t, fr = p["thickness"], p["flange_od"] / 2.0
    R, drum = float(e["reach"]), float(e["drum"])
    crystal, anode = geometry(float(e["rowland"]), R)
    cz = crystal[2]
    # the anode sits outside the chamber: slide it up the Rowland circle
    # until its housing clears the mount flange (a real one mounts the
    # sample lower in the chamber for the same reason)
    ax, az = anode[0], anode[2]
    for _i in range(8):
        n = math.hypot(ax, az - cz) or 1.0
        low = az + 150.0 * (az - cz) / n - 90.0
        if low >= t + 40.0:
            break
        az += t + 40.0 - low
    bag = _bag()
    rt = p["tube_od"] / 2.0
    bag["steel"] += [
        _open_mount(p),
        _group("difference", "Exit nozzle",
               _cyl("Nozzle", 7.0, R - 30.0, z=-(R - 30.0),
                    r2=p["bore"] / 2.0 * 0.8, segments=64),
               _cyl("Nozzle bore", 4.0, R, z=-R, r2=p["bore"] / 2.0 * 0.7,
                    segments=48)),
        _cyl("Exit tube", rt, cz - drum - t + 5.0, z=t, segments=96),
        _move(cf_flange(p, "Exit tube flange"), z=cz - drum - p["thickness"]),
        # the crystal drum lies along Y
        _move(_turn(_cyl("Crystal drum", drum, drum * 1.3, z=-drum * 0.65,
                         segments=128), x=90.0), 0.0, 0.0, cz),
        _box("Back plate", -drum * 0.8, -drum * 0.6, cz + drum - 8.0,
             drum * 1.6, drum * 1.2, 14.0),
        between("Anode tube", 21.0, (ax * 0.12, 0.0, cz - drum * 0.9),
                (ax, 0.0, az + 40.0), segments=64)]
    for k, (x, y) in enumerate(((-drum * 0.55, -drum * 0.35),
                                (drum * 0.55, -drum * 0.35),
                                (0.0, drum * 0.4))):
        bag["steel"].append(_move(_turn(_micrometer(
            "Crystal adjuster", 60.0, 7.0), y=-90.0), x, y, cz + drum + 6.0))
    vp = dict(CF_SIZES["CF40 (DN40)"])
    bag["steel"].append(_move(_turn(cf_flange(vp, "Viewport flange"),
                                    x=-90.0), 0.0, drum * 0.65, cz))
    # anode housing and its services, on from the anode away from the
    # crystal (u), the HV connector and water at its far end
    A = (ax, 0.0, az)
    dx, dz = ax - 0.0, az - cz
    n = math.hypot(dx, dz) or 1.0
    u = (dx / n, 0.0, dz / n)
    E = tuple(A[i] + 150.0 * u[i] for i in range(3))
    bag["alu"] += [between("Anode housing", 40.0, A, E, segments=96),
                   between("Housing flange", 52.0, A,
                           tuple(A[i] + 14.0 * u[i] for i in range(3)),
                           segments=96)]
    ex, ez = E[0], E[2]
    bag["dark"] += [_box("Ion pump body", ex + 30.0, -35.0, ez, 60.0, 70.0,
                         110.0),
                    _box("Magnet", ex + 30.0, -48.0, ez + 10.0, 60.0, 13.0,
                         90.0),
                    _box("Magnet", ex + 30.0, 35.0, ez + 10.0, 60.0, 13.0,
                         90.0)]
    bag["steel"] += [between("Pump neck", 12.0, (ex - 10.0, 0.0, ez + 40.0),
                             (ex + 30.0, 0.0, ez + 55.0)),
                     _cube("Valve", 26.0, 26.0, 26.0, x=ex, y=-60.0,
                           z=ez + 30.0),
                     between("Support strut", 8.0, (fr * 0.95, 0.0, t + 5.0),
                             (drum * 0.7, 0.0, cz - drum * 0.4)),
                     between("Support strut", 8.0, (-fr * 0.95, 0.0, t + 5.0),
                             (-drum * 0.7, 0.0, cz - drum * 0.4)),
                     between("Anode strut", 6.0, (rt, 0.0, (t + cz) * 0.4),
                             (ax - 30.0, 0.0, az + 20.0))]
    hz = ez
    quartz = _move(_turn(_cyl("Quartz crystal", drum * 0.45, 12.0,
                              segments=96), x=180.0), 0.0, 0.0,
                   cz + drum * 0.55)
    extra = [
        _object("Quartz crystal", _paint(quartz, QUARTZ, "Glass",
                                         alpha=0.8)),
        _object("Viewport glass", _paint(_move(_turn(_cyl(
            "Viewport glass", vp["bore"] / 2.0, 3.0, segments=48), x=-90.0),
            0.0, drum * 0.65 + vp["thickness"], cz), GLASS, "Glass",
            alpha=0.45)),
        _object("Anode HV connector", _paint(_hv_connector(
            "HV connector", ex, 0.0, hz - 90.0, 0.0), "#1d1f22", "Plastic")),
        _object("Anode (copper)", _paint(between(
            "Anode block", 16.0, A, tuple(A[i] - 30.0 * u[i]
                                          for i in range(3))), COPPER)),
        _hose("Water in", [(ex - 30.0, -14.0, hz), (ex - 80.0, -14.0, hz),
                           (ex - 80.0, -14.0, hz + 250.0)], HOSE_BLUE),
        _hose("Water out", [(ex - 30.0, 14.0, hz + 10.0),
                            (ex - 94.0, 14.0, hz + 10.0),
                            (ex - 94.0, 14.0, hz + 250.0)], HOSE_RED)]
    return _objects("X-ray monochromator", bag, extra)


# ── registration ────────────────────────────────────────────────────

def _spec(label, build, sizes, fields=()):
    return dict(label=label, category=CATEGORY, sizes=sizes,
                fields=list(fields), build=build)


PARTS = {
    "xray_twin": _spec("X-ray source, twin anode (detailed)",
                       build_twin_source, TWIN_SIZES,
                       [("reach", "Reach into chamber"),
                        ("lift", "Retraction")]),
    "xray_mono": _spec("X-ray monochromator (Rowland circle)",
                       build_monochromator, MONO_SIZES,
                       [("rowland", "Rowland circle Ø"),
                        ("reach", "Reach into chamber"),
                        ("drum", "Crystal drum radius")]),
}
