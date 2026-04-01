"""
timetable_view.py  —  Weekly Timetable View
Reads from the shared data.json; displays timetable for a chosen semester.
Launch: python timetable_view.py data.json [SemName]
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
CRUST    = "#11111B"
MANTLE   = "#181825"
FG       = "#CDD6F4"
SUBTEXT  = "#A6ADC8"
OVERLAY  = "#7F849C"
ACCENT   = "#89B4FA"
RED      = "#F38BA8"
ENTRY_BG = "#24273A"

COURSE_COLORS = [
    "#89B4FA", "#A6E3A1", "#FAB387", "#CBA6F7",
    "#F38BA8", "#94E2D5", "#F9E2AF", "#74C7EC",
    "#B4BEFE", "#EBA0AC",
]

DAYS     = ["Mon", "Tue", "Wed", "Thu", "Fri"]
DAY_FULL = {
    "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday",
    "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday",
}

SLOT_TYPES = ["Lecture", "Tutorial", "Exercise", "Lab", "Help Session", "Other"]


# ── Helpers ───────────────────────────────────────────────────────────────────
def parse_time(t):
    try:
        parts = str(t).replace(":", ".").split(".")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return h + m / 60
    except Exception:
        return None


def hex_darken(hx, factor=0.6):
    hx = hx.lstrip("#")
    r, g, b = (int(hx[i:i+2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(int(r*factor), int(g*factor), int(b*factor))


def hex_blend(hx, bg=BG, alpha=0.22):
    hx = hx.lstrip("#"); bg = bg.lstrip("#")
    r1, g1, b1 = (int(hx[i:i+2], 16) for i in (0, 2, 4))
    r2, g2, b2 = (int(bg[i:i+2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(
        int(r1*alpha + r2*(1-alpha)),
        int(g1*alpha + g2*(1-alpha)),
        int(b1*alpha + b2*(1-alpha)),
    )


def assign_columns(events):
    if not events:
        return []
    events = sorted(events, key=lambda x: x[0])
    n = len(events)
    col = [-1] * n
    for i in range(n):
        used = {col[j] for j in range(i) if events[j][1] > events[i][0]}
        c = 0
        while c in used:
            c += 1
        col[i] = c
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for i in range(n):
        for j in range(i+1, n):
            if events[i][0] < events[j][1] and events[j][0] < events[i][1]:
                union(i, j)
    group_max = {}
    for i in range(n):
        g = find(i)
        group_max[g] = max(group_max.get(g, 0), col[i])
    return [(events[i][2], col[i], group_max[find(i)] + 1) for i in range(n)]


# ── App ───────────────────────────────────────────────────────────────────────
class TimetableView:
    def __init__(self, root: tk.Tk, data_file: str, sem_name: str = ""):
        self.root = root
        self.data_file = data_file
        self.root.title("Timetable")
        self.root.geometry("1380x820")
        self.root.minsize(960, 640)
        self.root.configure(bg=BG)

        self.data: dict = {}
        self.sem_name = sem_name
        self.courses: list = []
        self.hidden_ids: set = set()
        self.vis_vars: dict = {}
        self._tip = None
        self._next_id = 0
        self._tab_btns: list = []

        self._styles()
        self._build_ui()
        self._load_data()

    def _styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TFrame",    background=SURFACE0)
        s.configure("TLabel",    background=SURFACE0, foreground=FG)
        s.configure("TCombobox", fieldbackground=ENTRY_BG, background=SURFACE1,
                    foreground=FG, selectbackground=ACCENT, arrowcolor=SUBTEXT,
                    borderwidth=0)
        s.map("TCombobox", fieldbackground=[("readonly", ENTRY_BG)])

    # ── Data ──────────────────────────────────────────────────────────────────
    def _load_data(self):
        try:
            with open(self.data_file, encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))
            self.data = {"semesters": []}
            return

        sems = [s["name"] for s in self.data.get("semesters", [])]
        self.sem_cb["values"] = sems
        if self.sem_name and self.sem_name in sems:
            self.sem_var.set(self.sem_name)
        elif sems:
            self.sem_var.set(sems[-1])
        self._switch_semester()

    def _switch_semester(self, *_):
        name = self.sem_var.get()
        sem = next((s for s in self.data.get("semesters", [])
                    if s["name"] == name), None)
        if not sem:
            return
        self.root.title(f"Timetable — {sem.get('display_name', name)}")

        # Flatten slots → individual timetable entries, preserving course ref
        self._next_id = 0
        flat = []
        for course in sem.get("courses", []):
            color = course.get("color", COURSE_COLORS[0])
            for slot in course.get("slots", []):
                entry = dict(slot)
                entry["_course_name"] = course["name"]
                entry["_base_module"] = course.get("base_module", "")
                entry["_color"]  = color
                entry["_id"]     = self._new_id()
                entry["_hidden"] = course.get("hidden", False)
                flat.append(entry)

        self.courses = flat
        self.hidden_ids = {e["_id"] for e in flat if e.get("_hidden")}
        self.draw_timetable()
        self.refresh_visibility()

    def _new_id(self):
        self._next_id += 1
        return self._next_id

    def _save_hidden(self):
        """Push hidden state back to data and save."""
        name = self.sem_var.get()
        sem = next((s for s in self.data.get("semesters", [])
                    if s["name"] == name), None)
        if not sem:
            return
        hidden_names = {e["_course_name"] for e in self.courses
                        if e["_id"] in self.hidden_ids}
        for course in sem["courses"]:
            course["hidden"] = course["name"] in hidden_names
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    # ── UI skeleton ───────────────────────────────────────────────────────────
    def _build_ui(self):
        topbar = tk.Frame(self.root, bg=CRUST, height=56)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)

        tk.Label(topbar, text="  📅  Timetable",
                 bg=CRUST, fg=FG, font=("Segoe UI", 15, "bold")
                 ).pack(side=tk.LEFT, padx=6, pady=12)

        tk.Frame(topbar, bg=SURFACE1, width=1).pack(
            side=tk.LEFT, fill=tk.Y, pady=12, padx=10)

        self.sem_var = tk.StringVar()
        self.sem_cb = ttk.Combobox(topbar, textvariable=self.sem_var,
                                   state="readonly", width=22,
                                   font=("Segoe UI", 10))
        self.sem_cb.pack(side=tk.LEFT, pady=14, padx=4)
        self.sem_cb.bind("<<ComboboxSelected>>", self._switch_semester)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                         padx=(10, 0), pady=10)
        self.canvas.bind("<Configure>",       lambda e: self.draw_timetable())
        self.canvas.bind("<MouseWheel>",       self._on_vscroll)
        self.canvas.bind("<Shift-MouseWheel>", self._on_hscroll)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        # Sidebar
        sb = tk.Frame(body, bg=MANTLE, width=296)
        sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0), pady=10)
        sb.pack_propagate(False)

        self._tab_rail = tk.Frame(sb, bg=SURFACE0, width=34)
        self._tab_rail.pack(side=tk.RIGHT, fill=tk.Y)
        self._tab_rail.pack_propagate(False)
        tk.Frame(sb, bg=SURFACE1, width=1).pack(side=tk.RIGHT, fill=tk.Y)
        self._tab_content_area = tk.Frame(sb, bg=BG)
        self._tab_content_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tab_options    = tk.Frame(self._tab_content_area, bg=BG)
        self.tab_visibility = tk.Frame(self._tab_content_area, bg=BG)

        for frame, label in [(self.tab_options, "Options"),
                              (self.tab_visibility, "Courses")]:
            self._make_tab_btn(frame, label)

        self._build_options_tab()
        self._build_visibility_tab()
        self._select_tab(self.tab_options, self._tab_btns[0])

    # ── Tab rail ──────────────────────────────────────────────────────────────
    def _make_tab_btn(self, frame, label):
        h = len(label) * 11 + 26
        c = tk.Canvas(self._tab_rail, bg=SURFACE0, width=34, height=h,
                      highlightthickness=0, cursor="hand2")
        c.pack(pady=(8, 0), fill=tk.X)
        txt_id    = c.create_text(17, h//2, text=label, angle=90,
                                  fill=SUBTEXT, font=("Segoe UI", 8, "bold"), anchor="center")
        accent_id = c.create_rectangle(0, 0, 0, h, fill=ACCENT, outline="")
        c._frame = frame; c._txt_id = txt_id; c._accent_id = accent_id
        c._h = h; c._active = False
        c.bind("<Button-1>", lambda e, f=frame, cv=c: self._select_tab(f, cv))
        c.bind("<Enter>",    lambda e, cv=c: cv.configure(bg=SURFACE1) if not cv._active else None)
        c.bind("<Leave>",    lambda e, cv=c: cv.configure(bg=SURFACE0) if not cv._active else None)
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
        day_row = tk.Frame(f, bg=BG)
        day_row.pack(fill=tk.X, padx=14, pady=(0, 6))
        self.show_sat = tk.BooleanVar(value=False)
        self.show_sun = tk.BooleanVar(value=False)
        for text, var in [("Saturday", self.show_sat), ("Sunday", self.show_sun)]:
            tk.Checkbutton(day_row, text=text, variable=var,
                           command=self.draw_timetable,
                           bg=BG, fg=FG, selectcolor=SURFACE1,
                           activebackground=BG, font=("Segoe UI", 9),
                           cursor="hand2").pack(side=tk.LEFT, padx=(0, 8))

        self._ph(f, "🕐  Time Range", top=14)
        tr = tk.Frame(f, bg=BG)
        tr.pack(fill=tk.X, padx=14, pady=(0, 6))
        self.start_h = tk.StringVar(value="8")
        self.end_h   = tk.StringVar(value="20")
        for lbl_text, var, vals, col in [
            ("From", self.start_h, [str(h) for h in range(6, 15)], 0),
            ("To",   self.end_h,   [str(h) for h in range(14, 24)], 2),
        ]:
            self._lbl(tr, lbl_text).grid(row=0, column=col, sticky="w")
            cb = ttk.Combobox(tr, textvariable=var, width=5, state="readonly", values=vals)
            cb.grid(row=0, column=col+1, padx=6)
            cb.bind("<<ComboboxSelected>>", lambda e: self.draw_timetable())

        self._ph(f, "🏷  Filter by Type", top=14)
        type_row = tk.Frame(f, bg=BG)
        type_row.pack(fill=tk.X, padx=14)
        self.type_vars = {}
        for t in SLOT_TYPES:
            v = tk.BooleanVar(value=True)
            self.type_vars[t] = v
            tk.Checkbutton(type_row, text=t, variable=v,
                           command=self.draw_timetable,
                           bg=BG, fg=FG, selectcolor=SURFACE1,
                           activebackground=BG, font=("Segoe UI", 8),
                           cursor="hand2").pack(anchor="w")

    # ── Visibility tab ────────────────────────────────────────────────────────
    def _build_visibility_tab(self):
        f = self.tab_visibility
        self._ph(f, "👁  Show / Hide")
        br = tk.Frame(f, bg=BG)
        br.pack(fill=tk.X, padx=14, pady=(0, 8))
        self._btn(br, "Show All", SURFACE1, FG, self.show_all).pack(side=tk.LEFT, padx=(0, 6))
        self._btn(br, "Hide All", SURFACE1, FG, self.hide_all).pack(side=tk.LEFT)

        wrap = tk.Frame(f, bg=BG)
        wrap.pack(fill=tk.BOTH, expand=True, padx=6)
        vsb = tk.Scrollbar(wrap, orient=tk.VERTICAL, bg=SURFACE1, troughcolor=SURFACE0,
                           relief=tk.FLAT, highlightthickness=0)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.vis_canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0,
                                    yscrollcommand=vsb.set)
        self.vis_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.configure(command=self.vis_canvas.yview)
        self.vis_frame = tk.Frame(self.vis_canvas, bg=BG)
        self._vwin = self.vis_canvas.create_window((0, 0), window=self.vis_frame, anchor="nw")
        self.vis_frame.bind("<Configure>", self._vis_resize)
        self.vis_canvas.bind("<Configure>", self._vis_resize)
        self.vis_canvas.bind("<MouseWheel>",
            lambda e: self.vis_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self.vis_canvas.bind("<Button-4>",
            lambda e: self.vis_canvas.yview_scroll(-1, "units"))
        self.vis_canvas.bind("<Button-5>",
            lambda e: self.vis_canvas.yview_scroll(1, "units"))

    def _vis_resize(self, _=None):
        self.vis_canvas.configure(scrollregion=self.vis_canvas.bbox("all"))
        self.vis_canvas.itemconfigure(self._vwin, width=self.vis_canvas.winfo_width())

    # ── Draw timetable ────────────────────────────────────────────────────────
    def draw_timetable(self):
        self.canvas.delete("all")
        days = list(DAYS)
        if self.show_sat.get(): days.append("Sat")
        if self.show_sun.get(): days.append("Sun")
        try:
            sh = int(self.start_h.get()); eh = int(self.end_h.get())
        except Exception:
            sh, eh = 8, 20
        sh, eh = min(sh, eh-1), max(sh+1, eh)

        cw  = max(self.canvas.winfo_width(), 600)
        TW  = 54; HDR = 46; HH = 80
        DAY_W = max(110, (cw - TW - 18) // len(days))
        TOT_H = HDR + (eh - sh) * HH + 10
        TOT_W = TW + len(days) * DAY_W + 4

        ch = max(self.canvas.winfo_height(), 400)
        self.canvas.configure(scrollregion=(0, 0, TOT_W, max(TOT_H, ch)))
        self.canvas.create_rectangle(0, 0, TOT_W, max(TOT_H, ch), fill=BG, outline="")

        for i in range(len(days)):
            x0 = TW + i * DAY_W; x1 = x0 + DAY_W
            self.canvas.create_rectangle(x0, HDR, x1, TOT_H,
                                         fill=SURFACE0 if i % 2 == 0 else BG, outline="")

        for h in range(sh, eh + 1):
            y = HDR + (h - sh) * HH
            self.canvas.create_line(TW, y, TOT_W, y, fill=SURFACE1, width=1)
            self.canvas.create_text(TW - 7, y + 2, text=f"{h:02d}:00",
                                    fill=OVERLAY, font=("Segoe UI", 8), anchor="e")
            if h < eh:
                for frac, dash, label_offset in [
                    (0.25, (1, 10), None), (0.5, (3, 6), 2), (0.75, (1, 10), None)
                ]:
                    yy = y + int(HH * frac)
                    self.canvas.create_line(TW, yy, TOT_W, yy, fill=SURFACE1, width=1, dash=dash)
                    if label_offset:
                        self.canvas.create_text(TW - 7, yy + label_offset,
                                                text=f"{h:02d}:30", fill=OVERLAY,
                                                font=("Segoe UI", 7), anchor="e")
                    else:
                        self.canvas.create_line(TW - 4, yy, TW, yy, fill=OVERLAY, width=1)

        for i in range(len(days) + 1):
            x = TW + i * DAY_W
            self.canvas.create_line(x, HDR, x, TOT_H, fill=SURFACE1, width=1)

        self.canvas.create_rectangle(0, 0, TOT_W, HDR, fill=MANTLE, outline="")
        self.canvas.create_line(0, HDR, TOT_W, HDR, fill=SURFACE1, width=1)
        for i, day in enumerate(days):
            x0 = TW + i * DAY_W; x1 = x0 + DAY_W
            self.canvas.create_text((x0+x1)//2, HDR//2,
                                    text=DAY_FULL.get(day, day).upper(),
                                    fill=FG, font=("Segoe UI", 9, "bold"))

        # Active slot type filter
        active_types = {t for t, v in self.type_vars.items() if v.get()} if self.type_vars else set(SLOT_TYPES)

        for di, day in enumerate(days):
            visible = [
                e for e in self.courses
                if e.get("day") == day
                and e.get("_id") not in self.hidden_ids
                and e.get("type", "Lecture") in active_types
            ]
            if not visible:
                continue
            events = []
            for e in visible:
                ft = parse_time(e.get("from")); tt = parse_time(e.get("to"))
                if ft is not None and tt is not None and ft < tt:
                    events.append((ft, tt, e))

            for (entry, col_idx, num_cols) in assign_columns(events):
                ft = parse_time(entry.get("from")); tt = parse_time(entry.get("to"))
                ft = max(ft, sh); tt = min(tt, eh)
                if ft >= tt:
                    continue
                col_w = DAY_W / num_cols
                PAD = 2
                x0 = TW + di * DAY_W + col_idx * col_w + PAD
                x1 = TW + di * DAY_W + (col_idx + 1) * col_w - PAD
                y0 = HDR + (ft - sh) * HH + PAD
                y1 = HDR + (tt - sh) * HH - PAD

                color = entry.get("_color", COURSE_COLORS[0])
                bg_c  = hex_blend(color, BG, 0.22)
                dark  = hex_darken(color, 0.65)
                tag   = f"e{id(entry)}"

                self.canvas.create_rectangle(x0, y0, x1, y1, fill=bg_c, outline="", tags=tag)
                self.canvas.create_rectangle(x0, y0, x0+4, y1, fill=color, outline="", tags=tag)
                self.canvas.create_rectangle(x0, y0, x1, y1, fill="", outline=dark, width=1, tags=tag)

                bh  = y1 - y0
                name = entry.get("_course_name", "?")
                slot_type = entry.get("type", "")
                tstr = f"{entry.get('from','')}–{entry.get('to','')}  {slot_type}"
                tw   = max(10, int(col_w) - 18)

                _parts = []
                for k in ("campus", "building"):
                    if entry.get(k): _parts.append(entry[k])
                rn = entry.get("room_no", "") or entry.get("room", "")
                if rn: _parts.append(f"Rm {rn}")
                loc = "  ·  ".join(_parts)

                def _clip(text, max_px, cw=7.0):
                    mc = max(3, int(max_px / cw))
                    return text if len(text) <= mc else text[:mc-1] + "…"

                def _wrap_clip(text, max_px, max_lines, cw=6.5):
                    mc = max(4, int(max_px / cw))
                    words = text.split(); lines = []; cur = ""
                    for word in words:
                        test = (cur + " " + word).strip()
                        if len(test) <= mc: cur = test
                        else:
                            if cur: lines.append(cur)
                            if len(lines) >= max_lines: break
                            cur = word[:mc]
                    if cur and len(lines) < max_lines:
                        lines.append(cur)
                    if lines and " ".join(lines) != text:
                        last = lines[-1]
                        lines[-1] = (last[:-1] if len(last) >= mc else last) + "…"
                    return "\n".join(lines) if lines else _clip(text, max_px, cw)

                if bh < 20:
                    pass
                elif bh < 34:
                    self.canvas.create_text(x0+8, y0+bh//2, text=_clip(name, tw, 6.5),
                                            fill=color, font=("Segoe UI", 8, "bold"),
                                            anchor="w", tags=tag)
                elif bh < 56:
                    self.canvas.create_text(x1-4, y0+4, text=tstr, fill=OVERLAY,
                                            font=("Segoe UI", 7), anchor="ne", tags=tag)
                    self.canvas.create_text(x0+8, y0+15, text=_clip(name, tw, 6.5),
                                            fill=color, font=("Segoe UI", 9, "bold"),
                                            anchor="nw", tags=tag)
                elif bh < 90:
                    self.canvas.create_text(x1-4, y0+4, text=tstr, fill=OVERLAY,
                                            font=("Segoe UI", 7), anchor="ne", tags=tag)
                    nl = max(1, min(2, (bh-30)//13))
                    nt = _wrap_clip(name, tw, nl)
                    nc = nt.count("\n") + 1
                    self.canvas.create_text(x0+8, y0+15, text=nt,
                                            fill=color, font=("Segoe UI", 10, "bold"),
                                            anchor="nw", tags=tag)
                    ly = y0+15+nc*13+2
                    if loc and ly+11 < y1-2:
                        self.canvas.create_text(x0+8, ly, text=_clip(f"📍 {loc}", tw, 6.0),
                                                fill=SUBTEXT, font=("Segoe UI", 7),
                                                anchor="nw", tags=tag)
                else:
                    self.canvas.create_text(x1-4, y0+5, text=tstr, fill=OVERLAY,
                                            font=("Segoe UI", 7), anchor="ne", tags=tag)
                    has_loc = bool(loc)
                    has_lec = bool(bh > 110 and entry.get("lecturer"))
                    mr = has_loc + has_lec
                    anl = bh - 18 - mr*12 - 6
                    nml = max(1, anl//14)
                    nt = _wrap_clip(name, tw, nml, 6.5)
                    nc = nt.count("\n") + 1
                    self.canvas.create_text(x0+8, y0+15, text=nt,
                                            fill=color, font=("Segoe UI", 11, "bold"),
                                            anchor="nw", tags=tag)
                    my = y0+15+nc*14+4
                    ml = []
                    if has_loc: ml.append(f"📍 {_clip(loc, tw, 6.0)}")
                    if has_lec: ml.append(f"👤 {_clip(entry['lecturer'], tw, 6.0)}")
                    if ml and my+len(ml)*11 < y1-2:
                        self.canvas.create_text(x0+8, my, text="\n".join(ml),
                                                fill=SUBTEXT, font=("Segoe UI", 7),
                                                anchor="nw", tags=tag)

                self.canvas.tag_bind(tag, "<Enter>",    lambda e, en=entry: self._tip_show(e, en))
                self.canvas.tag_bind(tag, "<Leave>",    lambda e: self._tip_hide())
                self.canvas.tag_bind(tag, "<Button-3>", lambda e, en=entry: self._ctx(e, en))

    # ── Tooltip ───────────────────────────────────────────────────────────────
    def _tip_show(self, event, entry):
        self._tip_hide()
        lines = [entry.get("_course_name", ""), f"[{entry.get('type','')}]"]
        lines.append(f"{entry.get('day','')}  {entry.get('from','')} – {entry.get('to','')}")
        lp = []
        for k in ("campus", "building"):
            if entry.get(k): lp.append(entry[k])
        rn = entry.get("room_no", "") or entry.get("room", "")
        if rn: lp.append(f"Room {rn}")
        if lp: lines.append("📍 " + "  ·  ".join(lp))
        if entry.get("lecturer"): lines.append(f"👤 {entry['lecturer']}")
        bm = entry.get("_base_module", "")
        if bm: lines.append(f"📚 {bm}")

        self._tip = tk.Toplevel(self.root)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{event.x_root+14}+{event.y_root+10}")
        tk.Label(self._tip, text="\n".join(lines), bg=MANTLE, fg=FG,
                 font=("Segoe UI", 9), relief=tk.FLAT, bd=0,
                 padx=12, pady=10, justify=tk.LEFT).pack()

    def _tip_hide(self):
        if self._tip:
            try: self._tip.destroy()
            except: pass
            self._tip = None

    # ── Context menu ──────────────────────────────────────────────────────────
    def _ctx(self, event, entry):
        m = tk.Menu(self.root, tearoff=0, bg=SURFACE0, fg=FG,
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

    # ── Visibility refresh ────────────────────────────────────────────────────
    def refresh_visibility(self):
        for w in self.vis_frame.winfo_children():
            w.destroy()
        self.vis_vars.clear()

        # Group by course name
        seen = {}
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
            tk.Label(row, bg=color, width=3, height=1, relief=tk.FLAT
                     ).pack(side=tk.LEFT, padx=(2, 6))
            col_f = tk.Frame(row, bg=BG)
            col_f.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Checkbutton(col_f, text=cn, variable=var,
                           bg=BG, fg=FG, selectcolor=SURFACE1,
                           activebackground=BG, font=("Segoe UI", 9),
                           cursor="hand2", anchor="w",
                           command=lambda i=cid, v=var: self._toggle(i, v)
                           ).pack(anchor="w")
            bm = entry.get("_base_module", "")
            if bm:
                tk.Label(col_f, text=bm, bg=BG, fg=OVERLAY,
                         font=("Segoe UI", 7)).pack(anchor="w")
        self._vis_resize()

    def _toggle(self, cid, var):
        if var.get(): self.hidden_ids.discard(cid)
        else:         self.hidden_ids.add(cid)
        self._save_hidden()
        self.draw_timetable()

    def show_all(self):
        self.hidden_ids.clear()
        for v in self.vis_vars.values(): v.set(True)
        self._save_hidden()
        self.draw_timetable()

    def hide_all(self):
        for cid, v in self.vis_vars.items():
            v.set(False); self.hidden_ids.add(cid)
        self._save_hidden()
        self.draw_timetable()

    # ── Scroll ────────────────────────────────────────────────────────────────
    def _on_vscroll(self, e):
        self.canvas.yview_scroll(int(-1*(e.delta/120)), "units")

    def _on_hscroll(self, e):
        self.canvas.xview_scroll(int(-1*(e.delta/120)), "units")

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
        return tk.Button(p, text=t, bg=bg, fg=fg, font=("Segoe UI", 9, "bold"),
                         relief=tk.FLAT, cursor="hand2", padx=10, pady=4,
                         activebackground=ACCENT, activeforeground=CRUST, command=cmd)


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    data_file = sys.argv[1] if len(sys.argv) > 1 else "data.json"
    sem_name  = sys.argv[2] if len(sys.argv) > 2 else ""
    root = tk.Tk()
    TimetableView(root, data_file, sem_name)
    root.mainloop()