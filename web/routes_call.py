"""Tasker 웹훅 + SSE 스트림 + 전화이력 + ADB Bridge 상태"""

import json
import time
import queue
from flask import Blueprint, jsonify, request, Response
from web.app import get_db, require_auth
from web import queries, config
from web.utils.phone_formatter import normalize_phone, format_phone_display

call_bp = Blueprint("call", __name__)

# SSE 이벤트 큐 (브라우저 알림용)
_call_queues = []  # list of queue.Queue

# ADB Bridge 상태
_bridge_status = {"last_seen": 0, "status": "unknown", "device": ""}


@call_bp.route("/api/incoming-call", methods=["POST", "GET"])
def incoming_call():
    """Tasker에서 전화 수신 시 호출하는 웹훅"""
    # API 키 인증
    key = request.args.get("key", "") or request.headers.get("X-API-Key", "")
    if config.TASKER_API_KEY and key != config.TASKER_API_KEY:
        return jsonify({"error": "unauthorized"}), 401

    # 전화번호 추출
    phone = request.form.get("phone") or request.args.get("phone") or ""
    if not phone and request.is_json and request.json:
        phone = request.json.get("phone", "")
    if not phone:
        return jsonify({"error": "no phone"}), 400

    phone = normalize_phone(phone)
    if not phone:
        return jsonify({"error": "invalid phone"}), 400

    db = get_db()

    # 고객 조회
    customer = queries.find_customer_by_phone(db, phone)
    customer_id = customer.id if customer else None
    pet_name = customer.pet_name if customer else ""

    # 전화이력 저장
    queries.add_call_history(db, phone, customer_id, pet_name)

    # SSE로 브라우저에 알림 전송
    event_data = {
        "phone": phone,
        "phone_display": format_phone_display(phone),
        "is_existing": customer is not None,
        "customer_id": customer_id,
        "customer_name": customer.name if customer else "",
        "pet_name": pet_name,
        "breed": customer.breed if customer else "",
    }
    if customer:
        last_visit = queries.get_last_visit_date(db, customer.id)
        stats = queries.get_customer_sales_stats(db, customer.id)
        event_data["last_visit"] = last_visit
        event_data["visit_count"] = stats["count"]
        # 최근 예약 이력 (최대 3건)
        recent = queries.get_customer_reservations(db, customer.id)[:3]
        event_data["recent_reservations"] = [{
            "date": r.date,
            "service": r.service_type,
            "amount": r.amount,
            "status": r.status,
        } for r in recent]

    _broadcast_event(event_data)

    return jsonify({"ok": True, "customer_id": customer_id})


@call_bp.route("/api/call-stream")
@require_auth
def call_stream():
    """SSE 스트림 - 브라우저가 연결하여 전화 알림 수신"""
    q = queue.Queue()
    _call_queues.append(q)

    def generate():
        try:
            # 연결 확인용 초기 이벤트
            yield "data: {\"type\":\"connected\"}\n\n"
            while True:
                try:
                    data = q.get(timeout=30)
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    # keep-alive
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            pass
        finally:
            if q in _call_queues:
                _call_queues.remove(q)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@call_bp.route("/api/call-history")
@require_auth
def call_history():
    db = get_db()
    date_str = request.args.get("date", "")
    if date_str:
        history = queries.get_call_history_by_date(db, date_str)
    else:
        history = queries.get_call_history(db, limit=30)

    for h in history:
        h["phone_display"] = format_phone_display(h.get("phone", ""))
        if h.get("created_at") and hasattr(h["created_at"], "strftime"):
            h["created_at"] = h["created_at"].strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"history": history})


@call_bp.route("/api/bridge-heartbeat", methods=["POST"])
def bridge_heartbeat():
    """ADB Bridge에서 60초마다 호출하는 하트비트"""
    key = request.args.get("key", "") or request.headers.get("X-API-Key", "")
    if config.TASKER_API_KEY and key != config.TASKER_API_KEY:
        return jsonify({"error": "unauthorized"}), 401

    status = request.form.get("status", "ok")
    device = request.form.get("device", "")

    _bridge_status["last_seen"] = time.time()
    _bridge_status["status"] = status
    _bridge_status["device"] = device

    # SSE로 브라우저에 상태 전파
    _broadcast_event({
        "type": "bridge_status",
        "status": status,
        "device": device,
        "alive": True,
    })

    return jsonify({"ok": True})


@call_bp.route("/api/bridge-status")
def bridge_status():
    """ADB Bridge 연결 상태 조회"""
    alive = (time.time() - _bridge_status["last_seen"]) < 90
    return jsonify({
        "status": _bridge_status["status"],
        "device": _bridge_status["device"],
        "alive": alive,
        "last_seen": _bridge_status["last_seen"],
    })


def _broadcast_event(data: dict):
    """모든 SSE 연결에 이벤트 전송"""
    if "type" not in data:
        data["type"] = "incoming_call"
    for q in list(_call_queues):
        try:
            q.put_nowait(data)
        except queue.Full:
            pass
