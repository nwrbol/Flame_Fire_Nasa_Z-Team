"""All-experiment O2 x pressure coverage map. Usage: python3 -I plot_gap_map.py <tests.csv> <out.png>"""
import sys, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
d = pd.read_csv(sys.argv[1])
d["p"] = d.pressure_kpa.fillna(d.pressure_kpa_assumed)
d["assumed"] = d.pressure_kpa.isna() & d.pressure_kpa_assumed.notna()
d = d.dropna(subset=["o2_min_pct", "p"])
d = d[d.o2_min_pct.between(5, 50)]
groups = [
    ("FLEX — капли (жидкое топливо)", d[d.experiment == "FLEX"], BLUE, "o", False),
    ("BASS-II / BASS — твёрдые (давление BASS-II принято ≈101 кПа)", d[d.experiment.isin(["BASS", "BASS-II"])], ORANGE, "s", False),
    ("ACME (CFI-G, Flame Design) — газовые пламёна, нормальные", d[(d.experiment.str.startswith("ACME")) & (d.experiment != "ACME BRE") & (d.config == "normal")], AQUA, "^", False),
    ("ACME BRE — горелка, имитирующая горение твёрдого материала", d[d.experiment == "ACME BRE"], YELLOW, "D", False),
]
fig, ax = plt.subplots(figsize=(9.8, 5.8), dpi=170, facecolor=SURF); ax.set_facecolor(SURF)
ax.axhspan(0, 70, color=GRID, alpha=0.5, zorder=0)
ax.text(11.4, 55, "ниже 70 кПа: ни капель, ни твёрдых —\nтолько газовые пламёна (ACME CFI-G, BRE)", va="center", fontsize=8, color=INK2)
for name, g, col, mk, _ in groups:
    g = g.assign(o=(g.o2_min_pct * 2).round() / 2, pp=(g.p / 5).round() * 5).groupby(["o", "pp"]).size().reset_index(name="n")
    ax.scatter(g.o, g.pp, s=26 + 16 * g.n ** 0.85, color=col, marker=mk, alpha=0.78, edgecolor=(INK2 if col == YELLOW else SURF), linewidth=0.8,
               label=f"{name}  (n={int(g.n.sum())})", zorder=3)
ax.annotate("34% O₂ при 8.2 psi (≈56.5 кПа): атмосфера\nдля Луны/Марса — только BRE, горелка, не твёрдое", (34, 56.5), xytext=(26.5, 185),
            fontsize=8.5, color=INK, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
ax.scatter([21], [101.3], marker="+", s=140, color=INK, linewidth=1.6, zorder=5)
ax.annotate("станция сейчас ≈21% / 101 кПа", (21, 101.3), xytext=(22.6, 128), fontsize=8.5, color=INK,
            arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
ax.set_xlim(11, 42); ax.set_ylim(40, 350)
ax.set_xlabel("Кислород в атмосфере, % (начальная доля)", color=INK2, fontsize=10)
ax.set_ylabel("Давление, кПа", color=INK2, fontsize=10)
ax.grid(True, color=GRID, lw=0.7, zorder=1)
for sp in ("top", "right"): ax.spines[sp].set_visible(False)
for sp in ("left", "bottom"): ax.spines[sp].set_color(GRID)
ax.tick_params(colors=INK2, labelsize=9, length=0)
ax.legend(loc="upper right", frameon=False, fontsize=8.5, labelcolor=INK, markerscale=0.8)
fig.suptitle("Что известно про кислород × давление: твёрдые — только у 1 атм, газы — до 3 бар", x=0.02, ha="left",
             color=INK, fontsize=12.5, fontweight="bold")
fig.text(0.02, 0.012, "Размер маркера — число тестов. Saffire не показан: давление в таблицах не указано. Инверсные пламёна ACME не показаны: у них нет O₂ в окружающей среде.",
         color=INK2, fontsize=7.3)
fig.subplots_adjust(top=0.9, bottom=0.12, left=0.07, right=0.97)
fig.savefig(sys.argv[2], facecolor=SURF); print("ok")
