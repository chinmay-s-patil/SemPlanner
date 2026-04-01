"""planner/utils/io_utils.py — Data file I/O + derived data helpers."""

import json
import os

DEFAULT_DATA_FILE = "data.json"

_FALLBACK = {
    "meta": {},
    "requirements": {},
    "semesters": [],
    "completed_courses": [],
}

# ── File I/O ─────────────────────────────────────────────────────────────────

def load_data(path=None):
    p = path or DEFAULT_DATA_FILE
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return dict(_FALLBACK)


def save_data(data, path=None):
    p = path or DEFAULT_DATA_FILE
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Derived helpers (pulled from data, not hardcoded) ─────────────────────────

def get_base_modules(data):
    """Ordered list of base module names from requirements, plus empty sentinel."""
    return list(data.get("requirements", {}).keys()) + [""]


def get_specific_modules(data):
    """Dict of {base_module: [specific_module_names]} derived from requirements."""
    out: dict = {}
    for base, cfg in data.get("requirements", {}).items():
        subs = list(cfg.get("subcategories", {}).keys())
        out[base] = subs if subs else [base]
    out[""] = [""]
    return out


def get_slot_types(data):
    return data.get("meta", {}).get(
        "slot_types",
        ["Lecture", "Tutorial", "Exercise", "Lab", "Help Session", "Other"],
    )


def get_days(data):
    return data.get("meta", {}).get(
        "days", ["Mon", "Tue", "Wed", "Thu", "Fri"]
    )


def get_day_full(data):
    return data.get("meta", {}).get(
        "day_full",
        {
            "Mon": "Monday",  "Tue": "Tuesday", "Wed": "Wednesday",
            "Thu": "Thursday","Fri": "Friday",  "Sat": "Saturday",
            "Sun": "Sunday",
        },
    )
