# MicroFlame

NASA Space Apps 2026 project for the "Flame in Freefall" challenge, about fire in microgravity:

- **Simulator** — pick one of 14 material families that NASA actually burned (PMMA, SIBAL, Nomex, wax, methanol/heptane droplets, ACME gas flames…) and set O₂, pressure, airflow and thickness. Each slider shows where NASA tested (green) and where it did not (stripes); outside the data the panel turns red ("NASA hasn't tested here"). Flame front, outcome and burn time come only from the closest real test within ±1 % O₂ / ±5 kPa, otherwise they read "not in NASA data". The animation is illustrative: a dome-shaped flame in microgravity, a buoyant flame on Earth.
- **NASA PSI catalogue and test records** — 1,372 records from the FireGap dataset with filters, full-text search and CSV / Excel download of the current selection.
- **AI assistant** — answers any question about fire in space, grounded in the dataset (TF-IDF retrieval + Groq LLM). It replies in the language of the question.

The site UI is in English. The data comes from an analyst-prepared NASA PSI dataset and is not independently revalidated; the simulator shows trends, not measurements.

## Layout

| Folder | What |
| --- | --- |
| `frontend/index.html` | The whole website (served by the backend at `/`) |
| `backend/app` | FastAPI: data API, `/api/chat`, request guard (rate limits, body limit, security headers) |
| `ai_assistant` | RAG assistant used by `/api/chat` |
| `backend/data`, `firegap_dataset` | FireGap dataset and its build scripts |

## Run locally (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r ai_assistant\requirements.txt
Copy-Item ai_assistant\.env.example ai_assistant\.env   # then put your GROQ_API_KEY into it
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8001
```

Open http://127.0.0.1:8001/. Without a Groq key the site still works; the chat reports that AI is not configured.

## 3D cabin and gravity data

- `tests.csv` has a `gravity_regime` column, set only from each study's platform in `studies.json` (ISS, or Cygnus in free flight → `microgravity`); unknown would stay empty.
- Gravity values: `backend/data/environments.json` (not part of the archive), read from the NASA NSSDCA Planetary Fact Sheets.
- The 3D cabin (`frontend/js/cabin3d.js`, three.js + cannon-es served locally) is an illustration in metres. Gravity is (0, −g, 0) with g from `environments.json`, fixed physics step 1/120 s; switching environment wakes and re-places every item. A porthole shows a procedural view of Earth, the Moon, Mars or orbit, and its sunlight casts hard or soft shadows. **Drop test** releases a book from 1.00 m and shows the measured time next to t = √(2h/g). Items are decor; only the sample burns. The browser loads nothing from the network. Sources: `CREDITS.md`.
- The backend still serves `/api/knowledge/*` (engine data from `assistant/engine.js`, facts from `facts_all.csv`); the page no longer shows that panel.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.test_security backend.tests.test_offline backend.tests.test_csv_data backend.tests.test_simulator backend.tests.test_knowledge
.\.venv\Scripts\python.exe -m pip install playwright      # once; uses the installed Microsoft Edge
.\.venv\Scripts\python.exe -m unittest e2e.test_site       # browser checks + docs/screenshots/*.png
```

API details: interactive docs at http://127.0.0.1:8001/docs while the server runs.
