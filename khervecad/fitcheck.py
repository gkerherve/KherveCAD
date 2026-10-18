"""Fits and tolerances (Qt-free).

* `clearances` — the smallest gap between parts that are mated or near
  each other (`analysis.interference` says whether they overlap; the
  gap is each part's vertices to the other's surface through
  `shrinkwrap.Target`), judged against a wanted clearance. A pin
  standing in a bore — a part with a round cross-section inside the
  other's footprint — also gets its DIAMETRAL clearance (twice the gap,
  assuming it is centred) and the ISO 286 hole-basis fit that clearance
  falls in (`classify`, `FITS`).
* `stackup` — a tolerance chain of Blueprint dimensions carrying
  tol_plus / tol_minus: worst case and RSS (root sum of squares about
  each dimension's mid-tolerance), against optional limits.

Each reports pass / warn / fail like `analysis.print_check`.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import analysis

#: wanted clearance between neighbouring parts, mm
DEFAULT_CLEARANCE = 0.1
#: parts further apart than this are not neighbours (unless mated)
DEFAULT_NEAR = 2.0
#: a gap under this is contact
TOUCH = 1e-3

# ── ISO 286 (µm), nominal size ranges up to 180 mm ─────────────────
_RANGES = (3, 6, 10, 18, 30, 50, 80, 120, 180)
_IT = {6: (6, 8, 9, 11, 13, 16, 19, 22, 25),
       7: (10, 12, 15, 18, 21, 25, 30, 35, 40),
       8: (14, 18, 22, 27, 33, 39, 46, 54, 63),
       9: (25, 30, 36, 43, 52, 62, 74, 87, 100),
       11: (60, 75, 90, 110, 130, 160, 190, 220, 250)}
#: shaft fundamental deviation: upper (es) for c..h, lower (ei) for k..s
_UPPER = {"c": (-60, -70, -80, -95, -110, -120, -140, -170, -200),
          "d": (-20, -30, -40, -50, -65, -80, -100, -120, -145),
          "f": (-6, -10, -13, -16, -20, -25, -30, -36, -43),
          "g": (-2, -4, -5, -6, -7, -9, -10, -12, -14),
          "h": (0,) * 9}
_LOWER = {"k": (0, 1, 1, 1, 2, 2, 2, 3, 3),
          "n": (4, 8, 10, 12, 15, 17, 20, 23, 27),
          "p": (6, 12, 15, 18, 22, 26, 32, 37, 43),
          "s": (14, 19, 23, 28, 35, 43, 53, 71, 92)}
#: the preferred hole-basis fits: (name, hole grade, shaft letter,
#: shaft grade, what it is for)
FITS = (("H11/c11", 11, "c", 11, "loose running"),
        ("H9/d9", 9, "d", 9, "free running"),
        ("H8/f7", 8, "f", 7, "close running"),
        ("H7/g6", 7, "g", 6, "sliding"),
        ("H7/h6", 7, "h", 6, "locational clearance"),
        ("H7/k6", 7, "k", 6, "locational transition"),
        ("H7/n6", 7, "n", 6, "locational transition"),
        ("H7/p6", 7, "p", 6, "locational interference"),
        ("H7/s6", 7, "s", 6, "medium drive"))


def _row(nominal):
    for i, top in enumerate(_RANGES):
        if nominal <= top:
            return i
    return None


def fit_limits(fit, nominal):
    """(min, max) diametral clearance in mm of *fit* at *nominal* mm (a
    negative clearance is interference), or None past 180 mm."""
    row = _row(nominal)
    if row is None or nominal <= 0:
        return None
    for name, hg, letter, sg, _use in FITS:
        if name == fit:
            break
    else:
        raise KeyError(fit)
    hole_hi = _IT[hg][row]
    it_s = _IT[sg][row]
    if letter in _UPPER:
        es = _UPPER[letter][row]
        ei = es - it_s
    else:
        ei = _LOWER[letter][row]
        es = ei + it_s
    return ((0 - es) / 1000.0, (hole_hi - ei) / 1000.0)


def classify(nominal, clearance):
    """The ISO fit a diametral *clearance* (mm) at *nominal* (mm) sits
    in: {fit, use, min, max, within} — the fit whose range holds it
    (the one with its middle nearest), else the nearest one."""
    best = None
    for name, _hg, _l, _sg, use in FITS:
        lim = fit_limits(name, nominal)
        if lim is None:
            return None
        lo, hi = lim
        within = lo - 1e-9 <= clearance <= hi + 1e-9
        off = 0.0 if within else min(abs(clearance - lo),
                                      abs(clearance - hi))
        score = (off, abs(clearance - (lo + hi) / 2))
        if best is None or score < best[0]:
            best = (score, dict(fit=name, use=use, min_mm=round(lo, 4),
                                max_mm=round(hi, 4), within=within))
    return best[1]


# ── clearance between parts ────────────────────────────────────────
def _verts(tris):
    return list({tuple(v) for t in tris for v in t})


def min_gap(ta, tb):
    """Smallest distance between two surfaces and the two points: each
    one's vertices to the other's triangles (an edge crossing an edge
    is missed, which a faceted pin in a bore never is)."""
    import numpy as np
    from .shrinkwrap import Target
    best = (math.inf, None, None)
    for src, dst in ((ta, tb), (tb, ta)):
        pts = np.array(_verts(src))
        q, _t = Target(dst).nearest(pts)
        d = np.linalg.norm(q - pts, axis=1)
        i = int(np.argmin(d))
        if d[i] < best[0]:
            p, r = pts[i].tolist(), q[i].tolist()
            best = (float(d[i]), p, r) if src is ta else \
                (float(d[i]), r, p)
    return best


def _round_section(box):
    """The axis a part's bounding box is round about — two equal
    extents — or None."""
    lo, hi = box
    ext = [hi[k] - lo[k] for k in range(3)]
    for k in range(3):
        i, j = [a for a in range(3) if a != k]
        if ext[i] > 0 and abs(ext[i] - ext[j]) <= 0.02 * max(ext[i],
                                                              ext[j]):
            return k
    return None


def _pin_in_bore(box_in, box_out, axis):
    i, j = [a for a in range(3) if a != axis]
    return all(box_out[0][a] - 1e-6 <= box_in[0][a] and
               box_in[1][a] <= box_out[1][a] + 1e-6 for a in (i, j)) and \
        box_in[0][axis] < box_out[1][axis] and \
        box_out[0][axis] < box_in[1][axis]


def _pin(box_a, box_b):
    """(inner index 0/1, axis, shaft diameter) when one part stands in
    the other like a pin in a bore."""
    for inner, (bi, bo) in enumerate(((box_a, box_b), (box_b, box_a))):
        axis = _round_section(bi)
        if axis is not None and _pin_in_bore(bi, bo, axis):
            k = [a for a in range(3) if a != axis][0]
            return inner, axis, bi[1][k] - bi[0][k]
    return None


def clearances(parts, wanted: float = DEFAULT_CLEARANCE,
               near: float = DEFAULT_NEAR, mated=()) -> dict:
    """*parts* = [(name, tris)], *mated* = pairs of names. One entry per
    pair that overlaps, is mated, or is within *near*: gap, the two
    nearest points, status and message; pins get ``fit``."""
    pairs = analysis.interference(parts)
    tris = dict(parts)
    mated = {frozenset(p) for p in mated}
    out = []
    for p in pairs:
        a, b = p["a"], p["b"]
        is_mated = frozenset((a, b)) in mated
        ta, tb = tris.get(a), tris.get(b)
        if not ta or not tb:
            continue
        entry = dict(a=a, b=b, mated=is_mated)
        box_a, box_b = analysis.bounds(ta), analysis.bounds(tb)
        if p["status"] != "clear":
            entry.update(gap=0.0, overlap=p["status"], status="fail",
                         message=f"{a} and {b} overlap ({p['status']}) — "
                                 "an interference fit is drawn as an "
                                 "overlap; make sure it is meant.")
            pin = _pin(box_a, box_b)
            if pin and p["status"] == "intersect":
                entry["pin"] = dict(inner=(a, b)[pin[0]],
                                    axis="xyz"[pin[1]],
                                    shaft_diameter=round(pin[2], 4))
            out.append(entry)
            continue
        if not analysis._boxes_overlap(box_a, box_b, near) and \
                not is_mated:
            continue
        gap, pa, pb = min_gap(ta, tb)
        if gap > near and not is_mated:
            continue
        entry.update(gap=round(gap, 4),
                     points=[[round(v, 3) for v in pa],
                             [round(v, 3) for v in pb]])
        pin = _pin(box_a, box_b)
        if pin:
            inner, axis, d = pin
            nominal = round(d + gap, 1)
            fit = classify(nominal, 2 * gap)
            entry["pin"] = dict(inner=(a, b)[inner], axis="xyz"[axis],
                                shaft_diameter=round(d, 4),
                                bore_diameter=round(d + 2 * gap, 4),
                                diametral_clearance=round(2 * gap, 4),
                                nominal=nominal)
            if fit:
                entry["pin"]["iso_fit"] = fit
        if gap < TOUCH:
            entry["status"] = "pass" if is_mated else "warn"
            entry["message"] = (f"{a} and {b} touch" +
                                (" (mated)." if is_mated else
                                 " — no clearance; is it meant?"))
        elif gap < wanted:
            entry["status"] = "warn"
            entry["message"] = (f"{gap:.3g} between {a} and {b}, under "
                                f"the {wanted:g} wanted.")
        else:
            entry["status"] = "pass"
            entry["message"] = f"{gap:.3g} between {a} and {b}."
        if "pin" in entry and entry["pin"].get("iso_fit"):
            f = entry["pin"]["iso_fit"]
            entry["message"] += (
                f" Ø{entry['pin']['nominal']:g} pin: "
                f"{entry['pin']['diametral_clearance']:.3g} diametral "
                f"clearance ≈ {f['fit']} ({f['use']}"
                + ("" if f["within"] else ", outside its range") + ").")
        out.append(entry)
    return dict(pairs=out, summary=_worst(e["status"] for e in out),
                wanted=wanted)


def _worst(statuses):
    worst = "pass"
    for s in statuses:
        if s == "fail":
            return "fail"
        if s == "warn":
            worst = "warn"
    return worst


# ── tolerance stack-up ─────────────────────────────────────────────
LINEAR = ("horizontal", "vertical", "aligned")


def _num(text):
    text = str(text or "").strip().lstrip("±+").replace("−", "-")
    try:
        return abs(float(text))
    except ValueError:
        return 0.0


def dim_value(d) -> float:
    """What a saved Blueprint dimension measures (the model's number,
    or its typed text when that is a number)."""
    typed = str(d.get("text") or "").strip()
    try:
        return float(typed)
    except ValueError:
        pass
    k = d.get("kind", "horizontal")
    if k in LINEAR and "a" in d and "b" in d:
        a, b = d["a"], d["b"]
        if k == "horizontal":
            return abs(b[0] - a[0])
        if k == "vertical":
            return abs(b[1] - a[1])
        return math.hypot(b[0] - a[0], b[1] - a[1])
    if k == "diameter":
        return 2.0 * float(d.get("r", 0.0))
    if k == "radius":
        return float(d.get("r", 0.0))
    return 0.0


def tolerances(d):
    """(plus, minus) of a dimension, both >= 0; '±0.1' in either field
    is symmetric."""
    plus, minus = d.get("tol_plus") or "", d.get("tol_minus") or ""
    p, m = _num(plus), _num(minus)
    if str(plus).strip().startswith("±") and not str(minus).strip():
        m = p
    if str(minus).strip().startswith("±") and not str(plus).strip():
        p = m
    return p, m


def dimensions(notes):
    """[(index, note)] of the dimension notes of a saved sheet."""
    return [(i, n) for i, n in enumerate(notes or [])
            if n.get("type") == "dim" and n.get("kind") != "angle"]


def stackup(notes, chain=None, limits=None) -> dict:
    """*chain* = [index or {index, sign}] into *notes* (default: every
    toleranced dimension, added). Returns worst case and RSS min / max
    of the closing value, each dimension's line, and against *limits*
    [lo, hi] a status: pass (worst case inside), warn (only RSS
    inside), fail; without limits, pass."""
    dims = dict(dimensions(notes))
    if chain is None:
        chain = [i for i, n in dims.items() if any(tolerances(n))]
    lines = []
    for link in chain:
        if isinstance(link, dict):
            idx, sign = int(link["index"]), float(link.get("sign", 1))
        else:
            idx, sign = int(link), 1.0
        if idx not in dims:
            raise ValueError(f"note {idx} is not a linear or Ø/R "
                             "dimension of this sheet")
        sign = -1.0 if sign < 0 else 1.0
        n = dims[idx]
        nominal = dim_value(n)
        p, m = tolerances(n)
        lines.append(dict(index=idx, sign=int(sign),
                          nominal=round(nominal, 4), plus=p, minus=m,
                          shows=str(n.get("prefix") or "") +
                          f"{nominal:g}"))
    if not lines:
        return dict(lines=[], status="pass",
                    message="No toleranced dimension on the sheet — give "
                            "dimensions tol_plus / tol_minus first.")
    nominal = sum(x["sign"] * x["nominal"] for x in lines)
    hi = sum(x["sign"] * x["nominal"] + (x["plus"] if x["sign"] > 0
                                         else x["minus"]) for x in lines)
    lo = sum(x["sign"] * x["nominal"] - (x["minus"] if x["sign"] > 0
                                         else x["plus"]) for x in lines)
    mean = sum(x["sign"] * (x["nominal"] + (x["plus"] - x["minus"]) / 2)
               for x in lines)
    half = math.sqrt(sum(((x["plus"] + x["minus"]) / 2) ** 2
                         for x in lines))
    out = dict(lines=lines, nominal=round(nominal, 4),
               worst_min=round(lo, 4), worst_max=round(hi, 4),
               rss_min=round(mean - half, 4), rss_max=round(mean + half, 4))
    text = (f"Closing value {nominal:g}: worst case {lo:g} … {hi:g}, "
            f"RSS {mean - half:.4g} … {mean + half:.4g}.")
    if limits:
        lim_lo, lim_hi = float(limits[0]), float(limits[1])
        if lim_lo - 1e-9 <= lo and hi <= lim_hi + 1e-9:
            status = "pass"
        elif lim_lo - 1e-9 <= mean - half and mean + half <= lim_hi + 1e-9:
            status = "warn"
            text += " Only the statistical (RSS) range fits the limits."
        else:
            status = "fail"
            text += " Out of the limits — tighten the tolerances."
        out["limits"] = [lim_lo, lim_hi]
    else:
        status = "pass"
    out.update(status=status, message=text)
    return out
