"""A **custom object** made from simple shapes — the way Claude (MCP) or
a script designs a piece the Part Library does not have: a bespoke
shelf, a bar counter, a sculpture. It is a Part Library part like any
other (``custom_object``), its design kept in its dims as
``dims["_shapes"]``, so it is placed, moved, copied, saved, finished
(`part_finish`) and kept in My Library exactly as a library part is.

Each shape is a dict, lengths in mm in the object's own frame (front
-Y, back +Y, standing on z = 0), with an optional ``name`` (its
component name, for finishes), ``color`` ("#rrggbb") and ``material``
(model.MATERIALS — Wood, Fabric, Leather, Marble, Metal, Glass...):

- ``box``: corner x, y, z and w, d, h; ``r`` rounds its edges;
- ``cylinder``: base centre x, y, z, height h, radius r (``r2`` at the
  top for a cone);
- ``sphere``: centre x, y, z and radius r;
- ``rod``: a round bar from ``a`` [x, y, z] to ``b`` with radius r.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from .model import CadNode
from .part_finish import FinishError, check

PART_ID = "custom_object"
KEY = "_shapes"
MAX_SHAPES = 400
SHAPES = ("box", "cylinder", "sphere", "rod")
DEFAULT_COLOR = "#c8c3ba"

_NEEDS = {"box": ("x", "y", "z", "w", "d", "h"),
          "cylinder": ("x", "y", "z", "h", "r"),
          "sphere": ("x", "y", "z", "r"),
          "rod": ("a", "b", "r")}


class ShapeError(ValueError):
    pass


def _num(v, what):
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ShapeError(f"{what}: a number, not {v!r}.") from None
    if f != f or abs(f) > 1e6:
        raise ShapeError(f"{what}: out of range.")
    return f


def _point(v, what):
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        raise ShapeError(f"{what}: [x, y, z].")
    return [_num(c, what) for c in v]


def clean(shapes):
    """*shapes* checked and normalised, or ShapeError."""
    if not isinstance(shapes, list) or not shapes:
        raise ShapeError("'shapes' is a non-empty list.")
    if len(shapes) > MAX_SHAPES:
        raise ShapeError(f"At most {MAX_SHAPES} shapes.")
    out = []
    for i, s in enumerate(shapes):
        where = f"shape {i}"
        if not isinstance(s, dict):
            raise ShapeError(f"{where}: an object.")
        kind = str(s.get("shape", "")).strip().lower()
        if kind not in SHAPES:
            raise ShapeError(f"{where}: 'shape' is one of "
                             f"{', '.join(SHAPES)}.")
        c = {"shape": kind}
        for key in _NEEDS[kind]:
            if key not in s:
                raise ShapeError(f"{where} ({kind}) needs "
                                 f"{', '.join(_NEEDS[kind])}.")
            c[key] = (_point(s[key], f"{where}.{key}") if key in "ab"
                      else _num(s[key], f"{where}.{key}"))
        for key in ("r2",) if kind == "cylinder" else \
                ("r",) if kind == "box" else ():
            if s.get(key) is not None:
                c[key] = _num(s[key], f"{where}.{key}")
        for key in ("w", "d", "h", "r"):
            if key in c and c[key] <= 0 and not (kind == "box"
                                                 and key == "r"):
                raise ShapeError(f"{where}.{key} must be positive.")
        if s.get("name"):
            c["name"] = str(s["name"])[:60]
        try:
            look = check({"color": s.get("color"),
                          "material": s.get("material")}) \
                if (s.get("color") or s.get("material")) else {}
        except FinishError as exc:
            raise ShapeError(f"{where}: {exc}") from None
        c.update(look)
        out.append(c)
    return out


def _node(s):
    kind = s["shape"]
    name = s.get("name") or kind.capitalize()
    if kind == "box":
        r = min(s.get("r", 0.0), s["w"] / 2, s["d"] / 2, s["h"] / 2) * 0.98
        common = dict(x=s["x"], y=s["y"], z=s["z"], width=s["w"],
                      depth=s["d"], height=s["h"], center=False)
        node = CadNode("rounded_box", name, dict(common, radius=r,
                                                 segments=12)) \
            if r > 0.5 else CadNode("cube", name, common)
    elif kind == "cylinder":
        node = CadNode("cylinder", name, dict(
            x=s["x"], y=s["y"], z=s["z"], height=s["h"],
            radius_bottom=s["r"], radius_top=s.get("r2", s["r"]),
            segments=32, center=False))
    elif kind == "sphere":
        node = CadNode("sphere", name, dict(x=s["x"], y=s["y"], z=s["z"],
                                            radius=s["r"], segments=24))
    else:
        (x1, y1, z1), (x2, y2, z2) = s["a"], s["b"]
        node = CadNode("capsule", name, dict(x1=x1, y1=y1, z1=z1, x2=x2,
                                             y2=y2, z2=z2, radius=s["r"],
                                             segments=16))
    col = CadNode("color", name, dict(color=s.get("color", DEFAULT_COLOR),
                                      alpha=1.0,
                                      material=s.get("material", "Default")))
    col.add(node)
    return col


def build(dims):
    try:
        shapes = clean(dims.get(KEY) or SAMPLE)
    except ShapeError:
        shapes = SAMPLE
    part = CadNode("union", "Custom object")
    for s in shapes:
        part.add(_node(s))
    return part


#: what an empty custom object shows: a plain cube to be redesigned
SAMPLE = [{"shape": "box", "name": "Block", "x": -250.0, "y": -250.0,
           "z": 0.0, "w": 500.0, "d": 500.0, "h": 500.0,
           "color": DEFAULT_COLOR, "material": "Default"}]

PARTS = {PART_ID: dict(label="Custom object (from shapes)",
                       category="Custom objects", build=build,
                       sizes={"Custom": {}}, fields=[])}
