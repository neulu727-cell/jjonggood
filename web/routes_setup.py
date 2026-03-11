"""ADB Bridge 원격 설치 페이지"""

import os
from flask import Blueprint, Response, request
from web import config

setup_bp = Blueprint("setup", __name__)

# adb_bridge.py 경로 (프로젝트 루트)
ADB_BRIDGE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "adb_bridge.py")

# 앱 시작 시 adb_bridge.py 내용을 캐시 (클라우드 배포 시에도 사용 가능)
_adb_bridge_cache = None


def _get_adb_bridge_content():
    global _adb_bridge_cache
    if _adb_bridge_cache is not None:
        return _adb_bridge_cache
    if os.path.exists(ADB_BRIDGE_PATH):
        with open(ADB_BRIDGE_PATH, encoding="utf-8") as f:
            _adb_bridge_cache = f.read()
    else:
        _adb_bridge_cache = _FALLBACK_ADB_BRIDGE
    return _adb_bridge_cache


@setup_bp.route("/setup")
def setup_page():
    """설치 안내 페이지 (인증 불필요)"""
    server_url = request.url_root.rstrip("/")
    return SETUP_HTML.replace("{{SERVER_URL}}", server_url)


@setup_bp.route("/setup/adb_bridge.py")
def download_adb_bridge():
    """adb_bridge.py 파일 다운로드"""
    content = _get_adb_bridge_content()
    return Response(content, mimetype="text/plain",
                    headers={"Content-Disposition": "attachment; filename=adb_bridge.py"})


@setup_bp.route("/setup/install.bat")
def download_install_bat():
    """Windows 설치 배치파일 다운로드 (API 키 자동 주입)"""
    server_url = request.args.get("server", request.url_root.rstrip("/"))
    api_key = config.TASKER_API_KEY  # 서버에서 자동 주입
    bat = _generate_install_bat(server_url, api_key)
    return Response(bat, mimetype="application/octet-stream",
                    headers={"Content-Disposition": "attachment; filename=jjonggood_setup.bat"})


def _generate_install_bat(server_url: str, api_key: str) -> str:
    return f'''@echo off
chcp 65001 >nul
title 쫑굿 ADB Bridge 원클릭 설치
setlocal enabledelayedexpansion

echo ============================================
echo   쫑굿 ADB Bridge 원클릭 설치
echo ============================================
echo.

:: 설치 폴더
set INSTALL_DIR=%USERPROFILE%\\jjonggood-bridge
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
echo   설치 위치: %INSTALL_DIR%
echo.

:: ── 1단계: Python 확인 / 자동 설치 ──
echo [1/6] Python 확인 중...
set PYTHON_CMD=
set LOCAL_PYTHON=%INSTALL_DIR%\\python\\python.exe

:: 로컬 임베디드 Python 먼저 확인
if exist "%LOCAL_PYTHON%" (
    echo        로컬 Python 발견!
    set PYTHON_CMD=%LOCAL_PYTHON%
    goto :python_ok
)

:: 시스템 Python 확인
python --version >nul 2>&1
if not errorlevel 1 (
    echo        시스템 Python 발견!
    set PYTHON_CMD=python
    goto :python_ok
)

:: Python 없음 → 임베디드 버전 자동 다운로드
echo        Python이 없습니다. 자동 다운로드 중...
set PY_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip
set PY_ZIP=%INSTALL_DIR%\\python_embed.zip

powershell -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_ZIP%'" 2>nul
if not exist "%PY_ZIP%" (
    echo [오류] Python 다운로드 실패. 인터넷 연결을 확인하세요.
    pause
    exit /b 1
)

echo        압축 해제 중...
if not exist "%INSTALL_DIR%\\python" mkdir "%INSTALL_DIR%\\python"
powershell -Command "$ProgressPreference='SilentlyContinue'; Expand-Archive -Path '%PY_ZIP%' -DestinationPath '%INSTALL_DIR%\\python' -Force" 2>nul
del "%PY_ZIP%" >nul 2>&1

if exist "%LOCAL_PYTHON%" (
    echo        Python 설치 완료!
    set PYTHON_CMD=%LOCAL_PYTHON%
) else (
    echo [오류] Python 설치 실패.
    pause
    exit /b 1
)

:python_ok
echo.

:: ── 2단계: ADB 확인 / 자동 설치 ──
echo [2/6] ADB 확인 중...
set ADB_CMD=
set LOCAL_ADB=%INSTALL_DIR%\\platform-tools\\adb.exe

:: 로컬 ADB 먼저 확인
if exist "%LOCAL_ADB%" (
    echo        로컬 ADB 발견!
    set ADB_CMD=%LOCAL_ADB%
    goto :adb_ok
)

:: 시스템 ADB 확인
adb version >nul 2>&1
if not errorlevel 1 (
    echo        시스템 ADB 발견!
    set ADB_CMD=adb
    goto :adb_ok
)

:: ADB 없음 → 자동 다운로드
echo        ADB가 없습니다. 자동 다운로드 중...
set ADB_URL=https://dl.google.com/android/repository/platform-tools-latest-windows.zip
set ADB_ZIP=%INSTALL_DIR%\\platform-tools.zip

powershell -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%ADB_URL%' -OutFile '%ADB_ZIP%'" 2>nul
if not exist "%ADB_ZIP%" (
    echo [오류] ADB 다운로드 실패. 인터넷 연결을 확인하세요.
    pause
    exit /b 1
)

echo        압축 해제 중...
powershell -Command "$ProgressPreference='SilentlyContinue'; Expand-Archive -Path '%ADB_ZIP%' -DestinationPath '%INSTALL_DIR%' -Force" 2>nul
del "%ADB_ZIP%" >nul 2>&1

if exist "%LOCAL_ADB%" (
    echo        ADB 설치 완료!
    set ADB_CMD=%LOCAL_ADB%
) else (
    echo [오류] ADB 설치 실패.
    pause
    exit /b 1
)

:adb_ok
echo.

:: ── 3단계: adb_bridge.py 다운로드 ──
echo [3/6] adb_bridge.py 다운로드 중...
powershell -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '{server_url}/setup/adb_bridge.py' -OutFile '%INSTALL_DIR%\\adb_bridge.py'" 2>nul
if not exist "%INSTALL_DIR%\\adb_bridge.py" (
    echo [오류] 다운로드 실패. 서버 연결을 확인하세요.
    pause
    exit /b 1
)
echo        완료!
echo.

:: ── 4단계: .env 파일 생성 (API 키 자동 주입) ──
echo [4/6] 설정 파일 생성...
(
    echo RENDER_URL={server_url}
    echo TASKER_API_KEY={api_key}
) > "%INSTALL_DIR%\\.env"
echo        서버: {server_url}
echo        API 키: 자동 설정 완료
echo.

:: ── 5단계: 시작프로그램 등록 ──
echo [5/6] 시작프로그램 등록...
set STARTUP_DIR=%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup
set VBS_PATH=%INSTALL_DIR%\\start_bridge.vbs

:: VBS로 숨김 실행 (CMD 창 안 뜨게)
(
    echo Set WshShell = CreateObject^("WScript.Shell"^)
    echo WshShell.Run "cmd /c cd /d %INSTALL_DIR% && ""%PYTHON_CMD%"" adb_bridge.py", 0, False
) > "%VBS_PATH%"

:: 시작프로그램 폴더에 바로가기 복사
copy "%VBS_PATH%" "%STARTUP_DIR%\\jjonggood_bridge.vbs" >nul 2>&1

:: 바로 실행용 배치파일도 생성
(
    echo @echo off
    echo chcp 65001 ^>nul
    echo title 쫑굿 ADB Bridge
    echo cd /d %INSTALL_DIR%
    echo echo 쫑굿 ADB Bridge 실행 중... ^(이 창을 닫으면 종료^)
    echo "%PYTHON_CMD%" adb_bridge.py
    echo pause
) > "%INSTALL_DIR%\\run_bridge.bat"

echo        완료!
echo.

:: ── 6단계: 바로 실행 ──
echo [6/6] ADB Bridge 시작...
echo.
echo ============================================
echo   설치 완료!
echo ============================================
echo.
echo   폰을 USB로 연결하고 USB 디버깅을 켜주세요.
echo   PC 재부팅 시 자동으로 실행됩니다.
echo.
echo   이 창을 닫으면 Bridge가 종료됩니다.
echo   (PC 재부팅 시 자동 재시작됨)
echo ============================================
echo.

cd /d "%INSTALL_DIR%"
"%PYTHON_CMD%" adb_bridge.py
pause
'''


# adb_bridge.py를 못 찾을 경우 (경로 문제) 안내 메시지
_FALLBACK_ADB_BRIDGE = "# adb_bridge.py - 서버에서 파일을 찾을 수 없습니다.\n# /setup 페이지에서 다시 다운로드하세요.\n"


SETUP_HTML = '''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ADB Bridge 설치</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
    background: #F7F8FA; color: #191F28;
    min-height: 100vh; padding: 0;
}
.header {
    background: #4F46E5; color: #fff; padding: 32px 24px;
    text-align: center;
}
.header h1 { font-size: 24px; font-weight: 700; margin-bottom: 8px; }
.header p { font-size: 14px; color: #A5B4FC; }
.container {
    max-width: 640px; margin: 0 auto; padding: 24px 16px 40px;
}
.card {
    background: #fff; border-radius: 16px; padding: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06); margin-bottom: 16px;
}
.card h2 { font-size: 17px; font-weight: 700; margin-bottom: 14px; color: #4F46E5; }
.flow {
    display: flex; align-items: center; justify-content: center; gap: 8px;
    padding: 16px; font-size: 13px; color: #4E5968; flex-wrap: wrap;
}
.flow-item {
    background: #EEF2FF; color: #4338CA; padding: 6px 14px; border-radius: 8px;
    font-weight: 600; font-size: 13px;
}
.flow-arrow { color: #C4C9D0; font-size: 18px; }
.big-btn {
    display: block; width: 100%; padding: 22px; text-align: center;
    background: #4F46E5; color: #fff; border: none; border-radius: 16px;
    font-size: 20px; font-weight: 700; cursor: pointer;
    text-decoration: none; transition: all 0.2s;
    box-shadow: 0 4px 12px rgba(79,70,229,0.3);
}
.big-btn:hover { background: #4338CA; transform: translateY(-2px); box-shadow: 0 6px 16px rgba(79,70,229,0.4); }
.big-btn:active { transform: translateY(0); }
.big-btn .sub { font-size: 13px; font-weight: 400; color: #C7D2FE; margin-top: 6px; display: block; }
.auto-list {
    list-style: none; padding: 0; margin: 16px 0 0 0;
}
.auto-list li {
    padding: 10px 0; border-bottom: 1px solid #F2F3F5;
    font-size: 14px; display: flex; align-items: center; gap: 10px;
}
.auto-list li:last-child { border-bottom: none; }
.auto-list .check { color: #22C55E; font-size: 18px; font-weight: 700; }
.note {
    background: #FEF3C7; border-radius: 10px; padding: 14px;
    font-size: 13px; color: #92400E; line-height: 1.6;
}
.note strong { color: #78350F; }
code {
    background: #F2F3F5; padding: 2px 8px; border-radius: 6px;
    font-family: 'Consolas', monospace; font-size: 13px; color: #4F46E5;
}
.status-box {
    text-align: center; padding: 20px; border-radius: 12px;
    font-size: 15px; font-weight: 600;
}
.status-alive { background: #DCFCE7; color: #166534; }
.status-no-device { background: #FEF9C3; color: #854D0E; }
.status-dead { background: #FEE2E2; color: #991B1B; }
.status-unknown { background: #F2F3F5; color: #6B7280; }
</style>
</head>
<body>
<div class="header">
    <h1>ADB Bridge 원클릭 설치</h1>
    <p>클릭 한 번으로 모든 것이 자동 설치됩니다</p>
</div>
<div class="container">

    <div class="card">
        <div class="flow">
            <span class="flow-item">USB 폰</span>
            <span class="flow-arrow">&rarr;</span>
            <span class="flow-item">ADB Bridge</span>
            <span class="flow-arrow">&rarr;</span>
            <span class="flow-item">웹앱 알림</span>
        </div>
    </div>

    <!-- 현재 상태 -->
    <div class="card">
        <h2>현재 Bridge 상태</h2>
        <div class="status-box status-unknown" id="bridgeStatusBox">
            확인 중...
        </div>
    </div>

    <!-- 원클릭 설치 -->
    <div class="card">
        <a class="big-btn" href="/setup/install.bat?server={{SERVER_URL}}">
            &#11015; 설치 파일 다운로드
            <span class="sub">다운 후 더블클릭 → 모든 것이 자동 설치됩니다</span>
        </a>

        <ul class="auto-list">
            <li><span class="check">&#10003;</span> Python 없으면 자동 다운로드</li>
            <li><span class="check">&#10003;</span> ADB 없으면 자동 다운로드</li>
            <li><span class="check">&#10003;</span> API 키 자동 설정</li>
            <li><span class="check">&#10003;</span> 시작프로그램 자동 등록</li>
            <li><span class="check">&#10003;</span> 설치 완료 후 바로 실행</li>
        </ul>
    </div>

    <div class="card">
        <div class="note">
            <strong>사전 준비:</strong> 폰을 USB로 연결하고
            <strong>USB 디버깅</strong>을 켜주세요.
            (설정 &rarr; 개발자 옵션 &rarr; USB 디버깅)
        </div>
    </div>

    <div class="card">
        <h2>설치 후 구조</h2>
        <pre style="background:#F8F9FB; padding:14px; border-radius:10px; font-size:13px; line-height:1.8; overflow-x:auto; color:#4E5968">
%USERPROFILE%\\jjonggood-bridge\\
  adb_bridge.py      &larr; 메인 프로그램
  .env               &larr; 서버 URL + API 키 (자동 생성)
  run_bridge.bat     &larr; 수동 실행용
  start_bridge.vbs   &larr; 시작프로그램 (숨김 실행)
  python\\            &larr; Python (자동 설치)
  platform-tools\\    &larr; ADB (자동 설치)</pre>
    </div>

    <div class="card">
        <h2>수동 관리</h2>
        <p style="font-size:14px; line-height:1.7; color:#4E5968; margin-bottom:10px">
            <strong>시작프로그램 제거:</strong>
            <code>Win+R</code> &rarr; <code>shell:startup</code> &rarr;
            <code>jjonggood_bridge.vbs</code> 삭제
        </p>
        <p style="font-size:14px; line-height:1.7; color:#4E5968">
            <strong>완전 삭제:</strong>
            시작프로그램 제거 후 <code>%USERPROFILE%\\jjonggood-bridge</code> 폴더 삭제
        </p>
    </div>

</div>

<script>
// 설치 페이지에서도 Bridge 상태 표시
(function() {
    fetch('/api/bridge-status', {credentials: 'same-origin'})
        .then(r => r.ok ? r.json() : null)
        .then(data => {
            if (!data) return;
            const box = document.getElementById('bridgeStatusBox');
            if (data.alive && data.status === 'ok') {
                box.className = 'status-box status-alive';
                box.textContent = '\\uD83D\\uDFE2 ADB 감시중 (기기: ' + (data.device || '연결됨') + ')';
            } else if (data.alive && data.status === 'no_device') {
                box.className = 'status-box status-no-device';
                box.textContent = '\\uD83D\\uDFE1 Bridge 실행 중 (기기 없음)';
            } else {
                box.className = 'status-box status-dead';
                box.textContent = '\\uD83D\\uDD34 Bridge 꺼짐';
            }
        })
        .catch(() => {
            const box = document.getElementById('bridgeStatusBox');
            box.className = 'status-box status-dead';
            box.textContent = '\\uD83D\\uDD34 Bridge 꺼짐';
        });
})();
</script>
</body>
</html>'''
