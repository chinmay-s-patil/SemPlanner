"""
requirements_view.py  —  Requirements Tracker
Shows overall credit requirements vs completed credits across all semesters.
Launch: python requirements_view.py data.json [SemName]
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys

# ── Palette ───────────────────────────────────────────────────────────────────
BG       = "#1E1E2E"
SURFACE0 = "#313244"
SURFACE1 = "#45475A"
CRUST    = "#11111B"
MANTLE   = "#181825"
FG       = "#CDD6F4"
SUBTEXT  = "#A6ADC8"
OVERLAY  = "#7F849C"
ACCENT   = "#89B4FA"
GREEN    = "#A6E3A1"
RED      = "#F38BA8"
YELLOW   = "#F9E2AF"
MAUVE    = "#CBA6F7"

DATA_FILE = "data.json"


def load_data(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_data(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class RequirementsView:
    def __init__(self, root: tk.Tk, data_file: str, sem_name: str = ""):
        self.root = root
        self.data_file = data_file
        self.root.title("Requirements Tracker")
        self.root.geometry("1080x720")
        self.root.minsize(860, 560)
        self.root.configure(bg=BG)

        self.data: dict = {}
        self._load()
        self._build_ui()
        self._refresh()

    def _load(self):
        try:
            self.data = load_data(self.data_file)
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))
            self.data = {"requirements": {}, "semesters": []}

    # ── Compute ───────────────────────────────────────────────────────────────
    def _compute(self):
        """
        Returns dict: { base_module: { specific_module: { completed, registered, required } } }
        """
        req_cfg = self.data.get("requirements", {})
        result = {}

        for base, cfg in req_cfg.items():
            result[base] = {}
            subs = cfg.get("subcategories", {})
            for specific, scfg in subs.items():
                result[base][specific] = {
                    "required":   scfg.get("required_credits", 0),
                    "completed":  0,
                    "registered": 0,
                }
            result[base]["_total_required"] = cfg.get("total_required", 0)

        # Walk all semesters
        for sem in self.data.get("semesters", []):
            for course in sem.get("courses", []):
                base     = course.get("base_module", "")
                specific = course.get("specific_module", "")
                credits  = course.get("credits", 0)
                exam     = course.get("exam_given", False)

                if base not in result:
                    result[base] = {}
                if specific not in result[base]:
                    result[base][specific] = {
                        "required": 0, "completed": 0, "registered": 0}

                result[base][specific]["registered"] += credits
                if exam:
                    result[base][specific]["completed"] += credits

        return result

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Top bar
        topbar = tk.Frame(self.root, bg=CRUST, height=56)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)
        tk.Label(topbar, text="  📋  Requirements Tracker",
                 bg=CRUST, fg=FG, font=("Segoe UI", 15, "bold")
                 ).pack(side=tk.LEFT, padx=14, pady=12)
        tk.Button(topbar, text="🔄  Refresh",
                  bg=SURFACE1, fg=FG, font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2", padx=10, pady=4,
                  command=self._refresh
                  ).pack(side=tk.RIGHT, padx=14, pady=12)

        # Summary row
        self.summary_bar = tk.Frame(self.root, bg=MANTLE, pady=8)
        self.summary_bar.pack(fill=tk.X)

        # Main scrollable area
        wrap = tk.Frame(self.root, bg=BG)
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
                                yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.configure(command=self.canvas.yview)
        hsb.configure(command=self.canvas.xview)

        self.content = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<MouseWheel>",
            lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self.canvas.bind("<Button-4>",
            lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>",
            lambda e: self.canvas.yview_scroll(1, "units"))

    def _on_resize(self, _=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    # ── Refresh / render ──────────────────────────────────────────────────────
    def _refresh(self):
        self._load()
        data = self._compute()

        # Clear
        for w in self.content.winfo_children():
            w.destroy()
        for w in self.summary_bar.winfo_children():
            w.destroy()

        # Column headers
        COLS = ["Base Module", "Specific Module",
                "Completed\nCredits", "Registered\nCredits", "Required\nCredits",
                "Remaining\n(Registered)", "Remaining\n(Total)"]
        COL_W = [160, 210, 90, 90, 90, 120, 120]

        hdr = tk.Frame(self.content, bg=SURFACE0)
        hdr.pack(fill=tk.X, pady=(0, 2))
        for i, (col, w) in enumerate(zip(COLS, COL_W)):
            tk.Label(hdr, text=col, bg=SURFACE0, fg=ACCENT,
                     font=("Segoe UI", 9, "bold"), width=w//7,
                     wraplength=w-10, justify=tk.CENTER,
                     pady=8, padx=4
                     ).grid(row=0, column=i, sticky="nsew", padx=1)
            hdr.columnconfigure(i, minsize=w)

        # Totals accumulator
        grand_completed = grand_registered = grand_required = 0

        req_cfg = self.data.get("requirements", {})
        row_idx = 0

        for base, base_cfg in req_cfg.items():
            subs    = base_cfg.get("subcategories", {})
            tot_req = base_cfg.get("total_required", 0)

            base_completed  = 0
            base_registered = 0

            # Base section header
            sec_hdr = tk.Frame(self.content, bg=SURFACE1, pady=2)
            sec_hdr.pack(fill=tk.X, pady=(6, 0))
            tk.Label(sec_hdr, text=f"  {base}",
                     bg=SURFACE1, fg=FG, font=("Segoe UI", 10, "bold"),
                     pady=4).pack(side=tk.LEFT)
            tk.Label(sec_hdr,
                     text=f"Required: {tot_req} ECTS",
                     bg=SURFACE1, fg=SUBTEXT, font=("Segoe UI", 9)
                     ).pack(side=tk.RIGHT, padx=10)

            if not subs:
                # Just a single row with the base total
                base_data = data.get(base, {})
                for specific, vals in base_data.items():
                    base_completed  += vals.get("completed", 0)
                    base_registered += vals.get("registered", 0)
                self._render_row(row_idx, base, "—",
                                 base_completed, base_registered, tot_req, COLS, COL_W)
                row_idx += 1
            else:
                for specific, scfg in subs.items():
                    spec_req  = scfg.get("required_credits", tot_req)
                    vals      = data.get(base, {}).get(specific, {})
                    completed = vals.get("completed", 0)
                    registered = vals.get("registered", 0)
                    base_completed  += completed
                    base_registered += registered

                    self._render_row(row_idx, "", specific,
                                     completed, registered, spec_req, COLS, COL_W)
                    row_idx += 1

            # Subtotal row for this base
            remaining_reg = max(0, base_registered - tot_req)
            remaining_tot = max(0, tot_req - base_completed)
            sub_frame = tk.Frame(self.content, bg=MANTLE)
            sub_frame.pack(fill=tk.X)
            vals_sub = [
                ("", "Subtotal", str(base_completed), str(base_registered),
                 str(tot_req),
                 str(base_registered - tot_req) if base_registered >= tot_req else f"-{max(0,tot_req-base_registered)}",
                 str(remaining_tot)),
            ]
            for _, spec, comp, reg, req, rem_reg, rem_tot in vals_sub:
                for i, (text, w, color) in enumerate([
                    ("", COL_W[0], MANTLE),
                    (f"  ↳ {base} total", COL_W[1], MANTLE),
                    (comp, COL_W[2], MANTLE),
                    (reg,  COL_W[3], MANTLE),
                    (req,  COL_W[4], MANTLE),
                    (rem_reg, COL_W[5], MANTLE),
                    (rem_tot, COL_W[6], MANTLE),
                ]):
                    fg_color = FG
                    if i == 6:
                        try:
                            fg_color = GREEN if int(rem_tot) <= 0 else YELLOW
                        except Exception:
                            pass
                    tk.Label(sub_frame, text=text, bg=color, fg=fg_color,
                             font=("Segoe UI", 8, "bold"),
                             width=w//7, pady=3, padx=4
                             ).grid(row=0, column=i, sticky="nsew", padx=1)
                sub_frame.columnconfigure(i, minsize=w)

            grand_completed  += base_completed
            grand_registered += base_registered
            grand_required   += tot_req

        # Grand total row
        sep = tk.Frame(self.content, bg=SURFACE1, height=2)
        sep.pack(fill=tk.X, pady=6)

        tot_frame = tk.Frame(self.content, bg=SURFACE0)
        tot_frame.pack(fill=tk.X)
        remaining_grand = max(0, grand_required - grand_completed)
        for i, (text, w) in enumerate([
            ("", COL_W[0]),
            ("  GRAND TOTAL", COL_W[1]),
            (str(grand_completed), COL_W[2]),
            (str(grand_registered), COL_W[3]),
            (str(grand_required), COL_W[4]),
            (str(grand_registered - grand_required) if grand_registered >= grand_required
             else f"-{grand_required - grand_registered}", COL_W[5]),
            (str(remaining_grand), COL_W[6]),
        ]):
            fg_c = ACCENT if i == 1 else (
                GREEN if i == 6 and remaining_grand <= 0 else
                RED   if i == 6 else FG
            )
            tk.Label(tot_frame, text=text, bg=SURFACE0, fg=fg_c,
                     font=("Segoe UI", 10, "bold"),
                     width=w//7, pady=6, padx=4
                     ).grid(row=0, column=i, sticky="nsew", padx=1)
            tot_frame.columnconfigure(i, minsize=w)

        # Summary bar
        pct = int(grand_completed / grand_required * 100) if grand_required else 0
        tk.Label(self.summary_bar, text="  Total Progress:",
                 bg=MANTLE, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        pb = tk.Frame(self.summary_bar, bg=SURFACE1, height=14, width=300)
        pb.pack(side=tk.LEFT, padx=10, pady=2)
        pb.pack_propagate(False)
        fill_w = int(300 * pct / 100) if pct else 0
        tk.Frame(pb, bg=GREEN, width=fill_w).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(self.summary_bar,
                 text=f"{grand_completed} / {grand_required} ECTS ({pct}%)",
                 bg=MANTLE, fg=FG, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(self.summary_bar,
                 text=f"   {remaining_grand} ECTS remaining",
                 bg=MANTLE, fg=YELLOW if remaining_grand > 0 else GREEN,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=8)

        # Per-semester credit breakdown
        self._render_semester_breakdown()

    def _render_row(self, idx, base, specific, completed, registered, required,
                    COLS, COL_W):
        bg_c   = SURFACE0 if idx % 2 == 0 else BG
        frame  = tk.Frame(self.content, bg=bg_c)
        frame.pack(fill=tk.X)

        remaining_reg = registered - required
        remaining_tot = max(0, required - completed)
        rem_reg_text  = str(remaining_reg) if remaining_reg >= 0 else f"-{abs(remaining_reg)}"

        rem_tot_color = (GREEN if remaining_tot <= 0 else
                         YELLOW if remaining_tot <= required * 0.5 else RED)

        for i, (text, w) in enumerate([
            (base, COL_W[0]),
            (specific, COL_W[1]),
            (str(completed), COL_W[2]),
            (str(registered), COL_W[3]),
            (str(required), COL_W[4]),
            (rem_reg_text, COL_W[5]),
            (str(remaining_tot), COL_W[6]),
        ]):
            fg_c = (rem_tot_color if i == 6 else
                    ACCENT         if i == 0 and base else
                    FG)
            tk.Label(frame, text=text, bg=bg_c, fg=fg_c,
                     font=("Segoe UI", 9), width=w//7, pady=5, padx=6,
                     anchor="w"
                     ).grid(row=0, column=i, sticky="nsew", padx=1)
            frame.columnconfigure(i, minsize=w)

    def _render_semester_breakdown(self):
        """Show per-semester credits at the bottom."""
        sep = tk.Frame(self.content, bg=SURFACE1, height=2)
        sep.pack(fill=tk.X, pady=(20, 6))

        tk.Label(self.content,
                 text="  Per-Semester Credit Breakdown",
                 bg=BG, fg=MAUVE, font=("Segoe UI", 11, "bold")
                 ).pack(anchor="w", padx=8, pady=(0, 6))

        for sem in self.data.get("semesters", []):
            courses = sem.get("courses", [])
            total_sem = sum(c.get("credits", 0) for c in courses)
            done_sem  = sum(c.get("credits", 0) for c in courses if c.get("exam_given"))

            sem_frame = tk.Frame(self.content, bg=SURFACE0, pady=4)
            sem_frame.pack(fill=tk.X, padx=8, pady=3)

            tk.Label(sem_frame,
                     text=f"  {sem.get('display_name', sem['name'])}",
                     bg=SURFACE0, fg=ACCENT, font=("Segoe UI", 10, "bold")
                     ).pack(side=tk.LEFT)
            tk.Label(sem_frame,
                     text=f"  {done_sem} done / {total_sem} registered",
                     bg=SURFACE0, fg=FG, font=("Segoe UI", 9)
                     ).pack(side=tk.LEFT, padx=8)

            # Mini progress bar
            pct = int(done_sem / total_sem * 100) if total_sem else 0
            pb = tk.Frame(sem_frame, bg=SURFACE1, height=10, width=150)
            pb.pack(side=tk.LEFT, padx=8)
            pb.pack_propagate(False)
            fill_w = int(150 * pct / 100) if pct else 0
            tk.Frame(pb, bg=GREEN, width=fill_w).pack(side=tk.LEFT, fill=tk.Y)
            tk.Label(sem_frame, text=f"({pct}%)",
                     bg=SURFACE0, fg=SUBTEXT, font=("Segoe UI", 8)
                     ).pack(side=tk.LEFT)

            # By module
            by_base: dict = {}
            for course in courses:
                b = course.get("base_module", "Other")
                by_base.setdefault(b, {"done": 0, "total": 0})
                by_base[b]["total"] += course.get("credits", 0)
                if course.get("exam_given"):
                    by_base[b]["done"] += course.get("credits", 0)

            detail_row = tk.Frame(sem_frame, bg=SURFACE0)
            detail_row.pack(side=tk.LEFT, padx=16)
            for b, vals in by_base.items():
                tk.Label(detail_row,
                         text=f"{b}: {vals['done']}/{vals['total']}",
                         bg=SURFACE0, fg=SUBTEXT, font=("Segoe UI", 8)
                         ).pack(side=tk.LEFT, padx=6)


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    data_file = sys.argv[1] if len(sys.argv) > 1 else "data.json"
    sem_name  = sys.argv[2] if len(sys.argv) > 2 else ""
    root = tk.Tk()
    RequirementsView(root, data_file, sem_name)
    root.mainloop()