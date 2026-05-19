@echo off
echo =============================================
echo  PSI Compare - Starting server...
echo =============================================
cd /d "%~dp0backend"
pip install -r requirements.txt -q
echo.
echo Server starting at http://localhost:8000
echo Press Ctrl+C to stop.
echo.
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
