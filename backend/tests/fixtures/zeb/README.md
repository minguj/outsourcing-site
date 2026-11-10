# ZEB 데모 브이월드 fixture

`vworld_*.json` 은 브이월드 문서 기준으로 작성한 **가정 스키마**입니다.
키 발급 후 `python -m backend.zeb.check_vworld "<지번주소>"` 를 실행하면 실제 응답이
`vworld_*.recorded.json` 으로 저장됩니다. 계약 테스트(`backend.tests.test_zeb_demo`)는
recorded 파일이 있으면 그것을 먼저 사용합니다. 필드명이 다르면 `backend/zeb/adapters/vworld.py` 의 `FIELD_MAP` 만 고칩니다.

## 법제처 자치법규 fixture (`law_ordin_*.json`)

조례 개정 감지(`backend/zeb/ordinance`) 테스트용입니다. 2026-11-10 배포 서버에서 받은 실제 응답(서울특별시 도시계획 조례,
2026.7.13 공포판, 자치법규일련번호 2149501)을 줄여 만들었습니다. 최상위 구조(`OrdinSearch.law`, `LawService.조문`), 조문번호 목록 형식,
제44조·제48조 문구는 실제와 같고, 제45~47·49~51조는 앞부분만 남겼습니다. 서울시 조례 행의 자치법규ID·공포번호와 상세링크의 OC 는 임의 값입니다.
