"""Render the co-authorship network as a standalone interactive HTML page.

Reads outputs/fieldmap-network.json (built by build_network_json.py) and writes
outputs/network_graph.html — one self-contained file with the graph data inlined
and no external dependencies, so it opens from disk or from GitHub Pages with no
server and no CDN.

The positions baked into fieldmap-network.json are tuned for the fixed canvas in
report.py and read badly at arbitrary window sizes (a handful of outliers stretch
the bounding box and the dense sub-fields collapse into overlapping blobs), so the
layout is recomputed here:

  spring layout per connected component -> collision relaxation against real node
  radii -> circle-pack the components into a sub-field island -> circle-pack the
  islands into the map.

Node radii are therefore in world units, so zooming keeps the picture consistent.
Rendering is plain canvas: 320 nodes and ~1.1k edges, no live force simulation.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import networkx as nx

import config as C

SRC = C.OUTPUTS / "fieldmap-network.json"
OUT = C.OUTPUTS / "network_graph.html"

R_SCALE = 1.55   # node "s" (4..18) -> world radius
GAP = 7.0        # breathing room between node discs
FILL = 0.13      # target area fill of a component's disc
ISLAND_GAP = 60.0
SEED = 20260721


# --------------------------------------------------------------------------- #
# layout
# --------------------------------------------------------------------------- #
def _enclosing_radius(pos: dict, radii: dict) -> float:
    return max((math.hypot(x, y) + radii[k] for k, (x, y) in pos.items()),
               default=0.0)


def _pack(items: list[tuple], gap: float) -> dict:
    """Greedy circle packing: biggest first, each new disc as close to the
    origin as it can sit without touching one already placed."""
    placed: list[tuple] = []
    out: dict = {}
    for key, r in sorted(items, key=lambda t: -t[1]):
        if not placed:
            placed.append((r, 0.0, 0.0))
            out[key] = (0.0, 0.0)
            continue
        step = max(1.5, r * 0.3)
        ring, best = 0.0, None
        while best is None and ring < 1e6:
            ring += step
            n_ang = max(16, int(2 * math.pi * ring / step))
            for a in range(n_ang):
                th = 2 * math.pi * a / n_ang
                cx, cy = ring * math.cos(th), ring * math.sin(th)
                if all(math.hypot(cx - px, cy - py) >= r + pr + gap
                       for pr, px, py in placed):
                    d = math.hypot(cx, cy)
                    if best is None or d < best[0]:
                        best = (d, cx, cy)
        cx, cy = (best[1], best[2]) if best else (0.0, 0.0)
        placed.append((r, cx, cy))
        out[key] = (cx, cy)
    return out


def _relax(pos: dict, radii: dict, rng: random.Random, iters: int = 140) -> None:
    """Push apart node discs that overlap. In place."""
    keys = list(pos)
    for _ in range(iters):
        moved = False
        for i in range(len(keys)):
            a = keys[i]
            for j in range(i + 1, len(keys)):
                b = keys[j]
                ax, ay = pos[a]
                bx, by = pos[b]
                dx, dy = bx - ax, by - ay
                d = math.hypot(dx, dy)
                need = radii[a] + radii[b] + GAP
                if d >= need:
                    continue
                if d < 1e-9:
                    th = rng.uniform(0, 2 * math.pi)
                    dx, dy, d = math.cos(th), math.sin(th), 1.0
                push = (need - d) / 2.0
                ux, uy = dx / d, dy / d
                pos[a] = (ax - ux * push, ay - uy * push)
                pos[b] = (bx + ux * push, by + uy * push)
                moved = True
        if not moved:
            break


def _component_layout(g: nx.Graph, nodes: list, radii: dict,
                      rng: random.Random, seed: int) -> dict:
    """Lay out one connected component, centred on the origin."""
    if len(nodes) == 1:
        return {nodes[0]: (0.0, 0.0)}

    raw = nx.spring_layout(g.subgraph(nodes), seed=seed, iterations=300)
    pos = {n: (float(p[0]), float(p[1])) for n, p in raw.items()}

    # scale so the discs occupy ~FILL of the enclosing area, then de-overlap
    span = max((math.hypot(x, y) for x, y in pos.values()), default=1.0) or 1.0
    area = sum(math.pi * (radii[n] + GAP / 2) ** 2 for n in nodes)
    target = math.sqrt(area / FILL / math.pi)
    k = target / span
    pos = {n: (x * k, y * k) for n, (x, y) in pos.items()}

    _relax(pos, radii, rng)
    cx = sum(p[0] for p in pos.values()) / len(pos)
    cy = sum(p[1] for p in pos.values()) / len(pos)
    return {n: (x - cx, y - cy) for n, (x, y) in pos.items()}


def compute_layout(nodes: list[dict], edges: list[list[int]]) -> None:
    """Assign world-space x/y/r to every node, in place."""
    rng = random.Random(SEED)
    radii = {i: n["s"] * R_SCALE for i, n in enumerate(nodes)}

    g = nx.Graph()
    g.add_nodes_from(range(len(nodes)))
    g.add_edges_from((a, b) for a, b in edges)

    by_comm: dict[int, list[int]] = {}
    for i, n in enumerate(nodes):
        by_comm.setdefault(int(n["c"]), []).append(i)

    islands: dict[int, dict] = {}
    for ci, members in sorted(by_comm.items()):
        sub = g.subgraph(members)
        comps = [sorted(c) for c in nx.connected_components(sub)]
        comps.sort(key=len, reverse=True)

        laid, sizes = {}, []
        for ci_idx, comp in enumerate(comps):
            p = _component_layout(g, comp, radii, rng, SEED + ci * 97 + ci_idx)
            laid[ci_idx] = p
            sizes.append((ci_idx, _enclosing_radius(p, radii)))

        centres = _pack(sizes, GAP * 2)
        island = {}
        for ci_idx, p in laid.items():
            ox, oy = centres[ci_idx]
            for n, (x, y) in p.items():
                island[n] = (x + ox, y + oy)

        # recentre the island on its own enclosing circle
        cx = sum(p[0] for p in island.values()) / len(island)
        cy = sum(p[1] for p in island.values()) / len(island)
        island = {n: (x - cx, y - cy) for n, (x, y) in island.items()}
        islands[ci] = island

    centres = _pack([(ci, _enclosing_radius(p, radii)) for ci, p in islands.items()],
                    ISLAND_GAP)

    for ci, island in islands.items():
        ox, oy = centres[ci]
        for n, (x, y) in island.items():
            nodes[n]["x"] = round(x + ox, 1)
            nodes[n]["y"] = round(y + oy, 1)
    for i, n in enumerate(nodes):
        n["r"] = round(radii[i], 1)


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Biophoton / UPE Field Map — Researcher Network</title>
<style>
  :root {
    --bg: #0e1117;
    --panel: #161b25;
    --panel-2: #1d2430;
    --line: #2a3242;
    --ink: #e6edf7;
    --ink-dim: #97a3b6;
    --ink-faint: #6b7688;
    --accent: #ffd24a;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0; height: 100%; overflow: hidden;
    background: var(--bg); color: var(--ink);
    font: 14px/1.5 ui-sans-serif, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  #app { display: flex; height: 100%; }

  /* ---------- side panel ---------- */
  aside {
    width: 300px; flex: none; background: var(--panel);
    border-right: 1px solid var(--line);
    display: flex; flex-direction: column; overflow-y: auto;
  }
  aside > * { padding: 14px 16px; border-bottom: 1px solid var(--line); }
  aside > *:last-child { border-bottom: 0; }
  h1 { margin: 0 0 4px; font-size: 15px; font-weight: 650; letter-spacing: -.01em; }
  .sub { margin: 0; font-size: 12px; color: var(--ink-dim); }
  .lbl {
    font-size: 10.5px; font-weight: 600; letter-spacing: .09em;
    text-transform: uppercase; color: var(--ink-faint); margin-bottom: 9px;
  }
  input[type=search] {
    width: 100%; padding: 8px 10px; border-radius: 7px;
    border: 1px solid var(--line); background: var(--panel-2);
    color: var(--ink); font: inherit; font-size: 13px;
  }
  input[type=search]:focus { outline: none; border-color: var(--accent); }
  input[type=search]::placeholder { color: var(--ink-faint); }
  .hits { margin-top: 7px; font-size: 11.5px; color: var(--ink-faint); min-height: 17px; }

  .legend-row {
    display: flex; align-items: center; gap: 9px;
    padding: 5px 6px; margin: 0 -6px; border-radius: 6px;
    cursor: pointer; user-select: none;
  }
  .legend-row:hover { background: var(--panel-2); }
  .legend-row.off { opacity: .38; }
  .dot { width: 11px; height: 11px; border-radius: 50%; flex: none; }
  .legend-name { flex: 1; font-size: 12.5px; }
  .legend-n { font-size: 11px; color: var(--ink-faint); font-variant-numeric: tabular-nums; }

  .seg { display: flex; gap: 6px; }
  .seg button {
    flex: 1; padding: 6px 8px; font: inherit; font-size: 12px;
    border-radius: 6px; border: 1px solid var(--line);
    background: var(--panel-2); color: var(--ink-dim); cursor: pointer;
  }
  .seg button.on { background: var(--accent); border-color: var(--accent); color: #17202e; font-weight: 600; }

  .ramp { height: 9px; border-radius: 5px; margin: 2px 0 6px;
          background: linear-gradient(90deg, #3b4354, #4f7fd0, #46c4a5, #ffd24a); }
  .ramp-ends { display: flex; justify-content: space-between; font-size: 11px; color: var(--ink-faint); }

  #detail { min-height: 132px; }
  #detail .empty { color: var(--ink-faint); font-size: 12.5px; }
  #detail .nm { font-size: 14.5px; font-weight: 620; margin-bottom: 3px; }
  #detail .inst { font-size: 12.5px; color: var(--ink-dim); margin-bottom: 10px; }
  #detail dl { margin: 0; display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; font-size: 12.5px; }
  #detail dt { color: var(--ink-faint); }
  #detail dd { margin: 0; overflow-wrap: anywhere; }

  .note { font-size: 11.5px; color: var(--ink-faint); line-height: 1.55; }

  /* ---------- canvas ---------- */
  main { flex: 1; position: relative; min-width: 0; }
  canvas { display: block; width: 100%; height: 100%; cursor: grab; }
  canvas.drag { cursor: grabbing; }
  #tip {
    position: absolute; pointer-events: none; opacity: 0;
    transform: translate(-50%, -100%); transition: opacity .1s;
    background: #0b0f16f2; border: 1px solid var(--line);
    border-radius: 7px; padding: 7px 10px; max-width: 260px;
    font-size: 12.5px; box-shadow: 0 6px 22px #0009;
  }
  #tip .t-n { font-weight: 620; }
  #tip .t-i { color: var(--ink-dim); font-size: 11.5px; }
  #zoom { position: absolute; right: 14px; bottom: 14px; display: flex; gap: 6px; }
  #zoom button {
    width: 30px; height: 30px; border-radius: 7px; cursor: pointer;
    border: 1px solid var(--line); background: #161b25e6; color: var(--ink);
    font: inherit; font-size: 15px; line-height: 1;
  }
  #zoom button:hover { background: var(--panel-2); }
  #zoom button.wide { width: auto; padding: 0 10px; font-size: 12px; }
  #hint { position: absolute; left: 14px; bottom: 14px; font-size: 11.5px; color: var(--ink-faint); }
  @media (max-width: 760px) {
    #app { flex-direction: column; }
    aside { width: 100%; max-height: 44%; border-right: 0; border-bottom: 1px solid var(--line); }
  }
</style>
</head>
<body>
<div id="app">
  <aside>
    <div>
      <h1>Biophoton / UPE Field Map</h1>
      <p class="sub">Researcher co-authorship network · <span id="meta"></span></p>
    </div>

    <div>
      <div class="lbl">Search</div>
      <input type="search" id="q" placeholder="Name or institution…" autocomplete="off" spellcheck="false">
      <div class="hits" id="hits"></div>
    </div>

    <div>
      <div class="lbl">Colour by</div>
      <div class="seg">
        <button id="mode-c" class="on">Sub-field</button>
        <button id="mode-o">Openness</button>
      </div>
      <div id="ramp-wrap" style="display:none; margin-top:10px">
        <div class="ramp"></div>
        <div class="ramp-ends"><span>closed 0.0</span><span>1.0 open</span></div>
      </div>
    </div>

    <div>
      <div class="lbl">Sub-fields <span style="text-transform:none;letter-spacing:0">(click to toggle)</span></div>
      <div id="legend"></div>
    </div>

    <div id="detail">
      <div class="lbl">Selected</div>
      <div class="empty">Hover a node for a quick look, click to pin it here.</div>
    </div>

    <div>
      <p class="note">
        Nodes are the top <span id="n-nodes"></span> ranked researchers; size is
        eigenvector centrality in the co-authorship graph, islands are Leiden
        sub-fields. Edges are co-authorship links. Built from OpenAlex,
        snapshot <span id="snap"></span>. No contact data is included in this view.
      </p>
    </div>
  </aside>

  <main>
    <canvas id="cv"></canvas>
    <div id="tip"></div>
    <div id="hint">Scroll to zoom · drag to pan</div>
    <div id="zoom">
      <button id="zi" title="Zoom in">+</button>
      <button id="zo" title="Zoom out">&minus;</button>
      <button id="zr" class="wide" title="Reset view">Reset</button>
    </div>
  </main>
</div>

<script id="graph-data" type="application/json">__DATA__</script>
<script>
(function () {
  "use strict";
  var DATA  = JSON.parse(document.getElementById("graph-data").textContent);
  var NODES = DATA.nodes, EDGES = DATA.edges;
  var PAL = DATA.palette, NAMES = DATA.names;

  document.getElementById("n-nodes").textContent = NODES.length;
  document.getElementById("snap").textContent = DATA.snapshot;
  document.getElementById("meta").textContent =
    NODES.length + " researchers · " + EDGES.length + " co-authorships";

  var adj = NODES.map(function () { return []; });
  EDGES.forEach(function (e) { adj[e[0]].push(e[1]); adj[e[1]].push(e[0]); });

  var cv = document.getElementById("cv"), ctx = cv.getContext("2d");
  var view = { x: 0, y: 0, k: 1 };
  var W = 0, H = 0, dpr = 1;
  var mode = "community";
  var hidden = {};
  var hover = -1, pinned = -1;
  var matched = null;

  // ---- colour ------------------------------------------------------------
  function hex2rgb(h) {
    return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  }
  var RAMP = ["#3b4354", "#4f7fd0", "#46c4a5", "#ffd24a"].map(hex2rgb);
  function opennessColor(o) {
    var t = Math.max(0, Math.min(1, o)) * (RAMP.length - 1);
    var i = Math.min(RAMP.length - 2, Math.floor(t)), f = t - i;
    var a = RAMP[i], b = RAMP[i + 1];
    return "rgb(" + Math.round(a[0] + (b[0] - a[0]) * f) + "," +
                    Math.round(a[1] + (b[1] - a[1]) * f) + "," +
                    Math.round(a[2] + (b[2] - a[2]) * f) + ")";
  }
  function nodeColor(n) {
    return mode === "openness" ? opennessColor(n.o) : (PAL[String(n.c)] || "#7c8698");
  }
  function visible(n) { return !hidden[String(n.c)]; }
  function dimmed(i) {
    if (matched && !matched.has(i)) return true;
    var focus = pinned >= 0 ? pinned : hover;
    if (focus < 0 || i === focus) return false;
    return adj[focus].indexOf(i) === -1;
  }

  // ---- transform ---------------------------------------------------------
  function sx(n) { return (n.x + view.x) * view.k + W / 2; }
  function sy(n) { return (n.y + view.y) * view.k + H / 2; }
  function toWorld(px, py) { return [(px - W / 2) / view.k - view.x, (py - H / 2) / view.k - view.y]; }
  function rad(n) { return Math.max(1.2, n.r * view.k); }

  function fit() {
    var vis = NODES.filter(visible);
    if (!vis.length) vis = NODES;
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    vis.forEach(function (n) {
      if (n.x - n.r < x0) x0 = n.x - n.r;
      if (n.x + n.r > x1) x1 = n.x + n.r;
      if (n.y - n.r < y0) y0 = n.y - n.r;
      if (n.y + n.r > y1) y1 = n.y + n.r;
    });
    var pad = 62;   // room for the labels that sit above the outermost nodes
    view.k = Math.min((W - pad * 2) / Math.max(1, x1 - x0), (H - pad * 2) / Math.max(1, y1 - y0));
    view.k = Math.max(0.02, Math.min(4, view.k));
    view.x = -(x0 + x1) / 2;
    view.y = -(y0 + y1) / 2;
    draw();
  }

  function resize() {
    dpr = window.devicePixelRatio || 1;
    W = cv.clientWidth; H = cv.clientHeight;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw();
  }

  // ---- draw --------------------------------------------------------------
  function draw() {
    ctx.clearRect(0, 0, W, H);
    var focus = pinned >= 0 ? pinned : hover;
    var near = focus >= 0 ? adj[focus] : null;

    // island captions, under the outer edge of each island so they never sit on nodes
    var bb = {};
    NODES.forEach(function (n) {
      if (!visible(n)) return;
      var k = String(n.c);
      if (!bb[k]) bb[k] = [Infinity, Infinity, -Infinity, -Infinity];
      var b = bb[k];
      if (n.x - n.r < b[0]) b[0] = n.x - n.r;
      if (n.y - n.r < b[1]) b[1] = n.y - n.r;
      if (n.x + n.r > b[2]) b[2] = n.x + n.r;
      if (n.y + n.r > b[3]) b[3] = n.y + n.r;
    });
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    ctx.font = "600 12px ui-sans-serif, -apple-system, Segoe UI, Roboto, sans-serif";
    ctx.fillStyle = "rgba(230,237,247,.30)";
    Object.keys(bb).forEach(function (k) {
      var b = bb[k];
      ctx.fillText((NAMES[k] || "Other").toUpperCase(),
                   ((b[0] + b[2]) / 2 + view.x) * view.k + W / 2,
                   (b[3] + view.y) * view.k + H / 2 + 12);
    });

    // edges
    EDGES.forEach(function (e) {
      var a = NODES[e[0]], b = NODES[e[1]];
      if (!visible(a) || !visible(b)) return;
      var lit = focus >= 0 && (e[0] === focus || e[1] === focus);
      if (lit)                { ctx.strokeStyle = "rgba(255,210,74,.6)";  ctx.lineWidth = 1.5; }
      else if (focus >= 0)    { ctx.strokeStyle = "rgba(120,132,152,.07)"; ctx.lineWidth = 1; }
      else                    { ctx.strokeStyle = "rgba(120,132,152,.22)"; ctx.lineWidth = 1; }
      ctx.beginPath(); ctx.moveTo(sx(a), sy(a)); ctx.lineTo(sx(b), sy(b)); ctx.stroke();
    });

    // nodes, dimmed ones first so highlights land on top
    var order = [];
    NODES.forEach(function (n, i) { if (visible(n)) order.push(i); });
    order.sort(function (a, b) { return (dimmed(a) ? 0 : 1) - (dimmed(b) ? 0 : 1); });

    order.forEach(function (i) {
      var n = NODES[i], px = sx(n), py = sy(n), r = rad(n);
      if (px < -60 || px > W + 60 || py < -60 || py > H + 60) return;
      var d = dimmed(i);
      ctx.globalAlpha = d ? 0.15 : 1;
      ctx.beginPath(); ctx.arc(px, py, r, 0, 6.2832);
      ctx.fillStyle = nodeColor(n); ctx.fill();
      if (!d && r > 2.2) { ctx.lineWidth = 1; ctx.strokeStyle = "rgba(14,17,23,.8)"; ctx.stroke(); }
      if (i === focus) {
        ctx.globalAlpha = 1; ctx.lineWidth = 2; ctx.strokeStyle = "#fff";
        ctx.beginPath(); ctx.arc(px, py, r + 3.5, 0, 6.2832); ctx.stroke();
      }
      ctx.globalAlpha = 1;
    });

    // labels — placed greedily, most important first, dropping any that collide
    ctx.textAlign = "center"; ctx.textBaseline = "bottom";
    ctx.font = "500 11px ui-sans-serif, -apple-system, Segoe UI, Roboto, sans-serif";
    var cand = [];
    order.forEach(function (i) {
      if (dimmed(i)) return;
      var r = rad(NODES[i]), px = sx(NODES[i]), py = sy(NODES[i]);
      if (px < -70 || px > W + 70 || py < -20 || py > H + 20) return;
      var pri;
      if (i === focus) pri = 0;
      else if (near && near.indexOf(i) !== -1) pri = 1;
      else if (matched && matched.has(i)) pri = 2;
      else if (r > 7) pri = 3;
      else return;
      cand.push({ i: i, pri: pri, r: r, px: px, py: py });
    });
    cand.sort(function (a, b) { return a.pri - b.pri || b.r - a.r; });

    var boxes = [];
    cand.forEach(function (c) {
      var name = NODES[c.i].n;
      var w = ctx.measureText(name).width;
      var ty = c.py - c.r - 3;
      var box = [c.px - w / 2 - 2, ty - 11, c.px + w / 2 + 2, ty + 2];
      for (var j = 0; j < boxes.length; j++) {
        var o = boxes[j];
        if (box[0] < o[2] && box[2] > o[0] && box[1] < o[3] && box[3] > o[1]) return;
      }
      boxes.push(box);
      ctx.lineWidth = 3; ctx.strokeStyle = "rgba(14,17,23,.92)";
      ctx.strokeText(name, c.px, ty);
      ctx.fillStyle = c.i === focus ? "#fff" : "#c9d4e4";
      ctx.fillText(name, c.px, ty);
    });
  }

  // ---- hit testing -------------------------------------------------------
  function pick(px, py) {
    var best = -1, bd = Infinity;
    for (var i = 0; i < NODES.length; i++) {
      var n = NODES[i];
      if (!visible(n)) continue;
      var r = Math.max(5, rad(n)) + 2;
      var dx = sx(n) - px, dy = sy(n) - py, d2 = dx * dx + dy * dy;
      if (d2 <= r * r && d2 < bd) { bd = d2; best = i; }
    }
    return best;
  }

  // ---- panels ------------------------------------------------------------
  var tip = document.getElementById("tip");
  function showTip(i, px, py) {
    var n = NODES[i];
    tip.innerHTML = '<div class="t-n"></div><div class="t-i"></div>';
    tip.querySelector(".t-n").textContent = n.n;
    tip.querySelector(".t-i").textContent =
      (n.inst || "unaffiliated") + " · openness " + n.o.toFixed(2);
    tip.style.left = px + "px";
    tip.style.top = (py - 12) + "px";
    tip.style.opacity = 1;
  }
  function hideTip() { tip.style.opacity = 0; }

  var detail = document.getElementById("detail");
  function renderDetail(i) {
    while (detail.firstChild) detail.removeChild(detail.firstChild);
    var lbl = document.createElement("div");
    lbl.className = "lbl"; lbl.textContent = "Selected";
    detail.appendChild(lbl);
    if (i < 0) {
      var p = document.createElement("div");
      p.className = "empty";
      p.textContent = "Hover a node for a quick look, click to pin it here.";
      detail.appendChild(p);
      return;
    }
    var n = NODES[i];
    var nm = document.createElement("div");
    nm.className = "nm"; nm.textContent = n.n;
    var inst = document.createElement("div");
    inst.className = "inst"; inst.textContent = n.inst || "unaffiliated";
    var dl = document.createElement("dl");
    [["Sub-field", NAMES[String(n.c)] || "Other"],
     ["Openness", n.o.toFixed(2)],
     ["Co-authors", adj[i].length + " in view"],
     ["Topics", n.cl || "—"]].forEach(function (kv) {
      var dt = document.createElement("dt"); dt.textContent = kv[0];
      var dd = document.createElement("dd"); dd.textContent = kv[1];
      dl.appendChild(dt); dl.appendChild(dd);
    });
    detail.appendChild(nm); detail.appendChild(inst); detail.appendChild(dl);
  }

  // ---- legend ------------------------------------------------------------
  var counts = {};
  NODES.forEach(function (n) { var k = String(n.c); counts[k] = (counts[k] || 0) + 1; });
  var legend = document.getElementById("legend");
  Object.keys(NAMES)
    .filter(function (k) { return counts[k]; })
    .sort(function (a, b) { return counts[b] - counts[a]; })
    .forEach(function (k) {
      var row = document.createElement("div");
      row.className = "legend-row";
      var dot = document.createElement("span");
      dot.className = "dot"; dot.style.background = PAL[k];
      var nm = document.createElement("span");
      nm.className = "legend-name"; nm.textContent = NAMES[k];
      var ct = document.createElement("span");
      ct.className = "legend-n"; ct.textContent = counts[k];
      row.appendChild(dot); row.appendChild(nm); row.appendChild(ct);
      row.onclick = function () {
        hidden[k] = !hidden[k];
        row.classList.toggle("off", !!hidden[k]);
        if (pinned >= 0 && !visible(NODES[pinned])) { pinned = -1; renderDetail(-1); }
        draw();
      };
      legend.appendChild(row);
    });

  // ---- interaction -------------------------------------------------------
  var dragging = false, moved = false, last = [0, 0];

  cv.addEventListener("mousedown", function (e) {
    dragging = true; moved = false; last = [e.clientX, e.clientY];
    cv.classList.add("drag");
  });
  window.addEventListener("mouseup", function () { dragging = false; cv.classList.remove("drag"); });
  window.addEventListener("mousemove", function (e) {
    if (!dragging) return;
    var dx = e.clientX - last[0], dy = e.clientY - last[1];
    if (Math.abs(dx) + Math.abs(dy) > 2) moved = true;
    view.x += dx / view.k; view.y += dy / view.k;
    last = [e.clientX, e.clientY];
    hideTip(); draw();
  });

  cv.addEventListener("mousemove", function (e) {
    if (dragging) return;
    var r = cv.getBoundingClientRect();
    var px = e.clientX - r.left, py = e.clientY - r.top;
    var i = pick(px, py);
    if (i !== hover) {
      hover = i;
      if (i >= 0) { showTip(i, px, py); if (pinned < 0) renderDetail(i); }
      else { hideTip(); if (pinned < 0) renderDetail(-1); }
      draw();
    } else if (i >= 0) { showTip(i, px, py); }
  });
  cv.addEventListener("mouseleave", function () {
    hover = -1; hideTip(); if (pinned < 0) renderDetail(-1); draw();
  });

  cv.addEventListener("click", function (e) {
    if (moved) return;
    var r = cv.getBoundingClientRect();
    var i = pick(e.clientX - r.left, e.clientY - r.top);
    pinned = (i >= 0 && i === pinned) ? -1 : i;
    renderDetail(pinned >= 0 ? pinned : hover);
    draw();
  });

  cv.addEventListener("wheel", function (e) {
    e.preventDefault();
    var r = cv.getBoundingClientRect();
    var px = e.clientX - r.left, py = e.clientY - r.top;
    var before = toWorld(px, py);
    view.k = Math.max(0.02, Math.min(14, view.k * Math.exp(-e.deltaY * 0.0016)));
    var after = toWorld(px, py);
    view.x += after[0] - before[0];
    view.y += after[1] - before[1];
    draw();
  }, { passive: false });

  function zoomBy(f) {
    var before = toWorld(W / 2, H / 2);
    view.k = Math.max(0.02, Math.min(14, view.k * f));
    var after = toWorld(W / 2, H / 2);
    view.x += after[0] - before[0]; view.y += after[1] - before[1];
    draw();
  }
  document.getElementById("zi").onclick = function () { zoomBy(1.35); };
  document.getElementById("zo").onclick = function () { zoomBy(1 / 1.35); };
  document.getElementById("zr").onclick = function () { pinned = -1; renderDetail(-1); fit(); };

  // search
  var hits = document.getElementById("hits");
  document.getElementById("q").addEventListener("input", function (e) {
    var q = e.target.value.trim().toLowerCase();
    if (!q) { matched = null; hits.textContent = ""; }
    else {
      matched = new Set();
      NODES.forEach(function (n, i) {
        if (n.n.toLowerCase().indexOf(q) !== -1 ||
            (n.inst && n.inst.toLowerCase().indexOf(q) !== -1)) matched.add(i);
      });
      hits.textContent = matched.size + (matched.size === 1 ? " match" : " matches");
    }
    draw();
  });

  // colour mode
  var mc = document.getElementById("mode-c"), mo = document.getElementById("mode-o");
  var ramp = document.getElementById("ramp-wrap");
  mc.onclick = function () {
    mode = "community"; mc.classList.add("on"); mo.classList.remove("on");
    ramp.style.display = "none"; draw();
  };
  mo.onclick = function () {
    mode = "openness"; mo.classList.add("on"); mc.classList.remove("on");
    ramp.style.display = "block"; draw();
  };

  window.addEventListener("resize", resize);
  resize();
  fit();
})();
</script>
</body>
</html>
"""


def main() -> None:
    data = json.loads(SRC.read_text())
    compute_layout(data["nodes"], data["edges"])
    html = TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    Path(OUT).write_text(html)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB, "
          f"{len(data['nodes'])} nodes, {len(data['edges'])} edges)")


if __name__ == "__main__":
    main()
