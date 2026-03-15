"""Google 연락처 연동: OAuth 인증 + 연락처 동기화"""

import logging
from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify, request, redirect, session

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


# ==================== 토큰 관리 ====================

def _get_flow(redirect_uri: str) -> Flow:
    """OAuth Flow 생성"""
    client_config = {
        "web": {
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = redirect_uri
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


def _get_credentials(db) -> Credentials | None:
    """유효한 Credentials 반환. 만료 시 자동 갱신."""
    row = _get_tokens(db)
    if not row:
        return None

    creds = Credentials(
        token=row["access_token"],
        refresh_token=row["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.GOOGLE_CLIENT_ID,
        client_secret=config.GOOGLE_CLIENT_SECRET,
    )

    # 만료 확인 및 갱신
    expires_at = row["expires_at"]
    now = datetime.now(KST)
    if expires_at and hasattr(expires_at, 'timestamp'):
        if not expires_at.tzinfo:
            expires_at = expires_at.replace(tzinfo=KST)
        if now >= expires_at - timedelta(minutes=5):
            try:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                new_expiry = datetime.now(KST) + timedelta(hours=1)
                _save_tokens(db, creds.token, creds.refresh_token or row["refresh_token"], new_expiry)
                log.info("Google token refreshed")
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
    """Google OAuth 시작"""
    if not GOOGLE_AVAILABLE:
        return jsonify({"error": "Google API 패키지가 설치되지 않았습니다"}), 500
    if not config.GOOGLE_CLIENT_ID or not config.GOOGLE_CLIENT_SECRET:
        return jsonify({"error": "Google OAuth가 설정되지 않았습니다"}), 400

    redirect_uri = request.host_url.rstrip("/") + "/google/callback"
    flow = _get_flow(redirect_uri)
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    session["google_oauth_state"] = state
    return redirect(auth_url)


@google_bp.route("/google/callback")
@require_auth
def google_callback():
    """OAuth 콜백 → 토큰 저장"""
    redirect_uri = request.host_url.rstrip("/") + "/google/callback"
    flow = _get_flow(redirect_uri)

    try:
        flow.fetch_token(authorization_response=request.url)
    except Exception as e:
        log.error("Google OAuth token fetch failed: %s", e)
        return "<script>alert('Google 인증 실패');window.close();</script>"

    creds = flow.credentials
    expires_at = datetime.now(KST) + timedelta(hours=1)

    db = get_db()
    _save_tokens(db, creds.token, creds.refresh_token, expires_at)
    log.info("Google OAuth connected successfully")

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

    - google_contact_id가 있으면 UPDATE (기존 메모 병합)
    - 없으면 전화번호로 기존 연락처 검색 → 있으면 UPDATE, 없으면 CREATE
    - 실패해도 예외를 던지지 않음 (로그만)
    """
    if not GOOGLE_AVAILABLE:
        return
    try:
        db = get_db()
        creds = _get_credentials(db)
        if not creds:
            return  # 연동 안 됨, 스킵

        service = _build_people_service(creds)

        if google_contact_id:
            _update_existing_contact(db, service, customer_id, google_contact_id,
                                     pet_name, weight, breed, phone, memo)
        else:
            # 전화번호로 기존 연락처 검색
            existing = _find_contact_by_phone(service, phone)
            if existing:
                resource_name = existing["resourceName"]
                # DB에 resourceName 저장
                db.execute("UPDATE customers SET google_contact_id = ? WHERE id = ?",
                           (resource_name, customer_id))
                _update_existing_contact(db, service, customer_id, resource_name,
                                         pet_name, weight, breed, phone, memo)
            else:
                _create_new_contact(db, service, customer_id,
                                    pet_name, weight, breed, phone, memo)

    except Exception as e:
        log.error("Google contact sync failed for customer %s: %s", customer_id, e)


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
    """기존 연락처 업데이트 (메모 병합)"""
    try:
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

    except Exception as e:
        log.error("Google contact update failed for %s: %s", resource_name, e)


def _create_new_contact(db, service, customer_id: int,
                        pet_name: str, weight, breed: str, phone: str, memo: str):
    """새 연락처 생성"""
    try:
        body = _build_contact_body(pet_name, weight, breed, phone, memo)
        result = service.people().createContact(body=body).execute()
        resource_name = result.get("resourceName", "")

        if resource_name:
            db.execute("UPDATE customers SET google_contact_id = ? WHERE id = ?",
                       (resource_name, customer_id))
            log.info("Google contact created: %s (customer %s)", resource_name, customer_id)

    except Exception as e:
        log.error("Google contact create failed for customer %s: %s", customer_id, e)
