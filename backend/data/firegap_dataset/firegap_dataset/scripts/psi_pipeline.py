"""Merge PSI investigations (ISA-Tab metadata + experimental table) into one dataset.

Usage:
  python3 -I psi_pipeline.py <out_dir> <adapter>:<i_Investigation.txt>:<table.csv> [...]
Adapters: saffire1, saffire2
Outputs: studies.json, tests.csv, skipped_rows.json
"""
import csv
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- ISA-Tab

def parse_isa(path):
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t"):
            if not row or not row[0].strip():
                continue
            key, vals = row[0].strip(), [v.strip() for v in row[1:]]
            if key not in out or (not any(out[key]) and any(vals)):
                out[key] = vals
    return out


def study_from_isa(path):
    isa = parse_isa(path)
    first = lambda k: (isa.get(k) or [""])[0]
    titles = isa.get("Study Publication Title", [])
    pubs = []
    for i in range(len(titles)):
        col = lambda k: (isa.get(k, []) + [""] * 50)[i]
        if col("Study Publication Title"):
            pubs.append({"title": col("Study Publication Title"),
                         "authors": col("Study Publication Author List"),
                         "doi": col("Study Publication DOI"),
                         "link": col("Comment[Study Publication Link]")})
    s = {
        "psi_id": first("Study Identifier"),
        "title": first("Study Title"),
        "acronym": first("Comment[Investigation Acronym]"),
        "psi_doi": first("Comment[DOI]"),
        "sub_area": first("Comment[SubResearch Area]"),
        "platform": first("Comment[Flight Platform]"),
        "hardware": first("Comment[Experiment Hardware]"),
        "objective": " ".join(first("Comment[Objective]").strip('"').split()),
        "hypothesis": first("Comment[Hypothesis]"),
        "approach": first("Comment[Approach]"),
        "research_impact": first("Comment[Research Impacts]"),
        "tags": [t for t in isa.get("Study Design Type", []) if t],
        "start_date": first("Comment[Investigation Start Date]"),
        "end_date": first("Comment[Investigation End Date]"),
        "proposal_title": first("Comment[Proposal Title]"),
        "publications": pubs,
        "quality_flags": [],
    }
    if "smoke" in s["proposal_title"].lower() and "SAFFIRE" in s["acronym"]:
        s["quality_flags"].append("Proposal Title is about smoke detection; looks copied from another experiment")
    if s["acronym"] == "SAFFIRE-I" and s["start_date"].endswith("2001"):
        s["quality_flags"].append(f"Dates {s['start_date']}..{s['end_date']} look wrong for Saffire-I")
    return s

# ---------------------------------------------------------------- helpers

NUM = r"\d*\.?\d+"

def nums(text):
    return [float(x) for x in re.findall(NUM, text or "")]


def value_unit(text, default_unit=None):
    """'0.27 mm' -> (0.27, 'mm'); 'See Fig. 5' -> (None, None)."""
    t = (text or "").strip()
    m = re.fullmatch(rf"~?\s*({NUM})\s*([a-zA-Z/]+)?", t)
    if not m:
        return None, None
    return float(m.group(1)), (m.group(2) or default_unit)


def to_mm(v, unit):
    if v is None:
        return None
    return {"mm": v, "cm": v * 10, "m": v * 1000}.get(unit)


def o2_range(text):
    n = nums(text)
    return (min(n), max(n), "~" in (text or "")) if n else (None, None, False)


def base_row(study, test_id):
    return {
        "psi_id": study["psi_id"], "experiment": study["acronym"], "test_id": test_id,
        "material": None, "material_filled_forward": False,
        "o2_min_pct": None, "o2_max_pct": None, "o2_approx": False, "o2_note": None,
        "pressure_kpa": None, "flow_cm_s": None, "flow_direction": None,
        "thickness_mm": None, "thickness_raw": None, "length_cm": None, "width_cm": None,
        "ignition_power_w": None, "ignition_time_s": None,
        "burn_time_s": None, "burn_time_raw": None,
        "ug_burn_length_raw": None, "ug_spread_rate_mm_s": None, "ug_spread_raw": None,
        "g1_burn_length_raw": None, "g1_spread_raw": None,
        "ug_outcome": None,
        "fuel": None, "n2_frac": None, "co2_frac_assumed": None, "he_frac": None,
        "droplet_d0_mm": None, "extinction_d_mm": None, "burn_rate_raw_unit_mm": None,
        "test_end": None, "test_date": None, "test_gmt": None,
        "pi": None, "material_class": None, "geometry": None, "pressure_kpa_assumed": None,
        "o2_final_pct": None, "co2_initial_pct": None, "co2_final_pct": None,
        "co_initial_ppm": None, "co_final_ppm": None,
        "fan_display_raw": None, "air_display_raw": None, "frames_shot_raw": None,
        "video_refs": None, "observations_raw": None,
        "config": None, "fuel_frac_burner": None, "fuel_frac_ambient": None, "fluent_o2_frac": None,
        "cool_flame_obs": None, "peak_burner_t_c": None, "adiabatic_flame_t_k": None,
        "fuel_dhc_kj_g": None, "mass_flux_g_m2s": None, "burner_mm": None, "data_quality_note": "",
    }

# ---------------------------------------------------------------- adapters

def read_table(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    header = [h.strip() for h in rows[0]]
    return header, [[c.strip() for c in r] + [""] * (len(header) - len(r)) for r in rows[1:] if any(c.strip() for c in r)]


def adapt_saffire1(study, path):
    header, rows = read_table(path)
    tests, skipped = [], []
    for r in rows:
        d = dict(zip(header, r))
        sid = d.get("Sample Number", "")
        if not nums(d.get("Air Flow (cm/s)")):
            skipped.append({"experiment": study["acronym"], "row": sid, "reason": d.get("Material")})
            continue
        t = base_row(study, sid)
        lo, hi, ap = o2_range(d.get("Percent O2"))
        t.update({
            "material": d["Material"], "o2_min_pct": lo, "o2_max_pct": hi, "o2_approx": ap,
            "flow_cm_s": nums(d["Air Flow (cm/s)"])[0], "flow_direction": d["Flow Direction"],
            "thickness_raw": d["Sample Thickness (cm)"] + " cm",
            "thickness_mm": to_mm(*value_unit(d["Sample Thickness (cm)"], "cm")),
            "length_cm": nums(d["Sample Length (cm)"])[0], "width_cm": nums(d["Sample Width (cm)"])[0],
            "ignition_power_w": nums(d["Ignition Power (W)"])[0], "ignition_time_s": nums(d["Ignition Time (s)"])[0],
            "burn_time_s": nums(d["Burn Time (s)"])[0], "burn_time_raw": d["Burn Time (s)"],
            "video_refs": ";".join(x for x in (d["Camera 1"], d["Camera 2"]) if x),
            "data_quality_note": "pressure not stated; outcome/spread rate not stated; "
                                 "length/width columns swapped vs metadata and Saffire-III table (94 cm long x 40.6 cm wide); "
                                 "thickness 0.37 cm is 10x Saffire-II SIBAL (0.37 mm) - possible unit error",
        })
        tests.append(t)
    return tests, skipped


def adapt_saffire2(study, path):
    header, rows = read_table(path)
    # headers have typos and '?' where a mu (micro-g) was lost in encoding
    H = {"id": 0, "mat": 1, "thk": 2, "len": 3, "wid": 4, "flow": 5, "o2": 6, "ipow": 7, "itime": 8,
         "burn": 9, "dir": 10, "ug_len": 11, "ug_spread": 12, "g1_len": 13, "g1_spread": 14, "c1": 15, "c2": 16}
    notes = {}
    tests, skipped, last_mat = [], [], None
    for r in rows:
        sid = r[H["id"]]
        m = re.match(r"Note\s*(\d+)\s*(.*)", sid)
        if m:
            notes[m.group(1)] = m.group(2).strip()
            continue
        if not nums(r[H["flow"]]):
            skipped.append({"experiment": study["acronym"], "row": sid, "reason": r[H["mat"]]})
            continue
        t = base_row(study, sid)
        q = []
        mat = r[H["mat"]]
        if not mat:
            mat, t["material_filled_forward"] = last_mat, True
            q.append(f"material blank in source; filled from previous row ({last_mat}) - verify")
        last_mat = mat
        # thickness: '037 mm' is almost certainly 0.37 mm
        thk_raw = r[H["thk"]]
        t["thickness_raw"] = thk_raw
        if re.fullmatch(r"0\d+\s*mm", thk_raw):
            v = float("0." + re.match(r"0(\d+)", thk_raw).group(1))
            t["thickness_mm"] = v
            q.append(f"thickness '{thk_raw}' read as {v} mm (missing decimal point)")
        else:
            t["thickness_mm"] = to_mm(*value_unit(thk_raw))
            if t["thickness_mm"] is None:
                q.append(f"thickness not numeric: '{thk_raw}'")
        lo, hi, ap = o2_range(r[H["o2"]])
        burn_raw = r[H["burn"]]
        burn = value_unit(burn_raw)[0]
        ug_len = r[H["ug_len"]]
        ug_spread = r[H["ug_spread"]]
        # outcome in microgravity, derived only from what the table states
        if burn_raw.lower().startswith("insignificant") and ug_len.startswith("~ 0"):
            outcome = "no sustained burning"
        elif burn is not None:
            outcome = "burned"
        else:
            outcome = None
        for k in re.findall(r"note\s*(\d)", " ".join(r), re.I):
            pass
        t.update({
            "material": mat, "o2_min_pct": lo, "o2_max_pct": hi, "o2_approx": ap,
            "o2_note": "derived from measured CO2 production, referenced to ISS initial O2 (table Note 1)",
            "flow_cm_s": nums(r[H["flow"]])[0], "flow_direction": r[H["dir"]],
            "length_cm": value_unit(r[H["len"]])[0], "width_cm": value_unit(r[H["wid"]])[0],
            "ignition_power_w": nums(r[H["ipow"]])[0], "ignition_time_s": nums(r[H["itime"]])[0],
            "burn_time_s": burn, "burn_time_raw": burn_raw,
            "ug_burn_length_raw": ug_len, "ug_spread_raw": ug_spread,
            "ug_spread_rate_mm_s": value_unit(ug_spread)[0] if "mm/s" in ug_spread else None,
            "g1_burn_length_raw": r[H["g1_len"]], "g1_spread_raw": r[H["g1_spread"]],
            "ug_outcome": outcome,
            "video_refs": ";".join(x for x in (r[H["c1"]], r[H["c2"]]) if x and x != "n/a"),
        })
        if r[H["len"]] != "29 cm":
            q.append(f"composite sample, lengths '{r[H['len']]}', thickness '{thk_raw}'")
        t["_note_refs"] = sorted(set(re.findall(r"note\s*(\d)", " ".join(r[1:]), re.I)))
        if r[H["c1"]] == r[H["c2"]] and r[H["c1"]]:
            q.append("Camera 1 and Camera 2 refs identical in source")
        if "S56" in r[H["c2"]]:
            q.append(f"camera ref '{r[H['c2']]}' looks like a typo")
        q.append("pressure not stated")
        t["data_quality_note"] = "; ".join(q)
        tests.append(t)
    for t in tests:
        refs = t.pop("_note_refs")
        if refs:
            t["data_quality_note"] += "; " + "; ".join(f"Note {n}: {notes.get(n, '?')}" for n in refs)
    return tests, skipped


def adapt_saffire3(study, path):
    header, rows = read_table(path)
    tests, skipped = [], []
    for r in rows:
        d = dict(zip(header, r))
        sid = d.get("Sample Number", "")
        if not nums(d.get("Air Flow")):
            skipped.append({"experiment": study["acronym"], "row": sid, "reason": d.get("Material")})
            continue
        t = base_row(study, sid)
        thk = d["Sample Thickness"]
        t.update({
            "material": d["Material"],
            "flow_cm_s": value_unit(d["Air Flow"])[0], "flow_direction": d["Direction"].strip(),
            "thickness_raw": thk, "thickness_mm": to_mm(*value_unit(thk)),
            "length_cm": value_unit(d["Sample Length"])[0], "width_cm": value_unit(d["Sample Width"])[0],
            "video_refs": ";".join(x for x in (d["Camera 1"], d["Camera 2"]) if x),
            "data_quality_note": "O2 not stated in table; pressure not stated; burn time and outcome not stated; "
                                 "metadata points to an 'Experimental Details' file in Science Documents; "
                                 "thickness given in cm (0.33 cm) like Saffire-I, vs 0.37 mm for SIBAL in Saffire-II - unit unclear",
        })
        tests.append(t)
    return tests, skipped


def adapt_flex(study, path):
    from collections import Counter
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = list(csv.reader(f))
    header = [h.strip() for h in rows[0]]
    body = [r for r in rows[1:] if any(c.strip() for c in r)]
    ids = Counter(r[1].strip() for r in body)
    stamps = Counter((r[2].strip(), r[3].strip()) for r in body if r[3].strip())

    def fnum(x):
        x = (x or "").strip()
        if not x or "\ufffd" in x:   # unreadable character in source
            return None, "unreadable" if x else "empty"
        approx = x.startswith("~")
        v = re.sub(r"[^0-9.]", "", x)
        try:
            return float(v), ("approx" if approx else "ok")
        except ValueError:
            return None, "unreadable"

    def fdate(x):
        m = re.fullmatch(r"(\d+)/(\d+)/(\d+)", (x or "").strip())
        if not m:
            return None
        mo, d, y = map(int, m.groups())
        y += 2000 if y < 100 else 0
        return f"{y:04d}-{mo:02d}-{d:02d}"

    tests = []
    for r in body:
        r = [c.strip() for c in r] + [""] * (len(header) - len(r))
        t = base_row(study, r[1])
        notes = []
        mm, st = fnum(r[5])
        kpa = None
        if mm is None or mm == 0:
            notes.append("ambient pressure is 0 or missing in source - treated as missing")
        else:
            kpa = round(mm * 0.133322, 2)
        o2, _ = fnum(r[6]); n2, _ = fnum(r[7]); co2, _ = fnum(r[8]); he, _ = fnum(r[9])
        d0, s0 = fnum(r[10]); de, se = fnum(r[11]); br, _ = fnum(r[12]); bt, sb = fnum(r[13])
        if s0 == "unreadable": notes.append("initial droplet diameter unreadable in source")
        if se == "unreadable": notes.append("extinction diameter unreadable in source")
        if sb == "approx": notes.append("burn time given as approximate (~)")
        if ids[r[1]] > 1: notes.append(f"test identifier {r[1]} appears {ids[r[1]]}x in source")
        if r[3] and stamps[(r[2], r[3])] > 1: notes.append("same date+time as another test (possible copy error)")
        notes.append("column header says 'CO'; treated as CO2 (metadata lists CO2, He, SF6 as FLEX suppressants) - verify")
        notes.append("burning-rate header says 'mm' - unit unclear (likely mm^2/s)")
        t.update({
            "test_id": r[1], "material": r[4], "fuel": r[4],
            "o2_min_pct": None if o2 is None else round(o2 * 100, 1),
            "o2_max_pct": None if o2 is None else round(o2 * 100, 1),
            "pressure_kpa": kpa,
            "n2_frac": n2, "co2_frac_assumed": co2, "he_frac": he,
            "droplet_d0_mm": d0, "extinction_d_mm": de, "burn_rate_raw_unit_mm": br,
            "burn_time_s": bt, "burn_time_raw": r[13] or None,
            "test_end": r[14], "test_date": fdate(r[2]), "test_gmt": r[3] or None,
            "data_quality_note": "; ".join(notes),
        })
        tests.append(t)
    return tests, []


def adapt_flex2_envelope(study, path):
    """FLEX-2 table is a planned test MATRIX (ranges / level lists), not measured tests."""
    header, rows = read_table(path)
    envs = []
    for r in rows:
        d = dict(zip(header, r))
        fuel = d.get("Sample (Fuel Type)", "")
        if not fuel:
            continue
        dia = nums(d.get("Initial Droplet Diameter (mm)"))
        o2 = nums(d.get("Oxygen Mole Fraction"))
        pa = nums(d.get("Ambient Pressure (atm)"))
        fl = nums(d.get("Flow Velocity (cm/s)"))
        mix = re.search(r"\(([^)]*)\)\s*$", fuel)
        envs.append({
            "psi_id": study["psi_id"], "experiment": study["acronym"], "fuel": fuel,
            "fuel_kind": mix.group(1) if mix else None,
            "droplet_d_mm_min": min(dia) if dia else None, "droplet_d_mm_max": max(dia) if dia else None,
            "ambient_gas": d.get("Ambient Gas Mixture"),
            "o2_levels_pct": ";".join(f"{x*100:g}" for x in o2),
            "o2_min_pct": min(o2) * 100 if o2 else None, "o2_max_pct": max(o2) * 100 if o2 else None,
            "pressure_levels_kpa": ";".join(f"{x*101.325:.1f}" for x in pa),
            "p_min_kpa": round(min(pa) * 101.325, 1) if pa else None,
            "p_max_kpa": round(max(pa) * 101.325, 1) if pa else None,
            "temp_c": nums(d.get("Ambient Temperature (C)"))[0] if nums(d.get("Ambient Temperature (C)")) else None,
            "flow_cm_s_min": min(fl) if fl else None, "flow_cm_s_max": max(fl) if fl else None,
            "kind": "planned test matrix, NOT measured results",
            "note": "metadata Approach says O2 0.1-0.4 mole fraction and 0.5-3.0 atm; table lists narrower O2 levels",
        })
    study["planned_envelopes"] = envs
    return [], []


INCH = {"1/4": 6.35, "3/8": 9.525, "1/2": 12.7, "0.5": 12.7}

def adapt_bass2(study, path):
    import datetime as dt
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = list(csv.reader(f))
    tests = []
    for r in rows[1:]:
        r = [c.strip() for c in r] + [""] * (17 - len(r))
        if not r[1]:
            continue
        pi, tid, date, doy, samp, mat_raw = r[0], r[1], r[2], r[3], r[4], re.sub(r"\s+", " ", r[5])
        t = base_row(study, tid)
        notes = []
        low = mat_raw.lower()
        thk = wid = dia = None
        m = re.search(r"(\d*\.?\d+)\s*(micron|mm)\b", low)
        if m:
            thk = float(m.group(1)) / (1000 if m.group(2) == "micron" else 1)   # -> mm
        m = re.search(r"(\d*\.?\d+)\s*cm", low)
        if m and "spherical" not in low:
            wid = float(m.group(1))
        # material / geometry class (only what the table supports)
        if "pmma" in low and "rod" not in low and "nomex" not in low:
            cls, geom = "PMMA (stated)", ("slab/thick sheet" if (thk or 0) >= 1 else "thin film")
            if "slab" in low: geom = "slab"
        elif "nomex" in low:
            cls, geom = "Nomex", "fabric"
        elif "sibal" in low:
            cls, geom = "SIBAL (cotton/fiberglass)", "fabric strip"
        elif "candle" in low:
            cls, geom = "wax candle", "candle"
        elif "spherical" in low:
            cls, geom = "spherical section (material not stated)", "sphere section"
        elif "rod" in low:
            m2 = re.search(r"(1/4|3/8|1/2|0\.5)", low)
            dia = INCH.get(m2.group(1)) if m2 else None
            geom = "rod"
            if "black" in low or "blac " in low:
                cls = "black rod (material not stated)"
            elif "pmma" in low:
                cls = "PMMA (stated)"
            else:
                cls = "clear rod (PMMA presumed, not stated)"
            thk = dia
        elif "film" in low or "micron" in low:
            cls, geom = "film (PMMA presumed, not stated)", "thin film"
        else:
            cls, geom = "unknown", None
        o2i, _ = (lambda x: (float(x), 1) if re.fullmatch(r"\d+(\.\d+)?", x) else (None, 0))(r[11])
        o2f = None
        if re.fullmatch(r"\d+(\.\d+)?", r[12]):
            v = float(r[12])
            if 10 <= v <= 25:
                o2f = v
            else:
                notes.append(f"final O2 {v}% implausible - treated as missing")
        def fl(x, what):
            if re.fullmatch(r"-?\d+(\.\d+)?", x):
                return float(x)
            if x and x.lower() not in ("none",):
                notes.append(f"{what} '{x}' not numeric (over range / out of scale)")
            return None
        # date sanity
        mo = re.fullmatch(r"(\d+)/(\d+)/(\d+)", date)
        iso = None
        if mo:
            mm, dd, yy = map(int, mo.groups())
            iso = f"{yy:04d}-{mm:02d}-{dd:02d}"
            if yy == 2018:
                notes.append("year 2018 outside the 2014 campaign - likely typo for 2014")
        if doy.isdigit() and iso:
            real = dt.date.fromisoformat(iso).timetuple().tm_yday
            if real != int(doy):
                notes.append(f"'GMT' column ({doy}) is a day-of-year that disagrees with date")
        if o2i is None:
            notes.append("initial O2 missing")
        notes.append("table has no explicit outcome (burned/extinguished) column; flow settings are free text")
        notes.append("pressure not per-test; report: ISS cabin ~1 atm, 99.2-99.5 kPa in tests of one section")
        t.update({
            "pi": pi, "material": mat_raw, "material_class": cls, "geometry": geom,
            "o2_min_pct": o2i, "o2_max_pct": o2i, "o2_final_pct": o2f,
            "co2_initial_pct": fl(r[13], "initial CO2"), "co2_final_pct": fl(r[14], "final CO2"),
            "co_initial_ppm": fl(r[15], "initial CO"), "co_final_ppm": fl(r[16], "final CO"),
            "thickness_mm": thk, "thickness_raw": mat_raw, "width_cm": wid,
            "pressure_kpa_assumed": 101.3,
            "fan_display_raw": r[7], "air_display_raw": r[8], "frames_shot_raw": r[10],
            "test_date": iso, "test_gmt": doy, "video_refs": f"sample {samp}",
            "data_quality_note": "; ".join(notes),
        })
        tests.append(t)
    return tests, []



def adapt_bass(study, path):
    """BASS (PSI-26): as-run test matrix xlsx. O2 (mole fraction), pressure (atm), CO2 (mmHg) are
    measured cabin values logged per run; observations are free text. Instrument settings kept raw."""
    import datetime as dt
    import openpyxl, warnings
    warnings.filterwarnings("ignore")
    ws = openpyxl.load_workbook(path, data_only=True)["as run matrix"]
    rows = list(ws.iter_rows(values_only=True))
    tests, skipped, seen = [], [], {}
    for i, r in enumerate(rows[3:], start=4):
        r = list(r) + [None] * (30 - len(r))
        asrun, mat_raw = r[2], r[5]
        if not any(c is not None for c in r):
            continue
        def sk(why):
            skipped.append({"row": i, "reason": why, "text": [str(c)[:80] for c in r[:6] if c is not None]})
        if mat_raw is None or str(mat_raw).strip().upper() in ("-", "SETUP", "STOW"):
            sk("not a test (setup/stow/notes)"); continue
        if "soot" in str(mat_raw).lower() and "clean" in str(mat_raw).lower():
            sk("soot cleaning, not a test"); continue
        if not str(asrun).strip().isdigit():
            sk("no as-run test number"); continue
        tid = f"BASS-{int(str(asrun).strip())}"
        t = base_row(study, tid)
        notes = []
        if tid in seen:
            notes.append(f"duplicate as-run number {asrun} (also row {seen[tid]}); sample ids differ")
            tid = tid + "b"; t["test_id"] = tid
        seen[tid] = i
        # date
        d, raw = r[0], r[0]
        iso = None
        if isinstance(d, (dt.datetime, dt.date)):
            iso = d.date() if isinstance(d, dt.datetime) else d
            if iso.year > 2100:
                fy = int(str(iso.year)[0] + str(iso.year)[2] + str(iso.year)[1] + str(iso.year)[3]); notes.append(f"year typo {iso.year} -> {fy} (digits swapped; fits row order)"); iso = iso.replace(year=fy)
        else:
            m = re.search(r"(\d{1,2})/(\d{1,2})/\D*(\d{2,4})", str(d))
            if m:
                y = int(m.group(3)); y += 2000 if y < 100 else 0
                iso = dt.date(y, int(m.group(1)), int(m.group(2)))
                notes.append("date was text; parsed as m/d/y")
        low = re.sub(r"\s+", " ", str(mat_raw)).strip().lower()
        if "sibal" in low: cls, geom = "SIBAL (cotton/fiberglass)", "fabric strip"
        elif "nomex" in low: cls, geom = "Nomex", "fabric"
        elif "ultem" in low: cls, geom = "Ultem (PEI)", "sheet"
        elif "paraf" in low or "parrafin" in low: cls, geom = "paraffin wax", ("slab" if "slab" in low else "candle")
        elif "japan" in low or "candle" in low: cls, geom = "wax candle", "candle"
        elif "wax" in low: cls, geom = "wax", "slab"
        elif "pmma" in low: cls, geom = "PMMA (stated)", ("slab" if "slab" in low else "sphere")
        elif "sphere" in low: cls, geom = "spherical sample (material not stated; PMMA likely)", "sphere"
        else: cls, geom = "unknown", None
        if "sphere" in low: geom = "sphere"
        if "slab" in low and "wax" not in low: geom = "slab"
        flow_dir = "opposed" if "oppos" in low or "oppsed" in low else None
        # environment
        def fv(x):
            try: return float(x)
            except (TypeError, ValueError): return None
        o2 = fv(r[26]); p_atm = fv(r[27]); co2 = fv(r[28])
        if o2 is not None:
            o2 = round(o2 * 100, 2)
            if not 10 <= o2 <= 30: notes.append(f"O2 {o2}% implausible"); o2 = None
        else:
            notes.append("O2 not logged for this run")
        if r[27] is not None and p_atm is None: notes.append("pressure not numeric")
        if "vitiat" in str(r[29]).lower() or (o2 is not None and o2 < 19 and iso and iso.year == 2013):
            notes.append("2013 reduced-O2 (GN2 dilution / 'vitiation') condition")
        samp = re.sub(r"\s+", " ", str(r[4] or "")).strip()
        t.update({
            "pi": None, "material": str(mat_raw).strip(), "material_class": cls, "geometry": geom,
            "flow_direction": flow_dir,
            "o2_min_pct": o2, "o2_max_pct": o2,
            "pressure_kpa": round(p_atm * 101.325, 1) if p_atm else None,
            "co2_initial_pct": None,
            "fan_display_raw": str(r[9]) if r[9] is not None else None,
            "air_display_raw": str(r[10]) if r[10] is not None else None,
            "frames_shot_raw": str(r[25]) if r[25] is not None else None,
            "test_date": iso.isoformat() if iso else None,
            "test_gmt": str(r[1]).strip() if r[1] is not None else None,
            "video_refs": f"sample {samp}", "observations_raw": re.sub(r"\s+", " ", str(r[29] or "")).strip() or None,
        })
        if co2 is not None: notes.append(f"CO2 {co2} mmHg (not converted)")
        notes.append("outcome (ignited/spread/extinguished) only in free-text observations; flow settings are instrument dial values, not cm/s")
        t["data_quality_note"] = "; ".join(notes)
        tests.append(t)
    return tests, skipped



def adapt_cfig(study, path):
    """ACME CFI-G (PSI-159). path = 'normal.csv|inverse.csv'. Gas-jet spherical flames, ISS CIR.
    Normal: fuel flows from burner into O2/N2 ambient -> ambient O2 = 'XO2 before test'.
    Inverse: O2/N2 flows from burner into fuel/N2 ambient -> NO ambient O2 (o2 fields left empty);
    XO2 is the O2 fraction of the burner flow and Xf the ambient fuel fraction."""
    normal_p, inverse_p = path.split("|")
    def fv(x):
        try: return float(x)
        except (TypeError, ValueError): return None
    def yn(x):
        x = (x or "").strip().lower()
        return {"yes": "yes", "no": "no", "flash": "flash"}.get(x)
    tests, seen = [], {}
    for cfg, fp in (("normal", normal_p), ("inverse", inverse_p)):
        hdr, rows = read_table(fp)
        for r in rows:
            d = dict(zip(hdr, r))
            if not d.get("Test"):
                continue
            tid = re.sub(r"\s+", "", d["Test"])
            t = base_row(study, tid); notes = []
            if tid in seen:
                notes.append("duplicate test id"); tid += "_dup"; t["test_id"] = tid
            seen[tid] = 1
            p_bar = fv(d.get("approx p (bar)"))
            hot = yn(d.get("Hot ignition"))
            end = (d.get("Self-ext or flow term") or d.get("Self -ext or flow term") or "").strip()
            bt = fv(d.get("burn time (sec)"))
            if bt is None and hot == "no": bt = 0.0
            if bt is None: notes.append("burn time missing")
            outcome = {"no": "no hot flame ignited", "flash": "momentary flash only"}.get(hot)
            if hot == "yes":
                outcome = {"SE": "hot flame; self-extinguished", "FT": "hot flame; ended by flow termination/timer"}.get(end, "hot flame; end mode unknown")
            fuel = d.get("Fuel", "").strip()
            peak_c = fv(d.get("Peak burner T (C )") or d.get("Peak burner Temp (C)"))
            tad = fv(d.get("Tad (K)"))
            if d.get("Tad (K)", "").startswith("#"): notes.append("Tad was a spreadsheet error (#DIV/0!), set empty")
            if cfg == "normal":
                o2 = fv(d.get("XO2 before test"))
                t["o2_min_pct"] = t["o2_max_pct"] = round(o2 * 100, 2) if o2 else None
                t["o2_final_pct"] = round(fv(d.get("XO2  after test")) * 100, 2) if fv(d.get("XO2  after test")) else None
                t["fuel_frac_burner"] = fv(d.get("Xf"))
                t["burn_rate_raw_unit_mm"] = None
                cf = (d.get("Cool flame?") or "").strip()
                t["cool_flame_obs"] = cf or None
                if not cf: notes.append("cool-flame column blank (assessment started only after round 1; blank = not recorded, not 'no')")
                if fv(d.get("mHC (mg/s)")) == 0: notes.append("zero fuel flow row (setup/aborted)")
            else:
                t["fuel_frac_ambient"] = fv(d.get("Xf  before test"))
                t["fluent_o2_frac"] = fv(d.get("XO2"))
                t["o2_note"] = "inverse flame: ambient is fuel/N2; XO2 here is O2 fraction of the burner flow"
                notes.append("inverse config: no ambient O2 value (o2_min/max left empty)")
                if "#VALUE" in (d.get("Peak burner temp (K)") or ""): notes.append("peak T (K) spreadsheet error")
            t.update({
                "material": fuel, "material_class": "gaseous fuel", "geometry": "spherical porous burner (6.35 mm)",
                "fuel": fuel, "config": cfg, "pressure_kpa": round(p_bar * 100, 1) if p_bar else None,
                "burn_time_s": bt, "ug_outcome": outcome,
                "peak_burner_t_c": peak_c, "adiabatic_flame_t_k": tad,
                "pi": "Sunderland (PI)", "observations_raw": (d.get("Comments") or "").strip() or None,
                "test_date": None, "test_gmt": f"day {d.get('Day')} / test-day id {tid[:5]}",
                "data_quality_note": "; ".join(notes),
            })
            tests.append(t)
    return tests, []



def adapt_flamedesign(study, path):
    """ACME Flame Design (PSI-10). path = 'normal.csv|inverse.csv'. Per report Table 1 the rows are the
    flames that ignited (no outcome column). 'RAMP/RAMPED' rows = flow was ramped, so fixed values are N/A.
    Normal: ambient O2 = XO2 (init). Inverse: ambient is C2H4/N2, XO2 = O2 fraction of burner flow."""
    normal_p, inverse_p = path.split("|")
    def fv(x):
        try: return float(x)
        except (TypeError, ValueError): return None
    tests = []
    for cfg, fp in (("normal", normal_p), ("inverse", inverse_p)):
        hdr, rows = read_table(fp)
        for r in rows:
            d = dict(zip(hdr, r))
            if not d.get("Test"): continue
            t = base_row(study, d["Test"].replace(" ", "")); notes = []
            ramp = any(str(v).upper().startswith(("RAMP", "LOW O2")) for v in d.values())
            if ramp: notes.append("flow ramped/low-O2 flag in table; fixed flow, Zst and Tad not given")
            p_atm = fv(d.get("pmean (atm)"))
            if p_atm is None: p_atm = fv(d.get("pinit (atm)"))
            if cfg == "normal":
                fuel = d["Fuel"]
                o2i = fv(d.get("XO2 (init)")); o2f = fv(d.get("XO2 (final)"))
                t["o2_min_pct"] = t["o2_max_pct"] = round(o2i * 100, 2) if o2i else None
                t["o2_final_pct"] = round(o2f * 100, 2) if o2f else None
                if o2f is None: notes.append("final O2 not recorded for this day")
                t["fuel_frac_burner"] = fv(d.get("Xfuel"))
                if fv(d.get("Xfuel")) is None and not ramp: notes.append("fuel fraction not numeric")
            else:
                fuel = "C2H4 (ambient, with N2)"
                t["fluent_o2_frac"] = fv(d.get("XO2"))
                t["fuel_frac_ambient"] = fv(d.get("XC2H4 initial"))
                t["o2_note"] = "inverse flame: ambient is C2H4/N2; XO2 is O2 fraction of burner flow"
                notes.append("inverse config: no ambient O2 value (o2_min/max empty)")
            if p_atm is None: notes.append("pressure missing")
            t.update({
                "material": fuel, "material_class": "gaseous fuel", "geometry": "spherical porous burner (6.35 mm)",
                "fuel": fuel, "config": cfg,
                "pressure_kpa": round(p_atm * 101.325, 1) if p_atm else None,
                "adiabatic_flame_t_k": fv(d.get("Tad (K)")),
                "ug_outcome": "listed as ignited flame (report Table 1 counts ignited flames per day)",
                "pi": "Axelbaum (PI)", "test_gmt": f"day {d.get('Day')}",
                "data_quality_note": "; ".join(notes + ["no extinction/soot outcome column; those come from the images and papers"]),
            })
            if t["test_id"].startswith(("19175", "21301")):
                t["ug_outcome"] = "listed in table; ignition not confirmed row by row"
                t["data_quality_note"] += ("; report Table 1 counts 14 ignited flames on 19175 (13 rows here)" if t["test_id"].startswith("19175")
                                           else "; report Table 1 counts 18 ignited flames on 21301 (20 rows here)")
            tests.append(t)
    return tests, []



def adapt_cld_days(study, path):
    """ACME CLD Flame (PSI-21). Table is a per-test-DAY log (not per flame): max MFC flows, fuel bottle,
    fuel concentration range (fuel mole fraction in the burner stream, N2-diluted), number of flames ignited.
    No O2, no pressure, no per-flame rows -> written to test_days.csv, not tests.csv."""
    hdr, rows = read_table(path)
    days = []
    for r in rows:
        d = dict(zip(hdr, r))
        if not d.get("Test Day"): continue
        bottle_raw = d["Fuel Bottle"]
        m = re.match(r"(\d+)%\s*([A-Za-z0-9]+)", bottle_raw)
        conc, fuel_raw = (m.group(1), m.group(2)) if m else (None, bottle_raw)
        fuel = "CH4" if fuel_raw.upper().startswith("CH") else ("C2H4" if fuel_raw.upper().startswith("C2H") else fuel_raw)
        notes = []
        if fuel_raw not in ("CH4", "C2H4"):
            notes.append(f"bottle label '{bottle_raw}' looks like a spreadsheet autofill artifact (CH4/C2H4 counter); fuel read as {fuel}")
        rng = d["Fuel conc. Range"].replace(" ", "")
        lo_hi = [float(x) for x in re.findall(r"\d+\.?\d*", rng)]
        days.append({
            "psi_id": study["psi_id"], "experiment": study["acronym"], "test_day": d["Test Day"],
            "year": 2000 + int(d["Test Day"][:2]), "day_of_year": int(d["Test Day"][2:]),
            "test_type": d["Test Type"], "fuel": fuel, "bottle_fuel_pct": conc,
            "fuel_mfc_max_slpm": float(d["Fuel MFC"]), "n2_mfc_max_slpm": float(d["N2 MFC"]),
            "fuel_conc_range_raw": d["Fuel conc. Range"],
            "fuel_conc_min_pct": min(lo_hi) if lo_hi else None, "fuel_conc_max_pct": max(lo_hi) if lo_hi else None,
            "flames_ignited": int(d["Flames ignited"]),
            "o2_pct": None, "pressure_kpa": None,
            "data_quality_note": "; ".join(notes + ["day-level log only: no O2, pressure or per-flame outcome in this table"]),
        })
    study["test_days"] = days
    study["n_flames_ignited"] = sum(x["flames_ignited"] for x in days)
    return [], []



def adapt_efield_days(study, path):
    """ACME E-FIELD Flames (PSI-22). No experimental table exists; rows hand-transcribed from Table 1 of the
    E-FIELD 30-day report (Inc. 57-58, 1 Jun 2019). Totals verified: 120 (coflow) + 99 (gas-jet) = 219 flames.
    Carry-forward cells (polarity, bottle) filled from the merged cells in the PDF table."""
    hdr, rows = read_table(path)
    days = []
    for r in rows:
        d = dict(zip(hdr, r))
        bottle = d["Fuel Bottle"]; m = re.match(r"(\d+)%\s*(\w+)", bottle)
        nums_ = [float(x) for x in re.findall(r"\d+", d["Fuel conc."])]
        coflow = d["Burner"] == "coflow"
        days.append({
            "psi_id": study["psi_id"], "experiment": study["acronym"], "test_day": d["Test Day"],
            "year": 2000 + int(d["Test Day"][:2]), "day_of_year": int(d["Test Day"][2:]),
            "test_type": f"round {d['Round']}, {d['Burner']} burner, mesh {d['Mesh Polarity']}",
            "fuel": m.group(2), "bottle_fuel_pct": m.group(1), "fuel_mfc_max_slpm": None, "n2_mfc_max_slpm": None,
            "fuel_conc_range_raw": d["Fuel conc."], "fuel_conc_min_pct": min(nums_), "fuel_conc_max_pct": max(nums_),
            "flames_ignited": int(d["Flames ignited"]),
            "o2_pct": 21.0 if coflow else None, "pressure_kpa": None,
            "burner": d["Burner"], "mesh_polarity": d["Mesh Polarity"],
            "data_quality_note": ("coflow air stated as 21% O2 in report; " if coflow else "ambient O2 of gas-jet rounds not stated in these reports; ")
                + "pressure not stated; transcribed from PDF table, not a PSI table; day-level log, no per-flame outcome",
        })
    study["test_days"] = days
    study["n_flames_ignited"] = sum(x["flames_ignited"] for x in days)
    assert sum(x["flames_ignited"] for x in days if x["burner"] == "coflow") == 120
    assert sum(x["flames_ignited"] for x in days if x["burner"] == "gas-jet") == 99
    return [], []



def adapt_sflame_days(study, path):
    """ACME s-Flame (PSI-23). Per-test-DAY log: atmosphere (O2 ~21%/~30% with N2 or He), fuel bottle,
    flames ignited. Atmosphere pressure: '~1 atm but pressure increases and O2% drops with vitiation'."""
    hdr, rows = read_table(path)
    days = []
    for r in rows:
        d = dict(zip(hdr, r))
        td = d.get("Test Day*")
        if not td: continue
        notes = []
        atm = d["Atmosphere*"]
        o2s = [float(x) for x in re.findall(r"~?(\d+)%", atm)]
        dil = re.search(r"with\s+(N\d?|He)\b", atm)
        diluent = None
        if dil:
            diluent = "He" if dil.group(1) == "He" else "N2"
            if dil.group(1) not in ("N2", "He"):
                notes.append(f"diluent typed '{dil.group(1)}' (spreadsheet autofill artifact), read as N2")
        bottle = d["Fuel Bottle"]
        raw_b = bottle
        if re.search(r"with N[3-9]", bottle):
            notes.append("bottle label has autofill artifact N3..N6 (read as N2)")
        species = []
        for sp in ("H2", "CH4", "C2H4"):
            if re.search(rf"\b{sp}\b", bottle) and sp not in species: species.append(sp)
        pct = [float(x) for x in re.findall(r"(\d+\.?\d*)%", bottle)]
        days.append({
            "psi_id": study["psi_id"], "experiment": study["acronym"], "test_day": td,
            "year": int(d["Year"]), "day_of_year": int(td[2:]),
            "test_type": d["Test Type"], "fuel": "+".join(species) or None, "bottle_fuel_pct": raw_b,
            "fuel_mfc_max_slpm": None, "n2_mfc_max_slpm": None,
            "fuel_conc_range_raw": bottle, "fuel_conc_min_pct": min(pct) if pct else None, "fuel_conc_max_pct": max(pct) if pct else None,
            "flames_ignited": int(d["Flames Ignited*"]),
            "o2_pct": None, "pressure_kpa": None,
            "o2_min_pct": min(o2s) if o2s else None, "o2_max_pct": max(o2s) if o2s else None,
            "diluent": diluent, "pressure_nominal_kpa": 101.3,
            "data_quality_note": "; ".join(notes + ["O2 is nominal ('~'); pressure nominal ~1 atm per report footnote, rises/O2 drops with vitiation; day-level log, no per-flame outcome"]),
        })
    study["test_days"] = days
    study["n_flames_ignited"] = sum(x["flames_ignited"] for x in days)
    return [], []



def adapt_bre(study, path):
    """ACME BRE (PSI-20). path = 'days.csv|per_flame.csv'.
    days.csv: corrected copy of the PSI day log (test-day id added; 2 wrong dates and 2 '%x100' cells fixed from the report).
    per_flame.csv: per-flame O2 / pressure / mass flux / end condition extracted from Dehghani (2022) dissertation
    Tables 6.1, E.1, F.1 by scripts/extract_bre_dissertation.py. Gas burner emulating a condensed fuel."""
    days_p, flame_p = path.split("|")
    hdr, rows = read_table(days_p)
    dayinfo, days = {}, []
    for r in rows:
        d = dict(zip(hdr, r))
        bottle = d["Fuel Bottle"].replace(" ", "")
        fuel = "CH4" if "CH4" in bottle else "C2H4"
        o2s = [float(x) for x in re.findall(r"\d+\.?\d*", d["Oxygen Conc (percent)"])]
        dayinfo[d["Test Day"]] = dict(burner=int(d["Burner Size (mm)"]), bottle=d["Fuel Bottle"], fuel=fuel)
        days.append({
            "psi_id": study["psi_id"], "experiment": study["acronym"], "test_day": d["Test Day"],
            "year": int(d["Year"]), "day_of_year": int(d["Test Day"][2:]), "test_type": f"{d['Burner Size (mm)']} mm burner",
            "fuel": fuel, "bottle_fuel_pct": d["Fuel Bottle"], "fuel_mfc_max_slpm": None, "n2_mfc_max_slpm": None,
            "fuel_conc_range_raw": d["Oxygen Conc (percent)"], "fuel_conc_min_pct": None, "fuel_conc_max_pct": None,
            "flames_ignited": int(d["Flames Ignited"]), "o2_pct": None, "pressure_kpa": None,
            "o2_min_pct": min(o2s), "o2_max_pct": max(o2s), "burner": f"{d['Burner Size (mm)']} mm",
            "data_quality_note": ("; ".join(x for x in [d.get("Source note", "")] if x) + "; " if d.get("Source note") else "")
                + "ambient O2 values are the nominal set points; pressure varied but is not listed in the day log (see per-flame rows)",
        })
    study["test_days"] = days
    study["n_flames_ignited"] = sum(x["flames_ignited"] for x in days)
    hdr2, rows2 = read_table(flame_p)
    tests = []
    for r in rows2:
        d = dict(zip(hdr2, r))
        day = d["test_id"][:5]
        info = dayinfo.get(day, {})
        t = base_row(study, d["test_id"]); notes = []
        if not info: notes.append("test day not in day log")
        xb, xa = float(d["xo2_before"]), float(d["xo2_after"])
        end = d["end_cond"]
        outcome = {"SE": "self-extinguished", "FT": "burning when fuel flow was terminated (treated as steady)",
                   "FTO": "burning with oscillations when fuel flow was terminated"}.get(end)
        if not end: notes.append("end condition not captured by text extraction of the PDF"); outcome = None
        if d["parse_note"]: notes.append(d["parse_note"])
        notes.append("values read from PDF text tables (dissertation), check the original table before quoting a single row")
        t.update({
            "material": f"gas burner emulating a condensed fuel ({info.get('bottle', '?')})", "material_class": "gaseous fuel (burning-rate emulator)",
            "geometry": f"flat porous burner, {info.get('burner', '?')} mm", "fuel": info.get("fuel"), "burner_mm": info.get("burner"),
            "o2_min_pct": round(xb * 100, 2), "o2_max_pct": round(xb * 100, 2), "o2_final_pct": round(xa * 100, 2),
            "pressure_kpa": round(float(d["p_bar"]) * 100, 1), "mass_flux_g_m2s": float(d["mass_flux"]) if "mass_flux" in d else float(d["mdot_g_m2s"]),
            "fuel_dhc_kj_g": float(d["dhc_kj_g"]) if d["dhc_kj_g"] else None,
            "burn_time_s": float(d["time_s"]) if d["time_s"] else None, "ug_outcome": outcome,
            "config": "normal (fuel into quiescent O2/N2)", "pi": "Quintiere / Sunderland (PI)",
            "test_gmt": f"test day {day}", "video_refs": f"dissertation {d['table']} line {d['source_line']}",
            "data_quality_note": "; ".join(notes),
        })
        tests.append(t)
    return tests, []


ADAPTERS = {"bre": adapt_bre, "sflame": adapt_sflame_days, "efield": adapt_efield_days, "cld": adapt_cld_days, "flamedesign": adapt_flamedesign, "cfig": adapt_cfig, "bass": adapt_bass, "bass2": adapt_bass2, "flex2env": adapt_flex2_envelope, "flex": adapt_flex, "saffire1": adapt_saffire1, "saffire2": adapt_saffire2, "saffire3": adapt_saffire3}

# ---------------------------------------------------------------- main

def main(out_dir, *specs):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    studies, tests, skipped, days = [], [], [], []
    for spec in specs:
        name, isa_path, table_path = spec.split(":", 2)
        if isa_path == "-":
            s = {"psi_id": "PSI-69", "title": "Flame Extinguishment Experiment", "acronym": "FLEX",
                 "publications": [], "quality_flags": ["no ISA-Tab metadata supplied for this study"]}
        else:
            s = study_from_isa(isa_path)
        tt, sk = ADAPTERS[name](s, table_path)
        days += s.pop("test_days", [])
        s["n_tests"] = len(tt)
        studies.append(s)
        tests += tt
        skipped += sk
        print(f"{s['psi_id']} {s['acronym']}: {len(tt)} tests, {len(sk)} skipped, {len(s['publications'])} pubs")
        for f in s["quality_flags"]:
            print("  FLAG:", f)
    (out / "studies.json").write_text(json.dumps(studies, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "skipped_rows.json").write_text(json.dumps(skipped, ensure_ascii=False, indent=2), encoding="utf-8")
    envs = [e for st in studies for e in st.get("planned_envelopes", [])]
    if envs:
        with open(out / "planned_envelopes.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(envs[0].keys()))
            w.writeheader()
            w.writerows(envs)
    if days:
        with open(out / "test_days.csv", "w", newline="", encoding="utf-8") as f:
            cols = []
            for x in days:
                cols += [k for k in x if k not in cols]
            w = csv.DictWriter(f, fieldnames=cols, restval="")
            w.writeheader(); w.writerows(days)
    with open(out / "tests.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(tests[0].keys()))
        w.writeheader()
        w.writerows(tests)


if __name__ == "__main__":
    main(*sys.argv[1:])
