# vcovhtml

Read a **Verilator** coverage `.dat` file (`SystemC::Coverage-3`) and render a
**EDA-style HTML report** — a single self-contained `.html` file (no CDNs,
no server) with:

- a **per-instance hierarchy tree** (expandable, roll-up % per coverage type,
  green/yellow/red colouring, `*combined` badges for merged identical instances);
- **point drill-down** at any instance (type, file:line, comment, hits, goal,
  covered/missed);
- a **functional (covergroup) section** (covergroup → coverpoint → bin, with
  the IEEE 1800 weighted scoring, hit/total and covered/missed);
- an overall **summary** (one card per type + covergroups);
- **search** (by instance name), **type filter**, and **status filter**
  (all / covered / missed).

It is a standalone tool, **not** part of the Verilator source tree. It reads
the same text format that `verilator_coverage` reads, so you do **not** need
`--coverage-per-instance` (merged identical instances are shown as `*combined`
nodes). If you *do* verilate with `--coverage-per-instance`, every node is a
true instance.

## Install

Python 3.8+, standard library only (no third-party dependencies).

```bash
pip install -e .          # from this directory
# or just run it from the checkout:
python3 -m vcovhtml coverage.dat
```

## Usage

```bash
# single coverage file -> coverage.html
vcovhtml coverage.dat

# custom output, open in browser, restrict types
vcovhtml coverage.dat -o report.html --open --types line branch expr

# a directory: every *.dat under it is parsed and merged (counts summed for
# identical points), like `verilator_coverage` given several inputs
vcovhtml /path/to/coverage/dir/
```

`vcovhtml` is installed on `PATH` by `pip install -e .`; otherwise use
`python3 -m vcovhtml ...`.

## Supported coverage types

Verilator writes these `t` fields; all are handled:

| `t` | shown as | notes |
|-----|----------|-------|
| `line` | Line | covered when hits > 0 |
| `toggle` | Toggle | comment holds the net + `0->1`/`1->0` |
| `branch` | Branch | comment holds the decision (`if`/`else`/`case:n`) |
| `expr` | Expr | condition / expression coverage |
| `fsm_state` | FSM state | state coverage |
| `fsm_arc` | FSM arc | transition coverage (comment `from->to`) |
| `user` | User | custom `cover` points |
| `covergroup` | Covergroup | functional coverage (weighted scoring) |

### Covergroup scoring (faithful to `verilator_coverage`)

A **bin** is covered when `count >= at_least` (its `s` threshold, default 1).
A **coverpoint** scores `hit/total` over its coverable bins (bins with a
`Bt` type — `ignore`/`illegal`/`default` — are excluded). A **covergroup** is
the weighted mean of its coverpoints (by `w`); the **overall functional**
score is the weighted mean of its covergroups (by `Gw`). With no bins, a
coverpoint is 0% if weighted, 100% otherwise (IEEE 1800-2023 19.11.1).

## The `.dat` format (reference)

Each line is `C '<name>' <count>` where `<name>` is a run of field pairs
`\x01<key>\x02<value>`. Keys (`include/verilated_cov_key.h`): `f` file, `l`
line, `n` col, `S` covered lines, `P` per_instance, `s` at_least, `t` type,
`page`, `h` hierarchy, `o` comment, `B` bin, `Bt` bin_type, `C`/`Cb` cross,
`Fv`/`Ff`/`Ft`/`Fg` fsm, `Gw` group_weight, `w` weight. Values are escaped:
`%`→`%25`, `"`→`%22`, non-printables→`%HH`. The count follows the **last**
`' `, because a value may contain a `'` (e.g. a parameter spec
`#(8'sh1,8'sh2,…)`). Hierarchy is split at dots, but not inside
`#(…)`, `\`-escaped identifiers, or quoted strings.

## Layout

```
vcovhtml/
  covdat.py      # parse .dat -> Point
  model.py       # splitHier, code tree + tallies, covergroup weighted tally
  report.py      # build JSON data island + assemble HTML
  report_css.py  # styling
  report_js.py   # interactive renderer
  cli.py         # argparse entry point
```

## Notes & troubleshooting

- **`Failed to parse` in other tools** is almost always the quote-in-parameter
  case (`#(8'sh1)`) tripping a non-greedy `[^']*` regex, or control
  characters being stripped in transit. `vcovhtml` uses `rfind("' ")` and reads
  the file byte-safe (`latin-1`), so it survives both.
- If a value genuinely contains the two-character sequence `' ` (quote then
  space), the count boundary is ambiguous; this matches `verilator_coverage`'
  own behaviour (`rfind("' ")`) and is vanishingly rare in practice.

## License

LGPL-3.0-only (a consumer-side companion to Verilator's coverage format).
