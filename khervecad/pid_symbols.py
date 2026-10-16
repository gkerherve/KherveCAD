"""P&ID symbols (Qt-free): ISO 10628 / ISA-5.1 graphics as primitives.

Every symbol is drawn about its own centre in sheet millimetres (y
DOWN, like the Blueprint) by a function returning primitives —
("line", kind, a, b), ("poly", kind, pts, closed, fill),
("circle", kind, c, r, fill), ("arc", kind, c, r, start, sweep) and
("text", kind, at, value, size, align, valign) — the same tuples the
window paints and the DXF exporter writes, so screen, PDF and CAD agree.
Kinds: "main" (equipment outline, 0.5 mm), "thin" (0.25 mm), "dash"
(a signal), "text".

`SYMBOLS[kind]` = Symbol(label, group, w, h, ports, draw, prefix):
*ports* {name: (x, y, direction)} with direction one of "l" "r" "u" "d"
— the way a pipe leaves that port; *prefix* the tag letters a new
symbol of that kind is numbered with (P-101, V-201, PT-301…).
`transform` turns a symbol's points and port directions by its
rotation (0/90/180/270) and mirror.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
from dataclasses import dataclass, field


# ── primitives ─────────────────────────────────────────────────────

def L(a, b, kind="main"):
    return ("line", kind, (float(a[0]), float(a[1])),
            (float(b[0]), float(b[1])))


def P(pts, kind="main", closed=True, fill=False):
    return ("poly", kind, [(float(x), float(y)) for x, y in pts],
            bool(closed), bool(fill))


def C(c, r, kind="main", fill=False):
    return ("circle", kind, (float(c[0]), float(c[1])), float(r), fill)


def A(c, r, start, sweep, kind="main"):
    return ("arc", kind, (float(c[0]), float(c[1])), float(r),
            float(start), float(sweep))


def T(value, at, size=2.5, align="center", valign="middle", kind="text"):
    return ("text", kind, (float(at[0]), float(at[1])), str(value),
            float(size), align, valign)


@dataclass
class Symbol:
    label: str
    group: str
    w: float
    h: float
    ports: dict
    draw: object
    prefix: str = ""
    #: fields its Properties show besides tag and label
    fields: tuple = ()
    description: str = ""
    extra: dict = field(default_factory=dict)


SYMBOLS = {}
GROUPS = ("Equipment", "Heat transfer", "Vessels & tanks", "Valves",
          "Actuated valves", "Safety", "Instruments", "Fittings & misc")


def _sym(kind, label, group, w, h, ports, prefix="", fields=(),
         description=""):
    def deco(fn):
        SYMBOLS[kind] = Symbol(label, group, w, h, ports, fn, prefix,
                               fields, description)
        return fn
    return deco


# two-port in-line items share their ports
_LR = {"in": (-6.0, 0.0, "l"), "out": (6.0, 0.0, "r")}


def _bowtie(s=5.0, fill=False):
    return [P([(-s, -s * 0.7), (s, s * 0.7), (s, -s * 0.7),
               (-s, s * 0.7)], fill=fill)]


def _stem(top=-7.0):
    return [L((0, 0), (0, top), "thin")]


# ── equipment ──────────────────────────────────────────────────────

@_sym("pump", "Centrifugal pump", "Equipment", 14, 14,
      {"in": (-7.0, 0.0, "l"), "out": (0.0, -7.0, "u")}, "P",
      ("flow", "head", "power"), "Circulating / centrifugal pump")
def _pump():
    return [C((0, 0), 6), L((0, -6), (6, -6)),
            P([(-3, -3.5), (-3, 3.5), (4, 0)], "thin", fill=False),
            L((-7, 0), (-6, 0)), L((0, -6), (0, -7))]


@_sym("pump_inline", "In-line circulator", "Equipment", 14, 12,
      {"in": (-7.0, 0.0, "l"), "out": (7.0, 0.0, "r")}, "P",
      ("flow", "head", "power"), "Wet-rotor circulator in the pipe")
def _pump_inline():
    return [C((0, 0), 5.5), P([(-3, -3.2), (-3, 3.2), (3.5, 0)], "thin"),
            L((-7, 0), (-5.5, 0)), L((5.5, 0), (7, 0))]


@_sym("compressor", "Compressor", "Equipment", 16, 16,
      {"suction": (-8.0, 0.0, "l"), "discharge": (8.0, 0.0, "r")}, "C",
      ("power", "refrigerant"), "Rotary / scroll refrigerant compressor")
def _compressor():
    return [C((0, 0), 7), L((-6.6, -2.4), (6.2, -3.8)),
            L((-6.6, 2.4), (6.2, 3.8)), L((-8, 0), (-7, 0)),
            L((7, 0), (8, 0))]


@_sym("fan", "Fan / blower", "Equipment", 16, 16,
      {"in": (-8.0, 0.0, "l"), "out": (8.0, 0.0, "r")}, "F",
      ("flow", "power"), "Axial or centrifugal fan")
def _fan():
    out = [C((0, 0), 7)]
    for a in (0, 120, 240):
        r = math.radians(a)
        tip = (5.5 * math.cos(r), 5.5 * math.sin(r))
        side = (3.0 * math.cos(r + 0.9), 3.0 * math.sin(r + 0.9))
        out.append(P([(0, 0), tip, side], "thin", fill=True))
    return out


@_sym("motor", "Electric motor", "Equipment", 12, 12,
      {"shaft": (6.0, 0.0, "r")}, "M", ("power",))
def _motor():
    return [C((0, 0), 5.5), T("M", (0, 0.2), 4.0)]


@_sym("controller", "Controller / panel", "Equipment", 22, 14,
      {"l": (-11.0, 0.0, "l"), "r": (11.0, 0.0, "r"),
       "u": (0.0, -7.0, "u"), "d": (0.0, 7.0, "d")}, "UC",
      ("function",), "Heat pump controller, PLC, thermostat panel")
def _controller():
    return [P([(-11, -7), (11, -7), (11, 7), (-11, 7)]),
            L((-11, -3.5), (11, -3.5), "thin")]


@_sym("heater", "Electric heater", "Equipment", 16, 10,
      {"l": (-8.0, 0.0, "l"), "r": (8.0, 0.0, "r")}, "H", ("power",),
      "Immersion / back-up heater")
def _heater():
    pts = [(-6 + i * 1.5, (-2.5 if i % 2 else 2.5)) for i in range(9)]
    return [P([(-8, -5), (8, -5), (8, 5), (-8, 5)]),
            P(pts, "thin", closed=False)]


# ── heat transfer ──────────────────────────────────────────────────

@_sym("plate_hx", "Plate heat exchanger", "Heat transfer", 14, 22,
      {"a_in": (-7.0, -8.0, "l"), "a_out": (-7.0, 8.0, "l"),
       "b_in": (7.0, 8.0, "r"), "b_out": (7.0, -8.0, "r")}, "E",
      ("duty", "plates"), "Brazed plate heat exchanger (condenser)")
def _plate_hx():
    out = [P([(-7, -11), (7, -11), (7, 11), (-7, 11)])]
    for k in range(-3, 4):
        y = k * 2.8
        out.append(L((-7, y - 1.4), (7, y + 1.4), "thin"))
    return out


@_sym("shell_tube", "Shell and tube exchanger", "Heat transfer", 28, 12,
      {"shell_in": (-8.0, -6.0, "u"), "shell_out": (8.0, 6.0, "d"),
       "tube_in": (-14.0, 0.0, "l"), "tube_out": (14.0, 0.0, "r")}, "E",
      ("duty",))
def _shell_tube():
    return [P([(-12, -6), (12, -6), (12, 6), (-12, 6)]),
            L((-14, 0), (-12, 0)), L((12, 0), (14, 0)),
            P([(-12, 0), (-8, -3), (-4, 3), (0, -3), (4, 3), (8, -3),
               (12, 0)], "thin", closed=False)]


@_sym("coil", "Finned coil (evaporator)", "Heat transfer", 26, 16,
      {"in": (-13.0, 6.0, "l"), "out": (-13.0, -6.0, "l")}, "E",
      ("duty", "area"), "Air coil: evaporator, condenser, air cooler")
def _coil():
    out = [P([(-11, -8), (11, -8), (11, 8), (-11, 8)])]
    pts = [(-13, 6), (-9, 6)]
    y = 6
    for i in range(5):
        x = 9 if i % 2 == 0 else -9
        pts += [(x, y), (x, y - 3)]
        y -= 3
    pts += [(-13, -6)]
    out.append(P(pts, "thin", closed=False))
    for x in range(-8, 10, 3):
        out.append(L((x, -8), (x + 1.5, -6.5), "thin"))
    return out


@_sym("radiator", "Radiator", "Heat transfer", 24, 12,
      {"flow": (-12.0, 4.0, "l"), "return": (12.0, 4.0, "r")}, "RAD",
      ("output",), "Panel radiator / emitter")
def _radiator():
    out = [P([(-10, -6), (10, -6), (10, 6), (-10, 6)])]
    for x in range(-7, 9, 3):
        out.append(L((x, -6), (x, 6), "thin"))
    out += [L((-12, 4), (-10, 4)), L((10, 4), (12, 4))]
    return out


@_sym("ufh", "Underfloor heating loop", "Heat transfer", 26, 14,
      {"flow": (-13.0, -5.0, "l"), "return": (-13.0, 5.0, "l")}, "UFH",
      ("area", "output"))
def _ufh():
    pts = [(-13, -5), (10, -5), (10, -2), (-8, -2), (-8, 1), (10, 1),
           (10, 4), (-6, 4), (-6, 5), (-13, 5)]
    return [P([(-11, -7), (12, -7), (12, 7), (-11, 7)], "thin"),
            P(pts, "main", closed=False)]


# ── vessels & tanks ────────────────────────────────────────────────

def _ellipse_cap(cx, cy, rx, ry, up, kind="main", n=12):
    pts = []
    for i in range(n + 1):
        a = math.pi * i / n
        pts.append((cx - rx * math.cos(a),
                    cy - ry * math.sin(a) * (1 if up else -1)))
    return P(pts, kind, closed=False)


def _vessel(w, h, kind="main"):
    rx, ry = w / 2.0, w / 4.0
    top, bot = -h / 2.0 + ry, h / 2.0 - ry
    return [L((-rx, top), (-rx, bot), kind), L((rx, top), (rx, bot), kind),
            _ellipse_cap(0, top, rx, ry, True, kind),
            _ellipse_cap(0, bot, rx, ry, False, kind)]


@_sym("tank", "Vertical tank / buffer", "Vessels & tanks", 20, 36,
      {"top": (0.0, -18.0, "u"), "bottom": (0.0, 18.0, "d"),
       "l_hi": (-10.0, -9.0, "l"), "l_lo": (-10.0, 9.0, "l"),
       "r_hi": (10.0, -9.0, "r"), "r_lo": (10.0, 9.0, "r")}, "TK",
      ("volume",), "Buffer tank, storage, low-loss header")
def _tank():
    return _vessel(20, 36)


@_sym("cylinder", "Hot water cylinder (coil)", "Vessels & tanks", 22, 40,
      {"coil_in": (-11.0, 4.0, "l"), "coil_out": (-11.0, 14.0, "l"),
       "cold_in": (11.0, 16.0, "r"), "hot_out": (0.0, -20.0, "u"),
       "drain": (0.0, 20.0, "d"), "r_hi": (11.0, -8.0, "r")}, "CYL",
      ("volume", "coil_area"), "Indirect unvented cylinder with coil")
def _cylinder():
    out = _vessel(22, 40)
    out.append(P([(-11, 4), (6, 5), (-8, 7), (6, 9), (-8, 11), (6, 13),
                  (-11, 14)], "thin", closed=False))
    return out


@_sym("expansion_vessel", "Expansion vessel", "Vessels & tanks", 14, 18,
      {"conn": (0.0, 9.0, "d")}, "EXP", ("volume", "precharge"),
      "Diaphragm expansion vessel")
def _expansion_vessel():
    out = _vessel(12, 15)
    out[0] = ("line", "main", (-6.0, -4.5), (-6.0, 4.5))
    out.append(L((-6, 0.5), (6, 0.5), "thin"))
    out.append(L((0, 7.5), (0, 9)))
    return out


@_sym("accumulator", "Suction accumulator", "Vessels & tanks", 12, 22,
      {"in": (0.0, -11.0, "u"), "out": (6.0, 7.0, "r")}, "ACC",
      ("volume",))
def _accumulator():
    return _vessel(12, 22) + [L((-6, 2), (6, 2), "dash")]


@_sym("receiver", "Liquid receiver", "Vessels & tanks", 26, 12,
      {"in": (-6.0, -6.0, "u"), "out": (6.0, 6.0, "d")}, "RCV",
      ("volume",))
def _receiver():
    return [P([(-9, -6), (9, -6)], closed=False), P([(-9, 6), (9, 6)],
                                                     closed=False),
            ("arc", "main", (-9.0, 0.0), 6.0, 90.0, 180.0),
            ("arc", "main", (9.0, 0.0), 6.0, 270.0, 180.0)]


# ── valves ─────────────────────────────────────────────────────────

@_sym("gate_valve", "Gate valve", "Valves", 12, 10, dict(_LR), "V",
      ("size",))
def _gate():
    return _bowtie() + [L((-6, 0), (-5, 0)), L((5, 0), (6, 0))]


@_sym("globe_valve", "Globe valve", "Valves", 12, 10, dict(_LR), "V",
      ("size",))
def _globe():
    return _bowtie() + [C((0, 0), 1.3, fill=True)]


@_sym("ball_valve", "Ball valve (isolation)", "Valves", 12, 10, dict(_LR),
      "V", ("size",), "Lever ball valve")
def _ball():
    return _bowtie() + [C((0, 0), 2.2)]


@_sym("butterfly_valve", "Butterfly valve", "Valves", 12, 10, dict(_LR),
      "V", ("size",))
def _butterfly():
    return [L((-5, -3.5), (-5, 3.5)), L((5, -3.5), (5, 3.5)),
            L((-6, 0), (6, 0), "thin"), L((-2.5, 3.5), (2.5, -3.5)),
            C((0, 0), 1.0, fill=True)]


@_sym("check_valve", "Check valve (non-return)", "Valves", 12, 10,
      dict(_LR), "NRV", ("size",), "Flow left to right only")
def _check():
    return [P([(-5, -3.5), (5, 0), (-5, 3.5)]), L((5, -3.5), (5, 3.5)),
            L((-6, 0), (-5, 0))]


@_sym("needle_valve", "Needle / regulating valve", "Valves", 12, 10,
      dict(_LR), "V", ("size",))
def _needle():
    return _bowtie() + [L((0, 0), (0, -6), "thin"),
                        P([(-1.5, -4), (1.5, -4), (0, -1)], "thin",
                          fill=True)]


@_sym("three_way_valve", "Three-way valve", "Valves", 12, 12,
      {"a": (-6.0, 0.0, "l"), "b": (6.0, 0.0, "r"),
       "ab": (0.0, 6.0, "d")}, "V", ("size",))
def _three_way():
    return [P([(-5, -3.5), (0, 0), (-5, 3.5)]),
            P([(5, -3.5), (0, 0), (5, 3.5)]),
            P([(-3.5, 5), (0, 0), (3.5, 5)])]


@_sym("four_way_valve", "Four-way reversing valve", "Valves", 16, 16,
      {"d": (0.0, -8.0, "u"), "s": (0.0, 8.0, "d"),
       "c": (8.0, 0.0, "r"), "e": (-8.0, 0.0, "l")}, "RV",
      ("mode",), "Refrigerant reversing valve: heating / defrost")
def _four_way():
    return [P([(-6, -6), (6, -6), (6, 6), (-6, 6)]),
            P([(0, -6), (4, -2)], "thin", closed=False),
            P([(-6, 0), (-2, 4), (0, 6)], "thin", closed=False),
            P([(2.6, -3.6), (4, -2), (2.2, -1.6)], "thin", fill=True),
            T("RV", (0, 1.8), 2.2)]


@_sym("drain_cock", "Drain cock", "Valves", 10, 10,
      {"in": (0.0, -5.0, "u")}, "DC", ("size",))
def _drain():
    return [P([(-3, -2.5), (3, 2.5), (3, -2.5), (-3, 2.5)]),
            L((0, -5), (0, -2.5)), L((3, 0), (5, 2.5), "thin")]


# ── actuated valves ────────────────────────────────────────────────

def _actuator_m():
    return [L((0, 0), (0, -6), "thin"), C((0, -8.5), 2.6),
            T("M", (0, -8.4), 2.4)]


@_sym("motorised_valve", "Motorised valve (2-port)", "Actuated valves",
      12, 18, dict(_LR), "MV", ("size", "signal"),
      "Zone valve with an electric actuator")
def _motorised():
    return _bowtie() + _actuator_m()


@_sym("diverter_valve", "Motorised diverter (3-port)", "Actuated valves",
      12, 20, {"a": (-6.0, 0.0, "l"), "b": (6.0, 0.0, "r"),
               "ab": (0.0, 6.0, "d")}, "DV", ("size", "signal"),
      "Hot water / heating diverter")
def _diverter():
    return _three_way() + _actuator_m()


@_sym("solenoid_valve", "Solenoid valve", "Actuated valves", 12, 18,
      dict(_LR), "SV", ("size", "voltage"))
def _solenoid():
    return _bowtie() + [L((0, 0), (0, -5), "thin"),
                        P([(-2.5, -5), (2.5, -5), (2.5, -10),
                           (-2.5, -10)]), T("S", (0, -7.5), 2.4)]


@_sym("control_valve", "Control valve (diaphragm)", "Actuated valves",
      12, 18, dict(_LR), "CV", ("size", "signal"))
def _control():
    return _bowtie() + [L((0, 0), (0, -5), "thin"),
                        ("arc", "main", (0.0, -5.0), 4.0, 0.0, 180.0),
                        L((-4, -5), (4, -5))]


@_sym("expansion_valve", "Electronic expansion valve", "Actuated valves",
      12, 18, dict(_LR), "EEV", ("size",),
      "Stepper-driven refrigerant expansion valve")
def _eev():
    return _bowtie() + [L((0, 0), (0, -5), "thin"),
                        P([(-3, -5), (3, -5), (3, -10), (-3, -10)]),
                        L((-3, -10), (3, -5), "thin")]


@_sym("txv", "Thermostatic expansion valve", "Actuated valves", 14, 18,
      dict(_LR), "TXV", ("size",), "With its sensing bulb")
def _txv():
    return _bowtie() + [L((0, 0), (0, -5), "thin"),
                        ("arc", "main", (0.0, -5.0), 3.5, 0.0, 180.0),
                        L((-3.5, -5), (3.5, -5)),
                        L((3, -7), (8, -7), "dash"),
                        P([(8, -8.5), (11, -8.5), (11, -5.5), (8, -5.5)],
                          "thin")]


# ── safety ─────────────────────────────────────────────────────────

@_sym("relief_valve", "Pressure relief / safety valve", "Safety", 14, 16,
      {"in": (0.0, 8.0, "d"), "out": (7.0, 0.0, "r")}, "PRV",
      ("set_pressure",), "Spring-loaded safety valve, angle pattern")
def _relief():
    zig = [(0, -1)] + [((-2 if i % 2 else 2), -2 - i * 1.2)
                       for i in range(5)] + [(0, -8.5)]
    return [P([(-3.5, 5), (3.5, 5), (0, 0)]),
            P([(5, -3.5), (5, 3.5), (0, 0)]), L((0, 5), (0, 8)),
            L((5, 0), (7, 0)), P(zig, "thin", closed=False)]


@_sym("pressure_switch", "Pressure switch", "Safety", 12, 12,
      {"pv": (0.0, 6.0, "d")}, "PS", ("set_pressure",))
def _pswitch():
    return [C((0, 0), 5), L((0, 5), (0, 6))]


@_sym("bursting_disc", "Bursting disc", "Safety", 10, 10,
      {"in": (0.0, 5.0, "d"), "out": (0.0, -5.0, "u")}, "BD", ())
def _disc():
    return [L((-4, 0), (4, 0)), ("arc", "main", (0.0, 2.0), 4.0, 30.0,
                                  120.0), L((0, -5), (0, 5), "thin")]


# ── instruments (ISA bubbles) ──────────────────────────────────────

def _bubble(panel=False):
    out = [C((0, 0), 5.0), L((0, 5), (0, 7), "thin")]
    if panel:
        out.append(L((-5, 0), (5, 0), "thin"))
    return out


@_sym("instrument", "Instrument (field)", "Instruments", 12, 14,
      {"pv": (0.0, 7.0, "d")}, "TI", ("range",),
      "ISA bubble: letters (TI, PT, FS…) and loop number")
def _instrument():
    return _bubble()


@_sym("instrument_panel", "Instrument (panel)", "Instruments", 12, 14,
      {"pv": (0.0, 7.0, "d")}, "TIC", ("range",),
      "Shown on the control panel / BMS")
def _instrument_panel():
    return _bubble(True)


@_sym("pressure_gauge", "Pressure gauge", "Instruments", 12, 14,
      {"pv": (0.0, 7.0, "d")}, "PI", ("range",))
def _gauge():
    return [C((0, 0), 5.0), L((0, 5), (0, 7)), L((0, 0), (3, -3), "thin"),
            C((0, 0), 0.8, fill=True)]


@_sym("thermometer", "Thermometer", "Instruments", 12, 14,
      {"pv": (0.0, 7.0, "d")}, "TI", ("range",))
def _thermometer():
    return [P([(-1, -6), (1, -6), (1, 2), (-1, 2)], "thin"),
            C((0, 3.5), 2.0, fill=True), L((0, 5.5), (0, 7))]


@_sym("temperature_sensor", "Temperature sensor (well)", "Instruments",
      12, 14, {"pv": (0.0, 7.0, "d")}, "TE", ("type",))
def _tsensor():
    return [C((0, 0), 5.0), L((0, 5), (0, 7))]


@_sym("flow_switch", "Flow switch", "Instruments", 12, 14,
      {"pv": (0.0, 7.0, "d")}, "FS", ("set_flow",))
def _flowswitch():
    return [C((0, 0), 5.0), L((0, 5), (0, 7))]


@_sym("flow_meter", "Flow / heat meter", "Instruments", 14, 10,
      dict(_LR), "FQ", ("range",))
def _flowmeter():
    return [P([(-5, -4), (5, -4), (5, 4), (-5, 4)]), C((0, 0), 2.5),
            L((-6, 0), (-5, 0)), L((5, 0), (6, 0))]


@_sym("sight_glass", "Sight glass", "Instruments", 12, 10, dict(_LR),
      "SG", ())
def _sight():
    return [C((0, 0), 4.0), C((0, 0), 2.0, "thin"), L((-6, 0), (-4, 0)),
            L((4, 0), (6, 0))]


# ── fittings & misc ────────────────────────────────────────────────

@_sym("strainer", "Y-strainer", "Fittings & misc", 12, 10, dict(_LR),
      "STR", ("mesh",))
def _strainer():
    return [L((-6, 0), (6, 0)), P([(-2, 0), (2, 5), (4, 3), (0, -2)]),
            L((0.5, 1.5), (3, 4), "thin")]


@_sym("filter", "Filter", "Fittings & misc", 12, 10, dict(_LR), "FLT",
      ("rating",))
def _filter():
    return [P([(-4, -4), (4, -4), (4, 4), (-4, 4)]),
            L((-4, -4), (4, 4), "dash"), L((-6, 0), (-4, 0)),
            L((4, 0), (6, 0))]


@_sym("magnetic_filter", "Magnetic filter", "Fittings & misc", 12, 14,
      dict(_LR), "MF", ())
def _magfilter():
    return [C((0, 0), 4.5), T("M", (0, 0.3), 3.0), L((-6, 0), (-4.5, 0)),
            L((4.5, 0), (6, 0))]


@_sym("filter_drier", "Filter drier", "Fittings & misc", 16, 8,
      {"in": (-8.0, 0.0, "l"), "out": (8.0, 0.0, "r")}, "FD", ())
def _drier():
    out = [P([(-5, -3), (5, -3), (5, 3), (-5, 3)]), L((-8, 0), (-5, 0)),
           L((5, 0), (8, 0))]
    for x in (-3, -1, 1, 3):
        out.append(L((x - 1, 3), (x + 1, -3), "thin"))
    return out


@_sym("air_vent", "Automatic air vent", "Fittings & misc", 10, 12,
      {"in": (0.0, 6.0, "d")}, "AAV", ())
def _airvent():
    return [P([(-3, -1), (3, -1), (3, 4), (-3, 4)]),
            P([(-2, -1), (0, -5), (2, -1)], "thin"), L((0, 4), (0, 6))]


@_sym("filling_loop", "Filling loop", "Fittings & misc", 20, 10,
      {"in": (-10.0, 0.0, "l"), "out": (10.0, 0.0, "r")}, "FL", ())
def _fillloop():
    return [L((-10, 0), (-6, 0)), P([(-6, -3), (-2, 3), (-2, -3),
                                     (-6, 3)]),
            ("arc", "thin", (0.0, 0.0), 3.0, 0.0, 180.0),
            P([(2, -3), (6, 3), (6, -3), (2, 3)]), L((6, 0), (10, 0))]


@_sym("reducer", "Reducer", "Fittings & misc", 10, 10, dict(_LR), "", ())
def _reducer():
    return [P([(-4, -4), (4, -2), (4, 2), (-4, 4)]), L((-6, 0), (-4, 0)),
            L((4, 0), (6, 0))]


@_sym("flexible", "Flexible connection", "Fittings & misc", 12, 8,
      dict(_LR), "", ())
def _flex():
    pts = [(-6, 0)] + [(-4 + i * 2, (-2 if i % 2 else 2)) for i in
                       range(5)] + [(6, 0)]
    return [P(pts, "main", closed=False)]


@_sym("tundish", "Tundish / discharge", "Fittings & misc", 10, 12,
      {"in": (0.0, -6.0, "u"), "out": (0.0, 6.0, "d")}, "TD", ())
def _tundish():
    return [P([(-4, -3), (4, -3), (1, 2), (-1, 2)]), L((0, -6), (0, -4)),
            L((0, 2), (0, 6))]


@_sym("off_page", "Off-page connector", "Fittings & misc", 22, 8,
      {"p": (-11.0, 0.0, "l")}, "", ("to",),
      "Where a line leaves the sheet (label = destination)")
def _offpage():
    return [P([(-11, -4), (7, -4), (11, 0), (7, 4), (-11, 4)])]


@_sym("boundary", "Equipment boundary", "Fittings & misc", 60, 40,
      {}, "", (), "Dash-dot box round a skid / package (monobloc unit)")
def _boundary():
    return [P([(-30, -20), (30, -20), (30, 20), (-30, 20)], "chain")]


# ── geometry of a placed symbol ────────────────────────────────────

_DIRS = {"l": (-1, 0), "r": (1, 0), "u": (0, -1), "d": (0, 1)}
_NAMES = {v: k for k, v in _DIRS.items()}


def transform(point, rot=0, mirror=False):
    """Local -> placed (about the centre): mirror in x, then turn *rot*
    degrees clockwise on the sheet (y down)."""
    x, y = float(point[0]), float(point[1])
    if mirror:
        x = -x
    r = int(rot) % 360
    if r == 90:
        x, y = -y, x
    elif r == 180:
        x, y = -x, -y
    elif r == 270:
        x, y = y, -x
    return x, y


def turn_dir(d, rot=0, mirror=False):
    v = _DIRS[d]
    t = transform(v, rot, mirror)
    return _NAMES[(int(round(t[0])), int(round(t[1])))]


def placed_prims(kind, x, y, rot=0, mirror=False, scale=1.0):
    """The symbol's primitives moved to (x, y), turned and mirrored."""
    sym = SYMBOLS[kind]
    out = []
    for p in sym.draw():
        t = p[0]

        def m(q):
            a, b = transform(q, rot, mirror)
            return (x + a * scale, y + b * scale)
        if t == "line":
            out.append((t, p[1], m(p[2]), m(p[3])))
        elif t == "poly":
            out.append((t, p[1], [m(q) for q in p[2]], p[3], p[4]))
        elif t == "circle":
            out.append((t, p[1], m(p[2]), p[3] * scale, p[4]))
        elif t == "arc":
            # an arc turns with the symbol: start angle rotated
            # (visual degrees counter-clockwise; y-down turn is clockwise)
            start, sweep = p[4], p[5]
            if mirror:
                start, sweep = 180.0 - start, -sweep
            start -= int(rot) % 360
            out.append((t, p[1], m(p[2]), p[3] * scale, start, sweep))
        elif t == "text":
            out.append((t, p[1], m(p[2]), p[3], p[4] * scale, p[5], p[6]))
    return out


def port_points(kind, x, y, rot=0, mirror=False):
    """{port: ((x, y), direction)} of a placed symbol."""
    sym = SYMBOLS[kind]
    out = {}
    for name, (px, py, d) in sym.ports.items():
        a, b = transform((px, py), rot, mirror)
        out[name] = ((x + a, y + b), turn_dir(d, rot, mirror))
    return out


def bounds(kind, x, y, rot=0, mirror=False):
    sym = SYMBOLS[kind]
    w, h = (sym.h, sym.w) if int(rot) % 180 == 90 else (sym.w, sym.h)
    return x - w / 2.0, y - h / 2.0, x + w / 2.0, y + h / 2.0


def by_group():
    """[(group, [(kind, Symbol)])] in palette order."""
    out = []
    for g in GROUPS:
        items = [(k, s) for k, s in SYMBOLS.items() if s.group == g]
        if items:
            out.append((g, items))
    return out
