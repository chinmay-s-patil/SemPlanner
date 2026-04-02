"""planner/hub.py — HubApp: single-window host with overlay drawer.

Added: save_data_dialog / Save As button in drawer and utility area.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox

from planner.constants import (
    BG, SURFACE0, SURFACE1, CRUST, MANTLE, FG, SUBTEXT, OVERLAY,
    ACCENT, GREEN, MAUVE,
)
from planner.utils.io_utils import load_data, save_data
from planner.panels.home         import HomePanel
from planner.panels.timetable    import TimetablePanel
from planner.panels.requirements import RequirementsPanel
from planner.panels.semester     import SemesterPanel


class HubApp:
    DRAWER_W = 240

    def __init__(self, root: tk.Tk, data_file: str = "data.json"):
        self.root = root
        self.root.title("Academic Hub")
        self.root.geometry("1300x820")
        self.root.minsize(900, 600)
        self.root.configure(bg=BG)

        self.data_file = data_file
        self.data      = load_data(data_file)

        self._current       = None
        self._drawer_open   = False
        self._panels: dict  = {}
        self._blur_photo    = None

        self._build_topbar()
        self._build_body()
        self._build_drawer()
        self.show_panel("home")

    # ── Top bar ───────────────────────────────────────────────────────────────
    def _build_topbar(self):
        self._topbar = tk.Frame(self.root, bg=CRUST, height=48)
        self._topbar.pack(fill=tk.X)
        self._topbar.pack_propagate(False)

        ham = tk.Button(
            self._topbar, text="☰", bg=CRUST, fg=FG,
            font=("Segoe UI", 16), relief=tk.FLAT, cursor="hand2",
            padx=14, pady=4, activebackground=SURFACE0,
            activeforeground=ACCENT, bd=0,
            command=self._toggle_drawer,
        )
        ham.pack(side=tk.LEFT)

        self._title_lbl = tk.Label(
            self._topbar, text="Academic Hub",
            bg=CRUST, fg=FG, font=("Segoe UI", 13, "bold"))
        self._title_lbl.pack(side=tk.LEFT, padx=8)

    # ── Body ──────────────────────────────────────────────────────────────────
    def _build_body(self):
        self._body = tk.Frame(self.root, bg=BG)
        self._body.pack(fill=tk.BOTH, expand=True)

        self._panels_host = tk.Frame(self._body, bg=BG)
        self._panels_host.place(x=0, y=0, relwidth=1, relheight=1)

        self._panels = {
            "home":         HomePanel(self._panels_host, self),
            "timetable":    TimetablePanel(self._panels_host, self),
            "requirements": RequirementsPanel(self._panels_host, self),
            "semester":     SemesterPanel(self._panels_host, self),
        }

        self._backdrop = tk.Canvas(
            self._body, highlightthickness=0, cursor="arrow")
        self._backdrop.bind("<Button-1>", lambda e: self._close_drawer())

    # ── Drawer ────────────────────────────────────────────────────────────────
    def _build_drawer(self):
        self._drawer = tk.Frame(self._body, bg=CRUST, width=self.DRAWER_W)

        logo = tk.Frame(self._drawer, bg=MANTLE, height=60)
        logo.pack(fill=tk.X)
        logo.pack_propagate(False)
        tk.Label(logo, text="  🎓  Academic Hub", bg=MANTLE, fg=FG,
                 font=("Segoe UI", 12, "bold")).pack(
            side=tk.LEFT, padx=10, pady=16)

        nav_items = [
            ("🏠  Home",             "home",         FG),
            ("📅  Timetable",        "timetable",    ACCENT),
            ("📋  Requirements",     "requirements", GREEN),
            ("📊  Semester Credits", "semester",     MAUVE),
        ]
        nav_container = tk.Frame(self._drawer, bg=CRUST)
        nav_container.pack(fill=tk.X, pady=(8, 0))

        self._nav_btns: dict = {}
        for label, panel_id, color in nav_items:
            btn = self._nav_btn(nav_container, label, color, panel_id)
            self._nav_btns[panel_id] = btn

        tk.Frame(self._drawer, bg=SURFACE1, height=1).pack(
            fill=tk.X, padx=16, pady=12)

        util = tk.Frame(self._drawer, bg=CRUST)
        util.pack(fill=tk.X, padx=12)
        self._small_btn(util, "📂  Load Data",
                         self.load_data_dialog).pack(fill=tk.X, pady=3)
        self._small_btn(util, "💾  Save Data",
                         self.save_data_dialog).pack(fill=tk.X, pady=3)
        self._small_btn(util, "💾  Save As…",
                         self.save_as_dialog).pack(fill=tk.X, pady=3)
        self._small_btn(util, "➕  New Semester",
                         self.new_semester_dialog).pack(fill=tk.X, pady=3)

        tk.Label(self._drawer,
                 text=f"  {os.path.basename(self.data_file)}",
                 bg=CRUST, fg=OVERLAY,
                 font=("Segoe UI", 8)).pack(
            side=tk.BOTTOM, anchor="w", padx=10, pady=8)

    def _nav_btn(self, parent, label, color, panel_id):
        ITEM_H = 46
        f = tk.Frame(parent, bg=CRUST, height=ITEM_H, cursor="hand2")
        f.pack(fill=tk.X)
        f.pack_propagate(False)

        accent_bar = tk.Frame(f, bg=CRUST, width=4)
        accent_bar.pack(side=tk.LEFT, fill=tk.Y)

        lbl = tk.Label(f, text=f"  {label}", bg=CRUST, fg=FG,
                       font=("Segoe UI", 10), anchor="w", cursor="hand2")
        lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def on_enter(_):
            if self._current != panel_id:
                f.configure(bg=SURFACE0)
                lbl.configure(bg=SURFACE0)

        def on_leave(_):
            if self._current != panel_id:
                f.configure(bg=CRUST)
                lbl.configure(bg=CRUST)

        def on_click(_):
            self.show_panel(panel_id)

        for widget in (f, lbl):
            widget.bind("<Enter>",    on_enter)
            widget.bind("<Leave>",    on_leave)
            widget.bind("<Button-1>", on_click)

        f._accent_bar = accent_bar
        f._lbl        = lbl
        f._color      = color
        return f

    def _small_btn(self, parent, text, cmd):
        return tk.Button(
            parent, text=text, bg=SURFACE0, fg=SUBTEXT,
            font=("Segoe UI", 9), relief=tk.FLAT, cursor="hand2",
            padx=10, pady=6, anchor="w",
            activebackground=SURFACE1, activeforeground=FG,
            bd=0, command=cmd)

    # ── Panel switching ───────────────────────────────────────────────────────
    def show_panel(self, name: str):
        for panel in self._panels.values():
            panel.frame.pack_forget()

        self._current = name
        panel = self._panels[name]
        panel.frame.pack(in_=self._panels_host, fill=tk.BOTH, expand=True)
        panel.reload()

        titles = {
            "home":         "Academic Hub",
            "timetable":    "📅  Timetable",
            "requirements": "📋  Requirements",
            "semester":     "📊  Semester Credits",
        }
        self._title_lbl.configure(text=titles.get(name, name))

        for pid, btn in self._nav_btns.items():
            if pid == name:
                btn.configure(bg=SURFACE1)
                btn._lbl.configure(bg=SURFACE1, fg=btn._color)
                btn._accent_bar.configure(bg=btn._color)
            else:
                btn.configure(bg=CRUST)
                btn._lbl.configure(bg=CRUST, fg=FG)
                btn._accent_bar.configure(bg=CRUST)

        self._close_drawer()

    # ── Drawer open / close ───────────────────────────────────────────────────
    def _toggle_drawer(self):
        if self._drawer_open:
            self._close_drawer()
        else:
            self._open_drawer()

    def _open_drawer(self):
        if self._drawer_open:
            return

        self.root.update_idletasks()
        self._blur_photo = None
        try:
            from PIL import ImageGrab, ImageFilter, ImageTk

            x = self._body.winfo_rootx()
            y = self._body.winfo_rooty()
            w = self._body.winfo_width()
            h = self._body.winfo_height()

            img     = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            blurred = img.filter(ImageFilter.GaussianBlur(14))
            photo   = ImageTk.PhotoImage(blurred)
            self._blur_photo = photo
        except Exception:
            pass

        self._backdrop.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lift(self._backdrop)
        self._backdrop.update_idletasks()

        bw = self._backdrop.winfo_width()
        bh = self._backdrop.winfo_height()
        self._backdrop.delete("all")

        if self._blur_photo:
            self._backdrop.create_image(0, 0, image=self._blur_photo, anchor="nw")
            self._backdrop.create_rectangle(
                0, 0, bw, bh, fill="#0D0D1A", stipple="gray25", outline="")
        else:
            self._backdrop.configure(bg="#0D0D1A")
            self._backdrop.create_rectangle(
                0, 0, bw, bh, fill="#0D0D1A", stipple="gray50", outline="")

        self._drawer.place(x=0, y=0, width=self.DRAWER_W, relheight=1)
        self._drawer.lift()
        self._drawer_open = True

    def _close_drawer(self):
        if not self._drawer_open:
            return
        self._drawer.place_forget()
        self._backdrop.place_forget()
        self._blur_photo = None
        self._drawer_open = False

    # ── Data actions ──────────────────────────────────────────────────────────
    def load_data_dialog(self):
        path = filedialog.askopenfilename(
            title="Open data.json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")])
        if path:
            self.data_file = path
            self.data      = load_data(path)
            if self._current:
                self._panels[self._current].reload()

    def save_data_dialog(self):
        """Save to current file immediately."""
        try:
            save_data(self.data, self.data_file)
            messagebox.showinfo("Saved",
                                f"Saved to:\n{self.data_file}",
                                parent=self.root)
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex), parent=self.root)

    def save_as_dialog(self):
        """Save to a new file location."""
        path = filedialog.asksaveasfilename(
            title="Save data as…",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile=os.path.basename(self.data_file),
        )
        if path:
            try:
                save_data(self.data, path)
                self.data_file = path
                messagebox.showinfo("Saved",
                                    f"Saved to:\n{path}",
                                    parent=self.root)
            except Exception as ex:
                messagebox.showerror("Save Error", str(ex), parent=self.root)

    def new_semester_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("New Semester")
        win.geometry("360x200")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="New Semester", bg=BG, fg=FG,
                 font=("Segoe UI", 13, "bold")).pack(pady=(18, 6))
        frm = tk.Frame(win, bg=BG)
        frm.pack(fill=tk.X, padx=30)
        frm.columnconfigure(1, weight=1)

        name_var = tk.StringVar(value="WiSe26")
        disp_var = tk.StringVar(value="Winter Semester 2026/27")
        for i, (lbl, var) in enumerate([
            ("Short name:",   name_var),
            ("Display name:", disp_var),
        ]):
            tk.Label(frm, text=lbl, bg=BG, fg=SUBTEXT,
                     font=("Segoe UI", 9)).grid(
                row=i, column=0, sticky="w", pady=4)
            tk.Entry(frm, textvariable=var, bg=SURFACE0, fg=FG,
                     insertbackground=FG, relief=tk.FLAT,
                     font=("Segoe UI", 10), highlightthickness=1,
                     highlightcolor=ACCENT, highlightbackground=SURFACE1,
                     ).grid(row=i, column=1, sticky="ew",
                            pady=4, padx=(10, 0))

        def create():
            n = name_var.get().strip()
            d = disp_var.get().strip()
            if not n:
                messagebox.showwarning("Missing",
                                       "Short name is required.", parent=win)
                return
            if any(s["name"] == n
                   for s in self.data.get("semesters", [])):
                messagebox.showwarning(
                    "Duplicate",
                    f"Semester '{n}' already exists.", parent=win)
                return
            self.data.setdefault("semesters", []).append(
                {"name": n, "display_name": d, "courses": [], "exams": []})
            save_data(self.data, self.data_file)
            if self._current:
                self._panels[self._current].reload()
            win.destroy()

        tk.Button(win, text="Create", bg=ACCENT, fg=CRUST,
                  font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
                  cursor="hand2", padx=10, pady=4,
                  command=create).pack(pady=14)