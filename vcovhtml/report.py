# -*- coding: utf-8 -*-
"""Build the JSON data island and assemble the self-contained HTML report."""
import json
import os

from . import __version__
from .covdat import Point
from .model import (
    build_code_tree,
    code_tallies,
    code_tallies_depth,
    build_du,
    build_covergroups,
    covergroups_by_module,
    cg_group_tally,
    cg_groups_tally,
    cg_item_tally,
    is_collapsed_hier,
    is_internal_point,
    merge_parametrized_points,
    module_base,
)
from .report_css import CSS
from .report_js import JS

# Display order for code-coverage type columns.
_CANON = ["line", "branch", "expr", "toggle", "fsm_state", "fsm_arc"]


def _point_json(p: Point) -> dict:
    hseg = p.h.split(".")[-1] if p.h else ""
    return {
        "t": p.t,
        "f": p.f,
        "l": p.l,
        "o": p.o,
        "h": hseg,
        "count": p.count,
        "s": p.s,
        "covered": p.covered(),
    }


def _entry(hit: int, total: int) -> dict:
    return {
        "hit": hit,
        "total": total,
        "score": (100.0 * hit / total) if total else None,
    }


def _combine_func(entries) -> dict:
    """Combine several functional roll-ups (sum hit/total, weighted score)."""
    entries = [e for e in entries if e]
    if not entries:
        return None
    hit = sum(e["hit"] for e in entries)
    total = sum(e["total"] for e in entries)
    wsum = sum(e["score"] * e["total"] for e in entries
               if e["score"] is not None and e["total"])
    wtot = sum(e["total"] for e in entries
               if e["score"] is not None and e["total"])
    score = (wsum / wtot) if wtot else None
    return {"hit": hit, "total": total, "score": score}


def _cg_item_json(item) -> dict:
    i = cg_item_tally(item)
    bins = [{
        "name": b.name,
        "count": b.count,
        "atLeast": b.atLeast,
        "covered": b.covered(),
    } for b in item.bins.values()]
    return {
        "name": item.name,
        "weight": item.weight,
        "hit": i["hit"],
        "total": i["total"],
        "score": i["score"],
        "bins": bins,
    }


def _cg_group_json(g) -> dict:
    gr = cg_group_tally(g)
    items = [_cg_item_json(it) for it in g.items.values()]
    return {
        "group": g.hier or g.page,
        "weight": g.weight,
        "hit": gr["hit"],
        "total": gr["total"],
        "score": gr["score"],
        "items": items,
    }


_MAX_SRC_FILE = 1 << 20  # 1 MiB; bigger files are never embedded


def fetch_source_lines(points, root):
    """Read the full referenced source files, if they resolve.

    The .dat stores each record's path (relative to where Verilator was
    run, or absolute) and line number -- no code.  Every distinct path
    that resolves under ``root`` and is at most ``_MAX_SRC_FILE`` bytes is
    read in one raw read, split into lines, and returned as a
    JSON-friendly map  path -> {"lines": [...]}.  Unreadable (or too
    large) paths are skipped: the report still renders, the UI shows
    "source unavailable" for those rows and leaves their line numbers
    unlinked.
    """
    want = set()
    for p in points:
        if p.t == "covergroup" or not p.f:
            continue
        want.add(p.f)
    out = {}
    for path in sorted(want):
        full = path if os.path.isabs(path) else os.path.join(root, path)
        try:
            size = os.path.getsize(full)
        except OSError:
            continue
        if size > _MAX_SRC_FILE:
            continue
        try:
            with open(full, "rb") as fh:
                raw = fh.read()
        except OSError:
            continue
        lines = raw.decode("utf-8", "replace").split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        out[path] = {"lines": lines}
    return out





def build_data(points, source: str, root: str = None) -> dict:
    """Reduce parsed Points to a JSON-serializable report payload."""
    # Collapse records reported once per parametrization of a module (a .dat
    # merged from separately-built variants) so every view sees each record
    # once; then drop Verilator SystemC-runtime units (std, std::process, ...)
    # so they never appear in any view or detail page.
    points = merge_parametrized_points(points)
    points = [p for p in points if not is_internal_point(p)]

    # -- source lines (optional): the .dat has no code; read the referenced
    # lines from disk when they resolve under ``root`` so each row can
    # show its source
    src = fetch_source_lines(points, root) if root else {}

    # -- functional coverage: attach to modules ------------------------
    groups = build_covergroups(points)
    by_module = covergroups_by_module(groups)
    module_func = {b: cg_groups_tally(gs) for b, gs in by_module.items()}
    module_cg = {b: [_cg_group_json(g) for g in gs] for b, gs in by_module.items()}
    overall = cg_groups_tally(list(groups.values()))

    # -- code coverage: per-instance hierarchy tree -------------------
    root, ordered = build_code_tree(points)
    code_tallies(root)
    code_tallies_depth(root)
    rows = []

    def _bases_of(full: str):
        return list(dict.fromkeys(s for s in full.split(".") if s in module_func))

    def _func_of(full: str):
        return _combine_func([module_func[b] for b in _bases_of(full)])

    def _cgs_of(full: str):
        out = []
        for b in _bases_of(full):
            out.extend(module_cg[b])
        return out

    def _walk(node):
        rows.append({
            "name": node.name or "design",
            "depth": node.depth,
            "collapsed": is_collapsed_hier(node.full),
            "tally": {t: list(v) for t, v in node.tally.items()},
            "points": [_point_json(p) for p in node.points],
            "functional": _func_of(node.full),
            "covergroups": _cgs_of(node.full),
            "hasChildren": bool(node.children),
        })
        for c in node.children.values():
            _walk(c)

    _walk(root)

    ordered_sorted = [t for t in _CANON if t in ordered] + \
                     [t for t in ordered if t not in _CANON]
    summary_code = {t: _entry(*root.tally.get(t, (0, 0))) for t in ordered_sorted}

    # -- code coverage: per-design-unit (module) view ------------------
    du_map, du_ordered = build_du(points)
    du_types = [t for t in _CANON if any(k.rsplit("#", 1)[1] == t for k in du_map)] + \
               [t for t in du_ordered if t not in _CANON
                and any(k.rsplit("#", 1)[1] == t for k in du_map)]

    by_base = {}  # base -> {"variants": [du, ...], "points": [...]}
    for p in points:
        if p.t == "covergroup":
            continue
        base = module_base(p.du_name())
        if not base:
            continue
        b = by_base.setdefault(base, {"variants": [], "points": []})
        duval = p.du_name()
        if duval not in b["variants"]:
            b["variants"].append(duval)
        b["points"].append(_point_json(p))
    du_rows = []
    for base in sorted(by_base):
        b = by_base[base]
        tally = {}
        for t in du_types:
            hv, tv = du_map.get(base + "#" + t, (0, 0))
            if tv:
                tally[t] = [hv, tv]
        du_rows.append({
            "name": base,
            "variants": b["variants"] if len(b["variants"]) > 1 else [],
            "tally": tally,
            "points": b["points"],
            "functional": module_func.get(base),
            "covergroups": module_cg.get(base, []),
        })

    return {
        "version": __version__,
        "source": source,
        "codeTypes": ordered_sorted,
        "duRows": du_rows,
        "byDesignUnit": bool(du_rows),
        "summaryCode": summary_code,
        "summaryFunctional": _entry(overall["hit"], overall["total"]),
        "rows": rows,
        "src": src,
        "nPoints": len(points),
    }


def render_html(data: dict) -> str:
    payload = json.dumps(data, separators=(",", ":"))
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Coverage Report</title>\n"
        "<style>\n" + CSS + "\n</style>\n"
        "</head>\n<body>\n"
        '<script type="application/json" id="data">\n' + payload + "\n</script>\n"
        '<div id="app"></div>\n'
        "<script>\n" + JS + "\n</script>\n"
        "</body>\n</html>\n"
    )


def write_report(points, source: str, out_path: str, root: str = None) -> str:
    """Build the report from points and write it to ``out_path``."""
    html = render_html(build_data(points, source, root))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path
