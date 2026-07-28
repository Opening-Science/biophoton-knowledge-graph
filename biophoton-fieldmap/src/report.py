"""Generate a self-contained interactive HTML field-map report.

Pulls from fieldmap.sqlite + exports, computes an "archipelago" layout (each
sub-field community laid out as its own island via a local Fruchterman-Reingold),
and emits outputs/field_map_report.html — one file, no external dependencies,
with an explorable canvas force-map (zoom / pan / hover / click / filter /
search), sub-field taxonomy, timeline, open-vs-closed, and a sortable table.

The report is shareable: it deliberately excludes the internal email column.
"""
from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter

import igraph as ig
import pandas as pd

import config as C

TOP_N = 420           # researchers shown as nodes
MAX_EDGES = 2600      # coauthorship edges drawn (by weight)

# sub-field community -> (short name, luminous color)
COMM = {
    0: ("Biophoton / UPE core", "#ffd24a"),
    3: ("ROS / redox / biochemiluminescence", "#ff6b6b"),
    1: ("Sonochemistry / cavitation", "#37d6c3"),
    2: ("Bubble & fluid physics", "#5aa9ff"),
    4: ("Sonoluminescence physics", "#b98cff"),
    6: ("Nanobubbles", "#5ad18a"),
}
OTHER = ("Other / adjacency", "#7c8698")


def con():
    return sqlite3.connect(C.DB_PATH)


def archipelago_layout(nodes: pd.DataFrame, edges: list[tuple[str, str, float]]):
    """Per-community local FR layout, each community translated to an island on
    a big ring; returns {author_id: (x, y)} in a ~[-1000,1000] plane."""
    id_index = {a: i for i, a in enumerate(nodes["author_id"])}
    comm_of = dict(zip(nodes["author_id"], nodes["community"]))
    comms = sorted(nodes["community"].unique(),
                   key=lambda c: -(nodes["community"] == c).sum())
    # ring positions for community centroids
    R = 950
    centroids = {}
    for i, cc in enumerate(comms):
        ang = 2 * math.pi * i / max(1, len(comms))
        centroids[cc] = (R * math.cos(ang), R * math.sin(ang))
    pos = {}
    for cc in comms:
        members = [a for a in nodes["author_id"] if comm_of[a] == cc]
        mset = set(members)
        local_idx = {a: i for i, a in enumerate(members)}
        g = ig.Graph(n=len(members))
        for a, b, w in edges:
            if a in mset and b in mset:
                g.add_edge(local_idx[a], local_idx[b])
        if g.vcount() == 0:
            continue
        try:
            lay = g.layout_fruchterman_reingold(niter=400)
        except Exception:
            lay = g.layout_circle()
        xs = [c[0] for c in lay]; ys = [c[1] for c in lay]
        # normalize local island to a radius scaled by member count
        span = max(1e-6, max(max(xs) - min(xs), max(ys) - min(ys)))
        scale = (120 + 22 * math.sqrt(len(members))) / span
        cx, cy = centroids[cc]
        mx = sum(xs) / len(xs); my = sum(ys) / len(ys)
        for a in members:
            lx, ly = lay[local_idx[a]]
            pos[a] = (cx + (lx - mx) * scale, cy + (ly - my) * scale)
    return pos


def build_graph_data(c):
    r = pd.read_csv(C.EXPORTS / "researchers.csv").head(TOP_N)
    ids = list(r["author_id"])
    idset = set(ids)
    ce = pd.read_sql_query(
        "SELECT author_a, author_b, weight FROM coauthor_edges", c)
    ce = ce[ce["author_a"].isin(idset) & ce["author_b"].isin(idset)]
    ce = ce.sort_values("weight", ascending=False).head(MAX_EDGES)
    edges = [(a, b, float(w)) for a, b, w in
             zip(ce["author_a"], ce["author_b"], ce["weight"])]

    r = r.copy()
    r["community"] = r["community"].fillna(-1).astype(int)
    pos = archipelago_layout(r[["author_id", "community"]], edges)

    # size by eigenvector centrality (fallback outreach), sqrt-scaled
    ev = r["eigenvector"].fillna(0).astype(float)
    evmax = ev.max() or 1.0
    nodes = []
    for row in r.itertuples():
        if row.author_id not in pos:
            continue
        x, y = pos[row.author_id]
        size = 4 + 15 * math.sqrt(max(0.0, float(getattr(row, "eigenvector", 0) or 0)) / evmax)
        nodes.append({
            "id": row.author_id,
            "n": str(row.display_name),
            "x": round(x, 1), "y": round(y, 1),
            "c": int(row.community),
            "cl": str(row.cluster) if pd.notna(row.cluster) else "",
            "st": str(getattr(row, "core_strand", "") or ""),
            "ca": int(getattr(row, "consciousness_adjacent", 0) or 0),
            "s": round(size, 1),
            "o": round(float(getattr(row, "openness", 0) or 0), 2),
            "sc": round(float(row.outreach_score), 3),
            "rk": int(row.rank),
            "sd": int(float(getattr(row, "seed_connectedness", 0) or 0)),
            "w": int(getattr(row, "n_works", 0) or 0),
            "rw": int(getattr(row, "recent_works", 0) or 0),
            "inst": str(row.institution) if pd.notna(row.institution) else "",
            "co": str(row.country) if pd.notna(row.country) else "",
            "or": (str(row.orcid).replace("https://orcid.org/", "")
                   if pd.notna(row.orcid) else ""),
        })
    keep = {n["id"] for n in nodes}
    elist = [{"a": a, "b": b, "w": w} for a, b, w in edges
             if a in keep and b in keep]
    return nodes, elist


def build_stats(c):
    works = pd.read_sql_query(
        "SELECT work_id, year, is_seed FROM works", c)
    wo = pd.read_sql_query("SELECT is_oa, has_preprint FROM work_openness", c)
    n_auth = pd.read_sql_query("SELECT COUNT(*) n FROM authors", c)["n"][0]
    # timeline
    yr = works.dropna(subset=["year"])
    bins = Counter((int(y) // 5) * 5 for y in yr["year"] if y and 1920 <= y <= 2029)
    timeline = [{"y": b, "n": bins[b]} for b in sorted(bins)]
    # sub-field sizes
    wc = pd.read_csv(C.EXPORTS / "work_communities.csv")
    sizes = wc["coupling_community"].value_counts().to_dict()
    subfields = []
    for cc, (name, color) in {**COMM}.items():
        subfields.append({"c": cc, "name": name, "color": color,
                          "works": int(sizes.get(cc, 0))})
    # open vs closed within core (community 0)
    r = pd.read_csv(C.EXPORTS / "researchers.csv")
    core = r[(r["community"] == 0) & (r["n_works"] >= 3)].dropna(subset=["openness"])
    top_open = core.sort_values("openness", ascending=False).head(8)
    top_closed = core.sort_values("openness").head(8)
    def mini(df):
        return [{"n": str(x.display_name), "o": round(float(x.openness), 2),
                 "oa": round(float(x.oa_share or 0), 2)} for x in df.itertuples()]
    # core sub-strands
    strands = []
    p = C.EXPORTS / "community0_subcluster_labels.json"
    if p.exists():
        labs = json.loads(p.read_text())
        for k, v in sorted(labs.items(), key=lambda kv: -kv[1]["n_seeds"]):
            if v.get("is_core"):
                strands.append({"n": v["label"], "seeds": v["n_seeds"],
                                "works": v["n_works"],
                                "auth": v.get("top_authors", [])[:4]})
    return {
        "n_works": int(len(works)),
        "n_authors": int(n_auth),
        "n_seeds": int((works["is_seed"] == 1).sum()),
        "oa_pct": round(float(wo["is_oa"].mean()) * 100, 0),
        "n_preprint": int(wo["has_preprint"].sum()),
        "timeline": timeline,
        "subfields": subfields,
        "open": mini(top_open),
        "closed": mini(top_closed),
        "strands": strands[:9],
    }


def top_table(c):
    r = pd.read_csv(C.EXPORTS / "researchers.csv").head(60)
    rows = []
    for x in r.itertuples():
        rows.append({
            "rk": int(x.rank), "n": str(x.display_name),
            "cl": str(x.cluster) if pd.notna(x.cluster) else "",
            "st": str(getattr(x, "core_strand", "") or ""),
            "ca": int(getattr(x, "consciousness_adjacent", 0) or 0),
            "inst": str(x.institution) if pd.notna(x.institution) else "",
            "co": str(x.country) if pd.notna(x.country) else "",
            "o": round(float(x.openness or 0), 2),
            "sd": int(float(x.seed_connectedness or 0)),
            "sc": round(float(x.outreach_score), 3),
            "or": (str(x.orcid).replace("https://orcid.org/", "")
                   if pd.notna(x.orcid) else ""),
        })
    return rows


def main():
    c = con()
    nodes, edges = build_graph_data(c)
    stats = build_stats(c)
    table = top_table(c)
    c.close()

    palette = {str(k): v[1] for k, v in COMM.items()}
    palette["-1"] = OTHER[1]
    names = {str(k): v[0] for k, v in COMM.items()}
    names["-1"] = OTHER[0]

    data = {"nodes": nodes, "edges": edges, "stats": stats, "table": table,
            "palette": palette, "names": names}

    html = TEMPLATE.replace("/*__DATA__*/", json.dumps(data))
    out = C.OUTPUTS / "field_map_report.html"
    out.write_text(html)
    print(f"Wrote {out} ({len(html)//1024} KB, {len(nodes)} nodes, "
          f"{len(edges)} edges)")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Biophoton / UPE Field Map</title>
<style>
:root{
 --bg:#070b16; --bg2:#0b1122; --panel:#0e1630cc; --line:#1e2c4d;
 --txt:#dbe4f5; --dim:#8a97b5; --gold:#ffd24a; --accent:#5aa9ff;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--txt);
 font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 -webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
header{position:relative;overflow:hidden;padding:64px 0 40px;
 background:radial-gradient(1200px 500px at 50% -120px,#16224a 0%,#0a1024 55%,var(--bg) 100%)}
header::after{content:"";position:absolute;inset:0;
 background-image:radial-gradient(1.5px 1.5px at 20% 30%,#ffffff22 40%,transparent),
 radial-gradient(1.5px 1.5px at 70% 60%,#ffffff18 40%,transparent),
 radial-gradient(1px 1px at 45% 80%,#ffffff22 40%,transparent),
 radial-gradient(1px 1px at 85% 25%,#ffffff18 40%,transparent);pointer-events:none}
h1{font-size:38px;margin:0 0 8px;letter-spacing:-.5px;font-weight:700}
h1 .g{color:var(--gold)}
.sub{color:var(--dim);font-size:16px;max-width:720px;line-height:1.55}
.stats{display:flex;flex-wrap:wrap;gap:14px;margin-top:26px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:12px;
 padding:14px 18px;min-width:120px;backdrop-filter:blur(6px)}
.stat b{display:block;font-size:26px;color:#fff;font-weight:700}
.stat span{color:var(--dim);font-size:12.5px;text-transform:uppercase;letter-spacing:.4px}
section{padding:40px 0;border-top:1px solid #101a33}
h2{font-size:24px;margin:0 0 6px;letter-spacing:-.3px}
.lead{color:var(--dim);margin:0 0 22px;max-width:820px;line-height:1.55}
.finding{background:linear-gradient(90deg,#12224422,transparent);
 border-left:3px solid var(--gold);padding:14px 18px;border-radius:0 10px 10px 0;
 margin:18px 0;line-height:1.55}
/* map */
.mapbox{position:relative;height:640px;border:1px solid var(--line);border-radius:16px;
 overflow:hidden;background:radial-gradient(900px 500px at 50% 40%,#0c1430,#070b16)}
#map{display:block;width:100%;height:100%;cursor:grab}
#map:active{cursor:grabbing}
.legend{position:absolute;top:14px;left:14px;background:var(--panel);
 border:1px solid var(--line);border-radius:12px;padding:10px 12px;backdrop-filter:blur(8px);
 max-width:250px}
.legend h4{margin:0 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:.6px;color:var(--dim)}
.lg{display:flex;align-items:center;gap:8px;padding:3px 4px;border-radius:6px;cursor:pointer;font-size:13px}
.lg:hover{background:#ffffff0d}
.lg.off{opacity:.35}
.dot{width:11px;height:11px;border-radius:50%;flex:none;box-shadow:0 0 8px currentColor}
.controls{position:absolute;top:14px;right:14px;display:flex;flex-direction:column;gap:8px;align-items:flex-end}
.controls input{background:var(--panel);border:1px solid var(--line);color:var(--txt);
 border-radius:9px;padding:8px 12px;width:190px;outline:none}
.btnrow{display:flex;gap:6px}
.btn{background:var(--panel);border:1px solid var(--line);color:var(--txt);
 border-radius:9px;padding:6px 11px;font-size:12.5px;cursor:pointer}
.btn:hover{border-color:var(--accent)}
.hint{position:absolute;bottom:12px;left:14px;color:var(--dim);font-size:12px}
.tip{position:fixed;pointer-events:none;z-index:50;background:#0a1226f2;border:1px solid var(--line);
 border-radius:10px;padding:10px 12px;font-size:13px;max-width:280px;display:none;
 box-shadow:0 10px 30px #0008}
.tip b{color:#fff}
.panel{position:absolute;top:14px;right:14px;width:290px;background:var(--panel);
 border:1px solid var(--line);border-radius:14px;padding:16px;backdrop-filter:blur(10px);
 display:none;z-index:20}
.panel .nm{font-size:18px;font-weight:700;color:#fff;margin-bottom:2px}
.panel .cl{font-size:12.5px;margin-bottom:12px}
.panel .row{display:flex;justify-content:space-between;font-size:13px;padding:4px 0;border-bottom:1px solid #16223f}
.panel .row span{color:var(--dim)}
.bar{height:6px;border-radius:4px;background:#16223f;overflow:hidden;margin-top:3px}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,#37d6c3,#ffd24a)}
.close{position:absolute;top:10px;right:12px;cursor:pointer;color:var(--dim);font-size:18px}
.badge{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;
 background:#3a1d4d;color:#e5b6ff;border:1px solid #6b3f86;margin-top:8px}
/* cards */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}
.card .t{font-weight:650;margin-bottom:4px;display:flex;align-items:center;gap:8px}
.card .m{color:var(--dim);font-size:12.5px;margin-bottom:8px}
.card .a{font-size:13px;line-height:1.5}
.strand{border-left:3px solid var(--gold);padding-left:12px;margin:10px 0}
.strand b{color:#fff}.strand small{color:var(--dim)}
/* timeline */
.tl{display:flex;align-items:flex-end;gap:3px;height:150px;margin-top:10px}
.tl .b{flex:1;background:linear-gradient(180deg,var(--accent),#26407a);border-radius:3px 3px 0 0;
 position:relative;min-height:2px}
.tl .b:hover{background:var(--gold)}
.tl .b span{position:absolute;bottom:-20px;left:50%;transform:translateX(-50%) rotate(0deg);
 font-size:9px;color:var(--dim);white-space:nowrap}
/* open vs closed */
.oc{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.oc h4{margin:0 0 10px;font-size:14px}
.ocrow{display:flex;align-items:center;gap:10px;margin:6px 0;font-size:13px}
.ocrow .nm{width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ocrow .bar{flex:1}
/* table */
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #14203c}
th{color:var(--dim);font-weight:600;cursor:pointer;user-select:none;position:sticky;top:0;background:var(--bg)}
th:hover{color:#fff}
tr:hover td{background:#0d1730}
.tbwrap{max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:12px}
.pill{font-size:11px;padding:1px 7px;border-radius:20px;background:#3a1d4d;color:#e5b6ff}
footer{padding:30px 0 60px;color:var(--dim);font-size:12.5px;border-top:1px solid #101a33}
@media(max-width:720px){.panel,.controls{position:static;width:auto;margin-top:10px}
 .oc{grid-template-columns:1fr}h1{font-size:28px}}
</style></head>
<body>
<header><div class="wrap">
 <h1>The <span class="g">Biophoton</span> / Ultra-Weak Photon Emission field</h1>
 <p class="sub">An interactive map of the biophoton / UPE research field — seeded from
 Michal Cifra's library, expanded via OpenAlex, clustered into sub-fields, and scored
 for openness. Explore the researcher constellation below.</p>
 <div class="stats" id="statbar"></div>
</div></header>

<section><div class="wrap">
 <h2>The field boundary — answered by the map</h2>
 <p class="lead">Leiden community detection over bibliographic coupling separates the field
 into distinct intellectual sub-fields. The key question — is sonoluminescence part of the
 biophoton core? — is answered empirically.</p>
 <div class="finding" id="finding"></div>
</div></section>

<section><div class="wrap">
 <h2>The researcher constellation</h2>
 <p class="lead">Each point is one of the top-ranked researchers, placed as an island by
 sub-field, linked by co-authorship. Size = network centrality; a glowing gold ring marks
 open researchers. Drag to pan, scroll to zoom, click a node for detail, click legend to filter.</p>
 <div class="mapbox">
   <canvas id="map"></canvas>
   <div class="legend" id="legend"><h4>Sub-fields — click to filter</h4></div>
   <div class="controls">
     <input id="search" placeholder="Search researcher…" autocomplete="off">
     <div class="btnrow">
       <button class="btn" id="toggleOpen">Openness glow</button>
       <button class="btn" id="reset">Reset view</button>
     </div>
   </div>
   <div class="panel" id="panel"></div>
   <div class="hint">scroll = zoom · drag = pan · click node = details</div>
 </div>
</div></section>

<section><div class="wrap">
 <h2>Inside the biophoton core</h2>
 <p class="lead">Re-clustering the core at higher resolution resolves it into real research
 strands — while the biofield / EEG / consciousness literature splits off separately.</p>
 <div id="strands"></div>
</div></section>

<section><div class="wrap">
 <h2>Sub-fields of the universe</h2>
 <div class="cards" id="subcards"></div>
</div></section>

<section><div class="wrap">
 <h2>Timeline of the field</h2>
 <p class="lead">Works per 5-year bin across the whole universe — the field grows an order of
 magnitude from the 1990s, then plateaus.</p>
 <div class="tl" id="timeline"></div>
 <div style="height:26px"></div>
</div></section>

<section><div class="wrap">
 <h2>Open vs closed — the biophoton core</h2>
 <p class="lead">The openness overlay (OA share, preprints, open infrastructure) separates who
 builds the field in the open from who encloses it.</p>
 <div class="oc"><div><h4 style="color:#5ad18a">Most open</h4><div id="openL"></div></div>
 <div><h4 style="color:#ff6b6b">Least open</h4><div id="closedL"></div></div></div>
</div></section>

<section><div class="wrap">
 <h2>Top researchers</h2>
 <p class="lead">Ranked by composite outreach score. Click a column to sort. The
 <span class="pill">consciousness-adjacent</span> pill marks the reputationally-mixed wing.</p>
 <div class="tbwrap"><table id="tbl"><thead></thead><tbody></tbody></table></div>
</div></section>

<footer><div class="wrap">
 Generated from <code>fieldmap.sqlite</code> · OpenAlex snapshot 2026-07 · nodes exclude the
 internal contact-email column · open-science field map for the OSF book.
</div></footer>

<div class="tip" id="tip"></div>
<script>
const DATA = /*__DATA__*/;
const P = DATA.palette, NM = DATA.names, S = DATA.stats;

/* ---------- stat bar ---------- */
document.getElementById('statbar').innerHTML = [
 [S.n_works.toLocaleString(),'works mapped'],
 [S.n_authors.toLocaleString(),'authors'],
 [S.n_seeds,'seed papers'],
 [S.oa_pct+'%','open access'],
 [S.n_preprint.toLocaleString(),'with preprint'],
].map(s=>`<div class="stat"><b>${s[0]}</b><span>${s[1]}</span></div>`).join('');

document.getElementById('finding').innerHTML =
 `<b>Sonoluminescence is an adjacency, not the core.</b> The sonoluminescence / cavitation
  papers cluster in their own communities, distinct from the biophoton core (Cifra, Popp,
  Van Wijk, Kobayashi). The field's true shape: a <b style="color:#ffd24a">biophoton/UPE core</b>,
  a distinct <b style="color:#ff6b6b">ROS / redox</b> wing, and a multi-part
  <b style="color:#b98cff">sonoluminescence / cavitation physics</b> periphery.`;

/* ---------- strands ---------- */
document.getElementById('strands').innerHTML = (S.strands||[]).map(s=>
 `<div class="strand"><b>${s.n}</b> <small>— ${s.seeds} seeds, ${s.works} works · ${s.auth.join(', ')}</small></div>`
).join('') || '<p class="lead">—</p>';

/* ---------- subfield cards ---------- */
document.getElementById('subcards').innerHTML = S.subfields.map(f=>
 `<div class="card"><div class="t"><span class="dot" style="color:${f.color}"></span>${f.name}</div>
  <div class="m">${f.works.toLocaleString()} works</div></div>`).join('');

/* ---------- timeline ---------- */
const tmax = Math.max(...S.timeline.map(d=>d.n));
document.getElementById('timeline').innerHTML = S.timeline.map(d=>
 `<div class="b" title="${d.y}-${d.y+4}: ${d.n} works" style="height:${Math.round(d.n/tmax*100)}%">
   ${d.y%20===0?`<span>${d.y}</span>`:''}</div>`).join('');

/* ---------- open/closed ---------- */
function ocRows(arr){return arr.map(x=>
 `<div class="ocrow"><span class="nm" title="${x.n}">${x.n}</span>
  <span class="bar"><i style="width:${Math.round(x.o*100)}%"></i></span>
  <span style="width:34px;text-align:right;color:var(--dim)">${x.o.toFixed(2)}</span></div>`).join('');}
document.getElementById('openL').innerHTML = ocRows(S.open);
document.getElementById('closedL').innerHTML = ocRows(S.closed);

/* ---------- table ---------- */
const COLS=[['rk','#'],['n','Researcher'],['cl','Sub-field'],['inst','Institution'],
 ['co','Ctry'],['sd','Seed-conn'],['o','Openness'],['sc','Score']];
let sortKey='rk',sortAsc=true;
function renderTable(){
 document.querySelector('#tbl thead').innerHTML='<tr>'+COLS.map(c=>
   `<th data-k="${c[0]}">${c[1]}${sortKey===c[0]?(sortAsc?' ▲':' ▼'):''}</th>`).join('')+'</tr>';
 const rows=[...DATA.table].sort((a,b)=>{let v=a[sortKey],w=b[sortKey];
   if(typeof v==='string'){v=v.toLowerCase();w=(w||'').toLowerCase();}
   return (v>w?1:v<w?-1:0)*(sortAsc?1:-1);});
 document.querySelector('#tbl tbody').innerHTML=rows.map(r=>{
   const orc=r.or?`<a href="https://orcid.org/${r.or}" target="_blank" rel="noopener">${r.n}</a>`:r.n;
   const pill=r.ca?` <span class="pill">consc.</span>`:'';
   return `<tr><td>${r.rk}</td><td>${orc}${pill}</td><td>${r.st||r.cl}</td>
     <td title="${r.inst}">${r.inst.slice(0,26)}</td><td>${r.co}</td>
     <td>${r.sd}</td><td>${r.o.toFixed(2)}</td><td>${r.sc.toFixed(3)}</td></tr>`;}).join('');
}
document.querySelector('#tbl thead').addEventListener('click',e=>{
 const k=e.target.dataset.k;if(!k)return;
 if(k===sortKey)sortAsc=!sortAsc;else{sortKey=k;sortAsc=(k==='n'||k==='cl'||k==='inst'||k==='co');}
 renderTable();});
renderTable();

/* ---------- map ---------- */
const cv=document.getElementById('map'),ctx=cv.getContext('2d');
const nodes=DATA.nodes,edges=DATA.edges,byId={};nodes.forEach(n=>byId[n.id]=n);
let DPR=Math.min(2,window.devicePixelRatio||1);
let view={x:0,y:0,k:1},hidden=new Set(),glow=true,hover=null,selected=null,highlight=null;

function fit(){
 const w=cv.clientWidth,h=cv.clientHeight;
 if(w<=0||h<=0)return false;
 const xs=nodes.map(n=>n.x),ys=nodes.map(n=>n.y);
 const minx=Math.min(...xs),maxx=Math.max(...xs),miny=Math.min(...ys),maxy=Math.max(...ys);
 const sx=Math.max(1,maxx-minx),sy=Math.max(1,maxy-miny);
 const k=0.86*Math.min(w/sx,h/sy);
 view.k=k;view.x=w/2-(minx+maxx)/2*k;view.y=h/2-(miny+maxy)/2*k;
 return true;
}
function resize(){cv.width=Math.max(1,cv.clientWidth*DPR);cv.height=Math.max(1,cv.clientHeight*DPR);draw();}
function toScreen(n){return[n.x*view.k+view.x,n.y*view.k+view.y];}

// adjacency for highlight
const adj={};edges.forEach(e=>{(adj[e.a]=adj[e.a]||new Set()).add(e.b);(adj[e.b]=adj[e.b]||new Set()).add(e.a);});

function draw(){
 ctx.setTransform(DPR,0,0,DPR,0,0);
 ctx.clearRect(0,0,cv.clientWidth,cv.clientHeight);
 const active=highlight?highlight:null;
 // edges
 ctx.lineWidth=.6;
 edges.forEach(e=>{const A=byId[e.a],B=byId[e.b];
   if(hidden.has(A.c)||hidden.has(B.c))return;
   const [ax,ay]=toScreen(A),[bx,by]=toScreen(B);
   let al=0.06+Math.min(.22,e.w*0.03);
   if(active){al=(active.has(e.a)&&active.has(e.b))?0.5:0.02;}
   ctx.strokeStyle=`rgba(120,150,220,${al})`;
   ctx.beginPath();ctx.moveTo(ax,ay);ctx.lineTo(bx,by);ctx.stroke();});
 // nodes
 nodes.forEach(n=>{if(hidden.has(n.c))return;
   const [x,y]=toScreen(n);const r=Math.max(2,n.s*Math.sqrt(view.k));
   const col=P[String(n.c)]||'#7c8698';
   const dim=active&&!active.has(n.id)&&n!==selected;
   ctx.globalAlpha=dim?0.15:1;
   if(glow&&n.o>=0.5){ctx.beginPath();ctx.arc(x,y,r+4,0,7);
     ctx.fillStyle=col+'22';ctx.fill();
     ctx.beginPath();ctx.arc(x,y,r+2.2,0,7);ctx.strokeStyle='#ffe58a';ctx.lineWidth=1.4;ctx.stroke();}
   const g=ctx.createRadialGradient(x,y,0,x,y,r);
   g.addColorStop(0,'#ffffff');g.addColorStop(.4,col);g.addColorStop(1,col+'66');
   ctx.beginPath();ctx.arc(x,y,r,0,7);ctx.fillStyle=g;ctx.fill();
   if(n.ca){ctx.beginPath();ctx.arc(x,y,r+1.4,0,7);ctx.strokeStyle='#e5b6ff';
     ctx.setLineDash([2,2]);ctx.lineWidth=1;ctx.stroke();ctx.setLineDash([]);}
   if(n===selected){ctx.beginPath();ctx.arc(x,y,r+5,0,7);ctx.strokeStyle='#fff';ctx.lineWidth=1.5;ctx.stroke();}
   ctx.globalAlpha=1;
   if(view.k>1.7&&!dim&&r>3){ctx.fillStyle='#cfd8ee';ctx.font='10px sans-serif';
     ctx.fillText(n.n.length>22?n.n.slice(0,21)+'…':n.n,x+r+3,y+3);}
 });
}

function pick(mx,my){let best=null,bd=1e9;
 for(const n of nodes){if(hidden.has(n.c))continue;const [x,y]=toScreen(n);
   const r=Math.max(2,n.s*Math.sqrt(view.k))+3;const d=(x-mx)**2+(y-my)**2;
   if(d<r*r&&d<bd){bd=d;best=n;}}return best;}

const tip=document.getElementById('tip');
cv.addEventListener('mousemove',e=>{
 const rc=cv.getBoundingClientRect();const n=pick(e.clientX-rc.left,e.clientY-rc.top);
 hover=n;
 if(n){tip.style.display='block';tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY+14)+'px';
   tip.innerHTML=`<b>${n.n}</b><br><span style="color:${P[String(n.c)]}">${NM[String(n.c)]}</span>`+
     (n.st?`<br><span style="color:#8a97b5">${n.st}</span>`:'')+
     `<br>openness ${n.o.toFixed(2)} · seed-conn ${n.sd}`+(n.ca?'<br><span style="color:#e5b6ff">consciousness-adjacent</span>':'');
   cv.style.cursor='pointer';}
 else{tip.style.display='none';cv.style.cursor=drag?'grabbing':'grab';}
});
cv.addEventListener('mouseleave',()=>{tip.style.display='none';});

let drag=null;
cv.addEventListener('mousedown',e=>{drag={x:e.clientX,y:e.clientY,vx:view.x,vy:view.y,moved:false};});
window.addEventListener('mousemove',e=>{if(!drag)return;
 const dx=e.clientX-drag.x,dy=e.clientY-drag.y;
 if(Math.abs(dx)+Math.abs(dy)>3)drag.moved=true;
 view.x=drag.vx+dx;view.y=drag.vy+dy;draw();});
window.addEventListener('mouseup',e=>{
 if(drag&&!drag.moved){const rc=cv.getBoundingClientRect();
   const n=pick(e.clientX-rc.left,e.clientY-rc.top);selectNode(n);}
 drag=null;});
cv.addEventListener('wheel',e=>{e.preventDefault();
 const rc=cv.getBoundingClientRect(),mx=e.clientX-rc.left,my=e.clientY-rc.top;
 const f=e.deltaY<0?1.12:0.89;const nk=Math.max(0.15,Math.min(9,view.k*f));
 view.x=mx-(mx-view.x)*(nk/view.k);view.y=my-(my-view.y)*(nk/view.k);view.k=nk;draw();},{passive:false});

function selectNode(n){
 selected=n;highlight=n?new Set([n.id,...(adj[n.id]||[])]):null;
 const panel=document.getElementById('panel');
 if(!n){panel.style.display='none';draw();return;}
 panel.style.display='block';
 const orc=n.or?`<a href="https://orcid.org/${n.or}" target="_blank" rel="noopener">${n.or}</a>`:'—';
 panel.innerHTML=`<span class="close" onclick="selectNode(null)">×</span>
  <div class="nm">${n.n}</div>
  <div class="cl" style="color:${P[String(n.c)]}">${NM[String(n.c)]}${n.st?' · '+n.st:''}</div>
  ${n.ca?'<div class="badge">consciousness-adjacent</div>':''}
  <div class="row"><span>Rank</span><b>#${n.rk}</b></div>
  <div class="row"><span>Outreach score</span><b>${n.sc.toFixed(3)}</b></div>
  <div class="row"><span>Seed-connectedness</span><b>${n.sd}</b></div>
  <div class="row"><span>Works · recent</span><b>${n.w} · ${n.rw}</b></div>
  <div class="row"><span>Institution</span><b style="text-align:right;max-width:150px">${n.inst||'—'}</b></div>
  <div class="row"><span>Country</span><b>${n.co||'—'}</b></div>
  <div class="row"><span>ORCID</span><b>${orc}</b></div>
  <div style="margin-top:10px;font-size:12px;color:var(--dim)">Openness ${n.o.toFixed(2)}</div>
  <div class="bar"><i style="width:${Math.round(n.o*100)}%"></i></div>`;
 draw();
}

/* legend */
const legend=document.getElementById('legend');
Object.keys(NM).forEach(k=>{if(!nodes.some(n=>String(n.c)===k))return;
 const d=document.createElement('div');d.className='lg';d.dataset.c=k;
 d.innerHTML=`<span class="dot" style="color:${P[k]}"></span>${NM[k]}`;
 d.onclick=()=>{const cc=+k;if(hidden.has(cc)){hidden.delete(cc);d.classList.remove('off');}
   else{hidden.add(cc);d.classList.add('off');}draw();};
 legend.appendChild(d);});

document.getElementById('search').addEventListener('input',e=>{
 const q=e.target.value.toLowerCase().trim();
 if(!q){highlight=null;selected=null;document.getElementById('panel').style.display='none';draw();return;}
 const hits=nodes.filter(n=>n.n.toLowerCase().includes(q));
 highlight=new Set(hits.map(n=>n.id));
 if(hits.length===1)selectNode(hits[0]);else draw();
});
document.getElementById('toggleOpen').onclick=()=>{glow=!glow;draw();};
document.getElementById('reset').onclick=()=>{hidden.clear();highlight=null;selected=null;
 document.querySelectorAll('.lg').forEach(l=>l.classList.remove('off'));
 document.getElementById('panel').style.display='none';document.getElementById('search').value='';
 fit();draw();};

window.addEventListener('resize',()=>{DPR=Math.min(2,window.devicePixelRatio||1);resize();});
let _fitted=false;
function init(){DPR=Math.min(2,window.devicePixelRatio||1);
 if(!fit()){requestAnimationFrame(init);return;}
 _fitted=true;resize();}
requestAnimationFrame(init);
window.addEventListener('load',init);
// re-fit the first time the map actually gets a non-zero size (robust against
// delayed layout / initially-collapsed viewports)
if(window.ResizeObserver){new ResizeObserver(()=>{
 if(!_fitted&&cv.clientWidth>0){init();}else if(_fitted){resize();}
}).observe(cv);}
</script>
</body></html>"""


if __name__ == "__main__":
    main()
