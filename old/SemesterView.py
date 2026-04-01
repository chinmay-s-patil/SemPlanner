"""
semester_view.py  —  Semester Course & Credit Tracker
Shows all courses for a chosen semester with module, credits, exam status.
Editable inline — saves back to data.json on change.
Launch: python semester_view.py data.json [SemName]
"""

import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
import json
import os
import sys

# ── Palette ───────────────────────────────────────────────────────────────────
BG       = "#1E1E2E"
SURFACE0 = "#313244"
SURFACE1 = "#45475A"
SURFACE2 = "#585B70"
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
PINK     = "#F5C2E7"
TEAL     = "#94E2D5"

COURSE_COLORS = [
    "#89B4FA", "#A6E3A1", "#FAB387", "#CBA6F7",
    "#F38BA8", "#94E2D5", "#F9E2AF", "#74C7EC",
    "#B4BEFE", "#EBA0AC",
]

BASE_MODULES = [
    "Master Modules", "Lab Courses", "Supplementary Courses",
    "Key Competencies", "Research Practice", "Master's Thesis", ""
]

SPECIFIC_MODULES = {
    "Master Modules": [
        "Integrated Systems", "Propulsion Systems", "Fluid/Aerodynamics",
        "Structure", "Dynamics/Control", "Domain Specific Modules",
        "Flexibilization in Engineering"
    ],
    "Lab Courses": ["Lab Courses"],
    "Supplementary Courses": ["Supplementary Courses"],
    "Key Competencies": [
        "Offers Contextual Studies", "Angebote Sprachenzentrum",
        "Carl-von-Linde-Akademie", "General Offers"
    ],
    "Research Practice": ["Teamproject", "Term Project", "Research Practice"],
    "Master's Thesis": ["Master's Thesis"],
    "": [""],
}


def load_data(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_data(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class SemesterView:
    def __init__(self, root: tk.Tk, data_file: str, sem_name: str = ""):
        self.root = root
        self.data_file = data_file
        self.root.title("Semester Credits")
        self.root.geometry("1300x740")
        self.root.minsize(1000, 560)
        self.root.configure(bg=BG)

        self.data: dict = {}
        self.sem_name = sem_name
        self.sem: dict = {}

        self._styles()
        self._build_ui()
        self._load_and_render()

    def _styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TCombobox", fieldbackground=SURFACE1, background=SURFACE0,
                    foreground=FG, selectbackground=ACCENT, arrowcolor=SUBTEXT,
                    borderwidth=0)
        s.map("TCombobox", fieldbackground=[("readonly", SURFACE1)])

    # ── Data ──────────────────────────────────────────────────────────────────
    def _load_and_render(self):
        try:
            self.data = load_data(self.data_file)
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex)); return

        sems = [s["name"] for s in self.data.get("semesters", [])]
        self.sem_cb["values"] = sems
        if self.sem_name and self.sem_name in sems:
            self.sem_var.set(self.sem_name)
        elif sems:
            self.sem_var.set(sems[-1])
        self._switch_semester()

    def _switch_semester(self, *_):
        name = self.sem_var.get()
        sem  = next((s for s in self.data.get("semesters", [])
                     if s["name"] == name), None)
        if not sem:
            return
        self.sem = sem
        self.root.title(f"Semester Credits — {sem.get('display_name', name)}")
        self._render_table()

    def _save(self):
        save_data(self.data_file, self.data)

    # ── UI skeleton ───────────────────────────────────────────────────────────
    def _build_ui(self):
        # Top bar
        topbar = tk.Frame(self.root, bg=CRUST, height=56)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)

        tk.Label(topbar, text="  📊  Semester Credits",
                 bg=CRUST, fg=FG, font=("Segoe UI", 15, "bold")
                 ).pack(side=tk.LEFT, padx=14, pady=12)

        tk.Frame(topbar, bg=SURFACE1, width=1).pack(
            side=tk.LEFT, fill=tk.Y, pady=12, padx=10)

        self.sem_var = tk.StringVar()
        self.sem_cb  = ttk.Combobox(topbar, textvariable=self.sem_var,
                                    state="readonly", width=24,
                                    font=("Segoe UI", 10))
        self.sem_cb.pack(side=tk.LEFT, pady=14, padx=4)
        self.sem_cb.bind("<<ComboboxSelected>>", self._switch_semester)

        self._btn(topbar, "➕  Add Course", GREEN, CRUST,
                  self._add_course_dialog).pack(side=tk.RIGHT, padx=14, pady=12)

        # Summary strip
        self.summary_bar = tk.Frame(self.root, bg=MANTLE, pady=6)
        self.summary_bar.pack(fill=tk.X)

        # Main table area (scrollable)
        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

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

        self.table_frame = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0, 0), window=self.table_frame, anchor="nw")
        self.table_frame.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Configure>", self._on_resize)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind(seq, self._scroll)

    def _on_resize(self, _=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _scroll(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    # ── Table render ──────────────────────────────────────────────────────────
    COL_DEFS = [
        ("No",         40),
        ("Course Name",260),
        ("Base Module",140),
        ("Specific Module",150),
        ("Credits",    62),
        ("Exam Given?",80),
        ("Credits\nObtainable",80),
        ("Exam Date",  90),
        ("Exam Time",  70),
        ("Alt Date",   90),
        ("Alt Time",   70),
        ("Additional Info", 160),
        ("", 40),   # delete button col
    ]

    def _render_table(self):
        for w in self.table_frame.winfo_children():
            w.destroy()
        self._refresh_summary()

        courses = self.sem.get("courses", [])

        # Header
        hdr = tk.Frame(self.table_frame, bg=SURFACE0)
        hdr.pack(fill=tk.X)
        for col_i, (label, width) in enumerate(self.COL_DEFS):
            tk.Label(hdr, text=label, bg=SURFACE0, fg=ACCENT,
                     font=("Segoe UI", 9, "bold"),
                     width=width//7, pady=8, padx=4,
                     wraplength=width-6, justify=tk.CENTER
                     ).grid(row=0, column=col_i, sticky="nsew", padx=1)
            hdr.columnconfigure(col_i, minsize=width)

        sep = tk.Frame(self.table_frame, bg=ACCENT, height=2)
        sep.pack(fill=tk.X)

        # Group rows by base module
        by_base: dict[str, list] = {}
        for course in courses:
            b = course.get("base_module", "Other")
            by_base.setdefault(b, []).append(course)

        row_num = 1
        for base, group in by_base.items():
            # Section header
            sec = tk.Frame(self.table_frame, bg=SURFACE1, pady=2)
            sec.pack(fill=tk.X, pady=(8, 0))
            tk.Label(sec, text=f"  {base}",
                     bg=SURFACE1, fg=FG, font=("Segoe UI", 10, "bold"),
                     pady=3).pack(side=tk.LEFT)
            # Credits for this group
            tot  = sum(c.get("credits", 0) for c in group)
            done = sum(c.get("credits", 0) for c in group if c.get("exam_given"))
            tk.Label(sec, text=f"{done}/{tot} ECTS",
                     bg=SURFACE1,
                     fg=GREEN if done >= tot else YELLOW,
                     font=("Segoe UI", 9)).pack(side=tk.RIGHT, padx=12)

            for ci, course in enumerate(group):
                self._render_course_row(row_num, ci, course,
                                        bg=SURFACE0 if ci % 2 == 0 else BG)
                row_num += 1

        # Totals row
        sep2 = tk.Frame(self.table_frame, bg=SURFACE1, height=2)
        sep2.pack(fill=tk.X, pady=6)
        tot_frame = tk.Frame(self.table_frame, bg=SURFACE0)
        tot_frame.pack(fill=tk.X)

        total_credits = sum(c.get("credits", 0) for c in courses)
        done_credits  = sum(c.get("credits", 0) for c in courses if c.get("exam_given"))

        for i, (text, width) in enumerate(self.COL_DEFS):
            if i == 1:
                t = f"Total — {row_num-1} courses"
                fg_c = FG
            elif i == 4:
                t = str(total_credits); fg_c = ACCENT
            elif i == 6:
                t = str(done_credits); fg_c = GREEN if done_credits == total_credits else YELLOW
            else:
                t = ""; fg_c = FG
            tk.Label(tot_frame, text=t, bg=SURFACE0, fg=fg_c,
                     font=("Segoe UI", 10, "bold"),
                     width=width//7, pady=6, padx=4
                     ).grid(row=0, column=i, sticky="nsew", padx=1)
            tot_frame.columnconfigure(i, minsize=width)

    def _render_course_row(self, row_num, ci, course, bg=BG):
        row = tk.Frame(self.table_frame, bg=bg)
        row.pack(fill=tk.X)

        color  = course.get("color", COURSE_COLORS[ci % len(COURSE_COLORS)])
        credits = course.get("credits", 0)
        exam    = course.get("exam_given", False)

        def make_lbl(text, width, fg_c=FG, bold=False):
            return tk.Label(row, text=text, bg=bg, fg=fg_c,
                            font=("Segoe UI", 9, "bold" if bold else "normal"),
                            width=width//7, pady=5, padx=4, anchor="w")

        # Color dot + No
        no_frame = tk.Frame(row, bg=bg)
        no_frame.grid(row=0, column=0, sticky="nsew", padx=1)
        tk.Label(no_frame, bg=color, width=3, height=1).pack(side=tk.LEFT, padx=2)
        tk.Label(no_frame, text=str(row_num), bg=bg, fg=OVERLAY,
                 font=("Segoe UI", 8)).pack(side=tk.LEFT)
        row.columnconfigure(0, minsize=self.COL_DEFS[0][1])

        # Course name (bold, colored)
        name_lbl = tk.Label(row, text=course.get("name", ""),
                             bg=bg, fg=color,
                             font=("Segoe UI", 9, "bold"),
                             width=self.COL_DEFS[1][1]//7,
                             pady=5, padx=4, anchor="w",
                             wraplength=self.COL_DEFS[1][1]-8, justify=tk.LEFT)
        name_lbl.grid(row=0, column=1, sticky="nsew", padx=1)
        name_lbl.bind("<Double-Button-1>",
                      lambda e, c=course: self._edit_course_dialog(c))
        row.columnconfigure(1, minsize=self.COL_DEFS[1][1])

        # Base module
        make_lbl(course.get("base_module", ""), self.COL_DEFS[2][1], SUBTEXT
                 ).grid(row=0, column=2, sticky="nsew", padx=1)
        row.columnconfigure(2, minsize=self.COL_DEFS[2][1])

        # Specific module
        make_lbl(course.get("specific_module", ""), self.COL_DEFS[3][1], SUBTEXT
                 ).grid(row=0, column=3, sticky="nsew", padx=1)
        row.columnconfigure(3, minsize=self.COL_DEFS[3][1])

        # Credits
        make_lbl(str(credits), self.COL_DEFS[4][1], ACCENT, bold=True
                 ).grid(row=0, column=4, sticky="nsew", padx=1)
        row.columnconfigure(4, minsize=self.COL_DEFS[4][1])

        # Exam Given — toggling checkbox
        exam_var = tk.BooleanVar(value=exam)
        exam_bg  = "#1a3a1a" if exam else bg
        cb = tk.Checkbutton(row, variable=exam_var, bg=exam_bg,
                            selectcolor=SURFACE1, activebackground=bg,
                            cursor="hand2",
                            command=lambda v=exam_var, c=course, r=row:
                                self._toggle_exam(c, v, r))
        cb.grid(row=0, column=5, sticky="nsew", padx=1)
        row.columnconfigure(5, minsize=self.COL_DEFS[5][1])

        # Credits obtainable (= credits if exam given, else 0)
        obtainable = credits if exam else 0
        make_lbl(str(obtainable), self.COL_DEFS[6][1],
                 GREEN if exam else OVERLAY
                 ).grid(row=0, column=6, sticky="nsew", padx=1)
        row.columnconfigure(6, minsize=self.COL_DEFS[6][1])

        # Date/time fields
        for col_i, field_key in enumerate(
                ["exam_date", "exam_time", "alt_date", "alt_time"], start=7):
            val = course.get(field_key, "")
            lbl = tk.Label(row, text=val or "—",
                           bg=bg, fg=SUBTEXT if not val else FG,
                           font=("Segoe UI", 8),
                           width=self.COL_DEFS[col_i][1]//7,
                           pady=5, padx=4, anchor="w",
                           cursor="hand2")
            lbl.grid(row=0, column=col_i, sticky="nsew", padx=1)
            lbl.bind("<Button-1>",
                     lambda e, c=course, k=field_key, l=lbl:
                         self._inline_edit(c, k, l))
            row.columnconfigure(col_i, minsize=self.COL_DEFS[col_i][1])

        # Additional info (col 11)
        info_lbl = tk.Label(row, text=course.get("additional_info", "") or "",
                            bg=bg, fg=OVERLAY,
                            font=("Segoe UI", 8),
                            width=self.COL_DEFS[11][1]//7,
                            pady=5, padx=4, anchor="w",
                            cursor="hand2",
                            wraplength=self.COL_DEFS[11][1]-8)
        info_lbl.grid(row=0, column=11, sticky="nsew", padx=1)
        info_lbl.bind("<Button-1>",
                      lambda e, c=course, l=info_lbl:
                          self._inline_edit(c, "additional_info", l))
        row.columnconfigure(11, minsize=self.COL_DEFS[11][1])

        # Delete button (col 12)
        tk.Button(row, text="✕", bg=bg, fg=RED,
                  font=("Segoe UI", 9), relief=tk.FLAT, cursor="hand2",
                  command=lambda c=course: self._delete_course(c)
                  ).grid(row=0, column=12, sticky="nsew", padx=1)
        row.columnconfigure(12, minsize=self.COL_DEFS[12][1])

    # ── Summary bar ───────────────────────────────────────────────────────────
    def _refresh_summary(self):
        for w in self.summary_bar.winfo_children():
            w.destroy()
        courses = self.sem.get("courses", [])
        total   = sum(c.get("credits", 0) for c in courses)
        done    = sum(c.get("credits", 0) for c in courses if c.get("exam_given"))
        n       = len(courses)
        pct     = int(done / total * 100) if total else 0

        tk.Label(self.summary_bar,
                 text=f"  {n} courses  |  {total} ECTS registered",
                 bg=MANTLE, fg=SUBTEXT, font=("Segoe UI", 9)
                 ).pack(side=tk.LEFT)

        pb = tk.Frame(self.summary_bar, bg=SURFACE1, height=12, width=200)
        pb.pack(side=tk.LEFT, padx=10)
        pb.pack_propagate(False)
        fill_w = int(200 * pct / 100) if pct else 0
        tk.Frame(pb, bg=GREEN, width=fill_w).pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(self.summary_bar,
                 text=f"{done}/{total} ECTS exam given ({pct}%)",
                 bg=MANTLE, fg=FG, font=("Segoe UI", 9, "bold")
                 ).pack(side=tk.LEFT, padx=6)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _toggle_exam(self, course, var, row):
        course["exam_given"] = var.get()
        self._save()
        self._render_table()

    def _inline_edit(self, course, field_key, label):
        """Pop a tiny entry over the label for quick editing."""
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.configure(bg=SURFACE1)
        x = label.winfo_rootx(); y = label.winfo_rooty()
        w = max(label.winfo_width(), 120); h = label.winfo_height() + 4
        win.geometry(f"{w}x{h}+{x}+{y-2}")

        var = tk.StringVar(value=course.get(field_key, "") or "")
        e = tk.Entry(win, textvariable=var, bg=SURFACE0, fg=FG,
                     insertbackground=FG, relief=tk.FLAT, font=("Segoe UI", 9),
                     highlightthickness=1, highlightcolor=ACCENT,
                     highlightbackground=ACCENT)
        e.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        e.focus_set(); e.select_range(0, tk.END)

        def commit(*_):
            course[field_key] = var.get().strip()
            self._save()
            win.destroy()
            self._render_table()

        e.bind("<Return>",  commit)
        e.bind("<FocusOut>", commit)
        e.bind("<Escape>", lambda e: win.destroy())

    def _delete_course(self, course):
        if messagebox.askyesno("Delete",
                               f"Remove '{course.get('name','')}' from this semester?",
                               parent=self.root):
            self.sem["courses"] = [c for c in self.sem["courses"] if c is not course]
            self._save()
            self._render_table()

    # ── Add course dialog ─────────────────────────────────────────────────────
    def _add_course_dialog(self):
        self._course_form_dialog(None)

    def _edit_course_dialog(self, course):
        self._course_form_dialog(course)

    def _course_form_dialog(self, existing=None):
        win = tk.Toplevel(self.root)
        win.title("Edit Course" if existing else "Add Course")
        win.geometry("520x680")
        win.configure(bg=BG)
        win.grab_set()
        win.resizable(False, False)

        tk.Label(win, text="Edit Course" if existing else "Add New Course",
                 bg=BG, fg=FG, font=("Segoe UI", 13, "bold")).pack(pady=(14, 6))

        g = tk.Frame(win, bg=BG)
        g.pack(fill=tk.X, padx=24)
        g.columnconfigure(1, weight=1)

        def row(label, widget_factory, r):
            tk.Label(g, text=label, bg=BG, fg=SUBTEXT,
                     font=("Segoe UI", 9)).grid(row=r, column=0, sticky="w", pady=4)
            w = widget_factory(g)
            w.grid(row=r, column=1, sticky="ew", pady=4, padx=(10, 0))
            return w

        def entry(parent, var, **kw):
            return tk.Entry(parent, textvariable=var, bg=SURFACE0, fg=FG,
                            insertbackground=FG, relief=tk.FLAT, font=("Segoe UI", 10),
                            highlightthickness=1, highlightcolor=ACCENT,
                            highlightbackground=SURFACE1, **kw)

        name_var   = tk.StringVar(value=existing.get("name", "") if existing else "")
        base_var   = tk.StringVar(value=existing.get("base_module", BASE_MODULES[0]) if existing else BASE_MODULES[0])
        spec_var   = tk.StringVar(value=existing.get("specific_module", "") if existing else "")
        cred_var   = tk.StringVar(value=str(existing.get("credits", 5)) if existing else "5")
        exam_var   = tk.BooleanVar(value=existing.get("exam_given", False) if existing else False)
        edate_var  = tk.StringVar(value=existing.get("exam_date", "") if existing else "")
        etime_var  = tk.StringVar(value=existing.get("exam_time", "") if existing else "")
        adate_var  = tk.StringVar(value=existing.get("alt_date", "") if existing else "")
        atime_var  = tk.StringVar(value=existing.get("alt_time", "") if existing else "")
        info_var   = tk.StringVar(value=existing.get("additional_info", "") if existing else "")
        color_var  = tk.StringVar(value=existing.get("color", COURSE_COLORS[0]) if existing else COURSE_COLORS[0])

        row("Course Name *", lambda p: entry(p, name_var), 0)

        # Base module combobox
        base_cb = ttk.Combobox(g, textvariable=base_var, values=BASE_MODULES,
                               state="readonly", font=("Segoe UI", 10))
        tk.Label(g, text="Base Module", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=4)
        base_cb.grid(row=1, column=1, sticky="ew", pady=4, padx=(10, 0))

        # Specific module combobox — updates when base changes
        tk.Label(g, text="Specific Module", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", pady=4)
        spec_cb = ttk.Combobox(g, textvariable=spec_var, font=("Segoe UI", 10))
        spec_cb.grid(row=2, column=1, sticky="ew", pady=4, padx=(10, 0))

        def update_spec(*_):
            opts = SPECIFIC_MODULES.get(base_var.get(), [""])
            spec_cb["values"] = opts
            if spec_var.get() not in opts:
                spec_var.set(opts[0] if opts else "")

        base_cb.bind("<<ComboboxSelected>>", update_spec)
        update_spec()

        row("Credits", lambda p: entry(p, cred_var, width=6), 3)

        # Exam given checkbox
        tk.Label(g, text="Exam Given?", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).grid(row=4, column=0, sticky="w", pady=4)
        tk.Checkbutton(g, variable=exam_var, bg=BG, fg=FG,
                       selectcolor=SURFACE1, activebackground=BG
                       ).grid(row=4, column=1, sticky="w", pady=4, padx=(10, 0))

        row("Exam Date",  lambda p: entry(p, edate_var), 5)
        row("Exam Time",  lambda p: entry(p, etime_var), 6)
        row("Alt Date",   lambda p: entry(p, adate_var), 7)
        row("Alt Time",   lambda p: entry(p, atime_var), 8)
        row("Additional Info", lambda p: entry(p, info_var), 9)

        # Color picker row
        tk.Label(g, text="Color", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).grid(row=10, column=0, sticky="w", pady=4)
        col_frame = tk.Frame(g, bg=BG)
        col_frame.grid(row=10, column=1, sticky="ew", pady=4, padx=(10, 0))
        color_sw = tk.Label(col_frame, bg=color_var.get(), width=4, relief=tk.FLAT)
        color_sw.pack(side=tk.LEFT)
        pal = tk.Frame(col_frame, bg=BG)
        pal.pack(side=tk.LEFT, padx=6)
        for c in COURSE_COLORS:
            dot = tk.Label(pal, bg=c, width=2, height=1, cursor="hand2")
            dot.pack(side=tk.LEFT, padx=1)
            dot.bind("<Button-1>", lambda e, col=c: (
                color_var.set(col), color_sw.configure(bg=col)))
        tk.Button(col_frame, text="Pick…", bg=SURFACE1, fg=FG,
                  font=("Segoe UI", 8), relief=tk.FLAT, cursor="hand2",
                  command=lambda: (
                      lambda res: (color_var.set(res[1]),
                                   color_sw.configure(bg=res[1]))
                  )(colorchooser.askcolor(color=color_var.get()))
                  if True else None
                  ).pack(side=tk.LEFT, padx=4)

        def commit():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Missing", "Course name is required.", parent=win)
                return
            try:
                credits = int(cred_var.get())
            except Exception:
                messagebox.showwarning("Bad Value", "Credits must be an integer.", parent=win)
                return

            if existing:
                existing.update({
                    "name": name,
                    "base_module": base_var.get(),
                    "specific_module": spec_var.get(),
                    "credits": credits,
                    "exam_given": exam_var.get(),
                    "exam_date": edate_var.get().strip(),
                    "exam_time": etime_var.get().strip(),
                    "alt_date":  adate_var.get().strip(),
                    "alt_time":  atime_var.get().strip(),
                    "additional_info": info_var.get().strip(),
                    "color": color_var.get(),
                })
            else:
                new_course = {
                    "name": name,
                    "base_module": base_var.get(),
                    "specific_module": spec_var.get(),
                    "credits": credits,
                    "exam_given": exam_var.get(),
                    "exam_date": edate_var.get().strip(),
                    "exam_time": etime_var.get().strip(),
                    "alt_date":  adate_var.get().strip(),
                    "alt_time":  atime_var.get().strip(),
                    "additional_info": info_var.get().strip(),
                    "color": color_var.get(),
                    "hidden": False,
                    "slots": [],
                }
                self.sem.setdefault("courses", []).append(new_course)

            self._save()
            win.destroy()
            self._render_table()

        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(pady=14)
        self._btn(btn_row, "Save", ACCENT, CRUST, commit).pack(side=tk.LEFT, padx=6)
        self._btn(btn_row, "Cancel", SURFACE1, FG, win.destroy).pack(side=tk.LEFT)

    # ── Widget helpers ────────────────────────────────────────────────────────
    def _btn(self, p, t, bg, fg, cmd):
        return tk.Button(p, text=t, bg=bg, fg=fg, font=("Segoe UI", 9, "bold"),
                         relief=tk.FLAT, cursor="hand2", padx=10, pady=4,
                         activebackground=ACCENT, activeforeground=CRUST, command=cmd)


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    data_file = sys.argv[1] if len(sys.argv) > 1 else "data.json"
    sem_name  = sys.argv[2] if len(sys.argv) > 2 else ""
    root = tk.Tk()
    SemesterView(root, data_file, sem_name)
    root.mainloop()