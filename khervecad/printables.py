"""Publish to Printables: build a complete upload bundle from the model.

Printables has no public upload API — Prusa has never shipped one, and
says so partly to keep automated uploads out — so this does not pretend
to push a model over the wire.  It does everything up to that point:
exports the geometry in the formats Printables accepts, renders the
preview stills, drafts the description, then hands the folder and the
upload page to the user, who is already signed in to Printables in
their own browser and makes the final call.

That split is deliberate.  Everything an assistant can honestly
automate is automated — `mcp_tools.publish_to_printables` builds the
whole bundle unattended, description included — and the one act that
publishes something in the user's name stays a human click.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                             QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                             QPushButton, QVBoxLayout)

from . import document, mesh
from .engine import CAMERA_ROTATIONS, write_stl
from .mcp_schema import (CATEGORIES, DEFAULT_CATEGORY,
                         DEFAULT_LICENSE, DEFAULT_ORIGIN,
                         DEFAULT_VIEWS, FORMATS, LICENSES, ORIGINS,
                         SUMMARY_LIMIT)

#: The page the user finishes on.  Printables' own "add a model" form.
UPLOAD_URL = "https://www.printables.com/model/add"

#: Where the tools live, for the credit line.
TOOLS_URL = "https://khervetools.com"

#: The choices are defined in `mcp_schema` — the MCP tool advertises
#: them and that module has to stay Qt-free, so it owns them and the
#: dialog follows.  A licence default of share-alike matches shipping
#: the parametric source, which is the point of publishing from a CAD
#: tool rather than a mesh.

#: The blocks are single long lines on purpose: Printables re-wraps
#: the description box to its own width, and text hard-wrapped at 70
#: columns comes out ragged there.
_CREDIT_HEAD = """\
MADE WITH

Designed in KherveCAD ({tools}) - a free, open-source parametric CAD app with OpenSCAD as its engine - and described with the help of Claude (Anthropic).
"""

#: Added only when the source really is in the folder.  A listing that
#: promises an editable source it does not ship is worse than one that
#: promises nothing.
_CREDIT_SOURCE = """
The {files} in the download {verb} the real, editable source, not an export of a mesh: open it, change a dimension, re-export.
"""

_CREDIT_TAIL = """
KherveCAD and the rest of the Kherve tools are at {tools}
"""

#: The credit block's heading.  One place, because `build_bundle` looks
#: for it to avoid appending the block twice.
CREDIT_HEADING = "MADE WITH"


def credit(formats=FORMATS) -> str:
    """The attribution block, naming only the files actually shipped."""
    source = [f".{f}" for f in ("scad", "kcad") if f in formats]
    text = _CREDIT_HEAD.format(tools=TOOLS_URL)
    if source:
        text += _CREDIT_SOURCE.format(
            files=" and ".join(source),
            verb="is" if len(source) == 1 else "are")
    return text + _CREDIT_TAIL.format(tools=TOOLS_URL)


def slug(text: str) -> str:
    """A filename stem: words, dashes, nothing surprising."""
    out = re.sub(r"[^\w\s-]", "", str(text)).strip()
    out = re.sub(r"[\s_-]+", "-", out)
    return out.strip("-") or "model"


def _variables(model) -> list:
    """The document's variables, as (name, value) — the parameters a
    downloader would actually change."""
    out = []
    for node in model.root.walk():
        if node.type == "assign":
            name = str(node.params.get("variable", "")).strip()
            if name:
                out.append((name, str(node.params.get("value", ""))))
    return out


def _bounds(model, fn=None):
    try:
        tris = mesh.tessellate(model.root, fn=fn)
    except Exception:
        return None
    from . import anchors
    box = anchors.bbox(tris)
    if box is None:
        return None
    lo, hi = box
    return [round(hi[i] - lo[i], 2) for i in range(3)]


def default_summary(window, title: str = "") -> str:
    """The one-line summary Printables makes required, under its cap.

    Read off the model rather than invented: what it is, that it was
    drawn parametrically, and its footprint if that still fits.
    """
    name = (title or "This model").strip()
    text = f"{name} - parametric model designed in KherveCAD"
    size = _bounds(window.model, fn=(window.model.global_fn
                                     if window.model.global_fn_on
                                     else None))
    if size:
        with_size = text + ", %g x %g x %g mm" % tuple(size)
        if len(with_size) <= SUMMARY_LIMIT:
            text = with_size
    if len(text) > SUMMARY_LIMIT:
        text = text[:SUMMARY_LIMIT - 1].rstrip(" ,-") + "…"
    return text


#: What the form's print-settings block says when the caller does not
#: say otherwise.  Declarative, because the field is answered here: a
#: note reading "adjust to what you actually printed" is an instruction
#: to the author sitting in a field the reader sees.
PRINT_SETTINGS = {
    "Rafts": "no",
    "Supports": "no",
    "Resolution": "0.2 mm layer height",
    "Infill": "20%",
    "Filament": "PLA",
    "Notes": "a starting point rather than a tested profile",
}


def form_answers(window, *, title, summary="", tags=(),
                 category=DEFAULT_CATEGORY, license=DEFAULT_LICENSE,
                 origin=DEFAULT_ORIGIN, formats=FORMATS,
                 print_settings=None) -> str:
    """The upload form, field by field, already filled in.

    Printables' "add a model" page asks the same questions every time
    and none of the answers are in the STL, so the bundle carries them
    as copy-and-paste text: the user reads down the page and pastes,
    rather than inventing a category and a summary at upload time.
    """
    model = window.model
    size = _bounds(model, fn=(model.global_fn if model.global_fn_on
                              else None))
    lines = [
        "PRINTABLES UPLOAD FORM - answers to copy across",
        "=" * 46,
        "",
        "Model name (required)",
        f"  {title}",
        "",
        "Summary (required, max %d characters)" % SUMMARY_LIMIT,
        f"  {summary or default_summary(window, title)}",
        "",
        "Main category (required)",
        f"  {category}",
        "",
        "Additional tags (space separated on the form)",
        "  " + (" ".join(tags) if tags else
                "parametric openscad cad 3dprint"),
        "",
        "Model origin - this is a...",
        f"  {origin}",
        "",
        "Licence",
        f"  {license}",
        "",
        "Description",
        "  Paste description.txt (plain text, no Markdown).",
        "",
        "Print settings",
    ]
    settings = dict(PRINT_SETTINGS)
    settings.update(print_settings or {})
    lines += [f"  {key}: {value}" for key, value in settings.items()]
    lines += [
        "",
        "Files to upload",
        "  " + ", ".join(f".{f}" for f in formats) +
        " plus every .png in this folder (the isometric render is "
        "first, so it becomes the cover image).",
    ]
    if size:
        lines += ["", "Bounding box (for your own check against the "
                  "bed)", "  %g x %g x %g mm" % tuple(size)]
    return "\n".join(lines) + "\n"


def _shape_of(model) -> tuple:
    """How the model is built, as (objects, booleans, extrusions).

    Not a classification — nothing here guesses what a part is *for*.
    It is the arithmetic a reader would otherwise do by opening the
    file, and it is the honest half of an opening paragraph.
    """
    objects = booleans = extrusions = 0
    for node in model.root.walk():
        if node.type in ("root", "variables", "masters", "assign"):
            continue
        objects += 1
        if node.type in ("difference", "intersection", "hull",
                         "minkowski"):
            booleans += 1
        elif node.type in ("linear_extrude", "rotate_extrude"):
            extrusions += 1
    return objects, booleans, extrusions


def opening(window, title: str = "") -> str:
    """The paragraph the description opens with.

    This used to be the line "one or two sentences on what this is for
    and why you made it", which is a note to the author sitting where
    the reader's first sentence belongs — and it went out unedited more
    often than not.  So it is written instead, from what the model
    actually says about itself: its size, how it is built, and how many
    dimensions are named rather than baked in.  Everything in it is
    true of any model; the *why* is the one thing only the author can
    add, and a real paragraph is far easier to add a sentence to than a
    placeholder is to replace.
    """
    model = window.model
    name = (title or "This").strip()
    size = _bounds(model, fn=(model.global_fn if model.global_fn_on
                              else None))
    first = name
    if size:
        first += " is a %g x %g x %g mm part" % tuple(size)
    else:
        first += " is a part"
    first += " designed in KherveCAD and exported straight from the "
    first += "object tree that defines it."

    objects, booleans, extrusions = _shape_of(model)
    built = []
    if extrusions:
        built.append("%d extrusion%s" % (extrusions,
                                         "" if extrusions == 1 else "s"))
    if booleans:
        built.append("%d boolean%s" % (booleans,
                                       "" if booleans == 1 else "s"))
    second = ""
    if objects:
        second = "It is built from %d object%s" % (
            objects, "" if objects == 1 else "s")
        if built:
            second += " (" + " and ".join(built) + ")"
        second += "."

    variables = _variables(model)
    third = ""
    if variables:
        third = ("%d dimension%s %s named rather than baked in, so it "
                 "can be resized without redrawing it." % (
                     len(variables),
                     "" if len(variables) == 1 else "s",
                     "is" if len(variables) == 1 else "are"))

    return " ".join(part for part in (first, second, third) if part)


def default_description(window, title: str = "",
                        formats=FORMATS) -> str:
    """A description worth editing rather than one worth deleting.

    Plain text, because that is what Printables' description box shows
    back: Markdown pasted in reads as literal hashes and backticks.
    Everything here is read off the model, so it is right by
    construction: the size someone needs to check against their bed,
    the parameters they can change, and where the thing came from.
    """
    model = window.model
    size = _bounds(model, fn=(model.global_fn if model.global_fn_on
                              else None))
    lines = []
    if title:
        lines += [title.upper(), ""]
    lines += [opening(window, title), ""]

    if size:
        lines += [
            "SIZE",
            "",
            "%g x %g x %g mm as modelled (X x Y x Z)." % tuple(size),
            "",
        ]

    variables = _variables(model)
    if variables:
        lines += ["PARAMETERS", "",
                  "The model is parametric - these are the values to "
                  "change in the .scad or .kcad file:", ""]
        lines += [f"  {name} = {value}" for name, value in variables]
        lines.append("")

    lines += [
        "PRINT SETTINGS",
        "",
        "Layer height: 0.2 mm",
        "Infill: 20%",
        "Supports: none",
        "Material: PLA",
        "",
        "A starting point rather than a tested profile - if you "
        "printed it differently, say so in a comment and I will "
        "update this.",
        "",
        credit(formats),
    ]
    return "\n".join(lines)


def build_bundle(window, folder, *, title, description="", tags=(),
                 license=DEFAULT_LICENSE, formats=FORMATS,
                 views=DEFAULT_VIEWS, image_size=(2000, 1500),
                 summary="", category=DEFAULT_CATEGORY,
                 origin=DEFAULT_ORIGIN, print_settings=None) -> dict:
    """Write the upload folder. Returns what was written and what wasn't.

    Never raises for a missing engine or a format OpenSCAD declined —
    those come back in ``warnings`` so a partial bundle is still
    usable, and the caller can say what is missing.
    """
    folder = Path(str(folder)).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    stem = slug(title)
    model, engine = window.model, window.engine
    code = model.to_scad()
    files, warnings = [], []

    def wrote(path):
        files.append(str(path))

    if "scad" in formats:
        path = folder / f"{stem}.scad"
        document.export_scad(model, str(path))
        wrote(path)

    if "kcad" in formats:
        path = folder / f"{stem}.kcad"
        document.save_kcad(model, str(path))
        wrote(path)

    if "stl" in formats:
        path = folder / f"{stem}.stl"
        if engine.available:
            error = engine.export_mesh(code, str(path))
            if error:
                warnings.append(f"STL export failed: {error}")
            else:
                wrote(path)
        else:
            fn = model.global_fn if model.global_fn_on else None
            write_stl(mesh.tessellate(model.root, fn=fn), str(path))
            wrote(path)
            warnings.append(
                "OpenSCAD was not found, so the STL came from the "
                "built-in tessellator." + (
                    " This model uses booleans and they are only "
                    "APPROXIMATED — holes are not cut. Do not upload "
                    "it: install OpenSCAD and build the bundle again."
                    if mesh.uses_booleans(model.root) else
                    " This model uses no booleans, so the geometry is "
                    "faithful."))

    if "3mf" in formats:
        path = folder / f"{stem}.3mf"
        if not engine.available:
            warnings.append(
                "No 3MF: OpenSCAD writes that format and it was not "
                "found.")
        else:
            error = engine.export_mesh(code, str(path))
            if error:
                warnings.append(f"3MF export failed: {error}")
            else:
                wrote(path)

    images = _render_previews(window, folder, stem, code, views,
                              image_size, warnings)
    files += [str(p) for p in images]

    body = description or default_description(window, title,
                                              formats)
    if TOOLS_URL not in body:
        # the credit is the point of publishing from here, and a
        # description written elsewhere (the MCP tool, the user) has no
        # reason to have carried it.
        body = body.rstrip() + "\n\n" + credit(formats)
    notes = folder / "description.txt"
    notes.write_text(body, encoding="utf-8")
    wrote(notes)

    summary = (summary or default_summary(window, title)).strip()
    if len(summary) > SUMMARY_LIMIT:
        summary = summary[:SUMMARY_LIMIT - 1].rstrip() + "…"
        warnings.append("The summary was trimmed to Printables' %d "
                        "character limit." % SUMMARY_LIMIT)
    form = folder / "upload-form.txt"
    form.write_text(form_answers(window, title=title, summary=summary,
                                 tags=tags, category=category,
                                 license=license, origin=origin,
                                 formats=formats,
                                 print_settings=print_settings),
                    encoding="utf-8")
    wrote(form)

    meta = folder / "printables.json"
    meta.write_text(json.dumps({
        "title": title,
        "summary": summary,
        "category": category,
        "origin": origin,
        "tags": list(tags),
        "license": license,
        "description_format": "plain text",
        "print_settings": dict(PRINT_SETTINGS,
                               **(print_settings or {})),
        "upload_url": UPLOAD_URL,
        "made_with": {"app": "KherveCAD", "url": TOOLS_URL,
                      "engine": "OpenSCAD",
                      "description_by": "Claude (Anthropic)"},
        "files": [Path(f).name for f in files],
    }, indent=2), encoding="utf-8")
    wrote(meta)

    return {"folder": str(folder), "files": files,
            "images": [str(p) for p in images],
            "description": body, "summary": summary,
            "category": category, "form": str(form),
            "warnings": warnings}


def trim_to_content(path, margin=0.06, aspect=4 / 3.0) -> bool:
    """Crop *path* down to the model, keeping *aspect*.

    OpenSCAD's ``--viewall`` frames the bounding SPHERE, so a long thin
    part lying on a diagonal is rendered correct and tiny — most of the
    canvas is empty background, and on Printables that is the thumbnail
    people decide on.  The background is flat, so the model's real
    extent is just the pixels that differ from the corner colour;
    cropping to that with a margin turns the same render into a picture
    of the part.  Returns False and leaves the file alone if there is
    nothing to crop.
    """
    from PyQt5.QtGui import QImage
    image = QImage(str(path))
    if image.isNull():
        return False
    image = image.convertToFormat(QImage.Format_RGB32)
    width, height = image.width(), image.height()
    background = image.pixel(0, 0)

    def differs(x, y):
        pixel = image.pixel(x, y)
        return (abs(((pixel >> 16) & 255) - ((background >> 16) & 255))
                + abs(((pixel >> 8) & 255) - ((background >> 8) & 255))
                + abs((pixel & 255) - (background & 255))) > 12

    step = max(1, min(width, height) // 400)   # a scan, not a survey
    xs, ys = [], []
    for y in range(0, height, step):
        for x in range(0, width, step):
            if differs(x, y):
                xs.append(x)
                ys.append(y)
    if not xs:
        return False
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    span = max(x1 - x0, (y1 - y0) * aspect) * (1 + 2 * margin)
    if span >= width * 0.92:
        return False                    # already fills the frame
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    # never crop past this: a front view of a flat part is a sliver,
    # and trimming to it exactly would hand Printables a 200 px image.
    box_w = min(width, max(span, width * 0.45))
    box_h = min(height, box_w / aspect)
    box_w = box_h * aspect
    left = int(max(0, min(width - box_w, cx - box_w / 2)))
    top = int(max(0, min(height - box_h, cy - box_h / 2)))
    crop = image.copy(left, top, int(box_w), int(box_h))
    return bool(crop.save(str(path), "PNG"))


def _render_previews(window, folder, stem, code, views, size,
                     warnings) -> list:
    """Preview stills, from OpenSCAD where it is installed and from the
    3D widget where it is not.

    Printables shows the FIRST image as the cover, and a listing is
    judged on it, so the isometric is rendered first and larger than
    the rest.  The names are numbered because the upload page keeps
    the order the files arrive in, which is the order the file dialog
    lists them.
    """
    ordered = list(views)
    for hero in ("Isometric",):          # the one that gets the click
        if hero in ordered:
            ordered.insert(0, ordered.pop(ordered.index(hero)))

    out = []
    for index, name in enumerate(ordered, 1):
        rotation = CAMERA_ROTATIONS.get(name)
        if rotation is None:
            warnings.append(f"Skipped unknown view {name!r}.")
            continue
        path = folder / f"{stem}-{index}-{name.lower()}.png"
        shot = (int(size[0] * 1.3), int(size[1] * 1.3)) if index == 1 \
            else size
        if window.engine.available:
            error = window.engine.export_png(code, str(path),
                                             rotation=rotation,
                                             size=shot)
            if error:
                warnings.append(f"{name} preview failed: {error}")
                continue
        else:
            window.view3d.set_view(name)
            pixmap = window.view3d.grab()
            if pixmap.isNull() or pixmap.width() < 2 or \
                    not pixmap.save(str(path), "PNG"):
                warnings.append(f"{name} preview could not be grabbed.")
                continue
            warnings.append(
                f"{name} preview is a screen grab of the built-in "
                "preview, not an OpenSCAD render.")
        try:
            trim_to_content(path)
        except Exception as exc:                     # cosmetic, never fatal
            warnings.append(f"{name} preview was not cropped: {exc}")
        out.append(path)
    return out


def open_upload_page():
    QDesktopServices.openUrl(QUrl(UPLOAD_URL))


def reveal(path):
    """Show *path* in the OS file manager."""
    path = Path(str(path))
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


class PublishDialog(QDialog):
    """File ▸ Publish to Printables — assemble the bundle, then hand
    the folder and the upload page over."""

    def __init__(self, window):
        super().__init__(window)
        self._w = window
        self.setWindowTitle("Publish to Printables")
        self.setMinimumWidth(640)
        self.result_bundle = None

        stem = Path(window._path).stem if window._path else ""
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.title_edit = QLineEdit(stem or "Untitled model")
        form.addRow("Model name", self.title_edit)
        self.summary_edit = QLineEdit(
            default_summary(window, self.title_edit.text()))
        self.summary_edit.setMaxLength(SUMMARY_LIMIT)
        self.summary_edit.setToolTip(
            "Printables' required one-liner, max %d characters."
            % SUMMARY_LIMIT)
        form.addRow("Summary", self.summary_edit)
        self.category_combo = QComboBox()
        self.category_combo.addItems(CATEGORIES)
        self.category_combo.setCurrentText(DEFAULT_CATEGORY)
        form.addRow("Main category", self.category_combo)
        self.origin_combo = QComboBox()
        self.origin_combo.addItems(ORIGINS)
        form.addRow("Model origin", self.origin_combo)
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText(
            "comma separated — printed, functional, parametric, openscad")
        form.addRow("Tags", self.tags_edit)
        self.license_combo = QComboBox()
        self.license_combo.addItems(LICENSES)
        self.license_combo.setCurrentText(DEFAULT_LICENSE)
        form.addRow("Licence", self.license_combo)
        layout.addLayout(form)

        files_box = QGroupBox("Files")
        files_row = QHBoxLayout(files_box)
        self._format_boxes = {}
        for key, label in (("stl", "STL"), ("3mf", "3MF"),
                           ("scad", "OpenSCAD source"),
                           ("kcad", "KherveCAD project")):
            box = QCheckBox(label)
            box.setChecked(True)
            files_row.addWidget(box)
            self._format_boxes[key] = box
        if not window.engine.available:
            self._format_boxes["3mf"].setChecked(False)
            self._format_boxes["3mf"].setEnabled(False)
            self._format_boxes["3mf"].setToolTip(
                "OpenSCAD writes 3MF and it was not found.")
        layout.addWidget(files_box)

        views_box = QGroupBox("Preview images")
        views_row = QHBoxLayout(views_box)
        self._view_boxes = {}
        for name in CAMERA_ROTATIONS:
            box = QCheckBox(name)
            box.setChecked(name in DEFAULT_VIEWS)
            views_row.addWidget(box)
            self._view_boxes[name] = box
        layout.addWidget(views_box)

        layout.addWidget(QLabel(
            "Description — plain text, so it pastes into Printables' "
            "box exactly as written:"))
        self.description_edit = QPlainTextEdit(
            default_description(window, self.title_edit.text(),
                                self._selected(self._format_boxes)))
        self.description_edit.setMinimumHeight(240)
        layout.addWidget(self.description_edit)

        regen = QPushButton("Regenerate from the model")
        regen.setToolTip("Rebuild the draft — this discards your edits.")
        regen.clicked.connect(self._regenerate)
        layout.addWidget(regen)

        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit(self._default_folder())
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        folder_row.addWidget(QLabel("Folder"))
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(browse)
        layout.addLayout(folder_row)

        self.open_box = QCheckBox(
            "Open the Printables upload page and show the folder when "
            "it is built")
        self.open_box.setChecked(True)
        layout.addWidget(self.open_box)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        build = buttons.addButton("Build bundle",
                                  QDialogButtonBox.AcceptRole)
        build.clicked.connect(self._build)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------ bits
    def _default_folder(self) -> str:
        base = (Path(self._w._path).parent if self._w._path
                else Path.home() / "Documents")
        return str(base / f"{slug(self.title_edit.text())}-printables")

    def _browse(self):
        path = QFileDialog.getExistingDirectory(
            self, "Bundle folder", self.folder_edit.text())
        if path:
            self.folder_edit.setText(path)

    def _regenerate(self):
        self.description_edit.setPlainText(
            default_description(self._w, self.title_edit.text(),
                                self._selected(self._format_boxes)))
        self.summary_edit.setText(
            default_summary(self._w, self.title_edit.text()))

    def _selected(self, boxes) -> tuple:
        return tuple(k for k, b in boxes.items() if b.isChecked())

    # ----------------------------------------------------------- build
    def _build(self):
        title = self.title_edit.text().strip() or "Untitled model"
        formats = self._selected(self._format_boxes)
        views = self._selected(self._view_boxes)
        if not formats:
            QMessageBox.warning(self, "Publish to Printables",
                                "Printables needs at least one model "
                                "file.")
            return
        tags = [t.strip() for t in self.tags_edit.text().split(",")
                if t.strip()]
        try:
            bundle = build_bundle(
                self._w, self.folder_edit.text(), title=title,
                description=self.description_edit.toPlainText(),
                tags=tags, license=self.license_combo.currentText(),
                formats=formats, views=views,
                summary=self.summary_edit.text(),
                category=self.category_combo.currentText(),
                origin=self.origin_combo.currentText())
        except Exception as exc:
            QMessageBox.warning(self, "Publish to Printables",
                                f"Could not build the bundle:\n{exc}")
            return

        self.result_bundle = bundle
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(bundle["description"])

        text = ["Bundle ready in:", bundle["folder"], "",
                "%d file(s), %d preview image(s)."
                % (len(bundle["files"]), len(bundle["images"])),
                "The description is on your clipboard, and "
                "upload-form.txt answers every field on the upload "
                "page."]
        if bundle["warnings"]:
            text += ["", "Warnings:"] + ["• " + w
                                         for w in bundle["warnings"]]
        if self.open_box.isChecked():
            text += ["", "Sign in to Printables in the browser tab "
                     "that just opened, drag the files in, paste the "
                     "description, and copy the rest of the fields "
                     "from upload-form.txt."]
            reveal(bundle["folder"])
            open_upload_page()
        QMessageBox.information(self, "Publish to Printables",
                                "\n".join(text))
        self.accept()
