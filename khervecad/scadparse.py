"""Import OpenSCAD programs back into a KherveCAD object tree.

Parses the OpenSCAD subset KherveCAD generates — primitives,
transforms, extrusions, booleans, offset/hull/minkowski, `for`
loops, `if/else`, assignments, `import()` and the `*` disable
modifier — plus common variations (named or positional arguments,
`d=` diameters, scalar `rotate`/`scale`, bare `{}` blocks).

User `module` definitions are inlined at each call site and user
`function` definitions are evaluated (recursion and cross-calls
included), so list comprehensions `[for (i = r) let (..) if (c) expr]`,
`concat`, vector variables and `.x/.y/.z` all resolve to real numbers at
import — a `polygon(points)` whose points come from a variable, a
comprehension or a function (e.g. a NACA airfoil) imports as concrete
coordinates. Assignments that evaluate to a vector are stored as a
self-contained literal so the tree never depends on a function that
codegen can't emit.

Parsing never crashes a whole file: a statement that can't be parsed is
skipped with a warning and import resumes at the next boundary. Anything
still outside the subset (`use`/`include`, unknown external calls) is
skipped with a warning. Non-constant expressions are kept verbatim as
expression strings, which KherveCAD params support.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re

from . import expr
from .model import CadNode

_TOKEN_RE = re.compile(r"""
    (?P<space>\s+)
  | (?P<comment>//[^\n]*|/\*.*?\*/)
  | (?P<number>\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?)
  | (?P<string>"(?:\\.|[^"\\])*")
  | (?P<ident>\$?[A-Za-z_]\w*)
  | (?P<op><=|>=|==|!=|&&|\|\||[-+*/%^<>=!?:,;(){}\[\]#.])
""", re.VERBOSE | re.DOTALL)


class ScadParseError(ValueError):
    pass


def _tokenize(text):
    tokens = []
    pos = 0
    while pos < len(text):
        match = _TOKEN_RE.match(text, pos)
        if match is None:
            raise ScadParseError(
                f"unexpected character {text[pos]!r} at offset {pos}")
        kind = match.lastgroup
        if kind not in ("space", "comment"):
            tokens.append((kind, match.group(), match.start(),
                           match.end()))
        pos = match.end()
    return tokens


class Parser:
    def __init__(self, text: str):
        self.text = text
        self.tokens = _tokenize(text)
        self.i = 0
        self.warnings = []
        #: name -> (params, body_start_i, body_end_i) for user modules,
        #: expanded (inlined) at each call site.
        self.modules = {}
        #: concrete values of top-level/bound assignments, so later
        #: expressions (polygon points, vector variables, list
        #: comprehensions) can be resolved to real numbers at import.
        self.scope = {}

    # ------------------------------------------------------- helpers
    def peek(self, offset=0):
        j = self.i + offset
        return self.tokens[j] if j < len(self.tokens) else None

    def next(self):
        token = self.peek()
        if token is None:
            raise ScadParseError("unexpected end of input")
        self.i += 1
        return token

    def accept(self, value):
        token = self.peek()
        if token is not None and token[1] == value:
            self.i += 1
            return True
        return False

    def expect(self, value):
        token = self.next()
        if token[1] != value:
            raise ScadParseError(
                f"expected {value!r}, got {token[1]!r}")
        return token

    def warn(self, message):
        self.warnings.append(message)

    def resolve_points(self, raw):
        """Turn a polygon ``points`` argument into a concrete list of
        ``[x, y]`` pairs. Accepts an inline list, a variable name, a list
        of variable names, or a list comprehension — anything that
        evaluates against the current scope. Returns None if it can't."""
        value = raw
        if isinstance(value, str):
            try:
                value = expr.evaluate(value, self.scope)
            except Exception:
                return None
        if not isinstance(value, (list, tuple)):
            return None
        pts = []
        for element in value:
            if isinstance(element, str):
                try:
                    element = expr.evaluate(element, self.scope)
                except Exception:
                    return None
            if isinstance(element, (list, tuple)) and len(element) >= 2:
                try:
                    pts.append([float(element[0]), float(element[1])])
                except (TypeError, ValueError):
                    return None
            else:
                return None
        return pts if len(pts) >= 3 else None

    # ------------------------------------------- expression scanning
    def _scan_expr(self, stop=(",", ")", "]", ";", ":")):
        """Consume one expression; return (numeric_or_None, source). A
        ternary `c ? a : b` is kept whole — its `:` is the ternary
        separator, not a stop (that would otherwise cut the expression)."""
        depth = 0
        ternary = 0
        start = self.peek()
        if start is None:
            raise ScadParseError("expected expression")
        begin = start[2]
        end = begin
        while True:
            token = self.peek()
            if token is None:
                break
            t = token[1]
            if depth == 0:
                if t == "?":
                    ternary += 1
                elif t == ":" and ternary > 0:
                    ternary -= 1               # ternary colon, keep going
                elif t in stop:
                    break
            if t in "([{":
                depth += 1
            elif t in ")]}":
                if depth == 0:
                    break
                depth -= 1
            end = token[3]
            self.i += 1
        source = self.text[begin:end].strip()
        if not source:
            raise ScadParseError("empty expression")
        try:
            value = expr.evaluate(source, self.scope)
        except (expr.ExprError, Exception):
            return None, source
        return value, source

    def _expr_param(self):
        """Expression as a param value: float when constant, else the
        source string."""
        value, source = self._scan_expr()
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return float(value)
        return source

    def _vector(self):
        """[a, b, ...] as a list of param values; assumes next is [."""
        self.expect("[")
        items = []
        if not self.accept("]"):
            while True:
                items.append(self._expr_param())
                if self.accept("]"):
                    break
                self.expect(",")
                if self.accept("]"):             # trailing comma
                    break
        return items

    def _arguments(self):
        """Parse (...) into (positional list, named dict)."""
        self.expect("(")
        positional, named = [], {}
        if self.accept(")"):
            return positional, named
        while True:
            token = self.peek()
            nxt = self.peek(1)
            if token and token[0] == "ident" and nxt and nxt[1] == "=" \
                    and (self.peek(2) is None or self.peek(2)[1] != "="):
                name = self.next()[1]
                self.expect("=")
                named[name] = self._argument_value()
            else:
                positional.append(self._argument_value())
            if self.accept(")"):
                return positional, named
            self.expect(",")
            if self.accept(")"):                 # trailing comma
                return positional, named

    def _argument_value(self):
        token = self.peek()
        if token is not None and token[1] == "[":
            # vector of vectors (polygon points) or plain vector
            if self.peek(1) is not None and self.peek(1)[1] == "[":
                self.expect("[")
                points = []
                while True:
                    points.append(self._vector())
                    if self.accept("]"):
                        break
                    self.expect(",")
                return points
            return self._vector()
        if token is not None and token[0] == "string":
            self.next()
            return _unquote(token[1])
        return self._expr_param()

    # ----------------------------------------------------- statements
    def parse_program(self) -> CadNode:
        root = CadNode("root")
        while self.peek() is not None:
            start = self.i
            try:
                node = self.parse_statement()
            except ScadParseError as exc:
                self.warn(f"skipped unparseable statement: {exc}")
                self._recover(start)
                continue
            except Exception as exc:             # never crash a whole file
                self.warn(f"skipped statement ({type(exc).__name__})")
                self._recover(start)
                continue
            if node is not None:
                root.add(node)
        return root

    def _recover(self, start):
        """After a failed statement, advance to the next top-level ';' or
        '}' so the rest of the file still imports (and we never loop)."""
        if self.i <= start:
            self.i = start + 1
        depth = 0
        while self.peek() is not None:
            token = self.next()
            if token[1] in "([{":
                depth += 1
            elif token[1] in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif token[1] == ";" and depth == 0:
                break

    def parse_statement(self):
        token = self.peek()
        if token is None:
            return None
        value = token[1]
        if value == ";":
            self.next()
            return None
        if value == "{":
            return self._block_as_union()
        if value in ("*", "!", "#", "%"):
            self.next()
            node = self.parse_statement()
            if node is not None and value == "*":
                node.visible = False
            elif value == "!":
                self.warn("'!' root modifier ignored")
            return node
        if token[0] != "ident":
            raise ScadParseError(f"unexpected token {value!r}")
        if value == "for":
            return self._parse_for()
        if value == "if":
            return self._parse_if()
        if value in ("use", "include"):
            self._skip_directive()
            return None
        if value == "module":
            self._capture_module()
            return None
        if value == "function":
            self._capture_function()
            return None
        nxt = self.peek(1)
        if nxt is not None and nxt[1] == "=":
            return self._parse_assign()
        if nxt is not None and nxt[1] == "(":
            return self._parse_call()
        raise ScadParseError(f"unexpected identifier {value!r}")

    def _block_as_union(self):
        self.expect("{")
        node = CadNode("union", "Group")
        while not self.accept("}"):
            child = self.parse_statement()
            if child is not None:
                node.add(child)
        return node

    def _children_into(self, node):
        """Attach the following statement / block as children."""
        if self.accept(";"):
            return node
        token = self.peek()
        if token is not None and token[1] == "{":
            self.expect("{")
            while not self.accept("}"):
                child = self.parse_statement()
                if child is not None:
                    node.add(child)
            return node
        child = self.parse_statement()
        if child is not None:
            node.add(child)
        return node

    def _parse_assign(self):
        name = self.next()[1]
        self.expect("=")
        value, source = self._scan_expr()
        self.accept(";")
        # remember the concrete value so later expressions (points that
        # reference this, list comprehensions using it, ...) can resolve.
        if value is not None:
            self.scope[name] = value
        if isinstance(value, bool):
            param = value
        elif isinstance(value, (int, float)):
            param = float(value)
        elif isinstance(value, (list, tuple)):
            # store the resolved vector/list as a self-contained literal —
            # its source may call user functions that are not tree nodes
            # (so validate() and codegen would otherwise choke on them).
            param = _literal(value)
        else:                                    # unresolved expression
            param = source
        return CadNode("assign", f"{name} =",
                       dict(variable=name, value=param))

    def _parse_for(self):
        self.next()                              # for
        self.expect("(")
        loops = []
        while True:
            var = self.next()[1]
            self.expect("=")
            loops.append((var, self._parse_range()))
            if self.accept(")"):
                break
            self.expect(",")
        outer = current = None
        for var, params in loops:
            params["variable"] = var
            node = CadNode("for_loop", f"For {var}", params)
            if current is not None:
                current.add(node)
            current = node
            outer = outer or node
        self._children_into(current)
        return outer

    def _parse_range(self):
        """[a:b], [a:s:b], [v1, v2, ...] or a single expression."""
        token = self.peek()
        if token is not None and token[1] == "[":
            self.expect("[")
            first = self._expr_param()
            if self.accept(":"):
                second = self._expr_param()
                if self.accept(":"):
                    third = self._expr_param()
                    self.expect("]")
                    return dict(start=first, step=second, end=third,
                                values="")
                self.expect("]")
                return dict(start=first, step=1.0, end=second,
                            values="")
            values = [first]
            while self.accept(","):
                values.append(self._expr_param())
            self.expect("]")
            from .model import fmt
            return dict(values=", ".join(fmt(v) for v in values))
        value = self._expr_param()
        from .model import fmt
        return dict(values=fmt(value))

    def _parse_if(self):
        self.next()                              # if
        self.expect("(")
        _value, condition = self._scan_expr(stop=(")",))
        self.expect(")")
        node = CadNode("if_else", f"If {condition}",
                       dict(condition=condition))
        self._children_into(node)
        if self.peek() is not None and self.peek()[1] == "else":
            self.next()
            else_branch = CadNode("union", "Else")
            self._children_into(else_branch)
            node.add(else_branch)
        return node

    def _skip_directive(self):
        # use <file> / include <file>
        while self.peek() is not None and self.peek()[1] not in (";", ">"):
            self.next()
        if self.peek() is not None:
            self.next()
        self.warn("use/include directive skipped")

    def _skip_definition(self, kind):
        name = "?"
        self.next()
        if self.peek() is not None and self.peek()[0] == "ident":
            name = self.next()[1]
        depth = 0
        started = False
        while self.peek() is not None:
            token = self.next()
            if token[1] in "({[":
                depth += 1
                started = True
            elif token[1] in ")}]":
                depth -= 1
            elif token[1] == ";" and depth == 0:
                break
            if started and depth == 0 and token[1] == "}":
                break
        self.warn(f"{kind} '{name}' skipped (not supported)")

    def _capture_function(self):
        """Record `function name(params) = expr;` as a callable in the
        scope, so expressions (and polygon points) that call it resolve
        at import. Supports defaults and recursion / cross-calls via a
        live closure over the parser scope."""
        self.next()                                   # 'function'
        if self.peek() is None or self.peek()[0] != "ident":
            return self._skip_definition("function")
        name = self.next()[1]
        self.expect("(")
        params = []
        while not self.accept(")"):
            pname = self.next()[1]
            default = None
            if self.accept("="):
                default = self._scan_expr(stop=(",", ")"))[1]
            params.append((pname, default))
            if self.accept(")"):
                break
            self.expect(",")
        self.expect("=")
        body = self._scan_expr(stop=(";",))[1]
        self.accept(";")
        scope = self.scope

        def call(*args, **kwargs):
            local = dict(scope)
            for idx, (pname, default) in enumerate(params):
                if idx < len(args):
                    local[pname] = args[idx]
                elif pname in kwargs:
                    local[pname] = kwargs[pname]
                elif default is not None:
                    local[pname] = expr.evaluate(default, local)
            return expr.evaluate(body, local)

        self.scope[name] = call

    # ------------------------------------------------------- modules
    def _capture_module(self):
        """Record a `module name(params) { body }` definition so each
        call can be inlined (its body re-parsed with the arguments bound
        as local variables)."""
        self.next()                                   # 'module'
        name = "?"
        if self.peek() is not None and self.peek()[0] == "ident":
            name = self.next()[1]
        self.expect("(")
        params = []
        while not self.accept(")"):
            pname = self.next()[1]
            default = None
            if self.accept("="):
                default = self._scan_expr(stop=(",", ")"))[1]
            params.append((pname, default))
            if self.accept(")"):
                break
            self.expect(",")                     # trailing comma tolerated
        self.expect("{")
        body_start = self.i
        depth = 1
        while depth > 0 and self.peek() is not None:
            tok = self.next()
            if tok[1] == "{":
                depth += 1
            elif tok[1] == "}":
                depth -= 1
        body_end = self.i - 1                          # the closing '}'
        self.modules[name] = (params, body_start, body_end)

    def _inline_module(self, name):
        """Expand a call to a user module: a union holding one assign per
        bound parameter, then the module body re-parsed as its children."""
        params, body_start, body_end = self.modules[name]
        positional, named = self._arguments()
        inst = CadNode("union", name)
        outer_scope = self.scope                      # bound params shadow
        self.scope = dict(outer_scope)                # the enclosing scope
        for idx, (pname, default) in enumerate(params):
            if idx < len(positional):
                value = positional[idx]
            elif pname in named:
                value = named[pname]
            else:
                value = default
            source = _arg_source(value)
            inst.add(CadNode("assign", f"{pname} =",
                             dict(variable=pname, value=source)))
            try:                                      # so the body can use
                self.scope[pname] = expr.evaluate(source, self.scope)
            except Exception:
                pass
        saved = self.i                                # re-parse the body
        self.i = body_start
        while self.i < body_end:
            child = self.parse_statement()
            if child is not None:
                inst.add(child)
        self.i = saved
        self.scope = outer_scope                      # restore
        self.accept(";")                              # end of the call
        return inst

    def _skip_call_statement(self):
        """Skip the arg list + attached statement of an unknown call."""
        self._arguments()
        token = self.peek()
        if token is None or self.accept(";"):
            return
        if token[1] == "{":
            depth = 0
            while self.peek() is not None:
                tok = self.next()
                if tok[1] == "{":
                    depth += 1
                elif tok[1] == "}":
                    depth -= 1
                    if depth == 0:
                        return
        else:
            self.parse_statement()

    # ----------------------------------------------------------- calls
    def _parse_call(self):
        name = self.next()[1]
        if name in self.modules and name not in _BUILDERS:
            return self._inline_module(name)
        builder = _BUILDERS.get(name)
        if builder is None:
            self.warn(f"unsupported call '{name}' skipped")
            self._skip_call_statement()
            return None
        positional, named = self._arguments()
        node = builder(self, positional, named)
        if node is None:
            # builder consumed the call but produced nothing
            if not self.accept(";"):
                pass
            return None
        if node.is_container():
            self._children_into(node)
            node = _fold_container(node) or node
        else:
            self.accept(";")
        return node


def _literal(value) -> str:
    """Serialise a concrete number/bool/vector as an OpenSCAD literal
    expression string (so an assign carries no reference to user
    functions or other variables)."""
    from .model import fmt
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return fmt(float(value))
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_literal(v) for v in value) + "]"
    return str(value)


def _arg_source(value) -> str:
    """A module argument (float, expression string, or vector list) as an
    expression source string for the bound-parameter assign node."""
    from .model import fmt
    if value is None:
        return "0"
    if isinstance(value, list):
        return "[" + ", ".join(_arg_source(v) for v in value) + "]"
    if isinstance(value, str):
        return value
    return fmt(value)


def _unquote(literal: str) -> str:
    return literal[1:-1].replace('\\"', '"').replace("\\\\", "\\")


def _num(value, default=0.0):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return value if isinstance(value, str) else default


def _get(positional, named, index, *names, default=None):
    for name in names:
        if name in named:
            return named[name]
    if index is not None and index < len(positional):
        return positional[index]
    return default


def _radius(positional, named, default):
    d = _get(positional, named, None, "d")
    if d is not None:
        if isinstance(d, (int, float)):
            return float(d) / 2.0
        return f"({d}) / 2"
    r = _get(positional, named, 0, "r", default=default)
    return _num(r, default)


# builder(parser, positional, named) -> CadNode | None

def _b_circle(parser, positional, named):
    params = dict(x=0.0, y=0.0,
                  radius=_radius(positional, named, 10.0),
                  segments=int(_num(named.get("$fn", 64), 64) or 64))
    return CadNode("circle", "Circle", params)


def _b_square(parser, positional, named):
    size = _get(positional, named, 0, "size", default=10.0)
    if isinstance(size, list):
        width, height = (size + [10.0])[:2]
    else:
        width = height = size
    params = dict(x=0.0, y=0.0, width=_num(width, 10.0),
                  height=_num(height, 10.0))
    if named.get("center"):
        if isinstance(width, (int, float)) and \
                isinstance(height, (int, float)):
            params["x"], params["y"] = -width / 2.0, -height / 2.0
        else:
            parser.warn("square(center=true) with expression size "
                        "imported uncentred")
    return CadNode("rect", "Rectangle", params)


def _b_polygon(parser, positional, named):
    raw = _get(positional, named, 0, "points", default=None)
    if "paths" in named:
        parser.warn("polygon paths= ignored (single outline assumed)")
    pts = parser.resolve_points(raw)
    if pts is None:
        parser.warn("polygon points could not be resolved — "
                    "placeholder triangle used")
        pts = [[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]]
    return CadNode("polygon", "Polygon",
                   dict(x=0.0, y=0.0, points=pts))


def _b_text(parser, positional, named):
    return CadNode("text", "Text", dict(
        x=0.0, y=0.0,
        text=str(_get(positional, named, 0, "text", default="text")),
        size=_num(_get(positional, named, 1, "size", default=10.0),
                  10.0)))


def _b_cube(parser, positional, named):
    size = _get(positional, named, 0, "size", default=10.0)
    if isinstance(size, list):
        w, d, h = (size + [10.0, 10.0])[:3]
        w, d, h = _num(w, 10.0), _num(d, 10.0), _num(h, 10.0)
    elif isinstance(size, str):
        # a variable/expression — could be scalar or a vector; the
        # graceful .x/.y/.z accessors read a scalar as [s, s, s]
        w, d, h = f"({size}).x", f"({size}).y", f"({size}).z"
    else:
        w = d = h = _num(size, 10.0)
    return CadNode("cube", "Cube", dict(
        x=0.0, y=0.0, z=0.0, width=w, depth=d, height=h,
        center=bool(named.get("center", False))))


def _b_sphere(parser, positional, named):
    return CadNode("sphere", "Sphere", dict(
        x=0.0, y=0.0, z=0.0,
        radius=_radius(positional, named, 10.0),
        segments=int(_num(named.get("$fn", 48), 48) or 48)))


def _b_cylinder(parser, positional, named):
    r = _get(positional, named, None, "r")
    d = _get(positional, named, None, "d")
    r1 = _get(positional, named, None, "r1")
    r2 = _get(positional, named, None, "r2")
    d1 = _get(positional, named, None, "d1")
    d2 = _get(positional, named, None, "d2")

    def half(v):
        if isinstance(v, (int, float)):
            return float(v) / 2.0
        return f"({v}) / 2"
    if r1 is None and len(positional) > 1:
        r1 = positional[1]                       # cylinder(h, r1, r2)
    if r2 is None and len(positional) > 2:
        r2 = positional[2]
    bottom = r1 if r1 is not None else (
        half(d1) if d1 is not None else (
            r if r is not None else (half(d) if d is not None else 5.0)))
    top = r2 if r2 is not None else (
        half(d2) if d2 is not None else (
            r if r is not None else (half(d) if d is not None else 5.0)))
    return CadNode("cylinder", "Cylinder", dict(
        x=0.0, y=0.0, z=0.0,
        height=_num(_get(positional, named, 0, "h", default=10.0), 10.0),
        radius_bottom=_num(bottom, 5.0), radius_top=_num(top, 5.0),
        segments=int(_num(named.get("$fn", 64), 64) or 64),
        center=bool(named.get("center", False))))


def _vector3(positional, named, default=0.0):
    v = _get(positional, named, 0, "v", default=[default] * 3)
    if not isinstance(v, list):
        return [v, v, v], True                  # scalar
    v = list(v) + [default] * (3 - len(v))
    return v[:3], False


def _b_translate(parser, positional, named):
    v, _scalar = _vector3(positional, named)
    return CadNode("translate", "Translate",
                   dict(x=_num(v[0]), y=_num(v[1]), z=_num(v[2])))


def _b_rotate(parser, positional, named):
    v = _get(positional, named, 0, "a", default=[0.0, 0.0, 0.0])
    if not isinstance(v, list):
        v = [0.0, 0.0, v]                       # rotate(45) is about Z
    v = list(v) + [0.0] * (3 - len(v))
    return CadNode("rotate", "Rotate",
                   dict(x=_num(v[0]), y=_num(v[1]), z=_num(v[2])))


def _b_scale(parser, positional, named):
    v, _ = _vector3(positional, named, 1.0)
    return CadNode("scale", "Scale",
                   dict(x=_num(v[0], 1.0), y=_num(v[1], 1.0),
                        z=_num(v[2], 1.0)))


def _b_mirror(parser, positional, named):
    v, _ = _vector3(positional, named)
    return CadNode("mirror", "Mirror",
                   dict(x=_num(v[0]), y=_num(v[1]), z=_num(v[2])))


def _b_linear_extrude(parser, positional, named):
    return CadNode("linear_extrude", "Linear extrude", dict(
        height=_num(_get(positional, named, 0, "height", default=10.0),
                    10.0),
        twist=_num(named.get("twist", 0.0)),
        scale=_num(named.get("scale", 1.0), 1.0),
        center=bool(named.get("center", False)),
        segments=int(_num(named.get("slices", 0), 0) or 0)))


def _b_rotate_extrude(parser, positional, named):
    return CadNode("rotate_extrude", "Rotate extrude", dict(
        angle=_num(named.get("angle", 360.0), 360.0),
        segments=int(_num(named.get("$fn", 96), 96) or 96)))


def _b_offset(parser, positional, named):
    if "delta" in named:
        return CadNode("offset", "Offset", dict(
            radius=_num(named["delta"]),
            chamfer=bool(named.get("chamfer", False))))
    return CadNode("offset", "Offset", dict(
        radius=_num(_get(positional, named, 0, "r", default=1.0), 1.0),
        chamfer=False))


def _b_projection(parser, positional, named):
    return CadNode("projection", "Projection",
                   dict(cut=bool(named.get("cut", False))))


def _b_import(parser, positional, named):
    path = _get(positional, named, 0, "file", default="")
    return CadNode("stl_import", "Import STL",
                   dict(path=str(path), x=0.0, y=0.0, z=0.0))


def _b_color(parser, positional, named):
    value = _get(positional, named, 0, "c", default="#4a90d9")
    alpha = _num(_get(positional, named, 1, "alpha", default=1.0), 1.0)
    if isinstance(value, list):
        rgb = [max(0.0, min(1.0, _num(v, 0.0))) for v in value[:3]]
        while len(rgb) < 3:
            rgb.append(0.0)
        if len(value) > 3:
            alpha = _num(value[3], 1.0)
        value = "#%02x%02x%02x" % tuple(int(round(c * 255))
                                        for c in rgb)
    return CadNode("color", "Color",
                   dict(color=str(value), alpha=alpha))


def _simple(type_, label):
    return lambda parser, positional, named: CadNode(type_, label)


_BUILDERS = {
    "circle": _b_circle, "square": _b_square, "polygon": _b_polygon,
    "text": _b_text, "cube": _b_cube, "sphere": _b_sphere,
    "cylinder": _b_cylinder,
    "translate": _b_translate, "rotate": _b_rotate,
    "scale": _b_scale, "mirror": _b_mirror,
    "linear_extrude": _b_linear_extrude,
    "rotate_extrude": _b_rotate_extrude,
    "offset": _b_offset, "projection": _b_projection,
    "import": _b_import, "color": _b_color,
    "union": _simple("union", "Group"),
    "difference": _simple("difference", "Difference"),
    "intersection": _simple("intersection", "Intersection"),
    "hull": _simple("hull", "Hull"),
    "minkowski": _simple("minkowski", "Minkowski"),
}

#: shape types whose x/y(/z) a wrapping translate can be folded into.
_FOLDABLE = {"circle", "rect", "polygon", "text", "cube", "sphere",
             "cylinder", "stl_import"}


def _fold_container(node: CadNode):
    """Simplify freshly-parsed containers:

    - translate wrapping one plain shape -> shape with x/y/z set;
    - hull of exactly two equal circles -> a line node (that is how
      KherveCAD compiles lines).
    """
    if node.type == "translate" and len(node.children) == 1:
        child = node.children[0]
        if child.type in _FOLDABLE and \
                _is_zero(child.params.get("x")) and \
                _is_zero(child.params.get("y")) and \
                _is_zero(child.params.get("z", 0.0)):
            child.params["x"] = node.params["x"]
            child.params["y"] = node.params["y"]
            if "z" in child.params:
                child.params["z"] = node.params["z"]
            elif not _is_zero(node.params.get("z", 0.0)):
                return None                     # 2D shape lifted in z
            node.remove(child)
            child.visible = node.visible and child.visible
            return child
    if node.type == "hull" and len(node.children) == 2 and \
            all(c.type == "circle" for c in node.children):
        a, b = node.children
        ra, rb = a.params.get("radius"), b.params.get("radius")
        if ra == rb and isinstance(ra, (int, float)):
            line = CadNode("line", "Line", dict(
                x1=a.params["x"], y1=a.params["y"],
                x2=b.params["x"], y2=b.params["y"],
                width=2.0 * ra))
            line.visible = node.visible
            return line
    return None


def _is_zero(value):
    return isinstance(value, (int, float)) and abs(value) < 1e-12


# ------------------------------------------------------------- API

#: Leaf node types that actually emit geometry. A container built only
#: from other things (assignments, empty operations) produces nothing.
_GEOMETRY_LEAVES = {
    "cube", "sphere", "cylinder", "stl_import", "circle", "rect",
    "polygon", "text", "line", "scad_raw", "reference",
}
#: Container/operation types that are meaningless when they wrap no
#: geometry — pruned on import so a skipped ``children()`` does not leave
#: an empty red node behind.
_PRUNE_WHEN_DEAD = {
    "translate", "rotate", "scale", "mirror", "offset", "color",
    "linear_extrude", "rotate_extrude", "projection",
    "union", "difference", "intersection", "hull", "minkowski",
    "if_else",
}


def _has_geometry(node) -> bool:
    if node.type in _GEOMETRY_LEAVES:
        return True
    return any(_has_geometry(child) for child in node.children)


def _prune_dead(root) -> None:
    """Drop operation/boolean nodes that end up wrapping no geometry —
    e.g. a module whose body was a bare ``children()`` we could not
    inline. Cascades bottom-up so a whole dead branch disappears rather
    than surfacing as empty red nodes."""
    changed = True
    while changed:
        changed = False
        for node in list(root.walk()):
            parent = node.parent
            if parent is None or node.type not in _PRUNE_WHEN_DEAD:
                continue
            if not _has_geometry(node):
                parent.remove(node)
                changed = True


def parse_scad(text: str):
    """Parse *text* into (root CadNode, warnings list)."""
    parser = Parser(text)
    root = parser.parse_program()
    _prune_dead(root)
    return root, parser.warnings


def import_scad(model, path: str):
    """Load a .scad file into *model*, replacing the document.
    Returns the list of warnings."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    root, warnings = parse_scad(text)
    model.root = root
    model.group_variables()               # gather loose top-level vars
    model.structure_changed.emit()
    return warnings
