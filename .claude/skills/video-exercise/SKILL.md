---
name: video-exercise
description: Rebuild a CAD tutorial video (SolidWorks, Fusion, Onshape...) in KherveCAD — turn a YouTube link, a video file, or a folder holding them into frames + captions with KherveFrames, read the steps, reproduce each in the live KherveCAD window, compare with the video, fix every KherveCAD problem it shows in a test-first loop, and only then write a KherveTeX report (PDF) of how the part is made. Use whenever the user gives a YouTube link or a video (or a folder with one) of a CAD exercise, or asks to reproduce / follow / copy a tutorial or exercise from a video.
---

# Rebuild a CAD exercise from a video

The point is twofold: get the part right, AND find out where KherveCAD
makes the exercise hard. The second matters as much as the first.

## 1. Find the source

The user may give:
- a YouTube link in the message;
- a video file (.mp4, .mov, .mkv, .webm);
- a FOLDER. Look inside it for a video file, and for links in any `.txt`,
  `.md`, `.url` (`URL=` line) or `.webloc` (`<string>` in the plist).
  Several links = several exercises: do them one at a time, asking which
  first if the order is not obvious.

Use the folder as the exercise's home: frames, notes and the `.kcad` go
there. With a bare link, make `~/Documents/KherveCAD Exercises/<video
title>/`.

## 2. Extract frames and captions

KherveFrames lives in `~/Documents/PycharmProjects/KherveFrames`
(its `./frames` launcher sets up certificates; never call frames.py with
the system Python).

```bash
~/Documents/PycharmProjects/KherveFrames/frames "<url or file>" --seconds 2 --subs --sheets --width 1280 --out "<exercise folder>/frames"
```

- One frame every 2 seconds is the DEFAULT (the user: ~50 frames for a
  10-minute video was not enough to see how each step is done — about
  30 a minute is). Go to `--seconds 1` over a fast passage
  (`--start/--end`, another `--out`). `--changes` alone misses clicks.
- `--sheets` tiles them 2x2 into `frames_sheets/`: read the SHEETS in
  order to follow every click (4 frames per picture), then open single
  frames at full size where a dimension, dialog or value must be read.
- `--subs` writes the caption on each image and `captions.txt` (what was
  said from one frame to the next). Add a language (`--subs fr`) if the
  video is not in English. "no captions found" is fine — go on without.
- Downloads are cached; re-running with other settings is cheap.
- If yt-dlp fails on a URL that used to work, run
  `.venv/bin/pip install -U yt-dlp` in that folder and retry.

## 3. Read the exercise before building

Read `captions.txt` whole, then look at the frames (Read the PNGs —
skim quickly, look closely at frames with dimensions, dialogs or a new
feature). Write `<exercise folder>/steps.md`: one numbered line per
feature — sketch plane, sketch shapes with EVERY dimension and relation
shown, then the feature (Extruded Boss 20 mm, Cut-Extrude Through All,
Fillet R5...) with the frame names it comes from. Note values you could
not read. The final part often shows in a drawing or the last frames:
take its overall size to check against at the end.

## 4. Build it in KherveCAD, the way the video does

Use the live window through the `mcp__khervecad__*` tools (and
get_document_info first). Follow the video's ORDER and its features —
sketch on the same plane or face, the same relations and Smart
Dimensions (`sketch_constraint`), the same extrudes / cuts / fillets /
patterns / mirrors (hole_wizard, fillet_edges, suppress, reference_geometry...)
— not a shortcut program that only ends up the same shape. The test is
whether a SolidWorks user could do it in KherveCAD the same way.
Name each feature as in the video. After each feature, `render_view`
from the angle of the matching frame and compare; fix before moving on.

When the user asks to watch, prefer real mouse work (computer use) over
MCP for the steps they want to see.

## 5. Check and save

Compare the finished part with the last frames: `render_view` from the
same views, `mass_properties` / `get_node_bounds` against any given
size or mass. Save as `<exercise folder>/<title>.kcad`; put a
`compare/` folder of KherveCAD renders beside matching frames if useful.

## 6. Problems → fix KherveCAD in a loop

Keep `<exercise folder>/problems.md` as you go: for each step that was
hard, impossible, wrong or needed a workaround — what the video did,
what KherveCAD did instead, how bad (blocker / workaround / cosmetic),
which module or tool it concerns, and a status (open / fixed in vN).

Then FIX THEM, without waiting to be asked, worst first, in a loop:

1. Reproduce the problem in a unit test under `tests/` first (offscreen,
   real mouse events where the user would use the mouse — see the
   `*_by_mouse` / `test_*_mouse` tests); it must FAIL before the fix.
2. Fix KherveCAD (follow CLAUDE.md: file size, MCP reach, help /
   tooltips, CLAUDE.md notes for anything non-obvious).
3. Run the new test and the related test files; then the whole suite
   before the commit if the change is broad.
4. Commit and push each fix on its own (`v<N>: fix: ...`, CLAUDE.md
   rules; stage only your own files). Mark it fixed in problems.md.
5. Redo the exercise's affected steps — from scratch, the video's way —
   in a fresh document. New problems go back into the list.

Repeat until the WHOLE exercise goes through the video's way with no
open blocker or workaround. Cosmetic leftovers may stay open, listed.
A missing tool that is a big feature of its own (days of work): build it
if the exercise cannot be done without it, but tell the user it is
coming first; anything else, ask before starting.
If the loop stalls (the same problem three times), stop and ask.

## 7. The report — only once it works

Only when step 6 is done and a final clean run of the exercise worked,
write the report in **KherveTeX** (the `mcp__khervetex__*` tools drive
the user's live KherveTeX window; get_document_info first, new_document
— never discard unsaved work). Title = the video's title; author line
says it was rebuilt in KherveCAD vN. Contents:

- **The part**: what it is, its overall size, the video link, a picture
  of the finished KherveCAD part (render_view saved as PNG into the
  exercise folder, \includegraphics).
- **How it is made**, one subsection per feature in order: plane or
  face, what is sketched with every dimension and relation, the feature
  and its values, and HOW to do it in KherveCAD (which tab / button /
  clicks, or the MCP call), with a KherveCAD render of that stage and,
  where it helps, the matching video frame beside it.
- **Check**: the final views against the video's, sizes / mass.
- **What KherveCAD needed**: the problems found and the fix for each
  (version, one line), and what is still cosmetic.

compile_document, look at the pages with render_page and fix the
layout, then save as `<exercise folder>/<title>.ktex` and export_pdf
`<title>.pdf` beside it. If KherveTeX is not connected, say so and ask
the user to open it rather than writing LaTeX by hand. End by giving the
user the PDF path and a short summary of the fixes.
