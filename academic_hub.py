"""academic_hub.py — SemCal: Academic Planner

Entry point.  Launch with:
    python3 academic_hub.py [path/to/data.json]
"""

import sys
import tkinter as tk

from planner.hub import HubApp

if __name__ == "__main__":
    data_file = sys.argv[1] if len(sys.argv) > 1 else "data.json"
    root = tk.Tk()
    HubApp(root, data_file=data_file)
    root.mainloop()
