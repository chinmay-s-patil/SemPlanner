import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import json
import os
from datetime import datetime

# ── Config ─────────────────────────────────────────────────────────────────────
CONFIG_FILE = "timetable.config"

COURSE_COLORS = [
    "#89B4FA", "#A6E3A1", "#FAB387", "#CBA6F7",
    "#F38BA8", "#94E2D5", "#F9E2AF", "#74C7EC",
    "#B4BEFE", "#EBA0AC",
]

# ── Catppuccin Mocha dark palette ──────────────────────────────────────────────
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
RED      = "#F38BA8"
ENTRY_BG = "#24273A"

DAYS     = ["Mon", "Tue", "Wed", "Thu", "Fri"]
DAY_FULL = {
    "Mon": "Monday",  "Tue": "Tuesday", "Wed": "Wednesday",
    "Thu": "Thursday","Fri": "Friday",  "Sat": "Saturday", "Sun": "Sunday",
}

# ── Helpers ────────────────────────────────────────────────────────────────────
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
    r,g,b = (int(hx[i:i+2],16) for i in (0,2,4))
    return "#{:02x}{:02x}{:02x}".format(int(r*factor),int(g*factor),int(b*factor))

def hex_blend(hx, bg=BG, alpha=0.20):
    """Blend hx onto bg at given alpha to simulate a tinted block."""
    hx = hx.lstrip("#"); bg = bg.lstrip("#")
    r1,g1,b1 = (int(hx[i:i+2],16) for i in (0,2,4))
    r2,g2,b2 = (int(bg[i:i+2],16) for i in (0,2,4))
    r = int(r1*alpha + r2*(1-alpha))
    g = int(g1*alpha + g2*(1-alpha))
    b = int(b1*alpha + b2*(1-alpha))
    return "#{:02x}{:02x}{:02x}".format(r,g,b)

def assign_columns(events):
    """
    events: list of (ft, tt, course_dict)
    Returns: list of (course_dict, col_idx, num_cols_in_group)

    Uses union-find so every event in the same overlap group receives the
    same num_cols — this prevents partial-width mismatches (e.g. one block
    using 1/2 of the column while a neighbour uses 1/3).
    """
    if not events:
        return []
    events = sorted(events, key=lambda x: x[0])
    n = len(events)
    col = [-1] * n

    # Greedy left-to-right column assignment
    for i in range(n):
        used = {col[j] for j in range(i) if events[j][1] > events[i][0]}
        c = 0
        while c in used:
            c += 1
        col[i] = c

    # --- Union-Find ---
    parent = list(range(n))

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(x, y):
        parent[find(x)] = find(y)

    for i in range(n):
        for j in range(i + 1, n):
            if events[i][0] < events[j][1] and events[j][0] < events[i][1]:
                union(i, j)

    # Max column index per connected component → num_cols for whole group
    group_max: dict = {}
    for i in range(n):
        g = find(i)
        group_max[g] = max(group_max.get(g, 0), col[i])

    result = []
    for i in range(n):
        g = find(i)
        result.append((events[i][2], col[i], group_max[g] + 1))
    return result


# ── App ────────────────────────────────────────────────────────────────────────
class TimetableApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Semester Timetable")
        self.root.geometry("1380x820")
        self.root.minsize(960, 640)
        self.root.configure(bg=BG)

        self.courses: list[dict] = []
        self.exams:   list[dict] = []
        self.hidden_ids: set     = set()   # set of course _id values
        self.vis_vars:   dict    = {}      # _id → BooleanVar
        self.config:     dict    = {}
        self._tip        = None
        self._next_id    = 0
        self._tab_btns:  list    = []

        self._styles()
        self._load_config()
        self._build_ui()

        if self.config.get("last_file") and os.path.exists(self.config["last_file"]):
            self.load_json_file(self.config["last_file"])
        else:
            self.draw_timetable()

    # ── ttk styles ─────────────────────────────────────────────────────────────
    def _styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TFrame",    background=SURFACE0)
        s.configure("TLabel",    background=SURFACE0, foreground=FG)
        s.configure("TCombobox", fieldbackground=ENTRY_BG, background=SURFACE1,
                    foreground=FG, selectbackground=ACCENT, arrowcolor=SUBTEXT,
                    borderwidth=0)
        s.map("TCombobox", fieldbackground=[("readonly", ENTRY_BG)])

    # ── Config ─────────────────────────────────────────────────────────────────
    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    self.config = json.load(f)
            except Exception:
                self.config = {}

    def _save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

    # ── ID helpers ─────────────────────────────────────────────────────────────
    def _new_id(self):
        self._next_id += 1
        return self._next_id

    def _ensure_ids(self):
        """Assign _id to any course that doesn't have one yet."""
        for c in self.courses:
            if "_id" not in c:
                c["_id"] = self._new_id()

    # ── UI skeleton ────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ─ Top bar ─
        topbar = tk.Frame(self.root, bg=CRUST, height=56)
        topbar.pack(fill=tk.X, side=tk.TOP)
        topbar.pack_propagate(False)

        tk.Label(topbar, text="  📅  Semester Timetable",
                 bg=CRUST, fg=FG, font=("Segoe UI",15,"bold")
                 ).pack(side=tk.LEFT, padx=6, pady=12)

        tk.Frame(topbar, bg=SURFACE1, width=1).pack(
            side=tk.LEFT, fill=tk.Y, pady=12, padx=10)

        self.semester_lbl = tk.Label(topbar, text="No file loaded",
                                     bg=CRUST, fg=SUBTEXT, font=("Segoe UI",10))
        self.semester_lbl.pack(side=tk.LEFT, pady=12)

        tk.Button(topbar, text="  📂  Import JSON  ",
                  bg=ACCENT, fg=CRUST, font=("Segoe UI",10,"bold"),
                  relief=tk.FLAT, activebackground="#74C7EC", cursor="hand2",
                  padx=4, pady=2, command=self.import_file
                  ).pack(side=tk.RIGHT, padx=14, pady=12)

        # ─ Body ─
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)

        # Canvas (no visible scrollbar)
        self.canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                         padx=(10,0), pady=10)
        self.canvas.bind("<Configure>",         lambda e: self.draw_timetable())
        self.canvas.bind("<MouseWheel>",         self._on_vscroll)
        self.canvas.bind("<Shift-MouseWheel>",   self._on_hscroll)
        self.canvas.bind("<Button-4>",  lambda e: self.canvas.yview_scroll(-1,"units"))
        self.canvas.bind("<Button-5>",  lambda e: self.canvas.yview_scroll( 1,"units"))

        # ─ Sidebar: content panel (left) + tab rail (right, sticks to wall) ─
        sb = tk.Frame(body, bg=MANTLE, width=296)
        sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0), pady=10)
        sb.pack_propagate(False)

        # Tab rail — rightmost strip, "stuck to the wall"
        self._tab_rail = tk.Frame(sb, bg=SURFACE0, width=34)
        self._tab_rail.pack(side=tk.RIGHT, fill=tk.Y)
        self._tab_rail.pack_propagate(False)

        # 1-px separator between content and rail
        tk.Frame(sb, bg=SURFACE1, width=1).pack(side=tk.RIGHT, fill=tk.Y)

        # Content area (expands left of the rail)
        self._tab_content_area = tk.Frame(sb, bg=BG)
        self._tab_content_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Tab content frames
        self.tab_options    = tk.Frame(self._tab_content_area, bg=BG)
        self.tab_visibility = tk.Frame(self._tab_content_area, bg=BG)
        self.tab_add        = tk.Frame(self._tab_content_area, bg=BG)
        self.tab_exams      = tk.Frame(self._tab_content_area, bg=BG)

        # Build tab buttons in the rail
        tab_defs = [
            (self.tab_options,    "Options"),
            (self.tab_visibility, "Courses"),
            (self.tab_add,        "Add"),
            (self.tab_exams,      "Exams"),
        ]
        for frame, label in tab_defs:
            self._make_tab_btn(frame, label)

        self._build_options_tab()
        self._build_visibility_tab()
        self._build_add_tab()
        self._build_exams_tab()

        # Show Options tab by default
        self._select_tab(self.tab_options, self._tab_btns[0])

    # ── Vertical tab rail helpers ───────────────────────────────────────────────
    def _make_tab_btn(self, frame, label):
        """Create a vertical tab button on the rail. Active tab = BG + accent stripe."""
        h = len(label) * 11 + 26
        c = tk.Canvas(self._tab_rail, bg=SURFACE0, width=34, height=h,
                      highlightthickness=0, cursor="hand2")
        c.pack(pady=(8, 0), fill=tk.X)

        txt_id    = c.create_text(17, h // 2, text=label, angle=90,
                                  fill=SUBTEXT, font=("Segoe UI", 8, "bold"),
                                  anchor="center")
        accent_id = c.create_rectangle(0, 0, 0, h, fill=ACCENT, outline="")

        c._frame     = frame
        c._txt_id    = txt_id
        c._accent_id = accent_id
        c._h         = h
        c._active    = False

        c.bind("<Button-1>", lambda e, f=frame, cv=c: self._select_tab(f, cv))
        c.bind("<Enter>",    lambda e, cv=c: cv.configure(bg=SURFACE1) if not cv._active else None)
        c.bind("<Leave>",    lambda e, cv=c: cv.configure(bg=SURFACE0) if not cv._active else None)

        self._tab_btns.append(c)
        return c

    def _select_tab(self, frame, btn_c):
        """Deactivate all tabs, then activate the chosen one."""
        for c in self._tab_btns:
            c._frame.pack_forget()
            c.configure(bg=SURFACE0)
            c.itemconfigure(c._txt_id, fill=SUBTEXT)
            c.coords(c._accent_id, 0, 0, 0, c._h)   # hide accent (zero width)
            c._active = False

        frame.pack(fill=tk.BOTH, expand=True)
        btn_c.configure(bg=BG)
        btn_c.itemconfigure(btn_c._txt_id, fill=FG)
        btn_c.coords(btn_c._accent_id, 0, 0, 3, btn_c._h)  # show 3-px accent stripe
        btn_c._active = True

    # ── Options tab ────────────────────────────────────────────────────────────
    def _build_options_tab(self):
        f = self.tab_options
        self._ph(f, "📆  Days")

        day_row = tk.Frame(f, bg=BG)
        day_row.pack(fill=tk.X, padx=14, pady=(0,6))
        self.show_sat = tk.BooleanVar(value=False)
        self.show_sun = tk.BooleanVar(value=False)
        self._chip(day_row, "Saturday", self.show_sat)
        self._chip(day_row, "Sunday",   self.show_sun)

        self._ph(f, "🕐  Time Range", top=14)
        tr = tk.Frame(f, bg=BG)
        tr.pack(fill=tk.X, padx=14, pady=(0,6))

        self._lbl(tr, "From").grid(row=0, column=0, sticky="w")
        self.start_h = tk.StringVar(value="8")
        cb1 = ttk.Combobox(tr, textvariable=self.start_h, width=5, state="readonly",
                           values=[str(h) for h in range(6,15)])
        cb1.grid(row=0, column=1, padx=6)
        cb1.bind("<<ComboboxSelected>>", lambda e: self.draw_timetable())

        self._lbl(tr, "To").grid(row=0, column=2, sticky="w", padx=(10,0))
        self.end_h = tk.StringVar(value="20")
        cb2 = ttk.Combobox(tr, textvariable=self.end_h, width=5, state="readonly",
                           values=[str(h) for h in range(14,24)])
        cb2.grid(row=0, column=3, padx=6)
        cb2.bind("<<ComboboxSelected>>", lambda e: self.draw_timetable())

        self._ph(f, "📁  File", top=14)
        self.file_lbl = tk.Label(f, text="—", bg=BG, fg=SUBTEXT,
                                 font=("Segoe UI",8), wraplength=220, justify="left")
        self.file_lbl.pack(anchor="w", padx=14)

        br = tk.Frame(f, bg=BG)
        br.pack(anchor="w", padx=14, pady=(10,0))
        self._btn(br, "📂  Import",  ACCENT,   CRUST, self.import_file).pack(side=tk.LEFT, padx=(0,6))
        self._btn(br, "💾  Export",  SURFACE1, FG,    self.export_data).pack(side=tk.LEFT)

    # ── Visibility tab ─────────────────────────────────────────────────────────
    def _build_visibility_tab(self):
        f = self.tab_visibility
        self._ph(f, "👁  Show / Hide")

        br = tk.Frame(f, bg=BG)
        br.pack(fill=tk.X, padx=14, pady=(0,8))
        self._btn(br, "Show All", SURFACE1, FG, self.show_all).pack(side=tk.LEFT, padx=(0,6))
        self._btn(br, "Hide All", SURFACE1, FG, self.hide_all).pack(side=tk.LEFT)

        wrap = tk.Frame(f, bg=BG)
        wrap.pack(fill=tk.BOTH, expand=True, padx=6)

        # Scrollbar — always visible so the panel is clearly scrollable
        vsb = tk.Scrollbar(wrap, orient=tk.VERTICAL,
                           bg=SURFACE1, troughcolor=SURFACE0,
                           activebackground=OVERLAY, relief=tk.FLAT,
                           highlightthickness=0)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.vis_canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0,
                                    yscrollcommand=vsb.set)
        self.vis_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.configure(command=self.vis_canvas.yview)

        self.vis_frame = tk.Frame(self.vis_canvas, bg=BG)
        self._vwin = self.vis_canvas.create_window((0,0), window=self.vis_frame, anchor="nw")

        self.vis_frame.bind("<Configure>",  self._vis_resize)
        self.vis_canvas.bind("<Configure>", self._vis_resize)
        # Windows / macOS wheel
        self.vis_canvas.bind("<MouseWheel>",
            lambda e: self.vis_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        # Linux scroll buttons
        self.vis_canvas.bind("<Button-4>",
            lambda e: self.vis_canvas.yview_scroll(-1, "units"))
        self.vis_canvas.bind("<Button-5>",
            lambda e: self.vis_canvas.yview_scroll( 1, "units"))

    def _vis_resize(self, _=None):
        self.vis_canvas.configure(scrollregion=self.vis_canvas.bbox("all"))
        self.vis_canvas.itemconfigure(self._vwin, width=self.vis_canvas.winfo_width())

    # ── Add tab ────────────────────────────────────────────────────────────────
    def _build_add_tab(self):
        f = self.tab_add
        self._ph(f, "＋  New Course")

        g = tk.Frame(f, bg=BG)
        g.pack(fill=tk.X, padx=14)
        g.columnconfigure(1, weight=1)

        self.nc_name      = tk.StringVar()
        self.nc_day       = tk.StringVar(value="Mon")
        self.nc_from      = tk.StringVar(value="08.00")
        self.nc_to        = tk.StringVar(value="10.00")
        self.nc_campus    = tk.StringVar()
        self.nc_building  = tk.StringVar()
        self.nc_room_no   = tk.StringVar()
        self.nc_lecturer  = tk.StringVar()
        self.nc_color     = tk.StringVar(value=COURSE_COLORS[0])

        fields = [
            ("Name *",    self.nc_name,     "entry"),
            ("Day *",     self.nc_day,      "day"),
            ("From *",    self.nc_from,     "entry"),
            ("To *",      self.nc_to,       "entry"),
            ("Campus",    self.nc_campus,   "entry"),
            ("Building",  self.nc_building, "entry"),
            ("Room No.",  self.nc_room_no,  "entry"),
            ("Lecturer",  self.nc_lecturer, "entry"),
        ]
        for i, (lbl, var, kind) in enumerate(fields):
            self._lbl(g, lbl).grid(row=i, column=0, sticky="w", pady=4)
            if kind == "entry":
                self._entry(g, var).grid(row=i, column=1, sticky="ew", pady=4, padx=(8,0))
            else:
                ttk.Combobox(g, textvariable=var, state="readonly", font=("Segoe UI",9),
                             values=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
                             ).grid(row=i, column=1, sticky="ew", pady=4, padx=(8,0))

        self._lbl(g, "Color").grid(row=len(fields), column=0, sticky="w", pady=4)
        cr = tk.Frame(g, bg=BG)
        cr.grid(row=len(fields), column=1, sticky="ew", pady=4, padx=(8,0))
        self.color_sw = tk.Label(cr, bg=COURSE_COLORS[0], width=3, relief=tk.FLAT, cursor="hand2")
        self.color_sw.pack(side=tk.LEFT)
        self.color_sw.bind("<Button-1>", lambda e: self.pick_color())
        tk.Button(cr, text="Pick…", bg=SURFACE1, fg=FG, font=("Segoe UI",8),
                  relief=tk.FLAT, cursor="hand2", command=self.pick_color
                  ).pack(side=tk.LEFT, padx=6)

        pal = tk.Frame(f, bg=BG)
        pal.pack(anchor="w", padx=14, pady=(4,0))
        for c in COURSE_COLORS:
            dot = tk.Label(pal, bg=c, width=2, height=1, cursor="hand2", relief=tk.FLAT)
            dot.pack(side=tk.LEFT, padx=1)
            dot.bind("<Button-1>", lambda e, col=c: self._set_color(col))

        self._btn(f, "＋  Add Course", ACCENT, CRUST, self.add_course
                  ).pack(anchor="w", padx=14, pady=12)

    # ── Exams tab ──────────────────────────────────────────────────────────────
    def _build_exams_tab(self):
        f = self.tab_exams
        self._ph(f, "📝  Add Exam")

        inner = tk.Frame(f, bg=BG)
        inner.pack(fill=tk.X, padx=14)
        inner.columnconfigure(1, weight=1)

        self.ex_subject = tk.StringVar()
        self.ex_date    = tk.StringVar(value="dd.mm.yyyy")
        self.ex_time    = tk.StringVar(value="hh.mm")
        self.ex_room    = tk.StringVar()
        self.ex_notes   = tk.StringVar()

        for i,(lbl,var) in enumerate([
            ("Subject *", self.ex_subject),
            ("Date *",    self.ex_date),
            ("Time",      self.ex_time),
            ("Room",      self.ex_room),
            ("Notes",     self.ex_notes),
        ]):
            self._lbl(inner, lbl).grid(row=i, column=0, sticky="w", pady=3)
            self._entry(inner, var, fs=8).grid(row=i, column=1, sticky="ew", pady=3, padx=(8,0))

        self._btn(f, "＋  Add Exam", ACCENT, CRUST, self.add_exam
                  ).pack(anchor="w", padx=14, pady=10)

        self._ph(f, "📋  Scheduled", top=4)

        wrap = tk.Frame(f, bg=BG)
        wrap.pack(fill=tk.BOTH, expand=True, padx=6)

        self.exam_canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        self.exam_canvas.pack(fill=tk.BOTH, expand=True)

        self.exam_frame = tk.Frame(self.exam_canvas, bg=BG)
        self._ewin = self.exam_canvas.create_window((0,0), window=self.exam_frame, anchor="nw")

        self.exam_frame.bind( "<Configure>",  self._exam_resize)
        self.exam_canvas.bind("<Configure>",  self._exam_resize)
        self.exam_canvas.bind("<MouseWheel>",
            lambda e: self.exam_canvas.yview_scroll(int(-1*(e.delta/120)),"units"))

    def _exam_resize(self, _=None):
        self.exam_canvas.configure(scrollregion=self.exam_canvas.bbox("all"))
        self.exam_canvas.itemconfigure(self._ewin, width=self.exam_canvas.winfo_width())

    # ── Draw timetable ─────────────────────────────────────────────────────────
    def draw_timetable(self):
        self.canvas.delete("all")

        days = list(DAYS)
        if self.show_sat.get(): days.append("Sat")
        if self.show_sun.get(): days.append("Sun")

        try:
            sh = int(self.start_h.get())
            eh = int(self.end_h.get())
        except Exception:
            sh, eh = 8, 20
        sh, eh = min(sh, eh-1), max(sh+1, eh)

        cw      = max(self.canvas.winfo_width(),  600)
        ch      = max(self.canvas.winfo_height(), 400)
        TW      = 54          # time column width
        HDR     = 46          # header height
        HH      = 80          # hour height (80px → 20px per 15 min)
        DAY_W   = max(110, (cw - TW - 18) // len(days))
        TOT_H   = HDR + (eh - sh) * HH + 10
        TOT_W   = TW + len(days) * DAY_W + 4

        self.canvas.configure(scrollregion=(0, 0, TOT_W, max(TOT_H, ch)))
        self.canvas.create_rectangle(0, 0, TOT_W, max(TOT_H, ch), fill=BG, outline="")

        # Alternating column shading
        for i in range(len(days)):
            x0 = TW + i * DAY_W
            x1 = x0 + DAY_W
            fill = SURFACE0 if i % 2 == 0 else BG
            self.canvas.create_rectangle(x0, HDR, x1, TOT_H, fill=fill, outline="")

        # Hour / 30-min / 15-min lines + labels
        for h in range(sh, eh + 1):
            y = HDR + (h - sh) * HH

            # Full-hour line
            self.canvas.create_line(TW, y, TOT_W, y, fill=SURFACE1, width=1)
            self.canvas.create_text(TW - 7, y + 2,
                                    text=f"{h:02d}:00",
                                    fill=OVERLAY, font=("Segoe UI", 8), anchor="e")

            if h < eh:
                # 15-min mark (very faint dotted)
                y15 = y + HH // 4
                self.canvas.create_line(TW, y15, TOT_W, y15,
                                        fill=SURFACE1, width=1, dash=(1, 10))
                # small tick + label on time column
                self.canvas.create_line(TW - 4, y15, TW, y15, fill=OVERLAY, width=1)

                # 30-min mark (dashed)
                y30 = y + HH // 2
                self.canvas.create_line(TW, y30, TOT_W, y30,
                                        fill=SURFACE1, width=1, dash=(3, 6))
                self.canvas.create_text(TW - 7, y30 + 2,
                                        text=f"{h:02d}:30",
                                        fill=OVERLAY, font=("Segoe UI", 7), anchor="e")

                # 45-min mark (very faint dotted)
                y45 = y + 3 * HH // 4
                self.canvas.create_line(TW, y45, TOT_W, y45,
                                        fill=SURFACE1, width=1, dash=(1, 10))
                self.canvas.create_line(TW - 4, y45, TW, y45, fill=OVERLAY, width=1)

        # Vertical separators
        for i in range(len(days) + 1):
            x = TW + i * DAY_W
            self.canvas.create_line(x, HDR, x, TOT_H, fill=SURFACE1, width=1)

        # Header bar
        self.canvas.create_rectangle(0, 0, TOT_W, HDR, fill=MANTLE, outline="")
        self.canvas.create_line(0, HDR, TOT_W, HDR, fill=SURFACE1, width=1)

        for i, day in enumerate(days):
            x0 = TW + i * DAY_W
            x1 = x0 + DAY_W
            self.canvas.create_text((x0+x1)//2, HDR//2,
                                    text=DAY_FULL.get(day, day).upper(),
                                    fill=FG, font=("Segoe UI",9,"bold"))

        # ── Course blocks with overlap ──
        for di, day in enumerate(days):
            visible = [
                c for c in self.courses
                if c.get("day") == day
                and c.get("_id") not in self.hidden_ids
            ]
            if not visible:
                continue

            events = []
            for c in visible:
                ft = parse_time(c.get("from"))
                tt = parse_time(c.get("to"))
                if ft is not None and tt is not None and ft < tt:
                    events.append((ft, tt, c))

            for (course, col_idx, num_cols) in assign_columns(events):
                ft = parse_time(course.get("from"))
                tt = parse_time(course.get("to"))
                ft = max(ft, sh);  tt = min(tt, eh)
                if ft >= tt: continue

                col_w = DAY_W / num_cols
                PAD   = 2
                x0 = TW + di * DAY_W + col_idx * col_w + PAD
                x1 = TW + di * DAY_W + (col_idx + 1) * col_w - PAD
                y0 = HDR + (ft - sh) * HH + PAD
                y1 = HDR + (tt - sh) * HH - PAD

                color = course.get("color", COURSE_COLORS[0])
                bg_c  = hex_blend(color, BG, 0.22)
                dark  = hex_darken(color, 0.65)
                tag   = f"c{id(course)}"

                # Background card
                self.canvas.create_rectangle(x0, y0, x1, y1,
                                             fill=bg_c, outline="", tags=tag)
                # Left accent stripe
                self.canvas.create_rectangle(x0, y0, x0+4, y1,
                                             fill=color, outline="", tags=tag)
                # Card border
                self.canvas.create_rectangle(x0, y0, x1, y1,
                                             fill="", outline=dark, width=1, tags=tag)

                bh    = y1 - y0
                name  = course.get("name", "?")
                tstr  = f"{course.get('from','')}–{course.get('to','')}"
                # Usable text width: 4px accent stripe + 4px gap on left, 6px on right
                tw    = max(10, int(col_w) - 18)

                # Build location string once
                _parts = []
                _campus   = course.get("campus",   "")
                _building = course.get("building", "")
                _room_no  = course.get("room_no",  "") or course.get("room", "")
                if _campus:   _parts.append(_campus)
                if _building: _parts.append(_building)
                if _room_no:  _parts.append(f"Rm {_room_no}")
                loc = "  ·  ".join(_parts)

                def _clip(text, max_px, cw=7.0):
                    """Single-line clip with ellipsis (estimates char width)."""
                    mc = max(3, int(max_px / cw))
                    return text if len(text) <= mc else text[:mc - 1] + "…"

                def _wrap_clip(text, max_px, max_lines, cw=6.5):
                    """Word-wrap into at most max_lines lines of max_px, with ellipsis."""
                    mc = max(4, int(max_px / cw))
                    words = text.split()
                    lines, cur = [], ""
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
                    # Ellipsis if anything was cut
                    if lines and " ".join(lines) != text:
                        last = lines[-1]
                        lines[-1] = (last[:-1] if len(last) >= mc else last) + "…"
                    return "\n".join(lines) if lines else _clip(text, max_px, cw)

                # ── Tier 1 — micro block (<20 px): nothing readable ──
                if bh < 20:
                    pass

                # ── Tier 2 — tiny block (20-34 px): 1-line name, no time ──
                elif bh < 34:
                    self.canvas.create_text(
                        x0 + 8, y0 + bh // 2,
                        text=_clip(name, tw, 6.5),
                        fill=color, font=("Segoe UI", 8, "bold"),
                        anchor="w", tags=tag)

                # ── Tier 3 — small block (34-56 px): time on its own row, name below ──
                elif bh < 56:
                    self.canvas.create_text(
                        x1 - 4, y0 + 4,
                        text=tstr, fill=OVERLAY,
                        font=("Segoe UI", 7), anchor="ne", tags=tag)
                    # Name starts below the time row (y + 14) so they never overlap
                    self.canvas.create_text(
                        x0 + 8, y0 + 15,
                        text=_clip(name, tw, 6.5),
                        fill=color, font=("Segoe UI", 9, "bold"),
                        anchor="nw", tags=tag)

                # ── Tier 4 — medium block (56-90 px): time row + name (1-2 lines) + loc ──
                elif bh < 90:
                    self.canvas.create_text(
                        x1 - 4, y0 + 4,
                        text=tstr, fill=OVERLAY,
                        font=("Segoe UI", 7), anchor="ne", tags=tag)
                    name_max_lines = max(1, min(2, (bh - 30) // 13))
                    name_text = _wrap_clip(name, tw, name_max_lines)
                    name_line_count = name_text.count("\n") + 1
                    self.canvas.create_text(
                        x0 + 8, y0 + 15,
                        text=name_text,
                        fill=color, font=("Segoe UI", 10, "bold"),
                        anchor="nw", tags=tag)
                    loc_y = y0 + 15 + name_line_count * 13 + 2
                    if loc and loc_y + 11 < y1 - 2:
                        self.canvas.create_text(
                            x0 + 8, loc_y,
                            text=_clip(f"📍  {loc}", tw, 6.0),
                            fill=SUBTEXT, font=("Segoe UI", 7),
                            anchor="nw", tags=tag)

                # ── Tier 5 — full block (≥90 px): name wrapped + meta below ──
                else:
                    self.canvas.create_text(
                        x1 - 4, y0 + 5,
                        text=tstr, fill=OVERLAY,
                        font=("Segoe UI", 7), anchor="ne", tags=tag)
                    # Calculate available height for name vs meta rows
                    has_loc = bool(loc)
                    has_lec = bool(bh > 110 and course.get("lecturer"))
                    meta_rows = has_loc + has_lec
                    avail_name_h = bh - 18 - meta_rows * 12 - 6
                    name_max_lines = max(1, avail_name_h // 14)
                    name_text = _wrap_clip(name, tw, name_max_lines, 6.5)
                    name_line_count = name_text.count("\n") + 1
                    self.canvas.create_text(
                        x0 + 8, y0 + 15,
                        text=name_text,
                        fill=color, font=("Segoe UI", 11, "bold"),
                        anchor="nw", tags=tag)
                    meta_y = y0 + 15 + name_line_count * 14 + 4
                    meta_lines = []
                    if has_loc:
                        meta_lines.append(f"📍  {_clip(loc, tw, 6.0)}")
                    if has_lec:
                        meta_lines.append(f"👤  {_clip(course['lecturer'], tw, 6.0)}")
                    if meta_lines and meta_y + len(meta_lines) * 11 < y1 - 2:
                        self.canvas.create_text(
                            x0 + 8, meta_y,
                            text="\n".join(meta_lines),
                            fill=SUBTEXT, font=("Segoe UI", 7),
                            anchor="nw", tags=tag)

                self.canvas.tag_bind(tag, "<Enter>",    lambda e, c=course: self._tip_show(e, c))
                self.canvas.tag_bind(tag, "<Leave>",    lambda e: self._tip_hide())
                self.canvas.tag_bind(tag, "<Button-3>", lambda e, c=course: self._ctx(e, c))

    # ── Tooltip ────────────────────────────────────────────────────────────────
    def _tip_show(self, event, course):
        self._tip_hide()
        lines = [course.get("name", "")]
        lines.append(f"{course.get('day','')}  {course.get('from','')} – {course.get('to','')}")

        # Location — new fields with fallback to legacy "room"
        campus   = course.get("campus",   "")
        building = course.get("building", "")
        room_no  = course.get("room_no",  "") or course.get("room", "")
        loc_parts = []
        if campus:   loc_parts.append(campus)
        if building: loc_parts.append(building)
        if room_no:  loc_parts.append(f"Room {room_no}")
        if loc_parts:
            lines.append("📍  " + "  ·  ".join(loc_parts))

        if course.get("lecturer"):
            lines.append(f"👤  {course['lecturer']}")

        self._tip = tk.Toplevel(self.root)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{event.x_root+14}+{event.y_root+10}")
        tk.Label(self._tip, text="\n".join(lines), bg=MANTLE, fg=FG,
                 font=("Segoe UI",9), relief=tk.FLAT, bd=0,
                 padx=12, pady=10, justify=tk.LEFT).pack()

    def _tip_hide(self):
        if self._tip:
            try: self._tip.destroy()
            except: pass
            self._tip = None

    # ── Context menu ───────────────────────────────────────────────────────────
    def _ctx(self, event, course):
        m = tk.Menu(self.root, tearoff=0, bg=SURFACE0, fg=FG,
                    activebackground=ACCENT, activeforeground=CRUST,
                    bd=0, relief=tk.FLAT)
        m.add_command(label="Hide course",
                      command=lambda: self._quick_hide(course))
        m.add_separator()
        m.add_command(label="Delete course",
                      command=lambda: self._delete_course(course))
        m.tk_popup(event.x_root, event.y_root)

    def _quick_hide(self, course):
        cid = course.get("_id")
        if cid is not None:
            self.hidden_ids.add(cid)
            if cid in self.vis_vars:
                self.vis_vars[cid].set(False)
        self.draw_timetable()

    def _delete_course(self, course):
        if messagebox.askyesno("Delete", f"Delete '{course.get('name','')}'?"):
            self.courses.remove(course)
            self.draw_timetable()
            self.refresh_visibility()

    # ── Import / Export ────────────────────────────────────────────────────────
    def import_file(self):
        path = filedialog.askopenfilename(
            title="Import Timetable JSON",
            filetypes=[("JSON Files","*.json"), ("All Files","*.*")])
        if path:
            self.load_json_file(path)

    def load_json_file(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as ex:
            messagebox.showerror("Import Error", str(ex))
            return

        self.courses = data.get("courses", [])
        self.exams   = data.get("exams",   [])

        # Auto-assign missing colors
        ci = 0
        for c in self.courses:
            if not c.get("color"):
                c["color"] = COURSE_COLORS[ci % len(COURSE_COLORS)]
                ci += 1

        # Always (re-)assign runtime IDs so each entry is independent
        self._next_id = 0
        for c in self.courses:
            c["_id"] = self._new_id()

        # Respect "hidden" flag from JSON (per-entry)
        self.hidden_ids = {
            c["_id"] for c in self.courses if c.get("hidden", False)
        }

        sem = data.get("semester", os.path.basename(path))
        self.semester_lbl.configure(text=sem)
        self.file_lbl.configure(text=os.path.basename(path))

        self.config["last_file"] = path
        self._save_config()

        self.draw_timetable()
        self.refresh_visibility()
        self.refresh_exams()

    def export_data(self):
        path = filedialog.asksaveasfilename(
            title="Export Timetable",
            defaultextension=".json",
            filetypes=[("JSON Files","*.json")])
        if not path: return

        # Sync hidden flag before saving
        for c in self.courses:
            c["hidden"] = (c.get("_id") in self.hidden_ids)

        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "semester": self.semester_lbl.cget("text"),
                "courses":  self.courses,
                "exams":    self.exams,
            }, f, indent=2, ensure_ascii=False)
        messagebox.showinfo("Exported", f"Saved → {os.path.basename(path)}")

    # ── Visibility ─────────────────────────────────────────────────────────────
    def refresh_visibility(self):
        for w in self.vis_frame.winfo_children():
            w.destroy()
        self.vis_vars.clear()

        # Show each course entry individually — duplicate names are independent
        for course in self.courses:
            cid   = course.get("_id")
            name  = course.get("name", "?")
            day   = course.get("day",  "")
            frm   = course.get("from", "")
            to_   = course.get("to",   "")
            color = course.get("color", "#888")

            # Build compact location for sub-label
            loc_parts = []
            if course.get("campus"):   loc_parts.append(course["campus"])
            if course.get("building"): loc_parts.append(course["building"])
            rn = course.get("room_no","") or course.get("room","")
            if rn: loc_parts.append(f"Rm {rn}")
            loc_str = "  ·  ".join(loc_parts) if loc_parts else ""

            var = tk.BooleanVar(value=(cid not in self.hidden_ids))
            self.vis_vars[cid] = var

            row = tk.Frame(self.vis_frame, bg=BG)
            row.pack(fill=tk.X, padx=6, pady=2)
            tk.Label(row, bg=color, width=3, height=1, relief=tk.FLAT
                     ).pack(side=tk.LEFT, padx=(2,6))

            # Show day+time so duplicate names are distinguishable
            label_text = f"{name}"
            sub_text   = f"{day}  {frm}–{to_}" + (f"   📍 {loc_str}" if loc_str else "")
            col_frame  = tk.Frame(row, bg=BG)
            col_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Checkbutton(col_frame, text=label_text, variable=var,
                           bg=BG, fg=FG, selectcolor=SURFACE1,
                           activebackground=BG, font=("Segoe UI", 9),
                           cursor="hand2", anchor="w",
                           command=lambda i=cid, v=var: self._toggle(i, v)
                           ).pack(anchor="w")
            tk.Label(col_frame, text=sub_text, bg=BG, fg=OVERLAY,
                     font=("Segoe UI", 7)).pack(anchor="w")

        self._vis_resize()

    def _toggle(self, cid, var):
        if var.get(): self.hidden_ids.discard(cid)
        else:         self.hidden_ids.add(cid)
        self.draw_timetable()

    def show_all(self):
        self.hidden_ids.clear()
        for v in self.vis_vars.values(): v.set(True)
        self.draw_timetable()

    def hide_all(self):
        for cid, v in self.vis_vars.items():
            v.set(False)
            self.hidden_ids.add(cid)
        self.draw_timetable()

    # ── Add course ─────────────────────────────────────────────────────────────
    def pick_color(self):
        res = colorchooser.askcolor(color=self.nc_color.get(), title="Pick Color")
        if res[1]: self._set_color(res[1])

    def _set_color(self, color):
        self.nc_color.set(color)
        self.color_sw.configure(bg=color)

    def add_course(self):
        name  = self.nc_name.get().strip()
        from_ = self.nc_from.get().strip()
        to_   = self.nc_to.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Course name is required.")
            return
        if parse_time(from_) is None or parse_time(to_) is None:
            messagebox.showwarning("Bad Time", "Use hh.mm (e.g. 08.00, 14.30)")
            return

        self.courses.append({
            "_id":       self._new_id(),
            "name":      name,
            "day":       self.nc_day.get(),
            "from":      from_,
            "to":        to_,
            "campus":    self.nc_campus.get().strip(),
            "building":  self.nc_building.get().strip(),
            "room_no":   self.nc_room_no.get().strip(),
            "lecturer":  self.nc_lecturer.get().strip(),
            "color":     self.nc_color.get(),
            "hidden":    False,
        })
        self.nc_name.set(""); self.nc_campus.set(""); self.nc_building.set("")
        self.nc_room_no.set(""); self.nc_lecturer.set("")
        self.draw_timetable()
        self.refresh_visibility()

    # ── Exams ──────────────────────────────────────────────────────────────────
    def add_exam(self):
        subj = self.ex_subject.get().strip()
        date = self.ex_date.get().strip()
        if not subj or date == "dd.mm.yyyy":
            messagebox.showwarning("Missing", "Subject and date are required.")
            return
        self.exams.append({
            "subject": subj, "date": date,
            "time":    self.ex_time.get().strip(),
            "room":    self.ex_room.get().strip(),
            "notes":   self.ex_notes.get().strip(),
        })
        self.ex_subject.set(""); self.ex_date.set("dd.mm.yyyy")
        self.ex_time.set("hh.mm"); self.ex_room.set(""); self.ex_notes.set("")
        self.refresh_exams()

    def refresh_exams(self):
        for w in self.exam_frame.winfo_children():
            w.destroy()

        if not self.exams:
            tk.Label(self.exam_frame, text="No exams scheduled.",
                     bg=BG, fg=OVERLAY, font=("Segoe UI",9)).pack(pady=16)
            self._exam_resize(); return

        def skey(e):
            try:    return datetime.strptime(e.get("date","01.01.2099"), "%d.%m.%Y")
            except: return datetime.max

        for i, ex in enumerate(sorted(self.exams, key=skey)):
            card = tk.Frame(self.exam_frame, bg=SURFACE0, padx=12, pady=8)
            card.pack(fill=tk.X, padx=4, pady=3)

            top = tk.Frame(card, bg=SURFACE0)
            top.pack(fill=tk.X)
            tk.Label(top, text=ex.get("subject","?"), bg=SURFACE0, fg=ACCENT,
                     font=("Segoe UI",10,"bold")).pack(side=tk.LEFT)
            tk.Button(top, text="✕", bg=SURFACE0, fg=RED, font=("Segoe UI",9),
                      relief=tk.FLAT, cursor="hand2",
                      command=lambda idx=i: self._del_exam(idx)
                      ).pack(side=tk.RIGHT)

            meta = [f"📅  {ex.get('date','')}"]
            if ex.get("time") not in ("hh.mm","",""):
                meta.append(f"🕐  {ex['time']}")
            if ex.get("room"): meta.append(f"🏠  {ex['room']}")
            tk.Label(card, text="   ".join(meta), bg=SURFACE0, fg=FG,
                     font=("Segoe UI",8)).pack(anchor="w", pady=(2,0))
            if ex.get("notes"):
                tk.Label(card, text=ex["notes"], bg=SURFACE0, fg=SUBTEXT,
                         font=("Segoe UI",8), wraplength=210, justify="left"
                         ).pack(anchor="w")

        self._exam_resize()

    def _del_exam(self, idx):
        if 0 <= idx < len(self.exams):
            self.exams.pop(idx)
            self.refresh_exams()

    # ── Scroll ─────────────────────────────────────────────────────────────────
    def _on_vscroll(self, e):
        self.canvas.yview_scroll(int(-1*(e.delta/120)), "units")

    def _on_hscroll(self, e):
        self.canvas.xview_scroll(int(-1*(e.delta/120)), "units")

    # ── Widget helpers ─────────────────────────────────────────────────────────
    def _ph(self, parent, text, top=14):
        """Pill header — section label + full-width separator line."""
        f = tk.Frame(parent, bg=BG)
        f.pack(fill=tk.X, padx=10, pady=(top, 6))
        tk.Label(f, text=text, bg=BG, fg=SUBTEXT,
                 font=("Segoe UI",8,"bold")).pack(side=tk.LEFT)
        tk.Frame(f, bg=SURFACE1, height=1).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(8,0), pady=6)

    def _lbl(self, parent, text):
        return tk.Label(parent, text=text, bg=BG, fg=SUBTEXT, font=("Segoe UI",9))

    def _entry(self, parent, var, fs=9):
        return tk.Entry(parent, textvariable=var, bg=ENTRY_BG, fg=FG,
                        insertbackground=FG, relief=tk.FLAT,
                        font=("Segoe UI",fs),
                        highlightthickness=1,
                        highlightcolor=ACCENT,
                        highlightbackground=SURFACE1)

    def _btn(self, parent, text, bg, fg, cmd):
        return tk.Button(parent, text=text, bg=bg, fg=fg,
                         font=("Segoe UI",9,"bold"), relief=tk.FLAT,
                         cursor="hand2", padx=10, pady=4,
                         activebackground=ACCENT, activeforeground=CRUST,
                         command=cmd)

    def _chip(self, parent, text, var):
        tk.Checkbutton(parent, text=text, variable=var,
                       command=self.draw_timetable,
                       bg=BG, fg=FG, selectcolor=SURFACE1,
                       activebackground=BG, font=("Segoe UI",9),
                       cursor="hand2"
                       ).pack(side=tk.LEFT, padx=(0,8))


# ── Entry ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    TimetableApp(root)
    root.mainloop()