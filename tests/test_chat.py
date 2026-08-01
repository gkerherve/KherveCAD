"""Offline tests for the KherveAI chat box (no network calls).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import chat


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    return MainWindow()


def test_provider_table_shape():
    for name, config in chat.AI_PROVIDERS.items():
        assert config["api_url"].startswith("https://")
        assert config["models"], name
        assert config["key_env"]
        assert config["header_format"] in ("Bearer", "x-api-key")


def test_request_formats():
    messages = [{"role": "user", "content": "hi"}]
    claude = chat.build_request("Claude", "m", messages, "sys")
    assert claude["system"] == "sys"
    assert claude["messages"] == messages
    mistral = chat.build_request("Mistral", "m", messages, "sys")
    assert mistral["messages"][0]["role"] == "system"
    ollama = chat.build_request("Ollama (Cloud)", "m", messages, "sys")
    assert ollama["messages"][0]["content"] == "sys"


def test_openai_provider_and_reasoning_models():
    assert "OpenAI" in chat.AI_PROVIDERS
    messages = [{"role": "user", "content": "hi"}]
    std = chat.build_request("OpenAI", "gpt-4o", messages, "sys")
    assert std["temperature"] == chat.TEMPERATURE
    assert "max_tokens" in std
    reason = chat.build_request("OpenAI", "gpt-5.1", messages, "sys")
    assert "max_completion_tokens" in reason
    assert "temperature" not in reason        # rejected by o-series


def test_reply_parsing():
    assert chat.parse_reply("Claude", {"content": [
        {"type": "text", "text": "a"}, {"type": "text", "text": "b"}
    ]}) == "ab"
    assert chat.parse_reply("Mistral", {"choices": [
        {"message": {"content": "hello"}}]}) == "hello"
    assert chat.parse_reply("Ollama (Cloud)", {"message":
                                               {"content": "y"}}) == "y"


def test_fetch_models_parses_and_filters(monkeypatch):
    import io
    import json
    import urllib.request

    payloads = {
        "https://api.openai.com/v1/models": {"data": [
            {"id": "gpt-5.2"}, {"id": "o4-mini"},
            {"id": "text-embedding-3-large"}, {"id": "dall-e-3"}]},
        "https://api.anthropic.com/v1/models": {"data": [
            {"id": "claude-opus-4-8"}, {"id": "claude-haiku-4-5"}]},
        "https://api.mistral.ai/v1/models": {"data": [
            {"id": "mistral-large-latest"}, {"id": "mistral-embed"}]},
        "https://ollama.com/api/tags": {"models": [
            {"name": "gpt-oss:120b-cloud"},
            {"model": "llama3.3:70b-cloud"}]},
    }

    class FakeResp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        return FakeResp(json.dumps(payloads[req.full_url]).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    # OpenAI keeps only chat models
    assert chat.fetch_models("OpenAI", "k") == ["gpt-5.2", "o4-mini"]
    # Mistral drops embedding models
    assert chat.fetch_models("Mistral", "k") == ["mistral-large-latest"]
    # Ollama reads name/model keys
    assert chat.fetch_models("Ollama (Cloud)", "k") == \
        ["gpt-oss:120b-cloud", "llama3.3:70b-cloud"]


def test_get_set_models_round_trip():
    from PyQt5.QtCore import QSettings
    try:
        assert chat.get_models("Claude") == \
            chat.AI_PROVIDERS["Claude"]["models"]   # default when empty
        chat.set_models("Claude", ["claude-x", "claude-y"])
        assert chat.get_models("Claude") == ["claude-x", "claude-y"]
        # a single cached entry still returns as a list
        chat.set_models("Claude", ["claude-solo"])
        assert chat.get_models("Claude") == ["claude-solo"]
    finally:
        QSettings("Kherve", "KherveCAD").remove("chat/models/Claude")


def test_config_dialog_has_model_refresh(window):
    from PyQt5.QtCore import QSettings
    dlg = chat.ChatConfigDialog(window)          # parented: clean teardown
    try:
        assert dlg.refresh_btn.isEnabled()
        dlg.provider.setCurrentText("OpenAI")
        dlg._models_loaded(["gpt-9", "o9-mini"])
        combo = [dlg.model.itemText(i)
                 for i in range(dlg.model.count())]
        assert combo == ["gpt-9", "o9-mini"]
        assert "loaded" in dlg.status.text()
    finally:
        QSettings("Kherve", "KherveCAD").remove("chat/models/OpenAI")


def test_slash_list_and_code(window):
    window.model.add_node("cube")
    panel = window.chat
    panel.handle_command("/list")
    assert "Cube 1" in panel.transcript.toPlainText()
    panel.handle_command("/code")
    assert "cube(" in panel.transcript.toPlainText()


def test_slash_part_inserts_flange(window):
    panel = window.chat
    panel.handle_command("/part cf40 flange")
    names = [n.name for n in window.model.root.children]
    assert any("CF40" in name for name in names)
    code = window.model.to_scad()
    assert "for (a = [0 : 60 : 330])" in code


def test_slash_hide_show(window):
    node = window.model.add_node("sphere")
    panel = window.chat
    panel.handle_command(f"/hide {node.name}")
    assert node.visible is False
    panel.handle_command(f"/show {node.name}")
    assert node.visible is True


def test_conversation_persists_across_restarts(window, monkeypatch,
                                               tmp_path):
    from PyQt5.QtCore import QSettings
    ini = str(tmp_path / "kcad.ini")
    monkeypatch.setattr(chat, "_persist_enabled", lambda: True)
    monkeypatch.setattr(
        chat, "QSettings",
        lambda *a, **k: QSettings(ini, QSettings.IniFormat))

    panel = window.chat
    panel.history = [
        {"role": "user", "content": "make a bracket"},
        {"role": "assistant", "content": "Sure.\n```scad\ncube(5);\n```"}]
    panel.input.remember("make a bracket")
    panel._save_state()

    from khervecad.chat import ChatPanel
    reopened = ChatPanel(window)                # simulate a fresh launch
    try:
        # the model still remembers the conversation
        assert [m["content"] for m in reopened.history] == \
            ["make a bracket", "Sure.\n```scad\ncube(5);\n```"]
        # and it is shown again in the transcript (prose only)
        text = reopened.transcript.toPlainText()
        assert "make a bracket" in text and "Sure." in text
        assert "cube(5)" not in text            # program block hidden
        # Up/Down recalls the previously typed line
        assert reopened.input.recent_history(10) == ["make a bracket"]
    finally:
        reopened.deleteLater()


def test_reply_auto_applies_program_not_shown_as_text(window):
    panel = window.chat
    window.model.add_node("cube")
    reply = ("Here's a sphere for you.\n"
             "```scad\nsphere(r=9, $fn=16);\n```")
    panel._replied(reply)
    # the program was applied straight to the tree...
    types = [n.type for n in window.model.root.children]
    assert types == ["sphere"]
    assert window.model.root.children[0].params["radius"] == 9.0
    transcript = panel.transcript.toPlainText()
    # ...the prose shows, but the raw program does not
    assert "Here's a sphere for you." in transcript
    assert "sphere(r=9" not in transcript
    assert "Built in the document" in transcript


def test_auto_apply_is_undoable(window):
    panel = window.chat
    window.model.add_node("cube")
    window.model.undo_stack.clear()
    panel._replied("```scad\nsphere(r=5, $fn=12);\n```")
    assert window.model.root.children[0].type == "sphere"


def test_history_keeps_long_conversation(window):
    panel = window.chat
    panel.history = []
    for i in range(100):                       # old cap dropped past 30
        panel.history.append({"role": "user", "content": f"m{i}"})
    panel._trim_history()
    assert len(panel.history) == 100           # tiny — nothing dropped
    assert panel.history[0]["content"] == "m0"


def test_history_trims_only_when_over_budget(window):
    panel = window.chat
    panel.history = []
    chunk = "x" * (chat._CHARS_PER_TOKEN * 1000)   # ~1000 tokens each
    count = (chat.HISTORY_TOKEN_BUDGET // 1000) + 50
    for _ in range(count):
        panel.history.append({"role": "user", "content": chunk})
    panel._trim_history()
    total = sum(len(m["content"]) for m in panel.history)
    assert total <= chat.HISTORY_TOKEN_BUDGET * chat._CHARS_PER_TOKEN
    assert len(panel.history) < count          # oldest turns dropped
    assert len(panel.history) >= 2             # but never wiped out


def test_chat_dock_visible_by_default(window):
    assert not window._chat_dock.isHidden()


def _press(widget, key):
    from PyQt5.QtCore import QEvent, Qt
    from PyQt5.QtGui import QKeyEvent
    widget.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier))


def test_input_history_up_down_recall(window):
    from PyQt5.QtCore import Qt
    inp = window.chat.input
    for line in ("first", "second", "third"):
        inp.setText(line)
        inp.remember(line)
    inp.clear()
    _press(inp, Qt.Key_Up)
    assert inp.text() == "third"
    _press(inp, Qt.Key_Up)
    assert inp.text() == "second"
    _press(inp, Qt.Key_Up)
    assert inp.text() == "first"
    _press(inp, Qt.Key_Up)
    assert inp.text() == "first"              # clamped at the oldest
    _press(inp, Qt.Key_Down)
    assert inp.text() == "second"
    _press(inp, Qt.Key_Down)
    assert inp.text() == "third"
    _press(inp, Qt.Key_Down)
    assert inp.text() == ""                    # back to the empty draft


def test_input_history_preserves_draft(window):
    from PyQt5.QtCore import Qt
    inp = window.chat.input
    inp.remember("old message")
    inp.setText("half-typed")                  # a new, unsent draft
    _press(inp, Qt.Key_Up)
    assert inp.text() == "old message"
    _press(inp, Qt.Key_Down)
    assert inp.text() == "half-typed"          # draft restored


def test_missing_key_warns_instead_of_sending(window, monkeypatch):
    panel = window.chat
    monkeypatch.setattr(chat, "get_api_key", lambda p: "")
    panel._ask("hello")
    assert "No API key" in panel.transcript.toPlainText()
    assert panel._worker is None


def _tiny_image():
    from PyQt5.QtGui import QImage
    img = QImage(4, 4, QImage.Format_RGB32)
    img.fill(0xFF3366)
    return img


def test_qimage_encodes_to_png_base64(app):
    import base64
    data = base64.b64decode(chat._qimage_to_png_b64(_tiny_image()))
    assert data[:8] == b"\x89PNG\r\n\x1a\n"       # PNG signature


def test_build_request_attaches_images_per_provider():
    messages = [{"role": "user", "content": "make this"}]
    images = [{"media_type": "image/png", "data": "QUJD"}]

    claude = chat.build_request("Claude", "m", messages, "sys", images)
    content = claude["messages"][-1]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["data"] == "QUJD"
    assert content[-1] == {"type": "text", "text": "make this"}

    openai = chat.build_request("OpenAI", "gpt-4o", messages, "sys",
                                images)
    parts = openai["messages"][-1]["content"]
    assert parts[0]["type"] == "text"
    assert parts[1]["image_url"]["url"] == "data:image/png;base64,QUJD"

    ollama = chat.build_request("Ollama (Cloud)", "m", messages, "sys",
                                images)
    assert ollama["messages"][-1]["images"] == ["QUJD"]

    # the caller's message list must not be mutated, and the no-image
    # path still sends a plain string
    assert messages[0]["content"] == "make this"
    plain = chat.build_request("Claude", "m", messages, "sys")
    assert plain["messages"][0]["content"] == "make this"


def test_attach_image_queues_and_clears(window):
    panel = window.chat
    panel._attach_image(_tiny_image())
    assert len(panel._pending_images) == 1
    assert panel._pending_images[0]["media_type"] == "image/png"
    assert not panel.attach_info.isHidden()            # indicator shown
    assert "1 image" in panel.attach_info.text()
    panel._clear_attachments()
    assert panel._pending_images == []
    assert panel.attach_info.isHidden()


class _FakeSignal:
    def connect(self, *_):
        pass


class _FakeWorker:                       # no QThread — safe to leak
    replied = failed = finished = _FakeSignal()

    def __init__(self, provider, model, key, messages, system,
                 images=None, parent=None):
        _FakeWorker.last_images = images
        _FakeWorker.last_messages = messages

    def start(self):
        pass


def test_send_passes_images_to_worker(window, monkeypatch):
    panel = window.chat
    monkeypatch.setattr(chat, "get_api_key", lambda p: "k")   # has a key
    monkeypatch.setattr(chat, "ChatWorker", _FakeWorker)
    panel._attach_image(_tiny_image())
    panel.input.setText("copy this")
    panel.send()
    assert len(_FakeWorker.last_images) == 1
    assert _FakeWorker.last_images[0]["data"]          # base64 present
    assert "thumb" not in _FakeWorker.last_images[0]    # stripped for wire
    assert panel._pending_images == []                 # queue drained
    # the image rode along with the request, not the persisted history
    assert panel.history[-1]["content"] == "copy this"


# ------------------------------------------- building inside an Object

def _object_window(window, name="Bracket"):
    """A window with the Object tab open on an empty part."""
    comp = window.model.new_component(name, visible=False)
    window.builder.open_component(comp)
    return comp


def test_reply_builds_inside_the_active_object(window):
    """With the Object tab open, the assistant's program becomes that
    part's contents — so the Object tree shows how it is made — instead
    of replacing the whole document."""
    panel = window.chat
    other = window.model.new_component("Untouched")
    comp = _object_window(window)
    panel._replied("A plate with a bore.\n```scad\n"
                   "difference() {\n cube([20, 20, 4]);\n"
                   " cylinder(h=10, r=3, $fn=16);\n}\n```")

    assert [n.type for n in comp.children] == ["difference"]
    bore = comp.children[0]
    assert [n.type for n in bore.children] == ["cube", "cylinder"]
    assert other in window.model.root.children     # document untouched
    assert comp in window.model.root.children
    assert "inside 'Bracket'" in panel.transcript.toPlainText()


def test_reply_in_main_still_builds_the_document(window):
    """Main mode is unchanged — and the note points at the Object tab
    for building the inside of a part."""
    panel = window.chat
    window.model.add_node("cube")
    panel._replied("```scad\nsphere(r=9, $fn=16);\n```")
    assert [n.type for n in window.model.root.children] == ["sphere"]
    transcript = panel.transcript.toPlainText()
    assert "Object tab" in transcript


def test_a_module_plus_call_is_unwrapped_into_the_object(window):
    """The assistant is shown the Object as `module P() {...} P();`
    (what subtree_scad emits) and usually answers in kind. Applied
    literally that would nest the part inside itself every time."""
    panel = window.chat
    comp = _object_window(window, "Spacer")
    panel._replied("```scad\nwall = 3;\nmodule Spacer() {\n"
                   "  cylinder(h=10, r=6, $fn=16);\n}\nSpacer();\n```")
    types = [n.type for n in comp.children]
    assert "component" not in types            # not nested in itself
    assert "cylinder" in types
    assert "assign" in types                   # the variable came too


def test_scope_context_names_the_mode(window):
    """Every message tells the model which mode it is writing for."""
    panel = window.chat
    window.model.add_node("cube")
    main = panel._scope_context()
    assert "MODE: Main" in main
    assert "Object tab" in main

    comp = _object_window(window, "Widget")
    window.model.add_node("sphere", parent=comp)
    scoped = panel._scope_context()
    assert "MODE: Object" in scoped
    assert "'Widget'" in scoped
    assert "sphere" in scoped                  # the part's own program
