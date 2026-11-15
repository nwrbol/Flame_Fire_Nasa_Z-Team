"""Build frontend/assets/analytics.json for the Analytics dashboard.

Reads the FireGap tests.csv, studies.json and data/facts_all.csv that the backend serves
(backend/data/firegap_dataset/firegap_dataset/), derives every record with
backend/app/analytics.py (the same code the filtered CSV export uses) and writes a compact
JSON: records as arrays + precomputed totals. Nothing is typed in by hand: the reference
atmospheres are parsed from facts_all.csv (facts X04, X22, X24).

Usage:  .venv\\Scripts\\python.exe scripts\\build_analytics.py
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import analytics as A  # noqa: E402
from backend.app.csv_data import read_dataset  # noqa: E402

DATASET = ROOT / 'backend' / 'data' / 'firegap_dataset' / 'firegap_dataset'
OUT = ROOT / 'frontend' / 'assets' / 'analytics.json'
FIELDS = ['id', 'test', 'study', 'family', 'material', 'o2', 'kpa', 'kpa_assumed', 'flow', 'thick', 'outcome', 'flags', 'gravity']


def num(text):
    return float(text.replace(',', '.'))


def references(facts):
    """Reference atmospheres, parsed from the fact texts (Russian original, decimal commas)."""
    by_id = {f['id']: f['fact_ru'] for f in facts}
    refs = []
    m = re.search(r'при (20,9)% O2 и [\d,]+ psi \(([\d,]+) кПа\)', by_id['X04'])
    refs.append({'id': 'iss', 'label': 'ISS cabin (sea-level air)', 'o2': num(m.group(1)), 'kpa': num(m.group(2)), 'fact': 'X04'})
    m = re.search(r'Шаттл сертифицировали на [\d,]+ psia \(([\d,]+) кПа\) и ([\d,]+)% O2', by_id['X22'])
    refs.append({'id': 'shuttle', 'label': 'Space Shuttle', 'o2': num(m.group(2)), 'kpa': num(m.group(1)), 'fact': 'X22'})
    m = re.search(r'([\d,]+) psia \(([\d,]+) кПа\) и ([\d,]+)% O2', by_id['X22'])
    refs.append({'id': 'lunar', 'label': 'Lunar base (proposed)', 'o2': num(m.group(3)), 'kpa': num(m.group(2)), 'fact': 'X22'})
    m = re.search(r'([\d,]+) psi, ([\d,]+)% O2', by_id['X24'])
    refs.append({'id': 'apollo', 'label': 'Apollo cabin', 'o2': num(m.group(2)), 'kpa': round(num(m.group(1)) * 6.894757, 1), 'fact': 'X24',
                 'note': f'{m.group(1)} psi'})
    return refs


def ventilation(facts):
    text = next(f['fact_ru'] for f in facts if f['id'] == 'X20')
    m = re.search(r'вентиляции космоаппарата \((\d+)[–-](\d+) см/с\)', text)
    return {'lo': float(m.group(1)), 'hi': float(m.group(2)), 'label': 'Spacecraft ventilation', 'fact': 'X20'}


def main():
    rows, _ = read_dataset(DATASET / 'tests.csv')
    studies = json.loads((DATASET / 'studies.json').read_text(encoding='utf-8'))
    with (DATASET / 'data' / 'facts_all.csv').open(encoding='utf-8-sig', newline='') as f:
        facts = list(csv.DictReader(f))
    platforms = {s['acronym']: s.get('platform', '') for s in studies}

    derived = [(r, A.derive(r['values'], platforms)) for r in rows]
    study_names = sorted({d['study'] for _, d in derived})
    materials = sorted({d['material'] for _, d in derived}, key=lambda m: (m == A.NOT_STATED, m))
    gravities = sorted({d['gravity'] for _, d in derived})

    def compact(x):
        return None if x is None else round(x, 3)

    records = []
    for r, d in derived:
        mask = sum(1 << A.QUALITY_IDS.index(q) for q in d['flags'])
        records.append([r['id'], r['values'].get('test_id', ''), study_names.index(d['study']), d['family'], materials.index(d['material']),
                        compact(d['o2']), compact(d['kpa']), 1 if d['kpa_assumed'] else 0, compact(d['flow']), compact(d['thick']),
                        d['outcome'], mask, gravities.index(d['gravity'])])

    n = len(derived)
    c = lambda key: dict(Counter(d[key] for _, d in derived))  # noqa: E731
    totals = {
        'records': n,
        'studies_with_records': len(study_names),
        'studies_in_catalogue': len(studies),
        'with_o2_and_pressure': sum(1 for _, d in derived if d['o2'] is not None and d['kpa'] is not None),
        'with_outcome': sum(1 for _, d in derived if d['outcome'] != 'none'),
        'with_flags': sum(1 for _, d in derived if d['flags']),
        'partial_gravity': sum(1 for _, d in derived if d['gravity'] in ('lunar', 'martian', 'partial')),
        'by_study': c('study'), 'by_family': c('family'), 'by_material': c('material'), 'by_outcome': c('outcome'),
        'by_gravity': {g or 'unknown': v for g, v in c('gravity').items()},
        'by_flag': {q: sum(1 for _, d in derived if q in d['flags']) for q in A.QUALITY_IDS},
        'flow_not_recorded': sum(1 for _, d in derived if d['flow'] is None),
    }
    assert sum(totals['by_study'].values()) == n and sum(totals['by_outcome'].values()) == n
    out = {
        'source': {'dataset': 'FireGap tests.csv (NASA PSI)', 'rows': n, 'built_from': ['tests.csv', 'studies.json', 'data/facts_all.csv']},
        'fields': FIELDS,
        'studies': study_names, 'materials': materials, 'gravities': gravities,
        'material_kind': {m: next((k for fid, lab, k, *_ in A.simulator.FAMILIES if lab == m), 'unknown') for m in materials},
        'families': [{'id': i, 'label': lab} for i, lab in A.FAMILIES],
        'outcomes': [{'id': i, 'label': lab} for i, lab in A.OUTCOMES],
        'quality': [{'id': i, 'label': lab} for i, lab, _ in A.QUALITY],
        'references': references(facts),
        'ventilation': ventilation(facts),
        'totals': totals,
        'records': records,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
    OUT.write_text(text, encoding='utf-8')
    print(f'{OUT.relative_to(ROOT)}: {n} records, {len(text.encode()) / 1024:.0f} KB')
    print('quality categories:')
    for q, label, _ in A.QUALITY:
        print(f'  {q:13s} {totals["by_flag"][q]:5d}  {label}')
    print('outcomes:', totals['by_outcome'], ' gravity:', totals['by_gravity'])


if __name__ == '__main__':
    main()
