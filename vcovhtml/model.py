# -*- coding: utf-8 -*-
"""Build the report model from a list of Points.

Computations (mirroring src/VlcTop.cpp):

* Code coverage (line, branch, expr, toggle, fsm_state, fsm_arc, and any other
  non-covergroup type): a per-instance hierarchy tree keyed by each point's
  ``h`` field, and a per-design-unit (module) roll-up keyed by each point's
  design unit.  A point is covered when its hits reach its threshold.

* Functional coverage (covergroup): the covergroup -> coverpoint -> bin
  weighted tally (covergroups / itemTally / groupTally / groupsTallies).

Design units:
  Verilator names each *distinct parameterization* of a module with a
  suffixed / param-spec design unit so the generated C++ stays correct:
  ``<base>__pi<hex>``, ``<base>__PB<n>``, ``<base>#(<params>)``, or any other
  ``<base>__<marker>``.  ``module_base`` strips all of these (``__``,
  ``#(...)`` and dotted covergroup parts) to the base module, so every variant
  of one module groups under a single row.  Verilator's SystemC runtime units
  (``std``, ``std::process``, ``std::semaphore``, ...) are dropped via
  ``is_internal_unit``.

Parametrization variants:
  A .dat merged from separately-built parametrizations of a module reports
  the same source record once per variant: identical in every field except
  the design unit (the page's variant name, and the unit-anchored prefix of
  a covergroup's hierarchy).  ``merge_parametrized_points`` consolidates
  records that share both their identity and their instance scope, summing
  counts (the union semantics of ``verilator_coverage --merge``), so each
  record is reported once instead of once per parametrization.  Records at
  different instances stay apart, preserving per-instance granularity.

Generate-for iterations:
  A point inside named begins reports the begin path in its ``h`` field,
  with the levels joined by ``__DOT__`` and the index of each generate-for
  iteration appended as ``__BRA__<n>__KET__`` (Verilator escapes the
  brackets and the dots, which the instance-path prefix and the record
  name use).  ``unescape_hier`` decodes them, so the per-instance tree
  carries one node per begin level and every view can distinguish the
  iterations of a generate-for loop.
"""
from __future__ import annotations

import re
from collections import OrderedDict

from .covdat import Point, _decode_fields

# Verilator SystemC-runtime design units to hide from the report.
_INTERNAL_LAST = {
    "std", "process", "semaphore", "condition", "event",
    "monitor", "time", "queue", "self",
}


def key_number(value) -> int:
    """int(value), or 1 when the field is absent/empty.  (C++ keyNumber.)"""
    if value is None:
        value = ""
    value = str(value).strip()
    if not value:
        return 1
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1


# ---------------------------------------------------------------------------
# splitHier  (port of src/VlcTop.cpp:115)
# ---------------------------------------------------------------------------

def _quoted_end(hier: str, pos: int) -> int:
    """Index of the closing '"' of the string opening at ``pos`` (-1 if none)."""
    n = len(hier)
    i = pos + 1
    while i < n:
        if hier[i] == "\\":
            i += 2
            continue
        if hier[i] == '"':
            return i
        i += 1
    return -1


def _splitHier(hier: str) -> list:
    parts = []
    if not hier:
        return parts
    start = 0
    depth = 0
    pos = 0
    n = len(hier)
    while pos < n:
        c = hier[pos]
        if c == "\\":
            nxt = hier.find(" ", pos)
            pos = nxt if nxt != -1 else n
            continue
        if not depth and hier.startswith("#(", pos):
            depth = 1
            pos += 1
        elif not depth and c == ".":
            parts.append(hier[start:pos])
            start = pos + 1
        elif depth and c == '"':
            end = _quoted_end(hier, pos)
            pos = end if end != -1 else n
            continue
        elif depth and c == "(":
            depth += 1
        elif depth and c == ")":
            depth -= 1
        pos += 1
    if depth:  # Unbalanced: fall back to a plain dot split (C++ behaviour)
        parts = []
        start = 0
        for dot in [i for i, ch in enumerate(hier) if ch == "."]:
            parts.append(hier[start:dot])
            start = dot + 1
    parts.append(hier[start:])
    return parts


_HIER_MEMO = {}


def splitHier(hier: str) -> list:
    """Memoized wrapper around ``_splitHier``.

    ``_splitHier`` is pure in its argument, and a coverage .dat holds many
    points per instance, so each string is parsed once and the segment list
    is reused by every consumer (internal-unit filter, code tree, ...).
    """
    v = _HIER_MEMO.get(hier)
    if v is None:
        if len(_HIER_MEMO) > 8192:
            _HIER_MEMO.clear()
        v = _splitHier(hier)
        _HIER_MEMO[hier] = v
    return v


def is_collapsed_hier(hier: str) -> bool:
    return ("*" in hier) or ("?" in hier)


def unescape_hier(hier: str) -> str:
    """Undo the markers Verilator writes into a point's ``h`` field.

    The levels of a begin path are joined by ``__DOT__`` and a
    generate-for iteration appends its index as ``__BRA__<n>__KET__``
    (never a literal ``.``/``[``, which the instance-path prefix and the
    record name use).  Decoding restores the readable form:
    ``g_foo__BRA__3__KET__`` -> ``g_foo[3]``,
    ``g_a__DOT__g_b`` -> ``g_a.g_b``.  A string without markers is
    returned unchanged.
    """
    if "__" not in hier:
        return hier
    return (hier.replace("__DOT__", ".")
                .replace("__BRA__", "[")
                .replace("__KET__", "]"))


def iter_sort_key(hier: str):
    """Sort key ordering generate-for iterations by numeric index.

    Each dot-segment of a decoded ``h`` may carry a trailing ``[n]``
    (or ``[*]`` for a combined instance).  The key is the sequence of
    those indexes in path order, so ``g[10]`` sorts after ``g[9]``
    instead of between ``g[1]`` and ``g[2]``.  A segment without a
    bracket sorts before a bracketed one at the same level, and
    ``[*]`` sorts last.
    """
    key = []
    for seg in (hier or "").split("."):
        m = re.match(r"^(.*?)\[(\*|\d+)\]$", seg)
        if m:
            key.append((1, 10 ** 9 if m.group(2) == "*" else int(m.group(2))))
        else:
            key.append((0, 0))
    return key


# ---------------------------------------------------------------------------
# Design-unit identity
# ---------------------------------------------------------------------------

def module_base(du: str) -> str:
    """Reduce a design unit to its base module name.

    Strips a parameter spec ``#(...)`` (and anything after the first ``.``),
    and any ``__``-suffixed variant marker, so that all of Verilator's
    variants of one module -- ``<base>__pi<hex>``, ``<base>__PB<n>``,
    ``<base>#(<params>)`` -- collapse under the bare base name.
    """
    if not du:
        return du
    n = du.split("#", 1)[0]   # drop parameter spec
    n = n.split(".", 1)[0]    # drop .cg_… (covergroup) / dotted part
    n = n.split("__", 1)[0]   # drop any __variant marker
    return n


def is_internal_unit(du: str) -> bool:
    """True for Verilator SystemC-runtime design units (``std``, ``std::process``,
    ``std::semaphore``, and similar), which are not user modules."""
    if not du:
        return False
    n = du.split("#", 1)[0]
    parts = n.split("::")
    if "std" in parts:
        return True
    last = parts[-1].split(".", 1)[0].split("__", 1)[0]
    return last in _INTERNAL_LAST


def is_internal_point(p: Point) -> bool:
    """True when a point belongs to an internal runtime unit, by its design
    unit or by any segment of its instance path."""
    if is_internal_unit(p.du_name()):
        return True
    for seg in splitHier(p.h):
        if is_internal_unit(seg):
            return True
    return False

def point_identity(p: Point) -> tuple:
    """A record's identity independent of its design unit.

    Every field except ``page`` (which carries the unit's name, including
    any parametrization marker) and ``h`` (the instance scope).  Two
    records for the same source location in the same module -- including
    different parametrizations of that module -- share an identity.
    """
    return (p.t, p.f, p.l, p.n, p.S, p.P, p.s, p.o, p.B, p.Bt, p.C, p.Cb,
            p.Gw, p.w, p.Fv, p.Ff, p.Ft, p.Fg)


def point_scope(p: Point) -> str:
    """The instance scope of a record.

    Code coverage: the full hierarchy.  Covergroups: the hierarchy minus
    its first segment, which is the design unit itself and therefore
    differs between parametrizations of one module.
    """
    h = p.h
    if p.t == "covergroup" and "." in h:
        h = h.split(".", 1)[1]
    return h


def merge_parametrized_points(points) -> list:
    """Consolidate records that share both their identity and their scope.

    A .dat merged from several parametrizations of one module contains the
    same record once per parametrization (differing only in the design
    unit).  Summing their counts -- the union semantics of
    `verilator_coverage --merge`: covered when hit in any variant -- makes
    both the per-instance and per-design-unit views report each record
    once.  Records at different hierarchies (distinct instances of a
    module) are left apart, preserving per-instance granularity.
    """
    acc = {}
    order = []
    for p in points:
        key = (point_identity(p), point_scope(p))
        q = acc.get(key)
        if q is None:
            acc[key] = p
            order.append(key)
        else:
            q.count += p.count
    return [acc[k] for k in order]


# ---------------------------------------------------------------------------
# Code coverage hierarchy tree
# ---------------------------------------------------------------------------

class Node:
    def __init__(self, name: str, full: str):
        self.name = name
        self.full = full
        self.depth = 0
        self.children = OrderedDict()
        self.points = []      # code points terminating exactly at this node
        self.tally = {}       # type -> (hit, total)  (filled by code_tallies)

    def child(self, name: str) -> "Node":
        if name not in self.children:
            full = (self.full + "." + name) if self.full else name
            self.children[name] = Node(name, full)
        return self.children[name]


def build_code_tree(points) -> tuple:
    root = Node("", "")
    ordered = []
    for p in points:
        if p.t == "covergroup":
            continue
        if p.t and p.t not in ordered:
            ordered.append(p.t)
        if p.h:
            node = root
            # Decode the begin markers before splitting, so a nested
            # generate-for reports one node per level (g_a[0].g_b[1]).
            for seg in splitHier(unescape_hier(p.h)):
                node = node.child(seg)
            node.points.append(p)
        else:
            root.points.append(p)
    return root, ordered


def build_du(points) -> tuple:
    """Per-design-unit (module) code roll-up for the "per design unit" view.

    Grouped by ``module_base`` so every parameterized variant of a module
    collapses under one row.  Keys are ``<base>#<type>``; a point's module is
    the base of its design-unit part.
    """
    du = {}
    ordered = []
    for p in points:
        if p.t == "covergroup":
            continue
        if p.t and p.t not in ordered:
            ordered.append(p.t)
        base = module_base(p.du_name())
        if not base:
            continue
        key = base + "#" + p.t
        h, tot = du.get(key, (0, 0))
        du[key] = (h + (1 if p.count > 0 else 0), tot + 1)
    return du, ordered


def code_tallies(node: Node) -> None:
    """Fill node.tally (and every descendant's) with hit/total per type."""
    def rec(n: Node) -> dict:
        n.depth = 0
        res = {}
        for p in n.points:
            t = p.t or "point"
            h, tot = res.get(t, (0, 0))
            res[t] = (h + (1 if p.count > 0 else 0), tot + 1)
        for c in n.children.values():
            cr = rec(c)
            for t, (h, tot) in cr.items():
                hh, tt = res.get(t, (0, 0))
                res[t] = (hh + h, tt + tot)
        n.tally = res
        return res
    rec(node)


def code_tallies_depth(node: Node, parent_depth: int = 0) -> None:
    node.depth = parent_depth
    for c in node.children.values():
        code_tallies_depth(c, parent_depth + 1)


# ---------------------------------------------------------------------------
# Functional coverage (covergroup) weighted tally
# ---------------------------------------------------------------------------

def _is_score_field(field: str) -> bool:
    for k in ("s", "w", "Gw"):
        if field.startswith("\x01" + k + "\x02"):
            return True
    return False


def bin_identity(name: str) -> str:
    """The record name minus the score fields, which identifies a bin."""
    out = []
    start = 0
    n = len(name)
    while start < n:
        end = name.find("\x01", start + 1)
        if end == -1:
            end = n
        field = name[start:end]
        if not _is_score_field(field):
            out.append(field)
        start = end
    return "".join(out)


class CgBin:
    def __init__(self):
        self.name = ""
        self.count = 0
        self.atLeast = 1
        self.binType = ""

    def add(self, name: str, count: int, atLeast: int, binType: str = "") -> None:
        self.name = name
        self.count += count
        self.atLeast = max(self.atLeast, atLeast)
        self.binType = binType

    def covered(self) -> bool:
        return self.count >= self.atLeast


class CgItem:
    def __init__(self, name: str):
        self.name = name
        self.weight = 1
        self.bins = OrderedDict()

    def add_weight(self, w: int) -> None:
        self.weight = max(self.weight, w)

    def new_bin(self, ident: str) -> CgBin:
        b = self.bins.get(ident)
        if b is None:
            b = CgBin()
            self.bins[ident] = b
        return b


class CgGroup:
    def __init__(self, page: str):
        self.page = page
        self.hier = ""
        self.weight = 1
        self.items = OrderedDict()

    def add_record(self, name: str, weight: int) -> None:
        self.hier = name
        self.weight = max(self.weight, weight)

    def new_item(self, name: str) -> CgItem:
        it = self.items.get(name)
        if it is None:
            it = CgItem(name)
            self.items[name] = it
        return it


def build_covergroups(points) -> "OrderedDict[str, CgGroup]":
    groups = OrderedDict()
    for pt in points:
        if pt.t != "covergroup":
            continue
        fields = _decode_fields(pt.name)
        hier = pt.h
        bin_ = pt.B
        if not bin_ or len(bin_) >= len(hier):
            bin_ = hier.rsplit(".", 1)[-1] if "." in hier else hier
        cut = min(len(hier), len(bin_) + 1)
        itemHier = hier[:len(hier) - cut]
        group = groups.get(pt.page)
        if group is None:
            group = CgGroup(pt.page)
            groups[pt.page] = group
        cgname = itemHier.rsplit(".", 1)[0] if "." in itemHier else itemHier
        group.add_record(cgname, key_number(fields.get("Gw")))
        item = group.new_item(itemHier)
        item.add_weight(key_number(fields.get("w")))
        item.new_bin(bin_identity(pt.name)).add(bin_, pt.count,
                                                 key_number(fields.get("s")),
                                                 fields.get("Bt", ""))
    return groups


def covergroups_by_module(groups) -> "dict[str, list[CgGroup]]":
    """Group covergroups by their base module (so functional attaches to a
    module like line/branch, and internal runtime units are dropped)."""
    by = {}
    for page, g in groups.items():
        # The module is the base of the page's design-unit part (a covergroup
        # is <module>[.cg_...]).  g.hier is a full instance path whose first
        # dot segment is the top, so it must not be used for the module.
        du = page.split("/", 1)[1] if "/" in page else page
        base = module_base(du)
        if not base or is_internal_unit(du):
            continue
        by.setdefault(base, []).append(g)
    return by


def cg_item_tally(item: CgItem) -> dict:
    coverable = [b for b in item.bins.values() if not b.binType]
    hit = sum(1 for b in coverable if b.covered())
    total = len(coverable)
    score = (hit / total * 100.0) if total else (0.0 if item.weight else 100.0)
    illegalHit = sum(1 for b in item.bins.values()
                     if b.binType and b.count > 0)
    return {"hit": hit, "total": total, "score": score,
            "illegalHit": illegalHit}


def cg_group_tally(group: CgGroup) -> dict:
    hit = 0
    total = 0
    weighted = 0.0
    weights = 0.0
    item_scores = {}
    for name, item in group.items.items():
        it = cg_item_tally(item)
        item_scores[name] = it
        hit += it["hit"]
        total += it["total"]
        if not it["total"]:
            continue
        weighted += item.weight * it["score"]
        weights += item.weight
    score = (weighted / weights) if weights else (0.0 if group.weight else 100.0)
    return {"hit": hit, "total": total, "score": score, "items": item_scores}


def cg_groups_tally(group_list) -> dict:
    """Roll-up over many covergroups.  (C++ groupsTally.)

    A group contributes to the weighted total when it has an item that both
    has weight and bins (groupTally's contributesp == weights != 0).
    """
    hit = 0
    total = 0
    weighted = 0.0
    weights = 0.0
    any_weight = False
    scores = {}
    for g in group_list:
        gr = cg_group_tally(g)
        scores[g.page] = gr
        hit += gr["hit"]
        total += gr["total"]
        if g.weight:
            any_weight = True
        # contributes iff it has an item with weight and bins
        contributes = any(it.weight and it.bins for it in g.items.values())
        if not contributes:
            continue
        weighted += g.weight * gr["score"]
        weights += g.weight
    score = (weighted / weights) if weights else (0.0 if any_weight else 100.0)
    return {"hit": hit, "total": total, "score": score, "groups": scores}
