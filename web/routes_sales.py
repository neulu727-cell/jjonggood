"""매출관리 API"""

from flask import Blueprint, jsonify, request
from web.app import get_db, require_auth
from web import queries
from datetime import datetime

sales_bp = Blueprint("sales", __name__)


@sales_bp.route("/api/sales/month")
@require_auth
def api_sales_month():
    db = get_db()
    y = request.args.get("y", type=int, default=datetime.now().year)
    m = request.args.get("m", type=int, default=datetime.now().month)
    data = queries.get_sales_month_data(db, y, m)
    return jsonify(data)
