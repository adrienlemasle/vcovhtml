# -*- coding: utf-8 -*-
"""Tests for vcovhtml (stdlib unittest; run with `python -m unittest`)."""
import json
import os
import tempfile
import unittest

from vcovhtml.covdat import unescape, parse_dat
from vcovhtml.model import (
    splitHier,
    is_collapsed_hier,
    build_code_tree,
    code_tallies,
    build_covergroups,
    cg_item_tally,
    cg_group_tally,
    cg_groups_tally,
)
from vcovhtml.report import build_data, render_html


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


class TestUnescape(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(unescape("no escapes"), "no escapes")

    def test_specials(self):
        # printable escapes are decoded: '%' -> %25, '"' -> %22
        self.assertEqual(unescape("a%25b%22c"), "a%b\"c")
        self.assertEqual(unescape("x%41y"), "xAy")

    def test_lone_percent(self):
        self.assertEqual(unescape("99%"), "99%")

    def test_nonprintable_stays(self):
        # non-printable escapes (0x01/0x02) are kept as-is, matching C++ unescape
        self.assertEqual(unescape("%01%02"), "%01%02")


class TestSplitHier(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(splitHier("tb.dut.u_a"), ["tb", "dut", "u_a"])

    def test_param_spec_with_quotes(self):
        h = "mymod#(8'sh1,8'sh2).cg_x.cp.y"
        self.assertEqual(
            splitHier(h),
            ["mymod#(8'sh1,8'sh2)", "cg_x", "cp", "y"],
        )

    def test_nested_parens(self):
        self.assertEqual(splitHier("a#(b#c).d"), ["a#(b#c)", "d"])

    def test_escaped_identifier_with_dots(self):
        # a backslash-escaped region ends at the next space; its internal dots
        # do not split the hierarchy
        self.assertEqual(splitHier("a.\\b.c .d"), ["a", "\\b.c ", "d"])

    def test_empty(self):
        self.assertEqual(splitHier(""), [])


class TestCollapsed(unittest.TestCase):
    def test(self):
        self.assertTrue(is_collapsed_hier("tb.dut.*"))
        self.assertTrue(is_collapsed_hier("a?b"))
        self.assertFalse(is_collapsed_hier("tb.dut.u_a"))


class TestParse(unittest.TestCase):
    def test_quote_in_param(self):
        fields = (
            "\x01t\x02covergroup"
            "\x01page\x02v_covergroup/m#(8'sh3,32'sh2).cg"
            "\x01f\x02file.sv"
            "\x01l\x0210"
            "\x01n\x025"
            "\x01B\x02b[0]"
            "\x01h\x02m#(8'sh3,32'sh2).cg.cp.b[0]"
        )
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.dat")
            _write(p, "# SystemC::Coverage-3\nC '" + fields + "' 7\n")
            pts, bad = parse_dat(p)
            self.assertEqual(bad, 0)
            self.assertEqual(len(pts), 1)
            pt = pts[0]
            self.assertEqual(pt.t, "covergroup")
            self.assertEqual(pt.B, "b[0]")
            self.assertEqual(pt.count, 7)
            self.assertEqual(pt.l, 10)
            self.assertTrue(pt.covered())
            self.assertIn("8'sh3", pt.h)

    def test_types_filter(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.dat")
            _write(
                p,
                "# SystemC::Coverage-3\n"
                "C '\x01t\x02line\x01f\x02a.v\x01l\x021' 5\n"
                "C '\x01t\x02branch\x01f\x02a.v\x01l\x022' 0\n",
            )
            pts, _ = parse_dat(p, {"line"})
            self.assertEqual([p.t for p in pts], ["line"])


class TestCodeTree(unittest.TestCase):
    def test_rollup(self):
        from vcovhtml.covdat import Point
        pts = [
            Point(name="\x01t\x02line\x01h\x02a.b", count=1, t="line", h="a.b", s=0),
            Point(name="\x01t\x02line\x01h\x02a.b", count=0, t="line", h="a.b", s=0),
            Point(name="\x01t\x02line\x01h\x02a.c", count=3, t="line", h="a.c", s=0),
        ]
        root, ordered = build_code_tree(pts)
        code_tallies(root)
        self.assertEqual(ordered, ["line"])
        # a.b has 1 hit of 2; a.c has 1 of 1; node a = 2 hits of 3
        self.assertEqual(root.tally["line"], (2, 3))
        an = root.children["a"]
        self.assertEqual(an.tally["line"], (2, 3))
        self.assertEqual(an.children["b"].tally["line"], (1, 2))
        self.assertEqual(an.children["c"].tally["line"], (1, 1))


class TestCovergroupTally(unittest.TestCase):
    def _bin(self, name, atLeast, Bt=""):
        parts = [
            "\x01t\x02covergroup",
            "\x01page\x02v_covergroup/m.cg",
            "\x01h\x02m.cg.cp." + name,
            "\x01B\x02" + name,
        ]
        if Bt:
            parts.append("\x01Bt\x02" + Bt)
        parts.append("\x01w\x022")
        parts.append("\x01s\x02%d" % atLeast)
        return "".join(parts)

    def _pt(self, name, count, atLeast, Bt=""):
        from vcovhtml.covdat import Point
        return Point(name=self._bin(name, atLeast, Bt), count=count,
                     t="covergroup", h="m.cg.cp." + name, B=name, w=2, s=atLeast)

    def test_weighted(self):
        pts = [
            self._pt("x", 5, 1),
            self._pt("y", 0, 1),
            self._pt("z", 9, 3),
        ]
        groups = build_covergroups(pts)
        self.assertEqual(len(groups), 1)
        g = list(groups.values())[0]
        item = g.items["m.cg.cp"]
        # 2 of 3 bins covered -> 66.67%
        it = cg_item_tally(item)
        self.assertEqual((it["hit"], it["total"]), (2, 3))
        self.assertAlmostEqual(it["score"], 100.0 * 2 / 3)
        gr = cg_group_tally(g)
        self.assertAlmostEqual(gr["score"], 100.0 * 2 / 3)
        overall = cg_groups_tally(list(groups.values()))
        self.assertAlmostEqual(overall["score"], 100.0 * 2 / 3)

    def test_noncoverable_excluded(self):
        pts = [
            self._pt("a", 1, 1),
            self._pt("i", 1, 1, Bt="illegal"),
        ]
        groups = build_covergroups(pts)
        g = list(groups.values())[0]
        item = g.items["m.cg.cp"]
        # illegal bin has Bt -> excluded; only 'a' counts: 1/1 = 100%
        self.assertEqual(len(item.bins), 1)
        self.assertAlmostEqual(cg_item_tally(item)["score"], 100.0)


class TestDataAndHtml(unittest.TestCase):
    def test_roundtrip(self):
        from vcovhtml.covdat import Point
        pts = [
            Point(name="\x01t\x02line\x01h\x02a.b\x01f\x02x.v\x01l\x023\x01o\x02stmt",
                  count=2, t="line", h="a.b", f="x.v", l=3, o="stmt", s=1),
            Point(name="\x01t\x02branch\x01h\x02a\x01f\x02x.v\x01l\x029\x01o\x02if",
                  count=0, t="branch", h="a", f="x.v", l=9, o="if", s=1),
        ]
        data = build_data(pts, "test.dat")
        self.assertEqual(data["codeTypes"], ["line", "branch"])
        html = render_html(data)
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertEqual(html.count("<script"), 2)
        i = html.find('id="data"') + len('id="data"')
        j = html.index("</script>", i)
        parsed = json.loads(html[i + 1:j])
        self.assertEqual(parsed["nPoints"], 2)
        self.assertEqual(len(parsed["rows"]), 3)  # root, a, a.b


if __name__ == "__main__":
    unittest.main()
