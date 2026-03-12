@echo off
chcp 65001 >nul
echo 시작 프로그램에 가게 모니터 등록 중...

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SCRIPT_DIR=%~dp0"
set "TARGET=%STARTUP%\jjonggood_monitor.bat"

:: 기존 파일 제거
if exist "%STARTUP%\jjonggood_backup.bat" del "%STARTUP%\jjonggood_backup.bat"
if exist "%TARGET%" del "%TARGET%"

:: 시작 프로그램 bat 생성 (한 줄씩 작성)
echo @echo off> "%TARGET%"
echo cd /d "%SCRIPT_DIR%">> "%TARGET%"
echo pythonw adb_bridge.py>> "%TARGET%"

echo.
echo 등록 완료!
echo 위치: %TARGET%
echo.
echo 컴퓨터 켤 때마다 자동 실행됩니다. (휴대폰 연결 + DB 백업)
pause
