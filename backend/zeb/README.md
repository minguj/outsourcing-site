# 초기 기획 데모 (대지 규모 + ZEB 신재생 시나리오)

화면: `/demo/zeb` (검색 제외, 공개 화면에서 링크하지 않음) · API: `/api/demo/zeb/*`

대상지를 고르면 용도지역·건폐율·용적률·높이 제한으로 건축 규모를 산정하고,
ZEB 등급별로 필요한 신재생 설비 조합(최소비용)과 도입비용을 계산해 보고서로 출력한다.

## 구조
```
backend/zeb/
  router.py          API (입출력 변환만)
  domain/            순수 계산 엔진 (I/O 없음)
    rules.py         규칙 YAML 로더, 기준일(as_of)별 규칙 선택, 규칙 지문
    trace.py         계산 근거 기록 (값·산식·입력·근거·검증 상태)
    massing.py       건폐율·용적률·층수·높이 → 규모
    energy.py        1차에너지 소요량, 설비 잠재량, 등급별 최소비용 조합
    feasibility.py   전체 흐름, 인사이트, calc_id
  rules/*.yaml       법령·조례·고시·가정값 (출처, checked_on, verified)
  adapters/          브이월드 / 샘플 필지
  samples/*.json     데모 샘플 필지·정비사업 (가상). 'data' 폴더명은 .gitignore 에 걸리므로 쓰지 않는다
  check_vworld.py    키 발급 후 실제 응답 확인용
frontend/src/app/demo/zeb/   검색(page) · 검토(plan) · 보고서(report), zb- 접두어 CSS
backend/tests/test_zeb_demo.py, backend/tests/fixtures/zeb/
```

## 설계 원칙
1. **계산 엔진은 I/O 와 분리한다.** 네트워크 없이 테스트하고, 문서 자동화·배치 검토에서 그대로 재사용한다.
2. **법규 값은 코드가 아니라 버전 있는 데이터다.** 적용값 = min(조례, 법정 상한). 조례 미등록 지역은 법정 상한 + `critical` 경고.
   지구단위계획·정비구역 등 개별 계획이 우선하는 구역은 자동 계산값을 확정값처럼 보여주지 않고 경고한다.
3. **모든 숫자에 근거를 남긴다.** `verified: false` 규칙을 쓴 단계는 화면·보고서에 "검토 필요"로 표시된다.
   결과마다 `calc_id = hash(입력 + 규칙 버전 + 엔진 버전)` 가 붙고, 화면 URL 에 모든 입력이 있어 링크로 재현된다.
4. **외부 데이터 실패를 숨기지 않는다.** 브이월드 조회 실패 시 샘플로 대체하지 않고 502 를 낸다. 결과에 `data_source` 배지.

## 규칙 YAML 을 바꿀 때
- 근거 URL·조항을 PR 에 적고 `checked_on` 을 갱신한다. 원문으로 확인한 값만 `verified: true`.
- 영향받는 골든 테스트는 손계산으로 기대값을 다시 정한다 (엔진 출력을 복사하지 않는다).
- `RuleIntegrityTests` 가 "조례값 ≤ 법정 상한", "출처 필드 존재" 를 강제한다.

## 브이월드
- 키는 서버 `/etc/outsourcing-deploy/backend.env` 의 `VWORLD_API_KEY`, `VWORLD_DOMAIN`(키 발급 시 서비스 URL 과 동일).
  비어 있으면 샘플 필지로만 동작한다. 화면에서 샘플/실데이터를 고를 수 있다.
- **브이월드는 해외·클라우드 IP 를 차단한다.** 운영 서버(시드니)에서 호출하면 502 가 난다.
  그래서 기본값 `VWORLD_MODE=browser`: 방문자 브라우저(국내 IP)가 직접 조회하고(`_zeb/vworld.ts`, fetch 실패 시 JSONP),
  원본 응답을 `/feasibility` 의 `vworld_raw` 로 보내면 서버가 `parse_land` 로 해석한다. 해석 규칙은 서버 한곳에만 있다.
  - 키는 `/api/demo/zeb/meta` 로 페이지에 전달된다 (브이월드 지도 API 와 같은 방식, 등록 도메인에서만 동작).
  - 해외에서 접속한 방문자는 실데이터 조회가 안 될 수 있다 (샘플·직접 입력은 가능).
  - 로컬(localhost)에서는 키의 등록 도메인과 달라 실데이터 조회가 안 될 수 있다.
- 국내 IP 서버에서 운영한다면 `VWORLD_MODE=server` 로 서버가 직접 조회한다 (키는 화면에 전달하지 않음).
- 오류 문구는 화면까지 전달되므로 인증키가 들어가지 않게 만든다 (`test_error_messages_never_contain_api_key`).
- 사용 API: 검색 API(지번 → PNU), 국가중점 API(토지특성: 면적·용도지역 / 토지이용계획: 지역·지구).
- 토지이용계획은 관계(`cnflcAtNm`)별로 나눈다: **포함**(규제 대상) / **저촉**(대지 일부가 걸침) / **접함**(인접 필지 것, 규제 판단 제외).
  접함까지 규제로 보면 옆 필지의 정비구역·지구단위계획 때문에 잘못된 경고가 나간다 (실응답으로 확인, `VWorldRecordedResponseTests`).
- 지목(`lndcgrCodeNm`)이 도로·하천 등이면 critical, 전·답·임야면 개발행위허가 경고. 기준은 `rules/zoning.yaml` 의 `land_categories`.
- 두 용도지역에 걸친 필지(용도지역2, 또는 포함·저촉된 다른 용도지역)는 대표 용도지역으로 계산하되 critical 경고.
- 호출 상한: 전역 분당 `VWORLD_PER_MINUTE`(기본 60). 필지 조회 결과는 1시간 메모리 캐시.
- fixture(`backend/tests/fixtures/zeb/vworld_*.json`)는 문서 기준 **가정 스키마**다. 키 발급 후 저장소 루트에서
  `python -m backend.zeb.check_vworld "<지번주소>"` 로 실제 응답을 녹화하고, 필드명이 다르면 `adapters/vworld.py` 의 `FIELD_MAP` 만 고친다.

## 계산 모델과 한계
- 규모: 지상 연면적만. 층수 = 올림(최대 연면적 ÷ 최대 건축면적)을 높이·층수 제한으로 자른다. 사선·일조는 높이 제한 입력으로 반영.
- 에너지: 자립률 = 1차에너지 순생산량 ÷ 소요량. 소요량은 용도별 원단위 가정.
  설비는 단위 생산량당 비용이 낮은 순서로 옥상·남측 입면·공지·열수요 한계까지 채운다 (분할 배낭 → 연속해 최적).
- 하지 않는 것: ECO2 수준 동적 해석, 1차에너지소요량 경로 인증, 대지 외 신재생, 지하·주차, 실견적.
- 검증 상태: 서울 제2·3종일반주거, 준주거, 일반상업, 준공업(공동주택) 용적률과 ZEB 등급 기준(2025-01-01 고시)은 공개 자료로 확인.
  나머지는 `verified: false`.
