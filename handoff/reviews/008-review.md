# 리뷰 008 — 수정 1(결함 제품, T44·T51) 검토 (v2 4단계)

- 검수자: Claude (읽기 전용)
- 검수일: 2026-10-18
- 범위: `git diff a1ed98f..HEAD`, `git log a1ed98f..HEAD` (커밋 3개)
  - `baaa7cd` docs: 4단계 명세 수정 1(결함 제품, T51). `handoff/tasks.md`, `handoff/decisions.md`
  - `77a133d` fix(T44,T51): `src/generate.py`(+15), `src/main.py`(+7), `src/summary.py`(+14), `recipes/generator.json`(+2), `tests/test_generate.py`(+35), `tests/test_summary.py`(+47), `README.md`, seed42 CSV·meta·보고서 재생성
  - `0aa3d9a` docs: `handoff/gpt-log.md`, `handoff/run-logs/t51-*`
- 기준: `handoff/tasks.md` 맨 위 「현행 작업: v2 4단계」 명세(수정 1 포함)·기대표 T42–T51·불변식 1–7, 그 아래 1–3단계 보존 조건
- 읽은 자료: `handoff/setup-notes.md`, `tasks.md`, `decisions.md`, `gpt-log.md`(「수정 1 · 리뷰 007 H1 해결」 절), `reviews/007-review.md`, 위 diff 전체, `src/generate.py` 전체, `src/main.py:95–175`, `src/summary.py:150–225`, `reports/gen_seed42_summary.csv`

## 1. 테스트 실행 (직접 실행)

```text
$ py -m unittest discover -s tests
.........................................................................................................
----------------------------------------------------------------------
Ran 105 tests in 73.056s

OK
T44 seed=42 products=500 generation_seconds=0.112951 judgment_analysis_seconds=0.071666
T44 seed=7 products=200 generation_seconds=0.045915 judgment_analysis_seconds=0.027459
T44 seed=42 all_rows_deepcopy_invariant_seconds=45.512481
T44 seed=7 all_rows_deepcopy_invariant_seconds=6.293889
```

결과: 105개 모두 통과. 리뷰 007에서 실패하던 T44(시드 42 폐기 0개)가 이제 통과한다. 늘어난 4개는 T51 테스트(`test_generate.py` 2개, `test_summary.py` 2개)다. gpt-log에 적힌 「105개 전부 통과」와 같다.

## 2. 보존 조건 확인

| 항목 | 방법 | 결과 |
| --- | --- | --- |
| `src/rules.py`, 기존 테스트 4개(`test_rules/recipe/retest/equipment.py`) 무수정 | `git diff --stat a1ed98f..HEAD`에 없음 | 충족 |
| 4단계 기존 테스트 본문·기대값 무수정 | `tests/` diff는 T51 함수 4개 추가와 import 두 줄(`patch`, `Generator`)뿐. 기존 T44 단언(`assertGreater(count, 0, …)`)도 그대로 | 충족 |
| 기존 T1–T50 테스트 통과 | 위 전체 실행 | 충족 |
| 기존 샘플 보고서 13개 바이트 동일 | 반례 P1: 임시 폴더에서 옵션 없이·각 모드로 다시 실행해 체크아웃 파일과 비교 | 충족 |
| seed42 산출물 재현(불변식 1) | 반례 P1: 임시 폴더에서 다시 생성한 CSV·meta, 그 입력의 보고서 4종·summary·trace(19개 중 6개)가 체크아웃 파일과 바이트 동일 | 충족 |
| 시드·기존 확률·기대표 무수정 | `recipes/generator.json` diff는 결함 키 2개 추가뿐. 다른 값(2%, LEAK-2 30%, 70%, 3%)은 그대로. `tasks.md` 기대표는 T44 괄호 주석과 T51 추가뿐이고, 이것은 사용자 확정 커밋 `baaa7cd`에서 바뀌었다 | 충족 |
| 리뷰 004 L1(모드를 보고서 개수로 추정하지 않음) | summary 결함 행은 `build_summary`의 meta 분기 안에서만 만든다. 보고서 쓰기 경로는 바뀌지 않음 | 충족 |

## 3. 명세·기대표 대조

| 항목 | 명세 | 실제 | 판단 |
| --- | --- | --- | --- |
| 결함 여부 추첨 | 같은 난수 흐름, 2% (`tasks.md:30,35`) | `src/generate.py:49` 제품 흐름이 처음 진행될 때(REGISTER 직전) `self.rng.random()` 한 번. 난수 객체는 하나뿐 | 일치 |
| 결함품 FAIL 확률 | 설비와 무관하게 모든 최초·재검사 90% | `src/generate.py:63–67`. 재검사 반복 안에서도 같은 `defective` 값을 씀. T51 단위 테스트가 0.899/0.9 경계와 0.019/0.02 경계를 확인 | 일치 |
| 정상품 확률 | 기존 설비 확률 그대로 | `else` 분기가 기존 식과 같음 | 일치 |
| 결함 여부 비공개 | CSV 열 없음, 판정기에 알리지 않음 | CSV는 7열 그대로(P2). 판정 경로에 결함 정보 없음. meta의 결함 목록을 지워도 rows·products·rejections·equipment·trace와 결함 5행 밖의 summary 행이 모두 같음(P3) | 일치 |
| meta 기록 | `defective_products`, 결함품 수 = 목록 길이, 버전 상수 올림 | `defective_count`, `defective_products` 기록. 버전 1.0.0→1.1.0. seed 42/7/43 모두 수 = 목록 길이(P2) | 일치 |
| main.py meta 검사 | 제품 ID 문자열 배열, 중복 불가 | `src/main.py:142–148`. 배열 아님·문자열 아님·빈/공백 문자열·중복을 종료 2로 거절. 보고서 쓰기 전 단계 | 일치 (등록되지 않은 ID는 아래 M1) |
| summary 결함 분포 | 주입 대비 절에만 결함품 폐기·보류·완료·그 밖, 정상품 폐기 | `src/summary.py:209–222`. products 보고서와 meta로 직접 다시 센 값과 seed 42/7/43 모두 일치(P2) | 일치 |
| T44 불변식 6 | 완료·보류·폐기·정지 설비·오류 5종 각 1개 이상 | seed42: 완료 487, 보류 9, 폐기 4, 정지 LEAK-2·FINAL-1, 오류 5종 각 24 | 일치 |
| T51 | meta 기록, 수 = 길이, summary 표시, CSV에 결함 열 없음 | `reports/gen_seed42_summary.csv:60–64` (4/2/0/0, 정상품 폐기 0) | 일치 |
| README 시드 42 결과 | 실행해서 나온 값만 | FPY 470/500, 최초 FAIL 30/1,236, 재검사 포함 38/1,261, 거절 검사 72·미실시 12, 정지 seq 1571·3962와 원인 seq가 summary.csv 값과 같음 | 일치 |

## 4. 반례 탐색

파일: `handoff/reviews/probes/test_probe_008.py` (임시 폴더만 쓴다. 저장소 `reports/`·`data/`에는 쓰지 않았다)

```text
$ py -m unittest handoff/reviews/probes/test_probe_008.py
........
----------------------------------------------------------------------
Ran 8 tests in 5.895s

OK
P2 seed=42 defective=6 dist=(4, 2, 0, 0, 0) fail_rate={True: 0.9333333333333333, False: 0.01854714064914992}
P2 seed=7 defective=7 dist=(3, 4, 0, 0, 0) fail_rate={True: 0.8823529411764706, False: 0.029069767441860465}
P2 seed=43 defective=8 dist=(4, 4, 0, 0, 0) fail_rate={True: 0.8260869565217391, False: 0.02631578947368421}
P4 {'unknown': (0, (0, 0, 0, 1, 0)), 'case': (0, (0, 0, 0, 1, 0)), 'space': (0, (0, 0, 0, 1, 0)), 'mixed': (0, (0, 0, 1, 1, 0))}
P5 returncode 0
P7 2 ����: 'defective_product_probability'
P8 1.0 0 
P8 dist 1.0 (1, 6, 0, 193, 0)
P8 0.0 0 
P8 dist 0.0 (0, 0, 0, 0, 0)
```
(P7 줄의 `����`는 터미널 인코딩 때문에 깨진 한글이다. 원문은 `오류: 'defective_product_probability'`.)

dist 순서: (결함품 폐기, 결함품 보류, 결함품 완료, 결함품 그 밖, 정상품 폐기).

| # | 입력 | 예상 (명세 근거) | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P1 | 임시 폴더에서 기존 샘플 4종을 각 모드로 실행 + seed42 다시 생성 후 `--summary --trace GEN_0005` | 체크아웃 파일과 바이트 동일(보존 조건, T50, 불변식 1) | 보고서 19개, CSV·meta 모두 동일 | 통과 |
| P2 | seed 42/500, 7/200, 43/300을 생성하고 summary의 결함 5행을 products 보고서와 meta로 직접 다시 셈 | summary 값 = 직접 센 값, 수 = 목록 길이, CSV 7열(T51). 결함품 FAIL 비율이 정상품보다 확연히 높음(90% 가정) | 세 시드 모두 일치. 결함품 FAIL 0.83–0.93, 정상품 0.019–0.029 | 통과 |
| P3 | seed42 입력의 meta에서 `defective_products`만 지우고 `--summary --trace GEN_0019`(결함품) 실행 | 숨은 진실은 주입 대비 절에만 쓴다 → 결함 5행 말고는 모두 같아야 함(`tasks.md:57`) | 보고서 4종·trace 바이트 동일, summary는 결함 5행만 차이 | 통과 |
| P4 | `defective_products`에 입력에 없는 ID `ZZZ`, 대소문자만 다른 `A`, 앞 공백 `" a"`, `["a","ZZZ"]` | 명세는 「문자열 배열, 중복 불가」만 정함. 존재하지 않는 제품에는 「최종 상태」가 없으므로 결함품 분포에 들어가면 안 됨 | 모두 종료 0. 없는 ID가 `defective_other`(그 밖) 1건으로 집계됨. 경고 없음 | **실패 → M1** |
| P5 | `defective_count: 99`, `defective_products: ["a"]` | T51 「결함품 수 = 목록 길이」. main.py 검사 대상에는 들어 있지 않음 | 종료 0, 목록 기준(1건)으로만 표시. 99는 어디에도 표시되지 않고 불일치도 알리지 않음 | 기록(L1) |
| P6 | 중복 ID 결함 목록이 든 잘못된 meta 옆에서 옵션 없이 / `--trace a`만 실행 | `--summary` 없으면 meta를 읽지 않음(이전 동작 보존) | 둘 다 종료 0, summary 미생성 | 통과 |
| P7 | 결함 키 2개가 없는 이전 설정 파일로 `src.generate` 실행 | 명세 밖. 트레이스백 없이 실패하고 CSV를 쓰지 않아야 함 | 종료 2, CSV 미생성, 트레이스백 없음. 메시지가 `오류: 'defective_product_probability'`뿐 | 통과(메시지는 L2) |
| P8 | 결함 확률 1.0 / 0.0으로 200개 생성 후 summary | 1.0: 목록 = 전체 200개, 결함 분포 합 = 200, 정상품 폐기 0. 0.0: 빈 목록, 결함 4행 0, 정상품 폐기 = 전체 폐기 | 1.0: (1, 6, 0, 193, 0) 합 200(설비가 모두 정지해 검사 대기 193). 0.0: 모두 0, 전체 폐기 0과 일치 | 통과 |

## 5. 지적 사항

### M1 (중간, 새 항목)
- 심각도: **중간**
- 파일:줄: `src/summary.py:209–222`(`defect_states = Counter(... if product_id in process.products)`와 `("defective_other", "그 밖", len(defective) - discarded - held - completed)`), 검사 쪽 `src/main.py:142–148`
- 문제: meta의 `defective_products`에 입력 CSV에 등록되지 않은 ID(오타·대소문자 차이·공백 포함·다른 입력의 meta)가 있으면, 그 ID를 「결함품 중 그 밖 상태」 1건으로 집계한다. 존재하지 않는 제품의 최종 상태를 지어내서 표시하는 셈이고, 종료 코드나 메시지로 알리지도 않는다.
- 근거: 반례 P4. `["ZZZ"]`, `["A"]`(fixture의 제품은 `a`), `[" a"]` 모두 종료 0에 `defective_other = 1`. `tasks.md:57`은 「결함품의 **최종 상태** 분포」를 요구하는데 미등록 ID에는 최종 상태가 없다. README의 meta 규칙(「비어 있지 않은 제품 ID 문자열의 배열, 중복 불가」)과 「그 밖」 설명 어디에도 미등록 ID가 그 밖으로 들어간다는 말이 없다. 명세가 직접 다루지 않는 입력에서 설명할 수 없는 값이 나오므로 CLAUDE.md 기준 중간이다. 리뷰 006의 「알 수 없는 주입 종류 키」(중간, 종료 2로 해결)와 같은 종류의 문제다. 생성기가 쓴 meta에서는 생기지 않는다(P2에서 목록 ⊆ 등록 제품).
- 제안: 다음 중 하나를 사용자가 고르게 한다. ① 입력에 등록되지 않은 ID가 목록에 있으면 기존 meta 구조 오류처럼 종료 2(보고서 미생성)로 처리한다. ② 미등록 ID를 `defective_unregistered` 같은 별도 행으로 내고 「그 밖」에서 뺀 뒤 README에 적는다. 어느 쪽이든 P4 사례를 회귀 테스트로 추가한다.

### L1 (낮음, 기록만)
- 파일:줄: `src/main.py:142–148`, `src/summary.py:209`
- 문제: meta의 `defective_count`가 목록 길이와 달라도 검사하지 않고 summary에도 쓰지 않는다(P5). 생성기가 만든 meta에서는 항상 같으므로 표시값에는 영향이 없다.
- 제안: 원하면 `defective_count`가 있을 때 목록 길이와 같은지 검사해 종료 2로 처리한다.

### L2 (낮음, 기록만)
- 파일:줄: `src/generate.py:49,64`, `src/generate.py:199–200`
- 문제: 결함 키가 없는 이전 설정으로 생성하면 `KeyError`가 잡혀 `오류: 'defective_product_probability'`만 출력된다(P7). 종료 2·CSV 미생성이라 동작은 맞지만, 어떤 설정 키가 빠졌는지 알기 어렵다. 확률 값의 범위(0–1) 검사도 없다(기존 키들도 마찬가지인 기존 상태).
- 제안: 원하면 「설정에 필요한 키 없음: …」처럼 메시지를 바꾼다.

### 이전 리뷰 낮음 항목
- 리뷰 007 L1(JSON 중복 키), 리뷰 006 L1, 리뷰 005 L1–L3: 이번 범위 밖이다. gpt-log도 보류로 기록했다. 상태는 이전과 같다(기록만).

## 6. GPT 의견에 동의하는 부분 (반례 탐색 후)
- 리뷰 007 H1 「반영·해결」: **동의**. T44가 기대값을 바꾸지 않고 통과하며(폐기 4개), 원인이던 설정 충돌을 사용자 결정(수정 1)대로 고쳤다. 시드·기존 확률·재검사 설비 선택도 그대로다(§2). P2에서 seed 7·43도 결함품 폐기가 3–4개라 시드 42 하나에만 맞춘 결과가 아니다.
- 「판정·FPY·FAIL률·파레토·trace는 결함 목록을 쓰지 않는다」: **동의**. P3에서 목록을 지워도 결함 5행 말고는 summary·보고서·trace가 바이트 단위로 같았다.
- 「결함품 2%는 추출 확률이라 정확히 10개를 보장하지 않는다」는 README·gpt-log 공개: **동의**. 실제 seed 42/7/43에서 6/7/8개(제품 수 500/200/300)였다.
- 정상품 폐기 수를 전체 폐기에서 결함품 폐기를 빼서 계산한 것: **동의**. P2(세 시드)와 P8(확률 0.0, 1.0 경계)에서 직접 센 값과 같았다. 다만 결함품 폐기는 등록된 ID만 세므로 M1이 이 값을 틀리게 만들지는 않는다.
- meta 검사를 `--summary`일 때만 하는 것: **동의**. 이전 동작 보존과 맞다(P6).
- seed42 보고서 6개가 바뀐 것: 수정 1이 「seed42 산출물을 다시 만든다」고 정했으므로 보존 조건 위반이 아니다. 기존 샘플 13개는 그대로다(P1).

## 7. 요약
- 리뷰 007 H1(리뷰 005 H1): **해결**. T44 통과, T51 일치.
- 새 지적: 중간 1(M1, 미등록 결함 ID를 「그 밖」으로 집계), 낮음 2(L1 `defective_count` 미검사, L2 이전 설정의 오류 메시지).
- 보존 조건(보호 파일 무수정, 기존 테스트 무수정 통과, 기존 샘플 보고서 13개 동일, seed42 재생성 재현)은 모두 충족.
- 테스트: 105개 모두 통과. 반례 8개 실행·통과(P4는 현재 동작을 고정한 단언이며 판단은 실패 → M1, P5는 기록).
- 미검증: 없음(테스트·반례는 모두 직접 실행).

VERDICT: FIX
