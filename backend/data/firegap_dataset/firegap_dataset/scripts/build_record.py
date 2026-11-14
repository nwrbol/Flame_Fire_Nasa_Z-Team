"""Turn a PSI ISA-Tab investigation file + experimental table CSV into clean records.

Usage: python3 -I build_record.py <i_Investigation.txt> <experimental_table.csv> <out_dir>
"""
import csv
import json
import re
import sys
from pathlib import Path


def parse_isa(path):
    """Return dict: field name -> list of values (empty cells kept)."""
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t"):
            if not row or not row[0].strip():
                continue
            key = row[0].strip()
            vals = [v.strip() for v in row[1:]]
            if key not in out:  # keep first occurrence (STUDY block wins over empty INVESTIGATION dupes)
                out[key] = vals
            elif not any(out[key]) and any(vals):
                out[key] = vals
    return out


def first(isa, key):
    v = isa.get(key, [])
    return v[0] if v else ""


def parse_o2(text):
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", text or "")]
    approx = "~" in (text or "")
    if not nums:
        return None, None, approx
    return min(nums), max(nums), approx


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def main(isa_path, csv_path, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    isa = parse_isa(isa_path)

    n_pubs = len(isa.get("Study Publication Title", []))
    pubs = []
    for i in range(n_pubs):
        def col(key):
            vals = isa.get(key, [])
            return vals[i] if i < len(vals) else ""
        pubs.append({
            "title": col("Study Publication Title"),
            "authors": col("Study Publication Author List"),
            "doi": col("Study Publication DOI"),
            "link": col("Comment[Study Publication Link]"),
        })

    study = {
        "psi_id": first(isa, "Study Identifier"),
        "title": first(isa, "Study Title"),
        "acronym": first(isa, "Comment[Investigation Acronym]"),
        "psi_doi": first(isa, "Comment[DOI]"),
        "research_area": first(isa, "Comment[Research Area]"),
        "sub_area": first(isa, "Comment[SubResearch Area]"),
        "platform": first(isa, "Comment[Flight Platform]"),
        "hardware": first(isa, "Comment[Experiment Hardware]"),
        "objective": " ".join(first(isa, "Comment[Objective]").split()),
        "hypothesis": first(isa, "Comment[Hypothesis]"),
        "approach": first(isa, "Comment[Approach]"),
        "research_impact": first(isa, "Comment[Research Impacts]"),
        "tags": [t for t in isa.get("Study Design Type", []) if t],
        "metadata_start_date": first(isa, "Comment[Investigation Start Date]"),
        "metadata_end_date": first(isa, "Comment[Investigation End Date]"),
        "proposal_title_in_metadata": first(isa, "Comment[Proposal Title]"),
        "publications": pubs,
    }

    # --- experimental table ---
    tests = []
    skipped = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [h.strip() for h in reader.fieldnames]
        for r in reader:
            r = {k: (v or "").strip() for k, v in r.items() if k}
            sid = r.get("Sample Number", "")
            if not sid:
                continue
            if num(r.get("Air Flow (cm/s)")) is None:  # pre-test flow visualisation rows etc.
                skipped.append({"row": sid, "reason": r.get("Material", "no numeric data")})
                continue
            o2min, o2max, approx = parse_o2(r.get("Percent O2"))
            notes = []
            notes.append("pressure not stated in table")
            notes.append("outcome (extinguished vs burned out, spread rate) not stated; only burn time")
            notes.append("length/width columns may be swapped: metadata says ~0.94 m long x 0.4 m wide")
            tests.append({
                "psi_id": study["psi_id"],
                "experiment": study["acronym"],
                "test_id": sid,
                "material": r.get("Material"),
                "o2_min_pct": o2min,
                "o2_max_pct": o2max,
                "o2_approx": approx,
                "pressure": None,
                "flow_cm_s": num(r.get("Air Flow (cm/s)")),
                "flow_direction": r.get("Flow Direction"),
                "burn_time_s": num(r.get("Burn Time (s)")),
                "ignition_power_w": num(r.get("Ignition Power (W)")),
                "ignition_time_s": num(r.get("Ignition Time (s)")),
                "sample_thickness_cm_as_listed": num(r.get("Sample Thickness (cm)")),
                "sample_length_cm_as_listed": num(r.get("Sample Length (cm)")),
                "sample_width_cm_as_listed": num(r.get("Sample Width (cm)")),
                "video_refs": ";".join(x for x in (r.get("Camera 1"), r.get("Camera 2")) if x),
                "data_quality_note": "; ".join(notes),
            })

    # metadata sanity flags
    flags = []
    if study["proposal_title_in_metadata"] and "smoke" in study["proposal_title_in_metadata"].lower():
        flags.append("Proposal Title in metadata is about smoke detection (looks like another experiment)")
    if study["metadata_start_date"].endswith("2001") or study["metadata_end_date"].endswith("2008"):
        flags.append(f"Investigation dates {study['metadata_start_date']} - {study['metadata_end_date']} look wrong for Saffire-I")
    study["quality_flags"] = flags

    (out_dir / "study.json").write_text(json.dumps(study, ensure_ascii=False, indent=2), encoding="utf-8")
    if tests:
        with open(out_dir / "tests.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(tests[0].keys()))
            w.writeheader()
            w.writerows(tests)
    (out_dir / "skipped_rows.json").write_text(json.dumps(skipped, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"study: {study['psi_id']} {study['acronym']}  publications: {len(pubs)}  tests: {len(tests)}  skipped: {len(skipped)}")
    for fl in flags:
        print("FLAG:", fl)


if __name__ == "__main__":
    main(*sys.argv[1:4])
