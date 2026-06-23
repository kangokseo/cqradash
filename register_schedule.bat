@echo off
chcp 65001 >nul
REM 매일 16:00(PC 로컬시간)에 자동 수집을 Windows 작업 스케줄러에 등록
cd /d "%~dp0"

set TASKNAME=CQRA_Dashboard_Daily

echo ============================================
echo   씨큐라 대시보드 - 자동 수집 등록 (매일 16:00)
echo ============================================
echo.
echo PC 시간대가 '한국 표준시(KST)' 인지 먼저 확인하세요.
echo (제어판 ^> 날짜 및 시간 ^> 표준 시간대: (UTC+09:00) 서울)
echo.

schtasks /Create /TN "%TASKNAME%" /TR "\"%~dp0run_silent.bat\"" /SC DAILY /ST 16:00 /F

echo.
if errorlevel 1 (
  echo [실패] 등록 실패. 이 파일을 마우스 오른쪽 ^> "관리자 권한으로 실행" 으로 다시 시도하세요.
) else (
  echo [완료] 매일 16:00 자동 수집 등록됨.  작업 이름: %TASKNAME%
  echo.
  echo  - 지금 한 번 테스트 실행:   schtasks /Run /TN "%TASKNAME%"
  echo  - 등록 확인:                schtasks /Query /TN "%TASKNAME%"
  echo  - 자동 수집 해제:           schtasks /Delete /TN "%TASKNAME%" /F
  echo  - 실행 로그:                data\run.log
)
echo.
pause
