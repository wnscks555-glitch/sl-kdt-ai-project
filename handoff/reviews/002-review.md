# 검수 002 — v2 1단계 모델별 공정 레시피 (T11–T22) + v1 보존

- 검수자: Claude (Claude Code, 읽기 전용)
- 검수일: 2026-10-18
- 대상 범위: `git diff 8f58a36..b8213e7` / `git log 8f58a36..HEAD` (12개 커밋, `a854df6`~`b8213e7`)
- 기준: `handoff/tasks.md` 맨 위 「현행 작업: v2 1단계」 명세와 기대표 T11–T22, 그리고 「v1 보존」 조건(T1–T10 무수정 통과, v1 보고서 바이트 동일)
- 읽은 자료: `handoff/setup-notes.md`, `tasks.md`, `decisions.md`, `gpt-log.md`(v2 절), `reviews/001-review.md`, `src/recipe.py`, `src/recipe_rules.py`, `src/recipe_reports.py`, `src/main.py` diff, `tests/test_recipe.py`, `tests/fixtures/*`(일부), `recipes/lamp_models.json`, README diff, `.claude/settings.json`·`tools/review-loop.ps1` diff

## 요약

높음·중간 항목은 없다. T11–T22가 모두 명세대로 동작하고 각각 테스트로 대응된다. 거절 사례는 `assert_rejected_unchanged`로 전체 제품 딕셔너리를 깊은 복사본과 비교하므로 "상태 불변" 조건을 명세보다 강하게 확인한다. v1 보존 조건도 충족한다(`src/rules.py`·`tests/test_rules.py`·v1 샘플·v1 보고서는 범위 안에서 한 줄도 바뀌지 않았고, 옵션 없는 실행 경로는 기본 인자로 기존 동작을 그대로 탄다). 아래 낮음 항목은 기록용이며 수정 요구로 세지 않는다.

## 직접 실행한 명령과 결과

### 1) 전체 단위 테스트 (v1 + v2)

```
py -m unittest discover -s tests
```

```
......................................
----------------------------------------------------------------------
Ran 38 tests in 4.534s

OK
```

v1 12개 + v2 26개. v1 테스트 파일은 무수정(아래 2).

### 2) v1 동결 파일 무수정 확인

```
git diff --stat 8f58a365e3dd35b2263d9aa0409e4fac243b219d..HEAD -- src/rules.py tests/test_rules.py reports/sample_events_rows.csv reports/sample_events_products.csv reports/sample_events_rejections.csv data/sample_events.csv
```

출력 없음(변경 0건).

### 3) v1 보고서 재생성 (저장소 루트에서 실행)

```
py -m src.main data/sample_events.csv
```

종료 후 `reports/sample_events_{rows,products,rejections}.csv` 3종을 다시 썼고, 판정 내용은 거절 RULE_SEQ 1 / RULE_INSP_PRE 1 / RULE_PRESERVE 5로 001 검수 때와 같다. (이 Bash 캡처는 cp949 콘솔이라 한글이 깨져 보였으나 파일 내용과는 무관하다.)

### 4) v2 샘플 보고서 재생성

```
py -m src.main data/sample_events_v2.csv --recipe recipes/lamp_models.json
```

첫 줄 `레시피: recipes/lamp_models.json | SHA-256: d7a8976ee178`. 76행, 거절 집계 RULE_RECIPE 5 / RULE_SEQ 1 / RULE_INSP_PRE 2 / RULE_NOT_DONE 0 / RULE_FAIL_HOLD 1 / RULE_PRESERVE 3, 제품 14개. README·테스트의 수치(76행·허용 64·거절 12)와 일치.

### 5) 재생성 결과와 커밋 파일 비교

```
git status --porcelain
```

```
?? handoff/loop-logs/
```

3)·4)에서 덮어쓴 보고서 6종 모두 커밋된 내용과 같다(변경 표시 없음). 단, 이 비교는 git의 줄바꿈 정규화(`core.autocrlf=true`)를 거친 비교다. gpt-log의 "Git blob(LF)과 생성 파일(CRLF)은 엄격 바이트 비교 시 착수 전부터 다르고, 체크아웃 파일과는 바이트 동일"이라는 명세 이견 기록과 모순되지 않는다(아래 L1).

## 기대표 대조 (v2)

| ID | 기대 결과 | 코드·테스트·샘플 확인 | 판정 |
| --- | --- | --- | --- |
| T11 | 모두 허용, 완료 | `test_t11_…`, 샘플 seq 1–9 | 일치 |
| T12 | b 완료, a = 공정 진행 중(P4 완료), 이유 `P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시` | `test_t12_…` 문자열 그대로 assert, 샘플 T12_A/B | 일치 |
| T13 | P3 RULE_SEQ(`P2 미완료`), P1 유지, 이어 P2 허용 | `recipe_rules.py` 공정 분기 `target != completed_steps`, `test_t13_…`, 샘플 seq 24–25 | 일치 |
| T14 | ① `P3 미완료` ② `P5 미완료` RULE_INSP_PRE, 결과 미저장 | `completed_steps <= steps.index(after)`, `test_t14_…` 양 제품 inspections == {} | 일치 |
| T15 | LEAK 중간 허용, 최종 검사 대기 `FINAL 미실시` | `test_t15_…`, 샘플 T15 | 일치 |
| T16 | LEAK FAIL 보류, P4 RULE_FAIL_HOLD, LEAK PASS RULE_PRESERVE, P3 유지 | `test_t16_…`, 샘플 seq 48–50 | 일치 |
| T16b | FINAL PASS 허용, 보류 유지 | `test_t16b_…` rule_id RULE_FAIL_HOLD, 샘플 seq 57–58 | 일치 |
| T17 | 셋 다 RULE_RECIPE, ① 제품 미생성 ②③ 불변 | `test_t17_…`, 샘플 seq 59/61/63 | 일치 |
| T18 | ①–⑦ 종료 코드 3, 보고서 미생성, 이벤트 미처리, ⑦ 두 오류 출력 | `main.run_recipe`가 CSV 읽기 전에 `load_recipe` → `parser.exit(3)`. `test_t18_invalid_recipe_stops_before_missing_input_…`가 12개 픽스처 전부 종료 코드 3·`reports/` 부재·`[행별 판정]` 미출력을, ⑦은 `A.steps:`와 `A.next:` 동시 출력을 확인 | 일치 |
| T19 | B 제품 P5 RULE_RECIPE, 불변 | `test_t19_…`, 샘플 seq 69 | 일치 |
| T20 | ① RULE_RECIPE 미생성 ② RULE_PRESERVE 불변 | `test_t20_…`, 샘플 seq 70/72 | 일치 |
| T21 | ① 두 번 실행 stdout·CSV 3종 바이트 동일 ② B LEAK after P3 레시피에서 해당 행 RULE_INSP_PRE | `test_t21_…`가 별도 폴더 두 곳 + 같은 폴더 재실행까지 비교, `leak_after_p3.json`으로 `P3 미완료` 거절 확인 | 일치 |
| T22 | RULE_PRESERVE(`이미 등록된 제품`), 모델 A·P2 유지 | `test_t22_…`, 샘플 seq 76 | 일치 |

판정 순서(명세 1–6)도 코드 분기 순서와 같다: 형식 → REGISTER(중복→모델) → 미등록 → 레시피에 없는 공정·검사 → 공정(지난 공정→보류→건너뜀) / 검사(after 미완료→결과 중복). `test_rule_priority_…`가 각 경계를 하나씩 확인한다.

## v1 보존 확인

- `src/rules.py`, `tests/test_rules.py`: 범위 내 diff 0줄. 공통 함수 이동도 없음(명세 "작은 함수도 옮기지 않는다" 준수).
- `src/main.py`: 변경은 `read_events`·`write_reports`·`print_reports`에 **기본값이 기존 값인** 인자를 추가한 것과 `--recipe` 분기뿐이다. `args.recipe is None`이면 기존 코드 경로를 그대로 탄다. v2 모듈 import는 `run_recipe` 안의 지연 import라서 v1 실행 시 로드되지 않는다.
- v1 보고서 3종: 재생성 결과가 커밋 파일과 같음(위 3·5). T10 테스트도 통과.
- v2 헤더로 v1 실행, v1 헤더로 v2 실행 시 모두 종료 코드 2·보고서 미생성: `test_header_mode_mismatch_…`에서 확인.

## GPT 의견에 동의하는 부분

- **검증 후 일괄 반영 구조 유지**: `RecipeProcess.apply`의 모든 거절은 `return`으로 빠지고 `self.products[product_id] = updated`는 한 곳뿐이다. `RecipeProduct`는 frozen이며 검사 결과도 `{**…}` 새 dict로 교체한다. v1 001 검수에서 동의한 설계를 그대로 이어 명세의 "상태 불변"을 구조로 보장한다.
- **레시피 오류를 이벤트·CSV보다 먼저 검사**: 없는 CSV 경로를 줘도 레시피 오류면 3으로 끝나도록 테스트한 점은 명세 "이벤트를 하나도 처리하지 않는다"를 가장 엄격하게 해석한 것이다. decisions.md(2026-10-18 T18 "전체 중단, 오류를 한 번에 모두 표시")와 일치.
- **오류 전체 수집**: 모델별로 `continue`하지 않고 오류를 누적해 `invalid_structure.json` 하나에서 16개 위치를 모두 보고한다. 명세 "발견한 모든 오류" 충족.
- **gpt-log의 CRLF 명세 이견 기록**: 엄격 바이트 비교가 착수 전부터 성립하지 않는다는 사실을 숨기지 않고, 출력 줄바꿈·Git 설정·기대표를 바꾸지 않은 판단에 동의한다. v1 출력을 건드리는 쪽이 회귀 위험이 더 크다.
- **해석·가정** (gpt-log ②·③): 빈 `event`·빈 `inspection`은 형식 오류(RULE_PRESERVE), 비어 있지 않은 미지 ID는 RULE_RECIPE, Pk 자리에 실제 마지막 공정 ID 표시, SHA-256은 원본 바이트 기준. 모두 명세 문구와 충돌하지 않으며 README에 반영돼 있다.
- **README**: v1 절을 지우지 않고 v2 절을 덧붙였으며 "가상 규칙·SL 기준 아님·완료가 출하/양품 아님" 경계 문구를 v2에도 굵게 명시했다. 명세 산출물 조건 충족.

## 발견 사항

### L1
- 심각도: 낮음
- 파일:줄: `handoff/tasks.md:14` (명세 문구) / `reports/sample_events_*.csv`
- 문제: 명세의 "커밋된 파일과 바이트 단위로 같다"가 Git blob 기준인지 체크아웃 파일 기준인지 정해져 있지 않다. `core.autocrlf=true` 환경에서는 blob(LF)과 생성 파일(CRLF)이 다르다.
- 근거: gpt-log 2026-10-18 회귀 기준 절의 명세 이견. 본 검수의 `git status` 비교도 정규화를 거친 비교라 체크아웃 바이트 비교와 같은 결론까지만 보장한다.
- 제안: 코드 수정 불필요. 시연 때 "체크아웃 파일과 바이트 동일, blob과는 줄바꿈만 다름"으로 설명하거나, 사용자가 tasks.md 문구를 그렇게 한정할지만 결정한다.

### L2
- 심각도: 낮음
- 파일:줄: `src/recipe.py` (`after = item.get("after")` 다음 `check_id(after, location + ".after")`)
- 문제: 명세 오류 목록의 "`after` 누락"이 별도 문구 없이 "ID 형식은 ^[A-Z][A-Z0-9_]*$ 이어야 함"으로 출력된다.
- 근거: 누락 시 `after`가 `None`이라 `check_id`의 형식 오류로 잡힌다. 위치(`A.inspections[0].after`)는 정확히 나오고 종료 코드 3도 지켜지므로 명세 위반은 아니다(`invalid_structure.json`의 `bad.inspections[0].after`가 이 경우를 덮는다).
- 제안: 마감 전 수정하지 않는다. 여유가 있으면 "누락" 문구를 분리한다.

### L3
- 심각도: 낮음
- 파일:줄: `src/recipe.py` (`json.loads(...)`)
- 문제: JSON 객체 안의 중복 키(예: 모델 `"A"`를 두 번 정의)는 오류 없이 마지막 값으로 덮인다.
- 근거: 표준 `json.loads` 기본 동작. 명세 오류 목록에 없는 항목이라 위반은 아니나, "규칙책이 틀리면 전체 중단"이라는 decisions.md의 취지와는 틈이 있다. SHA-256은 원본 바이트 기준이라 추적성은 남는다.
- 제안: 범위 확대이므로 이번에는 하지 않는다. 2단계 이후 `object_pairs_hook`으로 중복 키 검출을 고려.

### L4
- 심각도: 낮음
- 파일:줄: `src/main.py` `run_recipe` 첫 `print`
- 문제: 터미널 첫 줄의 레시피 경로는 전달받은 경로 문자열 그대로라, 같은 파일을 상대/절대 경로로 주면 stdout이 달라진다.
- 근거: 명세 재현성 기준은 "같은 CSV + 같은 레시피"이며 T21 테스트는 같은 경로로 비교한다. 판정·CSV 보고서는 경로와 무관하므로 판정 재현성에는 영향 없다.
- 제안: 수정하지 않는다. 동일성 비교는 SHA-256 12자리로 하면 된다고 README에 한 줄 덧붙일지만 사용자가 결정.

### L5 (코드 외, 운영)
- 심각도: 낮음
- 파일:줄: `.claude/settings.json` (커밋 `b8213e7`)
- 문제: deny 목록에서 `Write(src/**)`, `Write(tests/**)`가 빠졌다. 검수자(Claude)에 대한 `src/`·`tests/` 쓰기 차단이 `Edit` 규칙에만 남는다.
- 근거: 범위 diff. 같은 커밋에서 allow의 `Write(handoff/reviews/**)`도 빠졌다. gpt-log 완료 보고에는 ".claude/를 수정하지 않았다"고 되어 있어, 이 커밋은 사용자 작업으로 보인다. Codex 산출물 문제는 아니므로 판정에 넣지 않는다.
- 제안: 의도한 변경인지 사용자가 확인한다. 의도가 아니면 deny의 `Write(src/**)`·`Write(tests/**)`를 되돌린다(setup-notes "Claude 권한 원칙"과 맞추기 위해).

## 미검증

- PowerShell 콘솔(UTF-8 설정)에서 사람이 보는 한글 출력 화면. 본 검수의 Bash 캡처는 cp949라 깨져 보였고, 화면 표시는 확인하지 않았다(보고서 CSV는 정상).
- 생성 CSV와 체크아웃 파일의 `cmp` 수준 엄격 바이트 비교. 본 검수는 `git status`(줄바꿈 정규화 후 비교)와 T10·T21 테스트로만 확인했다.
- gpt-log의 "테스트 선작성 후 실패 관측" 주장: 커밋 이력상 테스트와 구현이 같은 커밋에 있는 경우가 있어 git으로는 순서를 확인할 수 없다.
- `tools/review-loop.ps1` 변경의 실제 동작(루프 실행)은 검수하지 않았다.

VERDICT: PASS
