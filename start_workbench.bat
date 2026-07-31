@echo off
chcp 65001 >nul
REM 启动 AI音乐工程工作台 (前后端)
cd /d "%~dp0"

echo === 启动后端 (FastAPI :8000) ===
start "music-backend" cmd /k "cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 >nul

echo === 启动前端 (Vite :5173) ===
start "music-frontend" cmd /k "cd frontend && npm run dev"

echo.
echo 后端: http://127.0.0.1:8000  (API文档: /docs)
echo 前端: http://127.0.0.1:5173
echo.
pause