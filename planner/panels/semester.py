"""planner/panels/semester.py — Per-semester course table with exam tracking."""

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
        ("No",            40),
        ("Course Name",   260),
        ("Base Module",   140),
        ("Specific Module", 150),
        ("Credits",       62),
        ("Exam Given?",   80),
        ("Credits\nObtainable", 80),
        ("Exam Date",     90),
        ("Exam Time",     70),
        ("Alt Date",      90),
        ("Alt Time",      70),
        ("Additional Info", 160),
        ("",              40),
    ]

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
        self.canvas.bind("<Configure>", self._on_resize)
        bind_scroll(self.canvas, h_canvas=self.canvas)

    def _on_resize(self, _=None):
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

    # ── Table render ──────────────────────────────────────────────────────────
    def _render_table(self):
        for w in self.table_frame.winfo_children():
            w.destroy()
        self._refresh_summary()
        courses = self.sem.get("courses", [])

        hdr = tk.Frame(self.table_frame, bg=SURFACE0)
        hdr.pack(fill=tk.X)
        for ci, (label, width) in enumerate(self.COL_DEFS):
            tk.Label(hdr, text=label, bg=SURFACE0, fg=ACCENT,
                     font=("Segoe UI", 9, "bold"),
                     width=width // 7, pady=8, padx=4,
                     wraplength=width - 6, justify=tk.CENTER,
                     ).grid(row=0, column=ci, sticky="nsew", padx=1)
            hdr.columnconfigure(ci, minsize=width)
        tk.Frame(self.table_frame, bg=ACCENT, height=2).pack(fill=tk.X)

        by_base: dict = {}
        for course in courses:
            b = course.get("base_module", "Other")
            by_base.setdefault(b, []).append(course)

        row_num = 1
        for base, group in by_base.items():
            sec = tk.Frame(self.table_frame, bg=SURFACE1, pady=2)
            sec.pack(fill=tk.X, pady=(8, 0))
            tk.Label(sec, text=f"  {base}", bg=SURFACE1, fg=FG,
                     font=("Segoe UI", 10, "bold"), pady=3).pack(side=tk.LEFT)
            tot  = sum(c.get("credits", 0) for c in group)
            done = sum(c.get("credits", 0)
                       for c in group if c.get("exam_given"))
            tk.Label(sec, text=f"{done}/{tot} ECTS", bg=SURFACE1,
                     fg=GREEN if done >= tot else YELLOW,
                     font=("Segoe UI", 9)).pack(side=tk.RIGHT, padx=12)
            for ci, course in enumerate(group):
                self._render_course_row(row_num, ci, course,
                                        bg=SURFACE0 if ci % 2 == 0 else BG)
                row_num += 1

        tk.Frame(self.table_frame, bg=SURFACE1, height=2).pack(
            fill=tk.X, pady=6)
        tot_frame = tk.Frame(self.table_frame, bg=SURFACE0)
        tot_frame.pack(fill=tk.X)
        total_credits = sum(c.get("credits", 0) for c in courses)
        done_credits  = sum(c.get("credits", 0)
                            for c in courses if c.get("exam_given"))
        for i, (text, width) in enumerate(self.COL_DEFS):
            if i == 1:
                t, fg_c = f"Total — {row_num - 1} courses", FG
            elif i == 4:
                t, fg_c = str(total_credits), ACCENT
            elif i == 6:
                t, fg_c = (str(done_credits),
                           GREEN if done_credits == total_credits else YELLOW)
            else:
                t, fg_c = "", FG
            tk.Label(tot_frame, text=t, bg=SURFACE0, fg=fg_c,
                     font=("Segoe UI", 10, "bold"),
                     width=width // 7, pady=6, padx=4,
                     ).grid(row=0, column=i, sticky="nsew", padx=1)
            tot_frame.columnconfigure(i, minsize=width)

        rebind_scroll_children(self.canvas, self.table_frame,
                               h_canvas=self.canvas)

    def _render_course_row(self, row_num, ci, course, bg=BG):
        row   = tk.Frame(self.table_frame, bg=bg)
        row.pack(fill=tk.X)
        color   = course.get("color", COURSE_COLORS[ci % len(COURSE_COLORS)])
        credits = course.get("credits", 0)
        exam    = course.get("exam_given", False)

        def make_lbl(text, width, fg_c=FG, bold=False):
            return tk.Label(row, text=text, bg=bg, fg=fg_c,
                            font=("Segoe UI", 9, "bold" if bold else "normal"),
                            width=width // 7, pady=5, padx=4, anchor="w")

        no_frame = tk.Frame(row, bg=bg)
        no_frame.grid(row=0, column=0, sticky="nsew", padx=1)
        tk.Label(no_frame, bg=color, width=3, height=1).pack(
            side=tk.LEFT, padx=2)
        tk.Label(no_frame, text=str(row_num), bg=bg, fg=OVERLAY,
                 font=("Segoe UI", 8)).pack(side=tk.LEFT)
        row.columnconfigure(0, minsize=self.COL_DEFS[0][1])

        name_lbl = tk.Label(row, text=course.get("name", ""), bg=bg,
                            fg=color, font=("Segoe UI", 9, "bold"),
                            width=self.COL_DEFS[1][1] // 7,
                            pady=5, padx=4, anchor="w",
                            wraplength=self.COL_DEFS[1][1] - 8,
                            justify=tk.LEFT)
        name_lbl.grid(row=0, column=1, sticky="nsew", padx=1)
        name_lbl.bind("<Double-Button-1>",
                      lambda e, c=course: self._edit_course_dialog(c))
        row.columnconfigure(1, minsize=self.COL_DEFS[1][1])

        make_lbl(course.get("base_module", ""),
                 self.COL_DEFS[2][1], SUBTEXT).grid(
            row=0, column=2, sticky="nsew", padx=1)
        row.columnconfigure(2, minsize=self.COL_DEFS[2][1])

        make_lbl(course.get("specific_module", ""),
                 self.COL_DEFS[3][1], SUBTEXT).grid(
            row=0, column=3, sticky="nsew", padx=1)
        row.columnconfigure(3, minsize=self.COL_DEFS[3][1])

        make_lbl(str(credits), self.COL_DEFS[4][1], ACCENT, bold=True).grid(
            row=0, column=4, sticky="nsew", padx=1)
        row.columnconfigure(4, minsize=self.COL_DEFS[4][1])

        exam_var = tk.BooleanVar(value=exam)
        exam_bg  = "#1a3a1a" if exam else bg
        cb = tk.Checkbutton(row, variable=exam_var, bg=exam_bg,
                            selectcolor=SURFACE1, activebackground=bg,
                            cursor="hand2",
                            command=lambda v=exam_var, c=course, r=row:
                            self._toggle_exam(c, v, r))
        cb.grid(row=0, column=5, sticky="nsew", padx=1)
        row.columnconfigure(5, minsize=self.COL_DEFS[5][1])

        obtainable = credits if exam else 0
        make_lbl(str(obtainable), self.COL_DEFS[6][1],
                 GREEN if exam else OVERLAY).grid(
            row=0, column=6, sticky="nsew", padx=1)
        row.columnconfigure(6, minsize=self.COL_DEFS[6][1])

        for col_i, field_key in enumerate(
                ["exam_date", "exam_time", "alt_date", "alt_time"], start=7):
            val = course.get(field_key, "")
            lbl = tk.Label(row, text=val or "—",
                           bg=bg, fg=SUBTEXT if not val else FG,
                           font=("Segoe UI", 8),
                           width=self.COL_DEFS[col_i][1] // 7,
                           pady=5, padx=4, anchor="w", cursor="hand2")
            lbl.grid(row=0, column=col_i, sticky="nsew", padx=1)
            lbl.bind("<Button-1>",
                     lambda e, c=course, k=field_key, l=lbl:
                     self._inline_edit(c, k, l))
            row.columnconfigure(col_i, minsize=self.COL_DEFS[col_i][1])

        info_lbl = tk.Label(row, text=course.get("additional_info", "") or "",
                            bg=bg, fg=OVERLAY, font=("Segoe UI", 8),
                            width=self.COL_DEFS[11][1] // 7,
                            pady=5, padx=4, anchor="w", cursor="hand2",
                            wraplength=self.COL_DEFS[11][1] - 8)
        info_lbl.grid(row=0, column=11, sticky="nsew", padx=1)
        info_lbl.bind("<Button-1>",
                      lambda e, c=course, l=info_lbl:
                      self._inline_edit(c, "additional_info", l))
        row.columnconfigure(11, minsize=self.COL_DEFS[11][1])

        tk.Button(row, text="✕", bg=bg, fg=RED, font=("Segoe UI", 9),
                  relief=tk.FLAT, cursor="hand2",
                  command=lambda c=course: self._delete_course(c),
                  ).grid(row=0, column=12, sticky="nsew", padx=1)
        row.columnconfigure(12, minsize=self.COL_DEFS[12][1])

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
    def _toggle_exam(self, course, var, row):
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

        e.bind("<Return>", commit)
        e.bind("<FocusOut>", commit)
        e.bind("<Escape>", lambda e: win.destroy())

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
        base_modules    = get_base_modules(self.data)
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
        base_var  = tk.StringVar(value=e.get("base_module", base_modules[0] if base_modules else ""))
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
                                       "Credits must be an integer.", parent=win)
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
