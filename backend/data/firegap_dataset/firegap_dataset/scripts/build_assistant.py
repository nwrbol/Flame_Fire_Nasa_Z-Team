"""Build the self-contained FireGap assistant page. Usage: python3 -I build_assistant.py <tests.csv> <studies.json> <engine.js> <out.html>"""
import sys, re, json, pandas as pd, math
tests_p, studies_p, engine_p, out_p = sys.argv[1:5]
d = pd.read_csv(tests_p)
studies = {s["psi_id"]: s for s in json.load(open(studies_p))}
def fam(r):
    e = r.experiment
    if e in ("BASS", "BASS-II"): return "solid"
    if e == "FLEX": return "droplet"
    if e == "ACME BRE": return "burner"
    if e in ("ACME CFI-G", "ACME/Flame Design") and r.config == "normal": return "gas"
    return None
def oc(r):
    s = str(r.ug_outcome)
    if r.experiment == "ACME CFI-G":
        return {"hot flame; self-extinguished": "ext", "hot flame; ended by flow termination/timer": "sust",
                "no hot flame ignited": "none", "momentary flash only": "none"}.get(s)
    if r.experiment == "ACME BRE":
        if s == "self-extinguished": return "ext"
        if s.startswith("burning"): return "sust"
    return None
def nn(x): return None if (x is None or (isinstance(x, float) and math.isnan(x))) else x
rows = []
for r in d.itertuples():
    f = fam(r)
    if not f: continue
    p = nn(r.pressure_kpa) if nn(r.pressure_kpa) is not None else nn(r.pressure_kpa_assumed)
    if nn(r.o2_min_pct) is None or p is None: continue
    obs = nn(r.observations_raw)
    if obs: obs = " ".join(str(obs).split())[:140]
    note = str(nn(r.data_quality_note) or "")
    rows.append(dict(id=str(r.test_id), psi=r.psi_id, exp=r.experiment, fam=f, mat=str(nn(r.material) or ""), o2=float(r.o2_min_pct), p=float(p),
        pa=nn(r.pressure_kpa) is None, oc=oc(r), burn=nn(r.burn_time_s), ext=nn(r.extinction_d_mm), obs=obs,
        fuel=nn(r.fuel), burner=nn(r.burner_mm), flux=nn(r.mass_flux_g_m2s), flag=bool(re.search(r"unreadable|appears 2x|typo|implausible|disagrees|spreadsheet error|not captured|approximate|copy error", note)), note=(note[:200] if re.search(r"unreadable|appears 2x|typo|implausible|disagrees|spreadsheet error|not captured|approximate|copy error", note) else "")))
meta = {k: dict(acr=v["acronym"], title=v["title"], doi=v.get("psi_doi")) for k, v in studies.items()}
data = {"tests": rows, "studies": meta}
html = open("/home/claude/assistant/template.html").read()
html = html.replace("/*ENGINE*/", open(engine_p).read()).replace("/*DATA*/", "const DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";")
open(out_p, "w").write(html); print(len(rows), "tests embedded,", len(html) // 1024, "KB")
