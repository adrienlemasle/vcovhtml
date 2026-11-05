# vcovhtml

Turn a **Verilator** coverage `.dat` file into an **EDA-style HTML report** —
a single self-contained `.html` (no CDNs, no server) that you can open
directly, email, or drop next to your coverage results.

## What you get

- a **per-instance hierarchy tree** — expandable, roll-up % per coverage
  type, green/yellow/red colouring, `*combined` badges for merged identical
  instances;
- a **per-design-unit (module) view** — the same coverage grouped by module
  instead of by instance;
- **point drill-down** at any node: file:line, comment, hits, goal,
  covered/missed, plus the **actual source line** when your sources resolve
  (see Quick start);
- **grouped details** that make large records readable:
  - *Expression* coverage: the `&&` combinations of one expression collapse
    into a single row with a readable condition, expandable to each
    combination;
  - *Toggle* coverage: three levels — signal → bit → `0->1`/`1->0` directions
    (single-bit signals expand straight to their directions);
- a **functional (covergroup) section** — covergroup → coverpoint → bin, with
  IEEE 1800 weighted scoring;
- **summary cards** (one per coverage type + covergroups), **search** by
  name, and **type** and **status** (all / covered / missed) filters.

It is a standalone tool, **not** part of the Verilator source tree. It reads
the same text format that `verilator_coverage` reads, so you do **not** need
`--coverage-per-instance` — merged identical instances show up as
`*combined` nodes. If you *do* verilate with `--coverage-per-instance`,
every node is a true instance and the per-instance roll-ups are exact.

## Install

Python 3.8+, standard library only (no third-party dependencies).

```bash
pip install -e .          # from this directory
# or just run it from the checkout:
python3 -m vcovhtml coverage.dat
```

## Quick start

```bash
vcovhtml coverage.dat
# -> coverage.html
```

Run it **from the same directory where you built with Verilator** and the
report shows each point's actual source line: the `.dat` stores file paths
relative to that build directory. Running somewhere else? Point at your
tree with `--source-root DIR` (absolute paths in the `.dat` are always used
as-is). Any row whose file can't be read degrades gracefully to a dimmed
*source unavailable* — the report never breaks.

Other options:

```bash
# custom output, open in a browser, restrict types
vcovhtml coverage.dat -o report.html --open --types line branch expr

# a directory: every *.dat under it is parsed and merged (counts summed
# for identical points), like `verilator_coverage` given several inputs
vcovhtml /path/to/coverage/dir/
```

`vcovhtml` is installed on `PATH` by `pip install -e .`; otherwise use
`python3 -m vcovhtml ...`.

### Merged coverage

Two kinds of merges are handled transparently:

- **multiple runs/tests** (a directory of `.dat`s): identical points get
  their counts summed — exactly what `verilator_coverage` does given several
  inputs;
- **parametrized builds**: a `.dat` produced by merging separately-built
  parametrizations of the same module reports each record once per variant.
  `vcovhtml` consolidates those variants (a record counts as covered when
  it was hit in *any* variant), so each line appears once instead of once
  per parametrization.

## Supported coverage types

Verilator writes these `t` fields; all are handled:

| `t` | shown as | notes |
|-----|----------|-------|
| `line` | Line | covered when hits > 0 |
| `toggle` | Toggle | comment holds the net + `0->1`/`1->0` |
| `branch` | Branch | comment holds the decision (`if`/`else`/`case:n`) |
| `expr` | Expression | condition / expression coverage |
| `fsm_state` | FSM state | state coverage |
| `fsm_arc` | FSM arc | transition coverage (comment `from->to`) |
| `user` | User | custom `cover` points |
| `covergroup` | Covergroup | functional coverage (weighted scoring) |

### Covergroup scoring (faithful to `verilator_coverage`)

A **bin** is covered when `count >= at_least` (its `s` threshold, default
1). A **coverpoint** scores `hit/total` over its coverable bins (bins with a
`Bt` type — `ignore`/`illegal`/`default` — are excluded). A **covergroup**
is the weighted mean of its coverpoints (by `w`); the **overall
functional** score is the weighted mean of its covergroups (by `Gw`). With
no bins, a coverpoint is 0% if weighted, 100% otherwise (IEEE 1800-2023
19.11.1).

## A note on confidentiality

The report embeds the referenced **source lines** of your design. Treat a
generated report the same way you treat your RTL: don't post it where your
sources shouldn't appear. If you share reports publicly, generate them with
`--source-root /nonexistent` (or any directory that resolves nothing) to
suppress the source column.

## License

LGPL-3.0-only (a consumer-side companion to Verilator's coverage format).

## Developer

See [DEVELOPER.md](DEVELOPER.md) for the `.dat` format reference, source
layout, testing and troubleshooting notes.
