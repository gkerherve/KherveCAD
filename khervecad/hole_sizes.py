"""Standard hole sizes for the Hole Wizard (2026-10-21, the user: "add
all sizes — M1, M1.2 … and the inch ones").

Every row, in MILLIMETRES whatever the standard: d (nominal), pitch,
clearance (close, normal, loose), socket-head cap screw head (diameter,
height), hex nut (across flats, height).

- **ISO metric** (coarse thread): M1 – M64. Clearance ISO 273 fine /
  medium / coarse; heads ISO 4762; nuts ISO 4032.
- **ANSI inch UNC** and **UNF**: #0 – 1". Clearance from ASME B18.2.8
  (close / normal / loose ≈ +1 %, +6 %, +12 % of d, never under
  d + 0.1 mm); heads 1960-series socket cap screws; finished hex nuts.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

STANDARDS = ["ISO metric", "ANSI inch UNC", "ANSI inch UNF"]
IN = 25.4

# name: (d, pitch, (close, normal, loose), head_d, head_h, nut_af, nut_h)
_METRIC = [
    ("M1", 1.0, 0.25, (1.1, 1.2, 1.3), 2.0, 1.0, 2.5, 0.8),
    ("M1.2", 1.2, 0.25, (1.3, 1.4, 1.5), 2.3, 1.2, 3.0, 1.0),
    ("M1.4", 1.4, 0.3, (1.5, 1.6, 1.8), 2.6, 1.4, 3.0, 1.2),
    ("M1.6", 1.6, 0.35, (1.7, 1.8, 2.0), 3.0, 1.6, 3.2, 1.3),
    ("M2", 2.0, 0.4, (2.2, 2.4, 2.6), 3.8, 2.0, 4.0, 1.6),
    ("M2.5", 2.5, 0.45, (2.7, 2.9, 3.1), 4.5, 2.5, 5.0, 2.0),
    ("M3", 3.0, 0.5, (3.2, 3.4, 3.6), 5.5, 3.0, 5.5, 2.4),
    ("M3.5", 3.5, 0.6, (3.7, 3.9, 4.2), 6.0, 3.5, 6.0, 2.8),
    ("M4", 4.0, 0.7, (4.3, 4.5, 4.8), 7.0, 4.0, 7.0, 3.2),
    ("M5", 5.0, 0.8, (5.3, 5.5, 5.8), 8.5, 5.0, 8.0, 4.7),
    ("M6", 6.0, 1.0, (6.4, 6.6, 7.0), 10.0, 6.0, 10.0, 5.2),
    ("M8", 8.0, 1.25, (8.4, 9.0, 10.0), 13.0, 8.0, 13.0, 6.8),
    ("M10", 10.0, 1.5, (10.5, 11.0, 12.0), 16.0, 10.0, 16.0, 8.4),
    ("M12", 12.0, 1.75, (13.0, 13.5, 14.5), 18.0, 12.0, 18.0, 10.8),
    ("M14", 14.0, 2.0, (15.0, 15.5, 16.5), 21.0, 14.0, 21.0, 12.8),
    ("M16", 16.0, 2.0, (17.0, 17.5, 18.5), 24.0, 16.0, 24.0, 14.8),
    ("M18", 18.0, 2.5, (19.0, 20.0, 21.0), 27.0, 18.0, 27.0, 15.8),
    ("M20", 20.0, 2.5, (21.0, 22.0, 24.0), 30.0, 20.0, 30.0, 18.0),
    ("M22", 22.0, 2.5, (23.0, 24.0, 26.0), 33.0, 22.0, 34.0, 19.4),
    ("M24", 24.0, 3.0, (25.0, 26.0, 28.0), 36.0, 24.0, 36.0, 21.5),
    ("M27", 27.0, 3.0, (28.0, 30.0, 32.0), 40.0, 27.0, 41.0, 23.8),
    ("M30", 30.0, 3.5, (31.0, 33.0, 35.0), 45.0, 30.0, 46.0, 25.6),
    ("M33", 33.0, 3.5, (34.0, 36.0, 38.0), 50.0, 33.0, 50.0, 28.7),
    ("M36", 36.0, 4.0, (37.0, 39.0, 42.0), 54.0, 36.0, 55.0, 31.0),
    ("M39", 39.0, 4.0, (40.0, 42.0, 45.0), 58.0, 39.0, 60.0, 33.4),
    ("M42", 42.0, 4.5, (43.0, 45.0, 48.0), 63.0, 42.0, 65.0, 34.0),
    ("M45", 45.0, 4.5, (46.0, 48.0, 52.0), 68.0, 45.0, 70.0, 36.0),
    ("M48", 48.0, 5.0, (50.0, 52.0, 56.0), 72.0, 48.0, 75.0, 38.0),
    ("M52", 52.0, 5.0, (54.0, 56.0, 62.0), 78.0, 52.0, 80.0, 42.0),
    ("M56", 56.0, 5.5, (58.0, 62.0, 66.0), 84.0, 56.0, 85.0, 45.0),
    ("M60", 60.0, 5.5, (62.0, 66.0, 70.0), 90.0, 60.0, 90.0, 48.0),
    ("M64", 64.0, 6.0, (66.0, 70.0, 74.0), 96.0, 64.0, 95.0, 51.0),
]

# name, major diameter (in), UNC tpi, UNF tpi, cap head d (in), nut af (in)
_INCH = [
    ("#0", 0.060, None, 80, 0.096, 5 / 32),
    ("#1", 0.073, 64, 72, 0.118, 5 / 32),
    ("#2", 0.086, 56, 64, 0.140, 3 / 16),
    ("#3", 0.099, 48, 56, 0.161, 3 / 16),
    ("#4", 0.112, 40, 48, 0.183, 1 / 4),
    ("#5", 0.125, 40, 44, 0.205, 5 / 16),
    ("#6", 0.138, 32, 40, 0.226, 5 / 16),
    ("#8", 0.164, 32, 36, 0.270, 11 / 32),
    ("#10", 0.190, 24, 32, 0.312, 3 / 8),
    ("#12", 0.216, 24, 28, 0.343, 7 / 16),
    ("1/4", 0.250, 20, 28, 0.375, 7 / 16),
    ("5/16", 0.3125, 18, 24, 0.469, 1 / 2),
    ("3/8", 0.375, 16, 24, 0.562, 9 / 16),
    ("7/16", 0.4375, 14, 20, 0.656, 11 / 16),
    ("1/2", 0.500, 13, 20, 0.750, 3 / 4),
    ("9/16", 0.5625, 12, 18, 0.843, 7 / 8),
    ("5/8", 0.625, 11, 18, 0.938, 15 / 16),
    ("3/4", 0.750, 10, 16, 1.125, 1.125),
    ("7/8", 0.875, 9, 14, 1.312, 1.3125),
    ("1", 1.000, 8, 12, 1.500, 1.5),
]


def _inch_rows(fine):
    out = []
    for name, d_in, unc, unf, head_in, af_in in _INCH:
        tpi = unf if fine else unc
        if tpi is None:
            continue
        d = d_in * IN
        clear = tuple(round(max(d + 0.1, d * k), 2)
                      for k in (1.01, 1.06, 1.12))
        label = "%s-%d %s" % (name, tpi, "UNF" if fine else "UNC")
        out.append((label, round(d, 3), round(IN / tpi, 4), clear,
                    round(head_in * IN, 2), round(d, 3),
                    round(af_in * IN, 2), round(0.875 * d, 2)))
    return out


TABLES = {"ISO metric": _METRIC, "ANSI inch UNC": _inch_rows(False),
          "ANSI inch UNF": _inch_rows(True)}
ROWS = {row[0]: dict(standard=std, d=row[1], pitch=row[2], clear=row[3],
                     head_d=row[4], head_h=row[5], nut_af=row[6],
                     nut_h=row[7])
        for std, rows in TABLES.items() for row in rows}


def sizes(standard=None):
    """Size names of *standard* (all when None), smallest first."""
    if standard is None:
        return list(ROWS)
    return [row[0] for row in TABLES[standard]]


def standard_of(size):
    return ROWS[size]["standard"]


#: ISO 4762 / DIN 974 counterbores for socket cap screws, where listed
_COUNTERBORE = {"M1.6": 3.5, "M2": 4.4, "M2.5": 5.4, "M3": 6.5, "M4": 8.0,
                "M5": 10.0, "M6": 11.0, "M8": 15.0, "M10": 18.0,
                "M12": 20.0, "M14": 24.0, "M16": 26.0, "M20": 33.0,
                "M24": 40.0, "M30": 48.0, "M36": 57.0, "M42": 66.0,
                "M48": 76.0}


def counterbore(size):
    """The bore a socket head sits in: the standard's where listed, else
    the head + clearance."""
    if size in _COUNTERBORE:
        return _COUNTERBORE[size]
    r = ROWS[size]
    return round(r["head_d"] + max(0.5, 0.08 * r["head_d"]), 2)
