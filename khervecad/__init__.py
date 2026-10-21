"""KherveCAD — easy-to-use CAD GUI with OpenSCAD as the engine.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

APP_NAME = "KherveCAD"

# drop-down rows in the theme's colours, set when each combo is made
# (before any module imports QComboBox) — combo_fix.py
from . import combo_fix as _combo_fix  # noqa: E402
_combo_fix.install()

from ._version import get_version  # noqa: E402

__version__ = get_version()
