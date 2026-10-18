"""Weld check (Qt-free): which parts of an assembly meet so that they
could be welded, what joint that is, how long the seam, which process
(TIG, MIG, …), filler and size suit the materials and thickness — and,
for the welds the design records, whether the recorded spec holds.

A part's weld specs live on it as ``params["welds"]`` = [{with, process,
joint, size, sides, filler, note}] keyed by the OTHER part's name (no
geometry: mesh skips the key, like "bom"). Joints are read from the
parts' bounding boxes: a part whose smallest extent is well under the
next is a PLATE of that thickness; where two touch, the contact patch's
thin axis tells a lap (both plates lying on each other), a T (a plate's
edge on another's face), a corner (that edge at the face's edge) or a
butt (edge to edge). Sizes follow the usual rules of thumb (minimum
fillet legs by thickness, square butt to 3 mm, single V to 20, double V
beyond) — guidance, flagged as such, not a welding procedure.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import analysis

#: gap under which two parts are taken to touch (mm)
TOUCH = 0.05
#: a part is a plate when its thinnest extent is under this x the next
PLATE = 0.4
PROCESSES = ("TIG", "MIG", "MAG", "FCAW", "SAW", "Stick", "Laser",
             "Spot", "Brazing", "Plastic welding")
JOINTS = ("fillet", "butt", "lap", "T", "corner", "edge", "plug")

#: material word -> class
_CLASSES = (("stainless", "stainless"), ("alumin", "aluminium"),
            ("titan", "titanium"), ("copper", "copper"),
            ("brass", "brass"), ("bronze", "brass"),
            ("galvan", "steel"), ("steel", "steel"), ("iron", "steel"),
            ("pp", "plastic"), ("polyprop", "plastic"),
            ("polyeth", "plastic"), ("pe", "plastic"), ("pvc", "plastic"),
            ("pla", "unweldable"), ("abs", "unweldable"),
            ("petg", "unweldable"), ("polycarb", "unweldable"),
            ("nylon", "unweldable"), ("rubber", "unweldable"),
            ("epdm", "unweldable"), ("wood", "unweldable"),
            ("oak", "unweldable"), ("pine", "unweldable"),
            ("glass", "unweldable"), ("concrete", "unweldable"),
            ("resin", "unweldable"), ("ceramic", "unweldable"))
FILLER = {"steel": "ER70S-6", "stainless": "ER308L",
          "aluminium": "ER4043 (ER5356 for 5xxx alloys)",
          "titanium": "ERTi-2", "copper": "ERCu", "brass": "CuSi3 / brazing rod",
          "plastic": "rod of the same polymer"}


def material_class(material: str) -> str:
    low = (material or "").lower()
    import re
    for word, cls in _CLASSES:
        if re.search(r"\b" + word + (r"\b" if len(word) <= 3 else ""),
                     low):
            return cls
    return "steel" if not low else "unknown"


def plate_axis(box):
    """(thin axis, thickness, is a plate) of a bounding box."""
    lo, hi = box
    ext = [hi[k] - lo[k] for k in range(3)]
    order = sorted(range(3), key=lambda k: ext[k])
    thin = order[0]
    return thin, ext[thin], ext[thin] < PLATE * ext[order[1]]


def process_for(cls: str, t: float):
    """(process, why) for a material class and thickness in mm."""
    if cls == "aluminium":
        return ("TIG", "aluminium this thin needs TIG's AC heat control") \
            if t <= 4 else ("MIG", "pulsed MIG for thicker aluminium")
    if cls == "stainless":
        return ("TIG", "thin stainless: TIG keeps the heat tint and "
                       "distortion down") if t <= 3 else \
            ("MIG", "MIG (pulsed, tri-mix gas) for thicker stainless")
    if cls == "titanium":
        return "TIG", "titanium needs TIG with a trailing argon shield"
    if cls == "copper":
        return "TIG", "copper: TIG with preheat above ~3 mm"
    if cls == "brass":
        return "Brazing", "brass loses its zinc when fusion-welded"
    if cls == "plastic":
        return "Plastic welding", "hot-gas or extrusion welding"
    if cls == "steel":
        if t < 1.0:
            return "TIG", "sheet under 1 mm burns through with MIG"
        if t <= 8.0:
            return "MIG", "MIG/MAG is the usual process for steel 1-8 mm"
        if t <= 25.0:
            return "MIG", "multi-pass MIG/MAG (or FCAW outdoors)"
        return "SAW", "submerged arc for heavy plate"
    return "", "not a weldable material"


def fillet_leg(t: float) -> float:
    """Minimum fillet leg for the thicker... rule of thumb by the
    THINNER part, never more than it."""
    leg = 3.0 if t <= 6 else 5.0 if t <= 12 else 6.0 if t <= 20 else 8.0
    return round(min(leg, t), 2)


def butt_prep(t: float) -> str:
    if t <= 3:
        return "square butt, full penetration"
    if t <= 20:
        return "single V 60°, 1-2 mm root face"
    return "double V 60° (or U), welded both sides"


def _contact(box_a, box_b, tol):
    lo = [max(box_a[0][k], box_b[0][k]) for k in range(3)]
    hi = [min(box_a[1][k], box_b[1][k]) for k in range(3)]
    if any(hi[k] < lo[k] - tol for k in range(3)):
        return None
    return lo, [max(hi[k], lo[k]) for k in range(3)]


def joint_of(box_a, box_b, tol=TOUCH):
    """{joint, seam (one side), all_round, thickness, normal axis} of two
    touching parts, or None."""
    c = _contact(box_a, box_b, tol)
    if c is None:
        return None
    lo, hi = c
    ext = [hi[k] - lo[k] for k in range(3)]
    n = min(range(3), key=lambda k: ext[k])
    u, v = sorted(ext[k] for k in range(3) if k != n)
    ta, tha, pa = plate_axis(box_a)
    tb, thb, pb = plate_axis(box_b)
    t = min(tha, thb)
    if pa and pb and ta == n and tb == n:
        joint, seam = "lap", v
    elif (pa and ta == n) != (pb and tb == n):
        a_base = pa and ta == n
        base = box_a if a_base else box_b
        k = tb if a_base else ta        # the standing part's thickness
        at_edge = k != n and (abs(lo[k] - base[0][k]) < tol or
                              abs(hi[k] - base[1][k]) < tol)
        joint, seam = ("corner" if at_edge else "T"), v
    elif pa and pb and ta == tb:
        joint, seam = "butt", v
    else:
        joint, seam = "fillet", v
    return dict(joint=joint, seam=round(seam, 3),
                all_round=round(2 * (u + v), 3), thickness=round(t, 3),
                normal="xyz"[n])


def advise(name_a, mat_a, name_b, mat_b, joint):
    """The recommendation for one joint: process, filler, size,
    preparation, status of the material pair and messages."""
    ca, cb = material_class(mat_a), material_class(mat_b)
    t = joint["thickness"]
    notes, status = [], "pass"
    if "unweldable" in (ca, cb) or "unknown" in (ca, cb):
        bad = mat_a if ca in ("unweldable", "unknown") else mat_b
        return dict(process="", status="fail", filler="",
                    messages=[f"{bad or 'that material'} cannot be "
                              "welded — bond, fasten or redesign."])
    pair = {ca, cb}
    if pair == {"aluminium", "steel"} or pair == {"aluminium",
                                                  "stainless"}:
        return dict(process="", status="fail", filler="", messages=[
            "Aluminium cannot be fusion-welded to steel — use a bimetal "
            "transition insert, rivets or bolts."])
    if "plastic" in pair and len(pair) > 1:
        return dict(process="", status="fail", filler="",
                    messages=["Plastic cannot be welded to metal."])
    if pair == {"stainless", "steel"}:
        cls, filler = "stainless", "ER309L (dissimilar)"
        notes.append("Stainless to carbon steel: ER309L filler.")
    elif "copper" in pair or "brass" in pair:
        cls = "brass" if "brass" in pair else "copper"
        filler = FILLER[cls]
        if len(pair) > 1:
            cls = "brass"
            notes.append("Copper alloy to another metal: braze it.")
    else:
        cls = ca
        filler = FILLER.get(cls, "")
    process, why = process_for(cls, t)
    notes.append(why)
    if cls == "steel" and ("galvan" in (mat_a + mat_b).lower()):
        notes.append("Galvanised: grind the zinc off the joint and "
                     "extract the fumes.")
    if t < 0.5 and process not in ("Brazing", "Plastic welding"):
        status = "warn"
        notes.append(f"{t:g} mm is very thin — laser, spot or micro-TIG.")
        process = "Spot" if joint["joint"] == "lap" else "Laser"
    out = dict(process=process, filler=filler, status=status)
    if joint["joint"] == "butt":
        out["preparation"] = butt_prep(t)
        out["size"] = t
    else:
        out["size"] = fillet_leg(t)
        out["throat"] = round(0.7 * out["size"], 2)
    out["messages"] = notes
    return out


def check_spec(spec, advice, joint):
    """Messages and status for a RECORDED weld against the advice."""
    status, msgs = advice["status"], []
    if advice["status"] == "fail":
        return "fail", advice["messages"]
    proc = str(spec.get("process") or "")
    if not proc:
        status = "warn"
        msgs.append("No process given.")
    elif advice["process"] and proc.upper() not in (
            advice["process"].upper(),) and not (
            {proc.upper(), advice["process"].upper()} <= {"MIG", "MAG"}):
        status = "warn"
        msgs.append(f"{proc} recorded; {advice['process']} is the usual "
                    "choice here.")
    try:
        size = float(spec.get("size") or 0)
    except (TypeError, ValueError):
        size = 0.0
    t = joint["thickness"]
    if size > t + 1e-6 and joint["joint"] != "butt":
        status = "fail"
        msgs.append(f"a {size:g} mm fillet on {t:g} mm material is bigger "
                    "than the part — it will burn through or distort.")
    elif size and size < 0.5 * advice.get("size", 0):
        status = "warn" if status == "pass" else status
        msgs.append(f"{size:g} mm is under half the {advice['size']:g} "
                    "mm usual for this thickness.")
    if spec.get("joint") and spec["joint"] != joint["joint"] and \
            joint["joint"] != "fillet":
        msgs.append(f"recorded as {spec['joint']}, the parts meet as a "
                    f"{joint['joint']} joint.")
    if not msgs:
        msgs.append("Spec agrees with the geometry and materials.")
    return status, msgs


def welds(parts, specs=None, materials=None, tol=TOUCH) -> dict:
    """*parts* [(name, tris)], *specs* {frozenset(a, b): spec},
    *materials* {name: material}. One entry per touching pair: the
    joint, the advice and — for a recorded weld — its status. The
    summary judges recorded welds only; unrecorded joints are
    ``candidates``."""
    specs = specs or {}
    materials = materials or {}
    boxes = {n: analysis.bounds(t) for n, t in parts if t}
    names = [n for n, t in parts if t]
    out = []
    from .fitcheck import min_gap
    tris = dict(parts)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            spec = specs.get(frozenset((a, b)))
            joint = joint_of(boxes[a], boxes[b], tol)
            if joint is None:
                if spec:
                    out.append(dict(a=a, b=b, recorded=spec,
                                    status="fail", messages=[
                                        "A weld is recorded but the parts "
                                        "do not touch."]))
                continue
            gap = min_gap(tris[a], tris[b])[0]
            if gap > tol and not spec:
                continue
            adv = advise(a, materials.get(a, ""), b,
                         materials.get(b, ""), joint)
            entry = dict(a=a, b=b, joint=joint, advice=adv,
                         materials=[materials.get(a, ""),
                                    materials.get(b, "")],
                         gap=round(gap, 4))
            if spec:
                entry["recorded"] = spec
                entry["status"], entry["messages"] = check_spec(
                    spec, adv, joint)
                if gap > tol:
                    entry["status"] = "fail"
                    entry["messages"].append(f"{gap:.3g} gap to bridge.")
            else:
                entry["status"] = "candidate"
                entry["messages"] = adv["messages"]
            out.append(entry)
    rec = [e["status"] for e in out if e.get("recorded")]
    summary = "fail" if "fail" in rec else "warn" if "warn" in rec else \
        "pass"
    return dict(joints=out, summary=summary,
                recorded=len(rec),
                candidates=sum(1 for e in out if e["status"] ==
                               "candidate"))


def symbol_text(i, e) -> str:
    """One line of the Blueprint's weld notes (ISO 2553 words)."""
    s = e.get("recorded") or {}
    adv = e.get("advice") or {}
    joint = s.get("joint") or e.get("joint", {}).get("joint", "fillet")
    size = s.get("size") or adv.get("size", "")
    proc = s.get("process") or adv.get("process", "")
    sides = s.get("sides") or "one side"
    text = f"WELD {i}: {e['a']} TO {e['b']} — {proc} {joint}"
    if size != "":
        text += f" {'s' if joint == 'butt' else 'z'}{size:g}" \
            if isinstance(size, (int, float)) else f" {size}"
    text += f", {sides}"
    if s.get("filler") or adv.get("filler"):
        text += f", filler {s.get('filler') or adv['filler']}"
    return text.upper()
