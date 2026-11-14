"""Extract per-flame BRE results from Dehghani (2022) dissertation text (pypdf output).
Tables used: 6.1 (ethylene/N2 + some CH4 days, 25 mm), E.1 (CH4/N2, 25 mm), F.1 (50 mm).
Usage: python3 -I extract_bre_dissertation.py <dissertation.txt> <out.csv>
Only rows whose key fields parse cleanly are kept; the rest go to the notes/skipped list."""
import csv, re, sys
L = open(sys.argv[1], encoding="utf-8").read().split("\n")
def find(prefix):
    for i, l in enumerate(L):
        if l.strip().startswith(prefix) and i > 1000: return i
    raise SystemExit("missing " + prefix)
a61, aE1, aF1, a62 = find("Table 6.1."), find("Table E.1."), find("Table F.1."), find("Table 6.2")
END = {"SE", "FT", "FTO"}
def isnum(x):
    try: float(x); return True
    except ValueError: return False
out, skipped = [], []
def rows(a, b):
    for i in range(a, b):
        m = re.match(r"^(\d{5}[A-Z]\d+)\s+(.*)$", L[i].strip())
        if m: yield i + 1, m.group(1), m.group(2).split()
for ln, tid, t in rows(a61, a62):
    # 6.1 layout: xo2b xo2a [dhc] p mdot ... [xr] [osc] time endcond
    end = t[-1] if t and t[-1] in END else None
    if len(t) < 5 or not isnum(t[0]) or not isnum(t[1]):
        skipped.append((tid, "table 6.1 row broken across lines or marked 'not useful'", ln)); continue
    x = [float(v) for v in t[:2]]
    rest = t[2:]
    if len(rest) > 2 and all(isnum(v) for v in rest[:3]) and 8 <= float(rest[0]) <= 50 and 0.4 <= float(rest[1]) <= 3.5:
        dhc, p, m = float(rest[0]), float(rest[1]), float(rest[2])
    elif len(rest) > 1 and isnum(rest[0]) and isnum(rest[1]) and 0.4 <= float(rest[0]) <= 3.5:
        dhc, p, m = None, float(rest[0]), float(rest[1])
    elif len(rest) > 2 and all(isnum(v) for v in rest[:3]) and 0.4 <= float(rest[1]) <= 3.5:
        dhc, p, m = float(rest[0]), float(rest[1]), float(rest[2])   # heat of combustion looks mistyped (e.g. 4.6)
    else:
        skipped.append((tid, "table 6.1: cannot locate pressure/mass flux", ln)); continue
    body = t[:-1] if end else t
    tm = float(body[-1]) if isnum(body[-1]) else None
    out.append(dict(test_id=tid, table="6.1", xo2_before=x[0], xo2_after=x[1], dhc_kj_g=dhc, p_bar=p, mdot_g_m2s=m,
                    end_cond=end, time_s=tm, source_line=ln,
                    parse_note="" if end else "end condition not captured by text extraction"))
for tab, a, b in (("E.1", aE1, aF1), ("F.1", aF1, len(L))):
    for ln, tid, t in rows(a, b):
        if len(t) < 8 or not all(isnum(v) for v in t[:7]) or t[7] not in END:
            skipped.append((tid, f"table {tab} row not parseable", ln)); continue
        dhc, xb, xa, p, m, osc, ext = [float(v) for v in t[:7]]
        out.append(dict(test_id=tid, table=tab, xo2_before=xb, xo2_after=xa, dhc_kj_g=dhc, p_bar=p, mdot_g_m2s=m,
                        end_cond=t[7], time_s=ext, source_line=ln, parse_note=""))
# dedupe: 20339A0 appears in 6.1 and E.1 (same flame): keep E.1
seen = {}
for r in out:
    if r["test_id"] in seen and r["table"] != "6.1": seen[r["test_id"]] = r
    elif r["test_id"] not in seen: seen[r["test_id"]] = r
final = list(seen.values())
with open(sys.argv[2], "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(final[0].keys())); w.writeheader(); w.writerows(final)
print(len(out), "rows parsed,", len(final), "unique,", len(skipped), "skipped:", skipped)
