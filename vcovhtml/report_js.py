# -*- coding: utf-8 -*-
"""Vanilla-JS renderer for the coverage report (no dependencies).

Navigation is three levels deep, all driven by the URL hash (deep-linkable):
  1. Report        -- per-instance tree and per-design-unit table (switchable),
                       each with a covergroup column alongside line/branch/
                       expr/toggle/fsm_state/fsm_arc.
  2. Node summary  -- click an instance / design-unit name: a per-type summary
                       table; each type name is clickable.
  3. Type detail   -- click a type: its points table, sortable by line number
                       (default) or covered/missed status.  The covergroup type
                       shows coverpoints (foldable to their bins) sortable by
                       the Cover column (full / partial / missed).
Verilator runtime units (std, std::process, ...) are filtered out by Python.
"""

JS = r"""
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("data").textContent);
  var app = document.getElementById("app");
  // Normalize code-point field names (report.py uses short t/f/l/o/s; some
  // builds use type/file/line/comment/atLeast).  Covergroup structures keep
  // their own names and are not touched.
  (function () {
    function n(p) {
      return {
        type: p.type !== undefined ? p.type : p.t,
        file: p.file !== undefined ? p.file : p.f,
        line: p.line !== undefined ? p.line : p.l,
        comment: p.comment !== undefined ? p.comment : p.o,
        atLeast: p.atLeast !== undefined ? p.atLeast : p.s,
        count: p.count,
        covered: p.covered,
        h: p.h,
      };
    }
    (DATA.rows || []).forEach(function (r) { r.points = (r.points || []).map(n); });
    (DATA.duRows || []).forEach(function (r) { r.points = (r.points || []).map(n); });
  })();

  function esc(s) {
    return (s == null ? "" : String(s)).replace(/[&<>\"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function cls(score) {
    if (score == null) return "n";
    if (score >= 100) return "g";
    if (score > 0) return "o";
    return "r";
  }
  function bar(score) {
    if (score == null) return "";
    return '<span class="pbar"><i class="' + cls(score) + '" style="width:' + Math.max(score, 3) + '%"></i></span>';
  }
  function cell(score) {
    if (score == null) return '<span class="pnum n">\u2014</span>';
    return bar(score) + '<span class="pnum ' + cls(score) + '">' + score.toFixed(1) + "%</span>";
  }
  function scoreOf(tally, type) {
    if (!tally || !tally[type] || !tally[type][1]) return null;
    return 100 * tally[type][0] / tally[type][1];
  }
  function shortName(p) {
    if (!p) return p;
    var parts = p.split(".");
    return parts[parts.length - 1];
  }
  function funcScore(f) { return f ? f.score : null; }

  function header(title, srcHtml) {
    var h = document.createElement("header");
    var t = document.createElement("h1");
    t.textContent = title;
    h.appendChild(t);
    if (srcHtml) {
      var s = document.createElement("div");
      s.className = "src";
      s.innerHTML = srcHtml;
      h.appendChild(s);
    }
    return h;
  }
  function typeName(t) {
    return t === "expr" ? "expression" : t;
  }
  var SRC = DATA.src || {};
  var SRC_ORDER = Object.keys(SRC);
  function srcIdx(f) {
    return f === undefined ? -1 : SRC_ORDER.indexOf(f);
  }
  function srcLine(f, l) {
    var s = f === undefined ? null : SRC[f];
    if (!s || !l) return null;
    var t = s.lines[l - 1];
    return t === undefined ? null : t;
  }
  var HL_KW = {};
  (function () {
    "module endmodule input output inout wire reg logic signed unsigned assign if else begin end case endcase for while do repeat forever function endfunction task endtask initial final always always_comb always_ff always_latch localparam parameter defparam generate endgenerate genvar import package struct enum typedef posedge negedge or and not xor nand nor buf strong weak tri tri0 tri1 wand wor real byte shortint longint int void static const default delay event assert assume cover specparam release wait fork join join_none unique parallel casez casex timeunit timeprecision context virtual interface modport endinterface endmodport".split(" ").forEach(function (k) {
      HL_KW[k] = 1;
    });
  })();
  var HL_RE = /(\/\/[^\n]*|\/\*[\s\S]*?(?:\*\/|$)|"(?:[^"\\\n]|\\.)*|'(?:[^'\\\n]|\\.)*|\b[0-9][\w']*|\b[A-Za-z_]\w*\b)/g;
  function hl(code) {
    if (code == null) return "";
    var out = "", last = 0, m, t, c;
    HL_RE.lastIndex = 0;
    while ((m = HL_RE.exec(code)) !== null) {
      out += esc(code.slice(last, m.index));
      t = m[0];
      if (t.charAt(0) === "/") c = "tk-c";
      else if (t.charAt(0) === '"' || t.charAt(0) === "'") c = "tk-s";
      else if (t.charAt(0) >= "0" && t.charAt(0) <= "9") c = "tk-n";
      else c = HL_KW[t] ? "tk-k" : null;
      out += c ? '<span class="' + c + '">' + esc(t) + "</span>" : esc(t);
      last = m.index + t.length;
    }
    return out + esc(code.slice(last));
  }
  function summaryCards() {
    var cards = document.createElement("div");
    cards.className = "cards";
    var mk = function (label, entry) {
      var sc = entry ? entry.score : null;
      var c = document.createElement("div");
      c.className = "card";
      c.innerHTML = '<div class="label">' + esc(label) + "</div>" +
        '<div class="pct ' + cls(sc) + '">' + (sc == null ? "\u2014" : sc.toFixed(1) + "%") + "</div>" +
        '<div class="frac">' + (entry ? entry.hit + " / " + entry.total : "\u2014") + "</div>";
      return c;
    };
    DATA.codeTypes.forEach(function (tp) {
      cards.appendChild(mk(typeName(tp), DATA.summaryCode[tp] || { hit: 0, total: 0, score: null }));
    });
    cards.appendChild(mk("Covergroups", DATA.summaryFunctional));
    return cards;
  }

  var state = { q: "", types: {}, status: "all", view: "design" };
  DATA.codeTypes.forEach(function (tp) { state.types[tp] = true; });
  state.types.func = true;
  var viewBtns = [];
  function controls() {
    var b = document.createElement("div");
    b.className = "controls";
    b.innerHTML =
      '<span class="grp"><label>View:</label></span>' +
      '<span class="seg">' +
      '<button id="v-inst" class="vbtn">Per instance</button>' +
      '<button id="v-dest" class="vbtn">Per design unit</button>' +
      '</span>' +
      '<input type="text" id="search" placeholder="Filter by name...">' +
      '<span class="grp"><label>Types:</label></span>' +
      DATA.codeTypes.map(function (tp) {
        return '<label class="chk"><input type="checkbox" id="type-' + tp + '" checked> ' + esc(typeName(tp)) + "</label>";
      }).join("") +
      '<label class="chk"><input type="checkbox" id="type-func" checked> covergroup</label>' +
      '<span class="grp"><label>Status:</label><select id="status">' +
      '<option value="all">all</option><option value="covered">covered</option>' +
      '<option value="missed">missed</option></select></span>' +
      '<span class="spacer"></span>' +
      '<button id="expandAll">Expand all</button><button id="collapseAll">Collapse all</button>';
    viewBtns = [b.querySelector("#v-inst"), b.querySelector("#v-dest")];
    viewBtns[0].addEventListener("click", function () { setView("instance"); });
    viewBtns[1].addEventListener("click", function () { setView("design"); });
    var search = b.querySelector("#search");
    search.value = state.q;
    var deb;
    search.addEventListener("input", function () {
      clearTimeout(deb);
      deb = setTimeout(function () { state.q = search.value; applyFilters(); }, 150);
    });
    DATA.codeTypes.forEach(function (tp) {
      b.querySelector("#type-" + tp).addEventListener("change", function (e) {
        state.types[tp] = e.target.checked; applyTypeCols();
      });
    });
    b.querySelector("#type-func").addEventListener("change", function (e) {
      state.types.func = e.target.checked; applyTypeCols();
    });
    b.querySelector("#status").addEventListener("change", function (e) {
      state.status = e.target.value; applyFilters();
    });
    b.querySelector("#expandAll").addEventListener("click", function () { collapsed.clear(); applyFilters(); });
    b.querySelector("#collapseAll").addEventListener("click", function () {
      instRows.forEach(function (r, i) { if (r.hasChildren && i !== 0) collapsed.add(i); });
      applyFilters();
    });
    return b;
  }
  function setView(v) {
    if (state.view === v) return;
    state.q = document.getElementById("search").value;
    state.view = v;
    if (location.hash) location.hash = "";
    else render();
  }

  var instRows = DATA.rows;
  var collapsed = new Set();
  instRows.forEach(function (r, i) { if (r.hasChildren) collapsed.add(i); });
  // Every parent starts collapsed: only the root shows, and expanding a node
  // reveals just its immediate children (one level at a time).
  var treeBody, parentArr, childrenArr;
  function buildInstanceTree() {
    var sec = document.createElement("section");
    var h2 = document.createElement("h2");
    h2.textContent = "Code Coverage (per instance)";
    sec.appendChild(h2);
    parentArr = new Array(instRows.length).fill(-1);
    childrenArr = instRows.map(function () { return []; });
    (function () {
      var stack = [];
      instRows.forEach(function (r, i) {
        while (stack.length && stack[stack.length - 1][0] >= r.depth) stack.pop();
        if (stack.length) { parentArr[i] = stack[stack.length - 1][1]; childrenArr[stack[stack.length - 1][1]].push(i); }
        stack.push([r.depth, i]);
      });
    })();
    var tbl = document.createElement("table");
    tbl.className = "tree";
    var head = "<thead><tr><th>Instance</th>";
    DATA.codeTypes.forEach(function (tp) {
      head += "<th class='pcell' data-type='" + tp + "'>" + esc(typeName(tp)) + "</th>";
    });
    head += '<th class="pcell" data-type="func">covergroup</th></tr></thead>';
    tbl.innerHTML = head + "<tbody></tbody>";
    treeBody = tbl.querySelector("tbody");
    instRows.forEach(function (r, i) {
      var tr = document.createElement("tr");
      tr.dataset.idx = i;
      var style = "padding-left:" + (8 + r.depth * 18) + "px";
      var twisty = r.hasChildren
        ? '<span class="twisty" data-tw="' + i + '">\u25ba</span>'
        : '<span class="twisty" style="cursor:default"></span>';
      var link = '<a class="name-link" href="#detail/inst/' + i + '">' + esc(r.name) + "</a>";
      var badge = r.collapsed ? ' <span class="collbadge" title="Combined instances (identical hierarchy)">*combined</span>' : "";
      var name = '<td class="name" style="' + style + '">' + twisty + link + badge + "</td>";
      var c = "";
      DATA.codeTypes.forEach(function (tp) {
        c += "<td class='pcell' data-type='" + tp + "'>" + cell(scoreOf(r.tally, tp)) + "</td>";
      });
      c += '<td class="pcell" data-type="func">' + cell(funcScore(r.functional)) + "</td>";
      tr.innerHTML = name + c;
      treeBody.appendChild(tr);
      var dr = document.createElement("tr");
      dr.className = "detail";
      dr.style.display = "none";
      dr.dataset.idx = "d" + i;
      dr.innerHTML = "<td colspan='" + (2 + DATA.codeTypes.length) + "' class='detail' id='det-" + i + "'></td>";
      treeBody.appendChild(dr);
    });
    tbl.addEventListener("click", function (e) {
      var nm = e.target.closest(".name-link");
      var tw = e.target.closest("[data-tw]");
      if (nm) { e.preventDefault(); gotoDetail("inst", +nm.getAttribute("href").split("/")[2]); return; }
      if (!tw) return;
      var i = +tw.dataset.tw;
      if (collapsed.has(i)) { collapsed.delete(i); tw.textContent = "\u25bc"; }
      else { collapsed.add(i); tw.textContent = "\u25ba"; }
      applyFilters();
    });
    sec.appendChild(tbl);
    return sec;
  }

  var duRows = DATA.duRows;
  function buildDesignUnits() {
    var sec = document.createElement("section");
    var h2 = document.createElement("h2");
    h2.textContent = "Code Coverage (per design unit)";
    sec.appendChild(h2);
    var tbl = document.createElement("table");
    tbl.className = "tree";
    var head = "<thead><tr><th>Design unit</th>";
    DATA.codeTypes.forEach(function (tp) {
      head += "<th class='pcell' data-type='" + tp + "'>" + esc(typeName(tp)) + "</th>";
    });
    head += '<th class="pcell" data-type="func">covergroup</th></tr></thead>';
    tbl.innerHTML = head + "<tbody></tbody>";
    var body = tbl.querySelector("tbody");
    duRows.forEach(function (r, i) {
      var tr = document.createElement("tr");
      tr.dataset.idx = i;
      var variants = (r.variants && r.variants.length > 1)
        ? ' <span class="collbadge" title="Variants: ' + esc(r.variants.join(", ")) + '">' + r.variants.length + " variants</span>"
        : "";
      tr.innerHTML = '<td class="name"><a class="name-link" href="#detail/du/' + i + '">' + esc(r.name) + "</a>" + variants + "</td>" +
        DATA.codeTypes.map(function (tp) { return "<td class='pcell' data-type='" + tp + "'>" + cell(scoreOf(r.tally, tp)) + "</td>"; }).join("") +
        '<td class="pcell" data-type="func">' + cell(funcScore(r.functional)) + "</td>";
      body.appendChild(tr);
      var dr = document.createElement("tr");
      dr.className = "detail";
      dr.style.display = "none";
      dr.dataset.idx = "d" + i;
      dr.innerHTML = "<td colspan='" + (2 + DATA.codeTypes.length) + "' class='detail' id='det-" + i + "'></td>";
      body.appendChild(dr);
    });
    tbl.addEventListener("click", function (e) {
      var nm = e.target.closest(".name-link");
      if (nm) { e.preventDefault(); gotoDetail("du", +nm.getAttribute("href").split("/")[2]); }
    });
    sec.appendChild(tbl);
    return sec;
  }

  function applyTypeCols() {
    document.querySelectorAll(".pcell").forEach(function (el) {
      var t = el.getAttribute("data-type");
      el.style.display = (t === "func" ? state.types.func : (state.types[t] !== false)) ? "" : "none";
    });
  }
  function applyFilters() {
    var q = state.q.trim().toLowerCase();
    document.querySelectorAll("#app .tree tbody tr").forEach(function (tr) {
      if (tr.classList.contains("detail")) return;
      var nm = tr.querySelector(".name");
      if (!nm) return;
      var matchQ = !q || nm.textContent.toLowerCase().indexOf(q) !== -1;
      var hid = false;
      if (tr.parentNode === treeBody) {            // instance row: apply collapse
        var p = parentArr[+tr.getAttribute("data-idx")];
        while (p !== -1) { if (collapsed.has(p)) { hid = true; break; } p = parentArr[p]; }
      }
      tr.style.display = (matchQ && !hid) ? "" : "none";
    });
  }

  var instSec, duSec;
  function render() {
    app.innerHTML = "";
    app.appendChild(header(DATA.title, DATA.srcHtml));
    app.appendChild(summaryCards());
    app.appendChild(controls());
    instSec = buildInstanceTree();
    duSec = buildDesignUnits();
    if (state.view === "instance") app.appendChild(instSec);
    else app.appendChild(duSec);
    viewBtns.forEach(function (b) { b.classList.remove("active"); });
    (state.view === "instance" ? viewBtns[0] : viewBtns[1]).classList.add("active");
    applyTypeCols();
    applyFilters();
  }

  function backBtn(href, label) {
    var a = document.createElement("a");
    a.className = "back";
    a.href = href;
    a.textContent = label;
    return a;
  }
  function renderNode(kind, i) {
    var r = kind === "inst" ? instRows[i] : duRows[i];
    app.innerHTML = "";
    app.appendChild(header((kind === "inst" ? "Instance: " : "Design unit: ") + r.name, DATA.srcHtml));
    app.appendChild(backBtn("#", "\u2190 Back to report"));
    var sum = document.createElement("section");
    var files = [];
    (r.points || []).forEach(function (p) {
      if (p.file && files.indexOf(p.file) === -1) files.push(p.file);
    });
    if (files.length) {
      var fd = document.createElement("div");
      fd.className = "file";
      fd.textContent = files.join(", ");
      sum.appendChild(fd);
    }
    var h2 = document.createElement("h2");
    h2.textContent = "Coverage by type";
    sum.appendChild(h2);
    var tbl = document.createElement("table");
    tbl.className = "tree";
    tbl.innerHTML = "<thead><tr><th>Type</th><th>Points</th><th>Covered</th><th>Score</th></tr></thead><tbody></tbody>";
    var tb = tbl.querySelector("tbody");
    var any = false;
    ["line", "branch", "expr", "toggle", "fsm_state", "fsm_arc"].forEach(function (tp) {
      var pts = (r.points || []).filter(function (p) { return p.type === tp; });
      if (!pts.length) return;
      any = true;
      var cov = pts.filter(function (p) { return p.covered; }).length;
      var sc = 100 * cov / pts.length;
      var tr = document.createElement("tr");
      tr.innerHTML = "<td><a class='type-link' href='#detail/" + kind + "/" + i + "/" + tp + "'>" + esc(typeName(tp)) + "</a></td>" +
        "<td>" + pts.length + "</td><td>" + cov + " / " + pts.length + "</td>" +
        "<td class='pnum " + cls(sc) + "'>" + sc.toFixed(1) + "%</td>";
      tb.appendChild(tr);
    });
    if (r.functional) {
      any = true;
      var fsc = funcScore(r.functional);
      var tr = document.createElement("tr");
      tr.innerHTML = "<td><a class='type-link' href='#detail/" + kind + "/" + i + "/covergroup'>covergroup</a></td>" +
        "<td class='pnum n'>\u2014</td><td class='pnum n'>\u2014</td>" +
        "<td class='pnum " + cls(fsc) + "'>" + (fsc == null ? "\u2014" : fsc.toFixed(1) + "%") + "</td>";
      tb.appendChild(tr);
    }
    if (!any) tb.innerHTML = "<tr><td colspan='4' class='empty'>No coverage points for this node.</td></tr>";
    sum.appendChild(tbl);
    app.appendChild(sum);
    sum.querySelectorAll(".type-link").forEach(function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        var segs = a.getAttribute("href").split("/");
        gotoDetail(kind, i, segs[3]);
      });
    });
  }

  var sortState = {};
  function coverStatus(score) {
    if (score == null) return { c: "n", t: "\u2014", rank: 3 };
    if (score >= 100) return { c: "g", t: "full", rank: 0 };
    if (score > 0) return { c: "o", t: "partial", rank: 1 };
    return { c: "r", t: "missed", rank: 2 };
  }
  var cgSort = { dir: null };
  function cgGroupBlock(g, idx) {
    var s = coverStatus(g.score);
    var h3 = "<h3 class='cg-grp'>" + esc(g.group) + " \u00b7 " +
      (g.score == null ? "\u2014" : g.score.toFixed(1) + "%") + " \u00b7 " + g.hit + " / " + g.total +
      " <span class='st " + s.c + "'>" + s.t + "</span></h3>";
    var arrow = cgSort.dir === "desc" ? " \u25bc" : cgSort.dir === "asc" ? " \u25b2" : "";
    var tbl = "<table class='tree'><thead><tr><th>Coverpoint</th><th>Weight</th><th>Score</th><th>Hit / Total</th>" +
      "<th class='sortable' data-cgsort='cover'>Cover" + arrow + "</th></tr></thead>" +
      "<tbody class='cg-pts' data-gi='" + idx + "'></tbody></table>";
    return h3 + tbl;
  }
  function drawCgTables() {
    var cgdata = window.__cgData || [];
    document.querySelectorAll("#app .cg-pts").forEach(function (tb) {
      var g = cgdata[+tb.getAttribute("data-gi")];
      if (!g) return;
      tb.innerHTML = "";
      var items = g.items.slice();
      if (cgSort.dir) {
        items.sort(function (a, b) {
          var ra = coverStatus(a.score).rank, rb = coverStatus(b.score).rank;
          if (ra !== rb) return (cgSort.dir === "desc") ? (ra - rb) : (rb - ra);
          var sa = a.score == null ? 0 : a.score, sb = b.score == null ? 0 : b.score;
          return (cgSort.dir === "desc") ? (sb - sa) : (sa - sb);
        });
      }
      items.forEach(function (it) {
        var s = coverStatus(it.score);
        var key = tb.getAttribute("data-gi") + ":" + it.name;
        var tr = document.createElement("tr");
        tr.innerHTML = "<td class='item-name'><span class='twisty' data-cg-tw='" + esc(key) + "'>\u25ba</span>" + esc(shortName(it.name)) + "</td>" +
          "<td>" + it.weight + "</td>" +
          "<td class='pnum " + s.c + "'>" + (it.score == null ? "\u2014" : it.score.toFixed(1) + "%") + "</td>" +
          "<td>" + it.hit + " / " + it.total + "</td>" +
          "<td class='st " + s.c + "'>" + s.t + "</td>";
        tb.appendChild(tr);
        it.bins.forEach(function (b) {
          var bc = b.covered ? "g" : "r";
          var br = document.createElement("tr");
          br.className = "cg-fold";
          br.style.display = "none";
          br.dataset.parent = key;
          br.innerHTML = "<td>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;" + esc(shortName(b.name)) + "</td><td></td><td></td>" +
            "<td class='count'>" + b.count + (b.atLeast > 1 ? " / " + b.atLeast : "") + "</td>" +
            "<td class='st " + bc + "'>" + (b.covered ? "covered" : "missed") + "</td>";
          tb.appendChild(br);
        });
      });
    });
  }
  function updateCgArrows(fsec) {
    var arrow = cgSort.dir === "desc" ? " \u25bc" : cgSort.dir === "asc" ? " \u25b2" : "";
    fsec.querySelectorAll("[data-cgsort]").forEach(function (th) { th.innerHTML = "Cover" + arrow; });
  }
  function toggleCgFold(fsec, tw) {
    var key = tw.getAttribute("data-cg-tw");
    var anyVisible = false;
    fsec.querySelectorAll("tr.cg-fold").forEach(function (r) {
      if (r.dataset.parent === key) {
        r.style.display = (r.style.display === "none") ? "" : "none";
        if (r.style.display !== "none") anyVisible = true;
      }
    });
    tw.textContent = anyVisible ? "\u25bc" : "\u25ba";
  }
  function iterOf(pt) {
    if (!pt.h) return "";
    var parts = pt.h.split(".");
    var last = parts[parts.length - 1];
    var m = last.match(/\[(\*|\d+)\]/);
    return m ? m[1] : "";
  }
  function srcCell(p) {
    var t = srcLine(p.file, p.line);
    if (t === null) return "<span class='dim'>source unavailable</span>";
    return (t === "") ? "&nbsp;" : hl(t);
  }

  function drawDetail(sec, rows) {
    if (!rows.length) return;
    var st = sortState[rows[0].type] || { key: "line", dir: "asc" };
    var body = sec.querySelector(".td-body");
    body.innerHTML = "";
    var sorted = rows.slice().sort(function (a, b) {
      var d = (st.dir === "asc") ? 1 : -1;
      if (st.key === "status") {
        if (a.covered !== b.covered) return (a.covered ? -1 : 1) * d;
        return (a.line - b.line) * d;
      }
      return (a.line - b.line) * d;
    });
    sec.querySelectorAll("th.sortable").forEach(function (th) {
      var base = (th.getAttribute("data-sort") === "line") ? "Line" : "Status";
      th.innerHTML = base + (th.getAttribute("data-sort") === st.key ? (st.dir === "asc" ? " \u25b2" : " \u25bc") : "");
    });
    sorted.forEach(function (p) {
      var tr = document.createElement("tr");
      var it = iterOf(p);
      var li = srcIdx(p.file);
      tr.innerHTML = "<td class='count'>" + (li >= 0 ? "<a class='line-link' href='#file/" + li + "/" + p.line + "'>" + p.line + "</a>" : p.line) + (it ? ' <span class="iter">[' + it + ']</span>' : "") + "</td>" +
        "<td class='comment'>" + esc(p.comment || "") + "</td>" +
        "<td class='code-line'>" + srcCell(p) + "</td>" +
        "<td class='st " + (p.covered ? "g" : "r") + "'>" + (p.covered ? "covered" : "missed") + "</td>" +
        "<td class='count'>" + p.count + "</td>" +
        "<td class='count'>" + (p.atLeast || 1) + "</td>";
      body.appendChild(tr);
    });
  }
  // ---- expression coverage: group combinations into their parent expression ----
  function exprInner(o) {
    var a = o.indexOf("("); var b = o.lastIndexOf(")");
    return (a >= 0 && b > a) ? o.slice(a + 1, b) : o;
  }
  function exprCombo(o) {
    var res = "1";
    if (o.indexOf(" => ") >= 0) res = o.split(" => ")[1].trim();
    var terms = exprInner(o).split(" && ").map(function (t) { return t.trim(); });
    var ops = []; var vals = [];
    terms.forEach(function (t) {
      if (t.indexOf("==") >= 0) {
        var p = t.split("==");
        ops.push(p[0].trim());
        vals.push(p[p.length - 1].trim());
      } else { ops.push(t); vals.push("?"); }
    });
    return { ops: ops, vals: vals, res: res };
  }
  function exprLabel(combos) {
    var full = combos[0];
    combos.forEach(function (o) {
      if (o.split("==").length - 1 > full.split("==").length - 1) full = o;
    });
    var c = exprCombo(full);
    if (c.res === "0" && c.vals.every(function (v) { return v === "0"; })) {
      return c.ops.join(" || ");
    }
    return c.ops.map(function (o, i) { return c.vals[i] === "0" ? "!" + o : o; }).join(" && ");
  }
  function groupExpr(points) {
    var map = {};
    points.forEach(function (p) {
      var key = (p.file || "") + "#" + p.line + "#" + (p.h || "");
      (map[key] = map[key] || []).push(p);
    });
    var out = [];
    var idx = 0;
    Object.keys(map).forEach(function (k) {
      var list = map[k];
      out.push({
        id: idx++,
        file: list[0].file || "",
        line: list[0].line || 0,
        label: exprLabel(list.map(function (p) { return p.comment || ""; })),
        total: list.length,
        hit: list.filter(function (p) { return p.count > 0; }).length,
        combos: list
      });
    });
    return out;
  }
  var exprSort = { key: "line", dir: "asc" };
  function exprArrow(key) {
    return exprSort.key === key ? (exprSort.dir === "asc" ? " \u25b2" : " \u25bc") : "";
  }

  function drawExprBody(sec, groups) {
    sec.querySelectorAll("[data-expsort]").forEach(function (th) {
      var k = th.getAttribute("data-expsort");
      th.innerHTML = (k === "line" ? "Line" : "Score") + exprArrow(k);
    });
    var body = sec.querySelector("table.pts tbody");
    body.innerHTML = "";
    var sorted = groups.slice().sort(function (a, b) {
      var d = (exprSort.dir === "asc") ? 1 : -1;
      if (exprSort.key === "score") {
        var sa = a.total ? 100 * a.hit / a.total : 0, sb = b.total ? 100 * b.hit / b.total : 0;
        if (sa !== sb) return (sb - sa) * d;
        return (a.line - b.line) * d;
      }
      if (a.line !== b.line) return (a.line - b.line) * d;
      return a.label.localeCompare(b.label);
    });
    sorted.forEach(function (g) {
      var sc = g.total ? 100 * g.hit / g.total : null;
      var row = document.createElement("tr");
      var eidx = srcIdx(g.file);
      row.innerHTML = "<td class='num'>" + (eidx >= 0 ? "<a class='line-link' href='#file/" + eidx + "/" + g.line + "'>" + g.line + "</a>" : g.line) + "</td>" +
        "<td class='name' style='padding-left:8px'><span class='twisty' data-eg='" + g.id + "'>\u25ba</span> <code class='expr'>" +
        esc(g.label) + "</code></td>" +
        "<td class='num'>" + g.total + "</td>" +
        "<td class='num'>" + g.hit + "</td>" +
        "<td class='pcell'>" + cell(sc) + "</td>";
      body.appendChild(row);
      var det = document.createElement("tr");
      det.className = "expr-detail";
      det.style.display = "none";
      det.setAttribute("data-egd", g.id);
      det.innerHTML = "<td colspan='5' class='expr-sub'><table class='pts sub'><thead><tr>" +
        "<th>Combination</th><th class='num'>Hits</th><th>Status</th></tr></thead><tbody>" +
        g.combos.map(function (c) {
          var hit = c.count > 0;
          return "<tr><td>" + esc(c.comment || "") + "</td><td class='num'>" + c.count +
            "</td><td class='st " + (hit ? "g" : "r") + "'>" + (hit ? "covered" : "missed") + "</td></tr>";
        }).join("") + "</tbody></table></td>";
      body.appendChild(det);
    });
  }
  function drawExprGroups(sec, points) {
    var groups = groupExpr(points);
    if (!groups.length) {
      sec.innerHTML += "<div class='empty'>No expression points.</div>";
      return;
    }
    sec.innerHTML += "<p class='hint'>" + groups.length + " expression(s) over " + points.length +
      " combinations. Click the Line or Score header to sort; click an expression to see which combinations are hit or missed.</p>";
    var tbl = document.createElement("table");
    tbl.className = "pts";
    tbl.innerHTML = "<thead><tr>" +
      "<th class='sortable' data-expsort='line'>Line</th>" +
      "<th>Expression</th>" +
      "<th class='num'>Combinations</th>" +
      "<th class='num'>Covered</th>" +
      "<th class='sortable' data-expsort='score'>Score</th>" +
      "</tr></thead><tbody></tbody>";
    sec.appendChild(tbl);
    drawExprBody(sec, groups);
    sec.addEventListener("click", function (e) {
      var th = e.target.closest("[data-expsort]");
      var tw = e.target.closest("[data-eg]");
      if (th) {
        var key = th.getAttribute("data-expsort");
        if (exprSort.key === key) exprSort.dir = (exprSort.dir === "asc") ? "desc" : "asc";
        else { exprSort.key = key; exprSort.dir = (key === "score") ? "desc" : "asc"; }
        drawExprBody(sec, groups);
        return;
      }
      if (tw) {
        var gi = tw.getAttribute("data-eg");
        var det = sec.querySelector("[data-egd='" + gi + "']");
        var open = det.style.display !== "none";
        det.style.display = open ? "none" : "";
        tw.textContent = open ? "\u25ba" : "\u25bc";
      }
    });
  }
  // ---- toggle coverage: signal -> bit -> direction ----
  function togParts(o) {
    var i = o.lastIndexOf(":");
    return i >= 0 ? { net: o.slice(0, i), dir: o.slice(i + 1) } : { net: o, dir: "" };
  }
  function sigBase(net) {
    var b = net;
    while (/\[\d+\]$/.test(b)) b = b.replace(/\[\d+\]$/, "");
    return b;
  }
  function groupBits(points) {
    var map = {};
    points.forEach(function (p) {
      var c = togParts(p.comment || "");
      var key = (p.file || "") + "#" + p.line + "#" + (p.h || "") + "#" + c.net;
      (map[key] = map[key] || []).push({ rec: p, net: c.net, dir: c.dir });
    });
    var out = [];
    var idx = 0;
    Object.keys(map).forEach(function (k) {
      var list = map[k];
      out.push({
        id: idx++,
        file: list[0].rec.file || "",
        line: list[0].rec.line || 0,
        h: list[0].rec.h || "",
        label: list[0].net,
        total: list.length,
        hit: list.filter(function (x) { return x.rec.count > 0; }).length,
        dirs: list
      });
    });
    return out;
  }
  function groupTog(points) {
    var bits = groupBits(points);
    var map = {};
    var out = [];
    bits.forEach(function (b) {
      var base = sigBase(b.label);
      var key = (b.file || "") + "#" + b.line + "#" + (b.h || "") + "#" + base;
      var s = map[key];
      if (!s) {
        s = { id: out.length, file: b.file, line: b.line, h: b.h, base: base,
              totalBits: 0, hitBits: 0, totalDirs: 0, hitDirs: 0, bits: [] };
        map[key] = s;
        out.push(s);
      }
      s.totalBits++;
      if (b.hit === b.total) s.hitBits++;
      s.totalDirs += b.total;
      s.hitDirs += b.hit;
      s.bits.push(b);
    });
    return out;
  }
  var togSort = { key: "line", dir: "asc" };
  function togArrow(key) {
    return togSort.key === key ? (togSort.dir === "asc" ? " \u25b2" : " \u25bc") : "";
  }
  function bitScore(b) {
    return b.total ? 100 * b.hit / b.total : null;
  }

  // direction sub-table for one bit (its 0->1 / 1->0 records)
  function dirTableHtml(b) {
    return "<table class='pts sub'><thead><tr>" +
      "<th>Direction</th><th class='num'>Hits</th><th>Status</th></tr></thead><tbody>" +
      b.dirs.map(function (x) {
        var hit = x.rec.count > 0;
        return "<tr><td>" + esc(x.dir) + "</td><td class='num'>" + x.rec.count +
          "</td><td class='st " + (hit ? "g" : "r") + "'>" + (hit ? "covered" : "missed") + "</td></tr>";
      }).join("") + "</tbody></table>";
  }

  function drawTogBody(sec, groups) {
    sec.querySelectorAll("[data-togsort]").forEach(function (th) {
      var k = th.getAttribute("data-togsort");
      th.innerHTML = (k === "line" ? "Line" : "Score") + togArrow(k);
    });
    var body = sec.querySelector("table.pts tbody");
    body.innerHTML = "";
    var sorted = groups.slice().sort(function (a, b) {
      var d = (togSort.dir === "asc") ? 1 : -1;
      if (togSort.key === "score") {
        var sa = a.totalBits ? 100 * a.hitBits / a.totalBits : 0, sb = b.totalBits ? 100 * b.hitBits / b.totalBits : 0;
        if (sa !== sb) return (sb - sa) * d;
        return (a.line - b.line) * d;
      }
      if (a.line !== b.line) return (a.line - b.line) * d;
      return a.base.localeCompare(b.base);
    });
    sorted.forEach(function (s) {
      var sc = s.totalBits ? 100 * s.hitBits / s.totalBits : null;
      var row = document.createElement("tr");
      var sidx = srcIdx(s.file);
      row.innerHTML = "<td class='num'>" + (sidx >= 0 ? "<a class='line-link' href='#file/" + sidx + "/" + s.line + "'>" + s.line + "</a>" : s.line) + "</td>" +
        "<td class='name' style='padding-left:8px'><span class='twisty' data-tg='" + s.id + "'>\u25ba</span> <code class='net'>" +
        esc(s.base) + "</code></td>" +
        "<td class='num'>" + s.totalBits + "</td>" +
        "<td class='num'>" + s.hitBits + "</td>" +
        "<td class='pcell'>" + cell(sc) + "</td>";
      body.appendChild(row);
      var det = document.createElement("tr");
      det.className = "tog-detail";
      det.style.display = "none";
      det.setAttribute("data-tgd", s.id);
      if (s.totalBits === 1 && s.bits[0].label === s.base) {
        // single-bit signal: expand straight to its direction records
        det.innerHTML = "<td colspan='5' class='tog-sub'>" + dirTableHtml(s.bits[0]) + "</td>";
      } else {
        var bitsHtml = s.bits.map(function (b) {
          var bsc = bitScore(b);
          return "<tr>" +
            "<td class='name'><span class='twisty' data-tbit='" + b.id + "'>\u25ba</span> <code class='net'>" + esc(b.label) + "</code></td>" +
            "<td class='num'>" + b.total + "</td>" +
            "<td class='num'>" + b.hit + "</td>" +
            "<td class='pcell'>" + cell(bsc) + "</td></tr>" +
            "<tr class='tog-bdet' style='display:none' data-tbd='" + b.id + "'>" +
            "<td colspan='4' class='tog-bsub'>" + dirTableHtml(b) + "</td></tr>";
        }).join("");
        det.innerHTML = "<td colspan='5' class='tog-sub'><table class='pts'>" +
          "<thead><tr><th>Bit</th><th class='num'>Directions</th><th class='num'>Covered</th><th class='num'>Score</th></tr></thead>" +
          "<tbody>" + bitsHtml + "</tbody></table></td>";
      }
      body.appendChild(det);
    });
  }
  function drawTogGroups(sec, points) {
    var groups = groupTog(points);
    if (!groups.length) {
      sec.innerHTML += "<div class='empty'>No toggle points.</div>";
      return;
    }
    var bitsTotal = groups.reduce(function (n, g) { return n + g.totalBits; }, 0);
    sec.innerHTML += "<p class='hint'>" + groups.length + " signal(s), " + bitsTotal + " bit(s), " + points.length +
      " direction records. Click the Line or Score header to sort; click a signal to see its bits; click a bit to see its 0->1 / 1->0 records.</p>";
    var tbl = document.createElement("table");
    tbl.className = "pts";
    tbl.innerHTML = "<thead><tr>" +
      "<th class='sortable' data-togsort='line'>Line</th>" +
      "<th>Signal</th>" +
      "<th class='num'>Bits</th>" +
      "<th class='num'>Bits covered</th>" +
      "<th class='sortable' data-togsort='score'>Score</th>" +
      "</tr></thead><tbody></tbody>";
    sec.appendChild(tbl);
    drawTogBody(sec, groups);
    sec.addEventListener("click", function (e) {
      var th = e.target.closest("[data-togsort]");
      var tw = e.target.closest("[data-tg]");
      var tb = e.target.closest("[data-tbit]");
      if (th) {
        var key = th.getAttribute("data-togsort");
        if (togSort.key === key) togSort.dir = (togSort.dir === "asc") ? "desc" : "asc";
        else { togSort.key = key; togSort.dir = (key === "score") ? "desc" : "asc"; }
        drawTogBody(sec, groups);
        return;
      }
      if (tw) {
        var gi = tw.getAttribute("data-tg");
        var det = sec.querySelector("[data-tgd='" + gi + "']");
        var open = det.style.display !== "none";
        det.style.display = open ? "none" : "";
        tw.textContent = open ? "\u25ba" : "\u25bc";
        return;
      }
      if (tb) {
        var bi = tb.getAttribute("data-tbit");
        var bd = sec.querySelector("[data-tbd='" + bi + "']");
        var bopen = bd.style.display !== "none";
        bd.style.display = bopen ? "none" : "";
        tb.textContent = bopen ? "\u25ba" : "\u25bc";
      }
    });
  }

  function renderTypeDetail(kind, i, type) {
    var r = kind === "inst" ? instRows[i] : duRows[i];
    app.innerHTML = "";
    app.appendChild(header((kind === "inst" ? "Instance: " : "Design unit: ") + r.name + " \u00b7 " + type, DATA.srcHtml));
    app.appendChild(backBtn("#detail/" + kind + "/" + i, "\u2190 " + r.name));
    if (type === "covergroup") {
      var fsec = document.createElement("section");
      fsec.className = "cg";
      var fscore = r.functional;
      fsec.innerHTML = "<h2>Functional coverage (covergroups)" + (fscore && fscore.score != null ? " \u00b7 " + fscore.score.toFixed(1) + "%" : "") + "</h2>";
      if (r.covergroups && r.covergroups.length) {
        var idx = 0;
        r.covergroups.forEach(function (g) { fsec.innerHTML += cgGroupBlock(g, idx++); });
        window.__cgData = r.covergroups;
      } else {
        fsec.innerHTML += "<div class='empty'>No covergroup data for this module.</div>";
      }
      app.appendChild(fsec);
      drawCgTables();
      fsec.addEventListener("click", function (e) {
        var tw = e.target.closest("[data-cg-tw]");
        var th = e.target.closest("[data-cgsort]");
        if (tw) { toggleCgFold(fsec, tw); return; }
        if (th) {
          cgSort.dir = cgSort.dir === null ? "desc" : cgSort.dir === "desc" ? "asc" : null;
          updateCgArrows(fsec);
          drawCgTables();
        }
      });
      return;
    }
    var rows = (r.points || []).filter(function (p) { return p.type === type; });
    if (type === "expr") {
      var esec = document.createElement("section");
      esec.innerHTML = "<h2>Expression coverage</h2>";
      app.appendChild(esec);
      drawExprGroups(esec, rows);
      return;
    }
    if (type === "toggle") {
      var tsec = document.createElement("section");
      tsec.innerHTML = "<h2>Toggle coverage</h2>";
      app.appendChild(tsec);
      drawTogGroups(tsec, rows);
      return;
    }
    if (!sortState[type]) sortState[type] = { key: "line", dir: "asc" };
    var sec = document.createElement("section");
    sec.innerHTML = "<h2>" + esc(type) + " coverage (" + rows.length + " points)</h2>";
    var st = sortState[type];
    var tbl = document.createElement("table");
    tbl.className = "tree";
    tbl.innerHTML = "<thead><tr>" +
      "<th class='sortable' data-sort='line'>Line" + (st.key === "line" ? (st.dir === "asc" ? " \u25b2" : " \u25bc") : "") + "</th>" +
      "<th>Comment</th>" +
      "<th>Source</th>" +
      "<th class='sortable' data-sort='status'>Status" + (st.key === "status" ? (st.dir === "asc" ? " \u25b2" : " \u25bc") : "") + "</th>" +
      "<th>Hits</th><th>Goal</th></tr></thead><tbody class='td-body'></tbody>";
    sec.appendChild(tbl);
    app.appendChild(sec);
    sec.addEventListener("click", function (e) {
      var th = e.target.closest("[data-sort]");
      if (!th) return;
      var key = th.getAttribute("data-sort");
      if (st.key === key) st.dir = (st.dir === "asc") ? "desc" : "asc";
      else { st.key = key; st.dir = "asc"; }
      drawDetail(sec, rows);
    });
    drawDetail(sec, rows);
  }

  function renderFile(idx, target) {
    var f = SRC_ORDER[idx];
    if (f === undefined) {
      render();
      return;
    }
    app.innerHTML = "";
    app.appendChild(header("Source: " + f.split("/").pop(),
      "<span class='file'>" + esc(f) + "</span>"));
    var back = document.createElement("button");
    back.className = "backbtn";
    back.innerHTML = "\u2190 Back to report";
    back.addEventListener("click", function () { location.hash = ""; });
    app.appendChild(back);
    var lines = SRC[f].lines;
    var rows = [];
    for (var i = 0; i < lines.length; i++) {
      var n = i + 1;
      rows.push("<tr" + (n === target ? " class='target'" : "") + ">" +
        "<td class='num'><a class='line-link' href='#file/" + idx + "/" + n + "'>" + n + "</a></td>" +
        "<td class='code-line'>" + (lines[i] === "" ? "&nbsp;" : hl(lines[i])) + "</td></tr>");
    }
    var tbl = document.createElement("table");
    tbl.className = "pts";
    tbl.innerHTML = "<thead><tr><th class='num'>Line</th><th>Source</th></tr></thead><tbody>" +
      rows.join("") + "</tbody>";
    app.appendChild(tbl);
    if (target) {
      var tr = tbl.querySelector("tr.target");
      if (tr) tr.scrollIntoView({ block: "center" });
    }
  }
  function route() {
    var h = location.hash.replace(/^#/, "");
    var parts = h.split("/").filter(Boolean);
    if (parts[0] === "file" && parts[1] !== undefined) {
      renderFile(+parts[1], parts[2] ? +parts[2] : null);
      return;
    }
    if (parts[0] === "detail" && parts.length >= 3) {
      var kind = parts[1];
      var i = +parts[2];
      if (parts.length >= 4) renderTypeDetail(kind, i, parts[3]);
      else renderNode(kind, i);
      window.scrollTo(0, 0);
      return;
    }
    render();
  }
  function gotoDetail(kind, i, type) {
    var h = "#detail/" + kind + "/" + i + (type ? "/" + type : "");
    if (location.hash === h) route();
    else location.hash = h;
  }
  window.addEventListener("hashchange", route);
  route();
})();
"""
