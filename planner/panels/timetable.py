"""planner/panels/timetable.py — Weekly timetable view.

Changes:
- Fixed pie chart (donut) at top of sidebar showing credit distribution by module.
- Right-click: "Self Study" toggle (hidden in timetable, counted in credits)
              and "Tag: For Notes" toggle (tag stored in slot JSON, shown with 📝).
- Credits tab: shows 📚 for self-study, 📝 for notes-tagged, respects new statuses.
- Visibility tab: shows status indicators per course.
- Options tab: "📋 Day Schedule" section — pick a day, see all slots listed.
"""

import json
import math
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
        self.hub             = hub
        self.frame           = tk.Frame(container, bg=BG)
        self.data_file       = hub.data_file
        self.data: dict      = {}
        self.courses: list   = []
        # hidden_ids  → not shown in timetable AND not counted in credits
        self.hidden_ids: set      = set()
        # self_study_ids → not shown in timetable BUT counted in credits
        self.self_study_ids: set  = set()
        # notes_ids → slot tagged "for notes" (shown in timetable with 📝)
        self.notes_ids: set       = set()
        self.vis_vars: dict       = {}
        self._tip                 = None
        self._next_id             = 0
        self._tab_btns: list      = []
        self.type_vars: dict      = {}
        self._credits_collapsed: dict = {}
        self._day_view_var        = None
        self._day_view_frame      = None
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
        for t in get_slot_types(self.data):
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

        # ── Right sidebar ─────────────────────────────────────────────────────
        sb = tk.Frame(body, bg=MANTLE, width=296)
        sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0), pady=10)
        sb.pack_propagate(False)

        self._tab_rail = tk.Frame(sb, bg=SURFACE0, width=34)
        self._tab_rail.pack(side=tk.RIGHT, fill=tk.Y)
        self._tab_rail.pack_propagate(False)

        tk.Frame(sb, bg=SURFACE1, width=1).pack(side=tk.RIGHT, fill=tk.Y)

        self._tca = tk.Frame(sb, bg=BG)
        self._tca.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ── Fixed pie chart (always visible at top of sidebar) ────────────────
        self._pie_outer = tk.Frame(self._tca, bg=SURFACE0)
        self._pie_outer.pack(fill=tk.X, side=tk.TOP)

        pie_hdr = tk.Frame(self._pie_outer, bg=SURFACE0)
        pie_hdr.pack(fill=tk.X, padx=6, pady=(4, 0))
        tk.Label(pie_hdr, text="  Credits Overview",
                 bg=SURFACE0, fg=SUBTEXT,
                 font=("Segoe UI", 7, "bold")).pack(side=tk.LEFT)

        self._pie_canvas = tk.Canvas(self._pie_outer, bg=SURFACE0,
                                      highlightthickness=0, height=118)
        self._pie_canvas.pack(fill=tk.X, padx=2)
        self._pie_canvas.bind("<Configure>", lambda e: self._draw_pie())

        self._pie_legend_frame = tk.Frame(self._pie_outer, bg=SURFACE0)
        self._pie_legend_frame.pack(fill=tk.X, padx=6, pady=(0, 4))

        tk.Frame(self._tca, bg=SURFACE1, height=1).pack(fill=tk.X, side=tk.TOP)

        # ── Scrollable tab area below pie ─────────────────────────────────────
        self._tab_area = tk.Frame(self._tca, bg=BG)
        self._tab_area.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

        self.tab_options    = tk.Frame(self._tab_area, bg=BG)
        self.tab_visibility = tk.Frame(self._tab_area, bg=BG)
        self.tab_credits    = tk.Frame(self._tab_area, bg=BG)

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

    # ── Pie chart (donut) ─────────────────────────────────────────────────────
    def _draw_pie(self):
        cv = self._pie_canvas
        cv.delete("all")

        name = self.sem_var.get()
        sem  = next((s for s in self.data.get("semesters", [])
                     if s["name"] == name), None)
        if not sem:
            return

        courses  = sem.get("courses", [])
        by_base: dict = defaultdict(int)
        for c in courses:
            base = c.get("base_module", "") or "Other"
            by_base[base] += c.get("credits", 0)

        total = sum(by_base.values())

        for w in self._pie_legend_frame.winfo_children():
            w.destroy()

        if total == 0:
            cv.create_text(130, 59, text="No credits yet",
                           fill=SUBTEXT, font=("Segoe UI", 9))
            return

        W  = max(cv.winfo_width(), 200)
        H  = 118
        CX = W // 2
        CY = 55
        R2 = 46   # outer radius
        R1 = 26   # inner radius (hole)

        start = -90.0  # start from top (12 o'clock)
        items = list(by_base.items())

        for i, (base, credits) in enumerate(items):
            color  = COURSE_COLORS[i % len(COURSE_COLORS)]
            extent = credits / total * 360
            self._donut_wedge(cv, CX, CY, R1, R2, start, extent, color)
            start += extent

            # Compact legend row
            row = tk.Frame(self._pie_legend_frame, bg=SURFACE0)
            row.pack(fill=tk.X, pady=0)
            tk.Frame(row, bg=color, width=6, height=6).pack(
                side=tk.LEFT, padx=(0, 3), pady=3)
            short = (base[:15] + "…") if len(base) > 15 else base
            tk.Label(row, text=f"{short}: {credits}",
                     bg=SURFACE0, fg=FG,
                     font=("Segoe UI", 7)).pack(side=tk.LEFT)

        # Center donut hole + text
        cv.create_oval(CX - R1 + 2, CY - R1 + 2,
                       CX + R1 - 2, CY + R1 - 2,
                       fill=SURFACE0, outline="")
        cv.create_text(CX, CY - 7, text=str(total),
                       fill=FG, font=("Segoe UI", 12, "bold"))
        cv.create_text(CX, CY + 7, text="ECTS",
                       fill=SUBTEXT, font=("Segoe UI", 7))

    def _donut_wedge(self, cv, cx, cy, r1, r2, start_deg, extent_deg, color):
        if abs(extent_deg) < 0.5:
            return
        steps  = max(int(abs(extent_deg) / 3), 6)
        outer, inner = [], []
        for i in range(steps + 1):
            a = math.radians(start_deg + extent_deg * i / steps)
            outer.append((cx + r2 * math.cos(a), cy + r2 * math.sin(a)))
            inner.append((cx + r1 * math.cos(a), cy + r1 * math.sin(a)))
        pts  = outer + list(reversed(inner))
        flat = [v for p in pts for v in p]
        if len(flat) >= 6:
            cv.create_polygon(flat, fill=color, outline=SURFACE0, width=1)

    # ── Data loading & semester switch ─────────────────────────────────────────
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
                entry["_self_study"]  = course.get("self_study", False)
                entry["_for_notes"]   = "notes" in slot.get("tags", [])
                # Keep live references so we can mutate JSON in place
                entry["_course_ref"]  = course
                entry["_slot_ref"]    = slot
                flat.append(entry)
        self.courses        = flat
        self.hidden_ids     = {e["_id"] for e in flat if e.get("_hidden")}
        self.self_study_ids = {e["_id"] for e in flat if e.get("_self_study")}
        self.notes_ids      = {e["_id"] for e in flat if e.get("_for_notes")}
        self.draw_timetable()
        self.refresh_visibility()
        self.refresh_credits()
        self._draw_pie()
        self._refresh_day_view()

    def _new_id(self):
        self._next_id += 1
        return self._next_id

    def _save_data(self):
        """Write self.data (with all in-memory mutations via refs) to disk."""
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def _save_hidden(self):
        """Propagate hidden_ids → course['hidden'] flags then save."""
        name = self.sem_var.get()
        sem  = next((s for s in self.data.get("semesters", [])
                     if s["name"] == name), None)
        if not sem:
            return
        hidden_names = {e["_course_name"] for e in self.courses
                        if e["_id"] in self.hidden_ids}
        for course in sem["courses"]:
            course["hidden"] = course["name"] in hidden_names
        self._save_data()

    def _hidden_course_names(self) -> set:
        return {e["_course_name"] for e in self.courses
                if e["_id"] in self.hidden_ids}

    def _self_study_course_names(self) -> set:
        return {e["_course_name"] for e in self.courses
                if e["_id"] in self.self_study_ids}

    def _notes_course_names(self) -> set:
        return {e["_course_name"] for e in self.courses
                if e["_id"] in self.notes_ids}

    def _get_sem_courses(self) -> list:
        name = self.sem_var.get()
        sem  = next((s for s in self.data.get("semesters", [])
                     if s["name"] == name), None)
        return sem.get("courses", []) if sem else []

    # ── Toggle actions ─────────────────────────────────────────────────────────
    def _toggle_course_hide(self, entry):
        """Toggle the 'hidden' state (no timetable, no credits) for all slots
        of the course that owns *entry*."""
        course_name  = entry["_course_name"]
        course_slots = [e for e in self.courses
                        if e["_course_name"] == course_name]
        any_hidden   = any(e["_id"] in self.hidden_ids for e in course_slots)
        for e in course_slots:
            if any_hidden:
                self.hidden_ids.discard(e["_id"])
            else:
                self.hidden_ids.add(e["_id"])
        self._save_hidden()
        self.draw_timetable()
        self.refresh_visibility()
        self.refresh_credits()
        self._refresh_day_view()

    def _toggle_self_study(self, entry):
        """Toggle 'self_study' on the owning course (hidden from timetable,
        still counted in credits)."""
        course_ref = entry.get("_course_ref")
        if not course_ref:
            return
        new_val = not course_ref.get("self_study", False)
        course_ref["self_study"] = new_val
        for e in self.courses:
            if e["_course_name"] == entry["_course_name"]:
                e["_self_study"] = new_val
                if new_val:
                    self.self_study_ids.add(e["_id"])
                else:
                    self.self_study_ids.discard(e["_id"])
        self._save_data()
        self.draw_timetable()
        self.refresh_visibility()
        self.refresh_credits()
        self._refresh_day_view()

    def _toggle_for_notes(self, entry):
        """Toggle the 'notes' tag on the specific slot *entry* refers to."""
        slot_ref = entry.get("_slot_ref")
        if not slot_ref:
            return
        tags = slot_ref.setdefault("tags", [])
        eid  = entry["_id"]
        if "notes" in tags:
            tags.remove("notes")
            entry["_for_notes"] = False
            self.notes_ids.discard(eid)
        else:
            tags.append("notes")
            entry["_for_notes"] = True
            self.notes_ids.add(eid)
        self._save_data()
        self.draw_timetable()
        self.refresh_visibility()
        self.refresh_credits()
        self._refresh_day_view()

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
        c._frame     = frame
        c._txt_id    = tid
        c._accent_id = aid
        c._h         = h
        c._active    = False
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
        tk.Checkbutton(dr, text="Show extended work days",
                       variable=self.show_extended, command=self.draw_timetable,
                       bg=BG, fg=FG, selectcolor=SURFACE1, activebackground=BG,
                       font=("Segoe UI", 9), cursor="hand2").pack(anchor="w")
        tk.Checkbutton(dr, text="Show weekends",
                       variable=self.show_weekends, command=self.draw_timetable,
                       bg=BG, fg=FG, selectcolor=SURFACE1, activebackground=BG,
                       font=("Segoe UI", 9), cursor="hand2").pack(anchor="w")

        self._ph(f, "🕐  Time Range", top=10)
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

        self._ph(f, "🏷  Filter by Type", top=10)
        self._type_frame = tk.Frame(f, bg=BG)
        self._type_frame.pack(fill=tk.X, padx=14)
        for t in _DEFAULT_SLOT_TYPES:
            v = tk.BooleanVar(value=True)
            self.type_vars[t] = v
            tk.Checkbutton(self._type_frame, text=t, variable=v,
                           command=self.draw_timetable,
                           bg=BG, fg=FG, selectcolor=SURFACE1, activebackground=BG,
                           font=("Segoe UI", 8), cursor="hand2").pack(anchor="w")

        # ── Day Schedule ──────────────────────────────────────────────────────
        self._ph(f, "📋  Day Schedule", top=10)
        day_ctrl = tk.Frame(f, bg=BG)
        day_ctrl.pack(fill=tk.X, padx=14, pady=(0, 4))
        self._day_view_var = tk.StringVar(value="Mon")
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_cb = ttk.Combobox(day_ctrl, textvariable=self._day_view_var,
                               values=day_names, state="readonly", width=10,
                               font=("Segoe UI", 9))
        day_cb.pack(side=tk.LEFT)
        day_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_day_view())

        self._day_view_frame = tk.Frame(f, bg=SURFACE0)
        self._day_view_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        self._refresh_day_view()

    def _refresh_day_view(self):
        """Rebuild the day-schedule list for the selected day."""
        if not self._day_view_frame or not self._day_view_var:
            return
        for w in self._day_view_frame.winfo_children():
            w.destroy()

        day   = self._day_view_var.get()
        slots = [e for e in self.courses if e.get("day") == day]
        slots.sort(key=lambda e: (parse_time(e.get("from")) or 0))

        if not slots:
            tk.Label(self._day_view_frame,
                     text="  No classes scheduled.",
                     bg=SURFACE0, fg=OVERLAY, font=("Segoe UI", 8), pady=4
                     ).pack(anchor="w")
            return

        hidden_from_tt = self.hidden_ids | self.self_study_ids

        for sl in slots:
            color    = sl.get("_color", ACCENT)
            eid      = sl["_id"]
            is_hid   = eid in self.hidden_ids
            is_ss    = eid in self.self_study_ids
            is_notes = eid in self.notes_ids
            tt_gone  = eid in hidden_from_tt

            row = tk.Frame(self._day_view_frame, bg=SURFACE0, pady=1)
            row.pack(fill=tk.X)
            tk.Frame(row, bg=color, width=3).pack(side=tk.LEFT, fill=tk.Y)

            inner = tk.Frame(row, bg=SURFACE0)
            inner.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 2), pady=2)

            t_str = f"{sl.get('from', '?')}–{sl.get('to', '?')}"
            tk.Label(inner, text=t_str, bg=SURFACE0, fg=OVERLAY,
                     font=("Segoe UI", 7)).pack(side=tk.LEFT)

            name_fg = OVERLAY if tt_gone else FG
            tk.Label(inner,
                     text=sl.get("_course_name", ""),
                     bg=SURFACE0, fg=name_fg,
                     font=("Segoe UI", 8), anchor="w",
                     wraplength=120).pack(side=tk.LEFT, fill=tk.X, expand=True)

            badges = ""
            if is_hid:   badges += "🚫"
            if is_ss:    badges += "📚"
            if is_notes: badges += "📝"
            if badges:
                tk.Label(inner, text=badges, bg=SURFACE0, fg=OVERLAY,
                         font=("Segoe UI", 8)).pack(side=tk.RIGHT)

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
        self.vis_canvas.configure(scrollregion=self.vis_canvas.bbox("all"))
        self.vis_canvas.itemconfigure(
            self._vwin, width=self.vis_canvas.winfo_width())

    # ── Credits tab ───────────────────────────────────────────────────────────
    def _build_credits_tab(self):
        f = self.tab_credits
        self._cred_summary = tk.Frame(f, bg=SURFACE0, pady=6)
        self._cred_summary.pack(fill=tk.X)

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
        self._cred_canvas.configure(scrollregion=self._cred_canvas.bbox("all"))
        self._cred_canvas.itemconfigure(
            self._cwin, width=self._cred_canvas.winfo_width())

    def refresh_credits(self):
        hidden_names     = self._hidden_course_names()
        self_study_names = self._self_study_course_names()
        notes_names      = self._notes_course_names()
        sem_courses      = self._get_sem_courses()

        groups: dict = defaultdict(lambda: defaultdict(list))
        for c in sem_courses:
            base = c.get("base_module", "") or ""
            spec = c.get("specific_module", "") or ""
            groups[base][spec].append(c)

        total_all = sum(c.get("credits", 0) for c in sem_courses)
        # self_study counts for credits; only truly hidden is excluded
        total_vis = sum(c.get("credits", 0) for c in sem_courses
                        if c.get("name") not in hidden_names)
        total_hid = total_all - total_vis

        # Summary bar
        for w in self._cred_summary.winfo_children():
            w.destroy()
        tk.Label(self._cred_summary, text="  Visible credits:",
                 bg=SURFACE0, fg=SUBTEXT, font=("Segoe UI", 8)).pack(side=tk.LEFT)
        pct = int(total_vis / total_all * 100) if total_all else 0
        pb  = tk.Frame(self._cred_summary, bg=SURFACE1, height=8, width=80)
        pb.pack(side=tk.LEFT, padx=6, pady=2)
        pb.pack_propagate(False)
        if pct:
            tk.Frame(pb, bg=ACCENT, width=int(80 * pct / 100)).pack(
                side=tk.LEFT, fill=tk.Y)
        tk.Label(self._cred_summary, text=f"{total_vis} / {total_all}",
                 bg=SURFACE0, fg=FG, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        if total_hid:
            tk.Label(self._cred_summary, text=f"  ({total_hid} hidden)",
                     bg=SURFACE0, fg=OVERLAY, font=("Segoe UI", 8)).pack(side=tk.LEFT)

        # Body
        for w in self._cred_frame.winfo_children():
            w.destroy()

        sorted_bases = sorted(groups.keys(), key=lambda b: (b == "", b.lower()))
        base_colors: dict = {}
        ci = 0
        for b in sorted_bases:
            if b == "":
                base_colors[b] = RED
            else:
                base_colors[b] = COURSE_COLORS[ci % len(COURSE_COLORS)]
                ci += 1

        for base in sorted_bases:
            specs    = groups[base]
            base_lbl = base if base else _UNASSIGNED_LABEL
            bcolor   = base_colors[base]
            base_vis = sum(c.get("credits", 0)
                           for sp in specs.values() for c in sp
                           if c.get("name") not in hidden_names)
            base_all = sum(c.get("credits", 0)
                           for sp in specs.values() for c in sp)
            collapsed = self._credits_collapsed.get(base, False)
            self._render_credits_base_section(
                base, base_lbl, bcolor, specs,
                base_vis, base_all,
                hidden_names, self_study_names, notes_names, collapsed)

        rebind_scroll_children(self._cred_canvas, self._cred_frame)
        self._cred_resize()

    def _render_credits_base_section(self, base_key, base_lbl, color, specs,
                                      base_vis, base_all,
                                      hidden_names, self_study_names,
                                      notes_names, collapsed):
        outer = tk.Frame(self._cred_frame, bg=BG)
        outer.pack(fill=tk.X, pady=(4, 0))

        hdr = tk.Frame(outer, bg=SURFACE1)
        hdr.pack(fill=tk.X)

        arrow_lbl = tk.Label(hdr, text="▶" if collapsed else "▼",
                             bg=SURFACE1, fg=color,
                             font=("Segoe UI", 8, "bold"), cursor="hand2",
                             padx=4, pady=4)
        arrow_lbl.pack(side=tk.LEFT)
        tk.Label(hdr, text=base_lbl, bg=SURFACE1, fg=color,
                 font=("Segoe UI", 9, "bold"), pady=4).pack(side=tk.LEFT)

        pill = tk.Frame(hdr, bg=SURFACE0, padx=4, pady=1)
        pill.pack(side=tk.RIGHT, padx=6, pady=3)
        fg_c = GREEN if base_vis == base_all else (YELLOW if base_vis > 0 else OVERLAY)
        tk.Label(pill, text=f"{base_vis}/{base_all} ECTS",
                 bg=SURFACE0, fg=fg_c, font=("Segoe UI", 8, "bold")).pack()

        body = tk.Frame(outer, bg=BG)
        if not collapsed:
            body.pack(fill=tk.X)
            self._render_credits_body(
                body, specs, hidden_names, self_study_names, notes_names, color)

        def toggle(_=None):
            self._credits_collapsed[base_key] = \
                not self._credits_collapsed.get(base_key, False)
            if self._credits_collapsed[base_key]:
                body.pack_forget()
                arrow_lbl.configure(text="▶")
            else:
                body.pack(fill=tk.X)
                self._render_credits_body(
                    body, specs, hidden_names, self_study_names, notes_names, color)
                arrow_lbl.configure(text="▼")
            rebind_scroll_children(self._cred_canvas, self._cred_frame)
            self._cred_resize()

        for w in (arrow_lbl, hdr):
            w.bind("<Button-1>", toggle)

    def _render_credits_body(self, parent, specs, hidden_names,
                               self_study_names, notes_names, color):
        for w in parent.winfo_children():
            w.destroy()
        sorted_specs = sorted(specs.keys(), key=lambda s: (s == "", s.lower()))

        for spec in sorted_specs:
            courses  = specs[spec]
            spec_lbl = spec if spec else "(none)"
            vis_cred = sum(c.get("credits", 0) for c in courses
                           if c.get("name") not in hidden_names)
            all_cred = sum(c.get("credits", 0) for c in courses)

            sh = tk.Frame(parent, bg=SURFACE0)
            sh.pack(fill=tk.X, pady=(3, 0), padx=2)
            tk.Label(sh, text=f"   {spec_lbl}", bg=SURFACE0, fg=SUBTEXT,
                     font=("Segoe UI", 8, "italic"), pady=3, anchor="w"
                     ).pack(side=tk.LEFT, fill=tk.X, expand=True)
            fg_s = GREEN if vis_cred == all_cred else (YELLOW if vis_cred > 0 else OVERLAY)
            tk.Label(sh, text=f"{vis_cred}/{all_cred}",
                     bg=SURFACE0, fg=fg_s,
                     font=("Segoe UI", 8, "bold"), pady=3, padx=6
                     ).pack(side=tk.RIGHT)

            for ri, course in enumerate(courses):
                name      = course.get("name", "")
                credits   = course.get("credits", 0)
                ccolor    = course.get("color", color)
                is_hidden = name in hidden_names
                is_ss     = name in self_study_names
                has_notes = name in notes_names

                row_bg = BG if ri % 2 == 0 else SURFACE0
                row    = tk.Frame(parent, bg=row_bg)
                row.pack(fill=tk.X, padx=2)

                tk.Frame(row, bg=ccolor, width=3).pack(side=tk.LEFT, fill=tk.Y)

                # Status badges
                badge = ""
                if is_hidden:  badge += "🚫"
                elif is_ss:    badge += "📚"
                if has_notes:  badge += "📝"
                if badge:
                    tk.Label(row, text=badge, bg=row_bg, fg=OVERLAY,
                             font=("Segoe UI", 7), pady=3, padx=2).pack(side=tk.LEFT)

                # Course name — greyed only if truly hidden, not self-study
                name_fg = OVERLAY if is_hidden else FG
                tk.Label(row, text=name, bg=row_bg, fg=name_fg,
                         font=("Segoe UI", 8), pady=3, padx=2, anchor="w",
                         wraplength=140).pack(side=tk.LEFT, fill=tk.X, expand=True)

                # Credits — TEAL for self-study to show "counted but off-timetable"
                cred_fg = OVERLAY if is_hidden else (TEAL if is_ss else ACCENT)
                tk.Label(row, text=str(credits), bg=row_bg, fg=cred_fg,
                         font=("Segoe UI", 8, "bold"), pady=3, padx=6
                         ).pack(side=tk.RIGHT)

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

        for h in range(sh, eh + 1):
            y = HDR + (h - sh) * HH
            self.canvas.create_line(TW, y, TOT_W, y, fill=SURFACE1, width=1)
            self.canvas.create_text(TW - 7, y + 2, text=f"{h:02d}:00",
                                    fill=OVERLAY, font=("Segoe UI", 8), anchor="e")
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
                        self.canvas.create_text(TW - 7, yy + lo, text=f"{h:02d}:30",
                                                fill=OVERLAY, font=("Segoe UI", 7),
                                                anchor="e")
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
            self.canvas.create_text((x0 + x1) // 2, HDR // 2,
                                    text=day_full.get(day, day).upper(),
                                    fill=FG, font=("Segoe UI", 9, "bold"))

        active_types  = ({t for t, v in self.type_vars.items() if v.get()}
                         if self.type_vars else set(_DEFAULT_SLOT_TYPES))
        # Both "hidden" and "self_study" are excluded from the timetable canvas
        hidden_from_tt = self.hidden_ids | self.self_study_ids

        for di, day in enumerate(days):
            visible = [
                e for e in self.courses
                if e.get("day") == day
                and e.get("_id") not in hidden_from_tt
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

                color    = entry.get("_color", COURSE_COLORS[0])
                bg_c     = hex_blend(color, BG, 0.22)
                dark     = hex_darken(color, 0.65)
                tag      = f"e{id(entry)}"
                is_notes = entry.get("_id") in self.notes_ids

                self.canvas.create_rectangle(
                    x0, y0, x1, y1, fill=bg_c, outline="", tags=tag)
                self.canvas.create_rectangle(
                    x0, y0, x0 + 4, y1, fill=color, outline="", tags=tag)

                if is_notes:
                    # Dashed border + small 📝 badge to distinguish notes slots
                    self.canvas.create_rectangle(
                        x0, y0, x1, y1, fill="", outline=color,
                        width=1, dash=(5, 3), tags=tag)
                    if (y1 - y0) > 18:
                        self.canvas.create_text(
                            x1 - 4, y0 + 4, text="📝",
                            font=("Segoe UI", 7), anchor="ne", tags=tag)
                else:
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
        bh    = y1 - y0
        name  = entry.get("_course_name", "?")
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
            mr  = has_loc + has_lec
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
        # Show active tags
        if entry.get("_for_notes"):
            lines.append("📝  For Notes")
        if entry.get("_self_study"):
            lines.append("📚  Self Study")

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
                    bd=0, relief=tk.FLAT, font=("Segoe UI", 9))

        # Hide course (toggle)
        any_hidden = any(
            e["_id"] in self.hidden_ids
            for e in self.courses
            if e["_course_name"] == entry["_course_name"]
        )
        hide_label = "✓  Hide course" if any_hidden else "    Hide course"
        m.add_command(label=hide_label,
                      command=lambda: self._toggle_course_hide(entry))

        # Self Study (course-level toggle)
        is_ss = entry.get("_self_study", False)
        ss_label = "✓  Self Study" if is_ss else "    Self Study"
        m.add_command(label=ss_label,
                      command=lambda: self._toggle_self_study(entry))

        m.add_separator()

        # For Notes (slot-level tag toggle)
        is_notes = entry["_id"] in self.notes_ids
        notes_label = "✓  Tag: For Notes" if is_notes else "    Tag: For Notes"
        m.add_command(label=notes_label,
                      command=lambda: self._toggle_for_notes(entry))

        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    # ── Visibility ────────────────────────────────────────────────────────────
    def refresh_visibility(self):
        for w in self.vis_frame.winfo_children():
            w.destroy()
        self.vis_vars.clear()

        ss_names    = self._self_study_course_names()
        notes_names = self._notes_course_names()

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

            # Status badges (right side)
            badges = ""
            if cn in ss_names:    badges += "📚"
            if cn in notes_names: badges += "📝"
            if badges:
                tk.Label(row, text=badges, bg=BG, fg=OVERLAY,
                         font=("Segoe UI", 9)).pack(side=tk.RIGHT, padx=4)

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
        self._refresh_day_view()

    def show_all(self):
        self.hidden_ids.clear()
        for v in self.vis_vars.values():
            v.set(True)
        self._save_hidden()
        self.draw_timetable()
        self.refresh_credits()
        self._refresh_day_view()

    def hide_all(self):
        for cid, v in self.vis_vars.items():
            v.set(False)
            self.hidden_ids.add(cid)
        self._save_hidden()
        self.draw_timetable()
        self.refresh_credits()
        self._refresh_day_view()

    # ── Widget helpers ────────────────────────────────────────────────────────
    def _ph(self, parent, text, top=14):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill=tk.X, padx=10, pady=(top, 6))
        tk.Label(f, text=text, bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
        tk.Frame(f, bg=SURFACE1, height=1).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0), pady=6)

    def _lbl(self, p, t):
        return tk.Label(p, text=t, bg=BG, fg=SUBTEXT, font=("Segoe UI", 9))

    def _btn(self, p, t, bg, fg, cmd):
        return tk.Button(p, text=t, bg=bg, fg=fg,
                         font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
                         cursor="hand2", padx=10, pady=4,
                         activebackground=ACCENT, activeforeground=CRUST,
                         command=cmd)