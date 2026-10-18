# 현행 작업: v2 2단계 — 재검사·폐기

상태: **초안 – 사용자 확정 전** (2026-10-18). 결정 근거는 `handoff/decisions.md`. 사용자가 확정하면 이 줄을 "사용자 확정"으로 바꾼다.
1단계(아래 「v2 1단계 명세」)는 완료(리뷰 002 PASS)이며, 그 동작과 테스트는 보존한다.

## 목표와 경계
- FAIL로 보류된 검사를 **재검사 요청 → 재검사 결과**로 처리한다. 재검사 PASS면 그 검사의 보류가 풀리고, 상한까지 FAIL이 이어지면 제품을 폐기한다.
- 원래 FAIL은 지우거나 덮어쓰지 않는다. 모든 시도는 이력으로 남는다.
- 모든 규칙은 가상 규칙이다. 재검사 상한 2회는 실제 SL 기준이 아니다.
- 이번 단계 제외: 설비·로트(3단계), 대량 생성기(4단계), 요청 ID·시도 ID 열 추가, 재검사 설비 지정, 폐기 취소, 레시피별로 다른 상한.

## 보존 조건 (가장 먼저 지킬 것)
- v1: 기존 조건 그대로(T1–T10, v1 보고서 동일).
- 1단계: `--recipe recipes/lamp_models.json`(재검사 설정 없음)의 동작·출력은 바뀌지 않는다. **T11–T22 테스트는 수정하지 않고 통과**해야 하며, `reports/sample_events_v2_*.csv` 3종도 다시 만들었을 때 체크아웃된 파일과 같아야 한다.
- `src/rules.py`, `tests/test_rules.py`, `tests/test_recipe.py`는 수정하지 않는다. 2단계 테스트는 새 파일(`tests/test_retest.py`)에 둔다.

## 재검사 모드 켜기
- 레시피의 **모든 모델**에 `"retest_limit": 2`를 넣으면 재검사 모드다. 하나도 없으면 1단계와 똑같이 동작한다.
- 일부 모델에만 있으면 설정 오류다. `retest_limit`은 1–5 정수(`true`·문자열 불가)여야 한다. 위반은 기존 레시피 검증과 같이 모든 오류를 표시하고 종료 코드 3.
- 기본 재검사 레시피: `recipes/lamp_models_retest.json` (`lamp_models.json`과 같고 두 모델에 `"retest_limit": 2`만 추가).
- `RETEST_REQUEST`는 공정 ID로 쓸 수 없는 예약어에 추가한다(`REGISTER`, `INSPECT`와 같음).
- 실행: `py -m src.main <입력CSV> --recipe recipes/lamp_models_retest.json`

## 입력 (CSV 열은 1단계와 같은 6열)
- 새 이벤트 `RETEST_REQUEST`: `inspection` 칸에 재검사할 검사 ID를 쓰고 `result`·`model`은 빈칸.
- 재검사 결과는 기존과 같은 `INSPECT` 행이다. 그 검사에 **열린 요청이 있을 때** 들어온 `INSPECT`를 그 요청의 재검사로 본다(요청과 결과는 같은 제품·같은 검사로 연결된다).

## 규칙 ID
- 신규 `RULE_RETEST`: 재검사 요청·재검사 결과·폐기와 관련된 판정. 재검사 모드의 거절 집계는 1단계 6개 뒤에 `RULE_RETEST`를 붙인 7개.

## 판정 규칙
**재검사 요청 (`RETEST_REQUEST X`)**
| 조건 | 결과 |
| --- | --- |
| X의 현재 결과가 FAIL이고 열린 요청이 없음 | 허용(`RULE_RETEST`). 요청이 열린다. **보류는 유지**된다 |
| X 결과가 없거나 PASS | 거절 `RULE_RETEST` (`미해결 FAIL 없음`) |
| X에 이미 열린 요청이 있음 | 거절 `RULE_RETEST` (`이미 열린 재검사 요청`) |

**검사 결과 (`INSPECT X`)**
| 조건 | 결과 |
| --- | --- |
| X의 첫 결과 | 1단계와 같음 |
| X에 결과가 있고 열린 요청이 있음 | 재검사로 허용(`RULE_RETEST`). 요청은 닫히고 X의 재검사 횟수 +1 |
| X에 결과가 있고 열린 요청이 없음 | 거절 `RULE_PRESERVE` (`결과 이미 존재`, 1단계 T16과 같음) |

- 재검사 결과가 **PASS**: X의 현재 결과가 PASS가 된다. 다른 검사에 미해결 FAIL이 없으면 보류가 풀리고 멈췄던 공정부터 다시 진행할 수 있다.
- 재검사 결과가 **FAIL**: 보류 유지. 요청은 소진됐으므로 다시 시도하려면 새 요청이 필요하다.
- **폐기**: 재검사 횟수가 `retest_limit`(2)에 도달한 재검사 결과가 FAIL이면, 그 행을 **허용하면서** 제품을 폐기 상태로 바꾼다. 재검사 횟수는 검사마다 따로 센다(허용된 재검사 결과 수 기준, 요청 수 아님).
- 폐기 제품에 들어온 모든 입력(공정·검사·요청)은 거절 `RULE_RETEST` (`폐기된 제품`). 단 형식 오류·중복 등록은 기존 규칙이 먼저다.

**판정 순서** (재검사 모드): 1 형식 오류 `RULE_PRESERVE` → 2 `REGISTER` 처리(1단계와 같음) → 3 미등록 `RULE_PRESERVE` → 4 폐기된 제품 `RULE_RETEST` → 5 레시피에 없는 공정·검사 `RULE_RECIPE` → 6 이벤트별 규칙(공정은 1단계 순서, 검사는 시점 `RULE_INSP_PRE` → 위 표, 요청은 위 표).
- `RETEST_REQUEST`의 형식 오류: `inspection` 빈칸, `result` 또는 `model` 기입 → `RULE_PRESERVE`.
- 상태 불변: 거절 행은 공정 위치·검사 이력·열린 요청·재검사 횟수·폐기 여부를 바꾸지 않는다.

## 상태와 보고서 (재검사 모드)
- 상태 우선순위: `폐기` > `보류` > `레시피 모의 흐름 완료` > `등록` > `공정 진행 중(Pk 완료)` > `검사 대기`.
- 미완료 이유: 1단계 규칙에 더해, 열린 요청이 있는 FAIL은 `X FAIL(재검사 요청됨)`, 폐기 제품은 `X 재검사 한도 2회 초과 FAIL로 폐기`.
- products 열: `product_id,model,state,incomplete_reason,history`. history는 레시피 검사 순서대로 시도가 있는 검사만 `X: FAIL@5 → 요청@7 → PASS@9(재검사 1)` 형식, 검사 사이는 `; `. 숫자는 그 행의 seq.
- rows·rejections 형식은 1단계와 같다(rejections는 7개 규칙).

## 사전 기대표 (초안 – 사용자 확정 전)
표기: `a(A)` = 제품 a를 모델 A로 등록. 「a 보류」 = a(A) → P1~P3 → LEAK FAIL. 레시피는 `recipes/lamp_models_retest.json`.

| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T23 | a 보류 → `RETEST_REQUEST LEAK` → P4 | 요청 허용(`RULE_RETEST`), 보류 유지. P4는 `RULE_FAIL_HOLD` 거절 |
| T24 | a 보류 → 요청 → LEAK PASS → P4 → P5 → LIGHT PASS → FINAL PASS | 재검사 PASS 허용(`RULE_RETEST`), 보류 해소, 이후 모두 허용. a = 완료. history `LEAK: FAIL → 요청 → PASS(재검사 1)` 형식 |
| T25 | a 보류 → LEAK PASS (요청 없음) | `RULE_PRESERVE` 거절, FAIL·보류 유지 |
| T26 | a 보류 → 요청 → LEAK FAIL → LEAK PASS → 요청 → LEAK PASS | 첫 재검사 FAIL 허용·보류 유지. 요청 없는 PASS는 `RULE_PRESERVE` 거절. 새 요청 뒤 PASS 허용(재검사 2), 보류 해소 |
| T27 | a 보류 → 요청 → FAIL → 요청 → FAIL → P4 → `RETEST_REQUEST LEAK` → LIGHT PASS | 두 번째 재검사 FAIL 허용, a = 폐기. 뒤의 세 입력은 모두 `RULE_RETEST` 거절, 상태 불변 |
| T28 | ① LEAK을 아직 안 한 제품에 요청 ② LEAK PASS인 제품에 요청 ③ 열린 요청이 있는데 또 요청 ④ B 제품에 `RETEST_REQUEST FINAL` ⑤ 미등록 제품에 요청 ⑥ 요청 행에 result 기입 | ①②③ `RULE_RETEST` ④ `RULE_RECIPE` ⑤⑥ `RULE_PRESERVE`. 모두 상태 불변 |
| T29 | b(A) → P1~P3 → LEAK PASS → P4~P5 → LIGHT FAIL → FINAL FAIL → 요청 LIGHT → LIGHT PASS → 요청 FINAL → FINAL PASS | LIGHT 재검사 PASS 뒤에도 FINAL FAIL로 보류 유지. FINAL 재검사 PASS 뒤 b = 완료 |
| T30 | a 보류 → 요청 → FAIL → 요청 → PASS(LEAK 재검사 2회 소진) → P4~P5 → LIGHT FAIL → 요청 → LIGHT PASS | LIGHT는 별도 횟수로 재검사 허용(재검사 1), 폐기되지 않음 |
| T31 | 재검사 레시피를 각각 ① `retest_limit: 0` ② `"2"` ③ `true` ④ A에만 `retest_limit` ⑤ 공정 ID `RETEST_REQUEST` | 모두 종료 코드 3, 오류 위치 표시, 보고서 미생성 |
| T32 | ① 1단계 레시피(`lamp_models.json`)로 `RETEST_REQUEST` 행 실행 ② 같은 CSV를 재검사 레시피로 두 번 실행 | ① `RULE_RECIPE` 거절(1단계 동작 그대로) ② 보고서 3종·터미널 출력 바이트 동일 |

## 산출물
- `recipes/lamp_models_retest.json`, `tests/test_retest.py`(T23–T32, 거절은 전체 상태 불변까지 assert), T31용 레시피는 `tests/fixtures/`
- `data/sample_events_retest.csv`(T23–T30을 제품별로 담은 고정 입력)와 `reports/sample_events_retest_*.csv`
- README에 「재검사 모드」 절 추가(켜는 법, 규칙 표, 폐기 기준과 이유, 제외 범위)

## 완료 보고 (반드시 포함)
- 실제로 실행한 명령과 출력 원문(v1·1단계 회귀, 2단계 테스트, 샘플 실행)
- 기대표와 실제가 다르면 숨기지 말고 보고. 기대표·기존 테스트를 고쳐서 통과시키지 않는다
- 명세가 모호해 내린 해석·가정, 명세 이견

---

# v2 1단계 명세 (완료, 2026-10-18 · 리뷰 002 PASS)

## 작업: 모델별 공정 레시피 설정화

상태: **사용자 확정** (2026-10-18). 결정 근거는 `handoff/decisions.md`. 사용자가 확정하면 이 줄을 "사용자 확정"으로 바꾼다.
v1(아래 「v1 명세」)은 완료·동결 상태이며 `v1.0` 기준점으로 보존한다.

## 목표와 경계
- 제품 모델마다 공정 순서와 필수 검사가 다르다. 이를 JSON 레시피로 정의하고, 같은 판정 원칙(순서·검사 시점·보류·이력 보존)을 모델별로 적용한다.
- 모든 공정·검사·모델은 **가상 규칙**이다. SL 실제 공정·기준이 아니다. 최종 상태 "레시피 모의 흐름 완료"는 출하·양품·SL 기준 적합을 뜻하지 않는다.
- 이번 단계 제외: 재검사·보류 해제(2단계), 설비·로트(3단계), 대량 생성기(4단계), 분기·병렬·순환 공정(그래프), 검사 통과를 다음 공정 조건으로 거는 중간 관문, 실행 중 레시피 변경, 등록 정정, 외부 패키지.

## v1 보존 (가장 먼저 지킬 조건)
- `py -m src.main <CSV>`(옵션 없음)는 v1과 **완전히 같게** 동작한다. 입력 5열, 보고서 3종, 규칙 ID 5개, 상태명, 종료 코드 모두 그대로다.
- `src/rules.py`와 `tests/test_rules.py`는 수정하지 않는다. v2 판정은 새 모듈(예: `src/recipe.py`, `src/recipe_rules.py`)에 둔다. 공통으로 쓸 수 있는 작은 함수만 옮기는 것도 하지 않는다(v1 회귀 위험 차단).
- 회귀 확인: T1–T10 무수정 통과, `py -m src.main data/sample_events.csv`로 다시 만든 `reports/sample_events_*.csv` 3종이 커밋된 파일과 바이트 단위로 같다.

## 실행
- v2: `py -m src.main <입력CSV> --recipe <레시피JSON>`
- 테스트: `py -m unittest discover -s tests` (v1·v2 테스트 모두)
- 기본 레시피 파일: `recipes/lamp_models.json`

## 레시피 형식 (선형)
```json
{
  "A": {
    "steps": ["P1", "P2", "P3", "P4", "P5"],
    "inspections": [
      {"id": "LEAK",  "after": "P3"},
      {"id": "LIGHT", "after": "P5"},
      {"id": "FINAL", "after": "P5"}
    ]
  },
  "B": {
    "steps": ["P1", "P2", "P3", "P4"],
    "inspections": [
      {"id": "LEAK",  "after": "P2"},
      {"id": "LIGHT", "after": "P4"}
    ]
  }
}
```
- `steps`의 배열 순서가 곧 공정 순서다. 등록(`REGISTER`)은 공정 수에 포함하지 않는다.
- `after`: 그 검사를 입력할 수 있는 가장 이른 시점(해당 공정 완료 뒤). 검사 PASS를 다음 공정 진행 조건으로 걸지는 않는다.
- 모델·공정·검사 ID 형식: 대문자 영문으로 시작하고 대문자·숫자·`_`만 사용(`^[A-Z][A-Z0-9_]*$`). 비교는 대소문자·공백까지 정확히 일치.
- 허용 키는 모델 아래 `steps`, `inspections`, 검사 항목 아래 `id`, `after`뿐이다.

## 레시피 검증 (T18)
이벤트를 처리하기 전에 레시피 전체를 검사한다. 오류가 하나라도 있으면:
- 이벤트를 하나도 처리하지 않고, 보고서 파일을 만들지 않는다.
- **발견한 모든 오류**를 위치와 함께 출력한다(예: `A.steps[2]: 공정 ID 중복 P1`).
- 종료 코드 **3**으로 끝낸다. (v1의 입력 파일·CSV 오류는 기존대로 2)

오류로 볼 것: JSON 형식 오류, 최상위가 객체가 아님, 모델이 0개, `steps`가 배열이 아니거나 비어 있음, 공정 ID 중복, `REGISTER`·`INSPECT`를 공정 ID로 사용, `inspections`가 배열이 아니거나 비어 있음, 검사 ID 중복, `after` 누락, `after`가 그 모델에 없는 공정, 허용하지 않은 키(예: `next`), ID 형식 위반.

## 입력 형식 (v2 CSV)
`seq,product_id,event,inspection,result,model`
- `event`: `REGISTER` | `INSPECT` | 그 제품 레시피의 공정 ID(예: `P3`)
- `model`: `REGISTER` 행에만 쓴다. 다른 행에서는 빈칸.
- `inspection`, `result`: `INSPECT` 행에만 쓴다(`result`는 `PASS` | `FAIL`).
- `seq`, `product_id` 규칙과 물리적 행 순서 처리는 v1과 같다.
- `--recipe`를 줬는데 헤더가 v2 6열이 아니면 기존 CSV 오류와 같이 종료 코드 2. `--recipe` 없이 v2 헤더를 주면 v1 헤더 오류(종료 코드 2).

## 규칙 ID (v2)
| 규칙 ID | 의미 |
| --- | --- |
| `RULE_RECIPE` | **신규.** 레시피에 없는 모델로 등록, 등록 행의 `model` 빈칸, 그 제품의 레시피에 없는 공정·검사 |
| `RULE_SEQ` | 공정은 레시피 순서대로 한 단계씩. 앞 공정을 건너뛰면 거절 |
| `RULE_INSP_PRE` | 검사의 `after` 공정이 끝나기 전 검사 입력은 거절 |
| `RULE_NOT_DONE` | 공정이나 필수 검사가 남아 있으면 완료 불가 |
| `RULE_FAIL_HOLD` | FAIL이 하나라도 있으면 보류. **보류 제품의 다음 공정 입력은 거절**한다. 아직 실시하지 않은 다른 검사의 최초 결과는 시점 조건을 만족하면 받는다(v1과 같음) |
| `RULE_PRESERVE` | 형식 오류(열·seq·product_id·result 값·빈칸 규칙), 미등록 제품, 중복 등록(다른 모델 포함), 이미 지난 공정 재입력, 같은 검사 두 번째 결과 |

**판정 순서** (한 행이 여러 조건에 걸리면 먼저 걸린 것 하나로 거절):
1. 형식 오류 → `RULE_PRESERVE`
2. `REGISTER`: 이미 등록됨 → `RULE_PRESERVE` / `model` 빈칸·레시피에 없는 모델 → `RULE_RECIPE`
3. 미등록 제품 → `RULE_PRESERVE`
4. 그 제품 레시피에 없는 공정·검사 → `RULE_RECIPE`
5. 공정 입력: 이미 지난 공정 → `RULE_PRESERVE` / 보류 중 → `RULE_FAIL_HOLD` / 건너뜀 → `RULE_SEQ`
6. 검사 입력: `after` 공정 미완료 → `RULE_INSP_PRE` / 이미 결과 있음 → `RULE_PRESERVE`

**허용 행의 rule_id**: 등록 → `RULE_RECIPE`, 공정 → `RULE_SEQ`, 검사 → 반영 후 보류 또는 완료면 `RULE_FAIL_HOLD`, 아니면 `RULE_NOT_DONE`.

**상태 불변**: 거절된 행은 모든 제품의 공정 위치·검사 결과·모델을 바꾸지 않는다. 검증을 모두 통과한 뒤 한 번만 반영한다.

## 상태와 미완료 이유
- 상태 우선순위: `보류`(FAIL 있음) > `레시피 모의 흐름 완료`(모든 공정 + 모든 검사 PASS) > `등록`(공정 0개) > `공정 진행 중(Pk 완료)` > `검사 대기`(공정은 다 끝났고 검사가 남음)
- 미완료 이유: 남은 공정을 레시피 순서대로 `Pk 미완료`, 이어서 검사를 레시피 순서대로 `X 미실시` 또는 `X FAIL`. 구분자는 `; `.

## 보고서 (v2)
- 파일: `reports/<입력파일명>_rows.csv`, `_products.csv`, `_rejections.csv` (v1과 같은 3종)
- rows 열: v1과 같음. products 열: `product_id,model,state,incomplete_reason`. rejections: 규칙 ID 6개 모두(0건 포함), 위 표 순서.
- 터미널 첫머리에 사용한 레시피 경로와 내용의 SHA-256 앞 12자리를 출력한다. 재현성 기준은 **같은 CSV + 같은 레시피**다.

## 사전 기대표 (초안 – 사용자 확정 전. 확정 후에는 구현 결과에 맞춰 바꾸지 않는다)
표기: `a(A)` = 제품 a를 모델 A로 등록. 레시피는 위 `recipes/lamp_models.json` 기준.

| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T11 | a(A) → P1~P5 → LEAK PASS → LIGHT PASS → FINAL PASS | 모두 허용. a = 레시피 모의 흐름 완료 |
| T12 | a(A), b(B) 등록 → 두 제품 공정을 섞어 입력(a는 P1~P4, b는 P1~P4) → b LEAK PASS, LIGHT PASS | b = 완료. a = 공정 진행 중(P4 완료), 미완료 이유 `P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시`. 두 제품 판정이 섞이지 않음 |
| T13 | a(A) → P1 → P3 → P2 | P3는 `RULE_SEQ` 거절(`P2 미완료`), a는 P1 유지. 이어지는 P2는 허용 |
| T14 | ① a(A) → P1~P2 → LEAK PASS ② c(A) → P1~P4 → LIGHT PASS | ① `RULE_INSP_PRE` 거절(`P3 미완료`) ② `RULE_INSP_PRE` 거절(`P5 미완료`). 둘 다 결과 미저장 |
| T15 | a(A) → P1~P3 → LEAK PASS → P4~P5 → LIGHT PASS | LEAK는 공정 중간에 허용. 최종 a = 검사 대기, 미완료 이유 `FINAL 미실시` |
| T16 | a(A) → P1~P3 → LEAK FAIL → P4 → LEAK PASS | LEAK FAIL 허용, a = 보류. P4는 `RULE_FAIL_HOLD` 거절, a는 P3 유지. LEAK PASS는 `RULE_PRESERVE` 거절, FAIL 유지 |
| T16b | a(A) → P1~P5 → LIGHT FAIL → FINAL PASS | LIGHT FAIL로 보류. FINAL PASS는 허용(아직 없던 검사의 최초 결과), 보류 유지 |
| T17 | ① c(C) 등록(없는 모델) ② A 제품에 P6 ③ B 제품에 FINAL 검사 | 모두 `RULE_RECIPE` 거절. ①은 제품 미생성, ②③은 기존 상태 불변 |
| T18 | 레시피를 각각 ① 빈 steps ② `P1,P2,P1` ③ 검사 ID 중복 ④ steps가 문자열 ⑤ 알 수 없는 키 `next` ⑥ `after`가 없는 공정 ⑦ 위 오류 두 개를 한 파일에 | 모두 종료 코드 3, 보고서 미생성, 이벤트 미처리. ⑦은 두 오류가 모두 출력됨 |
| T19 | b(B) → P1~P4 → P5 | P5는 A에만 있는 공정이므로 `RULE_RECIPE` 거절. b 상태 불변 |
| T20 | ① 등록 행의 model 빈칸 ② 공정 행에 model 기입 | ① `RULE_RECIPE` 거절, 제품 미생성 ② `RULE_PRESERVE` 거절, 상태 불변 |
| T21 | 같은 CSV를 ① 같은 레시피로 두 번 ② LEAK `after`만 다른 레시피로 실행 | ① 보고서 3종과 터미널 출력이 바이트 단위로 같음 ② 해당 LEAK 행의 판정이 달라짐(예: B의 LEAK after P3이면 P2 뒤 LEAK는 `RULE_INSP_PRE`) |
| T22 | a(A) → P1~P2 → a를 B로 다시 REGISTER | `RULE_PRESERVE` 거절(`이미 등록된 제품`). a는 모델 A, P2 완료 유지 |

## 산출물
- `recipes/lamp_models.json` (위 레시피)
- `src/` v2 모듈, `src/main.py`에 `--recipe` 옵션 추가(옵션 없을 때 경로는 v1 그대로)
- `tests/test_recipe.py`: T11–T22 각각 테스트. 거절 사례는 전체 제품 상태 불변까지 assert. T18·T21용 레시피는 `tests/fixtures/`에 둔다
- `data/sample_events_v2.csv`: T11–T17, T19, T20, T22를 제품별로 담은 고정 입력과 그 보고서 `reports/sample_events_v2_*.csv`
- README에 v2 절 추가(실행법, 레시피 형식, 규칙 표, v1과의 관계, 제외 범위). v1 절은 지우지 않는다

## 완료 보고 (반드시 포함)
- 실제로 실행한 명령과 출력 원문(v1 회귀, v2 테스트, 샘플 실행)
- 기대표와 실제 결과가 다르면 숨기지 말고 보고한다. 기대표·테스트를 고쳐서 통과시키지 않는다
- 명세가 모호해 내린 해석·가정 목록

---

# v1 명세 (완료·동결, 2026-10-17)

## 작업: 교육용 가상 조립·검사 공정의 진행 조건 판정기 (Python CLI)

상태: 사용자 확정 (2026-10-17). 이 PC에서는 `python`이 Store 안내로 연결되므로 실행 명령만 `py`로 바꿨다. 나머지는 사용자 원문 그대로다.

## 배경과 경계
- 위치: project/ (현재 docs만 있고 src, tests는 비어 있음)
- 제조기술개발 직무 지원용 교육 프로젝트. 모든 공정 순서·검사 조건은 가상 규칙이며 SL 실제 기준이 아님.
- 점등(LIGHT)·누설(LEAK) 결과는 실측값이 아닌 합성 PASS/FAIL 입력.
- 핵심 질문: "이 제품이 다음 단계로 진행해도 되는가? 안 된다면 어떤 입력과 규칙 때문인가?"
- 마감이 임박함. 아래 범위만 구현하고 기능을 추가하지 말 것.

## 제외 (구현 금지)
재검사 요청·승인·보류 해제, DB, 사용자·권한, 웹 UI·차트, LLM/LangGraph/RAG, 외부 패키지.
FAIL 제품은 이번 버전에서 계속 보류됨. 새 PASS로 덮어써서 해결하면 안 됨.

## 기술 조건
- Python 3 표준 라이브러리만 사용. 테스트는 unittest.
- 실행: py -m src.main <입력CSV> → 터미널 보고서 출력 + reports/ 아래 CSV 저장
- 테스트: py -m unittest discover -s tests
- 같은 입력을 다시 실행하면 판정 결과가 같아야 함(시각·난수를 판정에 쓰지 말 것).

## 입력 형식 (CSV)
seq,product_id,event,inspection,result
- event: REGISTER | PRE_ASSEMBLY | MAIN_ASSEMBLY | INSPECT
- inspection, result: INSPECT일 때만 사용 (LIGHT|LEAK, PASS|FAIL), 나머지 event에서는 빈칸

## 규칙 (각 규칙에 ID를 붙여 보고서에 표시)
- RULE_SEQ: REGISTER → PRE_ASSEMBLY → MAIN_ASSEMBLY 순서. 선행 단계가 없으면 거절.
- RULE_INSP_PRE: MAIN_ASSEMBLY 완료 전 INSPECT는 거절.
- RULE_NOT_DONE: LIGHT·LEAK 중 하나라도 결과가 없으면 "검사 대기"이며 완료 불가.
- RULE_FAIL_HOLD: 하나라도 FAIL이면 "보류". 두 검사가 모두 PASS일 때만 "선택한 두 검사까지의 모의 흐름 완료".
- RULE_PRESERVE: 같은 제품·같은 검사의 두 번째 결과, 중복 조립 이벤트, 미등록 제품, 잘못된 값은 거절. 거절된 입력은 제품 상태와 기존 결과를 절대 바꾸지 않음.

## 반드시 지킬 설계 조건
- 판정 로직(src/rules.py 등)과 입출력(src/main.py)을 분리.
- 거절 시 "메시지만 출력하고 상태는 바뀌는" 오류가 없도록, 검증을 모두 통과한 뒤에만 상태를 변경.
- 최종 상태명 "모의 흐름 완료"는 출하·양품·SL 기준 적합을 뜻하지 않는다고 README에 명시.

## 보고서 형식
1) 행별: seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
2) 제품별 최종 상태와 미완료 이유
3) 규칙 ID별 거절 건수 집계

## 사전 기대표 (사용자가 확정함. 구현 결과에 맞춰 이 표를 바꾸지 말 것)
| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T1 | 등록→예비→본조립→LIGHT PASS→LEAK PASS | 모의 흐름 완료 |
| T2 | 등록→본조립(예비 없음) | 거절 RULE_SEQ, 상태 '등록' 유지 |
| T3 | 등록→예비→LIGHT PASS(본조립 전) | 거절 RULE_INSP_PRE, 결과 저장 안 됨 |
| T4 | 조립 완료→LIGHT PASS, LEAK 없음 | 검사 대기, 미완료 이유 'LEAK 미실시' |
| T5 | 조립 완료→LIGHT PASS→LEAK FAIL | 보류, 이유 'LEAK FAIL' |
| T6 | T5 뒤 LEAK PASS 추가 입력 | 거절 RULE_PRESERVE, 원래 FAIL·보류 유지 |
| T7 | T1 뒤 LIGHT FAIL 추가 입력 | 거절 RULE_PRESERVE, 완료 상태·원래 PASS 유지 |
| T8 | 예비 조립 두 번 | 두 번째 거절, 상태 변화 없음 |
| T9 | 미등록 제품 이벤트, result='OK' 같은 잘못된 값 | 거절, 다른 제품 상태 영향 없음 |
| T10 | 같은 입력 CSV를 두 번 실행 | 두 보고서의 판정 열이 동일 |

## 산출물
- src/, tests/ (T1–T10을 각각 테스트로. T2·T3·T6·T7·T8·T9는 거절 후 '상태 불변'까지 assert)
- data/sample_events.csv (T1–T9를 제품별로 담은 고정 입력)
- README.md를 이 범위로 갱신(실행법, 가상 규칙 경계, 제외 범위·한계).
  docs/requirements.md는 삭제하지 말고 맨 위에 "재검사 범위는 이번 버전에서 제외, 현행 기준은 README" 한 줄만 추가.

## 완료 보고 (반드시 포함)
- 실제로 실행한 명령과 출력 원문(테스트 결과 포함)
- 기대표와 실제 결과가 다른 항목이 있으면 숨기지 말고 그대로 보고. 기대표나 테스트를 고쳐서 통과시키지 말 것.
- 구현하면서 내린 해석·가정 목록 (명세가 모호했던 부분)
