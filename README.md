# IEEE CBF Paper Tracker

> CBF (Control Barrier Function) papers from top IEEE journals and conferences (L-CSS, TAC, Automatica, TRO, CDC, ACC, etc.)

本页面由 GitHub Actions 自动更新，每天 07:00、12:00、17:00（北京时间）执行。

---

## Features

- **IEEE Venue Filtering**: Papers from IEEE Control Systems Letters, IEEE TAC, Automatica, IEEE TRO, CDC, ACC, ICRA, IROS, and more
- **Refined Keyword Search**: PTC (Prescribed-Time Control) as default, with optional sub-direction keywords
- **Real-time Search**: Custom keyword input with live API search via Semantic Scholar
- **Dual Mode**:
  1. **GitHub Actions**: Daily auto-fetch → updates papers_data.json + static HTML page
  2. **Local Backend**: Flask API + Vue 3 frontend for interactive real-time search

---

## Quick Start (Local)

```bash
chmod +x start.sh
./start.sh
```

Then open [http://localhost:5000](http://localhost:5000).

---

## Project Structure

```
IEEECBF/
├── .github/workflows/
│   └── update.yml          # GitHub Actions daily update
├── backend/
│   ├── app.py              # Flask API server
│   ├── fetcher.py          # Semantic Scholar + ArXiv fetcher
│   └── requirements.txt
├── frontend/               # Vue 3 SPA
│   ├── index.html
│   ├── app.js
│   └── style.css
├── docs/                   # Generated static pages (GitHub Pages)
│   ├── index.html
│   └── .nojekyll
├── fetch_papers.py         # Standalone fetcher (for GitHub Actions)
├── papers_data.json        # Cached paper database
├── start.sh                # Local startup script
└── README.md
```

---

## API Endpoints (Local)

| Endpoint | Description |
|---|---|
| `GET /api/health` | Service health & cache status |
| `GET /api/search?keyword=&refined=&venue=&sort=` | Search local cache |
| `GET /api/search/realtime?keyword=&refined=` | Real-time Semantic Scholar search |
| `GET /api/keywords` | List refined CBF direction keywords |
| `GET /api/venues` | Venue distribution statistics |
| `GET /api/stats` | Summary statistics |
| `POST /api/refresh` | Refresh paper cache from APIs |

---

## Refined Direction Keywords

| Code | Label | Default |
|---|---|---|
| PTC | Prescribed-Time Control | Yes |
| FTC | Fixed-Time Control | No |
| FInTC | Finite-Time Control | No |
| Adaptive | Adaptive CBF | No |
| Robust | Robust CBF | No |
| Safety | Safety-Critical Control | No |
| HOCBF | High-Order CBF | No |
| ISSf | Input-to-State Safety | No |
| Learning | Learning-Based CBF | No |
| Stochastic | Stochastic CBF | No |
| Event | Event-Triggered CBF | No |
| Distributed | Distributed CBF | No |
| MPC | MPC + CBF | No |
| CLF | CLF-CBF QP | No |

---

## License

MIT
