"""고객 CRUD API"""

from flask import Blueprint, jsonify, request
from web.app import get_db, require_auth
from web import queries
from web.utils.phone_formatter import normalize_phone, format_phone_display

customer_bp = Blueprint("customer", __name__)


@customer_bp.route("/api/customers/search")
@require_auth
def search_customers():
    db = get_db()
    keyword = request.args.get("q", "").strip()
    if not keyword:
        return jsonify({"customers": []})

    customers = queries.search_customers(db, keyword)
    result = []
    for c in customers:
        last_visit = queries.get_last_visit_date(db, c.id)
        stats = queries.get_customer_sales_stats(db, c.id)
        result.append({
            "id": c.id,
            "name": c.name,
            "phone": c.phone,
            "phone_display": format_phone_display(c.phone),
            "pet_name": c.pet_name,
            "breed": c.breed,
            "weight": c.weight,
            "age": c.age,
            "notes": c.notes,
            "memo": c.memo,
            "last_visit": last_visit,
            "visit_count": stats["count"],
            "total_sales": stats["total"],
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
    pet_name = data.get("pet_name", "").strip()
    breed = data.get("breed", "").strip()

    if not phone:
        return jsonify({"error": "유효한 전화번호를 입력하세요"}), 400
    if not pet_name:
        return jsonify({"error": "반려동물 이름을 입력하세요"}), 400
    if not breed:
        return jsonify({"error": "견종을 입력하세요"}), 400

    # 기존 고객 확인 (같은 전화번호 + 같은 반려동물 이름)
    existing_list = queries.find_customers_by_phone(db, phone)
    for existing in existing_list:
        if existing.pet_name == pet_name:
            return jsonify({"error": "이미 등록된 전화번호+반려동물입니다", "customer_id": existing.id}), 409

    cid = queries.create_customer(
        db,
        name=data.get("name", "").strip(),
        phone=phone,
        pet_name=pet_name,
        breed=breed,
        weight=float(data["weight"]) if data.get("weight") else None,
        age=data.get("age", ""),
        notes=data.get("notes", ""),
        memo=data.get("memo", ""),
    )
    return jsonify({"ok": True, "id": cid})


@customer_bp.route("/api/customer/<int:cid>", methods=["GET"])
@require_auth
def get_customer(cid):
    db = get_db()
    c = queries.get_customer_by_id(db, cid)
    if not c:
        return jsonify({"error": "not found"}), 404

    last_visit = queries.get_last_visit_date(db, cid)
    stats = queries.get_customer_sales_stats(db, cid)
    reservations = queries.get_customer_reservations(db, cid)

    res_list = []
    for r in reservations:
        res_list.append({
            "id": r.id, "date": r.date, "time": r.time,
            "service_type": r.service_type, "status": r.status,
            "amount": r.amount, "duration": r.duration,
        })

    return jsonify({
        "id": c.id, "name": c.name, "phone": c.phone,
        "phone_display": format_phone_display(c.phone),
        "pet_name": c.pet_name, "breed": c.breed,
        "weight": c.weight, "age": c.age,
        "notes": c.notes, "memo": c.memo,
        "last_visit": last_visit,
        "stats": stats,
        "reservations": res_list,
    })


@customer_bp.route("/api/customer/<int:cid>", methods=["PUT"])
@require_auth
def update_customer(cid):
    db = get_db()
    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400

    fields = {}
    for key in ("name", "pet_name", "breed", "age", "notes", "memo"):
        if key in data:
            fields[key] = data[key]
    if "phone" in data:
        fields["phone"] = normalize_phone(data["phone"])
    if "weight" in data:
        fields["weight"] = float(data["weight"]) if data["weight"] else None

    queries.update_customer(db, cid, **fields)
    return jsonify({"ok": True})


@customer_bp.route("/api/customer/<int:cid>", methods=["DELETE"])
@require_auth
def delete_customer(cid):
    db = get_db()
    queries.delete_customer(db, cid)
    return jsonify({"ok": True})


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
    # 모든 반려동물 통계 합산
    total_count = 0
    last_visit = None
    all_recent = []
    for cu in customers:
        s = queries.get_customer_sales_stats(db, cu.id)
        total_count += s["count"]
        lv = queries.get_last_visit_date(db, cu.id)
        if lv and (not last_visit or lv > last_visit):
            last_visit = lv
        all_recent.extend(queries.get_customer_reservations(db, cu.id)[:3])
    all_recent.sort(key=lambda r: r.date, reverse=True)
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
                "date": r.date, "service": r.service_type,
                "amount": r.amount, "status": r.status,
            } for r in all_recent[:3]],
        }
    })
