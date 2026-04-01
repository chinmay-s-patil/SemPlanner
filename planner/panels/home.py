"""planner/panels/home.py — Dashboard / home panel."""

import os
import tkinter as tk
from tkinter import ttk

from planner.constants import (
    BG, SURFACE0, SURFACE1, MANTLE, FG, SUBTEXT, OVERLAY,
    ACCENT, GREEN, YELLOW, MAUVE, CRUST,
)


class HomePanel:
    def __init__(self, container: tk.Frame, hub):
        self.hub   = hub
        self.frame = tk.Frame(container, bg=BG)
        self._build_ui()

    def reload(self):
        self._refresh_semester_cb()
        self._refresh_summary()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        topbar = tk.Frame(self.frame, bg=CRUST, height=60)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)
        tk.Label(topbar, text="  🎓  Academic Hub",
                 bg=CRUST, fg=FG,
                 font=("Segoe UI", 16, "bold")).pack(
            side=tk.LEFT, padx=14, pady=14)
        btn_frame = tk.Frame(topbar, bg=CRUST)
        btn_frame.pack(side=tk.RIGHT, padx=14, pady=12)
        self._btn(btn_frame, "📂  Load Data", SURFACE1, FG,
                  self.hub.load_data_dialog).pack(side=tk.LEFT, padx=(0, 6))
        self._btn(btn_frame, "➕  New Semester", GREEN, CRUST,
                  self.hub.new_semester_dialog).pack(side=tk.LEFT)

        sel_row = tk.Frame(self.frame, bg=MANTLE, pady=10)
        sel_row.pack(fill=tk.X)
        tk.Label(sel_row, text="  Semester:", bg=MANTLE, fg=SUBTEXT,
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(14, 6))
        self.sem_var = tk.StringVar()
        self.sem_cb  = ttk.Combobox(sel_row, textvariable=self.sem_var,
                                    state="readonly", width=30,
                                    font=("Segoe UI", 10))
        self.sem_cb.pack(side=tk.LEFT, padx=(0, 10))
        self._refresh_semester_cb()

        self.summary_frame = tk.Frame(self.frame, bg=SURFACE0, pady=6)
        self.summary_frame.pack(fill=tk.X, padx=20, pady=(14, 0))
        self._refresh_summary()

        cards = tk.Frame(self.frame, bg=BG)
        cards.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)
        cards.columnconfigure((0, 1, 2), weight=1, uniform="col")

        card_defs = [
            ("📅", "Timetable",       "Weekly schedule\nfor selected semester",  ACCENT, "timetable"),
            ("📋", "Requirements",    "Credit requirements\n& overall progress",  GREEN,  "requirements"),
            ("📊", "Semester Credits","Course list, modules\n& exam tracking",    MAUVE,  "semester"),
        ]
        for col, (icon, title, desc, color, panel_id) in enumerate(card_defs):
            self._make_card(cards, icon, title, desc, color, panel_id).grid(
                row=0, column=col, padx=8, pady=6, sticky="nsew")

        tk.Label(self.frame,
                 text=f"Data file: {os.path.abspath(self.hub.data_file)}",
                 bg=BG, fg=OVERLAY,
                 font=("Segoe UI", 8)).pack(
            side=tk.BOTTOM, anchor="w", padx=20, pady=(0, 8))

    def _make_card(self, parent, icon, title, desc, color, panel_id):
        card = tk.Frame(parent, bg=SURFACE0, cursor="hand2",
                        relief=tk.FLAT, bd=0)
        tk.Frame(card, bg=color, height=4).pack(fill=tk.X)
        tk.Label(card, text=icon, bg=SURFACE0, fg=color,
                 font=("Segoe UI", 32)).pack(pady=(18, 4))
        tk.Label(card, text=title, bg=SURFACE0, fg=FG,
                 font=("Segoe UI", 13, "bold")).pack()
        tk.Label(card, text=desc, bg=SURFACE0, fg=SUBTEXT,
                 font=("Segoe UI", 9), justify=tk.CENTER).pack(pady=(4, 14))
        tk.Button(card, text=f"Open {title}", bg=color, fg=CRUST,
                  font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
                  cursor="hand2", padx=14, pady=6,
                  activebackground=SURFACE1,
                  command=lambda p=panel_id: self.hub.show_panel(p),
                  ).pack(pady=(0, 18))
        card.bind("<Enter>", lambda e, c=card: c.configure(bg=SURFACE1))
        card.bind("<Leave>", lambda e, c=card: c.configure(bg=SURFACE0))
        return card

    def _refresh_semester_cb(self):
        names = [s["name"] for s in self.hub.data.get("semesters", [])]
        self.sem_cb["values"] = names
        if names:
            self.sem_var.set(names[-1])

    def _refresh_summary(self):
        for w in self.summary_frame.winfo_children():
            w.destroy()
        req       = self.hub.data.get("requirements", {})
        total_req = sum(v.get("total_required", 0) for v in req.values())
        completed = 0
        for sem in self.hub.data.get("semesters", []):
            for c in sem.get("courses", []):
                if c.get("exam_given") and c.get("credits", 0):
                    completed += c["credits"]
        remaining = max(0, total_req - completed)
        pct       = int(completed / total_req * 100) if total_req else 0

        tk.Label(self.summary_frame, text="  Overall Progress:",
                 bg=SURFACE0, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        pb_frame = tk.Frame(self.summary_frame, bg=SURFACE1,
                            height=12, width=200)
        pb_frame.pack(side=tk.LEFT, padx=10, pady=2)
        pb_frame.pack_propagate(False)
        if pct:
            tk.Frame(pb_frame, bg=GREEN, width=int(200 * pct / 100)).pack(
                side=tk.LEFT, fill=tk.Y)
        tk.Label(self.summary_frame,
                 text=f"{completed}/{total_req} credits  ({pct}%)",
                 bg=SURFACE0, fg=FG,
                 font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=6)
        tk.Label(self.summary_frame,
                 text=f"  {remaining} remaining",
                 bg=SURFACE0,
                 fg=YELLOW if remaining > 0 else GREEN,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)

    def _btn(self, parent, text, bg, fg, cmd):
        return tk.Button(parent, text=text, bg=bg, fg=fg,
                         font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
                         cursor="hand2", padx=10, pady=4,
                         activebackground=ACCENT, activeforeground=CRUST,
                         command=cmd)
