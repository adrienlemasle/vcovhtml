# vcovhtml — developer notes

Implementation-oriented material for people working on the tool itself: the
`.dat` format reference, the source layout, how to test, and the sharp
edges. User-facing docs live in [README.md](README.md).

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

Per-type comment shapes (what the report's grouping relies on):

| type | comment format | grouping |
|------|----------------|----------|
| `expr` | `(t1==0 && t2==1) => 1` — a conjunction of `term==value` pairs with an optional ` => result` | one group per file:line (+ last hierarchy segment); the label is the conjunction of the most terms, with `!` for `==0` terms |
| `toggle` | `<net>:<0->1 \| 1->0>` — the direction is always after the **last** colon; the net may contain dots (`a.b`) and `[n]` bit indexes, including multi-dim arrays (`RAM[0][1]`) | three levels: bits under `file+line+last-h-seg+net` (bit name = exact comment net), signals under the same key with all *trailing* `[n]` groups stripped (`sigBase`); single-bit signals expand straight to directions |

## Source layout

```
vcovhtml/
  covdat.py      # parse .dat -> Point
  model.py       # splitHier, code tree + tallies, covergroup weighted tally,
                 # merge_parametrized_points (variant consolidation)
  report.py      # build JSON data island (+ fetch_source_lines) + assemble HTML
  report_css.py  # styling (embedded in the HTML)
  report_js.py   # interactive renderer (embedded in the HTML)
  cli.py         # argparse entry point
tests/
  test_vcovhtml.py  # stdlib unittest suite
```

The data island is JSON inside `<script type="application/json" id="data">`.
To keep it small, point records use short keys (`t`/`f`/`l`/`o`/`s`/`h`/
`count`/`covered`) that the renderer normalizes to long names at startup —
any new consumer of the island must apply the same mapping.

## Testing

```bash
python3 -m unittest tests.test_vcovhtml   # stdlib only, no build step
```

For changes to the embedded JS, two extra checks are the convention in this
repo (no screenshots — verification is text-only):

1. extract the `<script>` body from a generated report and `node --check` it;
2. exercise the pure functions with Node's `vm` against the data island of a
   generated report — remember the short keys above when preparing points.

Committed test fixtures must stay **synthetic**; real coverage data is
confidential and never enters the repository or its history.

## Notes & troubleshooting

- **`Failed to parse` in other tools** is almost always the quote-in-parameter
  case (`#(8'sh1)`) tripping a non-greedy `[^']*` regex, or control
  characters being stripped in transit. `vcovhtml` uses `rfind("' ")` and reads
  the file byte-safe (`latin-1`), so it survives both.
- If a value genuinely contains the two-character sequence `' ` (quote then
  space), the count boundary is ambiguous; this matches `verilator_coverage`'
  own behaviour (`rfind("' ")`) and is vanishingly rare in practice.
- **Parametrization consolidation** (see README, "Merged coverage") merges
  records that share *both* their identity (all fields except `page` and `h`;
  for covergroups, `h` minus its unit-anchored first segment) and their
  instance scope (the full `h` for code). A single-build file never loses
  granularity under this: records at different instances of the same module
  have different hierarchies and stay apart.
- The `--source-root` reading is deliberately best-effort: unreadable paths
  are skipped rather than raising, so a report can be regenerated on a
  machine that does not have the full source tree.
