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
        i: p.i !== undefined ? p.i : "",
        tag: p.tag,
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

  function header(title, srcHtml, center) {
    var h = document.createElement("header");
    var t = document.createElement("h1");
    t.textContent = title;
    if (center) t.className = "center";
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
        c += "<td class='pcell linky' data-type='" + tp + "'>" + cell(scoreOf(r.tally, tp)) + "</td>";
      });
      c += '<td class="pcell linky" data-type="func">' + cell(funcScore(r.functional)) + "</td>";
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
      var pc = e.target.closest("td.pcell.linky");
      if (pc) {
        e.preventDefault();
        var t = pc.getAttribute("data-type");
        gotoDetail("inst", +e.target.closest("tr").dataset.idx, t === "func" ? "covergroup" : t);
        return;
      }
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
        DATA.codeTypes.map(function (tp) { return "<td class='pcell linky' data-type='" + tp + "'>" + cell(scoreOf(r.tally, tp)) + "</td>"; }).join("") +
        '<td class="pcell linky" data-type="func">' + cell(funcScore(r.functional)) + "</td>";
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
      if (nm) { e.preventDefault(); gotoDetail("du", +nm.getAttribute("href").split("/")[2]); return; }
      var pc = e.target.closest("td.pcell.linky");
      if (pc) {
        e.preventDefault();
        var t = pc.getAttribute("data-type");
        gotoDetail("du", +e.target.closest("tr").dataset.idx, t === "func" ? "covergroup" : t);
      }
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
    app.appendChild(header(DATA.title, DATA.srcHtml, true));
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

  // ---- shared detail-table state ----
  var sortState = {};

  // ---- functional coverage: covergroup -> coverpoint -> bin ----
  function groupCg(covergroups) {
    var out = [];
    var cIdx = 0;
    covergroups.forEach(function (g) {
      var cps = g.items.map(function (it) {
        return {
          id: cIdx++,
          label: it.name,
          weight: it.weight,
          totalBins: it.bins.length,
          hitBins: it.bins.filter(function (b) { return !b.binType && b.covered; }).length,
          score: it.score,
          bins: it.bins.map(function (b) {
            return { label: b.name, count: b.count, atLeast: b.atLeast || 1,
                     covered: b.covered, binType: b.binType || "" };
          })
        };
      });
      out.push({
        id: out.length,
        group: g.group,
        totalCps: cps.length,
        hitCps: cps.filter(function (c) { return c.score >= 100; }).length,
        score: g.score,
        cps: cps
      });
    });
    return out;
  }
  var cgSort = { key: "score", dir: "desc" };
  var cpSort = { key: "score", dir: "desc" };
  function cgArrow(key) {
    return cgSort.key === key ? (cgSort.dir === "asc" ? " \u25b2" : " \u25bc") : "";
  }
  function cpArrow(key) {
    return cpSort.key === key ? (cpSort.dir === "asc" ? " \u25b2" : " \u25bc") : "";
  }
  function binTableHtml(c) {
    return "<table class='pts sub'><thead><tr>" +
      "<th>Bin</th><th class='num'>Hits</th><th class='num'>Goal</th><th>Status</th></tr></thead><tbody>" +
      c.bins.map(function (b) {
        var nm = esc(shortName(b.label));
        var goal = b.atLeast > 1 ? b.atLeast : "";
        if (b.binType) {
          var ih = b.count > 0;
          var st = b.binType === "illegal" ? (ih ? "illegal hit" : "not hit") : b.binType;
          return "<tr class='bin-" + b.binType + "'><td>" + nm + "</td>" +
            "<td class='num'>" + b.count + "</td><td class='num'>" + goal + "</td>" +
            "<td class='st " + (ih ? "r" : "g") + "'>" + st + "</td></tr>";
        }
        return "<tr><td>" + nm + "</td><td class='num'>" + b.count +
          "</td><td class='num'>" + goal + "</td>" +
          "<td class='st " + (b.covered ? "g" : "r") + "'>" + (b.covered ? "covered" : "missed") + "</td></tr>";
      }).join("") + "</tbody></table>";
  }
  function cgRowHtml(c) {
    return "<tr>" +
      "<td class='name'><span class='twisty' data-cp='" + c.id + "'>\u25ba</span> <code class='net'>" + esc(shortName(c.label)) + "</code></td>" +
      "<td class='num'>" + c.weight + "</td>" +
      "<td class='num'>" + c.totalBins + "</td>" +
      "<td class='num'>" + c.hitBins + "</td>" +
      "<td class='pcell'>" + cell(c.score) + "</td></tr>" +
      "<tr class='cg-bdet' style='display:none' data-cbd='" + c.id + "'>" +
      "<td colspan='5' class='cg-bsub'>" + binTableHtml(c) + "</td></tr>";
  }
  function drawCgCps(sec) {
    var openCps = {};
    sec.querySelectorAll("[data-cbd]").forEach(function (r) {
      if (r.style.display !== "none") openCps[r.getAttribute("data-cbd")] = true;
    });
    sec.querySelectorAll("[data-cgpsort]").forEach(function (th) {
      th.innerHTML = "Score" + cpArrow("score");
    });
    sec.querySelectorAll("tbody.cg-cps").forEach(function (tb) {
      var g = null;
      (sec.__groups || []).forEach(function (x) { if (x.id === +tb.getAttribute("data-cgcp")) g = x; });
      if (!g) return;
      tb.innerHTML = "";
      var items = g.cps.slice().sort(function (a, b) {
        var d = (cpSort.dir === "asc") ? 1 : -1;
        if (cpSort.key === "score") {
          var sa = a.score == null ? -1 : a.score, sb = b.score == null ? -1 : b.score;
          if (sa !== sb) return (sb - sa) * d;
          return a.label.localeCompare(b.label);
        }
        return a.label.localeCompare(b.label) * d;
      });
      items.forEach(function (c) {
        var el = document.createElement("table");
        el.innerHTML = "<tbody>" + cgRowHtml(c) + "</tbody>";
        var src = el.firstChild;
        while (src.firstChild) tb.appendChild(src.firstChild);
        var bdet = tb.querySelector("[data-cbd='" + c.id + "']");
        if (openCps[c.id]) {
          bdet.style.display = "";
          tb.querySelector("[data-cp='" + c.id + "']").textContent = "\u25bc";
        }
      });
    });
  }
  function drawCgBody(sec, groups) {
    var openGroups = [];
    sec.querySelectorAll("tr[data-cgd]").forEach(function (r) {
      if (r.style.display !== "none") openGroups.push(+r.getAttribute("data-cgd"));
    });
    sec.querySelectorAll("[data-cgsort]").forEach(function (th) {
      var k = th.getAttribute("data-cgsort");
      th.innerHTML = (k === "score" ? "Score" : "Covergroup") + cgArrow(k);
    });
    var body = sec.querySelector("table.pts tbody");
    body.innerHTML = "";
    var sorted = groups.slice().sort(function (a, b) {
      var d = (cgSort.dir === "asc") ? 1 : -1;
      if (cgSort.key === "score") {
        var sa = a.score == null ? -1 : a.score, sb = b.score == null ? -1 : b.score;
        if (sa !== sb) return (sb - sa) * d;
        return a.group.localeCompare(b.group);
      }
      return a.group.localeCompare(b.group) * d;
    });
    sorted.forEach(function (g) {
      var row = document.createElement("tr");
      row.innerHTML = "<td class='name'><span class='twisty' data-cg='" + g.id + "'>\u25ba</span> <code class='net'>" +
        esc(shortName(g.group)) + "</code></td>" +
        "<td class='num'>" + g.totalCps + "</td>" +
        "<td class='num'>" + g.hitCps + "</td>" +
        "<td class='pcell'>" + cell(g.score) + "</td>";
      body.appendChild(row);
      var det = document.createElement("tr");
      det.className = "cg-detail";
      det.style.display = "none";
      det.setAttribute("data-cgd", g.id);
      det.innerHTML = "<td colspan='4' class='cg-sub'><table class='pts'>" +
        "<thead><tr><th>Coverpoint</th><th class='num'>Weight</th><th class='num'>Bins</th><th class='num'>Covered</th>" +
        "<th class='sortable' data-cgpsort='score'>Score" + cpArrow("score") + "</th></tr></thead>" +
        "<tbody class='cg-cps' data-cgcp='" + g.id + "'></tbody></table></td>";
      body.appendChild(det);
      if (openGroups.indexOf(g.id) >= 0) {
        det.style.display = "";
        row.querySelector("[data-cg]").textContent = "\u25bc";
      }
    });
    drawCgCps(sec);
  }
  function drawCgGroups(sec, covergroups, overall) {
    var groups = groupCg(covergroups);
    sec.__groups = groups;
    if (!groups.length) {
      sec.innerHTML += "<div class='empty'>No covergroup data for this module.</div>";
      return;
    }
    var cpsTotal = groups.reduce(function (n, g) { return n + g.totalCps; }, 0);
    var binsTotal = groups.reduce(function (n, g) { return n + g.cps.reduce(function (m, c) { return m + c.totalBins; }, 0); }, 0);
    var tail = (overall != null) ? " \u00b7 overall " + overall.toFixed(1) + "%" : "";
    sec.innerHTML += "<p class='hint'>" + groups.length + " covergroup(s), " + cpsTotal + " coverpoint(s), " + binsTotal +
      " bin(s)" + tail + ". Click the Covergroup or Score header to sort; click a covergroup to see its coverpoints (their Score header sorts them too); click a coverpoint to see its bins.</p>";
    var tbl = document.createElement("table");
    tbl.className = "pts";
    tbl.innerHTML = "<thead><tr>" +
      "<th class='sortable' data-cgsort='group'>Covergroup</th>" +
      "<th class='num'>Coverpoints</th>" +
      "<th class='num'>Covered</th>" +
      "<th class='sortable' data-cgsort='score'>Score</th>" +
      "</tr></thead><tbody></tbody>";
    sec.appendChild(tbl);
    drawCgBody(sec, groups);
    sec.addEventListener("click", function (e) {
      var cth = e.target.closest("[data-cgpsort]");
      if (cth) {
        cpSort.dir = (cpSort.dir === "desc") ? "asc" : "desc";
        drawCgCps(sec);
        return;
      }
      var th = e.target.closest("[data-cgsort]");
      var tw = e.target.closest("[data-cg]");
      var cp = e.target.closest("[data-cp]");
      if (th) {
        var key = th.getAttribute("data-cgsort");
        if (cgSort.key === key) cgSort.dir = (cgSort.dir === "asc") ? "desc" : "asc";
        else { cgSort.key = key; cgSort.dir = (key === "score") ? "desc" : "asc"; }
        drawCgBody(sec, groups);
        return;
      }
      if (tw) {
        var gi = tw.getAttribute("data-cg");
        var det = sec.querySelector("[data-cgd='" + gi + "']");
        var open = det.style.display !== "none";
        det.style.display = open ? "none" : "";
        tw.textContent = open ? "\u25ba" : "\u25bc";
        return;
      }
      if (cp) {
        var ci = cp.getAttribute("data-cp");
        var bdet = sec.querySelector("[data-cbd='" + ci + "']");
        var open2 = bdet.style.display !== "none";
        bdet.style.display = open2 ? "none" : "";
        cp.textContent = open2 ? "\u25ba" : "\u25bc";
      }
    });
  }
  // The instance suffix that identifies a record: the trailing [n] (or
  // the * of a combined instance) for a single-level h, and the whole
  // decoded begin path when it nests (several generate-for levels).
  function iterOf(pt) {
    if (!pt.h) return "";
    var parts = pt.h.split(".");
    if (parts.length > 1) return pt.h;
    var m = parts[0].match(/\[(\*|\d+)\]/);
    return m ? "[" + m[1] + "]" : "";
  }
  // Numeric-index ordering for generate iterations: the sequence of
  // bracket indexes in path order ([0].g[1] -> [0,1]).  A plain level
  // sorts before a generated one; [*] sorts last.
  function iterKey(h) {
    if (!h) return [];
    var out = [];
    h.split(".").forEach(function (seg) {
      var m = seg.match(/^(.*?)[\[]([^[\]]*)\]$/);
      if (m) out.push([1, m[2] === "*" ? 1e9 : parseInt(m[2], 10)]);
      else out.push([0, 0]);
    });
    return out;
  }
  function cmpIter(a, b) {
    var ka = iterKey(a.h), kb = iterKey(b.h);
    var n = Math.max(ka.length, kb.length);
    for (var i = 0; i < n; i++) {
      var x = ka[i] || [0, 0], y = kb[i] || [0, 0];
      if (x[0] !== y[0]) return x[0] - y[0];
      if (x[1] !== y[1]) return x[1] - y[1];
    }
    return 0;
  }
  function srcCell(p) {
    var t = srcLine(p.file, p.line);
    if (t === null) return "<span class='dim'>source unavailable</span>";
    return (t === "") ? "&nbsp;" : hl(t);
  }

  // line/branch detail: one row per source unit (the line, or the
  // branch at a line), the generate-for iterations collapsed beneath
  // it, ordered by numeric index. Line records carry a coverage type
  // in the comment field (block, case, elsif, else), branch records a
  // branch kind (if, else); the key and label include it, so each row
  // shows the type before the badge.
  function groupPoints(points) {
    var map = {};
    points.forEach(function (p) {
      var key = (p.file || "") + "#" + p.line + "#" + (p.comment || "");
      (map[key] = map[key] || []).push(p);
    });
    var out = [];
    Object.keys(map).forEach(function (k) {
      var list = map[k].slice().sort(cmpIter);
      out.push({
        id: out.length,
        file: list[0].file || "",
        line: list[0].line || 0,
        label: list[0].comment || "",
        total: list.length,
        hit: list.filter(function (p) { return p.covered; }).length,
        points: list
      });
    });
    return out;
  }

  function drawDetail(sec, rows) {
    if (!rows.length) return;
    var st = sortState[rows[0].type] || { key: "line", dir: "asc" };
    var body = sec.querySelector(".td-body");
    body.innerHTML = "";
    sec.querySelectorAll("th.sortable").forEach(function (th) {
      var base = (th.getAttribute("data-sort") === "line") ? "Line" : "Status";
      th.innerHTML = base + (th.getAttribute("data-sort") === st.key ? (st.dir === "asc" ? " \u25b2" : " \u25bc") : "");
    });
    var lineCell = function (p) {
      var li = srcIdx(p.file);
      return (li >= 0 ? "<a class='line-link' href='#file/" + li + "/" + p.line + "'>" + p.line + "</a>" : p.line);
    };
    var flatRow = function (p) {
      var it = iterOf(p);
      var tr = document.createElement("tr");
      tr.innerHTML = "<td class='count'>" + lineCell(p) + (it ? ' <span class="iter">' + esc(it) + "</span>" : "") + "</td>" +
        "<td class='comment'>" + esc(p.comment || "") + "</td>" +
        "<td class='code-line'>" + srcCell(p) + "</td>" +
        "<td class='st " + (p.covered ? "g" : "r") + "'>" + (p.covered ? "covered" : "missed") + "</td>" +
        "<td class='count'>" + p.count + "</td>" +
        "<td class='count'>" + (p.atLeast || 1) + "</td>";
      return tr;
    };
    if (rows[0].type !== "line" && rows[0].type !== "branch") {
      var sorted = rows.slice().sort(function (a, b) {
        var d = (st.dir === "asc") ? 1 : -1;
        if (st.key === "status") {
          if (a.covered !== b.covered) return (a.covered ? -1 : 1) * d;
        }
        return (a.line - b.line) * d;
      });
      sorted.forEach(function (p) { body.appendChild(flatRow(p)); });
      return;
    }
    var groups = groupPoints(rows);
    var d = (st.dir === "asc") ? 1 : -1;
    var rank = function (g) { return (g.hit === g.total) ? 2 : (g.hit ? 1 : 0); };
    groups.sort(function (a, b) {
      if (st.key === "status") {
        var r = rank(a) - rank(b);
        if (r) return r * d;
      }
      if (a.line !== b.line) return (a.line - b.line) * d;
      if (a.file !== b.file) return (a.file < b.file ? -1 : 1) * d;
      // same line + file: the .dat emission order (ids are assigned in
      // first-seen order), e.g. if before else
      return a.id - b.id;
    });
    groups.forEach(function (g) {
      if (g.total === 1) {
        // a single record: plain flat row, as before
        body.appendChild(flatRow(g.points[0]));
        return;
      }
      var row = document.createElement("tr");
      var cls = (g.hit === g.total) ? "g" : (g.hit ? "o" : "r");
      var txt = (g.hit === g.total) ? "covered" : (g.hit ? "partial" : "missed");
      row.innerHTML = "<td class='count'>" + lineCell(g.points[0]) + "</td>" +
        "<td class='name' style='padding-left:8px'><span class='twisty' data-pg='" + g.id + "'>\u25ba</span>" +
        (g.label ? ' <code class="expr">' + esc(g.label) + "</code>" : "") +
        ' <span class="collbadge" title="generate-for iterations">' + g.total + "</span></td>" +
        "<td class='code-line'>" + srcCell(g.points[0]) + "</td>" +
        "<td class='st " + cls + "'>" + txt + "</td>" +
        "<td class='count'>" + g.hit + "</td>" +
        "<td class='count'>" + g.total + "</td>";
      body.appendChild(row);
      var det = document.createElement("tr");
      det.className = "pg-detail";
      det.style.display = "none";
      det.setAttribute("data-pgd", g.id);
      // <tr> cannot be nested: the instances render in a sub-table
      // inside a spanning cell (same structure as expr-detail).
      var sub = "<table class='pts sub'><tr class='h'>" +
        "<th class='num'>Instance</th>" +
        "<th class='name'>Status</th>" +
        "<th class='count'>Hits</th>" +
        "<th class='count'>Goal</th></tr>";
      for (var pgi = 0; pgi < g.points.length; pgi++) {
        var p = g.points[pgi];
        var lab = p.i || p.comment || "";
        sub += "<tr><td class='name'>" + (lab ? '<span class="iter">' + esc(lab) + "</span>" : "") + "</td>" +
          '<td class="st ' + (p.covered ? "g" : "r") + '">' + (p.covered ? "covered" : "missed") + "</td>" +
          '<td class="count">' + p.count + '</td>' +
          '<td class="count">' + (p.atLeast || 1) + "</td></tr>";
      }
      sub += "</table>";
      det.innerHTML = "<td colspan='6' class='pg-sub'>" + sub + "</td>";
      body.appendChild(det);
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
      var i = t.lastIndexOf("==");
      if (i < 0) { ops.push(t); vals.push("?"); return; }
      var v = t.slice(i + 2).trim();
      var l = t.slice(0, i).trim();
      if (l.length > 2 && /^\(.*\)$/.test(l)) {
        // the operand is itself a wrapped comparison (Verilator nests
        // them: "(a == b)==0"): display the inner comparison
        l = l.slice(1, -1).trim();
      }
      ops.push(l); vals.push(v);
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
      // group on the condition (the comment minus its " => result"),
      // so all generate-for iterations of one expression collapse
      // under a single row
      var cond = (p.comment || "").split(" => ")[0];
      var key = (p.file || "") + "#" + p.line + "#" + cond;
      (map[key] = map[key] || []).push(p);
    });
    var out = [];
    var idx = 0;
    Object.keys(map).forEach(function (k) {
      var list = map[k].slice().sort(cmpIter);
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
        if (sa !== sb) return (sa - sb) * d;
        // same score: line number, then file, then .dat emission order
        if (a.line !== b.line) return a.line - b.line;
        if (a.file !== b.file) return a.file < b.file ? -1 : 1;
        return a.id - b.id;
      }
      if (a.line !== b.line) return (a.line - b.line) * d;
      if (a.file !== b.file) return (a.file < b.file ? -1 : 1) * d;
      // same line + file: the .dat emission order
      return a.id - b.id;
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
        "<th>Iteration / Combination</th><th class='num'>Hits</th><th>Status</th></tr></thead><tbody>" +
        g.combos.map(function (c) {
          var it = iterOf(c);
          var hit = c.count > 0;
          return "<tr><td>" + (it ? '<span class="iter">' + esc(it) + "</span> " : "") + esc(c.comment || "") + "</td><td class='num'>" + c.count +
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
      var sit = iterOf(s);
      row.innerHTML = "<td class='num'>" + (sidx >= 0 ? "<a class='line-link' href='#file/" + sidx + "/" + s.line + "'>" + s.line + "</a>" : s.line) + "</td>" +
        "<td class='name' style='padding-left:8px'><span class='twisty' data-tg='" + s.id + "'>\u25ba</span>" + (sit ? ' <span class="iter">' + esc(sit) + "</span>" : "") + " <code class='net'>" +
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

  // fsm: the comment is "<fullpath>.<signal>::<detail>" -- the signal is the
  // last dot-segment of the path; the detail is a state (fsm_state) or a
  // from->to transition (fsm_arc). We fold each signal's records together and
  // list its states / transitions when expanded, using the same layout as the
  // toggle and expression pages.
  function fsmParts(o) {
    var ci = o.indexOf("::");
    if (ci < 0) return { sig: o, detail: "" };
    var left = o.slice(0, ci);
    var detail = o.slice(ci + 2);
    var di = left.lastIndexOf(".");
    var sig = di >= 0 ? left.slice(di + 1) : left;
    return { sig: sig, detail: detail };
  }
  function groupFsm(points, type) {
    var map = {};
    points.forEach(function (p) {
      var c = fsmParts(p.comment || "");
      var key = (p.file || "") + "#" + p.line + "#" + (p.h || "") + "#" + c.sig;
      var g = map[key];
      if (!g) {
        g = { id: 0, file: p.file || "", line: p.line || 0, h: p.h || "",
              sig: c.sig, type: type, total: 0, hit: 0, items: [] };
        map[key] = g;
      }
      g.total++;
      if (p.count > 0) g.hit++;
      g.items.push({ detail: c.detail, rec: p });
    });
    var out = [];
    var idx = 0;
    Object.keys(map).forEach(function (k) {
      map[k].id = idx++;
      out.push(map[k]);
    });
    return out;
  }
  var fsmSort = {};
  function fsmArrow(type, key) {
    var s = fsmSort[type];
    return s && s.key === key ? (s.dir === "asc" ? " \u25b2" : " \u25bc") : "";
  }
  // detail sub-table: one row per state (fsm_state) or transition (fsm_arc)
  function fsmDetailTableHtml(g) {
    var head = g.type === "fsm_arc" ? "Transition" : "State";
    return "<table class='pts sub'><thead><tr>" +
      "<th>" + head + "</th><th class='num'>Hits</th><th>Status</th></tr></thead><tbody>" +
      g.items.map(function (x) {
        var hit = x.rec.count > 0;
        return "<tr><td>" + esc(x.detail) + "</td><td class='num'>" + x.rec.count +
          "</td><td class='st " + (hit ? "g" : "r") + "'>" + (hit ? "covered" : "missed") + "</td></tr>";
      }).join("") + "</tbody></table>";
  }
  function drawFsmBody(sec, groups) {
    var type = groups[0].type;
    sec.querySelectorAll("[data-fsmsort]").forEach(function (th) {
      var k = th.getAttribute("data-fsmsort");
      th.innerHTML = (k === "line" ? "Line" : "Score") + fsmArrow(type, k);
    });
    var body = sec.querySelector("table.pts tbody");
    body.innerHTML = "";
    var s = fsmSort[type];
    var sorted = groups.slice().sort(function (a, b) {
      var d = (s.dir === "asc") ? 1 : -1;
      if (s.key === "score") {
        var sa = a.total ? 100 * a.hit / a.total : 0, sb = b.total ? 100 * b.hit / b.total : 0;
        if (sa !== sb) return (sb - sa) * d;
        return (a.line - b.line) * d;
      }
      if (a.line !== b.line) return (a.line - b.line) * d;
      return a.sig.localeCompare(b.sig);
    });
    sorted.forEach(function (g) {
      var sc = g.total ? 100 * g.hit / g.total : null;
      var row = document.createElement("tr");
      var sidx = srcIdx(g.file);
      var fit = iterOf(g);
      row.innerHTML = "<td class='num'>" + (sidx >= 0 ? "<a class='line-link' href='#file/" + sidx + "/" + g.line + "'>" + g.line + "</a>" : g.line) + "</td>" +
        "<td class='name' style='padding-left:8px'><span class='twisty' data-fsg='" + g.id + "'>\u25ba</span>" + (fit ? ' <span class="iter">' + esc(fit) + "</span>" : "") + " <code class='net'>" +
        esc(g.sig) + "</code></td>" +
        "<td class='num'>" + g.total + "</td>" +
        "<td class='num'>" + g.hit + "</td>" +
        "<td class='pcell'>" + cell(sc) + "</td>";
      body.appendChild(row);
      var det = document.createElement("tr");
      det.className = "tog-detail";
      det.style.display = "none";
      det.setAttribute("data-fsd", g.id);
      det.innerHTML = "<td colspan='5' class='tog-sub'>" + fsmDetailTableHtml(g) + "</td>";
      body.appendChild(det);
    });
  }
  function drawFsmGroups(sec, points, type) {
    if (!fsmSort[type]) fsmSort[type] = { key: "line", dir: "asc" };
    var groups = groupFsm(points, type);
    if (!groups.length) {
      sec.innerHTML += "<div class='empty'>No " + type + " points.</div>";
      return;
    }
    var colName = type === "fsm_arc" ? "transitions" : "states";
    sec.innerHTML += "<p class='hint'>" + groups.length + " signal(s), " + points.length +
      " " + colName + ". Click the Line or Score header to sort; click a signal to see its " + colName + ".</p>";
    var tbl = document.createElement("table");
    tbl.className = "pts";
    var thName = type === "fsm_arc" ? "Transitions" : "States";
    tbl.innerHTML = "<thead><tr>" +
      "<th class='sortable' data-fsmsort='line'>Line</th>" +
      "<th>Signal</th>" +
      "<th class='num'>" + thName + "</th>" +
      "<th class='num'>" + thName + " covered</th>" +
      "<th class='sortable' data-fsmsort='score'>Score</th>" +
      "</tr></thead><tbody></tbody>";
    sec.appendChild(tbl);
    drawFsmBody(sec, groups);
    sec.addEventListener("click", function (e) {
      var th = e.target.closest("[data-fsmsort]");
      var tw = e.target.closest("[data-fsg]");
      if (th) {
        var key = th.getAttribute("data-fsmsort");
        if (fsmSort[type].key === key) fsmSort[type].dir = (fsmSort[type].dir === "asc") ? "desc" : "asc";
        else { fsmSort[type].key = key; fsmSort[type].dir = (key === "score") ? "desc" : "asc"; }
        drawFsmBody(sec, groups);
        return;
      }
      if (tw) {
        var gi = tw.getAttribute("data-fsg");
        var det = sec.querySelector("[data-fsd='" + gi + "']");
        var open = det.style.display !== "none";
        det.style.display = open ? "none" : "";
        tw.textContent = open ? "\u25ba" : "\u25bc";
      }
    });
  }

  // ---- fsm_arc: switchable graph view (states = nodes, transitions = edges) ----
  var fsmArcView = "table";
  function fsmViewBtns() {
    var div = document.createElement("div");
    div.className = "fsmview";
    [["table", "Table"], ["graph", "Graph"]].forEach(function (v) {
      var b = document.createElement("button");
      b.className = "fview" + (fsmArcView === v[0] ? " on" : "");
      b.textContent = v[1];
      b.setAttribute("data-fview", v[0]);
      div.appendChild(b);
    });
    return div;
  }
  function rectExit(px, py, w, h, qx, qy, pad) {
    var dx = qx - px, dy = qy - py;
    var tx = Math.abs(dx) > 1e-9 ? (w / 2 + pad) / Math.abs(dx) : Infinity;
    var ty = Math.abs(dy) > 1e-9 ? (h / 2 + pad) / Math.abs(dy) : Infinity;
    var t = Math.min(tx, ty);
    return { x: px + dx * t, y: py + dy * t };
  }
  // Order states along the actual transition flow. A DFS from the initial
  // state over the drawn arcs splits them into normal edges and back edges
  // (returns to ancestors); back edges are set aside and longest-path
  // layering over the rest is acyclic by construction, so the rows follow
  // the real flow from the entry. A barycenter re-order inside each layer
  // (seeded by discovery order) minimises crossings. Returns the per-layer
  // grouping, the DFS order, and the back-edge list.
  function fsmLayered(states, arcs, initState) {
    var adj = {};
    states.forEach(function (s) { adj[s] = []; });
    arcs.forEach(function (e) { adj[e.a].push(e); });
    var color = {};
    states.forEach(function (s) { color[s] = 0; });
    var order = [];
    var back = [];
    function dfs(u) {
      color[u] = 1;
      order.push(u);
      adj[u].forEach(function (e) {
        var v = e.b;
        if (color[v] === 0) {
          dfs(v);
        } else if (color[v] === 1) {
          e.back = true;
          back.push(e);
        }
      });
      color[u] = 2;
    }
    if (initState && color[initState] === 0) dfs(initState);
    states.forEach(function (s) { if (color[s] === 0) dfs(s); });
    var layer = {};
    states.forEach(function (s) { layer[s] = 0; });
    var fwd = arcs.filter(function (e) { return !e.back; });
    for (var it = 0; it < states.length; it++) {
      var ch = false;
      fwd.forEach(function (e) {
        if (layer[e.b] < layer[e.a] + 1) { layer[e.b] = layer[e.a] + 1; ch = true; }
      });
      if (!ch) break;
    }
    var maxL = 0;
    states.forEach(function (s) { if (layer[s] > maxL) maxL = layer[s]; });
    var byLayer = [];
    for (var L = 0; L <= maxL; L++) byLayer.push([]);
    states.forEach(function (s) { byLayer[layer[s]].push(s); });
    var pos = {};
    order.forEach(function (s, i) { pos[s] = i; });
    for (var L2 = 1; L2 <= maxL; L2++) {
      var score = {};
      byLayer[L2].forEach(function (s) {
        var sum = 0, n = 0;
        fwd.forEach(function (e) {
          if (e.b === s && layer[e.a] === L2 - 1) { sum += pos[e.a]; n++; }
        });
        score[s] = n ? sum / n : pos[s];
      });
      byLayer[L2].sort(function (a, b) {
        var d = score[a] - score[b];
        return d !== 0 ? d : a.localeCompare(b);
      });
      byLayer[L2].forEach(function (s, i2) { pos[s] = i2; });
    }
    return { byLayer: byLayer, layer: layer, order: order, back: back };
  }
  // Vertical layout: one horizontal row per layer, top-to-bottom. The reset
  // hub (initial state) is pinned to its own top row; boxes are sized to the
  // label so text never overflows. The side margins are widened to fit the
  // outer lanes that return (back) edges travel in, so a dense hub can have
  // several parallel return lanes without any of them touching a box.
  function fsmRowPos(byLayer, initState, upCount) {
    var vgap = 54, hgap = 40, nh = 32;
    var nw = {};
    byLayer.forEach(function (layer) {
      layer.forEach(function (s) { nw[s] = s.length * 7.4 + 22; });
    });
    var rows = [];
    if (initState) rows.push([initState]);
    byLayer.forEach(function (layer) {
      var r = layer.filter(function (s) { return s !== initState; });
      if (r.length) rows.push(r);
    });
    var rowW = [];
    rows.forEach(function (r) {
      var w = 0;
      r.forEach(function (s, i) { if (i) w += hgap; w += nw[s]; });
      rowW.push(w);
    });
    var maxW = 0;
    rowW.forEach(function (w) { if (w > maxW) maxW = w; });
    // Margins are sized for the worst case (every return nested on that
    // side), so the corridor positions computed after placement always fit
    // inside the svg.
    var marginL = upCount ? 14 * upCount + 14 : 26;
    var marginR = upCount ? 14 * upCount + 14 : 26;
    var totalW = maxW + marginL + marginR;
    var totalH = rows.length * (nh + vgap) - vgap + 60;
    var pos = {}, row = {};
    rows.forEach(function (r, ri) {
      var y = 30 + ri * (nh + vgap) + nh / 2;
      var x = marginL + (totalW - marginL - marginR - rowW[ri]) / 2;
      r.forEach(function (s) {
        pos[s] = { x: x + nw[s] / 2, y: y };
        row[s] = ri;
        x += nw[s] + hgap;
      });
    });
    return { pos: pos, w: totalW, h: totalH, nw: nw, row: row, rows: rows,
             marginL: marginL, marginR: marginR };
  }
  // SVG for a single fsm signal's state graph (vertical layout, the initial
  // state pinned to the top). Only covered (hit) transitions are drawn;
  // uncovered paths are counted in a note. Spanning returns to the hub are
  // routed through an outer lane so they never cross a state box.
  function fsmSignalGraphSvg(allPoints) {
    var arcs = allPoints.filter(function (p) { return p.type === "fsm_arc"; });
    if (!arcs.length) return "";
    var stateHits = {};
    allPoints.forEach(function (p) {
      if (p.type === "fsm_state") {
        var i2 = p.comment.indexOf("::");
        if (i2 >= 0) {
          var sn = p.comment.slice(i2 + 2);
          stateHits[sn] = (stateHits[sn] || 0) + p.count;
        }
      }
    });
    // The initial/reset state. Verilator dumps come in two flavors:
    //   - older: only the synthetic reset arcs (from every state to the
    //     initial state) are tagged, so it is the target of the most (the
    //     only) artificial arcs;
    //   - newer: the whole arc space is tagged (every non-design pair is
    //     artificial), so it is instead the target of the most real arcs --
    //     the state the flow converges on; ties go to the most-hit state.
    var artTargets = {}, realTargets = {};
    arcs.forEach(function (p) {
      var t = fsmParts(p.comment).detail.split("->")[1];
      if (!t) return;
      if (p.tag === "artificial") artTargets[t] = (artTargets[t] || 0) + 1;
      else realTargets[t] = (realTargets[t] || 0) + 1;
    });
    var initState = null;
    if (Object.keys(artTargets).length <= 2) {
      var bestA = 0;
      Object.keys(artTargets).forEach(function (t) {
        if (artTargets[t] > bestA) { bestA = artTargets[t]; initState = t; }
      });
    } else {
      var bestR = -1, bestH = -1;
      Object.keys(realTargets).forEach(function (t) {
        var r = realTargets[t], h = stateHits[t] || 0;
        if (r > bestR || (r === bestR && h > bestH)) { bestR = r; bestH = h; initState = t; }
      });
    }
    var set = {};
    arcs.forEach(function (p) {
      fsmParts(p.comment).detail.split("->").forEach(function (s) { if (s) set[s] = true; });
    });
    var states = Object.keys(set);
    var drawn = arcs.filter(function (p) { return p.count > 0; })
      .map(function (p) {
        var d = fsmParts(p.comment).detail.split("->");
        return { a: d[0], b: d[1] };
      });
    var lay2 = fsmLayered(states, drawn, initState);
    var lay = fsmRowPos(lay2.byLayer, initState, drawn.length);
    // “Long” arcs — every drawn arc that is not a straight vertical
    // between adjacent rows (returns included) — travel in
    // right-angle corridors; the margin is recomputed for their
    // exact count (relative x distances are invariant under the
    // re-centering).
    var longList = drawn.filter(function (e) {
      var sp = Math.abs(lay.row[e.a] - lay.row[e.b]);
      return !(sp === 1 && Math.abs(lay.pos[e.b].x - lay.pos[e.a].x) < 24);
    });
    if (longList.length !== drawn.length) lay = fsmRowPos(lay2.byLayer, initState, longList.length);
    // Long edges (returns and skips) travel in right-angle
    // corridors, one per side-lane, nested 14px apart and placed
    // outside the widest box of every row they span, so they never
    // cross a box. The side is the flow direction for downward
    // edges, the clearer side for returns into a dense row, and
    // otherwise it fills one side up to 3 arrows (which fit 10px
    // apart on a 26px box) before moving to the other, so no
    // arrowheads ever merge into one blob. When several edges
    // leave or enter the same box side, their anchors are centered
    // and spread along the side (pass B, once the final counts
    // are known).
    var laneMap = {};
    var sCount = {}, eCount = {}, laneNo = { left: 0, right: 0 };
    var sides = {};
    longList.forEach(function (e) {
      var lo = Math.min(lay.row[e.a], lay.row[e.b]);
      var hi = Math.max(lay.row[e.a], lay.row[e.b]);
      var maxR = -1e9, minL = 1e9;
      for (var r = lo; r <= hi; r++) lay.rows[r].forEach(function (s) {
        var re = lay.pos[s].x + lay.nw[s] / 2;
        var le = lay.pos[s].x - lay.nw[s] / 2;
        if (re > maxR) maxR = re;
        if (le < minL) minL = le;
      });
      var rightBoxes = 0, leftBoxes = 0;
      lay.rows[lay.row[e.a]].forEach(function (s) {
        if (s !== e.a && (lay.pos[s].x > lay.pos[e.a].x ? rightBoxes++ : leftBoxes++));
      });
      var tRight = 0, tLeft = 0;
      lay.rows[lay.row[e.b]].forEach(function (s2) {
        if (s2 !== e.b && (lay.pos[s2].x > lay.pos[e.b].x ? tRight++ : tLeft++));
      });
      var upEdge = lay.row[e.b] < lay.row[e.a];
      var edx = lay.pos[e.b].x - lay.pos[e.a].x;
      var side;
      if (!upEdge && edx !== 0) side = edx > 0 ? "right" : "left";
      else if (rightBoxes !== leftBoxes) side = rightBoxes < leftBoxes ? "right" : "left";
      else { var tl = eCount[e.b + "|left"] || 0;
        side = tl < 3 ? "left" : (eCount[e.b + "|right"] || 0) < 3 ? "right" : tl <= (eCount[e.b + "|right"] || 0) ? "left" : "right"; }
      var laneIdx = side === "right" ? laneNo.right : laneNo.left;
      if (side === "right") laneNo.right++; else laneNo.left++;
      sides[e.a + "->" + e.b] = { side: side, maxR: maxR, minL: minL, laneIdx: laneIdx,
        rightBoxes: rightBoxes, leftBoxes: leftBoxes, tRight: tRight, tLeft: tLeft };
      sCount[e.a + "|" + side] = (sCount[e.a + "|" + side] || 0) + 1;
      eCount[e.b + "|" + side] = (eCount[e.b + "|" + side] || 0) + 1;
    });
    var sPos = {}, ePos = {};
    longList.forEach(function (e) {
      var info = sides[e.a + "->" + e.b];
      var sKey = e.a + "|" + info.side, eKey = e.b + "|" + info.side;
      var si = sPos[sKey] || 0; sPos[sKey] = si + 1;
      var ei = ePos[eKey] || 0; ePos[eKey] = ei + 1;
      var nS = sCount[sKey], nE = eCount[eKey];
      var spS = nS > 1 ? Math.min(10, 22 / (nS - 1)) : 0;
      var spE = nE > 1 ? Math.min(10, 22 / (nE - 1)) : 0;
      info.soff = Math.max(-11, Math.min(11, (si - (nS - 1) / 2) * spS));
      info.eoff = Math.max(-11, Math.min(11, (ei - (nE - 1) / 2) * spE));
      info.laneX = info.side === "right"
        ? info.maxR + 14 + 14 * info.laneIdx
        : info.minL - 14 - 14 * info.laneIdx;
      // a head-on run at the anchor's y is only crossing-free if
      // no sibling box on that row sits between the box and the lane
      info.sClear = (info.side === "left" ? info.leftBoxes : info.rightBoxes) === 0;
      info.eClear = (info.side === "left" ? info.tLeft : info.tRight) === 0;
      laneMap[e.a + "->" + e.b] = info;
    });
    var skipped = 0;
    var svg = '<svg class="fsmgraph" viewBox="0 0 ' + lay.w + ' ' + lay.h +
      '" width="' + lay.w + '" height="' + lay.h + '"><defs>' +
      '<marker id="arrg" markerWidth="9" markerHeight="9" refX="8" refY="3.5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L8,3.5 L0,7 Z" fill="#1a7f37"/></marker>' +
      '</defs>';
    var ah = 16;
    function anc(pt, w, side) {
      if (side === "top") return { x: pt.x, y: pt.y - ah };
      if (side === "bottom") return { x: pt.x, y: pt.y + ah };
      if (side === "left") return { x: pt.x - w / 2, y: pt.y };
      return { x: pt.x + w / 2, y: pt.y };
    }
    function ctl(pt, side, ext) {
      if (side === "top") return { x: pt.x, y: pt.y - ext };
      if (side === "bottom") return { x: pt.x, y: pt.y + ext };
      if (side === "left") return { x: pt.x - ext, y: pt.y };
      return { x: pt.x + ext, y: pt.y };
    }
    arcs.forEach(function (p) {
      var d = fsmParts(p.comment).detail.split("->");
      var a = d[0], b = d[1];
      if (!(a in lay.pos) || !(b in lay.pos)) return;
      var hit = p.count > 0;
      if (!hit) { skipped++; return; }
      var title = esc(a + " \u2192 " + b + " \u2014 " + p.count + " hit(s) \u2014 covered");
      var cls = "eg";
      var mark = "arrg";
      var pa = lay.pos[a], pb = lay.pos[b];
      var wa = lay.nw[a], wb = lay.nw[b];
      var dx = pb.x - pa.x;
      var dstr;
      if (a === b) {
        dstr = 'M ' + (pa.x - wa / 4) + ' ' + (pa.y - 16) +
          ' C ' + (pa.x - wa / 2 - 10) + ' ' + (pa.y - 38) + ', ' + (pa.x + wa / 2 + 10) + ' ' + (pa.y - 38) +
          ', ' + (pa.x + wa / 4) + ' ' + (pa.y - 16);
      } else {
        var span = Math.abs(lay.row[a] - lay.row[b]);
        if (span === 1 && Math.abs(dx) < 24) {
          // straight vertical between adjacent rows
          var spt = anc(pa, wa, "bottom");
          var ept = anc(pb, wb, "top");
          var c1 = ctl(spt, "bottom", 26);
          var c2 = ctl(ept, "top", 26);
          dstr = 'M ' + spt.x.toFixed(1) + ' ' + spt.y.toFixed(1) +
            ' C ' + c1.x.toFixed(1) + ' ' + c1.y.toFixed(1) + ', ' + c2.x.toFixed(1) + ' ' + c2.y.toFixed(1) +
            ', ' + ept.x.toFixed(1) + ' ' + ept.y.toFixed(1);
        } else {
          // long edge (a return or a skip), routed either way:
          // a right-angle corridor. Both ends leave/enter the box
          // head-on (perpendicular to the side) whenever the run
          // to the lane is clear of sibling boxes; otherwise that
          // end steps along the side into the row gap instead
          // (still crossing-free). A clear end is a single straight
          // horizontal to the lane; the vertical run sits in the
          // lane, outside every box the edge spans, and spread
          // anchors keep stacked arrowheads apart
          var lm = laneMap[a + "->" + b] ||
            { side: "left", laneX: 16, soff: 0, eoff: 0, sClear: false, eClear: false };
          var sdx = lm.side === "left" ? -1 : 1;
          var g = 24;
          var sx = (pa.x + sdx * wa / 2).toFixed(1), ex = (pb.x + sdx * wb / 2).toFixed(1);
          var sy0 = (pa.y + lm.soff).toFixed(1), ey0 = (pb.y + lm.eoff).toFixed(1);
          dstr = 'M ' + sx + ' ' + sy0;
          if (lm.sClear) {
            dstr += ' L ' + lm.laneX.toFixed(1) + ' ' + sy0;
          } else {
            dstr += ' L ' + sx + ' ' + (pa.y + lm.soff + g).toFixed(1) +
              ' L ' + lm.laneX.toFixed(1) + ' ' + (pa.y + lm.soff + g).toFixed(1);
          }
          if (lm.eClear) {
            dstr += ' L ' + lm.laneX.toFixed(1) + ' ' + ey0 +
              ' L ' + ex + ' ' + ey0;
          } else {
            dstr += ' L ' + lm.laneX.toFixed(1) + ' ' + (pb.y + lm.eoff + g).toFixed(1) +
              ' L ' + ex + ' ' + (pb.y + lm.eoff + g).toFixed(1) +
              ' L ' + ex + ' ' + ey0;
          }
        }
      }
      svg += '<path class="' + cls + '" d="' + dstr + '" marker-end="url(#' + mark + ')"><title>' + title + '</title></path>';
    });
    states.forEach(function (s) {
      var p0 = lay.pos[s];
      var sh = stateHits[s] || 0;
      var w2 = lay.nw[s], h2 = 32;
      svg += '<g class="nd ' + (sh > 0 ? "ng" : "nr") + '">' +
        '<rect x="' + (p0.x - w2 / 2).toFixed(1) + '" y="' + (p0.y - h2 / 2) + '" width="' + w2.toFixed(1) +
        '" height="' + h2 + '" rx="6"/>' +
        '<text x="' + p0.x.toFixed(1) + '" y="' + (p0.y + 4) + '" text-anchor="middle">' + esc(s) + '</text>' +
        '<title>' + esc(s + " \u2014 " + sh + " hit(s) in fsm_state") + '</title></g>';
    });
    svg += '</svg>';
    if (skipped > 0) {
      svg += '<div class="fsmnote">' + skipped + ' uncovered transition path(s) are not drawn in the graph (see the table for missed transitions).</div>';
    }
    return svg;
  }

  function drawFsmGraph(sec, allPoints) {
    var map = {};
    allPoints.forEach(function (p) {
      if (p.type === "fsm_arc" || p.type === "fsm_state") {
        var c = fsmParts(p.comment);
        if (!map[c.sig]) map[c.sig] = [];
        map[c.sig].push(p);
      }
    });
    var sigs = Object.keys(map).sort();
    if (!sigs.length) {
      sec.innerHTML += "<div class='empty'>No fsm points.</div>";
      return;
    }
    sec.innerHTML += "<p class='hint'>" + sigs.length + " signal(s). Click a signal to show its state graph.</p>";
    sigs.forEach(function (sg, i) {
      var pts = map[sg];
      var arcs = pts.filter(function (p) { return p.type === "fsm_arc"; });
      var cov = arcs.filter(function (p) { return p.count > 0; }).length;
      var row = document.createElement("div");
      row.className = "fsmg-sig";
      row.innerHTML = "<span class='twisty' data-fsg2='" + i + "'>\u25ba</span> <code class='net'>" + esc(sg) +
        "</code> <span class='muted'>" + arcs.length + " transition(s): " + cov +
        " covered, " + (arcs.length - cov) + " missed</span>";
      sec.appendChild(row);
      var det = document.createElement("div");
      det.className = "fsmg-det";
      det.style.display = "none";
      det.setAttribute("data-fsd2", i);
      det.innerHTML = "<div class='fsmgraphwrap'>" + (fsmSignalGraphSvg(pts) || "<div class='empty'>No transitions.</div>") + "</div>";
      sec.appendChild(det);
    });
    sec.addEventListener("click", function (e) {
      var tw = e.target.closest("[data-fsg2]");
      if (!tw) return;
      var gi = tw.getAttribute("data-fsg2");
      var det = sec.querySelector("[data-fsd2='" + gi + "']");
      var open = det.style.display !== "none";
      det.style.display = open ? "none" : "";
      tw.textContent = open ? "\u25ba" : "\u25bc";
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
      fsec.innerHTML = "<h2>Functional coverage</h2>";
      var fscore = (r.functional && r.functional.score != null) ? r.functional.score : null;
      if (r.covergroups && r.covergroups.length) {
        drawCgGroups(fsec, r.covergroups, fscore);
      } else {
        fsec.innerHTML += "<div class='empty'>No covergroup data for this module.</div>";
      }
      app.appendChild(fsec);
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
    if (type === "fsm_state" || type === "fsm_arc") {
      var fsec = document.createElement("section");
      fsec.innerHTML = "<h2>" + (type === "fsm_arc" ? "FSM arc" : "FSM state") + " coverage</h2>";
      if (type === "fsm_arc") fsec.appendChild(fsmViewBtns());
      app.appendChild(fsec);
      if (type === "fsm_arc" && fsmArcView === "graph") {
        drawFsmGraph(fsec, r.points);
      } else {
        drawFsmGroups(fsec, rows, type);
      }
      fsec.addEventListener("click", function (e) {
        var b = e.target.closest("[data-fview]");
        if (b) {
          fsmArcView = b.getAttribute("data-fview");
          renderTypeDetail(kind, i, type);
        }
      });
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
      if (th) {
        var key = th.getAttribute("data-sort");
        if (st.key === key) st.dir = (st.dir === "asc") ? "desc" : "asc";
        else { st.key = key; st.dir = "asc"; }
        drawDetail(sec, rows);
        return;
      }
      var tw = e.target.closest("[data-pg]");
      if (tw) {
        var det = sec.querySelector("[data-pgd='" + tw.getAttribute("data-pg") + "']");
        var open = det.style.display !== "none";
        det.style.display = open ? "none" : "";
        tw.textContent = open ? "\u25ba" : "\u25bc";
      }
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
    back.addEventListener("click", function () { location.hash = lastHash; });
    app.appendChild(back);
    var lines = SRC[f].lines;
    var rows = [];
    for (var i = 0; i < lines.length; i++) {
      var n = i + 1;
      rows.push("<div class='fline" + (n === target ? " target" : "") + "'>" +
        "<span class='ln'><a class='line-link' href='#file/" + idx + "/" + n + "'>" + n + "</a></span>" +
        "<span class='fcode'>" + (lines[i] === "" ? "&nbsp;" : hl(lines[i])) + "</span></div>");
    }
    var pre = document.createElement("pre");
    pre.className = "filesrc";
    pre.innerHTML = rows.join("");
    app.appendChild(pre);
    if (target) {
      var tl = pre.querySelector(".fline.target");
      if (tl) tl.scrollIntoView({ block: "center" });
    }
  }
  var lastHash = "";
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
    lastHash = location.hash;
    if (location.hash === h) route();
    else location.hash = h;
  }
  window.addEventListener("hashchange", route);
  document.addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("a") : null;
    if (a && (a.getAttribute("href") || "").charAt(0) === "#") lastHash = location.hash;
  }, true);
  route();
})();
"""
