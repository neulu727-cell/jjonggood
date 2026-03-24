"""미용 견적 가격 계산"""

from web.config import PRICE_TABLE, SURCHARGES


def calculate_price(service_choice, weight_kg, breed_type="일반",
                    clipping_length="", face_cut=False):
    """
    service_choice: "위생목욕" | "클리핑" | "스포팅"
    breed_type: "일반" | "비숑"
    → 클리핑 + face_cut=True → "클리핑+얼굴컷" (일반) 또는 "클리핑+비숑컷" (비숑)
    → 클리핑 + face_cut=False → "클리핑"

    Returns: (estimated_price, actual_service)
    """
    # 1. 서비스 매핑
    if service_choice == "클리핑":
        if face_cut:
            actual_service = "클리핑+비숑컷" if breed_type == "비숑" else "클리핑+얼굴컷"
        else:
            actual_service = "클리핑"
    elif service_choice == "스포팅":
        actual_service = "스포팅"
    else:
        actual_service = "위생목욕"

    # 2. 견종별 요금표 선택 (특수견은 일반 요금 기준)
    table_key = "일반" if breed_type == "특수" else breed_type
    breed_table = PRICE_TABLE.get(table_key, PRICE_TABLE["일반"])

    # 3. 몸무게 구간으로 base price 조회
    base_price = 0
    if weight_kg is not None and weight_kg > 0:
        for (min_kg, max_kg), prices in breed_table.items():
            if min_kg <= weight_kg < max_kg:
                base_price = prices.get(actual_service, 0)
                break
        else:
            # 10kg 이상: 최고 구간 사용
            if weight_kg >= 10:
                last_prices = breed_table[(8, 10)]
                base_price = last_prices.get(actual_service, 0)

    total = base_price

    # 4. 클리핑 길이 추가금 (13mm: +1만, 20mm: +2만)
    if service_choice == "클리핑":
        if clipping_length == "13mm":
            total += SURCHARGES["clipping_13mm"]
        elif clipping_length == "20mm":
            total += SURCHARGES["clipping_20mm"]

    return total, actual_service
