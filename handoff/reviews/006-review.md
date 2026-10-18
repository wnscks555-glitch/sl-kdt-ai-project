# 리뷰 006 — 리뷰 005 수정 재검토 (v2 4단계, T42–T50)

- 검수자: Claude (읽기 전용)
- 검수일: 2026-10-18
- 범위: `git diff 9f372f8..HEAD` (커밋 322ec81 `fix: apply review 005 (loop 1/2)`). 변경 파일: `README.md`, `handoff/gpt-log.md`, `handoff/loop-logs/005-codex.txt`, `src/generate.py`, `src/main.py`, `src/summary.py`, `tests/test_generate.py`, `tests/test_summary.py`
- 기준: `handoff/tasks.md` 맨 위 「현행 작업: v2 4단계」 명세·기대표 T42–T50·불변식 1–7, 그 아래 1–3단계 보존 조건
- 읽은 자료: `handoff/setup-notes.md`, `tasks.md`, `decisions.md`, `gpt-log.md`(「리뷰 005 수정 단계」 절), `handoff/reviews/005-review.md`, 위 diff 전체, `src/main.py:95–175`, `src/summary.py:89–208`, `src/generate.py:94–175`

## 1. 테스트 실행 (직접 실행)

```text
$ py -m unittest discover -s tests
....................................................................................................
======================================================================
FAIL: test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors (test_generate.GeneratedInvariantTests) (requirement='discarded')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_generate.py", line 171, in test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors
    self.assertGreater(count, 0, "명세 이견: seed42 빈 검증 조건 미충족: " + requirement)
AssertionError: 0 not greater than 0 : 명세 이견: seed42 빈 검증 조건 미충족: discarded

----------------------------------------------------------------------
Ran 101 tests in 68.343s

FAILED (failures=1)
T44 seed=42 products=500 generation_seconds=0.147707 judgment_analysis_seconds=0.099003
T44 seed=7 products=200 generation_seconds=0.060412 judgment_analysis_seconds=0.032980
T44 seed=42 all_rows_deepcopy_invariant_seconds=43.223879
T44 seed=7 all_rows_deepcopy_invariant_seconds=6.115800
```
(터미널 인코딩 때문에 깨져 출력된 한글 경로·메시지는 원문으로 옮겼다. 그 밖의 내용은 그대로다.)

결과: 101개 중 100개 통과, 1개 실패. 리뷰 005의 98개에 새 회귀 3개(`test_review005_m1_*`, `test_review005_m2_*`, `test_review005_m3_*`)가 더해졌고 셋 다 통과했다. 실패는 리뷰 005와 같은 T44 폐기 조건 1건뿐이다.
참고: gpt-log는 Codex 환경에서 `No installed Python found!`로 테스트를 한 번도 실행하지 못했다고 공개했다. 위 실행이 이 수정의 첫 실행 검증이다.

## 2. 보존 조건 확인

| 항목 | 방법 | 결과 |
| --- | --- | --- |
| `src/rules.py`, 기존 테스트 4개 무수정 | `git diff --stat 9f372f8..HEAD`에 없음 | 충족 |
| `src/recipe_rules.py`, `src/equipment.py`, `src/recipe_reports.py`, `recipes/*`, `data/`, `reports/` 무수정 | 같은 diff stat에 없음 | 충족 |
| 기존 T1–T41 테스트 통과 | 위 전체 실행에서 실패는 T44 1건뿐 | 충족 |
| 기존 테스트 기대값 무수정 | `tests/` diff는 새 테스트 함수 3개와 import 추가뿐 | 충족 |
| 기존 샘플 보고서 13개 + seed42 CSV·meta·보고서 6개 바이트 동일 (M1 반올림 변경 영향 포함) | 반례 P1: 임시 폴더에서 다시 실행·생성해 체크아웃 파일과 비교 | 충족 (19개 보고서, CSV·meta 모두 동일) |
| `--summary`·`--trace` 없을 때 3단계와 동일 | `main.py` diff는 `if summary:` 블록 안쪽만 바뀜 + P1 | 충족 |

## 3. 이전 지적 항목 판정

| 항목 | 판정 | 근거 |
| --- | --- | --- |
| H1 (T44 폐기 0건, 명세 설정 충돌) | **미해결** | 위 실행에서 같은 실패가 그대로 남았다. gpt-log는 반박이 아니라 「보류: 사용자 결정 필요」로 처리했다. 이 처리 자체는 명세(불변식 6 「시드·확률을 몰래 바꾸지 말고 명세 이견으로 보고」)와 `decisions.md` 「빈 검증 방지」 결정을 따른 것이라 **동의**한다. 다만 `decisions.md`에 H1에 대한 사용자 결정이 아직 없고 T44 기대 결과(불변식 1–6 모두 통과)와 실제가 다르므로 높음으로 남는다. |
| M1 (반올림 동점) | **해결** | `src/summary.py:89–93`이 `Decimal` + `ROUND_HALF_UP`으로 바뀌었고 README:391에 「사사오입(예: 1/32 → 0.0313)」을 적었다. 새 회귀 `test_review005_m1_ratio_rounds_half_up` 통과. 반례 P2(0.00005, 1/3, 2/3, 99995/100000 등) 통과. 반례 P1에서 seed42 summary가 체크아웃 파일과 바이트 동일해 기존 산출물 값은 바뀌지 않았다. P3의 정밀도 한계는 도달할 수 없는 입력이라 낮음(L1)으로만 기록한다. |
| M2 (잘못된 meta 구조 트레이스백) | **해결** | `src/main.py:131–138`이 객체 여부, `normal_rows`의 0 이상 정수(bool 제외), `injected_errors` 객체·값 0 이상 정수를 검사하고 `ValueError` → 종료 2로 보낸다. 새 회귀(배열·null·누락·문자열·실수·bool·음수 15건) 통과. 반례 P6(NaN·Infinity·디렉터리 경로·깨진 JSON·중첩 dict 값) 모두 종료 2, 트레이스백 없음, 보고서 미생성. P5(값 0·일부 종류만·BOM·큰 정수)는 정상 처리. P7: `--summary` 없이 `--trace`만 주면 잘못된 meta를 읽지 않음(이전 동작 유지). 단 알 수 없는 종류 키는 통과시킨다 → 새 지적 M1. |
| M3 (소량 생성 실패 미공개) | **해결** | 리뷰 제안 ②(현 정책 유지 + 공개)를 택했다. README:370에 조건과 예시(`--seed 39 --products 4`)를 적었고, 메시지에 종류·배정 수·후보 0개·B 부재 이유가 나온다(`src/generate.py:134–138`). 새 회귀 통과. 반례 P8(제품 1–8 × 시드 1–60, 480건): 실패 3건(4/39, 5/45, 6/45) 모두 `ValueError` + 「배정 1건, 후보 0개; B 제품 없음」, 출력 파일 없음. 다른 예외 0건. P9: 실패 시 기존 CSV·meta를 덮어쓰지 않는다는 README 문장 확인. 재배분을 하지 않은 이유(5종 균등·3% 조건 유지)도 명세와 맞아 동의한다. |
| L1–L3 (낮음) | 기록 유지 | 이번 수정 범위 밖(gpt-log 명시). 수정 요구로 세지 않는다. |

## 4. 반례 탐색

파일: `handoff/reviews/probes/test_probe_006.py` (임시 폴더만 쓴다. 저장소 `reports/`·`data/`는 쓰지 않음)

```text
$ py -m unittest handoff/reviews/probes/test_probe_006.py
..FF.....
======================================================================
FAIL: test_p3_ratio_beyond_decimal_precision (handoff.reviews.probes.test_probe_006.Probe006)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "...\handoff\reviews\probes\test_probe_006.py", line 87, in test_p3_ratio_beyond_decimal_precision
    self.assertEqual(_ratio(10 ** 29 - 1, 2 * 10 ** 33), "0.0000")  # 유효숫자 29자리: 28자리에서 잘림
AssertionError: '0.0001' != '0.0000'
- 0.0001
?      ^
+ 0.0000
?      ^


======================================================================
FAIL: test_p4_meta_unknown_injection_key (handoff.reviews.probes.test_probe_006.Probe006)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "...\handoff\reviews\probes\test_probe_006.py", line 102, in test_p4_meta_unknown_injection_key
    self.assertEqual(total, per_kind)
AssertionError: 6 != 1

----------------------------------------------------------------------
Ran 9 tests in 5.007s

FAILED (failures=2)
P4 per_kind: 1 TOTAL: 6
P8 failures: 3 of 480; [(4, 39, '오류 주입 위치 없음: RECIPE_UNKNOWN_STEP (배정 1건, 후보 0개; B 제품 없음: B 제품의 P5 행을 주입할 수 없음)'), (5, 45, '오류 주입 위치 없음: RECIPE_UNKNOWN_STEP (배정 1건, 후보 0개; B 제품 없음: B 제품의 P5 행을 주입할 수 없음)'), (6, 45, '오류 주입 위치 없음: RECIPE_UNKNOWN_STEP (배정 1건, 후보 0개; B 제품 없음: B 제품의 P5 행을 주입할 수 없음)')]
```
(긴 저장소 경로는 `...`로 줄였고, 깨져 출력된 한글은 원문으로 옮겼다.)
참고: 첫 실행에서 P7이 실패했는데, 프로브가 고정 입력에 없는 제품 ID `p1`을 써서 생긴 프로브 오류였다(종료 2 `입력에 없는 제품 ID: p1`, 명세 T48대로). ID를 `a`로 고쳐 다시 실행한 결과가 위 출력이다. 같은 수정에서 P3에 유효숫자 29자리 경우를 더했고 P8 범위를 제품 1–3에서 1–8로 넓혔다.

| # | 입력 | 예상 (명세 근거) | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P1 | 임시 폴더에서 기존 샘플 4종 옵션 없이 실행 + seed42 다시 생성·`--summary --trace GEN_0005` | 체크아웃 파일과 바이트 동일(보존 조건, T50, 불변식 1). 반올림 변경으로 seed42 summary 값이 바뀌지 않아야 함 | 보고서 19개, CSV·meta 모두 동일 | 통과 |
| P2 | `_ratio` 경계: 5/100000, 4/100000, 1/3, 2/3, 7/7, 99995/100000, 99994/100000 | `0.0001`, `0.0000`, `0.3333`, `0.6667`, `1.0000`, `1.0000`, `0.9999` (README:391 사사오입) | 모두 일치 | 통과 |
| P3 | `_ratio(10**29-1, 2*10**33)` (참값 0.0000499…, 유효숫자 29자리) | `0.0000` (사사오입) | `0.0001`. `Decimal` 기본 정밀도 28자리에서 나눗셈이 먼저 반올림돼 이중 반올림. 유효숫자 26자리(`10**26-1`)는 정확 | **실패 → L1** (분모가 행 수라 10³³ 행은 만들 수 없음. 도달 불가 입력) |
| P4 | meta `{"normal_rows": 24, "injected_errors": {"SEQ_SKIP": 1, "FOO": 5}}` + `--summary` | 알 수 없는 종류는 거절(종료 2)하거나, 표시한다면 TOTAL 주입 수 = 종류별 행 합. 명세 「주입 오류 종류별 개수와 실제 사유 코드별 거절 수를 나란히 표시」, 사유 절의 「숨은 사유 없음」 원칙 | 종료 0. 종류별 행 합 1, TOTAL `injected_count` 6, TOTAL 주입률도 6/24로 계산. `FOO` 행은 어디에도 없음 | **실패 → 새 M1** |
| P5 | 유효 경계 meta: `normal_rows` 0, 일부 종류만, BOM, `normal_rows`=10³⁰ | 종료 0, 분모 0은 빈칸, 빠진 종류는 0 | 예상대로 | 통과 |
| P6 | meta: `NaN`, `Infinity` 값, meta 경로가 디렉터리, 깨진 JSON, 값이 중첩 객체 | 종료 2, 트레이스백 없음, 보고서 미생성 (README:372) | 5건 모두 예상대로 | 통과 |
| P7 | 잘못된 meta(`[]`)가 옆에 있는 입력에 `--summary` 없이 `--trace a`만 | 종료 0, meta를 읽지 않음, summary 미생성(이전 동작 보존) | 예상대로 | 통과 |
| P8 | `generate(seed, products)`, 제품 1–8 × 시드 1–60 (480건) | 실패는 `ValueError` + 「배정 N건, 후보 0개」 이유 표시, 출력 파일 없음(README:370) | 실패 3건 모두 이유 표시, 파일 없음. 다른 예외 0 | 통과 |
| P9 | 기존 `small.csv`·meta가 있는 상태에서 `--seed 39 --products 4` 실행 | 종료 2, 기존 두 파일 그대로(README:370 「기존 출력도 덮어쓰지 않습니다」) | 예상대로 | 통과 |

## 5. 지적 사항

### H1 (리뷰 005 H1, 미해결)
- 심각도: **높음**
- 파일:줄: `tests/test_generate.py:171` (원인 설정 `recipes/generator.json`, `src/generate.py:55–69`)
- 문제: T44 기대 결과 「불변식 1–6 모두 통과」와 다르다. 시드 42의 폐기 제품이 0개라 불변식 6을 충족하지 못하고, 불변식 3의 「폐기 뒤 허용 행 없음」 분기도 대상이 없어 실제로 검증되지 않는다.
- 근거: 위 전체 실행의 `AssertionError: 0 not greater than 0 : … discarded`. 원인 분석은 리뷰 005 H1·P7과 같다(재검사가 정상 설비로 가서 재검사 FAIL 확률이 사실상 2%).
- GPT 의견에 대한 판단: gpt-log의 「보류」 처리에 **동의**한다. 반례를 다시 찾아봐도 생성기·판정기의 폐기 경로는 명세대로 구현됐다. 시드·확률·테스트를 바꾸지 않고 실패를 공개한 것도 명세와 `decisions.md` 「빈 검증 방지」를 따른다. 하지만 이는 반박이 아니라 결정 대기이므로 해결로 처리하지 않는다.
- 제안: 사용자가 리뷰 005 H1의 선택지(① 제품 결함 재검사 FAIL 확률 별도 설정 ② 고장 설비 재검사 허용 ③ 폐기 조건을 고정 시나리오 T36으로 이전 등) 가운데 하나를 정해 `tasks.md`·`decisions.md`에 기록한다. 그 뒤 Codex가 생성 버전 상수와 seed42 산출물을 함께 갱신한다.

### M1 (새 지적)
- 심각도: **중간**
- 파일:줄: `src/main.py:135–138`, `src/summary.py:201–207`
- 문제: meta의 `injected_errors`에 5종 밖의 키(예: `FOO`)가 있으면 검사를 통과한다. summary의 `injection_comparison` 절은 종류별 행에서 그 키를 빼지만, TOTAL 행의 `injected_count`와 `injection_rate`에는 `sum(injected.values())`로 더한다. 그래서 TOTAL이 종류별 행 합과 다르고, 차이를 만든 키는 표 어디에도 나오지 않는다.
- 근거: 반례 P4. 종류별 합 1, TOTAL 6, 종료 0. 리뷰 005 M2 수정이 「구조가 잘못된 meta는 종료 2」로 정했는데(README:372) 키 검사는 빠졌다. 명세의 「숨은 사유 없음」 원칙과 맞지 않는 설명할 수 없는 값이다. 생성기가 쓰는 meta에서는 생기지 않고 손으로 고친 meta에서만 생긴다. 리뷰 005 L2(meta와 CSV의 연결 확인 수단 없음)와 겹치는 위험이다.
- 제안: M2 검사에 `set(injected) <= set(INJECTED_ERROR_CODES)`를 더해 어기면 `ValueError`(종료 2)로 처리하고 README:372에 「키는 5종 코드만」을 적는다. 또는 TOTAL을 5종 합으로만 계산한다. 어느 쪽이든 회귀 테스트를 추가한다.

### L1 (낮음, 기록만)
- 파일:줄: `src/summary.py:92`
- 문제: `Decimal` 나눗셈이 기본 정밀도 28자리에서 먼저 반올림돼서, 유효숫자 29자리 이상인 참값 0.0000499…가 `0.0001`이 된다(P3).
- 근거: 분모가 행 수라 이 경우가 생기려면 10³³ 행 정도가 필요하다. 실제로는 도달할 수 없어 동작 영향이 없다.
- 제안: 필요하면 `localcontext()`로 정밀도를 올리거나 정수 연산(`(2*n*10000 + d) // (2*d)`)으로 사사오입한다.

### 리뷰 005 L1–L3
- 이번 수정 범위 밖이다. 상태는 리뷰 005와 같다(기록만).

## 6. GPT 의견에 동의하는 부분 (반례 탐색 후)
- H1 보류와 실패 유지·공개: 동의(근거 H1). 다만 해결로 세지 않는다.
- M1을 사사오입으로 해석하고 README에 예시를 적은 것: 동의. 명세 예시 `0.0312`(T45 기대값 등)와 기존 산출물이 그대로임을 P1·전체 테스트로 확인했다.
- M2에서 bool을 정수로 받지 않은 것: 동의. P6에서 NaN·Infinity도 같은 경로로 막혔다.
- M3에서 재배분하지 않고 실패를 공개한 것: 동의. 재배분하면 「5종 균등 배분」 명세를 어긴다. P8·P9로 메시지와 무출력을 확인했다.
- 「성공 경로의 난수 소비·배분·버전·설정은 그대로」라는 주장: 동의. P1에서 seed42 CSV·meta가 바이트 동일하다.
- gpt-log의 「실행 검증 미완료」 공개: 사실이다. 이번 리뷰의 실행으로 새 회귀 3개 통과와 보존 조건을 확인했다.

## 7. 요약
- 리뷰 005 지적: M1·M2·M3 **해결**, H1 **미해결**(사용자 결정 대기, 처리 방식에는 동의).
- 새 지적: 중간 1(M1, meta의 알 수 없는 주입 종류 키가 TOTAL에만 숨어 더해짐), 낮음 1(L1, 도달 불가 정밀도 경계).
- 보존 조건(보호 파일 무수정, 기존 테스트 무수정 통과, 기존 보고서 13개·seed42 산출물 바이트 동일)은 모두 충족.
- 테스트: 101개 중 100개 통과, T44 1개 실패. 반례 9개 중 2개 실패(P3 → L1, P4 → M1).
- 미검증: 없음(테스트·반례는 모두 직접 실행).

VERDICT: FIX
