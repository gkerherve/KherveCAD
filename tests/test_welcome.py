"""The Welcome window (SolidWorks-style): New Part / Assembly / Drawing,
Open, Recent Documents, Folders and Resources.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import welcome
from khervecad.mainwindow import MainWindow


@pytest.fixture
def win(tmp_path):
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w._set_recent_files([])
    yield w
    w._set_recent_files([])
    d = getattr(w, "_welcome", None)
    if d is not None:
        d.close()
    w._dirty = False
    w.close()


def test_file_new_opens_the_welcome_window(win):
    dlg = win.new_dialog()
    assert dlg.isVisible()
    assert dlg is win.new_dialog()                 # one per window
    for name in ("btn_part", "btn_assembly", "btn_drawing",
                 "btn_advanced", "btn_open"):
        assert getattr(dlg, name).isVisibleTo(dlg)
    assert [b.text() for b in dlg._tabs] == list(welcome.TABS)


def test_new_part_opens_an_object(win):
    dlg = win.new_dialog()
    dlg.btn_part.click()
    assert not dlg.isVisible()
    assert win.builder.currentWidget() is win.builder.object_tab
    assert win.builder.object_tab.active_component().name == "Part1"


def test_new_assembly_is_the_main_tab(win):
    win.builder.open_component(win.model.new_component("X", visible=False))
    win._dirty = False          # a dirty one would ask, modally
    win.new_dialog().btn_assembly.click()
    assert win.builder.currentWidget() is win.builder._main_page
    assert not win.model.root.children


def test_new_drawing_opens_the_blueprint(win):
    win.new_dialog().btn_drawing.click()
    assert win._blueprint.isVisible()
    win._blueprint.close()


def test_advanced_sets_the_unit(win):
    assert welcome.new_document(win, "assembly", unit="cm")
    assert win.model.unit == "cm"
    win.model.set_unit("mm")


def test_unknown_kind_is_refused(win):
    with pytest.raises(ValueError):
        welcome.new_document(win, "sketchbook")


def test_recent_cards_and_folders(win, tmp_path):
    a, b = tmp_path / "a.kcad", tmp_path / "sub" / "b.kcad"
    b.parent.mkdir()
    from khervecad import document
    document.save_kcad(win.model, str(a))
    document.save_kcad(win.model, str(b))
    win._set_recent_files([str(b), str(a), str(tmp_path / "gone.kcad")])
    dlg = win.new_dialog()
    assert [c.property("path") for c in dlg.cards] == \
        [str(b), str(a), str(tmp_path / "gone.kcad")]
    assert not dlg.cards[2].isEnabled()            # a missing file
    assert len(dlg.folder_buttons) == 2
    assert dlg.recent_list.count() == 3
    dlg._pending = []                              # no pictures here
    dlg.cards[1].click()                           # opens a.kcad
    assert win._path == str(a)
    assert not dlg.isVisible()


def test_show_at_startup_setting(win):
    welcome.set_show_at_start(False)
    assert welcome.show_at_startup(win) is None
    welcome.set_show_at_start(True)
    dlg = welcome.show_at_startup(win)
    assert dlg is not None and dlg.show_check.isChecked()


def test_learn_lists_the_tutorials(win):
    dlg = win.new_dialog()
    assert dlg.learn_list.count() >= 10
    dlg.next_tip()
    assert dlg.tip_label.text() == welcome.TIPS[1]


def test_card_pictures_are_drawn_from_the_file(win, tmp_path, monkeypatch):
    from khervecad import document, welcome_thumb
    monkeypatch.setattr(welcome_thumb, "folder",
                        lambda: str(tmp_path / "thumbs"))
    win.model.add_node("cube")
    p = tmp_path / "t.kcad"
    document.save_kcad(win.model, str(p))
    assert welcome.card_pixmap(str(p)) is None
    assert welcome_thumb.render_file(str(p))
    pix = welcome.card_pixmap(str(p))
    assert pix is not None and not pix.isNull()
    img = pix.toImage()
    # the part is in the picture: not every pixel is the background
    colours = {img.pixel(x, y) for x in range(0, img.width(), 9)
               for y in range(0, img.height(), 9)}
    assert len(colours) > 4
    # an empty document is refused once, and remembered
    q = tmp_path / "empty.kcad"
    win.model.clear()
    document.save_kcad(win.model, str(q))
    assert not welcome_thumb.render_file(str(q))
    assert welcome_thumb.refused(str(q))


def test_cards_fill_in_their_pictures(win, tmp_path, monkeypatch):
    import time
    from khervecad import document, welcome_thumb
    monkeypatch.setattr(welcome_thumb, "folder",
                        lambda: str(tmp_path / "thumbs"))
    win.model.add_node("sphere")
    p = tmp_path / "ball.kcad"
    document.save_kcad(win.model, str(p))
    win._set_recent_files([str(p)])
    dlg = win.new_dialog()
    card = dlg.cards[0]
    assert not card.has_picture()
    for _ in range(60):                      # a timer chain, a turn each
        QApplication.processEvents()
        time.sleep(0.05)
        if card.has_picture():
            break
    assert card.has_picture()


def test_icons_are_painted_for_every_welcome_key():
    from khervecad import icons_welcome
    for key in icons_welcome.KEYS:
        ico = icons_welcome.get(key)
        assert ico is not None and not ico.isNull(), key
        assert not ico.pixmap(48, 48).toImage().isNull()


def test_kind_of_reads_the_file(tmp_path):
    import json
    from khervecad import icons_welcome
    one = tmp_path / "a.kcad"
    one.write_text(json.dumps({"tree": {"children": [
        {"type": "component"}]}}))
    two = tmp_path / "b.kcad"
    two.write_text(json.dumps({"tree": {"children": [
        {"type": "component"}, {"type": "component"}]}}))
    assert icons_welcome.kind_of(str(one)) == "part"
    assert icons_welcome.kind_of(str(two)) == "assembly"
    assert icons_welcome.kind_of(str(tmp_path / "nope")) == "part"
