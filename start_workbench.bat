@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo   AI Music Workbench Launcher
echo ============================================================
echo.
echo [1/2] Starting backend (FastAPI :8000) ...
start "music-backend" cmd /k "cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 >nul

echo [2/2] Starting frontend (Vite :5173) ...
start "music-frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ------------------------------------------------------------
echo   Backend: http://127.0.0.1:8000   (API docs: /docs)
echo   Frontend: http://127.0.0.1:5173
echo ------------------------------------------------------------
echo.
echo Close this window when done. Backend/frontend run in their
echo own windows ("music-backend" / "music-frontend").
echo.
pause
