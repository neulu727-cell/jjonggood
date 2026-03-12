"""Flask 앱 팩토리"""

import hashlib
import gzip
import io
import logging
import os
import sys
import time
from datetime import timedelta
from flask import Flask, session, redirect, url_for, request, render_template, jsonify, g
from web.db import DatabaseManager
from web import config

# --- 구조화 로깅 설정 ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("jjonggood")

db = None


def get_db() -> DatabaseManager:
    global db
    if db is None or db._pool is None:
        try:
            log.info("DB connecting...")
            db = DatabaseManager(config.DATABASE_URL)
            db.initialize()
            # 기본 서비스 타입 초기화
            from web import queries
            queries.init_default_services(db, config.DEFAULT_SERVICES)
            log.info("DB connected")
        except Exception as e:
            log.error("DB connection FAILED: %s", e)
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
    # 필수 환경변수 검증
    if not config.DATABASE_URL:
        log.critical("DATABASE_URL 환경변수를 설정하세요.")
        sys.exit(1)
    if config.VIEWER_PASSWORD in ("0000", ""):
        log.critical("VIEWER_PASSWORD를 안전한 비밀번호로 설정하세요.")
        sys.exit(1)
    if config.SECRET_KEY == "dev-secret-change-me":
        log.warning("SECRET_KEY가 기본값입니다. 프로덕션에서는 반드시 변경하세요.")

    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(__file__), "templates"),
                static_folder=os.path.join(os.path.dirname(__file__), "static"))
    app.secret_key = config.SECRET_KEY
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB 업로드 제한

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

    # --- 정적 파일 캐시 버스팅: url_for('static') → ?v=해시 자동 추가 ---
    _static_hashes = {}

    @app.context_processor
    def _static_cache_bust():
        def static_url(filename):
            if filename not in _static_hashes:
                fpath = os.path.join(app.static_folder, filename)
                if os.path.exists(fpath):
                    h = hashlib.md5(open(fpath, 'rb').read()).hexdigest()[:8]
                    _static_hashes[filename] = h
                else:
                    _static_hashes[filename] = "0"
            return url_for('static', filename=filename) + '?v=' + _static_hashes[filename]
        return dict(static_url=static_url)

    @app.route("/health")
    def health():
        try:
            d = get_db()
            d.fetch_one("SELECT 1")
            return jsonify({"status": "ok"}), 200
        except Exception:
            return jsonify({"status": "error"}), 503

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

    @app.after_request
    def add_security_headers(response):
        # --- 보안 헤더 ---
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )

        # --- 캐시 제어 ---
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        # --- gzip 압축 (text/html, application/json, text/css, application/javascript) ---
        if (response.status_code == 200
                and not response.direct_passthrough
                and "gzip" in request.headers.get("Accept-Encoding", "")
                and response.content_type
                and any(t in response.content_type for t in ("text/", "application/json", "application/javascript"))):
            data = response.get_data()
            if len(data) > 512:  # 512바이트 이상만 압축
                buf = io.BytesIO()
                with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=6) as gz:
                    gz.write(data)
                compressed = buf.getvalue()
                if len(compressed) < len(data):
                    response.set_data(compressed)
                    response.headers["Content-Encoding"] = "gzip"
                    response.headers["Content-Length"] = len(compressed)
                    response.headers["Vary"] = "Accept-Encoding"
        return response

    # --- 요청 로깅 (endpoint, status, duration) ---
    @app.before_request
    def _start_timer():
        g._req_start = time.time()

    @app.after_request
    def _log_request(response):
        if hasattr(g, '_req_start') and not request.path.startswith("/static/"):
            duration_ms = (time.time() - g._req_start) * 1000
            log.info("%s %s %s %.0fms", request.method, request.path,
                     response.status_code, duration_ms)
        return response

    # 앱 시작 시 DB 미리 연결 (Render 부팅 중에 연결해서 첫 요청 지연 방지)
    with app.app_context():
        try:
            get_db()
            log.info("DB pre-connected at startup")
        except Exception as e:
            log.warning("DB pre-connect failed (will retry on first request): %s", e)

    return app


# gunicorn 진입점
def create_app_gunicorn():
    return create_app()


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
