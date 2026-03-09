"""인증 라우트 — 로그인 실패 제한 + 기기 기억하기"""

import time
from datetime import timedelta
from flask import Blueprint, request, session, redirect, url_for, render_template
from web import config

auth_bp = Blueprint("auth", __name__)

# IP별 로그인 실패 기록: { ip: { "count": int, "first_fail": float } }
_login_failures = {}

MAX_FAILURES = 5
LOCKOUT_SECONDS = 600  # 10분


def _get_client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()


def _is_locked(ip):
    """IP가 차단 상태인지 확인. 만료되었으면 자동 해제."""
    rec = _login_failures.get(ip)
    if not rec or rec["count"] < MAX_FAILURES:
        return False
    elapsed = time.time() - rec["first_fail"]
    if elapsed >= LOCKOUT_SECONDS:
        # 차단 시간 지남 → 초기화
        del _login_failures[ip]
        return False
    return True


def _record_failure(ip):
    rec = _login_failures.get(ip)
    now = time.time()
    if rec is None:
        _login_failures[ip] = {"count": 1, "first_fail": now}
    else:
        rec["count"] += 1


def _clear_failures(ip):
    _login_failures.pop(ip, None)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        ip = _get_client_ip()

        if _is_locked(ip):
            error = "로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요."
            return render_template("login.html", error=error)

        pw = request.form.get("password", "")
        if pw == config.VIEWER_PASSWORD:
            session["authenticated"] = True
            _clear_failures(ip)

            # "기기 기억하기" 체크 시 세션 30일 유지
            remember = request.form.get("remember")
            if remember:
                session.permanent = True
            return redirect(url_for("index"))

        _record_failure(ip)
        remaining = MAX_FAILURES - _login_failures.get(ip, {}).get("count", 0)
        if remaining <= 0:
            error = "로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요."
        else:
            error = f"비밀번호가 틀렸습니다 (남은 시도: {remaining}회)"
    return render_template("login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
