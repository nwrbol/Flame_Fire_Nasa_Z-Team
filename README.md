# Flame in Freefall

NASA Space Apps 2026 project about fire in microgravity:

- **Simulator** — an illustrative spirit-lamp flame: blue and spherical in microgravity, yellow and buoyant on Earth, with soot/vapour smoke.
- **NASA PSI catalogue and test records** — 1,372 records from the FireGap dataset with filters and full-text search.
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

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.test_security backend.tests.test_offline backend.tests.test_csv_data
```

API details: [backend/FRONTEND_API.md](backend/FRONTEND_API.md).
