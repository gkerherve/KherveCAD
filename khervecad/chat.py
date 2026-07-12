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
            "claude-opus-4-5",
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
        ],
        "requires_key": True,
        "key_env": "ANTHROPIC_API_KEY",
        "key_url": "https://console.anthropic.com/settings/keys",
        "header_format": "x-api-key",
    },
    "OpenAI": {
        "api_url": "https://api.openai.com/v1/chat/completions",
        "models": [
            "gpt-5.1", "gpt-5", "gpt-4.1", "gpt-4o", "gpt-4o-mini",
            "o3", "o4-mini",
        ],
        "requires_key": True,
        "key_env": "OPENAI_API_KEY",
        "key_url": "https://platform.openai.com/api-keys",
        "header_format": "Bearer",
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

#: Upper bound on the reply length we ask the model for. Set high so
#: long programs and explanations are never truncated; providers clamp
#: it to whatever the chosen model actually supports.
MAX_TOKENS = 8000
TEMPERATURE = 0.7

#: Rough English chars-per-token, used only to keep the running
#: conversation inside a model's context window.
_CHARS_PER_TOKEN = 4
#: Keep as much of the conversation as fits in this many tokens of
#: history, so the assistant remembers the whole session — only the
#: oldest turns are dropped, and only once it would overflow a large
#: model's context window. (The true ceiling is whatever context window
#: the chosen model supports — e.g. ~200k tokens for Claude — so this
#: is generous headroom rather than a hard limit you will normally hit.)
HISTORY_TOKEN_BUDGET = 400000

#: The conversation is also saved between runs so the assistant picks up
#: where you left off. Persist at most this many characters (most recent
#: first) to keep the settings store small.
_PERSIST_CHARS = 200000


def _persist_enabled() -> bool:
    """Skip disk persistence under the offscreen test platform so the
    suite never reads or writes the user's real chat history."""
    return os.environ.get("QT_QPA_PLATFORM", "") != "offscreen"

SYSTEM_PROMPT = """\
You are the assistant inside KherveCAD — an easy-to-use CAD GUI with
OpenSCAD as the engine. The document is a tree of objects that maps
1:1 to an OpenSCAD program, editable in the Objects tree, the Code tab,
or by you.

When the user asks you to create or change geometry, reply with a
short explanation and ONE fenced code block tagged `scad` containing
the COMPLETE OpenSCAD program for the whole document (not a diff). The
app parses that block back into the object tree, so stay inside the
supported subset:
- shapes: circle(r/d,$fn,angle), square([w,h],center),
  polygon(points=[...]), text("s",size); cube([x,y,z]/size,center),
  sphere(r/d,$fn), cylinder(h,r1/r2 or d,$fn,center).
- transforms: translate/rotate/scale/mirror([x,y,z]) (rotate/scale
  also take a scalar), linear_extrude(height,twist,scale,center),
  rotate_extrude(angle,$fn), offset(r) / offset(delta,chamfer),
  projection(cut) (a 2D result — renders via OpenSCAD only).
- booleans: union/difference/intersection/hull/minkowski() {}.
- control: for (i = [a:s:b] | [v1,v2,...] | listvar), if (cond) {}
  else {}, name = value; assignments, `*` to disable.
- expressions: numbers, +-*/%^, comparisons, && ||, ternary c ? a : b,
  vectors [a,b,c] with v.x/.y/.z and v[i], ranges [a:s:b], and
  functions sin cos tan asin acos atan atan2 sqrt abs pow exp ln log
  min max floor ceil round sign norm len (trig in degrees).
- user module(){} definitions with parameters ARE supported — the app
  inlines each call; nested modules too. import("file.stl") works.
Avoid: function definitions, children()/$children, use/include,
recursion, and list comprehensions [for ...]. If the user needs those,
tell them to open the file directly (KherveCAD keeps it as a raw
OpenSCAD block that the engine renders).

Units are millimetres. Prefer named variables (and vectors like
size=[x,y,z]) for key dimensions so parts stay parametric. The user's
current program is provided with every message — modify it rather than
starting over, unless asked.

App features you can explain if asked: the Objects / Masters /
Variables / Code tabs (Masters holds reusable definitions placed as
Linked copies); the Examples menu (Learn tutorials, Mechanical parts,
Showcase); the Library menu of parametric parts (CF/KF flanges,
fasteners, chemistry & room items); the Git menu (Commit Ctrl+K, Push,
Pull) for the current .kcad's folder; F5 to render with OpenSCAD;
opening/importing .kcad/.scad/.stl via File > Open or drag-and-drop;
and File > New Window for a second document.
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


def get_models(provider: str) -> list:
    """The model list for *provider*: a previously refreshed list from
    settings, else the built-in defaults."""
    cached = QSettings(*_SETTINGS).value(f"chat/models/{provider}", None)
    if isinstance(cached, str):                # a lone entry round-trips
        cached = [cached]                      # as a bare string
    if cached:
        return [str(m) for m in cached]
    return list(AI_PROVIDERS.get(provider, {}).get("models", []))


def set_models(provider: str, models: list):
    QSettings(*_SETTINGS).setValue(f"chat/models/{provider}",
                                   list(models))


#: Where each provider lists its available models (GET, same auth as
#: the chat endpoint).
_MODELS_URLS = {
    "Claude": "https://api.anthropic.com/v1/models",
    "OpenAI": "https://api.openai.com/v1/models",
    "Mistral": "https://api.mistral.ai/v1/models",
    "Ollama (Cloud)": "https://ollama.com/api/tags",
}


def _keep_model(provider: str, model_id: str) -> bool:
    """Drop non-chat models the list endpoints also return."""
    lid = model_id.lower()
    if provider == "OpenAI":
        return lid.startswith(("gpt", "o1", "o3", "o4", "chatgpt"))
    if provider == "Mistral":
        return not any(bad in lid for bad in
                       ("embed", "ocr", "moderation"))
    return True


def fetch_models(provider: str, key: str) -> list:
    """Live model ids from the provider's list endpoint."""
    url = _MODELS_URLS.get(provider)
    if not url:
        return []
    config = AI_PROVIDERS[provider]
    headers = {}
    if config["header_format"] == "Bearer":
        headers["Authorization"] = f"Bearer {key}"
    elif config["header_format"] == "x-api-key":
        headers["x-api-key"] = key
        headers["anthropic-version"] = "2023-06-01"
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=30) as reply:
        payload = json.loads(reply.read().decode())
    if provider == "Ollama (Cloud)":
        items = payload.get("models", [])
        ids = [m.get("name") or m.get("model") for m in items]
    else:
        items = payload.get("data", [])
        ids = [m.get("id") for m in items]
    return [i for i in ids if i and _keep_model(provider, i)]


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
    # OpenAI / Mistral (OpenAI-style chat/completions)
    body = {"model": model,
            "messages": [{"role": "system", "content": system}]
            + messages}
    # OpenAI reasoning models (o-series, gpt-5) use a different token
    # field and reject a custom temperature
    if provider == "OpenAI" and model.startswith(("o1", "o3", "o4",
                                                  "gpt-5")):
        body["max_completion_tokens"] = MAX_TOKENS
    else:
        body["temperature"] = TEMPERATURE
        body["max_tokens"] = MAX_TOKENS
    return body


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


class ModelListWorker(QThread):
    """Fetch a provider's model list off the GUI thread."""

    loaded = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, provider, key, parent=None):
        super().__init__(parent)
        self.provider, self.key = provider, key

    def run(self):
        try:
            models = fetch_models(self.provider, self.key)
        except urllib.error.HTTPError as exc:
            self.failed.emit(f"HTTP {exc.code}: {exc.reason}")
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        if models:
            self.loaded.emit(models)
        else:
            self.failed.emit("no models returned")


class ChatConfigDialog(QDialog):
    """Provider / model / API key settings (persisted via QSettings)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assistant settings")
        self._mworker = None
        settings = QSettings(*_SETTINGS)

        self.provider = QComboBox()
        self.provider.addItems(list(AI_PROVIDERS))
        self.provider.setCurrentText(
            settings.value("chat/provider", "Claude"))
        self.provider.currentTextChanged.connect(self._provider_changed)

        self.model = QComboBox()
        self.refresh_btn = QToolButton()
        self.refresh_btn.setIcon(icons.icon("mdi.refresh"))
        self.refresh_btn.setToolTip(
            "Refresh — fetch the latest models from the provider")
        self.refresh_btn.clicked.connect(self._refresh_models)
        model_row = QHBoxLayout()
        model_row.setContentsMargins(0, 0, 0, 0)
        model_row.addWidget(self.model, 1)
        model_row.addWidget(self.refresh_btn)

        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.key_link = QLabel()
        self.key_link.setOpenExternalLinks(True)
        self.status = QLabel()
        self.status.setStyleSheet("color:#888888")

        form = QFormLayout(self)
        form.addRow("Provider", self.provider)
        form.addRow("Model", model_row)
        form.addRow("API key", self.key)
        form.addRow("", self.key_link)
        form.addRow("", self.status)
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
        self.model.addItems(get_models(provider))
        self.key.setText(get_api_key(provider))
        self.key.setPlaceholderText(
            f"or set {config['key_env']} in the environment")
        self.key_link.setText(
            f'<a href="{config["key_url"]}">Get a key</a>')
        self.status.clear()

    def _refresh_models(self):
        provider = self.provider.currentText()
        key = self.key.text().strip() or get_api_key(provider)
        if AI_PROVIDERS[provider]["requires_key"] and not key:
            self.status.setText("Enter the API key first, then refresh.")
            return
        self.refresh_btn.setEnabled(False)
        self.status.setText(f"Fetching {provider} models…")
        self._mworker = ModelListWorker(provider, key, self)
        self._mworker.loaded.connect(self._models_loaded)
        self._mworker.failed.connect(self._models_failed)
        self._mworker.finished.connect(
            lambda: self.refresh_btn.setEnabled(True))
        self._mworker.start()

    def _models_loaded(self, models):
        provider = self.provider.currentText()
        set_models(provider, models)
        current = self.model.currentText()
        self.model.clear()
        self.model.addItems(models)
        index = self.model.findText(current)
        if index >= 0:
            self.model.setCurrentIndex(index)
        self.status.setText(f"{len(models)} models loaded.")

    def _models_failed(self, message):
        self.status.setText("Couldn't fetch models: " + message)

    def _save(self):
        settings = QSettings(*_SETTINGS)
        provider = self.provider.currentText()
        settings.setValue("chat/provider", provider)
        settings.setValue("chat/model", self.model.currentText())
        set_api_key(provider, self.key.text().strip())
        self.accept()


_SCAD_BLOCK_RE = re.compile(r"```(?:scad|openscad)\s*\n(.*?)```",
                            re.DOTALL)


class ChatInput(QLineEdit):
    """Message box that recalls previously sent lines with Up/Down,
    shell-style — the same feel as KherveAI elsewhere in the family."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history = []
        self._index = 0                       # len == "composing new"
        self._draft = ""                      # text held while browsing

    def remember(self, text):
        """Record a just-sent line and reset the browse cursor."""
        if text and (not self._history or self._history[-1] != text):
            self._history.append(text)
        self._index = len(self._history)
        self._draft = ""

    def load_history(self, lines):
        """Seed the Up/Down history from a previous run."""
        self._history = list(lines)
        self._index = len(self._history)
        self._draft = ""

    def recent_history(self, limit):
        """The most recent typed lines, for persistence."""
        return self._history[-limit:]

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            self._browse(-1)
        elif event.key() == Qt.Key_Down:
            self._browse(1)
        else:
            super().keyPressEvent(event)

    def _browse(self, step):
        if not self._history:
            return
        if self._index == len(self._history) and step < 0:
            self._draft = self.text()         # keep the unsent draft
        new = max(0, min(self._index + step, len(self._history)))
        self._index = new
        self.setText(self._draft if new == len(self._history)
                     else self._history[new])
        self.end(False)                       # cursor to end of line


class ChatPanel(QWidget):
    """The KherveAI chat box, docked in the main window."""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window                  # MainWindow
        self.history = []                     # [{"role", "content"}]
        self._blocks = []                     # scad blocks by index
        self._worker = None

        header = QHBoxLayout()
        title = QLabel("<b>Assistant</b> — CAD helper")
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

        self.input = ChatInput()
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

        if _persist_enabled():
            self._load_state()
        else:
            self._welcome()

    # -------------------------------------------------------- persistence
    def _welcome(self):
        self._append_note(
            "Hi! I can answer questions and build geometry — when I "
            "design a part it is applied straight to the document "
            "(Ctrl+Z to undo). Type <b>/help</b> for app commands.")

    def _load_state(self):
        """Restore the previous conversation and the Up/Down input
        history saved on the last run."""
        settings = QSettings(*_SETTINGS)
        try:
            saved = json.loads(settings.value("chat/history", "") or "[]")
        except Exception:
            saved = []
        try:
            typed = json.loads(
                settings.value("chat/input_history", "") or "[]")
        except Exception:
            typed = []
        self.input.load_history([str(t) for t in typed if t])
        self.history = [m for m in saved if isinstance(m, dict)
                        and m.get("role") and "content" in m]
        if self.history:
            self._replay_transcript()
            self._append_note(
                "↺ Restored your previous conversation — I still "
                "remember it. Type <b>/clear</b> to start fresh.")
        else:
            self._welcome()

    def _save_state(self):
        if not _persist_enabled():
            return
        # keep the most recent messages within the persistence budget
        kept, total = [], 0
        for message in reversed(self.history):
            total += len(message.get("content", ""))
            if total > _PERSIST_CHARS and kept:
                break
            kept.insert(0, message)
        settings = QSettings(*_SETTINGS)
        settings.setValue("chat/history", json.dumps(kept))
        settings.setValue("chat/input_history",
                          json.dumps(self.input.recent_history(200)))

    def _replay_transcript(self):
        """Redraw the restored conversation in the transcript."""
        for message in self.history:
            if message["role"] == "user":
                self._append("user", html.escape(message["content"]))
            elif message["role"] == "assistant":
                prose = _SCAD_BLOCK_RE.sub("", message["content"]).strip()
                self._append("assistant", html.escape(
                    prose or message["content"]).replace("\n", "<br>"))

    # ------------------------------------------------------- transcript
    def _append(self, role, html_text):
        colors = {"user": "#2176c7", "assistant": "#2e7d4f",
                  "note": "#888888"}
        who = {"user": "You", "assistant": "Assistant",
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
        model.group_variables()
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
        self.input.remember(text)             # recall with Up/Down later
        self.input.clear()
        self._append("user", html.escape(text))
        if text.startswith("/"):
            self.handle_command(text)
        else:
            self._ask(text)
        self._save_state()                    # remember across restarts

    def _ask(self, text):
        settings = QSettings(*_SETTINGS)
        provider = settings.value("chat/provider", "Claude")
        if provider not in AI_PROVIDERS:
            provider = "Claude"
        config = AI_PROVIDERS[provider]
        models = get_models(provider)
        model = settings.value("chat/model", models[0])
        if model not in models:
            model = models[0]
        key = get_api_key(provider)
        if config["requires_key"] and not key:
            self._append_note(
                f"No API key for {provider}. Open settings (gear "
                f"icon) or set {config['key_env']}.")
            return
        self.history.append({"role": "user", "content": text})
        self._trim_history()
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

    def _trim_history(self):
        """Keep the whole conversation, dropping only the oldest turns
        once it would overflow the context budget — so the assistant
        remembers as much of the session as safely fits."""
        budget = HISTORY_TOKEN_BUDGET * _CHARS_PER_TOKEN     # in chars
        total = sum(len(m["content"]) for m in self.history)
        while len(self.history) > 2 and total > budget:
            total -= len(self.history.pop(0)["content"])

    def _replied(self, text):
        self.history.append({"role": "assistant", "content": text})
        self._trim_history()
        self._save_state()                    # remember across restarts
        blocks = _SCAD_BLOCK_RE.findall(text)
        # show only the explanation, never the raw program — the code
        # is applied to the document automatically
        prose = _SCAD_BLOCK_RE.sub("", text).strip()
        if prose:
            self._append("assistant",
                         html.escape(prose).replace("\n", "<br>"))
        elif not blocks:
            self._append("assistant",
                         html.escape(text).replace("\n", "<br>"))
        if blocks:
            self._auto_apply(blocks[-1])

    def _auto_apply(self, code):
        """Parse the assistant's program straight into the object tree
        (undoable with Ctrl+Z) instead of printing it in the chat."""
        from .scadparse import parse_scad
        try:
            root, warnings = parse_scad(code)
        except Exception as exc:
            self._append_note("Couldn't apply that program: "
                              + html.escape(str(exc)))
            return
        count = sum(1 for n in root.walk() if n.type != "root")
        self.window.model.root = root
        self.window.model.group_variables()
        self.window.model.structure_changed.emit()
        self.window.view3d.fit()
        note = (f"✓ Built in the document — {count} object"
                f"{'s' if count != 1 else ''}. Press Ctrl+Z to undo.")
        if warnings:
            note += " Skipped: " + "; ".join(warnings[:4])
        self._append_note(html.escape(note))

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
            self._append_note("usage: /part cf40 tee|gate|angle · "
                              "/part m6 bolt · /part turbo dn100")
            return
        if args[0].lower() == "turbo":
            wanted = args[1].lower() if len(args) > 1 else "dn100"
            size = next((k for k in library.TURBO_SIZES
                         if k.lower().startswith(wanted)),
                        "DN100 CF (~300 l/s)")
            node = library.build_part("turbo", {"_size": size})
            node.name = f"Turbo {size.split(' ')[0]}"
        elif args[0].upper() in library.BOLT_SIZES:
            dims = dict(library.BOLT_SIZES[args[0].upper()])
            kind = args[1].lower() if len(args) > 1 else "bolt"
            part_id = {"bolt": "bolt_hex", "screw": "bolt_socket",
                       "nut": "nut_hex"}.get(kind)
            if part_id is None:
                self._append_note("kinds: bolt, screw, nut")
                return
            node = library.build_part(part_id, dims)
            node.name = f"{args[0].upper()} {node.name}"
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
                       "cross": "cf_cross", "gate": "valve_gate",
                       "angle": "valve_angle",
                       "valve": "valve_angle"}.get(kind)
            if part_id is None:
                self._append_note(
                    "kinds: flange, blank, nipple, tee, cross, "
                    "gate, angle")
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
