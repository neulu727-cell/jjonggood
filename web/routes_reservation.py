"""예약 CRUD API"""

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

    rid = queries.create_reservation(
        db,
        customer_id=int(data["customer_id"]),
        date=data["date"],
        time=data["time"],
        service_type=data["service_type"],
        duration=int(data.get("duration", 60)),
        request=data.get("request", ""),
        amount=int(data.get("amount", 0)),
        fur_length=data.get("fur_length", ""),
    )
    return jsonify({"ok": True, "id": rid})


@reservation_bp.route("/api/reservation/<int:rid>", methods=["GET"])
@require_auth
def get_reservation(rid):
    db = get_db()
    r = queries.get_reservation_by_id(db, rid)
    if not r:
        return jsonify({"error": "not found"}), 404
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
        "fur_length": r.fur_length,
        "request": r.request,
        "groomer_memo": r.groomer_memo,
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
