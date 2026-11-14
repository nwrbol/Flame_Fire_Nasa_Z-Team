import csv
import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .security import RequestGuard
from .csv_data import read_dataset
from .investigations import INVESTIGATIONS

DATASET_DIR = Path(__file__).resolve().parent.parent / 'data' / 'firegap_dataset' / 'firegap_dataset'
DEFAULT_CSV = DATASET_DIR / 'tests.csv'

app = FastAPI(title='Flame in Freefall API', version='0.2.0')
app.add_middleware(RequestGuard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[s.strip() for s in os.getenv('FRONTEND_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173').split(',') if s.strip()],
    allow_methods=['GET'], allow_headers=['Content-Type'],
)


def load_dataset():
    default = DEFAULT_CSV
    path = Path(os.getenv('EXPERIMENTS_CSV', str(default)))
    try:
        rows, columns = read_dataset(path, os.getenv('EXPERIMENTS_ID_COLUMN'), os.getenv('CSV_DELIMITER', ','))
    except (OSError, ValueError, csv.Error, TypeError) as error:
        logging.getLogger(__name__).exception('Cannot read experiment CSV')
        raise HTTPException(500, 'Experiment CSV is unavailable or invalid') from error
    is_bundled = path.resolve() == default.resolve()
    source = {'data_source': 'csv', 'is_test_data': os.getenv('EXPERIMENTS_IS_TEST_DATA', 'false' if is_bundled else 'true').lower() != 'false'}
    if is_bundled:
        source.update(dataset='firegap_tests', provenance='Analyst-prepared NASA PSI data; not independently revalidated',
                      quality_note='Read data_quality_note and assumed/raw fields before interpreting values.')
    return rows, columns, source


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/api/metadata')
def metadata():
    rows, columns, source = load_dataset()
    return {**source, 'columns': columns, 'total': len(rows), 'ai_available': False,
            'filter_fields': [column['name'] for column in columns]}


@app.get('/api/investigations')
def investigations():
    # Keep the catalogue available even when the selected CSV is missing.
    catalogue = [dict(item) for item in INVESTIGATIONS]
    try:
        rows, _, _ = load_dataset()
    except HTTPException:
        rows = []
    for item in catalogue:
        matches = sorted({row['values'].get('experiment', '') for row in rows
                          if row['values'].get('experiment', '').upper() == item['name'].upper()
                          or (item['id'] == 'acme' and row['values'].get('experiment', '').startswith('ACME'))})
        if matches:
            item.update(data_status='analyst_csv_connected', filter_field='experiment', filter_values=matches)
    return {'investigations': catalogue, 'total': len(catalogue)}


@app.get('/api/experiments')
def experiments(
    page: int | None = Query(None, ge=1),
    page_size: int | None = Query(None, ge=1, le=100),
    filters: str = '{}',
    limit: int | None = Query(None, ge=1, le=100),
    offset: int | None = Query(None, ge=0),
    filter_field: str | None = None,
    filter_value: str | None = None,
):
    try:
        criteria = json.loads(filters)
        if not isinstance(criteria, dict) or any(not isinstance(v, str) for v in criteria.values()):
            raise ValueError()
    except (ValueError, TypeError, RecursionError) as error:
        raise HTTPException(422, 'filters must be a JSON object of existing column names and string values') from error
    if (filter_field is None) != (filter_value is None):
        raise HTTPException(400, 'Provide both filter_field and filter_value')
    if filter_field is not None:
        if filter_field in criteria and criteria[filter_field] != filter_value:
            raise HTTPException(400, 'Conflicting values for the same filter field')
        criteria[filter_field] = filter_value
    rows, columns, source = load_dataset()
    unknown = set(criteria) - {column['name'] for column in columns}
    if unknown:
        raise HTTPException(400, f'Unknown CSV filter field(s): {", ".join(sorted(unknown))}')
    if (limit is not None or offset is not None) and (page is not None or page_size is not None):
        raise HTTPException(400, 'Use either limit/offset or page/page_size, not both')
    rows = [row for row in rows if all(row['values'][k] == v for k, v in criteria.items())]
    size = limit if limit is not None else (page_size or 20)
    start = offset if offset is not None else ((page or 1) - 1) * size
    pagination = {'page': start // size + 1, 'page_size': size,
                  'total': len(rows), 'pages': (len(rows) + size - 1) // size,
                  'limit': size, 'offset': start}
    return {**source, 'experiments': rows[start:start + size], 'pagination': pagination}


@app.get('/api/experiments/{experiment_id}')
def experiment(experiment_id: str):
    rows, _, source = load_dataset()
    for row in rows:
        if row['id'] == experiment_id:
            return {**source, 'experiment': row}
    raise HTTPException(404, 'Experiment not found')
