"""
Standalone paper fetching script for GitHub Actions.
Fetches CBF papers from IEEE venues using Semantic Scholar + ArXiv,
saves to papers_data.json, and generates a static HTML page in docs/.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from html import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.fetcher import (
    fetch_cbf_papers_ieee,
    fetch_high_cited_cbf,
    fetch_arxiv_cbf_preprints,
    get_venue_stats,
    enrich_citations_s2,
)


def paper_card(p):
    authors = ", ".join(p["authors"][:5]) + (" et al." if len(p["authors"]) > 5 else "")
    venue_label = p.get("venueLabel", "")

    badges = f'<span class="badge badge-venue">{escape(venue_label)}</span>'
    if p.get("citations"):
        badges += f'<span class="badge badge-citations">{p["citations"]} citations</span>'
    if p.get("date") or p.get("year"):
        badges += f'<span class="badge badge-date">{p.get("date") or p.get("year")}</span>'

    url = p.get("url", "")
    link = f'<a href="{escape(url)}" target="_blank" class="paper-link">Paper →</a>' if url else ""

    abstract = p.get("abstract", "")
    abstract_html = f'<p class="abstract">{escape(abstract[:500])}{"..." if len(abstract) > 500 else ""}</p>' if abstract else ""

    search_data = escape(
        f'{p.get("title","")} {" ".join(p.get("authors",[]))} {p.get("abstract","")} {venue_label}'.lower(),
        quote=True,
    )

    return f"""    <div class="paper-card" data-search="{search_data}" data-date="{escape(str(p.get('date','') or p.get('year','')), quote=True)}" data-citations="{p.get('citations',0) or 0}">
      <div class="card-header">{badges}{link}</div>
      <h3>{escape(p["title"])}</h3>
      <p class="authors">{escape(authors)}</p>
      {abstract_html}
    </div>"""


STATIC_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IEEE CBF Papers Tracker</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{--content:min(85vw,1200px)}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f6f9;color:#1a1a2e;line-height:1.5}}
header{{background:linear-gradient(135deg,#0f4c81,#1a1a2e);color:white;padding:2rem;text-align:center}}
header h1{{font-size:1.8rem;margin-bottom:.3rem}}
header p{{opacity:.85;font-size:.9rem}}
header .update-time{{margin-top:.6rem;font-size:.8rem;opacity:.7}}
.tabs{{display:flex;justify-content:center;gap:.5rem;padding:1rem;background:white;border-bottom:1px solid #d8deea;position:sticky;top:0;z-index:10}}
.tab{{padding:.5rem 1.2rem;border:2px solid #0f4c81;border-radius:2rem;background:white;color:#0f4c81;cursor:pointer;font-weight:600;font-size:.85rem;transition:all .15s}}
.tab.active,.tab:hover{{background:#0f4c81;color:white}}
.controls{{width:var(--content);margin:1.2rem auto 0;padding:0;display:flex;flex-direction:column;gap:.8rem}}
.search-row{{display:flex;align-items:center;gap:.8rem}}
.search-input{{flex:1;padding:.75rem 1rem;border:1px solid #d8deea;border-radius:10px;font-size:.92rem;outline:none;background:white}}
.search-input:focus{{border-color:#0f4c81;box-shadow:0 0 0 3px rgba(15,76,129,.1)}}
.sort-wrap{{position:relative;min-width:180px}}
.sort-button{{width:100%;padding:.75rem .9rem;border:1px solid #d8deea;border-radius:10px;background:white;font-size:.9rem;cursor:pointer;display:flex;justify-content:space-between;align-items:center}}
.sort-menu{{display:none;position:absolute;top:calc(100%+4px);left:0;right:0;background:white;border:1px solid #d8deea;border-radius:10px;box-shadow:0 4px 20px rgba(0,0,0,.1);z-index:30;padding:.3rem}}
.sort-menu.open{{display:block}}
.sort-option{{width:100%;text-align:left;border:none;background:white;padding:.5rem .7rem;border-radius:6px;cursor:pointer;font-size:.85rem}}
.sort-option:hover,.sort-option.active{{background:#e8f0fe}}
.refined-chips{{display:flex;flex-wrap:wrap;gap:.4rem}}
.chip{{padding:.35rem .75rem;border:1px solid #d8deea;border-radius:999px;background:white;color:#1a1a2e;cursor:pointer;font-size:.8rem;font-weight:500;transition:all .12s}}
.chip.active,.chip:hover{{background:#0f4c81;color:white;border-color:#0f4c81}}
.section{{display:none;width:var(--content);margin:1.5rem auto 2rem;padding:0}}
.section.active{{display:block}}
.paper-card{{background:white;border-radius:10px;padding:1.1rem 1.3rem;margin-bottom:.8rem;box-shadow:0 2px 8px rgba(0,0,0,.06);transition:box-shadow .15s}}
.paper-card:hover{{box-shadow:0 4px 20px rgba(0,0,0,.1)}}
.card-header{{display:flex;gap:.5rem;margin-bottom:.5rem;flex-wrap:wrap;align-items:center}}
.badge{{font-size:.75rem;padding:.15rem .6rem;border-radius:1rem;font-weight:600}}
.badge-venue{{background:#e8f0fe;color:#0f4c81}}
.badge-citations{{background:#fff3e0;color:#e65100}}
.badge-date{{background:#e8f5e9;color:#2e7d32}}
.paper-link{{font-size:.8rem;color:#0f4c81;text-decoration:none;font-weight:600}}
.paper-link:hover{{text-decoration:underline}}
h3{{font-size:.95rem;margin-bottom:.3rem}}
.authors{{font-size:.8rem;color:#555;margin-bottom:.5rem}}
.abstract{{font-size:.8rem;color:#666;border-top:1px solid #f0f0f0;padding-top:.5rem;margin-top:.5rem}}
.filter-empty{{display:none;width:var(--content);margin:1rem auto 0;padding:0;color:#888;font-size:.85rem}}
footer{{text-align:center;padding:2rem;color:#999;font-size:.8rem}}
@media(max-width:768px){{header h1{{font-size:1.4rem}}.search-row{{flex-direction:column;align-items:stretch}}.sort-wrap{{min-width:100%}}.section,.controls,.filter-empty{{width:92vw}}}}
</style>
</head>
<body>
<header>
  <h1>IEEE CBF Papers Tracker</h1>
  <p>Control Barrier Function papers from top IEEE journals & conferences</p>
  <p class="update-time">Updated: {updated}</p>
</header>
<div class="tabs">
  <button class="tab active" onclick="show('latest',this)">Latest</button>
  <button class="tab" onclick="show('high-cited',this)">High Cited</button>
  <button class="tab" onclick="show('all',this)">All Papers</button>
</div>
<div class="controls">
  <div class="search-row">
    <input id="searchInput" class="search-input" type="text" placeholder="Search title / authors / abstract..." oninput="applyFilters()" />
    <div class="sort-wrap" id="sortWrap">
      <button id="sortButton" class="sort-button" type="button" onclick="toggleSort()">
        <span id="sortLabel">Sort by Time</span><span>▾</span>
      </button>
      <div id="sortMenu" class="sort-menu">
        <button class="sort-option active" onclick="chooseSort('time',this)">Sort by Time</button>
        <button class="sort-option" onclick="chooseSort('citations',this)">Sort by Citations</button>
      </div>
    </div>
  </div>
  <div class="refined-chips" id="venueChips">
    {venue_chips}
  </div>
</div>
<p id="filterEmpty" class="filter-empty">No papers match current filters.</p>
<div id="latest" class="section active">{latest_cards}</div>
<div id="high-cited" class="section">{hc_cards}</div>
<div id="all" class="section">{all_cards}</div>
<footer>Auto-updated by GitHub Actions | <a href="https://github.com/QianYuan1437/IEEECBF">Source</a></footer>
<script>
let activeSort='time';let activeVenue='';
function toggleSort(){{document.getElementById('sortMenu').classList.toggle('open')}}
function chooseSort(s,btn){{activeSort=s;document.querySelectorAll('.sort-option').forEach(o=>o.classList.remove('active'));btn.classList.add('active');document.getElementById('sortLabel').textContent=s==='citations'?'Sort by Citations':'Sort by Time';document.getElementById('sortMenu').classList.remove('open');applyFilters()}}
function applyFilters(){{var q=(document.getElementById('searchInput')?.value||'').trim().toLowerCase();var section=document.querySelector('.section.active');if(!section)return;var cards=Array.from(section.querySelectorAll('.paper-card'));var empty=document.getElementById('filterEmpty');cards.sort((a,b)=>{{var aD=a.dataset.date||'',bD=b.dataset.date||'',aC=parseInt(a.dataset.citations||'0'),bC=parseInt(b.dataset.citations||'0');if(activeSort==='citations')return(bC-aC)||bD.localeCompare(aD);return bD.localeCompare(aD)||(bC-aC)}});var visible=0;cards.forEach(c=>{{var text=(c.dataset.search||'').toLowerCase();var show=true;if(q&&!text.includes(q))show=false;if(activeVenue&&!text.includes(activeVenue.toLowerCase()))show=false;c.style.display=show?'':'none';if(show)visible++}});empty.style.display=visible?'none':'block';cards.forEach(c=>section.appendChild(c))}}
function show(id,btn){{document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));document.getElementById(id).classList.add('active');btn.classList.add('active');applyFilters()}}
function setVenue(v,btn){{activeVenue=v;document.querySelectorAll('#venueChips .chip').forEach(c=>c.classList.remove('active'));btn.classList.add('active');applyFilters()}}
document.addEventListener('click',function(e){{var w=document.getElementById('sortWrap'),m=document.getElementById('sortMenu');if(w&&m&&!w.contains(e.target))m.classList.remove('open')}});
applyFilters();
</script>
</body>
</html>"""


def load_existing_data():
    try:
        with open("papers_data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"latest": [], "high_cited": [], "arxiv": []}


def main():
    print("=" * 60)
    print("  IEEE CBF Paper Tracker - GitHub Actions Update")
    print("=" * 60)

    existing = load_existing_data()

    latest, high_cited, arxiv_preprints = [], [], []

    print("\n[1/4] Fetching latest IEEE CBF papers...")
    try:
        latest = fetch_cbf_papers_ieee(refined_codes=["PTC"], max_results=300)
    except Exception as e:
        print(f"  -> API fetch failed: {e}")
    if not latest and existing.get("latest"):
        print("  -> Falling back to existing cached data")
        latest = existing["latest"]
    print(f"  -> Found {len(latest)} latest papers")

    print("\n[2/4] Fetching high-citation CBF papers...")
    try:
        high_cited = fetch_high_cited_cbf(min_citations=30, max_results=200)
    except Exception as e:
        print(f"  -> API fetch failed: {e}")
    if not high_cited and existing.get("high_cited"):
        print("  -> Falling back to existing cached data")
        high_cited = existing["high_cited"]
    print(f"  -> Found {len(high_cited)} high-cited papers")

    print("\n[3/4] Fetching ArXiv CBF preprints...")
    try:
        arxiv_preprints = fetch_arxiv_cbf_preprints(max_results=50)
    except Exception as e:
        print(f"  -> API fetch failed: {e}")
    if not arxiv_preprints and existing.get("arxiv"):
        print("  -> Falling back to existing cached data")
        arxiv_preprints = existing["arxiv"]
    print(f"  -> Found {len(arxiv_preprints)} ArXiv preprints")

    print("\n[4/4] Enriching citation counts...")
    all_papers = latest + high_cited + arxiv_preprints
    try:
        enrich_citations_s2(all_papers, delay=0.08)
    except Exception as e:
        print(f"  -> Citation enrichment failed: {e}")
    print(f"  -> Enriched {len(all_papers)} papers")

    data_file = "papers_data.json"
    print(f"\nSaving paper data to {data_file}...")
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump({
            "latest": latest,
            "high_cited": high_cited,
            "arxiv": arxiv_preprints,
            "updated": datetime.now(timezone.utc).isoformat(),
        }, f, ensure_ascii=False, indent=2)

    print("\nGenerating static HTML page...")
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    latest_cards = "\n".join(paper_card(p) for p in latest[:200])
    hc_cards = "\n".join(paper_card(p) for p in high_cited[:200])

    seen = set()
    all_unique = []
    for p in latest + high_cited + arxiv_preprints:
        key = p.get("paperId") or p.get("title", "")
        if key in seen:
            continue
        seen.add(key)
        all_unique.append(p)
    all_cards = "\n".join(paper_card(p) for p in all_unique[:300])

    venue_stats = get_venue_stats(latest + high_cited)
    venue_chips_html = '<button class="chip active" type="button" onclick="setVenue(\'\',this)">All</button>\n'
    for venue_name, count in venue_stats[:20]:
        venue_chips_html += f'    <button class="chip" type="button" onclick="setVenue(\'{escape(venue_name)}\',this)">{escape(venue_name)} ({count})</button>\n'

    html = STATIC_HTML_TEMPLATE.format(
        updated=updated,
        latest_cards=latest_cards,
        hc_cards=hc_cards,
        all_cards=all_cards,
        venue_chips=venue_chips_html,
    )

    os.makedirs("docs", exist_ok=True)
    with open("docs/.nojekyll", "w") as f:
        f.write("")

    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("  -> docs/index.html generated")
    print("\nDone!")
    print(f"  Total latest: {len(latest)}")
    print(f"  Total high-cited: {len(high_cited)}")
    print(f"  Total ArXiv: {len(arxiv_preprints)}")


if __name__ == "__main__":
    main()
