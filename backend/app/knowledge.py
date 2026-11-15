"""What NASA knows: data for assistant/engine.js, environments (gravity) and sourced facts.

engine_data() mirrors scripts/build_assistant.py from the FireGap archive so the browser can
call assess(DATA, o2, p) from assistant/engine.js unchanged. Facts come from
data/facts_all.csv with English translations from backend/data/facts_en.json.
"""
import csv
import json
import math
import re
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
DATASET = DATA_DIR / 'firegap_dataset' / 'firegap_dataset'
ENGINE_JS = DATASET / 'assistant' / 'engine.js'
FACTS_CSV = DATASET / 'data' / 'facts_all.csv'
FACTS_EN = DATA_DIR / 'facts_en.json'
ENVIRONMENTS = DATA_DIR / 'environments.json'

FLAG_RE = re.compile(r'unreadable|appears 2x|typo|implausible|disagrees|spreadsheet error|not captured|approximate|copy error')
SOURCE_TYPE_EN = {
    'руководство NASA': 'NASA guide', 'стандарт': 'NASA standard', 'статья': 'paper', 'доклад NASA': 'NASA conference paper',
    'отчёт NASA': 'NASA report', 'обзор NASA': 'NASA review', 'презентация NASA': 'NASA presentation',
    'статья + пресс-релиз': 'paper + press release', 'страница JAXA': 'JAXA web page', 'новость ZARM': 'ZARM news',
    'презентация/статья': 'presentation / paper', 'отчёт NASA / SAE': 'NASA report / SAE paper',
}
TITLE_EN = [('9 февраля 1998', '9 February 1998'), ('загруженный файл, 70 стр.', '70 pp.'), ('слайдах', 'slides'), ('слайды', 'slides'),
            ('цитируется в', 'cited in'), (' и в ', ' and in '), (' и ', ' and ')]


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _family(v):
    e = v.get('experiment', '')
    if e in ('BASS', 'BASS-II'):
        return 'solid'
    if e == 'FLEX':
        return 'droplet'
    if e == 'ACME BRE':
        return 'burner'
    if e in ('ACME CFI-G', 'ACME/Flame Design') and v.get('config') == 'normal':
        return 'gas'
    return None


def _outcome(v):
    s, e = v.get('ug_outcome', ''), v.get('experiment', '')
    if e == 'ACME CFI-G':
        return {'hot flame; self-extinguished': 'ext', 'hot flame; ended by flow termination/timer': 'sust',
                'no hot flame ignited': 'none', 'momentary flash only': 'none'}.get(s)
    if e == 'ACME BRE':
        if s == 'self-extinguished':
            return 'ext'
        if s.startswith('burning'):
            return 'sust'
    return None


def engine_data(rows, studies):
    """DATA object for engine.js: {tests: [...], studies: {...}} (same fields as build_assistant.py)."""
    tests = []
    for row in rows:
        v = row['values']
        fam = _family(v)
        if not fam:
            continue
        p, assumed = _num(v.get('pressure_kpa')), False
        if p is None:
            p, assumed = _num(v.get('pressure_kpa_assumed')), True
        o2 = _num(v.get('o2_min_pct'))
        if o2 is None or p is None:
            continue
        obs = ' '.join((v.get('observations_raw') or '').split())[:140] or None
        note = v.get('data_quality_note') or ''
        flagged = bool(FLAG_RE.search(note))
        tests.append({
            'id': v.get('test_id', ''), 'psi': v.get('psi_id', ''), 'exp': v.get('experiment', ''), 'fam': fam,
            'mat': v.get('material', ''), 'o2': o2, 'p': p, 'pa': assumed, 'oc': _outcome(v),
            'burn': _num(v.get('burn_time_s')), 'ext': _num(v.get('extinction_d_mm')), 'obs': obs,
            'fuel': v.get('fuel') or None, 'burner': _num(v.get('burner_mm')), 'flux': _num(v.get('mass_flux_g_m2s')),
            'gravity': v.get('gravity_regime', ''), 'flag': flagged, 'note': note[:200] if flagged else '',
        })
    meta = {s['psi_id']: {'acr': s.get('acronym'), 'title': s.get('title'), 'doi': s.get('psi_doi'),
                          'platform': s.get('platform')} for s in studies}
    return {'tests': tests, 'studies': meta}


@lru_cache(maxsize=1)
def environments():
    return json.loads(ENVIRONMENTS.read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def _facts():
    en = json.loads(FACTS_EN.read_text(encoding='utf-8'))
    rows = {r['id']: r for r in csv.DictReader(FACTS_CSV.open(encoding='utf-8-sig'))}
    return en, rows


def _title(text):
    for ru, eng in TITLE_EN:
        text = text.replace(ru, eng)
    return text


def fact(fid):
    en, rows = _facts()
    row, tr = rows[fid], en['facts'][fid]
    return {
        'id': fid, 'fact': tr['fact'], 'caveat': tr.get('caveat', ''), 'where': tr.get('where', ''),
        'source_type': SOURCE_TYPE_EN.get(row['source_type'], row['source_type']),
        'source_title': _title(row['source_title']), 'url': row['url'] or None,
        'verified': en['verified'].get(row['verified'], row['verified']),
        'verified_raw': row['verified'], 'excerpt_only': row['verified'] == 'аннотация/выдержка',
        'translated_from': 'facts_all.csv (Russian original, column fact_ru)',
    }


def facts_for(env):
    en, _ = _facts()
    return [fact(fid) for fid in en['show'].get(env, [])]


def flow_sources():
    en, _ = _facts()
    return [fact(fid) for fid in en['flow_sources']]
