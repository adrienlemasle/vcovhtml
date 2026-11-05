# -*- coding: utf-8 -*-
"""Stylesheet for the coverage report (embedded in the HTML file)."""

CSS = r"""
:root {
  --bg: #f6f8fa;
  --panel: #ffffff;
  --line: #d0d7de;
  --text: #1f2329;
  --muted: #57606a;
  --accent: #0969da;
  --green: #1a7f37;
  --green-bg: #dafbe1;
  --orange: #9a6700;
  --orange-bg: #fff8c5;
  --red: #cf222e;
  --red-bg: #ffe1e6;
  --g: #1a7f37;
  --o: #9a6700;
  --r: #cf222e;
  --n: #8b949e;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  line-height: 1.5;
}
#app { max-width: 1200px; margin: 0 auto; padding: 24px 20px 60px; }
header { border-bottom: 2px solid var(--line); margin-bottom: 18px; padding-bottom: 12px; }
h1 { font-size: 22px; font-weight: 600; margin: 0 0 4px; }
.src { color: var(--muted); font-size: 13px; }
.src a { color: var(--accent); text-decoration: none; word-break: break-all; }
.file { color: var(--muted); font-family: ui-monospace, monospace; font-size: 12px; margin-bottom: 6px; }
h2 { font-size: 16px; font-weight: 600; margin: 26px 0 10px; }
a.name-link { color: var(--text); text-decoration: none; cursor: pointer; }
a.name-link:hover { color: var(--accent); text-decoration: underline; }
.backbtn {
  margin: 0 0 6px; padding: 7px 16px; border: 1px solid var(--line); border-radius: 8px;
  background: #fff; color: var(--accent); cursor: pointer; font: inherit; font-weight: 600;
}
.backbtn:hover { background: var(--accent); color: #fff; }

.cards { display: flex; flex-wrap: wrap; gap: 10px; margin: 16px 0; }
.card {
  background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
  padding: 10px 14px; min-width: 96px; flex: 1 1 auto;
}
.card .label { font-size: 12px; color: var(--muted); text-transform: capitalize; }
.card .pct { font-size: 22px; font-weight: 700; }
.card .frac { font-size: 12px; color: var(--muted); }
.card .pct.g { color: var(--green); }
.card .pct.o { color: var(--orange); }
.card .pct.r { color: var(--red); }
.card .pct.n { color: var(--n); }

.controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin: 14px 0; }
.controls label { color: var(--muted); font-size: 13px; }
.controls .grp { display: flex; gap: 6px; align-items: center; }
.controls .chk { display: inline-flex; gap: 4px; align-items: center; }
.controls select { padding: 3px 6px; border: 1px solid var(--line); border-radius: 6px; background: #fff; }
.controls input[type="text"] {
  flex: 1 1 200px; padding: 6px 10px; border: 1px solid var(--line); border-radius: 8px;
  background: #fff; min-width: 180px;
}
.controls button {
  padding: 6px 12px; border: 1px solid var(--line); border-radius: 8px;
  background: #fff; cursor: pointer; color: var(--text);
}
.controls button:hover { background: var(--line); }
.spacer { flex: 1; }
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
.seg .vbtn { border: none; border-right: 1px solid var(--line); padding: 6px 12px; background: #fff; cursor: pointer; color: var(--text); }
.seg .vbtn:last-child { border-right: none; }
.seg .vbtn.active { background: var(--accent); color: #fff; }

table { border-collapse: collapse; width: 100%; background: var(--panel); }
th, td { border: 1px solid var(--line); padding: 6px 10px; text-align: left; vertical-align: middle; }
thead th { background: #eef1f4; font-size: 12px; text-transform: capitalize; color: var(--muted); }
td.count { text-align: right; font-variant-numeric: tabular-nums; }
td.file { color: var(--muted); font-size: 12px; font-family: ui-monospace, SFMono-Regular, monospace; }
.st.g { color: var(--green); font-weight: 600; }
.st.o { color: var(--orange); font-weight: 600; }
.st.r { color: var(--red); font-weight: 600; }
.pnum.g { color: var(--green); }
.pnum.o { color: var(--orange); }
.pnum.r { color: var(--red); }
.pnum.n { color: var(--n); }

.pbar { display: inline-block; width: 60px; height: 7px; background: #e6e9ec; border-radius: 4px; vertical-align: middle; margin-right: 6px; overflow: hidden; }
.pbar i { display: block; height: 100%; }
.pbar i.g { background: var(--green); }
.pbar i.o { background: var(--orange); }
.pbar i.r { background: var(--red); }

table.tree td.name { font-weight: 500; white-space: nowrap; }
.twisty { display: inline-block; width: 16px; cursor: pointer; user-select: none; color: var(--muted); }
.collbadge { font-size: 11px; color: var(--muted); border: 1px solid var(--line); border-radius: 8px; padding: 0 6px; margin-left: 4px; }
.detail { background: #fbfcfd; }
.detail > .detail { padding: 0; }
.ptag { font-size: 11px; padding: 1px 7px; border-radius: 8px; border: 1px solid var(--line); color: var(--muted); text-transform: capitalize; }
.empty { color: #9aa0a6; padding: 14px 2px; font-size: 14px; }

section.cg .grp-name { font-weight: 600; }
section.cg .item-name { color: var(--muted); padding-left: 18px; }
section.cg .bin-row td { font-size: 12px; }
footer { margin-top: 30px; color: var(--muted); font-size: 12px; }
.hint { color: #6b7280; font-size: 13px; margin: 8px 0 12px; }
code.expr, code.net {
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  font-size: 13px; background: #eef1f5; padding: 2px 6px; border-radius: 4px; color: #1f2937;
}
.expr-detail td.expr-sub, .tog-detail td.tog-sub { padding: 6px 10px 14px 30px; background: #fafbfc; }
.tog-bdet td.tog-bsub { padding: 4px 10px 10px 34px; background: #f4f6f8; }
table.pts .num, table.pts th.num { text-align: right; }
table.pts.sub td { padding: 3px 8px; font-size: 13px; }
th.sortable { cursor: pointer; }
th.sortable:hover { color: var(--accent); }
"""
