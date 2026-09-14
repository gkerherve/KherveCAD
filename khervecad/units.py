"""The document's display unit (Qt-free).

OpenSCAD is unitless and so is the tree: a cube of size 10 is 10 of
whatever the author means. `DocumentModel.unit` records what they mean
— nanometres for a nanoparticle built from 0.49 nm lattice cells,
metres for a room — so every readout says it. The geometry is NEVER
rescaled by choosing a unit; the unit is a label, plus a factor to
millimetres for the outputs that are physically dimensioned: mass
(volume -> cm³ for the density), print time and cost (only meaningful
at a printable scale), and STL/3MF files, which slicers read as
millimetres.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re
import zipfile

DEFAULT = "mm"

#: code -> (symbol, name, millimetres per unit), smallest first
_TABLE = {
    "nm": ("nm", "nanometres", 1e-6),
    "um": ("µm", "micrometres", 1e-3),
    "mm": ("mm", "millimetres", 1.0),
    "cm": ("cm", "centimetres", 10.0),
    "m": ("m", "metres", 1000.0),
    "in": ("in", "inches", 25.4),
}
UNITS = tuple(_TABLE)

#: units a 3D printer works at 1:1 — print time and cost are estimated
#: only for these (a 100 nm particle or a 5 m room is not a print job)
PRINTABLE = ("mm", "cm", "in")

_ALIASES = {
    "µm": "um", "μm": "um", "micron": "um", "microns": "um",
    "micrometer": "um", "micrometers": "um", "micrometre": "um",
    "micrometres": "um",
    "nanometer": "nm", "nanometers": "nm", "nanometre": "nm",
    "nanometres": "nm",
    "millimeter": "mm", "millimeters": "mm", "millimetre": "mm",
    "millimetres": "mm",
    "centimeter": "cm", "centimeters": "cm", "centimetre": "cm",
    "centimetres": "cm",
    "meter": "m", "meters": "m", "metre": "m", "metres": "m",
    "inch": "in", "inches": "in", '"': "in",
}


def normalise(unit) -> str:
    """The unit code for *unit* ("nm", "µm", "inches", ...); raises
    ValueError for anything else."""
    text = str(unit or "").strip()
    if text in _TABLE:
        return text
    code = _ALIASES.get(text) or _ALIASES.get(text.lower())
    if code is None and text.lower() in _TABLE:
        code = text.lower()
    if code is None:
        raise ValueError(f"unknown unit {unit!r}; use one of "
                         f"{', '.join(UNITS)}")
    return code


def coerce(unit) -> str:
    """Like `normalise`, but an unknown unit (a hand-edited file) falls
    back to millimetres instead of refusing to open."""
    try:
        return normalise(unit)
    except ValueError:
        return DEFAULT


def symbol(unit) -> str:
    return _TABLE[coerce(unit)][0]


def name(unit) -> str:
    return _TABLE[coerce(unit)][1]


def to_mm(unit) -> float:
    """Millimetres in one *unit*."""
    return _TABLE[coerce(unit)][2]


def printable(unit) -> bool:
    return coerce(unit) in PRINTABLE


def choices():
    """[(code, "nm — nanometres"), ...] for a picker."""
    return [(code, f"{sym} — {nm}") for code, (sym, nm, _f) in
            _TABLE.items()]


def tidy(value: float, digits: int = 2) -> str:
    """No trailing zeros (30, 30.5, 36.06); scientific when the fixed
    rendering would print a nonzero number as 0."""
    if value and abs(value) < 0.5 * 10 ** -digits:
        return f"{value:.3g}"
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def length(value: float, unit, digits: int = 2) -> str:
    """"36.06 nm" — a tidy length with its unit."""
    return f"{tidy(value, digits)} {symbol(unit)}"


def mm(value: float, unit, power: int = 1) -> float:
    """*value* (in unit^power) in true mm^power."""
    return value * to_mm(unit) ** power


def cm3(volume: float, unit) -> float:
    """A volume in unit³ as cm³ (for a density in g/cm³)."""
    return mm(volume, unit, 3) / 1000.0


def significant(value: float, digits: int = 6) -> float:
    """*value* rounded to significant figures, so a nanometre part's
    volume in mm³ (1e-13) does not round to 0."""
    return float(f"{value:.{digits}g}") if value else 0.0


def export_note(unit) -> str:
    """What an STL/3MF of a non-mm document means to a slicer."""
    code = coerce(unit)
    if code == "mm":
        return ""
    return (f"The document is in {name(code)}. STL and 3MF files are read "
            f"as millimetres, so exported 1:1 each {symbol(code)} becomes "
            f"1 mm; scaled to millimetres every length is multiplied by "
            f"{to_mm(code):g}.")


# ------------------------------------------------------ scaling a file

_VERTEX = re.compile(rb"<(?:\w+:)?vertex\b[^>]*>")
_COORD = re.compile(rb'\b([xyz])="([^"]*)"')


def scale_mesh_file(path: str, factor: float):
    """Multiply every coordinate of an exported .stl or .3mf by
    *factor*, in place — how "scale to millimetres" is applied after
    OpenSCAD wrote the file 1:1 (wrapping the program in scale() would
    have to move its module definitions)."""
    path = str(path)
    if path.lower().endswith(".3mf"):
        _scale_3mf(path, factor)
        return
    from .engine import parse_mesh, write_stl
    tris = parse_mesh(path)
    write_stl([tuple(tuple(c * factor for c in v) for v in tri)
               for tri in tris], path)


def _scale_3mf(path: str, factor: float):
    def scale_vertex(match):
        return _COORD.sub(
            lambda m: m.group(1) + b'="' + repr(
                float(m.group(2)) * factor).encode() + b'"',
            match.group(0))

    with zipfile.ZipFile(path) as archive:
        members = [(info, archive.read(info.filename))
                   for info in archive.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for info, data in members:
            if info.filename.lower().endswith(".model"):
                data = _VERTEX.sub(scale_vertex, data)
            archive.writestr(info, data)
