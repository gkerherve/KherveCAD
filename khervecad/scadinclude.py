"""``use <...>`` / ``include <...>``, ``children()`` and calls the
importer cannot turn into objects — the parts of scadparse that reach
beyond one file.

- A directive becomes a **scad_use** node (it emits the same line, so
  the engine loads the library) and the library file is read for its
  module and function definitions (and, for ``include``, its variables)
  — resolved the way OpenSCAD resolves it (scadlib.resolve). Parsed
  libraries are cached per file and modification time.
- A call to a library module is **inlined** into objects like a local
  module when that works cleanly; when it does not (the body leans on
  something outside the importable subset, or yields no geometry) the
  call is kept verbatim as a **scad_raw** node, so the engine still
  renders it and nothing the author wrote is lost.
- A call nobody defines is kept as a scad_raw node too (it used to be
  dropped).
- ``children()`` inside an inlined module body stands for the call's
  own children, cloned where it is used more than once.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import re
from collections import namedtuple

from . import expr, scadlib
from .model import CadNode

#: a user module: parameter list, body token span, the token list and
#: text the span indexes, and for a library module its file's scope
Module = namedtuple("Module", "params start end tokens text scope")

#: (path, mtime) -> (modules, scope) of a parsed library file
_LIBRARY_CACHE = {}
#: parsed libraries kept
LIBRARY_CACHE_FILES = 64
#: a library larger than this is not read (the directive is still kept)
MAX_LIBRARY_BYTES = 4_000_000

_DIRECTIVE = re.compile(r"(use|include)\s*<([^>]*)>")


# ------------------------------------------------------------ directives

def parse_directive(parser):
    """A `use <...>` / `include <...>` token -> a scad_use node; the file's
    definitions join the parser's."""
    token = parser.next()
    match = _DIRECTIVE.match(token[1])
    kind, name = match.group(1), match.group(2).strip()
    parser.accept(";")
    node = CadNode("scad_use", f"{kind} <{name}>",
                   dict(kind=kind, path=name))
    path = scadlib.resolve(name, parser.base_dir)
    if path is not None and parser.base_dir and \
            scadlib.resolve(name) != path:
        scadlib.remember_import_dir(parser.base_dir)
    if path is None:
        parser.warn(f"{kind} <{name}>: file not found — install the "
                    "library (Library ▸ OpenSCAD Libraries) or put it "
                    "beside the .scad file")
        return node
    load_library(parser, path, kind)
    return node


def load_library(parser, path, kind):
    """Read *path*'s definitions into *parser* (modules and functions;
    variables too for an include)."""
    path = os.path.abspath(path)
    if path in parser._loading:
        return
    try:
        stamp = os.path.getmtime(path)
        size = os.path.getsize(path)
    except OSError:
        return
    if size > MAX_LIBRARY_BYTES:
        parser.warn(f"{os.path.basename(path)} is too large to read; "
                    "its modules render through OpenSCAD only")
        return
    key = (path, stamp)
    cached = _LIBRARY_CACHE.get(key)
    if cached is None:
        cached = _read_library(parser, path)
        if len(_LIBRARY_CACHE) >= LIBRARY_CACHE_FILES:
            _LIBRARY_CACHE.pop(next(iter(_LIBRARY_CACHE)))
        _LIBRARY_CACHE[key] = cached
    modules, scope = cached
    parser.modules.update(modules)
    for name, value in scope.items():
        if callable(value) or kind == "include":
            parser.scope[name] = value


def _read_library(parser, path):
    from .scadparse import Parser, ScadParseError
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        sub = Parser(text, base_dir=os.path.dirname(path))
    except (OSError, ScadParseError):
        return {}, {}
    sub._loading = parser._loading | {path}
    sub.library_scope = sub.scope            # its modules see this file
    while sub.peek() is not None:
        start = sub.i
        token = sub.peek()
        nxt = sub.peek(1)
        try:
            if token[0] == "directive":
                parse_directive(sub)
            elif token[1] == "module":
                sub._capture_module()
            elif token[1] == "function":
                sub._capture_function()
            elif token[0] == "ident" and nxt is not None and nxt[1] == "=":
                sub._parse_assign()
            else:                             # geometry: OpenSCAD's job
                sub._recover(start)
        except Exception:                     # never fail the importer
            sub._recover(start)
    return sub.modules, sub.scope


# -------------------------------------------------------------- children

def call_children(parser):
    """The children written after a module call — `;`, one statement or
    a `{ block }` — parsed in the caller's scope."""
    if parser.accept(";"):
        return []
    token = parser.peek()
    if token is None:
        return []
    kids = []
    if token[1] == "{":
        parser.expect("{")
        while not parser.accept("}"):
            child = parser.parse_statement()
            if child is not None:
                kids.append(child)
    else:
        child = parser.parse_statement()
        if child is not None:
            kids.append(child)
    return kids


def clone(node):
    """A deep copy of *node*'s subtree (fresh ids)."""
    import copy
    twin = CadNode(node.type, node.name, copy.deepcopy(node.params))
    twin.visible = node.visible
    for child in node.children:
        twin.add(clone(child))
    return twin


def parse_children(parser):
    """`children()`, `children(i)`, `children([a, b])`, `children([a :
    b])` inside a module body being inlined -> the call's children (the
    originals the first time, so their comment labels stay, then
    clones)."""
    from .scadlang import raw_arguments
    args = raw_arguments(parser) if parser.peek() is not None and \
        parser.peek()[1] == "(" else ""
    parser.accept(";")
    if not parser._children_stack:
        parser.warn("children() outside a module skipped")
        return None
    kids = parser._children_stack[-1]
    if args:
        try:
            picked = expr.evaluate(args, parser.scope)
        except expr.ExprError:
            parser.warn(f"children({args}) could not be resolved")
            return None
        indices = picked if isinstance(picked, list) else [picked]
        chosen = []
        for index in indices:
            try:
                chosen.append(kids[int(index)])
            except (TypeError, ValueError, IndexError):
                pass
    else:
        chosen = list(kids)
    if not chosen:
        return None
    used = getattr(parser, "_children_used", None)
    if used is None:
        used = parser._children_used = set()
    out = []
    for kid in chosen:
        out.append(clone(kid) if id(kid) in used else kid)
        used.add(id(kid))
    if len(out) == 1:
        return out[0]
    group = CadNode("union", "Children")
    for kid in out:
        group.add(kid)
    return group


# ------------------------------------------------------ raw fallbacks

def _statement_text(parser, start):
    """Source of tokens[start:parser.i], its continuation lines dedented
    by the first line's indent (so re-exporting inside a block does not
    indent it further each round trip)."""
    tokens = parser.tokens
    if start >= parser.i:
        return ""
    first, last = tokens[start], tokens[parser.i - 1]
    text = parser.text
    line_start = text.rfind("\n", 0, first[2]) + 1
    indent = first[2] - line_start
    body = text[first[2]:last[3]]
    lines = body.split("\n")
    out = [lines[0]]
    for line in lines[1:]:
        strip = min(indent, len(line) - len(line.lstrip(" ")))
        out.append(line[strip:])
    return "\n".join(out)


def raw_statement(parser, start, message):
    """The statement from token *start* to here as a scad_raw node — the
    code is kept exactly, and OpenSCAD renders it."""
    code = _statement_text(parser, start)
    if not code.strip():
        return None
    parser.warn(message)
    if not code.rstrip().endswith((";", "}")):
        code = code.rstrip() + ";"
    name = parser.tokens[start][1]
    return CadNode("scad_raw", f"{name}()", dict(code=code))


def inline_or_raw(parser, name, start):
    """Inline a module call; a LIBRARY module that does not come out as
    clean objects is kept as its call, verbatim."""
    from .scadparse import _has_geometry
    module = parser.modules[name]
    if module.scope is None:                    # this file's own module
        return parser._inline_module(name)
    warnings, heads = len(parser.warnings), len(parser._heads)
    try:
        node = parser._inline_module(name)
        clean = len(parser.warnings) == warnings and node is not None \
            and _has_geometry(node)
    except Exception:
        node, clean = None, False
    if clean:
        return node
    del parser.warnings[warnings:]
    del parser._heads[heads:]
    if parser.i <= start + 1:                   # the call was not consumed
        parser.i = start + 1
        parser._skip_call_statement()
    return raw_statement(parser, start, f"{name}() kept as OpenSCAD code "
                                        "(rendered by OpenSCAD)")
