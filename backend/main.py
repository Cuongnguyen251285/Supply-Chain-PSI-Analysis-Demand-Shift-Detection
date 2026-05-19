import uuid
import os
import math
import tempfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from psi_parser import parse_psi_sheet
from psi_compare import compare_psi
from window_3w import compute_window_3w
from excel_writer import write_excel_output

app = FastAPI(title="PSI Compare")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_sessions: dict[str, str] = {}  # session_id -> excel_path

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


def _sanitize(obj):
    """Recursively replace non-finite floats (NaN/Inf) with 0 for JSON safety."""
    if isinstance(obj, float):
        if not math.isfinite(obj):
            return 0.0
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


@app.post("/api/compare")
async def compare(
    file_old: UploadFile = File(...),
    file_new: UploadFile = File(...),
    start_week: str = Form(...),
    threshold_compare: float = Form(0.20),
    threshold_window: float = Form(0.10),
):
    old_bytes = await file_old.read()
    new_bytes = await file_new.read()

    old_ext = Path(file_old.filename or "file.xlsx").suffix.lower() or ".xlsx"
    new_ext = Path(file_new.filename or "file.xlsx").suffix.lower() or ".xlsx"

    with tempfile.NamedTemporaryFile(suffix=old_ext, delete=False) as f:
        f.write(old_bytes)
        old_path = f.name
    with tempfile.NamedTemporaryFile(suffix=new_ext, delete=False) as f:
        f.write(new_bytes)
        new_path = f.name

    try:
        old_map, week_headers = parse_psi_sheet(old_path)
        new_map, _ = parse_psi_sheet(new_path)

        if not week_headers:
            raise ValueError(
                "No week columns found. Make sure your Excel has headers like W01, W02 … "
                "starting from column L (index 11)."
            )

        compare_results, future_weeks = compare_psi(
            old_map, new_map, week_headers, start_week, threshold_compare
        )
        window_results = compute_window_3w(
            old_map, new_map, week_headers, start_week, threshold_window
        )

        session_id = str(uuid.uuid4())
        excel_path = Path(tempfile.gettempdir()) / f"psi_compare_{session_id}.xlsx"

        old_label = Path(file_old.filename or "OLD").stem
        new_label = Path(file_new.filename or "NEW").stem

        write_excel_output(
            str(excel_path),
            compare_results,
            window_results,
            future_weeks,
            start_week,
            old_label,
            new_label,
        )

        _sessions[session_id] = str(excel_path)

        payload = {
            "session_id": session_id,
            "old_label": old_label,
            "new_label": new_label,
            "future_weeks": future_weeks,
            "compare": compare_results,
            "window": window_results,
        }

        # Cache session data as JSON for on-the-fly filtering downloads
        import json
        json_path = Path(tempfile.gettempdir()) / f"psi_compare_{session_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "future_weeks": future_weeks,
                "start_week": start_week,
                "old_label": old_label,
                "new_label": new_label,
                "compare": compare_results,
                "window": window_results
            }, f, ensure_ascii=False)

        return JSONResponse(_sanitize(payload))

    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"{str(e)}\n{traceback.format_exc()}")
    finally:
        try:
            os.unlink(old_path)
        except Exception:
            pass
        try:
            os.unlink(new_path)
        except Exception:
            pass


@app.get("/api/download/{session_id}")
async def download(session_id: str):
    excel_path = _sessions.get(session_id)
    if not excel_path or not Path(excel_path).exists():
        raise HTTPException(404, "Session not found or expired")
    return FileResponse(
        excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="PSI_Compare_Result.xlsx",
    )


@app.get("/api/download-filtered/{session_id}")
async def download_filtered(
    session_id: str,
    c_search: str = "",
    c_status: str = "ALL",
    c_type: str = "ALL",
    w_search: str = "",
    w_dir: str = "ALL",
    w_type: str = "ALL"
):
    json_path = Path(tempfile.gettempdir()) / f"psi_compare_{session_id}.json"
    if not json_path.exists():
        raise HTTPException(404, "Session cache expired or not found")
    
    import json
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    compare_results = data["compare"]
    window_results = data["window"]
    future_weeks = data["future_weeks"]
    start_week = data["start_week"]
    old_label = data["old_label"]
    new_label = data["new_label"]
    
    # Filter compare results
    filtered_compare = []
    groups = {}
    for row in compare_results:
        item = row["item"]
        if item not in groups:
            groups[item] = []
        groups[item].append(row)
        
    c_search_lower = c_search.lower().strip()
    for item, rows in groups.items():
        match_search = not c_search_lower or \
            c_search_lower in item.lower() or \
            c_search_lower in (rows[0].get("vendor") or "").lower() or \
            c_search_lower in (rows[0].get("desc") or "").lower()
            
        if not match_search:
            continue
            
        matched_rows = []
        for r in rows:
            match_status = c_status == "ALL" or r.get("status") == c_status
            match_type = c_type == "ALL" or r.get("seg_type") == c_type
            if match_status and match_type:
                matched_rows.append(r)
                
        if matched_rows:
            filtered_compare.extend(matched_rows)
            
    # Filter window results
    filtered_window = []
    w_search_lower = w_search.lower().strip()
    for row in window_results:
        item = row.get("item") or ""
        vendor = row.get("vendor") or ""
        desc = row.get("desc") or ""
        direction = row.get("direction") or ""
        seg_type = row.get("seg_type") or ""
        
        match_search = not w_search_lower or \
            w_search_lower in item.lower() or \
            w_search_lower in vendor.lower() or \
            w_search_lower in desc.lower()
            
        match_dir = w_dir == "ALL" or direction == w_dir
        match_type = w_type == "ALL" or seg_type == w_type
        
        if match_search and match_dir and match_type:
            filtered_window.append(row)
            
    # Generate filtered Excel file
    temp_excel_path = Path(tempfile.gettempdir()) / f"psi_compare_filtered_{uuid.uuid4()}.xlsx"
    write_excel_output(
        str(temp_excel_path),
        filtered_compare,
        filtered_window,
        future_weeks,
        start_week,
        old_label,
        new_label
    )
    
    from fastapi import BackgroundTasks
    def cleanup():
        try:
            if temp_excel_path.exists():
                temp_excel_path.unlink()
        except Exception:
            pass
            
    background_tasks = BackgroundTasks()
    background_tasks.add_task(cleanup)
    
    return FileResponse(
        str(temp_excel_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="PSI_Compare_Filtered.xlsx",
        background=background_tasks
    )


# Serve frontend last so API routes take priority
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")
