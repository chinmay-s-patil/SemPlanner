"""
collegeView.py  —  Academic Hub  (Unified Single-Window)
All three views live in one window.
Navigation: hamburger (☰) opens an overlay drawer that slides in on top
without resizing or moving any existing UI.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import json, os, sys

# ── Catppuccin Mocha ──────────────────────────────────────────────────────────
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

# ── Shared constants ──────────────────────────────────────────────────────────
COURSE_COLORS = ["#89B4FA","#A6E3A1","#FAB387","#CBA6F7","#F38BA8",
                 "#94E2D5","#F9E2AF","#74C7EC","#B4BEFE","#EBA0AC"]
BASE_MODULES  = ["Master Modules","Lab Courses","Supplementary Courses",
                 "Key Competencies","Research Practice","Master's Thesis",""]
SPECIFIC_MODULES = {
    "Master Modules":     ["Integrated Systems","Propulsion Systems","Fluid/Aerodynamics",
                           "Structure","Dynamics/Control","Domain Specific Modules",
                           "Flexibilization in Engineering"],
    "Lab Courses":        ["Lab Courses"],
    "Supplementary Courses": ["Supplementary Courses"],
    "Key Competencies":   ["Offers Contextual Studies","Angebote Sprachenzentrum",
                           "Carl-von-Linde-Akademie","General Offers"],
    "Research Practice":  ["Teamproject","Term Project","Research Practice"],
    "Master's Thesis":    ["Master's Thesis"],
    "":                   [""],
}
DAYS     = ["Mon","Tue","Wed","Thu","Fri"]
DAY_FULL = {"Mon":"Monday","Tue":"Tuesday","Wed":"Wednesday",
            "Thu":"Thursday","Fri":"Friday","Sat":"Saturday","Sun":"Sunday"}
SLOT_TYPES = ["Lecture","Tutorial","Exercise","Lab","Help Session","Other"]

DATA_FILE = "data.json"


# ── I/O helpers ───────────────────────────────────────────────────────────────
def load_data(path=None):
    p = path or DATA_FILE
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"requirements": {}, "semesters": [], "completed_courses": []}

def save_data(data, path=None):
    p = path or DATA_FILE
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Timetable math helpers ────────────────────────────────────────────────────
def parse_time(t):
    try:
        parts = str(t).replace(":", ".").split(".")
        return int(parts[0]) + (int(parts[1]) if len(parts) > 1 else 0) / 60
    except Exception:
        return None

def hex_darken(hx, f=0.6):
    hx = hx.lstrip("#")
    r, g, b = (int(hx[i:i+2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(int(r*f), int(g*f), int(b*f))

def hex_blend(hx, bg_col=BG, a=0.22):
    hx = hx.lstrip("#"); bg_col = bg_col.lstrip("#")
    r1,g1,b1 = (int(hx[i:i+2],16) for i in (0,2,4))
    r2,g2,b2 = (int(bg_col[i:i+2],16) for i in (0,2,4))
    return "#{:02x}{:02x}{:02x}".format(
        int(r1*a+r2*(1-a)), int(g1*a+g2*(1-a)), int(b1*a+b2*(1-a)))

def assign_columns(events):
    if not events: return []
    events = sorted(events, key=lambda x: x[0])
    n = len(events); col = [-1]*n
    for i in range(n):
        used = {col[j] for j in range(i) if events[j][1] > events[i][0]}
        c = 0
        while c in used: c += 1
        col[i] = c
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(x, y): parent[find(x)] = find(y)
    for i in range(n):
        for j in range(i+1, n):
            if events[i][0] < events[j][1] and events[j][0] < events[i][1]:
                union(i, j)
    gm = {}
    for i in range(n):
        g = find(i); gm[g] = max(gm.get(g, 0), col[i])
    return [(events[i][2], col[i], gm[find(i)]+1) for i in range(n)]


# ─────────────────────────────────────────────────────────────────────────────
#  TIMETABLE PANEL
# ─────────────────────────────────────────────────────────────────────────────
class TimetablePanel:
    def __init__(self, container: tk.Frame, hub):
        self.hub       = hub
        self.frame     = tk.Frame(container, bg=BG)
        self.data_file = hub.data_file
        self.data: dict      = {}
        self.courses: list   = []
        self.hidden_ids: set = set()
        self.vis_vars: dict  = {}
        self._tip        = None
        self._next_id    = 0
        self._tab_btns: list = []
        self._init_styles()
        self._build_ui()

    def _init_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TCombobox", fieldbackground="#24273A", background=SURFACE1,
                    foreground=FG, selectbackground=ACCENT, arrowcolor=SUBTEXT, borderwidth=0)
        s.map("TCombobox", fieldbackground=[("readonly","#24273A")])

    # ── Reload from file / hub ────────────────────────────────────────────────
    def reload(self):
        try:
            with open(self.data_file, encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex)); return
        sems = [s["name"] for s in self.data.get("semesters", [])]
        self.sem_cb["values"] = sems
        cur = self.sem_var.get()
        if cur not in sems:
            self.sem_var.set(sems[-1] if sems else "")
        self._switch_semester()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        topbar = tk.Frame(self.frame, bg=CRUST, height=52)
        topbar.pack(fill=tk.X); topbar.pack_propagate(False)
        tk.Label(topbar, text="  📅  Timetable", bg=CRUST, fg=FG,
                 font=("Segoe UI",14,"bold")).pack(side=tk.LEFT, padx=6, pady=12)
        tk.Frame(topbar, bg=SURFACE1, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=12, padx=10)
        self.sem_var = tk.StringVar()
        self.sem_cb  = ttk.Combobox(topbar, textvariable=self.sem_var,
                                    state="readonly", width=22, font=("Segoe UI",10))
        self.sem_cb.pack(side=tk.LEFT, pady=14, padx=4)
        self.sem_cb.bind("<<ComboboxSelected>>", self._switch_semester)

        body = tk.Frame(self.frame, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10,0), pady=10)
        self.canvas.bind("<Configure>",       lambda e: self.draw_timetable())
        self.canvas.bind("<MouseWheel>",       self._on_vscroll)
        self.canvas.bind("<Shift-MouseWheel>", self._on_hscroll)
        self.canvas.bind("<Button-4>",  lambda e: self.canvas.yview_scroll(-1,"units"))
        self.canvas.bind("<Button-5>",  lambda e: self.canvas.yview_scroll(1,"units"))

        sb = tk.Frame(body, bg=MANTLE, width=296)
        sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(6,0), pady=10); sb.pack_propagate(False)
        self._tab_rail = tk.Frame(sb, bg=SURFACE0, width=34)
        self._tab_rail.pack(side=tk.RIGHT, fill=tk.Y); self._tab_rail.pack_propagate(False)
        tk.Frame(sb, bg=SURFACE1, width=1).pack(side=tk.RIGHT, fill=tk.Y)
        self._tca = tk.Frame(sb, bg=BG)
        self._tca.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tab_options    = tk.Frame(self._tca, bg=BG)
        self.tab_visibility = tk.Frame(self._tca, bg=BG)
        for frame, label in [(self.tab_options,"Options"),(self.tab_visibility,"Courses")]:
            self._make_tab_btn(frame, label)
        self._build_options_tab()
        self._build_visibility_tab()
        self._select_tab(self.tab_options, self._tab_btns[0])

    # ── Data ──────────────────────────────────────────────────────────────────
    def _switch_semester(self, *_):
        name = self.sem_var.get()
        sem  = next((s for s in self.data.get("semesters",[]) if s["name"]==name), None)
        if not sem: return
        self._next_id = 0; flat = []
        for course in sem.get("courses",[]):
            color = course.get("color", COURSE_COLORS[0])
            for slot in course.get("slots",[]):
                entry = dict(slot)
                entry["_course_name"] = course["name"]
                entry["_base_module"] = course.get("base_module","")
                entry["_color"]  = color
                entry["_id"]     = self._new_id()
                entry["_hidden"] = course.get("hidden", False)
                flat.append(entry)
        self.courses = flat
        self.hidden_ids = {e["_id"] for e in flat if e.get("_hidden")}
        self.draw_timetable(); self.refresh_visibility()

    def _new_id(self): self._next_id += 1; return self._next_id

    def _save_hidden(self):
        name = self.sem_var.get()
        sem  = next((s for s in self.data.get("semesters",[]) if s["name"]==name), None)
        if not sem: return
        hidden_names = {e["_course_name"] for e in self.courses if e["_id"] in self.hidden_ids}
        for course in sem["courses"]:
            course["hidden"] = course["name"] in hidden_names
        with open(self.data_file,"w",encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    # ── Tab rail ──────────────────────────────────────────────────────────────
    def _make_tab_btn(self, frame, label):
        h = len(label)*11+26
        c = tk.Canvas(self._tab_rail, bg=SURFACE0, width=34, height=h,
                      highlightthickness=0, cursor="hand2"); c.pack(pady=(8,0), fill=tk.X)
        tid = c.create_text(17, h//2, text=label, angle=90,
                            fill=SUBTEXT, font=("Segoe UI",8,"bold"), anchor="center")
        aid = c.create_rectangle(0,0,0,h, fill=ACCENT, outline="")
        c._frame=frame; c._txt_id=tid; c._accent_id=aid; c._h=h; c._active=False
        c.bind("<Button-1>", lambda e,f=frame,cv=c: self._select_tab(f,cv))
        c.bind("<Enter>",    lambda e,cv=c: cv.configure(bg=SURFACE1) if not cv._active else None)
        c.bind("<Leave>",    lambda e,cv=c: cv.configure(bg=SURFACE0) if not cv._active else None)
        self._tab_btns.append(c)

    def _select_tab(self, frame, btn_c):
        for c in self._tab_btns:
            c._frame.pack_forget(); c.configure(bg=SURFACE0)
            c.itemconfigure(c._txt_id, fill=SUBTEXT); c.coords(c._accent_id,0,0,0,c._h); c._active=False
        frame.pack(fill=tk.BOTH, expand=True); btn_c.configure(bg=BG)
        btn_c.itemconfigure(btn_c._txt_id, fill=FG); btn_c.coords(btn_c._accent_id,0,0,3,btn_c._h); btn_c._active=True

    # ── Options tab ───────────────────────────────────────────────────────────
    def _build_options_tab(self):
        f = self.tab_options
        self._ph(f,"📆  Days")
        dr = tk.Frame(f,bg=BG); dr.pack(fill=tk.X,padx=14,pady=(0,6))
        self.show_sat=tk.BooleanVar(value=False); self.show_sun=tk.BooleanVar(value=False)
        for text,var in [("Saturday",self.show_sat),("Sunday",self.show_sun)]:
            tk.Checkbutton(dr,text=text,variable=var,command=self.draw_timetable,
                           bg=BG,fg=FG,selectcolor=SURFACE1,activebackground=BG,
                           font=("Segoe UI",9),cursor="hand2").pack(side=tk.LEFT,padx=(0,8))
        self._ph(f,"🕐  Time Range",top=14)
        tr = tk.Frame(f,bg=BG); tr.pack(fill=tk.X,padx=14,pady=(0,6))
        self.start_h=tk.StringVar(value="8"); self.end_h=tk.StringVar(value="20")
        for lt,var,vals,col in [("From",self.start_h,[str(h) for h in range(6,15)],0),
                                 ("To",  self.end_h,  [str(h) for h in range(14,24)],2)]:
            self._lbl(tr,lt).grid(row=0,column=col,sticky="w")
            cb=ttk.Combobox(tr,textvariable=var,width=5,state="readonly",values=vals)
            cb.grid(row=0,column=col+1,padx=6)
            cb.bind("<<ComboboxSelected>>",lambda e:self.draw_timetable())
        self._ph(f,"🏷  Filter by Type",top=14)
        ty=tk.Frame(f,bg=BG); ty.pack(fill=tk.X,padx=14)
        self.type_vars={}
        for t in SLOT_TYPES:
            v=tk.BooleanVar(value=True); self.type_vars[t]=v
            tk.Checkbutton(ty,text=t,variable=v,command=self.draw_timetable,
                           bg=BG,fg=FG,selectcolor=SURFACE1,activebackground=BG,
                           font=("Segoe UI",8),cursor="hand2").pack(anchor="w")

    # ── Visibility tab ────────────────────────────────────────────────────────
    def _build_visibility_tab(self):
        f = self.tab_visibility
        self._ph(f,"👁  Show / Hide")
        br=tk.Frame(f,bg=BG); br.pack(fill=tk.X,padx=14,pady=(0,8))
        self._btn(br,"Show All",SURFACE1,FG,self.show_all).pack(side=tk.LEFT,padx=(0,6))
        self._btn(br,"Hide All",SURFACE1,FG,self.hide_all).pack(side=tk.LEFT)
        wrap=tk.Frame(f,bg=BG); wrap.pack(fill=tk.BOTH,expand=True,padx=6)
        vsb=tk.Scrollbar(wrap,orient=tk.VERTICAL,bg=SURFACE1,troughcolor=SURFACE0,
                         relief=tk.FLAT,highlightthickness=0); vsb.pack(side=tk.RIGHT,fill=tk.Y)
        self.vis_canvas=tk.Canvas(wrap,bg=BG,highlightthickness=0,yscrollcommand=vsb.set)
        self.vis_canvas.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        vsb.configure(command=self.vis_canvas.yview)
        self.vis_frame=tk.Frame(self.vis_canvas,bg=BG)
        self._vwin=self.vis_canvas.create_window((0,0),window=self.vis_frame,anchor="nw")
        self.vis_frame.bind("<Configure>",self._vis_resize)
        self.vis_canvas.bind("<Configure>",self._vis_resize)
        for seq in ("<MouseWheel>","<Button-4>","<Button-5>"):
            self.vis_canvas.bind(seq,lambda e,s=seq:
                self.vis_canvas.yview_scroll(int(-1*(e.delta/120)),"units")
                if not e.num else self.vis_canvas.yview_scroll(-1 if e.num==4 else 1,"units"))

    def _vis_resize(self,_=None):
        self.vis_canvas.configure(scrollregion=self.vis_canvas.bbox("all"))
        self.vis_canvas.itemconfigure(self._vwin,width=self.vis_canvas.winfo_width())

    # ── Draw ──────────────────────────────────────────────────────────────────
    def draw_timetable(self):
        self.canvas.delete("all")
        days=list(DAYS)
        if self.show_sat.get(): days.append("Sat")
        if self.show_sun.get(): days.append("Sun")
        try: sh=int(self.start_h.get()); eh=int(self.end_h.get())
        except: sh,eh=8,20
        sh,eh=min(sh,eh-1),max(sh+1,eh)
        cw=max(self.canvas.winfo_width(),600)
        TW=54; HDR=46; HH=80
        DAY_W=max(110,(cw-TW-18)//len(days))
        TOT_H=HDR+(eh-sh)*HH+10; TOT_W=TW+len(days)*DAY_W+4
        ch=max(self.canvas.winfo_height(),400)
        self.canvas.configure(scrollregion=(0,0,TOT_W,max(TOT_H,ch)))
        self.canvas.create_rectangle(0,0,TOT_W,max(TOT_H,ch),fill=BG,outline="")
        for i in range(len(days)):
            x0=TW+i*DAY_W; x1=x0+DAY_W
            self.canvas.create_rectangle(x0,HDR,x1,TOT_H,
                                         fill=SURFACE0 if i%2==0 else BG,outline="")
        for h in range(sh,eh+1):
            y=HDR+(h-sh)*HH
            self.canvas.create_line(TW,y,TOT_W,y,fill=SURFACE1,width=1)
            self.canvas.create_text(TW-7,y+2,text=f"{h:02d}:00",
                                    fill=OVERLAY,font=("Segoe UI",8),anchor="e")
            if h<eh:
                for frac,dash,lo in [(0.25,(1,10),None),(0.5,(3,6),2),(0.75,(1,10),None)]:
                    yy=y+int(HH*frac)
                    self.canvas.create_line(TW,yy,TOT_W,yy,fill=SURFACE1,width=1,dash=dash)
                    if lo:
                        self.canvas.create_text(TW-7,yy+lo,text=f"{h:02d}:30",
                                                fill=OVERLAY,font=("Segoe UI",7),anchor="e")
                    else:
                        self.canvas.create_line(TW-4,yy,TW,yy,fill=OVERLAY,width=1)
        for i in range(len(days)+1):
            x=TW+i*DAY_W; self.canvas.create_line(x,HDR,x,TOT_H,fill=SURFACE1,width=1)
        self.canvas.create_rectangle(0,0,TOT_W,HDR,fill=MANTLE,outline="")
        self.canvas.create_line(0,HDR,TOT_W,HDR,fill=SURFACE1,width=1)
        for i,day in enumerate(days):
            x0=TW+i*DAY_W; x1=x0+DAY_W
            self.canvas.create_text((x0+x1)//2,HDR//2,
                                    text=DAY_FULL.get(day,day).upper(),
                                    fill=FG,font=("Segoe UI",9,"bold"))
        active_types={t for t,v in self.type_vars.items() if v.get()} if self.type_vars else set(SLOT_TYPES)
        for di,day in enumerate(days):
            visible=[e for e in self.courses
                     if e.get("day")==day and e.get("_id") not in self.hidden_ids
                     and e.get("type","Lecture") in active_types]
            if not visible: continue
            events=[(parse_time(e.get("from")),parse_time(e.get("to")),e) for e in visible]
            events=[(ft,tt,e) for ft,tt,e in events if ft is not None and tt is not None and ft<tt]
            for (entry,col_idx,num_cols) in assign_columns(events):
                ft=parse_time(entry.get("from")); tt=parse_time(entry.get("to"))
                ft=max(ft,sh); tt=min(tt,eh)
                if ft>=tt: continue
                col_w=DAY_W/num_cols; PAD=2
                x0=TW+di*DAY_W+col_idx*col_w+PAD; x1=TW+di*DAY_W+(col_idx+1)*col_w-PAD
                y0=HDR+(ft-sh)*HH+PAD; y1=HDR+(tt-sh)*HH-PAD
                color=entry.get("_color",COURSE_COLORS[0])
                bg_c=hex_blend(color,BG,0.22); dark=hex_darken(color,0.65)
                tag=f"e{id(entry)}"
                self.canvas.create_rectangle(x0,y0,x1,y1,fill=bg_c,outline="",tags=tag)
                self.canvas.create_rectangle(x0,y0,x0+4,y1,fill=color,outline="",tags=tag)
                self.canvas.create_rectangle(x0,y0,x1,y1,fill="",outline=dark,width=1,tags=tag)
                bh=y1-y0; name=entry.get("_course_name","?")
                slot_type=entry.get("type",""); tstr=f"{entry.get('from','')}–{entry.get('to','')}  {slot_type}"
                tw=max(10,int(col_w)-18)
                _parts=[]
                for k in ("campus","building"):
                    if entry.get(k): _parts.append(entry[k])
                rn=entry.get("room_no","") or entry.get("room","")
                if rn: _parts.append(f"Rm {rn}")
                loc="  ·  ".join(_parts)
                def _clip(text,max_px,cw=7.0): mc=max(3,int(max_px/cw)); return text if len(text)<=mc else text[:mc-1]+"…"
                def _wrap_clip(text,max_px,max_lines,cw=6.5):
                    mc=max(4,int(max_px/cw)); words=text.split(); lines=[]; cur=""
                    for word in words:
                        test=(cur+" "+word).strip()
                        if len(test)<=mc: cur=test
                        else:
                            if cur: lines.append(cur)
                            if len(lines)>=max_lines: break
                            cur=word[:mc]
                    if cur and len(lines)<max_lines: lines.append(cur)
                    if lines and " ".join(lines)!=text:
                        last=lines[-1]; lines[-1]=(last[:-1] if len(last)>=mc else last)+"…"
                    return "\n".join(lines) if lines else _clip(text,max_px,cw)
                if bh<20: pass
                elif bh<34:
                    self.canvas.create_text(x0+8,y0+bh//2,text=_clip(name,tw,6.5),fill=color,font=("Segoe UI",8,"bold"),anchor="w",tags=tag)
                elif bh<56:
                    self.canvas.create_text(x1-4,y0+4,text=tstr,fill=OVERLAY,font=("Segoe UI",7),anchor="ne",tags=tag)
                    self.canvas.create_text(x0+8,y0+15,text=_clip(name,tw,6.5),fill=color,font=("Segoe UI",9,"bold"),anchor="nw",tags=tag)
                elif bh<90:
                    self.canvas.create_text(x1-4,y0+4,text=tstr,fill=OVERLAY,font=("Segoe UI",7),anchor="ne",tags=tag)
                    nl=max(1,min(2,(bh-30)//13)); nt=_wrap_clip(name,tw,nl); nc=nt.count("\n")+1
                    self.canvas.create_text(x0+8,y0+15,text=nt,fill=color,font=("Segoe UI",10,"bold"),anchor="nw",tags=tag)
                    ly=y0+15+nc*13+2
                    if loc and ly+11<y1-2:
                        self.canvas.create_text(x0+8,ly,text=_clip(f"📍 {loc}",tw,6.0),fill=SUBTEXT,font=("Segoe UI",7),anchor="nw",tags=tag)
                else:
                    self.canvas.create_text(x1-4,y0+5,text=tstr,fill=OVERLAY,font=("Segoe UI",7),anchor="ne",tags=tag)
                    has_loc=bool(loc); has_lec=bool(bh>110 and entry.get("lecturer")); mr=has_loc+has_lec
                    anl=bh-18-mr*12-6; nml=max(1,anl//14); nt=_wrap_clip(name,tw,nml,6.5); nc=nt.count("\n")+1
                    self.canvas.create_text(x0+8,y0+15,text=nt,fill=color,font=("Segoe UI",11,"bold"),anchor="nw",tags=tag)
                    my=y0+15+nc*14+4; ml=[]
                    if has_loc: ml.append(f"📍 {_clip(loc,tw,6.0)}")
                    if has_lec: ml.append(f"👤 {_clip(entry['lecturer'],tw,6.0)}")
                    if ml and my+len(ml)*11<y1-2:
                        self.canvas.create_text(x0+8,my,text="\n".join(ml),fill=SUBTEXT,font=("Segoe UI",7),anchor="nw",tags=tag)
                self.canvas.tag_bind(tag,"<Enter>",    lambda e,en=entry: self._tip_show(e,en))
                self.canvas.tag_bind(tag,"<Leave>",    lambda e: self._tip_hide())
                self.canvas.tag_bind(tag,"<Button-3>", lambda e,en=entry: self._ctx(e,en))

    # ── Tooltip ───────────────────────────────────────────────────────────────
    def _tip_show(self,event,entry):
        self._tip_hide()
        lines=[entry.get("_course_name",""),f"[{entry.get('type','')}]"]
        lines.append(f"{entry.get('day','')}  {entry.get('from','')} – {entry.get('to','')}")
        lp=[]
        for k in ("campus","building"):
            if entry.get(k): lp.append(entry[k])
        rn=entry.get("room_no","") or entry.get("room","")
        if rn: lp.append(f"Room {rn}")
        if lp: lines.append("📍 "+"  ·  ".join(lp))
        if entry.get("lecturer"): lines.append(f"👤 {entry['lecturer']}")
        bm=entry.get("_base_module","")
        if bm: lines.append(f"📚 {bm}")
        self._tip=tk.Toplevel(self.frame)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{event.x_root+14}+{event.y_root+10}")
        tk.Label(self._tip,text="\n".join(lines),bg=MANTLE,fg=FG,font=("Segoe UI",9),
                 relief=tk.FLAT,bd=0,padx=12,pady=10,justify=tk.LEFT).pack()

    def _tip_hide(self):
        if self._tip:
            try: self._tip.destroy()
            except: pass
            self._tip=None

    def _ctx(self,event,entry):
        m=tk.Menu(self.frame,tearoff=0,bg=SURFACE0,fg=FG,activebackground=ACCENT,
                  activeforeground=CRUST,bd=0,relief=tk.FLAT)
        m.add_command(label="Hide course",command=lambda:self._quick_hide(entry))
        m.tk_popup(event.x_root,event.y_root)

    def _quick_hide(self,entry):
        cid=entry.get("_id")
        if cid is not None:
            self.hidden_ids.add(cid)
            if cid in self.vis_vars: self.vis_vars[cid].set(False)
        self._save_hidden(); self.draw_timetable()

    def refresh_visibility(self):
        for w in self.vis_frame.winfo_children(): w.destroy()
        self.vis_vars.clear()
        seen={}
        for entry in self.courses:
            cn=entry["_course_name"]
            if cn not in seen: seen[cn]=entry
        for cn,entry in seen.items():
            cid=entry["_id"]; color=entry.get("_color","#888")
            var=tk.BooleanVar(value=(cid not in self.hidden_ids)); self.vis_vars[cid]=var
            row=tk.Frame(self.vis_frame,bg=BG); row.pack(fill=tk.X,padx=6,pady=2)
            tk.Label(row,bg=color,width=3,height=1,relief=tk.FLAT).pack(side=tk.LEFT,padx=(2,6))
            col_f=tk.Frame(row,bg=BG); col_f.pack(side=tk.LEFT,fill=tk.X,expand=True)
            tk.Checkbutton(col_f,text=cn,variable=var,bg=BG,fg=FG,selectcolor=SURFACE1,
                           activebackground=BG,font=("Segoe UI",9),cursor="hand2",anchor="w",
                           command=lambda i=cid,v=var:self._toggle(i,v)).pack(anchor="w")
            bm=entry.get("_base_module","")
            if bm: tk.Label(col_f,text=bm,bg=BG,fg=OVERLAY,font=("Segoe UI",7)).pack(anchor="w")
        self._vis_resize()

    def _toggle(self,cid,var):
        if var.get(): self.hidden_ids.discard(cid)
        else: self.hidden_ids.add(cid)
        self._save_hidden(); self.draw_timetable()

    def show_all(self):
        self.hidden_ids.clear()
        for v in self.vis_vars.values(): v.set(True)
        self._save_hidden(); self.draw_timetable()

    def hide_all(self):
        for cid,v in self.vis_vars.items(): v.set(False); self.hidden_ids.add(cid)
        self._save_hidden(); self.draw_timetable()

    def _on_vscroll(self,e): self.canvas.yview_scroll(int(-1*(e.delta/120)),"units")
    def _on_hscroll(self,e): self.canvas.xview_scroll(int(-1*(e.delta/120)),"units")

    def _ph(self,parent,text,top=14):
        f=tk.Frame(parent,bg=BG); f.pack(fill=tk.X,padx=10,pady=(top,6))
        tk.Label(f,text=text,bg=BG,fg=SUBTEXT,font=("Segoe UI",8,"bold")).pack(side=tk.LEFT)
        tk.Frame(f,bg=SURFACE1,height=1).pack(side=tk.LEFT,fill=tk.X,expand=True,padx=(8,0),pady=6)
    def _lbl(self,p,t): return tk.Label(p,text=t,bg=BG,fg=SUBTEXT,font=("Segoe UI",9))
    def _btn(self,p,t,bg,fg,cmd): return tk.Button(p,text=t,bg=bg,fg=fg,
        font=("Segoe UI",9,"bold"),relief=tk.FLAT,cursor="hand2",padx=10,pady=4,
        activebackground=ACCENT,activeforeground=CRUST,command=cmd)


# ─────────────────────────────────────────────────────────────────────────────
#  REQUIREMENTS PANEL
# ─────────────────────────────────────────────────────────────────────────────
class RequirementsPanel:
    def __init__(self, container: tk.Frame, hub):
        self.hub       = hub
        self.frame     = tk.Frame(container, bg=BG)
        self.data_file = hub.data_file
        self.data: dict = {}
        self._build_ui()

    def reload(self):
        try:
            self.data = load_data(self.data_file)
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))
            self.data = {"requirements": {}, "semesters": []}
        self._refresh()

    # ── Compute ───────────────────────────────────────────────────────────────
    def _compute(self):
        req_cfg = self.data.get("requirements", {})
        result  = {}
        for base, cfg in req_cfg.items():
            result[base] = {}
            for specific, scfg in cfg.get("subcategories", {}).items():
                result[base][specific] = {"required": scfg.get("required_credits",0),
                                          "completed": 0, "registered": 0}
            result[base]["_total_required"] = cfg.get("total_required", 0)
        for sem in self.data.get("semesters", []):
            for course in sem.get("courses", []):
                base=course.get("base_module",""); specific=course.get("specific_module","")
                credits=course.get("credits",0); exam=course.get("exam_given",False)
                if base not in result: result[base]={}
                if specific not in result[base]:
                    result[base][specific]={"required":0,"completed":0,"registered":0}
                result[base][specific]["registered"]+=credits
                if exam: result[base][specific]["completed"]+=credits
        return result

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        topbar = tk.Frame(self.frame, bg=CRUST, height=52)
        topbar.pack(fill=tk.X); topbar.pack_propagate(False)
        tk.Label(topbar, text="  📋  Requirements Tracker", bg=CRUST, fg=FG,
                 font=("Segoe UI",14,"bold")).pack(side=tk.LEFT, padx=14, pady=12)
        tk.Button(topbar, text="🔄  Refresh", bg=SURFACE1, fg=FG,
                  font=("Segoe UI",9,"bold"), relief=tk.FLAT, cursor="hand2",
                  padx=10, pady=4, command=self.reload
                  ).pack(side=tk.RIGHT, padx=14, pady=12)

        self.summary_bar = tk.Frame(self.frame, bg=MANTLE, pady=8)
        self.summary_bar.pack(fill=tk.X)

        wrap = tk.Frame(self.frame, bg=BG)
        wrap.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)
        vsb = tk.Scrollbar(wrap, orient=tk.VERTICAL, bg=SURFACE1,
                           troughcolor=SURFACE0, relief=tk.FLAT, highlightthickness=0)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = tk.Scrollbar(wrap, orient=tk.HORIZONTAL, bg=SURFACE1,
                           troughcolor=SURFACE0, relief=tk.FLAT, highlightthickness=0)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0,
                                yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.configure(command=self.canvas.yview); hsb.configure(command=self.canvas.xview)
        self.content = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0,0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Configure>",  self._on_resize)
        self.canvas.bind("<MouseWheel>",
            lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)),"units"))
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1,"units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1,"units"))

    def _on_resize(self,_=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    # ── Refresh ───────────────────────────────────────────────────────────────
    def _refresh(self):
        data = self._compute()
        for w in self.content.winfo_children(): w.destroy()
        for w in self.summary_bar.winfo_children(): w.destroy()

        COLS  = ["Base Module","Specific Module","Completed\nCredits","Registered\nCredits",
                 "Required\nCredits","Remaining\n(Registered)","Remaining\n(Total)"]
        COL_W = [160,210,90,90,90,120,120]

        hdr = tk.Frame(self.content, bg=SURFACE0); hdr.pack(fill=tk.X, pady=(0,2))
        for i,(col,w) in enumerate(zip(COLS,COL_W)):
            tk.Label(hdr,text=col,bg=SURFACE0,fg=ACCENT,font=("Segoe UI",9,"bold"),
                     width=w//7,wraplength=w-10,justify=tk.CENTER,pady=8,padx=4
                     ).grid(row=0,column=i,sticky="nsew",padx=1)
            hdr.columnconfigure(i,minsize=w)

        grand_completed=grand_registered=grand_required=0
        req_cfg=self.data.get("requirements",{}); row_idx=0

        for base,base_cfg in req_cfg.items():
            subs=base_cfg.get("subcategories",{}); tot_req=base_cfg.get("total_required",0)
            base_completed=base_registered=0
            sec_hdr=tk.Frame(self.content,bg=SURFACE1,pady=2); sec_hdr.pack(fill=tk.X)
            tk.Label(sec_hdr,text=f"  {base}",bg=SURFACE1,fg=MAUVE,
                     font=("Segoe UI",10,"bold"),pady=3).pack(side=tk.LEFT)
            tk.Label(sec_hdr,text=f"Required: {tot_req} ECTS",
                     bg=SURFACE1,fg=SUBTEXT,font=("Segoe UI",8)).pack(side=tk.RIGHT,padx=12)

            if not subs:
                vals=data.get(base,{})
                for specific,scfg in vals.items():
                    if specific.startswith("_"): continue
                    base_completed+=scfg.get("completed",0)
                    base_registered+=scfg.get("registered",0)
                self._render_row(row_idx,base,"—",base_completed,base_registered,tot_req,COLS,COL_W)
                row_idx+=1
            else:
                for specific,scfg in subs.items():
                    spec_req=scfg.get("required_credits",tot_req)
                    vals=data.get(base,{}).get(specific,{})
                    completed=vals.get("completed",0); registered=vals.get("registered",0)
                    base_completed+=completed; base_registered+=registered
                    self._render_row(row_idx,"",specific,completed,registered,spec_req,COLS,COL_W)
                    row_idx+=1

            remaining_tot=max(0,tot_req-base_completed)
            sub_frame=tk.Frame(self.content,bg=MANTLE); sub_frame.pack(fill=tk.X)
            rem_reg_val=base_registered-tot_req
            rem_reg_txt=str(rem_reg_val) if rem_reg_val>=0 else f"-{abs(rem_reg_val)}"
            for i,(text,w,fg_c) in enumerate([
                ("",COL_W[0],FG),(f"  ↳ {base} total",COL_W[1],FG),(str(base_completed),COL_W[2],FG),
                (str(base_registered),COL_W[3],FG),(str(tot_req),COL_W[4],FG),
                (rem_reg_txt,COL_W[5],FG),
                (str(remaining_tot),COL_W[6],GREEN if remaining_tot<=0 else YELLOW),
            ]):
                tk.Label(sub_frame,text=text,bg=MANTLE,fg=fg_c,font=("Segoe UI",8,"bold"),
                         width=w//7,pady=3,padx=4).grid(row=0,column=i,sticky="nsew",padx=1)
                sub_frame.columnconfigure(i,minsize=w)

            grand_completed+=base_completed; grand_registered+=base_registered; grand_required+=tot_req

        sep=tk.Frame(self.content,bg=SURFACE1,height=2); sep.pack(fill=tk.X,pady=6)
        tot_frame=tk.Frame(self.content,bg=SURFACE0); tot_frame.pack(fill=tk.X)
        remaining_grand=max(0,grand_required-grand_completed)
        for i,(text,w) in enumerate([
            ("",COL_W[0]),("  GRAND TOTAL",COL_W[1]),(str(grand_completed),COL_W[2]),
            (str(grand_registered),COL_W[3]),(str(grand_required),COL_W[4]),
            (str(grand_registered-grand_required) if grand_registered>=grand_required else f"-{grand_required-grand_registered}",COL_W[5]),
            (str(remaining_grand),COL_W[6]),
        ]):
            fg_c=ACCENT if i==1 else (GREEN if i==6 and remaining_grand<=0 else RED if i==6 else FG)
            tk.Label(tot_frame,text=text,bg=SURFACE0,fg=fg_c,font=("Segoe UI",10,"bold"),
                     width=w//7,pady=6,padx=4).grid(row=0,column=i,sticky="nsew",padx=1)
            tot_frame.columnconfigure(i,minsize=w)

        pct=int(grand_completed/grand_required*100) if grand_required else 0
        tk.Label(self.summary_bar,text="  Total Progress:",
                 bg=MANTLE,fg=SUBTEXT,font=("Segoe UI",9)).pack(side=tk.LEFT)
        pb=tk.Frame(self.summary_bar,bg=SURFACE1,height=14,width=300)
        pb.pack(side=tk.LEFT,padx=10,pady=2); pb.pack_propagate(False)
        if pct: tk.Frame(pb,bg=GREEN,width=int(300*pct/100)).pack(side=tk.LEFT,fill=tk.Y)
        tk.Label(self.summary_bar,text=f"{grand_completed} / {grand_required} ECTS ({pct}%)",
                 bg=MANTLE,fg=FG,font=("Segoe UI",10,"bold")).pack(side=tk.LEFT)
        tk.Label(self.summary_bar,text=f"   {remaining_grand} ECTS remaining",
                 bg=MANTLE,fg=YELLOW if remaining_grand>0 else GREEN,
                 font=("Segoe UI",9)).pack(side=tk.LEFT,padx=8)

        self._render_semester_breakdown()

    def _render_row(self,idx,base,specific,completed,registered,required,COLS,COL_W):
        bg_c=SURFACE0 if idx%2==0 else BG; frame=tk.Frame(self.content,bg=bg_c); frame.pack(fill=tk.X)
        remaining_reg=registered-required; remaining_tot=max(0,required-completed)
        rem_reg_text=str(remaining_reg) if remaining_reg>=0 else f"-{abs(remaining_reg)}"
        rem_tot_color=(GREEN if remaining_tot<=0 else YELLOW if remaining_tot<=required*0.5 else RED)
        for i,(text,w) in enumerate([(base,COL_W[0]),(specific,COL_W[1]),(str(completed),COL_W[2]),
            (str(registered),COL_W[3]),(str(required),COL_W[4]),(rem_reg_text,COL_W[5]),(str(remaining_tot),COL_W[6])]):
            fg_c=(rem_tot_color if i==6 else ACCENT if i==0 and base else FG)
            tk.Label(frame,text=text,bg=bg_c,fg=fg_c,font=("Segoe UI",9),
                     width=w//7,pady=5,padx=6,anchor="w").grid(row=0,column=i,sticky="nsew",padx=1)
            frame.columnconfigure(i,minsize=w)

    def _render_semester_breakdown(self):
        sep=tk.Frame(self.content,bg=SURFACE1,height=2); sep.pack(fill=tk.X,pady=(20,6))
        tk.Label(self.content,text="  Per-Semester Credit Breakdown",
                 bg=BG,fg=MAUVE,font=("Segoe UI",11,"bold")).pack(anchor="w",padx=8,pady=(0,6))
        for sem in self.data.get("semesters",[]):
            courses=sem.get("courses",[]); total_sem=sum(c.get("credits",0) for c in courses)
            done_sem=sum(c.get("credits",0) for c in courses if c.get("exam_given"))
            sf=tk.Frame(self.content,bg=SURFACE0,pady=4); sf.pack(fill=tk.X,padx=8,pady=3)
            tk.Label(sf,text=f"  {sem.get('display_name',sem['name'])}",
                     bg=SURFACE0,fg=ACCENT,font=("Segoe UI",10,"bold")).pack(side=tk.LEFT)
            tk.Label(sf,text=f"  {done_sem} done / {total_sem} registered",
                     bg=SURFACE0,fg=FG,font=("Segoe UI",9)).pack(side=tk.LEFT,padx=8)
            pct=int(done_sem/total_sem*100) if total_sem else 0
            pb=tk.Frame(sf,bg=SURFACE1,height=10,width=150); pb.pack(side=tk.LEFT,padx=8)
            pb.pack_propagate(False)
            if pct: tk.Frame(pb,bg=GREEN,width=int(150*pct/100)).pack(side=tk.LEFT,fill=tk.Y)
            tk.Label(sf,text=f"({pct}%)",bg=SURFACE0,fg=SUBTEXT,font=("Segoe UI",8)).pack(side=tk.LEFT)
            by_base: dict={}
            for course in courses:
                b=course.get("base_module","Other"); by_base.setdefault(b,{"done":0,"total":0})
                by_base[b]["total"]+=course.get("credits",0)
                if course.get("exam_given"): by_base[b]["done"]+=course.get("credits",0)
            dr=tk.Frame(sf,bg=SURFACE0); dr.pack(side=tk.LEFT,padx=16)
            for b,vals in by_base.items():
                tk.Label(dr,text=f"{b}: {vals['done']}/{vals['total']}",
                         bg=SURFACE0,fg=SUBTEXT,font=("Segoe UI",8)).pack(side=tk.LEFT,padx=6)


# ─────────────────────────────────────────────────────────────────────────────
#  SEMESTER PANEL
# ─────────────────────────────────────────────────────────────────────────────
class SemesterPanel:
    COL_DEFS = [
        ("No",40),("Course Name",260),("Base Module",140),("Specific Module",150),
        ("Credits",62),("Exam Given?",80),("Credits\nObtainable",80),
        ("Exam Date",90),("Exam Time",70),("Alt Date",90),("Alt Time",70),
        ("Additional Info",160),("",40),
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
        s.configure("TCombobox", fieldbackground=SURFACE1, background=SURFACE0,
                    foreground=FG, selectbackground=ACCENT, arrowcolor=SUBTEXT, borderwidth=0)
        s.map("TCombobox", fieldbackground=[("readonly", SURFACE1)])

    def reload(self):
        try:
            self.data = load_data(self.data_file)
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex)); return
        sems = [s["name"] for s in self.data.get("semesters",[])]
        self.sem_cb["values"] = sems
        cur = self.sem_var.get()
        if cur not in sems:
            self.sem_var.set(sems[-1] if sems else "")
        self._switch_semester()

    # ── UI skeleton ───────────────────────────────────────────────────────────
    def _build_ui(self):
        topbar = tk.Frame(self.frame, bg=CRUST, height=52)
        topbar.pack(fill=tk.X); topbar.pack_propagate(False)
        tk.Label(topbar, text="  📊  Semester Credits", bg=CRUST, fg=FG,
                 font=("Segoe UI",14,"bold")).pack(side=tk.LEFT, padx=14, pady=12)
        tk.Frame(topbar, bg=SURFACE1, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=12, padx=10)
        self.sem_var = tk.StringVar()
        self.sem_cb  = ttk.Combobox(topbar, textvariable=self.sem_var,
                                    state="readonly", width=24, font=("Segoe UI",10))
        self.sem_cb.pack(side=tk.LEFT, pady=14, padx=4)
        self.sem_cb.bind("<<ComboboxSelected>>", self._switch_semester)
        self._btn(topbar, "➕  Add Course", GREEN, CRUST,
                  self._add_course_dialog).pack(side=tk.RIGHT, padx=14, pady=12)

        self.summary_bar = tk.Frame(self.frame, bg=MANTLE, pady=6)
        self.summary_bar.pack(fill=tk.X)

        wrap = tk.Frame(self.frame, bg=BG)
        wrap.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        vsb = tk.Scrollbar(wrap, orient=tk.VERTICAL, bg=SURFACE1,
                           troughcolor=SURFACE0, relief=tk.FLAT, highlightthickness=0)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = tk.Scrollbar(wrap, orient=tk.HORIZONTAL, bg=SURFACE1,
                           troughcolor=SURFACE0, relief=tk.FLAT, highlightthickness=0)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0,
                                yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.configure(command=self.canvas.yview); hsb.configure(command=self.canvas.xview)
        self.table_frame = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0,0), window=self.table_frame, anchor="nw")
        self.table_frame.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Configure>", self._on_resize)
        for seq in ("<MouseWheel>","<Button-4>","<Button-5>"):
            self.canvas.bind(seq, self._scroll)

    def _on_resize(self,_=None): self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    def _scroll(self,event):
        if event.num==4: self.canvas.yview_scroll(-1,"units")
        elif event.num==5: self.canvas.yview_scroll(1,"units")
        else: self.canvas.yview_scroll(int(-1*(event.delta/120)),"units")

    # ── Data ──────────────────────────────────────────────────────────────────
    def _switch_semester(self,*_):
        name=self.sem_var.get()
        sem=next((s for s in self.data.get("semesters",[]) if s["name"]==name),None)
        if not sem: return
        self.sem=sem; self._render_table()

    def _save(self): save_data(self.data, self.data_file)

    # ── Table render ──────────────────────────────────────────────────────────
    def _render_table(self):
        for w in self.table_frame.winfo_children(): w.destroy()
        self._refresh_summary()
        courses=self.sem.get("courses",[])
        hdr=tk.Frame(self.table_frame,bg=SURFACE0); hdr.pack(fill=tk.X)
        for ci,(label,width) in enumerate(self.COL_DEFS):
            tk.Label(hdr,text=label,bg=SURFACE0,fg=ACCENT,font=("Segoe UI",9,"bold"),
                     width=width//7,pady=8,padx=4,wraplength=width-6,justify=tk.CENTER
                     ).grid(row=0,column=ci,sticky="nsew",padx=1)
            hdr.columnconfigure(ci,minsize=width)
        tk.Frame(self.table_frame,bg=ACCENT,height=2).pack(fill=tk.X)
        by_base:dict={}
        for course in courses:
            b=course.get("base_module","Other"); by_base.setdefault(b,[]).append(course)
        row_num=1
        for base,group in by_base.items():
            sec=tk.Frame(self.table_frame,bg=SURFACE1,pady=2); sec.pack(fill=tk.X,pady=(8,0))
            tk.Label(sec,text=f"  {base}",bg=SURFACE1,fg=FG,
                     font=("Segoe UI",10,"bold"),pady=3).pack(side=tk.LEFT)
            tot=sum(c.get("credits",0) for c in group)
            done=sum(c.get("credits",0) for c in group if c.get("exam_given"))
            tk.Label(sec,text=f"{done}/{tot} ECTS",bg=SURFACE1,
                     fg=GREEN if done>=tot else YELLOW,
                     font=("Segoe UI",9)).pack(side=tk.RIGHT,padx=12)
            for ci,course in enumerate(group):
                self._render_course_row(row_num,ci,course,bg=SURFACE0 if ci%2==0 else BG)
                row_num+=1
        tk.Frame(self.table_frame,bg=SURFACE1,height=2).pack(fill=tk.X,pady=6)
        tot_frame=tk.Frame(self.table_frame,bg=SURFACE0); tot_frame.pack(fill=tk.X)
        total_credits=sum(c.get("credits",0) for c in courses)
        done_credits=sum(c.get("credits",0) for c in courses if c.get("exam_given"))
        for i,(text,width) in enumerate(self.COL_DEFS):
            if i==1: t=f"Total — {row_num-1} courses"; fg_c=FG
            elif i==4: t=str(total_credits); fg_c=ACCENT
            elif i==6: t=str(done_credits); fg_c=GREEN if done_credits==total_credits else YELLOW
            else: t=""; fg_c=FG
            tk.Label(tot_frame,text=t,bg=SURFACE0,fg=fg_c,font=("Segoe UI",10,"bold"),
                     width=width//7,pady=6,padx=4).grid(row=0,column=i,sticky="nsew",padx=1)
            tot_frame.columnconfigure(i,minsize=width)

    def _render_course_row(self,row_num,ci,course,bg=BG):
        row=tk.Frame(self.table_frame,bg=bg); row.pack(fill=tk.X)
        color=course.get("color",COURSE_COLORS[ci%len(COURSE_COLORS)])
        credits=course.get("credits",0); exam=course.get("exam_given",False)
        def make_lbl(text,width,fg_c=FG,bold=False):
            return tk.Label(row,text=text,bg=bg,fg=fg_c,
                            font=("Segoe UI",9,"bold" if bold else "normal"),
                            width=width//7,pady=5,padx=4,anchor="w")
        no_frame=tk.Frame(row,bg=bg); no_frame.grid(row=0,column=0,sticky="nsew",padx=1)
        tk.Label(no_frame,bg=color,width=3,height=1).pack(side=tk.LEFT,padx=2)
        tk.Label(no_frame,text=str(row_num),bg=bg,fg=OVERLAY,font=("Segoe UI",8)).pack(side=tk.LEFT)
        row.columnconfigure(0,minsize=self.COL_DEFS[0][1])
        name_lbl=tk.Label(row,text=course.get("name",""),bg=bg,fg=color,
                          font=("Segoe UI",9,"bold"),width=self.COL_DEFS[1][1]//7,
                          pady=5,padx=4,anchor="w",wraplength=self.COL_DEFS[1][1]-8,justify=tk.LEFT)
        name_lbl.grid(row=0,column=1,sticky="nsew",padx=1)
        name_lbl.bind("<Double-Button-1>",lambda e,c=course:self._edit_course_dialog(c))
        row.columnconfigure(1,minsize=self.COL_DEFS[1][1])
        make_lbl(course.get("base_module",""),self.COL_DEFS[2][1],SUBTEXT).grid(row=0,column=2,sticky="nsew",padx=1)
        row.columnconfigure(2,minsize=self.COL_DEFS[2][1])
        make_lbl(course.get("specific_module",""),self.COL_DEFS[3][1],SUBTEXT).grid(row=0,column=3,sticky="nsew",padx=1)
        row.columnconfigure(3,minsize=self.COL_DEFS[3][1])
        make_lbl(str(credits),self.COL_DEFS[4][1],ACCENT,bold=True).grid(row=0,column=4,sticky="nsew",padx=1)
        row.columnconfigure(4,minsize=self.COL_DEFS[4][1])
        exam_var=tk.BooleanVar(value=exam); exam_bg="#1a3a1a" if exam else bg
        cb=tk.Checkbutton(row,variable=exam_var,bg=exam_bg,selectcolor=SURFACE1,
                          activebackground=bg,cursor="hand2",
                          command=lambda v=exam_var,c=course,r=row:self._toggle_exam(c,v,r))
        cb.grid(row=0,column=5,sticky="nsew",padx=1); row.columnconfigure(5,minsize=self.COL_DEFS[5][1])
        obtainable=credits if exam else 0
        make_lbl(str(obtainable),self.COL_DEFS[6][1],GREEN if exam else OVERLAY).grid(row=0,column=6,sticky="nsew",padx=1)
        row.columnconfigure(6,minsize=self.COL_DEFS[6][1])
        for col_i,field_key in enumerate(["exam_date","exam_time","alt_date","alt_time"],start=7):
            val=course.get(field_key,"")
            lbl=tk.Label(row,text=val or "—",bg=bg,fg=SUBTEXT if not val else FG,
                         font=("Segoe UI",8),width=self.COL_DEFS[col_i][1]//7,pady=5,padx=4,anchor="w",cursor="hand2")
            lbl.grid(row=0,column=col_i,sticky="nsew",padx=1)
            lbl.bind("<Button-1>",lambda e,c=course,k=field_key,l=lbl:self._inline_edit(c,k,l))
            row.columnconfigure(col_i,minsize=self.COL_DEFS[col_i][1])
        info_lbl=tk.Label(row,text=course.get("additional_info","") or "",bg=bg,fg=OVERLAY,
                          font=("Segoe UI",8),width=self.COL_DEFS[11][1]//7,pady=5,padx=4,anchor="w",cursor="hand2",
                          wraplength=self.COL_DEFS[11][1]-8)
        info_lbl.grid(row=0,column=11,sticky="nsew",padx=1)
        info_lbl.bind("<Button-1>",lambda e,c=course,l=info_lbl:self._inline_edit(c,"additional_info",l))
        row.columnconfigure(11,minsize=self.COL_DEFS[11][1])
        tk.Button(row,text="✕",bg=bg,fg=RED,font=("Segoe UI",9),relief=tk.FLAT,cursor="hand2",
                  command=lambda c=course:self._delete_course(c)).grid(row=0,column=12,sticky="nsew",padx=1)
        row.columnconfigure(12,minsize=self.COL_DEFS[12][1])

    def _refresh_summary(self):
        for w in self.summary_bar.winfo_children(): w.destroy()
        courses=self.sem.get("courses",[]); total=sum(c.get("credits",0) for c in courses)
        done=sum(c.get("credits",0) for c in courses if c.get("exam_given"))
        n=len(courses); pct=int(done/total*100) if total else 0
        tk.Label(self.summary_bar,text=f"  {n} courses  |  {total} ECTS registered",
                 bg=MANTLE,fg=SUBTEXT,font=("Segoe UI",9)).pack(side=tk.LEFT)
        pb=tk.Frame(self.summary_bar,bg=SURFACE1,height=12,width=200)
        pb.pack(side=tk.LEFT,padx=10); pb.pack_propagate(False)
        if pct: tk.Frame(pb,bg=GREEN,width=int(200*pct/100)).pack(side=tk.LEFT,fill=tk.Y)
        tk.Label(self.summary_bar,text=f"{done}/{total} ECTS exam given ({pct}%)",
                 bg=MANTLE,fg=FG,font=("Segoe UI",9,"bold")).pack(side=tk.LEFT,padx=6)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _toggle_exam(self,course,var,row):
        course["exam_given"]=var.get(); self._save(); self._render_table()

    def _inline_edit(self,course,field_key,label):
        win=tk.Toplevel(self.frame); win.overrideredirect(True); win.configure(bg=SURFACE1)
        x=label.winfo_rootx(); y=label.winfo_rooty()
        w=max(label.winfo_width(),120); h=label.winfo_height()+4
        win.geometry(f"{w}x{h}+{x}+{y-2}")
        var=tk.StringVar(value=course.get(field_key,"") or "")
        e=tk.Entry(win,textvariable=var,bg=SURFACE0,fg=FG,insertbackground=FG,relief=tk.FLAT,
                   font=("Segoe UI",9),highlightthickness=1,highlightcolor=ACCENT,highlightbackground=ACCENT)
        e.pack(fill=tk.BOTH,expand=True,padx=2,pady=2); e.focus_set(); e.select_range(0,tk.END)
        def commit(*_): course[field_key]=var.get().strip(); self._save(); win.destroy(); self._render_table()
        e.bind("<Return>",commit); e.bind("<FocusOut>",commit); e.bind("<Escape>",lambda e:win.destroy())

    def _delete_course(self,course):
        if messagebox.askyesno("Delete",f"Remove '{course.get('name','')}' from this semester?",parent=self.frame):
            self.sem["courses"]=[c for c in self.sem["courses"] if c is not course]
            self._save(); self._render_table()

    def _add_course_dialog(self): self._course_form_dialog(None)
    def _edit_course_dialog(self,course): self._course_form_dialog(course)

    def _course_form_dialog(self,existing=None):
        win=tk.Toplevel(self.frame); win.title("Edit Course" if existing else "Add Course")
        win.geometry("520x680"); win.configure(bg=BG); win.grab_set(); win.resizable(False,False)
        tk.Label(win,text="Edit Course" if existing else "Add New Course",
                 bg=BG,fg=FG,font=("Segoe UI",13,"bold")).pack(pady=(14,6))
        g=tk.Frame(win,bg=BG); g.pack(fill=tk.X,padx=24); g.columnconfigure(1,weight=1)
        def row(label,wf,r):
            tk.Label(g,text=label,bg=BG,fg=SUBTEXT,font=("Segoe UI",9)).grid(row=r,column=0,sticky="w",pady=4)
            w=wf(g); w.grid(row=r,column=1,sticky="ew",pady=4,padx=(10,0)); return w
        def entry(parent,var,**kw):
            return tk.Entry(parent,textvariable=var,bg=SURFACE0,fg=FG,insertbackground=FG,
                            relief=tk.FLAT,font=("Segoe UI",10),highlightthickness=1,
                            highlightcolor=ACCENT,highlightbackground=SURFACE1,**kw)
        e=existing or {}
        name_var =tk.StringVar(value=e.get("name",""))
        base_var =tk.StringVar(value=e.get("base_module",BASE_MODULES[0]))
        spec_var =tk.StringVar(value=e.get("specific_module",""))
        cred_var =tk.StringVar(value=str(e.get("credits",5)))
        exam_var =tk.BooleanVar(value=e.get("exam_given",False))
        edate_var=tk.StringVar(value=e.get("exam_date",""))
        etime_var=tk.StringVar(value=e.get("exam_time",""))
        adate_var=tk.StringVar(value=e.get("alt_date",""))
        atime_var=tk.StringVar(value=e.get("alt_time",""))
        info_var =tk.StringVar(value=e.get("additional_info",""))
        color_var=tk.StringVar(value=e.get("color",COURSE_COLORS[0]))
        row("Course Name *",lambda p:entry(p,name_var),0)
        tk.Label(g,text="Base Module",bg=BG,fg=SUBTEXT,font=("Segoe UI",9)).grid(row=1,column=0,sticky="w",pady=4)
        base_cb=ttk.Combobox(g,textvariable=base_var,values=BASE_MODULES,state="readonly",font=("Segoe UI",10))
        base_cb.grid(row=1,column=1,sticky="ew",pady=4,padx=(10,0))
        tk.Label(g,text="Specific Module",bg=BG,fg=SUBTEXT,font=("Segoe UI",9)).grid(row=2,column=0,sticky="w",pady=4)
        spec_cb=ttk.Combobox(g,textvariable=spec_var,font=("Segoe UI",10))
        spec_cb.grid(row=2,column=1,sticky="ew",pady=4,padx=(10,0))
        def update_spec(*_):
            opts=SPECIFIC_MODULES.get(base_var.get(),[""])
            spec_cb["values"]=opts
            if spec_var.get() not in opts: spec_var.set(opts[0] if opts else "")
        base_cb.bind("<<ComboboxSelected>>",update_spec); update_spec()
        row("Credits",lambda p:entry(p,cred_var,width=6),3)
        tk.Label(g,text="Exam Given?",bg=BG,fg=SUBTEXT,font=("Segoe UI",9)).grid(row=4,column=0,sticky="w",pady=4)
        tk.Checkbutton(g,variable=exam_var,bg=BG,fg=FG,selectcolor=SURFACE1,activebackground=BG
                       ).grid(row=4,column=1,sticky="w",pady=4,padx=(10,0))
        row("Exam Date",  lambda p:entry(p,edate_var),5)
        row("Exam Time",  lambda p:entry(p,etime_var),6)
        row("Alt Date",   lambda p:entry(p,adate_var),7)
        row("Alt Time",   lambda p:entry(p,atime_var),8)
        row("Additional Info",lambda p:entry(p,info_var),9)
        tk.Label(g,text="Color",bg=BG,fg=SUBTEXT,font=("Segoe UI",9)).grid(row=10,column=0,sticky="w",pady=4)
        col_frame=tk.Frame(g,bg=BG); col_frame.grid(row=10,column=1,sticky="ew",pady=4,padx=(10,0))
        color_sw=tk.Label(col_frame,bg=color_var.get(),width=4,relief=tk.FLAT); color_sw.pack(side=tk.LEFT)
        pal=tk.Frame(col_frame,bg=BG); pal.pack(side=tk.LEFT,padx=6)
        for c in COURSE_COLORS:
            dot=tk.Label(pal,bg=c,width=2,height=1,cursor="hand2"); dot.pack(side=tk.LEFT,padx=1)
            dot.bind("<Button-1>",lambda e,col=c:(color_var.set(col),color_sw.configure(bg=col)))
        tk.Button(col_frame,text="Pick…",bg=SURFACE1,fg=FG,font=("Segoe UI",8),relief=tk.FLAT,cursor="hand2",
                  command=lambda:(lambda res:(color_var.set(res[1]),color_sw.configure(bg=res[1]))
                  )(colorchooser.askcolor(color=color_var.get())) if True else None
                  ).pack(side=tk.LEFT,padx=4)
        def commit():
            name=name_var.get().strip()
            if not name: messagebox.showwarning("Missing","Course name is required.",parent=win); return
            try: credits=int(cred_var.get())
            except: messagebox.showwarning("Bad Value","Credits must be an integer.",parent=win); return
            fields=dict(name=name,base_module=base_var.get(),specific_module=spec_var.get(),
                        credits=credits,exam_given=exam_var.get(),exam_date=edate_var.get().strip(),
                        exam_time=etime_var.get().strip(),alt_date=adate_var.get().strip(),
                        alt_time=atime_var.get().strip(),additional_info=info_var.get().strip(),
                        color=color_var.get())
            if existing: existing.update(fields)
            else: fields.update(hidden=False,slots=[]); self.sem.setdefault("courses",[]).append(fields)
            self._save(); win.destroy(); self._render_table()
        btn_row=tk.Frame(win,bg=BG); btn_row.pack(pady=14)
        self._btn(btn_row,"Save",ACCENT,CRUST,commit).pack(side=tk.LEFT,padx=6)
        self._btn(btn_row,"Cancel",SURFACE1,FG,win.destroy).pack(side=tk.LEFT)

    def _btn(self,p,t,bg,fg,cmd):
        return tk.Button(p,text=t,bg=bg,fg=fg,font=("Segoe UI",9,"bold"),relief=tk.FLAT,
                         cursor="hand2",padx=10,pady=4,activebackground=ACCENT,
                         activeforeground=CRUST,command=cmd)


# ─────────────────────────────────────────────────────────────────────────────
#  HOME PANEL  (the original hub dashboard)
# ─────────────────────────────────────────────────────────────────────────────
class HomePanel:
    def __init__(self, container: tk.Frame, hub):
        self.hub   = hub
        self.frame = tk.Frame(container, bg=BG)
        self._build_ui()

    def reload(self):
        self._refresh_summary()

    def _build_ui(self):
        topbar = tk.Frame(self.frame, bg=CRUST, height=60)
        topbar.pack(fill=tk.X); topbar.pack_propagate(False)
        tk.Label(topbar, text="  🎓  Academic Hub",
                 bg=CRUST, fg=FG, font=("Segoe UI",16,"bold")).pack(side=tk.LEFT, padx=14, pady=14)
        btn_frame = tk.Frame(topbar, bg=CRUST); btn_frame.pack(side=tk.RIGHT, padx=14, pady=12)
        self._btn(btn_frame,"📂  Load Data",SURFACE1,FG,self.hub.load_data_dialog).pack(side=tk.LEFT,padx=(0,6))
        self._btn(btn_frame,"➕  New Semester",GREEN,CRUST,self.hub.new_semester_dialog).pack(side=tk.LEFT)

        # Semester selector row
        sel_row = tk.Frame(self.frame, bg=MANTLE, pady=10)
        sel_row.pack(fill=tk.X)
        tk.Label(sel_row, text="  Semester:", bg=MANTLE, fg=SUBTEXT,
                 font=("Segoe UI",10)).pack(side=tk.LEFT, padx=(14,6))
        self.sem_var = tk.StringVar()
        self.sem_cb  = ttk.Combobox(sel_row, textvariable=self.sem_var,
                                    state="readonly", width=30, font=("Segoe UI",10))
        self.sem_cb.pack(side=tk.LEFT, padx=(0,10))
        self._refresh_semester_cb()

        # Credit summary strip
        self.summary_frame = tk.Frame(self.frame, bg=SURFACE0, pady=6)
        self.summary_frame.pack(fill=tk.X, padx=20, pady=(14,0))
        self._refresh_summary()

        # Three launch cards
        cards = tk.Frame(self.frame, bg=BG)
        cards.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)
        cards.columnconfigure((0,1,2), weight=1, uniform="col")

        card_defs = [
            ("📅","Timetable",     "Weekly schedule\nfor selected semester",  ACCENT,"timetable"),
            ("📋","Requirements",  "Credit requirements\n& overall progress",   GREEN,"requirements"),
            ("📊","Semester Credits","Course list, modules\n& exam tracking",   MAUVE,"semester"),
        ]
        for col,(icon,title,desc,color,panel_id) in enumerate(card_defs):
            self._make_card(cards,icon,title,desc,color,panel_id).grid(
                row=0,column=col,padx=8,pady=6,sticky="nsew")

        tk.Label(self.frame, text=f"Data file: {os.path.abspath(self.hub.data_file)}",
                 bg=BG,fg=OVERLAY,font=("Segoe UI",8)).pack(side=tk.BOTTOM,anchor="w",padx=20,pady=(0,8))

    def _make_card(self,parent,icon,title,desc,color,panel_id):
        card = tk.Frame(parent, bg=SURFACE0, cursor="hand2", relief=tk.FLAT, bd=0)
        tk.Frame(card, bg=color, height=4).pack(fill=tk.X)
        tk.Label(card,text=icon,bg=SURFACE0,fg=color,font=("Segoe UI",32)).pack(pady=(18,4))
        tk.Label(card,text=title,bg=SURFACE0,fg=FG,font=("Segoe UI",13,"bold")).pack()
        tk.Label(card,text=desc,bg=SURFACE0,fg=SUBTEXT,font=("Segoe UI",9),justify=tk.CENTER).pack(pady=(4,14))
        tk.Button(card, text=f"Open {title}", bg=color, fg=CRUST,
                  font=("Segoe UI",9,"bold"), relief=tk.FLAT, cursor="hand2",
                  padx=14, pady=6, activebackground=SURFACE1,
                  command=lambda p=panel_id: self.hub.show_panel(p)
                  ).pack(pady=(0,18))
        for widget in (card,):
            widget.bind("<Enter>", lambda e,c=card: c.configure(bg=SURFACE1))
            widget.bind("<Leave>", lambda e,c=card: c.configure(bg=SURFACE0))
        return card

    def _refresh_semester_cb(self):
        names = [s["name"] for s in self.hub.data.get("semesters",[])]
        self.sem_cb["values"] = names
        if names: self.sem_var.set(names[-1])

    def _refresh_summary(self):
        for w in self.summary_frame.winfo_children(): w.destroy()
        req = self.hub.data.get("requirements",{})
        total_req = sum(v.get("total_required",0) for v in req.values())
        completed = 0
        for sem in self.hub.data.get("semesters",[]):
            for c in sem.get("courses",[]):
                if c.get("exam_given") and c.get("credits",0):
                    completed += c["credits"]
        remaining = max(0, total_req-completed)
        pct = int(completed/total_req*100) if total_req else 0
        tk.Label(self.summary_frame,text="  Overall Progress:",
                 bg=SURFACE0,fg=SUBTEXT,font=("Segoe UI",9)).pack(side=tk.LEFT)
        pb_frame=tk.Frame(self.summary_frame,bg=SURFACE1,height=12,width=200)
        pb_frame.pack(side=tk.LEFT,padx=10,pady=2); pb_frame.pack_propagate(False)
        if pct: tk.Frame(pb_frame,bg=GREEN,width=int(200*pct/100)).pack(side=tk.LEFT,fill=tk.Y)
        tk.Label(self.summary_frame,text=f"{completed}/{total_req} credits  ({pct}%)",
                 bg=SURFACE0,fg=FG,font=("Segoe UI",9,"bold")).pack(side=tk.LEFT,padx=6)
        tk.Label(self.summary_frame,text=f"  {remaining} remaining",
                 bg=SURFACE0,fg=YELLOW if remaining>0 else GREEN,
                 font=("Segoe UI",9)).pack(side=tk.LEFT)

    def _btn(self,parent,text,bg,fg,cmd):
        return tk.Button(parent,text=text,bg=bg,fg=fg,font=("Segoe UI",9,"bold"),relief=tk.FLAT,
                         cursor="hand2",padx=10,pady=4,activebackground=ACCENT,
                         activeforeground=CRUST,command=cmd)


# ─────────────────────────────────────────────────────────────────────────────
#  HUB APP  —  single-window host with overlay drawer
# ─────────────────────────────────────────────────────────────────────────────
class HubApp:
    DRAWER_W = 240

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Academic Hub")
        self.root.geometry("1300x820")
        self.root.minsize(900, 600)
        self.root.configure(bg=BG)

        self.data_file = DATA_FILE
        self.data      = load_data()

        self._current  = None
        self._drawer_open = False
        self._panels: dict = {}

        self._build_topbar()
        self._build_body()
        self._build_drawer()
        self.show_panel("home")

    # ── Top bar (fixed, contains only ☰ + title) ─────────────────────────────
    def _build_topbar(self):
        self._topbar = tk.Frame(self.root, bg=CRUST, height=48)
        self._topbar.pack(fill=tk.X); self._topbar.pack_propagate(False)

        # Hamburger button
        ham = tk.Button(self._topbar, text="☰", bg=CRUST, fg=FG,
                        font=("Segoe UI",16), relief=tk.FLAT, cursor="hand2",
                        padx=14, pady=4, activebackground=SURFACE0,
                        activeforeground=ACCENT, bd=0,
                        command=self._toggle_drawer)
        ham.pack(side=tk.LEFT)

        # App title (updates per panel)
        self._title_lbl = tk.Label(self._topbar, text="Academic Hub",
                                   bg=CRUST, fg=FG, font=("Segoe UI",13,"bold"))
        self._title_lbl.pack(side=tk.LEFT, padx=8)

    # ── Body (panels live here; backdrop + drawer float on top) ──────────────
    def _build_body(self):
        self._body = tk.Frame(self.root, bg=BG)
        self._body.pack(fill=tk.BOTH, expand=True)

        # All panels share this host
        self._panels_host = tk.Frame(self._body, bg=BG)
        self._panels_host.place(x=0, y=0, relwidth=1, relheight=1)

        # Build all panel objects
        self._panels = {
            "home":         HomePanel(self._panels_host, self),
            "timetable":    TimetablePanel(self._panels_host, self),
            "requirements": RequirementsPanel(self._panels_host, self),
            "semester":     SemesterPanel(self._panels_host, self),
        }

        # Dim backdrop — placed behind drawer, captures outside-clicks
        self._backdrop = tk.Frame(self._body, bg="#0D0D1A", cursor="arrow")
        self._backdrop.bind("<Button-1>", lambda e: self._close_drawer())

    # ── Overlay drawer ────────────────────────────────────────────────────────
    def _build_drawer(self):
        self._drawer = tk.Frame(self._body, bg=CRUST, width=self.DRAWER_W)

        # App logo strip
        logo = tk.Frame(self._drawer, bg=MANTLE, height=60)
        logo.pack(fill=tk.X); logo.pack_propagate(False)
        tk.Label(logo, text="  🎓  Academic Hub", bg=MANTLE, fg=FG,
                 font=("Segoe UI",12,"bold")).pack(side=tk.LEFT, padx=10, pady=16)

        # Nav items
        nav_items = [
            ("🏠  Home",             "home",         FG),
            ("📅  Timetable",        "timetable",    ACCENT),
            ("📋  Requirements",     "requirements", GREEN),
            ("📊  Semester Credits", "semester",     MAUVE),
        ]
        nav_container = tk.Frame(self._drawer, bg=CRUST)
        nav_container.pack(fill=tk.X, pady=(8,0))

        self._nav_btns = {}
        for label, panel_id, color in nav_items:
            btn = self._nav_btn(nav_container, label, color, panel_id)
            self._nav_btns[panel_id] = btn

        # Separator
        tk.Frame(self._drawer, bg=SURFACE1, height=1).pack(fill=tk.X, padx=16, pady=12)

        # Utility buttons
        util = tk.Frame(self._drawer, bg=CRUST)
        util.pack(fill=tk.X, padx=12)
        self._small_btn(util, "📂  Load Data",     self.load_data_dialog).pack(fill=tk.X, pady=3)
        self._small_btn(util, "➕  New Semester",   self.new_semester_dialog).pack(fill=tk.X, pady=3)

        # Data file label at bottom
        tk.Label(self._drawer,
                 text=f"  {os.path.basename(self.data_file)}",
                 bg=CRUST, fg=OVERLAY, font=("Segoe UI",8)
                 ).pack(side=tk.BOTTOM, anchor="w", padx=10, pady=8)

    def _nav_btn(self, parent, label, color, panel_id):
        """Full-width nav button for the drawer."""
        ITEM_H = 46
        f = tk.Frame(parent, bg=CRUST, height=ITEM_H, cursor="hand2")
        f.pack(fill=tk.X); f.pack_propagate(False)

        accent_bar = tk.Frame(f, bg=CRUST, width=4)
        accent_bar.pack(side=tk.LEFT, fill=tk.Y)

        lbl = tk.Label(f, text=f"  {label}", bg=CRUST, fg=FG,
                       font=("Segoe UI",10), anchor="w", cursor="hand2")
        lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def on_enter(_):
            if self._current != panel_id:
                f.configure(bg=SURFACE0); lbl.configure(bg=SURFACE0)
        def on_leave(_):
            if self._current != panel_id:
                f.configure(bg=CRUST); lbl.configure(bg=CRUST)
        def on_click(_):
            self.show_panel(panel_id)

        for widget in (f, lbl):
            widget.bind("<Enter>",   on_enter)
            widget.bind("<Leave>",   on_leave)
            widget.bind("<Button-1>",on_click)

        f._accent_bar = accent_bar
        f._lbl        = lbl
        f._color      = color
        return f

    def _small_btn(self, parent, text, cmd):
        return tk.Button(parent, text=text, bg=SURFACE0, fg=SUBTEXT,
                         font=("Segoe UI",9), relief=tk.FLAT, cursor="hand2",
                         padx=10, pady=6, anchor="w", activebackground=SURFACE1,
                         activeforeground=FG, bd=0, command=cmd)

    # ── Panel switching ───────────────────────────────────────────────────────
    def show_panel(self, name: str):
        # Hide all panels
        for panel in self._panels.values():
            panel.frame.pack_forget()

        self._current = name
        panel = self._panels[name]
        panel.frame.pack(in_=self._panels_host, fill=tk.BOTH, expand=True)
        panel.reload()

        # Update topbar title
        titles = {"home":"Academic Hub","timetable":"📅  Timetable",
                  "requirements":"📋  Requirements","semester":"📊  Semester Credits"}
        self._title_lbl.configure(text=titles.get(name, name))

        # Update active nav button styling
        for pid, btn in self._nav_btns.items():
            if pid == name:
                btn.configure(bg=SURFACE1); btn._lbl.configure(bg=SURFACE1, fg=btn._color)
                btn._accent_bar.configure(bg=btn._color)
            else:
                btn.configure(bg=CRUST); btn._lbl.configure(bg=CRUST, fg=FG)
                btn._accent_bar.configure(bg=CRUST)

        self._close_drawer()

    # ── Drawer open / close ───────────────────────────────────────────────────
    def _toggle_drawer(self):
        if self._drawer_open: self._close_drawer()
        else: self._open_drawer()

    def _open_drawer(self):
        if self._drawer_open: return
        # Backdrop covers the entire body
        self._backdrop.place(x=0, y=0, relwidth=1, relheight=1)
        self._backdrop.lift()
        # Drawer sits on top of backdrop, flush left
        self._drawer.place(x=0, y=0, width=self.DRAWER_W, relheight=1)
        self._drawer.lift()
        self._drawer_open = True

    def _close_drawer(self):
        if not self._drawer_open: return
        self._drawer.place_forget()
        self._backdrop.place_forget()
        self._drawer_open = False

    # ── Data actions ──────────────────────────────────────────────────────────
    def load_data_dialog(self):
        path = filedialog.askopenfilename(
            title="Open data.json",
            filetypes=[("JSON Files","*.json"),("All Files","*.*")])
        if path:
            global DATA_FILE
            DATA_FILE = path
            self.data_file = path
            self.data = load_data(path)
            if self._current:
                self._panels[self._current].reload()

    def new_semester_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("New Semester"); win.geometry("360x200")
        win.configure(bg=BG); win.resizable(False,False); win.grab_set()
        tk.Label(win,text="New Semester",bg=BG,fg=FG,
                 font=("Segoe UI",13,"bold")).pack(pady=(18,6))
        frm=tk.Frame(win,bg=BG); frm.pack(fill=tk.X,padx=30); frm.columnconfigure(1,weight=1)
        name_var=tk.StringVar(value="WiSe26")
        disp_var=tk.StringVar(value="Winter Semester 2026/27")
        for i,(lbl,var) in enumerate([("Short name:",name_var),("Display name:",disp_var)]):
            tk.Label(frm,text=lbl,bg=BG,fg=SUBTEXT,font=("Segoe UI",9)
                     ).grid(row=i,column=0,sticky="w",pady=4)
            tk.Entry(frm,textvariable=var,bg=SURFACE0,fg=FG,insertbackground=FG,relief=tk.FLAT,
                     font=("Segoe UI",10),highlightthickness=1,highlightcolor=ACCENT,
                     highlightbackground=SURFACE1).grid(row=i,column=1,sticky="ew",pady=4,padx=(10,0))
        def create():
            n=name_var.get().strip(); d=disp_var.get().strip()
            if not n: messagebox.showwarning("Missing","Short name is required.",parent=win); return
            if any(s["name"]==n for s in self.data.get("semesters",[])):
                messagebox.showwarning("Duplicate",f"Semester '{n}' already exists.",parent=win); return
            self.data.setdefault("semesters",[]).append(
                {"name":n,"display_name":d,"courses":[],"exams":[]})
            save_data(self.data, self.data_file)
            if self._current: self._panels[self._current].reload()
            win.destroy()
        tk.Button(win,text="Create",bg=ACCENT,fg=CRUST,font=("Segoe UI",9,"bold"),
                  relief=tk.FLAT,cursor="hand2",padx=10,pady=4,command=create).pack(pady=14)


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        DATA_FILE = sys.argv[1]
    root = tk.Tk()
    HubApp(root)
    root.mainloop()