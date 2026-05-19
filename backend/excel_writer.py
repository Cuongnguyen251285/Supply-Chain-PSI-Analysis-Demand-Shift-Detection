import math
from typing import List, Dict

import xlsxwriter

# ── Colour palette ──────────────────────────────────────────────────────────
C_DARK_BLUE  = "#1F4E78"
C_GREEN      = "#548235"
C_RED        = "#C00000"
C_ORANGE     = "#ED7D31"
C_GRAY       = "#7F7F7F"
C_BLUE       = "#2E75B6"
C_YELLOW     = "#FFC000"
C_LT_BLUE    = "#BDD7EE"
C_WHITE      = "#FFFFFF"
C_ZEBRA      = "#F8F9FB"

# Heatmap palette to match requested styles (positive = red/pink, negative = yellow/orange)
C_HEAT_P_DARK    = "#FF5B62" # Large positive >= 30%
C_HEAT_P_MEDIUM  = "#FF8F95" # Medium positive >= 15%
C_HEAT_P_LIGHT   = "#FFC7CE" # Small positive >= 8%
C_HEAT_P_MICRO   = "#FFEBEE" # Micro positive > 0%

C_HEAT_N_EXTREME = "#ED7D31" # Extreme negative <= -50%
C_HEAT_N_DARK    = "#F4B084" # Large negative <= -25%
C_HEAT_N_MEDIUM  = "#FFE699" # Medium negative <= -10%
C_HEAT_N_LIGHT   = "#FFF2CC" # Small negative < 0%

C_FONT_P_DARK    = "#FFFFFF"
C_FONT_P_MEDIUM  = "#FFFFFF"
C_FONT_P_LIGHT   = "#9C0006" # Dark red text for standard light red fill
C_FONT_P_MICRO   = "#9C0006"

C_FONT_N_EXTREME = "#FFFFFF"
C_FONT_N_DARK    = "#000000"
C_FONT_N_MEDIUM  = "#000000"
C_FONT_N_LIGHT   = "#000000"

def _heat_fill_colors(pct: float):
    """Return (bg_color, font_color) based on pct."""
    if not math.isfinite(pct):
        return None, "#000000"
    if pct == 0.0:
        return None, "#000000"
        
    if pct > 0:
        if pct >= 0.3:
            return C_HEAT_P_DARK, C_FONT_P_DARK
        elif pct >= 0.15:
            return C_HEAT_P_MEDIUM, C_FONT_P_MEDIUM
        elif pct >= 0.08:
            return C_HEAT_P_LIGHT, C_FONT_P_LIGHT
        else:
            return C_HEAT_P_MICRO, C_FONT_P_MICRO
    else:
        if pct <= -0.5:
            return C_HEAT_N_EXTREME, C_FONT_N_EXTREME
        elif pct <= -0.25:
            return C_HEAT_N_DARK, C_FONT_N_DARK
        elif pct <= -0.1:
            return C_HEAT_N_MEDIUM, C_FONT_N_MEDIUM
        else:
            return C_HEAT_N_LIGHT, C_FONT_N_LIGHT

def get_format(wb, bg_color=None, font_color="#000000", bold=False, align="left", num_fmt=None, bottom_border=False):
    key = (bg_color, font_color, bold, align, num_fmt, bottom_border)
    if not hasattr(wb, '_format_cache'):
        wb._format_cache = {}
    if key not in wb._format_cache:
        props = {'font_color': font_color, 'bold': bold, 'font_size': 10, 'valign': 'vcenter'}
        if bg_color:
            props['bg_color'] = bg_color
            # Xlsxwriter does not require pattern=1 if bg_color is provided
        if "center" in align:
            props['align'] = 'center'
        elif "right" in align:
            props['align'] = 'right'
        else:
            props['align'] = 'left'
            
        if "wrap" in align:
            props['text_wrap'] = True
            
        if num_fmt:
            props['num_format'] = num_fmt
            
        if bottom_border:
            props['bottom'] = 2
            props['bottom_color'] = C_DARK_BLUE
            
        wb._format_cache[key] = wb.add_format(props)
    return wb._format_cache[key]

# ── Main entry point ─────────────────────────────────────────────────────────
def write_excel_output(
    path: str,
    compare_results: List[Dict],
    window_results: List[Dict],
    future_weeks: List[str],
    start_week: str,
    old_label: str,
    new_label: str,
):
    wb = xlsxwriter.Workbook(path)
    _write_compare_sheet(wb, compare_results, future_weeks, old_label, new_label)
    _write_window_sheet(wb, window_results, start_week)
    wb.close()

# ── PSI_Compare sheet ─────────────────────────────────────────────────────────
def _write_compare_sheet(
    wb: xlsxwriter.Workbook,
    results: List[Dict],
    future_weeks: List[str],
    old_label: str,
    new_label: str,
):
    ws = wb.add_worksheet("PSI_Compare")

    n_weeks = len(future_weeks)
    first_week = future_weeks[0] if future_weeks else ""

    FIXED_COLS = 12
    total_cols = FIXED_COLS + n_weeks

    # Row 0: Title
    fmt_title = wb.add_format({'bg_color': C_DARK_BLUE, 'font_color': C_WHITE, 'bold': True, 'size': 14, 'align': 'center', 'valign': 'vcenter'})
    title = f"PSI COMPARE: {old_label} vs {new_label} | From {first_week}"
    if total_cols > 1:
        ws.merge_range(0, 0, 0, min(total_cols - 1, 25), title, fmt_title)
    else:
        ws.write(0, 0, title, fmt_title)
    ws.set_row(0, 30)

    # Rows 1-4: KPI cards
    demand_results = [r for r in results if r["seg_type"] == "Demand"]
    kpi_data = [
        ("NEW ITEMS",      sum(1 for r in demand_results if r["status"] == "NEW"),      C_GREEN),
        ("REMOVED",        sum(1 for r in demand_results if r["status"] == "REMOVED"),  C_GRAY),
        ("DEMAND UP >20%", sum(1 for r in demand_results if r["status"] == "SPIKE"),    C_RED),
        ("DEMAND DOWN >20%", sum(1 for r in demand_results if r["status"] == "DROP"),   C_ORANGE),
    ]
    for idx, (label, count, color) in enumerate(kpi_data):
        row = 1 + idx
        ws.set_row(row, 22)
        fmt_lbl = wb.add_format({'bg_color': color, 'font_color': C_WHITE, 'bold': True, 'size': 10, 'align': 'left', 'valign': 'vcenter'})
        ws.merge_range(row, 0, row, 1, label, fmt_lbl)
        fmt_cnt = wb.add_format({'bg_color': color, 'font_color': C_WHITE, 'bold': True, 'size': 12, 'align': 'center', 'valign': 'vcenter'})
        ws.write(row, 2, count, fmt_cnt)

    # Row 5: spacer
    ws.set_row(5, 8)

    # Row 6: Header
    HDR_ROW = 6
    headers = ["#", "Item", "Vendor", "Description", "Type", "Metric",
               "Status", "Total OLD", "Total NEW", "Total Δ", "Total %Δ", "Flag"]
    headers += future_weeks

    ws.set_row(HDR_ROW, 30)
    fmt_hdr = wb.add_format({'bg_color': C_DARK_BLUE, 'font_color': C_WHITE, 'bold': True, 'size': 10, 'align': 'center', 'valign': 'vcenter'})
    for ci, h in enumerate(headers):
        ws.write(HDR_ROW, ci, h, fmt_hdr)

    # Column widths
    col_widths = {
        0: 6,   # #
        1: 14,  # Item
        2: 20,  # Vendor
        3: 30,  # Description
        4: 14,  # Type
        5: 10,  # Metric
        6: 10,  # Status
        7: 12,  # Total OLD
        8: 12,  # Total NEW
        9: 12, # Total Δ
        10: 10, # Total %Δ
        11: 18, # Flag
    }
    for col_i in range(FIXED_COLS, total_cols):
        col_widths[col_i] = 9
    for col_i, width in col_widths.items():
        ws.set_column(col_i, col_i, width)

    # Data rows
    from collections import OrderedDict
    groups: OrderedDict[str, List[Dict]] = OrderedDict()
    for r in results:
        k = r["item"]
        if k not in groups:
            groups[k] = []
        groups[k].append(r)

    for item_key in groups:
        groups[item_key].sort(key=lambda x: (0 if x["seg_type"] == "Demand" else 1))

    current_row = HDR_ROW + 1
    stt = 0

    STATUS_COLORS = {
        "NEW":     (C_GREEN,  C_WHITE),
        "REMOVED": (C_GRAY,   C_WHITE),
        "SPIKE":   (C_RED,    C_WHITE),
        "DROP":    (C_ORANGE, C_WHITE),
    }

    zebra = False
    for item_key, item_rows in groups.items():
        zebra = not zebra
        zebra_fill = C_ZEBRA if zebra else None

        for seg_idx, r in enumerate(item_rows):
            stt += 1
            seg_type = r["seg_type"]
            is_demand = (seg_type == "Demand")
            weeks_data = r["weeks"]

            status = r["status"]
            sc = STATUS_COLORS.get(status)

            is_last_seg = (seg_idx == len(item_rows) - 1)

            def _write_meta(row_idx, metric_val, is_pct_row=False):
                # Apply bottom border to all cells in the last row of the group
                apply_bottom = (is_last_seg and is_pct_row)
                
                # Col 0: stt
                ws.write(row_idx, 0, stt, get_format(wb, bg_color=zebra_fill, align="center", bottom_border=apply_bottom))
                # Col 1: item
                ws.write(row_idx, 1, r["item"], get_format(wb, bg_color=zebra_fill, align="left", bottom_border=apply_bottom))
                # Col 2: vendor
                ws.write(row_idx, 2, r["vendor"], get_format(wb, bg_color=zebra_fill, align="left", bottom_border=apply_bottom))
                # Col 3: desc
                ws.write(row_idx, 3, r["desc"], get_format(wb, bg_color=zebra_fill, align="left", bottom_border=apply_bottom))
                # Col 4: seg_type
                ws.write(row_idx, 4, seg_type, get_format(wb, bg_color=zebra_fill, align="center", bottom_border=apply_bottom))
                # Col 5: Metric
                ws.write(row_idx, 5, metric_val, get_format(wb, bg_color=zebra_fill, align="center", bold=True, bottom_border=apply_bottom))
                
                # Col 6: Status
                if sc:
                    ws.write(row_idx, 6, status, get_format(wb, bg_color=sc[0], font_color=sc[1], bold=True, align="center", bottom_border=apply_bottom))
                else:
                    ws.write(row_idx, 6, status, get_format(wb, bg_color=zebra_fill, align="center", bottom_border=apply_bottom))

                # Col 7: Total OLD
                ws.write(row_idx, 7, r["old_total"] if r["old_total"] else "", get_format(wb, bg_color=zebra_fill, align="right", num_fmt="#,##0;(#,##0);-", bottom_border=apply_bottom))
                # Col 8: Total NEW
                ws.write(row_idx, 8, r["new_total"] if r["new_total"] else "", get_format(wb, bg_color=zebra_fill, align="right", num_fmt="#,##0;(#,##0);-", bottom_border=apply_bottom))
                # Col 9: Total Δ
                dt = r["delta_total"]
                ws.write(row_idx, 9, dt if dt != 0 else "", get_format(wb, bg_color=zebra_fill, align="right", num_fmt="+#,##0;-#,##0;-", bold=True, bottom_border=apply_bottom))
                # Col 10: Total %Δ
                pt = r["pct_total"]
                ws.write(row_idx, 10, pt if pt != 0 else "", get_format(wb, bg_color=zebra_fill, align="right", num_fmt="+0.0%;-0.0%;-", bold=True, bottom_border=apply_bottom))

                # Col 11: Flag
                if is_demand and r["flag"]:
                    if sc:
                        ws.write(row_idx, 11, r["flag"], get_format(wb, bg_color=sc[0], font_color=sc[1], bold=True, align="center", bottom_border=apply_bottom))
                    else:
                        ws.write(row_idx, 11, r["flag"], get_format(wb, bg_color=zebra_fill, align="center", bold=True, bottom_border=apply_bottom))
                else:
                    ws.write(row_idx, 11, "", get_format(wb, bg_color=zebra_fill, align="center", bottom_border=apply_bottom))

            # OLD row
            old_row = current_row
            _write_meta(old_row, old_label)
            for wi, wd in enumerate(weeks_data):
                ws.write(old_row, FIXED_COLS + wi, wd["old"] if wd["old"] != 0 else "", get_format(wb, bg_color=zebra_fill, align="right", num_fmt="#,##0;(#,##0);-"))
            current_row += 1

            # NEW row
            new_row = current_row
            _write_meta(new_row, new_label)
            for wi, wd in enumerate(weeks_data):
                ws.write(new_row, FIXED_COLS + wi, wd["new"] if wd["new"] != 0 else "", get_format(wb, bg_color=zebra_fill, align="right", num_fmt="#,##0;(#,##0);-"))
            current_row += 1

            # DELTA row
            delta_row = current_row
            _write_meta(delta_row, "Δ")
            for wi, wd in enumerate(weeks_data):
                d = wd["delta"]
                p = wd["pct"]
                o = wd["old"]
                n = wd["new"]
                
                c_val = d if (o != 0 or n != 0) else ""
                bg, fc = _heat_fill_colors(p)
                if c_val == "":
                    bg = None
                    fc = "#000000"
                fill_color = bg if bg else zebra_fill
                
                ws.write(delta_row, FIXED_COLS + wi, c_val, get_format(wb, bg_color=fill_color, font_color=fc, bold=True, align="right", num_fmt="+#,##0;-#,##0;-"))
            current_row += 1

            # PCT row
            pct_row = current_row
            _write_meta(pct_row, "%Δ", is_pct_row=True)
            for wi, wd in enumerate(weeks_data):
                p = wd["pct"]
                o = wd["old"]
                n = wd["new"]
                
                c_val = p if (o != 0 or n != 0) else ""
                bg, fc = _heat_fill_colors(p)
                if c_val == "":
                    bg = None
                    fc = "#000000"
                fill_color = bg if bg else zebra_fill
                
                apply_bottom = (is_last_seg)
                ws.write(pct_row, FIXED_COLS + wi, c_val, get_format(wb, bg_color=fill_color, font_color=fc, bold=True, align="right", num_fmt="+0.0%;-0.0%;-", bottom_border=apply_bottom))
            current_row += 1

    # AutoFilter
    ws.autofilter(HDR_ROW, 0, current_row - 1, total_cols - 1)

    # Freeze panes
    ws.freeze_panes(HDR_ROW + 1, 6)


# ── Window_3W sheet ───────────────────────────────────────────────────────────
def _write_window_sheet(wb: xlsxwriter.Workbook, alerts: List[Dict], start_week: str):
    ws = wb.add_worksheet("Window_3W")

    COLS = ["#", "Item", "Description", "Vendor", "Type", "Direction",
            "Zone Window", "# Wks", "OLD Total", "NEW Total", "Δ", "%Δ",
            "Lead Time", "MOQ", "SS Stock", "Ending Stock", "Action"]
    N_COLS = len(COLS)

    # Row 0: Title
    title = f"WINDOW 3W ANALYSIS | {start_week} onwards"
    fmt_title = wb.add_format({'bg_color': C_DARK_BLUE, 'font_color': C_WHITE, 'bold': True, 'size': 14, 'align': 'center', 'valign': 'vcenter'})
    ws.merge_range(0, 0, 0, N_COLS - 1, title, fmt_title)
    ws.set_row(0, 30)

    # KPI counts
    demand_alerts = [a for a in alerts if a["seg_type"] == "Demand"]
    kpi_data = [
        ("Demand INCREASE",    sum(1 for a in demand_alerts if a["direction"] == "INCREASE"),   C_GREEN),
        ("Demand DECREASE",    sum(1 for a in demand_alerts if a["direction"] == "DECREASE"),   C_ORANGE),
        ("Demand NEW DEMAND",  sum(1 for a in demand_alerts if a["direction"] == "NEW DEMAND"), C_BLUE),
        ("Demand ZERO OUT",    sum(1 for a in demand_alerts if a["direction"] == "ZERO OUT"),   C_RED),
        ("Delivery changes",   sum(1 for a in alerts if a["seg_type"] != "Demand"),             C_GRAY),
    ]
    for idx, (label, count, color) in enumerate(kpi_data):
        row = 1 + idx
        ws.set_row(row, 22)
        fmt_lbl = wb.add_format({'bg_color': color, 'font_color': C_WHITE, 'bold': True, 'size': 10, 'align': 'left', 'valign': 'vcenter'})
        ws.merge_range(row, 0, row, 1, label, fmt_lbl)
        fmt_cnt = wb.add_format({'bg_color': color, 'font_color': C_WHITE, 'bold': True, 'size': 12, 'align': 'center', 'valign': 'vcenter'})
        ws.write(row, 2, count, fmt_cnt)

    # Row 6: Header
    HDR_ROW = 6
    ws.set_row(HDR_ROW, 30)
    fmt_hdr = wb.add_format({'bg_color': C_DARK_BLUE, 'font_color': C_WHITE, 'bold': True, 'size': 10, 'align': 'center', 'valign': 'vcenter'})
    for ci, h in enumerate(COLS):
        ws.write(HDR_ROW, ci, h, fmt_hdr)

    # Column widths
    widths = [6, 14, 28, 14, 12, 16, 18, 7, 13, 13, 13, 10, 8, 8, 10, 10, 32]
    for ci, w in enumerate(widths):
        ws.set_column(ci, ci, w)

    DIRECTION_COLORS = {
        "INCREASE":   (C_GREEN,  C_WHITE),
        "DECREASE":   (C_ORANGE, C_WHITE),
        "NEW DEMAND": (C_BLUE,   C_WHITE),
        "ZERO OUT":   (C_RED,    C_WHITE),
    }

    current_row = HDR_ROW + 1
    for stt_i, alert in enumerate(alerts, start=1):
        r = current_row
        ws.set_row(r, 40)

        ws.write(r, 0, stt_i, get_format(wb, align="center"))
        ws.write(r, 1, alert["item"], get_format(wb, align="left"))
        ws.write(r, 2, alert["desc"], get_format(wb, align="left_wrap"))
        ws.write(r, 3, alert["vendor"], get_format(wb, align="left"))
        ws.write(r, 4, alert["seg_type"], get_format(wb, align="left"))

        dc = DIRECTION_COLORS.get(alert["direction"], (C_GRAY, C_WHITE))
        ws.write(r, 5, alert["direction"], get_format(wb, bg_color=dc[0], font_color=dc[1], bold=True, align="center"))

        ws.write(r, 6, alert["zone_window"], get_format(wb, align="center"))
        ws.write(r, 7, alert["n_wks"], get_format(wb, align="center"))
        ws.write(r, 8, alert["old_total"], get_format(wb, align="right", num_fmt="#,##0;(#,##0);-"))
        ws.write(r, 9, alert["new_total"], get_format(wb, align="right", num_fmt="#,##0;(#,##0);-"))
        ws.write(r, 10, alert["delta"], get_format(wb, align="right", num_fmt="+#,##0;-#,##0;-", bold=True))

        pct = alert["pct"]
        pct_heat_f, pct_heat_fc = _heat_fill_colors(pct)
        ws.write(r, 11, pct if pct != 0 else "", get_format(wb, bg_color=pct_heat_f, font_color=pct_heat_fc, bold=True, align="right", num_fmt="+0.0%;-0.0%;-"))

        ws.write(r, 12, alert["lt"], get_format(wb, align="center", num_fmt="#,##0;(#,##0);-"))
        ws.write(r, 13, alert["moq"], get_format(wb, align="center", num_fmt="#,##0;(#,##0);-"))
        ws.write(r, 14, alert["ss"], get_format(wb, align="right", num_fmt="#,##0;(#,##0);-"))
        ws.write(r, 15, alert["ending"], get_format(wb, align="right", num_fmt="#,##0;(#,##0);-"))
        ws.write(r, 16, alert["action"], get_format(wb, align="left_wrap"))

        current_row += 1

    last_data_row = current_row - 1

    # AutoFilter
    ws.autofilter(HDR_ROW, 0, last_data_row, N_COLS - 1)

    # Freeze panes
    ws.freeze_panes(HDR_ROW + 1, 7)

