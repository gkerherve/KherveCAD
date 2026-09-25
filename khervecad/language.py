"""Application language: Edit ▸ Language, persisted via QSettings.

`khervecad/i18n/<code>.json` is a flat {English source text: translated
text} dict. `DictTranslator` answers Qt's translation lookups
(`self.tr("...")`) from that dict instead of a compiled `.qm` — this
build environment ships no `lupdate`/`lrelease`, and a flat table is
all the app needs (no plural forms, one language active at a time).
A key missing from the table, or a language with no file yet, falls
back to the English source text unchanged.

Switching language takes effect on the next launch: widgets built
this session already hold their (untranslated) text, and KherveCAD
does not implement Qt's `LanguageChange` re-translation across every
window. `set_language()` says so when it returns.
"""

import json
from pathlib import Path

from PyQt5.QtCore import QCoreApplication, QSettings, QTranslator

#: language code -> its own name, as shown in the picker itself.
LANGUAGES = {
    "en": "English",
    "zh": "中文",
    "fr": "Français",
    "es": "Español",
}

_DATA_DIR = Path(__file__).parent / "i18n"
_SETTINGS = ("Kherve", "KherveCAD")


def current_language() -> str:
    code = str(QSettings(*_SETTINGS).value("language", "en"))
    return code if code in LANGUAGES else "en"


def set_language(code: str):
    if code not in LANGUAGES:
        raise ValueError(code)
    QSettings(*_SETTINGS).setValue("language", code)


class DictTranslator(QTranslator):
    """A `QTranslator` backed by a flat JSON {source: translation} dict."""

    def __init__(self, table: dict):
        super().__init__()
        self._table = table

    def translate(self, context, source_text, disambiguation=None, n=-1):
        # None -> a null QString, which is how Qt itself tells "no
        # translation" apart from "translated to the empty string"; a
        # plain "" is NOT null and was swallowing Qt's own internal
        # template strings (QUndoStack's "%1 %2" among them), so its
        # .arg() calls warned about missing arguments and produced
        # blank menu text once any DictTranslator was installed.
        return self._table.get(source_text, None)


def _load(code: str) -> dict:
    path = _DATA_DIR / f"{code}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


#: the installed translator, so a later `install()` can remove it first.
_active = None


def install(app: QCoreApplication, code: str = None):
    """Install the translator for *code* (default: the saved language)."""
    global _active
    if _active is not None:
        app.removeTranslator(_active)
        _active = None
    code = code or current_language()
    if code == "en":
        return
    table = _load(code)
    if not table:
        return
    _active = DictTranslator(table)
    app.installTranslator(_active)


def tr(text: str) -> str:
    """Translate *text* against the active language's table directly.

    For plain functions and data tables (tooltips.py's TIPS, a dialog
    module with no QObject of its own) that cannot call `self.tr()`.
    Looks the string up in the installed `DictTranslator`'s table with
    no dependency on a live `QApplication` — safe to call even from the
    MCP subprocess, which never builds one. Falls back to *text*
    unchanged when there is no active translator or no entry for it.
    """
    if _active is None:
        return text
    found = _active._table.get(text)
    return text if found is None else found
