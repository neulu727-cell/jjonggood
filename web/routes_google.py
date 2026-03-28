"""Google 연락처 연동: OAuth 인증 + 연락처 동기화"""

import logging
from datetime import datetime, timedelta, timezone
import json
from flask import Blueprint, jsonify, request, redirect, session, Response

from web.app import get_db, require_auth
from web import config

log = logging.getLogger("jjonggood.google")

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    log.warning("Google API 패키지 미설치 — 연락처 연동 비활성화")
    GOOGLE_AVAILABLE = False

google_bp = Blueprint("google", __name__)

SCOPES = ["https://www.googleapis.com/auth/contacts"]

KST = timezone(timedelta(hours=9))


def _build_redirect_uri() -> str:
    """프록시 뒤에서도 https 리디렉션 URI를 생성"""
    url = request.host_url.rstrip("/") + "/google/callback"
    if url.startswith("http://") and "localhost" not in url:
        url = "https://" + url[7:]
    return url


# ==================== 토큰 관리 ====================

def _get_flow(redirect_uri: str):
    """OAuth Flow 생성 (PKCE 비활성화 — 세션 유실 시 무한재귀 방지)"""
    client_config = {
        "web": {
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES, code_verifier=None)
    flow.redirect_uri = redirect_uri
    flow.code_verifier = None  # PKCE 비활성화
    return flow


def _save_tokens(db, access_token: str, refresh_token: str, expires_at: datetime):
    """토큰 저장 (항상 1행만 유지)"""
    db.execute("DELETE FROM google_tokens")
    db.execute(
        "INSERT INTO google_tokens (access_token, refresh_token, expires_at) VALUES (?, ?, ?)",
        (access_token, refresh_token, expires_at),
    )


def _get_tokens(db):
    """저장된 토큰 조회"""
    return db.fetch_one("SELECT * FROM google_tokens ORDER BY id DESC LIMIT 1")


def _get_credentials(db):
    """유효한 Credentials 반환. 만료 시 자동 갱신."""
    row = _get_tokens(db)
    if not row:
        log.warning("Google credentials: no tokens found in DB")
        return None

    access_token = row["access_token"]
    refresh_token = row["refresh_token"]

    if not refresh_token:
        log.warning("Google credentials: no refresh_token — re-auth needed")
        return None

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.GOOGLE_CLIENT_ID,
        client_secret=config.GOOGLE_CLIENT_SECRET,
    )

    # 만료 확인 및 갱신 — 항상 refresh 시도 (토큰이 1시간 만료이므로)
    needs_refresh = False
    expires_at = row["expires_at"]
    now = datetime.now(KST)

    if expires_at is None:
        needs_refresh = True
    elif isinstance(expires_at, str):
        # DB에서 문자열로 온 경우 파싱
        try:
            expires_at = datetime.fromisoformat(expires_at)
        except (ValueError, TypeError):
            needs_refresh = True
    if not needs_refresh and expires_at is not None:
        if not getattr(expires_at, 'tzinfo', None):
            expires_at = expires_at.replace(tzinfo=KST)
        if now >= expires_at - timedelta(minutes=5):
            needs_refresh = True

    if needs_refresh:
        try:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            new_expiry = datetime.now(KST) + timedelta(hours=1)
            _save_tokens(db, creds.token, creds.refresh_token or refresh_token, new_expiry)
            log.info("Google token refreshed successfully")
        except Exception as e:
            log.error("Google token refresh failed: %s", e)
            return None

    return creds


def _build_people_service(creds):
    """People API 서비스 객체 생성"""
    return build("people", "v1", credentials=creds, cache_discovery=False)


# ==================== OAuth 라우트 ====================

@google_bp.route("/google/connect")
@require_auth
def google_connect():
    """Google OAuth 시작 (PKCE 없이 직접 URL 생성)"""
    if not GOOGLE_AVAILABLE:
        return jsonify({"error": "Google API 패키지가 설치되지 않았습니다"}), 500
    if not config.GOOGLE_CLIENT_ID or not config.GOOGLE_CLIENT_SECRET:
        return jsonify({"error": "Google OAuth가 설정되지 않았습니다"}), 400

    redirect_uri = _build_redirect_uri()
    from urllib.parse import urlencode
    params = urlencode({
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    })
    auth_url = f"https://accounts.google.com/o/oauth2/auth?{params}"
    return redirect(auth_url)


@google_bp.route("/google/callback")
@require_auth
def google_callback():
    """OAuth 콜백 → 토큰 저장 (Flow 우회, 직접 HTTP 교환)"""
    import sys, traceback
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(300)
    try:
        return _do_google_callback()
    except RecursionError:
        tb = traceback.format_exc()
        log.error("Google callback RecursionError:\n%s", tb)
        log.error("redirect_uri=%s, host=%s", _build_redirect_uri(), request.host_url)
        # traceback 마지막 몇 줄을 alert에 표시하여 디버그
        short_tb = "\\n".join(tb.strip().split("\\n")[-6:])
        return f"<script>alert('재귀오류 traceback:\\n{short_tb}');window.location='/';</script>"
    except Exception as e:
        log.error("Google callback error: %s", e)
        return f"<script>alert('Google 인증 실패: {e}');window.location='/';</script>"
    finally:
        sys.setrecursionlimit(old_limit)


def _do_google_callback():
    import requests as http_requests

    redirect_uri = _build_redirect_uri()
    log.info("Google callback: redirect_uri=%s, host_url=%s", redirect_uri, request.host_url)
    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        log.error("Google OAuth error: %s", error)
        return f"<script>alert('Google 인증 거부: {error}');window.location='/';</script>"

    if not code:
        return "<script>alert('Google 인증 실패: 인증 코드가 없습니다');window.location='/';</script>"

    # Flow.fetch_token 대신 직접 POST로 토큰 교환 (무한재귀 방지)
    token_resp = http_requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": config.GOOGLE_CLIENT_ID,
        "client_secret": config.GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }, timeout=15)

    token_data = token_resp.json()

    if "error" in token_data:
        log.error("Google token exchange failed: %s — redirect_uri=%s", token_data, redirect_uri)
        msg = token_data.get("error_description", token_data["error"])
        return f"<script>alert('Google 인증 실패: {msg}');window.location='/';</script>"

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")
    expires_at = datetime.now(KST) + timedelta(seconds=token_data.get("expires_in", 3600))

    db = get_db()
    _save_tokens(db, access_token, refresh_token, expires_at)
    log.info("Google OAuth connected successfully (direct exchange)")

    return "<script>alert('Google 연락처 연동 완료!');window.location='/';</script>"


@google_bp.route("/google/status")
@require_auth
def google_status():
    """연동 상태 확인"""
    db = get_db()
    row = _get_tokens(db)
    connected = row is not None
    return jsonify({"connected": connected})


@google_bp.route("/google/disconnect", methods=["POST"])
@require_auth
def google_disconnect():
    """연동 해제"""
    db = get_db()
    db.execute("DELETE FROM google_tokens")
    log.info("Google OAuth disconnected")
    return jsonify({"ok": True})


@google_bp.route("/google/debug")
@require_auth
def google_debug():
    """Google 연동 상태 디버깅"""
    info = {"google_available": GOOGLE_AVAILABLE}

    if not GOOGLE_AVAILABLE:
        info["error"] = "Google API 패키지 미설치"
        return jsonify(info)

    info["client_id_set"] = bool(config.GOOGLE_CLIENT_ID)
    info["client_secret_set"] = bool(config.GOOGLE_CLIENT_SECRET)

    db = get_db()
    row = _get_tokens(db)
    if not row:
        info["tokens"] = None
        info["error"] = "토큰 없음 — /google/connect 필요"
        return jsonify(info)

    info["tokens"] = {
        "has_access_token": bool(row["access_token"]),
        "has_refresh_token": bool(row["refresh_token"]),
        "expires_at": str(row["expires_at"]),
        "expires_at_type": type(row["expires_at"]).__name__,
    }

    # 직접 refresh 시도하여 에러 메시지 캡처
    refresh_token = row["refresh_token"]
    access_token = row["access_token"]
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.GOOGLE_CLIENT_ID,
        client_secret=config.GOOGLE_CLIENT_SECRET,
    )

    try:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        info["refresh_result"] = "OK"
        info["credentials_valid"] = True
        # refresh 성공 → 토큰 갱신 저장
        new_expiry = datetime.now(KST) + timedelta(hours=1)
        _save_tokens(db, creds.token, creds.refresh_token or refresh_token, new_expiry)
    except Exception as e:
        info["refresh_result"] = f"FAILED: {e}"
        info["credentials_valid"] = False
        info["fix"] = "Google 연동을 다시 해주세요 (/google/connect)"
        return jsonify(info)

    try:
        service = _build_people_service(creds)
        result = service.people().connections().list(
            resourceName="people/me",
            pageSize=1,
            personFields="names",
        ).execute()
        info["api_test"] = "OK"
        info["total_contacts"] = result.get("totalPeople", result.get("totalItems", "?"))
    except Exception as e:
        info["api_test"] = f"FAILED: {e}"

    return jsonify(info)


@google_bp.route("/google/sync-incremental")
@require_auth
def google_sync_incremental():
    """google_contact_id가 없는 고객만 동기화 (증분)"""
    if not GOOGLE_AVAILABLE:
        return jsonify({"error": "Google API 패키지가 설치되지 않았습니다"}), 500

    db = get_db()
    creds = _get_credentials(db)
    if not creds:
        return jsonify({"error": "Google 연동이 필요합니다"}), 400

    customers = db.fetch_all(
        "SELECT * FROM customers WHERE phone != 'BOSS' AND (google_contact_id IS NULL OR google_contact_id = '') ORDER BY id"
    )
    total = len(customers)

    if total == 0:
        return jsonify({"ok": True, "message": "동기화할 고객이 없습니다 (모두 동기화 완료)"})

    def generate():
        success = 0
        fail = 0
        synced_names = []
        errors = []

        yield f"data: {json.dumps({'type': 'start', 'total': total}, ensure_ascii=False)}\n\n"

        for i, c in enumerate(customers):
            ok, msg = sync_contact_to_google(
                c["id"], c["pet_name"], c["weight"], c["breed"],
                c["phone"], c.get("memo", ""), c.get("google_contact_id"),
            )
            weight_str = f" {c['weight']}kg" if c.get("weight") else ""
            breed_str = f" {c['breed']}" if c.get("breed") else ""
            name = f"{c['pet_name']}{weight_str}{breed_str}"

            if ok:
                success += 1
                synced_names.append(name)
                yield f"data: {json.dumps({'type': 'progress', 'i': i + 1, 'total': total, 'name': name, 'ok': True}, ensure_ascii=False)}\n\n"
            else:
                fail += 1
                errors.append(f"{name}: {msg}")
                yield f"data: {json.dumps({'type': 'progress', 'i': i + 1, 'total': total, 'name': name, 'ok': False, 'error': msg}, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'success': success, 'fail': fail, 'synced_names': synced_names, 'errors': errors[:3]}, ensure_ascii=False)}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@google_bp.route("/google/sync-batch", methods=["POST"])
@require_auth
def google_sync_batch():
    """고객 배치 동기화 — offset/limit으로 5명씩 처리"""
    if not GOOGLE_AVAILABLE:
        return jsonify({"error": "Google API 패키지가 설치되지 않았습니다"}), 500

    db = get_db()
    creds = _get_credentials(db)
    if not creds:
        return jsonify({"error": "Google 연동이 필요합니다"}), 400

    data = request.get_json() or {}
    offset = int(data.get("offset", 0))
    limit = min(int(data.get("limit", 3)), 5)  # 기본 3명, 최대 5명 (rate limit 방지)

    all_customers = db.fetch_all("SELECT * FROM customers WHERE phone != 'BOSS' ORDER BY id")
    total = len(all_customers)
    batch = all_customers[offset:offset + limit]

    import time
    results = []
    for i, c in enumerate(batch):
        if i > 0:
            time.sleep(1.5)  # Rate limit 방지: 건당 1.5초 간격
        ok, msg = sync_contact_to_google(
            c["id"], c["pet_name"], c["weight"], c["breed"],
            c["phone"], c.get("memo", ""), c.get("google_contact_id"),
        )
        weight_str = f" {c['weight']}kg" if c.get("weight") else ""
        breed_str = f" {c['breed']}" if c.get("breed") else ""
        name = f"{c['pet_name']}{weight_str}{breed_str}"
        results.append({"name": name, "ok": ok, "error": "" if ok else msg})

    return jsonify({
        "total": total,
        "offset": offset,
        "processed": len(batch),
        "results": results,
        "done": offset + limit >= total,
    })


# ==================== 연락처 동기화 ====================

def _merge_notes(existing_notes: str, app_memo: str) -> str:
    """기존 Google 연락처 메모와 앱 메모를 병합.

    - 기존 메모 줄들을 보존
    - 앱 메모 줄 중 기존에 없는 내용만 추가
    - 중복 줄 제거
    """
    if not existing_notes and not app_memo:
        return ""
    if not existing_notes:
        return app_memo.strip()
    if not app_memo:
        return existing_notes.strip()

    existing_lines = [l.strip() for l in existing_notes.strip().splitlines() if l.strip()]
    app_lines = [l.strip() for l in app_memo.strip().splitlines() if l.strip()]

    # 기존 줄 집합 (중복 판단용)
    existing_set = set(existing_lines)

    # 기존 줄 유지 + 앱 메모에서 새로운 줄만 추가
    merged = list(existing_lines)
    for line in app_lines:
        if line not in existing_set:
            merged.append(line)
            existing_set.add(line)

    return "\n".join(merged)


def _build_contact_body(pet_name: str, weight, breed: str, phone: str, memo: str) -> dict:
    """People API 용 연락처 body 생성"""
    weight_str = f" {weight}kg" if weight else ""
    breed_str = f" {breed}" if breed else ""
    display_name = f"{pet_name}{weight_str}{breed_str}".strip()

    body = {
        "names": [{"givenName": display_name}],
        "phoneNumbers": [{"value": phone, "type": "mobile"}],
    }
    if memo:
        body["biographies"] = [{"value": memo, "contentType": "TEXT_PLAIN"}]
    return body


def sync_contact_to_google(customer_id: int, pet_name: str, weight, breed: str,
                           phone: str, memo: str, google_contact_id: str = None):
    """고객 데이터를 Google 연락처에 동기화.

    Returns: (success: bool, message: str)
    """
    if not GOOGLE_AVAILABLE:
        return False, "Google API 패키지 미설치"

    try:
        db = get_db()
        creds = _get_credentials(db)
        if not creds:
            return False, "Google 연동이 필요합니다"

        service = _build_people_service(creds)

        # resourceName 형식 보정: "people/" 접두사 필수
        if google_contact_id and not google_contact_id.startswith("people/"):
            google_contact_id = f"people/{google_contact_id}"
            db.execute("UPDATE customers SET google_contact_id = ? WHERE id = ?",
                       (google_contact_id, customer_id))

        if google_contact_id:
            _update_existing_contact(db, service, customer_id, google_contact_id,
                                     pet_name, weight, breed, phone, memo)
        else:
            existing = _find_contact_by_phone(service, phone)
            if existing:
                resource_name = existing["resourceName"]
                db.execute("UPDATE customers SET google_contact_id = ? WHERE id = ?",
                           (resource_name, customer_id))
                _update_existing_contact(db, service, customer_id, resource_name,
                                         pet_name, weight, breed, phone, memo)
            else:
                _create_new_contact(db, service, customer_id,
                                    pet_name, weight, breed, phone, memo)

        return True, "Google 연락처 동기화 완료"

    except Exception as e:
        log.error("Google contact sync failed for customer %s: %s", customer_id, e)
        return False, str(e)


def _find_contact_by_phone(service, phone: str):
    """전화번호로 Google 연락처 검색"""
    try:
        results = service.people().searchContacts(
            query=phone,
            readMask="names,phoneNumbers,biographies",
            pageSize=5,
        ).execute()

        for result in results.get("results", []):
            person = result.get("person", {})
            for pn in person.get("phoneNumbers", []):
                # 전화번호 정규화 비교
                stored = pn.get("value", "").replace("-", "").replace(" ", "").replace("+82", "0")
                target = phone.replace("-", "").replace(" ", "")
                if stored == target or stored.endswith(target[-8:]):
                    return person
    except Exception as e:
        log.warning("Google contact search failed: %s", e)
    return None


def _get_existing_notes(service, resource_name: str) -> str:
    """기존 연락처의 메모(biographies) 조회"""
    try:
        person = service.people().get(
            resourceName=resource_name,
            personFields="biographies",
        ).execute()
        bios = person.get("biographies", [])
        if bios:
            return bios[0].get("value", "")
    except Exception as e:
        log.warning("Failed to get existing notes for %s: %s", resource_name, e)
    return ""


def _update_existing_contact(db, service, customer_id: int, resource_name: str,
                              pet_name: str, weight, breed: str, phone: str, memo: str):
    """기존 연락처 업데이트 (메모 병합). 실패 시 예외 전파."""
    # 기존 연락처 전체 조회 (etag 필요)
    person = service.people().get(
        resourceName=resource_name,
        personFields="names,phoneNumbers,biographies,metadata",
    ).execute()

    # 기존 메모 가져와서 병합
    existing_notes = ""
    bios = person.get("biographies", [])
    if bios:
        existing_notes = bios[0].get("value", "")

    merged_memo = _merge_notes(existing_notes, memo)

    body = _build_contact_body(pet_name, weight, breed, phone, merged_memo)
    body["etag"] = person.get("etag", "")

    service.people().updateContact(
        resourceName=resource_name,
        updatePersonFields="names,phoneNumbers,biographies",
        body=body,
    ).execute()

    log.info("Google contact updated: %s (customer %s)", resource_name, customer_id)


def _create_new_contact(db, service, customer_id: int,
                        pet_name: str, weight, breed: str, phone: str, memo: str):
    """새 연락처 생성. 실패 시 예외 전파."""
    body = _build_contact_body(pet_name, weight, breed, phone, memo)
    result = service.people().createContact(body=body).execute()
    resource_name = result.get("resourceName", "")

    if resource_name:
        db.execute("UPDATE customers SET google_contact_id = ? WHERE id = ?",
                   (resource_name, customer_id))
        log.info("Google contact created: %s (customer %s)", resource_name, customer_id)
