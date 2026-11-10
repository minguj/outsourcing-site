# ZEB 데모 브이월드 fixture

`vworld_*.json` 은 브이월드 문서 기준으로 작성한 **가정 스키마**입니다.
키 발급 후 `python -m backend.zeb.check_vworld "<지번주소>"` 를 실행하면 실제 응답이
`vworld_*.recorded.json` 으로 저장됩니다. 계약 테스트(`backend.tests.test_zeb_demo`)는
recorded 파일이 있으면 그것을 먼저 사용합니다. 필드명이 다르면 `backend/zeb/adapters/vworld.py` 의 `FIELD_MAP` 만 고칩니다.

## 법제처 자치법규 fixture (`law_ordin_*.json`)

조례 개정 감지(`backend/zeb/ordinance`) 테스트용입니다. 필드명은 법제처 Open API 가이드(자치법규 목록·본문 조회)를 따랐고,
응답의 최상위 구조는 가이드에 없어 **가정**했습니다. 해석 코드는 구조에 기대지 않고 `자치법규명`·`조내용` 키가 있는
객체를 찾아 쓰므로, 실제 응답의 중첩이 달라도 동작합니다. 조문 문구는 서울시 도시계획 조례의 형식을 본떠 만든 예시입니다.
