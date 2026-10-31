# grid_plots.py - all the matplotlib drawing (kept separate from the window code)
import numpy as np
from matplotlib.lines import Line2D
from grid_data import IEEE_30_LINES, GEN_PMAX, V_MIN, V_MAX

BG_MAIN, BG_CARD = "#FFFFFF", "#F2F2F7"
FG_TEXT, FG_MUTED = "#000000", "#636366"
COLOR_ACCENT, COLOR_RED, COLOR_GREEN, COLOR_ORANGE = "#007AFF", "#FF3B30", "#34C759", "#FF9500"
COLOR_GREY = "#AEAEB2"
ISLAND_COLORS = ["#007AFF", "#34C759", "#AF52DE", "#FF9500", "#5AC8FA", "#FF2D55"]

POS = {
    1: (1, 10),  2: (3, 10), 3: (2, 9),   4: (3, 8),   5: (5, 10),
    6: (5, 8),   7: (6, 9),  8: (7, 8),   9: (5, 6),   10: (5, 4),
    11: (4, 6),  12: (3, 5), 13: (3, 4),  14: (2, 4),  15: (2, 3),
    16: (4, 4),  17: (4, 3), 18: (1, 2),  19: (2, 1),  20: (3, 1),
    21: (4, 1),  22: (5, 1), 23: (1, 3),  24: (3, 2),  25: (6, 2),
    26: (7, 2),  27: (7, 4), 28: (7, 6),  29: (8, 3),  30: (8, 4)
}


def loading_color(pct):
    if pct > 100: return COLOR_RED
    if pct > 70:  return COLOR_ORANGE
    return COLOR_GREEN


def voltage_color(vm):
    if vm < V_MIN or vm > V_MAX: return COLOR_RED
    if vm < V_MIN + 0.02 or vm > V_MAX - 0.02: return COLOR_ORANGE
    return COLOR_GREEN


def nearest_line(x, y, max_dist=0.25):
    # which line is closest to the click, or None if nothing is close
    best, best_d = None, max_dist
    for k, (a, b) in enumerate(IEEE_30_LINES):
        (x1, y1), (x2, y2) = POS[a], POS[b]
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        d = np.hypot(x - (x1 + t * dx), y - (y1 + t * dy))
        if d < best_d:
            best, best_d = k, d
    return best


def draw_topology(ax, res, color_mode="island"):
    # color_mode is "island" or "voltage"
    ax.clear(); ax.set_facecolor(BG_MAIN)
    bus, lines = res["bus"], res["lines"]
    for l in lines:
        (x1, y1), (x2, y2) = POS[l["f"]], POS[l["t"]]
        if not l["in_service"]:
            ax.plot([x1, x2], [y1, y2], color=COLOR_RED, ls="--", lw=1.8, zorder=1)
        elif not l["energized"]:
            ax.plot([x1, x2], [y1, y2], color="#D1D1D6", lw=1.2, zorder=1)
        else:
            mw = max(abs(l["p_from"]), abs(l["p_to"]))
            ax.plot([x1, x2], [y1, y2], color=loading_color(l["loading"]),
                    lw=1.2 + min(mw, 120) / 30.0, zorder=1, solid_capstyle="round")
    gens = set(GEN_PMAX)
    for b, (x, y) in POS.items():
        d = bus[b]
        if color_mode == "voltage":
            col = voltage_color(d["vm"]) if d["energized"] else COLOR_GREY
        else:
            isl = res["islands"][d["island"] - 1]
            col = COLOR_GREY if isl["code"] in ("dead", "collapse") else \
                ISLAND_COLORS[(d["island"] - 1) % len(ISLAND_COLORS)]
        ax.scatter([x], [y], s=330 if b in gens else 250, c=col,
                   marker="s" if b in gens else "o", edgecolors="#1C1C1E",
                   linewidths=1.6 if b in gens else 1.1, zorder=3)
        ax.text(x, y, str(b), color="white", fontsize=7, fontweight="bold",
                ha="center", va="center", zorder=4)
        if b in res["tripped_gens"]:
            ax.scatter([x], [y], s=520, marker="x", c=COLOR_RED, linewidths=2, zorder=5)
    handles = [
        Line2D([], [], marker="s", color="w", markerfacecolor=COLOR_ACCENT, markeredgecolor="#1C1C1E", markersize=9, label="Generator"),
        Line2D([], [], marker="o", color="w", markerfacecolor=COLOR_ACCENT, markeredgecolor="#1C1C1E", markersize=8, label="Load bus"),
        Line2D([], [], color=COLOR_GREEN, lw=2.5, label="Line under 70% loaded"),
        Line2D([], [], color=COLOR_ORANGE, lw=2.5, label="Line 70-100% loaded"),
        Line2D([], [], color=COLOR_RED, lw=2.5, label="Line overloaded"),
        Line2D([], [], color=COLOR_RED, lw=1.8, ls="--", label="Line cut"),
        Line2D([], [], marker="o", color="w", markerfacecolor=COLOR_GREY, markeredgecolor="#1C1C1E", markersize=8, label="Blackout"),
    ]
    ax.legend(handles=handles, loc="center right", fontsize=7, framealpha=0.95,
              facecolor=BG_CARD, edgecolor="#D1D1D6")
    ax.set_xlim(0.3, 10.8); ax.set_ylim(0.3, 10.7)
    ax.axis("off")


def _style(ax, title=None):
    ax.clear(); ax.set_facecolor(BG_MAIN)
    ax.tick_params(colors=FG_TEXT, labelsize=8)
    ax.grid(axis="y", ls="--", alpha=0.3, color=FG_MUTED)
    for s in ax.spines.values(): s.set_color("#D1D1D6")
    if title: ax.set_title(title, fontsize=9, color=FG_TEXT)


def draw_balance(ax, res):
    _style(ax, "Generation vs demand per island")
    isl = res["islands"]
    x = np.arange(len(isl)); w = 0.27
    ax.bar(x - w, [i["gen"] for i in isl], w, label="Generation", color=COLOR_GREEN)
    ax.bar(x, [i["demand"] for i in isl], w, label="Demand", color=COLOR_RED)
    ax.bar(x + w, [i["shed"] for i in isl], w, label="Load cut", color=COLOR_ORANGE)
    ax.set_xticks(x); ax.set_xticklabels([f"#{i['id']}" for i in isl])
    ax.set_ylabel("MW", fontsize=9); ax.legend(fontsize=7)


def draw_voltage(ax, res):
    _style(ax, "Voltage at each bus")
    buses = list(range(1, 31))
    vm = [res["bus"][b]["vm"] for b in buses]
    ax.bar(buses, vm, color=[voltage_color(v) if v > 0 else COLOR_GREY for v in vm])
    ax.axhline(V_MIN, color=COLOR_RED, ls="--", lw=1); ax.axhline(V_MAX, color=COLOR_RED, ls="--", lw=1)
    ax.set_ylim(0.8, 1.15); ax.set_xlim(0.3, 30.7)
    ax.set_xticks(buses); ax.tick_params(axis="x", labelsize=6)
    ax.set_xlabel("Bus", fontsize=8); ax.set_ylabel("|V| (pu)", fontsize=9)


def draw_loading(ax, res, top=15):
    _style(ax, f"{top} busiest lines (% of rating)")
    ls = sorted(res["lines"], key=lambda l: l["loading"], reverse=True)[:top][::-1]
    y = np.arange(len(ls))
    ax.barh(y, [l["loading"] for l in ls], color=[loading_color(l["loading"]) for l in ls])
    ax.set_yticks(y); ax.set_yticklabels([f"{l['f']}-{l['t']}" for l in ls], fontsize=7)
    ax.axvline(100, color=COLOR_RED, ls="--", lw=1)
    ax.grid(axis="y", alpha=0); ax.grid(axis="x", ls="--", alpha=0.3)
    ax.set_xlabel("% loading", fontsize=8)
