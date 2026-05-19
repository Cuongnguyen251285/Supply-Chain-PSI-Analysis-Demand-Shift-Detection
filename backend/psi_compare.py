import math
from typing import Dict, List, Tuple


def compare_psi(
    old_map: Dict,
    new_map: Dict,
    week_headers: List[str],
    start_week: str,
    threshold: float = 0.20,
) -> Tuple[List[Dict], List[str]]:
    try:
        start_idx = week_headers.index(start_week)
    except ValueError:
        start_idx = 0

    future_weeks = week_headers[start_idx:]
    all_keys = sorted(set(old_map) | set(new_map))
    results = []

    for key in all_keys:
        item_str, seg_type = key.split("|", 1)
        old = old_map.get(key)
        new = new_map.get(key)
        meta = new or old

        def _slice(d):
            w = d["weeks"][start_idx:] if d else []
            # pad/truncate to len(future_weeks)
            w = list(w) + [0] * max(0, len(future_weeks) - len(w))
            return w[:len(future_weeks)]

        old_f = _slice(old)
        new_f = _slice(new)

        old_total = sum(old_f)
        new_total = sum(new_f)
        delta_total = new_total - old_total

        if old is None:
            status, flag = "NEW", "NEW ITEM"
            pct_total = 1.0
        elif new is None:
            status, flag = "REMOVED", "REMOVED"
            pct_total = -1.0
        else:
            if old_total != 0:
                pct_total = delta_total / old_total
            else:
                pct_total = 1.0 if new_total > 0 else 0.0

            # Clamp pct_total to finite
            if not math.isfinite(pct_total):
                pct_total = 0.0

            if pct_total >= threshold:
                status, flag = "SPIKE", "DEMAND UP >20%"
            elif pct_total <= -threshold:
                status, flag = "DROP", "DEMAND DOWN >20%"
            elif delta_total != 0:
                status, flag = "CHANGED", ""
            else:
                status, flag = "SAME", ""

        weeks = []
        for i, w in enumerate(future_weeks):
            o, n = old_f[i], new_f[i]
            d = n - o
            if o != 0:
                p = d / o
            else:
                p = 1.0 if n > 0 else 0.0
            if not math.isfinite(p):
                p = 0.0
            weeks.append({"week": w, "old": o, "new": n, "delta": d, "pct": p})

        results.append({
            "item": item_str,
            "vendor": meta.get("vendor", ""),
            "desc": meta.get("desc", ""),
            "seg_type": seg_type,
            "status": status,
            "flag": flag,
            "old_total": old_total,
            "new_total": new_total,
            "delta_total": delta_total,
            "pct_total": pct_total,
            "moq": meta.get("moq", 0),
            "lt": meta.get("lt", 0),
            "ss": meta.get("ss", 0),
            "ending": meta.get("ending", 0),
            "weeks": weeks,
        })

    return results, future_weeks
