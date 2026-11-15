"""Analytics: one derivation of every test record, shared by the build script
(scripts/build_analytics.py -> frontend/assets/analytics.json) and the filtered CSV export,
so the dashboard and the download always count the same rows.

Describes the dataset (what was tested, where the gaps are). No risk score, no prediction.
"""
import math
import re

from . import simulator

# Investigation families (as in the FireGap gap map); Saffire kept on its own.
FAMILY_OF_STUDY = {
    'BASS': 'solid', 'BASS-II': 'solid',
    'FLEX': 'droplet',
    'ACME CFI-G': 'gas', 'ACME/Flame Design': 'gas',
    'ACME BRE': 'bre',
    'SAFFIRE-I': 'saffire', 'SAFFIRE-II': 'saffire', 'SAFFIRE-III': 'saffire',
}
FAMILIES = [('solid', 'Solid samples (BASS, BASS-II)'), ('droplet', 'Fuel droplets (FLEX)'),
            ('gas', 'Gas flames (ACME CFI-G, Flame Design)'), ('bre', 'Burning-rate emulator (ACME BRE)'),
            ('saffire', 'Saffire (large-scale, uncrewed Cygnus)')]

# Outcome of the test as stated in ug_outcome. Only explicit end states count:
# "listed as ignited" / "ignition not confirmed" say nothing about how the flame ended.
OUTCOMES = [('out', 'Went out'), ('burning', 'Kept burning'), ('none', 'Not recorded')]
_OUT = re.compile(r'self-extinguish|no hot flame|momentary flash|no sustained', re.I)
_BURN = re.compile(r'^burned$|burning when fuel flow|ended by flow termination|^burning', re.I)

# Data-quality categories, derived from the wording of data_quality_note (plus the
# pressure_kpa_assumed column). A record can have several.
QUALITY = [
    ('units', 'Units unclear or not converted',
     re.compile(r'unit unclear|not converted|unit error|given in cm|dial values', re.I)),
    ('verify', "Marked 'verify' or possible transcription error",
     re.compile(r'verify|check the original|copy error|typo|swapped', re.I)),
    ('filled', 'Empty field filled from the previous row', re.compile(r'filled from previous row', re.I)),
    ('p_assumed', 'Pressure assumed (not measured per test)', re.compile(r'pressure not per-test', re.I)),
    ('p_missing', 'Pressure not stated', re.compile(r'pressure not stated|ambient pressure is 0 or missing', re.I)),
    ('o2_missing', 'O₂ not stated (incl. inverse flames)', re.compile(r'no ambient o2|o2 not stated', re.I)),
    ('outcome', 'No structured outcome column',
     re.compile(r'no explicit outcome|no extinction/soot outcome|outcome \(ignited/spread/extinguished\) only in free-text|outcome[^;]*not stated', re.I)),
    ('pdf', 'Read from PDF text / unreadable in source',
     re.compile(r'read from pdf|unreadable|text extraction', re.I)),
    ('invalid', 'Invalid or non-numeric value in source',
     re.compile(r'spreadsheet error|implausible|not numeric|#div/0|treated as missing|zero fuel flow', re.I)),
    ('not_recorded', 'Field left blank in source (not recorded)', re.compile(r'blank = not recorded|not recorded for this day|blank in source', re.I)),
    ('date', 'Date parsed from text or suspect', re.compile(r'date was text|outside the 20\d\d campaign', re.I)),
]
QUALITY_IDS = [q[0] for q in QUALITY]


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _material_labels():
    return {fid: label for fid, label, *_ in simulator.FAMILIES}


MATERIAL_LABEL = _material_labels()
NOT_STATED = 'Material not stated'


def quality_flags(values):
    note = values.get('data_quality_note') or ''
    flags = [qid for qid, _, rx in QUALITY if rx.search(note)]
    if (values.get('pressure_kpa_assumed') or '').strip() and 'p_assumed' not in flags:
        flags.append('p_assumed')
    flags.sort(key=QUALITY_IDS.index)
    return flags


def outcome_of(values):
    text = (values.get('ug_outcome') or '').strip()
    if not text:
        return 'none'
    if _OUT.search(text):
        return 'out'
    if _BURN.search(text):
        return 'burning'
    return 'none'


def gravity_of(values, platform):
    """gravity_regime column if present; else from the study platform (ISS / free-flying
    Cygnus = microgravity); empty stays empty."""
    g = (values.get('gravity_regime') or '').strip()
    if g:
        return g
    p = (platform or '').lower()
    if 'iss' in p or 'international space station' in p or 'cygnus' in p:
        return 'microgravity'
    return ''


def derive(values, platforms=None):
    study = (values.get('experiment') or '').strip()
    o2 = _num(values.get('o2_min_pct'))
    if o2 is None:
        o2 = _num(values.get('o2_max_pct'))
    kpa, assumed = _num(values.get('pressure_kpa')), False
    if kpa is None:
        kpa = _num(values.get('pressure_kpa_assumed'))
        assumed = kpa is not None
    fam = simulator.family_of(values)
    return {
        'study': study,
        'family': FAMILY_OF_STUDY.get(study, 'other'),
        'material': MATERIAL_LABEL.get(fam, NOT_STATED) if fam != 'solid_unlabelled' else NOT_STATED,
        'o2': o2, 'kpa': kpa, 'kpa_assumed': assumed,
        'flow': _num(values.get('flow_cm_s')), 'thick': _num(values.get('thickness_mm')),
        'outcome': outcome_of(values), 'flags': quality_flags(values),
        'gravity': gravity_of(values, (platforms or {}).get(study)),
    }


def matches(d, f):
    """Dashboard filter semantics (shared with the browser):
    study/family/material: lists (empty = all); o2/kpa: [lo, hi] inclusive, hi may be exclusive
    when 'o2_open'/'kpa_open' is true (grid cells). An active range excludes records without a value."""
    for key in ('study', 'family', 'material'):
        allowed = f.get(key) or []
        if allowed and d[key] not in allowed:
            return False
    for key in ('o2', 'kpa'):
        rng = f.get(key)
        if rng:
            v = d[key]
            if v is None:
                return False
            lo, hi = rng
            if v < lo or (v >= hi if f.get(key + '_open') else v > hi):
                return False
    return True


def validate_filter(f):
    if not isinstance(f, dict):
        raise ValueError('filter must be an object')
    out = {}
    for key in ('study', 'family', 'material'):
        v = f.get(key, [])
        if not isinstance(v, list) or any(not isinstance(x, str) or len(x) > 120 for x in v) or len(v) > 50:
            raise ValueError(f'{key} must be a list of strings')
        out[key] = v
    for key in ('o2', 'kpa'):
        v = f.get(key)
        if v is not None:
            if not (isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) and math.isfinite(x) for x in v)):
                raise ValueError(f'{key} must be [lo, hi]')
            out[key] = [float(v[0]), float(v[1])]
        out[key + '_open'] = bool(f.get(key + '_open', False))
    return out
