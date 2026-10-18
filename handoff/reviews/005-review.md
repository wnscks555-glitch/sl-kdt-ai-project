# 리뷰 005 — v2 4단계 (합성 데이터 생성기·분석 보고서·추적, T42–T50)

- 검수자: Claude (읽기 전용)
- 검수일: 2026-10-18
- 범위: `git diff 51e3f83..HEAD`, `git log 51e3f83..HEAD` (dc7694e … a7956ab, 커밋 11개)
- 기준: `handoff/tasks.md` 맨 위 「현행 작업: v2 4단계」 명세·기대표 T42–T50·불변식 1–7, 그 아래 1–3단계 보존 조건
- 읽은 자료: `handoff/setup-notes.md`, `tasks.md`, `decisions.md`, `gpt-log.md`(4단계 절 전체), `src/generate.py`, `src/summary.py`, `src/reason_codes.py`, `src/trace.py`, `src/main.py` diff, `src/recipe_rules.py`, `src/equipment.py`, `tests/test_generate.py`, `tests/test_summary.py`, `recipes/generator.json`, `recipes/equipment_generated.json`, README 「생성기·분석·추적」 절, `reports/gen_seed42_summary.csv`
- 참고: `CLAUDE.md`, `tools/review-loop.ps1` 변경(a7956ab)은 검수 규칙·루프 설정이며 판정기 동작과 무관하다. 검수 대상에서 제외한다.

## 1. 테스트 실행 (직접 실행)

```text
$ py -m unittest discover -s tests
.................................................................................................
======================================================================
FAIL: test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors (test_generate.GeneratedInvariantTests) (requirement='discarded')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_generate.py", line 157, in test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors
    self.assertGreater(count, 0, "명세 이견: seed42 빈 검증 조건 미충족: " + requirement)
AssertionError: 0 not greater than 0 : 명세 이견: seed42 빈 검증 조건 미충족: discarded

----------------------------------------------------------------------
Ran 98 tests in 58.898s

FAILED (failures=1)
T44 seed=42 products=500 generation_seconds=0.108228 judgment_analysis_seconds=0.063679
T44 seed=7 products=200 generation_seconds=0.048139 judgment_analysis_seconds=0.025483
T44 seed=42 all_rows_deepcopy_invariant_seconds=38.363994
T44 seed=7 all_rows_deepcopy_invariant_seconds=5.865638
```
(터미널 인코딩 때문에 한글 경로·메시지가 깨져 출력된 부분은 같은 줄의 원문으로 옮겼다. 그 밖의 내용은 그대로다.)

결과: 98개 중 97개 통과, 1개 실패(종료 코드 1). gpt-log 「v2 4단계 완료 보고」의 최종 결과(98개·1 FAIL, 같은 테스트)와 일치한다.

## 2. 보존 조건 확인

| 항목 | 방법 | 결과 |
| --- | --- | --- |
| `src/rules.py`, 기존 테스트 4개(`test_rules.py`, `test_recipe.py`, `test_retest.py`, `test_equipment.py`) 무수정 | `git diff --stat 51e3f83..HEAD`에 없음 | 충족 |
| `src/recipe_rules.py`, `src/equipment.py`, `src/recipe_reports.py`, `recipes/equipment.json` 무수정 | 같은 diff stat에 없음 | 충족 |
| 기존 T1–T41 테스트 통과 | 위 전체 실행에서 실패는 T44 1건뿐 | 충족 |
| 기존 샘플 보고서 13개 바이트 동일 | 반례 P8: 임시 폴더에서 4개 샘플을 옵션 없이 다시 실행해 체크아웃 파일과 비교 | 충족 (13개 동일) |
| seed42 CSV·meta·보고서 6개 재현 | 반례 P8: 임시 폴더에서 다시 생성·실행해 체크아웃 파일과 비교 | 충족 (CSV·meta·6개 동일) |
| 리뷰 004 L1(보고서 개수로 모드 추정 금지) | `src/main.py`: `len(reports) == 4` → `equipment_mode=` 키워드 인자, summary·trace는 별도 함수·경로 | 충족 |
| `--summary`·`--trace` 없을 때 3단계와 동일 | `main.py` diff: 두 옵션이 없으면 `build_analysis`를 호출하지 않고, 기존 4종은 같은 함수로 쓴다 + P8 | 충족 |

## 3. 기대표 대조

| ID | 판정 | 근거 |
| --- | --- | --- |
| T42 | 일치 | `test_t42` 통과. meta에 시드·제품 수·3종 SHA-256·버전·행 수·주입 개수가 있음. P8에서 체크아웃된 meta와 바이트 동일 |
| T43 | 일치 | `test_t43` 통과 |
| T44 | **불일치** | 불변식 6의 폐기 1개 이상 조건 실패(→ H1). 불변식 1–5는 두 시드 모두 통과 |
| T45 | 일치 | 손 계산값 먼저 기록(`test_summary.py:45–72`). 파레토 순서·값까지 assert |
| T46 | 일치 | `test_t46` 통과. 정지 설비 거절 2건이 입력 오류 파레토에서 빠짐 |
| T47 | 일치 | 물리 순서·교차 제품 원인 seq 표시, seq 중복·감소, p/P 파일 분리까지 검사 |
| T48 | 일치 | 없는 ID·비설비 모드 모두 종료 2, 보고서 미생성 |
| T49 | 일치 | 표에 없는 문구면 `ValueError`, 쓰기 전에 실패 |
| T50 | 일치 | P8로 다시 확인 |

## 4. 반례 탐색

파일: `handoff/reviews/probes/test_probe_005.py` (임시 폴더만 쓴다. 저장소 `reports/`·`data/`는 쓰지 않음)

```text
$ py -m unittest handoff/reviews/probes/test_probe_005.py
FF...F..
======================================================================
FAIL: test_p1_ratio_half_tie_rounds_up (handoff.reviews.probes.test_probe_005.Probe005)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "...\handoff\reviews\probes\test_probe_005.py", line 45, in test_p1_ratio_half_tie_rounds_up
    self.assertEqual(_ratio(1, 32), "0.0313")
AssertionError: '0.0312' != '0.0313'
- 0.0312
?      ^
+ 0.0313
?      ^


======================================================================
FAIL: test_p2_malformed_meta_exits_2_without_reports (handoff.reviews.probes.test_probe_005.Probe005) (meta='array')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "...\handoff\reviews\probes\test_probe_005.py", line 57, in test_p2_malformed_meta_exits_2_without_reports
    self.assertEqual(run.returncode, 2, stderr[-400:])
AssertionError: 1 != 2 : ry=args.summary, trace=args.trace)
  File "...\project\src\main.py", line 133, in run_recipe
    summary_rows = build_summary(analysis, meta)
  File "...\project\src\summary.py", line 195, in build_summary
    normal_rows = meta["normal_rows"]
TypeError: list indices must be integers or slices, not str


======================================================================
FAIL: test_p2_malformed_meta_exits_2_without_reports (handoff.reviews.probes.test_probe_005.Probe005) (meta='missing_keys')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "...\handoff\reviews\probes\test_probe_005.py", line 57, in test_p2_malformed_meta_exits_2_without_reports
    self.assertEqual(run.returncode, 2, stderr[-400:])
AssertionError: 1 != 2 : ecipe, parser, args.equipment, summary=args.summary, trace=args.trace)
  File "...\project\src\main.py", line 133, in run_recipe
    summary_rows = build_summary(analysis, meta)
  File "...\project\src\summary.py", line 195, in build_summary
    normal_rows = meta["normal_rows"]
KeyError: 'normal_rows'


======================================================================
FAIL: test_p3_small_product_counts_generate (handoff.reviews.probes.test_probe_005.Probe005)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "...\handoff\reviews\probes\test_probe_005.py", line 71, in test_p3_small_product_counts_generate
    self.assertEqual(failures, [])
AssertionError: Lists differ: [(4, 39, '오류 주입 위치 없음: RECIPE_UNKNOWN_STEP')] != []

First list contains 1 additional elements.
First extra element 0:
(4, 39, '오류 주입 위치 없음: RECIPE_UNKNOWN_STEP')

- [(4, 39, '오류 주입 위치 없음: RECIPE_UNKNOWN_STEP')]
+ []

======================================================================
FAIL: test_p7_discard_reachable_over_seeds (handoff.reviews.probes.test_probe_005.Probe005)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "...\handoff\reviews\probes\test_probe_005.py", line 156, in test_p7_discard_reachable_over_seeds
    self.assertGreater(sum(discards.values()), 0)
AssertionError: 0 not greater than 0

----------------------------------------------------------------------
Ran 9 tests in 25.481s

FAILED (failures=5)
P3 failures: 1 [(4, 39, '오류 주입 위치 없음: RECIPE_UNKNOWN_STEP')]
P6 inspection_metrics keys: ['ALL', '', 'AIM', 'FINAL', 'LEAK', 'LIGHT']
P7 seeds_with_discard: 0 total_discards: 0 first_fails_total: 2600
```
(긴 저장소 경로는 `...`로 줄였고, 깨져 출력된 한글은 원문으로 옮겼다.)

9개 중 4개 테스트 실패(P2는 하위 테스트 2개 모두 실패). 실패 표시 5건.

| # | 입력 | 예상 (명세 근거) | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P1 | `_ratio(1, 32)` (0.03125, 이진수로 정확한 동점) | `0.0313` — 「비율은 소수 넷째 자리 반올림」, README:387 「반올림한 문자열」 | `0.0312` (Python `format`의 동점 짝수 맞춤) | **실패 → M1** |
| P2 | 입력 옆 `in.csv.meta.json`이 `[]` 또는 `{}`, `--summary` | 입력 파일 오류와 같이 종료 코드 2, 메시지 출력(README:137 「입력 파일·파싱 오류는 종료 코드 2」) | 트레이스백, 종료 코드 1 (`TypeError` / `KeyError`). 보고서는 쓰지 않음 | **실패 → M2** |
| P3 | `generate(seed, products)`, products 4·5·6 × 시드 1–40 | 생성 성공(명세는 `--products`에 양의 정수만 요구) | products=4·시드 39에서 `오류 주입 위치 없음: RECIPE_UNKNOWN_STEP`(B 제품 없음)로 생성 실패. 나머지 119건은 성공 | **실패 → M3** |
| P4 | 시드 1–20 × 200개 생성 → summary | 종류별 주입 수 = 실제 상세 코드 거절 수, 정지 설비 거절 0(주입 행은 반드시 거절되고 상태를 바꾸지 않음) | 20개 시드 모두 일치 | 통과 |
| P5 | seed42 생성 결과·3단계 샘플의 상태 분포 6칸 합 | = 등록 제품 수(빠진 상태 문구 없음) | 일치 | 통과 |
| P6 | 이전 단계 모드 조합: **재검사 없는 레시피**(`lamp_models.json`) + 설비 모드. LEAK-2 FAIL 2건으로 정지 → 정지 설비 결과, `RETEST_REQUEST`, 공백 product_id, 빈 inspection, 없는 검사 `AIM`, 시점 전 LIGHT, 미등록 제품 | 거절 7 = 입력 오류 6(코드별 1) + 정지 1. trace c의 정지 거절에 정지 행 17/b, 원인 16;17 / a;b. history `LEAK: PASS@24[LEAK-1]` | 모두 예상대로. 다만 inspection_metrics에 key가 빈 문자열인 행이 생김 | 통과 (빈 key 행은 L1) |
| P7 | 시드 1–100 × 500개, 기본 설정 | 명세 불변식 6이 성립하려면 폐기가 도달 가능해야 함 | 100개 시드 모두 폐기 0. 최초 FAIL은 합계 2,600건 | **실패 → H1 근거** (구현 결함이 아니라 명세 설정에서 생기는 결과) |
| P8 | 임시 폴더에서 기존 샘플 4종 다시 실행 + seed42 다시 생성·`--summary --trace GEN_0005` | 체크아웃 파일과 바이트 동일(보존 조건, T50, 불변식 1) | 보고서 19개, CSV·meta 모두 동일 | 통과 |
| P9 | 같은 `--trace x`를 두 번 + 등록이 안 된 ID `ghost`(거절 행만 있음) | 종료 0, 파일 생성, ghost는 「미등록」 | 예상대로 | 통과 |

## 5. 지적 사항

### H1
- 심각도: **높음**
- 파일:줄: `tests/test_generate.py:157` (원인 설정은 `recipes/generator.json`, `src/generate.py:55–69`)
- 문제: T44 기대 결과 「불변식 1–6 모두 통과」와 다르다. 시드 42의 폐기 제품이 0개라 불변식 6을 충족하지 못한다. 그 결과 불변식 3의 「폐기 뒤 허용 행 없음」 부분도 시드 42·7에서 대상 0개로 실제로 검증되지 않는다(`test_t44_no_accepted_events_after_discard_or_equipment_stop`의 `discarded` 분기가 한 번도 실행되지 않음).
- 근거: 직접 실행 결과 `AssertionError: 0 not greater than 0 : … discarded`. P7에서 시드 1–100(각 500개)이 모두 폐기 0이고, 최초 FAIL은 합계 2,600건이다. 폐기되려면 최초 FAIL → 요청(70%) → 재검사 FAIL → 요청(70%) → 재검사 FAIL이 이어져야 한다. 그런데 재검사는 「가능하면 다른 설비」로 가고, 고장 설비 LEAK-2는 최초 결과 몇 건 만에 정지한다(seed42 seq 1556). 그래서 재검사 FAIL 확률은 사실상 정상 설비의 2%다. 최초 FAIL 1건당 폐기 확률은 대략 0.7×0.02×0.7×0.02 ≈ 0.0002이고, 2,600건이면 기대값이 약 0.5건이다. 관측값 0과 어긋나지 않는다.
- GPT 의견에 대한 판단: **동의.** gpt-log의 「명세 이견: 폐기 희소」 분석은 P7 반례 탐색 결과와 맞는다. 생성기 코드를 읽어도 폐기 경로(`attempt == retest_limit`에서 FAIL이면 종료, 판정기는 `count >= retest_limit and FAIL`이면 폐기)는 명세대로 구현됐다. 시드·확률·테스트를 몰래 바꾸지 않고 실패를 유지·공개한 처리도 명세(불변식 6, 「완료 보고」)를 따른 것이다. 구현 결함이 아니라 명세의 설정값끼리 충돌한 결과다.
- 제안: 사용자 결정이 필요하다. Codex가 혼자 고칠 항목이 아니다. 선택지 예: ① 생성 설정에 재검사 FAIL 확률을 따로 둔다(예: 처음 FAIL한 제품의 재검사 FAIL 확률 = 제품 결함 가정값). ② 고장 설비에서 재검사를 허용한다. ③ 불변식 6의 폐기 조건을 별도 고정 시나리오(T36)로 옮긴다. 결정한 뒤 `tasks.md`·`decisions.md`에 기록하고, 생성 버전 상수와 seed42 산출물을 함께 갱신한다.

### M1
- 심각도: **중간**
- 파일:줄: `src/summary.py:89`
- 문제: 비율 문자열이 정확한 동점에서 짝수 쪽으로 맞춰진다. `format(x, ".4f")`를 쓰기 때문이다. 1/32 = 0.03125는 `0.0312`가 된다. README:387과 명세는 「반올림」이라고 적고 있어 문서와 동작이 다르다.
- 근거: P1. 분모가 32·160·800·… 처럼 소수 다섯째 자리에서 5로 정확히 끝나는 비율(최초 FAIL률, FPY, 주입률 등)에서 값이 0.0001 차이 난다. 명세 예시 `0.0312`가 우연히 1/32의 짝수 맞춤 결과와 같아서 의도가 모호하다.
- 제안: 사용자가 「반올림」의 뜻(사사오입 / 짝수 맞춤)을 정한다. 사사오입이면 `decimal.Decimal(numerator) / Decimal(denominator)`에 `quantize(Decimal("0.0001"), ROUND_HALF_UP)`를 쓰고 동점 테스트를 추가한다. 짝수 맞춤을 유지하면 README에 그 규칙을 적는다.

### M2
- 심각도: **중간**
- 파일:줄: `src/main.py` 126–131(meta 읽기), `src/summary.py:195–196`
- 문제: 입력 옆 meta.json이 JSON으로는 올바르지만 구조가 다르면(최상위 배열, `normal_rows`/`injected_errors` 누락, 값 타입 오류) `TypeError`/`KeyError` 트레이스백이 나고 종료 코드 1로 끝난다. 다른 입력 오류는 모두 메시지와 함께 종료 코드 2로 끝나는데, 이 경우만 설명할 수 없는 결과가 된다. 보고서를 쓰기 전이라 부분 출력은 없다.
- 근거: P2 하위 테스트 2개 실패. `except` 목록은 `(OSError, UnicodeError, csv.Error, ValueError)`뿐이다.
- 제안: meta를 읽은 직후 dict 여부, `normal_rows` 정수, `injected_errors` dict(값 정수)를 검사하고 어기면 `ValueError`로 종료 2를 낸다. 회귀 테스트를 추가한다.

### M3
- 심각도: **중간**
- 파일:줄: `src/generate.py:133–134`
- 문제: 제품 수가 작아 B 모델이 하나도 뽑히지 않았는데 주입 개수 배분에서 `RECIPE_UNKNOWN_STEP`에 1개 이상이 걸리면 생성 전체가 `오류 주입 위치 없음`으로 실패한다(종료 2). 명세는 `--products`에 양의 정수만 요구하고, 이 제약은 README·gpt-log 어디에도 공개되지 않았다.
- 근거: P3에서 products=4·시드 39가 실패했다. 다른 종류도 후보가 없으면 같은 경로로 실패한다(예: 모든 제품이 첫 행에서 끝나는 극단 설정).
- 제안: 사용자가 동작을 정한다. ① 후보가 없는 종류는 0개로 두고 meta에 「배정 불가」를 기록한다. ② 현재처럼 실패시키되 README에 최소 조건을 적고 메시지에 이유(B 제품 없음)를 표시한다. 어느 쪽이든 테스트를 추가한다.

### L1 (낮음, 기록만)
- 파일:줄: `src/summary.py:140`, `:148`
- 문제: inspection이나 equipment가 비어서 거절된 INSPECT 행이 있으면 inspection_metrics·equipment_metrics에 key가 `""`인 행이 생긴다(P6에서 `['ALL', '', 'AIM', …]`). 값은 맞지만 표에서 무엇인지 읽기 어렵다.
- 제안: key를 `(빈칸)` 같은 표시로 바꾸거나 README에 설명한다.

### L2 (낮음, 기록만)
- 파일:줄: `src/generate.py:160–166`, `src/main.py:126`
- 문제: meta에 생성된 CSV 자체의 SHA-256이 없다. 그래서 입력 CSV를 고친 뒤에도 옆의 meta가 그대로 「주입 대비」 절에 쓰이고, 일치 여부를 확인할 수 없다. 명세는 CSV 해시를 요구하지 않았다.
- 제안: 다음 버전에서 meta에 출력 CSV 해시를 넣고, summary에서 다르면 경고하거나 절을 생략한다.

### L3 (낮음, 기록만)
- 파일:줄: `src/generate.py:57–58`
- 문제: 같은 검사의 설비가 모두 정지하면 생성기는 그 제품의 남은 공정까지 만들지 않는다. 그래서 A 모델의 LEAK(after P3)에서 멈추면 판정기 상태가 명세 괄호 속의 「검사 대기」가 아니라 「공정 진행 중(P3 완료)」이 된다. gpt-log에 해석으로 공개됐고, seed42에서는 해당 제품이 0개라 산출물에는 영향이 없다.
- 제안: 사용자가 해석을 확인해 `decisions.md`에 남긴다.

## 6. GPT 의견에 동의하는 부분 (반례 탐색 후)
- 명세 이견(폐기 0)의 원인 분석과 실패 유지·공개: 동의(H1, P7 근거).
- 주입 오류는 반드시 거절되는 위치에만 끼워 넣어 정상 행이 바뀌지 않는다는 설명: 동의. P4에서 시드 20개 모두 종류별 주입 수와 실제 사유 코드 거절 수가 같고 정지 설비 거절이 0이다. 시드 42·7에서는 모든 행 deepcopy 불변식도 통과했다.
- 상세 사유 코드 28종이 판정기의 모든 거절 문구를 덮는다는 주장: 동의. `recipe_rules.py`의 거절 문구 28개(형식 11, 등록·미등록·폐기, 레시피, 재검사, 설비, 시점·순서·보류)를 표와 하나씩 대조했고, P6(재검사 없는 레시피 + 설비 모드)에서 6개 코드가 실패 없이 분류됐다.
- 리뷰 004 L1 반영(명시적 `equipment_mode`): 동의. 기존 출력 바이트 보존을 P8로 확인했다.
- `CLAUDE.md`·`tools/review-loop.ps1` 변경은 Codex 작업에 넣지 않았다는 기록: diff상 a7956ab 커밋에만 있으며 판정기 코드와 무관하다. 동의.

## 7. 요약
- 높음 1(H1, 명세 설정 충돌로 T44 미충족, 사용자 결정 필요), 중간 3(M1 반올림 동점, M2 잘못된 meta 트레이스백, M3 소량 생성 실패 미공개), 낮음 3(기록만).
- 보존 조건(기존 테스트 무수정 통과, 기존 보고서 13개 바이트 동일, 보호 파일 무수정)은 모두 충족.
- 미검증: 없음(테스트·반례는 모두 직접 실행).

VERDICT: FIX
