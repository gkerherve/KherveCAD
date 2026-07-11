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


def test_reply_parsing():
    assert chat.parse_reply("Claude", {"content": [
        {"type": "text", "text": "a"}, {"type": "text", "text": "b"}
    ]}) == "ab"
    assert chat.parse_reply("Mistral", {"choices": [
        {"message": {"content": "hello"}}]}) == "hello"
    assert chat.parse_reply("Ollama (Cloud)", {"message":
                                               {"content": "y"}}) == "y"


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


def test_scad_block_apply_replaces_document(window, monkeypatch):
    panel = window.chat
    window.model.add_node("cube")
    from PyQt5.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    panel.apply_scad("sphere(r=9, $fn=16);")
    types = [n.type for n in window.model.root.children]
    assert types == ["sphere"]
    assert window.model.root.children[0].params["radius"] == 9.0


def test_scad_block_detected_and_linked(window):
    panel = window.chat
    text = "Here you go:\n```scad\ncube(5);\n```\nDone."
    rendered = panel._render_markdownish(text)
    assert "apply:0" in rendered
    assert panel._blocks == ["cube(5);\n"]


def test_missing_key_warns_instead_of_sending(window, monkeypatch):
    panel = window.chat
    monkeypatch.setattr(chat, "get_api_key", lambda p: "")
    panel._ask("hello")
    assert "No API key" in panel.transcript.toPlainText()
    assert panel._worker is None
