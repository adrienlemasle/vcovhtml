# -*- coding: utf-8 -*-
"""Parse Verilator SystemC::Coverage-3 .dat files into Point objects.

A .dat file is a sequence of lines::

    # SystemC::Coverage-3
    C '<name>' <count>

where <name> is a run of field pairs, each ``<0x01><key><0x02><value>``.
<value> is escaped: '%' -> %25, '"' -> %22, and any non-printable byte ->
%HH (two upper-case hex digits).  See include/verilated_cov_key.h
(VerilatedCovKey::escape/unescape) and src/VlcPoint.h (keyExtract).

The hit <count> follows the *last* "' " in the line, because a value may
itself contain a "'" (e.g. a module parameter spec "#(8'sh1)").  This
mirrors VlcTop::readCoverage, which uses line.rfind("' ").

Read byte-safe as latin-1 so the control characters survive intact.
"""
from __future__ import annotations

from dataclasses import dataclass, field


def _hexval(c: str) -> int:
    if "0" <= c <= "9":
        return ord(c) - 0x30
    if "A" <= c <= "F":
        return ord(c) - 0x37
    return -1


def unescape(text: str) -> str:
    """Undo VerilatedCovKey::escape: decode %HH that form a printable char."""
    if "%" not in text:
        return text
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "%" and i + 2 < n:
            high = _hexval(text[i + 1])
            low = -1 if high < 0 else _hexval(text[i + 2])
            c = -1 if low < 0 else high * 16 + low
            if 32 <= c < 127:  # printable
                out.append(chr(c))
                i += 3
                continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _decode_fields(compact: str) -> dict:
    """Split the compact field string into {key: unescaped_value}.

    Fields are delimited by 0x01; within a field, key and value by 0x02.
    A value never holds a raw 0x01 (it is escaped), so splitting on 0x01 is
    safe.  Mirrors VlcPoint::keyExtract.
    """
    fields = {}
    for part in compact.split("\x01"):
        key, _, val = part.partition("\x02")
        if not _:
            continue
        fields[key] = unescape(val)
    return fields


# field key (file) -> (attribute, is_int)
_FIELD_MAP = {
    "n": ("n", True), "f": ("f", False), "S": ("S", False),
    "P": ("P", True), "s": ("s", True), "t": ("t", False),
    "B": ("B", False), "Bt": ("Bt", False), "o": ("o", False),
    "C": ("C", True), "Cb": ("Cb", False),
    "Ff": ("Ff", False), "Fg": ("Fg", False), "Ft": ("Ft", False),
    "Fv": ("Fv", False),
    "Gw": ("Gw", True), "w": ("w", True),
    "h": ("h", False), "l": ("l", True),
}


def _as_int(val, default=0):
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


@dataclass
class Point:
    """One coverage record.  Attribute names match the file's short keys."""

    name: str = ""            # raw compact field string (kept for re-writing)
    count: int = 0            # hits
    # common
    t: str = ""               # type
    f: str = ""               # filename
    l: int = 0                # line
    n: int = 0                # column
    S: str = ""               # covered lines (comma list)
    P: int = 0                # per_instance
    s: int = 0                # thresh / at_least
    page: str = ""            # v_<type>/<design-unit>
    h: str = ""               # hierarchy path
    o: str = ""               # comment (textual description)
    # covergroup
    B: str = ""               # bin name
    Bt: str = ""              # bin_type (ignore/illegal/default)
    C: int = 0                # is_cross
    Cb: str = ""              # cross bins
    Gw: int = 0               # group weight
    w: int = 0                # item weight
    # fsm
    Fv: str = ""              # fsm var
    Ff: str = ""              # from state
    Ft: str = ""              # to state
    Fg: str = ""              # tag

    def type(self) -> str:
        return self.t or "point"

    def covered(self) -> bool:
        """Covered iff hits reach the threshold (1 when none is written)."""
        need = self.s if self.s > 0 else 1
        return self.count >= need

    def du_name(self) -> str:
        """The design-unit part of a page: 'v_<type>/<du>' -> '<du>'.
        Memoized: ``page`` is set once at parse time."""
        v = getattr(self, "_du", None)
        if v is None:
            v = self.page.split("/", 1)[1] if (self.page and "/" in self.page) else self.h
            self._du = v
        return v


def parse_dat(path: str, types=None):
    """Parse a .dat file.  Returns (points, malformed_count).

    ``types`` is an optional set of type strings to keep (e.g. {"line"});
    None keeps all.
    """
    points = []
    malformed = 0
    with open(path, "r", encoding="latin-1", newline="") as f:
        first = True
        for raw in f:
            line = raw.rstrip("\n").rstrip("\r")
            if first:
                first = False
                if line.startswith("# SystemC::Coverage"):
                    continue
            if not line or line[0] != "C":
                continue
            idx = line.rfind("' ")
            if idx < 3:
                malformed += 1
                continue
            try:
                count = int(line[idx + 2:].strip())
            except ValueError:
                malformed += 1
                continue
            p = Point(name=line[3:idx], count=count)
            for key, val in _decode_fields(line[3:idx]).items():
                if key == "page":
                    p.page = val
                    continue
                if key in _FIELD_MAP:
                    attr, is_int = _FIELD_MAP[key]
                    setattr(p, attr, _as_int(val) if is_int else val)
            if types is not None and p.t not in types:
                continue
            points.append(p)
    return points, malformed
