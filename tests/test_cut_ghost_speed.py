"""The red cut preview of a Circular Pattern of cuts (4000 overlapping
triangles) took minutes to paint - `QPainterPath.simplified()` on every
repaint. Exercise 010."""
import math
import time

from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import QApplication

from khervecad import cut_ghost


class _Win:
    def __init__(self, tris):
        self._cut_ghost = tris


def _tris(n):
    out = []
    for i in range(n):
        a = i * 0.37
        cx, cy = 200 + 60 * math.cos(a), 200 + 60 * math.sin(a * 1.3)
        out.append([(cx, cy, 0), (cx + 40, cy + 3 * (i % 7), 0), (cx + 5, cy + 40, 0)])
    return out


def test_painting_thousands_of_overlapping_triangles_is_quick():
    QApplication.instance() or QApplication([])
    img = QImage(400, 400, QImage.Format_ARGB32)
    p = QPainter(img)
    t0 = time.time()
    cut_ghost.paint(_Win(_tris(4000)), p, lambda v: (v[0], v[1]))
    p.end()
    assert time.time() - t0 < 3.0
