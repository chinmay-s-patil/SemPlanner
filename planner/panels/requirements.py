"""planner/panels/requirements.py — Credit requirements tracker with sunburst chart.

Changes:
- Total program credits = 120 (95 fixed modules + 25 flexible)
- Overflow logic: credits beyond a module's requirement feed the flexible pool
- New table: Required / Registered / Completed columns, fills horizontal space
- Per-Semester breakdown is collapsible
- Loading indicator (non-blanking spinner)
- Sunburst chart: outer ring = base module, inner ring = sub-module
- all_required flag support (modules where any subcat fills the total)
"""

import math
import tkinter as tk
from tkinter import messagebox

from planner.constants import (
    BG, SURFACE0, SURFACE1, MANTLE, FG, SUBTEXT, OVERLAY,
    ACCENT, GREEN, RED, YELLOW, MAUVE, TEAL, PINK, CRUST,
)
from planner.utils.io_utils import load_data, save_data
from planner.utils.scroll_utils import bind_scroll, rebind_scroll_children

# ── Palette ───────────────────────────────────────────────────────────────────
CHART_COLORS = [ACCENT, GREEN, YELLOW, MAUVE, TEAL, PINK, RED,
                "#FAB387", "#74C7EC", "#B4BEFE"]

# ── Program constants ─────────────────────────────────────────────────────────
TOTAL_PROGRAM_CREDITS = 120   # full program requirement


class RequirementsPanel:
    # ── Column definitions (name, min-width, stretch-weight) ─────────────────
    COL_DEFS = [
        ("Base Module",      140, 0),
        ("Specific Module",  180, 1),   # stretches
        ("Required",          72, 0),
        ("Registered",         72, 0),
        ("Overflow",           72, 0),
        ("Completed",          72, 0),
        ("Remaining",          80, 0),
        ("Progress",          140, 1),   # stretches
    ]
    _NAT_W = sum(w for _, w, _ in COL_DEFS)

    def __init__(self, container: tk.Frame, hub):
        self.hub       = hub
        self.frame     = tk.Frame(container, bg=BG)
        self.data_file = hub.data_file
        self.data: dict = {}
        self._sem_collapsed: dict = {}  # semester_name → bool collapsed
        self._loading = False
        self._build_ui()

    def reload(self):
        self._show_loading(True)
        self.frame.after(50, self._do_reload)

    def _do_reload(self):
        try:
            self.data = load_data(self.data_file)
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))
            self.data = {"requirements": {}, "semesters": []}
        self._show_loading(False)
        self._refresh()

    def _show_loading(self, state: bool):
        self._loading = state
        if state:
            for w in self.summary_bar.winfo_children():
                w.destroy()
            spinner = tk.Label(
                self.summary_bar,
                text="⟳  Loading…",
                bg=MANTLE, fg=ACCENT,
                font=("Segoe UI", 10, "bold"))
            spinner.pack(side=tk.LEFT, padx=14, pady=6)
            self._animate_spinner(spinner, 0)
        # If False, the actual _refresh() will repopulate summary_bar

    def _animate_spinner(self, lbl, tick):
        if not self._loading:
            return
        symbols = ["⟳", "↻", "⟲", "↺"]
        lbl.configure(text=f"{symbols[tick % 4]}  Loading…")
        lbl.after(120, lambda: self._animate_spinner(lbl, tick + 1))

    # ── Core compute ──────────────────────────────────────────────────────────
    def _compute(self):
        """Return (modules_dict, flexible_dict, grand_fixed_required)."""
        req_cfg = self.data.get("requirements", {})

        grand_fixed_req = sum(cfg.get("total_required", 0)
                              for cfg in req_cfg.values())
        flexible_required = max(0, TOTAL_PROGRAM_CREDITS - grand_fixed_req)

        # Build module structure
        modules: dict = {}
        for base, cfg in req_cfg.items():
            tot_req  = cfg.get("total_required", 0)
            subs_cfg = cfg.get("subcategories", {})
            all_req  = cfg.get("all_required", False)

            sub_data: dict = {}
            for sub, scfg in subs_cfg.items():
                sub_data[sub] = {
                    "required":   scfg.get("required_credits", 0),
                    "registered": 0,
                    "completed":  0,
                }

            modules[base] = {
                "required":    tot_req,
                "all_required": all_req,
                "registered":  0,
                "completed":   0,
                "subcategories": sub_data,
            }

        # Populate from courses in all semesters
        for sem in self.data.get("semesters", []):
            for course in sem.get("courses", []):
                base     = course.get("base_module", "")
                specific = course.get("specific_module", "")
                credits  = course.get("credits", 0)
                exam     = course.get("exam_given", False)

                if base in modules:
                    modules[base]["registered"] += credits
                    if exam:
                        modules[base]["completed"] += credits
                    if specific in modules[base]["subcategories"]:
                        modules[base]["subcategories"][specific]["registered"] += credits
                        if exam:
                            modules[base]["subcategories"][specific]["completed"] += credits

        # Overflow: credits beyond module requirement go to flexible pool
        total_overflow_reg  = 0
        total_overflow_comp = 0
        for mdata in modules.values():
            mdata["overflow_reg"]  = max(0, mdata["registered"] - mdata["required"])
            mdata["overflow_comp"] = max(0, mdata["completed"]  - mdata["required"])
            total_overflow_reg  += mdata["overflow_reg"]
            total_overflow_comp += mdata["overflow_comp"]

        flexible = {
            "required":    flexible_required,
            "registered":  min(total_overflow_reg,  flexible_required),
            "completed":   min(total_overflow_comp, flexible_required),
            "excess_reg":  max(0, total_overflow_reg  - flexible_required),
            "excess_comp": max(0, total_overflow_comp - flexible_required),
        }
        flexible["remaining"] = max(0, flexible_required - flexible["completed"])

        return modules, flexible, grand_fixed_req

    # ── UI skeleton ───────────────────────────────────────────────────────────
    def _build_ui(self):
        topbar = tk.Frame(self.frame, bg=MANTLE, height=52)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)
        tk.Label(topbar, text="  📋  Requirements Tracker",
                 bg=MANTLE, fg=FG,
                 font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT, padx=14, pady=12)
        self._btn(topbar, "🔄  Refresh",
                  SURFACE1, FG, self.reload).pack(side=tk.RIGHT, padx=8, pady=12)
        self._btn(topbar, "💾  Save",
                  SURFACE1, FG, self._save).pack(side=tk.RIGHT, padx=0, pady=12)

        self.summary_bar = tk.Frame(self.frame, bg=MANTLE, pady=8)
        self.summary_bar.pack(fill=tk.X)

        wrap = tk.Frame(self.frame, bg=BG)
        wrap.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        vsb = tk.Scrollbar(wrap, orient=tk.VERTICAL, bg=SURFACE1,
                           troughcolor=SURFACE0, relief=tk.FLAT,
                           highlightthickness=0)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = tk.Scrollbar(wrap, orient=tk.HORIZONTAL, bg=SURFACE1,
                           troughcolor=SURFACE0, relief=tk.FLAT,
                           highlightthickness=0)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0,
                                yscrollcommand=vsb.set,
                                xscrollcommand=hsb.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.configure(command=self.canvas.yview)
        hsb.configure(command=self.canvas.xview)

        self.content = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Configure>",  self._on_resize)
        bind_scroll(self.canvas, h_canvas=self.canvas)

    def _on_resize(self, _=None):
        cw = self.canvas.winfo_width()
        self.canvas.itemconfigure(self._win, width=max(cw, self._NAT_W + 4))
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _save(self):
        try:
            save_data(self.data, self.data_file)
            # Brief flash in summary bar
            orig = self.summary_bar.cget("bg")
            self.summary_bar.configure(bg="#1a3a1a")
            self.summary_bar.after(400, lambda: self.summary_bar.configure(bg=MANTLE))
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex))

    # ── Main refresh ──────────────────────────────────────────────────────────
    def _refresh(self):
        modules, flexible, grand_fixed_req = self._compute()

        grand_required   = TOTAL_PROGRAM_CREDITS
        grand_registered = sum(m["registered"] for m in modules.values())
        grand_completed  = sum(m["completed"]  for m in modules.values())
        grand_remaining  = max(0, grand_required - grand_completed
                               - flexible["completed"])
        pct = int((grand_completed + flexible["completed"])
                  / grand_required * 100) if grand_required else 0

        # Store for chart
        self._modules         = modules
        self._flexible        = flexible
        self._grand_completed = grand_completed + flexible["completed"]

        for w in self.content.winfo_children():
            w.destroy()

        # ── Top-level two-column layout ───────────────────────────────────────
        root_frame = tk.Frame(self.content, bg=BG)
        root_frame.pack(fill=tk.BOTH, expand=True)

        self._table_col = tk.Frame(root_frame, bg=BG)
        self._table_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._chart_col = tk.Frame(root_frame, bg=SURFACE0, width=310)
        self._chart_col.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 6), pady=6)
        self._chart_col.pack_propagate(False)

        # ── Build chart (right) ───────────────────────────────────────────────
        self._render_chart_section(self._chart_col, modules, flexible)

        # ── Build table (left) ────────────────────────────────────────────────
        self._render_main_table(modules, flexible)

        # ── Per-semester breakdown ────────────────────────────────────────────
        self._render_semester_breakdown()

        # ── Summary bar ──────────────────────────────────────────────────────
        self._refresh_summary(grand_completed + flexible["completed"],
                              grand_required, pct,
                              grand_remaining + flexible["remaining"])

        rebind_scroll_children(self.canvas, self.content, h_canvas=self.canvas)
        self._on_resize()

    def _refresh_summary(self, completed, required, pct, remaining):
        for w in self.summary_bar.winfo_children():
            w.destroy()
        tk.Label(self.summary_bar, text="  Total Progress:",
                 bg=MANTLE, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        pb = tk.Frame(self.summary_bar, bg=SURFACE1, height=14, width=300)
        pb.pack(side=tk.LEFT, padx=10, pady=2)
        pb.pack_propagate(False)
        if pct:
            tk.Frame(pb, bg=GREEN, width=int(300 * pct / 100)).pack(
                side=tk.LEFT, fill=tk.Y)
        tk.Label(self.summary_bar,
                 text=f"{completed} / {required} ECTS  ({pct}%)",
                 bg=MANTLE, fg=FG,
                 font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(self.summary_bar,
                 text=f"   {remaining} ECTS remaining",
                 bg=MANTLE,
                 fg=YELLOW if remaining > 0 else GREEN,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=8)

    # ── Main table ────────────────────────────────────────────────────────────
    def _render_main_table(self, modules, flexible):
        sep = tk.Frame(self._table_col, bg=SURFACE1, height=2)
        sep.pack(fill=tk.X)

        tbl = tk.Frame(self._table_col, bg=BG)
        tbl.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        num_cols = len(self.COL_DEFS)
        for ci, (_, w, wt) in enumerate(self.COL_DEFS):
            tbl.columnconfigure(ci, minsize=w, weight=wt)

        gr = 0

        # ── Header ────────────────────────────────────────────────────────────
        for ci, (label, w, _) in enumerate(self.COL_DEFS):
            tk.Label(tbl, text=label, bg=SURFACE0, fg=ACCENT,
                     font=("Segoe UI", 9, "bold"),
                     pady=8, padx=6, anchor="center",
                     wraplength=max(w - 8, 30),
                     justify=tk.CENTER,
                     ).grid(row=gr, column=ci, sticky="nsew", padx=1)
        gr += 1
        tk.Frame(tbl, bg=ACCENT, height=2).grid(
            row=gr, column=0, columnspan=num_cols, sticky="ew")
        gr += 1

        row_idx = 0
        for i, (base, mdata) in enumerate(modules.items()):
            color = CHART_COLORS[i % len(CHART_COLORS)]
            # Section header
            sh = tk.Frame(tbl, bg=SURFACE1, pady=2)
            sh.grid(row=gr, column=0, columnspan=num_cols, sticky="ew", pady=(6, 0))
            tk.Label(sh, text=f"  {base}", bg=SURFACE1, fg=color,
                     font=("Segoe UI", 10, "bold"), pady=3).pack(side=tk.LEFT)
            req_lbl = tk.Label(sh, text=f"Required: {mdata['required']} ECTS",
                               bg=SURFACE1, fg=SUBTEXT, font=("Segoe UI", 8))
            req_lbl.pack(side=tk.RIGHT, padx=12)
            gr += 1

            all_req  = mdata.get("all_required", False)
            subs     = mdata["subcategories"]

            if not subs or all_req:
                # Single row for this module
                gr = self._table_row(tbl, gr, row_idx, "",
                                     "Any combination" if all_req else base,
                                     mdata["required"],
                                     min(mdata["registered"], mdata["required"]),
                                     mdata["overflow_reg"],
                                     min(mdata["completed"], mdata["required"]),
                                     color, SURFACE0 if row_idx % 2 == 0 else BG)
                row_idx += 1
            else:
                for sub, sdata in subs.items():
                    sub_reg  = min(sdata["registered"], sdata["required"]) if sdata["required"] > 0 else sdata["registered"]
                    sub_over = max(0, sdata["registered"] - sdata["required"]) if sdata["required"] > 0 else 0
                    sub_comp = min(sdata["completed"], sdata["required"]) if sdata["required"] > 0 else sdata["completed"]
                    gr = self._table_row(tbl, gr, row_idx, "",
                                         sub, sdata["required"], sub_reg,
                                         sub_over, sub_comp,
                                         color, SURFACE0 if row_idx % 2 == 0 else BG)
                    row_idx += 1

            # Module total row
            mod_reg_eff  = min(mdata["registered"], mdata["required"])
            mod_comp_eff = min(mdata["completed"],  mdata["required"])
            mod_remain   = max(0, mdata["required"] - mdata["completed"])
            sf = tk.Frame(tbl, bg=MANTLE)
            sf.grid(row=gr, column=0, columnspan=num_cols, sticky="ew")
            for ci, (text, w_hint, _) in enumerate(self.COL_DEFS):
                if ci == 0:
                    t = ""
                elif ci == 1:
                    t = f"  ↳ {base} total"
                elif ci == 2:
                    t = str(mdata["required"])
                elif ci == 3:
                    t = str(mod_reg_eff)
                elif ci == 4:
                    t = str(mdata["overflow_reg"])
                elif ci == 5:
                    t = str(mod_comp_eff)
                elif ci == 6:
                    t = str(mod_remain)
                else:
                    t = ""
                fg_c = (GREEN if ci == 6 and mod_remain <= 0
                        else RED if ci == 6 and mod_remain > 0
                        else color if ci == 1
                        else FG)
                tk.Label(sf, text=t, bg=MANTLE, fg=fg_c,
                         font=("Segoe UI", 8, "bold"),
                         pady=3, padx=6, anchor="w",
                         ).grid(row=0, column=ci, sticky="nsew", padx=1)
                sf.columnconfigure(ci, minsize=self.COL_DEFS[ci][1],
                                   weight=self.COL_DEFS[ci][2])
            gr += 1

        # ── Flexible row ──────────────────────────────────────────────────────
        sh = tk.Frame(tbl, bg=SURFACE1, pady=2)
        sh.grid(row=gr, column=0, columnspan=num_cols, sticky="ew", pady=(6, 0))
        tk.Label(sh, text="  ✦  Flexible Credits",
                 bg=SURFACE1, fg=TEAL,
                 font=("Segoe UI", 10, "bold"), pady=3).pack(side=tk.LEFT)
        tk.Label(sh,
                 text=f"Required: {flexible['required']} ECTS  (overflow from other modules)",
                 bg=SURFACE1, fg=SUBTEXT,
                 font=("Segoe UI", 8)).pack(side=tk.RIGHT, padx=12)
        gr += 1

        flex_remain = flexible["remaining"]
        gr = self._table_row(tbl, gr, row_idx, "",
                              "Overflow → Flexible Pool",
                              flexible["required"],
                              flexible["registered"],
                              flexible.get("excess_reg", 0),
                              flexible["completed"],
                              TEAL, SURFACE0)
        row_idx += 1

        # ── Grand total ───────────────────────────────────────────────────────
        tk.Frame(tbl, bg=ACCENT, height=2).grid(
            row=gr, column=0, columnspan=num_cols, sticky="ew", pady=6)
        gr += 1

        grand_req  = TOTAL_PROGRAM_CREDITS
        grand_reg  = sum(min(m["registered"], m["required"])
                         for m in modules.values()) + flexible["registered"]
        grand_comp = sum(min(m["completed"],  m["required"])
                         for m in modules.values()) + flexible["completed"]
        grand_over = sum(m["overflow_reg"] for m in modules.values())
        grand_rem  = max(0, grand_req - grand_comp - flexible["completed"])

        tot = tk.Frame(tbl, bg=SURFACE0)
        tot.grid(row=gr, column=0, columnspan=num_cols, sticky="ew")
        for ci, (_, w_hint, _) in enumerate(self.COL_DEFS):
            if ci == 1:
                t = "  GRAND TOTAL"
            elif ci == 2:
                t = str(grand_req)
            elif ci == 3:
                t = str(grand_reg)
            elif ci == 4:
                t = str(grand_over)
            elif ci == 5:
                t = str(grand_comp)
            elif ci == 6:
                t = str(grand_rem)
            else:
                t = ""
            fg_c = (ACCENT if ci == 1
                    else GREEN if ci == 6 and grand_rem <= 0
                    else RED   if ci == 6
                    else FG)
            tk.Label(tot, text=t, bg=SURFACE0, fg=fg_c,
                     font=("Segoe UI", 10, "bold"),
                     pady=6, padx=6, anchor="w",
                     ).grid(row=0, column=ci, sticky="nsew", padx=1)
            tot.columnconfigure(ci, minsize=self.COL_DEFS[ci][1],
                                weight=self.COL_DEFS[ci][2])

    def _table_row(self, tbl, gr, row_idx, base, specific,
                   required, registered, overflow, completed,
                   color, bg_c):
        remaining = max(0, required - completed)
        pct_done  = int(completed / required * 100) if required else 0

        row_f = tk.Frame(tbl, bg=bg_c)
        row_f.grid(row=gr, column=0, columnspan=len(self.COL_DEFS),
                   sticky="nsew", padx=0)

        texts = [base, specific, str(required), str(registered),
                 str(overflow), str(completed), str(remaining), ""]

        for ci, (text, w_hint, wt) in enumerate(self.COL_DEFS):
            val = texts[ci]
            if ci == 7:
                # Progress bar cell
                pb_host = tk.Frame(row_f, bg=bg_c, height=26)
                pb_host.grid(row=0, column=ci, sticky="nsew", padx=6, pady=4)
                pb_host.pack_propagate(False)
                bar_bg = tk.Frame(pb_host, bg=SURFACE1, height=10)
                bar_bg.pack(fill=tk.X, expand=True, side=tk.LEFT, pady=8)
                bar_bg.pack_propagate(False)
                if pct_done:
                    bar_fill = tk.Frame(bar_bg, bg=color, height=10)
                    bar_fill.place(x=0, y=0, relwidth=min(pct_done / 100, 1),
                                   relheight=1)
                tk.Label(pb_host, text=f"{pct_done}%", bg=bg_c, fg=SUBTEXT,
                         font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(4, 0))
            else:
                fg_c = (color     if ci == 1 and val
                        else RED   if ci == 6 and remaining > 0 and required > 0
                        else GREEN if ci == 6 and required > 0
                        else YELLOW if ci == 4 and overflow > 0
                        else FG)
                tk.Label(row_f, text=val, bg=bg_c, fg=fg_c,
                         font=("Segoe UI", 9),
                         pady=5, padx=6, anchor="w",
                         ).grid(row=0, column=ci, sticky="nsew", padx=1)
            row_f.columnconfigure(ci, minsize=self.COL_DEFS[ci][1],
                                  weight=self.COL_DEFS[ci][2])
        return gr + 1

    # ── Chart section (right column) ──────────────────────────────────────────
    def _render_chart_section(self, parent, modules, flexible):
        SIZE = 280

        chart_hdr = tk.Frame(parent, bg=SURFACE0, pady=8)
        chart_hdr.pack(fill=tk.X)
        tk.Label(chart_hdr, text="  Credit Map",
                 bg=SURFACE0, fg=FG,
                 font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)

        # ── Sunburst canvas ───────────────────────────────────────────────────
        chart_top = tk.Frame(parent, bg=SURFACE0)
        chart_top.pack(pady=(10, 4))
        self._donut_canvas = tk.Canvas(chart_top, width=SIZE, height=SIZE,
                                        bg=SURFACE0, highlightthickness=0)
        self._donut_canvas.pack()

        # ── Mode nav ──────────────────────────────────────────────────────────
        nav_row = tk.Frame(parent, bg=SURFACE0)
        nav_row.pack(fill=tk.X, padx=10, pady=(4, 0))

        self._chart_views = [
            {"title": "Required Allocation",  "mode": "required"},
            {"title": "Registration Status",  "mode": "registered"},
            {"title": "Completion Progress",  "mode": "completed"},
        ]
        self._chart_mode = 0

        tk.Label(nav_row, text="◀", bg=SURFACE0, fg=ACCENT,
                 font=("Segoe UI", 13, "bold"), cursor="hand2",
                 ).pack(side=tk.LEFT, padx=(0, 6))
        self._nav_btns_left = nav_row.winfo_children()[-1]
        self._nav_btns_left.bind("<Button-1>", lambda e: self._cycle_chart(-1))

        self._chart_title_lbl = tk.Label(nav_row, text="",
                                          bg=SURFACE0, fg=FG,
                                          font=("Segoe UI", 10, "bold"))
        self._chart_title_lbl.pack(side=tk.LEFT)

        tk.Label(nav_row, text="▶", bg=SURFACE0, fg=ACCENT,
                 font=("Segoe UI", 13, "bold"), cursor="hand2",
                 ).pack(side=tk.LEFT, padx=(6, 0))
        self._nav_btns_right = nav_row.winfo_children()[-1]
        self._nav_btns_right.bind("<Button-1>", lambda e: self._cycle_chart(1))

        # Dot indicators
        dot_row = tk.Frame(parent, bg=SURFACE0)
        dot_row.pack(pady=(4, 8))
        self._dot_labels = []
        for i in range(len(self._chart_views)):
            d = tk.Label(dot_row, text="●", bg=SURFACE0,
                         fg=ACCENT if i == 0 else OVERLAY,
                         font=("Segoe UI", 9), cursor="hand2")
            d.pack(side=tk.LEFT, padx=2)
            d.bind("<Button-1>", lambda e, idx=i: self._goto_chart(idx))
            self._dot_labels.append(d)

        # Legend
        sep = tk.Frame(parent, bg=SURFACE1, height=1)
        sep.pack(fill=tk.X, padx=8, pady=(0, 6))

        self._legend_frame = tk.Frame(parent, bg=SURFACE0)
        self._legend_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        # Stats strip
        stats_frame = tk.Frame(parent, bg=SURFACE0)
        stats_frame.pack(fill=tk.X, padx=8, pady=(0, 10))

        grand_comp = sum(min(m["completed"], m["required"]) for m in modules.values())
        grand_comp += flexible["completed"]
        grand_reg  = sum(min(m["registered"], m["required"]) for m in modules.values())
        grand_reg  += flexible["registered"]

        for lbl, val, clr in [
            ("Required",   str(TOTAL_PROGRAM_CREDITS), SUBTEXT),
            ("Registered", str(grand_reg),              ACCENT),
            ("Earned",     str(grand_comp),             GREEN),
            ("Remaining",  str(max(0, TOTAL_PROGRAM_CREDITS - grand_comp)),
             YELLOW if grand_comp < TOTAL_PROGRAM_CREDITS else GREEN),
        ]:
            sf = tk.Frame(stats_frame, bg=SURFACE0)
            sf.pack(side=tk.LEFT, padx=(0, 12))
            tk.Label(sf, text=lbl,        bg=SURFACE0, fg=OVERLAY,
                     font=("Segoe UI", 7)).pack(anchor="w")
            tk.Label(sf, text=val + " ECTS", bg=SURFACE0, fg=clr,
                     font=("Segoe UI", 10, "bold")).pack(anchor="w")

        self._draw_sunburst()

    def _cycle_chart(self, d):
        self._chart_mode = (self._chart_mode + d) % len(self._chart_views)
        self._draw_sunburst()

    def _goto_chart(self, idx):
        self._chart_mode = idx
        self._draw_sunburst()

    def _draw_sunburst(self):
        canvas = self._chart_views  # just to get mode
        mode   = self._chart_views[self._chart_mode]["mode"]
        title  = self._chart_views[self._chart_mode]["title"]

        self._chart_title_lbl.configure(text=title)
        for i, d in enumerate(self._dot_labels):
            d.configure(fg=ACCENT if i == self._chart_mode else OVERLAY)

        cv     = self._donut_canvas
        SIZE   = 280
        CX = CY = SIZE // 2

        OUTER_R1 = 86   # base module ring
        OUTER_R2 = 116
        INNER_R1 = 48   # sub-module ring
        INNER_R2 = 83

        cv.delete("all")

        # Background
        cv.create_oval(CX - OUTER_R2, CY - OUTER_R2,
                       CX + OUTER_R2, CY + OUTER_R2,
                       fill=SURFACE1, outline="")

        modules = self._modules
        flexible = self._flexible
        req_cfg = self.data.get("requirements", {})

        # Total for proportioning
        total_for_chart = TOTAL_PROGRAM_CREDITS

        start = 90.0
        legend_items = []

        for i, (base, mdata) in enumerate(modules.items()):
            color     = CHART_COLORS[i % len(CHART_COLORS)]
            base_val  = self._chart_val(mdata, mode, is_module=True)
            if base_val <= 0:
                continue

            extent = base_val / total_for_chart * 360

            # ── Outer ring: base module ───────────────────────────────────────
            self._ring_wedge(cv, CX, CY, OUTER_R1, OUTER_R2, start, extent, color)
            self._ring_sep(cv, CX, CY, OUTER_R1, OUTER_R2, start)

            # ── Inner ring: sub modules ───────────────────────────────────────
            cfg      = req_cfg.get(base, {})
            subs     = cfg.get("subcategories", {})
            all_req  = cfg.get("all_required", False)

            if not subs or all_req:
                dark = self._hex_blend(color, SURFACE0, 0.5)
                self._ring_wedge(cv, CX, CY, INNER_R1, INNER_R2, start, extent, dark)
                self._ring_sep(cv, CX, CY, INNER_R1, INNER_R2, start)
            else:
                sub_start = start
                sub_vals  = {s: self._chart_val_sub(
                    mdata["subcategories"].get(s, {}),
                    scfg, mode)
                    for s, scfg in subs.items()}
                sub_total = sum(sub_vals.values())
                if sub_total <= 0:
                    sub_total = 1

                for j, (sub, scfg) in enumerate(subs.items()):
                    sv = sub_vals[sub]
                    if sv <= 0:
                        continue
                    sub_extent = sv / sub_total * extent
                    alpha = 0.35 + 0.45 * (j / max(len(subs) - 1, 1))
                    sub_c = self._hex_blend(color, SURFACE0, alpha)
                    self._ring_wedge(cv, CX, CY, INNER_R1, INNER_R2,
                                     sub_start, sub_extent, sub_c)
                    self._ring_sep(cv, CX, CY, INNER_R1, INNER_R2, sub_start)
                    sub_start += sub_extent

            legend_items.append((base, color, base_val, mdata["required"]))
            start += extent

        # Flexible slice
        flex_val = self._chart_val(flexible, mode, is_module=False)
        if flex_val > 0:
            flex_ext = flex_val / total_for_chart * 360
            self._ring_wedge(cv, CX, CY, OUTER_R1, OUTER_R2, start, flex_ext, TEAL)
            self._ring_sep(cv, CX, CY, OUTER_R1, OUTER_R2, start)
            dark_teal = self._hex_blend(TEAL, SURFACE0, 0.5)
            self._ring_wedge(cv, CX, CY, INNER_R1, INNER_R2, start, flex_ext, dark_teal)
            legend_items.append(("Flexible", TEAL, flex_val, flexible["required"]))

        # Center circle + text
        cv.create_oval(CX - INNER_R1 + 2, CY - INNER_R1 + 2,
                       CX + INNER_R1 - 2, CY + INNER_R1 - 2,
                       fill=SURFACE0, outline="")

        pct = int(self._grand_completed / TOTAL_PROGRAM_CREDITS * 100) \
              if TOTAL_PROGRAM_CREDITS else 0
        cv.create_text(CX, CY - 9,  text=f"{pct}%",
                       fill=FG, font=("Segoe UI", 15, "bold"))
        cv.create_text(CX, CY + 9,  text="Earned",
                       fill=SUBTEXT, font=("Segoe UI", 8))

        # Legend
        for w in self._legend_frame.winfo_children():
            w.destroy()
        for (name, color, val, req) in legend_items:
            row = tk.Frame(self._legend_frame, bg=SURFACE0)
            row.pack(fill=tk.X, pady=1)
            tk.Frame(row, bg=color, width=10, height=10).pack(
                side=tk.LEFT, padx=(0, 6))
            pct_str = f"{int(val / req * 100)}%" if req > 0 else "—"
            tk.Label(row, text=f"{name}  ({val}/{req}  {pct_str})",
                     bg=SURFACE0, fg=FG,
                     font=("Segoe UI", 8)).pack(side=tk.LEFT)

    # ── Sunburst helpers ──────────────────────────────────────────────────────
    def _chart_val(self, mdata, mode, is_module=True):
        if mode == "required":
            return mdata["required"]
        if mode == "registered":
            if is_module:
                return min(mdata["registered"], mdata["required"])
            return mdata["registered"]
        if mode == "completed":
            if is_module:
                return min(mdata["completed"], mdata["required"])
            return mdata["completed"]
        return mdata["required"]

    def _chart_val_sub(self, sdata, scfg, mode):
        if mode == "required":
            return scfg.get("required_credits", 0)
        if mode == "registered":
            return sdata.get("registered", 0)
        if mode == "completed":
            return sdata.get("completed", 0)
        return scfg.get("required_credits", 0)

    def _ring_wedge(self, cv, cx, cy, r1, r2, start_deg, extent_deg, color):
        """Draw a filled ring wedge (annular sector) using polygon approximation."""
        if extent_deg <= 0:
            return
        steps = max(int(abs(extent_deg) / 2), 6)
        outer_pts = []
        inner_pts = []
        for i in range(steps + 1):
            ang = math.radians(start_deg + extent_deg * i / steps)
            outer_pts.append((cx + r2 * math.cos(ang),
                               cy - r2 * math.sin(ang)))
            inner_pts.append((cx + r1 * math.cos(ang),
                               cy - r1 * math.sin(ang)))
        pts = outer_pts + list(reversed(inner_pts))
        flat = [c for p in pts for c in p]
        if len(flat) >= 6:
            cv.create_polygon(flat, fill=color, outline="")

    def _ring_sep(self, cv, cx, cy, r1, r2, angle_deg):
        """Draw a thin separator line at the given angle."""
        ang = math.radians(angle_deg)
        x1 = cx + r1 * math.cos(ang)
        y1 = cy - r1 * math.sin(ang)
        x2 = cx + r2 * math.cos(ang)
        y2 = cy - r2 * math.sin(ang)
        cv.create_line(x1, y1, x2, y2, fill=SURFACE0, width=2)

    def _hex_blend(self, c1: str, c2: str, a: float) -> str:
        c1 = c1.lstrip("#")
        c2 = c2.lstrip("#")
        r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
        r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
        return "#{:02x}{:02x}{:02x}".format(
            int(r1 * a + r2 * (1 - a)),
            int(g1 * a + g2 * (1 - a)),
            int(b1 * a + b2 * (1 - a)))

    # ── Semester breakdown ────────────────────────────────────────────────────
    def _render_semester_breakdown(self):
        sep = tk.Frame(self._table_col, bg=SURFACE1, height=2)
        sep.pack(fill=tk.X, padx=8, pady=(16, 0))

        hdr_row = tk.Frame(self._table_col, bg=BG)
        hdr_row.pack(fill=tk.X, padx=8, pady=(4, 2))
        tk.Label(hdr_row, text="  📆  Per-Semester Credit Breakdown",
                 bg=BG, fg=MAUVE,
                 font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)

        container = tk.Frame(self._table_col, bg=BG)
        container.pack(fill=tk.X, padx=8, pady=(0, 12))

        for sem in self.data.get("semesters", []):
            self._render_sem_row(container, sem)

    def _render_sem_row(self, container, sem):
        name     = sem.get("display_name", sem["name"])
        sem_key  = sem["name"]
        courses  = sem.get("courses", [])
        total    = sum(c.get("credits", 0) for c in courses)
        done     = sum(c.get("credits", 0) for c in courses if c.get("exam_given"))
        pct      = int(done / total * 100) if total else 0
        collapsed = self._sem_collapsed.get(sem_key, False)

        outer = tk.Frame(container, bg=SURFACE0, pady=0)
        outer.pack(fill=tk.X, pady=3)

        # ── Header row ────────────────────────────────────────────────────────
        hdr = tk.Frame(outer, bg=SURFACE0, pady=6)
        hdr.pack(fill=tk.X)

        arrow_sym = "▶" if collapsed else "▼"
        arrow = tk.Label(hdr, text=arrow_sym, bg=SURFACE0, fg=ACCENT,
                         font=("Segoe UI", 9, "bold"), cursor="hand2")
        arrow.pack(side=tk.LEFT, padx=(8, 4))

        tk.Label(hdr, text=name, bg=SURFACE0, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(hdr, text=f"  {done}/{total} ECTS  ({pct}%)",
                 bg=SURFACE0, fg=FG,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=6)

        # Progress bar
        pb = tk.Frame(hdr, bg=SURFACE1, height=8, width=120)
        pb.pack(side=tk.LEFT, padx=8)
        pb.pack_propagate(False)
        if pct:
            tk.Frame(pb, bg=GREEN, width=int(120 * pct / 100)).pack(
                side=tk.LEFT, fill=tk.Y)

        # Module badges
        by_base: dict = {}
        for c in courses:
            b = c.get("base_module", "Other")
            by_base.setdefault(b, {"done": 0, "total": 0})
            by_base[b]["total"] += c.get("credits", 0)
            if c.get("exam_given"):
                by_base[b]["done"] += c.get("credits", 0)
        badge_frame = tk.Frame(hdr, bg=SURFACE0)
        badge_frame.pack(side=tk.RIGHT, padx=8)
        for b, v in by_base.items():
            tk.Label(badge_frame,
                     text=f"{b[:10]}: {v['done']}/{v['total']}",
                     bg=SURFACE0, fg=SUBTEXT,
                     font=("Segoe UI", 7)).pack(side=tk.LEFT, padx=3)

        # ── Detail frame (collapsible) ────────────────────────────────────────
        detail = tk.Frame(outer, bg=BG)
        if not collapsed:
            detail.pack(fill=tk.X)
            self._render_sem_detail(detail, courses)

        def toggle(_e=None):
            self._sem_collapsed[sem_key] = not self._sem_collapsed.get(sem_key, False)
            if self._sem_collapsed[sem_key]:
                detail.pack_forget()
                arrow.configure(text="▶")
            else:
                detail.pack(fill=tk.X)
                self._render_sem_detail(detail, courses)
                arrow.configure(text="▼")
            rebind_scroll_children(self.canvas, self.content, h_canvas=self.canvas)
            self._on_resize()

        for w in (arrow, hdr):
            w.bind("<Button-1>", toggle)

    def _render_sem_detail(self, parent, courses):
        for w in parent.winfo_children():
            w.destroy()
        if not courses:
            tk.Label(parent, text="  No courses.", bg=BG, fg=OVERLAY,
                     font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=4)
            return

        # Mini-table
        mini_cols = [("Course", 220, 1), ("Base", 130, 0),
                     ("Credits", 58, 0), ("✓", 36, 0), ("Obtained", 66, 0)]
        tbl = tk.Frame(parent, bg=BG)
        tbl.pack(fill=tk.X, padx=10, pady=(2, 6))
        for ci, (lbl, w, wt) in enumerate(mini_cols):
            tbl.columnconfigure(ci, minsize=w, weight=wt)
            tk.Label(tbl, text=lbl, bg=SURFACE1, fg=ACCENT,
                     font=("Segoe UI", 8, "bold"),
                     pady=4, padx=4).grid(row=0, column=ci, sticky="nsew", padx=1)

        for ri, c in enumerate(courses):
            bg_c = SURFACE0 if ri % 2 == 0 else BG
            exam = c.get("exam_given", False)
            obtained = c.get("credits", 0) if exam else 0
            texts = [c.get("name", ""), c.get("base_module", ""),
                     str(c.get("credits", 0)), "✓" if exam else "—",
                     str(obtained)]
            for ci, (_, _, _) in enumerate(mini_cols):
                fg_c = (GREEN if ci == 3 and exam
                        else RED if ci == 3
                        else FG)
                tk.Label(tbl, text=texts[ci], bg=bg_c, fg=fg_c,
                         font=("Segoe UI", 8),
                         pady=4, padx=4, anchor="w",
                         ).grid(row=ri + 1, column=ci, sticky="nsew", padx=1)

    # ── Widget helpers ────────────────────────────────────────────────────────
    def _btn(self, parent, text, bg, fg, cmd):
        return tk.Button(parent, text=text, bg=bg, fg=fg,
                         font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
                         cursor="hand2", padx=10, pady=4,
                         activebackground=SURFACE1, activeforeground=FG,
                         bd=0, command=cmd)