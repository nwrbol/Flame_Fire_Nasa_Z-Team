import csv
import hashlib
import json
import re
from pathlib import Path


def read_dataset(path: Path, id_column=None, delimiter=','):
    with path.open(encoding='utf-8-sig', newline='') as file:
        reader = csv.DictReader(file, delimiter=delimiter, strict=True)
        columns = reader.fieldnames
        if not columns or any(not c.strip() for c in columns) or len(set(columns)) != len(columns):
            raise ValueError('CSV headers must be nonempty and unique')
        rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError('CSV row width does not match headers')
    key = id_column or ('id' if 'id' in columns else None)
    if key and key not in columns:
        raise ValueError('Configured ID column is missing')
    if 'id' in columns and key != 'id':
        ids = [row['id'] for row in rows]
        if any(not value.strip() for value in ids) or len(set(ids)) != len(ids):
            raise ValueError('CSV id values must be nonempty and unique')
    records, seen = [], set()
    for row in rows:
        identifier = row[key] if key else hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if not identifier.strip() or identifier in seen:
            raise ValueError('Empty/duplicate IDs or identical rows; configure a unique ID column')
        seen.add(identifier)
        records.append({'id': identifier, 'values': row})
    metadata = []
    for column in columns:
        values = [r[column] for r in rows if r[column] != '']
        kind = 'unknown'
        if values:
            kind = 'string'
            if column == key:
                kind = 'string'
            elif all(re.fullmatch(r'-?(0|[1-9]\d*)', v) for v in values):
                kind = 'integer'
            elif all(re.fullmatch(r'-?(?:(?:0|[1-9]\d*)(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', v) for v in values):
                kind = 'number'
            elif all(v.lower() in ('true', 'false') for v in values):
                kind = 'boolean'
        metadata.append({'name': column, 'inferred_type': kind, 'has_empty_values': any(r[column] == '' for r in rows), 'unit': None})
    return records, metadata


def read_experiments(path: Path):
    return read_dataset(path)[0]
