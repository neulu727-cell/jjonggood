"""예약 CRUD API"""

import re
from flask import Blueprint, jsonify, request
from web.app import get_db, require_auth
from web import queries

reservation_bp = Blueprint("reservation", __name__)


@reservation_bp.route("/api/reservation", methods=["POST"])
@require_auth
def create_reservation():
    db = get_db()
    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400

    required = ["customer_id", "date", "time", "service_type"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"{field} required"}), 400

    # 날짜 형식 검증 (YYYY-MM-DD)
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(data["date"])):
        return jsonify({"error": "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD)"}), 400

    # 시간 형식 검증 (HH:MM)
    if not re.match(r"^\d{1,2}:\d{2}$", str(data["time"])):
        return jsonify({"error": "시간 형식이 올바르지 않습니다 (HH:MM)"}), 400

    # 숫자 필드 안전 변환
    try:
        customer_id = int(data["customer_id"])
        duration = int(data.get("duration", 60))
        amount = int(data.get("amount", 0))
        quoted_amount = int(data.get("quoted_amount", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "숫자 필드 값이 올바르지 않습니다"}), 400

    # customer_id 존재 확인
    if not queries.get_customer_by_id(db, customer_id):
        return jsonify({"error": "존재하지 않는 고객입니다"}), 404

    rid = queries.create_reservation(
        db,
        customer_id=customer_id,
        date=data["date"],
        time=data["time"],
        service_type=data["service_type"][:50],
        duration=duration,
        request=data.get("request", "")[:500],
        amount=amount,
        fur_length=data.get("fur_length", "")[:20],
        quoted_amount=quoted_amount,
        payment_method=data.get("payment_method", "")[:30],
    )
    return jsonify({"ok": True, "id": rid})


@reservation_bp.route("/api/reservation/<int:rid>", methods=["GET"])
@require_auth
def get_reservation(rid):
    db = get_db()
    r = queries.get_reservation_by_id(db, rid)
    if not r:
        return jsonify({"error": "not found"}), 404
    customer = queries.get_customer_by_id(db, r.customer_id)
    start_h, start_m = map(int, r.time.split(":"))
    end_minutes = start_h * 60 + start_m + r.duration
    end_h, end_m = divmod(end_minutes, 60)
    return jsonify({
        "id": r.id,
        "customer_id": r.customer_id,
        "customer_name": r.customer_name,
        "pet_name": r.pet_name,
        "breed": r.breed,
        "customer_phone": r.customer_phone,
        "date": r.date,
        "time": r.time,
        "end_time": f"{end_h:02d}:{end_m:02d}",
        "service_type": r.service_type,
        "duration": r.duration,
        "amount": r.amount,
        "quoted_amount": r.quoted_amount,
        "payment_method": r.payment_method,
        "fur_length": r.fur_length,
        "request": r.request,
        "groomer_memo": r.groomer_memo,
        "customer_memo": customer.memo if customer else "",
        "status": r.status,
        "completed_at": r.completed_at,
    })


@reservation_bp.route("/api/reservation/<int:rid>", methods=["PUT"])
@require_auth
def update_reservation(rid):
    db = get_db()
    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400

    queries.update_reservation_with_history(db, rid, **data)
    return jsonify({"ok": True})


@reservation_bp.route("/api/reservation/<int:rid>/status", methods=["PUT"])
@require_auth
def update_status(rid):
    db = get_db()
    data = request.get_json()
    status = data.get("status", "")
    if status not in ("confirmed", "completed", "cancelled", "no_show"):
        return jsonify({"error": "invalid status"}), 400

    if status == "cancelled":
        queries.delete_reservation(db, rid)
    else:
        queries.update_reservation_status(db, rid, status)
    return jsonify({"ok": True})


@reservation_bp.route("/api/reservation/<int:rid>/memo", methods=["PUT"])
@require_auth
def update_memo(rid):
    db = get_db()
    data = request.get_json()
    memo = data.get("memo", "")
    queries.update_reservation_memo(db, rid, memo)
    return jsonify({"ok": True})


@reservation_bp.route("/api/reservation/<int:rid>/edits", methods=["GET"])
@require_auth
def get_edits(rid):
    db = get_db()
    edits = queries.get_reservation_edits(db, rid)
    for e in edits:
        if e.get("created_at") and hasattr(e["created_at"], "strftime"):
            e["created_at"] = e["created_at"].strftime("%Y-%m-%d %H:%M")
    return jsonify({"edits": edits})
