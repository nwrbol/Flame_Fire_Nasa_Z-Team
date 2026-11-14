# Frontend API

Local backend: http://127.0.0.1:8001
Interactive API: http://127.0.0.1:8001/docs

Start from the project root in Windows PowerShell:

```powershell
Remove-Item Env:EXPERIMENTS_CSV, Env:EXPERIMENTS_ID_COLUMN, Env:CSV_DELIMITER, Env:EXPERIMENTS_IS_TEST_DATA -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8001
```

GET endpoints:
- `/health`: server health, independent of CSV.
- `/api/investigations`: catalogue and available exact experiment filters.
- `/api/experiments?limit=20&offset=0`: selected CSV records.
- `/api/experiments/{id}`: detail; unknown ID returns 404.
- `/api/metadata`: column names, conservative types, unknown units, count, filter fields.

The bundled FireGap tests.csv contains 1,372 records and 61 columns. `values`
contains original strings; empty cells are empty strings, not zero. Preserve
`data_quality_note`, `_raw`, `_assumed` and approximate flags in displays.
`is_test_data: false` identifies the analyst-supplied dataset, not independent
scientific verification. Show a test-data banner whenever the flag is true.
IDs are content hashes because test_id repeats; use the returned id for detail.

Read the catalogue first. Entries marked `analyst_csv_connected` provide
`filter_field` and `filter_values`. ACME has several names; query each separately.
Other catalogue entries may have no measured data. FLEX-2 has plans only, which
are intentionally excluded from this API's measurement list.

```javascript
const API = 'http://127.0.0.1:8001';
async function get(path) {
  const response = await fetch(API + path);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
const catalogue = await get('/api/investigations');
const query = new URLSearchParams({filter_field: 'experiment', filter_value: 'FLEX', limit: '20', offset: '0'});
const data = await get('/api/experiments?' + query);
const detail = await get('/api/experiments/' + encodeURIComponent(data.experiments[0].id));
```

`q` (max 100 chars) is a free-text search: every whitespace-separated word must
appear, case-insensitively, in some field of the record. It combines with the
exact filters (AND) and also runs before pagination.

Filters are exact, case-sensitive, and run before pagination. Unknown columns
return 400. For multiple fields, use `filters` containing JSON string values,
encoded with URLSearchParams. All conditions use AND. Empty filters are supported.
`limit` is 1-100; offset is nonnegative. Existing page/page_size also work, but
cannot be mixed with limit/offset. Invalid pagination returns 422.

CORS allows localhost and 127.0.0.1 on ports 3000 and 5173, unchanged.
Use FRONTEND_ORIGINS only when the actual frontend origin changes, then restart.
Do not use localhost in a deployed frontend to reach a remote backend.
Missing or invalid CSV returns 500; health and catalogue remain available.
`POST /api/chat` (JSON `{message, history}`) answers questions via the RAG
assistant in `ai_assistant/`; it returns `{answer, sources, grounded}` and needs
`Content-Type: application/json`, a body under 64 KB, and stays within 8
requests/min per client (30/min overall). 503 means AI is not configured,
502 means the model did not respond. Supporting logs, plans, metadata and charts are preserved
on disk but are not separate HTTP endpoints.

## Actual response: GET /api/experiments?limit=1

```json
{
  "data_source": "csv",
  "is_test_data": false,
  "dataset": "firegap_tests",
  "provenance": "Analyst-prepared NASA PSI data; not independently revalidated",
  "quality_note": "Read data_quality_note and assumed/raw fields before interpreting values.",
  "experiments": [
    {
      "id": "25d9c496f25b688ca35bc0132c290262e139a627f69a5decfe748981bf81c10c",
      "values": {
        "psi_id": "PSI-98",
        "experiment": "SAFFIRE-I",
        "test_id": "S1",
        "material": "SIBAL Fabric",
        "material_filled_forward": "False",
        "o2_min_pct": "21.5",
        "o2_max_pct": "21.7",
        "o2_approx": "False",
        "o2_note": "",
        "pressure_kpa": "",
        "flow_cm_s": "20.0",
        "flow_direction": "Concurrent",
        "thickness_mm": "3.7",
        "thickness_raw": "0.37 cm",
        "length_cm": "40.6",
        "width_cm": "94.0",
        "ignition_power_w": "182.0",
        "ignition_time_s": "8.0",
        "burn_time_s": "420.0",
        "burn_time_raw": "420",
        "ug_burn_length_raw": "",
        "ug_spread_rate_mm_s": "",
        "ug_spread_raw": "",
        "g1_burn_length_raw": "",
        "g1_spread_raw": "",
        "ug_outcome": "",
        "fuel": "",
        "n2_frac": "",
        "co2_frac_assumed": "",
        "he_frac": "",
        "droplet_d0_mm": "",
        "extinction_d_mm": "",
        "burn_rate_raw_unit_mm": "",
        "test_end": "",
        "test_date": "",
        "test_gmt": "",
        "pi": "",
        "material_class": "",
        "geometry": "",
        "pressure_kpa_assumed": "",
        "o2_final_pct": "",
        "co2_initial_pct": "",
        "co2_final_pct": "",
        "co_initial_ppm": "",
        "co_final_ppm": "",
        "fan_display_raw": "",
        "air_display_raw": "",
        "frames_shot_raw": "",
        "video_refs": "S1C1;S1C2",
        "observations_raw": "",
        "config": "",
        "fuel_frac_burner": "",
        "fuel_frac_ambient": "",
        "fluent_o2_frac": "",
        "cool_flame_obs": "",
        "peak_burner_t_c": "",
        "adiabatic_flame_t_k": "",
        "fuel_dhc_kj_g": "",
        "mass_flux_g_m2s": "",
        "burner_mm": "",
        "data_quality_note": "pressure not stated; outcome/spread rate not stated; length/width columns swapped vs metadata and Saffire-III table (94 cm long x 40.6 cm wide); thickness 0.37 cm is 10x Saffire-II SIBAL (0.37 mm) - possible unit error"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 1,
    "total": 1372,
    "pages": 1372,
    "limit": 1,
    "offset": 0
  }
}
```

## Actual connected catalogue entry (excerpt)

```json
{
  "id": "flex",
  "name": "FLEX",
  "series": "FLEX",
  "description": "Study of liquid fuel droplet combustion and the effectiveness of gaseous fire suppressants in microgravity.",
  "source_url": "https://psi.nasa.gov/physci/repo/data/investigations/PSI-69",
  "data_status": "analyst_csv_connected",
  "filter_field": "experiment",
  "filter_values": [
    "FLEX"
  ]
}
```

## Handoff for the current frontend

The supplied index.html is a standalone page; it does not load main.jsx.
Choose that page or the separate React App.jsx before wiring requests.
Changing api.js alone will not update the standalone page.

Replace hard-coded archive cards with GET /api/investigations. Add a records view
using GET /api/experiments and read fields from each record's values object.
Use GET /api/metadata for available fields. Fetch subsequent pages explicitly;
the default response is not the complete dataset.

The current frontend's /api/materials, /api/simulate, /api/chat and proposed
/api/audit are not implemented. Do not silently fall back to simulated results.
Show loading, empty, unavailable and error states. AI is not connected yet.
The illustrative flame animation is not a validated prediction of fire risk.
Do not display invented risk percentages as NASA measurements.

For Vite local development, point the existing /api proxy to
http://127.0.0.1:8001. A teammate must run their own backend or use a shared hosted
URL; localhost always refers to the machine running the browser/proxy.
For production, configure the public HTTPS API URL or a hosting reverse proxy;
Vite's development proxy does not apply to the deployed build.

Render server strings as text, never unsanitized innerHTML. Keep source quality
notes visible. Product labels should be English. Correct the FLEX source labels
against the catalogue/analyst metadata before displaying them.

The API returns 414 for oversized URLs and 429 with Retry-After for its shared
request budget. Respect Retry-After; do not retry in a tight loop.
