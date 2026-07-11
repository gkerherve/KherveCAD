"""Object tree model — the single source of truth.

A KherveCAD document is a tree of ``CadNode`` objects. Every GUI tool
(shape tools, extrusions, booleans, the properties panel, dragging in
the 2D view) only ever creates or edits nodes; the OpenSCAD program
shown in the Code tab is generated from the tree by ``to_scad()``, so
the tree and the code can never disagree. OpenSCAD is the engine —
each node type maps to exactly one OpenSCAD statement.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import itertools

from PyQt5.QtCore import QObject, pyqtSignal

from . import expr

# --------------------------------------------------------------- registry

SHAPE_2D = "2d"
SHAPE_3D = "3d"
OPERATION = "op"
BOOLEAN = "bool"
CONTROL = "ctl"          # loops / conditionals / assignments

#: hard cap when unrolling while loops into an OpenSCAD value list.
MAX_WHILE_ITERATIONS = 1000

#: param schema entry: (key, label, kind, minimum, maximum)
#: kinds: "float", "int", "bool", "str", "points" (list of [x, y]).
NODE_TYPES = {
    # ----- 2D shapes ------------------------------------------------
    "line": dict(
        label="Line", category=SHAPE_2D, icon="mdi.vector-line",
        params=dict(x1=0.0, y1=0.0, x2=40.0, y2=0.0, width=2.0),
        schema=[("x1", "X1", "float", -1e6, 1e6),
                ("y1", "Y1", "float", -1e6, 1e6),
                ("x2", "X2", "float", -1e6, 1e6),
                ("y2", "Y2", "float", -1e6, 1e6),
                ("width", "Width", "float", 0.01, 1e4)]),
    "rect": dict(
        label="Rectangle", category=SHAPE_2D, icon="mdi.rectangle-outline",
        params=dict(x=0.0, y=0.0, width=40.0, height=25.0),
        schema=[("x", "X", "float", -1e6, 1e6),
                ("y", "Y", "float", -1e6, 1e6),
                ("width", "Width", "float", 0.01, 1e6),
                ("height", "Height", "float", 0.01, 1e6)]),
    "circle": dict(
        label="Circle", category=SHAPE_2D, icon="mdi.circle-outline",
        params=dict(x=0.0, y=0.0, radius=15.0, angle=360.0,
                    start_angle=0.0, segments=64),
        schema=[("x", "X", "float", -1e6, 1e6),
                ("y", "Y", "float", -1e6, 1e6),
                ("radius", "Radius", "float", 0.01, 1e6),
                ("angle", "Angle (90=quarter)", "float", 1.0, 360.0),
                ("start_angle", "Start angle", "float", -360.0, 360.0),
                ("segments", "Segments ($fn)", "int", 3, 512)]),
    "polygon": dict(
        label="Polygon", category=SHAPE_2D, icon="mdi.vector-polygon",
        params=dict(x=0.0, y=0.0,
                    points=[[0.0, 0.0], [40.0, 0.0], [20.0, 30.0]]),
        schema=[("x", "X", "float", -1e6, 1e6),
                ("y", "Y", "float", -1e6, 1e6),
                ("points", "Points", "points", None, None)]),
    "text": dict(
        label="Text", category=SHAPE_2D, icon="mdi.format-text",
        params=dict(x=0.0, y=0.0, text="Kherve", size=10.0),
        schema=[("x", "X", "float", -1e6, 1e6),
                ("y", "Y", "float", -1e6, 1e6),
                ("text", "Text", "str", None, None),
                ("size", "Size", "float", 0.1, 1e4)]),
    # ----- 3D primitives --------------------------------------------
    "cube": dict(
        label="Cube", category=SHAPE_3D, icon="mdi.cube-outline",
        params=dict(x=0.0, y=0.0, z=0.0,
                    width=20.0, depth=20.0, height=20.0, center=False),
        schema=[("x", "X", "float", -1e6, 1e6),
                ("y", "Y", "float", -1e6, 1e6),
                ("z", "Z", "float", -1e6, 1e6),
                ("width", "Width (X)", "float", 0.01, 1e6),
                ("depth", "Depth (Y)", "float", 0.01, 1e6),
                ("height", "Height (Z)", "float", 0.01, 1e6),
                ("center", "Center", "bool", None, None)]),
    "sphere": dict(
        label="Sphere", category=SHAPE_3D, icon="mdi.circle-slice-8",
        params=dict(x=0.0, y=0.0, z=0.0, radius=12.0, segments=48),
        schema=[("x", "X", "float", -1e6, 1e6),
                ("y", "Y", "float", -1e6, 1e6),
                ("z", "Z", "float", -1e6, 1e6),
                ("radius", "Radius", "float", 0.01, 1e6),
                ("segments", "Segments ($fn)", "int", 4, 512)]),
    "cylinder": dict(
        label="Cylinder", category=SHAPE_3D, icon="mdi.database-outline",
        params=dict(x=0.0, y=0.0, z=0.0, height=25.0,
                    radius_bottom=10.0, radius_top=10.0,
                    segments=64, center=False),
        schema=[("x", "X", "float", -1e6, 1e6),
                ("y", "Y", "float", -1e6, 1e6),
                ("z", "Z", "float", -1e6, 1e6),
                ("height", "Height", "float", 0.01, 1e6),
                ("radius_bottom", "Radius bottom", "float", 0.0, 1e6),
                ("radius_top", "Radius top", "float", 0.0, 1e6),
                ("segments", "Segments ($fn)", "int", 3, 512),
                ("center", "Center", "bool", None, None)]),
    # ----- operations (wrap children) --------------------------------
    "linear_extrude": dict(
        label="Linear extrude", category=OPERATION,
        icon="mdi.arrow-expand-up",
        params=dict(height=10.0, twist=0.0, scale=1.0, center=False,
                    segments=0),
        schema=[("height", "Height", "float", 0.01, 1e6),
                ("twist", "Twist (deg)", "float", -1e5, 1e5),
                ("scale", "Scale", "float", 0.0, 1e4),
                ("center", "Center", "bool", None, None),
                ("segments", "Slices (0=auto)", "int", 0, 512)]),
    "rotate_extrude": dict(
        label="Rotate extrude", category=OPERATION,
        icon="mdi.rotate-3d-variant",
        params=dict(angle=360.0, segments=96),
        schema=[("angle", "Angle (deg)", "float", 0.01, 360.0),
                ("segments", "Segments ($fn)", "int", 3, 512)]),
    "translate": dict(
        label="Translate", category=OPERATION, icon="mdi.cursor-move",
        params=dict(x=0.0, y=0.0, z=0.0),
        schema=[("x", "X", "float", -1e6, 1e6),
                ("y", "Y", "float", -1e6, 1e6),
                ("z", "Z", "float", -1e6, 1e6)]),
    "rotate": dict(
        label="Rotate", category=OPERATION, icon="mdi.rotate-right",
        params=dict(x=0.0, y=0.0, z=0.0),
        schema=[("x", "X (deg)", "float", -360.0, 360.0),
                ("y", "Y (deg)", "float", -360.0, 360.0),
                ("z", "Z (deg)", "float", -360.0, 360.0)]),
    "scale": dict(
        label="Scale", category=OPERATION, icon="mdi.resize",
        params=dict(x=1.0, y=1.0, z=1.0),
        schema=[("x", "X", "float", 0.001, 1e4),
                ("y", "Y", "float", 0.001, 1e4),
                ("z", "Z", "float", 0.001, 1e4)]),
    "mirror": dict(
        label="Mirror", category=OPERATION, icon="mdi.flip-horizontal",
        params=dict(x=1.0, y=0.0, z=0.0),
        schema=[("x", "X", "float", -1.0, 1.0),
                ("y", "Y", "float", -1.0, 1.0),
                ("z", "Z", "float", -1.0, 1.0)]),
    "offset": dict(
        label="Offset (round corners)", category=OPERATION,
        icon="mdi.rounded-corner",
        params=dict(radius=2.0, chamfer=False),
        schema=[("radius", "Radius (+out/-in)", "float", -1e4, 1e4),
                ("chamfer", "Chamfer (no rounding)", "bool", None, None)]),
    # ----- booleans / grouping ---------------------------------------
    "union": dict(
        label="Group (union)", category=BOOLEAN, icon="mdi.group",
        params=dict(), schema=[]),
    "difference": dict(
        label="Difference", category=BOOLEAN, icon="mdi.set-left",
        params=dict(), schema=[]),
    "intersection": dict(
        label="Intersection", category=BOOLEAN, icon="mdi.set-center",
        params=dict(), schema=[]),
    "hull": dict(
        label="Hull", category=BOOLEAN, icon="mdi.vector-combine",
        params=dict(), schema=[]),
    "minkowski": dict(
        label="Minkowski (round edges)", category=BOOLEAN,
        icon="mdi.blur",
        params=dict(), schema=[]),
    # ----- control flow ----------------------------------------------
    "for_loop": dict(
        label="For loop", category=CONTROL, icon="mdi.repeat",
        params=dict(variable="i", start=0.0, end=4.0, step=1.0,
                    values=""),
        schema=[("variable", "Variable", "str", None, None),
                ("start", "From", "float", -1e6, 1e6),
                ("end", "To", "float", -1e6, 1e6),
                ("step", "Step", "float", -1e6, 1e6),
                ("values", "Values (overrides range)", "str",
                 None, None)]),
    "while_loop": dict(
        label="While loop", category=CONTROL, icon="mdi.repeat-variant",
        params=dict(variable="x", start=1.0, condition="x < 100",
                    update="x * 2"),
        schema=[("variable", "Variable", "str", None, None),
                ("start", "Initial value", "float", -1e6, 1e6),
                ("condition", "While condition", "str", None, None),
                ("update", "Update expression", "str", None, None)]),
    "if_else": dict(
        label="If / else", category=CONTROL, icon="mdi.call-split",
        params=dict(condition="true"),
        schema=[("condition", "Condition", "str", None, None)]),
    "assign": dict(
        label="Variable", category=CONTROL, icon="mdi.variable",
        params=dict(variable="size", value="10"),
        schema=[("variable", "Name", "str", None, None),
                ("value", "Value / expression", "str", None, None)]),
    # ----- external geometry ------------------------------------------
    "stl_import": dict(
        label="Import STL", category=SHAPE_3D,
        icon="mdi.file-import-outline",
        params=dict(path="", x=0.0, y=0.0, z=0.0),
        schema=[("path", "STL file", "str", None, None),
                ("x", "X", "float", -1e6, 1e6),
                ("y", "Y", "float", -1e6, 1e6),
                ("z", "Z", "float", -1e6, 1e6)]),
}

#: types that accept children.
CONTAINER_TYPES = {t for t, d in NODE_TYPES.items()
                   if d["category"] in (OPERATION, BOOLEAN, CONTROL)} \
    - {"assign"}


def fmt(value) -> str:
    """Format a number the OpenSCAD way: no trailing zeros. Strings
    pass through raw — they are expressions like ``i * 10``."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return text if text not in ("", "-") else "0"
    return str(value)


def scad_str(text: str) -> str:
    """Quote *text* as an OpenSCAD string literal."""
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


# ------------------------------------------------------------------ node

class CadNode:
    """One object in the tree: a shape, an operation or a boolean."""

    _ids = itertools.count(1)

    def __init__(self, type: str, name: str = "", params: dict = None):
        if type not in NODE_TYPES and type != "root":
            raise ValueError(f"unknown node type: {type}")
        self.id = next(CadNode._ids)
        self.type = type
        self.name = name or (NODE_TYPES[type]["label"]
                             if type != "root" else "root")
        self.visible = True
        base = {} if type == "root" else NODE_TYPES[type]["params"]
        self.params = {k: (list(map(list, v)) if isinstance(v, list) else v)
                       for k, v in base.items()}
        if params:
            self.params.update(params)
        self.children = []
        self.parent = None

    # ------------------------------------------------------- structure
    def add(self, child: "CadNode", index: int = None) -> "CadNode":
        child.parent = self
        if index is None:
            self.children.append(child)
        else:
            self.children.insert(index, child)
        return child

    def remove(self, child: "CadNode"):
        self.children.remove(child)
        child.parent = None

    def index(self) -> int:
        return self.parent.children.index(self) if self.parent else 0

    def walk(self):
        """Yield self and all descendants, depth first."""
        yield self
        for child in self.children:
            yield from child.walk()

    def is_container(self) -> bool:
        return self.type == "root" or self.type in CONTAINER_TYPES

    @property
    def category(self) -> str:
        return "root" if self.type == "root" \
            else NODE_TYPES[self.type]["category"]

    def has_2d_content(self) -> bool:
        """True if the subtree bottoms out in 2D shapes (extrudable)."""
        if self.category == SHAPE_2D:
            return True
        if self.category == SHAPE_3D:
            return False
        return any(c.has_2d_content() for c in self.children)

    def arc_points(self, env: dict = None):
        """Arc vertices of a (possibly partial) circle, local coords."""
        import math
        p = self.params
        radius = expr.resolve(p["radius"], env, 1.0)
        angle = min(max(expr.resolve(p.get("angle", 360.0), env, 360.0),
                        1.0), 360.0)
        start = expr.resolve(p.get("start_angle", 0.0), env, 0.0)
        segments = max(int(expr.resolve(p["segments"], env, 64)), 3)
        steps = max(int(segments * angle / 360.0), 2)
        return [(radius * math.cos(math.radians(start + angle * i / steps)),
                 radius * math.sin(math.radians(start + angle * i / steps)))
                for i in range(steps + 1)]

    def loop_values(self, env: dict = None):
        """Concrete values a for/while loop iterates over (unrolled
        with the expression evaluator; used by codegen for `while` and
        by the preview tessellator for both)."""
        p = self.params
        if self.type == "for_loop":
            if str(p.get("values", "")).strip():
                out = []
                for chunk in str(p["values"]).split(","):
                    try:
                        out.append(expr.evaluate(chunk, env))
                    except expr.ExprError:
                        out.append(0.0)
                return out
            start = expr.resolve(p["start"], env, 0.0)
            end = expr.resolve(p["end"], env, 0.0)
            step = expr.resolve(p["step"], env, 1.0) or 1.0
            values, v = [], start
            while (step > 0 and v <= end + 1e-9) or \
                    (step < 0 and v >= end - 1e-9):
                values.append(v)
                v += step
                if len(values) >= MAX_WHILE_ITERATIONS:
                    break
            return values
        if self.type == "while_loop":
            var = str(p.get("variable", "x")) or "x"
            value = expr.resolve(p["start"], env, 0.0)
            values = []
            scope = dict(env or {})
            for _ in range(MAX_WHILE_ITERATIONS):
                scope[var] = value
                try:
                    if not expr.evaluate(p["condition"], scope):
                        break
                    values.append(value)
                    value = expr.evaluate(p["update"], scope)
                except expr.ExprError:
                    break
            return values
        return []

    # --------------------------------------------------------- codegen
    def to_scad(self, indent: int = 0) -> str:
        lines = []
        self.emit(lines, indent)
        return "\n".join(text for text, _node in lines)

    def emit(self, lines, indent: int = 0, spans: dict = None):
        """Append (text, node) pairs for this subtree to *lines*.
        When *spans* is given, record ``spans[node.id] = (first_line,
        last_line_exclusive)`` so the GUI can map code lines back to
        nodes (selection highlight, OpenSCAD error marking)."""
        start = len(lines)
        pad = "    " * indent
        star = "" if self.visible else "*"

        if self.type == "root":
            for child in self.children:
                child.emit(lines, indent, spans)
        elif self.type == "if_else":
            self._emit_if_else(lines, indent, spans)
        else:
            head = pad + star + self._statement()
            if not self.is_container():
                lines.append((head + ";", self))
            elif not self.children:
                lines.append((head + " { }", self))
            else:
                lines.append((head + " {", self))
                for child in self.children:
                    child.emit(lines, indent + 1, spans)
                lines.append((pad + "}", self))
        if spans is not None:
            spans[self.id] = (start, len(lines))

    def _emit_if_else(self, lines, indent: int, spans):
        """`if (cond) { then } else { else }` — the else branch is a
        child union node named "Else"; everything else is the then
        branch."""
        pad = "    " * indent
        star = "" if self.visible else "*"
        else_node = next((c for c in self.children
                          if c.type == "union"
                          and c.name.lower().startswith("else")), None)
        then_nodes = [c for c in self.children if c is not else_node]
        head = f"{pad}{star}if ({fmt(self.params['condition'])})"
        has_else = else_node is not None and else_node.children
        if then_nodes:
            lines.append((head + " {", self))
            for child in then_nodes:
                child.emit(lines, indent + 1, spans)
            lines.append((pad + ("} else {" if has_else else "}"),
                          self))
        else:
            lines.append((head + " { }" + (" else {" if has_else
                                           else ""), self))
        if has_else:
            for child in else_node.children:
                child.emit(lines, indent + 1, spans)
            lines.append((pad + "}", self))

    def _statement(self) -> str:
        p = self.params
        t = self.type
        if t == "line":
            # A stroked segment: the hull of two circles gives a line
            # with round caps — a real 2D solid OpenSCAD can extrude.
            d = fmt(p["width"])
            return (f"hull() {{ "
                    f"translate([{fmt(p['x1'])}, {fmt(p['y1'])}]) "
                    f"circle(d={d}, $fn=32); "
                    f"translate([{fmt(p['x2'])}, {fmt(p['y2'])}]) "
                    f"circle(d={d}, $fn=32); }}")
        if t == "rect":
            return (f"translate([{fmt(p['x'])}, {fmt(p['y'])}]) "
                    f"square([{fmt(p['width'])}, {fmt(p['height'])}])")
        if t == "circle":
            angle = p.get("angle", 360.0)
            partial = isinstance(angle, str) or angle < 360.0
            if not partial:
                return (f"translate([{fmt(p['x'])}, {fmt(p['y'])}]) "
                        f"circle(r={fmt(p['radius'])}, "
                        f"$fn={fmt(p['segments'])})")
            # Quarter / semi / any pie slice: a polygon fan of arc
            # points (centre first) — a real 2D solid.
            pts = ", ".join(f"[{fmt(x)}, {fmt(y)}]"
                            for x, y in self.arc_points())
            return (f"translate([{fmt(p['x'])}, {fmt(p['y'])}]) "
                    f"polygon(points=[[0, 0], {pts}])")
        if t == "polygon":
            pts = ", ".join(f"[{fmt(x)}, {fmt(y)}]"
                            for x, y in p["points"])
            return (f"translate([{fmt(p['x'])}, {fmt(p['y'])}]) "
                    f"polygon(points=[{pts}])")
        if t == "text":
            return (f"translate([{fmt(p['x'])}, {fmt(p['y'])}]) "
                    f"text({scad_str(p['text'])}, size={fmt(p['size'])})")
        if t == "cube":
            return (f"translate([{fmt(p['x'])}, {fmt(p['y'])}, "
                    f"{fmt(p['z'])}]) "
                    f"cube([{fmt(p['width'])}, {fmt(p['depth'])}, "
                    f"{fmt(p['height'])}], center={fmt(p['center'])})")
        if t == "sphere":
            return (f"translate([{fmt(p['x'])}, {fmt(p['y'])}, "
                    f"{fmt(p['z'])}]) "
                    f"sphere(r={fmt(p['radius'])}, "
                    f"$fn={fmt(p['segments'])})")
        if t == "cylinder":
            return (f"translate([{fmt(p['x'])}, {fmt(p['y'])}, "
                    f"{fmt(p['z'])}]) "
                    f"cylinder(h={fmt(p['height'])}, "
                    f"r1={fmt(p['radius_bottom'])}, "
                    f"r2={fmt(p['radius_top'])}, "
                    f"$fn={fmt(p['segments'])}, "
                    f"center={fmt(p['center'])})")
        if t == "linear_extrude":
            args = [f"height={fmt(p['height'])}"]
            if p["twist"]:
                args.append(f"twist={fmt(p['twist'])}")
            if p["scale"] != 1.0:
                args.append(f"scale={fmt(p['scale'])}")
            if p["center"]:
                args.append("center=true")
            if p["segments"]:
                args.append(f"slices={fmt(p['segments'])}")
            return f"linear_extrude({', '.join(args)})"
        if t == "rotate_extrude":
            args = []
            if p["angle"] != 360.0:
                args.append(f"angle={fmt(p['angle'])}")
            args.append(f"$fn={fmt(p['segments'])}")
            return f"rotate_extrude({', '.join(args)})"
        if t in ("translate", "rotate", "scale", "mirror"):
            return (f"{t}([{fmt(p['x'])}, {fmt(p['y'])}, "
                    f"{fmt(p['z'])}])")
        if t in ("union", "difference", "intersection", "hull",
                 "minkowski"):
            return f"{t}()"
        if t == "offset":
            if p["chamfer"]:
                return (f"offset(delta={fmt(p['radius'])}, "
                        f"chamfer=true)")
            return f"offset(r={fmt(p['radius'])})"
        if t == "for_loop":
            var = str(p.get("variable", "i")) or "i"
            if str(p.get("values", "")).strip():
                return f"for ({var} = [{p['values']}])"
            return (f"for ({var} = [{fmt(p['start'])} : "
                    f"{fmt(p['step'])} : {fmt(p['end'])}])")
        if t == "while_loop":
            # OpenSCAD has no while — unroll to a concrete value list,
            # which is a plain (and valid) for loop.
            var = str(p.get("variable", "x")) or "x"
            values = self.loop_values() or [0]
            body = ", ".join(fmt(float(v)) for v in values)
            return (f"for ({var} = [{body}]) "
                    f"/* while {fmt(p['condition'])} */")
        if t == "assign":
            return f"{p['variable']} = {fmt(p['value'])}"
        if t == "stl_import":
            return (f"translate([{fmt(p['x'])}, {fmt(p['y'])}, "
                    f"{fmt(p['z'])}]) "
                    f"import({scad_str(p['path'])}, convexity=10)")
        raise ValueError(f"no codegen for type: {t}")   # pragma: no cover


# -------------------------------------------------------------- document

class DocumentModel(QObject):
    """The open document: a root node plus change signals.

    Panels connect to the signals; anything that edits the tree calls
    the methods here so every view stays in sync.
    """

    #: tree shape changed (nodes added / removed / moved / grouped).
    structure_changed = pyqtSignal()
    #: a single node's params / name / visibility changed.
    node_changed = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.root = CadNode("root")

    # -------------------------------------------------------- queries
    def find(self, node_id: int):
        for node in self.root.walk():
            if node.id == node_id:
                return node
        return None

    def unique_name(self, type: str) -> str:
        base = NODE_TYPES[type]["label"]
        taken = {n.name for n in self.root.walk()}
        for i in itertools.count(1):
            name = f"{base} {i}"
            if name not in taken:
                return name

    def to_scad(self) -> str:
        return self.to_scad_map()[0]

    def to_scad_map(self):
        """The full program plus ``{node_id: (first, last_exclusive)}``
        line spans into it — the basis for code-line highlighting and
        for mapping OpenSCAD error line numbers back to nodes."""
        from . import APP_NAME, __version__
        header = (f"// Generated by {APP_NAME} v{__version__}\n"
                  f"// Edit objects in the GUI — this program is\n"
                  f"// regenerated from the object tree.\n")
        offset = header.count("\n") + 1          # + the blank line
        lines, spans = [], {}
        self.root.emit(lines, 0, spans)
        body = "\n".join(text for text, _n in lines)
        code = header + "\n" + body + ("\n" if body else "")
        shifted = {nid: (s + offset, e + offset)
                   for nid, (s, e) in spans.items()}
        return code, shifted

    def node_at_line(self, line: int):
        """Deepest node whose code span contains 0-based *line*."""
        _code, spans = self.to_scad_map()
        best, best_size = None, None
        for nid, (s, e) in spans.items():
            if s <= line < e:
                size = e - s
                if best_size is None or size < best_size:
                    best, best_size = nid, size
        return self.find(best) if best is not None else None

    # -------------------------------------------------------- editing
    def add_node(self, type: str, params: dict = None,
                 parent: CadNode = None, name: str = "") -> CadNode:
        node = CadNode(type, name or self.unique_name(type), params)
        (parent or self.root).add(node)
        if type == "if_else":
            node.add(CadNode("union", "Else"))
        self.structure_changed.emit()
        return node

    def remove_node(self, node: CadNode):
        if node.parent is None:
            return
        node.parent.remove(node)
        self.structure_changed.emit()

    def set_param(self, node: CadNode, key: str, value):
        node.params[key] = value
        self.node_changed.emit(node)

    def set_visible(self, node: CadNode, visible: bool):
        node.visible = visible
        self.node_changed.emit(node)

    def rename(self, node: CadNode, name: str):
        node.name = name
        self.node_changed.emit(node)

    def shift_node(self, node: CadNode, delta: int):
        """Move *node* up/down within its parent (Ctrl+Up/Down)."""
        parent = node.parent
        if parent is None:
            return
        i = node.index()
        j = max(0, min(len(parent.children) - 1, i + delta))
        if i != j:
            parent.children.insert(j, parent.children.pop(i))
            self.structure_changed.emit()

    def move_node(self, node: CadNode, new_parent: CadNode,
                  index: int = None):
        if new_parent is node or any(n is node for n in
                                     self._ancestors(new_parent)):
            return                       # refuse to reparent into itself
        node.parent.remove(node)
        new_parent.add(node, index)
        self.structure_changed.emit()

    @staticmethod
    def _ancestors(node: CadNode):
        while node is not None:
            yield node
            node = node.parent

    def wrap_nodes(self, nodes, op_type: str) -> CadNode:
        """Wrap *nodes* (same parent expected) in a new container node
        — this is how extrusions, transforms and booleans are applied."""
        nodes = [n for n in nodes if n.parent is not None]
        if not nodes:
            return None
        parent = nodes[0].parent
        nodes = [n for n in nodes if n.parent is parent]
        index = min(n.index() for n in nodes)
        wrapper = CadNode(op_type, self.unique_name(op_type))
        for n in nodes:
            parent.remove(n)
            wrapper.add(n)
        if op_type == "if_else":
            wrapper.add(CadNode("union", "Else"))
        parent.add(wrapper, index)
        self.structure_changed.emit()
        return wrapper

    def round_edges(self, nodes, radius: float = 1.0) -> CadNode:
        """Round the edges of *nodes* after extrusion: wrap them in
        minkowski() with a small sphere — the OpenSCAD idiom."""
        wrapper = self.wrap_nodes(nodes, "minkowski")
        if wrapper is not None:
            sphere = CadNode("sphere", self.unique_name("sphere"),
                             dict(radius=radius, segments=24))
            wrapper.add(sphere)
            self.structure_changed.emit()
        return wrapper

    def group_nodes(self, nodes) -> CadNode:
        return self.wrap_nodes(nodes, "union")

    def ungroup(self, node: CadNode):
        """Replace a container node by its children (any container)."""
        if not node.is_container() or node.parent is None:
            return
        parent, index = node.parent, node.index()
        parent.remove(node)
        for child in list(node.children):
            node.remove(child)
            parent.add(child, index)
            index += 1
        self.structure_changed.emit()

    def duplicate(self, node: CadNode) -> CadNode:
        clone = self._clone(node)
        clone.name = self.unique_name(node.type)
        node.parent.add(clone, node.index() + 1)
        self.structure_changed.emit()
        return clone

    def _clone(self, node: CadNode) -> CadNode:
        copy = CadNode(node.type, node.name, None)
        copy.params = {k: (list(map(list, v)) if isinstance(v, list)
                           else v) for k, v in node.params.items()}
        copy.visible = node.visible
        for child in node.children:
            copy.add(self._clone(child))
        return copy

    def clear(self):
        self.root = CadNode("root")
        self.structure_changed.emit()


# ------------------------------------------------------------ validation

def validate(root: CadNode) -> dict:
    """Static checks over the tree: ``{node_id: error message}`` for
    every node that would break (or silently ruin) the OpenSCAD
    program. The tree panel paints these nodes red."""
    errors = {}

    def check(node, env):
        message = _check_node(node, env, errors)
        if message:
            errors[node.id] = message
        scoped = dict(env)
        if node.type in ("for_loop", "while_loop"):
            values = node.loop_values(env)
            var = str(node.params.get("variable", "i")) or "i"
            scoped[var] = values[0] if values else 0.0
        for child in node.children:
            check(child, scoped)
            if child.type == "assign" and child.visible:
                var = str(child.params.get("variable", "")).strip()
                if var:
                    try:
                        scoped[var] = expr.evaluate(
                            child.params.get("value", 0), scoped)
                    except expr.ExprError:
                        pass
    check(root, {})
    return errors


def _check_node(node, env, errors):
    import re
    p = node.params
    t = node.type
    if t == "root":
        return None

    # --- expression params (numeric schema fields holding strings)
    for key, _label, kind, _mn, _mx in NODE_TYPES[t]["schema"]:
        value = p.get(key)
        if kind in ("float", "int") and isinstance(value, str):
            try:
                expr.evaluate(value, env)
            except expr.ExprError as exc:
                return f"{key}: {exc}"

    if t in ("for_loop", "while_loop", "assign"):
        var = str(p.get("variable", "")).strip()
        if not re.fullmatch(r"\$?[A-Za-z_]\w*", var or ""):
            return f"invalid variable name: {var!r}"
    if t == "assign":
        try:
            expr.evaluate(p.get("value", 0), env)
        except expr.ExprError as exc:
            return f"value: {exc}"
    if t in ("while_loop", "if_else"):
        scope = dict(env)
        if t == "while_loop":
            scope[str(p.get("variable", "x")) or "x"] = 0.0
            for key in ("condition", "update"):
                try:
                    expr.evaluate(p[key], scope)
                except expr.ExprError as exc:
                    return f"{key}: {exc}"
            if len(node.loop_values(env)) >= MAX_WHILE_ITERATIONS:
                return ("while loop does not terminate "
                        f"(capped at {MAX_WHILE_ITERATIONS})")
        else:
            try:
                expr.evaluate(p["condition"], scope)
            except expr.ExprError as exc:
                return f"condition: {exc}"
    if t == "for_loop" and str(p.get("values", "")).strip():
        for chunk in str(p["values"]).split(","):
            try:
                expr.evaluate(chunk, env)
            except expr.ExprError as exc:
                return f"values: {exc}"

    if t == "polygon" and len(p.get("points", [])) < 3:
        return "polygon needs at least 3 points"
    if t == "stl_import":
        from pathlib import Path
        path = str(p.get("path", "")).strip()
        if not path:
            return "no STL file selected"
        if not Path(path).exists():
            return f"file not found: {path}"

    if t in ("linear_extrude", "rotate_extrude"):
        if _contains_3d(node):
            return "extrusions need 2D shapes, but this contains 3D"
        if not node.has_2d_content():
            return "empty extrusion — put 2D shapes inside"
        if t == "rotate_extrude":
            from . import mesh
            for outline in mesh.collect_outlines(node, env):
                xs = [x for x, _y in outline]
                if xs and min(xs) < -1e-6 and max(xs) > 1e-6:
                    return ("profile crosses the Z axis — keep it on "
                            "one side of x = 0")
    elif node.is_container() and t != "if_else":
        if not any(c.type != "assign" for c in node.children):
            return "empty — add child objects"
    elif t == "if_else":
        else_node = next((c for c in node.children
                          if c.type == "union"
                          and c.name.lower().startswith("else")), None)
        then_nodes = [c for c in node.children if c is not else_node]
        if not then_nodes and not (else_node and else_node.children):
            return "empty — add objects to the branches"
    return None


def _contains_3d(node) -> bool:
    """True if the subtree produces 3D geometry (illegal inside an
    extrusion)."""
    for n in node.walk():
        if n is node:
            continue
        if n.category == SHAPE_3D or \
                n.type in ("linear_extrude", "rotate_extrude"):
            return True
    return False
