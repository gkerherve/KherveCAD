"""AI ▸ Mesh from Photo…: pick a picture and a backend, generate,
import — with the work on a thread so the window keeps painting.

`run_blocking` is the same generation for the MCP tool: it pumps the
event loop while the thread runs, since a tool call already holds the
GUI thread and a hosted generation takes minutes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import tempfile
from pathlib import Path

from PyQt5.QtCore import (QCoreApplication, QEventLoop, QSettings, Qt,
                          QThread, pyqtSignal)
from PyQt5.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox,
                             QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPlainTextEdit, QPushButton,
                             QVBoxLayout)

from . import language, photo3d

_SETTINGS = ("Kherve", "KherveCAD")
BACKEND_LABELS = {"tripo": "Tripo (api.tripo3d.ai)",
                  "meshy": "Meshy (api.meshy.ai)",
                  "local": "Local command"}


def get_key(backend: str) -> str:
    key = QSettings(*_SETTINGS).value(f"photo3d/keys/{backend}", "") or ""
    if not key:
        key = os.environ.get(photo3d.KEY_ENV.get(backend, ""), "")
    return key


def set_key(backend: str, key: str):
    QSettings(*_SETTINGS).setValue(f"photo3d/keys/{backend}", key)


def get_command() -> str:
    return QSettings(*_SETTINGS).value("photo3d/command", "") or ""


def set_command(command: str):
    QSettings(*_SETTINGS).setValue("photo3d/command", command)


def output_dir(image) -> str:
    """Where the generated files go: beside the picture when its folder
    is writable, else a temp folder."""
    folder = Path(image).parent
    if os.access(folder, os.W_OK):
        return str(folder)
    return tempfile.mkdtemp(prefix="khervecad-photo3d-")


class Worker(QThread):
    done = pyqtSignal(str)          # the STL path
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, image, backend, key, command, size_mm, parent=None):
        super().__init__(parent)
        self.image, self.backend = image, backend
        self.key, self.command, self.size_mm = key, command, size_mm

    def run(self):
        try:
            mesh = photo3d.generate(
                self.image, output_dir(self.image), self.backend,
                self.key, self.command,
                progress=lambda s: self.progress.emit(
                    str(s.get("status") or s.get("progress") or "")))
            self.done.emit(photo3d.to_stl(mesh, self.size_mm))
        except Exception as exc:              # reported, never raised
            self.failed.emit(str(exc))


def run_blocking(window, image, backend, key, command, size_mm,
                 timeout_s=photo3d.TIMEOUT_S) -> str:
    """Generate on a thread while the event loop keeps running; returns
    the STL path or raises photo3d.Photo3DError."""
    import time
    worker = Worker(image, backend, key, command, size_mm, window)
    result = {}
    # direct connections: the result is stored from the worker thread,
    # not queued behind an event loop that may have stopped pumping
    worker.done.connect(lambda p: result.setdefault("stl", p),
                        Qt.DirectConnection)
    worker.failed.connect(lambda m: result.setdefault("error", m),
                          Qt.DirectConnection)
    worker.start()
    deadline = time.monotonic() + timeout_s
    while worker.isRunning() and time.monotonic() < deadline:
        QCoreApplication.processEvents(QEventLoop.AllEvents, 50)
        QThread.msleep(15)
    worker.wait(2000)
    QCoreApplication.processEvents(QEventLoop.AllEvents, 50)
    if "error" in result:
        raise photo3d.Photo3DError(result["error"])
    if "stl" not in result:
        raise photo3d.Photo3DError("the generation timed out")
    return result["stl"]


class Photo3DDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setWindowTitle(language.tr("Mesh from Photo"))
        self.setWindowFlag(Qt.Tool, True)
        self.worker = None
        form = QFormLayout()
        row = QHBoxLayout()
        self.image = QLineEdit()
        self.image.setPlaceholderText(
            language.tr("A picture of the object, one view"))
        browse = QPushButton(language.tr("Browse\u2026"))
        browse.clicked.connect(self._browse)
        row.addWidget(self.image, 1)
        row.addWidget(browse)
        form.addRow(language.tr("Picture"), row)
        self.backend = QComboBox()
        for key, label in BACKEND_LABELS.items():
            self.backend.addItem(label, key)
        self.backend.setCurrentIndex(0)
        self.backend.currentIndexChanged.connect(self._backend_changed)
        form.addRow(language.tr("Generator"), self.backend)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        form.addRow(language.tr("API key"), self.key)
        self.command = QLineEdit()
        self.command.setPlaceholderText(
            "python gen.py --image {image} --out {output}")
        self.command.setText(get_command())
        form.addRow(language.tr("Command"), self.command)
        self.size = QDoubleSpinBox()
        self.size.setRange(1.0, 100000.0)
        self.size.setValue(100.0)
        self.size.setSuffix(" mm")
        form.addRow(language.tr("Longest side"), self.size)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(200)
        self.go = QPushButton(language.tr("Generate and import"))
        self.go.clicked.connect(self.generate)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel(language.tr(
            "One picture gives a plausible surface — the "
                             "far side is guessed. Sculpt it afterwards, "
                             "checking against the photo with View \u25b8 "
                             "Compare to Reference Image.")))
        lay.addWidget(self.log, 1)
        lay.addWidget(self.go)
        self._backend_changed()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, language.tr("Picture"), "",
            "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.image.setText(path)

    def _backend_changed(self):
        backend = self.backend.currentData()
        self.key.setEnabled(backend != "local")
        self.command.setEnabled(backend == "local")
        self.key.setText(get_key(backend) if backend != "local" else "")

    def say(self, text):
        self.log.appendPlainText(text)

    def generate(self):
        image = self.image.text().strip()
        backend = self.backend.currentData()
        if not Path(image).is_file():
            self.say(language.tr("Choose a picture first."))
            return
        key, command = self.key.text().strip(), self.command.text().strip()
        if backend != "local":
            set_key(backend, key)
        else:
            set_command(command)
        self.go.setEnabled(False)
        self.say(language.tr("Generating with {backend}\u2026").format(
            backend=BACKEND_LABELS[backend]))
        self.worker = Worker(image, backend, key, command, self.size.value(),
                             self)
        self.worker.progress.connect(lambda s: self.say(f"  {s}"))
        self.worker.failed.connect(self._failed)
        self.worker.done.connect(self._done)
        self.worker.start()

    def _failed(self, message):
        self.go.setEnabled(True)
        self.say(language.tr("Failed: {message}").format(message=message))

    def _done(self, stl):
        self.go.setEnabled(True)
        self.say(language.tr("Imported {name}").format(
            name=Path(stl).name))
        self.window_._import_mesh_path(stl)


def open_photo3d(window):
    dialog = getattr(window, "_photo3d_dialog", None)
    if dialog is None:
        dialog = window._photo3d_dialog = Photo3DDialog(window)
    dialog.show()
    dialog.raise_()
    return dialog
