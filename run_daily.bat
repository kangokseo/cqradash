@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   KIS 수익률 대시보드 - 일일 수집
echo ============================================
echo.

REM requests 미설치 시 자동 설치
python -c "import requests" 2>nul || python -m pip install requests

REM 인자가 있으면 해당 일자, 없으면 오늘
python run.py %1

echo.
if errorlevel 1 (
  echo [오류] 위 메시지를 확인하세요.
  echo  - python 명령이 없으면 Python 3 설치 필요: https://www.python.org/downloads/
  echo  - .env 의 APP_KEY/SECRET, 계좌번호를 확인하세요.
) else (
  echo [완료] dashboard.html 을 더블클릭(또는 새로고침)하세요.
)
echo.
pause
