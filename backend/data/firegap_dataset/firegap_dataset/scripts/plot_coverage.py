"""FLEX coverage map: O2 vs ambient pressure, marker = how each test ended.
Usage: python3 -I plot_coverage.py <tests.csv> <out.png>
"""
import sys
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
STYLE = {  # slot 1-3 of the validated palette + a distinct marker shape each
    "Extinction": ("#2a78d6", "o"),
    "Disruption": ("#eb6834", "^"),
    "Completion": ("#1baf7a", "s"),
}

d = pd.read_csv(sys.argv[1])
f = d[(d.experiment == "FLEX") & d.pressure_kpa.notna() & d.o2_min_pct.notna()]

fig, ax = plt.subplots(figsize=(9.6, 5.8), dpi=170, facecolor=SURFACE)
ax.set_facecolor(SURFACE)

# no-data zone below the lowest tested pressure
pmin = f.pressure_kpa.min()
ax.add_patch(Rectangle((10, 40), 32, pmin - 40, facecolor="none", edgecolor=INK2,
                       hatch="///", linewidth=0, alpha=0.35, zorder=0))
ax.text(41.6, 45, "ниже 70 кПа результатов FLEX нет", color=INK2, fontsize=9, va="center", ha="right")

f = f.assign(pc=(f.pressure_kpa / 10).round() * 10)          # pressure cluster
g = (f.groupby(["o2_min_pct", "pc", "test_end"])
       .agg(n=("test_id", "size"), p=("pressure_kpa", "mean")).reset_index())
DX = {"Extinction": -0.28, "Disruption": 0.0, "Completion": 0.28}   # dodge so overlaps stay visible
for k, (col, mk) in STYLE.items():
    s_ = g[g.test_end == k]
    ax.scatter(s_.o2_min_pct + DX[k], s_.p, s=22 + 16 * s_.n ** 0.9, marker=mk, color=col,
               edgecolor=SURFACE, linewidth=0.8, alpha=0.88,
               label=f"{k} (n={int(s_.n.sum())})", zorder=3)

# FLEX-2 planned matrix (hollow circles) - plan, not results
import os, itertools
envp = os.path.join(os.path.dirname(sys.argv[1]), "planned_envelopes.csv")
if os.path.exists(envp):
    e = pd.read_csv(envp)
    o2s = sorted({float(x) for v in e.o2_levels_pct.astype(str) for x in v.split(";") if x})
    ps = sorted({float(x) for v in e.pressure_levels_kpa.astype(str) for x in v.split(";") if x})
    gx, gy = zip(*itertools.product(o2s, ps))
    ax.scatter(gx, gy, s=46, marker="o", facecolor="none", edgecolor=INK2, linewidth=1.1,
               linestyle=(0, (2, 2)), zorder=2, label=f"FLEX-2 (PSI-68): план, {len(gx)} условий")

# reference atmospheres (hollow, direct-labelled)
ref = [("МКС: 21% O₂, ~101 кПа", 21, 101.3, (22.2, 112)),
       ("34% O₂ при 8,2 psi (≈56,5 кПа)", 34, 56.5, (22.8, 58))]
for name, x, y, (tx, ty) in ref:
    ax.scatter([x], [y], s=110, marker="D", facecolor="none", edgecolor=INK, linewidth=1.4, zorder=4)
    ax.annotate(name, (x, y), xytext=(tx, ty), color=INK, fontsize=9,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8), va="center")

ax.set_xlim(10, 42); ax.set_ylim(40, 320)
ax.set_xlabel("Кислород в атмосфере, % (начальная доля)", color=INK2, fontsize=10)
ax.set_ylabel("Давление, кПа", color=INK2, fontsize=10)
ax.grid(True, color=GRID, linewidth=0.7, zorder=0)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
for sp in ("left", "bottom"):
    ax.spines[sp].set_color(GRID)
ax.tick_params(colors=INK2, labelsize=9)
ax.set_title(f"FLEX (PSI-69): {len(f)} тестов горения капли и где данных нет",
             loc="left", color=INK, fontsize=12.5, fontweight="bold", pad=34)
fig.text(0.09, 0.885, "Форма и цвет — чем закончился тест, размер — число тестов. Ромбы — условия для сравнения.\nПустые круги — план FLEX-2 (PSI-68), это не результаты.",
         color=INK2, fontsize=9, va="top", linespacing=1.5)
leg = ax.legend(loc="upper right", frameon=False, fontsize=9, labelcolor=INK2)
fig.text(0.09, 0.015, "Источник: PSI-69 и PSI-68 Experimental table. Давление переведено из мм рт. ст.; "
         "один тест без давления в источнике не показан.", color=INK2, fontsize=7.5)
fig.subplots_adjust(top=0.82, bottom=0.14, left=0.09, right=0.97)
fig.savefig(sys.argv[2], facecolor=SURFACE)
print("saved", sys.argv[2], len(f), "points")
