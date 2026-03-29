"""고객 CRUD API"""

import logging
from flask import Blueprint, jsonify, request
from web.app import get_db, require_auth, bump_update
from web import queries
from web.utils.phone_formatter import normalize_phone, format_phone_display

log = logging.getLogger("jjonggood.customer")

customer_bp = Blueprint("customer", __name__)


def _record_history(db, customer_id, action, field_name="", old_value="", new_value=""):
    """고객 변경이력 기록"""
    db.execute(
        "INSERT INTO customer_history (customer_id, action, field_name, old_value, new_value) VALUES (?, ?, ?, ?, ?)",
        (customer_id, action, field_name, str(old_value or "")[:500], str(new_value or "")[:500])
    )


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
        WHERE c.phone != 'BOSS'
    """

    if keyword:
        like = f"%{keyword}%"
        rows = db.fetch_all(
            base_query + " AND (c.name ILIKE ? OR c.phone ILIKE ? OR c.pet_name ILIKE ?)"
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
            "channel": d.get("channel", ""),
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

    # 생성 이력 기록
    _record_history(db, cid, "create", "", "", f"{pet_name} ({breed}) {phone}")

    # Google 연락처 동기화
    google_synced = False
    google_msg = ""
    try:
        from web.routes_google import sync_contact_to_google, GOOGLE_AVAILABLE
        if not GOOGLE_AVAILABLE:
            google_msg = "Google API 패키지 미설치"
        else:
            google_synced, google_msg = sync_contact_to_google(cid, pet_name, weight, breed, phone, memo)
            if not google_synced:
                log.warning("Google sync failed on create (customer %s): %s", cid, google_msg)
    except Exception as e:
        log.error("Google sync exception on create (customer %s): %s", cid, e, exc_info=True)
        google_msg = str(e)

    bump_update()
    weight_str = f" {weight}kg" if weight else ""
    breed_str = f" {breed}" if breed else ""
    google_name = f"{pet_name}{weight_str}{breed_str}".strip()
    return jsonify({"ok": True, "id": cid, "google_synced": google_synced, "google_msg": google_msg, "google_contact_name": google_name})


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
        "notes": d.get("notes", ""), "memo": d.get("memo", ""), "channel": d.get("channel", ""),
        "phone2": d.get("phone2", ""), "phone2_display": format_phone_display(d.get("phone2", "")),
        "phone3": d.get("phone3", ""), "phone3_display": format_phone_display(d.get("phone3", "")),
        "keyring": bool(d.get("keyring", False)),
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
    if "channel" in data:
        fields["channel"] = str(data["channel"])[:20]
    if "phone2" in data:
        fields["phone2"] = normalize_phone(data["phone2"]) if data["phone2"] else ""
    if "phone3" in data:
        fields["phone3"] = normalize_phone(data["phone3"]) if data["phone3"] else ""

    # 수정 전 기존 데이터 조회 (이력용)
    old_data = db.fetch_one("SELECT * FROM customers WHERE id = ?", (cid,))

    queries.update_customer(db, cid, **fields)

    # 메모 변경 시 형제 강아지에게도 동기화
    if "memo" in fields:
        customer = db.fetch_one("SELECT phone FROM customers WHERE id = ?", (cid,))
        if customer and customer["phone"]:
            db.execute(
                "UPDATE customers SET memo = ?, updated_at = NOW() WHERE phone = ? AND id != ?",
                (fields["memo"], customer["phone"], cid)
            )

    # 변경 이력 기록
    if old_data:
        for key, new_val in fields.items():
            old_val = old_data.get(key, "")
            if old_val is None:
                old_val = ""
            if new_val is None:
                new_val = ""
            if str(old_val) != str(new_val):
                _record_history(db, cid, "update", key, old_val, new_val)

    # Google 연락처 동기화
    google_synced = False
    google_msg = ""
    try:
        from web.routes_google import sync_contact_to_google
        customer = db.fetch_one("SELECT * FROM customers WHERE id = ?", (cid,))
        if customer:
            google_synced, google_msg = sync_contact_to_google(
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
        google_msg = str(e)

    bump_update()
    google_name = ""
    if customer:
        w = f" {customer['weight']}kg" if customer.get("weight") else ""
        b = f" {customer['breed']}" if customer.get("breed") else ""
        google_name = f"{customer['pet_name']}{w}{b}".strip()
    return jsonify({"ok": True, "google_synced": google_synced, "google_msg": google_msg, "google_contact_name": google_name})


@customer_bp.route("/api/customer/<int:cid>", methods=["DELETE"])
@require_auth
def delete_customer(cid):
    # URL 유출 대비: 고객 삭제 비활성화
    # 삭제 이력은 활성화 시 기록됨
    db = get_db()
    old_data = db.fetch_one("SELECT * FROM customers WHERE id = ?", (cid,))
    if old_data:
        _record_history(db, cid, "delete", "", f"{old_data.get('pet_name','')} ({old_data.get('breed','')}) {old_data.get('phone','')}", "")
    return jsonify({"error": "삭제 기능이 비활성화되어 있습니다"}), 403


@customer_bp.route("/api/customer/<int:cid>/keyring", methods=["PUT"])
@require_auth
def toggle_keyring(cid):
    db = get_db()
    data = request.get_json() or {}
    keyring = bool(data.get("keyring", False))
    db.execute("UPDATE customers SET keyring = ?, updated_at = NOW() WHERE id = ?", (keyring, cid))
    bump_update()
    return jsonify({"ok": True, "keyring": keyring})


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
                "date": r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else str(r["date"]),
                "service": r["service_type"],
                "amount": r["amount"], "status": r["status"],
            } for r in recent_rows],
        },
        "pets": pets,
    })


@customer_bp.route("/api/customers/history")
@require_auth
def customer_history():
    """고객 변경이력 조회"""
    db = get_db()
    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", 50, type=int)
    rows = db.fetch_all(
        """SELECT h.*, c.pet_name, c.breed
           FROM customer_history h
           LEFT JOIN customers c ON h.customer_id = c.id
           ORDER BY h.created_at DESC
           LIMIT ? OFFSET ?""",
        (min(limit, 100), offset)
    )
    result = []
    for r in rows:
        created = r["created_at"]
        if hasattr(created, 'strftime'):
            created = created.strftime("%m/%d %H:%M")
        else:
            created = str(created)[:16] if created else ""
        result.append({
            "id": r["id"],
            "customer_id": r["customer_id"],
            "pet_name": r.get("pet_name") or "",
            "breed": r.get("breed") or "",
            "action": r["action"],
            "field_name": r["field_name"] or "",
            "old_value": r["old_value"] or "",
            "new_value": r["new_value"] or "",
            "created_at": created,
        })
    return jsonify({"history": result})


@customer_bp.route("/api/customer/<int:cid>/photos", methods=["GET"])
@require_auth
def get_customer_photos(cid):
    """고객 참고사진 조회"""
    db = get_db()
    rows = db.fetch_all(
        "SELECT id, image_data, TO_CHAR(created_at, 'MM/DD') as created_at FROM customer_photos WHERE customer_id = ? ORDER BY created_at DESC",
        (cid,)
    )
    return jsonify({"photos": [{"id": r["id"], "image_data": r["image_data"], "created_at": r["created_at"] or ""} for r in rows]})


@customer_bp.route("/api/customer/<int:cid>/photos", methods=["POST"])
@require_auth
def add_customer_photo(cid):
    """고객 참고사진 추가"""
    db = get_db()
    data = request.get_json()
    if not data or not data.get("image_data"):
        return jsonify({"error": "이미지 데이터가 없습니다"}), 400

    image_data = data["image_data"]
    # base64 data URL 크기 제한 (약 5MB)
    if len(image_data) > 5 * 1024 * 1024:
        return jsonify({"error": "이미지가 너무 큽니다 (5MB 이하)"}), 400

    # 사진 수 제한 (고객당 최대 20장)
    count = db.fetch_one("SELECT COUNT(*) as cnt FROM customer_photos WHERE customer_id = ?", (cid,))
    if count and count["cnt"] >= 20:
        return jsonify({"error": "사진은 최대 20장까지 등록 가능합니다"}), 400

    db.execute(
        "INSERT INTO customer_photos (customer_id, image_data) VALUES (?, ?)",
        (cid, image_data)
    )
    return jsonify({"ok": True})


@customer_bp.route("/api/customer/<int:cid>/photo/<int:pid>", methods=["DELETE"])
@require_auth
def delete_customer_photo(cid, pid):
    """고객 참고사진 삭제"""
    db = get_db()
    db.execute("DELETE FROM customer_photos WHERE id = ? AND customer_id = ?", (pid, cid))
    return jsonify({"ok": True})


@customer_bp.route("/api/customers/missing-breed")
@require_auth
def missing_breed():
    """견종이 비어있는 고객 조회 (일회성 조사용)"""
    db = get_db()
    rows = db.fetch_all(
        "SELECT id, pet_name, breed, phone, memo FROM customers WHERE breed IS NULL OR breed = '' ORDER BY id"
    )
    result = [{"id": r["id"], "pet_name": r["pet_name"], "breed": r["breed"] or "", "phone": r["phone"], "memo": r["memo"] or ""} for r in rows]
    return jsonify({"count": len(result), "customers": result})
