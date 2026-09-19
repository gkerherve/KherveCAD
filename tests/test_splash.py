"""The start-up picture (splash.py) and its wiring into app.main()."""

import inspect

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import __version__, app, splash


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_splash_shows_the_version_and_fills_step_by_step(qapp):
    screen = splash.Splash()
    assert screen.pixmap().width() >= splash.WIDTH
    assert screen.fraction == 0.0
    screen.step("Building the window")
    assert 0 < screen.fraction < 1
    screen.step("Ready")
    assert screen.fraction == 1.0
    screen.step("Something else")             # any text keeps the bar
    assert screen.fraction == 1.0 and screen.step_text == "Something else"
    image = screen.grab().toImage()
    assert not image.isNull()
    screen.close()
    assert __version__


def test_main_shows_the_splash_before_the_heavy_import():
    source = inspect.getsource(app.main)
    assert source.index("Splash()") < source.index("from .mainwindow")
    assert "splash.finish(win)" in source
