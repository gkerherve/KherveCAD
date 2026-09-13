"""Writing a Blueprint sheet: PDF, SVG and PNG through Qt's own
painting of the scene, a layered DXF (R12, sheet millimetres) from the
items' primitives, and printing.

The DXF is written from the SAME primitives the screen paints
(`blueprint_items`), so lines, arrows, circles, arcs and text land where
they are drawn — on VISIBLE / HIDDEN / CENTER / DIM / TEXT / HATCH /
FRAME / TITLE layers with real HIDDEN and CENTER linetypes, for any CAD
or CAM program.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from pathlib import Path

from PyQt5.QtCore import QMarginsF, QPointF, QRectF, QSize, QSizeF, Qt
from PyQt5.QtGui import QImage, QPainter

from . import blueprint_items as bi

#: layer -> (AutoCAD colour index, linetype)
LAYERS = {
    "VISIBLE": (7, "CONTINUOUS"), "HIDDEN": (8, "HIDDEN"),
    "CENTER": (1, "CENTER"), "DIM": (4, "CONTINUOUS"),
    "TEXT": (7, "CONTINUOUS"), "HATCH": (8, "CONTINUOUS"),
    "FRAME": (7, "CONTINUOUS"), "TITLE": (7, "CONTINUOUS"),
    "THIN": (7, "CONTINUOUS"), "CUT": (1, "CENTER"),
    "SKETCH": (7, "CONTINUOUS"), "SECTION": (7, "CONTINUOUS"),
}
#: a primitive's line kind decides its layer; thin lines and text go
#: on the owning item's own layer
KIND_LAYERS = {"visible": "VISIBLE", "hidden": "HIDDEN",
               "center": "CENTER", "dim": "DIM", "hatch": "HATCH",
               "frame": "FRAME", "cut": "CUT"}


class DxfWriter:
    """Just enough DXF R12: layers with linetypes, LINE, CIRCLE, ARC,
    SOLID and TEXT. Sheet y runs down; DXF's runs up."""

    def __init__(self, sheet_height):
        self.H = float(sheet_height)
        self.entities = []

    def _xy(self, p, code=10):
        return [str(code), f"{p[0]:.4f}", str(code + 10),
                f"{self.H - p[1]:.4f}", str(code + 20), "0"]

    def line(self, layer, a, b):
        self.entities += ["0", "LINE", "8", layer] + self._xy(a) + \
            self._xy(b, 11)

    def circle(self, layer, c, r):
        self.entities += ["0", "CIRCLE", "8", layer] + self._xy(c) + \
            ["40", f"{r:.4f}"]

    def arc(self, layer, c, r, start, sweep):
        # visual counter-clockwise on the sheet is counter-clockwise in
        # DXF's y-up frame too, so the angles carry straight over
        self.entities += ["0", "ARC", "8", layer] + self._xy(c) + \
            ["40", f"{r:.4f}", "50", f"{start % 360.0:.4f}", "51",
             f"{(start + sweep) % 360.0:.4f}"]

    def solid(self, layer, pts):
        pts = list(pts)[:4]
        while len(pts) < 4:
            pts.append(pts[-1])
        # SOLID takes its corners in Z order: 1, 2, 4, 3
        body = self._xy(pts[0]) + self._xy(pts[1], 11) + \
            self._xy(pts[3], 12) + self._xy(pts[2], 13)
        self.entities += ["0", "SOLID", "8", layer] + body

    def text(self, layer, p, height, value, angle=0.0):
        if not str(value).strip():
            return
        self.entities += ["0", "TEXT", "8", layer] + self._xy(p) + \
            ["40", f"{height:.4f}", "1", _ascii(value), "50",
             f"{angle % 360.0:.4f}"]

    def document(self):
        out = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4",
               "0", "ENDSEC", "0", "SECTION", "2", "TABLES",
               "0", "TABLE", "2", "LTYPE", "70", "3"]
        for name, desc, pattern in (
                ("CONTINUOUS", "Solid line", ()),
                ("HIDDEN", "__ __ __", (3.0, -1.5)),
                ("CENTER", "____ _ ____", (8.0, -1.5, 1.5, -1.5))):
            out += ["0", "LTYPE", "2", name, "70", "0", "3", desc, "72",
                    "65", "73", str(len(pattern)), "40",
                    f"{sum(abs(v) for v in pattern):.4f}"]
            for v in pattern:
                out += ["49", f"{v:.4f}"]
        out += ["0", "ENDTAB", "0", "TABLE", "2", "LAYER", "70",
                str(len(LAYERS))]
        for name, (colour, ltype) in LAYERS.items():
            out += ["0", "LAYER", "2", name, "70", "0", "62", str(colour),
                    "6", ltype]
        out += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2",
                "ENTITIES"] + self.entities + ["0", "ENDSEC", "0", "EOF"]
        return "\n".join(out) + "\n"


def _ascii(value):
    """R12 text is 8-bit: spell out what it cannot carry."""
    table = {"Ø": "%%c", "±": "%%p", "°": "%%d", "×": "x", "−": "-",
             "√": "V"}
    return "".join(table.get(c, c if ord(c) < 128 else "?")
                   for c in str(value).replace("\n", " "))


def add_prims(writer, prims, transform, item_layer):
    """Write *prims* (item coordinates) through *transform* (item ->
    sheet) on their layers."""
    def m(p):
        q = transform.map(QPointF(p[0], p[1]))
        return q.x(), q.y()
    for p in prims:
        kind = p[1]
        layer = KIND_LAYERS.get(kind, item_layer)
        if p[0] == "line":
            writer.line(layer, m(p[2]), m(p[3]))
        elif p[0] == "poly":
            pts = [m(q) for q in p[2]]
            if p[4] and 3 <= len(pts) <= 4:
                writer.solid(layer, pts)
                continue
            ring = pts + pts[:1] if p[3] else pts
            for a, b in zip(ring, ring[1:]):
                writer.line(layer, a, b)
        elif p[0] == "circle":
            writer.circle(layer, m(p[2]), p[3])
        elif p[0] == "arc":
            writer.arc(layer, m(p[2]), p[3], p[4], p[5])
        elif p[0] == "text":
            t = bi.text_transform(p)
            size = p[4]
            for i, value in enumerate(str(p[3]).split("\n")):
                base = t.map(QPointF(0.0, i * 1.6 * size))
                q = transform.map(base)
                writer.text("TEXT" if item_layer != "DIM" else "DIM",
                            (q.x(), q.y()), size, value, p[7])


def sheet_items(scene):
    """The items that make up the drawing, bottom to top — no previews,
    no snap markers."""
    out = []
    for item in scene.items(Qt.AscendingOrder):
        if getattr(item, "transient", False) or not item.isVisible():
            continue
        if isinstance(item, (bi.SheetItem, bi.ViewItem)):
            out.append(item)
    return out


def dxf_text(scene):
    writer = DxfWriter(scene.sheet_rect().height())
    for item in sheet_items(scene):
        if isinstance(item, bi.ViewItem):
            add_prims(writer, item.dxf_prims(), item.sceneTransform(),
                      "TEXT")
        else:
            add_prims(writer, item.prims, item.sceneTransform(), item.LAYER)
    return writer.document()


def write_dxf(scene, path):
    Path(path).write_text(dxf_text(scene), encoding="ascii")


def paint_sheet(scene, painter, target):
    """The sheet alone, into *target* (device rectangle)."""
    with scene.exporting():
        painter.setRenderHint(QPainter.Antialiasing, True)
        scene.render(painter, target, scene.sheet_rect(),
                     Qt.IgnoreAspectRatio)


def write_pdf(scene, path):
    from PyQt5.QtGui import QPageSize, QPdfWriter
    rect = scene.sheet_rect()
    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QSizeF(rect.width(), rect.height()),
                                 QPageSize.Millimeter))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    writer.setResolution(600)
    writer.setTitle(scene.title_text())
    writer.setCreator("KherveCAD")
    painter = QPainter(writer)
    paint_sheet(scene, painter, QRectF(0, 0, writer.width(),
                                       writer.height()))
    painter.end()


def write_svg(scene, path):
    from PyQt5.QtSvg import QSvgGenerator
    rect = scene.sheet_rect()
    k = 4.0
    gen = QSvgGenerator()
    gen.setFileName(str(path))
    gen.setSize(QSize(int(rect.width() * k), int(rect.height() * k)))
    gen.setViewBox(QRectF(0, 0, rect.width() * k, rect.height() * k))
    gen.setTitle(scene.title_text())
    gen.setDescription("Drawn in KherveCAD")
    painter = QPainter(gen)
    paint_sheet(scene, painter, QRectF(0, 0, rect.width() * k,
                                       rect.height() * k))
    painter.end()


def to_image(scene, px_per_mm=8.0):
    rect = scene.sheet_rect()
    image = QImage(int(rect.width() * px_per_mm),
                   int(rect.height() * px_per_mm), QImage.Format_ARGB32)
    image.fill(scene.look.color("ground"))
    painter = QPainter(image)
    paint_sheet(scene, painter, QRectF(0, 0, image.width(), image.height()))
    painter.end()
    return image


def write_png(scene, path, px_per_mm=8.0):
    if not to_image(scene, px_per_mm).save(str(path), "PNG"):
        raise OSError(f"Could not write {path}.")


WRITERS = {".pdf": write_pdf, ".svg": write_svg, ".png": write_png,
           ".dxf": write_dxf}
FILTERS = "PDF (*.pdf);;DXF for CAD/CAM (*.dxf);;SVG (*.svg);;PNG (*.png)"


def export(scene, path):
    suffix = Path(str(path)).suffix.lower()
    if suffix not in WRITERS:
        raise ValueError("A blueprint is written as .pdf, .svg, .png or "
                         ".dxf")
    Path(str(path)).parent.mkdir(parents=True, exist_ok=True)
    WRITERS[suffix](scene, str(path))
    return str(path)


def print_sheet(scene, parent=None):
    """Print through the system dialog, the sheet fitted to the page."""
    from PyQt5.QtGui import QPageLayout, QPageSize
    from PyQt5.QtPrintSupport import QPrintDialog, QPrinter
    rect = scene.sheet_rect()
    printer = QPrinter(QPrinter.HighResolution)
    printer.setPageSize(QPageSize(QSizeF(rect.width(), rect.height()),
                                  QPageSize.Millimeter))
    printer.setPageOrientation(QPageLayout.Landscape)
    printer.setDocName(scene.title_text())
    dialog = QPrintDialog(printer, parent)
    if dialog.exec_() != QPrintDialog.Accepted:
        return False
    painter = QPainter(printer)
    page = printer.pageRect(QPrinter.DevicePixel)
    target = QRectF(0, 0, page.width(), page.height())
    ratio = rect.width() / rect.height()
    if target.width() / target.height() > ratio:
        w = target.height() * ratio
        target = QRectF((target.width() - w) / 2, 0, w, target.height())
    else:
        h = target.width() / ratio
        target = QRectF(0, (target.height() - h) / 2, target.width(), h)
    paint_sheet(scene, painter, target)
    painter.end()
    return True
