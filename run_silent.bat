@echo off
chcp 65001 >nul
REM 작업 스케줄러 전용 무인 실행 (pause 없음, 로그 기록)
cd /d "%~dp0"
if not exist "%~dp0data" mkdir "%~dp0data"
python -c "import requests" 2>nul || python -m pip install requests
echo ============================================ >> "%~dp0data\run.log"
echo [%date% %time%] 수집 시작 >> "%~dp0data\run.log"
python run.py >> "%~dp0data\run.log" 2>&1
echo [%date% %time%] 수집 종료 (errorlevel=%errorlevel%) >> "%~dp0data\run.log"
