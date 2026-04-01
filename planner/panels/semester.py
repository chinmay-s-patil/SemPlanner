"""planner/panels/semester.py — Per-semester course table with exam tracking.

Key fix: the entire table (header + all data rows + totals) lives inside a
single tk.Frame whose columns are configured ONCE.  Every row is placed with
.grid() into that frame, so columns are guaranteed to line up perfectly.
"""

import tkinter as tk
from tkinter import ttk, messagebox, colorchooser

from planner.constants import (
    BG, SURFACE0, SURFACE1, MANTLE, FG, SUBTEXT, OVERLAY,
    ACCENT, GREEN, RED, YELLOW, MAUVE, CRUST, COURSE_COLORS,
)
from planner.utils.io_utils import (
    load_data, save_data,
    get_base_modules, get_specific_modules,
)
from planner.utils.scroll_utils import bind_scroll, rebind_scroll_children


class SemesterPanel:
    COL_DEFS = [
        ("No",               40),
        ("Course Name",     240),
        ("Base Module",     130),
        ("Specific Module", 140),
        ("Credits",          58),
        ("Exam\nGiven?",     68),
        ("Credits\nObtained", 72),
        ("Exam Date",        88),
        ("Exam Time",        66),
        ("Alt Date",         88),
        ("Alt Time",         66),
        ("Additional Info", 155),
        ("",                 36),
    ]
    # Total natural width
    _NAT_W = sum(w for _, w in COL_DEFS)   # ≈ 1251 px

    def __init__(self, container: tk.Frame, hub):
        self.hub       = hub
        self.frame     = tk.Frame(container, bg=BG)
        self.data_file = hub.data_file
        self.data: dict = {}
        self.sem: dict  = {}
        self._init_styles()
        self._build_ui()

    def _init_styles(self):
        s = ttk.Style()
        s.configure("Sem.TCombobox",
                    fieldbackground=SURFACE1, background=SURFACE0,
                    foreground=FG, selectbackground=ACCENT,
                    arrowcolor=SUBTEXT, borderwidth=0)
        s.map("Sem.TCombobox", fieldbackground=[("readonly", SURFACE1)])

    def reload(self):
        try:
            self.data = load_data(self.data_file)
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))
            return
        sems = [s["name"] for s in self.data.get("semesters", [])]
        self.sem_cb["values"] = sems
        cur = self.sem_var.get()
        if cur not in sems:
            self.sem_var.set(sems[-1] if sems else "")
        self._switch_semester()

    # ── UI skeleton ───────────────────────────────────────────────────────────
    def _build_ui(self):
        topbar = tk.Frame(self.frame, bg=CRUST, height=52)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)
        tk.Label(topbar, text="  📊  Semester Credits", bg=CRUST, fg=FG,
                 font=("Segoe UI", 14, "bold")).pack(
            side=tk.LEFT, padx=14, pady=12)
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

        self.summary_bar = tk.Frame(self.frame, bg=MANTLE, pady=6)
        self.summary_bar.pack(fill=tk.X)

        wrap = tk.Frame(self.frame, bg=BG)
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
                                yscrollcommand=vsb.set,
                                xscrollcommand=hsb.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.configure(command=self.canvas.yview)
        hsb.configure(command=self.canvas.xview)

        self.table_frame = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window(
            (0, 0), window=self.table_frame, anchor="nw")

        self.table_frame.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Configure>",      self._on_resize)
        bind_scroll(self.canvas, h_canvas=self.canvas)

    def _on_resize(self, _=None):
        # Always stretch the inner frame to at least the canvas width so there
        # is no wasted horizontal space and no spurious horizontal scrollbar.
        cw = self.canvas.winfo_width()
        self.canvas.itemconfigure(self._win, width=max(cw, self._NAT_W + 4))
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    # ── Data ──────────────────────────────────────────────────────────────────
    def _switch_semester(self, *_):
        name = self.sem_var.get()
        sem  = next((s for s in self.data.get("semesters", [])
                     if s["name"] == name), None)
        if not sem:
            return
        self.sem = sem
        self._render_table()

    def _save(self):
        save_data(self.data, self.data_file)

    # ── Table render (single shared grid) ─────────────────────────────────────
    def _render_table(self):
        for w in self.table_frame.winfo_children():
            w.destroy()
        self._refresh_summary()
        courses = self.sem.get("courses", [])

        # ── One frame, one grid — all rows share the same column definitions ──
        tbl = tk.Frame(self.table_frame, bg=BG)
        tbl.pack(fill=tk.BOTH, expand=True)

        num_cols = len(self.COL_DEFS)
        for ci, (_, width) in enumerate(self.COL_DEFS):
            # Column 1 (Course Name) gets any extra horizontal space
            tbl.columnconfigure(ci, minsize=width,
                                weight=1 if ci == 1 else 0)

        gr = 0  # current grid row

        # ── Header row ────────────────────────────────────────────────────────
        for ci, (label, width) in enumerate(self.COL_DEFS):
            tk.Label(tbl, text=label, bg=SURFACE0, fg=ACCENT,
                     font=("Segoe UI", 9, "bold"),
                     pady=8, padx=4,
                     wraplength=max(width - 8, 20),
                     justify=tk.CENTER,
                     ).grid(row=gr, column=ci, sticky="nsew", padx=1, ipadx=0)
        gr += 1

        # Thick accent separator under header
        tk.Frame(tbl, bg=ACCENT, height=2).grid(
            row=gr, column=0, columnspan=num_cols, sticky="ew")
        gr += 1

        # ── Group courses by base module ──────────────────────────────────────
        by_base: dict = {}
        for course in courses:
            b = course.get("base_module", "Other")
            by_base.setdefault(b, []).append(course)

        row_num = 1
        for base, group in by_base.items():
            tot  = sum(c.get("credits", 0) for c in group)
            done = sum(c.get("credits", 0) for c in group if c.get("exam_given"))

            # Section header spans all columns
            sec = tk.Frame(tbl, bg=SURFACE1, pady=2)
            sec.grid(row=gr, column=0, columnspan=num_cols,
                     sticky="ew", pady=(8, 0))
            tk.Label(sec, text=f"  {base}", bg=SURFACE1, fg=FG,
                     font=("Segoe UI", 10, "bold"), pady=3).pack(side=tk.LEFT)
            tk.Label(sec, text=f"{done}/{tot} ECTS", bg=SURFACE1,
                     fg=GREEN if done >= tot else YELLOW,
                     font=("Segoe UI", 9)).pack(side=tk.RIGHT, padx=12)
            gr += 1

            for ci_c, course in enumerate(group):
                row_bg = SURFACE0 if ci_c % 2 == 0 else BG
                self._place_course_row(tbl, gr, row_num, ci_c, course, row_bg)
                gr += 1
                row_num += 1

        # ── Grand-total row ───────────────────────────────────────────────────
        tk.Frame(tbl, bg=SURFACE1, height=2).grid(
            row=gr, column=0, columnspan=num_cols, sticky="ew", pady=6)
        gr += 1

        total_credits = sum(c.get("credits", 0) for c in courses)
        done_credits  = sum(c.get("credits", 0)
                            for c in courses if c.get("exam_given"))
        for ci, (_, _w) in enumerate(self.COL_DEFS):
            if ci == 1:
                t, fg_c = f"  Total — {row_num - 1} courses", FG
            elif ci == 4:
                t, fg_c = str(total_credits), ACCENT
            elif ci == 6:
                t, fg_c = (str(done_credits),
                           GREEN if done_credits == total_credits else YELLOW)
            else:
                t, fg_c = "", FG
            tk.Label(tbl, text=t, bg=SURFACE0, fg=fg_c,
                     font=("Segoe UI", 10, "bold"),
                     pady=6, padx=4, anchor="w",
                     ).grid(row=gr, column=ci, sticky="nsew", padx=1)

        rebind_scroll_children(self.canvas, self.table_frame,
                               h_canvas=self.canvas)
        self._on_resize()

    # ── Place one course into the shared grid ──────────────────────────────────
    def _place_course_row(self, tbl, gr, row_num, ci, course, bg=BG):
        color   = course.get("color", COURSE_COLORS[ci % len(COURSE_COLORS)])
        credits = course.get("credits", 0)
        exam    = course.get("exam_given", False)

        # Col 0 — colour-dot + row number
        no_f = tk.Frame(tbl, bg=bg)
        no_f.grid(row=gr, column=0, sticky="nsew", padx=1)
        tk.Label(no_f, bg=color, width=3).pack(side=tk.LEFT, fill=tk.Y, padx=(2, 4))
        tk.Label(no_f, text=str(row_num), bg=bg, fg=OVERLAY,
                 font=("Segoe UI", 8), pady=5).pack(side=tk.LEFT)

        # Col 1 — course name (double-click to edit)
        name_lbl = tk.Label(tbl, text=course.get("name", ""),
                            bg=bg, fg=color,
                            font=("Segoe UI", 9, "bold"),
                            pady=5, padx=6, anchor="w",
                            wraplength=self.COL_DEFS[1][1] - 10,
                            justify=tk.LEFT)
        name_lbl.grid(row=gr, column=1, sticky="nsew", padx=1)
        name_lbl.bind("<Double-Button-1>",
                      lambda e, c=course: self._edit_course_dialog(c))

        # Col 2 — base module
        tk.Label(tbl, text=course.get("base_module", ""),
                 bg=bg, fg=SUBTEXT, font=("Segoe UI", 9),
                 pady=5, padx=4, anchor="w",
                 ).grid(row=gr, column=2, sticky="nsew", padx=1)

        # Col 3 — specific module
        tk.Label(tbl, text=course.get("specific_module", ""),
                 bg=bg, fg=SUBTEXT, font=("Segoe UI", 9),
                 pady=5, padx=4, anchor="w",
                 ).grid(row=gr, column=3, sticky="nsew", padx=1)

        # Col 4 — credits
        tk.Label(tbl, text=str(credits),
                 bg=bg, fg=ACCENT, font=("Segoe UI", 9, "bold"),
                 pady=5, padx=4, anchor="center",
                 ).grid(row=gr, column=4, sticky="nsew", padx=1)

        # Col 5 — exam checkbox
        exam_var = tk.BooleanVar(value=exam)
        cb_bg    = "#1a3a1a" if exam else bg
        cb_f     = tk.Frame(tbl, bg=cb_bg)
        cb_f.grid(row=gr, column=5, sticky="nsew", padx=1)
        tk.Checkbutton(
            cb_f, variable=exam_var,
            bg=cb_bg, selectcolor=SURFACE1, activebackground=bg,
            cursor="hand2",
            command=lambda v=exam_var, c=course: self._toggle_exam(c, v),
        ).pack(expand=True)

        # Col 6 — credits obtained
        obtained = credits if exam else 0
        tk.Label(tbl, text=str(obtained),
                 bg=bg, fg=GREEN if exam else OVERLAY,
                 font=("Segoe UI", 9),
                 pady=5, padx=4, anchor="center",
                 ).grid(row=gr, column=6, sticky="nsew", padx=1)

        # Cols 7-10 — date/time fields (click to inline-edit)
        for col_i, field_key in enumerate(
                ["exam_date", "exam_time", "alt_date", "alt_time"], start=7):
            val = course.get(field_key, "") or ""
            lbl = tk.Label(tbl, text=val if val else "—",
                           bg=bg, fg=FG if val else SUBTEXT,
                           font=("Segoe UI", 8),
                           pady=5, padx=4, anchor="w", cursor="hand2")
            lbl.grid(row=gr, column=col_i, sticky="nsew", padx=1)
            lbl.bind("<Button-1>",
                     lambda e, c=course, k=field_key, l=lbl:
                     self._inline_edit(c, k, l))

        # Col 11 — additional info (click to inline-edit)
        info_lbl = tk.Label(tbl,
                            text=course.get("additional_info", "") or "",
                            bg=bg, fg=OVERLAY, font=("Segoe UI", 8),
                            pady=5, padx=4, anchor="w", cursor="hand2",
                            wraplength=self.COL_DEFS[11][1] - 8)
        info_lbl.grid(row=gr, column=11, sticky="nsew", padx=1)
        info_lbl.bind("<Button-1>",
                      lambda e, c=course, l=info_lbl:
                      self._inline_edit(c, "additional_info", l))

        # Col 12 — delete button
        tk.Button(tbl, text="✕", bg=bg, fg=RED, font=("Segoe UI", 9),
                  relief=tk.FLAT, cursor="hand2",
                  command=lambda c=course: self._delete_course(c),
                  ).grid(row=gr, column=12, sticky="nsew", padx=1)

    def _refresh_summary(self):
        for w in self.summary_bar.winfo_children():
            w.destroy()
        courses = self.sem.get("courses", [])
        total = sum(c.get("credits", 0) for c in courses)
        done  = sum(c.get("credits", 0) for c in courses if c.get("exam_given"))
        n     = len(courses)
        pct   = int(done / total * 100) if total else 0
        tk.Label(self.summary_bar,
                 text=f"  {n} courses  |  {total} ECTS registered",
                 bg=MANTLE, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        pb = tk.Frame(self.summary_bar, bg=SURFACE1, height=12, width=200)
        pb.pack(side=tk.LEFT, padx=10)
        pb.pack_propagate(False)
        if pct:
            tk.Frame(pb, bg=GREEN, width=int(200 * pct / 100)).pack(
                side=tk.LEFT, fill=tk.Y)
        tk.Label(self.summary_bar,
                 text=f"{done}/{total} ECTS exam given ({pct}%)",
                 bg=MANTLE, fg=FG,
                 font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=6)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _toggle_exam(self, course, var):
        course["exam_given"] = var.get()
        self._save()
        self._render_table()

    def _inline_edit(self, course, field_key, label):
        win = tk.Toplevel(self.frame)
        win.overrideredirect(True)
        win.configure(bg=SURFACE1)
        x = label.winfo_rootx()
        y = label.winfo_rooty()
        w = max(label.winfo_width(), 120)
        h = label.winfo_height() + 4
        win.geometry(f"{w}x{h}+{x}+{y - 2}")
        var = tk.StringVar(value=course.get(field_key, "") or "")
        e = tk.Entry(win, textvariable=var, bg=SURFACE0, fg=FG,
                     insertbackground=FG, relief=tk.FLAT,
                     font=("Segoe UI", 9), highlightthickness=1,
                     highlightcolor=ACCENT, highlightbackground=ACCENT)
        e.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        e.focus_set()
        e.select_range(0, tk.END)

        def commit(*_):
            course[field_key] = var.get().strip()
            self._save()
            win.destroy()
            self._render_table()

        e.bind("<Return>",   commit)
        e.bind("<FocusOut>", commit)
        e.bind("<Escape>",   lambda e: win.destroy())

    def _delete_course(self, course):
        if messagebox.askyesno(
                "Delete",
                f"Remove '{course.get('name', '')}' from this semester?",
                parent=self.frame):
            self.sem["courses"] = [c for c in self.sem["courses"]
                                   if c is not course]
            self._save()
            self._render_table()

    def _add_course_dialog(self):
        self._course_form_dialog(None)

    def _edit_course_dialog(self, course):
        self._course_form_dialog(course)

    def _course_form_dialog(self, existing=None):
        base_modules     = get_base_modules(self.data)
        specific_modules = get_specific_modules(self.data)

        win = tk.Toplevel(self.frame)
        win.title("Edit Course" if existing else "Add Course")
        win.geometry("520x680")
        win.configure(bg=BG)
        win.grab_set()
        win.resizable(False, False)

        tk.Label(win,
                 text="Edit Course" if existing else "Add New Course",
                 bg=BG, fg=FG,
                 font=("Segoe UI", 13, "bold")).pack(pady=(14, 6))

        g = tk.Frame(win, bg=BG)
        g.pack(fill=tk.X, padx=24)
        g.columnconfigure(1, weight=1)

        def row(label, wf, r):
            tk.Label(g, text=label, bg=BG, fg=SUBTEXT,
                     font=("Segoe UI", 9)).grid(
                row=r, column=0, sticky="w", pady=4)
            w = wf(g)
            w.grid(row=r, column=1, sticky="ew", pady=4, padx=(10, 0))
            return w

        def entry(parent, var, **kw):
            return tk.Entry(parent, textvariable=var, bg=SURFACE0, fg=FG,
                            insertbackground=FG, relief=tk.FLAT,
                            font=("Segoe UI", 10), highlightthickness=1,
                            highlightcolor=ACCENT,
                            highlightbackground=SURFACE1, **kw)

        e = existing or {}
        name_var  = tk.StringVar(value=e.get("name", ""))
        base_var  = tk.StringVar(value=e.get("base_module",
                                             base_modules[0] if base_modules else ""))
        spec_var  = tk.StringVar(value=e.get("specific_module", ""))
        cred_var  = tk.StringVar(value=str(e.get("credits", 5)))
        exam_var  = tk.BooleanVar(value=e.get("exam_given", False))
        edate_var = tk.StringVar(value=e.get("exam_date", ""))
        etime_var = tk.StringVar(value=e.get("exam_time", ""))
        adate_var = tk.StringVar(value=e.get("alt_date", ""))
        atime_var = tk.StringVar(value=e.get("alt_time", ""))
        info_var  = tk.StringVar(value=e.get("additional_info", ""))
        color_var = tk.StringVar(value=e.get("color", COURSE_COLORS[0]))

        row("Course Name *", lambda p: entry(p, name_var), 0)
        tk.Label(g, text="Base Module", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).grid(
            row=1, column=0, sticky="w", pady=4)
        base_cb = ttk.Combobox(g, textvariable=base_var,
                               values=base_modules, state="readonly",
                               font=("Segoe UI", 10))
        base_cb.grid(row=1, column=1, sticky="ew", pady=4, padx=(10, 0))

        tk.Label(g, text="Specific Module", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).grid(
            row=2, column=0, sticky="w", pady=4)
        spec_cb = ttk.Combobox(g, textvariable=spec_var,
                               font=("Segoe UI", 10))
        spec_cb.grid(row=2, column=1, sticky="ew", pady=4, padx=(10, 0))

        def update_spec(*_):
            opts = specific_modules.get(base_var.get(), [""])
            spec_cb["values"] = opts
            if spec_var.get() not in opts:
                spec_var.set(opts[0] if opts else "")

        base_cb.bind("<<ComboboxSelected>>", update_spec)
        update_spec()

        row("Credits",      lambda p: entry(p, cred_var, width=6), 3)
        tk.Label(g, text="Exam Given?", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).grid(
            row=4, column=0, sticky="w", pady=4)
        tk.Checkbutton(g, variable=exam_var, bg=BG, fg=FG,
                       selectcolor=SURFACE1, activebackground=BG,
                       ).grid(row=4, column=1, sticky="w",
                              pady=4, padx=(10, 0))
        row("Exam Date",       lambda p: entry(p, edate_var), 5)
        row("Exam Time",       lambda p: entry(p, etime_var), 6)
        row("Alt Date",        lambda p: entry(p, adate_var), 7)
        row("Alt Time",        lambda p: entry(p, atime_var), 8)
        row("Additional Info", lambda p: entry(p, info_var),  9)

        tk.Label(g, text="Color", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).grid(
            row=10, column=0, sticky="w", pady=4)
        col_frame = tk.Frame(g, bg=BG)
        col_frame.grid(row=10, column=1, sticky="ew", pady=4, padx=(10, 0))
        color_sw = tk.Label(col_frame, bg=color_var.get(), width=4,
                            relief=tk.FLAT)
        color_sw.pack(side=tk.LEFT)
        pal = tk.Frame(col_frame, bg=BG)
        pal.pack(side=tk.LEFT, padx=6)
        for cc in COURSE_COLORS:
            dot = tk.Label(pal, bg=cc, width=2, height=1, cursor="hand2")
            dot.pack(side=tk.LEFT, padx=1)
            dot.bind("<Button-1>",
                     lambda ev, col=cc: (color_var.set(col),
                                         color_sw.configure(bg=col)))
        tk.Button(col_frame, text="Pick…", bg=SURFACE1, fg=FG,
                  font=("Segoe UI", 8), relief=tk.FLAT, cursor="hand2",
                  command=lambda: (lambda res: (
                      color_var.set(res[1]),
                      color_sw.configure(bg=res[1]),
                  ) if res and res[1] else None)(
                      colorchooser.askcolor(color=color_var.get()))
                  ).pack(side=tk.LEFT, padx=4)

        def commit():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Missing",
                                       "Course name is required.", parent=win)
                return
            try:
                credits = int(cred_var.get())
            except ValueError:
                messagebox.showwarning("Bad Value",
                                       "Credits must be an integer.",
                                       parent=win)
                return
            fields = dict(
                name=name, base_module=base_var.get(),
                specific_module=spec_var.get(), credits=credits,
                exam_given=exam_var.get(),
                exam_date=edate_var.get().strip(),
                exam_time=etime_var.get().strip(),
                alt_date=adate_var.get().strip(),
                alt_time=atime_var.get().strip(),
                additional_info=info_var.get().strip(),
                color=color_var.get(),
            )
            if existing:
                existing.update(fields)
            else:
                fields.update(hidden=False, slots=[])
                self.sem.setdefault("courses", []).append(fields)
            self._save()
            win.destroy()
            self._render_table()

        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(pady=14)
        self._btn(btn_row, "Save",   ACCENT,   CRUST, commit).pack(
            side=tk.LEFT, padx=6)
        self._btn(btn_row, "Cancel", SURFACE1, FG,    win.destroy).pack(
            side=tk.LEFT)

    def _btn(self, p, t, bg, fg, cmd):
        return tk.Button(p, text=t, bg=bg, fg=fg,
                         font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
                         cursor="hand2", padx=10, pady=4,
                         activebackground=ACCENT, activeforeground=CRUST,
                         command=cmd)