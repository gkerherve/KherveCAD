"""Regenerate the User Guide's SolidWorks-style pictures (khervecad/help/
sw_*.png) from the mouse tests: every picture is the real window, part
way through building a part with the mouse.

    python packaging/make_help_mouse_shots.py

It runs the tests with KHERVECAD_SHOTS pointing at a temporary folder
and copies the pictures the guide uses under their guide names.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "khervecad" / "help"

TESTS = ["tests/test_smart_dimension_by_mouse.py",
         "tests/test_open_arcs_by_mouse.py",
         "tests/test_drawings_by_mouse.py",
         "tests/test_more_parts_by_mouse.py",
         "tests/test_options_dialog.py"]

#: guide name -> the test's picture
PICTURES = {
    "sw_window": "s3b-s.png",
    "sw_smart_middle_origin": "sd1-line-middle-to-origin.png",
    "sw_smart_circle": "sd3-origin-to-circle.png",
    "sw_extruded": "sd4-extruded.png",
    "sw_dimension_in_3d": "sd5-diameter-changed-in-3d.png",
    "sw_arcs": "a1-open-arcs.png",
    "sw_line_to_arc": "a4-line-then-arc.png",
    "sw_slot": "a5-slot.png",
    "sw_d_sketch": "a2-d-sketch.png",
    "sw_d_extruded": "a3-d-extruded.png",
    "sw_relations": "s1a-base-sketch.png",
    "sw_fix_origin": "k1a-base-sketch.png",
    "sw_sketch_fillet": "b1a-base-sketch.png",
    "sw_cut_selected": "s5a-hole-sketch.png",
    "sw_pivot_1": "p1a-plate-sketch.png",
    "sw_pivot_2": "p1b-plate-boss.png",
    "sw_pivot_3": "p2a-pivot-hole-smart-dimension.png",
    "sw_pivot_4": "p3b-slot-cut.png",
    "sw_pivot_5": "p3c-r100-arm-sketch.png",
    "sw_pivot_6": "p4b-lug-boss.png",
    "sw_pivot_done": "p6-pivot-guide--55.png",
    "sw_pivot_changed": "p7-pivot-hole-changed-to-20.png",
    "sw_bracket_rounds": "b6c-rounds-r3.png",
    "sw_bracket_done": "b7-bracket--55.png",
    "sw_s_bracket": "s6-s-bracket--55.png",
    "sw_block": "k7-block--55.png",
    "sw_options_general": "options-0-general.png",
    "sw_options_display": "options-1-display.png",
    "sw_options_sketch": "options-2-sketch.png",
    "sw_options_units": "options-7-units.png",
}


def main():
    shots = Path(tempfile.mkdtemp(prefix="khervecad_help_"))
    env = dict(os.environ, KHERVECAD_SHOTS=str(shots),
               QT_QPA_PLATFORM="offscreen")
    subprocess.run([sys.executable, "-m", "pytest", "-q",
                    "-p", "no:cacheprovider"] + TESTS, cwd=ROOT, env=env,
                   check=False)
    missing = []
    for name, src in PICTURES.items():
        path = shots / src
        if path.exists():
            shutil.copyfile(path, OUT / (name + ".png"))
        else:
            missing.append(src)
    print("copied %d pictures" % (len(PICTURES) - len(missing)))
    if missing:
        print("missing:", ", ".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
