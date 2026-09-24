"""language.py: the Edit ▸ Language picker and its translation tables."""

import json
from pathlib import Path

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

from khervecad import language

I18N_DIR = Path(language.__file__).parent / "i18n"


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_languages_lists_every_shipped_table_plus_english():
    assert language.LANGUAGES["en"] == "English"
    for code in language.LANGUAGES:
        if code == "en":
            continue
        assert (I18N_DIR / f"{code}.json").exists(), code


def test_every_table_is_a_flat_string_to_string_dict():
    for code in language.LANGUAGES:
        if code == "en":
            continue
        table = json.loads((I18N_DIR / f"{code}.json").read_text(
            encoding="utf-8"))
        assert table, code
        for key, value in table.items():
            assert isinstance(key, str) and isinstance(value, str), code
            assert key and value, code


def test_set_and_current_language_round_trip():
    QSettings("Kherve", "KherveCAD").remove("language")
    assert language.current_language() == "en"
    language.set_language("fr")
    try:
        assert language.current_language() == "fr"
    finally:
        QSettings("Kherve", "KherveCAD").remove("language")


def test_set_language_refuses_an_unknown_code():
    with pytest.raises(ValueError):
        language.set_language("xx")


def test_dict_translator_distinguishes_missing_from_empty():
    # a missing key must come back as a null QString (translate()
    # returns None -> PyQt gives a null QString), never "" — a Qt
    # internal template (QUndoStack's "%1 %2") reads a non-null empty
    # string as "translated to nothing" and its own .arg() calls then
    # warn about missing arguments.
    tr = language.DictTranslator({"&File": "&Fichier"})
    assert tr.translate("MainWindow", "&File") == "&Fichier"
    assert tr.translate("MainWindow", "&Unknown") is None


def test_install_is_a_no_op_for_english(app):
    language.install(app, "en")
    # nothing raised, and no translator left needing removal later
    assert language._active is None
