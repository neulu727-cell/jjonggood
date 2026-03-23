"""미용 견적 가격 계산"""

from web.config import PRICE_TABLE, SURCHARGES


def calculate_price(service_choice, weight_kg, clipping_length="",
                    face_cut=False, matting="none", fur_length=""):
    """
    service_choice: "위생목욕" | "클리핑" | "스포팅"
    → 클리핑 + face_cut=True → actual_service="전체얼컷"
    → 클리핑 + face_cut=False → actual_service="전체미용"

    Returns: (estimated_price, actual_service)
    """
    # 1. 서비스 매핑
    if service_choice == "클리핑":
        actual_service = "전체얼컷" if face_cut else "전체미용"
    elif service_choice == "스포팅":
        actual_service = "스포팅"
    else:
        actual_service = "위생목욕"

    # 2. 몸무게 구간으로 base price 조회
    base_price = 0
    if weight_kg is not None and weight_kg > 0:
        for (min_kg, max_kg), prices in PRICE_TABLE.items():
            if min_kg <= weight_kg < max_kg:
                base_price = prices.get(actual_service, 0)
                break
        else:
            # 13kg 이상: 최고 구간 사용
            if weight_kg >= 13:
                last_prices = PRICE_TABLE[(11, 13)]
                base_price = last_prices.get(actual_service, 0)
            # 1kg 미만: 최저 구간 사용
            elif weight_kg < 1:
                first_prices = PRICE_TABLE[(1, 3)]
                base_price = first_prices.get(actual_service, 0)

    total = base_price

    # 3. 클리핑 길이 추가금 (1.3cm: +1만, 2cm: +2만)
    if service_choice == "클리핑":
        if clipping_length == "1.3cm":
            total += SURCHARGES["clipping_1.3cm"]
        elif clipping_length == "2cm":
            total += SURCHARGES["clipping_2cm"]

    # 4. 위생목욕 + 얼굴커트 시: +1.5만
    if service_choice == "위생목욕" and face_cut:
        total += SURCHARGES["face_cut"]

    # 5. 엉킴 추가금
    if matting == "light":
        total += SURCHARGES["matting_light"]
    elif matting == "heavy":
        total += SURCHARGES["matting_heavy"]

    # 6. 털길이 추가금 (위생목욕만)
    if service_choice == "위생목욕":
        if fur_length == "중간":
            total += SURCHARGES["fur_medium"]
        elif fur_length == "길다":
            total += SURCHARGES["fur_long"]

    return total, actual_service
