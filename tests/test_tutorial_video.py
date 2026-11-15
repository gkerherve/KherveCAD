"""The tutorial-video recorder films a click with sound and captions.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""
import os
import subprocess

import pytest
from PyQt5.QtWidgets import QApplication, QPushButton

from khervecad import tutorial_video as tv

_APP = QApplication.instance() or QApplication([])


@pytest.mark.skipif(tv.ffmpeg() is None, reason="no ffmpeg")
def test_a_click_is_filmed_with_voice_and_captions(tmp_path):
    w = QPushButton("Press me")
    w.resize(320, 200)
    hits = []
    w.clicked.connect(lambda: hits.append(1))
    w.show()
    out = str(tmp_path / "clip.mp4")
    rec = tv.Recorder(w, out, fps=10)
    rec.say("Press the button.")
    rec.click(w)
    info = rec.finish()
    assert hits == [1]
    assert os.path.getsize(out) > 1000 and info["lines"] == 1
    assert "Press the button." in open(str(tmp_path / "clip.srt")).read()
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "stream=codec_type", "-of", "csv=p=0", out],
                           capture_output=True, text=True).stdout
    assert "video" in probe and "audio" in probe
