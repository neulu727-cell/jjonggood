"""Flask 앱 팩토리"""

import os
import sys
from datetime import timedelta
from flask import Flask, session, redirect, url_for, request, render_template, jsonify
from web.db import DatabaseManager
from web import config


db = None


def get_db() -> DatabaseManager:
    global db
    if db is None or db._pool is None:
        try:
            print(f"[DB] Connecting to: {config.DATABASE_URL[:40]}...")
            db = DatabaseManager(config.DATABASE_URL)
            db.initialize()
            # 기본 서비스 타입 초기화
            from web import queries
            queries.init_default_services(db, config.DEFAULT_SERVICES)
            print("[DB] Connection successful!")
        except Exception as e:
            print(f"[DB] Connection FAILED: {e}")
            db = None
            raise
    return db


def require_auth(f):
    """로그인 필요 데코레이터"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def create_app():
    # 강한 비밀번호 강제: 환경변수 미설정 또는 "0000"이면 시작 거부
    if config.VIEWER_PASSWORD in ("0000", ""):
        print("ERROR: VIEWER_PASSWORD 환경변수를 안전한 비밀번호로 설정하세요. (기본값 '0000' 사용 불가)")
        sys.exit(1)

    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(__file__), "templates"),
                static_folder=os.path.join(os.path.dirname(__file__), "static"))
    app.secret_key = config.SECRET_KEY
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

    # 블루프린트 등록
    from web.routes_auth import auth_bp
    from web.routes_calendar import calendar_bp
    from web.routes_reservation import reservation_bp
    from web.routes_customer import customer_bp
    from web.routes_call import call_bp
    from web.routes_backup import backup_bp
    from web.routes_setup import setup_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(reservation_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(call_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(setup_bp)

    @app.route("/health")
    def health():
        return "OK"

    @app.route("/")
    def index():
        if not session.get("authenticated"):
            return redirect(url_for("auth.login"))
        return render_template("index.html",
                               services=config.DEFAULT_SERVICES,
                               fur_lengths=config.FUR_LENGTHS,
                               breeds=config.COMMON_BREEDS,
                               business_start=config.BUSINESS_HOURS_START,
                               business_end=config.BUSINESS_HOURS_END,
                               slot_interval=config.TIME_SLOT_INTERVAL,
                               tasker_key=config.TASKER_API_KEY)

    @app.route("/api/config")
    def api_config():
        """프론트엔드에서 필요한 설정 반환"""
        if not session.get("authenticated"):
            return jsonify({"error": "unauthorized"}), 401
        return jsonify({
            "services": [{"name": s[0], "duration": s[1], "price": s[2]}
                         for s in config.DEFAULT_SERVICES],
            "fur_lengths": config.FUR_LENGTHS,
            "breeds": config.COMMON_BREEDS,
            "business_start": config.BUSINESS_HOURS_START,
            "business_end": config.BUSINESS_HOURS_END,
            "slot_interval": config.TIME_SLOT_INTERVAL,
        })

    # 앱 시작 시 DB 미리 연결 (Render 부팅 중에 연결해서 첫 요청 지연 방지)
    with app.app_context():
        try:
            get_db()
            print("[APP] DB pre-connected at startup")
        except Exception as e:
            print(f"[APP] DB pre-connect failed (will retry on first request): {e}")

    return app


# gunicorn 진입점
def create_app_gunicorn():
    return create_app()


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
