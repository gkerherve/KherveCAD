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
from .mcp_schema import (DEFAULT_LICENSE, DEFAULT_VIEWS, FORMATS,
                         LICENSES)

#: The page the user finishes on.  Printables' own "add a model" form.
UPLOAD_URL = "https://www.printables.com/model/add"

#: Where the tools live, for the credit line.
TOOLS_URL = "https://khervetools.com"

#: The choices are defined in `mcp_schema` — the MCP tool advertises
#: them and that module has to stay Qt-free, so it owns them and the
#: dialog follows.  A licence default of share-alike matches shipping
#: the parametric source, which is the point of publishing from a CAD
#: tool rather than a mesh.

_CREDIT_HEAD = """\
## Made with

Designed in [KherveCAD]({tools}) — a free, open-source parametric CAD
app with OpenSCAD as its engine — and described with the help of
Claude (Anthropic).
"""

#: Added only when the source really is in the folder.  A listing that
#: promises an editable source it does not ship is worse than one that
#: promises nothing.
_CREDIT_SOURCE = """
The {files} in the download {verb} the real, editable source, not an
export of a mesh: open it, change a dimension, re-export.
"""

_CREDIT_TAIL = """
KherveCAD and the rest of the Kherve tools are at <{tools}>.
"""


def credit(formats=FORMATS) -> str:
    """The attribution block, naming only the files actually shipped."""
    source = [f".{f}" for f in ("scad", "kcad") if f in formats]
    text = _CREDIT_HEAD.format(tools=TOOLS_URL)
    if source:
        text += _CREDIT_SOURCE.format(
            files=" and ".join(f"`{s}`" for s in source),
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


def default_description(window, title: str = "",
                        formats=FORMATS) -> str:
    """A description worth editing rather than one worth deleting.

    Everything here is read off the model, so it is right by
    construction: the size someone needs to check against their bed,
    the parameters they can change, and where the thing came from.
    """
    model = window.model
    size = _bounds(model, fn=(model.global_fn if model.global_fn_on
                              else None))
    lines = []
    if title:
        lines += [f"# {title}", ""]
    lines += ["_One or two sentences on what this is for and why you "
              "made it._", ""]

    if size:
        lines += [
            "## Size",
            "",
            f"**{size[0]} × {size[1]} × {size[2]} mm** as modelled "
            "(X × Y × Z).",
            "",
        ]

    variables = _variables(model)
    if variables:
        lines += ["## Parameters", "",
                  "The model is parametric — these are the values to "
                  "change in the `.scad` or `.kcad` file:", ""]
        lines += [f"- `{name}` = {value}" for name, value in variables]
        lines.append("")

    lines += [
        "## Print settings",
        "",
        "- Layer height: 0.2 mm",
        "- Infill: 20%",
        "- Supports: none",
        "- Material: PLA",
        "",
        "_Adjust to what you actually printed._",
        "",
        credit(formats),
    ]
    return "\n".join(lines)


def build_bundle(window, folder, *, title, description="", tags=(),
                 license=DEFAULT_LICENSE, formats=FORMATS,
                 views=DEFAULT_VIEWS, image_size=(1600, 1200)) -> dict:
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
    notes = folder / "description.md"
    notes.write_text(body, encoding="utf-8")
    wrote(notes)

    meta = folder / "printables.json"
    meta.write_text(json.dumps({
        "title": title,
        "tags": list(tags),
        "license": license,
        "upload_url": UPLOAD_URL,
        "made_with": {"app": "KherveCAD", "url": TOOLS_URL,
                      "engine": "OpenSCAD",
                      "description_by": "Claude (Anthropic)"},
        "files": [Path(f).name for f in files],
    }, indent=2), encoding="utf-8")
    wrote(meta)

    return {"folder": str(folder), "files": files,
            "images": [str(p) for p in images],
            "description": body, "warnings": warnings}


def _render_previews(window, folder, stem, code, views, size,
                     warnings) -> list:
    """Preview stills, from OpenSCAD where it is installed and from the
    3D widget where it is not."""
    out = []
    for name in views:
        rotation = CAMERA_ROTATIONS.get(name)
        if rotation is None:
            warnings.append(f"Skipped unknown view {name!r}.")
            continue
        path = folder / f"{stem}-{name.lower()}.png"
        if window.engine.available:
            error = window.engine.export_png(code, str(path),
                                             rotation=rotation,
                                             size=size)
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
        form.addRow("Title", self.title_edit)
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

        layout.addWidget(QLabel("Description — Markdown, as Printables "
                                "takes it:"))
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
                formats=formats, views=views)
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
                "The description is on your clipboard."]
        if bundle["warnings"]:
            text += ["", "Warnings:"] + ["• " + w
                                         for w in bundle["warnings"]]
        if self.open_box.isChecked():
            text += ["", "Sign in to Printables in the browser tab that "
                     "just opened, drag the files in, and paste the "
                     "description."]
            reveal(bundle["folder"])
            open_upload_page()
        QMessageBox.information(self, "Publish to Printables",
                                "\n".join(text))
        self.accept()
