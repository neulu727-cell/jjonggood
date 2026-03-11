"""ADB Bridge 원격 설치 페이지"""

import os
from flask import Blueprint, Response, request

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
    """Windows 설치 배치파일 다운로드"""
    server_url = request.args.get("server", request.url_root.rstrip("/"))
    api_key = request.args.get("key", "")
    bat = _generate_install_bat(server_url, api_key)
    return Response(bat, mimetype="application/octet-stream",
                    headers={"Content-Disposition": "attachment; filename=jjonggood_setup.bat"})


def _generate_install_bat(server_url: str, api_key: str) -> str:
    return f'''@echo off
chcp 65001 >nul
title 쫑굿 ADB Bridge 설치

echo ============================================
echo   쫑굿 ADB Bridge 자동 설치
echo ============================================
echo.

:: Python 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo        https://www.python.org/downloads/ 에서 설치하세요.
    echo        설치 시 "Add Python to PATH" 체크 필수!
    pause
    exit /b 1
)

:: ADB 확인
adb version >nul 2>&1
if errorlevel 1 (
    echo [경고] ADB가 설치되어 있지 않습니다.
    echo        Android SDK Platform Tools를 설치해야 합니다.
    echo        https://developer.android.com/tools/releases/platform-tools
    echo.
    echo        설치 후 다시 실행하거나, 지금 계속하시겠습니까?
    choice /C YN /M "계속 진행 (Y/N)"
    if errorlevel 2 exit /b 1
)

:: 설치 폴더
set INSTALL_DIR=%USERPROFILE%\\jjonggood-bridge
echo.
echo [1/4] 설치 폴더: %INSTALL_DIR%
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: adb_bridge.py 다운로드
echo [2/4] adb_bridge.py 다운로드 중...
powershell -Command "Invoke-WebRequest -Uri '{server_url}/setup/adb_bridge.py' -OutFile '%INSTALL_DIR%\\adb_bridge.py'" 2>nul
if not exist "%INSTALL_DIR%\\adb_bridge.py" (
    echo [오류] 다운로드 실패. 서버 연결을 확인하세요.
    pause
    exit /b 1
)
echo        완료!

:: .env 파일 생성
echo [3/4] 설정 파일 생성...
(
    echo RENDER_URL={server_url}
    echo TASKER_API_KEY={api_key}
) > "%INSTALL_DIR%\\.env"
echo        서버: {server_url}

:: 시작프로그램 등록
echo [4/4] 시작프로그램 등록...
set STARTUP_DIR=%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup
set VBS_PATH=%INSTALL_DIR%\\start_bridge.vbs

:: VBS로 숨김 실행 (CMD 창 안 뜨게)
(
    echo Set WshShell = CreateObject^("WScript.Shell"^)
    echo WshShell.Run "cmd /c cd /d %INSTALL_DIR% && python adb_bridge.py", 0, False
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
    echo python adb_bridge.py
    echo pause
) > "%INSTALL_DIR%\\run_bridge.bat"

echo.
echo ============================================
echo   설치 완료!
echo ============================================
echo.
echo   설치 위치: %INSTALL_DIR%
echo   시작프로그램: 자동 등록됨 (PC 부팅 시 자동 실행)
echo.
echo   지금 바로 실행하시겠습니까?
choice /C YN /M "실행 (Y/N)"
if errorlevel 2 goto :done

echo.
echo ADB Bridge 시작...
cd /d "%INSTALL_DIR%"
python adb_bridge.py

:done
echo.
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
    background: #4F46E5; color: #fff; padding: 24px;
    text-align: center;
}
.header h1 { font-size: 22px; font-weight: 700; margin-bottom: 6px; }
.header p { font-size: 14px; color: #A5B4FC; }
.container {
    max-width: 640px; margin: 0 auto; padding: 24px 16px 40px;
}
.card {
    background: #fff; border-radius: 16px; padding: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06); margin-bottom: 16px;
}
.card h2 { font-size: 17px; font-weight: 700; margin-bottom: 14px; color: #4F46E5; }
.card h3 { font-size: 15px; font-weight: 700; margin: 16px 0 8px; }
.steps { list-style: none; counter-reset: step; }
.steps li {
    counter-increment: step; padding: 12px 0; border-bottom: 1px solid #F2F3F5;
    font-size: 14px; line-height: 1.7; display: flex; gap: 12px;
}
.steps li:last-child { border-bottom: none; }
.steps li::before {
    content: counter(step);
    display: flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; border-radius: 50%;
    background: #EEF2FF; color: #4F46E5; font-weight: 700;
    font-size: 13px; flex-shrink: 0;
}
.steps li span { flex: 1; }
.note {
    background: #FEF3C7; border-radius: 10px; padding: 14px;
    font-size: 13px; color: #92400E; margin-top: 12px; line-height: 1.6;
}
.note strong { color: #78350F; }
.btn-download {
    display: block; width: 100%; padding: 16px; text-align: center;
    background: #4F46E5; color: #fff; border: none; border-radius: 12px;
    font-size: 16px; font-weight: 700; cursor: pointer;
    text-decoration: none; transition: all 0.2s;
}
.btn-download:hover { background: #4338CA; transform: translateY(-1px); }
.btn-download:active { transform: translateY(0); }
.btn-secondary {
    display: block; width: 100%; padding: 14px; text-align: center;
    background: #F2F3F5; color: #191F28; border: none; border-radius: 12px;
    font-size: 14px; font-weight: 600; cursor: pointer;
    text-decoration: none; margin-top: 10px; transition: all 0.2s;
}
.btn-secondary:hover { background: #E5E8EB; }
code {
    background: #F2F3F5; padding: 2px 8px; border-radius: 6px;
    font-family: 'Consolas', monospace; font-size: 13px; color: #4F46E5;
}
.prereq { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid #F2F3F5; font-size: 14px; }
.prereq:last-child { border-bottom: none; }
.prereq .icon { font-size: 20px; }
.prereq a { color: #4F46E5; text-decoration: none; font-weight: 600; }
.prereq a:hover { text-decoration: underline; }
.flow {
    display: flex; align-items: center; justify-content: center; gap: 8px;
    padding: 16px; font-size: 13px; color: #4E5968; flex-wrap: wrap;
}
.flow-item {
    background: #EEF2FF; color: #4338CA; padding: 6px 14px; border-radius: 8px;
    font-weight: 600; font-size: 13px;
}
.flow-arrow { color: #C4C9D0; font-size: 18px; }
</style>
</head>
<body>
<div class="header">
    <h1>ADB Bridge 설치</h1>
    <p>어떤 PC에서든 수신전화 연결을 설정하세요</p>
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

    <div class="card">
        <h2>사전 준비</h2>
        <div class="prereq">
            <span class="icon">&#128013;</span>
            <span>Python 3.8 이상 &mdash;
                <a href="https://www.python.org/downloads/" target="_blank">다운로드</a>
                (설치 시 <strong>Add to PATH</strong> 체크)
            </span>
        </div>
        <div class="prereq">
            <span class="icon">&#128241;</span>
            <span>ADB (Android Platform Tools) &mdash;
                <a href="https://developer.android.com/tools/releases/platform-tools" target="_blank">다운로드</a>
                후 PATH에 추가
            </span>
        </div>
        <div class="prereq">
            <span class="icon">&#128268;</span>
            <span>폰 USB 디버깅 활성화 (설정 &rarr; 개발자 옵션 &rarr; USB 디버깅)</span>
        </div>
    </div>

    <div class="card">
        <h2>원클릭 설치</h2>
        <ol class="steps">
            <li><span>아래 버튼으로 설치 파일을 다운로드합니다</span></li>
            <li><span>다운로드된 <code>jjonggood_setup.bat</code> 파일을 <strong>더블클릭</strong>하여 실행합니다</span></li>
            <li><span>자동으로 설치 + 시작프로그램 등록이 완료됩니다</span></li>
            <li><span>PC를 재부팅하면 자동으로 ADB Bridge가 실행됩니다</span></li>
        </ol>

        <div style="margin-top: 20px">
            <a class="btn-download" href="/setup/install.bat?server={{SERVER_URL}}" id="btnDownload">
                설치 파일 다운로드 (.bat)
            </a>
            <a class="btn-secondary" href="/setup/adb_bridge.py">
                adb_bridge.py만 다운로드
            </a>
        </div>

        <div class="note" style="margin-top:16px">
            <strong>참고:</strong> 설치 파일에 API 키가 포함되어야 합니다.
            아래에서 API 키를 입력하면 설치 파일에 자동으로 포함됩니다.
        </div>

        <div style="margin-top:14px">
            <label style="font-size:13px; font-weight:600; color:#4E5968; display:block; margin-bottom:6px">
                API 키 (TASKER_API_KEY)
            </label>
            <input type="text" id="apiKeyInput" placeholder="API 키 입력..."
                style="width:100%; padding:12px 14px; border:1.5px solid #E5E8EB; border-radius:10px;
                font-size:14px; outline:none; font-family:inherit;"
                oninput="updateDownloadLink()">
        </div>
    </div>

    <div class="card">
        <h2>설치 후 구조</h2>
        <pre style="background:#F8F9FB; padding:14px; border-radius:10px; font-size:13px; line-height:1.8; overflow-x:auto; color:#4E5968">
%USERPROFILE%\\jjonggood-bridge\\
  adb_bridge.py      ← 메인 프로그램
  .env               ← 서버 URL + API 키
  run_bridge.bat     ← 수동 실행용
  start_bridge.vbs   ← 시작프로그램 (숨김 실행)</pre>
    </div>

    <div class="card">
        <h2>수동 관리</h2>
        <h3>시작프로그램 제거</h3>
        <p style="font-size:14px; line-height:1.7; color:#4E5968">
            <code>Win+R</code> &rarr; <code>shell:startup</code> 입력 &rarr;
            <code>jjonggood_bridge.vbs</code> 파일 삭제
        </p>
        <h3 style="margin-top:16px">완전 삭제</h3>
        <p style="font-size:14px; line-height:1.7; color:#4E5968">
            시작프로그램 제거 후, <code>%USERPROFILE%\\jjonggood-bridge</code> 폴더 삭제
        </p>
    </div>

</div>

<script>
function updateDownloadLink() {
    const key = document.getElementById('apiKeyInput').value.trim();
    const btn = document.getElementById('btnDownload');
    let url = '/setup/install.bat?server={{SERVER_URL}}';
    if (key) url += '&key=' + encodeURIComponent(key);
    btn.href = url;
}
</script>
</body>
</html>'''
