# ZEB 데모 브이월드 fixture

`vworld_*.json` 은 브이월드 문서 기준으로 작성한 **가정 스키마**입니다.
키 발급 후 `python -m backend.zeb.check_vworld "<지번주소>"` 를 실행하면 실제 응답이
`vworld_*.recorded.json` 으로 저장됩니다. 계약 테스트(`backend.tests.test_zeb_demo`)는
recorded 파일이 있으면 그것을 먼저 사용합니다. 필드명이 다르면 `backend/zeb/adapters/vworld.py` 의 `FIELD_MAP` 만 고칩니다.
