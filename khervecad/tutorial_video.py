"""Tutorial videos made by KherveCAD itself (2026-11-15, the user: "is
there a way to create videos on how to build each part, so that I don't
need to create the video on YouTube? ... it needs to show the mouse
moving and everything").

A `Recorder` drives the real window with real mouse and key events (the
same events the ``*_by_mouse`` tests send) and films it: every frame is
the window grabbed (plus any dialog over it), a drawn mouse pointer that
GLIDES to each target, a ripple where it clicks, an outline round the
button it is going for, and the narration as a caption bar. ``say``
speaks a line: the macOS voice (``say``) records it now and it is laid
on the sound track at that moment while the mouse goes on working; the
next line waits for it to end. ``finish`` writes the MP4 (ffmpeg), an
.srt of the captions and a .txt narration script, so the same film can
be voiced again by any other text-to-speech.

The video's clock is the FRAME count, not the wall clock: grabbing a
window with a 3D view takes longer than a frame, and the film must not
stutter for it. Waits (an animation, a render) still pump the event loop
for real time.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import shutil
import subprocess
import tempfile
import wave

from PyQt5.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, Qt
from PyQt5.QtGui import (QColor, QFont, QImage, QMouseEvent, QPainter,
                         QPainterPath, QPen)
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import (QAction, QApplication, QInputDialog, QTabBar,
                             QToolButton, QWidget)

FPS = 20
VOICE = "Samantha"
RATE = 175                 # words a minute
SAMPLE_RATE = 22050
CAPTION_FONT = 22
GAP_AFTER_LINE = 0.35      # seconds of quiet after each spoken line


def ffmpeg():
    return shutil.which("ffmpeg") or next(
        (p for p in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg")
         if os.path.exists(p)), None)


def speak_to_wav(text, path, voice=VOICE, rate=RATE):
    """The line spoken into *path* (mono 16-bit); its length in seconds.
    Silence of a matching length where there is no ``say`` (tests on
    another system), so the film still lines up."""
    say = shutil.which("say")
    if say:
        try:
            subprocess.run([say, "-v", voice, "-r", str(rate), "-o", path,
                            "--data-format=LEI16@%d" % SAMPLE_RATE, text],
                           check=True, capture_output=True, timeout=60)
            with wave.open(path) as w:
                return w.getnframes() / float(w.getframerate())
        except (OSError, subprocess.SubprocessError, wave.Error):
            pass
    seconds = max(1.0, len(text.split()) / (rate / 60.0))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"\0\0" * int(seconds * SAMPLE_RATE))
    return seconds


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def pointer_path():
    """The arrow pointer, tip at (0, 0), ~22 px tall."""
    p = QPainterPath()
    for i, (x, y) in enumerate(((0, 0), (0, 19), (4.6, 14.8), (8.2, 22),
                                (11.2, 20.6), (7.8, 13.6), (14, 13.4))):
        (p.moveTo if i == 0 else p.lineTo)(x, y)
    p.closeSubpath()
    return p


class Recorder:
    """Films *win* while a script drives it. Use as::

        rec = Recorder(win, "part.mp4")
        rec.title("Base block", "KherveCAD tutorial")
        rec.say("Open the Sketch tab.")
        rec.click_tab("Sketch")
        ...
        rec.finish()
    """

    def __init__(self, win, out_path, fps=FPS, voice=VOICE, rate=RATE,
                 burn_captions=True):
        self.win = win
        self.out = os.path.abspath(out_path)
        self.fps = fps
        self.voice = voice
        self.rate = rate
        self.burn = burn_captions
        self.frames = 0
        self.lines = []            # (start, end, text, wav)
        self.caption = ""
        self.caption_until = 0.0
        self.voice_until = 0.0
        self.chapter = ""
        self.pos = QPoint(win.width() // 2, win.height() // 2)
        self.pressed = False
        self.ripples = []          # (x, y, frame started)
        self.highlight = None      # QRect in window coordinates
        self.typing = None         # (text, QRect) shown over a field
        self._base = None
        self.tmp = tempfile.mkdtemp(prefix="kcad_video_")
        size = self._size()
        self.w, self.h = size
        exe = ffmpeg()
        if exe is None:
            raise RuntimeError("ffmpeg is needed to write a video "
                               "(brew install ffmpeg)")
        self.silent = os.path.join(self.tmp, "picture.mp4")
        self.proc = subprocess.Popen(
            [exe, "-y", "-loglevel", "error", "-f", "rawvideo",
             "-pix_fmt", "bgra", "-s", "%dx%d" % size, "-r", str(fps),
             "-i", "-", "-c:v", "libx264", "-preset", "medium",
             "-crf", "20", "-pix_fmt", "yuv420p", self.silent],
            stdin=subprocess.PIPE)

    # ----------------------------------------------------------- clock
    @property
    def t(self):
        return self.frames / float(self.fps)

    def _size(self):
        w, h = self.win.width(), self.win.height()
        return w - w % 2, h - h % 2

    # --------------------------------------------------------- picture
    def grab(self):
        """The window as it is now, with every dialog over it."""
        QApplication.processEvents()
        img = self.win.grab().toImage().convertToFormat(
            QImage.Format_ARGB32)
        p = QPainter(img)
        origin = self.win.mapToGlobal(QPoint(0, 0))
        for top in QApplication.topLevelWidgets():
            if top is self.win or not top.isVisible() or \
                    top.windowType() in (Qt.ToolTip, Qt.Desktop):
                continue
            if isinstance(top, QWidget) and top.width() > 0:
                at = top.mapToGlobal(QPoint(0, 0)) - origin
                p.drawPixmap(at, top.grab())
        p.end()
        self._base = img
        return img

    def _compose(self):
        if self._base is None:
            self.grab()
        img = self._base.copy(0, 0, self.w, self.h)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        if self.highlight is not None:
            p.setPen(QPen(QColor(255, 140, 0), 3))
            p.setBrush(QColor(255, 140, 0, 40))
            p.drawRoundedRect(QRectF(self.highlight).adjusted(-3, -3, 3, 3),
                              5, 5)
        for x, y, f0 in self.ripples:
            age = (self.frames - f0) / float(self.fps)
            if age < 0.6:
                r = 8 + 40 * age
                a = int(220 * (1 - age / 0.6))
                p.setPen(QPen(QColor(255, 80, 40, a), 3))
                p.setBrush(QColor(255, 80, 40, a // 4))
                p.drawEllipse(QPointF(x, y), r, r)
        self.ripples = [r for r in self.ripples
                        if (self.frames - r[2]) / float(self.fps) < 0.6]
        if self.typing:
            text, rect = self.typing
            f = QFont()
            f.setPointSize(16)
            f.setBold(True)
            p.setFont(f)
            box = QRectF(rect.x(), rect.y() - 44,
                         max(120, 18 * len(text) + 40), 36)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(30, 30, 30, 220))
            p.drawRoundedRect(box, 6, 6)
            p.setPen(QColor("white"))
            p.drawText(box, int(Qt.AlignCenter), "⌨  " + text)
        self._paint_pointer(p)
        if self.burn and self.caption and self.t <= self.caption_until:
            self._paint_caption(p, self.caption)
        if self.chapter:
            self._paint_chapter(p, self.chapter)
        p.end()
        return img

    def _paint_pointer(self, p):
        p.save()
        p.translate(self.pos.x(), self.pos.y())
        if self.pressed:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 80, 40, 90))
            p.drawEllipse(QPointF(0, 0), 14, 14)
        p.scale(1.15, 1.15)
        path = pointer_path()
        p.translate(1.2, 1.6)
        p.fillPath(path, QColor(0, 0, 0, 70))         # shadow
        p.translate(-1.2, -1.6)
        p.setPen(QPen(QColor("white"), 1.6))
        p.setBrush(QColor(20, 20, 20))
        p.drawPath(path)
        p.restore()

    def _paint_caption(self, p, text):
        f = QFont()
        f.setPointSize(CAPTION_FONT)
        p.setFont(f)
        margin = 60
        box = QRectF(margin, 0, self.w - 2 * margin, 10)
        bound = p.boundingRect(box, int(Qt.AlignCenter | Qt.TextWordWrap),
                               text)
        r = QRectF(bound).adjusted(-20, -12, 20, 12)
        r.moveBottom(self.h - 34)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 190))
        p.drawRoundedRect(r, 10, 10)
        p.setPen(QColor("white"))
        p.drawText(r, int(Qt.AlignCenter | Qt.TextWordWrap), text)

    def _paint_chapter(self, p, text):
        f = QFont()
        f.setPointSize(15)
        f.setBold(True)
        p.setFont(f)
        r = QRectF(p.boundingRect(QRectF(0, 0, 900, 40), 0, text))
        r = r.adjusted(-14, -8, 14, 8)
        r.moveTopRight(QPointF(self.w - 16, self.h * 0.28))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(33, 118, 199, 220))
        p.drawRoundedRect(r, 8, 8)
        p.setPen(QColor("white"))
        p.drawText(r, int(Qt.AlignCenter), text)

    def frame(self, n=1, regrab=False):
        for _ in range(n):
            if regrab:
                self.grab()
            img = self._compose()
            self.proc.stdin.write(img.bits().asstring(img.byteCount()))
            self.frames += 1

    def wait(self, seconds, live=True):
        """Film *seconds* of the window as it goes on (animations,
        renders); *live* pumps the event loop for real time."""
        n = max(1, int(round(seconds * self.fps)))
        for _ in range(n):
            if live:
                QTest.qWait(int(1000 / self.fps))
            self.frame(regrab=live)

    # --------------------------------------------------------- talking
    def say(self, text, wait=False):
        """Speak *text* from now on; the mouse keeps working while it is
        said. A line still being said is let finish first."""
        if self.t < self.voice_until:
            self.wait(self.voice_until - self.t, live=False)
        wav = os.path.join(self.tmp, "line%03d.wav" % len(self.lines))
        dur = speak_to_wav(text, wav, self.voice, self.rate)
        start = self.t
        self.lines.append((start, start + dur, text, wav))
        self.caption = text
        self.voice_until = start + dur + GAP_AFTER_LINE
        self.caption_until = self.voice_until
        if wait:
            self.wait(self.voice_until - self.t, live=False)

    def done_talking(self):
        if self.t < self.voice_until:
            self.wait(self.voice_until - self.t, live=False)

    def title(self, text, sub="", seconds=3.0):
        """A title card."""
        img = QImage(self.w, self.h, QImage.Format_ARGB32)
        img.fill(QColor(24, 36, 54))
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont()
        f.setPointSize(44)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(QRectF(0, self.h * 0.30, self.w, 90),
                   int(Qt.AlignCenter), text)
        f.setPointSize(22)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(170, 200, 235))
        p.drawText(QRectF(80, self.h * 0.30 + 100, self.w - 160, 200),
                   int(Qt.AlignHCenter | Qt.TextWordWrap), sub)
        p.end()
        for _ in range(int(seconds * self.fps)):
            self.proc.stdin.write(img.bits().asstring(img.byteCount()))
            self.frames += 1

    # ----------------------------------------------------------- mouse
    def to_win(self, widget, point):
        return widget.mapTo(self.win, QPoint(point)) \
            if widget is not self.win else QPoint(point)

    def _send_move(self, widget, local, buttons=Qt.NoButton,
                   mods=Qt.NoModifier):
        QApplication.sendEvent(widget, QMouseEvent(
            QEvent.MouseMove, QPointF(local), Qt.NoButton, buttons, mods))

    def move(self, widget, point, seconds=None, hover=False,
             buttons=Qt.NoButton, mods=Qt.NoModifier):
        """Glide the pointer to *point* of *widget*. *hover* sends the
        moves to the widget on the way (pre-highlights under it)."""
        target = self.to_win(widget, point)
        a = QPointF(self.pos)
        d = math.hypot(target.x() - a.x(), target.y() - a.y())
        if seconds is None:
            seconds = min(1.0, 0.25 + d / 1400.0)
        n = max(2, int(seconds * self.fps))
        for i in range(1, n + 1):
            s = i / float(n)
            e = s * s * (3 - 2 * s)                   # ease in and out
            self.pos = QPoint(int(round(a.x() + (target.x() - a.x()) * e)),
                              int(round(a.y() + (target.y() - a.y()) * e)))
            regrab = False
            if hover or buttons != Qt.NoButton:
                local = widget.mapFrom(self.win, self.pos) \
                    if widget is not self.win else self.pos
                if widget.rect().contains(local) or buttons != Qt.NoButton:
                    self._send_move(widget, local, buttons, mods)
                    regrab = True
            self.frame(regrab=regrab)
        self.pos = target

    def click(self, widget, point=None, mods=Qt.NoModifier, pause=0.35,
              button=Qt.LeftButton, hover=False, outline=False,
              double=False):
        if point is None:
            point = widget.rect().center()
        if outline:
            self.highlight = QRect(self.to_win(widget, QPoint(0, 0)),
                                   widget.size())
        self.move(widget, point, hover=hover)
        self._send_move(widget, QPoint(point))
        self.frame(2, regrab=True)
        self.pressed = True
        self.ripples.append((self.pos.x(), self.pos.y(), self.frames))
        self.frame(2)
        if double:
            QTest.mouseDClick(widget, button, mods, QPoint(point))
        else:
            QTest.mouseClick(widget, button, mods, QPoint(point))
        self.pressed = False
        self.highlight = None
        self.wait(pause)

    def drag(self, widget, a, b, mods=Qt.NoModifier, seconds=0.9):
        self.move(widget, a, hover=True)
        self._send_move(widget, QPoint(a))
        self.pressed = True
        self.ripples.append((self.pos.x(), self.pos.y(), self.frames))
        self.frame(2, regrab=True)
        QTest.mousePress(widget, Qt.LeftButton, mods, QPoint(a))
        self.move(widget, b, seconds=seconds, buttons=Qt.LeftButton,
                  mods=mods)
        QTest.mouseRelease(widget, Qt.LeftButton, mods, QPoint(b))
        self.pressed = False
        self.wait(0.3)

    def key(self, widget, key, mods=Qt.NoModifier, pause=0.3):
        QTest.keyClick(widget, key, mods)
        self.wait(pause)

    def type_into(self, field, text, per_char=0.09):
        """Click into a text field, select what is there and type."""
        edit = field.lineEdit() if hasattr(field, "lineEdit") else field
        self.click(edit, pause=0.15)
        edit.selectAll()
        self.frame(2, regrab=True)
        for ch in str(text):
            QTest.keyClicks(edit, ch)
            self.frame(max(1, int(per_char * self.fps)), regrab=True)
        QTest.keyClick(edit, Qt.Key_Return)
        self.wait(0.3)

    def choose(self, combo, data=None, text=None):
        """Open a drop-down on film and pick an entry (by data or text)."""
        self.click(combo, pause=0.2)
        i = combo.findData(data) if data is not None else \
            combo.findText(text)
        combo.hidePopup()
        if i >= 0:
            combo.setCurrentIndex(i)
        self.wait(0.4)

    # ----------------------------------------------- KherveCAD helpers
    def button(self, action):
        """The visible tool button showing *action* (an action or its
        data key)."""
        if not isinstance(action, QAction):
            action = next(a for a in self.win.findChildren(QAction)
                          if a.data() == action)
        for b in self.win.findChildren(QToolButton):
            if b.isVisible() and b.defaultAction() is action:
                return b
        return None

    def click_action(self, key, pause=0.5):
        """Click a ribbon / toolbar button by its action (or data key);
        an action with no visible button is triggered with the pointer
        going to the ribbon area."""
        b = self.button(key)
        if b is not None:
            self.click(b, outline=True, pause=pause)
            return
        act = key if isinstance(key, QAction) else next(
            a for a in self.win.findChildren(QAction) if a.data() == key)
        act.trigger()
        self.wait(pause)

    def click_tab(self, name, pause=0.5):
        bar = next(b for b in self.win.findChildren(QTabBar)
                   if b.isVisible() and any(
                       b.tabText(i).replace("&", "") == name
                       for i in range(b.count())))
        i = next(i for i in range(bar.count())
                 if bar.tabText(i).replace("&", "") == name)
        rect = bar.tabRect(i)
        self.highlight = QRect(bar.mapTo(self.win, rect.topLeft()),
                               rect.size())
        self.click(bar, rect.center(), pause=pause)

    def sketch_point(self, x, y):
        """A point of the 2D sketch in its view's viewport."""
        return self.win.view2d.mapFromScene(QPointF(x, y))

    def click_sketch(self, x, y, **kw):
        self.click(self.win.view2d.viewport(), self.sketch_point(x, y),
                   hover=True, **kw)

    def drag_sketch(self, a, b, **kw):
        self.drag(self.win.view2d.viewport(), self.sketch_point(*a),
                  self.sketch_point(*b), **kw)

    def world_point(self, xyz):
        v3 = self.win.view3d
        q = v3._project(*v3._camera(), tuple(xyz))
        return QPoint(int(round(q[0])), int(round(q[1])))

    def click_world(self, xyz, **kw):
        self.click(self.win.view3d, self.world_point(xyz), hover=True, **kw)

    def answer_values(self, scene=None):
        """Let a Smart Dimension's value be TYPED on film: the scene's
        ``ask_value`` hook shows a real input box over the window and the
        recorder types the next value of ``self.values`` into it."""
        scene = scene or self.win.view2d.scene()
        self.values = []

        def ask(kind, measured):
            value = self.values.pop(0) if self.values else "%g" % measured
            box = QInputDialog(self.win)
            box.setWindowTitle("Smart Dimension")
            box.setLabelText("Value (%s):" % ("°" if kind == "angle"
                                               else "mm"))
            box.setTextValue("%g" % round(measured, 3))
            box.setWindowModality(Qt.NonModal)
            box.adjustSize()
            g = box.frameGeometry()
            centre = self.win.mapToGlobal(self.pos)
            box.move(centre.x() + 30, centre.y() - g.height() - 20)
            box.show()
            self.wait(0.4)
            from PyQt5.QtWidgets import QLineEdit
            edit = box.findChild(QLineEdit)
            self.click(edit, pause=0.1)
            edit.selectAll()
            for ch in str(value):
                QTest.keyClicks(edit, ch)
                self.frame(2, regrab=True)
            self.wait(0.4)
            box.hide()
            box.deleteLater()
            return str(value)
        scene.ask_value = ask
        return ask

    # ----------------------------------------------------------- write
    def finish(self, tail=1.0):
        self.done_talking()
        self.wait(tail, live=False)
        self.proc.stdin.close()
        self.proc.wait()
        total = self.t
        track = os.path.join(self.tmp, "voice.wav")
        self._write_track(track, total)
        exe = ffmpeg()
        subprocess.run([exe, "-y", "-loglevel", "error", "-i", self.silent,
                        "-i", track, "-c:v", "copy", "-c:a", "aac",
                        "-b:a", "128k", "-shortest", self.out], check=True)
        stem = os.path.splitext(self.out)[0]
        with open(stem + ".srt", "w", encoding="utf-8") as f:
            for i, (a, b, text, _w) in enumerate(self.lines, 1):
                f.write("%d\n%s --> %s\n%s\n\n" % (i, srt_time(a),
                                                   srt_time(b), text))
        with open(stem + " narration.txt", "w", encoding="utf-8") as f:
            f.write("# Narration for %s — one line per spoken step, with "
                    "the time it starts.\n# Voice it again with any "
                    "text-to-speech and lay each line at its time.\n\n"
                    % os.path.basename(self.out))
            for a, _b, text, _w in self.lines:
                f.write("[%s] %s\n" % (srt_time(a)[:8], text))
        shutil.rmtree(self.tmp, ignore_errors=True)
        return {"video": self.out, "seconds": round(total, 1),
                "lines": len(self.lines)}

    def _write_track(self, path, total):
        n = int(total * SAMPLE_RATE) + SAMPLE_RATE
        buf = bytearray(n * 2)
        for start, _end, _text, wav in self.lines:
            try:
                with wave.open(wav) as w:
                    data = w.readframes(w.getnframes())
                    if w.getframerate() != SAMPLE_RATE or \
                            w.getsampwidth() != 2:
                        continue
            except (OSError, wave.Error):
                continue
            at = int(start * SAMPLE_RATE) * 2
            end = min(len(buf), at + len(data))
            buf[at:end] = data[:end - at]
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes(bytes(buf))
