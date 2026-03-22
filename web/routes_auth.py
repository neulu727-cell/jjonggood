"""인증 라우트 — 비활성화 (로그인 불필요, 자동 접근 허용)"""

from flask import Blueprint, redirect, url_for, session

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """로그인 페이지 비활성화 — 관리자로 리다이렉트"""
    session["authenticated"] = True
    return redirect(url_for("admin_index"))


@auth_bp.route("/logout")
def logout():
    """로그아웃 비활성화 — 관리자로 리다이렉트"""
    return redirect(url_for("admin_index"))
