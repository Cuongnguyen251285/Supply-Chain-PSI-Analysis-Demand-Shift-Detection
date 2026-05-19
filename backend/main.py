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


# Serve frontend last so API routes take priority
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")
