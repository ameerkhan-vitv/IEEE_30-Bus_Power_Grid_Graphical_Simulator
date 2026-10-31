# main_app.py
# IEEE 30-bus power grid simulator - run this file to start the program.
# Course project: Computer Aided Power System Analysis
# Team: (add your names here)
import csv
import os
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from grid_data import IEEE_30_LINES, GEN_PMAX, V_MIN, V_MAX
from grid_engine import solve_system, run_n1_sweep, build_ybus
from grid_tests import SCENARIOS, summarize, run_validation
import grid_plots as gp

BG_MAIN, BG_CARD = gp.BG_MAIN, gp.BG_CARD
FG_TEXT, FG_MUTED = gp.FG_TEXT, gp.FG_MUTED
COLOR_ACCENT, COLOR_RED = gp.COLOR_ACCENT, gp.COLOR_RED
COLOR_GREEN, COLOR_ORANGE = gp.COLOR_GREEN, gp.COLOR_ORANGE


class GridSandboxApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IEEE 30-Bus Power Grid Simulator")
        self.root.geometry("1500x900")
        self.root.configure(bg=BG_MAIN)

        self.broken_lines = []      # list of (from, to) tuples
        self.tripped_gens = []      # list of bus numbers
        self.res = None
        self.n1_rows = []
        self.tab_frames = {}
        self.demo_job = None
        self.demo_idx = 0

        self.color_mode = tk.StringVar(value="island")
        self.setup_ui_layout()
        self.update_simulation()

    # ---- building the window ----
    def _btn(self, parent, text, cmd, bg=BG_CARD, fg=FG_TEXT):
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                         activebackground=COLOR_ACCENT, activeforeground=BG_MAIN,
                         bd=1, relief=tk.GROOVE, padx=10, pady=3, cursor="hand2",
                         font=("Helvetica", 9, "bold"))

    def setup_ui_layout(self):
        # controls at the top
        ctl = tk.LabelFrame(self.root, text=" Controls ", bg=BG_MAIN, fg=COLOR_ACCENT,
                            font=("Helvetica", 10, "bold"), bd=1, relief=tk.SOLID)
        ctl.pack(fill=tk.X, padx=12, pady=(8, 4))
        row1 = tk.Frame(ctl, bg=BG_MAIN); row1.pack(fill=tk.X, pady=3)
        row2 = tk.Frame(ctl, bg=BG_MAIN); row2.pack(fill=tk.X, pady=3)

        tk.Label(row1, text="Line:", bg=BG_MAIN, font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(10, 2))
        self.line_selector = ttk.Combobox(
            row1, values=[f"{a} - {b}" for a, b in IEEE_30_LINES], state="readonly", width=8)
        self.line_selector.pack(side=tk.LEFT, padx=4)
        self.line_selector.current(0)
        self._btn(row1, "Cut Line", self.trip_selected_line, COLOR_RED, BG_MAIN).pack(side=tk.LEFT, padx=3)
        self._btn(row1, "Restore Line", self.close_selected_line).pack(side=tk.LEFT, padx=3)
        self._btn(row1, "Reset All", self.reset_entire_grid).pack(side=tk.LEFT, padx=3)
        tk.Label(row1, text="   (or just click a line on the map to cut / restore it)",
                 bg=BG_MAIN, fg=FG_MUTED, font=("Helvetica", 9, "italic")).pack(side=tk.LEFT, padx=8)

        tk.Label(row2, text="Quick faults:", bg=BG_MAIN, font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(10, 4))
        self._btn(row2, "Random Faults", self.trigger_random_storm).pack(side=tk.LEFT, padx=3)
        self._btn(row2, "Fail Key Lines", self.trigger_infrastructure_attack).pack(side=tk.LEFT, padx=3)
        tk.Label(row2, text="  Generator:", bg=BG_MAIN, font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(14, 2))
        self.gen_selector = ttk.Combobox(row2, values=[f"Bus {g}" for g in GEN_PMAX],
                                         state="readonly", width=7)
        self.gen_selector.pack(side=tk.LEFT, padx=4)
        self.gen_selector.current(0)
        self._btn(row2, "Gen Off / On", self.toggle_generator).pack(side=tk.LEFT, padx=3)

        tk.Label(row2, text="  Load level (%):", bg=BG_MAIN, font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(14, 2))
        self.load_scale = tk.Scale(row2, from_=50, to=150, resolution=5, orient=tk.HORIZONTAL,
                                   length=160, bg=BG_MAIN, highlightthickness=0)
        self.load_scale.set(100)
        self.load_scale.pack(side=tk.LEFT)
        self.load_scale.bind("<ButtonRelease-1>", lambda e: self.update_simulation())

        tk.Label(row2, text="  Colour buses by:", bg=BG_MAIN, font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(14, 2))
        for txt, val in (("Island", "island"), ("Voltage", "voltage")):
            tk.Radiobutton(row2, text=txt, variable=self.color_mode, value=val, bg=BG_MAIN,
                           command=self.update_simulation).pack(side=tk.LEFT)
        self._btn(row2, "Show Ybus", self.show_ybus).pack(side=tk.RIGHT, padx=3)
        self._btn(row2, "Export CSV", self.export_csv).pack(side=tk.RIGHT, padx=3)

        row3 = tk.Frame(ctl, bg=BG_MAIN); row3.pack(fill=tk.X, pady=3)
        tk.Label(row3, text="Tests:", bg=BG_MAIN, fg=COLOR_ACCENT,
                 font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=(10, 4))
        self.scenario_selector = ttk.Combobox(row3, values=[s["name"] for s in SCENARIOS],
                                              state="readonly", width=44)
        self.scenario_selector.pack(side=tk.LEFT, padx=4)
        self.scenario_selector.current(0)
        self._btn(row3, "Run", self.run_selected_scenario, COLOR_ACCENT, BG_MAIN).pack(side=tk.LEFT, padx=3)
        self.demo_btn = self._btn(row3, "Play All Demos", self.toggle_demo)
        self.demo_btn.pack(side=tk.LEFT, padx=3)
        self._btn(row3, "Self-Check", self.show_validation).pack(side=tk.LEFT, padx=3)

        self.banner = tk.Label(self.root, text="Pick a demo from the Tests drop-down, or click lines on the map to cut them.",
                               bg="#EAF3FF", fg=FG_TEXT, font=("Helvetica", 10), anchor=tk.W,
                               justify=tk.LEFT, wraplength=1400, padx=10, pady=5, bd=1, relief=tk.SOLID)
        self.banner.pack(fill=tk.X, padx=12, pady=(0, 4))

        # status bar (packed first so it stays at the bottom)
        bar = tk.Frame(self.root, bg=BG_CARD, bd=1, relief=tk.SUNKEN, height=32)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)
        self.status_left = tk.Label(bar, bg=BG_CARD, fg=FG_TEXT, font=("Helvetica", 10, "bold"), anchor=tk.W)
        self.status_left.pack(side=tk.LEFT, padx=12, fill=tk.Y)
        self.status_right = tk.Label(bar, bg=BG_CARD, font=("Helvetica", 10, "bold"), anchor=tk.E)
        self.status_right.pack(side=tk.RIGHT, padx=12, fill=tk.Y)

        # map on the left, tabs on the right
        main = tk.Frame(self.root, bg=BG_MAIN)
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        gframe = tk.LabelFrame(main, text=" Grid Map ", bg=BG_MAIN, fg=FG_MUTED,
                               font=("Helvetica", 10, "bold"), bd=1, relief=tk.SOLID)
        gframe.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        self.fig_map = Figure(figsize=(6.5, 6.5), facecolor=BG_MAIN)
        self.ax_map = self.fig_map.add_subplot(111)
        self.canvas_map = FigureCanvasTkAgg(self.fig_map, master=gframe)
        self.canvas_map.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.canvas_map.mpl_connect("button_press_event", self.on_map_click)

        right = tk.Frame(main, bg=BG_MAIN, width=640)
        right.pack(side=tk.RIGHT, fill=tk.BOTH)
        right.pack_propagate(False)
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill=tk.BOTH, expand=True)

        def chart_tab(title):
            frame = tk.Frame(self.tabs, bg=BG_MAIN)
            self.tabs.add(frame, text=title)
            self.tab_frames[title] = frame
            fig = Figure(figsize=(5.5, 4.5), facecolor=BG_MAIN)
            ax = fig.add_subplot(111)
            canvas = FigureCanvasTkAgg(fig, master=frame)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            return fig, ax, canvas

        self.fig_bal, self.ax_bal, self.cv_bal = chart_tab("Power Balance")
        self.fig_v, self.ax_v, self.cv_v = chart_tab("Voltages")
        self.fig_ld, self.ax_ld, self.cv_ld = chart_tab("Line Loading")

        # N-1 tab
        n1 = tk.Frame(self.tabs, bg=BG_MAIN); self.tabs.add(n1, text="N-1 Check")
        self.tab_frames["N-1 Check"] = n1
        top = tk.Frame(n1, bg=BG_MAIN); top.pack(fill=tk.X, pady=4)
        self._btn(top, "Cut every line, one at a time", self.run_n1).pack(side=tk.LEFT, padx=6)
        tk.Label(top, text="Double-click a row to try that fault on the map", bg=BG_MAIN, fg=FG_MUTED,
                 font=("Helvetica", 9, "italic")).pack(side=tk.LEFT, padx=6)
        self.n1_tree = self._make_tree(
            n1, [("line", "Line", 60), ("isl", "Islands", 55), ("lost", "Lost MW", 65),
                 ("ovl", "Overl.", 50), ("maxl", "Max load %", 80), ("minv", "Min V", 60),
                 ("sev", "Severity", 70)])
        self.n1_tree.bind("<Double-1>", self.apply_n1_row)

        # tables tab
        rs = tk.Frame(self.tabs, bg=BG_MAIN); self.tabs.add(rs, text="Tables")
        sub = ttk.Notebook(rs); sub.pack(fill=tk.BOTH, expand=True)
        bf = tk.Frame(sub, bg=BG_MAIN); lf = tk.Frame(sub, bg=BG_MAIN)
        sub.add(bf, text="Buses"); sub.add(lf, text="Lines")
        self.bus_tree = self._make_tree(
            bf, [("bus", "Bus", 40), ("isl", "Isl.", 40), ("v", "|V| pu", 60), ("a", "Angle°", 60),
                 ("pd", "Pd MW", 60), ("sv", "Served", 60), ("pg", "Pg MW", 60), ("qg", "Qg MVAr", 65)])
        self.line_tree = self._make_tree(
            lf, [("ln", "Line", 55), ("st", "State", 55), ("pf", "P from", 60), ("qf", "Q from", 60),
                 ("pt", "P to", 60), ("qt", "Q to", 60), ("ls", "Loss MW", 60), ("ld", "Load %", 60)])

        # log tab
        lg = tk.Frame(self.tabs, bg=BG_MAIN); self.tabs.add(lg, text="Log")
        self.report_box = tk.Text(lg, wrap=tk.WORD, font=("Courier", 10), bg="#FFFFFF",
                                  fg="#000000", bd=1, relief=tk.SOLID, padx=8, pady=8)
        self.report_box.pack(fill=tk.BOTH, expand=True)

    def _make_tree(self, parent, cols):
        frame = tk.Frame(parent, bg=BG_MAIN); frame.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(frame, columns=[c[0] for c in cols], show="headings", height=18)
        for key, text, w in cols:
            tree.heading(key, text=text)
            tree.column(key, width=w, anchor=tk.CENTER)
        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.tag_configure("bad", foreground=COLOR_RED)
        tree.tag_configure("warn", foreground="#C77700")
        tree.tag_configure("off", foreground="#8E8E93")
        return tree

    # ---- button actions ----
    @staticmethod
    def _same(a, b):
        return frozenset(a) == frozenset(b)

    def _is_broken(self, line):
        return any(self._same(line, b) for b in self.broken_lines)

    def _open_line(self, line):
        if not self._is_broken(line):
            self.broken_lines.append(line)

    def _close_line(self, line):
        self.broken_lines = [b for b in self.broken_lines if not self._same(b, line)]

    def trip_selected_line(self):
        self._open_line(IEEE_30_LINES[self.line_selector.current()])
        self.update_simulation()

    def close_selected_line(self):
        self._close_line(IEEE_30_LINES[self.line_selector.current()])
        self.update_simulation()

    def reset_entire_grid(self):
        self.broken_lines, self.tripped_gens = [], []
        self.load_scale.set(100)
        self.update_simulation()

    def trigger_random_storm(self):
        for fault in random.sample(IEEE_30_LINES, random.randint(3, 5)):
            self._open_line(fault)
        self.update_simulation()

    def trigger_infrastructure_attack(self):
        crit = [l for l in IEEE_30_LINES if 4 in l or 6 in l or 12 in l]
        for fault in random.sample(crit, min(len(crit), 4)):
            self._open_line(fault)
        self.update_simulation()

    def toggle_generator(self):
        g = int(self.gen_selector.get().split()[1])
        if g in self.tripped_gens:
            self.tripped_gens.remove(g)
        else:
            self.tripped_gens.append(g)
        self.update_simulation()

    # ---- demos and self-check ----
    TAB_TITLES = {"balance": "Power Balance", "voltage": "Voltages", "loading": "Line Loading"}

    def apply_scenario(self, sc):
        self.broken_lines = [tuple(l) for l in sc["lines"]]
        self.tripped_gens = list(sc["gens"])
        self.load_scale.set(sc["scale"])
        self.update_simulation()
        self.tabs.select(self.tab_frames[self.TAB_TITLES[sc["tab"]]])
        self.banner.config(text=f"{sc['name']}\n{sc['desc']}\n{summarize(self.res)}")

    def run_selected_scenario(self):
        self.stop_demo()
        self.apply_scenario(SCENARIOS[self.scenario_selector.current()])

    def toggle_demo(self):
        if self.demo_job is not None:
            self.stop_demo()
            return
        self.demo_idx = 0
        self.demo_btn.config(text="Stop", bg=COLOR_RED, fg=BG_MAIN)
        self._demo_step()

    def _demo_step(self):
        if self.demo_idx < len(SCENARIOS):
            sc = SCENARIOS[self.demo_idx]
            self.scenario_selector.current(self.demo_idx)
            self.apply_scenario(sc)
            self.banner.config(text=f"[Demo {self.demo_idx + 1} of {len(SCENARIOS)}]  " + self.banner.cget("text"))
            self.demo_idx += 1
            self.demo_job = self.root.after(6000, self._demo_step)
        else:                                   # last step: the N-1 check
            self.reset_entire_grid()
            self.run_n1()
            self.tabs.select(self.tab_frames["N-1 Check"])
            worst = self.n1_rows[0]
            self.banner.config(text="[Demo finished]  Every line cut one at a time on the healthy grid. "
                                    f"Worst single fault: line {worst['line'][0]}-{worst['line'][1]} "
                                    f"(score {worst['severity']:.1f}). Double-click any row to replay it.")
            self.stop_demo()

    def stop_demo(self):
        if self.demo_job is not None:
            self.root.after_cancel(self.demo_job)
        self.demo_job = None
        self.demo_btn.config(text="Play All Demos", bg=BG_CARD, fg=FG_TEXT)

    def show_validation(self):
        checks = run_validation()
        passed = sum(1 for _, p, _ in checks if p)
        win = tk.Toplevel(self.root)
        win.title("Self-check results")
        win.geometry("980x640")
        color = COLOR_GREEN if passed == len(checks) else COLOR_RED
        tk.Label(win, text=f"{passed} / {len(checks)} checks passed", fg=color,
                 font=("Helvetica", 14, "bold")).pack(pady=6)
        tree = self._make_tree(win, [("res", "Result", 70), ("name", "Check", 470), ("det", "Detail", 400)])
        tree.column("name", anchor=tk.W); tree.column("det", anchor=tk.W)
        for name, ok, detail in checks:
            tree.insert("", tk.END, values=("PASS" if ok else "FAIL", name, detail),
                        tags=("" if ok else "bad",))

    def on_map_click(self, event):
        if event.inaxes is not self.ax_map or event.xdata is None:
            return
        k = gp.nearest_line(event.xdata, event.ydata)
        if k is None:
            return
        line = IEEE_30_LINES[k]
        self.line_selector.current(k)
        if self._is_broken(line):
            self._close_line(line)
        else:
            self._open_line(line)
        self.update_simulation()

    def run_n1(self):
        self.n1_rows = run_n1_sweep(self.load_scale.get() / 100.0, self.tripped_gens)
        self.n1_tree.delete(*self.n1_tree.get_children())
        for r in self.n1_rows:
            tag = "bad" if (r["lost"] > 0.05 or r["islands"] > 1) else ("warn" if r["overloads"] else "")
            self.n1_tree.insert("", tk.END, values=(
                f"{r['line'][0]}-{r['line'][1]}", r["islands"], f"{r['lost']:.1f}", r["overloads"],
                f"{r['max_loading']:.0f}", f"{r['min_v']:.3f}", f"{r['severity']:.1f}"), tags=(tag,))

    def apply_n1_row(self, _event):
        sel = self.n1_tree.selection()
        if not sel:
            return
        a, b = self.n1_tree.item(sel[0])["values"][0].split("-")
        self.broken_lines = [(int(a), int(b))]
        self.update_simulation()

    def show_ybus(self):
        Y = build_ybus(self.broken_lines)
        win = tk.Toplevel(self.root)
        win.title("Ybus matrix (pu, 100 MVA base)")
        win.geometry("760x640")
        txt = tk.Text(win, font=("Courier", 9), wrap=tk.NONE)
        sy = ttk.Scrollbar(win, command=txt.yview); txt.configure(yscrollcommand=sy.set)
        sy.pack(side=tk.RIGHT, fill=tk.Y); txt.pack(fill=tk.BOTH, expand=True)
        txt.insert(tk.END, f"Ybus for the CURRENT topology ({len(self.broken_lines)} open breakers)\n"
                           f"Non-zero entries  Y(i,j) = G + jB\n{'=' * 60}\n")
        for i in range(30):
            txt.insert(tk.END, f"\nBus {i + 1}:\n")
            for j in range(30):
                if abs(Y[i, j]) > 1e-9:
                    tag = "diag" if i == j else "off "
                    txt.insert(tk.END, f"  Y({i + 1:2d},{j + 1:2d}) {tag} = {Y[i, j].real:9.4f} {Y[i, j].imag:+9.4f}j\n")
        txt.configure(state=tk.DISABLED)

    def export_csv(self):
        if self.res is None:
            return
        folder = filedialog.askdirectory(title="Choose folder for CSV export")
        if not folder:
            return
        with open(os.path.join(folder, "bus_results.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["bus", "island", "Vm_pu", "angle_deg", "Pd_MW", "served_MW", "Pg_MW", "Qg_MVAr"])
            for b, d in self.res["bus"].items():
                w.writerow([b, d["island"], f"{d['vm']:.4f}", f"{d['va']:.3f}", f"{d['pd']:.2f}",
                            f"{d['served']:.2f}", f"{d['pg']:.2f}", f"{d['qg']:.2f}"])
        with open(os.path.join(folder, "line_results.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["from", "to", "in_service", "P_from", "Q_from", "P_to", "Q_to", "loss_MW", "loading_pct"])
            for l in self.res["lines"]:
                w.writerow([l["f"], l["t"], l["in_service"], f"{l['p_from']:.2f}", f"{l['q_from']:.2f}",
                            f"{l['p_to']:.2f}", f"{l['q_to']:.2f}", f"{l['loss']:.3f}", f"{l['loading']:.1f}"])
        if self.n1_rows:
            with open(os.path.join(folder, "n1_contingency.csv"), "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["line", "islands", "load_lost_MW", "overloaded_lines", "max_loading_pct",
                            "min_voltage_pu", "severity"])
                for r in self.n1_rows:
                    w.writerow([f"{r['line'][0]}-{r['line'][1]}", r["islands"], f"{r['lost']:.2f}",
                                r["overloads"], f"{r['max_loading']:.1f}", f"{r['min_v']:.4f}",
                                f"{r['severity']:.2f}"])
        messagebox.showinfo("Export", f"Results written to:\n{folder}")

    # ---- redraw everything ----
    def update_simulation(self):
        res = solve_system(self.broken_lines, self.load_scale.get() / 100.0, self.tripped_gens)
        self.res = res

        gp.draw_topology(self.ax_map, res, self.color_mode.get())
        self.fig_map.tight_layout(); self.canvas_map.draw()
        gp.draw_balance(self.ax_bal, res); self.fig_bal.tight_layout(); self.cv_bal.draw()
        gp.draw_voltage(self.ax_v, res); self.fig_v.tight_layout(); self.cv_v.draw()
        gp.draw_loading(self.ax_ld, res); self.fig_ld.tight_layout(); self.cv_ld.draw()

        self._fill_tables(res)
        self._fill_log(res)

        t = res["totals"]
        self.status_left.config(
            text=f"Islands: {len(res['islands'])} | Lines cut: {len(self.broken_lines)} | "
                 f"Supplied: {t['served']:.1f} of {t['demand']:.1f} MW | Losses: {t['losses']:.2f} MW")
        codes = {i["code"] for i in res["islands"]}
        viol = res["violations"]
        if codes & {"dead", "collapse"} and t["demand"] - t["served"] > 0.05:
            self.status_right.config(text="STATUS: POWER CUT - LOAD LOST", fg=COLOR_RED)
        elif viol["voltage"] or viol["overload"]:
            self.status_right.config(text="STATUS: WARNING - LIMITS EXCEEDED", fg=COLOR_ORANGE)
        elif "shed" in codes:
            self.status_right.config(text="STATUS: WARNING - LOAD BEING CUT", fg=COLOR_ORANGE)
        elif self.broken_lines or self.tripped_gens or self.load_scale.get() != 100:
            self.status_right.config(text="STATUS: CHANGED - STILL WITHIN LIMITS", fg=COLOR_ORANGE)
        else:
            self.status_right.config(text="STATUS: NORMAL", fg=COLOR_GREEN)

    def _fill_tables(self, res):
        self.bus_tree.delete(*self.bus_tree.get_children())
        for b, d in res["bus"].items():
            tag = "off" if not d["energized"] else ("bad" if d["vm"] < V_MIN or d["vm"] > V_MAX else "")
            self.bus_tree.insert("", tk.END, tags=(tag,), values=(
                b, d["island"], f"{d['vm']:.4f}", f"{d['va']:.2f}", f"{d['pd']:.1f}",
                f"{d['served']:.1f}", f"{d['pg']:.1f}", f"{d['qg']:.1f}"))
        self.line_tree.delete(*self.line_tree.get_children())
        for l in res["lines"]:
            state = "OPEN" if not l["in_service"] else ("ON" if l["energized"] else "DEAD")
            tag = "off" if state != "ON" else ("bad" if l["loading"] > 100 else ("warn" if l["loading"] > 70 else ""))
            self.line_tree.insert("", tk.END, tags=(tag,), values=(
                f"{l['f']}-{l['t']}", state, f"{l['p_from']:.1f}", f"{l['q_from']:.1f}",
                f"{l['p_to']:.1f}", f"{l['q_to']:.1f}", f"{l['loss']:.2f}", f"{l['loading']:.0f}"))

    def _fill_log(self, res):
        t, box = res["totals"], self.report_box
        box.delete("1.0", tk.END)
        w = lambda text: box.insert(tk.END, text + "\n")
        w("SUMMARY")
        w(f"Islands            : {len(res['islands'])}")
        w(f"Lines cut          : {len(self.broken_lines)}  {self.broken_lines or ''}")
        w(f"Generators off     : {self.tripped_gens or 'none'}")
        w(f"Demand level       : {self.load_scale.get():.0f}%")
        w(f"Demand / supplied / cut : {t['demand']:.1f} / {t['served']:.1f} / {t['shed']:.1f} MW")
        w(f"Generation / losses     : {t['gen']:.1f} / {t['losses']:.2f} MW")
        w("=" * 44 + "\n")
        for i in res["islands"]:
            w(f"ISLAND {i['id']}  ({len(i['buses'])} buses)")
            w(f"  Status       : {i['status']}")
            w(f"  Buses        : {i['buses']}")
            if i["slack"] is not None:
                w(f"  Balancing bus: {i['slack']}")
            w(f"  Generation   : {i['gen']:.1f} MW   Demand: {i['demand']:.1f} MW")
            if i["demand"] > 0:
                w(f"  Load cut     : {i['shed']:.1f} MW ({100 * i['shed'] / i['demand']:.0f}%)")
            else:
                w("  Load cut     : 0.0 MW")
            if i["curtailed"] > 0.05:
                w(f"  Gen turned down: {i['curtailed']:.1f} MW")
            w("-" * 44)
        v = res["violations"]
        w("\nPROBLEMS")
        if not v["voltage"] and not v["overload"]:
            w("  none")
        for b, vm in v["voltage"]:
            w(f"  Bus {b:2d} voltage {vm:.3f} pu (allowed {V_MIN}-{V_MAX})")
        for k, ld in v["overload"]:
            l = res["lines"][k]
            w(f"  Line {l['f']}-{l['t']} at {ld:.0f}% of its {l['rating']:.0f} MVA rating")


if __name__ == "__main__":
    window = tk.Tk()
    app = GridSandboxApp(window)
    window.mainloop()
