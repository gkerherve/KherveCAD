"""CAD exchange — STEP, IGES, BREP and Rhino .3dm, in and out (Qt-free).

KherveCAD's own shapes are OpenSCAD programs and its preview is
triangles, which is all a 3D printer needs and nothing an engineering
office can open: Fusion, SolidWorks, Onshape and Rhino swap parts as
STEP or IGES — exact surfaces, not facets. This module is the door.

Two engines, both optional, both found at run time:

* **OpenCascade** (``cadquery-ocp``, LGPL) for STEP / IGES / BREP.
* **rhino3dm** (MIT, McNeel's openNURBS) for Rhino's .3dm.

Without them every function here says so plainly (`missing`) and the
rest of KherveCAD works exactly as before.

EXPORT is exact where it can be. `Compiler` walks the object tree and
builds a TRUE B-rep for what has one — cubes, spheres, cylinders and
cones, linear and rotate extrusions of 2D shapes (circles stay circles),
every transform, union / difference / intersection, loops, ifs,
variables, Objects and their instances — so a hole in an exported
plate is a real cylinder in SolidWorks, not 64 flat facets. Anything
else (a blend, a sculpt, a gear, an imported scan) is written as its
preview mesh, sewn into a closed solid, and COUNTED: the export reports
how much was exact so nobody discovers it in the other program.
Each top-level part becomes one named, coloured product in the STEP
file, which is how it arrives in Fusion as a browser of named parts.

IMPORT reads every part of the file with its name and colour, meshes
the exact surfaces at a chosen quality and hands back triangles; the
window turns each part into a KherveCAD Object (see `import_parts`).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

#: what each engine opens and saves
OCC_EXTS = (".step", ".stp", ".iges", ".igs", ".brep", ".brp")
RHINO_EXTS = (".3dm",)
CAD_EXTS = OCC_EXTS + RHINO_EXTS

#: mesh quality for import: (linear deflection as a fraction of the
#: part's size, angular deflection in degrees). "Fine" is what a render
#: wants, "Draft" what a 200-part assembly wants.
QUALITY = {
    "Draft": (0.004, 20.0),
    "Normal": (0.0015, 12.0),
    "Fine": (0.0005, 6.0),
}

#: friendly names for the file dialogs and messages
FORMAT_NAMES = {
    ".step": "STEP", ".stp": "STEP", ".iges": "IGES", ".igs": "IGES",
    ".brep": "OpenCascade BREP", ".brp": "OpenCascade BREP",
    ".3dm": "Rhino 3DM",
}


def occ_available() -> bool:
    try:
        import OCP.TopoDS  # noqa: F401
        return True
    except Exception:                          # pragma: no cover
        return False


def rhino_available() -> bool:
    try:
        import rhino3dm  # noqa: F401
        return True
    except Exception:                          # pragma: no cover
        return False


def missing(ext: str) -> str | None:
    """None when *ext* can be read and written here, else one sentence
    a person can act on — what to install, by name."""
    ext = ext.lower()
    if ext in OCC_EXTS and not occ_available():
        return ("{fmt} needs OpenCascade, which is not installed. "
                "Run:  pip install cadquery-ocp  — then restart "
                "KherveCAD.").format(fmt=FORMAT_NAMES.get(ext, ext))
    if ext in RHINO_EXTS and not rhino_available():
        return ("Rhino files need rhino3dm, which is not installed. "
                "Run:  pip install rhino3dm  — then restart KherveCAD.")
    if ext not in CAD_EXTS:
        return f"{ext} is not a CAD exchange format."
    return None


# ================================================================ import

@dataclass
class Part:
    """One part read from a file: name, colour "#rrggbb" or None, and
    its triangles in millimetres."""
    name: str
    color: str | None
    tris: list = field(default_factory=list)
    shape: object = None          # the exact OCC shape, when there is one


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(
        max(0, min(255, int(round(c * 255)))) for c in rgb)


def read_parts(path, quality="Normal") -> list[Part]:
    """Every part in a STEP / IGES / BREP / 3DM file, meshed.

    Raises ValueError with a readable message for a file that cannot be
    read (a missing engine, a damaged file, a file with no solids)."""
    path = str(path)
    ext = Path(path).suffix.lower()
    problem = missing(ext)
    if problem:
        raise ValueError(problem)
    if ext in OCC_EXTS:
        _quiet()
    if ext in RHINO_EXTS:
        parts = _read_3dm(path)
    elif ext in (".brep", ".brp"):
        parts = _read_brep(path, quality)
    else:
        parts = _read_xcaf(path, ext, quality)
    parts = [p for p in parts if p.tris]
    if ext in OCC_EXTS:            # the export finds them again here
        _EXACT.clear()
        _EXACT[(path, Path(path).stat().st_mtime)] = [p.shape
                                                      for p in parts]
    if not parts:
        raise ValueError(
            f"{Path(path).name} holds no solids or surfaces KherveCAD "
            "can show (it may be only curves, points or annotations).")
    _unique_names(parts)
    return parts


_EXACT = {}


def exact_shapes(path):
    """The exact shapes of a STEP / IGES / BREP file's parts, in the
    order `read_parts` lists them (so an imported part's index finds its
    own surface again), cached by path and modification time. None when
    the file is gone or has no exact form (a .3dm is read as meshes)."""
    path = str(path)
    p = Path(path)
    if p.suffix.lower() not in OCC_EXTS or not p.is_file() or \
            not occ_available():
        return None
    key = (path, p.stat().st_mtime)
    if key not in _EXACT:
        _quiet()
        try:
            if p.suffix.lower() in (".brep", ".brp"):
                got = _read_brep(path, None)
            else:
                got = _read_xcaf(path, p.suffix.lower(), None)
        except (ValueError, RuntimeError):
            return None
        # the same filter read_parts applies: parts with no faces go
        got = [g for g in got if _has_faces(g.shape)]
        _EXACT.clear()
        _EXACT[key] = [g.shape for g in got]
    return _EXACT[key]


def _has_faces(shape):
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE
    return shape is not None and TopExp_Explorer(shape, TopAbs_FACE).More()


def _unique_names(parts):
    seen = {}
    for p in parts:
        base = (p.name or "Part").strip() or "Part"
        n = seen.get(base, 0)
        seen[base] = n + 1
        p.name = base if n == 0 else f"{base} {n + 1}"


def _mesh_shape(shape, quality):
    """Triangles of an OCC shape at *quality*, outward wound."""
    lin, ang = QUALITY.get(quality, QUALITY["Normal"])
    return _mesh_shape_rel(shape, lin, ang)


def _mesh_shape_rel(shape, lin, ang):
    """Triangles of an OCC shape, the deflection *lin* a fraction of its
    size and *ang* degrees, outward wound."""
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopoDS import TopoDS
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    if box.IsVoid():
        return []
    lo, hi = box.CornerMin(), box.CornerMax()
    x0, y0, z0, x1, y1, z1 = lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()
    size = max(x1 - x0, y1 - y0, z1 - z0, 1e-6)
    BRepMesh_IncrementalMesh(shape, size * lin, False,
                             math.radians(ang), True)
    tris = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = _topods("Face", exp.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            trsf = loc.Transformation()
            pts = []
            for i in range(1, tri.NbNodes() + 1):
                p = tri.Node(i).Transformed(trsf)
                pts.append((p.X(), p.Y(), p.Z()))
            flip = face.Orientation() == TopAbs_REVERSED
            for i in range(1, tri.NbTriangles() + 1):
                a, b, c = tri.Triangle(i).Get()
                if flip:
                    b, c = c, b
                tris.append((pts[a - 1], pts[b - 1], pts[c - 1]))
        exp.Next()
    return tris


def _read_brep(path, quality):
    from OCP.BRepTools import BRepTools
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Shape
    shape = TopoDS_Shape()
    if not BRepTools.Read_s(shape, path, BRep_Builder()):
        raise ValueError(f"Could not read {Path(path).name}.")
    return [Part(Path(path).stem, None,
                 _mesh_shape(shape, quality) if quality else [], shape)]


def _read_xcaf(path, ext, quality):
    """STEP / IGES through the XCAF document, so parts keep the names
    and colours the other program gave them — and an assembly arrives
    as its parts, each placed where it was."""
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    from OCP.IFSelect import IFSelect_RetDone

    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    if ext in (".step", ".stp"):
        from OCP.STEPCAFControl import STEPCAFControl_Reader
        reader = STEPCAFControl_Reader()
    else:
        from OCP.IGESCAFControl import IGESCAFControl_Reader
        reader = IGESCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    if reader.ReadFile(path) != IFSelect_RetDone:
        raise ValueError(
            f"Could not read {Path(path).name} — the file may be "
            "damaged or not really " + FORMAT_NAMES.get(ext, ext) + ".")
    if not reader.Transfer(doc):
        raise ValueError(f"{Path(path).name} could not be converted.")
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    colors = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    parts = []
    roots = _label_seq()
    shapes.GetFreeShapes(roots)
    for i in range(1, roots.Length() + 1):
        _walk_label(roots.Value(i), shapes, colors, None, None, None,
                    parts, quality)
    if not parts:                  # no XCAF structure: one plain shape
        parts = _read_plain(reader, path, quality)
    return parts


def _topods(kind, shape):
    """TopoDS.Face(shape) — spelt Face_s in OCP before 7.8."""
    from OCP.TopoDS import TopoDS
    return (getattr(TopoDS, kind + "_s", None) or getattr(TopoDS, kind))(
        shape)


def _label_seq():
    try:
        from OCP.TDF import TDF_LabelSequence
        return TDF_LabelSequence()
    except ImportError:                     # OCP 7.8+: generic sequences
        from OCP.collections import Sequence_TDF_Label
        return Sequence_TDF_Label()


def _quiet():
    """OpenCascade prints transfer statistics to stdout; nobody using
    KherveCAD reads them, and a frozen build has no console anyway."""
    global _QUIETED
    if _QUIETED:
        return
    _QUIETED = True
    try:
        from OCP.Message import Message
        Message.DefaultMessenger_s().ChangePrinters().Clear()
    except Exception:                        # pragma: no cover
        pass


_QUIETED = False


def _label_name(label):
    from OCP.TDataStd import TDataStd_Name
    attr = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), attr):
        return attr.Get().ToExtString()
    return ""


def _label_color(label, shape, colors):
    from OCP.Quantity import Quantity_Color
    from OCP.XCAFDoc import (XCAFDoc_ColorSurf, XCAFDoc_ColorGen)
    col = Quantity_Color()
    for kind in (XCAFDoc_ColorSurf, XCAFDoc_ColorGen):
        try:
            found = colors.GetColor_s(label, kind, col)
        except (AttributeError, TypeError):
            found = colors.GetColor(label, kind, col)
        if found:
            return _hex((col.Red(), col.Green(), col.Blue()))
    if shape is not None:
        for kind in (XCAFDoc_ColorSurf, XCAFDoc_ColorGen):
            if colors.GetColor(shape, kind, col):
                return _hex((col.Red(), col.Green(), col.Blue()))
    return None


def _walk_label(label, shapes, colors, trsf, name, color, parts,
                quality):
    """Depth first through an assembly: an instance carries its own
    placement and, usually, the name the user sees in the other CAD."""
    from OCP.TDF import TDF_Label
    from OCP.gp import gp_Trsf
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.TopLoc import TopLoc_Location

    own_name = _label_name(label)
    shape = shapes.GetShape_s(label)
    here = trsf if trsf is not None else gp_Trsf()
    if shapes.IsReference_s(label):
        loc = shapes.GetLocation_s(label)
        here = here.Multiplied(loc.Transformation())
        ref = TDF_Label()
        shapes.GetReferredShape_s(label, ref)
        col = _label_color(label, None, colors) or color
        _walk_label(ref, shapes, colors, here, own_name or name, col,
                    parts, quality)
        return
    col = _label_color(label, shape, colors) or color
    if shapes.IsAssembly_s(label):
        kids = _label_seq()
        shapes.GetComponents_s(label, kids)
        for i in range(1, kids.Length() + 1):
            _walk_label(kids.Value(i), shapes, colors, here,
                        None, col, parts, quality)
        return
    if shape is None or shape.IsNull():
        return
    placed = shape.Moved(TopLoc_Location(here))
    tris = _mesh_shape(placed, quality) if quality else []
    parts.append(Part(name or own_name or "Part", col, tris, placed))


def _read_plain(reader, path, quality):
    shape = reader.ChangeReader().OneShape() \
        if hasattr(reader, "ChangeReader") else None
    if shape is None or shape.IsNull():
        return []
    return [Part(Path(path).stem, None,
                 _mesh_shape(shape, quality) if quality else [], shape)]


def _read_3dm(path):
    """A Rhino file's objects with their names, layers and colours.

    Rhino saves a RENDER MESH with every surface unless "save small" was
    ticked; those meshes are what is read (rhino3dm has no surface
    mesher of its own). A surface saved without one is counted and
    reported, so a sparse import is never a mystery."""
    import rhino3dm as r3
    model = r3.File3dm.Read(path)
    if model is None:
        raise ValueError(f"Could not read {Path(path).name}.")
    scale = _rhino_mm(model)
    layers = {i: model.Layers[i] for i in range(len(model.Layers))}
    parts, bare = [], 0
    for obj in model.Objects:
        geom, attr = obj.Geometry, obj.Attributes
        if not attr.Visible:
            continue
        meshes = _rhino_meshes(geom, r3)
        if meshes is None:
            continue                       # curves, points, text…
        if not meshes:
            bare += 1
            continue
        tris = []
        for m in meshes:
            tris.extend(_rhino_tris(m, scale))
        layer = layers.get(attr.LayerIndex)
        name = attr.Name or (layer.Name if layer else "") or \
            type(geom).__name__
        rgba = attr.ObjectColor if attr.ColorSource == \
            r3.ObjectColorSource.ColorFromObject else \
            (layer.Color if layer else None)
        color = _hex([c / 255.0 for c in rgba[:3]]) if rgba else None
        parts.append(Part(name, color, tris))
    if bare and not parts:
        raise ValueError(
            f"{Path(path).name} has {bare} surface(s) saved without "
            "render meshes. In Rhino, use File ▸ Save As and untick "
            "\"Save small\", or Export Selected as STEP, then open that.")
    return parts


def _rhino_meshes(geom, r3):
    """Render meshes of a Rhino object; [] when it is a surface saved
    without any, None when it is not a solid kind at all."""
    if isinstance(geom, r3.Mesh):
        return [geom]
    if isinstance(geom, r3.Extrusion):
        m = geom.GetMesh(r3.MeshType.Any)
        if m is not None:
            return [m]
        geom = geom.ToBrep(True)
    if isinstance(geom, r3.SubD):
        return []
    if isinstance(geom, r3.Brep):
        out = []
        for i in range(len(geom.Faces)):
            m = geom.Faces[i].GetMesh(r3.MeshType.Any)
            if m is not None:
                out.append(m)
        return out
    return None


def _rhino_tris(m, scale):
    verts = m.Vertices
    pts = [(verts[i].X * scale, verts[i].Y * scale, verts[i].Z * scale)
           for i in range(len(verts))]
    tris = []
    for i in range(len(m.Faces)):
        f = m.Faces[i]
        a, b, c, d = f[0], f[1], f[2], f[3]
        tris.append((pts[a], pts[b], pts[c]))
        if d != c:
            tris.append((pts[a], pts[c], pts[d]))
    return tris


#: Rhino's unit systems -> millimetres
_RHINO_UNITS = {"Millimeters": 1.0, "Centimeters": 10.0, "Meters": 1000.0,
                "Inches": 25.4, "Feet": 304.8, "Microns": 0.001,
                "Kilometers": 1e6, "Yards": 914.4, "None": 1.0}


def _rhino_mm(model) -> float:
    name = str(model.Settings.ModelUnitSystem).rsplit(".", 1)[-1]
    return _RHINO_UNITS.get(name, 1.0)


# ================================================================ export

@dataclass
class Report:
    """What an export did, for the sentence the user reads."""
    parts: int = 0
    exact: int = 0            # leaves written as true surfaces
    faceted: int = 0          # leaves written as sewn meshes
    faceted_names: list = field(default_factory=list)

    def sentence(self, fmt: str) -> str:
        from .language import tr
        if fmt.startswith("Rhino"):
            return tr("Saved {n} part(s) for Rhino, each on its own "
                      "named, coloured layer as a mesh. For editable "
                      "surfaces in Rhino, export STEP instead — Rhino "
                      "opens it as true NURBS.").format(n=self.parts)
        if not self.faceted:
            return tr("Saved {n} part(s) as {fmt} with exact surfaces — "
                      "every hole and curve opens as true geometry in "
                      "other CAD programs.").format(n=self.parts, fmt=fmt)
        names = ", ".join(sorted(set(self.faceted_names))[:5])
        if len(set(self.faceted_names)) > 5:
            names += "…"
        if not self.exact:
            return tr("Saved {n} part(s) as {fmt}. They are made of shapes "
                      "with no exact form ({names}), so they were written "
                      "as faceted solids — fine for viewing and printing, "
                      "but faces will be triangles in other CAD "
                      "programs.").format(n=self.parts, fmt=fmt,
                                          names=names)
        return tr("Saved {n} part(s) as {fmt}. Most of it is exact; "
                  "{names} had no exact form and went in as faceted "
                  "solids.").format(n=self.parts, fmt=fmt, names=names)


class Compiler:
    """Object tree -> OpenCascade shapes (see the module docstring)."""

    def __init__(self, root, fn=None, unit_mm=1.0):
        from . import mesh
        self.mesh = mesh
        self.root = root
        self.fn = fn
        self.unit_mm = unit_mm or 1.0
        self.report = Report()

    # -- helpers ---------------------------------------------------
    def _num(self, node, key, env, default=0.0):
        return self.mesh.rv(node.params.get(key, default), env, default)

    @staticmethod
    def _trsf(m):
        from OCP.gp import gp_GTrsf, gp_Mat, gp_XYZ
        g = gp_GTrsf()
        g.SetVectorialPart(gp_Mat(m[0][0], m[0][1], m[0][2],
                                  m[1][0], m[1][1], m[1][2],
                                  m[2][0], m[2][1], m[2][2]))
        g.SetTranslationPart(gp_XYZ(m[0][3], m[1][3], m[2][3]))
        return g

    def _apply(self, shape, m):
        """Shape through a 4x4 matrix — a rigid one stays exact
        (BRepBuilderAPI_Transform), a stretch goes through GTransform
        which converts circles to B-splines (still exact)."""
        if shape is None:
            return None
        lin = [[m[i][j] for j in range(3)] for i in range(3)]
        det = (lin[0][0] * (lin[1][1] * lin[2][2] - lin[1][2] * lin[2][1])
               - lin[0][1] * (lin[1][0] * lin[2][2] - lin[1][2] * lin[2][0])
               + lin[0][2] * (lin[1][0] * lin[2][1] - lin[1][1] * lin[2][0]))
        cols = [math.sqrt(sum(lin[i][j] ** 2 for i in range(3)))
                for j in range(3)]
        uniform = max(cols) - min(cols) < 1e-9 * max(cols + [1.0])
        if uniform and abs(abs(det) - cols[0] ** 3) < 1e-6 * \
                max(1.0, abs(det)):
            from OCP.gp import gp_Trsf
            from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
            s = cols[0] or 1.0
            if det > 0:
                t = gp_Trsf()
                t.SetValues(m[0][0] / s, m[0][1] / s, m[0][2] / s, m[0][3],
                            m[1][0] / s, m[1][1] / s, m[1][2] / s, m[1][3],
                            m[2][0] / s, m[2][1] / s, m[2][2] / s, m[2][3])
                if abs(s - 1.0) > 1e-12:
                    sc = gp_Trsf()
                    from OCP.gp import gp_Pnt
                    sc.SetScale(gp_Pnt(0, 0, 0), s)
                    t = t.Multiplied(sc)
                return BRepBuilderAPI_Transform(shape, t, True).Shape()
        from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform
        return BRepBuilderAPI_GTransform(shape, self._trsf(m), True).Shape()

    def _fuse(self, shapes):
        """Several shapes as one. A COMPOUND, not a boolean fuse: every
        CAD program reads overlapping solids in one part, and fusing
        them is the slowest thing OpenCascade does — three imported
        meshes took minutes to fuse and gain nothing by it. A boolean
        the user asked for (difference, intersection) is still cut."""
        shapes = [s for s in shapes if s is not None]
        if not shapes:
            return None
        if len(shapes) == 1:
            return shapes[0]
        return self._compound(shapes)

    @staticmethod
    def _compound(shapes):
        from OCP.TopoDS import TopoDS_Compound
        from OCP.BRep import BRep_Builder
        comp, b = TopoDS_Compound(), BRep_Builder()
        b.MakeCompound(comp)
        for s in shapes:
            if s is not None:
                b.Add(comp, s)
        return comp

    # -- faceted fallback -----------------------------------------
    def faceted(self, node, env):
        tris = [t for t, _c, _s in self.mesh._tess(
            node, dict(env), None, frozenset(), False)]
        if not tris:
            return None
        self.report.faceted += 1
        self.report.faceted_names.append(self._part_name)
        return solid_from_tris(tris)

    # -- the walk ----------------------------------------------------
    def shape(self, node, env):
        """The exact shape of *node*'s subtree, or None (no geometry)."""
        if not node.visible:
            return None
        m = self.mesh
        t = node.type
        if t in ("root", "variables", "color", "component"):
            out = self._children(node, env)
            if t == "component" and node is not self._top:
                out = self._apply(out, m.node_matrix(node, env)) \
                    if out is not None else None
            return out
        if t == "union":
            out = self._children(node, env)
            mat = m.node_matrix(node, env)
            return self._apply(out, mat) if out is not None else None
        if t in ("assign", "masters", "projection"):
            return None
        if t == "reference":
            return self._reference(node, env)
        if t in ("difference", "intersection"):
            return self._boolean(node, env)
        if t in ("for_loop", "while_loop"):
            var = str(node.params.get("variable", "i")) or "i"
            out = []
            for value in node.loop_values(env):
                scoped = dict(env)
                scoped[var] = value
                out.append(self._children(node, scoped))
            return self._fuse(out)
        if t == "if_else":
            return self._fuse([self.shape(c, env)
                               for c in m._if_branch(node, env)])
        if t in m._TRANSFORM_MATS:
            p = m.rp(node, env)
            mat = m._TRANSFORM_MATS[t](p["x"], p["y"], p["z"])
            inner = self._children(node, env)
            return self._apply(inner, mat) if inner is not None else None
        if t == "cube":
            return self._cube(m.rp(node, env))
        if t == "sphere":
            return self._sphere(m.rp(node, env))
        if t == "cylinder":
            return self._cylinder(m.rp(node, env))
        if t == "curve":
            from . import curve3d
            try:
                got = curve3d.exact_shape(node, env)
            except Exception:
                got = None
            if got is not None:
                self._leaf()
                return got
        if t == "curve_surface":
            from . import curve_surface
            try:
                got = curve_surface.shape(node, env)
            except Exception:
                got = None
            if got is not None:
                self._leaf()
                return got
        if t == "stl_import":
            got = self._imported(node, env)
            if got is not None:
                return got
        if t == "linear_extrude":
            got = self._linear_extrude(node, env)
            if got is not None:
                return got
        if t == "rotate_extrude":
            got = self._rotate_extrude(node, env)
            if got is not None:
                return got
        return self.faceted(node, env)

    def _children(self, node, env):
        env = dict(env)
        out = []
        for child in node.children:
            if child.type == "assign":
                self.mesh._apply_assign(child, env)
            elif child.type == "variables":
                for g in child.children:
                    if g.type == "assign":
                        self.mesh._apply_assign(g, env)
                    else:
                        out.append(self.shape(g, env))
            else:
                out.append(self.shape(child, env))
        return self._fuse(out)

    def _reference(self, node, env):
        m = self.mesh
        target = (m._REF_INDEX or {}).get(
            str(node.params.get("ref", "")).strip())
        if target is None or node.id in self._stack:
            return None
        self._stack.add(node.id)
        try:
            if target.type == "component":
                saved_visible = target.visible
                target.visible = True
                try:
                    out = self._children(target, env)
                finally:
                    target.visible = saved_visible
            else:
                out = self.shape(target, env)
        finally:
            self._stack.discard(node.id)
        vals = [self._num(node, k, env) for k in
                ("x", "y", "z", "rx", "ry", "rz")]
        if out is not None and any(vals):
            mat = m.mat_mul(m.mat_translate(*vals[:3]),
                            m.mat_rotate(*vals[3:]))
            out = self._apply(out, mat)
        return out

    def _boolean(self, node, env):
        ops = self.mesh._operands(node, env)
        shapes = [self.shape(c, scope) for c, scope in ops]
        if not shapes or shapes[0] is None:
            return None
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Common
        result = shapes[0]
        for s in shapes[1:]:
            if s is None:
                if node.type == "intersection":
                    return None
                continue
            op = (BRepAlgoAPI_Cut if node.type == "difference"
                  else BRepAlgoAPI_Common)(result, s)
            if not op.IsDone():
                return self.faceted(node, env)
            op.SimplifyResult()
            result = op.Shape()
        return result

    def _imported(self, node, env):
        """A part that came in from a STEP / IGES file goes back out as
        the file's own exact surface — moved, turned and scaled as the
        user placed it — not as the triangles shown on screen."""
        src = str(node.params.get("cad_source", "")).strip()
        if not src:
            return None
        shapes = exact_shapes(src)
        try:
            shape = shapes[int(node.params.get("cad_part", 0))]
        except (TypeError, ValueError, IndexError):
            return None
        m = self.mesh
        p = m.rp(node, env)
        s = p.get("scale", 1.0) / self.unit_mm  # file mm -> document units
        mat = m.mat_mul(m.mat_translate(p["x"], p["y"], p["z"]),
                        m.mat_mul(m.mat_rotate(p.get("rx", 0.0),
                                               p.get("ry", 0.0),
                                               p.get("rz", 0.0)),
                                  m.mat_scale(s, s, s)))
        self._leaf()
        return self._apply(shape, mat)

    # -- primitives ----------------------------------------------------
    def _leaf(self):
        self.report.exact += 1

    def _cube(self, p):
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.gp import gp_Pnt
        w, d, h = p["width"], p["depth"], p["height"]
        if min(w, d, h) <= 0:
            return None
        x, y, z = p["x"], p["y"], p["z"]
        if p.get("center"):
            x, y, z = x - w / 2, y - d / 2, z - h / 2
        self._leaf()
        return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), w, d, h).Shape()

    def _sphere(self, p):
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
        from OCP.gp import gp_Pnt
        if p["radius"] <= 0:
            return None
        self._leaf()
        return BRepPrimAPI_MakeSphere(
            gp_Pnt(p["x"], p["y"], p["z"]), p["radius"]).Shape()

    def _cylinder(self, p):
        from OCP.BRepPrimAPI import (BRepPrimAPI_MakeCylinder,
                                     BRepPrimAPI_MakeCone)
        from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
        h, r1, r2 = p["height"], p["radius_bottom"], p["radius_top"]
        if h <= 0 or max(r1, r2) <= 0:
            return None
        z = p["z"] - (h / 2 if p.get("center") else 0.0)
        ax = gp_Ax2(gp_Pnt(p["x"], p["y"], z), gp_Dir(0, 0, 1))
        self._leaf()
        if abs(r1 - r2) < 1e-12:
            return BRepPrimAPI_MakeCylinder(ax, r1, h).Shape()
        return BRepPrimAPI_MakeCone(ax, r1, r2, h).Shape()

    # -- 2D -> faces ---------------------------------------------------
    def _face_2d(self, node, env):
        """The 2D content under an extrude as ONE planar face at z = 0,
        circles kept as circles where the content is a plain circle (or
        a plain circle minus circles) — else from the outlines."""
        exact = self._exact_profile(node, env)
        if exact is not None:
            return exact
        m = self.mesh
        loops = [o for o in m.collect_outlines(node, env) if len(o) >= 3]
        if not loops:
            return None
        faces = []
        for solid, holes in m.outline_regions(loops):
            faces.append(_planar_face(solid, holes))
        faces = [f for f in faces if f is not None]
        if not faces:
            return None
        return self._fuse(faces) if len(faces) > 1 else faces[0]

    def _exact_profile(self, node, env):
        """A circle or rectangle (each optionally translated), or a
        difference of them, built from true circles — so a tube or a
        washer exports with cylindrical faces."""
        kids = [c for c in node.children if c.visible
                and c.type not in ("assign",)]
        if len(kids) != 1:
            return None
        return self._exact_2d(kids[0], env, 0.0, 0.0)

    def _exact_2d(self, n, env, dx, dy):
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
        m = self.mesh
        if n.type == "translate" and len(n.children) == 1:
            p = m.rp(n, env)
            if abs(p["z"]) > 1e-12:
                return None
            return self._exact_2d(n.children[0], env, dx + p["x"],
                                  dy + p["y"])
        if n.type == "circle":
            p = m.rp(n, env)
            if p.get("angle", 360.0) not in (0, 360, 360.0) or \
                    p["radius"] <= 0:
                return None
            return _circle_face(p["x"] + dx, p["y"] + dy, p["radius"])
        if n.type == "rect":
            p = m.rp(n, env)
            w, h = p["width"], p["height"]
            if min(w, h) <= 0 or p.get("radius", 0):
                return None
            x, y = p["x"] + dx, p["y"] + dy
            if p.get("center"):
                x, y = x - w / 2, y - h / 2
            return _planar_face([(x, y), (x + w, y), (x + w, y + h),
                                 (x, y + h)], [])
        if n.type == "difference":
            kids = [c for c in n.children if c.visible]
            if not kids:
                return None
            faces = [self._exact_2d(c, env, dx, dy) for c in kids]
            if any(f is None for f in faces):
                return None
            out = faces[0]
            for f in faces[1:]:
                out = BRepAlgoAPI_Cut(out, f).Shape()
            return out
        return None

    def _linear_extrude(self, node, env):
        p = self.mesh.rp(node, env)
        if abs(p.get("twist", 0.0)) > 1e-9 or \
                abs(p.get("scale", 1.0) - 1.0) > 1e-9:
            return None                # a twisted extrude is faceted
        h = p["height"]
        if h <= 0:
            return None
        face = self._face_2d(node, env)
        if face is None:
            return None
        from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
        from OCP.gp import gp_Vec
        solid = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, h)).Shape()
        if p.get("center"):
            solid = self._apply(solid, self.mesh.mat_translate(0, 0,
                                                               -h / 2))
        self._leaf()
        return solid

    def _rotate_extrude(self, node, env):
        p = self.mesh.rp(node, env)
        angle = p.get("angle", 360.0) or 360.0
        face = self._face_2d(node, env)
        if face is None:
            return None
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
        from OCP.gp import gp_Ax1, gp_Pnt, gp_Dir
        # OpenSCAD revolves the XY profile about Y, then stands Y up as Z
        stand = [[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]]
        upright = self._apply(face, stand)
        if upright is None:
            return None
        axis = gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
        try:
            if abs(angle) >= 360.0:
                solid = BRepPrimAPI_MakeRevol(upright, axis).Shape()
            else:
                solid = BRepPrimAPI_MakeRevol(
                    upright, axis, math.radians(angle)).Shape()
        except Exception:
            return None
        self._leaf()
        return solid

    # -- entry ---------------------------------------------------------
    def parts(self):
        """[(name, colour or None, shape)] — one per top-level part."""
        m = self.mesh
        m._set_fn(self.fn)
        m._set_refs(self.root)
        self._stack = set()
        out = []
        try:
            env = {}
            for child in self.root.children:
                if child.type == "assign":
                    m._apply_assign(child, env)
                    continue
                if child.type == "variables":
                    for g in child.children:
                        if g.type == "assign":
                            m._apply_assign(g, env)
                    continue
                if not child.visible:
                    continue
                self._top = None
                self._part_name = _display_name(child)
                shape = self.shape(child, env)
                if shape is None:
                    continue
                out.append((_display_name(child), _first_color(child),
                            shape))
        finally:
            m._set_fn(None)
            m._clear_refs()
        self.report.parts = len(out)
        return out


def _type_label(t):
    from .model import NODE_TYPES
    return str(NODE_TYPES.get(t, {}).get("label", t))


#: wrappers that say where a part is, not what it is
_WRAPPERS = ("translate", "rotate", "scale", "mirror", "color")


def _display_name(node):
    """What the part is called, the way the user named it: a "// Label"
    comment (the bracketed tag of "Cube [Body]"), else a name the user
    typed, found by looking through placement wrappers and into the
    first operand of a boolean (the body a hole is cut from) — else the
    kind of the first meaningful node ("Linear extrude", not
    "Translate")."""
    from .model import name_tag
    chain, n = [], node
    while n is not None and len(chain) < 12:
        chain.append(n)
        kids = [c for c in n.children if c.visible and c.type != "assign"]
        if n.type in _WRAPPERS + ("difference", "intersection",
                                  "linear_extrude", "rotate_extrude") \
                and kids:
            n = kids[0]
        else:
            n = None
    for n in chain:
        tag = name_tag(n.name)
        if tag:
            return tag
    for n in chain:
        name = (n.name or "").strip()
        if name and not name.lower().startswith(
                _type_label(n.type).lower()):
            return name
    first = next((n for n in chain if n.type not in _WRAPPERS), node)
    return _type_label(first.type)


def _first_color(node):
    for n in node.walk():
        if not n.visible:
            continue
        if n.type == "color":
            return str(n.params.get("color", "")) or None
        if n.type in ("union", "reference", "component"):
            col = str(n.params.get("color", "")).strip()
            if col:
                return col
    return None


def _planar_face(solid, holes):
    from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakePolygon,
                                    BRepBuilderAPI_MakeFace)
    from OCP.gp import gp_Pnt

    def wire(loop):
        poly = BRepBuilderAPI_MakePolygon()
        pts = [p for i, p in enumerate(loop)
               if i == 0 or (abs(p[0] - loop[i - 1][0]) > 1e-9
                             or abs(p[1] - loop[i - 1][1]) > 1e-9)]
        if len(pts) < 3:
            return None
        for x, y in pts:
            poly.Add(gp_Pnt(x, y, 0))
        poly.Close()
        return poly.Wire() if poly.IsDone() else None
    outer = wire(solid)
    if outer is None:
        return None
    mk = BRepBuilderAPI_MakeFace(outer, True)
    for h in holes:
        w = wire(h)
        if w is not None:
            w.Reverse()
            mk.Add(w)
    if not mk.IsDone():
        return None
    from OCP.ShapeFix import ShapeFix_Face
    fix = ShapeFix_Face(mk.Face())
    fix.Perform()
    return fix.Face()


def _circle_face(x, y, r):
    from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge,
                                    BRepBuilderAPI_MakeWire,
                                    BRepBuilderAPI_MakeFace)
    from OCP.gp import gp_Circ, gp_Ax2, gp_Pnt, gp_Dir
    circ = gp_Circ(gp_Ax2(gp_Pnt(x, y, 0), gp_Dir(0, 0, 1)), r)
    wire = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circ).Edge())
    return BRepBuilderAPI_MakeFace(wire.Wire(), True).Face()


def solid_from_tris(tris):
    """A closed triangle soup as an OCC solid (one planar face per
    triangle, shared edges merged), or a shell when it is not closed —
    which every receiving program still opens."""
    from OCP.Poly import Poly_Triangulation, Poly_Triangle
    from OCP.gp import gp_Pnt
    from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeShapeOnMesh,
                                    BRepBuilderAPI_MakeSolid)
    from OCP.TopoDS import TopoDS
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer
    index, pts, faces = {}, [], []
    for tri in tris:
        ids = []
        for v in tri:
            key = (round(v[0], 6), round(v[1], 6), round(v[2], 6))
            if key not in index:
                index[key] = len(pts)
                pts.append(key)
            ids.append(index[key])
        if len(set(ids)) == 3:
            faces.append(ids)
    if not faces:
        return None
    poly = Poly_Triangulation(len(pts), len(faces), False)
    for i, (x, y, z) in enumerate(pts, 1):
        poly.SetNode(i, gp_Pnt(x, y, z))
    for i, (a, b, c) in enumerate(faces, 1):
        poly.SetTriangle(i, Poly_Triangle(a + 1, b + 1, c + 1))
    mk = BRepBuilderAPI_MakeShapeOnMesh(poly)
    mk.Build()
    shape = mk.Shape()
    exp = TopExp_Explorer(shape, TopAbs_SHELL)
    if exp.More():
        shell = _topods("Shell", exp.Current())
        if shell.Closed():
            solid = BRepBuilderAPI_MakeSolid(shell)
            if solid.IsDone():
                return solid.Solid()
        return shell
    return shape


# -------------------------------------------------------- writers

def export_model(root, path, fn=None, unit_mm=1.0):
    """Write the document to *path* — STEP, IGES, BREP or 3DM by the
    extension. Returns the Report; raises ValueError for a missing
    engine or a write that failed."""
    path = str(path)
    ext = Path(path).suffix.lower()
    problem = missing(ext)
    if problem:
        raise ValueError(problem)
    if ext in RHINO_EXTS:
        return _write_3dm(root, path, fn, unit_mm)
    _quiet()
    comp = Compiler(root, fn, unit_mm)
    parts = comp.parts()
    if not parts:
        raise ValueError("There is nothing visible to export.")
    if abs(unit_mm - 1.0) > 1e-12:
        from OCP.gp import gp_Trsf, gp_Pnt
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        t = gp_Trsf()
        t.SetScale(gp_Pnt(0, 0, 0), unit_mm)
        parts = [(n, c, BRepBuilderAPI_Transform(s, t, True).Shape())
                 for n, c, s in parts]
    if ext in (".brep", ".brp"):
        from OCP.BRepTools import BRepTools
        if not BRepTools.Write_s(Compiler._compound(
                [s for _n, _c, s in parts]), path):
            raise ValueError(f"Could not write {path}.")
    else:
        _write_xcaf(parts, path, ext)
    return comp.report


def _write_xcaf(parts, path, ext):
    """Named, coloured parts into a STEP (AP214) or IGES file."""
    from OCP.TCollection import (TCollection_ExtendedString,
                                 TCollection_AsciiString)
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ColorSurf
    from OCP.TDataStd import TDataStd_Name
    from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCP.IFSelect import IFSelect_RetDone

    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    colors = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    for name, color, shape in parts:
        label = shapes.AddShape(shape, False)
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(name))
        rgb = _parse_color(color)
        if rgb is not None:
            colors.SetColor(label, Quantity_Color(*rgb, Quantity_TOC_RGB),
                            XCAFDoc_ColorSurf)
    if ext in (".step", ".stp"):
        from OCP.STEPCAFControl import STEPCAFControl_Writer
        from OCP.STEPControl import STEPControl_AsIs
        from OCP.Interface import Interface_Static
        Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
        Interface_Static.SetCVal_s("write.step.unit", "MM")
        writer = STEPCAFControl_Writer()
        writer.SetColorMode(True)
        writer.SetNameMode(True)
        if not writer.Transfer(doc, STEPControl_AsIs):
            raise ValueError("Could not convert the model to STEP.")
        status = writer.Write(path)
    else:
        from OCP.IGESCAFControl import IGESCAFControl_Writer
        writer = IGESCAFControl_Writer()
        writer.SetColorMode(True)
        writer.SetNameMode(True)
        if not writer.Transfer(doc):
            raise ValueError("Could not convert the model to IGES.")
        status = IFSelect_RetDone if writer.Write(path) else None
    if status != IFSelect_RetDone:
        raise ValueError(f"Could not write {Path(path).name}.")
    del TCollection_AsciiString


_NAMED = {"red": "#ff0000", "green": "#008000", "blue": "#0000ff",
          "white": "#ffffff", "black": "#000000", "yellow": "#ffff00",
          "gray": "#808080", "grey": "#808080", "orange": "#ffa500",
          "silver": "#c0c0c0", "gold": "#ffd700"}


def _parse_color(color):
    if not color:
        return None
    text = _NAMED.get(str(color).strip().lower(), str(color).strip())
    if text.startswith("#") and len(text) in (7, 9):
        try:
            return tuple(int(text[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        except ValueError:
            return None
    return None


def _write_3dm(root, path, fn, unit_mm):
    """Each part as a named, coloured mesh on its own layer. Rhino
    reads them as meshes; for exact surfaces send STEP instead (the
    dialog says so)."""
    import rhino3dm as r3
    from . import mesh
    model = r3.File3dm()
    model.Settings.ModelUnitSystem = r3.UnitSystem.Millimeters
    report = Report()
    mesh._set_fn(fn)
    mesh._set_refs(root)
    try:
        env = {}
        for child in root.children:
            if child.type == "assign":
                mesh._apply_assign(child, env)
                continue
            if not child.visible or child.type == "variables":
                continue
            rows = mesh._tess(child, dict(env), None, frozenset(), False)
            if not rows:
                continue
            m = r3.Mesh()
            index = {}
            for tri, _c, _s in rows:
                ids = []
                for v in tri:
                    key = (round(v[0] * unit_mm, 6), round(v[1] * unit_mm, 6),
                           round(v[2] * unit_mm, 6))
                    if key not in index:
                        index[key] = m.Vertices.Add(*key)
                    ids.append(index[key])
                if len(set(ids)) == 3:
                    m.Faces.AddFace(*ids)
            m.Normals.ComputeNormals()
            m.Compact()
            name = _display_name(child)
            layer = r3.Layer()
            layer.Name = name
            rgb = _parse_color(_first_color(child))
            if rgb:
                layer.Color = tuple(int(c * 255) for c in rgb) + (255,)
            li = model.Layers.Add(layer)
            attr = r3.ObjectAttributes()
            attr.Name = name
            attr.LayerIndex = li
            model.Objects.AddMesh(m, attr)
            report.parts += 1
            report.faceted += 1
            report.faceted_names.append(name)
    finally:
        mesh._set_fn(None)
        mesh._clear_refs()
    if not report.parts:
        raise ValueError("There is nothing visible to export.")
    if not model.Write(path, 7):
        raise ValueError(f"Could not write {Path(path).name}.")
    return report
