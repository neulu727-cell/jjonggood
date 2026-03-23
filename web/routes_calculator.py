"""견적 계산기 API 블루프린트"""

import json
import time
import queue
import threading
from flask import Blueprint, request, jsonify, Response
from web.app import get_db, require_auth, bump_update
from web.pricing import calculate_price
from web import queries

calculator_bp = Blueprint("calculator", __name__)

# --- SSE: 새 요청 알림 ---
_sse_clients = []
_sse_lock = threading.Lock()


def _notify_sse(data: dict):
    """모든 SSE 클라이언트에 이벤트 전송"""
    msg = f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(msg)
            except Exception:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)


# --- Rate limiting (IP 기반, 분당 10회) ---
_rate_limits = {}  # ip -> [timestamps]


def _check_rate_limit(ip: str, max_per_minute: int = 10) -> bool:
    now = time.time()
    if ip not in _rate_limits:
        _rate_limits[ip] = []
    _rate_limits[ip] = [t for t in _rate_limits[ip] if now - t < 60]
    if len(_rate_limits[ip]) >= max_per_minute:
        return False
    _rate_limits[ip].append(now)
    return True


# === 공개 엔드포인트 ===

@calculator_bp.route("/api/calculate-price", methods=["POST"])
def api_calculate_price():
    """가격 계산 (서버 검증용)"""
    data = request.get_json(silent=True) or {}
    service_choice = data.get("service_choice", "위생목욕")
    weight_kg = data.get("weight_kg")
    breed_type = data.get("breed_type", "일반")
    clipping_length = data.get("clipping_length", "")
    face_cut = bool(data.get("face_cut", False))

    try:
        weight_kg = float(weight_kg) if weight_kg else 0
    except (ValueError, TypeError):
        weight_kg = 0

    price, actual_service = calculate_price(
        service_choice, weight_kg, breed_type, clipping_length, face_cut
    )
    return jsonify({
        "estimated_price": price,
        "actual_service": actual_service,
    })


@calculator_bp.route("/api/grooming-request", methods=["POST"])
def api_grooming_request():
    """견적 요청 전송"""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
    ip = ip.split(",")[0].strip()
    if not _check_rate_limit(ip):
        return jsonify({"error": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요."}), 429

    data = request.get_json(silent=True) or {}
    breed = (data.get("breed") or "").strip()
    service_choice = data.get("service_choice", "위생목욕")

    if not breed:
        return jsonify({"error": "견종을 입력해주세요."}), 400

    try:
        weight_kg = float(data.get("weight_kg", 0))
    except (ValueError, TypeError):
        weight_kg = 0

    breed_type = data.get("breed_type", "일반")
    clipping_length = data.get("clipping_length", "")
    face_cut = bool(data.get("face_cut", False))
    customer_name = (data.get("customer_name") or "").strip()[:50]
    customer_phone = (data.get("customer_phone") or "").strip()[:20]
    memo = (data.get("memo") or "").strip()[:500]

    price, actual_service = calculate_price(
        service_choice, weight_kg, breed_type, clipping_length, face_cut
    )

    db = get_db()
    req_id = queries.create_grooming_request(
        db, breed=breed, weight=weight_kg,
        service_type=service_choice, actual_service=actual_service,
        clipping_length=clipping_length, face_cut=face_cut,
        matting="none", fur_length="",
        estimated_price=price, customer_name=customer_name,
        customer_phone=customer_phone, memo=memo,
    )

    bump_update()

    # SSE 알림
    _notify_sse({
        "type": "new_request",
        "id": req_id,
        "breed": breed,
        "service_type": service_choice,
        "actual_service": actual_service,
        "estimated_price": price,
        "customer_name": customer_name,
    })

    return jsonify({"ok": True, "id": req_id, "estimated_price": price})


# === 관리자 엔드포인트 ===

@calculator_bp.route("/api/grooming-requests")
@require_auth
def api_grooming_requests():
    """요청 목록 조회"""
    status = request.args.get("status")
    limit = min(int(request.args.get("limit", 50)), 200)
    db = get_db()
    rows = queries.get_grooming_requests(db, status=status, limit=limit)
    # datetime → string
    for r in rows:
        if r.get("created_at") and hasattr(r["created_at"], "strftime"):
            r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")
    return jsonify(rows)


@calculator_bp.route("/api/grooming-requests/stream")
@require_auth
def api_grooming_requests_stream():
    """SSE 스트림 (실시간 알림)"""
    q = queue.Queue(maxsize=50)
    with _sse_lock:
        _sse_clients.append(q)

    def generate():
        try:
            # 초기 pending 수 전송
            db = get_db()
            cnt = queries.get_pending_request_count(db)
            yield f"data: {json.dumps({'type': 'init', 'pending_count': cnt})}\n\n"
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield msg
                except queue.Empty:
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            pass
        finally:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@calculator_bp.route("/api/grooming-requests/<int:req_id>/status", methods=["PUT"])
@require_auth
def api_update_grooming_request_status(req_id):
    """상태 변경"""
    data = request.get_json(silent=True) or {}
    status = data.get("status", "")
    if status not in ("confirmed", "dismissed"):
        return jsonify({"error": "Invalid status"}), 400

    db = get_db()
    queries.update_grooming_request_status(db, req_id, status)
    bump_update()
    return jsonify({"ok": True})


@calculator_bp.route("/api/grooming-requests/pending-count")
@require_auth
def api_pending_count():
    db = get_db()
    cnt = queries.get_pending_request_count(db)
    return jsonify({"count": cnt})
