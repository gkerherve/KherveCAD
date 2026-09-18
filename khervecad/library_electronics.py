"""Electronics for the parts library (2026-09-18, the user's request): a
drawer of development boards beside the Arduino Uno and Raspberry Pi 4
(`library_vitamins`), the through-hole components a breadboard project
is made of, and the machines an electronics lab stands on its benches.

- **Boards** ("Electronics boards"), at their published outlines and
  mounting holes: Arduino Nano and Mega 2560, ESP32-DevKitC V4,
  NodeMCU ESP8266 (LoLin V3), Raspberry Pi Pico, Zero 2 W and 5,
  Teensy 4.0, STM32 "Blue Pill", BBC micro:bit V2. Built by
  `library_vitamins._board` (PCB + holes, then the chips and
  connectors that matter for an enclosure where they sit).
- **Components** ("Electronic components"): resistor (colour bands from
  the value), ceramic and electrolytic capacitors, LEDs, TO-92
  transistor, TO-220 regulator, DIP ICs, breadboards, potentiometer,
  tactile switch, pin headers, relay module, 7-segment display, buzzer,
  18650 and 9 V batteries, SG90 servo, 16x2 LCD, 0.96" OLED,
  perfboard, terminal block. True size in mm, standing on z = 0 with
  their leads going down into the board.
- **Lab equipment** ("Electronics lab"): ESD workbench with a shelf,
  soldering station, hot-air rework station, fume extractor, bench and
  handheld multimeters, spectrum analyser, electronic load, logic
  analyser, stereo microscope, helping hands, ESD mat and a component
  drawer cabinet. Room-scale like `library_lab` (whose helpers these
  use): front -Y, centred on X and Y, bench pieces ``on_top``.

No booleans outside the PCB's mounting holes, so the preview is right.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import library_home as _home
from .library_lab import (BLACK, CHROME, SAFETY_RED, TRACE, _box, _cyl,
                          _disc_y, _instrument, _knob, _rod, _screen)
from .library_room import _dims
from .library_vitamins import (ELECTRONICS, PCB_BLUE, PCB_GREEN, STEEL,
                               _board)
from .model import CadNode

COMPONENTS = "Electronic components"
LAB = "Electronics lab"

PCB_BLACK = "#1b1d21"
GOLD = "#d4af37"
TIN = "#c9ccd0"
CHIP = "#26282c"
MODULE = "#b8bcc2"
ESD_BLUE = "#3a6ea5"


# ------------------------------------------------------------- helpers
def _b(name, x, y, z, w, d, h, color, material="Default", alpha=1.0):
    """A sharp box from its low corner (component scale: never rounded)."""
    return _home._box(name, x, y, z, w, d, h, color, 0.0, material, alpha)


def _c(name, x, y, z, h, r, color, r2=None, seg=16, material="Default",
       alpha=1.0):
    return _home._cyl(name, x, y, z, h, r, color, r2, seg, material, alpha)


def _turned(node, x, y, z, **turn):
    rot = CadNode("rotate", node.name, dict(x=turn.get("rx", 0.0),
                                            y=turn.get("ry", 0.0),
                                            z=turn.get("rz", 0.0)))
    rot.add(node)
    move = CadNode("translate", node.name, dict(x=x, y=y, z=z))
    move.add(rot)
    return move


def _xcyl(name, x0, y, z, length, r, color, seg=16, material="Default",
          alpha=1.0):
    """A cylinder along +X from x0, its axis at (y, z)."""
    return _turned(_c(name, 0, 0, 0, length, r, color, seg=seg,
                      material=material, alpha=alpha), x0, y, z, ry=90.0)


def _ycyl(name, x, y0, z, length, r, color, seg=16, material="Default"):
    """A cylinder along +Y from y0, its axis at (x, z)."""
    return _turned(_c(name, 0, 0, 0, length, r, color, seg=seg,
                      material=material), x, y0, z, rx=-90.0)


def _paint(node, color, material="Default", alpha=1.0):
    return _home._paint(node, color, material, alpha)


def _prism(name, points, h, color, z=0.0):
    """A 2D outline (x, y points) extruded *h* up from z."""
    ext = CadNode("linear_extrude", name, dict(height=h, twist=0.0,
                                               scale=1.0, center=False,
                                               segments=0))
    ext.add(CadNode("polygon", name, dict(x=0.0, y=0.0,
                                          points=[list(p) for p in points])))
    node = _paint(ext, color)
    if z:
        node = _turned(node, 0.0, 0.0, z)
    return node


def _half_disc(name, r, h, color):
    """A TO-92 body: the half disc y >= 0 extruded h."""
    ext = CadNode("linear_extrude", name, dict(height=h, twist=0.0,
                                               scale=1.0, center=False,
                                               segments=0))
    ext.add(CadNode("circle", name, dict(x=0.0, y=0.0, radius=r,
                                         angle=180.0, start_angle=0.0,
                                         segments=24)))
    return _paint(ext, color)


def _lead(name, x, y, top, bottom=-3.5, r=0.3):
    return _rod(name, (x, y, top), (x, y, bottom), r, TIN, "Metal")


def _group(name, *children):
    node = CadNode("union", name)
    for child in children:
        node.add(child)
    return node


def _header(name, x, y, pins, rows=1, pitch=2.54, z=1.6, h=2.5):
    """A male pin header: black strip, square pins through it, lying
    along +X from (x, y) — the strip's low corner."""
    node = CadNode("union", name)
    node.add(_b("Strip", x, y, z, pins * pitch, rows * pitch, h, BLACK))
    for i in range(pins):
        for j in range(rows):
            node.add(_b("Pin", x + (i + 0.5) * pitch - 0.32,
                        y + (j + 0.5) * pitch - 0.32, z - 3.0, 0.64, 0.64,
                        h + 3.0 + 6.0, GOLD, "Metal"))
    return node


def _spec(label, category, build, sizes=None, fields=(), colors=None,
          **extra):
    entry = dict(label=label, category=category, build=build,
                 sizes=sizes or {"Standard": {}}, fields=list(fields),
                 **extra)
    if colors:
        entry["colors"] = list(colors)
    return entry


# -------------------------------------------------------------- boards
def _add(board, *parts):
    for p in parts:
        board.add(p)
    return board


def build_arduino_nano(dims):
    """Arduino Nano: 45 × 18 mm, two 15-pin headers, mini-USB."""
    holes = [(1.3, 1.3), (43.7, 1.3), (1.3, 16.7), (43.7, 16.7)]
    parts = [("Mini-USB", -1.5, 5.3, 9.2, 7.5, 4.0, STEEL, "Metal"),
             ("ATmega328P", 22.0, 5.5, 7.0, 7.0, 1.2, CHIP, "Default"),
             ("CH340", 12.0, 6.0, 5.0, 6.0, 1.5, CHIP, "Default"),
             ("Reset", 31.0, 7.5, 3.0, 3.0, 1.5, "#e9e9e6", "Default")]
    board = _board("Arduino Nano", 45.0, 18.0, holes, 1.8, parts, PCB_BLUE)
    return _add(board, _header("D header", 3.4, 0.0, 15, z=0.0),
                _header("A header", 3.4, 15.46, 15, z=0.0))


def build_arduino_mega(dims):
    """Arduino Mega 2560: 101.6 × 53.3 mm, Uno holes plus two more."""
    holes = [(14.0, 2.5), (15.3, 50.7), (66.1, 7.6), (66.1, 35.5),
             (90.2, 50.7), (96.5, 2.5)]
    parts = [("USB-B", -6.2, 38.1, 16.3, 12.2, 10.9, STEEL, "Metal"),
             ("DC jack", -1.8, 3.3, 14.2, 9.0, 11.0, BLACK, "Default"),
             ("ATmega2560", 40.0, 20.0, 14.0, 14.0, 1.2, CHIP, "Default"),
             ("ATmega16U2", 18.0, 36.0, 5.0, 5.0, 1.0, CHIP, "Default")]
    board = _board("Arduino Mega 2560", 101.6, 53.3, holes, 3.2, parts,
                   PCB_BLUE)
    return _add(board, _header("Digital header", 18.0, 50.4, 18),
                _header("Analog header", 27.0, 0.6, 16),
                _header("Double header", 93.5, 5.0, 18, rows=2))


def build_esp32_devkitc(dims):
    """ESP32-DevKitC V4: 54.4 × 27.9 mm, WROOM-32 module, 2 × 19 pins."""
    parts = [("Micro-USB", -1.0, 10.3, 5.7, 7.5, 2.9, STEEL, "Metal"),
             ("CP2102", 9.0, 10.5, 5.0, 5.0, 1.0, CHIP, "Default"),
             ("EN button", 4.5, 3.5, 4.0, 3.0, 1.8, BLACK, "Default"),
             ("BOOT button", 4.5, 21.5, 4.0, 3.0, 1.8, BLACK, "Default"),
             ("Module PCB", 29.0, 0.95, 25.5, 18.0 + 8.0, 0.8, PCB_BLACK,
              "Default"),
             ("RF shield", 29.8, 4.0, 17.6, 18.0, 3.1, MODULE, "Metal")]
    board = _board("ESP32-DevKitC V4", 54.4, 27.9, [], 0.0, parts,
                   PCB_BLACK)
    return _add(board, _header("Left header", 3.2, 0.0, 19, z=0.0),
                _header("Right header", 3.2, 25.36, 19, z=0.0))


def build_nodemcu(dims):
    """NodeMCU ESP8266 (LoLin V3): 58 × 31 mm, ESP-12 module, CH340."""
    holes = [(2.5, 2.5), (55.5, 2.5), (2.5, 28.5), (55.5, 28.5)]
    parts = [("Micro-USB", -1.0, 11.8, 5.7, 7.5, 2.9, STEEL, "Metal"),
             ("CH340G", 12.0, 11.0, 10.0, 5.0, 1.5, CHIP, "Default"),
             ("ESP-12 PCB", 34.0, 7.5, 24.0, 16.0, 0.8, PCB_BLUE,
              "Default"),
             ("RF shield", 34.5, 8.0, 15.0, 12.0, 2.4, MODULE, "Metal"),
             ("Flash", 6.0, 3.5, 3.5, 3.0, 1.5, BLACK, "Default"),
             ("Reset", 6.0, 24.5, 3.5, 3.0, 1.5, BLACK, "Default")]
    board = _board("NodeMCU ESP8266", 58.0, 31.0, holes, 3.0, parts,
                   PCB_BLACK)
    return _add(board, _header("Left header", 9.8, 1.0, 15, z=0.0),
                _header("Right header", 9.8, 27.46, 15, z=0.0))


def build_pi_pico(dims):
    """Raspberry Pi Pico: 51 × 21 mm, RP2040, holes 47 × 11.4 mm."""
    holes = [(2.0, 4.8), (49.0, 4.8), (2.0, 16.2), (49.0, 16.2)]
    parts = [("Micro-USB", -1.3, 6.75, 5.5, 7.5, 2.6, STEEL, "Metal"),
             ("RP2040", 22.0, 7.0, 7.0, 7.0, 0.9, CHIP, "Default"),
             ("Flash", 13.0, 12.5, 5.0, 6.0, 0.8, CHIP, "Default"),
             ("BOOTSEL", 10.5, 3.5, 3.5, 4.5, 1.6, "#e9e9e6", "Default"),
             ("Debug pads", 48.5, 8.0, 1.5, 5.0, 0.1, GOLD, "Metal")]
    board = _board("Raspberry Pi Pico", 51.0, 21.0, holes, 2.1, parts,
                   PCB_GREEN)
    for side, y in (("Left", 0.2), ("Right", 19.5)):
        for i in range(20):
            board.add(_b(f"{side} pad", 1.3 + i * 2.54 - 0.8, y, 1.6, 1.6,
                         1.3, 0.05, GOLD, "Metal"))
    return board


def build_pi_zero2w(dims):
    """Raspberry Pi Zero 2 W: 65 × 30 mm, holes 58 × 23 mm."""
    holes = [(3.5, 3.5), (61.5, 3.5), (3.5, 26.5), (61.5, 26.5)]
    parts = [("RP3A0 SiP", 20.0, 7.5, 14.0, 14.0, 1.2, "#8a8f96", "Metal"),
             ("Mini-HDMI", 12.4 - 5.6, -1.0, 11.2, 7.6, 3.3, STEEL,
              "Metal"),
             ("USB", 41.4 - 4.0, -1.0, 8.0, 5.6, 2.8, STEEL, "Metal"),
             ("Power", 54.0 - 4.0, -1.0, 8.0, 5.6, 2.8, STEEL, "Metal"),
             ("microSD", -2.0, 10.0, 14.0, 11.0, 1.4, STEEL, "Metal"),
             ("Camera", 62.0, 8.0, 4.0, 14.0, 1.2, BLACK, "Default")]
    board = _board("Raspberry Pi Zero 2 W", 65.0, 30.0, holes, 2.75, parts,
                   PCB_GREEN)
    for i in range(20):
        for j in range(2):
            board.add(_c("GPIO pad", 7.1 + 1.27 + i * 2.54,
                          24.5 + 1.27 + j * 2.54, 1.6, 0.05, 0.8, GOLD,
                          seg=8, material="Metal"))
    return board


def build_pi5(dims):
    """Raspberry Pi 5: 85 × 56 mm, holes 58 × 49 mm like the Pi 4, RP1,
    power button, fan and PCIe connectors."""
    holes = [(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]
    parts = [("Ethernet", 65.0, 2.5, 21.0, 16.0, 13.5, STEEL, "Metal"),
             ("USB 3 (pair)", 69.0, 20.5, 17.5, 13.5, 16.0, "#2f6db5",
              "Default"),
             ("USB 2 (pair)", 69.0, 38.0, 17.5, 13.5, 16.0, STEEL, "Metal"),
             ("USB-C power", 11.2 - 4.5, -1.5, 9.0, 7.5, 3.3, STEEL,
              "Metal"),
             ("Micro-HDMI 0", 26.0 - 3.5, -1.5, 7.0, 8.0, 3.0, STEEL,
              "Metal"),
             ("Micro-HDMI 1", 39.5 - 3.5, -1.5, 7.0, 8.0, 3.0, STEEL,
              "Metal"),
             ("BCM2712", 25.0, 20.0, 16.0, 16.0, 2.4, "#8a8f96", "Metal"),
             ("RP1", 49.0, 22.0, 9.0, 9.0, 1.0, CHIP, "Default"),
             ("RAM", 26.0, 38.0, 14.0, 10.0, 1.1, CHIP, "Default"),
             ("Power button", -0.5, 26.0, 4.0, 3.0, 2.0, BLACK, "Default"),
             ("Fan header", 64.0, 44.0, 5.0, 3.0, 3.0, "#e9e9e6", "Default"),
             ("PCIe FPC", -0.5, 9.0, 3.0, 17.0, 1.5, BLACK, "Default"),
             ("Camera/Display 0", 45.0, 2.0, 3.0, 16.0, 2.0, BLACK,
              "Default"),
             ("Camera/Display 1", 51.0, 2.0, 3.0, 16.0, 2.0, BLACK,
              "Default")]
    board = _board("Raspberry Pi 5", 85.0, 56.0, holes, 2.75, parts,
                   PCB_GREEN)
    return _add(board, _header("GPIO header", 7.1, 50.0, 20, rows=2))


def build_teensy40(dims):
    """Teensy 4.0: 35.6 × 17.8 mm, i.MX RT1062, 2 × 14 pins."""
    parts = [("Micro-USB", -1.0, 5.2, 5.7, 7.5, 2.9, STEEL, "Metal"),
             ("i.MX RT1062", 17.0, 4.0, 10.0, 10.0, 1.2, CHIP, "Default"),
             ("Program button", 30.0, 7.0, 3.5, 3.5, 1.5, "#e9e9e6",
              "Default")]
    board = _board("Teensy 4.0", 35.6, 17.8, [], 0.0, parts, PCB_GREEN)
    return _add(board, _header("Left header", 0.05, 0.0, 14, z=0.0),
                _header("Right header", 0.05, 15.26, 14, z=0.0))


def build_blue_pill(dims):
    """STM32F103C8 "Blue Pill": 53 × 22.5 mm, micro-USB, BOOT jumpers."""
    parts = [("Micro-USB", -1.0, 7.5, 5.7, 7.5, 2.9, STEEL, "Metal"),
             ("STM32F103C8", 26.0, 7.8, 7.0, 7.0, 1.4, CHIP, "Default"),
             ("Crystal", 16.0, 8.5, 4.5, 3.0, 3.5, STEEL, "Metal"),
             ("Reset", 38.0, 8.5, 5.0, 5.0, 2.0, BLACK, "Default"),
             ("BOOT jumpers", 45.0, 6.0, 5.0, 7.6, 8.5, BLACK, "Default")]
    board = _board("STM32 Blue Pill", 53.0, 22.5, [], 0.0, parts, PCB_BLUE)
    return _add(board, _header("Top header", 6.0, 0.0, 20, z=0.0),
                _header("Bottom header", 6.0, 19.96, 20, z=0.0),
                _header("SWD header", 50.3, 6.2, 4, z=0.0))


def build_microbit(dims):
    """BBC micro:bit V2: 52 × 42 mm, 5 × 5 LEDs, buttons A and B, the
    gold edge connector along the bottom."""
    parts = [("Micro-USB", 18.5, 38.0, 7.5, 5.7, 2.9, STEEL, "Metal"),
             ("Button A", 3.5, 20.0, 6.0, 6.0, 2.0, BLACK, "Default"),
             ("Button B", 42.5, 20.0, 6.0, 6.0, 2.0, BLACK, "Default"),
             ("Touch logo", 23.0, 32.0, 6.0, 4.0, 0.05, GOLD, "Metal"),
             ("Edge connector", 2.0, 0.0, 48.0, 7.0, 0.05, GOLD, "Metal")]
    board = _board("BBC micro:bit V2", 52.0, 42.0, [], 0.0, parts,
                   PCB_BLACK)
    for i in range(5):
        for j in range(5):
            board.add(_b("LED", 16.0 + i * 5.0, 11.0 + j * 5.0, 1.6, 1.0,
                         2.0, 0.6, "#ff3b30", "Emissive"))
    for x in (4.0, 21.0, 38.0):
        board.add(_c("Ring pad", x + 5.0, 3.5, 1.6, 0.05, 3.0, GOLD, seg=16,
                     material="Metal"))
    return board


# ---------------------------------------------------------- components
BAND = ["#1b1b1b", "#7b4a1e", "#d0312d", "#f08a24", "#f2d21b", "#2e8b57",
        "#2f6db5", "#7d3fb0", "#8c8c8c", "#f4f4f2"]
GOLD_BAND = "#c9a227"
RESISTOR_SIZES = {"220 Ω": dict(ohms=220.0), "1 kΩ": dict(ohms=1000.0),
                  "10 kΩ": dict(ohms=10000.0), "100 kΩ": dict(ohms=1e5),
                  "4.7 kΩ": dict(ohms=4700.0), "470 Ω": dict(ohms=470.0)}


def bands(ohms):
    """The three value bands of a 4-band resistor (+ gold tolerance)."""
    ohms = max(float(ohms), 1.0)
    exp = int(math.floor(math.log10(ohms))) - 1
    sig = int(round(ohms / 10 ** exp))
    if sig >= 100:
        sig //= 10
        exp += 1
    return [BAND[sig // 10], BAND[sig % 10], BAND[max(0, min(9, exp))],
            GOLD_BAND]


def build_resistor(dims):
    """A ¼ W axial resistor: 6.3 mm body, colour bands from the value,
    leads bent down on a 10.16 mm (0.4") pitch."""
    p = _dims(dims, RESISTOR_SIZES)
    L, r, z = 6.3, 1.2, 1.5
    node = CadNode("union", "Resistor")
    node.add(_rod("Body", (-L / 2 + r, 0, z), (L / 2 - r, 0, z), r,
                  "#d8c49a", "Default"))
    for x, col in zip((-2.1, -1.2, -0.3, 1.9), bands(p["ohms"])):
        node.add(_xcyl("Band", x, 0, z, 0.5, r + 0.05, col, seg=16))
    for s in (-1, 1):
        node.add(_rod("Lead", (s * L / 2, 0, z), (s * 5.08, 0, z), 0.3,
                      TIN, "Metal"))
        node.add(_lead("Lead", s * 5.08, 0, z))
    return node


CERAMIC_SIZES = {"100 nF": dict(r=2.5), "10 nF": dict(r=2.0)}


def build_ceramic_cap(dims):
    p = _dims(dims, CERAMIC_SIZES)
    r = p["r"]
    node = CadNode("union", "Ceramic capacitor")
    node.add(_ycyl("Disc", 0, -1.2, 1.5 + r, 2.4, r, "#c8752f", seg=20))
    for s in (-1, 1):
        node.add(_lead("Lead", s * 1.27, 0, 1.8))
    return node


ELECTROLYTIC_SIZES = {"100 µF 25 V": dict(dia=6.3, h=11.0, pitch=2.5),
                      "10 µF 50 V": dict(dia=5.0, h=11.0, pitch=2.0),
                      "1000 µF 25 V": dict(dia=10.0, h=20.0, pitch=5.0),
                      "4700 µF 35 V": dict(dia=16.0, h=31.5, pitch=7.5)}


def build_electrolytic(dims):
    """Radial electrolytic: sleeve, minus stripe, vent on the can top."""
    p = _dims(dims, ELECTROLYTIC_SIZES)
    r, h, pitch = p["dia"] / 2, p["h"], p["pitch"]
    node = CadNode("union", "Electrolytic capacitor")
    node.add(_c("Sleeve", 0, 0, 0.5, h - 0.5, r, "#1c2a5a", seg=24))
    node.add(_c("Can top", 0, 0, h, 0.2, r * 0.85, TIN, seg=24,
                material="Metal"))
    node.add(_b("Minus stripe", -r - 0.05, -r * 0.35, 0.8, 0.3, r * 0.7,
                h - 1.2, "#c9ccd0"))
    for s in (-1, 1):
        node.add(_lead("Lead", s * pitch / 2, 0, 0.6))
    return node


LED_COLORS = {"Red": "#ff3b30", "Green": "#34c759", "Blue": "#2f7bff",
              "Yellow": "#ffd60a", "White": "#f5f7ff"}
LED_SIZES = {"5 mm": dict(dia=5.0, h=8.6), "3 mm": dict(dia=3.0, h=5.3)}


def build_led(dims):
    """A through-hole LED: flanged epoxy dome, long anode lead."""
    p = _dims(dims, LED_SIZES)
    col = LED_COLORS.get(dims.get("_color") or "Red", "#ff3b30")
    r, h = p["dia"] / 2, p["h"]
    node = CadNode("union", "LED")
    node.add(_c("Flange", 0, 0, 0, 1.0, r + 0.4, col, seg=24,
                material="Glass", alpha=0.75))
    node.add(_rod("Dome", (0, 0, 1.0 + r * 0.01), (0, 0, h - r), r, col,
                  "Glass"))
    node.add(_b("Die", -0.3, -0.3, h * 0.45, 0.6, 0.6, 0.4, col,
                "Emissive"))
    node.add(_lead("Anode", 1.27, 0, 1.0, -5.0))
    node.add(_lead("Cathode", -1.27, 0, 1.0, -3.5))
    return node


def build_to92(dims):
    """A TO-92 transistor (2N2222, BC547): flat face to the front."""
    node = CadNode("union", "Transistor (TO-92)")
    node.add(_turned(_half_disc("Body", 2.4, 4.5, CHIP), 0, -1.0, 3.0))
    for x in (-1.27, 0.0, 1.27):
        node.add(_lead("Leg", x, 0.2, 3.0, -3.5, 0.22))
    return node


def build_to220(dims):
    """A TO-220 regulator or MOSFET: body, metal tab with its hole."""
    node = CadNode("union", "Regulator (TO-220)")
    node.add(_b("Body", -5.0, -2.25, 3.0, 10.0, 4.5, 9.0, CHIP))
    node.add(_b("Tab", -5.0, 1.0, 3.0, 10.0, 1.3, 15.5, TIN, "Metal"))
    node.add(_ycyl("Tab hole", 0, 0.95, 15.3, 1.4, 1.8, "#3a3d42", seg=16))
    for x in (-2.54, 0.0, 2.54):
        node.add(_b("Leg", x - 0.4, -0.25, -3.5, 0.8, 0.5, 6.5, TIN,
                    "Metal"))
    return node


DIP_SIZES = {f"DIP-{n}": dict(pins=n) for n in (8, 14, 16, 28, 40)}


def build_dip(dims):
    """A DIP chip: black body, notch at pin 1, legs bent down on 2.54 mm
    pitch and 7.62 mm (15.24 mm for 28/40 pins) row spacing."""
    p = _dims(dims, DIP_SIZES)
    n = int(p["pins"])
    half = n // 2
    row = 15.24 if n >= 28 else 7.62
    length = half * 2.54 + 0.3
    w = row - 1.2
    node = CadNode("union", f"DIP-{n}")
    node.add(_b("Body", -length / 2, -w / 2, 0.5, length, w, 3.3, CHIP))
    node.add(_c("Notch", -length / 2 + 0.4, 0, 3.75, 0.1, 0.8, "#3a3d42",
                seg=12))
    node.add(_c("Pin 1 dot", -length / 2 + 1.6, -w / 2 + 1.4, 3.8, 0.05,
                0.4, "#3a3d42", seg=8))
    for i in range(half):
        x = -(half - 1) * 1.27 + i * 2.54
        for s in (-1, 1):
            node.add(_b("Leg", x - 0.25, s * row / 2 - 0.13, -3.2, 0.5,
                        0.26, 4.8, TIN, "Metal"))
            y = -row / 2 if s < 0 else w / 2
            node.add(_b("Shoulder", x - 0.75, y, 1.2, 1.5, (row - w) / 2,
                        0.26, TIN, "Metal"))
    return node


BREADBOARD_SIZES = {"Half (400 points)": dict(cols=30, rails=True),
                    "Full (830 points)": dict(cols=63, rails=True),
                    "Mini (170 points)": dict(cols=17, rails=False)}


def build_breadboard(dims):
    """A solderless breadboard: two 5-row halves either side of the
    centre channel, red / blue power rails, the holes on 2.54 mm."""
    p = _dims(dims, BREADBOARD_SIZES)
    cols, rails = int(p["cols"]), bool(p["rails"])
    pitch = 2.54
    length = cols * pitch + 4.0
    width = 55.0 if rails else 35.0
    node = CadNode("union", "Breadboard")
    node.add(_b("Body", -length / 2, -width / 2, 0, length, width, 8.5,
                "#f2f2ee"))
    node.add(_b("Channel", -length / 2, -1.5, 8.45, length, 3.0, 0.1,
                "#d6d6d0"))
    hole = "#44464b"
    x0 = -(cols - 1) * pitch / 2
    for side in (-1, 1):
        for rw in range(5):
            y = side * (3.81 + rw * pitch)
            for c in range(cols):
                node.add(_b("Hole", x0 + c * pitch - 0.5, y - 0.5, 8.45,
                            1.0, 1.0, 0.1, hole))
        if rails:
            for k, col in enumerate(("#2f6db5", "#d0312d")):
                y = side * (19.0 + k * pitch)
                node.add(_b("Rail line", -length / 2 + 2, y + side * 1.6
                            - 0.3, 8.45, length - 4, 0.6, 0.1,
                            col if side > 0 else ("#d0312d", "#2f6db5")[k]))
                for c in range(cols):
                    if c % 6 == 5:
                        continue
                    node.add(_b("Rail hole", x0 + c * pitch - 0.5, y - 0.5,
                                8.45, 1.0, 1.0, 0.1, hole))
    return node


def build_potentiometer(dims):
    """A 16 mm rotary potentiometer: body, bushing, knurled shaft, three
    solder lugs to the front."""
    node = CadNode("union", "Potentiometer")
    node.add(_c("Body", 0, 0, 0, 7.0, 8.0, "#4a4d52", seg=24))
    node.add(_c("Bushing", 0, 0, 7.0, 7.0, 3.5, TIN, seg=16,
                material="Metal"))
    node.add(_c("Shaft", 0, 0, 14.0, 13.0, 3.0, "#b8bcc2", seg=16,
                material="Metal"))
    node.add(_b("Slot", -3.0, -0.4, 26.0, 6.0, 0.8, 1.1, "#6d7278"))
    for x in (-5.0, 0.0, 5.0):
        node.add(_b("Lug", x - 1.0, -12.0, 1.0, 2.0, 5.0, 0.4, TIN,
                    "Metal"))
    return node


BUTTON_SIZES = {"6 × 6 mm": dict(s=6.0), "12 × 12 mm": dict(s=12.0)}
BUTTON_COLORS = {"Black": BLACK, "Red": "#d0312d", "Blue": "#2f6db5",
                 "Yellow": "#f2d21b", "White": "#f4f4f2"}


def build_tact_switch(dims):
    p = _dims(dims, BUTTON_SIZES)
    s = p["s"]
    cap = BUTTON_COLORS.get(dims.get("_color") or "Black", BLACK)
    node = CadNode("union", "Tactile switch")
    node.add(_b("Body", -s / 2, -s / 2, 0, s, s, s * 0.6, "#2c2e33"))
    node.add(_b("Plate", -s / 2, -s / 2, s * 0.6, s, s, 0.2, TIN, "Metal"))
    node.add(_c("Actuator", 0, 0, s * 0.6, s * 0.4, s * 0.29, cap, seg=16))
    for sx in (-1, 1):
        for sy in (-1, 1):
            node.add(_b("Leg", sx * s * 0.54 - 0.35, sy * s * 0.37 - 0.35,
                        -3.5, 0.7, 0.7, 3.8, TIN, "Metal"))
    return node


HEADER_SIZES = {"1 × 10": dict(pins=10, rows=1),
                "1 × 40": dict(pins=40, rows=1),
                "2 × 20": dict(pins=20, rows=2),
                "1 × 6": dict(pins=6, rows=1)}


def build_pin_header(dims):
    p = _dims(dims, HEADER_SIZES)
    pins, rows = int(p["pins"]), int(p["rows"])
    return _header("Pin header", -pins * 1.27, -rows * 1.27, pins, rows,
                   z=0.0)


def build_relay_module(dims):
    """A 1-channel 5 V relay module: blue relay, screw terminal, LED and
    a 3-pin header."""
    node = CadNode("union", "Relay module")
    node.add(_b("PCB", -25.0, -13.0, 0, 50.0, 26.0, 1.6, PCB_BLUE))
    node.add(_b("Relay", -8.0, -8.0, 1.6, 19.0, 15.5, 15.5, "#2f6db5"))
    node.add(_b("Terminal", 14.0, -7.5, 1.6, 7.5, 15.0, 10.0, "#2e8b57"))
    for i in range(3):
        node.add(_c("Screw", 17.75, -5.0 + i * 5.0, 11.6, 0.3, 1.6, TIN,
                    seg=12, material="Metal"))
    node.add(_b("LED", -20.0, 6.0, 1.6, 1.6, 0.8, 0.6, "#ff3b30",
                "Emissive"))
    node.add(_header("Header", -24.0, -3.8, 3, z=1.6))
    return node


SEG7_COLORS = {"Red": "#ff3b30", "Green": "#34c759", "Blue": "#2f7bff"}


def build_seven_segment(dims):
    """A 0.56" 7-segment digit: segments lit in the chosen colour."""
    col = SEG7_COLORS.get(dims.get("_color") or "Red", "#ff3b30")
    w, d, h = 12.6, 19.0, 8.0
    node = CadNode("union", "7-segment display")
    node.add(_b("Body", -w / 2, -d / 2, 0, w, d, h, "#202226"))
    seg = [(-2.5, 6.5, 5.0, 1.0), (-2.5, -0.5, 5.0, 1.0),
           (-2.5, -7.5, 5.0, 1.0), (-3.5, 0.5, 1.0, 6.0),
           (2.5, 0.5, 1.0, 6.0), (-3.5, -6.5, 1.0, 6.0),
           (2.5, -6.5, 1.0, 6.0)]
    for x, y, sw, sd in seg:
        node.add(_b("Segment", x, y, h, sw, sd, 0.05, col, "Emissive"))
    node.add(_c("DP", 4.8, -7.0, h, 0.05, 0.6, col, seg=8,
                material="Emissive"))
    for i in range(5):
        for s in (-1, 1):
            node.add(_lead("Pin", -5.08 + i * 2.54, s * 7.62, 0.5))
    return node


def build_buzzer(dims):
    node = CadNode("union", "Buzzer")
    node.add(_c("Body", 0, 0, 0, 9.5, 6.0, "#202226", seg=24))
    node.add(_c("Sound hole", 0, 0, 9.5, 0.05, 1.0, "#555", seg=12))
    for s in (-1, 1):
        node.add(_lead("Lead", s * 3.8, 0, 0.5))
    return node


def build_battery_18650(dims):
    node = CadNode("union", "18650 cell")
    node.add(_xcyl("Wrap", -32.5, 0, 9.25, 64.0, 9.25, "#2f6db5", seg=24))
    node.add(_xcyl("Plus cap", 31.5, 0, 9.25, 1.5, 4.0, TIN, seg=16,
                   material="Metal"))
    node.add(_xcyl("Minus", -33.0, 0, 9.25, 0.5, 8.5, TIN, seg=24,
                   material="Metal"))
    return node


def build_battery_9v(dims):
    node = CadNode("union", "9 V battery")
    node.add(_b("Case", -13.25, -8.75, 0, 26.5, 17.5, 46.0, "#1f1f22"))
    node.add(_b("Label", -13.3, -8.8, 8.0, 26.6, 17.6, 28.0, "#e8b923"))
    node.add(_c("Plus", -6.35, 0, 46.0, 2.5, 3.0, TIN, seg=16,
                material="Metal"))
    node.add(_c("Minus", 6.35, 0, 46.0, 2.5, 4.0, TIN, seg=6,
                material="Metal"))
    return node


def build_servo_sg90(dims):
    """SG90 micro servo: 22.8 × 12.2 mm body, mounting ears, output
    spline and a single-arm horn."""
    node = CadNode("union", "SG90 servo")
    node.add(_b("Body", -11.4, -6.1, 0, 22.8, 12.2, 22.7, "#2f6db5",
                alpha=0.9))
    node.add(_b("Ears", -16.0, -6.1, 15.9, 32.0, 12.2, 2.5, "#2f6db5"))
    node.add(_c("Gear bump", 5.5, 0, 22.7, 4.0, 5.9, "#2f6db5", seg=24))
    node.add(_c("Spline", 5.5, 0, 26.7, 3.0, 2.4, "#f4f4f2", seg=12))
    node.add(_turned(_prism("Horn", [(0, -3.0), (0, 3.0), (17, 1.8),
                                     (17, -1.8)], 1.3, "#f4f4f2"),
                     5.5, 0.0, 29.7))
    node.add(_rod("Cable", (-11.4, 0, 3.0), (-30.0, 0, 3.0), 1.2,
                  "#7b4a1e", "Rubber"))
    return node


def build_lcd1602(dims):
    """A 16 × 2 character LCD module: 80 × 36 mm PCB, bezel, glowing
    screen, 16-pin header."""
    node = CadNode("union", "LCD 16×2")
    node.add(_b("PCB", -40.0, -18.0, 0, 80.0, 36.0, 1.6, PCB_GREEN))
    node.add(_b("Bezel", -35.5, -12.5, 1.6, 71.0, 24.0, 7.0, "#202226"))
    node.add(_b("Screen", -32.25, -7.25, 8.6, 64.5, 14.5, 0.1, "#3b7dd8",
                "Emissive"))
    for row in range(2):
        for c in range(16):
            node.add(_b("Char", -31.0 + c * 3.9, -5.8 + row * 6.3, 8.7,
                        3.0, 5.0, 0.02, "#5b95e8"))
    node.add(_header("Header", -38.0, 15.0, 16, z=0.0))
    return node


def build_oled(dims):
    """A 0.96" 128 × 64 I²C OLED: 27 × 27 mm, 4-pin header."""
    node = CadNode("union", "OLED 0.96in")
    node.add(_b("PCB", -13.5, -13.5, 0, 27.0, 27.0, 1.2, PCB_BLUE))
    node.add(_b("Glass", -13.5, -9.5, 1.2, 27.0, 19.0, 1.4, "#111216"))
    node.add(_b("Pixels", -11.0, -5.5, 2.6, 22.0, 11.0, 0.02, "#7fd6ff",
                "Emissive"))
    node.add(_header("Header", -5.08, 11.0, 4, z=0.0))
    return node


PERF_SIZES = {"70 × 50 mm": dict(w=70.0, d=50.0),
              "100 × 80 mm": dict(w=100.0, d=80.0)}


def build_perfboard(dims):
    p = _dims(dims, PERF_SIZES)
    w, d = p["w"], p["d"]
    node = CadNode("union", "Perfboard")
    node.add(_b("Board", -w / 2, -d / 2, 0, w, d, 1.6, "#c9a36b"))
    nx, ny = int((w - 4) // 2.54), int((d - 4) // 2.54)
    x0, y0 = -(nx - 1) * 1.27, -(ny - 1) * 1.27
    for i in range(nx):
        for j in range(ny):
            node.add(_b("Pad", x0 + i * 2.54 - 0.6, y0 + j * 2.54 - 0.6,
                        1.6, 1.2, 1.2, 0.04, "#d98e3a", "Metal"))
    return node


TERMINAL_SIZES = {"2 way": dict(n=2), "3 way": dict(n=3)}


def build_terminal_block(dims):
    p = _dims(dims, TERMINAL_SIZES)
    n = int(p["n"])
    w = n * 5.08
    node = CadNode("union", "Screw terminal")
    node.add(_b("Body", -w / 2, -3.75, 0, w, 7.5, 10.0, "#2e8b57"))
    for i in range(n):
        x = -w / 2 + 2.54 + i * 5.08
        node.add(_c("Screw", x, 0, 10.0, 0.3, 1.6, TIN, seg=12,
                    material="Metal"))
        node.add(_b("Wire entry", x - 1.5, -3.8, 2.0, 3.0, 0.1, 3.0,
                    "#1b1b1b"))
        node.add(_lead("Pin", x, 1.0, 0.5, -3.5, 0.5))
    return node


# ------------------------------------------------------ lab equipment
ESD_BENCH_SIZES = {"1.6 m": dict(w=1600.0, d=800.0, h=900.0),
                   "1.2 m": dict(w=1200.0, d=750.0, h=900.0),
                   "2.0 m": dict(w=2000.0, d=800.0, h=900.0)}


def build_esd_bench(dims):
    """An ESD workbench: blue dissipative top, steel frame, a raised
    instrument shelf at the back with a power strip under it."""
    p = _dims(dims, ESD_BENCH_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    part = CadNode("union", "ESD workbench")
    part.add(_box("Top", -w / 2, -d / 2, h - 30, w, d, 30, "#e8e8e4"))
    part.add(_box("ESD mat", -w / 2 + 20, -d / 2 + 20, h, w - 40,
                  d - 60, 3, ESD_BLUE))
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.add(_box("Leg", sx * (w / 2 - 50) - 25,
                          sy * (d / 2 - 50) - 25, 0, 50, 50, h - 30,
                          "#8f969e", material="Metal"))
        part.add(_box("Upright", sx * (w / 2 - 40) - 20, d / 2 - 60, h,
                      40, 40, 450, "#8f969e", material="Metal"))
    part.add(_box("Shelf", -w / 2, d / 2 - 320, h + 420, w, 300, 25,
                  "#e8e8e4"))
    part.add(_box("Rail", -w / 2 + 40, d / 2 - 60, h + 60, w - 80, 40, 60,
                  "#8f969e", material="Metal"))
    part.add(_box("Power strip", -w / 2 + 60, d / 2 - 100, h + 360,
                  w * 0.5, 50, 45, "#f4f4f2"))
    part.add(_box("Rail stretcher", -w / 2 + 50, -25, 150, w - 100, 50, 40,
                  "#8f969e", material="Metal"))
    part.add(_disc_y("Ground snap", w / 2 - 80, -d / 2 + 25, h + 5, 6, 4,
                     "#c9ccd0", material="Metal", seg=8))
    return part


def build_soldering_station(dims):
    """A soldering station: control unit with a display, the iron in its
    coil holder with a brass-wool cleaner."""
    part = CadNode("union", "Soldering station")
    part.add(_box("Unit", -110, -80, 0, 130, 160, 100, "#2b2f36"))
    part.add(_box("Display", -95, -82, 55, 70, 4, 30, "#10151b"))
    part.add(_box("Temperature", -88, -84, 62, 55, 2, 16, "#ff5a36",
                  material="Emissive"))
    part.add(_knob("Dial", -60, -80, 28, BLACK, r=11))
    part.add(_box("Holder base", 35, -60, 0, 90, 120, 20, "#3a3d42"))
    part.add(_cyl("Brass wool", 60, -25, 20, 25, 25, GOLD, material="Metal"))
    coil = _rod("Coil", (100, 40, 30), (100, -30, 90), 16, "#8f969e",
                "Metal")
    part.add(coil)
    part.add(_rod("Iron", (100, 50, 25), (100, -60, 105), 7, "#1f2226",
                  "Rubber"))
    part.add(_rod("Tip", (100, -60, 105), (100, -85, 121), 2, CHROME))
    part.add(_rod("Cable", (100, 55, 22), (-60, 80, 40), 3, BLACK,
                  "Rubber"))
    return part


def build_hot_air(dims):
    """A hot-air rework station: unit with two readouts and the gun on
    its cradle."""
    part = CadNode("union", "Hot-air station")
    part.add(_box("Unit", -110, -90, 0, 220, 180, 120, "#e9e9e6"))
    for i, x in enumerate((-80, 10)):
        part.add(_box("Readout", x, -92, 70, 60, 3, 25,
                      ("#ff5a36", TRACE)[i], material="Emissive"))
        part.add(_knob("Knob", x + 30, -90, 35, BLACK, r=10))
    part.add(_box("Cradle", 110, -40, 60, 40, 60, 40, "#3a3d42"))
    part.add(_rod("Gun", (130, 40, 110), (130, -80, 110), 18, "#2b2f36",
                  "Default"))
    part.add(_rod("Nozzle", (130, -80, 110), (130, -110, 110), 5, CHROME))
    return part


def build_fume_extractor(dims):
    """A bench fume extractor: carbon filter box on a stand."""
    part = CadNode("union", "Fume extractor")
    part.add(_box("Foot", -80, -70, 0, 160, 140, 15, "#2b2f36"))
    part.add(_rod("Stand", (0, 20, 15), (0, 20, 110), 8, "#8f969e"))
    part.add(_box("Housing", -80, -40, 110, 160, 110, 160, "#2b2f36"))
    part.add(_box("Filter", -70, -42, 120, 140, 3, 140, "#4a4f56"))
    for i in range(6):
        part.add(_box("Slat", -65, -44, 130 + i * 22, 130, 2, 6, "#5a5f66"))
    return part


def build_bench_multimeter(dims):
    part = _instrument("Bench multimeter", 230, 300, 90)
    _screen(part, -95, -150, 35, 120, 40, color="#10151b")
    part.add(_box("Digits", -85, -153, 48, 90, 2, 16, "#ffffff",
                  material="Emissive"))
    for i in range(6):
        part.add(_box("Key", 40 + (i % 3) * 22, -156, 55 - (i // 3) * 20,
                      16, 6, 12, "#c8ccd1"))
    for i, col in enumerate((SAFETY_RED, BLACK, SAFETY_RED, BLACK)):
        part.add(_disc_y("Jack", 45 + i * 16, -152, 18, 5, 8, col, seg=8))
    return part


def build_multimeter(dims):
    """A handheld multimeter in its yellow holster, on its tilt stand,
    with the red and black probes laid beside it."""
    body = CadNode("union", "Multimeter")
    body.add(_box("Holster", -45, -22, 0, 90, 44, 185, "#e8b923"))
    body.add(_box("Face", -38, -24, 10, 76, 4, 165, "#2b2f36"))
    body.add(_box("Display", -30, -26, 125, 60, 3, 40, "#9fb8a0"))
    body.add(_box("Digits", -24, -27, 135, 48, 1, 20, "#1b1b1b"))
    body.add(_disc_y("Dial", 0, -27, 80, 22, 6, BLACK, seg=16))
    for i, col in enumerate((BLACK, SAFETY_RED, SAFETY_RED)):
        body.add(_disc_y("Jack", -25 + i * 25, -26, 25, 4, 5, col, seg=8))
    part = CadNode("union", "Multimeter")
    tilt = CadNode("rotate", "Tilt", dict(x=-20.0, y=0.0, z=0.0))
    tilt.add(body)
    part.add(tilt)
    for x, col in ((70, SAFETY_RED), (85, BLACK)):
        part.add(_rod("Probe", (x, 60, 6), (x, -80, 6), 5, col, "Rubber"))
        part.add(_rod("Tip", (x, -80, 6), (x, -100, 6), 1, CHROME))
    return part


def build_spectrum_analyser(dims):
    part = _instrument("Spectrum analyser", 400, 380, 200)
    _screen(part, -180, -190, 30, 220, 150, color="#0f1a24")
    for i in range(12):
        hgt = 20 + 90 * math.exp(-((i - 6) / 2.2) ** 2) + (i * 7 % 11)
        part.add(_box("Peak", -170 + i * 17, -193, 45, 6, 2, hgt,
                      "#ffd84a", material="Emissive"))
    for i in range(12):
        part.add(_box("Key", 60 + (i % 4) * 28, -196, 150 - (i // 4) * 28,
                      20, 6, 18, "#c8ccd1"))
    part.add(_knob("Dial", 110, -190, 60, r=22))
    part.add(_disc_y("RF in", 160, -192, 30, 10, 14, CHROME, seg=12))
    return part


def build_electronic_load(dims):
    part = _instrument("Electronic load", 215, 400, 90, color="#dfe2e5")
    part.add(_box("Readout", -95, -202, 45, 110, 3, 30, TRACE,
                  material="Emissive"))
    part.add(_knob("Set", 50, -200, 45, r=14))
    for i, col in enumerate((SAFETY_RED, BLACK)):
        part.add(_disc_y("Terminal", 70 + i * 25, -202, 20, 8, 16, col,
                         seg=8))
    return part


def build_logic_analyser(dims):
    """A USB logic analyser: small box, 8 coloured leads to grabbers."""
    part = CadNode("union", "Logic analyser")
    part.add(_box("Case", -30, -20, 0, 60, 40, 14, "#1f2226"))
    colours = ["#1b1b1b", "#7b4a1e", "#d0312d", "#f08a24", "#f2d21b",
               "#2e8b57", "#2f6db5", "#7d3fb0"]
    for i, col in enumerate(colours):
        x = -17.5 + i * 5
        part.add(_rod("Lead", (x, -20, 7), (x - 20 + i * 5, -120, 3), 0.8,
                      col, "Rubber"))
    part.add(_rod("USB cable", (0, 20, 7), (0, 120, 3), 2, BLACK,
                  "Rubber"))
    return part


def build_microscope(dims):
    """A stereo inspection microscope on a pillar stand, ring light."""
    part = CadNode("union", "Stereo microscope")
    part.add(_box("Base", -110, -130, 0, 220, 260, 30, "#e9e9e6", r=0))
    part.add(_box("Stage", -70, -110, 30, 140, 140, 4, "#1b1b1b"))
    part.add(_cyl("Pillar", 0, 100, 30, 330, 16, "#c9ccd0",
                  material="Metal"))
    part.add(_box("Arm", -25, -10, 250, 50, 125, 40, "#e9e9e6"))
    part.add(_cyl("Head", 0, -30, 170, 110, 35, "#e9e9e6"))
    part.add(_cyl("Ring light", 0, -30, 160, 12, 42, "#2b2f36"))
    part.add(_cyl("Ring glow", 0, -30, 158, 2, 38, "#ffffff", r2=38,
                  material="Emissive"))
    for sx in (-1, 1):
        part.add(_rod("Eyepiece", (sx * 18, -30, 280), (sx * 22, -60, 340),
                      11, "#2b2f36", "Default"))
    part.add(_disc_y("Focus", 30, 5, 270, 22, 20, BLACK, seg=8))
    return part


def build_helping_hands(dims):
    """Helping hands: cast base, two flexible arms with crocodile clips
    and a magnifier."""
    part = CadNode("union", "Helping hands")
    part.add(_box("Base", -75, -50, 0, 150, 100, 20, "#2b2f36"))
    for sx in (-1, 1):
        part.add(_rod("Arm", (sx * 50, 20, 20), (sx * 70, -40, 160), 4,
                      "#3a3d42", "Default"))
        part.add(_rod("Clip", (sx * 70, -40, 160), (sx * 55, -70, 150), 3,
                      CHROME))
    part.add(_rod("Lens arm", (0, 30, 20), (0, -20, 230), 4, "#3a3d42",
                  "Default"))
    part.add(_disc_y("Lens", 0, -25, 230, 45, 4, "#cfe8ff",
                     material="Glass", alpha=0.35))
    part.add(_disc_y("Lens rim", 0, -24, 230, 48, 3, BLACK))
    return part


def build_esd_mat(dims):
    p = _dims(dims, {"600 × 500 mm": dict(w=600.0, d=500.0)})
    w, d = p["w"], p["d"]
    part = CadNode("union", "ESD mat")
    part.add(_box("Mat", -w / 2, -d / 2, 0, w, d, 2, ESD_BLUE))
    part.add(_cyl("Snap", w / 2 - 30, d / 2 - 30, 2, 3, 6, "#c9ccd0",
                  material="Metal"))
    part.add(_rod("Wrist strap cord", (w / 2 - 30, d / 2 - 30, 4),
                  (w / 2 - 150, -d / 2 + 60, 3), 2, "#2f2f33", "Rubber"))
    part.add(_cyl("Wrist band", w / 2 - 150, -d / 2 + 60, 0, 10, 35,
                  "#2f6db5"))
    return part


DRAWER_SIZES = {"4 × 8 drawers": dict(cols=4, rows=8),
                "6 × 10 drawers": dict(cols=6, rows=10)}


def build_component_drawers(dims):
    """A component cabinet: clear drawers of resistors and parts, each
    with a label strip, in a grey frame."""
    p = _dims(dims, DRAWER_SIZES)
    cols, rows = int(p["cols"]), int(p["rows"])
    dw, dh, d = 62.0, 42.0, 150.0
    w, h = cols * dw + 20, rows * dh + 20
    part = CadNode("union", "Component drawers")
    part.add(_box("Frame", -w / 2, -d / 2 + 5, 0, w, d - 5, h, "#8f969e"))
    tints = ["#d0312d", "#2f6db5", "#e8b923", "#2e8b57", "#7b4a1e",
             "#1b1b1b"]
    for c in range(cols):
        for r in range(rows):
            x = -w / 2 + 10 + c * dw
            z = 10 + r * dh
            part.add(_box("Drawer", x + 2, -d / 2, z + 2, dw - 4, 6,
                          dh - 4, "#dfe9f2", alpha=0.55))
            part.add(_box("Parts", x + 8, -d / 2 + 8, z + 4, dw - 16, 30,
                          10, tints[(c * 7 + r * 3) % len(tints)]))
            part.add(_box("Label", x + 12, -d / 2 - 1, z + dh - 14, dw - 24,
                          1, 8, "#f4f4f2"))
    return part


# ------------------------------------------------------------ registry
BOARD_BUILDS = {
    "elec_arduino_nano": ("Arduino Nano", build_arduino_nano),
    "elec_arduino_mega": ("Arduino Mega 2560", build_arduino_mega),
    "elec_esp32": ("ESP32-DevKitC V4", build_esp32_devkitc),
    "elec_nodemcu": ("NodeMCU ESP8266 (LoLin V3)", build_nodemcu),
    "elec_pi_pico": ("Raspberry Pi Pico", build_pi_pico),
    "elec_pi_zero2w": ("Raspberry Pi Zero 2 W", build_pi_zero2w),
    "elec_pi5": ("Raspberry Pi 5", build_pi5),
    "elec_teensy40": ("Teensy 4.0", build_teensy40),
    "elec_blue_pill": ("STM32 Blue Pill", build_blue_pill),
    "elec_microbit": ("BBC micro:bit V2", build_microbit),
}

PARTS = {pid: _spec(label, ELECTRONICS, build)
         for pid, (label, build) in BOARD_BUILDS.items()}
PARTS.update({
    "elec_resistor": _spec("Resistor (¼ W)", COMPONENTS, build_resistor,
                           RESISTOR_SIZES),
    "elec_ceramic_cap": _spec("Ceramic capacitor", COMPONENTS,
                              build_ceramic_cap, CERAMIC_SIZES),
    "elec_electrolytic": _spec("Electrolytic capacitor", COMPONENTS,
                               build_electrolytic, ELECTROLYTIC_SIZES),
    "elec_led": _spec("LED", COMPONENTS, build_led, LED_SIZES,
                      colors=LED_COLORS),
    "elec_to92": _spec("Transistor (TO-92)", COMPONENTS, build_to92),
    "elec_to220": _spec("Regulator / MOSFET (TO-220)", COMPONENTS,
                        build_to220),
    "elec_dip": _spec("DIP integrated circuit", COMPONENTS, build_dip,
                      DIP_SIZES),
    "elec_breadboard": _spec("Breadboard", COMPONENTS, build_breadboard,
                             BREADBOARD_SIZES),
    "elec_potentiometer": _spec("Potentiometer", COMPONENTS,
                                build_potentiometer),
    "elec_tact_switch": _spec("Tactile push button", COMPONENTS,
                              build_tact_switch, BUTTON_SIZES,
                              colors=BUTTON_COLORS),
    "elec_pin_header": _spec("Pin header", COMPONENTS, build_pin_header,
                             HEADER_SIZES),
    "elec_relay": _spec("Relay module (1 channel)", COMPONENTS,
                        build_relay_module),
    "elec_seven_segment": _spec("7-segment display", COMPONENTS,
                                build_seven_segment, colors=SEG7_COLORS),
    "elec_buzzer": _spec("Buzzer", COMPONENTS, build_buzzer),
    "elec_18650": _spec("18650 Li-ion cell", COMPONENTS,
                        build_battery_18650),
    "elec_9v": _spec("9 V battery", COMPONENTS, build_battery_9v),
    "elec_servo": _spec("SG90 micro servo", COMPONENTS, build_servo_sg90),
    "elec_lcd1602": _spec("LCD 16×2 module", COMPONENTS, build_lcd1602),
    "elec_oled": _spec("OLED 0.96in display", COMPONENTS, build_oled),
    "elec_perfboard": _spec("Perfboard", COMPONENTS, build_perfboard,
                            PERF_SIZES),
    "elec_terminal": _spec("Screw terminal block", COMPONENTS,
                           build_terminal_block, TERMINAL_SIZES),
    # lab equipment
    "elec_esd_bench": _spec("ESD workbench (with shelf)", LAB,
                            build_esd_bench, ESD_BENCH_SIZES,
                            [("w", "Width"), ("d", "Depth"),
                             ("h", "Height")]),
    "elec_soldering_station": _spec("Soldering station", LAB,
                                    build_soldering_station, on_top=True),
    "elec_hot_air": _spec("Hot-air rework station", LAB, build_hot_air,
                          on_top=True),
    "elec_fume_extractor": _spec("Solder fume extractor", LAB,
                                 build_fume_extractor, on_top=True),
    "elec_bench_multimeter": _spec("Bench multimeter", LAB,
                                   build_bench_multimeter, on_top=True),
    "elec_multimeter": _spec("Handheld multimeter", LAB, build_multimeter,
                             on_top=True),
    "elec_spectrum_analyser": _spec("Spectrum analyser", LAB,
                                    build_spectrum_analyser, on_top=True),
    "elec_electronic_load": _spec("Electronic load", LAB,
                                  build_electronic_load, on_top=True),
    "elec_logic_analyser": _spec("Logic analyser", LAB,
                                 build_logic_analyser, on_top=True),
    "elec_microscope": _spec("Stereo inspection microscope", LAB,
                             build_microscope, on_top=True),
    "elec_helping_hands": _spec("Helping hands with magnifier", LAB,
                                build_helping_hands, on_top=True),
    "elec_esd_mat": _spec("ESD mat with wrist strap", LAB, build_esd_mat,
                          on_top=True),
    "elec_component_drawers": _spec("Component drawer cabinet", LAB,
                                    build_component_drawers, DRAWER_SIZES,
                                    on_top=True),
})

#: the electronics lab room's catalogue (house.FURNITURE_CATALOG)
LAB_FURNITURE = [pid for pid, spec in PARTS.items()
                 if spec["category"] == LAB] + [
    "lab_oscilloscope", "lab_power_supply", "lab_signal_generator",
    "lab_electronics_bench", "lab_instrument_rack", "lab_stool",
    "lab_whiteboard", "lab_fire_extinguisher", "lab_first_aid",
    "elec_breadboard", "elec_arduino_mega", "vit_board", "room_monitor",
    "office_lockers", "home_coat_stand"]
