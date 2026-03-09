"""백업 다운로드 API"""

import json
from datetime import datetime
from flask import Blueprint, Response

backup_bp = Blueprint("backup", __name__)


@backup_bp.route("/api/backup")
def download_backup():
    from web.app import get_db, require_auth
    from flask import session, jsonify

    if not session.get("authenticated"):
        return jsonify({"error": "unauthorized"}), 401

    db = get_db()

    # 고객 데이터
    customers = db.fetch_all("SELECT * FROM customers ORDER BY id")
    customers_list = []
    for row in customers:
        d = dict(row)
        for k, v in d.items():
            if hasattr(v, 'isoformat'):
                d[k] = v.isoformat()
        customers_list.append(d)

    # 예약 데이터
    reservations = db.fetch_all("SELECT * FROM reservations ORDER BY id")
    reservations_list = []
    for row in reservations:
        d = dict(row)
        for k, v in d.items():
            if hasattr(v, 'isoformat'):
                d[k] = v.isoformat()
            elif hasattr(v, 'total_seconds'):
                d[k] = str(v)
        reservations_list.append(d)

    # 전화이력 데이터
    call_history = db.fetch_all("SELECT * FROM call_history ORDER BY id")
    call_history_list = []
    for row in call_history:
        d = dict(row)
        for k, v in d.items():
            if hasattr(v, 'isoformat'):
                d[k] = v.isoformat()
        call_history_list.append(d)

    backup_data = {
        "exported_at": datetime.now().isoformat(),
        "customers": customers_list,
        "reservations": reservations_list,
        "call_history": call_history_list,
    }

    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    json_str = json.dumps(backup_data, ensure_ascii=False, indent=2)

    return Response(
        json_str,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
