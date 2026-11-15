"""Simulator support: material families, NASA test coverage and the closest real test.

Every number the simulator shows must come from a real FireGap test. This module
groups the dataset's free-text material names into families, reports which
O2 / pressure / flow / thickness ranges were actually tested for each family,
and finds the closest test to a slider setting. If no test is close enough the
API says so explicitly instead of inventing a value.
"""
import math
import re

# Tolerances: a test "covers" a setting when it is within these distances.
TOL_O2 = 1.0          # percentage points of O2
TOL_KPA = 5.0         # kPa
TOL_FLOW = 5.0        # cm/s
TOL_THICK = 1.5       # factor (x or / 1.5)

# (id, label, kind, soot level 0..1 for the illustrative animation, matcher)
# Labels follow one style: "Name (detail)", with a detail only where it adds information;
# the group heading (solid / droplet / gas / rig) says what kind of fuel it is.
# Soot levels are qualitative combustion chemistry (methanol burns soot-free,
# ethylene/heptane/wax are sooty); they only colour the illustration.
FAMILIES = [
    # Matching order matters: the first match wins ("material not stated; PMMA likely" is
    # not PMMA, and the BRE burner must be caught before "ethane" matches "methane").
    # Display order is set separately in materials().
    ('solid_unlabelled', 'Solid sample (material not stated)', 'solid', 0.45,
     lambda m, c, e: 'material not stated' in c or 'black rod' in m),
    # A test rig, not a material: a porous gas burner that emulates a burning solid surface.
    ('bre', 'Burning-rate emulator (gas burner: ethylene, methane)', 'rig', 0.6, lambda m, c, e: e == 'acme bre'),
    ('pmma', 'PMMA (acrylic)', 'solid', 0.45,
     lambda m, c, e: 'pmma' in m or 'pmma' in c or 'clear rod' in c or c.startswith('film')),
    ('sibal', 'SIBAL (cotton-fiberglass fabric)', 'solid', 0.5, lambda m, c, e: 'sibal' in m or 'sibal' in c),
    ('nomex', 'Nomex (aramid fabric)', 'solid', 0.2, lambda m, c, e: 'nomex' in c or m == 'nomex'),
    ('wax', 'Candle wax (paraffin, Japan wax)', 'solid', 0.75, lambda m, c, e: 'wax' in c or 'wax' in m or 'candle' in m),
    ('silicone', 'Silicone', 'solid', 0.15, lambda m, c, e: 'silicone' in m),
    ('ultem', 'Ultem (PEI)', 'solid', 0.3, lambda m, c, e: 'ultem' in c or 'ultem' in m),
    ('methanol', 'Methanol', 'droplet', 0.0, lambda m, c, e: m == 'methanol'),
    ('heptane', 'Heptane', 'droplet', 0.8, lambda m, c, e: m == 'heptane'),
    ('ethylene', 'Ethylene', 'gas', 0.85, lambda m, c, e: e == 'acme/flame design' and m.startswith('c2h4')),
    ('propane', 'Propane', 'gas', 0.6, lambda m, c, e: 'propane' in m or m.startswith('c3h8')),
    ('ethane', 'Ethane', 'gas', 0.45, lambda m, c, e: 'ethane' in m),
    ('butane', 'Butane', 'gas', 0.65, lambda m, c, e: 'butane' in m),
]
KIND_ORDER = ('solid', 'droplet', 'gas', 'rig')
FALLBACK = {'solid_unlabelled'}   # "unknown" options always go last in their group

EXTINGUISHED = re.compile(r'self-extinguish|no hot flame|momentary flash|no sustained', re.I)
BURNING = re.compile(r'burned|burning|steady|ignited flame|hot flame', re.I)


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def family_of(values):
    material = (values.get('material') or values.get('fuel') or '').strip().lower()
    cls = (values.get('material_class') or '').strip().lower()
    exp = (values.get('experiment') or '').strip().lower()
    for fid, _, _, _, match in FAMILIES:
        if match(material, cls, exp):
            return fid
    return None


def conditions(values):
    """Numeric test conditions; None where the dataset does not state them."""
    lo, hi = _num(values.get('o2_min_pct')), _num(values.get('o2_max_pct'))
    if lo is None:
        lo = hi
    if hi is None:
        hi = lo
    kpa, assumed = _num(values.get('pressure_kpa')), False
    if kpa is None:
        kpa, assumed = _num(values.get('pressure_kpa_assumed')), True
    return {'o2': None if lo is None else (min(lo, hi), max(lo, hi)),
            'kpa': kpa, 'kpa_assumed': assumed and kpa is not None,
            'flow': _num(values.get('flow_cm_s')), 'thickness': _num(values.get('thickness_mm'))}


def outcome(values):
    """'burned' | 'extinguished' | None (unknown) from the free-text outcome."""
    text = values.get('ug_outcome') or ''
    if EXTINGUISHED.search(text):
        return 'extinguished'
    if BURNING.search(text):
        return 'burned'
    return None


def _merge(intervals):
    out = []
    for lo, hi in sorted(intervals):
        if out and lo <= out[-1][1]:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return [[round(a, 2), round(b, 2)] for a, b in out]


def materials(rows):
    """Families present in the data with counts and tested ranges (tolerance included)."""
    result = []
    for fid, label, kind, soot, _ in FAMILIES:
        tests = [row for row in rows if family_of(row['values']) == fid]
        if not tests:
            continue
        cov = {'o2': [], 'pressure': [], 'flow': [], 'thickness': []}
        missing = {'o2': 0, 'pressure': 0, 'flow': 0, 'thickness': 0}
        for row in tests:
            c = conditions(row['values'])
            missing['o2'] += c['o2'] is None
            missing['pressure'] += c['kpa'] is None
            missing['flow'] += c['flow'] is None
            missing['thickness'] += not c['thickness']
            if c['o2']:
                cov['o2'].append((c['o2'][0] - TOL_O2, c['o2'][1] + TOL_O2))
            if c['kpa'] is not None:
                cov['pressure'].append((c['kpa'] - TOL_KPA, c['kpa'] + TOL_KPA))
            if c['flow'] is not None:
                cov['flow'].append((max(0.0, c['flow'] - TOL_FLOW), c['flow'] + TOL_FLOW))
            if c['thickness']:
                cov['thickness'].append((c['thickness'] / TOL_THICK, c['thickness'] * TOL_THICK))
        result.append({'id': fid, 'label': label, 'kind': kind, 'soot': soot, 'tests': len(tests),
                       'fallback': fid in FALLBACK,
                       'experiments': sorted({row['values'].get('experiment', '') for row in tests}),
                       'coverage': {k: _merge(v) for k, v in cov.items()},
                       # tests that do not state a condition: outside the bands it is "not recorded",
                       # not "untested"
                       'missing': missing})
    # Display order: by group, then the richest data sets first; "unknown" last in its group.
    result.sort(key=lambda m: (KIND_ORDER.index(m['kind']), m['fallback'], -m['tests'], m['label']))
    return result


def _gap_o2(o2, rng):
    return max(0.0, rng[0] - o2, o2 - rng[1])


def nearest(rows, family, o2, kpa, flow=None, thickness=None):
    """Closest real test of a family to the setting, and whether it is within tolerance.

    Distance is measured in tolerance units per stated condition; conditions the test
    does not state (often flow and thickness) are reported as 'not recorded', not guessed.
    Tests without a stated O2 or pressure are skipped: they cannot confirm a setting.
    """
    best, best_score, n_within = None, None, 0
    for row in rows:
        values = row['values']
        if family_of(values) != family:
            continue
        c = conditions(values)
        if not c['o2'] or c['kpa'] is None:
            continue
        gaps = {'o2': _gap_o2(o2, c['o2']), 'pressure': abs(kpa - c['kpa'])}
        if flow is not None and c['flow'] is not None:
            gaps['flow'] = abs(flow - c['flow'])
        if thickness and c['thickness']:
            gaps['thickness'] = max(thickness, c['thickness']) / min(thickness, c['thickness'])
        units = [gaps['o2'] / TOL_O2, gaps['pressure'] / TOL_KPA]
        if 'flow' in gaps:
            units.append(gaps['flow'] / TOL_FLOW)
        if 'thickness' in gaps:
            units.append(math.log(gaps['thickness']) / math.log(TOL_THICK))
        within = all(u <= 1.0 + 1e-9 for u in units)
        n_within += within
        # Prefer tests inside tolerance; among those, ones with a structured result (outcome,
        # spread rate, burn time), then ones with crew observations only; then distance.
        structured = bool(outcome(values) or _num(values.get('ug_spread_rate_mm_s')) is not None
                          or _num(values.get('burn_time_s')) is not None)
        rank = 0 if structured else 1 if (values.get('observations_raw') or '').strip() else 2
        dist = math.hypot(*units)
        score = (0, rank, dist) if within else (1, dist, rank)
        if best_score is None or score < best_score:
            best, best_score = (row, c, gaps, within), score
    if best is None:
        return {'within': False, 'n_within': 0, 'test': None}
    row, c, gaps, within = best
    v = row['values']
    return {
        'within': within, 'n_within': n_within,
        'gaps': {k: round(val, 2) for k, val in gaps.items()},
        'test': {
            'id': row['id'], 'experiment': v.get('experiment', ''), 'test_id': v.get('test_id', ''),
            'material': v.get('material') or v.get('fuel', ''),
            'o2': list(c['o2']), 'pressure_kpa': c['kpa'], 'pressure_assumed': c['kpa_assumed'],
            'flow_cm_s': c['flow'], 'thickness_mm': c['thickness'],
            'outcome_text': v.get('ug_outcome', ''), 'outcome': outcome(v),
            'spread_rate_mm_s': _num(v.get('ug_spread_rate_mm_s')),
            'burn_time_s': _num(v.get('burn_time_s')),
            'observations': (v.get('observations_raw') or '').strip(),
            'data_quality_note': v.get('data_quality_note', ''),
        },
    }
