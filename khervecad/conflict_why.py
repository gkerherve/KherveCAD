# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Say WHICH relations a refused dimension fights (2026-11-16, the user:
"if there is a constraint, then that constraint should be clearly
explained where it is, because I can't see where that constraint comes
from"). A row is a culprit when the sketch solves once it is left out;
the sentence names each one ("Fixed on Reference edge (start)")."""

#: at most this many other rows are tried (each is one solve)
MAX_TRIED = 40


def culprits(container, rs, new_index, env=None, held=None):
    """Indices of the rows (other than *new_index*) without which *rs*
    solves."""
    from . import sketch_constraints as sc
    out = []
    others = [i for i in range(len(rs)) if i != new_index]
    for i in others[:MAX_TRIED]:
        if rs[i].get("driven"):
            continue
        trial = [r for j, r in enumerate(rs) if j != i]
        try:
            report = sc.solve(container, trial, env=env, write=False,
                              held=held or [])
        except Exception:
            continue
        if report.get("ok"):
            out.append(i)
    return out


def words(container, row):
    try:
        from .relations_window import describe
        label, ents, value = describe(container, row)
    except Exception:
        return str(row.get("kind", "?"))
    text = label
    if value:
        text += " " + value
    if ents:
        text += " on " + ents
    return text


def explain(container, rs, new_index, env=None, held=None):
    """' It fights: …. Delete or change that relation (Display/Delete
    Relations), or make this dimension driven.' — or '' when no single
    relation is to blame."""
    found = culprits(container, rs, new_index, env, held)
    if not found:
        return (" Several relations hold it together — open Display / "
                "Delete Relations to see them.")
    names = "; ".join(words(container, rs[i]) for i in found[:4])
    more = " (and %d more)" % (len(found) - 4) if len(found) > 4 else ""
    fixed = any(rs[i].get("kind") in ("fix", "on_edge") for i in found)
    hint = (" That one is a FIXED reference (an edge or point of the "
            "part copied into the sketch) — its size comes from the part; "
            "change the part, or make this dimension driven."
            if fixed else
            " Delete or change it (Display / Delete Relations), or make "
            "this dimension driven.")
    return " It fights: %s%s.%s" % (names, more, hint)
