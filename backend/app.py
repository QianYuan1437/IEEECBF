import json
import os
from collections import Counter
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory

from backend.fetcher import (
    REFINED_KEYWORDS,
    fetch_cbf_papers_ieee,
    fetch_high_cited_cbf,
    fetch_arxiv_cbf_preprints,
    get_refined_keywords_meta,
    get_venue_stats,
    search_real_time,
    enrich_citations_s2,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "frontend"),
    static_url_path="",
)

DATA_FILE = os.path.join(BASE_DIR, "papers_data.json")
PAPERS_CACHE = {"latest": [], "high_cited": [], "arxiv": []}
CACHE_LOADED = False


def load_cache():
    global PAPERS_CACHE, CACHE_LOADED
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        PAPERS_CACHE["latest"] = data.get("latest", [])
        PAPERS_CACHE["high_cited"] = data.get("high_cited", [])
        PAPERS_CACHE["arxiv"] = data.get("arxiv", [])
        CACHE_LOADED = True
    except Exception:
        CACHE_LOADED = False


def save_cache():
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(PAPERS_CACHE, f, ensure_ascii=False, indent=2)


def _filter_papers(papers, keyword="", refined_codes=None, venue=""):
    results = papers
    if keyword.strip():
        kw = keyword.strip().lower()
        results = [
            p for p in results
            if kw in p.get("title", "").lower()
            or kw in p.get("abstract", "").lower()
            or any(kw in a.lower() for a in p.get("authors", []))
        ]

    if refined_codes:
        terms = []
        for code in refined_codes:
            if code in REFINED_KEYWORDS:
                terms.extend([t.lower() for t in REFINED_KEYWORDS[code]["terms"]])
        if terms:
            results = [
                p for p in results
                if any(t in p.get("title", "").lower() or t in p.get("abstract", "").lower() for t in terms)
            ]

    if venue.strip():
        v = venue.strip().lower()
        results = [
            p for p in results
            if v in (p.get("venueLabel", "") or "").lower()
            or v in (p.get("venue", "") or "").lower()
            or v in (p.get("journal", "") or "").lower()
        ]

    return results


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "cache_loaded": CACHE_LOADED,
        "cache_papers": {
            "latest": len(PAPERS_CACHE["latest"]),
            "high_cited": len(PAPERS_CACHE["high_cited"]),
            "arxiv": len(PAPERS_CACHE["arxiv"]),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/api/search")
def api_search():
    keyword = request.args.get("keyword", "")
    refined_codes = request.args.getlist("refined")
    venue = request.args.get("venue", "")
    source = request.args.get("source", "all")

    papers = []
    if source == "latest":
        papers = PAPERS_CACHE.get("latest", [])
    elif source == "high_cited":
        papers = PAPERS_CACHE.get("high_cited", [])
    elif source == "arxiv":
        papers = PAPERS_CACHE.get("arxiv", [])
    else:
        papers = (
            PAPERS_CACHE.get("latest", [])
            + PAPERS_CACHE.get("high_cited", [])
            + PAPERS_CACHE.get("arxiv", [])
        )
        seen = set()
        deduped = []
        for p in papers:
            key = p.get("paperId") or p.get("title", "")
            if key in seen:
                continue
            seen.add(key)
            deduped.append(p)
        papers = deduped

    filtered = _filter_papers(papers, keyword=keyword, refined_codes=refined_codes, venue=venue)

    sort_by = request.args.get("sort", "date")
    if sort_by == "citations":
        filtered.sort(key=lambda x: (x.get("citations", 0) or 0), reverse=True)
    else:
        filtered.sort(key=lambda x: (x.get("date") or "", x.get("year") or 0, x.get("citations", 0) or 0), reverse=True)

    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    total = len(filtered)
    page = filtered[offset:offset + limit]

    return jsonify({
        "total": total,
        "limit": limit,
        "offset": offset,
        "papers": page,
    })


@app.route("/api/search/realtime")
def api_search_realtime():
    keyword = request.args.get("keyword", "")
    refined_codes = request.args.getlist("refined")
    max_results = request.args.get("max_results", 50, type=int)

    if not keyword.strip() and not refined_codes:
        refined_codes = ["PTC"]

    results = search_real_time(
        keyword=keyword,
        refined_codes=refined_codes,
        max_results=min(max_results, 100),
    )

    return jsonify({
        "total": len(results),
        "papers": results,
    })


@app.route("/api/keywords")
def api_keywords():
    return jsonify({
        "keywords": get_refined_keywords_meta(),
    })


@app.route("/api/venues")
def api_venues():
    all_papers = (
        PAPERS_CACHE.get("latest", [])
        + PAPERS_CACHE.get("high_cited", [])
    )
    venue_counter = Counter()
    for p in all_papers:
        label = p.get("venueLabel", "")
        if label:
            venue_counter[label] += 1
    venues = [
        {"name": name, "count": count}
        for name, count in venue_counter.most_common(50)
    ]
    return jsonify({"venues": venues})


@app.route("/api/paper/<paper_id>")
def api_paper(paper_id):
    all_papers = (
        PAPERS_CACHE.get("latest", [])
        + PAPERS_CACHE.get("high_cited", [])
        + PAPERS_CACHE.get("arxiv", [])
    )
    for p in all_papers:
        if p.get("paperId") == paper_id:
            return jsonify(p)
    return jsonify({"error": "Paper not found"}), 404


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    try:
        print("Starting cache refresh...")
        latest = fetch_cbf_papers_ieee(max_results=200)
        high_cited = fetch_high_cited_cbf(min_citations=30, max_results=200)
        arxiv_preprints = fetch_arxiv_cbf_preprints(max_results=50)

        all_new = latest + high_cited + arxiv_preprints
        enrich_citations_s2(all_new, delay=0.1)

        PAPERS_CACHE["latest"] = latest
        PAPERS_CACHE["high_cited"] = high_cited
        PAPERS_CACHE["arxiv"] = arxiv_preprints
        save_cache()

        global CACHE_LOADED
        CACHE_LOADED = True

        return jsonify({
            "status": "ok",
            "latest": len(latest),
            "high_cited": len(high_cited),
            "arxiv": len(arxiv_preprints),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats")
def api_stats():
    all_papers = (
        PAPERS_CACHE.get("latest", [])
        + PAPERS_CACHE.get("high_cited", [])
        + PAPERS_CACHE.get("arxiv", [])
    )

    venue_stats = get_venue_stats(all_papers)

    year_counter = Counter()
    for p in all_papers:
        y = p.get("year")
        if y:
            year_counter[int(y)] += 1

    years = [{"year": y, "count": c} for y, c in sorted(year_counter.items(), reverse=True)]

    total_citations = sum(p.get("citations", 0) or 0 for p in all_papers)

    return jsonify({
        "total_papers": len(all_papers),
        "total_citations": total_citations,
        "venue_stats": [{"venue": v, "count": c} for v, c in venue_stats],
        "year_stats": years[:20],
    })


load_cache()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
