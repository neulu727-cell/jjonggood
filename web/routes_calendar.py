"""캘린더 + 타임라인 API"""

from flask import Blueprint, jsonify, request
from web.app import get_db, require_auth
from web import queries
from datetime import datetime

calendar_bp = Blueprint("calendar", __name__)


@calendar_bp.route("/api/month")
@require_auth
def api_month():
    db = get_db()
    y = request.args.get("y", type=int, default=datetime.now().year)
    m = request.args.get("m", type=int, default=datetime.now().month)
    counts = queries.get_reservation_counts_by_month(db, y, m)
    names = queries.get_reservation_names_by_month(db, y, m)
    return jsonify({"counts": counts, "names": names})


@calendar_bp.route("/api/day")
@require_auth
def api_day():
    db = get_db()
    date_str = request.args.get("date", "")
    if not date_str:
        return jsonify({"error": "date required"}), 400
    reservations = queries.get_reservations_by_date(db, date_str)
    items = []
    for r in reservations:
        start_h, start_m = map(int, r.time.split(":"))
        end_minutes = start_h * 60 + start_m + r.duration
        end_h, end_m = divmod(end_minutes, 60)
        items.append({
            "id": r.id,
            "time": r.time,
            "end_time": f"{end_h:02d}:{end_m:02d}",
            "customer_id": r.customer_id,
            "customer_name": r.customer_name,
            "pet_name": r.pet_name,
            "breed": r.breed,
            "customer_phone": r.customer_phone,
            "service": r.service_type,
            "duration": r.duration,
            "amount": r.amount,
            "fur_length": r.fur_length,
            "request": r.request,
            "groomer_memo": r.groomer_memo,
            "status": r.status,
            "completed_at": r.completed_at,
        })
    return jsonify({"date": date_str, "reservations": items})
