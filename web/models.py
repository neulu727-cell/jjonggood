"""데이터 모델 (dataclass)"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Customer:
    id: int
    name: str
    phone: str
    pet_name: str
    breed: str
    weight: Optional[float] = None
    age: Optional[str] = None
    notes: str = ""
    memo: str = ""
    channel: str = ""
    google_contact_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Reservation:
    id: int
    customer_id: int
    date: str
    time: str
    service_type: str
    duration: int = 60
    request: str = ""
    status: str = "confirmed"
    amount: int = 0
    quoted_amount: int = 0
    payment_method: str = ""
    fur_length: str = ""
    groomer_memo: str = ""
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    # 조인 시 사용되는 고객 정보
    customer_name: str = ""
    pet_name: str = ""
    customer_phone: str = ""
    breed: str = ""


@dataclass
class GroomerMemo:
    id: int
    reservation_id: int
    content: str
    created_at: Optional[str] = None
