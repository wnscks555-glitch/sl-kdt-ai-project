# 리뷰 007 — 리뷰 006 수정 재검토 (v2 4단계, T42–T50)

- 검수자: Claude (읽기 전용)
- 검수일: 2026-10-18
- 범위: `git diff 93a255e..HEAD` (커밋 d78482b `fix: apply review 006 (loop 2/2)`). 변경 파일: `README.md`, `handoff/gpt-log.md`, `handoff/loop-logs/006-codex.txt`, `src/main.py`(+3줄), `tests/test_summary.py`(+3 사례)
- 기준: `handoff/tasks.md` 맨 위 「현행 작업: v2 4단계」 명세·기대표 T42–T50·불변식 1–7, 그 아래 1–3단계 보존 조건
- 읽은 자료: `handoff/setup-notes.md`, `decisions.md`(전체), `gpt-log.md`(「리뷰 006 수정 단계」 절), `handoff/reviews/006-review.md`, 위 diff 전체, `src/main.py:95–160`, `src/summary.py:185–208`, `src/reason_codes.py`의 `INJECTED_ERROR_CODES`
- `tasks.md`는 이번 범위에서 바뀌지 않았다(마지막 변경 커밋 0931cd9). `decisions.md`도 바뀌지 않았다.

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
Ran 101 tests in 67.143s

FAILED (failures=1)
T44 seed=42 products=500 generation_seconds=0.115423 judgment_analysis_seconds=0.081114
T44 seed=7 products=200 generation_seconds=0.048380 judgment_analysis_seconds=0.034593
T44 seed=42 all_rows_deepcopy_invariant_seconds=42.455382
T44 seed=7 all_rows_deepcopy_invariant_seconds=5.920517
```
(터미널 인코딩 때문에 깨져 출력된 한글 경로·메시지는 원문으로 옮겼다. 그 밖의 내용은 그대로다.)

결과: 101개 중 100개 통과, 1개 실패. 테스트 수는 리뷰 006과 같다. 이번 수정은 새 함수가 아니라 기존 `test_review005_m2_invalid_meta_exits_2_without_reports`의 subTest 사례 3개를 더한 것이라서 수가 늘지 않았다. 이 함수는 통과했다. 실패는 리뷰 005·006과 같은 T44 폐기 조건 1건뿐이다.
참고: gpt-log는 이번에도 Codex 환경에서 `No installed Python found!`로 테스트를 실행하지 못했다고 공개했다. 위 실행이 이 수정을 처음 실행해 본 검증이다.

## 2. 보존 조건 확인

| 항목 | 방법 | 결과 |
| --- | --- | --- |
| `src/rules.py`, 기존 테스트 4개 무수정 | `git diff --stat 93a255e..HEAD`에 없음 | 충족 |
| `src/recipe_rules.py`, `src/equipment.py`, `src/recipe_reports.py`, `src/summary.py`, `src/generate.py`, `recipes/*`, `data/`, `reports/` 무수정 | 같은 diff stat에 없음 | 충족 |
| 기존 T1–T41 테스트 통과 | 위 전체 실행에서 실패는 T44 1건뿐 | 충족 |
| 기존 테스트 기대값 무수정 | `tests/` diff는 리뷰 005 회귀 함수의 `invalid` 목록에 사례 3개를 더한 것뿐. 기존 사례·단언은 그대로 | 충족 |
| 기존 샘플 보고서 13개 + seed42 CSV·meta·보고서 6개 바이트 동일 | 반례 P1: 임시 폴더에서 다시 실행·생성해 체크아웃 파일과 비교. 생성기 meta가 새 키 검사를 통과하는지도 함께 확인 | 충족 (19개 보고서, CSV·meta 모두 동일) |
| `--summary` 없을 때 이전 동작과 동일 | 새 검사는 `if summary:` 블록 안쪽(`src/main.py:126,140–141`)에만 있음 + P9 | 충족 |

## 3. 이전 지적 항목 판정

| 항목 | 판정 | 근거 |
| --- | --- | --- |
| H1 (T44 폐기 0건, 리뷰 005 H1부터 이어짐) | **미해결** | 위 실행에서 같은 실패가 남았다. gpt-log는 반박하지 않고 「보류: 사용자 결정 필요」로 처리했다. 불변식 6과 `decisions.md` 「빈 검증 방지」(시드·확률을 몰래 바꾸지 말고 명세 이견으로 보고)를 따른 처리라서 처리 방식에는 **동의**한다. 그러나 `decisions.md`에 H1에 대한 사용자 결정이 아직 없고, T44 기대 결과(불변식 1–6 모두 통과)와 실제가 다르다. 그래서 높음으로 남긴다. |
| M1 (meta의 알 수 없는 주입 종류 키가 TOTAL에만 더해짐) | **해결** | `src/main.py:140–141`이 `set(injected) <= set(INJECTED_ERROR_CODES)`를 검사하고, 어기면 `ValueError` → 종료 2로 보낸다. 검사 위치가 보고서 쓰기(`write_reports`, 152행) 전이라 보고서를 쓰지 않는다. 리뷰 006 제안 첫째 안과 같다. README:372에 허용 코드 5종을 적었고 상수와 일치한다(P2). 회귀 사례 3개(`FOO: 5` 섞임, `FOO: 0`, 판정 코드이지만 주입 종류가 아닌 `EQUIP_STOPPED`)가 통과했다. 리뷰 006 P4 입력은 이제 종료 2가 된다(P6·회귀). 유효한 키 집합에서는 TOTAL이 종류별 합과 같다(P4). |
| 리뷰 006 L1, 리뷰 005 L1–L3 (낮음) | 기록 유지 | 이번 수정 범위 밖(gpt-log 명시). 수정 요구로 세지 않는다. |

## 4. 반례 탐색

파일: `handoff/reviews/probes/test_probe_007.py` (임시 폴더만 쓴다. 저장소 `reports/`·`data/`에는 쓰지 않았다)

```text
$ py -m unittest handoff/reviews/probes/test_probe_007.py
.........
----------------------------------------------------------------------
Ran 9 tests in 3.985s

OK
P8 duplicate key SEQ_SKIP injected_count: 5
```

| # | 입력 | 예상 (명세 근거) | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P1 | 임시 폴더에서 기존 샘플 4종을 옵션 없이 실행 + seed42 다시 생성 후 `--summary --trace GEN_0005` | 체크아웃 파일과 바이트 동일(보존 조건, T50, 불변식 1). 생성기 meta가 새 키 검사에 걸리지 않아야 함 | 보고서 19개, CSV·meta 모두 동일, 종료 0 | 통과 |
| P2 | README:372의 코드 5개 ↔ `INJECTED_ERROR_CODES` | 순서·내용 일치(문서·동작 일치) | 일치 | 통과 |
| P3 | `injected_errors` 키가 `seq_skip`, `Seq_Skip`, `"SEQ_SKIP "`, `" SEQ_SKIP"`, `""` | README 「5종 코드만 허용」 → 정확히 일치하지 않으면 종료 2, 트레이스백 없음, 보고서 미생성 | 5건 모두 종료 2, 메시지에 「5종」, `reports/` 없음 | 통과 |
| P4 | `injected_errors`가 `{}`, 5종 전부(1–5), 5종 모두 0 | 종료 0, 종류별 행 5개 + TOTAL, TOTAL 주입 수 = 종류별 합 = meta 합 | 예상대로 | 통과 |
| P5 | 최상위에 `seed`, `FOO` 같은 다른 키가 있는 meta | README는 `injected_errors`의 키만 제한함 → 종료 0 | 종료 0 | 통과 |
| P6 | 알 수 없는 키(`EQUIP_STOPPED: 0`)와 `--trace a`를 함께 지정 | 종료 2, trace·기본 보고서 모두 미생성(README 「보고서를 쓰지 않습니다」) | 종료 2, `reports/` 없음 | 통과 |
| P7 | 키 오류와 값 타입 오류가 겹침 `{"FOO": "x"}` | 검사 순서와 무관하게 종료 2, 트레이스백 없음 | 종료 2(값 검사가 먼저 잡음) | 통과 |
| P8 | 같은 키가 두 번 나온 JSON `{"SEQ_SKIP": 1, "SEQ_SKIP": 5}` | 명세·README 모두 다루지 않음. 동작만 기록 | 종료 0, 마지막 값 5를 씀(Python `json` 표준 동작) | 통과(기록만, 아래 L1) |
| P9 | 알 수 없는 키 meta가 옆에 있는 입력을 `--summary` 없이 기본 실행, `--trace a`만 지정해 실행 | 종료 0, meta를 읽지 않음, summary 미생성(이전 동작 보존) | 두 경우 모두 예상대로 | 통과 |

## 5. 지적 사항

### H1 (리뷰 005 H1, 미해결)
- 심각도: **높음**
- 파일:줄: `tests/test_generate.py:171` (원인 설정 `recipes/generator.json`, `src/generate.py:55–69`)
- 문제: T44 기대 결과 「불변식 1–6 모두 통과」와 다르다. 시드 42에서 폐기된 제품이 0개라 불변식 6을 충족하지 못한다. 불변식 3의 「폐기 뒤 허용 행 없음」 분기도 대상이 없어서 실제로는 검증되지 않는다.
- 근거: 위 전체 실행의 `AssertionError: 0 not greater than 0 : … discarded`. 원인 분석은 리뷰 005 H1·P7과 같다(재검사가 정상 설비로 가서 재검사 FAIL 확률이 사실상 2%). 이번 diff는 생성기·설정을 건드리지 않았다.
- GPT 의견에 대한 판단: 「보류」 처리에 **동의**한다. 시드·확률·테스트를 바꾸지 않고 실패를 공개한 것은 명세를 따른 것이다. 다만 반박이 아니라 결정 대기이므로 해결로 처리하지 않는다.
- 제안: 사용자가 리뷰 005 H1의 선택지(① 제품 결함 재검사 FAIL 확률 별도 설정 ② 고장 설비 재검사 허용 ③ 폐기 조건을 고정 시나리오 T36으로 이전 등) 가운데 하나를 골라 `tasks.md`·`decisions.md`에 기록한다. 그 뒤 Codex가 생성 버전 상수와 seed42 산출물을 함께 갱신한다.

### L1 (낮음, 기록만, 새 항목)
- 파일:줄: `src/main.py:130`
- 문제: meta JSON에 같은 키가 두 번 나오면 `json.loads`가 마지막 값만 남긴다. 그래서 `{"SEQ_SKIP": 1, "SEQ_SKIP": 5}`는 5건으로 표시되고 앞의 값은 소리 없이 버려진다(P8).
- 근거: 생성기가 쓰는 meta에서는 생기지 않고, 손으로 고친 meta에서만 생긴다. 표시값은 하나로 정해지고 TOTAL도 종류별 합과 같아서 표 안의 모순은 없다. README:372의 구조 규칙도 이 경우를 따로 다루지 않는다.
- 제안: 원하면 `object_pairs_hook`으로 중복 키를 검사해 종료 2로 처리한다.

### 리뷰 006 L1, 리뷰 005 L1–L3
- 이번 수정 범위 밖이다. 상태는 이전 리뷰와 같다(기록만).

## 6. GPT 의견에 동의하는 부분 (반례 탐색 후)
- M1을 TOTAL 계산 변경이 아니라 입력 거절로 처리한 것: 동의. README:372의 「구조가 잘못된 meta는 종료 2」 방침과 맞는다. P3·P6·P7에서 대소문자·공백·`--trace` 조합·겹친 오류도 모두 같은 경로로 막혔다.
- 키가 0건이어도 거절한 것(`{"FOO": 0}`): 동의. 값과 상관없이 키 집합으로 판단해야 규칙을 설명하기 쉽다.
- 기존 `INJECTED_ERROR_CODES` 상수를 다시 쓴 것: 동의. 생성기·summary와 같은 출처라서 README와도 일치한다(P2).
- 「빠진 종류는 0건」 정책 유지: 동의(P4 `{}` 경우).
- H1 보류: 동의(근거 H1). 다만 해결로 세지 않는다.
- 「기존 샘플·seed42 산출물 바이트 비교는 미검증」이라는 gpt-log의 공개는 사실이다. 이번 P1로 동일함을 확인했다.

## 7. 요약
- 리뷰 006 지적: M1 **해결**, H1 **미해결**(사용자 결정 대기, 처리 방식에는 동의).
- 새 지적: 낮음 1(L1, JSON 중복 키). 중간 이상의 새 지적은 없다.
- 보존 조건(보호 파일 무수정, 기존 테스트 무수정 통과, 기존 보고서 13개·seed42 산출물 바이트 동일)은 모두 충족.
- 테스트: 101개 중 100개 통과, T44 1개 실패. 반례 9개 모두 통과.
- 미검증: 없음(테스트·반례는 모두 직접 실행).

VERDICT: FIX
