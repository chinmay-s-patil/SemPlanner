"""planner/utils/math_utils.py — Time parsing, colour math, and column layout."""

from planner.constants import BG


# ── Time ─────────────────────────────────────────────────────────────────────

def parse_time(t):
    """'16.30' or '16:30' → 16.5 (float hours).  Returns None on error."""
    try:
        parts = str(t).replace(":", ".").split(".")
        return int(parts[0]) + (int(parts[1]) if len(parts) > 1 else 0) / 60
    except Exception:
        return None


# ── Colour helpers ────────────────────────────────────────────────────────────

def hex_darken(hx: str, f: float = 0.6) -> str:
    hx = hx.lstrip("#")
    r, g, b = (int(hx[i:i+2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(int(r * f), int(g * f), int(b * f))


def hex_blend(hx: str, bg_col: str = BG, a: float = 0.22) -> str:
    hx     = hx.lstrip("#")
    bg_col = bg_col.lstrip("#")
    r1, g1, b1 = (int(hx[i:i+2], 16) for i in (0, 2, 4))
    r2, g2, b2 = (int(bg_col[i:i+2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(
        int(r1 * a + r2 * (1 - a)),
        int(g1 * a + g2 * (1 - a)),
        int(b1 * a + b2 * (1 - a)),
    )


# ── Column-overlap layout ─────────────────────────────────────────────────────

def assign_columns(events):
    """
    Given a list of (start, end, data) tuples, return
    [(data, col_index, num_cols)] with overlapping events spread across columns.
    """
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
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for i in range(n):
        for j in range(i + 1, n):
            if events[i][0] < events[j][1] and events[j][0] < events[i][1]:
                union(i, j)

    gm: dict = {}
    for i in range(n):
        g = find(i)
        gm[g] = max(gm.get(g, 0), col[i])

    return [(events[i][2], col[i], gm[find(i)] + 1) for i in range(n)]
