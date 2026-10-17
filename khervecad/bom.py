"""Bill of materials (Qt-free): the document as an engineering BOM.

`build(model)` walks the tree the way it is assembled — Objects and
their instances are ASSEMBLIES and PARTS, nested Objects are
sub-assemblies, and inside a part every LABELLED node ("Cube [Copper
tube]", the `// Copper tube` comment of the program) is a COMPONENT,
grouped by its label so 140 aluminium fins are one line with quantity
140. A component inside a for loop counts once per iteration.

Every line gets an item number ("1", "1.3", "1.3.2"), a part number,
a description written from what the node IS (a tube's outside diameter
and length, a cylinder's diameter and height, a plate's thickness), a
quantity and unit (pieces, or metres for tube, pipe and cable), the
material (set by hand, else read from the label — "copper", "brass",
"rubber" — or from the colour node above it, marked `estimated`), the
finish / colour, the bounding size, mass each and total (volume from
the preview mesh × the material's density) and cost.

Anything typed by hand lives on the node as `params["bom"]` — part_no,
description, material, finish, supplier, cost, unit, notes, exclude —
so it is saved in the .kcad, undone with the rest, and follows the part
when it moves. `set_fields` writes it on every node of a grouped line.

Exports: CSV, XLSX (written here — no openpyxl), HTML and JSON.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import csv
import html
import io
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import analysis
from .model import name_tag

#: the BOM columns: key, heading, what the table and exports show
COLUMNS = (
    ("item", "Item"), ("part_no", "Part no."), ("name", "Name"),
    ("description", "Description"), ("qty", "Qty"), ("unit", "Unit"),
    ("material", "Material"), ("finish", "Finish / colour"),
    ("size", "Size L × W × H (mm)"), ("mass_each", "Mass each (kg)"),
    ("mass_total", "Mass total (kg)"), ("cost_each", "Unit cost"),
    ("cost_total", "Total cost"), ("supplier", "Supplier"),
    ("source", "Source"), ("notes", "Notes"),
)
#: what a user may type into a line (stored in params["bom"])
EDITABLE = ("part_no", "description", "material", "finish", "supplier",
            "cost", "mass", "unit", "notes", "exclude")
#: single-child wrappers a label may sit under: the piece is the whole
#: chain (a tube's label lands on the circle inside its sweep)
_CHAIN = {"color", "translate", "rotate", "scale", "mirror", "union",
          "sweep", "linear_extrude", "rotate_extrude", "resize",
          "multmatrix", "offset", "render"}

#: densities in g/cm³: the print materials of analysis.py and what
#: machines are made of
DENSITY = dict(analysis.MATERIALS)
DENSITY.update({
    "Copper": 8.96, "Brass": 8.47, "Bronze": 8.80,
    "Stainless steel": 8.00, "Galvanised steel": 7.85,
    "Cast iron": 7.20, "Aluminium": 2.70, "Zinc": 7.13, "Lead": 11.34,
    "Gold": 19.3, "Silver": 10.5,
    "Concrete": 2.40, "Glass": 2.50, "Polycarbonate": 1.20,
    "Acrylic": 1.18, "PVC": 1.38, "Polypropylene": 0.91,
    "Polyethylene": 0.95, "EPDM rubber": 1.15, "Rubber": 1.10,
    "Silicone": 1.10, "Elastomeric foam": 0.065, "PU foam": 0.04,
    "FR4 (PCB)": 1.85, "Ceramic": 2.40, "Wood": 0.60, "Oak": 0.75,
    "Plywood": 0.60, "MDF": 0.75, "Paper": 0.80, "Fabric": 0.30,
    "Leather": 0.86, "Stone": 2.60, "Marble": 2.70, "Granite": 2.70,
    "Brick": 1.90, "Water": 1.00, "Cable (Cu/PVC)": 2.60,
})

#: words in a label that name the material outright (first match wins,
#: so "stainless" is before "steel" and "copper" before "pipe")
_WORDS = (
    ("stainless", "Stainless steel"), ("galvan", "Galvanised steel"),
    ("cast iron", "Cast iron"), ("copper", "Copper"), ("brass", "Brass"),
    ("bronze", "Bronze"), ("alumin", "Aluminium"), ("steel", "Steel"),
    ("titanium", "Titanium"), ("concrete", "Concrete"),
    ("glass", "Glass"), ("polycarbonate", "Polycarbonate"),
    ("acrylic", "Acrylic"), ("pvc", "PVC"), ("rubber", "EPDM rubber"),
    ("grommet", "EPDM rubber"), ("gasket", "EPDM rubber"),
    ("insulation", "Elastomeric foam"), ("lagging", "Elastomeric foam"),
    ("foam", "Elastomeric foam"), ("pcb", "FR4 (PCB)"),
    ("circuit board", "FR4 (PCB)"), ("cable", "Cable (Cu/PVC)"),
    ("wire", "Cable (Cu/PVC)"), ("ceramic", "Ceramic"),
    ("wood", "Wood"), ("timber", "Wood"), ("plywood", "Plywood"),
    ("mdf", "MDF"), ("marble", "Marble"), ("granite", "Granite"),
    ("stone", "Stone"), ("brick", "Brick"), ("fabric", "Fabric"),
    ("leather", "Leather"), ("silicone", "Silicone"),
    ("pad", "Concrete"), ("plinth", "Concrete"), ("pla", "PLA"), ("petg", "PETG"), ("abs", "ABS"),
)
#: what a colour node's material says when no word does
_FINISH_MATERIAL = {"Metal": "Steel", "Gold": "Brass", "Copper": "Copper",
                    "Glass": "Polycarbonate", "Rubber": "EPDM rubber",
                    "Clay": "Ceramic", "Skin": "Silicone",
                    "Emissive": "Polycarbonate"}
#: labels that make a line a length of stock (metres, not pieces)
_LENGTH_WORDS = ("pipe", "tube", "line", "cable", "wire", "hose",
                 "capillary", "insulation", "lagging", "rod", "bar",
                 "rail", "profile", "extrusion")
#: node types that never carry a component of their own
_STRUCTURAL = {"root", "variables", "masters", "assign", "if_else",
               "for_loop", "while_loop"}


@dataclass
class Line:
    """One BOM line. *nodes* are the tree nodes it stands for (several
    for a grouped component); *children* its own lines."""
    level: int
    kind: str                      # assembly | part | component | loose
    name: str
    nodes: list
    qty: float = 1.0
    unit: str = "pc"
    values: dict = field(default_factory=dict)
    estimated: bool = False
    children: list = field(default_factory=list)
    #: component lines a coarser BOM does not list but still weighs
    hidden: list = field(default_factory=list)

    def get(self, key, default=""):
        return self.values.get(key, default)


@dataclass
class Bom:
    title: str
    lines: list                     # top-level Lines (a tree)
    currency: str = analysis.DEFAULT_CURRENCY
    warnings: list = field(default_factory=list)

    def flat(self, max_level=None):
        """Every line, depth first, as (Line) — the indented BOM."""
        out = []

        def walk(lines):
            for ln in lines:
                if max_level is None or ln.level <= max_level:
                    out.append(ln)
                walk(ln.children)
        walk(self.lines)
        return out

    def rows(self, max_level=None):
        """The table: one dict per line, every COLUMNS key filled in."""
        return [dict(line_row(ln), level=ln.level, kind=ln.kind,
                     estimated=ln.estimated,
                     node_ids=[n.id for n in ln.nodes])
                for ln in self.flat(max_level)]

    def totals(self):
        """Whole-assembly figures, from the top-level lines (whose own
        totals include everything under them)."""
        mass = sum(ln.get("mass_total", 0.0) or 0.0 for ln in self.lines)
        cost = sum(ln.get("cost_total", 0.0) or 0.0 for ln in self.lines)
        parts = sum(1 for ln in self.flat() if ln.kind == "component")
        unique = len({(ln.name, ln.get("material")) for ln in self.flat()
                      if ln.kind in ("component", "part", "loose")})
        return {"mass_kg": round(mass, 3), "cost": round(cost, 2),
                "lines": len(self.flat()), "component_lines": parts,
                "unique_items": unique, "currency": self.currency}

    def summary_by_material(self):
        """{material: kg} over the leaf lines — a quick costing view."""
        out = {}
        for ln in self.flat():
            if ln.children:
                continue
            m = ln.get("material") or "Unknown"
            out[m] = out.get(m, 0.0) + (ln.get("mass_total", 0.0) or 0.0)
        return {k: round(v, 3) for k, v in sorted(
            out.items(), key=lambda kv: -kv[1])}


# ── reading the tree ───────────────────────────────────────────────

def overrides(node):
    """The hand-typed BOM fields on *node* (a copy)."""
    got = node.params.get("bom")
    return dict(got) if isinstance(got, dict) else {}


def set_fields(nodes, fields):
    """Write hand-typed *fields* on every node of a line. An empty value
    removes the override (the line goes back to what it reads)."""
    for node in nodes:
        data = overrides(node)
        for key, value in fields.items():
            if key not in EDITABLE:
                raise KeyError(f"not a BOM field: {key}")
            if value in ("", None):
                data.pop(key, None)
            else:
                data[key] = value
        if data:
            node.params["bom"] = data
        else:
            node.params.pop("bom", None)


def build(model, detail="components", fn=None, scope=None):
    """The BOM of *model* (or of the Object *scope*). *detail*:
    "assemblies" (Objects only), "parts" (Objects and loose parts) or
    "components" (every labelled piece inside a part too)."""
    from . import mesh
    root = scope or model.root
    defs = {c.name: c for c in model.all_components()}
    title = scope.name if scope is not None else (
        getattr(model, "title", "") or _doc_title(model))
    bom = Bom(title, [])
    ctx = _Context(model, defs, detail,
                   fn if fn is not None else model.effective_fn(), mesh)
    if scope is not None:
        top = _part_line(ctx, scope, 0, 1)
        bom.lines = top.children if top.children else [top]
        for ln in bom.lines:
            _relevel(ln, 0)
    else:
        bom.lines = _assembly_lines(ctx, root, 0)
    _number(bom.lines, "")
    prefix = _prefix(title)
    for ln in bom.flat():
        if not ln.get("part_no"):
            ln.values["part_no"] = prefix + "-" + "-".join(
                f"{int(p):02d}" for p in ln.values["item"].split("."))
    bom.warnings = ctx.warnings
    return bom


def _doc_title(model):
    comps = [c for c in model.components() if c.visible]
    if len(comps) == 1:
        return comps[0].name
    return "Assembly"


def _prefix(title):
    words = re.findall(r"[A-Za-z0-9]+", title or "")
    letters = "".join(w[0] for w in words if not w.isdigit())[:4].upper()
    return letters or "PART"


def _relevel(line, level):
    line.level = level
    for ch in line.children:
        _relevel(ch, level + 1)


def _number(lines, stem):
    for i, ln in enumerate(lines, 1):
        ln.values["item"] = f"{stem}{i}"
        _number(ln.children, f"{stem}{i}.")


class _Context:
    def __init__(self, model, defs, detail, fn, mesh):
        self.model, self.defs, self.detail = model, defs, detail
        self.fn, self.mesh = fn, mesh
        self.warnings = []
        self._volumes = {}


def _assembly_lines(ctx, container, level):
    """The lines of whatever *container* places: visible Objects (plus
    every instance of each), instances of hidden definitions, and loose
    visible geometry."""
    lines, by_def = [], {}
    for child in container.children:
        if child.type in ("variables", "masters", "assign"):
            continue
        if child.type == "component":
            count = len([n for n in container.children
                         if n.type == "reference"
                         and n.params.get("ref") == child.name])
            qty = (1 if child.visible else 0) + count
            if qty and child.name not in by_def:
                ln = _part_line(ctx, child, level, qty)
                by_def[child.name] = ln
                lines.append(ln)
        elif child.type == "reference":
            comp = ctx.defs.get(child.params.get("ref"))
            if comp is None or comp.name in by_def:
                continue
            if comp.parent is container:
                continue        # counted with its definition above
            qty = len([n for n in container.children
                       if n.type == "reference"
                       and n.params.get("ref") == comp.name])
            ln = _part_line(ctx, comp, level, qty, via=child)
            by_def[comp.name] = ln
            lines.append(ln)
        elif child.visible and ctx.detail != "assemblies":
            ln = _loose_line(ctx, child, level)
            if ln is not None:
                lines.append(ln)
    return [ln for ln in lines if not ln.values.get("exclude")]


def _part_line(ctx, comp, level, qty, via=None):
    """An Object: an assembly if it holds Objects (or instances), a part
    otherwise; with "components" detail its labelled pieces go under."""
    sub = _assembly_lines(ctx, comp, level + 1) if any(
        c.type in ("component", "reference") for c in _flatten(comp)) \
        else []
    sub = [s for s in sub if s.kind != "loose"] or sub
    kind = "assembly" if any(s.kind in ("assembly", "part")
                             for s in sub) else "part"
    ln = Line(level, kind, comp.name, [comp] + ([via] if via else []),
              qty=qty)
    if kind == "part":
        comps = _component_lines(ctx, comp, level + 1)
        if ctx.detail == "components":
            ln.children = comps
        else:
            ln.hidden = comps     # still weigh it and name its material
    elif kind == "assembly":
        ln.children = sub
        if ctx.detail == "components":
            loose = _component_lines(ctx, comp, level + 1, shallow=True)
            ln.children += loose
    _fill(ctx, ln, comp)
    return ln


def _flatten(node):
    """*node*'s descendants down to (and including) the first Objects
    and instances — what it places, not what those hold."""
    out = []
    for child in node.children:
        out.append(child)
        if child.type not in ("component", "reference"):
            out.extend(_flatten(child))
    return out


def _loose_line(ctx, node, level):
    if node.type in _STRUCTURAL and node.type not in (
            "for_loop", "while_loop", "if_else"):
        return None
    name = name_tag(node.name) or node.name
    ln = Line(level, "loose", name, [node])
    if ctx.detail == "components":
        ln.children = _component_lines(ctx, node, level + 1)
    _fill(ctx, ln, node)
    return ln


def _component_lines(ctx, part, level, shallow=False):
    """The labelled pieces of *part*, grouped by (label, material,
    size): a line each, its quantity counting loop iterations."""
    groups, order = {}, []

    def walk(node, mult):
        for child in node.children:
            if child.type in ("component", "reference"):
                continue
            if child.type in ("variables", "masters", "assign"):
                continue
            if not child.visible:
                continue
            m = mult
            if child.type in ("for_loop", "while_loop"):
                m = mult * _iterations(child)
            tag = name_tag(child.name) or _chain_tag(child)
            if tag:
                key = _group_key(ctx, child, tag)
                if key not in groups:
                    groups[key] = []
                    order.append(key)
                groups[key].append((child, m))
                continue
            walk(child, m)
    walk(part, 1)
    lines = []
    for key in order:
        members = groups[key]
        first = members[0][0]
        if not _volume_of(ctx, first) and key[2] is not None and \
                min(key[2]) < 1e-6:
            continue        # a flat decal (text, a 2D mark): no stock
        ln = Line(level, "component", key[0], [n for n, _m in members],
                  qty=float(sum(m for _n, m in members)))
        _fill(ctx, ln, first, members, part=part)
        if not ln.values.get("exclude"):
            lines.append(ln)
    return lines


def _chain_tag(node):
    """The label on the one piece at the bottom of *node*'s single-child
    chain of wrappers (colour, move, sweep, extrude), if any."""
    n = node
    while n.type in _CHAIN and len(n.children) == 1:
        n = n.children[0]
        tag = name_tag(n.name)
        if tag:
            return tag
    return ""


def piece_tag(node):
    return name_tag(node.name) or _chain_tag(node)


def _group_key(ctx, node, tag):
    size = _size_of(ctx, node)
    return (tag, _material_of(node, tag, _part_name(node))[0],
            tuple(round(v, 1) for v in size) if size else None)


def _iterations(loop):
    from .bake import _codegen_env
    try:
        return max(1, len(list(loop.loop_values(_codegen_env(loop)))))
    except Exception:                        # noqa: BLE001
        return 1


# ── what a line says ───────────────────────────────────────────────

def line_row(ln):
    """*ln* as table cells (strings and numbers)."""
    v = ln.values
    row = {}
    for key, _head in COLUMNS:
        value = v.get(key, "")
        if key == "qty":
            value = _fmt_qty(ln.qty, ln.unit)
        elif key == "unit":
            value = ln.unit
        elif key == "name":
            value = ln.name
        elif key in ("mass_each", "mass_total"):
            value = round(value, 4) if isinstance(value, float) else ""
        elif key in ("cost_each", "cost_total"):
            value = round(value, 2) if isinstance(value, float) else ""
        elif key == "material" and value and ln.estimated:
            value = f"{value} (est.)"
        row[key] = value
    return row


def _fmt_qty(qty, unit):
    if unit == "pc":
        return int(round(qty))
    return round(qty, 3)


def _part_name(node):
    n = node.parent
    while n is not None and n.type not in ("component", "root"):
        n = n.parent
    return n.name if n is not None and n.type == "component" else ""


def _fill(ctx, ln, node, members=None, part=None):
    """Description, material, size, mass and cost of *ln*, then the
    hand-typed overrides on top."""
    tag = piece_tag(node) if ln.kind == "component" else ""
    label = tag or ln.name
    material, estimated = _material_of(node, label, _part_name(node))
    inside = ln.children or ln.hidden
    if inside and "material" not in overrides(node):
        # an assembly or part is mostly what its heaviest pieces are
        weight = {}
        for ch in inside:
            m = ch.get("material")
            if m:
                weight[m] = weight.get(m, 0.0) + (ch.get("mass_total", 0.0)
                                                  or 0.0)
        if weight:
            material = max(weight, key=weight.get)
            estimated = any(ch.estimated for ch in inside
                            if ch.get("material") == material)
    ln.estimated = estimated
    v = ln.values
    v["material"] = material
    v["finish"] = _finish_of(node)
    size = _size_of(ctx, node)
    v["size"] = " × ".join(_num(s) for s in size) if size else ""
    v["source"] = _source_of(node)
    length = _stock_length(ctx, node, label)
    if length and ln.kind == "component":
        # stock sold by length: quantity in metres, mass per metre
        ln.unit = "m"
        each_m = length / 1000.0
        ln.qty = round(sum(m for _n, m in (members or [(node, 1)]))
                       * each_m, 3)
        v["description"] = _describe(node, label, length)
    else:
        v["description"] = _describe(node, label, size=size, ln=ln)
    vol = _volume_of(ctx, node)
    density = DENSITY.get(material)
    if inside:
        # an assembly weighs what is in it
        total = sum(ch.get("mass_total", 0.0) or 0.0 for ch in inside)
        each = total
        if not total and vol and density:
            each = vol / 1000.0 * density / 1000.0
        v["mass_each"] = each
        v["mass_total"] = each * ln.qty
        cost = sum(ch.get("cost_total", 0.0) or 0.0 for ch in inside)
        v["cost_each"] = cost
        v["cost_total"] = cost * ln.qty
    else:
        each = vol / 1000.0 * density / 1000.0 if vol and density else 0.0
        if ln.unit == "m" and ln.qty:
            pieces = sum(m for _n, m in (members or [(node, 1)]))
            v["mass_each"] = each * pieces / ln.qty     # kg per metre
            v["mass_total"] = each * pieces
        else:
            v["mass_each"] = each
            v["mass_total"] = each * ln.qty
        v["cost_each"] = 0.0
        v["cost_total"] = 0.0
    if density is None and material:
        ctx.warnings.append(f"{ln.name}: no density for {material}")
    o = overrides(node)
    for key in ("part_no", "description", "finish", "supplier", "notes",
                "exclude"):
        if key in o:
            v[key] = o[key]
    if "unit" in o:
        ln.unit = str(o["unit"])
    if "material" in o:
        v["material"] = str(o["material"])
        ln.estimated = False
        d = DENSITY.get(v["material"])
        if d and vol and not ln.children:
            each = vol / 1000.0 * d / 1000.0
            v["mass_each"] = each
            v["mass_total"] = each * (ln.qty if ln.unit == "pc" else
                                      sum(m for _n, m in (members or
                                                          [(node, 1)])))
    if "mass" in o:
        try:
            v["mass_each"] = float(o["mass"])
            v["mass_total"] = float(o["mass"]) * ln.qty
        except (TypeError, ValueError):
            pass
    if "cost" in o:
        try:
            v["cost_each"] = float(o["cost"])
            v["cost_total"] = float(o["cost"]) * ln.qty
        except (TypeError, ValueError):
            pass
    if "source" in o:
        v["source"] = o["source"]


def _num(x):
    if abs(x) >= 10:
        return f"{x:.0f}"
    return f"{x:.1f}".rstrip("0").rstrip(".") or "0"


def _colour_node(node):
    n = node
    while n is not None and n.type not in ("root",):
        if n.type == "color":
            return n
        for ch in n.children[:1]:
            if ch.type == "color" and n is node:
                return ch
        n = n.parent
    return None


def _rgb(value):
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return tuple(float(c) for c in value[:3])
        except (TypeError, ValueError):
            return None
    text = str(value or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", text):
        return tuple(int(text[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    return None


def _material_of(node, label, part=""):
    """(material, estimated) — a word in the label (then in the part's
    name, "Concrete pad"), else the colour node's material and hue."""
    o = overrides(node)
    if o.get("material"):
        return str(o["material"]), False
    low = (label or "").lower()
    for text in (low, (part or "").lower()):
        for word, material in _WORDS:
            # a word START ("alumin" in aluminium) — "pla" must not
            # match "plate"
            if re.search(r"\b" + re.escape(word) + (
                    r"\b" if len(word) <= 4 else ""), text):
                return material, text is not low
    col = _colour_node(node)
    if col is None:
        return "", True
    rgb = _rgb(col.params.get("color"))
    finish = str(col.params.get("material", "Default"))
    if rgb:
        r, g, b = rgb
        if r > 0.65 and 0.35 < g < 0.62 and b < 0.36:
            return "Copper", True
        if r > 0.7 and g > 0.55 and b < 0.42 and r - b > 0.3:
            return "Brass", True
    if finish in _FINISH_MATERIAL:
        return _FINISH_MATERIAL[finish], True
    alpha = col.params.get("alpha", 1.0)
    try:
        if float(alpha) < 0.5:
            return "Polycarbonate", True
    except (TypeError, ValueError):
        pass
    if rgb and max(rgb) - min(rgb) < 0.08:
        if max(rgb) < 0.2:
            return "EPDM rubber" if "foot" in low or "grommet" in low \
                else "Steel", True
        return "Galvanised steel", True
    return "Steel", True


def _finish_of(node):
    col = _colour_node(node)
    if col is None:
        return ""
    rgb = _rgb(col.params.get("color"))
    colour = _colour_name(rgb) if rgb else str(col.params.get("color", ""))
    finish = str(col.params.get("material", "Default"))
    parts = [colour]
    if finish not in ("Default", ""):
        parts.append(finish.lower())
    try:
        if float(col.params.get("alpha", 1.0)) < 0.99:
            parts.append("translucent")
    except (TypeError, ValueError):
        pass
    return ", ".join(p for p in parts if p)


_NAMED = (("black", (0.08, 0.08, 0.08)), ("white", (0.95, 0.95, 0.95)),
          ("light grey", (0.75, 0.76, 0.78)), ("grey", (0.5, 0.5, 0.52)),
          ("dark grey", (0.25, 0.25, 0.27)), ("red", (0.8, 0.12, 0.1)),
          ("orange", (0.95, 0.55, 0.15)), ("yellow", (0.95, 0.85, 0.2)),
          ("green", (0.12, 0.5, 0.22)), ("blue", (0.12, 0.3, 0.8)),
          ("light blue", (0.5, 0.7, 0.95)), ("navy", (0.1, 0.12, 0.35)),
          ("copper", (0.8, 0.47, 0.24)), ("brass", (0.82, 0.66, 0.3)),
          ("brown", (0.45, 0.3, 0.15)), ("purple", (0.5, 0.2, 0.6)),
          ("pink", (0.95, 0.6, 0.7)), ("concrete", (0.63, 0.63, 0.6)))


def _colour_name(rgb):
    return min(_NAMED, key=lambda kv: sum(
        (a - b) ** 2 for a, b in zip(rgb, kv[1])))[0]


def _source_of(node):
    lib = node.params.get("library")
    if isinstance(lib, dict) and lib.get("title"):
        return "My library: " + str(lib["title"])
    part = node.params.get("library_part")
    if part:
        return "Library: " + str(part)
    if node.type == "stl_import":
        return "Imported mesh"
    return "Designed"


# ── geometry ───────────────────────────────────────────────────────

def _tris(ctx, node):
    """*node*'s own triangles, in its parent's frame, with the variables
    of its scope (loop variables at their first value)."""
    key = node.id
    got = ctx._volumes.get(("tris", key))
    if got is not None:
        return got
    from .bake import _codegen_env
    env = _codegen_env(node)
    n = node.parent
    while n is not None:
        if n.type in ("for_loop", "while_loop"):
            var = str(n.params.get("variable", "i")) or "i"
            if var not in env:
                try:
                    env[var] = next(iter(n.loop_values(env)))
                except Exception:              # noqa: BLE001
                    env[var] = 0
        n = n.parent
    saved = node.visible
    try:
        node.visible = True
        tris = ctx.mesh.tessellate(node, env, fn=min(ctx.fn or 24, 24))
    except Exception as exc:                   # noqa: BLE001
        ctx.warnings.append(f"{node.name}: no geometry ({exc})")
        tris = []
    finally:
        node.visible = saved
    ctx._volumes[("tris", key)] = tris
    return tris


def _size_of(ctx, node):
    tris = _tris(ctx, node)
    if not tris:
        return None
    pts = [p for t in tris for p in t]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return [hi[i] - lo[i] for i in range(3)]


def _volume_of(ctx, node):
    """mm³ — the signed volume of the preview mesh (open meshes, a sheet
    or a 2D shape, come back near zero, which is honest)."""
    got = ctx._volumes.get(("vol", node.id))
    if got is None:
        tris = _tris(ctx, node)
        got = abs(analysis.mass_properties(tris)["volume"]) if tris \
            else 0.0
        ctx._volumes[("vol", node.id)] = got
    return got


def _sweep_of(node):
    for n in [node] + list(node.walk()):
        if n.type == "sweep":
            return n
    return None


def _stock_length(ctx, node, label):
    """mm of tube / cable a component stands for, or 0: a sweep's path
    length, else a long thin box's or cylinder's long side when the
    label says it is stock."""
    low = (label or "").lower()
    if not any(w in low for w in _LENGTH_WORDS):
        return 0.0
    sw = _sweep_of(node)
    if sw is not None:
        pts = sw.params.get("path") or []
        try:
            pts = [[float(c) for c in p] for p in pts]
        except (TypeError, ValueError):
            pts = []
        if len(pts) >= 2:
            return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
    size = _size_of(ctx, node)
    if size:
        s = sorted(size)
        if s[2] > 4 * max(s[1], 1e-6):
            return s[2]
    return 0.0


def _profile_diameter(node):
    sw = _sweep_of(node)
    if sw is None:
        return None
    for n in sw.walk():
        if n.type == "circle":
            try:
                return 2.0 * float(n.params.get("r", 0))
            except (TypeError, ValueError):
                return None
    return None


#: what a wrapper turns its 2D content into, for descriptions
_MAKERS = {"rotate_extrude": "turned ring / revolved section",
           "linear_extrude": "extruded profile", "sweep": "swept section",
           "offset": "profile"}


def _describe(node, label, length=0.0, size=None, ln=None):
    """A sentence of what the node IS, from its type and numbers."""
    o = overrides(node)
    if o.get("description"):
        return str(o["description"])
    lib = node.params.get("library")
    if isinstance(lib, dict) and lib.get("description"):
        first = str(lib["description"]).split(". ")[0]
        return first[:160]
    d = _profile_diameter(node)
    if length and d:
        return f"{label}, Ø{_num(d)} mm OD, {length / 1000.0:.3f} m a piece"
    if length:
        return f"{label}, {length / 1000.0:.3f} m a piece"
    if node.type == "component" and ln is not None:
        inside = ln.children or ln.hidden
        pieces = sum(int(round(c.qty)) if c.unit == "pc" else 1
                     for c in inside)
        dims = (", " + " × ".join(_num(x) for x in size) + " mm") \
            if size else ""
        if inside:
            return (f"{label}{dims}; {len(inside)} kinds of component, "
                    f"{pieces} pieces")
        return f"{label}{dims}"
    from . import mesh
    from .bake import _codegen_env
    leaf, scaled, made = node, False, None
    while len(leaf.children) == 1 and leaf.type in _CHAIN:
        scaled = scaled or leaf.type in ("scale", "resize", "multmatrix")
        if made is None and leaf.type in _MAKERS:
            made = _MAKERS[leaf.type]
        leaf = leaf.children[0]
    if made is not None and size:
        return f"{label}: {made}, " + " × ".join(_num(x) for x in size) \
            + " mm overall"
    try:
        p = mesh.rp(leaf, _codegen_env(leaf))
    except Exception:                          # noqa: BLE001
        p = {}

    def f(key):
        try:
            return float(p.get(key))
        except (TypeError, ValueError):
            return None
    t = leaf.type
    if not scaled and t == "cylinder":
        r1, r2, h = f("radius_bottom"), f("radius_top"), f("height")
        if None not in (r1, r2, h):
            if abs(r1 - r2) < 1e-6:
                return f"{label}: cylinder Ø{_num(2 * r1)} × {_num(h)} mm"
            return (f"{label}: cone Ø{_num(2 * r1)} → Ø{_num(2 * r2)} × "
                    f"{_num(h)} mm")
    if not scaled and t == "cube":
        dims = [f("width"), f("depth"), f("height")]
        if None not in dims:
            small = sorted(dims)
            if small[0] < 0.2 * small[1]:
                return (f"{label}: plate {_num(small[0])} mm thick, "
                        f"{_num(small[2])} × {_num(small[1])} mm")
            return f"{label}: block " + " × ".join(_num(x) for x in dims) \
                + " mm"
    if not scaled and t == "sphere" and f("radius") is not None:
        return f"{label}: sphere Ø{_num(2 * f('radius'))} mm"
    from .model import NODE_TYPES
    kind = NODE_TYPES.get(t, {}).get("label", t).lower()
    if scaled and t == "sphere":
        kind = "dome / ellipsoid"
    if size:
        return f"{label}: {kind}, " + " × ".join(_num(x) for x in size) \
            + " mm overall"
    return f"{label} ({kind})"


def world_box(model, line, fn=None, stop=None):
    """(lo, hi) of *line*'s first node in world millimetres (in the
    frame of the Object *stop* when given), or None."""
    from . import mesh
    from .bake import _codegen_env
    node = line.nodes[0] if line.nodes else None
    if node is None:
        return None
    saved = node.visible
    try:
        node.visible = True
        tris = mesh.tessellate(node, _codegen_env(node),
                               fn=min(fn or model.effective_fn() or 24, 16))
    except Exception:                          # noqa: BLE001
        return None
    finally:
        node.visible = saved
    if not tris:
        return None
    m = mesh.ancestor_matrix(node, anchors_env(model), stop=stop)
    pts = [p for t in tris for p in t]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
               for z in (lo[2], hi[2])]
    world = [[sum(m[r][c] * q[c] for c in range(3)) + m[r][3]
              for r in range(3)] for q in corners]
    return ([min(p[i] for p in world) for i in range(3)],
            [max(p[i] for p in world) for i in range(3)])


def anchors_env(model):
    from .anchors import doc_env
    try:
        return doc_env(model)
    except Exception:                          # noqa: BLE001
        return {}


def sheet_lines(model, detail="parts", most=40):
    """The lines a drawing's parts list shows: the parts of the drawn
    assembly — looking inside a lone wrapping Object, as a library part
    or Make Object leaves one — at most *most*."""
    b = build(model, detail)
    lines = [ln for ln in b.lines if ln.kind in ("part", "assembly")]
    while len(lines) == 1 and \
            any(c.kind in ("part", "assembly") for c in lines[0].children):
        lines = [c for c in lines[0].children
                 if c.kind in ("part", "assembly")]
    # loose shapes are one part's construction, not a parts list
    return b, lines[:most]


# ── exports ────────────────────────────────────────────────────────

def _headers(columns=None):
    keys = [k for k, _h in COLUMNS if columns is None or k in columns]
    heads = [h for k, h in COLUMNS if k in keys]
    return keys, heads


def to_csv(bom, path=None, columns=None, indent=True):
    keys, heads = _headers(columns)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Level"] + heads)
    for row in bom.rows():
        cells = [row["level"]]
        for k in keys:
            value = row[k]
            if k == "name" and indent:
                value = "  " * row["level"] + str(value)
            cells.append(value)
        w.writerow(cells)
    t = bom.totals()
    w.writerow([])
    w.writerow(["", "TOTAL", "", "", "", "", "", "", "", "", "",
                t["mass_kg"], "", t["cost"]])
    text = buf.getvalue()
    if path:
        Path(path).write_text(text, encoding="utf-8-sig")
    return text


def to_json(bom, path=None):
    data = {"title": bom.title, "columns": [k for k, _h in COLUMNS],
            "rows": bom.rows(), "totals": bom.totals(),
            "by_material_kg": bom.summary_by_material(),
            "warnings": bom.warnings}
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if path:
        Path(path).write_text(text, encoding="utf-8")
    return text


def to_html(bom, path=None, columns=None):
    keys, heads = _headers(columns)
    t = bom.totals()
    out = ["<!doctype html><meta charset='utf-8'>",
           f"<title>{html.escape(bom.title)} — bill of materials</title>",
           "<style>body{font:13px system-ui,sans-serif;margin:24px}"
           "table{border-collapse:collapse;width:100%}"
           "th,td{border:1px solid #bbb;padding:3px 6px;text-align:left}"
           "th{background:#e8ecf2}tr.l0{font-weight:600;background:#f4f6f9}"
           "td.n{text-align:right}</style>",
           f"<h1>{html.escape(bom.title)}</h1>",
           "<p>Bill of materials. Total mass "
           f"{t['mass_kg']} kg; {t['lines']} lines, "
           f"{t['unique_items']} different items.</p>",
           "<table><tr><th>Level</th>" +
           "".join(f"<th>{html.escape(h)}</th>" for h in heads) + "</tr>"]
    for row in bom.rows():
        cells = []
        for k in keys:
            value = html.escape(str(row[k]))
            if k == "name":
                value = "&nbsp;&nbsp;" * row["level"] + value
            cls = " class='n'" if isinstance(row[k], (int, float)) else ""
            cells.append(f"<td{cls}>{value}</td>")
        out.append(f"<tr class='l{min(row['level'], 1)}'>"
                   f"<td>{row['level']}</td>{''.join(cells)}</tr>")
    out.append("</table>")
    mats = bom.summary_by_material()
    if mats:
        out.append("<h2>Mass by material</h2><table><tr><th>Material</th>"
                   "<th>kg</th></tr>" + "".join(
                       f"<tr><td>{html.escape(m)}</td><td class='n'>{kg}"
                       "</td></tr>" for m, kg in mats.items()) + "</table>")
    text = "\n".join(out)
    if path:
        Path(path).write_text(text, encoding="utf-8")
    return text


def to_xlsx(bom, path, columns=None):
    """A real .xlsx: the BOM sheet (indented names, numbers as numbers,
    a totals row) and a mass-by-material sheet — `xlsx.write`."""
    from . import xlsx
    keys, heads = _headers(columns)
    rows = [["Level"] + heads]
    for row in bom.rows():
        cells = [row["level"]]
        for k in keys:
            value = row[k]
            if k == "name":
                value = "    " * row["level"] + str(value)
            cells.append(value)
        rows.append(cells)
    t = bom.totals()
    total = [""] * (len(keys) + 1)
    total[1] = "TOTAL"
    if "mass_total" in keys:
        total[keys.index("mass_total") + 1] = t["mass_kg"]
    if "cost_total" in keys:
        total[keys.index("cost_total") + 1] = t["cost"]
    rows += [[], total]
    mats = [["Material", "Mass (kg)"]] + [
        [m, kg] for m, kg in bom.summary_by_material().items()]
    return xlsx.write(path, {"BOM": rows, "By material": mats})


def part_bom(model, comp, detail="components"):
    """The BOM of ONE Object, cut from the whole design's BOM so its
    item and part numbers are the same everywhere: its lines re-rooted
    at level 0 under a title of the Object's name and part number."""
    whole = build(model, detail)
    for ln in whole.flat():
        if ln.kind in ("part", "assembly") and comp in ln.nodes:
            lines = list(ln.children) or [ln]
            for c in lines:
                _relevel(c, 0)
            sub = Bom(f"{ln.name} ({ln.get('part_no')})", lines,
                      warnings=whole.warnings)
            return sub
    sub = build(model, detail, scope=comp)
    return sub


def parts_of(model):
    """[(name, Object)] with a BOM of their own: every part and
    sub-assembly in BOM order, each definition once."""
    from .drawing_set import parts
    return parts(model)


def export_per_part(model, path, detail="components"):
    """Every Object's own BOM. *path* .xlsx: one workbook, a Summary
    sheet (the whole design) then a sheet per Object; anything else: a
    folder of CSV files, one per Object plus the summary."""
    from . import xlsx
    path = Path(path)
    items = [(name, part_bom(model, comp, detail))
             for name, comp in parts_of(model)]
    whole = build(model, "parts")
    if path.suffix.lower() == ".xlsx":
        sheets = [("Summary", _table(whole))]
        for name, b in items:
            sheets.append((name, _table(b)))
        xlsx.write(path, sheets)
        return [str(path)]
    path.mkdir(parents=True, exist_ok=True)
    out = [str(path / "00 Summary.csv")]
    to_csv(whole, out[0])
    for i, (name, b) in enumerate(items, 1):
        safe = re.sub(r"[\\/:*?\"<>|]+", "-", name)
        f = path / f"{i:02d} {safe}.csv"
        to_csv(b, f)
        out.append(str(f))
    return out


def _table(bom_, columns=None):
    keys, heads = _headers(columns)
    rows = [["Level"] + heads]
    for row in bom_.rows():
        rows.append([row["level"]] + [
            ("    " * row["level"] + str(row[k])) if k == "name" else row[k]
            for k in keys])
    t = bom_.totals()
    total = [""] * (len(keys) + 1)
    total[1] = "TOTAL"
    total[keys.index("mass_total") + 1] = t["mass_kg"]
    total[keys.index("cost_total") + 1] = t["cost"]
    return rows + [[], total]


EXPORTERS = {".csv": to_csv, ".json": to_json, ".html": to_html,
             ".htm": to_html, ".xlsx": to_xlsx}


def export(bom, path, columns=None):
    """Write *bom* by *path*'s extension (.csv .xlsx .html .json)."""
    ext = Path(path).suffix.lower()
    if ext not in EXPORTERS:
        raise ValueError(f"BOM export takes .csv, .xlsx, .html or .json, "
                         f"not {ext or 'no extension'}")
    fn = EXPORTERS[ext]
    if ext == ".json":
        fn(bom, path)
    else:
        fn(bom, path, columns=columns) if ext != ".csv" else \
            fn(bom, path, columns=columns)
    return str(path)
