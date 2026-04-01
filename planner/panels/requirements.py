"""planner/panels/requirements.py — Credit requirements tracker with donut chart."""

import math
import tkinter as tk
from tkinter import messagebox

from planner.constants import (
    BG, SURFACE0, SURFACE1, MANTLE, FG, SUBTEXT, OVERLAY,
    ACCENT, GREEN, RED, YELLOW, MAUVE, TEAL, PINK, CRUST,
)
from planner.utils.io_utils import load_data
from planner.utils.scroll_utils import bind_scroll, rebind_scroll_children

# ── Donut chart colour palette ────────────────────────────────────────────────
CHART_COLORS = [ACCENT, GREEN, YELLOW, MAUVE, TEAL, PINK, RED,
                "#FAB387", "#74C7EC", "#B4BEFE"]


class RequirementsPanel:
    def __init__(self, container: tk.Frame, hub):
        self.hub       = hub
        self.frame     = tk.Frame(container, bg=BG)
        self.data_file = hub.data_file
        self.data: dict = {}
        self._chart_mode = 0          # 0-3 cycles through chart views
        self._build_ui()

    def reload(self):
        try:
            self.data = load_data(self.data_file)
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))
            self.data = {"requirements": {}, "semesters": []}
        self._refresh()

    # ── Compute credits ───────────────────────────────────────────────────────
    def _compute(self):
        req_cfg = self.data.get("requirements", {})
        result: dict = {}
        for base, cfg in req_cfg.items():
            result[base] = {}
            for specific, scfg in cfg.get("subcategories", {}).items():
                result[base][specific] = {
                    "required":   scfg.get("required_credits", 0),
                    "completed":  0,
                    "registered": 0,
                }
            result[base]["_total_required"] = cfg.get("total_required", 0)
        for sem in self.data.get("semesters", []):
            for course in sem.get("courses", []):
                base     = course.get("base_module", "")
                specific = course.get("specific_module", "")
                credits  = course.get("credits", 0)
                exam     = course.get("exam_given", False)
                result.setdefault(base, {})
                result[base].setdefault(specific, {
                    "required": 0, "completed": 0, "registered": 0})
                result[base][specific]["registered"] += credits
                if exam:
                    result[base][specific]["completed"] += credits
        return result

    # ── Aggregate totals for the chart ────────────────────────────────────────
    def _totals(self, data):
        """Return (grand_completed, grand_registered, grand_required) and
        a list of per-base dicts for breakdown view."""
        req_cfg = self.data.get("requirements", {})
        grand_completed = grand_registered = grand_required = 0
        per_base = []
        for base, base_cfg in req_cfg.items():
            subs     = base_cfg.get("subcategories", {})
            tot_req  = base_cfg.get("total_required", 0)
            b_comp = b_reg = 0
            if not subs:
                vals = data.get(base, {})
                for specific, scfg in vals.items():
                    if specific.startswith("_"):
                        continue
                    b_comp += scfg.get("completed", 0)
                    b_reg  += scfg.get("registered", 0)
            else:
                for specific in subs:
                    vals = data.get(base, {}).get(specific, {})
                    b_comp += vals.get("completed", 0)
                    b_reg  += vals.get("registered", 0)
            per_base.append({
                "name": base, "completed": b_comp,
                "registered": b_reg, "required": tot_req,
            })
            grand_completed  += b_comp
            grand_registered += b_reg
            grand_required   += tot_req
        return grand_completed, grand_registered, grand_required, per_base

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        topbar = tk.Frame(self.frame, bg=MANTLE, height=52)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)
        tk.Label(topbar, text="  📋  Requirements Tracker",
                 bg=MANTLE, fg=FG,
                 font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT, padx=14, pady=12)
        tk.Button(topbar, text="🔄  Refresh",
                  bg=SURFACE1, fg=FG, font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2", padx=10, pady=4,
                  command=self.reload,
                  ).pack(side=tk.RIGHT, padx=14, pady=12)

        self.summary_bar = tk.Frame(self.frame, bg=MANTLE, pady=8)
        self.summary_bar.pack(fill=tk.X)

        wrap = tk.Frame(self.frame, bg=BG)
        wrap.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)
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
        self._win = self.canvas.create_window(
            (0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Configure>",  self._on_resize)
        bind_scroll(self.canvas, h_canvas=self.canvas)

    def _on_resize(self, _=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    # ── Refresh ───────────────────────────────────────────────────────────────
    def _refresh(self):
        data = self._compute()
        for w in self.content.winfo_children():
            w.destroy()
        for w in self.summary_bar.winfo_children():
            w.destroy()

        grand_completed, grand_registered, grand_required, per_base = \
            self._totals(data)

        # ── Layout ────────────────────────────────────────────────────────────
        main_layout = tk.Frame(self.content, bg=BG)
        main_layout.pack(fill=tk.BOTH, expand=True)

        self._table_col = tk.Frame(main_layout, bg=BG)
        self._table_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 16))

        self._donut_col = tk.Frame(main_layout, bg=BG)
        self._donut_col.pack(side=tk.RIGHT, fill=tk.Y, pady=0)

        # ── Donut chart section (Right) ───────────────────────────────────────
        self._render_donut_section(
            self._donut_col, grand_completed, grand_registered, grand_required, per_base)

        # ── Table section (Left) ──────────────────────────────────────────────
        sep_t = tk.Frame(self._table_col, bg=SURFACE1, height=2)
        sep_t.pack(fill=tk.X, pady=(0, 10))
        tk.Label(self._table_col, text="  📊  Detailed Breakdown",
                 bg=BG, fg=MAUVE,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8, pady=(0, 6))

        COLS  = ["Base Module", "Specific Module",
                 "Completed\nCredits", "Registered\nCredits",
                 "Required\nCredits", "Remaining\n(Registered)",
                 "Remaining\n(Total)"]
        COL_W = [160, 210, 90, 90, 90, 120, 120]

        hdr = tk.Frame(self._table_col, bg=SURFACE0)
        hdr.pack(fill=tk.X, pady=(0, 2))
        for i, (col, w) in enumerate(zip(COLS, COL_W)):
            tk.Label(hdr, text=col, bg=SURFACE0, fg=ACCENT,
                     font=("Segoe UI", 9, "bold"),
                     width=w // 7, wraplength=w - 10,
                     justify=tk.CENTER, pady=8, padx=4,
                     ).grid(row=0, column=i, sticky="nsew", padx=1)
            hdr.columnconfigure(i, minsize=w)

        req_cfg = self.data.get("requirements", {})
        row_idx = 0

        for base, base_cfg in req_cfg.items():
            subs    = base_cfg.get("subcategories", {})
            tot_req = base_cfg.get("total_required", 0)
            base_completed = base_registered = 0

            sec_hdr = tk.Frame(self._table_col, bg=SURFACE1, pady=2)
            sec_hdr.pack(fill=tk.X)
            tk.Label(sec_hdr, text=f"  {base}", bg=SURFACE1, fg=MAUVE,
                     font=("Segoe UI", 10, "bold"), pady=3).pack(side=tk.LEFT)
            tk.Label(sec_hdr, text=f"Required: {tot_req} ECTS",
                     bg=SURFACE1, fg=SUBTEXT,
                     font=("Segoe UI", 8)).pack(side=tk.RIGHT, padx=12)

            if not subs:
                vals = data.get(base, {})
                for specific, scfg in vals.items():
                    if specific.startswith("_"):
                        continue
                    base_completed += scfg.get("completed", 0)
                    base_registered += scfg.get("registered", 0)
                self._render_row(row_idx, base, "—",
                                 base_completed, base_registered, tot_req,
                                 COLS, COL_W)
                row_idx += 1
            else:
                for specific, scfg in subs.items():
                    spec_req   = scfg.get("required_credits", tot_req)
                    vals       = data.get(base, {}).get(specific, {})
                    completed  = vals.get("completed", 0)
                    registered = vals.get("registered", 0)
                    base_completed  += completed
                    base_registered += registered
                    self._render_row(row_idx, "", specific,
                                     completed, registered, spec_req,
                                     COLS, COL_W)
                    row_idx += 1

            remaining_tot = max(0, tot_req - base_completed)
            sub_frame = tk.Frame(self._table_col, bg=MANTLE)
            sub_frame.pack(fill=tk.X)
            rem_reg_val = base_registered - tot_req
            rem_reg_txt = (str(rem_reg_val) if rem_reg_val >= 0
                           else f"-{abs(rem_reg_val)}")
            for i, (text, w, fg_c) in enumerate([
                ("",          COL_W[0], FG),
                (f"  ↳ {base} total", COL_W[1], FG),
                (str(base_completed),  COL_W[2], FG),
                (str(base_registered), COL_W[3], FG),
                (str(tot_req),         COL_W[4], FG),
                (rem_reg_txt,          COL_W[5], FG),
                (str(remaining_tot),   COL_W[6],
                 GREEN if remaining_tot <= 0 else YELLOW),
            ]):
                tk.Label(sub_frame, text=text, bg=MANTLE, fg=fg_c,
                         font=("Segoe UI", 8, "bold"),
                         width=w // 7, pady=3, padx=4,
                         ).grid(row=0, column=i, sticky="nsew", padx=1)
                sub_frame.columnconfigure(i, minsize=w)

        sep = tk.Frame(self._table_col, bg=SURFACE1, height=2)
        sep.pack(fill=tk.X, pady=6)
        tot_frame = tk.Frame(self._table_col, bg=SURFACE0)
        tot_frame.pack(fill=tk.X)
        remaining_grand = max(0, grand_required - grand_completed)
        grand_rem_reg = grand_registered - grand_required
        grand_rem_reg_txt = (str(grand_rem_reg) if grand_rem_reg >= 0
                             else f"-{abs(grand_rem_reg)}")
        for i, (text, w) in enumerate([
            ("",              COL_W[0]),
            ("  GRAND TOTAL", COL_W[1]),
            (str(grand_completed),  COL_W[2]),
            (str(grand_registered), COL_W[3]),
            (str(grand_required),   COL_W[4]),
            (grand_rem_reg_txt,     COL_W[5]),
            (str(remaining_grand),  COL_W[6]),
        ]):
            fg_c = (ACCENT if i == 1
                    else GREEN if i == 6 and remaining_grand <= 0
                    else RED if i == 6
                    else FG)
            tk.Label(tot_frame, text=text, bg=SURFACE0, fg=fg_c,
                     font=("Segoe UI", 10, "bold"),
                     width=w // 7, pady=6, padx=4,
                     ).grid(row=0, column=i, sticky="nsew", padx=1)
            tot_frame.columnconfigure(i, minsize=w)

        # ── Summary bar ──────────────────────────────────────────────────────
        pct = int(grand_completed / grand_required * 100) if grand_required else 0
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
                 text=f"{grand_completed} / {grand_required} ECTS ({pct}%)",
                 bg=MANTLE, fg=FG,
                 font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(self.summary_bar,
                 text=f"   {remaining_grand} ECTS remaining",
                 bg=MANTLE,
                 fg=YELLOW if remaining_grand > 0 else GREEN,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=8)

        self._render_semester_breakdown()

        # ── Re-bind scroll on all new children ────────────────────────────────
        rebind_scroll_children(self.canvas, self.content,
                               h_canvas=self.canvas)

    # ── Donut chart section ───────────────────────────────────────────────────
    def _render_donut_section(self, parent, completed, registered, required, per_base):
        chart_frame = tk.Frame(parent, bg=SURFACE0)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Top part: the canvas donut
        top_part = tk.Frame(chart_frame, bg=SURFACE0)
        top_part.pack(side=tk.TOP, pady=(16, 4))

        SIZE   = 240
        OUTER  = 100
        INNER  = 56
        self._donut_canvas = tk.Canvas(top_part, width=SIZE, height=SIZE,
                                       bg=SURFACE0, highlightthickness=0)
        self._donut_canvas.pack()

        # Bottom part: legend + switcher
        bottom_part = tk.Frame(chart_frame, bg=SURFACE0)
        bottom_part.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=16, pady=4)

        # Chart mode definitions
        remaining = max(0, required - completed)
        left_to_register = max(0, required - registered)
        self._chart_views = [
            {
                "title": "Overall Progress",
                "subtitle": "Earned vs Remaining",
                "center_val": f"{int(completed / required * 100) if required else 0}%",
                "center_sub": "Earned",
                "slices": [
                    ("Credits Earned", completed, GREEN),
                    ("Credits Remaining", remaining, SURFACE1),
                ],
            },
            {
                "title": "Registration Status",
                "subtitle": "Registered vs Still Needed",
                "center_val": f"{registered}",
                "center_sub": "Registered",
                "slices": [
                    ("Registered", registered, ACCENT),
                    ("Still Needed", left_to_register, SURFACE1),
                ],
            },
            {
                "title": "Earned vs Registered",
                "subtitle": "Completion within Registered",
                "center_val": f"{int(completed / registered * 100) if registered else 0}%",
                "center_sub": "Passed",
                "slices": [
                    ("Exams Passed", completed, GREEN),
                    ("Not Yet Passed", max(0, registered - completed), YELLOW),
                ],
            },
            {
                "title": "By Module",
                "subtitle": "Earned Credits per Base Module",
                "center_val": f"{completed}",
                "center_sub": "Total Earned",
                "slices": [(b["name"], b["completed"],
                            CHART_COLORS[i % len(CHART_COLORS)])
                           for i, b in enumerate(per_base)
                           if b["completed"] > 0] or [("None", 1, SURFACE1)],
            },
        ]

        # Title row with navigation arrows
        nav_row = tk.Frame(bottom_part, bg=SURFACE0)
        nav_row.pack(fill=tk.X, pady=(0, 6))

        btn_left = tk.Label(nav_row, text="◀", bg=SURFACE0, fg=ACCENT,
                            font=("Segoe UI", 14, "bold"), cursor="hand2")
        btn_left.pack(side=tk.LEFT, padx=(0, 8))
        btn_left.bind("<Button-1>", lambda e: self._cycle_chart(-1))

        self._chart_title_lbl = tk.Label(
            nav_row, text="", bg=SURFACE0, fg=FG,
            font=("Segoe UI", 12, "bold"))
        self._chart_title_lbl.pack(side=tk.LEFT)

        btn_right = tk.Label(nav_row, text="▶", bg=SURFACE0, fg=ACCENT,
                             font=("Segoe UI", 14, "bold"), cursor="hand2")
        btn_right.pack(side=tk.LEFT, padx=(8, 0))
        btn_right.bind("<Button-1>", lambda e: self._cycle_chart(1))

        self._chart_subtitle_lbl = tk.Label(
            bottom_part, text="", bg=SURFACE0, fg=SUBTEXT,
            font=("Segoe UI", 9))
        self._chart_subtitle_lbl.pack(anchor="w", pady=(0, 10))

        # Dot indicators
        dot_row = tk.Frame(bottom_part, bg=SURFACE0)
        dot_row.pack(anchor="w", pady=(0, 12))
        self._dot_labels = []
        for i in range(len(self._chart_views)):
            d = tk.Label(dot_row, text="●", bg=SURFACE0,
                         fg=ACCENT if i == 0 else OVERLAY,
                         font=("Segoe UI", 10), cursor="hand2")
            d.pack(side=tk.LEFT, padx=3)
            d.bind("<Button-1>", lambda e, idx=i: self._goto_chart(idx))
            self._dot_labels.append(d)

        # Legend
        self._legend_frame = tk.Frame(bottom_part, bg=SURFACE0)
        self._legend_frame.pack(fill=tk.X, anchor="w")

        # Stats summary line
        stats_frame = tk.Frame(bottom_part, bg=SURFACE0)
        stats_frame.pack(fill=tk.X, pady=(14, 0))
        for lbl, val, clr in [
            ("Required", str(required), SUBTEXT),
            ("Registered", str(registered), ACCENT),
            ("Earned", str(completed), GREEN),
            ("Remaining", str(remaining), YELLOW if remaining > 0 else GREEN),
        ]:
            sf = tk.Frame(stats_frame, bg=SURFACE0)
            sf.pack(side=tk.LEFT, padx=(0, 20))
            tk.Label(sf, text=lbl, bg=SURFACE0, fg=OVERLAY,
                     font=("Segoe UI", 8)).pack(anchor="w")
            tk.Label(sf, text=val + " ECTS", bg=SURFACE0, fg=clr,
                     font=("Segoe UI", 11, "bold")).pack(anchor="w")

        # Draw initial chart
        self._draw_donut()

    def _cycle_chart(self, direction):
        self._chart_mode = (self._chart_mode + direction) % len(self._chart_views)
        self._draw_donut()

    def _goto_chart(self, idx):
        self._chart_mode = idx
        self._draw_donut()

    def _draw_donut(self):
        view   = self._chart_views[self._chart_mode]
        canvas = self._donut_canvas
        SIZE   = 240
        CX, CY = SIZE // 2, SIZE // 2
        OUTER  = 100
        INNER  = 56

        canvas.delete("all")

        # Update title / subtitle
        self._chart_title_lbl.configure(text=view["title"])
        self._chart_subtitle_lbl.configure(text=view["subtitle"])

        # Update dots
        for i, d in enumerate(self._dot_labels):
            d.configure(fg=ACCENT if i == self._chart_mode else OVERLAY)

        # Update legend
        for w in self._legend_frame.winfo_children():
            w.destroy()
        slices = view["slices"]
        total  = sum(s[1] for s in slices)

        for name, value, color in slices:
            row = tk.Frame(self._legend_frame, bg=SURFACE0)
            row.pack(fill=tk.X, pady=2)
            swatch = tk.Frame(row, bg=color, width=12, height=12)
            swatch.pack(side=tk.LEFT, padx=(0, 8))
            swatch.pack_propagate(False)
            pct_str = f"{int(value / total * 100)}%" if total else "0%"
            tk.Label(row, text=f"{name}  —  {value} ECTS  ({pct_str})",
                     bg=SURFACE0, fg=FG,
                     font=("Segoe UI", 9)).pack(side=tk.LEFT)

        # ── Draw the donut arcs ───────────────────────────────────────────────
        if total == 0:
            # Empty ring
            canvas.create_oval(CX - OUTER, CY - OUTER, CX + OUTER, CY + OUTER,
                               fill=SURFACE1, outline="")
            canvas.create_oval(CX - INNER, CY - INNER, CX + INNER, CY + INNER,
                               fill=SURFACE0, outline="")
        else:
            # Background ring
            canvas.create_oval(CX - OUTER, CY - OUTER, CX + OUTER, CY + OUTER,
                               fill=SURFACE1, outline="")

            # Draw arcs using polygon approximation for filled arcs
            start_angle = 90  # start from top
            for name, value, color in slices:
                if value <= 0:
                    continue
                extent = (value / total) * 360
                self._draw_arc_wedge(canvas, CX, CY, OUTER, start_angle,
                                     extent, color)
                start_angle += extent

            # Cut out inner circle
            canvas.create_oval(CX - INNER, CY - INNER, CX + INNER, CY + INNER,
                               fill=SURFACE0, outline="")

            # Separator lines between slices
            start_angle = 90
            for name, value, color in slices:
                if value <= 0:
                    continue
                extent = (value / total) * 360
                # Draw a thin line at the start of each arc
                rad = math.radians(start_angle)
                x1 = CX + INNER * math.cos(rad)
                y1 = CY - INNER * math.sin(rad)
                x2 = CX + OUTER * math.cos(rad)
                y2 = CY - OUTER * math.sin(rad)
                canvas.create_line(x1, y1, x2, y2, fill=SURFACE0, width=2)
                start_angle += extent

        # Center text
        canvas.create_text(CX, CY - 8, text=view["center_val"],
                           fill=FG, font=("Segoe UI", 20, "bold"))
        canvas.create_text(CX, CY + 16, text=view["center_sub"],
                           fill=SUBTEXT, font=("Segoe UI", 9))

    def _draw_arc_wedge(self, canvas, cx, cy, radius, start_deg, extent_deg,
                        color):
        """Draw a filled arc wedge using a polygon for smooth rendering."""
        points = []
        steps  = max(int(extent_deg / 2), 8)
        for i in range(steps + 1):
            angle = math.radians(start_deg + extent_deg * i / steps)
            x = cx + radius * math.cos(angle)
            y = cy - radius * math.sin(angle)
            points.extend([x, y])
        # Close through center
        points.extend([cx, cy])
        if len(points) >= 6:
            canvas.create_polygon(points, fill=color, outline="")

    # ── Table rows  ───────────────────────────────────────────────────────────
    def _render_row(self, idx, base, specific, completed, registered,
                    required, COLS, COL_W):
        bg_c = SURFACE0 if idx % 2 == 0 else BG
        frame = tk.Frame(self._table_col, bg=bg_c)
        frame.pack(fill=tk.X)
        remaining_reg = registered - required
        remaining_tot = max(0, required - completed)
        rem_reg_text  = (str(remaining_reg) if remaining_reg >= 0
                         else f"-{abs(remaining_reg)}")
        rem_tot_color = (GREEN if remaining_tot <= 0
                         else YELLOW if remaining_tot <= required * 0.5
                         else RED)
        for i, (text, w) in enumerate([
            (base,              COL_W[0]),
            (specific,          COL_W[1]),
            (str(completed),    COL_W[2]),
            (str(registered),   COL_W[3]),
            (str(required),     COL_W[4]),
            (rem_reg_text,      COL_W[5]),
            (str(remaining_tot),COL_W[6]),
        ]):
            fg_c = (rem_tot_color if i == 6
                    else ACCENT if i == 0 and base
                    else FG)
            tk.Label(frame, text=text, bg=bg_c, fg=fg_c,
                     font=("Segoe UI", 9),
                     width=w // 7, pady=5, padx=6, anchor="w",
                     ).grid(row=0, column=i, sticky="nsew", padx=1)
            frame.columnconfigure(i, minsize=w)

    def _render_semester_breakdown(self):
        sep = tk.Frame(self._table_col, bg=SURFACE1, height=2)
        sep.pack(fill=tk.X, pady=(20, 6))
        tk.Label(self._table_col, text="  Per-Semester Credit Breakdown",
                 bg=BG, fg=MAUVE,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8, pady=(0, 6))

        for sem in self.data.get("semesters", []):
            courses   = sem.get("courses", [])
            total_sem = sum(c.get("credits", 0) for c in courses)
            done_sem  = sum(c.get("credits", 0)
                           for c in courses if c.get("exam_given"))
            sf = tk.Frame(self._table_col, bg=SURFACE0, pady=4)
            sf.pack(fill=tk.X, padx=8, pady=3)
            name = sem.get("display_name", sem["name"])
            tk.Label(sf, text=f"  {name}", bg=SURFACE0, fg=ACCENT,
                     font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
            tk.Label(sf, text=f"  {done_sem} done / {total_sem} registered",
                     bg=SURFACE0, fg=FG,
                     font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=8)
            pct = int(done_sem / total_sem * 100) if total_sem else 0
            pb  = tk.Frame(sf, bg=SURFACE1, height=10, width=150)
            pb.pack(side=tk.LEFT, padx=8)
            pb.pack_propagate(False)
            if pct:
                tk.Frame(pb, bg=GREEN, width=int(150 * pct / 100)).pack(
                    side=tk.LEFT, fill=tk.Y)
            tk.Label(sf, text=f"({pct}%)", bg=SURFACE0, fg=SUBTEXT,
                     font=("Segoe UI", 8)).pack(side=tk.LEFT)

            by_base: dict = {}
            for course in courses:
                b = course.get("base_module", "Other")
                by_base.setdefault(b, {"done": 0, "total": 0})
                by_base[b]["total"] += course.get("credits", 0)
                if course.get("exam_given"):
                    by_base[b]["done"] += course.get("credits", 0)
            dr = tk.Frame(sf, bg=SURFACE0)
            dr.pack(side=tk.LEFT, padx=16)
            for b, vals in by_base.items():
                tk.Label(dr, text=f"{b}: {vals['done']}/{vals['total']}",
                         bg=SURFACE0, fg=SUBTEXT,
                         font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=6)
