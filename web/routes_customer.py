"""고객 CRUD API"""

import logging
from flask import Blueprint, jsonify, request
from web.app import get_db, require_auth
from web import queries
from web.utils.phone_formatter import normalize_phone, format_phone_display

log = logging.getLogger("jjonggood.customer")

customer_bp = Blueprint("customer", __name__)


def _safe_float(val):
    """안전한 float 변환. 빈값이면 None, 변환 불가시 None."""
    if not val and val != 0:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


@customer_bp.route("/api/customers/search")
@require_auth
def search_customers():
    db = get_db()
    keyword = request.args.get("q", "").strip()
    sort = request.args.get("sort", "name")  # "name" or "recent"

    SORT_OPTIONS = {
        "recent": "last_visit DESC NULLS LAST",
        "name": "LOWER(c.pet_name)",
    }
    order = SORT_OPTIONS.get(sort, SORT_OPTIONS["name"])

    base_query = """
        SELECT c.*,
               MAX(CASE WHEN r.status='completed' THEN r.date END) AS last_visit,
               COUNT(CASE WHEN r.status='completed' AND r.amount>0 THEN 1 END) AS visit_count,
               COALESCE(SUM(CASE WHEN r.status='completed' AND r.amount>0 THEN r.amount END),0) AS total_sales
        FROM customers c
        LEFT JOIN reservations r ON r.customer_id = c.id
    """

    if keyword:
        like = f"%{keyword}%"
        rows = db.fetch_all(
            base_query + " WHERE c.name ILIKE ? OR c.phone ILIKE ? OR c.pet_name ILIKE ?"
            " GROUP BY c.id ORDER BY " + order,
            (like, like, like))
    else:
        rows = db.fetch_all(
            base_query + " GROUP BY c.id ORDER BY " + order)

    result = []
    for row in rows:
        d = dict(row)
        lv = d.get("last_visit")
        if lv and hasattr(lv, 'strftime'):
            lv = lv.strftime("%Y-%m-%d")
        elif lv:
            lv = str(lv)
        result.append({
            "id": d["id"],
            "name": d.get("name", ""),
            "phone": d.get("phone", ""),
            "phone_display": format_phone_display(d.get("phone", "")),
            "pet_name": d.get("pet_name", ""),
            "breed": d.get("breed", ""),
            "weight": d.get("weight"),
            "age": d.get("age"),
            "notes": d.get("notes", ""),
            "memo": d.get("memo", ""),
            "last_visit": lv,
            "visit_count": d.get("visit_count", 0),
            "total_sales": int(d.get("total_sales", 0)),
        })

    return jsonify({"customers": result})


@customer_bp.route("/api/customer", methods=["POST"])
@require_auth
def create_customer():
    db = get_db()
    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400

    phone = normalize_phone(data.get("phone", ""))
    pet_name = data.get("pet_name", "").strip()[:50]
    breed = data.get("breed", "").strip()[:50]

    if not phone:
        return jsonify({"error": "유효한 전화번호를 입력하세요"}), 400
    if not pet_name:
        return jsonify({"error": "반려동물 이름을 입력하세요"}), 400
    # breed는 선택사항 (간소화 폼에서 빈값 허용)

    # 기존 고객 확인 (같은 전화번호 + 같은 반려동물 이름)
    existing_list = queries.find_customers_by_phone(db, phone)
    for existing in existing_list:
        if existing.pet_name == pet_name:
            return jsonify({"error": "이미 등록된 전화번호+반려동물입니다", "customer_id": existing.id}), 409

    weight = _safe_float(data.get("weight"))
    channel = data.get("channel", "").strip()[:20]
    memo = data.get("memo", "")[:500]
    # 유입경로 → 메모에 자동 추가
    if channel and not memo.startswith(f"[{channel}]"):
        memo = f"[{channel}] {memo}".strip() if memo else f"[{channel}]"

    cid = queries.create_customer(
        db,
        name=data.get("name", "").strip()[:50],
        phone=phone,
        pet_name=pet_name,
        breed=breed,
        weight=weight,
        age=data.get("age", "")[:20],
        notes=data.get("notes", "")[:500],
        memo=memo,
        channel=channel,
    )

    # Google 연락처 동기화
    try:
        from web.routes_google import sync_contact_to_google
        sync_contact_to_google(cid, pet_name, weight, breed, phone, memo)
    except Exception as e:
        log.warning("Google sync failed on create (customer %s): %s", cid, e)

    return jsonify({"ok": True, "id": cid})


@customer_bp.route("/api/customer/<int:cid>", methods=["GET"])
@require_auth
def get_customer(cid):
    db = get_db()
    d = queries.get_customer_detail(db, cid)
    if not d:
        return jsonify({"error": "not found"}), 404

    def _res_dict(r):
        sh, sm = (int(x) for x in (r.time or "00:00").split(":"))
        em = sh * 60 + sm + (r.duration or 0)
        eh, emm = divmod(em, 60)
        return {
            "id": r.id, "date": r.date, "time": r.time,
            "end_time": f"{eh:02d}:{emm:02d}",
            "service_type": r.service_type, "status": r.status,
            "amount": r.amount, "duration": r.duration,
            "payment_method": r.payment_method or "",
            "request": r.request or "", "groomer_memo": r.groomer_memo or "",
            "fur_length": r.fur_length or "",
            "pet_name": r.pet_name or "",
        }

    # 현재 펫 예약 이력
    reservations = queries.get_customer_reservations(db, cid)
    res_list = [_res_dict(r) for r in reservations]

    siblings = queries.get_siblings(db, d.get("phone", ""), exclude_id=cid)

    # 형제 강아지들의 예약 이력도 포함
    sibling_reservations = {}
    for s in siblings:
        s_res = queries.get_customer_reservations(db, s["id"])
        sibling_reservations[s["id"]] = [_res_dict(r) for r in s_res]

    return jsonify({
        "id": d["id"], "name": d.get("name", ""), "phone": d.get("phone", ""),
        "phone_display": format_phone_display(d.get("phone", "")),
        "pet_name": d.get("pet_name", ""), "breed": d.get("breed", ""),
        "weight": d.get("weight"), "age": d.get("age"),
        "notes": d.get("notes", ""), "memo": d.get("memo", ""),
        "last_visit": d["last_visit"],
        "stats": d["stats"],
        "reservations": res_list,
        "siblings": siblings,
        "sibling_reservations": sibling_reservations,
    })


@customer_bp.route("/api/customer/<int:cid>", methods=["PUT"])
@require_auth
def update_customer(cid):
    db = get_db()
    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400

    fields = {}
    for key in ("name", "pet_name", "breed", "age", "notes"):
        if key in data:
            fields[key] = data[key]
    if "memo" in data:
        fields["memo"] = str(data["memo"])[:500]
    if "phone" in data:
        fields["phone"] = normalize_phone(data["phone"])
    if "weight" in data:
        fields["weight"] = _safe_float(data["weight"])

    queries.update_customer(db, cid, **fields)

    # Google 연락처 동기화
    try:
        from web.routes_google import sync_contact_to_google
        customer = db.fetch_one("SELECT * FROM customers WHERE id = ?", (cid,))
        if customer:
            sync_contact_to_google(
                cid,
                customer["pet_name"],
                customer["weight"],
                customer["breed"],
                customer["phone"],
                customer.get("memo", ""),
                customer.get("google_contact_id"),
            )
    except Exception as e:
        log.warning("Google sync failed on update (customer %s): %s", cid, e)

    return jsonify({"ok": True})


@customer_bp.route("/api/customer/<int:cid>", methods=["DELETE"])
@require_auth
def delete_customer(cid):
    # URL 유출 대비: 고객 삭제 비활성화
    return jsonify({"error": "삭제 기능이 비활성화되어 있습니다"}), 403


@customer_bp.route("/api/customer/by-phone")
@require_auth
def find_by_phone():
    db = get_db()
    phone = normalize_phone(request.args.get("phone", ""))
    if not phone:
        return jsonify({"customer": None})
    customers = queries.find_customers_by_phone(db, phone)
    if not customers:
        return jsonify({"customer": None})
    c = customers[0]
    customer_ids = [cu.id for cu in customers]

    # 단일 쿼리로 모든 고객의 통계를 한번에 조회
    placeholders = ",".join("?" for _ in customer_ids)
    stats_row = db.fetch_one(f"""
        SELECT COUNT(*) as cnt,
               MAX(CASE WHEN status='completed' THEN date END) as last_visit
        FROM reservations
        WHERE customer_id IN ({placeholders}) AND status = 'completed' AND amount > 0
    """, tuple(customer_ids))

    total_count = stats_row["cnt"] if stats_row else 0
    last_visit = stats_row["last_visit"] if stats_row else None
    if last_visit and hasattr(last_visit, 'strftime'):
        last_visit = last_visit.strftime("%Y-%m-%d")
    elif last_visit:
        last_visit = str(last_visit)

    # 최근 예약 3건도 단일 쿼리
    recent_rows = db.fetch_all(f"""
        SELECT date, service_type, amount, status
        FROM reservations
        WHERE customer_id IN ({placeholders})
        ORDER BY date DESC, time DESC
        LIMIT 3
    """, tuple(customer_ids))

    pets = [{"id": cu.id, "pet_name": cu.pet_name, "breed": cu.breed} for cu in customers]

    return jsonify({
        "customer": {
            "id": c.id, "name": c.name, "phone": c.phone,
            "phone_display": format_phone_display(c.phone),
            "pet_name": ", ".join(cu.pet_name for cu in customers),
            "breed": ", ".join(cu.breed for cu in customers),
            "weight": c.weight,
            "visit_count": total_count,
            "last_visit": last_visit,
            "recent_reservations": [{
                "date": r["date"], "service": r["service_type"],
                "amount": r["amount"], "status": r["status"],
            } for r in recent_rows],
        },
        "pets": pets,
    })
