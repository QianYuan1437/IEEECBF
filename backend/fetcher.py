import re
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Optional
from xml.etree import ElementTree as ET

import requests


SEMANTIC_SCHOLAR_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_SCHOLAR_PAPER = "https://api.semanticscholar.org/graph/v1/paper"
SEMANTIC_SCHOLAR_BULK = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
CROSSREF_API = "https://api.crossref.org/works"

CBF_CORE_TERMS = [
    "control barrier function",
    "control barrier functions",
    "CBF",
]

IEEE_VENUE_PATTERNS = [
    re.compile(r"ieee control systems letters", re.IGNORECASE),
    re.compile(r"l-css", re.IGNORECASE),
    re.compile(r"ieee robotics and automation letters", re.IGNORECASE),
    re.compile(r"ieee.*transactions on automatic control", re.IGNORECASE),
    re.compile(r"automatica", re.IGNORECASE),
    re.compile(r"ieee.*transactions on robotics", re.IGNORECASE),
    re.compile(r"ieee.*transactions on control systems technology", re.IGNORECASE),
    re.compile(r"ieee.*transactions on systems.? man.*cybernetics", re.IGNORECASE),
    re.compile(r"international journal of robust and nonlinear control", re.IGNORECASE),
    re.compile(r"systems.? control letters", re.IGNORECASE),
    re.compile(r"nonlinear analysis.*hybrid systems", re.IGNORECASE),
    re.compile(r"annual reviews in control", re.IGNORECASE),
    re.compile(r"ieee.*transactions on intelligent transportation", re.IGNORECASE),
    re.compile(r"ieee.*transactions on mechatronics", re.IGNORECASE),
    re.compile(r"ieee\/asme.*transactions on mechatronics", re.IGNORECASE),
    re.compile(r"ifac.*automatica", re.IGNORECASE),
    re.compile(r"conference on decision and control", re.IGNORECASE),
    re.compile(r"american control conference", re.IGNORECASE),
    re.compile(r"ieee.*conference.*robotics.*automation", re.IGNORECASE),
    re.compile(r"intelligent robots and systems", re.IGNORECASE),
    re.compile(r"robotics.? science and systems", re.IGNORECASE),
    re.compile(r"conference on robot learning", re.IGNORECASE),
    re.compile(r"european control conference", re.IGNORECASE),
    re.compile(r"ieee control systems magazine", re.IGNORECASE),
    re.compile(r"ieee access", re.IGNORECASE),
    re.compile(r"ieee.*control technology", re.IGNORECASE),
]

VENUE_LABELS = {
    "IEEE Control Systems Letters": "L-CSS",
    "IEEE Robotics and Automation Letters": "RA-L",
    "IEEE Transactions on Automatic Control": "TAC",
    "Automatica": "Automatica",
    "IEEE Transactions on Robotics": "TRO",
    "IEEE Transactions on Control Systems Technology": "TCST",
    "IEEE Trans. Systems, Man, and Cybernetics": "TSMC",
    "Int. J. Robust Nonlinear Control": "IJRNC",
    "Systems & Control Letters": "SCL",
    "Nonlinear Analysis: Hybrid Systems": "NAHS",
    "Annual Reviews in Control": "ARC",
    "CDC": "CDC",
    "ACC": "ACC",
    "ICRA": "ICRA",
    "IROS": "IROS",
    "RSS": "RSS",
    "CoRL": "CoRL",
    "ECC": "ECC",
}

REFINED_KEYWORDS = {
    "PTC": {
        "label": "Prescribed-Time Control",
        "zh": "预设时间控制",
        "terms": ["prescribed-time control", "prescribed-time", "ptc", "predefined-time control", "predefined-time"],
    },
    "FTC": {
        "label": "Fixed-Time Control",
        "zh": "固定时间控制",
        "terms": ["fixed-time control", "fixed-time"],
    },
    "FInTC": {
        "label": "Finite-Time Control",
        "zh": "有限时间控制",
        "terms": ["finite-time control", "finite-time"],
    },
    "Adaptive": {
        "label": "Adaptive CBF",
        "zh": "自适应CBF",
        "terms": ["adaptive control barrier", "adaptive cbf"],
    },
    "Robust": {
        "label": "Robust CBF",
        "zh": "鲁棒CBF",
        "terms": ["robust control barrier", "robust cbf", "robustness"],
    },
    "Safety": {
        "label": "Safety-Critical Control",
        "zh": "安全关键控制",
        "terms": ["safety-critical", "safety critical"],
    },
    "HOCBF": {
        "label": "High-Order CBF",
        "zh": "高阶CBF",
        "terms": ["high-order control barrier", "high order cbf", "hocbf"],
    },
    "ISSf": {
        "label": "Input-to-State Safety",
        "zh": "输入-状态安全",
        "terms": ["input-to-state safety", "issf", "issf-cbf"],
    },
    "Learning": {
        "label": "Learning-Based CBF",
        "zh": "基于学习的CBF",
        "terms": ["learning", "neural cbf", "reinforcement learning cbf", "rl cbf"],
    },
    "Stochastic": {
        "label": "Stochastic CBF",
        "zh": "随机CBF",
        "terms": ["stochastic cbf", "stochastic control barrier"],
    },
    "Event": {
        "label": "Event-Triggered CBF",
        "zh": "事件触发CBF",
        "terms": ["event-triggered cbf", "event triggered cbf"],
    },
    "Distributed": {
        "label": "Distributed CBF",
        "zh": "分布式CBF",
        "terms": ["distributed cbf", "distributed control barrier", "multi-agent cbf"],
    },
    "MPC": {
        "label": "MPC + CBF",
        "zh": "模型预测控制结合CBF",
        "terms": ["mpc cbf", "model predictive control barrier", "mpc-cbf"],
    },
    "CLF": {
        "label": "CLF-CBF QP",
        "zh": "CLF-CBF二次规划",
        "terms": ["clf-cbf", "clf cbf", "control lyapunov barrier"],
    },
}

ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_SUBJECT_LABELS = {
    "cs.AI": "Artificial Intelligence",
    "cs.RO": "Robotics",
    "cs.LG": "Machine Learning",
    "cs.SY": "Systems and Control",
    "cs.CV": "Computer Vision",
    "eess.SY": "Systems and Control",
    "math.OC": "Optimization and Control",
    "math.DS": "Dynamical Systems",
    "stat.ML": "Machine Learning",
}


def _is_cbf_paper(title: str = "", abstract: str = "") -> bool:
    text = f"{title} {abstract}".lower()
    return any(term in text for term in CBF_CORE_TERMS)


def _match_refined_keyword(title: str = "", abstract: str = "", keywords: list = None) -> bool:
    if not keywords:
        return True
    text = f"{title} {abstract}".lower()
    return any(kw.lower() in text for kw in keywords)


def _get_refined_terms(key_codes: list) -> list:
    terms = []
    for code in key_codes:
        if code in REFINED_KEYWORDS:
            terms.extend(REFINED_KEYWORDS[code]["terms"])
    return terms


def _venue_matches_ieee(venue_name: str = "", journal_name: str = "") -> bool:
    combined = f"{venue_name} {journal_name}"
    if not combined.strip():
        return False
    for pattern in IEEE_VENUE_PATTERNS:
        if pattern.search(combined):
            return True
    return False


def _extract_venue_label(venue_name: str = "", journal_name: str = "") -> str:
    combined = f"{venue_name} {journal_name}".lower()

    if "control systems letters" in combined:
        return "L-CSS"
    if "robotics and automation letters" in combined:
        return "RA-L"
    if "transactions on automatic control" in combined:
        return "TAC"
    if "automatica" in combined and "conference" not in combined:
        return "Automatica"
    if "transactions on robotics" in combined:
        return "TRO"
    if "transactions on control systems technology" in combined:
        return "TCST"
    if "systems, man" in combined and "cybernetics" in combined:
        return "TSMC"
    if "robust and nonlinear" in combined:
        return "IJRNC"
    if "systems & control letters" in combined or "systems and control letters" in combined:
        return "SCL"
    if "nonlinear analysis" in combined and "hybrid" in combined:
        return "NAHS"
    if "annual reviews in control" in combined:
        return "ARC"
    if "decision and control" in combined:
        return "CDC"
    if "american control" in combined:
        return "ACC"
    if "robotics and automation" in combined and "conference" in combined:
        return "ICRA"
    if "intelligent robots and systems" in combined:
        return "IROS"
    if "robotics: science" in combined or "robotics science" in combined:
        return "RSS"
    if "robot learning" in combined:
        return "CoRL"
    if "european control" in combined:
        return "ECC"
    if "ieee access" in combined:
        return "IEEE Access"
    if "ieee transactions" in combined:
        return "IEEE Trans"
    if "ieee" in combined:
        return "IEEE"
    return venue_name or journal_name or "Unknown"


def _paper_from_s2(item: dict) -> dict:
    ext_ids = item.get("externalIds") or {}
    arxiv_id = ext_ids.get("ArXiv") or ""
    doi = ext_ids.get("DOI") or ""

    if doi:
        url = f"https://doi.org/{doi}"
    elif arxiv_id:
        url = f"https://arxiv.org/abs/{arxiv_id}"
    else:
        pid = item.get("paperId", "")
        url = f"https://www.semanticscholar.org/paper/{pid}" if pid else ""

    journal_info = item.get("journal") or {}
    venue_info = item.get("publicationVenue") or {}
    journal_name = journal_info.get("name", "") if isinstance(journal_info, dict) else ""
    venue_name = venue_info.get("name", "") if isinstance(venue_info, dict) else ""

    authors = [a.get("name", "") for a in (item.get("authors") or [])]

    return {
        "paperId": item.get("paperId", ""),
        "title": item.get("title", ""),
        "authors": authors,
        "year": item.get("year"),
        "date": item.get("publicationDate", ""),
        "citations": item.get("citationCount", 0) or 0,
        "arxivId": arxiv_id,
        "doi": doi,
        "url": url,
        "abstract": item.get("abstract") or "",
        "journal": journal_name,
        "venue": venue_name,
        "venueLabel": _extract_venue_label(venue_name, journal_name),
        "subjects": [],
    }


def search_s2(query: str, limit: int = 100, offset: int = 0,
              year_from: str = None, year_to: str = None,
              fields_of_study: list = None, retries: int = 3,
              timeout: int = 30) -> dict:
    search_fields = (
        "paperId,title,authors,year,citationCount,externalIds,"
        "publicationDate,abstract,journal,publicationVenue,"
        "publicationTypes,openAccessPdf"
    )
    params = {
        "query": query,
        "limit": min(limit, 100),
        "offset": offset,
        "fields": search_fields,
    }
    if year_from:
        params["year"] = f"{year_from}-{year_to or ''}"

    for attempt in range(retries):
        try:
            resp = requests.get(SEMANTIC_SCHOLAR_SEARCH, params=params, timeout=timeout)
        except requests.RequestException:
            resp = None

        if resp is not None and resp.status_code == 200:
            return resp

        if resp is not None and resp.status_code == 429:
            wait = 5 * (attempt + 1)
            time.sleep(wait)
            continue

        if attempt < retries - 1:
            time.sleep(1.5 * (attempt + 1))

    return None


def search_s2_bulk(query: str, total: int = 500, batch_size: int = 100) -> list:
    all_items = []
    offset = 0
    while offset < total:
        resp = search_s2(query, limit=batch_size, offset=offset)
        if not resp:
            break
        try:
            data = resp.json()
        except Exception:
            break
        items = data.get("data", [])
        if not items:
            break
        all_items.extend(items)
        offset += len(items)
        if offset >= data.get("total", 0):
            break
        time.sleep(0.5)
    return all_items


def fetch_cbf_papers_ieee(
    refined_codes: list = None,
    extra_keywords: str = "",
    max_results: int = 500,
    year_from: str = None,
    year_to: str = None,
) -> list:
    refined_codes = refined_codes or []
    refined_terms = _get_refined_terms(refined_codes)

    if extra_keywords.strip():
        extra_terms = [t.strip() for t in extra_keywords.split(",") if t.strip()]
        refined_terms.extend(extra_terms)

    papers = []
    seen_pids = set()
    seen_titles = set()

    queries = []

    if refined_terms:
        for rt in refined_terms:
            q = f'"control barrier function" AND "{rt}"'
            queries.append(q)
            q2 = f'"control barrier function" {rt}'
            queries.append(q2)
    else:
        queries = ['"control barrier function"']

    for query in queries:
        if len(papers) >= max_results:
            break
        remaining = max_results - len(papers)
        batch = min(remaining, 100)
        resp = search_s2(query, limit=batch, offset=0, year_from=year_from, year_to=year_to)
        if not resp:
            continue
        try:
            data = resp.json()
        except Exception:
            continue

        for item in data.get("data", []):
            paper = _paper_from_s2(item)

            if not _is_cbf_paper(paper["title"], paper["abstract"]):
                continue

            pid = paper["paperId"]
            title_key = paper["title"].lower().strip()[:80]
            if pid in seen_pids or title_key in seen_titles:
                continue
            seen_pids.add(pid)
            seen_titles.add(title_key)

            journal_name = paper.get("journal", "")
            venue_name = paper.get("venue", "")

            if not _venue_matches_ieee(venue_name, journal_name):
                if len(papers) < max_results * 0.2:
                    papers.append(paper)
                continue

            papers.append(paper)
            if len(papers) >= max_results:
                break

        time.sleep(0.3)

    papers.sort(key=lambda x: (x.get("year") or 0, x.get("citations", 0) or 0), reverse=True)
    return papers[:max_results]


def fetch_high_cited_cbf(min_citations: int = 30, max_results: int = 300) -> list:
    papers = []
    seen = set()

    queries = [
        '"control barrier function"',
        "control barrier function",
        "CBF safety-critical control",
    ]

    for query in queries:
        offset = 0
        while len(papers) < max_results:
            resp = search_s2(query, limit=100, offset=offset)
            if not resp:
                break
            try:
                data = resp.json()
            except Exception:
                break
            items = data.get("data", [])
            if not items:
                break

            for item in items:
                if (item.get("citationCount") or 0) < min_citations:
                    continue
                paper = _paper_from_s2(item)
                if not _is_cbf_paper(paper["title"], paper["abstract"]):
                    continue
                key = paper["paperId"] or paper["title"]
                if key in seen:
                    continue
                seen.add(key)

                journal_name = paper.get("journal", "")
                venue_name = paper.get("venue", "")
                if _venue_matches_ieee(venue_name, journal_name):
                    papers.append(paper)
                elif len(papers) < max_results * 0.3:
                    papers.append(paper)

                if len(papers) >= max_results:
                    break

            offset += 100
            if offset >= data.get("total", 0):
                break
            time.sleep(1)

        if len(papers) >= max_results:
            break

    papers.sort(key=lambda x: (x.get("citations", 0) or 0), reverse=True)
    return papers[:max_results]


def enrich_citations_s2(papers: list, delay: float = 0.05) -> list:
    for p in papers:
        pid = p.get("paperId", "")
        if not pid:
            continue
        try:
            resp = requests.get(
                f"{SEMANTIC_SCHOLAR_PAPER}/{pid}",
                params={"fields": "citationCount"},
                timeout=10,
            )
            if resp.status_code == 200:
                p["citations"] = resp.json().get("citationCount", p.get("citations", 0)) or 0
        except Exception:
            pass
        time.sleep(delay)
    return papers


def fetch_arxiv_cbf_preprints(max_results: int = 50) -> list:
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    try:
        resp = requests.get(ARXIV_API, params={
            "search_query": 'all:"control barrier function"',
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception:
        return []

    papers = []
    for entry in root.findall("atom:entry", ns):
        aid = entry.find("atom:id", ns).text.split("/abs/")[-1]
        title = entry.find("atom:title", ns).text.strip()
        abstract = entry.find("atom:summary", ns).text.strip()
        if not _is_cbf_paper(title, abstract):
            continue
        primary = entry.find("arxiv:primary_category", ns)
        primary_term = primary.get("term") if primary is not None else ""
        all_terms = [c.get("term") for c in entry.findall("atom:category", ns) if c.get("term")]
        subjects = [primary_term] if primary_term else []
        subjects.extend([t for t in all_terms if t != primary_term])

        authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]

        papers.append({
            "paperId": f"arxiv:{aid}",
            "title": title,
            "authors": authors,
            "year": None,
            "date": entry.find("atom:published", ns).text[:10] if entry.find("atom:published", ns) is not None else "",
            "citations": 0,
            "arxivId": aid,
            "doi": "",
            "url": f"https://arxiv.org/abs/{aid}",
            "abstract": abstract,
            "journal": "",
            "venue": "",
            "venueLabel": "arXiv",
            "subjects": subjects,
        })

    return papers


def search_real_time(
    keyword: str = "",
    refined_codes: list = None,
    max_results: int = 50,
) -> list:
    refined_codes = refined_codes or []
    refined_terms = _get_refined_terms(refined_codes)

    base_query = '"control barrier function"'
    if keyword.strip():
        base_query += f' AND "{keyword.strip()}"'
    elif refined_terms:
        for rt in refined_terms[:3]:
            base_query += f' AND "{rt}"'

    resp = search_s2(base_query, limit=max_results, offset=0)
    if not resp:
        return []

    try:
        data = resp.json()
    except Exception:
        return []

    papers = []
    seen = set()
    for item in data.get("data", []):
        paper = _paper_from_s2(item)
        if not _is_cbf_paper(paper["title"], paper["abstract"]):
            continue
        key = paper["paperId"] or paper["title"].lower()[:80]
        if key in seen:
            continue
        seen.add(key)

        journal_name = paper.get("journal", "")
        venue_name = paper.get("venue", "")
        if _venue_matches_ieee(venue_name, journal_name):
            papers.append(paper)
        elif len(papers) < max_results * 0.3:
            papers.append(paper)

        if len(papers) >= max_results:
            break

    return papers


def get_refined_keywords_meta() -> list:
    return [
        {
            "code": code,
            "label": info["label"],
            "zh": info.get("zh", ""),
            "default": code == "PTC",
        }
        for code, info in REFINED_KEYWORDS.items()
    ]


def get_venue_stats(papers: list) -> list:
    venue_counter = Counter()
    for p in papers:
        label = p.get("venueLabel", "Other")
        venue_counter[label] += 1
    return venue_counter.most_common(30)
