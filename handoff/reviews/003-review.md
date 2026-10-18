# 리뷰 003 — v2 2단계 재검사·폐기 (T23–T32)

- 검수자: Claude (읽기 전용)
- 날짜: 2026-10-18
- 범위: `git log/diff 962a4b5..HEAD` (015435c, 230f437, a02642d, 90351c2, df14cb1, 4e01653, 5362304, b32f344, 955ee83)
- 기준: `handoff/tasks.md` 맨 위 「현행 작업: v2 2단계」 명세·기대표 T23–T32, 보존 조건(v1 T1–T10·v1 보고서, 1단계 T11–T22·v2 보고서)
- 읽은 것: setup-notes.md, tasks.md, decisions.md, gpt-log.md(2단계 부분), src/recipe.py·recipe_rules.py·recipe_reports.py·main.py 변경분, tests/test_retest.py 전체, tests/test_recipe.py 일부, README 목차

## 1. 테스트 실행

명령: `py -m unittest discover -s tests`

```text
......................................................
----------------------------------------------------------------------
Ran 54 tests in 5.467s

OK
```

- 54개 통과(v1 12 + 1단계 26 + 2단계 16, GPT 보고와 개수 일치).
- **미검증**: 저장소 밖 임시 폴더에서 `py -m src.main data/sample_events.csv`, `... sample_events_v2.csv --recipe recipes/lamp_models.json`, `... sample_events_retest.csv --recipe recipes/lamp_models_retest.json`를 직접 실행해 바이트 비교하려 했으나 이 세션의 권한 설정(don't ask 모드)에서 해당 Bash 명령이 거부됐다. 그래서 CLI를 직접 다시 실행하지 못했다. 대신 아래 정적 근거와 테스트 결과로 확인했다.

## 2. 보존 조건 확인

| 조건 | 결과 | 근거 |
| --- | --- | --- |
| `src/rules.py`, `tests/test_rules.py`, `tests/test_recipe.py` 무수정 | 확인 | `git diff --stat 962a4b5..HEAD -- <세 파일>` 출력 없음 |
| `AGENTS.md`, `CLAUDE.md`, `.claude/` 무수정 | 확인 | 같은 명령의 출력 없음 |
| T1–T10 무수정 통과 | 확인 | test_rules.py 변경 없음 + 위 54개 통과 |
| T11–T22 무수정 통과 | 확인 | test_recipe.py 변경 없음 + 위 54개 통과 |
| v1 보고서 `reports/sample_events_*.csv` 3종 바이트 동일 | 커밋 파일 무변경 확인, **재생성 비교는 미검증** | 6개 보고서 파일의 `git diff --stat` 출력 없음. v1 경로(`src/rules.py`, `main.py`의 v1 분기)는 diff에 없음. `test_rules.py`의 샘플 내용 검사 통과. GPT는 SHA-256 동일을 보고함(gpt-log) |
| 1단계 보고서 `reports/sample_events_v2_*.csv` 3종 동일 | 같음(재생성 비교 미검증) | `main.py`는 `book.retest_enabled`가 거짓이면 기존 열·제목 그대로(`src/main.py:97-104`), `recipe_reports.py`는 거짓이면 RULE_IDS 6개 그대로. `test_sample_v2_matches_expected_products_and_rejection_counts` 통과 |
| gpt-log 기존 본문 보존 | 확인 | `git diff 962a4b5..HEAD -- handoff/gpt-log.md`에서 삭제 줄 0개 (커밋별 stat의 삭제 수는 중간 커밋들 사이의 변화이며, 전체 구간 기준 순삭제는 없음) |

## 3. 기대표 대조 (코드·테스트·샘플 보고서 기준)

| ID | 판정 | 근거 |
| --- | --- | --- |
| T23 | 일치 | `recipe_rules.py:125-132` 요청은 open_requests만 추가, 보류 유지. test_t23, 샘플 T23(P4 `RULE_FAIL_HOLD`) |
| T24 | 일치 | `:137-150` 열린 요청이 있으면 결과를 바꾸고 요청 닫음. history `LEAK: FAIL@12 → 요청@13 → PASS@14(재검사 1); …` |
| T25 | 일치 | `:138-139` 요청 없으면 `RULE_PRESERVE 결과 이미 존재`. test_t25는 전체 products 깊은 복사본과 비교 |
| T26 | 일치 | 첫 재검사 FAIL로 요청 소진·횟수 1, 무요청 PASS 거절, 재요청 뒤 PASS(재검사 2) |
| T27 | 일치 | `:145-147` 횟수가 상한에 닿은 FAIL 행을 허용하면서 폐기. `:116-117` 폐기 검사가 미등록 뒤·RULE_RECIPE 앞(판정 순서 3→4→5와 같음). 뒤의 세 입력 `RULE_RETEST` 거절 + 상태 불변 assert |
| T28 | 일치 | ①② `미해결 FAIL 없음` ③ `이미 열린 재검사 요청` ④ `RULE_RECIPE` ⑤⑥ `RULE_PRESERVE`. 테스트는 ⑥ 외에 model 기입·inspection 빈칸도 확인 |
| T29 | 일치 | 검사별 독립 요청·횟수. LIGHT PASS 뒤 보류 유지(`FINAL FAIL`), FINAL PASS 뒤 완료. b32f344에서 기대표 입력 순서(LIGHT FAIL → FINAL FAIL → 요청 LIGHT …)로 맞춘 것을 확인 |
| T30 | 일치 | retest_counts `{"LEAK": 2, "LIGHT": 1}`, 상한에서 PASS면 폐기하지 않음, 최종 `검사 대기 / FINAL 미실시` |
| T31 | 일치 | `recipe.py:63-75` 하나라도 있으면 모든 모델에 요구, `type(limit) is not int`로 bool 배제, 1–5 범위. `:89` 예약어에 `RETEST_REQUEST` 추가. CLI 테스트에서 종료 코드 3·stdout 없음·reports 폴더 미생성·위치 접두어 출력 확인 |
| T32 | 일치 | ① `:119-120` 1단계 레시피면 `RULE_RECIPE` ② 같은 폴더 두 번 + 다른 폴더 한 번 실행해 stdout·CSV 3종 바이트 동일, 7개 규칙 순서·history 열 확인 |

샘플 보고서 집계(`reports/sample_events_retest_rejections.csv`): RULE_RECIPE 1(T28④), RULE_FAIL_HOLD 1(T23), RULE_PRESERVE 4(T25, T26, T28⑤, T28⑥), RULE_RETEST 6(T27 3건 + T28①②③). 손으로 센 값과 같다. 커밋된 파일과 재생성 파일의 바이트 비교는 `test_sample_t23_to_t30_reports_match_fixed_input`가 수행하며 통과했다.

## 4. GPT 의견에 대한 판단 (동의)

- **T32 명세 이견에 동의.** 1단계 기존 구현은 inspection이 채워진 `RETEST_REQUEST`를 `RULE_PRESERVE`로 거절했으므로 "1단계 동작 그대로 `RULE_RECIPE`"라는 기대표 문구와 실제로 충돌한다. 기대표의 명시값(`RULE_RECIPE`)을 따르고 이견을 공개한 처리는 CLAUDE.md·tasks.md의 "기대표를 고쳐 통과시키지 않는다" 원칙에 맞다. T11–T22와 v2 샘플에는 이런 행이 없어 영향이 없다.
- **"미해결 FAIL 최대 1개" 결정 근거와 T29의 충돌 지적에 동의.** decisions.md의 근거 문장이 사실과 다르다. 다만 구현은 검사 ID로 연결하므로(요청 행에 inspection 기입) 동작상 모호함은 없다. 근거 문장만 사용자가 고치면 된다.
- **폐기 문구 "2회 초과"를 원문대로 둔 판단에 동의.** 아래 L3 참고.
- 상태 불변 검증 방식(`copy.deepcopy(products)` 후 동등 비교)은 frozen dataclass라 공정 위치·검사 결과·열린 요청·횟수·폐기 여부·이력을 모두 포함한다. 명세의 "거절은 전체 상태 불변까지 assert" 요구를 충족한다.

## 5. 지적 사항

높음: 없음
중간: 없음

### L1
- 심각도: 낮음
- 파일:줄: `src/recipe_rules.py:202-206`
- 문제: 형식 검사의 `RETEST_REQUEST` 분기가 재검사 모드와 관계없이 적용되어, 1단계 레시피에서 일부 `RETEST_REQUEST` 행의 판정이 이전과 달라졌다. GPT가 공개한 이견(inspection 기입 → `RULE_RECIPE`) 외에 다음 두 경우는 보고되지 않았다.
  - inspection 빈칸 `RETEST_REQUEST`: 이전 `RULE_RECIPE`("제품 레시피에 없는 공정 RETEST_REQUEST") → 현재 `RULE_PRESERVE`("inspection이 비어 있음")
  - result 기입 `RETEST_REQUEST`: 규칙 ID(`RULE_PRESERVE`)는 같고 거절 이유 문구만 바뀜
- 근거: `git show 962a4b5:src/recipe_rules.py`의 `_invalid_fields`에는 `RETEST_REQUEST` 분기가 없어 이 행이 공정 경로로 갔다. 보존 조건은 "1단계 동작·출력은 바뀌지 않는다"인데, T11–T22·v2 샘플에는 이런 행이 없어 테스트와 보고서는 그대로다.
- 제안: 코드는 고치지 않는다(마감일, 위험이 작음). gpt-log의 「명세 이견(T32)」 항목에 위 두 경우를 한 줄로 덧붙여 공개 범위만 맞춘다.

### L2
- 심각도: 낮음
- 파일:줄: `handoff/tasks.md:3`, `handoff/decisions.md` 마지막 줄
- 문제: 230f437 커밋 메시지는 "confirm v2 stage-2 retest spec"인데 tasks.md 상태 줄은 여전히 "초안 – 사용자 확정 전"이고, decisions.md의 "재검사 모드 켜는 방식"도 "제안" 상태다.
- 근거: 사전 기대표가 확정되지 않았다면 이번 PASS 판정의 기준도 초안이 된다. GPT도 "착수 승인을 실행 권한으로 해석했다"고 밝혔다.
- 제안: 사용자가 tasks.md 상태 줄과 decisions.md에 확정을 기록한다(사용자 작업이며 코드 변경은 필요 없음).

### L3
- 심각도: 낮음
- 파일:줄: `src/recipe_rules.py:69`
- 문제: 폐기 이유 문구 "재검사 한도 2회 초과 FAIL로 폐기"는 실제 조건(상한 2회에 **도달한** 재검사가 FAIL)과 말이 어긋난다.
- 근거: 문구는 tasks.md 원문 그대로이고 동작은 결정 기록("2번째 재검사도 FAIL이면 폐기")과 같다. GPT가 이 점을 공개했다.
- 제안: 마감 전에는 바꾸지 않는다(기대표·샘플 보고서가 함께 바뀜). 시연 때 "2회 재검사 후에도 FAIL"이라고 말로 설명한다.

### L4
- 심각도: 낮음
- 파일:줄: `tests/test_retest.py:39-55`, `:292-299`
- 문제: T31 테스트는 오류 위치 접두어(`A.retest_limit:` 등)만 확인하고 메시지 내용은 확인하지 않는다. T32 ①은 CLI가 아니라 `RecipeProcess`를 직접 호출해 확인한다.
- 근거: 명세 요구("오류 위치 표시", "`RULE_RECIPE` 거절")는 충족한다. CLI 경로의 1단계 동작은 test_recipe.py가 따로 확인한다.
- 제안: 기록만 한다. 수정은 요구하지 않는다.

## 6. 결론

- T23–T32는 기대표와 모두 일치하고, 보호 파일과 v1·1단계 보고서·테스트는 바뀌지 않았다. 테스트 54개가 통과했다.
- 높음·중간 지적은 없다. 낮음 L1–L4는 기록만 한다. L1은 gpt-log에 한 줄 공개하기를, L2는 사용자 확정 기록을 권한다.
- 미검증: v1·1단계·재검사 샘플 CLI를 저장소 밖에서 직접 재생성해 바이트 비교하는 작업(권한 거부로 실행하지 못함). 재검사 샘플은 테스트가 바이트 비교를 대신 수행했다.

VERDICT: PASS
