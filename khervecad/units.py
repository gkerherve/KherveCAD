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

import math
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


#: metric lengths a readout may climb to, in millimetres (never down:
#: a crystal in nanometres keeps saying nm)
_READABLE = (("nm", "nm", 1e-6), ("um", "µm", 1e-3), ("mm", "mm", 1.0),
             ("m", "m", 1e3), ("km", "km", 1e6))


def readable(value: float, unit):
    """(value, symbol) with *value* model units said in the largest
    metric unit — never smaller than the document's own — that keeps
    it at least 1: a true-size map's 200000 mm reads 200 m, a planet's
    5e9 mm reads 5000 km, 250 mm and 0.5 µm stay as they are. Inches
    are left alone. Powers of ten only, so a round 1-2-5 stays round."""
    code = coerce(unit)
    if code == "in":
        return value, symbol(code)
    base = to_mm(code)
    mm = value * base
    best = (value, symbol(code))
    for _code, sym, size in _READABLE:
        if size >= base and abs(mm) / size >= 1 - 1e-9:
            best = (mm / size, sym)
    return best


def grouped(value: float, digits: int = 2) -> str:
    """`tidy`, with thin spaces between thousands past 9999
    (212 600 000), which is how a scale is written."""
    # a whole number is written whole: `tidy` strips trailing zeros for
    # the decimals, and with none it ate an integer's own (212600000
    # came out 2126)
    if float(value).is_integer() and abs(value) < 1e15:
        text = str(int(round(value)))
    else:
        text = tidy(value, digits)
    whole, _dot, frac = text.partition(".")
    sign = "-" if whole.startswith("-") else ""
    whole = whole.lstrip("-")
    if len(whole) > 4 and whole.isdigit():
        whole = f"{int(whole):,}".replace(",", "\u2009")
    return sign + whole + (("." + frac) if frac else "")


def ratio_text(n: float) -> str:
    """"1 : 212 600 000" for a model *n* times smaller than life,
    "25 : 1" for one enlarged, "1 : 1" at life size; four significant
    figures, since a scale is a round number."""
    if not n or n <= 0 or not math.isfinite(n):
        return "1 : 1"
    if n >= 1:
        return f"1 : {grouped(float(f'{n:.4g}'), 0)}"
    return f"{grouped(float(f'{1 / n:.4g}'), 0)} : 1"


def parse_ratio(text) -> float:
    """The N of "1 : N" from what someone types: "1:250000000",
    "250 000 000", "1 : 2.5e8", "25:1" (an enlargement, N = 0.04). A
    number alone is N. Raises ValueError for anything else."""
    raw = str(text).replace("\u2009", "").replace(" ", "").replace(
        ",", "").replace("_", "")
    if not raw:
        raise ValueError("empty scale")
    if ":" in raw:
        a, _colon, b = raw.partition(":")
        num, den = float(a), float(b)
    else:
        num, den = 1.0, float(raw)
    if num <= 0 or den <= 0 or not (math.isfinite(num)
                                    and math.isfinite(den)):
        raise ValueError(f"not a scale: {text!r}")
    return den / num


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
