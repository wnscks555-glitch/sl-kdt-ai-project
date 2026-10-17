# 검수 001 — T1–T10 진행 조건 판정기 첫 구현

- 검수자: Claude (Claude Code, 읽기 전용)
- 검수일: 2026-10-17
- 대상 커밋: `20b604f feat: implement virtual process checks and CSV reports (T1-T10)` (기준 `cc3d211..20b604f`)
- 기준: `handoff/tasks.md` 명세와 사전 기대표 T1–T10 (`docs/`는 기준으로 쓰지 않음)
- 읽은 자료: `handoff/setup-notes.md`, `tasks.md`, `gpt-log.md`, `decisions.md`, `git log`, `git diff`, `src/rules.py`, `src/main.py`, `tests/test_rules.py`, `data/sample_events.csv`, `README.md`, `docs/requirements.md` 첫 줄, `AGENTS.md`

## 요약

높음·중간 항목은 없다. T1–T10이 모두 명세대로 동작하고, 각 시나리오가 테스트로 대응되며, 거절 시 상태 불변을 전체 제품 사전 비교로 확인한다. 아래 낮음 항목은 기록용이며 마감(2026-10-18) 전 수정을 요구하지 않는다.

## 직접 실행한 명령과 결과

### 1) 단위 테스트

```
py -m unittest discover -s tests
```

```
............
----------------------------------------------------------------------
Ran 12 tests in 0.294s

OK
exit=0
```

### 2) CLI 재현성 (저장소 밖 임시 폴더에서 실행해 추적 파일을 덮어쓰지 않음)

`PYTHONIOENCODING`을 지정하지 않은 상태로 실행했다 (시연 환경과 같은 조건).

```
PYTHONPATH=<project> py -m src.main <project>/data/sample_events.csv
```

```
exit(no PYTHONIOENCODING)=0
rows matches committed
products matches committed
rejections matches committed
```

새로 만든 보고서 3종이 커밋된 `reports/*.csv`와 바이트 단위로 같다 (`cmp`). 인코딩 오류 없이 종료 코드 0이다.

### 3) 경계 입력 탐침 (`src.rules.Process`를 import만 해서 호출, 소스 미수정)

| 입력 | 결과 | 판단 |
| --- | --- | --- |
| 본조립 뒤 `PRE_ASSEMBLY` | RULE_PRESERVE 거절, 상태 불변 | 적절 (사유 문구는 아래 L2) |
| product_id `" A"` (앞 공백) | 미등록 제품 거절 | 아래 L3 |
| inspection `light` (소문자) | RULE_PRESERVE 거절 | README에 명시된 해석과 일치 |
| result `"PASS "` (뒤 공백) | RULE_PRESERVE 거절 | 위와 같음 |
| 미등록 제품 `INSPECT` | RULE_PRESERVE 거절 | 적절 |
| 중복 `REGISTER` | RULE_PRESERVE 거절 | 적절 (gpt-log 가정 4와 일치) |
| `LEAK FAIL` 뒤 `LIGHT PASS`(첫 결과) | 허용, 보류 유지 | gpt-log 가정 3과 일치. 명세의 "FAIL은 계속 보류"를 어기지 않음 |
| 그 뒤 `LIGHT FAIL` | RULE_PRESERVE 거절, 결과 불변 | 적절 |

최종 상태 `{'A': ('MAIN_ASSEMBLY', {'LEAK': 'FAIL', 'LIGHT': 'PASS'}, '보류')}` 로 거절 행이 상태를 바꾸지 않았다.

## 기대표 대조

| ID | 기대 결과 | 코드·테스트·샘플 확인 | 판정 |
| --- | --- | --- | --- |
| T1 | 모의 흐름 완료 | `test_t1_…`, 샘플 seq 5 | 일치 |
| T2 | 거절 RULE_SEQ, '등록' 유지 | `rules.py:87-90`, `test_t2_…`가 전체 상태 불변 assert, 샘플 seq 7 | 일치 |
| T3 | 거절 RULE_INSP_PRE, 결과 저장 안 됨 | `rules.py:94-95`, `test_t3_…` inspections == {} | 일치 |
| T4 | 검사 대기, 'LEAK 미실시' | `test_t4_…`, 샘플 제품 T4 | 일치 |
| T5 | 보류, 'LEAK FAIL' | `test_t5_…`, 샘플 제품 T5 | 일치 |
| T6 | 거절 RULE_PRESERVE, FAIL·보류 유지 | `rules.py:97-98`, `test_t6_…` | 일치 |
| T7 | 거절 RULE_PRESERVE, 완료·PASS 유지 | `test_t7_…`, 샘플 seq 31 | 일치 |
| T8 | 두 번째 거절, 상태 변화 없음 | `rules.py:85-86`, `test_t8_…` | 일치 |
| T9 | 거절, 다른 제품 영향 없음 | `test_t9_…`가 OTHER 완료 상태 유지까지 assert | 일치 |
| T10 | 두 보고서 판정 열 동일 | `test_t10_…`가 stdout·CSV 3종 전체 바이트 비교 (명세보다 강함), 본 검수 2) 재확인 | 일치 |

## GPT 의견에 동의하는 부분

- **검증 후 일괄 반영 설계** (`rules.py:66-108`): 모든 거절 분기가 `return`으로 빠져나가고 `self.products[...] = updated`는 단 한 곳(107행)에만 있다. `Product`는 frozen이고 갱신은 `replace`와 새 dict로만 한다. 명세의 "메시지만 출력하고 상태는 바뀌는 오류 방지"를 구조로 보장한다. gpt-log의 S2 반박(주석 유지)에 동의한다. 107행 주석이 이 불변식을 설명한다.
- **판정/입출력 분리**: `rules.py`는 파일·터미널 접근이 없고 `main.py`만 I/O를 맡는다. 명세 조건 충족.
- **보류 우선 해석** (gpt-log 가정 3): `status`가 FAIL을 가장 먼저 검사하므로(`rules.py:26`) 이후 어떤 PASS도 보류를 풀 수 없다. 명세 "새 PASS로 덮어써서 해결하면 안 됨"과 맞는다.
- **결정성**: 시각·난수 사용이 없고, 제품 순서는 dict 삽입 순서, 규칙 순서는 `RULE_IDS` 튜플로 고정된다.
- **README 경계 문구**: "출하·양품·SL 기준 적합을 뜻하지 않는다"가 굵게 명시되어 있다. `docs/requirements.md` 첫 줄 추가도 명세대로이고 본문은 남아 있다.
- **완료 보고**: 기대표·테스트를 고치지 않았다고 명시했고, 해석·가정 8개를 숨김 없이 나열했다. 본 검수에서 그 주장과 다른 점은 찾지 못했다.

## 발견 사항

### L1
- 심각도: 낮음
- 파일:줄: `tests/test_rules.py:182-240`
- 문제: T10 테스트는 두 실행이 서로 같은지만 보고, 샘플의 판정 결과가 기대표와 맞는지(예: 제품 T5 = 보류, 거절 7건)는 assert하지 않는다.
- 근거: 기대표 T1–T9는 `ProcessRulesTests`에서 개별로 검증하므로 명세 위반은 아니다. 다만 `data/sample_events.csv`가 바뀌어 시나리오가 깨져도 테스트는 통과한다.
- 제안: 마감 전에는 수정하지 않아도 된다. 이후 여유가 있으면 제품 보고서의 9행을 기대값과 비교하는 assert 하나를 추가한다.

### L2
- 심각도: 낮음
- 파일:줄: `src/rules.py:85-86`
- 문제: 이미 지난 단계로 되돌아가는 이벤트(본조립 뒤 `PRE_ASSEMBLY`)도 거절 사유가 "중복 조립 이벤트"로 나온다.
- 근거: 단계 비교가 `current >= target` 한 조건이라 중복과 역행을 구분하지 않는다. 거절과 상태 보존은 정상이고 규칙 ID(RULE_PRESERVE)도 명세 범위 안이다.
- 제안: 수정하지 않는다. 시연에서 질문이 나오면 "이미 지난 단계 재입력은 중복으로 취급"이라고 설명하면 된다.

### L3
- 심각도: 낮음
- 파일:줄: `src/rules.py:119-120`
- 문제: `product_id`가 빈 값인지만 확인하고 앞뒤 공백은 정리하지 않는다. `" A"`는 `"A"`와 다른 미등록 제품으로 거절된다.
- 근거: 경계 탐침 결과. 거절이므로 상태를 바꾸지 않아 안전 쪽으로 동작한다. event·inspection·result의 "정확 일치" 정책(README)과 일관된다.
- 제안: 수정하지 않는다. README 입력 형식 절에 "product_id 앞뒤 공백도 그대로 구분함"을 한 줄 덧붙일지만 사용자가 결정한다.

### L4 (코드 외, 운영)
- 심각도: 낮음
- 파일:줄: `.claude/settings.json` (미커밋 변경), `tools/review-loop.ps1:79-81` (미추적)
- 문제: 작업 트리에 커밋하지 않은 변경이 있어, `review-loop.ps1`을 지금 실행하면 시작 직후 "커밋하지 않은 변경" 조건으로 멈춘다. 또 수정 회차 커밋이 `git add .`(`Save-Commit ... @('.')`)라서 그때 생긴 파일이 모두 함께 커밋된다.
- 근거: `git status` 결과 `M .claude/settings.json`, `?? tools/`. 스크립트 79행의 `git status --porcelain` 검사.
- 제안: 루프를 쓸 계획이면 사용자가 두 파일을 먼저 커밋한다. Codex 산출물 문제는 아니므로 판정에 넣지 않는다.

## 미검증

- PowerShell 콘솔에서 사람이 직접 보는 한글 출력 화면: 종료 코드 0과 인코딩 예외 없음까지만 확인했고, 화면 표시는 보지 않았다.
- gpt-log의 "테스트를 소스 작성 전에 먼저 작성" 주장: 커밋이 하나로 합쳐져 있어 git 이력으로 확인할 수 없다.
- 다른 PC나 `py` 런처가 없는 환경에서 T10 테스트 동작 (`subprocess`로 `py`를 직접 호출함).

VERDICT: PASS
