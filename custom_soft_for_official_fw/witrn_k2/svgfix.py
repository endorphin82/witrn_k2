"""Qt 6.x SVG export compatibility for pyqtgraph's SVGExporter.

Qt 6 emits SVG path data with close-path ``Z`` commands, whitespace-separated
tokens and other forms that pyqtgraph 0.14's strict ``letterX,Y`` parser cannot
handle (raises ``ValueError: not enough values to unpack``). This module
normalizes path data to absolute ``M``/``L``/``C`` commands before pyqtgraph
applies its coordinate correction, then patches the exporter in-place.
"""

from __future__ import annotations

import importlib
import re
import xml.dom.minidom as xml

_TOKEN_RE = re.compile(r"[A-Za-z]|[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


def _path_to_abs_mlc(d: str) -> str | None:
    """Convert SVG path data to absolute M/L/C pairs (pyqtgraph-parseable).

    Z becomes an L back to the subpath start, H/V become L, S/Q/T are
    converted to exact cubic form, A is approximated by L to its endpoint.
    Returns None if the path cannot be parsed.
    """
    tokens = _TOKEN_RE.findall(d)
    out: list[tuple[str, list[tuple[float, float]]]] = []
    i = 0
    cmd: str | None = None
    cur = (0.0, 0.0)
    sub = (0.0, 0.0)
    prev_c2: tuple[float, float] | None = None  # last cubic control point (for S)
    prev_q: tuple[float, float] | None = None  # last quadratic control point (for T)

    def take(n: int) -> list[float] | None:
        nonlocal i
        vals: list[float] = []
        for _ in range(n):
            if i >= len(tokens) or tokens[i].isalpha():
                return None
            vals.append(float(tokens[i]))
            i += 1
        return vals

    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd.upper() == "Z":
                out.append(("L", [sub]))
                cur = sub
                prev_c2 = prev_q = None
                continue
        if cmd is None:
            return None
        rel = cmd.islower()
        kind = cmd.upper()
        if kind == "M":
            v = take(2)
            if v is None:
                return None
            x, y = v
            if rel:
                x += cur[0]
                y += cur[1]
            cur = (x, y)
            sub = cur
            out.append(("M", [cur]))
            cmd = "l" if rel else "L"
            prev_c2 = prev_q = None
        elif kind == "L":
            v = take(2)
            if v is None:
                return None
            x, y = v
            if rel:
                x += cur[0]
                y += cur[1]
            cur = (x, y)
            out.append(("L", [cur]))
            prev_c2 = prev_q = None
        elif kind == "H":
            v = take(1)
            if v is None:
                return None
            x = v[0] + (cur[0] if rel else 0.0)
            cur = (x, cur[1])
            out.append(("L", [cur]))
            prev_c2 = prev_q = None
        elif kind == "V":
            v = take(1)
            if v is None:
                return None
            y = v[0] + (cur[1] if rel else 0.0)
            cur = (cur[0], y)
            out.append(("L", [cur]))
            prev_c2 = prev_q = None
        elif kind == "C":
            v = take(6)
            if v is None:
                return None
            pts = []
            for k in range(0, 6, 2):
                x, y = v[k], v[k + 1]
                if rel:
                    x += cur[0]
                    y += cur[1]
                pts.append((x, y))
            cur = pts[-1]
            out.append(("C", pts))
            prev_c2 = pts[1]
            prev_q = None
        elif kind == "S":
            v = take(4)
            if v is None:
                return None
            pts = []
            for k in range(0, 4, 2):
                x, y = v[k], v[k + 1]
                if rel:
                    x += cur[0]
                    y += cur[1]
                pts.append((x, y))
            cp1 = (
                (2 * cur[0] - prev_c2[0], 2 * cur[1] - prev_c2[1])
                if prev_c2
                else cur
            )
            out.append(("C", [cp1, pts[0], pts[1]]))
            cur = pts[1]
            prev_c2 = pts[1]
            prev_q = None
        elif kind == "Q":
            v = take(4)
            if v is None:
                return None
            pts = []
            for k in range(0, 4, 2):
                x, y = v[k], v[k + 1]
                if rel:
                    x += cur[0]
                    y += cur[1]
                pts.append((x, y))
            cp, end = pts
            cp1 = (cur[0] + 2 / 3 * (cp[0] - cur[0]), cur[1] + 2 / 3 * (cp[1] - cur[1]))
            cp2 = (end[0] + 2 / 3 * (cp[0] - end[0]), end[1] + 2 / 3 * (cp[1] - end[1]))
            out.append(("C", [cp1, cp2, end]))
            cur = end
            prev_q = cp
            prev_c2 = None
        elif kind == "T":
            v = take(2)
            if v is None:
                return None
            x, y = v
            if rel:
                x += cur[0]
                y += cur[1]
            cp = (
                (2 * cur[0] - prev_q[0], 2 * cur[1] - prev_q[1]) if prev_q else cur
            )
            end = (x, y)
            cp1 = (cur[0] + 2 / 3 * (cp[0] - cur[0]), cur[1] + 2 / 3 * (cp[1] - cur[1]))
            cp2 = (end[0] + 2 / 3 * (cp[0] - end[0]), end[1] + 2 / 3 * (cp[1] - end[1]))
            out.append(("C", [cp1, cp2, end]))
            cur = end
            prev_q = cp
            prev_c2 = None
        elif kind == "A":
            v = take(7)
            if v is None:
                return None
            x, y = v[5], v[6]
            if rel:
                x += cur[0]
                y += cur[1]
            cur = (x, y)
            out.append(("L", [cur]))
            prev_c2 = prev_q = None
        else:
            return None

    parts: list[str] = []
    for letter, pts in out:
        parts.append(f"{letter}{pts[0][0]},{pts[0][1]}")
        for p in pts[1:]:
            parts.append(f"{p[0]},{p[1]}")
    return " ".join(parts)


def _normalize_node_paths(node) -> None:
    if isinstance(node, xml.Element) and node.tagName == "path":
        d = node.getAttribute("d")
        if d and d.strip():
            nd = _path_to_abs_mlc(d)
            if nd is not None:
                node.setAttribute("d", nd)
    children = getattr(node, "childNodes", None)
    if children:
        for ch in list(children):
            _normalize_node_paths(ch)


def patch_pyqtgraph_svg_export() -> None:
    """Patch pyqtgraph's SVGExporter so Qt 6 path data doesn't crash it."""
    mod = importlib.import_module("pyqtgraph.exporters.SVGExporter")
    if getattr(mod, "_witrn_patched", False):
        return
    orig = mod.correctCoordinates

    def correctCoordinates(node, defs, item, options=None):
        _normalize_node_paths(node)
        orig(node, defs, item, options)

    mod.correctCoordinates = correctCoordinates
    mod._witrn_patched = True
