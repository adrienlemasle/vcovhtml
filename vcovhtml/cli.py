# -*- coding: utf-8 -*-
"""Command-line entry point for vcovhtml.

Accepts a single .dat file, or a directory (every *.dat under it is parsed
and merged, summing counts of identical points across runs -- the same
behaviour as `verilator_coverage` when given several inputs).

When a source tree is available (``--source-root``, defaulting to the current
directory), the report also shows each point's actual source line; rows whose
files cannot be read degrade gracefully.  Clicking a line number opens the
full source file, landed on that line.  ``--no-source`` skips the source
reading entirely (fastest).

By default the global per-type coverage summary is printed after the
report is written; ``--per-design-unit`` prints one row per design unit
instead, each cell showing hits/total and score.

``--no-report`` runs in CLI-only mode: no HTML report is written and the
data island is never built, so the summary is printed from the parsed
points directly (the fastest way to get the numbers for a large .dat).
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import webbrowser

from . import __version__
from .covdat import parse_dat
from .model import (
    build_covergroups,
    build_du,
    cg_groups_tally,
    covergroups_by_module,
    is_internal_point,
    merge_parametrized_points,
    module_base,
)
from .report import _CANON, _entry, build_data, write_report


def _inputs(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            found = sorted(glob.glob(os.path.join(p, "*.dat")))
            if not found:
                print("warning: no *.dat in %s" % p, file=sys.stderr)
            files.extend(found)
        else:
            files.append(p)
    return files


def _merge(files, types=None):
    acc = {}
    order = []
    malformed = 0
    for path in files:
        pts, m = parse_dat(path, types)
        malformed += m
        for p in pts:
            if p.name in acc:
                acc[p.name].count += p.count
            else:
                acc[p.name] = p
                order.append(p.name)
    return [acc[n] for n in order], malformed


def _print_summary(data):
    print("Coverage summary")
    print("%-12s %7s %7s   %8s" % ("type", "hit", "total", "score"))
    rows = []
    for tp in data["codeTypes"]:
        e = data["summaryCode"].get(tp, {"hit": 0, "total": 0, "score": None})
        rows.append((tp, e))
    rows.append(("covergroup", data["summaryFunctional"]))
    for tp, e in rows:
        sc = ("%.1f%%" % e["score"]) if e["score"] is not None else "-"
        print("%-12s %7d %7d   %8s" % (tp, e["hit"], e["total"], sc))
    print("total points: %d" % data["nPoints"])


def _print_du_summary(data):
    """One row per design unit: hits/total (score) per coverage type."""
    rows = data["duRows"]
    types = data["codeTypes"]
    cols = types + ["covergroup"]

    def fmt(hit, total, score):
        if not total:
            return "-"
        sc = ("%.1f%%" % score) if score is not None else "n/a"
        return "%d/%d (%s)" % (hit, total, sc)

    def code_cells(r):
        out = []
        for tp in types:
            t = r["tally"].get(tp)
            if not t:
                out.append("-")
            else:
                hit, total = t
                out.append(fmt(hit, total, 100.0 * hit / total if total else None))
        return out

    def func_cell(r):
        f = r.get("functional")
        if not f:
            return "-"
        return fmt(f["hit"], f["total"], f["score"])

    table = []
    for r in rows:
        name = r["name"]
        if len(r.get("variants") or []) > 1:
            name += " (%d variants)" % len(r["variants"])
        table.append([name] + code_cells(r) + [func_cell(r)])
    tot = {tp: [0, 0] for tp in types}
    for r in rows:
        for tp in types:
            t = r["tally"].get(tp)
            if t:
                tot[tp][0] += t[0]
                tot[tp][1] += t[1]
    sf = data["summaryFunctional"]
    table.append(
        ["total"]
        + [fmt(h, t, 100.0 * h / t if t else None) for h, t in tot.values()]
        + [fmt(sf["hit"], sf["total"], sf["score"])])

    widths = [max([len(h)] + [len(row[i]) for row in table])
              for i, h in enumerate(["design unit"] + cols)]
    print("Per design unit")
    print("  ".join(h.ljust(w) for h, w in zip(["design unit"] + cols, widths)))
    for row in table:
        print("  ".join(c.ljust(w) for c, w in zip(row, widths)))


def _cli_summary(points):
    """Summary numbers without the HTML data island (for --no-report).

    Uses the same building blocks as build_data -- parametrization merge,
    internal-unit filtering, build_du and the covergroup tallies -- so the
    printed numbers agree with the report, while the island itself (point
    JSON, source reading, covergroup serialization) is never built.
    """
    pts = [p for p in merge_parametrized_points(points)
           if not is_internal_point(p)]

    ordered = []
    for p in pts:
        if p.t != "covergroup" and p.t not in ordered:
            ordered.append(p.t)
    code_types = [t for t in _CANON if t in ordered] +                  [t for t in ordered if t not in _CANON]

    tals = {}
    for p in pts:
        if p.t == "covergroup":
            continue
        h, tot = tals.get(p.t, (0, 0))
        tals[p.t] = (h + (1 if p.count > 0 else 0), tot + 1)
    summary_code = {t: _entry(*tals.get(t, (0, 0))) for t in code_types}

    groups = build_covergroups(pts)
    by_module = covergroups_by_module(groups)
    module_func = {b: cg_groups_tally(gs) for b, gs in by_module.items()}
    overall = cg_groups_tally(list(groups.values()))

    du_map, du_ordered = build_du(pts)
    du_types = [t for t in _CANON if any(k.rsplit("#", 1)[1] == t for k in du_map)] +                [t for t in du_ordered if t not in _CANON
                and any(k.rsplit("#", 1)[1] == t for k in du_map)]
    by_base = {}
    for p in pts:
        if p.t == "covergroup":
            continue
        base = module_base(p.du_name())
        if not base:
            continue
        b = by_base.setdefault(base, [])
        duval = p.du_name()
        if duval not in b:
            b.append(duval)
    du_rows = []
    for base in sorted(by_base):
        variants = by_base[base]
        tally = {}
        for t in du_types:
            hv, tv = du_map.get(base + "#" + t, (0, 0))
            if tv:
                tally[t] = [hv, tv]
        du_rows.append({
            "name": base,
            "variants": variants if len(variants) > 1 else [],
            "tally": tally,
            "functional": module_func.get(base),
        })

    return {
        "codeTypes": code_types,
        "summaryCode": summary_code,
        "summaryFunctional": _entry(overall["hit"], overall["total"]),
        "duRows": du_rows,
        "byDesignUnit": bool(du_rows),
        "nPoints": len(pts),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="vcovhtml",
        description="Read a Verilator coverage .dat and write an EDA-style HTML report.",
    )
    ap.add_argument("input", nargs="+",
                    help="one or more .dat files, or directories containing them")
    ap.add_argument("-o", "--output", default="coverage.html",
                    help="output HTML file (default: coverage.html)")
    ap.add_argument("--types", nargs="*", default=None, metavar="TYPE",
                    help="restrict to these types, e.g. line branch expr")
    ap.add_argument("--source-root", default=None, metavar="DIR",
                    help="directory from which the .dat's relative source paths are "
                         "resolved for the source-line view (default: current directory; "
                         "rows degrade gracefully when a file is missing)")
    ap.add_argument("--no-source", action="store_true",
                    help="do not read source files at all (fastest; no Source column, no file pages)")
    ap.add_argument("--no-report", action="store_true",
                    help="CLI-only mode: do not write the HTML report and skip "
                         "the data island (fastest for large .dat files)")
    ap.add_argument("--per-design-unit", action="store_true",
                    help="print one summary row per design unit (hits/total and "
                         "score per type) instead of the global summary")
    ap.add_argument("--open", action="store_true",
                    help="open the report in a web browser after writing")
    ap.add_argument("--version", action="version", version="vcovhtml " + __version__)
    args = ap.parse_args(argv)

    files = _inputs(args.input)
    types = set(args.types) if args.types else None
    points, malformed = _merge(files, types)
    if malformed:
        print("warning: skipped %d malformed line(s)" % malformed, file=sys.stderr)
    if not points:
        print("error: no coverage points parsed from %s" % " ".join(args.input),
              file=sys.stderr)
        return 1

    if args.no_report:
        if args.open:
            print("warning: --open ignored: no report is written with "
                  "--no-report", file=sys.stderr)
        data = _cli_summary(points)
    else:
        source = " ".join(args.input)
        root = None if args.no_source else (args.source_root or os.getcwd())
        data = build_data(points, source, root)
        src_n = len(data.get("src") or {})
        if src_n:
            print("source lines: %d file(s) embedded" % src_n)
        out = write_report(data, args.output)

    if args.per_design_unit:
        if data["byDesignUnit"]:
            _print_du_summary(data)
        else:
            print("warning: no design units in this data; "
                  "showing the global summary", file=sys.stderr)
            _print_summary(data)
    else:
        _print_summary(data)

    if not args.no_report:
        print("wrote %s" % out)
        if args.open:
            webbrowser.open("file://" + os.path.abspath(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
