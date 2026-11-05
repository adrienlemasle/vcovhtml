# -*- coding: utf-8 -*-
"""Command-line entry point for vcovhtml.

Accepts a single .dat file, or a directory (every *.dat under it is parsed
and merged, summing counts of identical points across runs -- the same
behaviour as `verilator_coverage` when given several inputs).

When a source tree is available (``--source-root``, defaulting to the current
directory), the report also shows each point's actual source line; rows whose
files cannot be read degrade gracefully.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import webbrowser

from . import __version__
from .covdat import parse_dat
from .report import build_data, write_report


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

    source = " ".join(args.input)
    root = args.source_root or os.getcwd()
    data = build_data(points, source, root)
    out = write_report(points, source, args.output, root)
    _print_summary(data)
    print("wrote %s" % out)
    if args.open:
        webbrowser.open("file://" + os.path.abspath(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
