"""
웹 예약 뷰어 (읽기 전용) - 모바일 최적화

Render 배포:  DB는 PC에서 /api/sync로 업로드
로컬 실행:    python web_viewer.py (기존 DB 직접 읽기)
"""

import os
import sys
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, session, redirect, url_for

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DB_PATH
from database.db_manager import DatabaseManager
from database import queries

app = Flask(__name__)
app.secret_key = os.environ.get("WEB_VIEWER_SECRET", "jjonggood-viewer-2026")

# 비밀번호: 환경변수 또는 기본값
VIEWER_PASSWORD = os.environ.get("VIEWER_PASSWORD", "0000")

# 동기화 키: PC → Render 업로드 인증용
SYNC_KEY = os.environ.get("SYNC_KEY", "change-me")

# Render 환경 감지
IS_CLOUD = bool(os.environ.get("RENDER"))
CLOUD_DB_PATH = "/tmp/grooming_shop.db" if IS_CLOUD else DB_PATH

# DB 연결 (클라우드에서는 동기화 전까지 DB 없을 수 있음)
db = None
last_sync = None


def get_db():
    """DB 연결. 없으면 None 반환."""
    global db
    if db is not None:
        return db
    if os.path.exists(CLOUD_DB_PATH):
        db = DatabaseManager(CLOUD_DB_PATH)
        db.initialize()
        return db
    if not IS_CLOUD:
        db = DatabaseManager(CLOUD_DB_PATH)
        db.initialize()
        return db
    return None


# ==================== 인증 ====================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if pw == VIEWER_PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("index"))
        return LOGIN_HTML.replace("{{error}}", '<p class="error">비밀번호가 틀렸습니다</p>')
    return LOGIN_HTML.replace("{{error}}", "")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def require_auth():
    return bool(session.get("authenticated"))


# ==================== DB 동기화 (PC → Render) ====================

@app.route("/api/sync", methods=["POST"])
def api_sync():
    """PC에서 SQLite DB 파일을 업로드받는 엔드포인트."""
    global db, last_sync
    key = request.headers.get("X-Sync-Key", "")
    if key != SYNC_KEY:
        return jsonify({"error": "unauthorized"}), 401

    file = request.files.get("db")
    if not file:
        return jsonify({"error": "no file"}), 400

    # 기존 연결 닫고 새 파일 저장
    if db is not None:
        db.close()
        db = None

    file.save(CLOUD_DB_PATH)
    db = DatabaseManager(CLOUD_DB_PATH)
    db.initialize()
    last_sync = datetime.now().strftime("%Y-%m-%d %H:%M")

    size_kb = os.path.getsize(CLOUD_DB_PATH) / 1024
    return jsonify({"ok": True, "size_kb": round(size_kb, 1), "synced_at": last_sync})


@app.route("/api/sync-status")
def api_sync_status():
    """마지막 동기화 시간 확인."""
    has_db = os.path.exists(CLOUD_DB_PATH)
    return jsonify({"has_db": has_db, "last_sync": last_sync})


# ==================== 페이지 ====================

@app.route("/")
def index():
    if not require_auth():
        return redirect(url_for("login"))
    return MAIN_HTML


# ==================== API ====================

@app.route("/api/month")
def api_month():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    d = get_db()
    if d is None:
        return jsonify({"counts": {}, "names": {}, "no_db": True})
    y = request.args.get("y", type=int, default=datetime.now().year)
    m = request.args.get("m", type=int, default=datetime.now().month)
    counts = queries.get_reservation_counts_by_month(d, y, m)
    names = queries.get_reservation_names_by_month(d, y, m)
    return jsonify({"counts": counts, "names": names, "last_sync": last_sync})


@app.route("/api/day")
def api_day():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    d = get_db()
    if d is None:
        return jsonify({"date": "", "reservations": [], "no_db": True})
    date_str = request.args.get("date", "")
    if not date_str:
        return jsonify({"error": "date required"}), 400
    reservations = queries.get_reservations_by_date(d, date_str)
    items = []
    for r in reservations:
        start_h, start_m = map(int, r.time.split(":"))
        end_minutes = start_h * 60 + start_m + r.duration
        end_h, end_m = divmod(end_minutes, 60)
        items.append({
            "time": r.time,
            "end_time": f"{end_h:02d}:{end_m:02d}",
            "pet_name": r.pet_name,
            "breed": r.breed,
            "service": r.service_type,
            "duration": r.duration,
            "status": r.status,
        })
    return jsonify({"date": date_str, "reservations": items})


# ==================== HTML 템플릿 ====================

LOGIN_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>예약 뷰어 - 로그인</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
    background: #f5f5f5;
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh; min-height: 100dvh;
}
.login-box {
    background: #fff; border-radius: 16px; padding: 40px 28px;
    width: 90%; max-width: 360px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    text-align: center;
}
.login-box h1 { font-size: 22px; margin-bottom: 8px; color: #333; }
.login-box .subtitle { font-size: 13px; color: #999; margin-bottom: 28px; }
.login-box input {
    width: 100%; padding: 14px 16px; border: 1.5px solid #ddd;
    border-radius: 10px; font-size: 16px; text-align: center;
    letter-spacing: 8px; outline: none; margin-bottom: 16px;
    -webkit-text-security: disc;
}
.login-box input:focus { border-color: #7c5cbf; }
.login-box button {
    width: 100%; padding: 14px; background: #7c5cbf; color: #fff;
    border: none; border-radius: 10px; font-size: 16px; font-weight: 600;
    cursor: pointer;
}
.login-box button:active { background: #6a4daa; }
.error { color: #e74c3c; font-size: 13px; margin-bottom: 12px; }
</style>
</head>
<body>
<form class="login-box" method="POST" action="/login">
    <h1>🐾 예약 뷰어</h1>
    <p class="subtitle">비밀번호를 입력하세요</p>
    {{error}}
    <input type="password" name="password" inputmode="numeric" pattern="[0-9]*"
           placeholder="••••" autofocus autocomplete="current-password">
    <button type="submit">확인</button>
</form>
</body>
</html>"""

MAIN_HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<title>🐾 예약 뷰어</title>
<style>
:root {
    --primary: #7c5cbf;
    --primary-light: #ede7f6;
    --primary-badge: #d1c4e9;
    --bg: #fafafa;
    --card: #ffffff;
    --text: #333333;
    --text-light: #888888;
    --border: #eee;
    --sunday: #e74c3c;
    --saturday: #3498db;
    --today-ring: #7c5cbf;
}
* { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
html, body {
    font-family: -apple-system, 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
    background: var(--bg); color: var(--text);
    height: 100%; overflow: hidden;
    -webkit-user-select: none; user-select: none;
}

/* === 전체 레이아웃 (모바일 세로 16:9 최적화) === */
#app {
    display: flex; flex-direction: column;
    height: 100vh; height: 100dvh;
    max-width: 480px; margin: 0 auto;
    background: var(--card);
}

/* === 헤더 === */
.header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 16px; border-bottom: 1px solid var(--border);
    flex-shrink: 0;
}
.header h1 { font-size: 17px; font-weight: 700; }
.month-nav {
    display: flex; align-items: center; gap: 12px;
}
.month-nav button {
    background: none; border: none; font-size: 20px; color: var(--text);
    cursor: pointer; padding: 4px 8px; border-radius: 6px;
    line-height: 1;
}
.month-nav button:active { background: var(--primary-light); }
.month-label {
    font-size: 17px; font-weight: 700; min-width: 90px; text-align: center;
}
.header-actions { display: flex; gap: 8px; align-items: center; }
.btn-today {
    font-size: 13px; padding: 5px 10px; border-radius: 14px;
    border: 1.5px solid var(--primary); color: var(--primary);
    background: none; font-weight: 600; cursor: pointer;
}
.btn-today:active { background: var(--primary-light); }

/* === 캘린더 === */
.calendar-section { flex-shrink: 0; }
.weekday-row {
    display: grid; grid-template-columns: repeat(7, 1fr);
    text-align: center; font-size: 12px; font-weight: 600;
    padding: 8px 4px 4px; color: var(--text-light);
    border-bottom: 1px solid var(--border);
}
.weekday-row span:first-child { color: var(--sunday); }
.weekday-row span:last-child { color: var(--saturday); }

.calendar-grid {
    display: grid; grid-template-columns: repeat(7, 1fr);
    gap: 1px; padding: 2px 4px;
}
.cal-cell {
    display: flex; flex-direction: column; align-items: center;
    padding: 4px 1px; min-height: 64px; cursor: pointer;
    border-radius: 8px; position: relative;
}
.cal-cell:active { background: var(--primary-light); }
.cal-cell.selected { background: var(--primary-light); }
.cal-cell.empty { cursor: default; }
.cal-cell.empty:active { background: none; }

.cal-day {
    font-size: 14px; font-weight: 600; width: 28px; height: 28px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 50%; margin-bottom: 2px;
}
.cal-cell.today .cal-day {
    background: var(--primary); color: #fff;
}
.cal-cell.sunday .cal-day { color: var(--sunday); }
.cal-cell.saturday .cal-day { color: var(--saturday); }
.cal-cell.other-month .cal-day { color: #ccc; }

.cal-badges {
    display: flex; flex-direction: column; align-items: center;
    gap: 1px; width: 100%; overflow: hidden;
}
.cal-badge {
    font-size: 9px; background: var(--primary-badge); color: #4a148c;
    padding: 1px 4px; border-radius: 3px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    max-width: 100%; line-height: 1.3;
}
.cal-more {
    font-size: 9px; color: var(--text-light); line-height: 1.3;
}

/* === 타임라인 === */
.timeline-section {
    flex: 1; overflow-y: auto; overflow-x: hidden;
    -webkit-overflow-scrolling: touch;
    border-top: 3px solid var(--primary);
}
.timeline-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 16px; position: sticky; top: 0;
    background: var(--card); z-index: 5;
    border-bottom: 1px solid var(--border);
}
.timeline-date {
    font-size: 15px; font-weight: 700;
}
.timeline-count {
    font-size: 13px; color: var(--primary); font-weight: 600;
}
.timeline-close {
    font-size: 20px; background: none; border: none;
    color: var(--text-light); cursor: pointer; padding: 4px;
}

.timeline-list { padding: 0 12px 20px; }

.res-card {
    display: flex; align-items: flex-start; gap: 12px;
    padding: 14px 0; border-bottom: 1px solid var(--border);
}
.res-time-col {
    flex-shrink: 0; text-align: center; min-width: 52px;
}
.res-time-start {
    font-size: 14px; font-weight: 700; color: var(--text);
}
.res-time-end {
    font-size: 11px; color: var(--text-light); margin-top: 2px;
}
.res-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--primary-badge); margin: 4px auto 0;
}
.res-info { flex: 1; min-width: 0; }
.res-pet {
    font-size: 15px; font-weight: 600; margin-bottom: 3px;
    display: flex; align-items: center; gap: 6px;
}
.res-pet .breed {
    font-size: 12px; font-weight: 400; color: var(--text-light);
}
.res-service {
    font-size: 13px; color: var(--text-light);
}
.res-status {
    display: inline-block; font-size: 11px; padding: 2px 8px;
    border-radius: 10px; font-weight: 600; margin-left: auto;
    flex-shrink: 0;
}
.res-status.confirmed { background: #e3f2fd; color: #1565c0; }
.res-status.completed { background: #e8f5e9; color: #2e7d32; }

.empty-timeline {
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    padding: 60px 20px; color: var(--text-light);
}
.empty-timeline .icon { font-size: 36px; margin-bottom: 8px; }
.empty-timeline p { font-size: 14px; }

/* === 하단 안내 === */
.footer-hint {
    flex-shrink: 0; text-align: center;
    padding: 8px; font-size: 11px; color: #bbb;
    border-top: 1px solid var(--border);
}

/* === 스와이프 힌트 === */
.swipe-hint {
    display: none; position: fixed; top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(0,0,0,0.7); color: #fff;
    padding: 10px 20px; border-radius: 10px;
    font-size: 14px; z-index: 100;
    pointer-events: none;
}
.swipe-hint.show { display: block; }

/* === 로딩 === */
.loading {
    display: flex; align-items: center; justify-content: center;
    padding: 40px; color: var(--text-light); font-size: 14px;
}
.loading::after {
    content: ''; display: inline-block; width: 18px; height: 18px;
    border: 2px solid var(--primary-badge); border-top-color: var(--primary);
    border-radius: 50%; margin-left: 8px;
    animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div id="app">
    <!-- 헤더 -->
    <div class="header">
        <button class="btn-today" onclick="goToday()">오늘</button>
        <div class="month-nav">
            <button onclick="changeMonth(-1)">‹</button>
            <span class="month-label" id="monthLabel"></span>
            <button onclick="changeMonth(1)">›</button>
        </div>
        <div class="header-actions">
            <a href="/logout" style="font-size:13px;color:#999;text-decoration:none;">나가기</a>
        </div>
    </div>

    <!-- 캘린더 -->
    <div class="calendar-section">
        <div class="weekday-row">
            <span>일</span><span>월</span><span>화</span><span>수</span>
            <span>목</span><span>금</span><span>토</span>
        </div>
        <div class="calendar-grid" id="calendarGrid"></div>
    </div>

    <!-- 타임라인 -->
    <div class="timeline-section" id="timelineSection">
        <div id="timelineContent">
            <div class="empty-timeline">
                <div class="icon">📅</div>
                <p>날짜를 선택하세요</p>
            </div>
        </div>
    </div>

    <div class="footer-hint" id="footerHint">읽기 전용 뷰어</div>
</div>

<div class="swipe-hint" id="swipeHint"></div>

<script>
// === 상태 ===
let currentYear, currentMonth;
let selectedDate = null;
let monthData = { counts: {}, names: {} };

const WEEKDAYS_KR = ['일','월','화','수','목','금','토'];
const STATUS_LABEL = { confirmed: '예약', completed: '완료' };

// === 초기화 ===
function init() {
    const now = new Date();
    currentYear = now.getFullYear();
    currentMonth = now.getMonth() + 1;
    loadMonth();
    setupSwipe();
    updateSyncStatus();
}

// === 동기화 상태 표시 ===
async function updateSyncStatus() {
    try {
        const res = await fetch('/api/sync-status');
        const data = await res.json();
        const footer = document.getElementById('footerHint');
        if (!data.has_db) {
            footer.textContent = 'PC에서 동기화가 필요합니다';
            footer.style.color = '#e74c3c';
        } else if (data.last_sync) {
            footer.textContent = `마지막 동기화: ${data.last_sync}`;
        }
    } catch (e) {}
}

// === 월간 데이터 로드 ===
async function loadMonth() {
    updateMonthLabel();
    renderCalendarSkeleton();

    try {
        const res = await fetch(`/api/month?y=${currentYear}&m=${currentMonth}`);
        if (!res.ok) { window.location.href = '/login'; return; }
        monthData = await res.json();
        if (monthData.no_db) {
            document.getElementById('calendarGrid').innerHTML =
                '<div class="empty-timeline" style="grid-column:1/-1"><div class="icon">📡</div><p>PC에서 데이터를 동기화해주세요</p></div>';
            return;
        }
    } catch (e) {
        monthData = { counts: {}, names: {} };
    }
    renderCalendar();
}

function updateMonthLabel() {
    document.getElementById('monthLabel').textContent =
        `${currentYear}.${String(currentMonth).padStart(2,'0')}`;
}

// === 캘린더 렌더링 ===
function renderCalendarSkeleton() {
    document.getElementById('calendarGrid').innerHTML =
        '<div class="loading">불러오는 중</div>';
}

function renderCalendar() {
    const grid = document.getElementById('calendarGrid');
    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;

    // 해당 월 1일의 요일, 마지막 날
    const firstDay = new Date(currentYear, currentMonth - 1, 1).getDay();
    const lastDate = new Date(currentYear, currentMonth, 0).getDate();

    let html = '';

    // 이전 달 빈 칸
    for (let i = 0; i < firstDay; i++) {
        html += '<div class="cal-cell empty"></div>';
    }

    // 날짜 셀
    for (let d = 1; d <= lastDate; d++) {
        const dateStr = `${currentYear}-${String(currentMonth).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        const dow = (firstDay + d - 1) % 7;
        const isToday = dateStr === todayStr;
        const isSelected = dateStr === selectedDate;
        const isSun = dow === 0;
        const isSat = dow === 6;

        let cls = 'cal-cell';
        if (isToday) cls += ' today';
        if (isSelected) cls += ' selected';
        if (isSun) cls += ' sunday';
        if (isSat) cls += ' saturday';

        const names = monthData.names[dateStr] || [];
        const maxBadges = 2;

        let badgesHtml = '';
        for (let i = 0; i < Math.min(names.length, maxBadges); i++) {
            const entry = names[i];
            let label = entry.pet_name;
            if (entry.breed) {
                label += `(${entry.breed.substring(0, 2)}`+ '…)';
                if (label.length > 8) label = label.substring(0, 7) + '…';
            }
            badgesHtml += `<span class="cal-badge">${escHtml(label)}</span>`;
        }
        if (names.length > maxBadges) {
            badgesHtml += `<span class="cal-more">+${names.length - maxBadges}</span>`;
        }

        html += `<div class="${cls}" onclick="selectDate('${dateStr}')">
            <span class="cal-day">${d}</span>
            <div class="cal-badges">${badgesHtml}</div>
        </div>`;
    }

    grid.innerHTML = html;
}

// === 날짜 선택 → 타임라인 ===
async function selectDate(dateStr) {
    selectedDate = dateStr;
    renderCalendar();

    const content = document.getElementById('timelineContent');
    content.innerHTML = '<div class="loading">불러오는 중</div>';

    try {
        const res = await fetch(`/api/day?date=${dateStr}`);
        if (!res.ok) { window.location.href = '/login'; return; }
        const data = await res.json();
        renderTimeline(data);
    } catch (e) {
        content.innerHTML = '<div class="empty-timeline"><div class="icon">⚠️</div><p>데이터를 불러올 수 없습니다</p></div>';
    }

    // 타임라인 스크롤 상단으로
    document.getElementById('timelineSection').scrollTop = 0;
}

function renderTimeline(data) {
    const content = document.getElementById('timelineContent');
    const date = new Date(data.date + 'T00:00:00');
    const dow = WEEKDAYS_KR[date.getDay()];
    const parts = data.date.split('-');
    const dateLabel = `${parts[0]}.${parts[1]}.${parts[2]}(${dow})`;
    const items = data.reservations || [];

    let html = `
        <div class="timeline-header">
            <div>
                <span class="timeline-date">${dateLabel}</span>
                <span class="timeline-count">${items.length}건</span>
            </div>
            <button class="timeline-close" onclick="closeTimeline()">✕</button>
        </div>
    `;

    if (items.length === 0) {
        html += `<div class="empty-timeline">
            <div class="icon">🐾</div>
            <p>예약이 없습니다</p>
        </div>`;
    } else {
        html += '<div class="timeline-list">';
        for (const r of items) {
            const startLabel = formatTime(r.time);
            const endLabel = formatTime(r.end_time);
            const statusCls = r.status || 'confirmed';
            const statusText = STATUS_LABEL[statusCls] || statusCls;
            const breedText = r.breed ? `(${r.breed})` : '';

            html += `
                <div class="res-card">
                    <div class="res-time-col">
                        <div class="res-time-start">${startLabel}</div>
                        <div class="res-time-end">${endLabel}</div>
                        <div class="res-dot"></div>
                    </div>
                    <div class="res-info">
                        <div class="res-pet">
                            🐾 ${escHtml(r.pet_name)}
                            <span class="breed">${escHtml(breedText)}</span>
                        </div>
                        <div class="res-service">${escHtml(r.service)}</div>
                    </div>
                    <span class="res-status ${statusCls}">${statusText}</span>
                </div>
            `;
        }
        html += '</div>';
    }

    content.innerHTML = html;
}

function closeTimeline() {
    selectedDate = null;
    renderCalendar();
    document.getElementById('timelineContent').innerHTML =
        '<div class="empty-timeline"><div class="icon">📅</div><p>날짜를 선택하세요</p></div>';
}

// === 월 이동 ===
function changeMonth(delta) {
    currentMonth += delta;
    if (currentMonth > 12) { currentMonth = 1; currentYear++; }
    if (currentMonth < 1) { currentMonth = 12; currentYear--; }
    selectedDate = null;
    loadMonth();
}

function goToday() {
    const now = new Date();
    currentYear = now.getFullYear();
    currentMonth = now.getMonth() + 1;
    const todayStr = `${currentYear}-${String(currentMonth).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
    selectedDate = todayStr;
    loadMonth().then(() => selectDate(todayStr));
}

// === 스와이프 (월 이동) ===
function setupSwipe() {
    let startX = 0, startY = 0;
    const el = document.querySelector('.calendar-section');

    el.addEventListener('touchstart', e => {
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
    }, { passive: true });

    el.addEventListener('touchend', e => {
        const dx = e.changedTouches[0].clientX - startX;
        const dy = e.changedTouches[0].clientY - startY;
        if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) {
            if (dx > 0) changeMonth(-1);
            else changeMonth(1);
        }
    }, { passive: true });
}

// === 유틸 ===
function formatTime(timeStr) {
    if (!timeStr) return '';
    const [h, m] = timeStr.split(':').map(Number);
    const period = h < 12 ? '오전' : '오후';
    const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
    return `${period} ${h12}:${String(m).padStart(2, '0')}`;
}

function escHtml(s) {
    if (!s) return '';
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// === 시작 ===
init();
</script>
</body>
</html>"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print("=" * 50)
    print("  🐾 애견미용샵 예약 뷰어 (읽기 전용)")
    print(f"  http://localhost:{port}")
    if IS_CLOUD:
        print("  모드: 클라우드 (Render)")
    else:
        print(f"  비밀번호: {VIEWER_PASSWORD}")
        print("  모드: 로컬")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False)
