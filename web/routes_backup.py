"""백업 다운로드 / 데이터 임포트 API"""

import json
import logging
import re
from datetime import datetime
from flask import Blueprint, Response

log = logging.getLogger("jjonggood.backup")

backup_bp = Blueprint("backup", __name__)


@backup_bp.route("/api/backup")
def download_backup():
    from web.app import get_db, require_auth
    from web import config
    from flask import session, jsonify, request

    # 세션 인증 또는 API 키 인증
    api_key = request.args.get("key", "")
    if not session.get("authenticated") and api_key != config.TASKER_API_KEY:
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

    # 고객 변경이력
    customer_history = db.fetch_all("SELECT * FROM customer_history ORDER BY id")
    customer_history_list = []
    for row in customer_history:
        d = dict(row)
        for k, v in d.items():
            if hasattr(v, 'isoformat'):
                d[k] = v.isoformat()
        customer_history_list.append(d)

    # 참고사진 (base64 원본 포함)
    photos = db.fetch_all("SELECT * FROM customer_photos ORDER BY id")
    photos_list = []
    for row in photos:
        d = dict(row)
        for k, v in d.items():
            if hasattr(v, 'isoformat'):
                d[k] = v.isoformat()
        photos_list.append(d)

    backup_data = {
        "exported_at": datetime.now().isoformat(),
        "customers": customers_list,
        "reservations": reservations_list,
        "call_history": call_history_list,
        "customer_history": customer_history_list,
        "customer_photos": photos_list,
    }

    # ?format=json이면 다운로드 헤더 없이 JSON 반환 (자동백업용)
    if request.args.get("format") == "json":
        return jsonify(backup_data)

    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    json_str = json.dumps(backup_data, ensure_ascii=False, indent=2)

    return Response(
        json_str,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


STATUS_MAP = {
    "예약": "confirmed",
    "완료": "completed",
    "취소": "cancelled",
    "노쇼": "no_show",
}


def _parse_date(raw: str) -> str:
    """MM/DD → YYYY-MM-DD (올해) 또는 YYYY-MM-DD 그대로 반환."""
    raw = raw.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw
    m = re.match(r"^(\d{1,2})/(\d{1,2})$", raw)
    if m:
        year = datetime.now().year
        return f"{year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    raise ValueError(f"날짜 형식 오류: {raw}")


def _safe_int(val, default=0):
    if not val or not str(val).strip():
        return default
    return int(str(val).strip())


def _safe_float(val, default=None):
    if not val or not str(val).strip():
        return default
    return float(str(val).strip())


@backup_bp.route("/api/import-data", methods=["POST"])
def import_data():
    """통합 TSV 파일 하나로 고객+예약 동시 임포트.

    양식 (탭 구분, 첫 줄 헤더):
    전화번호  반려동물  견종  몸무게  나이  메모  날짜  시간  소요시간(분)  서비스  털길이  금액  결제금액  결제방법  상태  미용메모

    - 같은 전화번호가 여러 줄이면 → 고객 1명, 예약 여러 건
    - 날짜가 비어있으면 → 고객만 등록 (예약 없음)
    - 미용메모(16번째)는 선택사항
    """
    from web.app import get_db
    from web import queries
    from flask import session, jsonify, request

    if not session.get("authenticated"):
        return jsonify({"error": "unauthorized"}), 401

    data_file = request.files.get("datafile")
    if not data_file:
        return jsonify({"error": "파일이 필요합니다"}), 400

    try:
        text = data_file.read().decode("utf-8-sig")
    except Exception as e:
        log.exception("파일 읽기 실패")
        return jsonify({"error": "파일 읽기 실패"}), 400

    db = get_db()
    errors = []
    phone_to_id = {}
    customers_count = 0
    reservations_count = 0

    # 트랜잭션으로 감싸기: 실패 시 ROLLBACK → 기존 데이터 보존
    conn = db.get_conn()
    try:
        with conn.cursor() as cur:
            # 1. 기존 데이터 전체 삭제
            for table in ("reservation_edits", "groomer_memos", "call_history", "reservations", "customers"):
                cur.execute(f"DELETE FROM {table}")

            # 2. 파싱 & 삽입
            lines = text.strip().split("\n")
            for i, line in enumerate(lines[1:], start=2):
                line = line.strip()
                if not line:
                    continue
                cols = line.split("\t")
                if len(cols) < 2:
                    errors.append(f"{i}행: 컬럼 부족")
                    continue

                phone = re.sub(r"[^0-9]", "", cols[0].strip())
                if not phone:
                    errors.append(f"{i}행: 전화번호 없음")
                    continue
                if len(phone) == 10 and not phone.startswith("0"):
                    phone = "0" + phone

                pet_name = cols[1].strip() if len(cols) > 1 else ""
                breed = cols[2].strip() if len(cols) > 2 else ""
                weight = _safe_float(cols[3] if len(cols) > 3 else "")
                age = cols[4].strip() if len(cols) > 4 else ""
                memo = cols[5].strip() if len(cols) > 5 else ""

                key = (phone, pet_name)
                if key not in phone_to_id:
                    try:
                        cur.execute(
                            """INSERT INTO customers (name, phone, pet_name, breed, weight, age, memo)
                               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                            ("", phone, pet_name, breed, weight, age, memo))
                        phone_to_id[key] = cur.fetchone()[0]
                        customers_count += 1
                    except Exception as e:
                        errors.append(f"{i}행: 고객 등록 실패 - {e}")
                        continue

                customer_id = phone_to_id[key]

                date_raw = cols[6].strip() if len(cols) > 6 else ""
                if not date_raw:
                    continue

                try:
                    date_str = _parse_date(date_raw)
                except ValueError as e:
                    errors.append(f"{i}행: {e}")
                    continue

                time_str = cols[7].strip() if len(cols) > 7 else "10:00"
                duration = _safe_int(cols[8] if len(cols) > 8 else "", 60)
                service = cols[9].strip() if len(cols) > 9 else "전체미용"
                fur_length = cols[10].strip() if len(cols) > 10 else ""
                quoted_amount = _safe_int(cols[11] if len(cols) > 11 else "", 0)
                amount = _safe_int(cols[12] if len(cols) > 12 else "", 0)
                payment_method = cols[13].strip() if len(cols) > 13 else ""
                status_raw = cols[14].strip() if len(cols) > 14 else "예약"
                status = STATUS_MAP.get(status_raw, "confirmed")
                groomer_memo = cols[15].strip() if len(cols) > 15 else ""

                try:
                    cur.execute(
                        """INSERT INTO reservations
                           (customer_id, date, time, service_type, duration, request,
                            amount, quoted_amount, payment_method, fur_length, status, groomer_memo)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (customer_id, date_str, time_str, service, duration, "",
                         amount, quoted_amount, payment_method, fur_length, status, groomer_memo))
                    reservations_count += 1
                except Exception as e:
                    errors.append(f"{i}행: 예약 등록 실패 - {e}")

        conn.commit()
    except Exception as e:
        conn.rollback()
        log.exception("임포트 실패 (롤백됨)")
        return jsonify({"error": "임포트 실패 (데이터 복원됨)"}), 500
    finally:
        db.put_conn(conn)

    return jsonify({
        "ok": True,
        "customers_count": customers_count,
        "reservations_count": reservations_count,
        "errors": errors,
    })
