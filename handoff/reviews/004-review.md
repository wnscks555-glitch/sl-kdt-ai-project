# 리뷰 004 — v2 3단계 검사 설비 이상 감지·정지 (T33–T41)

- 검수자: Claude (읽기 전용)
- 기준: `handoff/tasks.md` 맨 위 「현행 작업: v2 3단계」의 명세·기대표 T33–T41, 보존 조건(v1 T1–T10, 1·2단계, 기존 샘플 보고서 9종)
- 범위: `git log`·`git diff b17c8b0b12537b6f7c202fd37c396327f4cf77a7..HEAD` (커밋 9개, f3e1382 ~ 26d8186)
- 읽은 자료: `handoff/setup-notes.md`, `tasks.md`, `decisions.md`, `gpt-log.md`(해석·이견 부분), `src/equipment.py`, `src/recipe_rules.py`(전체), `src/recipe_reports.py`·`src/main.py` diff, `tests/test_equipment.py`(전체), `tests/fixtures/equipment_unknown_inspection.json`, `reports/sample_events_equipment_{rows,products,equipment}.csv`, README 「설비 모드」 절

## 1. 실행한 명령과 결과

```
py -m unittest discover -s tests
```
```
.........................................................................
----------------------------------------------------------------------
Ran 73 tests in 8.623s

OK
```

```
git diff --stat b17c8b0b12537b6f7c202fd37c396327f4cf77a7..HEAD -- src/rules.py tests/test_rules.py tests/test_recipe.py tests/test_retest.py reports/sample_events_rows.csv reports/sample_events_products.csv reports/sample_events_rejections.csv reports/sample_events_v2_rows.csv reports/sample_events_v2_products.csv reports/sample_events_v2_rejections.csv reports/sample_events_retest_rows.csv reports/sample_events_retest_products.csv reports/sample_events_retest_rejections.csv AGENTS.md
```
```
(출력 없음 — 보호 대상 파일과 기존 보고서 9종 모두 변경 없음)
```

- **미검증**: CLI를 저장소 밖에서 내가 직접 실행해 보고서를 다시 만들고 바이트를 비교하는 작업은 하지 않았다. 이 세션 권한(don't ask 모드)에서 복합 Bash 명령이 거부됐고, 저장소 안에서 실행하면 `reports/`를 덮어쓰게 되어 쓰기 범위 규칙에 어긋난다. 대신 아래 테스트가 임시 폴더에서 CLI를 실행해 바이트를 비교하며, 이번 실행에서 통과했다.
  - `test_t41_without_equipment_all_nine_legacy_reports_unchanged`: v1·1단계·2단계 샘플을 `--equipment` 없이 실행해 체크아웃된 보고서 9종과 바이트 비교하고, 출력 파일이 3개뿐이며 터미널에 `설비:`가 없음을 확인
  - `test_sample_t33_to_t39_reports_and_all_rejected_state_unchanged`: 설비 샘플 보고서 4종 바이트 비교
  - `test_t41_four_reports_history_equipment_order_and_byte_reproducibility`: 같은 폴더 2회와 다른 폴더 1회 실행에서 stdout·보고서 4종 바이트 동일

## 2. 보존 조건

| 조건 | 결과 | 근거 |
| --- | --- | --- |
| `src/rules.py`, `tests/test_rules.py`·`test_recipe.py`·`test_retest.py`, `AGENTS.md` 무수정 | 충족 | 위 `git diff --stat`에 출력 없음 |
| v1 T1–T10 무수정 통과 | 충족 | `test_rules.py` 무변경, 전체 73개 통과 |
| v1 보고서 `reports/sample_events_*.csv` 3종 바이트 동일 | 충족(테스트로 확인) | 커밋 파일 무변경, `test_t41_without_equipment_all_nine_legacy_reports_unchanged`가 재생성 결과와 바이트 비교해 통과. v1 경로(`src/main.py:138-144`)는 `--equipment` 의존 검사만 앞에 추가됐고 v1 분기 자체는 그대로 |
| 1·2단계 동작·보고서 동일 | 충족 | `equipment_book is None`이면 `_invalid_fields`는 6열(`recipe_rules.py:200`), 설비 검사·기록·`@` 표시는 모두 `equipment_book is not None` 조건 안에 있음(`:140`, `:193`, `:226`, `:237`). `InspectionAttempt.text`는 equipment가 빈 값이면 접미사가 없음(`:32`). 보고서 개수 분기는 `len(reports) == 4`(`main.py`)인데, 설비가 없으면 3종이 반환됨 |

## 3. 기대표 대조

| ID | 결과 | 근거 |
| --- | --- | --- |
| T33 | 일치 | 원인 행은 허용된 뒤 `record`로 정지됨(`recipe_rules.py:193-195`, `equipment.py:33-38`). 단위 테스트에서 stopped_at_seq가 세 번째 행이고 p1·p3 보류, p2 진행, LEAK-1 가동. 샘플에서는 LEAK-2가 seq 14 FAIL, 20 PASS, 25 FAIL 뒤 25에서 정지 |
| T34 | 일치 | `정지된 설비` 거절(`:146-147`), p4 inspections `{}`. LEAK-1 행은 허용됨. 샘플 seq 30·31 |
| T35 | 일치 | 정지 검사가 재검사 분기보다 앞에서 `return`하므로 `open_requests`가 그대로 남음. LEAK-1 재검사는 `RULE_RETEST`, 재검사 1, 보류 해소. LEAK-1의 counted_results는 0(재검사는 세지 않음). 샘플 seq 32·33 |
| T36 | 일치 | 집계 조건 `row["inspection"] not in product.inspections`(갱신 전 product)라서 최초 결과만 셈. 폐기, LEAK-1 (1, 1, 가동). 샘플 seq 5–9 |
| T37 | 일치 | `recent_results`를 `[-window:]`로 잘라 판정(`equipment.py:34`). (4, 2, 가동)이며, 누적 FAIL 2건이어도 창 안에 FAIL이 1건이라 정지하지 않음을 테스트가 구분함 |
| T38 | 일치 | ①② `RULE_EQUIP`, ③④ `RULE_PRESERVE`. REGISTER·RETEST_REQUEST에 equipment를 기입한 경우와 7열이 아닌 행까지 추가로 확인. `reject()` 헬퍼가 제품과 설비 전체를 deepcopy로 비교함 |
| T39 | 일치 | 시점 거절 행은 `record` 전에 `return`함. 단위 테스트(LEAK-2)와 샘플(LEAK-1, seq 81·84·89·94)은 둘 다 거절 FAIL을 셌다면 더 일찍 정지했을 구성이라 이 차이를 실제로 가려냄 |
| T40 | 일치 | ①–⑥ fixture 7개(⑥은 `LEAK-1: "AIM"`) 모두 CLI 종료 코드 3, 오류 위치 표시, stdout 비어 있음, `reports/` 미생성. 다중 오류 fixture에서는 오류가 모두 출력됨. bool·문자열·소수·경계값(0, 21, 1/1, 20/20)도 따로 검사 |
| T41 | 일치 | ① 기존 9종 바이트 동일 ② `parser.error` → 종료 코드 2 ③ 7열 CSV를 `--equipment` 없이 주면 헤더 오류 2(그 반대와 열 순서가 바뀐 경우도 포함) ④ 보고서 4종과 stdout 바이트 동일. 규칙 집계는 재검사 모드 8개, 1단계 레시피 7개, products 열 차이까지 확인 |

판정 순서(형식 → 등록·미등록 → 폐기 → 레시피 → 설비 → 시점 → 최초·재검사)는 `recipe_rules.py:104-172`의 분기 순서와 같고, `test_priority_format_registration_discard_recipe_equipment_timing_duplicate`가 단계마다 확인한다. 보고서 형식(설비 파일 순서, 정지 전 stopped_at_seq 빈칸, rows의 `@LEAK-2`, history의 `[LEAK-2]`, 터미널의 설비 경로와 SHA-256 12자리)도 명세와 같다.

샘플 손계산: LEAK-1의 허용된 최초 결과는 seq 5, 31, 38, 43, 48, 53, 58, 71, 76, 81, 89, 94로 12건이고, FAIL은 5, 43, 58, 81, 94로 5건이다. 최근 3건이 FAIL, PASS, FAIL이 되는 94에서 정지한다. 보고서 `12,5,정지,94`와 같다. 거절 7건(EQUIP 4, PRESERVE 2, INSP_PRE 1)도 rows와 같다.

## 4. GPT 구현에 동의하는 부분

- **정지 판정을 허용 직전 한 곳에 둔 점**(`recipe_rules.py:193-196`): 거절 행은 모두 이 지점 전에 `return`하므로 "거절 행은 설비 기록을 바꾸지 않는다"가 코드 구조로 보장된다. 1·2단계의 "검증 후 한 번만 반영" 원칙을 그대로 따른다.
- **`EquipmentState`를 frozen dataclass와 `replace`로 만든 점**: 제품 상태와 같은 방식이라, 테스트에서 deepcopy 비교만으로 설비 상태 불변을 검사할 수 있다.
- **`type(value) is not int` 검사**(`equipment.py:72`): `isinstance`였다면 `True`가 통과했을 텐데, 명세의 "`true` 불가"를 정확히 지킨다.
- **샘플의 BUFFER 제품**: LEAK-1을 여러 시나리오가 함께 쓰는데, PASS 버퍼로 창을 비워 T37·T39가 서로 영향을 주지 않게 했다. README에도 이 이유를 적었다.
- **README 정지 기준 설명**: WECO 규칙과 다른 점(측정값·σ를 쓰지 않음)과 SL·업계 기준이 아니라는 점을 굵게 적어, `decisions.md`의 「정지 기준」 결정 이유와 맞는다.

## 5. 지적 사항

### L1 (낮음) / `src/main.py` `write_reports`·`print_reports` (`if len(reports) == 4`) / 보고서 개수로 설비 모드를 추정함
- 문제: 설비 모드인지 여부를 명시적인 값이 아니라 반환 튜플의 길이로 판단한다.
- 근거: 지금은 `build_recipe_reports`가 3개 또는 4개만 반환하므로 올바르게 동작한다. 하지만 보고서가 하나 더 늘면 조용히 잘못된 열 이름이 붙을 수 있다.
- 제안: 마감 전에는 수정하지 않는다. 다음 범위에서 `equipment_book is not None` 같은 명시적인 값을 넘기는 방식을 검토한다.

### L2 (낮음) / `src/equipment.py:37` / `record`가 정지 상태를 해제할 수 있는 구조
- 문제: `stopped_at_seq=seq if ... else None`이라서, 정지된 설비에 `record`가 다시 호출되면 정지가 풀린다.
- 근거: 정지 설비의 행은 `:146`에서 항상 거절되므로 지금은 이 경로에 도달하지 않는다. 즉 "정지는 실행이 끝날 때까지 유지"는 호출부의 불변 조건에 기대고 있다. T34·T35가 이 동작을 확인한다.
- 제안: 기록만 남긴다. 다음 범위에서 설비 재가동을 구현할 때 `self.stopped_at_seq or (...)` 형태로 바꾸는 것을 검토한다.

### L3 (낮음) / `data/sample_events_equipment.csv` seq 81–94 / T39 샘플은 기대표와 다른 설비(LEAK-1)를 씀
- 문제: 기대표 T39는 LEAK-2 기준인데, 샘플에서는 LEAK-1로 재현했다.
- 근거: 샘플에서는 LEAK-2가 T33에서 이미 정지했으므로 LEAK-2로는 재현할 수 없다. 단위 테스트 `test_t39_...`는 기대표대로 LEAK-2를 쓰며 통과했다. 판정 의미는 같다.
- 제안: 수정할 필요 없음. 원하면 README 샘플 설명에 "T39는 LEAK-1로 재현"이라는 한 줄을 추가한다.

### L4 (낮음) / `handoff/tasks.md:59` / 기대표 제목이 여전히 「초안 – 사용자 확정 전」
- 문제: 상태 줄(`:3`)은 "사용자 확정"인데, 기대표 제목은 초안 표시 그대로다.
- 근거: 2단계 리뷰 003에서도 같은 종류의 표기 불일치가 있었다. 판정에는 영향이 없다.
- 제안: 사용자가 원하면 제목에서 "초안" 표시를 지운다(사용자가 고칠 문서).

### L5 (낮음) / `README.md:74`, `:170`, `:236` / 이전 단계 절의 "제외 범위"에 지금은 구현된 기능이 남아 있음
- 문제: v1 절은 "재검사 제외", 1단계 절은 "설비·로트 제외", 2단계 절은 "설비·로트 제외"라고 적혀 있다.
- 근거: 각 절이 해당 단계의 범위를 기록한 것이라 틀린 내용은 아니다. 다만 처음 읽는 사람은 헷갈릴 수 있다.
- 제안: 마감일이므로 그대로 둬도 된다. 시간이 남으면 각 절 제목 옆에 "(해당 단계 기준)"이라고 적는다.

## 6. 결론

- 높음 0, 중간 0, 낮음 5(L1–L5, 기록만 하며 수정 요구가 아님).
- T33–T41 모두 기대표와 일치한다. 테스트 73개가 통과했다. v1·1·2단계 보존 조건은 diff 무변경과 CLI 바이트 비교 테스트로 확인했다.
- 미검증: 검수자가 CLI를 직접 다시 실행해 바이트를 비교하는 작업(권한 제약 때문이며, 같은 비교를 수행하는 테스트는 통과함).

VERDICT: PASS
