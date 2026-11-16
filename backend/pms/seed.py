"""PMS 데모 샘플 데이터. 운영사·소유주·사업장·사람은 모두 가상이다."""
from __future__ import annotations


def _units(site_id: str, building: str, floors: int, per_floor: int, base_type: str) -> list[dict]:
    units = []
    for floor in range(1, floors + 1):
        for no in range(1, per_floor + 1):
            code = f"{floor}{no:02d}"
            units.append({
                "id": f"{site_id}-{building}{code}", "site_id": site_id, "building": building,
                "floor": floor, "number": code, "type": base_type if no % 2 else f"{base_type} 넓은형",
                "area_m2": 33.0 if no % 2 else 46.2, "maintenance": False,
            })
    return units


def build() -> dict:
    sites = [
        {
            "id": "site-garam", "name": "가람 시니어 레지던스", "asset_type": "senior_housing",
            "asset_label": "시니어하우징", "owner": "가람 자산신탁(가상)", "city": "서울 양천구(가상 주소)",
            "billing": {"due_day": 10, "late_rate_pct": 12.0},
            "prices": {
                "meal": {"label": "식사(1식)", "price": 9000},
                "care_visit": {"label": "방문 케어(1회)", "price": 30000},
                "shuttle": {"label": "병원 동행 셔틀(1회)", "price": 15000},
            },
        },
        {
            "id": "site-nuri", "name": "누리 하우스", "asset_type": "rental_housing",
            "asset_label": "임대주택", "owner": "누리 임대리츠(가상)", "city": "경기 고양시(가상 주소)",
            "billing": {"due_day": 5, "late_rate_pct": 10.0},
            "prices": {
                "parking": {"label": "주차(월)", "price": 30000},
                "cleaning": {"label": "세대 청소(1회)", "price": 25000},
            },
        },
    ]
    units = _units("site-garam", "A", 3, 4, "원룸형") + _units("site-nuri", "B", 2, 4, "투룸형")
    for unit in units:
        if unit["id"] == "site-garam-A304":
            unit["maintenance"] = True
    residents = [
        {"id": "r-101", "site_id": "site-garam", "unit_id": "site-garam-A101", "name": "김순자", "birth_year": 1944,
         "status": "resident", "phone": "010-2481-7731",
         "guardian": {"name": "박지훈", "relation": "아들", "phone": "010-9123-4402"},
         "care": {"level": "경증 지원", "notes": "고혈압 약 복용, 아침 식후 복약 확인", "allergies": ["견과류"]}},
        {"id": "r-102", "site_id": "site-garam", "unit_id": "site-garam-A102", "name": "이영호", "birth_year": 1941,
         "status": "resident", "phone": "010-3377-1290",
         "guardian": {"name": "이수민", "relation": "딸", "phone": "010-5521-8830"},
         "care": {"level": "자립", "notes": "주 2회 병원 동행 셔틀 이용", "allergies": []}},
        {"id": "r-201", "site_id": "site-garam", "unit_id": "site-garam-A201", "name": "정말순", "birth_year": 1946,
         "status": "resident", "phone": "010-6620-4418",
         "guardian": {"name": "정해원", "relation": "아들", "phone": "010-7710-2245"},
         "care": {"level": "경증 지원", "notes": "11월 15일 입주, 낙상 주의", "allergies": ["유제품"]}},
        {"id": "r-202", "site_id": "site-garam", "unit_id": "site-garam-A202", "name": "최봉길", "birth_year": 1939,
         "status": "resident", "phone": "010-8890-1123",
         "guardian": {"name": "최나연", "relation": "손녀", "phone": "010-4432-9981"},
         "care": {"level": "중등 지원", "notes": "11월 20일 퇴거 예정 (해지 계약)", "allergies": []}},
        {"id": "r-301", "site_id": "site-garam", "unit_id": "site-garam-A301", "name": "한정희", "birth_year": 1948,
         "status": "applicant", "phone": "010-1209-5567",
         "guardian": {"name": "한도윤", "relation": "아들", "phone": "010-3398-7710"},
         "care": {"level": "자립", "notes": "12월 입주 상담 중", "allergies": []}},
        {"id": "r-n101", "site_id": "site-nuri", "unit_id": "site-nuri-B101", "name": "오세린", "birth_year": 1990,
         "status": "resident", "phone": "010-2290-6634",
         "guardian": {"name": "오민국", "relation": "부", "phone": "010-6634-1180"},
         "care": {"level": "해당 없음", "notes": "", "allergies": []}},
        {"id": "r-n102", "site_id": "site-nuri", "unit_id": "site-nuri-B102", "name": "류태오", "birth_year": 1987,
         "status": "resident", "phone": "010-7745-3321",
         "guardian": {"name": "류하나", "relation": "배우자", "phone": "010-1188-4425"},
         "care": {"level": "해당 없음", "notes": "", "allergies": []}},
    ]
    contracts = [
        {"id": "c-101", "site_id": "site-garam", "unit_id": "site-garam-A101", "resident_id": "r-101",
         "status": "active", "start_date": "2026-03-01", "end_date": None, "deposit": 300_000_000, "monthly_fee": 3_200_000},
        {"id": "c-102", "site_id": "site-garam", "unit_id": "site-garam-A102", "resident_id": "r-102",
         "status": "active", "start_date": "2026-06-01", "end_date": None, "deposit": 300_000_000, "monthly_fee": 3_200_000},
        {"id": "c-201", "site_id": "site-garam", "unit_id": "site-garam-A201", "resident_id": "r-201",
         "status": "active", "start_date": "2026-11-15", "end_date": None, "deposit": 400_000_000, "monthly_fee": 3_900_000},
        {"id": "c-202", "site_id": "site-garam", "unit_id": "site-garam-A202", "resident_id": "r-202",
         "status": "terminated", "start_date": "2026-01-01", "end_date": "2026-11-20", "deposit": 400_000_000, "monthly_fee": 3_900_000},
        {"id": "c-301", "site_id": "site-garam", "unit_id": "site-garam-A301", "resident_id": "r-301",
         "status": "draft", "start_date": "2026-12-01", "end_date": None, "deposit": 300_000_000, "monthly_fee": 3_200_000},
        {"id": "c-n101", "site_id": "site-nuri", "unit_id": "site-nuri-B101", "resident_id": "r-n101",
         "status": "active", "start_date": "2026-02-01", "end_date": None, "deposit": 50_000_000, "monthly_fee": 650_000},
        {"id": "c-n102", "site_id": "site-nuri", "unit_id": "site-nuri-B102", "resident_id": "r-n102",
         "status": "active", "start_date": "2026-09-10", "end_date": None, "deposit": 50_000_000, "monthly_fee": 720_000},
    ]
    usages = [
        {"id": "u-1", "site_id": "site-garam", "resident_id": "r-101", "service": "meal", "date": "2026-11-03", "quantity": 20},
        {"id": "u-2", "site_id": "site-garam", "resident_id": "r-101", "service": "care_visit", "date": "2026-11-10", "quantity": 2},
        {"id": "u-3", "site_id": "site-garam", "resident_id": "r-102", "service": "shuttle", "date": "2026-11-05", "quantity": 4},
        {"id": "u-4", "site_id": "site-garam", "resident_id": "r-102", "service": "meal", "date": "2026-11-05", "quantity": 12},
        {"id": "u-5", "site_id": "site-garam", "resident_id": "r-201", "service": "meal", "date": "2026-11-16", "quantity": 6},
        {"id": "u-6", "site_id": "site-nuri", "resident_id": "r-n101", "service": "parking", "date": "2026-11-01", "quantity": 1},
        {"id": "u-7", "site_id": "site-nuri", "resident_id": "r-n102", "service": "cleaning", "date": "2026-11-12", "quantity": 1},
    ]
    users = [
        {"id": "u-hq", "name": "강본사", "role": "hq_admin", "site_ids": []},
        {"id": "u-mgr-garam", "name": "윤매니저", "role": "site_manager", "site_ids": ["site-garam"]},
        {"id": "u-care-garam", "name": "서케어", "role": "care_staff", "site_ids": ["site-garam"]},
        {"id": "u-acct", "name": "문회계", "role": "accountant", "site_ids": ["site-garam", "site-nuri"]},
        {"id": "u-mgr-nuri", "name": "장매니저", "role": "site_manager", "site_ids": ["site-nuri"]},
        {"id": "u-guardian", "name": "박지훈", "role": "guardian", "site_ids": ["site-garam"], "resident_ids": ["r-101"]},
    ]
    return {
        "operator": {"name": "한결 리빙(가상 운영사)"},
        "sites": sites, "units": units, "residents": residents, "contracts": contracts,
        "usages": usages, "users": users, "invoices": [], "payments": [], "audit": [],
    }
