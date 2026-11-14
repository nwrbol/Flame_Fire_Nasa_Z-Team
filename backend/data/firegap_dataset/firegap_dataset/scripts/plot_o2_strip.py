"""O2 coverage by material family. Usage: python3 -I plot_o2_strip.py <tests.csv> <out.png>"""
import sys, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
d = pd.read_csv(sys.argv[1]).dropna(subset=["o2_min_pct"])

def fam(r):
    if r.experiment == "FLEX": return "FLEX: капли жидкого\nтоплива (метанол, гептан)"
    if r.experiment == "BASS":
        return "BASS: сферы ПММА, свечи,\nSIBAL, Nomex (в т.ч. 16–18% O₂)"
    if r.experiment == "BASS-II":
        c = str(r.material_class)
        if c.startswith("SIBAL"): return "BASS-II: ткань SIBAL"
        if c.startswith("Nomex"): return "BASS-II: Nomex"
        return "BASS-II: ПММА, стержни,\nплёнки и др."
    if r.experiment.startswith("SAFFIRE"): return "Saffire I–III: ткань,\nсиликон, ПММА"
d["fam"] = d.apply(fam, axis=1)
order = ["FLEX: капли жидкого\nтоплива (метанол, гептан)", "BASS-II: ПММА, стержни,\nплёнки и др.",
         "BASS-II: ткань SIBAL", "BASS-II: Nomex", "BASS: сферы ПММА, свечи,\nSIBAL, Nomex (в т.ч. 16–18% O₂)", "Saffire I–III: ткань,\nсиликон, ПММА"]
col = {order[0]: BLUE, order[1]: ORANGE, order[2]: ORANGE, order[3]: ORANGE, order[4]: ORANGE, order[5]: AQUA}
mk = {order[0]: "o", order[1]: "s", order[2]: "s", order[3]: "s", order[4]: "D", order[5]: "^"}
fig, ax = plt.subplots(figsize=(9.6, 5.4), dpi=170, facecolor=SURF); ax.set_facecolor(SURF)
for i, f in enumerate(order):
    g = d[d.fam == f].assign(o2r=lambda x: (x.o2_min_pct * 2).round() / 2).groupby("o2r").size().reset_index(name="n").rename(columns={"o2r": "o2_min_pct"})
    y = len(order) - 1 - i
    ax.scatter(g.o2_min_pct, [y] * len(g), s=30 + 14 * g.n ** 0.9, color=col[f], marker=mk[f],
               edgecolor=SURF, linewidth=0.8, alpha=0.88, zorder=3)
    ax.text(41.7, y, f"n={int(g.n.sum())}", ha="right", va="center", color=INK2, fontsize=8.5)
ax.axvline(34, color=INK, lw=1.2, ls=(0, (4, 3)), zorder=2)
ax.text(33.7, 3.5, "34% O₂ — пример из другой команды,\nпроверьте по документам NASA", ha="right", va="center", color=INK, fontsize=8.5)
solids = d[d.fam != order[0]]
mx = solids.o2_min_pct.max()
ax.annotate(f"макс. у твёрдых: {mx:.1f}%", (mx + 0.3, 1), xytext=(24.6, 1.55), color=INK, fontsize=9,
            arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8), va="center")
ax.set_yticks(range(len(order))); ax.set_yticklabels(order[::-1], fontsize=9, color=INK)
ax.set_xlim(11, 42); ax.set_ylim(-0.6, len(order) - 0.2)
ax.set_xlabel("Кислород в атмосфере, % (начальная доля)", color=INK2, fontsize=10)
ax.grid(True, axis="x", color=GRID, lw=0.7, zorder=0)
for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
ax.spines["bottom"].set_color(GRID); ax.tick_params(colors=INK2, labelsize=9, length=0)
fig.suptitle("Твёрдые материалы тестировали при кислороде до ~22.7%, жидкие капли — до 34%", x=0.02, ha="left",
             color=INK, fontsize=12.5, fontweight="bold")
fig.text(0.02, 0.015, "Размер маркера — число тестов. Источник: Experimental tables PSI-69, PSI-25, PSI-26, PSI-98/99/100. BASS: 22.7% — измеренный фон станции, не обогащение.", color=INK2, fontsize=7.5)
fig.subplots_adjust(top=0.88, bottom=0.14, left=0.36, right=0.97)
fig.savefig(sys.argv[2], facecolor=SURF); print("ok")
