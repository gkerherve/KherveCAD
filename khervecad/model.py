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

# --------------------------------------------------------------- registry

SHAPE_2D = "2d"
SHAPE_3D = "3d"
OPERATION = "op"
BOOLEAN = "bool"

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
        params=dict(x=0.0, y=0.0, radius=15.0, segments=64),
        schema=[("x", "X", "float", -1e6, 1e6),
                ("y", "Y", "float", -1e6, 1e6),
                ("radius", "Radius", "float", 0.01, 1e6),
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
}

#: types that accept children.
CONTAINER_TYPES = {t for t, d in NODE_TYPES.items()
                   if d["category"] in (OPERATION, BOOLEAN)}


def fmt(value) -> str:
    """Format a number the OpenSCAD way: no trailing zeros."""
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

    # --------------------------------------------------------- codegen
    def to_scad(self, indent: int = 0) -> str:
        pad = "    " * indent
        star = "" if self.visible else "*"

        if self.type == "root":
            parts = [c.to_scad(indent) for c in self.children]
            return "\n".join(p for p in parts if p)

        head = pad + star + self._statement()
        if not self.is_container():
            return head + ";"
        if not self.children:
            return head + " { }"
        body = "\n".join(c.to_scad(indent + 1) for c in self.children)
        return f"{head} {{\n{body}\n{pad}}}"

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
            return (f"translate([{fmt(p['x'])}, {fmt(p['y'])}]) "
                    f"circle(r={fmt(p['radius'])}, "
                    f"$fn={fmt(p['segments'])})")
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
        if t in ("union", "difference", "intersection"):
            return f"{t}()"
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
        from . import APP_NAME, __version__
        header = (f"// Generated by {APP_NAME} v{__version__}\n"
                  f"// Edit objects in the GUI — this program is\n"
                  f"// regenerated from the object tree.\n")
        body = self.root.to_scad()
        return header + "\n" + body + ("\n" if body else "")

    # -------------------------------------------------------- editing
    def add_node(self, type: str, params: dict = None,
                 parent: CadNode = None, name: str = "") -> CadNode:
        node = CadNode(type, name or self.unique_name(type), params)
        (parent or self.root).add(node)
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
        parent.add(wrapper, index)
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
