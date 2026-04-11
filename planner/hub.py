"""planner/hub.py — HubApp: single-window host with overlay drawer.

Added: File menu (Export/Import semester as JSON, XLSX, CSV + template download).
Added: Actions menu with Reload Data.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from planner.constants import (
    BG, SURFACE0, SURFACE1, CRUST, MANTLE, FG, SUBTEXT, OVERLAY,
    ACCENT, GREEN, MAUVE, RED, YELLOW, TEAL,
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

        # Left: hamburger + brand
        left = tk.Frame(self._topbar, bg=CRUST)
        left.pack(side=tk.LEFT, fill=tk.Y)

        ham = tk.Button(
            left, text="☰", bg=CRUST, fg=FG,
            font=("Segoe UI", 16), relief=tk.FLAT, cursor="hand2",
            padx=14, pady=4, activebackground=SURFACE0,
            activeforeground=ACCENT, bd=0,
            command=self._toggle_drawer,
        )
        ham.pack(side=tk.LEFT, fill=tk.Y)

        # Thin accent divider after hamburger
        tk.Frame(left, bg=SURFACE1, width=1).pack(
            side=tk.LEFT, fill=tk.Y, pady=10)

        # Brand / logo text
        tk.Label(
            left, text="🎓  Academic Hub",
            bg=CRUST, fg=ACCENT,
            font=("Segoe UI", 10, "bold"),
            padx=12,
        ).pack(side=tk.LEFT, fill=tk.Y)

        # Another divider before menu buttons
        tk.Frame(left, bg=SURFACE1, width=1).pack(
            side=tk.LEFT, fill=tk.Y, pady=10)

        # ── Menu buttons (File, Actions) ──────────────────────────────────────
        menu_area = tk.Frame(self._topbar, bg=CRUST)
        menu_area.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0))

        self._file_btn = self._topbar_menu_btn(
            menu_area, "  File  ▾  ", self._show_file_menu)
        self._file_btn.pack(side=tk.LEFT, fill=tk.Y)

        self._actions_btn = self._topbar_menu_btn(
            menu_area, "  Actions  ▾  ", self._show_actions_menu, color=TEAL)
        self._actions_btn.pack(side=tk.LEFT, fill=tk.Y)

        # ── Right side: current panel breadcrumb + data-file chip ─────────────
        right = tk.Frame(self._topbar, bg=CRUST)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=12)

        # Data-file chip
        self._file_chip = tk.Label(
            right,
            text=f"  📄  {os.path.basename(self.data_file)}  ",
            bg=SURFACE0, fg=SUBTEXT,
            font=("Segoe UI", 8),
            relief=tk.FLAT, padx=6, pady=2,
            cursor="hand2",
        )
        self._file_chip.pack(side=tk.RIGHT, pady=12, padx=(4, 0))
        self._file_chip.bind("<Button-1>", lambda e: self.load_data_dialog())

        tk.Frame(right, bg=SURFACE1, width=1).pack(
            side=tk.RIGHT, fill=tk.Y, pady=10, padx=6)

        # Panel breadcrumb label
        self._title_lbl = tk.Label(
            right, text="",
            bg=CRUST, fg=SUBTEXT,
            font=("Segoe UI", 9),
        )
        self._title_lbl.pack(side=tk.RIGHT, fill=tk.Y)

    def _topbar_menu_btn(self, parent, text, cmd, color=FG):
        """Create a flat topbar menu button with hover highlight."""
        btn = tk.Button(
            parent, text=text, bg=CRUST, fg=color,
            font=("Segoe UI", 9, "bold"), relief=tk.FLAT, cursor="hand2",
            pady=0, activebackground=SURFACE0,
            activeforeground=color, bd=0,
            command=cmd,
        )
        btn.bind("<Enter>", lambda e: btn.configure(bg=SURFACE0))
        btn.bind("<Leave>", lambda e: btn.configure(bg=CRUST))
        return btn

    # ── File menu ─────────────────────────────────────────────────────────────
    def _show_file_menu(self):
        m = self._make_menu()

        def _sub():
            return self._make_menu(parent=m)

        exp = _sub()
        exp.add_command(label="As JSON…",  command=self.export_semester_json)
        exp.add_command(label="As XLSX…",  command=self.export_semester_xlsx)
        exp.add_command(label="As CSV…",   command=self.export_semester_csv)

        imp = _sub()
        imp.add_command(label="From JSON…",  command=self.import_semester_json)
        imp.add_command(label="From XLSX…",  command=self.import_semester_xlsx)
        imp.add_command(label="From CSV…",   command=self.import_semester_csv)

        m.add_cascade(label="Export Semester  ▶", menu=exp)
        m.add_cascade(label="Import Semester  ▶", menu=imp)
        m.add_separator()
        m.add_command(label="📥  Download XLSX Template…",
                      command=self.download_template)
        m.add_separator()
        m.add_command(label="📂  Load Data File…",  command=self.load_data_dialog)
        m.add_command(label="💾  Save Data",         command=self.save_data_dialog)
        m.add_command(label="💾  Save Data As…",     command=self.save_as_dialog)
        m.add_separator()
        m.add_command(label="➕  New Semester",       command=self.new_semester_dialog)

        self._popup_menu(m, self._file_btn)

    # ── Actions menu ──────────────────────────────────────────────────────────
    def _show_actions_menu(self):
        m = self._make_menu(accent=TEAL)

        m.add_command(label="🔄  Reload Data",
                      command=self.reload_data)
        m.add_separator()
        m.add_command(label="💾  Save Data",
                      command=self.save_data_dialog)
        m.add_command(label="➕  New Semester",
                      command=self.new_semester_dialog)

        self._popup_menu(m, self._actions_btn)

    def _make_menu(self, parent=None, accent=ACCENT):
        return tk.Menu(
            parent or self.root, tearoff=0,
            bg=SURFACE0, fg=FG,
            activebackground=accent, activeforeground=CRUST,
            font=("Segoe UI", 9),
            bd=0, relief=tk.FLAT,
        )

    def _popup_menu(self, menu, btn):
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    # ── Reload data ───────────────────────────────────────────────────────────
    def reload_data(self):
        """Re-read the current data file from disk and refresh the active panel."""
        try:
            self.data = load_data(self.data_file)
            if self._current:
                self._panels[self._current].reload()
            # Flash the file chip green briefly as visual confirmation
            self._file_chip.configure(bg="#1a3a1a", fg=GREEN)
            self._file_chip.after(
                600,
                lambda: self._file_chip.configure(bg=SURFACE0, fg=SUBTEXT),
            )
        except Exception as ex:
            messagebox.showerror("Reload Error", str(ex), parent=self.root)

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
        self._small_btn(util, "🔄  Reload Data",
                         self.reload_data).pack(fill=tk.X, pady=3)
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
            "home":         "Home",
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

    # ─────────────────────────────────────────────────────────────────────────
    # Data actions (load / save)
    # ─────────────────────────────────────────────────────────────────────────

    def load_data_dialog(self):
        path = filedialog.askopenfilename(
            title="Open data.json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")])
        if path:
            self.data_file = path
            self.data      = load_data(path)
            self._file_chip.configure(
                text=f"  📄  {os.path.basename(self.data_file)}  ")
            if self._current:
                self._panels[self._current].reload()

    def save_data_dialog(self):
        try:
            save_data(self.data, self.data_file)
            messagebox.showinfo("Saved",
                                f"Saved to:\n{self.data_file}",
                                parent=self.root)
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex), parent=self.root)

    def save_as_dialog(self):
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
                self._file_chip.configure(
                    text=f"  📄  {os.path.basename(self.data_file)}  ")
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

    # ─────────────────────────────────────────────────────────────────────────
    # Semester picker helper
    # ─────────────────────────────────────────────────────────────────────────

    def _pick_semester_dialog(self, title="Select Semester") -> dict | None:
        sems = self.data.get("semesters", [])
        if not sems:
            messagebox.showwarning("No Semesters",
                                   "No semesters in the current data file.",
                                   parent=self.root)
            return None
        if len(sems) == 1:
            return sems[0]

        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("340x170")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        result: list = [None]

        tk.Label(win, text=title, bg=BG, fg=FG,
                 font=("Segoe UI", 12, "bold")).pack(pady=(18, 10))

        var = tk.StringVar(value=sems[-1]["name"])
        cb  = ttk.Combobox(win, textvariable=var,
                           values=[s["name"] for s in sems],
                           state="readonly", font=("Segoe UI", 10), width=28)
        cb.pack(padx=30, fill=tk.X)

        def confirm():
            result[0] = next(
                (s for s in sems if s["name"] == var.get()), None)
            win.destroy()

        tk.Button(win, text="Continue", bg=ACCENT, fg=CRUST,
                  font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
                  cursor="hand2", padx=14, pady=5,
                  command=confirm).pack(pady=16)

        win.wait_window()
        return result[0]

    # ─────────────────────────────────────────────────────────────────────────
    # Export
    # ─────────────────────────────────────────────────────────────────────────

    def export_semester_json(self):
        sem = self._pick_semester_dialog("Export Semester — choose semester")
        if not sem:
            return
        path = filedialog.asksaveasfilename(
            title="Export Semester as JSON",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile=f"{sem['name']}.json",
        )
        if path:
            try:
                from planner.utils.export_import_utils import export_semester_json as _exp
                _exp(sem, path)
                messagebox.showinfo(
                    "Exported",
                    f"Semester '{sem['name']}' exported to:\n{path}",
                    parent=self.root)
            except Exception as ex:
                messagebox.showerror("Export Error", str(ex), parent=self.root)

    def export_semester_xlsx(self):
        sem = self._pick_semester_dialog("Export Semester — choose semester")
        if not sem:
            return
        path = filedialog.asksaveasfilename(
            title="Export Semester as XLSX",
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx"), ("All Files", "*.*")],
            initialfile=f"{sem['name']}.xlsx",
        )
        if path:
            try:
                from planner.utils.export_import_utils import export_semester_xlsx as _exp
                _exp(sem, path)
                messagebox.showinfo(
                    "Exported",
                    f"Semester '{sem['name']}' exported to:\n{path}",
                    parent=self.root)
            except Exception as ex:
                messagebox.showerror("Export Error", str(ex), parent=self.root)

    def export_semester_csv(self):
        sem = self._pick_semester_dialog("Export Semester — choose semester")
        if not sem:
            return
        path = filedialog.asksaveasfilename(
            title="Export Semester as CSV",
            defaultextension=".csv",
            filetypes=[("CSV File", "*.csv"), ("All Files", "*.*")],
            initialfile=f"{sem['name']}.csv",
        )
        if path:
            try:
                from planner.utils.export_import_utils import export_semester_csv as _exp
                _exp(sem, path)
                messagebox.showinfo(
                    "Exported",
                    f"Semester '{sem['name']}' exported to:\n{path}",
                    parent=self.root)
            except Exception as ex:
                messagebox.showerror("Export Error", str(ex), parent=self.root)

    # ─────────────────────────────────────────────────────────────────────────
    # Import
    # ─────────────────────────────────────────────────────────────────────────

    def import_semester_json(self):
        path = filedialog.askopenfilename(
            title="Import Semester from JSON",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        if path:
            try:
                from planner.utils.export_import_utils import import_semester_json as _imp
                self._merge_imported_semester(_imp(path))
            except Exception as ex:
                messagebox.showerror("Import Error", str(ex), parent=self.root)

    def import_semester_xlsx(self):
        path = filedialog.askopenfilename(
            title="Import Semester from XLSX",
            filetypes=[("Excel Workbook", "*.xlsx"), ("All Files", "*.*")],
        )
        if path:
            try:
                from planner.utils.export_import_utils import import_semester_xlsx as _imp
                self._merge_imported_semester(_imp(path))
            except Exception as ex:
                messagebox.showerror("Import Error", str(ex), parent=self.root)

    def import_semester_csv(self):
        path = filedialog.askopenfilename(
            title="Import Semester from CSV",
            filetypes=[("CSV File", "*.csv"), ("All Files", "*.*")],
        )
        if path:
            try:
                from planner.utils.export_import_utils import import_semester_csv as _imp
                self._merge_imported_semester(_imp(path))
            except Exception as ex:
                messagebox.showerror("Import Error", str(ex), parent=self.root)

    def _merge_imported_semester(self, sem: dict):
        existing       = self.data.get("semesters", [])
        existing_names = {s["name"] for s in existing}

        win = tk.Toplevel(self.root)
        win.title("Import Semester")
        win.geometry("400x230")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Import Semester",
                 bg=BG, fg=FG,
                 font=("Segoe UI", 13, "bold")).pack(pady=(16, 4))

        frm = tk.Frame(win, bg=BG)
        frm.pack(fill=tk.X, padx=30)
        frm.columnconfigure(1, weight=1)

        name_var = tk.StringVar(value=sem.get("name", "Imported"))
        disp_var = tk.StringVar(value=sem.get("display_name", "Imported Semester"))

        def _entry_row(r, label, var):
            tk.Label(frm, text=label, bg=BG, fg=SUBTEXT,
                     font=("Segoe UI", 9)).grid(
                row=r, column=0, sticky="w", pady=4)
            tk.Entry(frm, textvariable=var, bg=SURFACE0, fg=FG,
                     insertbackground=FG, relief=tk.FLAT,
                     font=("Segoe UI", 10), highlightthickness=1,
                     highlightcolor=ACCENT, highlightbackground=SURFACE1,
                     ).grid(row=r, column=1, sticky="ew", pady=4, padx=(10, 0))

        _entry_row(0, "Short name:",   name_var)
        _entry_row(1, "Display name:", disp_var)

        tk.Label(frm, text=f"  {len(sem.get('courses', []))} courses will be imported",
                 bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 8, "italic")).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        def do_import():
            n = name_var.get().strip()
            d = disp_var.get().strip()
            if not n:
                messagebox.showwarning("Missing",
                                       "Short name is required.", parent=win)
                return
            sem["name"]         = n
            sem["display_name"] = d

            if n in existing_names:
                if not messagebox.askyesno(
                    "Overwrite?",
                    f"Semester '{n}' already exists. Overwrite it?",
                    parent=win,
                ):
                    return
                for i, s in enumerate(self.data["semesters"]):
                    if s["name"] == n:
                        self.data["semesters"][i] = sem
                        break
            else:
                self.data.setdefault("semesters", []).append(sem)

            save_data(self.data, self.data_file)
            if self._current:
                self._panels[self._current].reload()
            win.destroy()
            messagebox.showinfo(
                "Imported",
                f"Semester '{n}' imported successfully.",
                parent=self.root)

        tk.Button(win, text="Import", bg=ACCENT, fg=CRUST,
                  font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
                  cursor="hand2", padx=14, pady=5,
                  command=do_import).pack(pady=14)

    # ─────────────────────────────────────────────────────────────────────────
    # Template
    # ─────────────────────────────────────────────────────────────────────────

    def download_template(self):
        path = filedialog.asksaveasfilename(
            title="Save XLSX Template",
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx"), ("All Files", "*.*")],
            initialfile="semester_template.xlsx",
        )
        if path:
            try:
                from planner.utils.export_import_utils import export_template_xlsx
                export_template_xlsx(path)
                messagebox.showinfo(
                    "Template Saved",
                    f"Template saved to:\n{path}\n\n"
                    "Edit the rows, then use File → Import Semester → From XLSX…",
                    parent=self.root)
            except Exception as ex:
                messagebox.showerror("Error", str(ex), parent=self.root)