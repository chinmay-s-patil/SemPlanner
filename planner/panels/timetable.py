"""planner/panels/timetable.py — Weekly timetable view.

Changes:
- Added "Credits" tab showing live credit breakdown filtered by visibility.
  Visible courses are counted; hidden courses shown separately in a collapsed
  footer. Groups by base module → specific module, with "" displayed as
  "⚠ Unassigned".
"""

import json
import tkinter as tk
from tkinter import ttk, messagebox
from collections import defaultdict

from planner.constants import (
    BG, SURFACE0, SURFACE1, CRUST, MANTLE, FG, SUBTEXT, OVERLAY,
    ACCENT, GREEN, MAUVE, RED, YELLOW, TEAL, COURSE_COLORS,
)
from planner.utils.io_utils import get_slot_types, get_days, get_day_full
from planner.utils.math_utils import parse_time, hex_darken, hex_blend, assign_columns
from planner.utils.scroll_utils import bind_scroll, rebind_scroll_children

_DEFAULT_SLOT_TYPES = ["Lecture", "Tutorial", "Exercise", "Lab", "Help Session", "Other"]
_UNASSIGNED_LABEL   = "⚠  Unassigned"


class TimetablePanel:
    def __init__(self, container: tk.Frame, hub):
        self.hub         = hub
        self.frame       = tk.Frame(container, bg=BG)
        self.data_file   = hub.data_file
        self.data: dict  = {}
        self.courses: list   = []
        self.hidden_ids: set = set()
        self.vis_vars: dict  = {}
        self._tip        = None
        self._next_id    = 0
        self._tab_btns: list = []
        self.type_vars: dict = {}
        # Track collapse state for each base-module group in Credits tab
        self._credits_collapsed: dict = {}
        self._init_styles()
        self._build_ui()

    # ── Styles ────────────────────────────────────────────────────────────────
    def _init_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TT.TCombobox",
                    fieldbackground="#24273A", background=SURFACE1,
                    foreground=FG, selectbackground=ACCENT,
                    arrowcolor=SUBTEXT, borderwidth=0)
        s.map("TT.TCombobox", fieldbackground=[("readonly", "#24273A")])

    # ── Reload ────────────────────────────────────────────────────────────────
    def reload(self):
        try:
            with open(self.data_file, encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))
            return

        sems = [s["name"] for s in self.data.get("semesters", [])]
        self.sem_cb["values"] = sems
        cur = self.sem_var.get()
        if cur not in sems:
            self.sem_var.set(sems[-1] if sems else "")

        self._sync_type_controls()
        self._switch_semester()

    def _sync_type_controls(self):
        slot_types = get_slot_types(self.data)
        for t in slot_types:
            if t not in self.type_vars:
                self.type_vars[t] = tk.BooleanVar(value=True)

    # ── UI skeleton ───────────────────────────────────────────────────────────
    def _build_ui(self):
        topbar = tk.Frame(self.frame, bg=CRUST, height=52)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)
        tk.Label(topbar, text="  📅  Timetable", bg=CRUST, fg=FG,
                 font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT, padx=6, pady=12)
        tk.Frame(topbar, bg=SURFACE1, width=1).pack(
            side=tk.LEFT, fill=tk.Y, pady=12, padx=10)
        self.sem_var = tk.StringVar()
        self.sem_cb  = ttk.Combobox(topbar, textvariable=self.sem_var,
                                    state="readonly", width=22,
                                    font=("Segoe UI", 10))
        self.sem_cb.pack(side=tk.LEFT, pady=14, padx=4)
        self.sem_cb.bind("<<ComboboxSelected>>", self._switch_semester)

        body = tk.Frame(self.frame, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                         padx=(10, 0), pady=10)
        self.canvas.bind("<Configure>", lambda e: self.draw_timetable())

        sb = tk.Frame(body, bg=MANTLE, width=296)
        sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0), pady=10)
        sb.pack_propagate(False)

        self._tab_rail = tk.Frame(sb, bg=SURFACE0, width=34)
        self._tab_rail.pack(side=tk.RIGHT, fill=tk.Y)
        self._tab_rail.pack_propagate(False)

        tk.Frame(sb, bg=SURFACE1, width=1).pack(side=tk.RIGHT, fill=tk.Y)

        self._tca = tk.Frame(sb, bg=BG)
        self._tca.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tab_options    = tk.Frame(self._tca, bg=BG)
        self.tab_visibility = tk.Frame(self._tca, bg=BG)
        self.tab_credits    = tk.Frame(self._tca, bg=BG)

        for frame, label in [
            (self.tab_options,    "Options"),
            (self.tab_visibility, "Courses"),
            (self.tab_credits,    "Credits"),
        ]:
            self._make_tab_btn(frame, label)

        self._build_options_tab()
        self._build_visibility_tab()
        self._build_credits_tab()
        self._select_tab(self.tab_options, self._tab_btns[0])

    # ── Data ──────────────────────────────────────────────────────────────────
    def _switch_semester(self, *_):
        name = self.sem_var.get()
        sem  = next((s for s in self.data.get("semesters", [])
                     if s["name"] == name), None)
        if not sem:
            return
        self._next_id = 0
        flat: list = []
        for course in sem.get("courses", []):
            color = course.get("color", COURSE_COLORS[0])
            for slot in course.get("slots", []):
                entry = dict(slot)
                entry["_course_name"] = course["name"]
                entry["_base_module"] = course.get("base_module", "")
                entry["_color"]       = color
                entry["_id"]          = self._new_id()
                entry["_hidden"]      = course.get("hidden", False)
                flat.append(entry)
        self.courses    = flat
        self.hidden_ids = {e["_id"] for e in flat if e.get("_hidden")}
        self.draw_timetable()
        self.refresh_visibility()
        self.refresh_credits()

    def _new_id(self):
        self._next_id += 1
        return self._next_id

    def _save_hidden(self):
        name = self.sem_var.get()
        sem  = next((s for s in self.data.get("semesters", [])
                     if s["name"] == name), None)
        if not sem:
            return
        hidden_names = {e["_course_name"] for e in self.courses
                        if e["_id"] in self.hidden_ids}
        for course in sem["courses"]:
            course["hidden"] = course["name"] in hidden_names
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def _hidden_course_names(self) -> set:
        """Return the set of course names that are currently hidden."""
        return {e["_course_name"] for e in self.courses
                if e["_id"] in self.hidden_ids}

    def _get_sem_courses(self) -> list:
        """Return the raw course dicts for the selected semester."""
        name = self.sem_var.get()
        sem  = next((s for s in self.data.get("semesters", [])
                     if s["name"] == name), None)
        return sem.get("courses", []) if sem else []

    # ── Tab rail ──────────────────────────────────────────────────────────────
    def _make_tab_btn(self, frame, label):
        h = len(label) * 11 + 26
        c = tk.Canvas(self._tab_rail, bg=SURFACE0, width=34, height=h,
                      highlightthickness=0, cursor="hand2")
        c.pack(pady=(8, 0), fill=tk.X)
        tid = c.create_text(17, h // 2, text=label, angle=90,
                            fill=SUBTEXT, font=("Segoe UI", 8, "bold"),
                            anchor="center")
        aid = c.create_rectangle(0, 0, 0, h, fill=ACCENT, outline="")
        c._frame      = frame
        c._txt_id     = tid
        c._accent_id  = aid
        c._h          = h
        c._active     = False
        c.bind("<Button-1>", lambda e, f=frame, cv=c: self._select_tab(f, cv))
        c.bind("<Enter>",    lambda e, cv=c:
               cv.configure(bg=SURFACE1) if not cv._active else None)
        c.bind("<Leave>",    lambda e, cv=c:
               cv.configure(bg=SURFACE0) if not cv._active else None)
        self._tab_btns.append(c)

    def _select_tab(self, frame, btn_c):
        for c in self._tab_btns:
            c._frame.pack_forget()
            c.configure(bg=SURFACE0)
            c.itemconfigure(c._txt_id, fill=SUBTEXT)
            c.coords(c._accent_id, 0, 0, 0, c._h)
            c._active = False
        frame.pack(fill=tk.BOTH, expand=True)
        btn_c.configure(bg=BG)
        btn_c.itemconfigure(btn_c._txt_id, fill=FG)
        btn_c.coords(btn_c._accent_id, 0, 0, 3, btn_c._h)
        btn_c._active = True

    # ── Options tab ───────────────────────────────────────────────────────────
    def _build_options_tab(self):
        f = self.tab_options

        self._ph(f, "📆  Days")
        dr = tk.Frame(f, bg=BG)
        dr.pack(fill=tk.X, padx=14, pady=(0, 6))

        self.show_extended = tk.BooleanVar(value=False)
        self.show_weekends = tk.BooleanVar(value=False)

        tk.Checkbutton(
            dr, text="Show extended work days",
            variable=self.show_extended, command=self.draw_timetable,
            bg=BG, fg=FG, selectcolor=SURFACE1, activebackground=BG,
            font=("Segoe UI", 9), cursor="hand2",
        ).pack(anchor="w")
        tk.Checkbutton(
            dr, text="Show weekends",
            variable=self.show_weekends, command=self.draw_timetable,
            bg=BG, fg=FG, selectcolor=SURFACE1, activebackground=BG,
            font=("Segoe UI", 9), cursor="hand2",
        ).pack(anchor="w")

        self._ph(f, "🕐  Time Range", top=14)
        tr = tk.Frame(f, bg=BG)
        tr.pack(fill=tk.X, padx=14, pady=(0, 6))
        self.start_h = tk.StringVar(value="8")
        self.end_h   = tk.StringVar(value="20")
        for lt, var, vals, col in [
            ("From", self.start_h, [str(h) for h in range(6, 15)],  0),
            ("To",   self.end_h,   [str(h) for h in range(14, 24)], 2),
        ]:
            self._lbl(tr, lt).grid(row=0, column=col, sticky="w")
            cb = ttk.Combobox(tr, textvariable=var, width=5,
                              state="readonly", values=vals)
            cb.grid(row=0, column=col + 1, padx=6)
            cb.bind("<<ComboboxSelected>>", lambda e: self.draw_timetable())

        self._ph(f, "🏷  Filter by Type", top=14)
        self._type_frame = tk.Frame(f, bg=BG)
        self._type_frame.pack(fill=tk.X, padx=14)
        for t in _DEFAULT_SLOT_TYPES:
            v = tk.BooleanVar(value=True)
            self.type_vars[t] = v
            tk.Checkbutton(
                self._type_frame, text=t, variable=v,
                command=self.draw_timetable,
                bg=BG, fg=FG, selectcolor=SURFACE1, activebackground=BG,
                font=("Segoe UI", 8), cursor="hand2",
            ).pack(anchor="w")

    # ── Visibility tab ────────────────────────────────────────────────────────
    def _build_visibility_tab(self):
        f = self.tab_visibility
        self._ph(f, "👁  Show / Hide")
        br = tk.Frame(f, bg=BG)
        br.pack(fill=tk.X, padx=14, pady=(0, 8))
        self._btn(br, "Show All", SURFACE1, FG, self.show_all).pack(
            side=tk.LEFT, padx=(0, 6))
        self._btn(br, "Hide All", SURFACE1, FG, self.hide_all).pack(
            side=tk.LEFT)

        wrap = tk.Frame(f, bg=BG)
        wrap.pack(fill=tk.BOTH, expand=True, padx=6)
        vsb = tk.Scrollbar(wrap, orient=tk.VERTICAL, bg=SURFACE1,
                           troughcolor=SURFACE0, relief=tk.FLAT,
                           highlightthickness=0)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.vis_canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0,
                                    yscrollcommand=vsb.set)
        self.vis_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.configure(command=self.vis_canvas.yview)

        self.vis_frame = tk.Frame(self.vis_canvas, bg=BG)
        self._vwin = self.vis_canvas.create_window(
            (0, 0), window=self.vis_frame, anchor="nw")
        self.vis_frame.bind("<Configure>", self._vis_resize)
        self.vis_canvas.bind("<Configure>", self._vis_resize)
        bind_scroll(self.vis_canvas)

    def _vis_resize(self, _=None):
        self.vis_canvas.configure(
            scrollregion=self.vis_canvas.bbox("all"))
        self.vis_canvas.itemconfigure(
            self._vwin, width=self.vis_canvas.winfo_width())

    # ── Credits tab ───────────────────────────────────────────────────────────
    def _build_credits_tab(self):
        """Build the static skeleton for the Credits tab (scrollable)."""
        f = self.tab_credits

        # Summary strip at top
        self._cred_summary = tk.Frame(f, bg=SURFACE0, pady=6)
        self._cred_summary.pack(fill=tk.X)

        # Scrollable body
        wrap = tk.Frame(f, bg=BG)
        wrap.pack(fill=tk.BOTH, expand=True)

        vsb = tk.Scrollbar(wrap, orient=tk.VERTICAL, bg=SURFACE1,
                           troughcolor=SURFACE0, relief=tk.FLAT,
                           highlightthickness=0)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._cred_canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0,
                                      yscrollcommand=vsb.set)
        self._cred_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.configure(command=self._cred_canvas.yview)

        self._cred_frame = tk.Frame(self._cred_canvas, bg=BG)
        self._cwin = self._cred_canvas.create_window(
            (0, 0), window=self._cred_frame, anchor="nw")
        self._cred_frame.bind("<Configure>", self._cred_resize)
        self._cred_canvas.bind("<Configure>", self._cred_resize)
        bind_scroll(self._cred_canvas)

    def _cred_resize(self, _=None):
        self._cred_canvas.configure(
            scrollregion=self._cred_canvas.bbox("all"))
        self._cred_canvas.itemconfigure(
            self._cwin, width=self._cred_canvas.winfo_width())

    def refresh_credits(self):
        """Rebuild the Credits tab content based on current visibility."""
        # ── Gather data ───────────────────────────────────────────────────────
        hidden_names = self._hidden_course_names()
        sem_courses  = self._get_sem_courses()

        # Group courses: {base: {specific: [course_dict, ...]}}
        groups: dict = defaultdict(lambda: defaultdict(list))
        for c in sem_courses:
            base = c.get("base_module", "") or ""
            spec = c.get("specific_module", "") or ""
            groups[base][spec].append(c)

        # ── Totals ────────────────────────────────────────────────────────────
        total_all  = sum(c.get("credits", 0) for c in sem_courses)
        total_vis  = sum(c.get("credits", 0) for c in sem_courses
                         if c.get("name") not in hidden_names)
        total_hid  = total_all - total_vis

        # ── Summary strip ─────────────────────────────────────────────────────
        for w in self._cred_summary.winfo_children():
            w.destroy()

        tk.Label(self._cred_summary, text="  Visible credits:",
                 bg=SURFACE0, fg=SUBTEXT,
                 font=("Segoe UI", 8)).pack(side=tk.LEFT)

        pct = int(total_vis / total_all * 100) if total_all else 0
        pb  = tk.Frame(self._cred_summary, bg=SURFACE1, height=8, width=80)
        pb.pack(side=tk.LEFT, padx=6, pady=2)
        pb.pack_propagate(False)
        if pct:
            tk.Frame(pb, bg=ACCENT,
                     width=int(80 * pct / 100)).pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(self._cred_summary,
                 text=f"{total_vis} / {total_all}",
                 bg=SURFACE0, fg=FG,
                 font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)

        if total_hid:
            tk.Label(self._cred_summary,
                     text=f"  ({total_hid} hidden)",
                     bg=SURFACE0, fg=OVERLAY,
                     font=("Segoe UI", 8)).pack(side=tk.LEFT)

        # ── Body ──────────────────────────────────────────────────────────────
        for w in self._cred_frame.winfo_children():
            w.destroy()

        # Determine a consistent color for each base module
        sorted_bases = sorted(groups.keys(),
                              key=lambda b: (b == "", b.lower()))
        base_colors: dict = {}
        ci = 0
        for b in sorted_bases:
            if b == "":
                base_colors[b] = RED
            else:
                base_colors[b] = COURSE_COLORS[ci % len(COURSE_COLORS)]
                ci += 1

        for base in sorted_bases:
            specs     = groups[base]
            base_lbl  = base if base else _UNASSIGNED_LABEL
            bcolor    = base_colors[base]

            base_vis  = sum(c.get("credits", 0)
                            for sp_courses in specs.values()
                            for c in sp_courses
                            if c.get("name") not in hidden_names)
            base_all  = sum(c.get("credits", 0)
                            for sp_courses in specs.values()
                            for c in sp_courses)

            collapsed = self._credits_collapsed.get(base, False)
            self._render_credits_base_section(
                base, base_lbl, bcolor, specs,
                base_vis, base_all, hidden_names, collapsed)

        rebind_scroll_children(self._cred_canvas, self._cred_frame)
        self._cred_resize()

    def _render_credits_base_section(self, base_key, base_lbl, color,
                                     specs: dict, base_vis, base_all,
                                     hidden_names: set, collapsed: bool):
        """Render one collapsible base-module block inside the credits body."""
        outer = tk.Frame(self._cred_frame, bg=BG)
        outer.pack(fill=tk.X, pady=(4, 0))

        # ── Section header ────────────────────────────────────────────────────
        hdr = tk.Frame(outer, bg=SURFACE1, pady=0)
        hdr.pack(fill=tk.X)

        arrow_lbl = tk.Label(hdr,
                             text="▶" if collapsed else "▼",
                             bg=SURFACE1, fg=color,
                             font=("Segoe UI", 8, "bold"), cursor="hand2",
                             padx=4, pady=4)
        arrow_lbl.pack(side=tk.LEFT)

        tk.Label(hdr, text=base_lbl, bg=SURFACE1, fg=color,
                 font=("Segoe UI", 9, "bold"),
                 pady=4).pack(side=tk.LEFT)

        # Mini progress pill
        pill_bg = SURFACE0
        pill_f  = tk.Frame(hdr, bg=pill_bg, padx=4, pady=1)
        pill_f.pack(side=tk.RIGHT, padx=6, pady=3)
        pct_b = int(base_vis / base_all * 100) if base_all else 0
        fg_c  = GREEN if base_vis == base_all else (YELLOW if base_vis > 0 else OVERLAY)
        tk.Label(pill_f,
                 text=f"{base_vis}/{base_all} ECTS",
                 bg=pill_bg, fg=fg_c,
                 font=("Segoe UI", 8, "bold")).pack()

        # ── Detail body (collapsible) ─────────────────────────────────────────
        body = tk.Frame(outer, bg=BG)
        if not collapsed:
            body.pack(fill=tk.X)
            self._render_credits_body(body, specs, hidden_names, color)

        def toggle(_e=None):
            self._credits_collapsed[base_key] = \
                not self._credits_collapsed.get(base_key, False)
            if self._credits_collapsed[base_key]:
                body.pack_forget()
                arrow_lbl.configure(text="▶")
            else:
                body.pack(fill=tk.X)
                self._render_credits_body(body, specs, hidden_names, color)
                arrow_lbl.configure(text="▼")
            rebind_scroll_children(self._cred_canvas, self._cred_frame)
            self._cred_resize()

        for w in (arrow_lbl, hdr):
            w.bind("<Button-1>", toggle)

    def _render_credits_body(self, parent, specs: dict, hidden_names: set, color):
        """Render specific-module sub-rows and individual courses."""
        for w in parent.winfo_children():
            w.destroy()

        sorted_specs = sorted(specs.keys(),
                              key=lambda s: (s == "", s.lower()))

        for spec in sorted_specs:
            courses  = specs[spec]
            spec_lbl = spec if spec else "(none)"

            vis_cred = sum(c.get("credits", 0) for c in courses
                           if c.get("name") not in hidden_names)
            all_cred = sum(c.get("credits", 0) for c in courses)

            # Specific module sub-header
            sh = tk.Frame(parent, bg=SURFACE0, pady=0)
            sh.pack(fill=tk.X, pady=(3, 0), padx=2)

            tk.Label(sh, text=f"   {spec_lbl}",
                     bg=SURFACE0, fg=SUBTEXT,
                     font=("Segoe UI", 8, "italic"),
                     pady=3, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

            pct_s = int(vis_cred / all_cred * 100) if all_cred else 0
            fg_s  = (GREEN  if vis_cred == all_cred
                     else YELLOW if vis_cred > 0
                     else OVERLAY)
            tk.Label(sh, text=f"{vis_cred}/{all_cred}",
                     bg=SURFACE0, fg=fg_s,
                     font=("Segoe UI", 8, "bold"),
                     pady=3, padx=6).pack(side=tk.RIGHT)

            # Individual course rows
            for ri, course in enumerate(courses):
                name    = course.get("name", "")
                credits = course.get("credits", 0)
                ccolor  = course.get("color", color)
                hidden  = name in hidden_names

                row_bg  = BG if ri % 2 == 0 else SURFACE0
                row     = tk.Frame(parent, bg=row_bg, pady=0)
                row.pack(fill=tk.X, padx=2)

                # Color dot
                tk.Frame(row, bg=ccolor, width=3).pack(
                    side=tk.LEFT, fill=tk.Y, padx=(6, 0))

                # Hidden eye indicator
                eye = tk.Label(row,
                               text="  " if not hidden else "🚫",
                               bg=row_bg, fg=OVERLAY,
                               font=("Segoe UI", 7),
                               pady=3, padx=2)
                eye.pack(side=tk.LEFT)

                # Course name (greyed if hidden)
                name_fg = OVERLAY if hidden else FG
                tk.Label(row,
                         text=name,
                         bg=row_bg, fg=name_fg,
                         font=("Segoe UI", 8),
                         pady=3, padx=2, anchor="w",
                         wraplength=140,
                         justify=tk.LEFT,
                         ).pack(side=tk.LEFT, fill=tk.X, expand=True)

                # Credits badge
                cred_fg = OVERLAY if hidden else ACCENT
                tk.Label(row,
                         text=str(credits),
                         bg=row_bg, fg=cred_fg,
                         font=("Segoe UI", 8, "bold"),
                         pady=3, padx=6).pack(side=tk.RIGHT)

    # ── Draw timetable ────────────────────────────────────────────────────────
    def draw_timetable(self):
        self.canvas.delete("all")

        base_days = get_days(self.data) if self.data else ["Mon","Tue","Wed","Thu","Fri"]
        day_full  = get_day_full(self.data) if self.data else {}
        days = list(base_days)
        if self.show_extended.get() or self.show_weekends.get():
            if "Sat" not in days:
                days.append("Sat")
        if self.show_weekends.get():
            if "Sun" not in days:
                days.append("Sun")

        try:
            sh = int(self.start_h.get())
            eh = int(self.end_h.get())
        except Exception:
            sh, eh = 8, 20
        sh = min(sh, eh - 1)
        eh = max(sh + 1, eh)

        cw  = max(self.canvas.winfo_width(),  600)
        ch  = max(self.canvas.winfo_height(), 400)
        TW  = 54
        HDR = 46

        HH    = max(28, (ch - HDR - 10) // (eh - sh))
        DAY_W = max(110, (cw - TW - 18) // len(days))
        TOT_W = TW + len(days) * DAY_W + 4
        TOT_H = HDR + (eh - sh) * HH + 10

        self.canvas.configure(scrollregion=(0, 0, TOT_W, TOT_H))
        self.canvas.create_rectangle(0, 0, TOT_W, TOT_H, fill=BG, outline="")

        for i in range(len(days)):
            x0 = TW + i * DAY_W
            x1 = x0 + DAY_W
            self.canvas.create_rectangle(
                x0, HDR, x1, TOT_H,
                fill=SURFACE0 if i % 2 == 0 else BG, outline="")

        import math
        for h in range(sh, eh + 1):
            y = HDR + (h - sh) * HH
            self.canvas.create_line(TW, y, TOT_W, y, fill=SURFACE1, width=1)
            self.canvas.create_text(TW - 7, y + 2,
                                    text=f"{h:02d}:00",
                                    fill=OVERLAY, font=("Segoe UI", 8),
                                    anchor="e")
            if h < eh:
                for frac, dash, lo in [
                    (0.25, (1, 10), None),
                    (0.50, (3, 6),  2),
                    (0.75, (1, 10), None),
                ]:
                    yy = y + int(HH * frac)
                    self.canvas.create_line(TW, yy, TOT_W, yy,
                                            fill=SURFACE1, width=1, dash=dash)
                    if lo:
                        self.canvas.create_text(
                            TW - 7, yy + lo,
                            text=f"{h:02d}:30",
                            fill=OVERLAY, font=("Segoe UI", 7), anchor="e")
                    else:
                        self.canvas.create_line(TW - 4, yy, TW, yy,
                                                fill=OVERLAY, width=1)

        for i in range(len(days) + 1):
            x = TW + i * DAY_W
            self.canvas.create_line(x, HDR, x, TOT_H, fill=SURFACE1, width=1)

        self.canvas.create_rectangle(0, 0, TOT_W, HDR, fill=MANTLE, outline="")
        self.canvas.create_line(0, HDR, TOT_W, HDR, fill=SURFACE1, width=1)
        for i, day in enumerate(days):
            x0 = TW + i * DAY_W
            x1 = x0 + DAY_W
            self.canvas.create_text(
                (x0 + x1) // 2, HDR // 2,
                text=day_full.get(day, day).upper(),
                fill=FG, font=("Segoe UI", 9, "bold"))

        active_types = ({t for t, v in self.type_vars.items() if v.get()}
                        if self.type_vars else set(_DEFAULT_SLOT_TYPES))

        for di, day in enumerate(days):
            visible = [
                e for e in self.courses
                if e.get("day") == day
                and e.get("_id") not in self.hidden_ids
                and e.get("type", "Lecture") in active_types
            ]
            if not visible:
                continue
            events = [(parse_time(e.get("from")), parse_time(e.get("to")), e)
                      for e in visible]
            events = [(ft, tt, e) for ft, tt, e in events
                      if ft is not None and tt is not None and ft < tt]

            for entry, col_idx, num_cols in assign_columns(events):
                ft = parse_time(entry.get("from"))
                tt = parse_time(entry.get("to"))
                ft = max(ft, sh)
                tt = min(tt, eh)
                if ft >= tt:
                    continue

                col_w = DAY_W / num_cols
                PAD   = 2
                x0 = TW + di * DAY_W + col_idx * col_w + PAD
                x1 = TW + di * DAY_W + (col_idx + 1) * col_w - PAD
                y0 = HDR + (ft - sh) * HH + PAD
                y1 = HDR + (tt - sh) * HH - PAD

                color = entry.get("_color", COURSE_COLORS[0])
                bg_c  = hex_blend(color, BG, 0.22)
                dark  = hex_darken(color, 0.65)
                tag   = f"e{id(entry)}"

                self.canvas.create_rectangle(
                    x0, y0, x1, y1, fill=bg_c, outline="", tags=tag)
                self.canvas.create_rectangle(
                    x0, y0, x0 + 4, y1, fill=color, outline="", tags=tag)
                self.canvas.create_rectangle(
                    x0, y0, x1, y1, fill="", outline=dark, width=1, tags=tag)

                self._draw_event_text(entry, x0, y0, x1, y1, color, col_w, tag)

                self.canvas.tag_bind(tag, "<Enter>",
                                     lambda e, en=entry: self._tip_show(e, en))
                self.canvas.tag_bind(tag, "<Leave>",
                                     lambda e: self._tip_hide())
                self.canvas.tag_bind(tag, "<Button-3>",
                                     lambda e, en=entry: self._ctx(e, en))

    def _draw_event_text(self, entry, x0, y0, x1, y1, color, col_w, tag):
        bh   = y1 - y0
        name = entry.get("_course_name", "?")
        stype = entry.get("type", "")
        tstr  = f"{entry.get('from', '')}–{entry.get('to', '')}  {stype}"
        tw    = max(10, int(col_w) - 18)

        _parts: list = []
        for k in ("campus", "building"):
            if entry.get(k):
                _parts.append(entry[k])
        rn = entry.get("room_no", "") or entry.get("room", "")
        if rn:
            _parts.append(f"Rm {rn}")
        loc = "  ·  ".join(_parts)

        def _clip(text, max_px, cw=7.0):
            mc = max(3, int(max_px / cw))
            return text if len(text) <= mc else text[:mc - 1] + "…"

        def _wrap_clip(text, max_px, max_lines, cw=6.5):
            mc    = max(4, int(max_px / cw))
            words = text.split()
            lines: list = []
            cur   = ""
            for word in words:
                test = (cur + " " + word).strip()
                if len(test) <= mc:
                    cur = test
                else:
                    if cur:
                        lines.append(cur)
                    if len(lines) >= max_lines:
                        break
                    cur = word[:mc]
            if cur and len(lines) < max_lines:
                lines.append(cur)
            if lines and " ".join(lines) != text:
                last = lines[-1]
                lines[-1] = (last[:-1] if len(last) >= mc else last) + "…"
            return "\n".join(lines) if lines else _clip(text, max_px, cw)

        c = self.canvas
        if bh < 20:
            pass
        elif bh < 34:
            c.create_text(x0+8, y0+bh//2,
                          text=_clip(name, tw, 6.5), fill=color,
                          font=("Segoe UI", 8, "bold"), anchor="w", tags=tag)
        elif bh < 56:
            c.create_text(x1-4, y0+4, text=tstr, fill=OVERLAY,
                          font=("Segoe UI", 7), anchor="ne", tags=tag)
            c.create_text(x0+8, y0+15, text=_clip(name, tw, 6.5), fill=color,
                          font=("Segoe UI", 9, "bold"), anchor="nw", tags=tag)
        elif bh < 90:
            c.create_text(x1-4, y0+4, text=tstr, fill=OVERLAY,
                          font=("Segoe UI", 7), anchor="ne", tags=tag)
            nl = max(1, min(2, (bh - 30) // 13))
            nt = _wrap_clip(name, tw, nl)
            nc = nt.count("\n") + 1
            c.create_text(x0+8, y0+15, text=nt, fill=color,
                          font=("Segoe UI", 10, "bold"), anchor="nw", tags=tag)
            ly = y0 + 15 + nc * 13 + 2
            if loc and ly + 11 < y1 - 2:
                c.create_text(x0+8, ly,
                              text=_clip(f"📍 {loc}", tw, 6.0),
                              fill=SUBTEXT, font=("Segoe UI", 7),
                              anchor="nw", tags=tag)
        else:
            c.create_text(x1-4, y0+5, text=tstr, fill=OVERLAY,
                          font=("Segoe UI", 7), anchor="ne", tags=tag)
            has_loc = bool(loc)
            has_lec = bool(bh > 110 and entry.get("lecturer"))
            mr = has_loc + has_lec
            anl = bh - 18 - mr * 12 - 6
            nml = max(1, anl // 14)
            nt  = _wrap_clip(name, tw, nml, 6.5)
            nc  = nt.count("\n") + 1
            c.create_text(x0+8, y0+15, text=nt, fill=color,
                          font=("Segoe UI", 11, "bold"), anchor="nw", tags=tag)
            my  = y0 + 15 + nc * 14 + 4
            ml: list = []
            if has_loc:
                ml.append(f"📍 {_clip(loc, tw, 6.0)}")
            if has_lec:
                ml.append(f"👤 {_clip(entry['lecturer'], tw, 6.0)}")
            if ml and my + len(ml) * 11 < y1 - 2:
                c.create_text(x0+8, my, text="\n".join(ml), fill=SUBTEXT,
                              font=("Segoe UI", 7), anchor="nw", tags=tag)

    # ── Tooltip ───────────────────────────────────────────────────────────────
    def _tip_show(self, event, entry):
        self._tip_hide()
        lines = [
            entry.get("_course_name", ""),
            f"[{entry.get('type', '')}]",
            f"{entry.get('day', '')}  {entry.get('from', '')} – {entry.get('to', '')}",
        ]
        lp: list = []
        for k in ("campus", "building"):
            if entry.get(k):
                lp.append(entry[k])
        rn = entry.get("room_no", "") or entry.get("room", "")
        if rn:
            lp.append(f"Room {rn}")
        if lp:
            lines.append("📍 " + "  ·  ".join(lp))
        if entry.get("lecturer"):
            lines.append(f"👤 {entry['lecturer']}")
        bm = entry.get("_base_module", "")
        if bm:
            lines.append(f"📚 {bm}")
        self._tip = tk.Toplevel(self.frame)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{event.x_root + 14}+{event.y_root + 10}")
        tk.Label(self._tip, text="\n".join(lines),
                 bg=MANTLE, fg=FG, font=("Segoe UI", 9),
                 relief=tk.FLAT, bd=0, padx=12, pady=10,
                 justify=tk.LEFT).pack()

    def _tip_hide(self):
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

    # ── Context menu ──────────────────────────────────────────────────────────
    def _ctx(self, event, entry):
        m = tk.Menu(self.frame, tearoff=0, bg=SURFACE0, fg=FG,
                    activebackground=ACCENT, activeforeground=CRUST,
                    bd=0, relief=tk.FLAT)
        m.add_command(label="Hide course",
                      command=lambda: self._quick_hide(entry))
        m.tk_popup(event.x_root, event.y_root)

    def _quick_hide(self, entry):
        cid = entry.get("_id")
        if cid is not None:
            self.hidden_ids.add(cid)
            if cid in self.vis_vars:
                self.vis_vars[cid].set(False)
        self._save_hidden()
        self.draw_timetable()
        self.refresh_credits()

    # ── Visibility ────────────────────────────────────────────────────────────
    def refresh_visibility(self):
        for w in self.vis_frame.winfo_children():
            w.destroy()
        self.vis_vars.clear()
        seen: dict = {}
        for entry in self.courses:
            cn = entry["_course_name"]
            if cn not in seen:
                seen[cn] = entry
        for cn, entry in seen.items():
            cid   = entry["_id"]
            color = entry.get("_color", "#888")
            var   = tk.BooleanVar(value=(cid not in self.hidden_ids))
            self.vis_vars[cid] = var
            row = tk.Frame(self.vis_frame, bg=BG)
            row.pack(fill=tk.X, padx=6, pady=2)
            tk.Label(row, bg=color, width=3, height=1,
                     relief=tk.FLAT).pack(side=tk.LEFT, padx=(2, 6))
            col_f = tk.Frame(row, bg=BG)
            col_f.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Checkbutton(
                col_f, text=cn, variable=var, bg=BG, fg=FG,
                selectcolor=SURFACE1, activebackground=BG,
                font=("Segoe UI", 9), cursor="hand2", anchor="w",
                command=lambda i=cid, v=var: self._toggle(i, v),
            ).pack(anchor="w")
            bm = entry.get("_base_module", "")
            if bm:
                tk.Label(col_f, text=bm, bg=BG, fg=OVERLAY,
                         font=("Segoe UI", 7)).pack(anchor="w")

        rebind_scroll_children(self.vis_canvas, self.vis_frame)
        self._vis_resize()

    def _toggle(self, cid, var):
        if var.get():
            self.hidden_ids.discard(cid)
        else:
            self.hidden_ids.add(cid)
        self._save_hidden()
        self.draw_timetable()
        self.refresh_credits()

    def show_all(self):
        self.hidden_ids.clear()
        for v in self.vis_vars.values():
            v.set(True)
        self._save_hidden()
        self.draw_timetable()
        self.refresh_credits()

    def hide_all(self):
        for cid, v in self.vis_vars.items():
            v.set(False)
            self.hidden_ids.add(cid)
        self._save_hidden()
        self.draw_timetable()
        self.refresh_credits()

    # ── Widget helpers ────────────────────────────────────────────────────────
    def _ph(self, parent, text, top=14):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill=tk.X, padx=10, pady=(top, 6))
        tk.Label(f, text=text, bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
        tk.Frame(f, bg=SURFACE1, height=1).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0), pady=6)

    def _lbl(self, p, t):
        return tk.Label(p, text=t, bg=BG, fg=SUBTEXT,
                        font=("Segoe UI", 9))

    def _btn(self, p, t, bg, fg, cmd):
        return tk.Button(p, text=t, bg=bg, fg=fg,
                         font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
                         cursor="hand2", padx=10, pady=4,
                         activebackground=ACCENT, activeforeground=CRUST,
                         command=cmd)