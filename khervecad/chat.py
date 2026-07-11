"""KherveAI chat box — the family assistant panel, wired for CAD.

Same design as KherveAI in KherveFitting: multiple AI providers
(Claude / Mistral / Ollama Cloud) behind one chat panel, API keys per
provider (settings dialog or environment variables), and slash
commands that drive the app directly without any network.

The CAD twist: the assistant always sees the current OpenSCAD
program, and when it replies with a fenced ``scad`` code block the
panel offers to apply it — the block is parsed by the .scad importer
straight into the object tree, so the assistant can build and edit
geometry with the full tool set.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import html
import json
import os
import re
import urllib.error
import urllib.request

from PyQt5.QtCore import QSettings, Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                             QFormLayout, QHBoxLayout, QLabel,
                             QLineEdit, QMessageBox, QPushButton,
                             QTextBrowser, QToolButton, QVBoxLayout,
                             QWidget)

from . import icons

_SETTINGS = ("Kherve", "KherveCAD")

#: AI provider options and their models — same structure as the
#: KherveAI family modules.
AI_PROVIDERS = {
    "Claude": {
        "api_url": "https://api.anthropic.com/v1/messages",
        "models": [
            "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20251001",
        ],
        "requires_key": True,
        "key_env": "ANTHROPIC_API_KEY",
        "key_url": "https://console.anthropic.com/settings/keys",
        "header_format": "x-api-key",
    },
    "Mistral": {
        "api_url": "https://api.mistral.ai/v1/chat/completions",
        "models": [
            "mistral-large-latest", "mistral-small-latest",
        ],
        "requires_key": True,
        "key_env": "MISTRAL_API_KEY",
        "key_url": "https://console.mistral.ai/api-keys/",
        "header_format": "Bearer",
    },
    "Ollama (Cloud)": {
        "api_url": "https://ollama.com/api/chat",
        "models": [
            "gpt-oss:120b-cloud", "gpt-oss:20b-cloud",
            "deepseek-v3.1:671b-cloud", "llama3.3:70b-cloud",
        ],
        "requires_key": True,
        "key_env": "OLLAMA_API_KEY",
        "key_url": "https://ollama.com/settings/keys",
        "header_format": "Bearer",
    },
}

MAX_TOKENS = 3000
TEMPERATURE = 0.7

SYSTEM_PROMPT = """\
You are KherveAI, the assistant inside KherveCAD — an easy-to-use CAD
GUI with OpenSCAD as the engine. The document is a tree of objects
that maps 1:1 to an OpenSCAD program.

When the user asks you to create or change geometry, reply with a
short explanation and ONE fenced code block tagged `scad` containing
the COMPLETE OpenSCAD program for the whole document (not a diff).
The app parses that block back into the object tree, so stay inside
this supported subset:
circle(r,$fn), square([w,h]), polygon(points=[...]), text("s",size),
cube([x,y,z],center), sphere(r,$fn), cylinder(h,r1,r2,$fn,center),
translate/rotate/scale/mirror([x,y,z]), linear_extrude(height,twist,
scale,center), rotate_extrude(angle,$fn), union/difference/
intersection/hull/minkowski() {}, offset(r) or offset(delta,chamfer),
for (i = [a:s:b]) or [v1,v2,...], if (cond) {} else {}, variable
assignments (name = value;), import("file.stl"), and the `*` disable
modifier. No modules, functions, use or include.

Units are millimetres. Prefer named variables for key dimensions so
parts stay parametric. The user's current program is provided with
every message — modify it rather than starting over, unless asked.
"""


def get_api_key(provider: str) -> str:
    """Provider key from settings, falling back to the environment."""
    settings = QSettings(*_SETTINGS)
    key = settings.value(f"chat/api_keys/{provider}", "") or ""
    if not key:
        env = AI_PROVIDERS.get(provider, {}).get("key_env")
        key = os.environ.get(env, "") if env else ""
    return key


def set_api_key(provider: str, key: str):
    QSettings(*_SETTINGS).setValue(f"chat/api_keys/{provider}", key)


def build_request(provider: str, model: str, messages, system: str):
    """Request body per provider — same formats as KherveAI."""
    if provider == "Claude":
        return {"model": model, "messages": messages,
                "max_tokens": MAX_TOKENS, "system": system,
                "stream": False}
    if provider == "Ollama (Cloud)":
        return {"model": model, "stream": False,
                "messages": [{"role": "system", "content": system}]
                + messages,
                "options": {"temperature": TEMPERATURE}}
    # Mistral (OpenAI-style)
    return {"model": model,
            "messages": [{"role": "system", "content": system}]
            + messages,
            "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS}


def parse_reply(provider: str, payload: dict) -> str:
    if provider == "Claude":
        return "".join(part.get("text", "")
                       for part in payload.get("content", []))
    if provider == "Ollama (Cloud)":
        return payload.get("message", {}).get("content", "")
    choices = payload.get("choices", [])
    return choices[0]["message"]["content"] if choices else ""


class ChatWorker(QThread):
    """One request to the selected provider, off the GUI thread."""

    replied = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, provider, model, key, messages, system,
                 parent=None):
        super().__init__(parent)
        self.provider, self.model, self.key = provider, model, key
        self.messages, self.system = messages, system

    def run(self):
        config = AI_PROVIDERS[self.provider]
        headers = {"Content-Type": "application/json"}
        if config["header_format"] == "Bearer":
            headers["Authorization"] = f"Bearer {self.key}"
        elif config["header_format"] == "x-api-key":
            headers["x-api-key"] = self.key
            headers["anthropic-version"] = "2023-06-01"
        body = build_request(self.provider, self.model, self.messages,
                             self.system)
        request = urllib.request.Request(
            config["api_url"], data=json.dumps(body).encode(),
            headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=180) as reply:
                payload = json.loads(reply.read().decode())
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode()[:300]
            except Exception:
                pass
            self.failed.emit(f"HTTP {exc.code}: {detail or exc.reason}")
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        text = parse_reply(self.provider, payload)
        if text:
            self.replied.emit(text)
        else:
            self.failed.emit("empty reply from provider")


class ChatConfigDialog(QDialog):
    """Provider / model / API key settings (persisted via QSettings)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KherveAI settings")
        settings = QSettings(*_SETTINGS)

        self.provider = QComboBox()
        self.provider.addItems(list(AI_PROVIDERS))
        self.provider.setCurrentText(
            settings.value("chat/provider", "Claude"))
        self.provider.currentTextChanged.connect(self._provider_changed)

        self.model = QComboBox()
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.key_link = QLabel()
        self.key_link.setOpenExternalLinks(True)

        form = QFormLayout(self)
        form.addRow("Provider", self.provider)
        form.addRow("Model", self.model)
        form.addRow("API key", self.key)
        form.addRow("", self.key_link)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                   | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self._provider_changed(self.provider.currentText())
        saved_model = settings.value("chat/model", "")
        if saved_model:
            index = self.model.findText(saved_model)
            if index >= 0:
                self.model.setCurrentIndex(index)

    def _provider_changed(self, provider):
        config = AI_PROVIDERS[provider]
        self.model.clear()
        self.model.addItems(config["models"])
        self.key.setText(get_api_key(provider))
        self.key.setPlaceholderText(
            f"or set {config['key_env']} in the environment")
        self.key_link.setText(
            f'<a href="{config["key_url"]}">Get a key</a>')

    def _save(self):
        settings = QSettings(*_SETTINGS)
        provider = self.provider.currentText()
        settings.setValue("chat/provider", provider)
        settings.setValue("chat/model", self.model.currentText())
        set_api_key(provider, self.key.text().strip())
        self.accept()


_SCAD_BLOCK_RE = re.compile(r"```(?:scad|openscad)\s*\n(.*?)```",
                            re.DOTALL)


class ChatPanel(QWidget):
    """The KherveAI chat box, docked in the main window."""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window                  # MainWindow
        self.history = []                     # [{"role", "content"}]
        self._blocks = []                     # scad blocks by index
        self._worker = None

        header = QHBoxLayout()
        title = QLabel("<b>KherveAI</b> — CAD assistant")
        settings_btn = QToolButton()
        settings_btn.setIcon(icons.icon("mdi.cog-outline"))
        settings_btn.setToolTip("Provider, model and API key")
        settings_btn.clicked.connect(self.open_settings)
        header.addWidget(QLabel())
        header.itemAt(0).widget().setPixmap(
            icons.icon("mdi.robot-outline").pixmap(20, 20))
        header.addWidget(title)
        header.addStretch()
        header.addWidget(settings_btn)

        self.transcript = QTextBrowser()
        self.transcript.setOpenLinks(False)
        self.transcript.anchorClicked.connect(self._anchor_clicked)

        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "Ask, or /help for commands — e.g. “add a CF40 flange”")
        self.input.returnPressed.connect(self.send)
        self.send_btn = QPushButton(icons.icon("mdi.send-outline"), "")
        self.send_btn.setToolTip("Send")
        self.send_btn.clicked.connect(self.send)

        input_row = QHBoxLayout()
        input_row.addWidget(self.input)
        input_row.addWidget(self.send_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addLayout(header)
        layout.addWidget(self.transcript, 1)
        layout.addLayout(input_row)

        self._append_note(
            "Hi! I can answer questions and build geometry — my "
            "<code>scad</code> replies can be applied straight to the "
            "document. Type <b>/help</b> for app commands.")

    # ------------------------------------------------------- transcript
    def _append(self, role, html_text):
        colors = {"user": "#2176c7", "assistant": "#2e7d4f",
                  "note": "#888888"}
        who = {"user": "You", "assistant": "KherveAI",
               "note": "•"}[role]
        self.transcript.append(
            f'<p><b style="color:{colors[role]}">{who}:</b> '
            f'{html_text}</p>')
        bar = self.transcript.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _append_note(self, html_text):
        self._append("note", html_text)

    def _render_markdownish(self, text):
        """Escape + render fenced code blocks, adding Apply links for
        scad blocks."""
        parts = []
        last = 0
        for match in re.finditer(r"```(\w*)\s*\n(.*?)```", text,
                                 re.DOTALL):
            parts.append(html.escape(text[last:match.start()])
                         .replace("\n", "<br>"))
            lang, code = match.group(1), match.group(2)
            escaped = html.escape(code)
            parts.append(f"<pre style='background:rgba(127,127,127"
                         f",0.15); padding:6px'>{escaped}</pre>")
            if lang.lower() in ("scad", "openscad"):
                self._blocks.append(code)
                index = len(self._blocks) - 1
                parts.append(f'<a href="apply:{index}">&#9654; Apply '
                             f'this program to the document</a><br>')
            last = match.end()
        parts.append(html.escape(text[last:]).replace("\n", "<br>"))
        return "".join(parts)

    def _anchor_clicked(self, url):
        target = url.toString()
        if not target.startswith("apply:"):
            return
        try:
            code = self._blocks[int(target.split(":", 1)[1])]
        except (ValueError, IndexError):
            return
        self.apply_scad(code)

    # ---------------------------------------------------------- applying
    def apply_scad(self, code):
        from .scadparse import parse_scad
        try:
            root, warnings = parse_scad(code)
        except Exception as exc:
            self._append_note(f"Could not parse that program: "
                              f"{html.escape(str(exc))}")
            return
        model = self.window.model
        answer = QMessageBox.question(
            self, "Apply program",
            "Replace the current document with this program?\n"
            "(No = add it alongside the existing objects.)",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if answer == QMessageBox.Cancel:
            return
        if answer == QMessageBox.Yes:
            model.root = root
        else:
            for child in list(root.children):
                root.remove(child)
                model.root.add(child)
        model.structure_changed.emit()
        self.window.view3d.fit()
        note = "Program applied."
        if warnings:
            note += " Skipped: " + "; ".join(warnings[:5])
        self._append_note(html.escape(note))

    # ------------------------------------------------------------ sending
    def send(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self._append("user", html.escape(text))
        if text.startswith("/"):
            self.handle_command(text)
            return
        self._ask(text)

    def _ask(self, text):
        settings = QSettings(*_SETTINGS)
        provider = settings.value("chat/provider", "Claude")
        if provider not in AI_PROVIDERS:
            provider = "Claude"
        config = AI_PROVIDERS[provider]
        model = settings.value("chat/model", config["models"][0])
        if model not in config["models"]:
            model = config["models"][0]
        key = get_api_key(provider)
        if config["requires_key"] and not key:
            self._append_note(
                f"No API key for {provider}. Open settings (gear "
                f"icon) or set {config['key_env']}.")
            return
        self.history.append({"role": "user", "content": text})
        system = (SYSTEM_PROMPT
                  + "\n\nCurrent document program:\n```scad\n"
                  + self.window.model.to_scad() + "\n```")
        self.send_btn.setEnabled(False)
        self._append_note(f"asking {provider} ({model})…")
        self._worker = ChatWorker(provider, model, key,
                                  list(self.history), system, self)
        self._worker.replied.connect(self._replied)
        self._worker.failed.connect(self._failed)
        self._worker.finished.connect(
            lambda: self.send_btn.setEnabled(True))
        self._worker.start()

    def _replied(self, text):
        self.history.append({"role": "assistant", "content": text})
        if len(self.history) > 30:            # keep the context lean
            self.history = self.history[-30:]
        self._append("assistant", self._render_markdownish(text))

    def _failed(self, message):
        self._append_note("Request failed: " + html.escape(message))

    def open_settings(self):
        ChatConfigDialog(self).exec_()

    # ------------------------------------------------------ slash commands
    def handle_command(self, text):
        parts = text[1:].split()
        command, args = (parts[0].lower() if parts else "help"), parts[1:]
        window = self.window
        model = window.model

        if command == "help":
            self._append_note(
                "Commands: <b>/code</b> show the OpenSCAD program · "
                "<b>/list</b> object tree · <b>/render</b> OpenSCAD "
                "render · <b>/fit</b> fit 3D view · <b>/part</b> "
                "&lt;cf16|cf40|cf63|cf100|cf160&gt; "
                "&lt;flange|nipple|tee|cross&gt; · /part turbo · "
                "<b>/hide</b>|<b>/show</b> &lt;name&gt; · "
                "<b>/settings</b> · <b>/clear</b> chat history")
        elif command == "code":
            self._append_note("<pre>" + html.escape(model.to_scad())
                              + "</pre>")
        elif command == "list":
            lines = []
            for node in model.root.walk():
                if node.type == "root":
                    continue
                depth = 0
                probe = node
                while probe.parent is not None:
                    depth += 1
                    probe = probe.parent
                eye = "" if node.visible else " (hidden)"
                lines.append("&nbsp;" * (depth - 1) * 3
                             + html.escape(f"{node.name} [{node.type}]"
                                           + eye))
            self._append_note("<br>".join(lines) or "empty document")
        elif command == "render":
            window._render_now()
            self._append_note("render requested")
        elif command == "fit":
            window.view3d.fit()
            self._append_note("3D view fitted")
        elif command == "clear":
            self.history = []
            self.transcript.clear()
            self._append_note("chat history cleared")
        elif command == "settings":
            self.open_settings()
        elif command == "part":
            self._cmd_part(args)
        elif command in ("hide", "show"):
            name = " ".join(args).lower()
            hits = [n for n in model.root.walk()
                    if name and name in n.name.lower()]
            for node in hits:
                model.set_visible(node, command == "show")
            self._append_note(f"{command}: {len(hits)} object(s)")
        else:
            self._append_note(f"unknown command /{command} — try /help")

    def _cmd_part(self, args):
        from . import library
        model = self.window.model
        if not args:
            self._append_note("usage: /part cf40 tee — or /part turbo")
            return
        if args[0].lower() == "turbo":
            node = library.build_part("turbo", {})
        else:
            size_key = next((k for k in library.CF_SIZES
                             if k.lower().startswith(args[0].lower())),
                            None)
            if size_key is None:
                self._append_note("sizes: " + ", ".join(
                    k.split()[0] for k in library.CF_SIZES))
                return
            kind = args[1].lower() if len(args) > 1 else "flange"
            part_id = {"flange": "cf_flange", "blank": "cf_blank",
                       "nipple": "cf_nipple", "tee": "cf_tee",
                       "cross": "cf_cross"}.get(kind)
            if part_id is None:
                self._append_note(
                    "kinds: flange, blank, nipple, tee, cross")
                return
            dims = dict(library.CF_SIZES[size_key])
            dims["port_length"] = 60.0
            node = library.build_part(part_id, dims)
            node.name = f"{size_key.split()[0]} {node.name}"
        model.root.add(node)
        model.structure_changed.emit()
        self.window.builder.tree.select_nodes([node])
        self.window.view3d.fit()
        self._append_note(html.escape(f"inserted {node.name}"))
