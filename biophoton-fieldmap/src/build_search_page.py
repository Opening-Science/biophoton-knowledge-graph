"""Build a self-contained paper search page over the full ranked field index.

Reads full_paper_index.sqlite, embeds every paper (with a truncated abstract
snippet for preview + search) into one HTML file with a client-side search,
sub-field / open-access / seed filters, and rank / citation / year sorting.
No server, no external dependencies. Shareable.
"""
from __future__ import annotations

import json
import sqlite3

import pandas as pd

import config as C

ABSTRACT_WORDS = 60   # abstract stored as a truncated inverted index (no prose)
SUBFIELDS = {0: "Biophoton / UPE core", 3: "ROS / redox",
             1: "Sonochemistry", 2: "Bubble & fluid physics",
             4: "Sonoluminescence", 6: "Nanobubbles"}
IN_DB = C.OUTPUTS / "index" / "full_paper_index.sqlite"
OUT = C.OUTPUTS / "index" / "paper_search.html"


import re
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def invert(text: str, max_words: int) -> dict:
    """Abstract as an inverted index {word: [positions]}, truncated. Ships no
    ordered prose; the page reconstructs order in-browser (matches OpenAlex).
    Email addresses that authors embed in abstracts are redacted."""
    text = _EMAIL.sub("", text or "")
    words = text.split()[:max_words]
    idx: dict[str, list[int]] = {}
    for i, w in enumerate(words):
        idx.setdefault(w, []).append(i)
    return idx


def main():
    con = sqlite3.connect(IN_DB)
    df = pd.read_sql_query(
        "SELECT rank, work_id, doi, title, authors, year, cited_by_count, "
        "primary_topic, oa_status, is_oa, is_seed, abstract, openalex_url, link "
        "FROM papers ORDER BY rank", con)
    con.close()

    wc = pd.read_csv(C.EXPORTS / "work_communities.csv")[
        ["work_id", "coupling_community"]]
    df = df.merge(wc, on="work_id", how="left")
    df["sf"] = df["coupling_community"].apply(
        lambda c: int(c) if pd.notna(c) and int(c) in SUBFIELDS else -1)

    papers = []
    for r in df.itertuples():
        papers.append({
            "r": int(r.rank),
            "t": str(r.title or "")[:200],
            "au": str(r.authors or "")[:90],
            "y": int(r.year) if pd.notna(r.year) else None,
            "d": str(r.doi or ""),
            "o": (r.oa_status or "closed"),
            "tp": str(r.primary_topic or "")[:48],
            "s": int(r.is_seed),
            "c": int(r.cited_by_count or 0),
            "sf": int(r.sf),
            "ai": invert(r.abstract, ABSTRACT_WORDS),
            "u": (r.link or r.openalex_url),
        })

    data = {"papers": papers,
            "subfields": {str(k): v for k, v in SUBFIELDS.items()},
            "total": len(papers)}
    html = TEMPLATE.replace("/*__DATA__*/", json.dumps(data, ensure_ascii=False))
    OUT.write_text(html)
    print(f"Wrote {OUT} ({len(html)//1024//1024} MB, {len(papers)} papers)")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Biophoton Field: Paper Search</title>
<style>
:root{--bg:#070b16;--panel:#0e1630;--line:#1e2c4d;--txt:#dbe4f5;--dim:#8a97b5;
 --gold:#ffd24a;--accent:#5aa9ff;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
 font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
header{padding:22px 24px 14px;background:radial-gradient(900px 300px at 30% -80px,#16224a,#070b16);
 border-bottom:1px solid var(--line);position:sticky;top:0;z-index:10;backdrop-filter:blur(6px)}
h1{margin:0 0 3px;font-size:21px}h1 .g{color:var(--gold)}
.sub{color:var(--dim);font-size:13px;margin-bottom:12px}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
input[type=search],select{background:var(--panel);border:1px solid var(--line);
 color:var(--txt);border-radius:9px;padding:9px 12px;outline:none;font-size:14px}
input[type=search]{flex:1;min-width:240px}
label.chk{display:inline-flex;align-items:center;gap:5px;color:var(--dim);font-size:13px;
 background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:8px 11px;cursor:pointer}
.count{color:var(--dim);font-size:13px;margin-left:auto}
main{max-width:1080px;margin:0 auto;padding:16px 24px 60px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
 padding:13px 16px;margin-bottom:10px}
.card .top{display:flex;gap:10px;align-items:baseline}
.rank{color:var(--gold);font-weight:700;font-size:13px;white-space:nowrap}
.title{font-weight:600;font-size:15px;line-height:1.35}
.meta{color:var(--dim);font-size:12.5px;margin:4px 0}
.badge{display:inline-block;font-size:10.5px;padding:1px 7px;border-radius:20px;
 border:1px solid var(--line);margin-right:5px}
.oa{color:#5ad18a;border-color:#2c6b45}.closed{color:#ff8b8b;border-color:#6b3030}
.seed{color:#ffd24a;border-color:#6b5a1f}.sf{color:#9db8e6}
.abs{font-size:12.5px;color:#b9c4dd;line-height:1.5;margin-top:6px;
 max-height:0;overflow:hidden;transition:max-height .2s}
.card.open .abs{max-height:200px}
.links{font-size:12.5px;margin-top:7px}
.more{color:var(--dim);cursor:pointer;font-size:12px}
.empty{color:var(--dim);text-align:center;padding:40px}
</style></head><body>
<header>
 <h1>The <span class="g">Biophoton</span> field: paper search</h1>
 <div class="sub">Every work in the field map, ranked by importance. Search title, authors, or abstract.</div>
 <div class="controls">
   <input type="search" id="q" placeholder="Search papers (e.g. delayed luminescence, oxidative stress)...">
   <select id="sf"></select>
   <select id="sort">
     <option value="r">Sort: field rank</option>
     <option value="c">Sort: citations</option>
     <option value="y">Sort: newest</option>
   </select>
   <label class="chk"><input type="checkbox" id="oaonly"> Open access</label>
   <label class="chk"><input type="checkbox" id="seedonly"> Seeds</label>
   <span class="count" id="count"></span>
 </div>
</header>
<main id="results"></main>
<script>
const DATA = /*__DATA__*/;
const P = DATA.papers, SF = DATA.subfields;
const OA_OPEN = new Set(["gold","green","hybrid","bronze","diamond"]);
const LIMIT = 200;

// abstracts ship as an inverted index {word:[positions]}; reconstruct order here
function recon(ai){if(!ai)return'';const arr=[];for(const w in ai)for(const p of ai[w])arr[p]=w;return arr.join(' ');}
// precompute a display abstract and a lowercase search blob once, on load
P.forEach(p=>{const ab=recon(p.ai);p._ab=ab;
 p._blob=(p.t+' '+p.au+' '+ab+' '+p.tp).toLowerCase();});

const sfSel = document.getElementById('sf');
sfSel.innerHTML = '<option value="">All sub-fields</option>' +
  Object.entries(SF).map(([k,v])=>`<option value="${k}">${v}</option>`).join('') +
  '<option value="-1">Other / adjacency</option>';

const q=document.getElementById('q'), sortSel=document.getElementById('sort'),
 oaonly=document.getElementById('oaonly'), seedonly=document.getElementById('seedonly'),
 results=document.getElementById('results'), countEl=document.getElementById('count');

function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}

function render(){
 const term=q.value.toLowerCase().trim();
 const words=term.split(/\s+/).filter(Boolean);
 const sf=sfSel.value, oaf=oaonly.checked, sf2=seedonly.checked;
 let rows=P.filter(p=>{
   if(sf!==''&&String(p.sf)!==sf)return false;
   if(oaf&&!OA_OPEN.has(p.o))return false;
   if(sf2&&!p.s)return false;
   if(words.length){if(!words.every(w=>p._blob.includes(w)))return false;}
   return true;
 });
 const sv=sortSel.value;
 if(sv==='c')rows.sort((a,b)=>b.c-a.c);
 else if(sv==='y')rows.sort((a,b)=>(b.y||0)-(a.y||0));
 else rows.sort((a,b)=>a.r-b.r);
 countEl.textContent=rows.length.toLocaleString()+' / '+DATA.total.toLocaleString()+' papers';
 const shown=rows.slice(0,LIMIT);
 if(!shown.length){results.innerHTML='<div class="empty">No papers match.</div>';return;}
 results.innerHTML=shown.map(p=>{
   const oaCls=OA_OPEN.has(p.o)?'oa':'closed';
   const sfName=SF[p.sf]||'Other';
   const link=p.u?`<a href="${esc(p.u)}" target="_blank" rel="noopener">${p.d?('doi:'+esc(p.d)):'OpenAlex'}</a>`:'';
   return `<div class="card">
     <div class="top"><span class="rank">#${p.r}</span>
       <span class="title">${esc(p.t)}</span></div>
     <div class="meta">${esc(p.au)}${p.y?(' · '+p.y):''} · ${p.c.toLocaleString()} cites</div>
     <div>
       <span class="badge ${oaCls}">${p.o}</span>
       ${p.s?'<span class="badge seed">seed</span>':''}
       <span class="badge sf">${esc(sfName)}</span>
       <span class="badge">${esc(p.tp)}</span>
     </div>
     ${p._ab?`<div class="abs">${esc(p._ab)}...</div>
       <span class="more">show abstract</span>`:''}
     <div class="links">${link}</div>
   </div>`;
 }).join('') + (rows.length>LIMIT?
   `<div class="empty">Showing top ${LIMIT} of ${rows.length.toLocaleString()}. Refine your search.</div>`:'');
 results.querySelectorAll('.more').forEach(m=>m.onclick=()=>{
   const card=m.closest('.card');card.classList.toggle('open');
   m.textContent=card.classList.contains('open')?'hide abstract':'show abstract';});
}
[q,sfSel,sortSel,oaonly,seedonly].forEach(el=>el.addEventListener('input',render));
render();
</script></body></html>"""


if __name__ == "__main__":
    main()
