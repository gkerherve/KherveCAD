---
name: video-exercise
description: Rebuild a CAD tutorial video (SolidWorks, Fusion, Onshape...) in KherveCAD — turn a YouTube link, a video file, or a folder holding them into frames + captions with KherveFrames, read the steps, reproduce each in the live KherveCAD window, compare with the video, and report where KherveCAD struggled. Use whenever the user gives a YouTube link or a video (or a folder with one) of a CAD exercise, or asks to reproduce / follow / copy a tutorial or exercise from a video.
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
~/Documents/PycharmProjects/KherveFrames/frames "<url or file>" --changes --subs --out "<exercise folder>/frames"
```

- `--changes` (screen-change detection) is the default choice for a
  screen recording. Aim for roughly 30-150 frames: too many → raise it
  (`--changes 0.15`), steps missing → lower it (`0.04`) or use
  `--seconds 2` over the part that moved too fast (`--start/--end`).
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

## 6. Report the problems — the main output

Write `<exercise folder>/problems.md` and summarise it to the user:
for each step that was hard, impossible, wrong or needed a workaround:
what the video did, what KherveCAD did instead, how bad (blocker /
workaround / cosmetic), and which KherveCAD module or tool it concerns.
Also list SolidWorks tools the video used that KherveCAD lacks. Do NOT
start fixing KherveCAD inside this skill: offer the fixes (most
important first) and wait for the user's go.
