import math
from datetime import datetime, timedelta
from typing import Dict, List
from collections import defaultdict


def compute_window_3w(
    old_map: Dict,
    new_map: Dict,
    week_headers: List[str],
    start_week: str,
    threshold: float = 0.10,
) -> List[Dict]:
    try:
        start_idx = week_headers.index(start_week)
    except ValueError:
        start_idx = 0

    future_weeks = week_headers[start_idx:]
    n_weeks = len(future_weeks)
    week_idx_map = {w: i for i, w in enumerate(week_headers)}
    today = datetime.today()

    all_keys = sorted(set(old_map) | set(new_map))
    alerts = []

    for key in all_keys:
        item_str, seg_type = key.split("|", 1)
        old = old_map.get(key)
        new = new_map.get(key)
        meta = new or old

        def _get(d, gi):
            if d is None:
                return 0.0
            w = d["weeks"]
            return w[gi] if gi < len(w) else 0.0

        triggered = []
        for wi in range(n_weeks - 2):
            g = start_idx + wi
            o_sum = sum(_get(old, g + k) for k in range(3))
            n_sum = sum(_get(new, g + k) for k in range(3))
            d = n_sum - o_sum

            if o_sum == 0 and n_sum > 0:
                direction, pct = "NEW DEMAND", 1.0
            elif o_sum > 0 and n_sum == 0:
                direction, pct = "ZERO OUT", -1.0
            elif o_sum == 0:
                continue
            else:
                pct = d / o_sum
                if not math.isfinite(pct):
                    pct = 0.0
                if pct >= threshold:
                    direction = "INCREASE"
                elif pct <= -threshold:
                    direction = "DECREASE"
                else:
                    continue

            triggered.append({
                "wIdx": wi,
                "direction": direction,
                "weeks": future_weeks[wi:wi + 3],
            })

        # Merge zones: same direction, gap <= 2
        zones = []
        for tw in triggered:
            merged = False
            for zone in zones:
                if zone["direction"] == tw["direction"]:
                    if tw["wIdx"] - zone["wIndices"][-1] <= 2:
                        zone["wIndices"].append(tw["wIdx"])
                        zone["week_set"].update(tw["weeks"])
                        merged = True
                        break
            if not merged:
                zones.append({
                    "direction": tw["direction"],
                    "wIndices": [tw["wIdx"]],
                    "week_set": set(tw["weeks"]),
                })

        moq = int(meta.get("moq", 0) or 1)
        lt = int(meta.get("lt", 0) or 0)

        for zone in zones:
            zone_weeks = sorted(zone["week_set"], key=lambda w: week_idx_map.get(w, 9999))
            zone_old = sum(_get(old, week_idx_map[w]) for w in zone_weeks if w in week_idx_map)
            zone_new = sum(_get(new, week_idx_map[w]) for w in zone_weeks if w in week_idx_map)
            zone_delta = zone_new - zone_old

            if zone_old != 0:
                zone_pct = zone_delta / zone_old
            else:
                zone_pct = 1.0 if zone_new > 0 else 0.0
            if not math.isfinite(zone_pct):
                zone_pct = 0.0

            zone_str = f"{zone_weeks[0]}...{zone_weeks[-1]}" if len(zone_weeks) > 1 else zone_weeks[0]
            direction = zone["direction"]

            units = (round(abs(zone_delta) / moq) * moq) if moq > 0 else int(abs(zone_delta))
            order_by = (today + timedelta(days=lt)).strftime("%d/%m/%Y")

            if direction in ("INCREASE", "NEW DEMAND"):
                action = f"Tang dat hang ~{int(units):,} don vi (round MOQ={moq}). LT={lt} ngay, can dat truoc {order_by}"
            else:
                action = f"Giam/hoan ~{int(units):,} don vi. Kiem tra inventory."

            alerts.append({
                "item": item_str,
                "desc": meta.get("desc", ""),
                "vendor": meta.get("vendor", ""),
                "seg_type": seg_type,
                "direction": direction,
                "zone_window": zone_str,
                "n_wks": len(zone_weeks),
                "old_total": zone_old,
                "new_total": zone_new,
                "delta": zone_delta,
                "pct": zone_pct,
                "lt": lt,
                "moq": moq,
                "ss": meta.get("ss", 0),
                "ending": meta.get("ending", 0),
                "action": action,
            })

    alerts.sort(key=lambda x: abs(x["delta"]), reverse=True)
    return alerts
