# Flame in Freefall Р В Р вЂ Р В РІР‚С™Р Р†Р вЂљРЎСљ Backend

Python 3.12 + FastAPI. The catalogue describes NASA investigations; experimental
records come from one selected CSV. The default is the analyst-prepared FireGap
`tests.csv`: 1,372 records and 61 columns. Demo data has been removed.
This is source-derived data, not independently validated scientific ground truth.
Always display `data_quality_note` and preserve assumptions and missing values.

## Run in Windows PowerShell

```powershell
cd D:\SpaceAppsHackathon
# Only if the virtual environment does not exist:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8001
```

Open http://127.0.0.1:8001/docs. Stop with Ctrl+C.
Swagger is a backend testing interface; the team's frontend connects separately.

## API

| GET | Purpose |
|---|---|
| `/health` | `{"status":"ok"}`, independent of CSV availability |
| `/api/investigations` | Local Python catalogue, independent of CSV availability |
| `/api/metadata` | Columns, inferred types, unknown units, record count, filter fields |
| `/api/experiments?limit=20&offset=0` | Records from the selected CSV |
| `/api/experiments/{experiment_id}` | One record by string ID; otherwise 404 |

Response examples and JavaScript: [FRONTEND_API.md](FRONTEND_API.md).
Future analysis plan (Russian): [AI_PLAN.md](AI_PLAN.md).

Existing `data_source`, `is_test_data`, `experiments`, `experiment`, `values`,
pagination fields, and `page/page_size/filters` requests are preserved.
New fields: `pagination.limit/offset` and `metadata.filter_fields`.
An unknown filter column now returns **400**, including through the legacy
`filters` parameter (previously 422). This is an intentional requirements change.

## Filtering and pagination

```text
/api/experiments?filter_field=experiment&filter_value=FLEX&limit=1&offset=1
```

Filtering uses exact, case-sensitive string comparison **before** pagination.
For multiple conditions, pass `filters` as a URL-encoded JSON object with string
values, such as `{"experiment":"BASS-II","material":"Cotton"}`. Conditions use AND.
The `filter_field/filter_value` pair can supplement `filters`; conflicting values
return 400. Empty values (`filter_value=`) are supported. No matches returns an
empty list and total 0.

`limit`: 1Р В Р вЂ Р В РІР‚С™Р Р†Р вЂљРЎС™100, default 20; `offset`: at least 0, default 0.
Legacy pagination: `page` starts at 1; `page_size` is 1Р В Р вЂ Р В РІР‚С™Р Р†Р вЂљРЎС™100.
Mixing the two pagination schemes returns 400. `total` counts matching records;
`pages` is the page count. With arbitrary offsets, `page` is `offset // limit + 1`;
use offset for navigation rather than reconstructing it from page.
An incomplete filter pair returns 400; invalid numeric parameters or filter JSON
return 422.

## CSV configuration

Default: `backend/data/firegap_dataset/firegap_dataset/tests.csv`. UTF-8 with or without BOM.
All columns are preserved; `name` and `description` are optional.
Headers must be nonempty and unique; row widths must match the header.
Malformed quoting or encoding, missing files, and empty or duplicate IDs return
500 with a safe `detail` message. Diagnostic information stays in server logs.

All values remain strings, preserving whitespace, numeric precision, and leading
zeros. Empty cells remain `""`. Markers such as `NA`, `null`, and `-` are not
automatically replaced. Metadata types are inferred from nonempty column values:
`string`, `integer`, `number`, `boolean`, or `unknown`. These are hints, not a
scientific schema, and do not convert values. ID columns are strings.
Unknown measurement units are explicitly represented as `unit: null`.

Set environment variables in the same terminal before starting the server.
`.env` files are not loaded automatically.

```powershell
$env:EXPERIMENTS_CSV = 'D:\SpaceAppsHackathon\backend\data\analysts.csv'
# Optional: use this when the unique key has a different name.
$env:EXPERIMENTS_ID_COLUMN = 'sample_id'
$env:CSV_DELIMITER = ','
# Only for a verified real dataset:
$env:EXPERIMENTS_IS_TEST_DATA = 'false'
```

External CSV files are marked as test data by default. The bundled FireGap
file defaults to source data; an explicit test-data flag takes precedence. `data_source: csv` does
not verify NASA provenance. Relative paths resolve from the working directory.

ID priority: `EXPERIMENTS_ID_COLUMN`, then `id`, then a SHA-256 hash of row content.
Existing ID formats are preserved. Reordering rows or columns does not change
hashes; changing values does. Identical rows without explicit IDs are rejected:
analysts must supply a unique key. If an `id` column exists, its uniqueness is
checked even when a different key is configured.
Use `encodeURIComponent(id)` in URLs; IDs must not contain `/`.

The CSV is reread on each request. Pagination limits the response, not file reads.
This is intended for a small, prepared hackathon dataset.

## Catalogue and source verification

`app/investigations.py` contains 10 entries. Catalogue IDs are application keys,
not CSV row IDs or PSI identifiers. `description_only_csv_not_connected` means
measurements are not connected **in this backend**, not that NASA lacks data.

Source check, November 14, 2026: direct PSI retrieval returned empty JavaScript
pages. Indexed NASA content confirmed FLEX / PSI-69, Saffire-I / PSI-98, and
SAME-R / PSI-101. SAME and SAME-R remain separate entries.
The mappings PSI-68 / FLEX-2, PSI-99 / Saffire-II, PSI-100 / Saffire-III, and
PSI-25 / BASS-II could not be verified. These links are retained as
`provided_source_url` with `provided_source_status: name_mapping_unverified`.
Their `source_url` points to an accessible official source for the description.

Sources:

- [NASA combustion research overview](https://www.nasa.gov/missions/station/studying-combustion-and-fire-safety/)
- [Saffire IР В Р вЂ Р В РІР‚С™Р Р†Р вЂљРЎС™III, NASA publication](https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/20170000230.pdf)
- [ACME](https://science.nasa.gov/mission/acme/)
- [NASA investigation list: SAME and SAME-R](https://science.nasa.gov/physical-sciences-informatics-psi/nasa-psi-research-opportunity/)
- [FLEX](https://psi.nasa.gov/physci/repo/data/investigations/PSI-69)
- [Saffire-I](https://psi.nasa.gov/physci/repo/data/investigations/PSI-98)
- [SAME-R](https://psi.nasa.gov/physci/repo/data/investigations/PSI-101)

Selecting an investigation does not switch CSV files yet. Later, a small server-side
mapping from `investigation_id` to an approved local CSV path and a selection
parameter in the existing API will be sufficient. Clients should supply approved
keys, not paths. Add this once datasets and their provenance are confirmed;
no additional loading architecture has been introduced.

## CORS and legacy routes

CORS is unchanged: localhost and 127.0.0.1 on ports 3000 and 5173, GET requests.
`FRONTEND_ORIGINS` replaces the list (comma-separated origins, no trailing slash).
Restart after configuration changes. Frontend code is not present in this folder
and has not been modified.

Legacy `/api/fires` was already absent before this development stage. It was
neither removed nor restored here. External consumers cannot be checked without
their frontend code. If the team still uses this route, obtain its exact contract
and agree on a compatibility restoration.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

The existing unittest suite and ASGI HTTP, parameter, and CORS checks are preserved
and extended. No new dependencies are required. To run without a network/event loop:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_offline.py -v
```

16 offline tests passed after FireGap integration. The full HTTP suite was started, but Windows hangs in
`socket.socketpair -> accept` while creating the asyncio loop, before any request.
Diagnostics confirmed this; HTTP/CORS checks have not been verified in this
environment. Offline tests cover the loader, route functions, and OpenAPI, but
do not replace HTTP tests.

`app/main.py`: HTTP and CORS; `app/csv_data.py`: CSV and type inference;
`app/investigations.py`: catalogue; `app/ai.py`: existing analyzer interface.
No database, AI API, API keys, new dependencies, or AI endpoints have been added.

## FireGap integration

`tests.csv` is the only default measurement table. The API preserves all 61 source
columns as strings, including raw fields and analyst quality notes. `test_id` is
not globally unique, so the existing content-hash fallback identifies each record.
Do not set `EXPERIMENTS_ID_COLUMN=test_id` for this dataset.

The default dataset has `is_test_data: false`; this means it is not fictional demo
data, not that every measurement has been verified. An explicit
`EXPERIMENTS_IS_TEST_DATA=true` still overrides this. Custom CSVs default to test
status until explicitly marked otherwise. Clear old CSV/ID/delimiter environment
settings before launching with the supplied dataset.

Catalogue entries with matching experiment names expose `filter_field`,
`filter_values`, and `data_status: analyst_csv_connected`. ACME has several filter
values: query each exact experiment name as needed. Missing/unreadable CSV files
do not prevent the catalogue or health endpoint from responding.

The package also contains 88 day-level logs, planned FLEX-2 envelopes, study
metadata, exclusion reasons, supporting extraction tables, charts and scripts.
They remain in place for provenance and future work; they are not merged into
individual measurements or executed by the API. In particular, FLEX-2 plans are
not measured results, and SAME has no connected rows in this package.
To inspect another CSV later, select its local path with `EXPERIMENTS_CSV` and
explicitly decide its test-data status; do not combine tables at different levels.
Units remain null in API metadata: headers carry supplied units where available,
but several source units are disputed. No scientific conversions are performed.

## Security review and frontend handoff

See SECURITY.md for implemented controls and their limits. The shared API budget
is 240 GET requests per minute per process; oversized URLs return 414. Respect
429 Retry-After responses. Existing allowed CORS origins are unchanged.

Latest validation: 19 offline loader, route and security-guard tests passed.
Full ASGI HTTP tests remain unverified in this Windows execution environment.
Run the full unittest suite on the developer machine before deployment.
FRONTEND_API.md includes integration notes for the supplied standalone HTML and
React alternatives. No frontend source files were changed by this review.
