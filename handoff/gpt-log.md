# GPT(Codex) 작업 기록

작업 단위마다 아래 형식으로 추가하고 커밋한다.

## YYYY-MM-DD 작업 ID
- 연결 요구사항·시나리오:
- 변경 파일:
- 무엇을 왜 바꿨는지:
- 실행 방법과 결과:
- 리뷰 반영 (리뷰 번호·항목별 반영/보류/반박과 이유):

## 2026-10-17 T1–T10 진행 조건 판정기 구현

- 연결 요구사항·시나리오: `handoff/tasks.md`의 전체 명세와 사전 기대표 T1–T10.
- 변경 파일: `src/__init__.py`, `src/rules.py`, `src/main.py`, `tests/test_rules.py`, `data/sample_events.csv`, `README.md`, `docs/requirements.md`, `reports/sample_events_rows.csv`, `reports/sample_events_products.csv`, `reports/sample_events_rejections.csv`, 이 로그.
- 무엇을 왜 바꿨는지: 가상 공정 판정과 CSV 입출력을 분리했다. 모든 거절 조건을 먼저 확인하고 허용된 입력만 새 제품 상태로 반영한다. 최초 검사 결과를 보존하고 FAIL은 계속 보류한다. 고정 샘플 39행과 재현 가능한 보고서 3종을 함께 남긴다.
- 실행 방법과 결과: 아래 원문 기록 참조. T1–T10 각각의 테스트와 관련 경계 2개, 총 12개 통과. 샘플은 39행 중 허용 32행·거절 7행이다.

### 기대표와 실제 결과

사전 기대표와 다른 항목은 없다. 기대표는 변경하지 않았고, 테스트는 소스 작성 전에 만들었으며 구현 결과에 맞춰 기대값을 수정하지 않았다.

| ID | 실제 확인 결과 |
| --- | --- |
| T1 | 두 PASS 후 「선택한 두 검사까지의 모의 흐름 완료」, 미완료 이유 없음 |
| T2 | RULE_SEQ 거절, 등록 상태 및 전체 제품 상태 불변 |
| T3 | RULE_INSP_PRE 거절, 검사 결과 미저장 및 전체 제품 상태 불변 |
| T4 | 검사 대기, LEAK 미실시 |
| T5 | 보류, LEAK FAIL |
| T6 | RULE_PRESERVE 거절, 원래 LEAK FAIL·보류 및 전체 제품 상태 불변 |
| T7 | RULE_PRESERVE 거절, 원래 LIGHT PASS·완료 및 전체 제품 상태 불변 |
| T8 | 두 번째 예비 조립 RULE_PRESERVE 거절, 전체 제품 상태 불변 |
| T9 | 미등록 제품 이벤트와 result=OK 모두 RULE_PRESERVE 거절, 다른 제품을 포함한 전체 상태 불변 |
| T10 | 실제 CLI를 두 번 실행한 stdout·CSV 3종 전체 바이트 동일. 같은 작업 폴더에서 덮어쓰기 재실행해도 stdout과 보고서 SHA-256 동일 |

T2·T3·T6·T7·T8·T9는 거절 직전 `deepcopy(Process.products)`와 거절 직후 전체 제품 사전을 비교한다. 추가 경계 테스트는 잘못된 값·중복 등록/본조립과 FAIL/미실시 공존 시 보류 우선순위를 확인한다.

### 구현하면서 내린 해석·가정

1. `seq`는 양의 정수 행 표식으로 해석했다. 유일성·단조 증가 조건은 추가하지 않으며 CSV 물리 행 순서로 처리한다.
2. 본조립 전 상태는 '등록'·'예비 조립', 본조립 이후 미실시 검사가 있으면 '검사 대기'로 표시한다. 최종 완료명은 명세의 전체 문구를 사용한다.
3. FAIL과 미실시가 공존하면 '보류'를 우선한다. 아직 실시하지 않은 다른 검사의 최초 결과는 받을 수 있지만 기존 FAIL을 변경하거나 보류를 해제하지 않는다. 미완료 이유에는 FAIL·미실시·미완료 조립 단계를 함께 표시한다.
4. 값/열 수 오류, 미등록, 중복 등록·조립·검사 결과는 RULE_PRESERVE로 거절한다. 형식 검증을 먼저 수행하고, 유효한 입력에 순서·본조립 선행 조건을 검사한다. 중복 등록도 기존 상태 보존 대상으로 해석했다.
5. CSV 헤더는 명세의 5개 열 이름·순서를 정확히 사용하고 UTF-8(선택적 BOM)으로 읽는다. 이벤트·검사·결과는 대문자 정확 일치이며 비INSPECT 행의 두 검사 칸은 빈칸이어야 한다. product_id는 빈값/공백만 있는 값을 거절한다. 잘못된 데이터 행은 거절 후 계속 처리하고, 읽기·디코딩·헤더·CSV 파싱 오류는 종료 코드 2로 끝낸다.
6. 보고서 3종은 현재 작업 폴더의 reports/에 입력 파일 stem을 붙여 저장하고 같은 이름은 덮어쓴다. 각 실행은 입력 전체로 상태를 다시 계산하며 이전 보고서를 상태 저장소로 읽지 않는다. 행/제품/규칙 순서를 고정하고 시각·난수를 쓰지 않는다. CSV는 한글 확인을 위해 UTF-8 BOM으로 저장한다.
7. 허용된 등록·조립에는 RULE_SEQ, 허용된 미완료 검사에는 RULE_NOT_DONE, 허용된 FAIL/완료 판정에는 RULE_FAIL_HOLD를 표시한다. 거절 건수는 거절 행만 집계하며 다섯 규칙을 0건까지 모두 출력한다.
8. 터미널 출력 기록을 UTF-8로 받기 위해 실행 셸의 PYTHONIOENCODING만 지정했다. 판정 동작이나 입력값은 바꾸지 않는다.

### 실제 실행 명령과 출력 원문

실행 환경: Windows PowerShell, 저장소 project/. 아래 명령은 실제 실행한 애플리케이션·검증 명령이다. 테스트 출력의 실행 시간도 관측값 그대로 남긴다.

환경 확인:

```powershell
py --version
```

```text
Python 3.9.13
```

테스트를 먼저 작성한 지원 에이전트가 `py -m unittest discover -s tests`를 소스 작성 전에 실행해 `ModuleNotFoundError: No module named 'src.rules'`와 `FAILED (errors=1)`를 확인했다. 기존 구현이 없는 상태의 의도한 최초 실패이며, 이후 소스를 작성했다.

초기 실패 출력 원문(지원 에이전트 도구가 반환한 경로의 문자 깨짐도 그대로 보존):

```text
E
======================================================================
ERROR: test_rules (unittest.loader._FailedTest)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_rules
Traceback (most recent call last):
  File "C:\Users\PC\anaconda3\lib\unittest\loader.py", line 436, in _find_test_path
    module = self._get_module_from_name(name)
  File "C:\Users\PC\anaconda3\lib\unittest\loader.py", line 377, in _get_module_from_name
    __import__(name)
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_rules.py", line 10, in <module>
    from src.rules import Process
ModuleNotFoundError: No module named 'src.rules'


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
```

구현 후 기본 테스트(종료 코드 0):

```powershell
py -m unittest discover -s tests
```

```text
............
----------------------------------------------------------------------
Ran 12 tests in 0.353s

OK
```

시나리오별 테스트 확인(종료 코드 0):

```powershell
py -m unittest discover -s tests -v
```

```text
test_t10_identical_input_produces_identical_stdout_and_csv_bytes (test_rules.CommandLineTests) ... ok
test_fail_has_hold_priority_when_other_inspection_is_missing (test_rules.ProcessRulesTests) ... ok
test_preserve_invalid_values_and_duplicate_registration_or_main (test_rules.ProcessRulesTests) ... ok
test_t1_two_pass_results_complete_simulated_flow (test_rules.ProcessRulesTests) ... ok
test_t2_main_without_pre_is_rejected_and_registration_preserved (test_rules.ProcessRulesTests) ... ok
test_t3_inspection_before_main_is_rejected_without_saving_result (test_rules.ProcessRulesTests) ... ok
test_t4_missing_leak_keeps_inspection_pending (test_rules.ProcessRulesTests) ... ok
test_t5_leak_fail_holds_product (test_rules.ProcessRulesTests) ... ok
test_t6_later_pass_cannot_overwrite_fail_or_hold (test_rules.ProcessRulesTests) ... ok
test_t7_later_fail_cannot_overwrite_pass_or_completion (test_rules.ProcessRulesTests) ... ok
test_t8_duplicate_pre_assembly_preserves_entire_state (test_rules.ProcessRulesTests) ... ok
test_t9_unregistered_and_invalid_result_preserve_all_products (test_rules.ProcessRulesTests) ... ok

----------------------------------------------------------------------
Ran 12 tests in 0.326s

OK
```

샘플 CLI(종료 코드 0):

```powershell
$env:PYTHONIOENCODING = 'utf-8'
py -m src.main data/sample_events.csv
```

```text
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T1 | REGISTER | RULE_SEQ | 허용 |  | 등록
2 | T1 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
3 | T1 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
4 | T1 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
5 | T1 | INSPECT LEAK PASS | RULE_FAIL_HOLD | 허용 |  | 선택한 두 검사까지의 모의 흐름 완료
6 | T2 | REGISTER | RULE_SEQ | 허용 |  | 등록
7 | T2 | MAIN_ASSEMBLY | RULE_SEQ | 거절 | PRE_ASSEMBLY 미완료 | 등록
8 | T3 | REGISTER | RULE_SEQ | 허용 |  | 등록
9 | T3 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
10 | T3 | INSPECT LIGHT PASS | RULE_INSP_PRE | 거절 | MAIN_ASSEMBLY 미완료 | 예비 조립
11 | T4 | REGISTER | RULE_SEQ | 허용 |  | 등록
12 | T4 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
13 | T4 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
14 | T4 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
15 | T5 | REGISTER | RULE_SEQ | 허용 |  | 등록
16 | T5 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
17 | T5 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
18 | T5 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
19 | T5 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
20 | T6 | REGISTER | RULE_SEQ | 허용 |  | 등록
21 | T6 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
22 | T6 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
23 | T6 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
24 | T6 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
25 | T6 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
26 | T7 | REGISTER | RULE_SEQ | 허용 |  | 등록
27 | T7 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
28 | T7 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
29 | T7 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
30 | T7 | INSPECT LEAK PASS | RULE_FAIL_HOLD | 허용 |  | 선택한 두 검사까지의 모의 흐름 완료
31 | T7 | INSPECT LIGHT FAIL | RULE_PRESERVE | 거절 | LIGHT 결과 이미 존재 | 선택한 두 검사까지의 모의 흐름 완료
32 | T8 | REGISTER | RULE_SEQ | 허용 |  | 등록
33 | T8 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
34 | T8 | PRE_ASSEMBLY | RULE_PRESERVE | 거절 | 중복 조립 이벤트 | 예비 조립
35 | T9_UNREGISTERED | MAIN_ASSEMBLY | RULE_PRESERVE | 거절 | 미등록 제품 | 미등록
36 | T9 | REGISTER | RULE_SEQ | 허용 |  | 등록
37 | T9 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
38 | T9 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
39 | T9 | INSPECT LIGHT OK | RULE_PRESERVE | 거절 | 잘못된 result (PASS 또는 FAIL 필요) | 검사 대기

[제품별 최종 상태]
product_id | 최종 상태 | 미완료 이유
T1 | 선택한 두 검사까지의 모의 흐름 완료 | 
T2 | 등록 | PRE_ASSEMBLY 미완료; MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T3 | 예비 조립 | MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T4 | 검사 대기 | LEAK 미실시
T5 | 보류 | LEAK FAIL
T6 | 보류 | LEAK FAIL
T7 | 선택한 두 검사까지의 모의 흐름 완료 | 
T8 | 예비 조립 | MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T9 | 검사 대기 | LIGHT 미실시; LEAK 미실시

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_SEQ | 1
RULE_INSP_PRE | 1
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 0
RULE_PRESERVE | 5

저장 파일:
reports/sample_events_rows.csv
reports/sample_events_products.csv
reports/sample_events_rejections.csv
```

같은 명령을 같은 작업 디렉터리에서 다시 실행했고 종료 코드 0이었다. 두 번째 실행의 stdout 원문은 위 첫 번째 블록과 완전히 같았다. 실행 전·후 보고서 SHA-256도 각각 같았다.

| 보고서 | 두 실행에서 동일한 SHA-256 |
| --- | --- |
| `sample_events_rows.csv` | `EB4042FB981C2FFE6611117A0EBB5636C552177A894D83A4406A607B08A952C8` |
| `sample_events_products.csv` | `E2317C768731185C28B5040AEA345EB197873E76CF3459ADACF25B3EA89C86E6` |
| `sample_events_rejections.csv` | `72143E7C3410B4A0AC1829F139027FCBCA3FB305C7D83586CB0B2F8AC9D6C17F` |

보존 검증: `docs/requirements.md`는 지정한 첫 줄 외 기존 본문 바이트가 HEAD의 필터링 본문과 동일했다. `AGENTS.md`, `CLAUDE.md`, `.claude/settings.json`, `handoff/tasks.md`, `handoff/decisions.md`, `handoff/setup-notes.md`, `handoff/reviews/.gitkeep`의 SHA-256은 작업 전후 동일했다. 테스트·CLI·보존 검증 외에 패키지 설치나 원격 변경은 실행하지 않았다.

### 리뷰 반영

- 작업 전 최신 `handoff/reviews/`에는 .gitkeep만 있었으므로 Claude 리뷰 반영 대상은 없었다.
- 내부 단순화 점검 5개 관점에서 재사용·품질·효율·테스트 지적은 없었다.
- S1 모듈 docstring 삭제 제안: 반박. 교육 프로젝트에서 판정과 입출력의 역할·경계를 간단히 설명하므로 유지한다.
- S2 상태 반영 직전 주석 삭제 제안: 반박. '모든 검증 후 한 번 반영'이라는 상태 보존 설계 의도를 남겨 이후 수정 시 경계를 확인할 수 있도록 유지한다. 실제 검증 조건이나 테스트는 변경하지 않는다.
- C1 독립 코드 리뷰: 정확성·프로젝트 지침·테스트·유지보수성·입력 안전성·신뢰성·적대적 검토의 7개 관점 모두 지적 0건. T1–T10과 설계·보고서·산출물·제외 범위를 충족한다는 최종 결과(Ready to merge)를 확인했다. 반영할 코드 지적 사항은 없다.
- 위 리뷰는 내부 Codex 검토이며 외부 모델 전송이나 Claude 실행을 한 것이 아니다. Claude의 실제 교차검수 결과는 사용자가 검수 후 남길 handoff/reviews/ 기록으로 구분한다.
- 교훈 기록 판단(ce-compound mode:non-interactive): 상태 보존·보류 우선·결정성·실행 환경 판단은 최종 코드·테스트·README·이 로그에서 복원할 수 있어 별도 해결 문서를 만들지 않았다(Documentation skipped).
- 검증 범위: 실제 Python 3.9.13 테스트와 CLI, 보고서 재실행 동일성, 파일 보존, 정적 코드 리뷰. 별도 lint/typecheck 설정은 없다. 출력 원문의 빈 열 뒤 공백 2곳은 그대로 보존하며, 코드·일반 문서의 공백 검사와 구분했다.

## 2026-10-18 T1–T10 v2 착수 전 회귀 기준

- 시작 커밋 `27e8992` / `main` / 작업 트리 깨끗함. CE 설정·`docs/solutions/` 없음. 사용자 확정 현행 절과 5단계 순서를 구현 계획으로 사용한다(계획 재작성 없음). `ce-work mode:return-to-caller`의 native 경로로 로컬 구현·검증하고 주 에이전트가 리뷰·교훈 판단을 맡는다.
- 리뷰 001: L1 보류(v1 테스트 동결 및 사용자 보류 승인), L2 보류(v1 문구 보존), L3 보류(product_id 정확 일치 유지; v2 설명에 명시), L4 보류(당시 운영 기록이며 현재 트리 깨끗함; review-loop 실행은 범위 밖).
- 명세 이견: v1 생성 파일과 Git 내부 blob의 엄격한 바이트 비교는 착수 전부터 불일치한다. `core.autocrlf=true`, blob LF / 체크아웃·csv.writer 출력 CRLF가 원인이다. Git 체크아웃 필터를 적용한 커밋 파일과 생성 파일은 3종 모두 바이트 동일하고, CRLF를 LF로 바꿔 비교한 blob 내용도 동일하다. v1 보존을 위해 출력 줄바꿈·Git 설정·기대표를 바꾸지 않고 이 차이를 명시한다.
- 실제 실행 명령과 출력 원문(줄바꿈은 Markdown용 LF로 표시, 실행 환경 `PYTHONIOENCODING=utf-8`):

```powershell
py -m unittest discover -s tests
```

```text
............
----------------------------------------------------------------------
Ran 12 tests in 0.330s

OK
exit=0
```

```powershell
py -m src.main data/sample_events.csv
```

```text
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T1 | REGISTER | RULE_SEQ | 허용 |  | 등록
2 | T1 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
3 | T1 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
4 | T1 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
5 | T1 | INSPECT LEAK PASS | RULE_FAIL_HOLD | 허용 |  | 선택한 두 검사까지의 모의 흐름 완료
6 | T2 | REGISTER | RULE_SEQ | 허용 |  | 등록
7 | T2 | MAIN_ASSEMBLY | RULE_SEQ | 거절 | PRE_ASSEMBLY 미완료 | 등록
8 | T3 | REGISTER | RULE_SEQ | 허용 |  | 등록
9 | T3 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
10 | T3 | INSPECT LIGHT PASS | RULE_INSP_PRE | 거절 | MAIN_ASSEMBLY 미완료 | 예비 조립
11 | T4 | REGISTER | RULE_SEQ | 허용 |  | 등록
12 | T4 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
13 | T4 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
14 | T4 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
15 | T5 | REGISTER | RULE_SEQ | 허용 |  | 등록
16 | T5 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
17 | T5 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
18 | T5 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
19 | T5 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
20 | T6 | REGISTER | RULE_SEQ | 허용 |  | 등록
21 | T6 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
22 | T6 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
23 | T6 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
24 | T6 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
25 | T6 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
26 | T7 | REGISTER | RULE_SEQ | 허용 |  | 등록
27 | T7 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
28 | T7 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
29 | T7 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
30 | T7 | INSPECT LEAK PASS | RULE_FAIL_HOLD | 허용 |  | 선택한 두 검사까지의 모의 흐름 완료
31 | T7 | INSPECT LIGHT FAIL | RULE_PRESERVE | 거절 | LIGHT 결과 이미 존재 | 선택한 두 검사까지의 모의 흐름 완료
32 | T8 | REGISTER | RULE_SEQ | 허용 |  | 등록
33 | T8 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
34 | T8 | PRE_ASSEMBLY | RULE_PRESERVE | 거절 | 중복 조립 이벤트 | 예비 조립
35 | T9_UNREGISTERED | MAIN_ASSEMBLY | RULE_PRESERVE | 거절 | 미등록 제품 | 미등록
36 | T9 | REGISTER | RULE_SEQ | 허용 |  | 등록
37 | T9 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
38 | T9 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
39 | T9 | INSPECT LIGHT OK | RULE_PRESERVE | 거절 | 잘못된 result (PASS 또는 FAIL 필요) | 검사 대기

[제품별 최종 상태]
product_id | 최종 상태 | 미완료 이유
T1 | 선택한 두 검사까지의 모의 흐름 완료 | 
T2 | 등록 | PRE_ASSEMBLY 미완료; MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T3 | 예비 조립 | MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T4 | 검사 대기 | LEAK 미실시
T5 | 보류 | LEAK FAIL
T6 | 보류 | LEAK FAIL
T7 | 선택한 두 검사까지의 모의 흐름 완료 | 
T8 | 예비 조립 | MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T9 | 검사 대기 | LIGHT 미실시; LEAK 미실시

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_SEQ | 1
RULE_INSP_PRE | 1
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 0
RULE_PRESERVE | 5

저장 파일:
reports/sample_events_rows.csv
reports/sample_events_products.csv
reports/sample_events_rejections.csv
exit=0
```

비교 명령: `git cat-file --filters HEAD:reports/sample_events_<종류>.csv` 및 `git show HEAD:reports/sample_events_<종류>.csv`의 원시 바이트를 `Path.read_bytes()`와 비교.

```text
reports/sample_events_rows.csv: checkout_byte_equal=True, blob_byte_equal=False, LF_normalized_equal=True, SHA-256=eb4042fb981c2ffe6611117a0ebb5636c552177a894d83a4406a607b08a952c8
reports/sample_events_products.csv: checkout_byte_equal=True, blob_byte_equal=False, LF_normalized_equal=True, SHA-256=e2317c768731185c28b5040aea345eb197873e76cf3459adacf25b3ea89c86e6
reports/sample_events_rejections.csv: checkout_byte_equal=True, blob_byte_equal=False, LF_normalized_equal=True, SHA-256=72143e7c3410b4a0ac1829f139027fcbca3fb305c7d83586cb0b2f8ac9d6c17f
```

## 2026-10-18 ① 레시피 로드·검증 (T18)

- 변경: `src/recipe.py`, `recipes/lamp_models.json`, `tests/test_recipe.py`, `tests/fixtures/`. JSON 구조·허용 키·ID·중복·예약 공정·검사 시점을 전체 검증하고 원본 파일 바이트 SHA-256을 보존한다. CLI 종료 코드와 이벤트 미처리는 ③에서 연결한다.
- 테스트 선작성: `ModuleNotFoundError: No module named 'src.recipe'`로 의도한 실패 확인. 첫 구현 검증에서는 문자열이 아닌 공정 ID의 배열 수준 진단이 빠져 `E.steps` 위치 검사가 실패했다. 테스트/기대표는 유지하고 문자열 ID 배열의 구조 진단을 추가했다.
- 수행 오류: 첫 검증 실패 뒤 커밋 실행이 차단되지 않아 `0b086b9`에 미통과 구현이 들어갔다. 즉시 구현을 수정하고 이 후속 커밋 전에 전체 16개 테스트 통과를 확인했다. 이후 모든 커밋은 테스트 exit=0을 별도 확인한 후 실행한다.
- 실제 명령 `py -m unittest discover -s tests` 출력 원문:

```text
................
----------------------------------------------------------------------
Ran 16 tests in 0.326s

OK
exit=0
```
- 해석: UTF-8 BOM 허용. 읽기·디코딩 실패도 레시피 오류다. JSON 문법 오류는 파싱 위치를 표시하며 파싱 가능한 설정은 독립 오류를 모두 수집한다.

## 2026-10-18 ② v2 판정 (T11–T17, T19–T22 중 판정 항목)

- 변경: `src/recipe_rules.py`, `tests/test_recipe.py`. v1 파일을 가져다 옮기거나 고치지 않고 모델별 공정 위치·최초 검사 결과를 새 모듈로 관리한다. 모든 검증 후 제품 사전에 한 번만 반영한다.
- 테스트 지원 에이전트는 명세로 17개 테스트를 작성하고 `py -m unittest discover -s tests -p test_recipe.py`에서 `ModuleNotFoundError: No module named 'src.recipe_rules'`, `Ran 1 test`, `FAILED (errors=1)`을 관측했다. 주 에이전트도 모듈 부재를 확인한 후 구현했다. 기대값은 구현 결과에 맞춰 수정하지 않았다.
- T11–T17/T16b/T19/T20/T22 및 판정 우선순위·정확 일치·비숫자 공정명·배열 순서·seq 물리 행 순서 통과. 거절 테스트마다 전체 제품 사전을 deepcopy 비교하고 OTHER 제품도 확인한다. T21의 CLI 재현성은 ③에서 검증한다.
- 해석: 빈 event/INSPECT inspection은 형식 오류, 비어 있지 않은 미등록 공정·검사 ID는 `RULE_RECIPE`. 등록 model 빈값은 지정대로 `RULE_RECIPE`. 공정 건너뜀 사유는 가장 먼저 남아 있는 공정을 표시한다. 진행 상태의 Pk 자리에는 실제 마지막 공정 ID를 쓴다. rows의 input은 v1처럼 event/inspection/result로 유지하고 모델은 products에 기록한다.
- 실제 명령 `py -m unittest discover -s tests` 출력 원문:

```text
.................................
----------------------------------------------------------------------
Ran 33 tests in 0.335s

OK
exit=0
```

## 2026-10-18 ③ --recipe CLI 연결 (T18, T21 및 T11–T22 통합)

- 변경: `src/main.py`, `src/recipe_reports.py`, `tests/test_recipe.py`, `tests/fixtures/leak_after_p3.json`. 옵션 없을 때 기존 v1 build_reports/Process를 사용한다. CSV 읽기·쓰기·출력의 기본값은 유지하고 v2만 6열/모델열/6개 규칙을 사용한다. 레시피 전체 로드 성공 후에만 CSV 읽기·판정을 시작한다.
- 증거: CLI 테스트 먼저 추가 후 `py -m unittest discover -s tests -p test_recipe.py`에서 `unrecognized arguments: --recipe`, `Ran 25 tests`, `FAILED (failures=14)` 관측. 구현 후 전체 테스트 결과 원문:

```text
.....................................
----------------------------------------------------------------------
Ran 37 tests in 3.997s

OK
exit=0
```
- T18: 12개 잘못된/없는 설정과 없는 입력 CSV 조합에서 모두 종료 3, 이벤트 보고서·디렉터리 미생성 확인. 두 오류 위치를 함께 출력한다. 이미 존재하는 보고서는 지우지 않는다.
- T21: 별도 폴더 2회와 같은 폴더 덮어쓰기 1회의 stdout·3개 CSV 바이트 일치. B의 LEAK after만 P2→P3인 fixture에서 해당 검사 행이 허용→RULE_INSP_PRE 거절로 바뀌며 검사 결과가 미저장된다.
- v1/v2 헤더 교차 및 입력 읽기 오류는 종료 2. seq 중복/감소를 실제 CSV로 확인하고 열 수가 다른 행은 RULE_PRESERVE 거절 후 전체 제품 상태를 유지한다.
- 해석: SHA-256은 읽은 JSON 파일 원본 바이트(BOM·줄바꿈 포함) 기준이며 표시 경로는 전달받은 Path의 POSIX 표기다. JSON 읽기 실패도 레시피 오류 3이다.

## 2026-10-18 ④ 고정 샘플·보고서 (T11–T17, T19, T20, T22)

- 변경: `data/sample_events_v2.csv`, `reports/sample_events_v2_*.csv`, `tests/test_recipe.py`. 명세 시나리오를 제품별로 묶은 고정 76행이며 14개 제품, 허용 64행·거절 12행이다. T16b도 포함한다. 샘플 생성기 프로그램은 산출물에 추가하지 않았다.
- 증거: 샘플 기대값 테스트를 먼저 작성하고 샘플 파일 부재(exit=2)로 실패를 확인했다. 데이터 추가 후 14개 제품 상태/모델/미완료 사유 및 6개 거절 건수의 고정 기대값을 모두 확인했다(기존 리뷰 001 L1의 v2 대응).
- 실제 명령 `py -m unittest discover -s tests` 출력 원문:

```text
......................................
----------------------------------------------------------------------
Ran 38 tests in 4.113s

OK
exit=0
```
- 샘플 실행 명령과 출력 원문:

```powershell
py -m src.main data/sample_events_v2.csv --recipe recipes/lamp_models.json
```

```text
레시피: recipes/lamp_models.json | SHA-256: d7a8976ee178
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T11 | REGISTER | RULE_RECIPE | 허용 |  | 등록
2 | T11 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
3 | T11 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
4 | T11 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
5 | T11 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
6 | T11 | P5 | RULE_SEQ | 허용 |  | 검사 대기
7 | T11 | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
8 | T11 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
9 | T11 | INSPECT FINAL PASS | RULE_FAIL_HOLD | 허용 |  | 레시피 모의 흐름 완료
10 | T12_A | REGISTER | RULE_RECIPE | 허용 |  | 등록
11 | T12_B | REGISTER | RULE_RECIPE | 허용 |  | 등록
12 | T12_A | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
13 | T12_B | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
14 | T12_A | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
15 | T12_B | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
16 | T12_A | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
17 | T12_B | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
18 | T12_A | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
19 | T12_B | P4 | RULE_SEQ | 허용 |  | 검사 대기
20 | T12_B | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
21 | T12_B | INSPECT LIGHT PASS | RULE_FAIL_HOLD | 허용 |  | 레시피 모의 흐름 완료
22 | T13 | REGISTER | RULE_RECIPE | 허용 |  | 등록
23 | T13 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
24 | T13 | P3 | RULE_SEQ | 거절 | P2 미완료 | 공정 진행 중(P1 완료)
25 | T13 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
26 | T14_LEAK | REGISTER | RULE_RECIPE | 허용 |  | 등록
27 | T14_LEAK | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
28 | T14_LEAK | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
29 | T14_LEAK | INSPECT LEAK PASS | RULE_INSP_PRE | 거절 | P3 미완료 | 공정 진행 중(P2 완료)
30 | T14_LIGHT | REGISTER | RULE_RECIPE | 허용 |  | 등록
31 | T14_LIGHT | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
32 | T14_LIGHT | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
33 | T14_LIGHT | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
34 | T14_LIGHT | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
35 | T14_LIGHT | INSPECT LIGHT PASS | RULE_INSP_PRE | 거절 | P5 미완료 | 공정 진행 중(P4 완료)
36 | T15 | REGISTER | RULE_RECIPE | 허용 |  | 등록
37 | T15 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
38 | T15 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
39 | T15 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
40 | T15 | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
41 | T15 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
42 | T15 | P5 | RULE_SEQ | 허용 |  | 검사 대기
43 | T15 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
44 | T16 | REGISTER | RULE_RECIPE | 허용 |  | 등록
45 | T16 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
46 | T16 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
47 | T16 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
48 | T16 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
49 | T16 | P4 | RULE_FAIL_HOLD | 거절 | FAIL로 보류 중인 제품 | 보류
50 | T16 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
51 | T16B | REGISTER | RULE_RECIPE | 허용 |  | 등록
52 | T16B | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
53 | T16B | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
54 | T16B | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
55 | T16B | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
56 | T16B | P5 | RULE_SEQ | 허용 |  | 검사 대기
57 | T16B | INSPECT LIGHT FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
58 | T16B | INSPECT FINAL PASS | RULE_FAIL_HOLD | 허용 |  | 보류
59 | T17_C | REGISTER | RULE_RECIPE | 거절 | model이 비어 있거나 레시피에 없는 모델 | 미등록
60 | T17_A | REGISTER | RULE_RECIPE | 허용 |  | 등록
61 | T17_A | P6 | RULE_RECIPE | 거절 | 제품 레시피에 없는 공정 P6 | 등록
62 | T17_B | REGISTER | RULE_RECIPE | 허용 |  | 등록
63 | T17_B | INSPECT FINAL PASS | RULE_RECIPE | 거절 | 제품 레시피에 없는 검사 FINAL | 등록
64 | T19 | REGISTER | RULE_RECIPE | 허용 |  | 등록
65 | T19 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
66 | T19 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
67 | T19 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
68 | T19 | P4 | RULE_SEQ | 허용 |  | 검사 대기
69 | T19 | P5 | RULE_RECIPE | 거절 | 제품 레시피에 없는 공정 P5 | 검사 대기
70 | T20_MISSING | REGISTER | RULE_RECIPE | 거절 | model이 비어 있거나 레시피에 없는 모델 | 미등록
71 | T20 | REGISTER | RULE_RECIPE | 허용 |  | 등록
72 | T20 | P1 | RULE_PRESERVE | 거절 | REGISTER 이외의 model은 빈칸이어야 함 | 등록
73 | T22 | REGISTER | RULE_RECIPE | 허용 |  | 등록
74 | T22 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
75 | T22 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
76 | T22 | REGISTER | RULE_PRESERVE | 거절 | 이미 등록된 제품 | 공정 진행 중(P2 완료)

[제품별 최종 상태]
product_id | model | 최종 상태 | 미완료 이유
T11 | A | 레시피 모의 흐름 완료 | 
T12_A | A | 공정 진행 중(P4 완료) | P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T12_B | B | 레시피 모의 흐름 완료 | 
T13 | A | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T14_LEAK | A | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T14_LIGHT | A | 공정 진행 중(P4 완료) | P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T15 | A | 검사 대기 | FINAL 미실시
T16 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시
T16B | A | 보류 | LEAK 미실시; LIGHT FAIL
T17_A | A | 등록 | P1 미완료; P2 미완료; P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T17_B | B | 등록 | P1 미완료; P2 미완료; P3 미완료; P4 미완료; LEAK 미실시; LIGHT 미실시
T19 | B | 검사 대기 | LEAK 미실시; LIGHT 미실시
T20 | A | 등록 | P1 미완료; P2 미완료; P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T22 | A | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_RECIPE | 5
RULE_SEQ | 1
RULE_INSP_PRE | 2
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 1
RULE_PRESERVE | 3

저장 파일:
reports/sample_events_v2_rows.csv
reports/sample_events_v2_products.csv
reports/sample_events_v2_rejections.csv
exit=0
```

## 2026-10-18 ⑤ README (T11–T22)

- v1 설명을 보존하고 v2 실행법·6열 입력·JSON 형식·검증·6개 규칙·상태·재현성·보고서·제외 범위를 추가했다. 가상 규칙 및 완료가 품질/출하 판정이 아님을 명시했다.
- 문서 변경이므로 새 테스트는 추가하지 않고 위 단계에서 확보한 전체 테스트를 그대로 재실행했다. 명령 `py -m unittest discover -s tests` 출력 원문:

```text
......................................
----------------------------------------------------------------------
Ran 38 tests in 4.538s

OK
exit=0
```

## 2026-10-18 품질 단순화 (T11–T22)

- `ce-simplify-code mode:pipeline`: 재사용·품질·효율·테스트·주석의 5개 독립 검토를 수합했다. 재사용/품질/효율/테스트 변경 0건. 구현을 다시 설명하는 모듈 요약 주석 2개만 제거했다. 입출력 금지 경계를 설명하는 판정 모듈 docstring은 유지했다.
- v1/v2 의도적 분리를 유지하며 보호된 proof tests는 수정하지 않았다. 별도 lint/typecheck 설정은 없고 패키지 설치는 하지 않았다. 실제 명령 `py -m unittest discover -s tests` 출력 원문:

```text
......................................
----------------------------------------------------------------------
Ran 38 tests in 4.211s

OK
exit=0
```

## 2026-10-18 최종 v1 회귀·보존 확인 (T1–T10)

- 최종 구현 이후 실행한 명령과 출력 원문:

```powershell
py -m src.main data/sample_events.csv
```

```text
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T1 | REGISTER | RULE_SEQ | 허용 |  | 등록
2 | T1 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
3 | T1 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
4 | T1 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
5 | T1 | INSPECT LEAK PASS | RULE_FAIL_HOLD | 허용 |  | 선택한 두 검사까지의 모의 흐름 완료
6 | T2 | REGISTER | RULE_SEQ | 허용 |  | 등록
7 | T2 | MAIN_ASSEMBLY | RULE_SEQ | 거절 | PRE_ASSEMBLY 미완료 | 등록
8 | T3 | REGISTER | RULE_SEQ | 허용 |  | 등록
9 | T3 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
10 | T3 | INSPECT LIGHT PASS | RULE_INSP_PRE | 거절 | MAIN_ASSEMBLY 미완료 | 예비 조립
11 | T4 | REGISTER | RULE_SEQ | 허용 |  | 등록
12 | T4 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
13 | T4 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
14 | T4 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
15 | T5 | REGISTER | RULE_SEQ | 허용 |  | 등록
16 | T5 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
17 | T5 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
18 | T5 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
19 | T5 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
20 | T6 | REGISTER | RULE_SEQ | 허용 |  | 등록
21 | T6 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
22 | T6 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
23 | T6 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
24 | T6 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
25 | T6 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
26 | T7 | REGISTER | RULE_SEQ | 허용 |  | 등록
27 | T7 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
28 | T7 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
29 | T7 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
30 | T7 | INSPECT LEAK PASS | RULE_FAIL_HOLD | 허용 |  | 선택한 두 검사까지의 모의 흐름 완료
31 | T7 | INSPECT LIGHT FAIL | RULE_PRESERVE | 거절 | LIGHT 결과 이미 존재 | 선택한 두 검사까지의 모의 흐름 완료
32 | T8 | REGISTER | RULE_SEQ | 허용 |  | 등록
33 | T8 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
34 | T8 | PRE_ASSEMBLY | RULE_PRESERVE | 거절 | 중복 조립 이벤트 | 예비 조립
35 | T9_UNREGISTERED | MAIN_ASSEMBLY | RULE_PRESERVE | 거절 | 미등록 제품 | 미등록
36 | T9 | REGISTER | RULE_SEQ | 허용 |  | 등록
37 | T9 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
38 | T9 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
39 | T9 | INSPECT LIGHT OK | RULE_PRESERVE | 거절 | 잘못된 result (PASS 또는 FAIL 필요) | 검사 대기

[제품별 최종 상태]
product_id | 최종 상태 | 미완료 이유
T1 | 선택한 두 검사까지의 모의 흐름 완료 | 
T2 | 등록 | PRE_ASSEMBLY 미완료; MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T3 | 예비 조립 | MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T4 | 검사 대기 | LEAK 미실시
T5 | 보류 | LEAK FAIL
T6 | 보류 | LEAK FAIL
T7 | 선택한 두 검사까지의 모의 흐름 완료 | 
T8 | 예비 조립 | MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T9 | 검사 대기 | LIGHT 미실시; LEAK 미실시

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_SEQ | 1
RULE_INSP_PRE | 1
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 0
RULE_PRESERVE | 5

저장 파일:
reports/sample_events_rows.csv
reports/sample_events_products.csv
reports/sample_events_rejections.csv
exit=0
```
- 보고서는 `git cat-file --filters 27e8992:<파일>` 원시 바이트와 대조했다. raw blob LF/CRLF 차이는 착수 전과 같다. 보호 경로는 `git hash-object --path <파일> <파일>`과 `git rev-parse 27e8992:<파일>`의 내용 ID를 대조했다. 보호 파일 중 decisions.md처럼 이미 LF인 작업 파일도 있어 전체 원시 바이트가 checkout 필터와 같다고 주장하지 않는다.

```text
reports/sample_events_rows.csv: checkout_byte_equal=True, blob_byte_equal=False, SHA-256=eb4042fb981c2ffe6611117a0ebb5636c552177a894d83a4406a607b08a952c8
reports/sample_events_products.csv: checkout_byte_equal=True, blob_byte_equal=False, SHA-256=e2317c768731185c28b5040aea345eb197873e76cf3459adacf25b3ea89c86e6
reports/sample_events_rejections.csv: checkout_byte_equal=True, blob_byte_equal=False, SHA-256=72143e7c3410b4a0ac1829f139027fcbca3fb305c7d83586cb0b2f8ac9d6c17f
Protected tracked files: 8; all Git content IDs match starting commit 27e8992
Branch: main
```

## 2026-10-18 v2 1단계 완료 보고 (T1–T22)

- 사용자 확정 현행 절의 ① 레시피 로드·검증 → ② 판정 → ③ CLI → ④ 샘플·보고서 → ⑤ README 순서로 구현·검증·커밋했다. `main`에서 작업했으며 새 브랜치·push·원격 설정 변경·패키지 설치는 하지 않았다.
- 산출물: `recipes/lamp_models.json`, `src/recipe.py`, `src/recipe_rules.py`, `src/recipe_reports.py`, `src/main.py`, `tests/test_recipe.py`, `tests/fixtures/`, `data/sample_events_v2.csv`, `reports/sample_events_v2_rows.csv`, `reports/sample_events_v2_products.csv`, `reports/sample_events_v2_rejections.csv`, `README.md`.
- 검증: 착수 전 v1 12개 테스트, 레시피 16개, 판정 33개, CLI 37개, 샘플/README/최종 주석 정리 후 전체 38개 테스트(기존 v1 12 + v2 26) 모두 통과. 명령·출력 원문은 위 각 단계에 보존했다. 최종 v1 실행은 시작 체크아웃 보고서 3종과 바이트·SHA-256 동일하다.
- 기대표는 수정하지 않았다. `src/rules.py`, `tests/test_rules.py`, `handoff/tasks.md`, `handoff/decisions.md`, `handoff/reviews/`, `CLAUDE.md`, `.claude/`는 수정하지 않았다. 신규 테스트의 기대값도 구현 결과에 맞춰 변경하지 않았다.

### 기대표 대조

| ID | 실제 결과 |
| --- | --- |
| T11 | A의 5공정·3검사 PASS 후 레시피 모의 흐름 완료 |
| T12 | 섞인 입력에서도 B 완료, A P4 완료와 지정 미완료 사유 유지 |
| T13 | P3를 RULE_SEQ/P2 미완료로 거절, 상태 유지 후 P2 허용 |
| T14 | LEAK/P3 미완료, LIGHT/P5 미완료를 RULE_INSP_PRE로 거절, 검사 결과 미저장 |
| T15 | 중간 LEAK PASS 허용, 최종 검사 대기/FINAL 미실시 |
| T16 | LEAK FAIL 보류, P4 RULE_FAIL_HOLD 거절, 재입력 PASS RULE_PRESERVE 거절, P3/FAIL 유지 |
| T16b | LIGHT FAIL 뒤 FINAL 첫 PASS 허용, 보류 유지 |
| T17 | 없는 모델/제품 레시피에 없는 공정·검사 모두 RULE_RECIPE, 전체 상태 불변 |
| T18 | 지정 7사례 및 추가 구조/읽기 오류를 위치별 출력, 종료 3, 이벤트 미처리·보고서 미생성 |
| T19 | B의 P5 입력 RULE_RECIPE 거절, 전체 상태 불변 |
| T20 | 등록 model 빈값 RULE_RECIPE, 다른 행 model 기입 RULE_PRESERVE, 전체 상태 불변 |
| T21 | 동일 입력·레시피의 stdout/CSV 3종 바이트 동일; B LEAK after 변경 시 해당 검사 행의 판정 변화 |
| T22 | 다른 모델 재등록 RULE_PRESERVE/이미 등록된 제품 거절, 모델 A/P2 유지 |

v2 기대표와 실제 결과의 차이는 없다. **명세 이견:** v1의 Git 내부 blob과 생성 CSV를 변환 없이 비교하면 LF/CRLF 차이로 엄격한 바이트 동일 조건은 착수 전부터 성립하지 않았다. 체크아웃된 커밋 파일과의 바이트 동일 조건은 충족한다. 이 차이를 숨기거나 Git 설정·v1 출력·기대표를 변경하지 않았다.

### 명세가 모호해 내린 해석·가정

1. `seq`는 v1의 양의 정수 표식이다. 유일성/단조 증가를 요구하지 않고 물리적 행 순서로 처리한다. product_id와 ID의 앞뒤 공백을 정리하지 않는다.
2. 빈 event/INSPECT inspection은 빈칸 형식 오류로 RULE_PRESERVE, 비어 있지 않은 미등록 공정·검사는 RULE_RECIPE다. 등록 model 빈값은 명시된 RULE_RECIPE가 형식 오류보다 우선한다는 뜻이 아니라 형식 검사를 통과한 등록 행에 적용한다.
3. 진행 상태의 Pk는 하드코딩한 번호가 아닌 실제 완료 공정 ID다. 건너뜀 사유는 가장 먼저 남아 있는 공정을 표시한다.
4. rows의 input은 v1처럼 event/inspection/result로 표시한다. model은 지정된 products 열에 기록한다. 미등록 또는 거절된 신규 등록은 products에 만들지 않는다.
5. 레시피는 UTF-8 및 선택적 BOM을 허용하고 읽기/디코딩 실패도 종료 3으로 처리한다. JSON 문법이 깨지면 구문 위치를 알리고, 파싱 가능한 설정은 독립적으로 확인할 수 있는 모든 구조 오류를 수집한다.
6. 해시는 재직렬화가 아닌 원본 레시피 파일 바이트 기준(BOM·줄바꿈 포함)이다. 표시 경로는 인자로 받은 Path의 POSIX 표기다.
7. 보고서 위치·BOM·덮어쓰기·입력 stem 방식은 v1과 같다. 잘못된 레시피는 보고서를 생성·덮어쓰지 않으며 기존 보고서를 삭제하지 않는다.
8. 모듈/보고서의 일부 구조 중복은 v1 동결을 위한 의도적 분리로 유지한다. 별도 lint/typecheck 설정은 없으므로 설치 없이 unittest와 실제 CLI·보고서 바이트 대조로 검증했다.

### 교훈 기록 판단

`ce-compound mode:non-interactive`: Documentation skipped. 판정·상태 보존 판단은 코드·테스트·README에서 복원 가능하고, 줄바꿈 비교 조건은 이 로그에 근거·재현 명령을 이미 기록했다. 별도 해결 지식 문서를 중복 생성하지 않았다.

### 확인 범위와 한계

- Windows/Python 3.9.13의 `py`로 로컬 검증했다. 다른 운영체제와 콘솔의 육안 한글 표시는 검증하지 않았다.
- 보류 해제·재검사·정정·설비·로트·그래프·중간 관문·대량 생성기는 현행 제외 범위대로 구현하지 않았다.
- `git diff --check`에서 원문 CLI 출력의 빈 미완료 사유 뒤 구분자 공백을 trailing whitespace로 표시한다. 로그 원문 보존 요구에 따라 이 공백은 유지한다.

### 최종 코드 리뷰 (T1–T22)

- `ce-code-review mode:agent base:27e8992 plan:handoff/tasks.md`의 full 범위로 correctness, adversarial, testing, standards, security, maintainability, reliability 7개 관점을 검토했다. 7개 결과 모두 실질 지적/추가 테스트 공백 0건이다.
- 독립 반례 탐침은 모델별 상태 분리, 보류 중 규칙 우선순위, 다른 검사의 최초 결과 허용, 임의 공정명·배열 순서, 다중 모델 설정 오류 시 이벤트/보고서 호출 차단을 확인했다. 외부 모델로 코드 전송은 하지 않았다. 병합 결과 primary=0, selected=0이며 추가 finding 검증 대상은 없다.
- 기존 v1.0 태그를 유지했다. 최종 보존 대조와 코드/테스트에 대한 `git diff --check 27e8992 -- . ":(exclude)handoff/gpt-log.md"`는 변경·공백 오류 없이 통과했다.

# 2026-10-18 v2 2단계: 재검사·폐기 (T23–T32)
## 착수·계획과 회귀 기준

- main에서 시작, 작업 전 git status --short 출력 없음. 기준 커밋 230f437. 새 브랜치·원격 작업·패키지 설치 없음.
- practical-work-operation 적용. 현행 절은 충분한 작업 순서·검증이 있어 별도 계획 문서를 만들지 않고 ce-work mode:return-to-caller로 실행한다. 구현 후 주 에이전트가 단순화·리뷰·교훈 기록 여부를 판단한다. docs/solutions 및 CE 설정 없음.
- 순서: ① 레시피 검증(T31) → ② 판정(T23–T30) → ③ 모드·보고서(T32) → ④ 고정 샘플·보고서 → ⑤ README. 각 단계 전체 테스트와 경로 한정 커밋. 완료 보고는 마지막 별도 커밋.
- 해석: tasks.md의 초안 표시는 이번 사용자 구현 요청과 decisions.md의 2단계 착수 승인으로 확정된 작업 범위로 취급. 해당 파일은 수정하지 않는다.
- 리뷰 002 처리: L1 반영(결정 기록의 체크아웃 파일 기준으로 엄격 바이트 비교), L2 보류(after 누락 문구는 범위 밖), L3 보류(JSON 중복 키는 범위 밖), L4 보류(경로 표현 유지), L5 반영(사용자가 의도한 설정 변경으로 확인했으므로 읽기 전용 유지).

명령: `py -m unittest discover -s tests`

```text
......................................
----------------------------------------------------------------------
Ran 38 tests in 3.902s

OK
```
종료 코드: 0

명령: `py -m src.main data/sample_events.csv`

```text
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T1 | REGISTER | RULE_SEQ | 허용 |  | 등록
2 | T1 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
3 | T1 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
4 | T1 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
5 | T1 | INSPECT LEAK PASS | RULE_FAIL_HOLD | 허용 |  | 선택한 두 검사까지의 모의 흐름 완료
6 | T2 | REGISTER | RULE_SEQ | 허용 |  | 등록
7 | T2 | MAIN_ASSEMBLY | RULE_SEQ | 거절 | PRE_ASSEMBLY 미완료 | 등록
8 | T3 | REGISTER | RULE_SEQ | 허용 |  | 등록
9 | T3 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
10 | T3 | INSPECT LIGHT PASS | RULE_INSP_PRE | 거절 | MAIN_ASSEMBLY 미완료 | 예비 조립
11 | T4 | REGISTER | RULE_SEQ | 허용 |  | 등록
12 | T4 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
13 | T4 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
14 | T4 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
15 | T5 | REGISTER | RULE_SEQ | 허용 |  | 등록
16 | T5 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
17 | T5 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
18 | T5 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
19 | T5 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
20 | T6 | REGISTER | RULE_SEQ | 허용 |  | 등록
21 | T6 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
22 | T6 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
23 | T6 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
24 | T6 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
25 | T6 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
26 | T7 | REGISTER | RULE_SEQ | 허용 |  | 등록
27 | T7 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
28 | T7 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
29 | T7 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
30 | T7 | INSPECT LEAK PASS | RULE_FAIL_HOLD | 허용 |  | 선택한 두 검사까지의 모의 흐름 완료
31 | T7 | INSPECT LIGHT FAIL | RULE_PRESERVE | 거절 | LIGHT 결과 이미 존재 | 선택한 두 검사까지의 모의 흐름 완료
32 | T8 | REGISTER | RULE_SEQ | 허용 |  | 등록
33 | T8 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
34 | T8 | PRE_ASSEMBLY | RULE_PRESERVE | 거절 | 중복 조립 이벤트 | 예비 조립
35 | T9_UNREGISTERED | MAIN_ASSEMBLY | RULE_PRESERVE | 거절 | 미등록 제품 | 미등록
36 | T9 | REGISTER | RULE_SEQ | 허용 |  | 등록
37 | T9 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
38 | T9 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
39 | T9 | INSPECT LIGHT OK | RULE_PRESERVE | 거절 | 잘못된 result (PASS 또는 FAIL 필요) | 검사 대기

[제품별 최종 상태]
product_id | 최종 상태 | 미완료 이유
T1 | 선택한 두 검사까지의 모의 흐름 완료 | 
T2 | 등록 | PRE_ASSEMBLY 미완료; MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T3 | 예비 조립 | MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T4 | 검사 대기 | LEAK 미실시
T5 | 보류 | LEAK FAIL
T6 | 보류 | LEAK FAIL
T7 | 선택한 두 검사까지의 모의 흐름 완료 | 
T8 | 예비 조립 | MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T9 | 검사 대기 | LIGHT 미실시; LEAK 미실시

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_SEQ | 1
RULE_INSP_PRE | 1
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 0
RULE_PRESERVE | 5

저장 파일:
reports/sample_events_rows.csv
reports/sample_events_products.csv
reports/sample_events_rejections.csv
```
종료 코드: 0

명령: `py -m src.main data/sample_events_v2.csv --recipe recipes/lamp_models.json`

```text
레시피: recipes/lamp_models.json | SHA-256: d7a8976ee178
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T11 | REGISTER | RULE_RECIPE | 허용 |  | 등록
2 | T11 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
3 | T11 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
4 | T11 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
5 | T11 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
6 | T11 | P5 | RULE_SEQ | 허용 |  | 검사 대기
7 | T11 | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
8 | T11 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
9 | T11 | INSPECT FINAL PASS | RULE_FAIL_HOLD | 허용 |  | 레시피 모의 흐름 완료
10 | T12_A | REGISTER | RULE_RECIPE | 허용 |  | 등록
11 | T12_B | REGISTER | RULE_RECIPE | 허용 |  | 등록
12 | T12_A | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
13 | T12_B | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
14 | T12_A | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
15 | T12_B | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
16 | T12_A | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
17 | T12_B | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
18 | T12_A | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
19 | T12_B | P4 | RULE_SEQ | 허용 |  | 검사 대기
20 | T12_B | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
21 | T12_B | INSPECT LIGHT PASS | RULE_FAIL_HOLD | 허용 |  | 레시피 모의 흐름 완료
22 | T13 | REGISTER | RULE_RECIPE | 허용 |  | 등록
23 | T13 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
24 | T13 | P3 | RULE_SEQ | 거절 | P2 미완료 | 공정 진행 중(P1 완료)
25 | T13 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
26 | T14_LEAK | REGISTER | RULE_RECIPE | 허용 |  | 등록
27 | T14_LEAK | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
28 | T14_LEAK | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
29 | T14_LEAK | INSPECT LEAK PASS | RULE_INSP_PRE | 거절 | P3 미완료 | 공정 진행 중(P2 완료)
30 | T14_LIGHT | REGISTER | RULE_RECIPE | 허용 |  | 등록
31 | T14_LIGHT | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
32 | T14_LIGHT | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
33 | T14_LIGHT | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
34 | T14_LIGHT | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
35 | T14_LIGHT | INSPECT LIGHT PASS | RULE_INSP_PRE | 거절 | P5 미완료 | 공정 진행 중(P4 완료)
36 | T15 | REGISTER | RULE_RECIPE | 허용 |  | 등록
37 | T15 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
38 | T15 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
39 | T15 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
40 | T15 | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
41 | T15 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
42 | T15 | P5 | RULE_SEQ | 허용 |  | 검사 대기
43 | T15 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
44 | T16 | REGISTER | RULE_RECIPE | 허용 |  | 등록
45 | T16 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
46 | T16 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
47 | T16 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
48 | T16 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
49 | T16 | P4 | RULE_FAIL_HOLD | 거절 | FAIL로 보류 중인 제품 | 보류
50 | T16 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
51 | T16B | REGISTER | RULE_RECIPE | 허용 |  | 등록
52 | T16B | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
53 | T16B | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
54 | T16B | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
55 | T16B | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
56 | T16B | P5 | RULE_SEQ | 허용 |  | 검사 대기
57 | T16B | INSPECT LIGHT FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
58 | T16B | INSPECT FINAL PASS | RULE_FAIL_HOLD | 허용 |  | 보류
59 | T17_C | REGISTER | RULE_RECIPE | 거절 | model이 비어 있거나 레시피에 없는 모델 | 미등록
60 | T17_A | REGISTER | RULE_RECIPE | 허용 |  | 등록
61 | T17_A | P6 | RULE_RECIPE | 거절 | 제품 레시피에 없는 공정 P6 | 등록
62 | T17_B | REGISTER | RULE_RECIPE | 허용 |  | 등록
63 | T17_B | INSPECT FINAL PASS | RULE_RECIPE | 거절 | 제품 레시피에 없는 검사 FINAL | 등록
64 | T19 | REGISTER | RULE_RECIPE | 허용 |  | 등록
65 | T19 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
66 | T19 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
67 | T19 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
68 | T19 | P4 | RULE_SEQ | 허용 |  | 검사 대기
69 | T19 | P5 | RULE_RECIPE | 거절 | 제품 레시피에 없는 공정 P5 | 검사 대기
70 | T20_MISSING | REGISTER | RULE_RECIPE | 거절 | model이 비어 있거나 레시피에 없는 모델 | 미등록
71 | T20 | REGISTER | RULE_RECIPE | 허용 |  | 등록
72 | T20 | P1 | RULE_PRESERVE | 거절 | REGISTER 이외의 model은 빈칸이어야 함 | 등록
73 | T22 | REGISTER | RULE_RECIPE | 허용 |  | 등록
74 | T22 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
75 | T22 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
76 | T22 | REGISTER | RULE_PRESERVE | 거절 | 이미 등록된 제품 | 공정 진행 중(P2 완료)

[제품별 최종 상태]
product_id | model | 최종 상태 | 미완료 이유
T11 | A | 레시피 모의 흐름 완료 | 
T12_A | A | 공정 진행 중(P4 완료) | P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T12_B | B | 레시피 모의 흐름 완료 | 
T13 | A | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T14_LEAK | A | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T14_LIGHT | A | 공정 진행 중(P4 완료) | P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T15 | A | 검사 대기 | FINAL 미실시
T16 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시
T16B | A | 보류 | LEAK 미실시; LIGHT FAIL
T17_A | A | 등록 | P1 미완료; P2 미완료; P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T17_B | B | 등록 | P1 미완료; P2 미완료; P3 미완료; P4 미완료; LEAK 미실시; LIGHT 미실시
T19 | B | 검사 대기 | LEAK 미실시; LIGHT 미실시
T20 | A | 등록 | P1 미완료; P2 미완료; P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T22 | A | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_RECIPE | 5
RULE_SEQ | 1
RULE_INSP_PRE | 2
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 1
RULE_PRESERVE | 3

저장 파일:
reports/sample_events_v2_rows.csv
reports/sample_events_v2_products.csv
reports/sample_events_v2_rejections.csv
```
종료 코드: 0

재생성 전 체크아웃 파일의 SHA-256과 재생성 파일의 SHA-256 직접 비교(줄바꿈 정규화 없음):

```text
reports/sample_events_products.csv: 체크아웃 바이트 동일=True
reports/sample_events_rejections.csv: 체크아웃 바이트 동일=True
reports/sample_events_rows.csv: 체크아웃 바이트 동일=True
reports/sample_events_v2_products.csv: 체크아웃 바이트 동일=True
reports/sample_events_v2_rejections.csv: 체크아웃 바이트 동일=True
reports/sample_events_v2_rows.csv: 체크아웃 바이트 동일=True
```

## ① 레시피 검증 (T31)

- 레시피 전체 모델의 retest_limit 유무·1–5 정수(bool 제외) 검증, RETEST_REQUEST 예약어 추가. 기본 파일은 기존 레시피에 상한 2만 추가.
- 기존 로더 테스트를 읽고 tests/test_retest.py의 T31 테스트 3개와 오류 픽스처 6개를 먼저 작성. 구현 전 failures=3, errors=3(기본 파일 없음·유효 상한 거절·혼합 설정/예약어 오류 미검출)을 확인했다. 구현 후 아래 전체 41개 테스트 통과.
- 검증 로그 수집 도중 PowerShell 파이프의 cp949/UTF-8 불일치로 보조 스크립트 2회가 SyntaxError로 시작되지 않았다. 저장소 밖 UTF-8 파일로 실행해 해결했으며 제품 코드와 출력 인코딩은 바꾸지 않았다.

명령: `py -m unittest discover -s tests`

```text
.........................................
----------------------------------------------------------------------
Ran 41 tests in 5.376s

OK
```
종료 코드: 0

## ② 재검사 판정 (T23–T30)

- 제품·검사별 열린 요청, 허용된 재검사 결과 횟수, 최초 FAIL을 보존하는 시도 이력, 폐기 원인을 추가. 검증을 끝낸 새 상태만 기존 한 곳에서 반영한다. 거절은 전체 제품 딕셔너리 깊은 복사와 비교한다.
- T23–T30 및 판정 우선순위·동시 요청·물리적 순서 이력 테스트 10개를 먼저 추가. 구현 전 아래 9개 실패(요청이 기존 형식 오류로 거절됨), 구현 후 전체 51개 통과. tests/test_rules.py·tests/test_recipe.py는 그대로 사용했다.
- **명세 이견(T32)**: 기존 1단계는 inspection이 채워진 RETEST_REQUEST를 RULE_PRESERVE로 거절했다. 현행 명세의 명시 기대 RULE_RECIPE를 우선하여 요청 형식을 따로 인식하고 재검사 모드가 아니면 RULE_RECIPE로 거절한다. T11–T22 및 기존 보고서는 유지한다. 기대표·기존 테스트는 수정하지 않는다.
- **명세 이견(결정 근거)**: decisions.md의 “미해결 FAIL 최대 1개” 설명과 달리 T29는 복수 FAIL을 요구한다. 현행 규칙대로 제품+검사별 요청·횟수를 독립 관리하며 동시 요청도 허용한다.
- 해석: history에는 허용된 최초 결과·요청·재검사만 남긴다. 검사 그룹은 레시피 순서, 각 그룹은 실제 입력 순서를 유지하고 seq로 정렬하지 않는다. 폐기 이유는 명세 문자열 그대로이며, 한도 2회에 도달한 FAIL에 폐기된다(세 번째 재검사를 기다리지 않음).

명령: `py -m unittest discover -s tests -p test_retest.py`

```text
FFFF.FFFFF...
======================================================================
FAIL: test_parallel_requests_and_history_follow_recipe_and_physical_order (test_retest.RetestProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 244, in test_parallel_requests_and_history_follow_recipe_and_physical_order
    self.request("FINAL")
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 116, in request
    return self.accept("RETEST_REQUEST", inspection=inspection, rule_id="RULE_RETEST")
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 91, in accept
    self.assertTrue(decision.accepted, decision)
AssertionError: False is not true : Decision(seq='11', product_id='a', input_text='RETEST_REQUEST FINAL', rule_id='RULE_PRESERVE', accepted=False, reason='INSPECT 이외의 inspection과 result는 빈칸이어야 함', state='보류')

======================================================================
FAIL: test_priority_format_registration_scrap_recipe_and_inspection_timing (test_retest.RetestProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 230, in test_priority_format_registration_scrap_recipe_and_inspection_timing
    self.scrap()
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 124, in scrap
    self.request()
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 116, in request
    return self.accept("RETEST_REQUEST", inspection=inspection, rule_id="RULE_RETEST")
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 91, in accept
    self.assertTrue(decision.accepted, decision)
AssertionError: False is not true : Decision(seq='8', product_id='a', input_text='RETEST_REQUEST LEAK', rule_id='RULE_PRESERVE', accepted=False, reason='INSPECT 이외의 inspection과 result는 빈칸이어야 함', state='보류')

======================================================================
FAIL: test_t23_request_keeps_hold_and_does_not_count_as_attempt (test_retest.RetestProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 130, in test_t23_request_keeps_hold_and_does_not_count_as_attempt
    requested = self.request()
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 116, in request
    return self.accept("RETEST_REQUEST", inspection=inspection, rule_id="RULE_RETEST")
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 91, in accept
    self.assertTrue(decision.accepted, decision)
AssertionError: False is not true : Decision(seq='8', product_id='a', input_text='RETEST_REQUEST LEAK', rule_id='RULE_PRESERVE', accepted=False, reason='INSPECT 이외의 inspection과 result는 빈칸이어야 함', state='보류')

======================================================================
FAIL: test_t24_pass_releases_hold_resumes_and_preserves_original_fail (test_retest.RetestProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 142, in test_t24_pass_releases_hold_resumes_and_preserves_original_fail
    request = self.request()
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 116, in request
    return self.accept("RETEST_REQUEST", inspection=inspection, rule_id="RULE_RETEST")
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 91, in accept
    self.assertTrue(decision.accepted, decision)
AssertionError: False is not true : Decision(seq='8', product_id='a', input_text='RETEST_REQUEST LEAK', rule_id='RULE_PRESERVE', accepted=False, reason='INSPECT 이외의 inspection과 result는 빈칸이어야 함', state='보류')

======================================================================
FAIL: test_t26_failed_retest_consumes_request_and_second_pass_is_allowed (test_retest.RetestProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 161, in test_t26_failed_retest_consumes_request_and_second_pass_is_allowed
    self.request()
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 116, in request
    return self.accept("RETEST_REQUEST", inspection=inspection, rule_id="RULE_RETEST")
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 91, in accept
    self.assertTrue(decision.accepted, decision)
AssertionError: False is not true : Decision(seq='8', product_id='a', input_text='RETEST_REQUEST LEAK', rule_id='RULE_PRESERVE', accepted=False, reason='INSPECT 이외의 inspection과 result는 빈칸이어야 함', state='보류')

======================================================================
FAIL: test_t27_limit_fail_is_accepted_then_all_inputs_preserve_scrap (test_retest.RetestProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 174, in test_t27_limit_fail_is_accepted_then_all_inputs_preserve_scrap
    decision = self.scrap()
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 124, in scrap
    self.request()
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 116, in request
    return self.accept("RETEST_REQUEST", inspection=inspection, rule_id="RULE_RETEST")
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 91, in accept
    self.assertTrue(decision.accepted, decision)
AssertionError: False is not true : Decision(seq='8', product_id='a', input_text='RETEST_REQUEST LEAK', rule_id='RULE_PRESERVE', accepted=False, reason='INSPECT 이외의 inspection과 result는 빈칸이어야 함', state='보류')

======================================================================
FAIL: test_t28_request_rejections_preserve_every_product (test_retest.RetestProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 187, in test_t28_request_rejections_preserve_every_product
    self.reject(self.row("RETEST_REQUEST", inspection="LEAK"), "RULE_RETEST", "미해결 FAIL 없음")
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 101, in reject
    self.assertEqual(decision.rule_id, rule_id)
AssertionError: 'RULE_PRESERVE' != 'RULE_RETEST'
- RULE_PRESERVE
+ RULE_RETEST


======================================================================
FAIL: test_t29_other_failed_inspection_keeps_hold_and_requests_are_independent (test_retest.RetestProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 207, in test_t29_other_failed_inspection_keeps_hold_and_requests_are_independent
    self.request("LIGHT")
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 116, in request
    return self.accept("RETEST_REQUEST", inspection=inspection, rule_id="RULE_RETEST")
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 91, in accept
    self.assertTrue(decision.accepted, decision)
AssertionError: False is not true : Decision(seq='12', product_id='a', input_text='RETEST_REQUEST LIGHT', rule_id='RULE_PRESERVE', accepted=False, reason='INSPECT 이외의 inspection과 result는 빈칸이어야 함', state='보류')

======================================================================
FAIL: test_t30_counters_are_per_inspection_and_limit_pass_never_scraps (test_retest.RetestProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 215, in test_t30_counters_are_per_inspection_and_limit_pass_never_scraps
    self.request()
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 116, in request
    return self.accept("RETEST_REQUEST", inspection=inspection, rule_id="RULE_RETEST")
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 91, in accept
    self.assertTrue(decision.accepted, decision)
AssertionError: False is not true : Decision(seq='8', product_id='a', input_text='RETEST_REQUEST LEAK', rule_id='RULE_PRESERVE', accepted=False, reason='INSPECT 이외의 inspection과 result는 빈칸이어야 함', state='보류')

----------------------------------------------------------------------
Ran 13 tests in 1.094s

FAILED (failures=9)
```
종료 코드: 1

명령: `py -m unittest discover -s tests`

```text
...................................................
----------------------------------------------------------------------
Ran 51 tests in 5.177s

OK
```
종료 코드: 0

## ③ 모드 전환과 보고서 (T32)

- 모든 모델에 retest_limit이 있을 때만 products에 history를 더하고, 6개 규칙 뒤 RULE_RETEST를 붙인다. rows 형식과 1단계 4열·6개 집계·터미널 헤더는 유지한다.
- 실제 CLI를 통한 history 정확 문자열, 요청 없는 입력 거절 집계, 같은 폴더 반복 및 별도 폴더 반복의 stdout·stderr·CSV 3종 바이트 비교 테스트를 추가. 구현 전 RULE_RETEST 집계 키 누락으로 실패, 구현 후 전체 53개 통과.

명령: `py -m unittest discover -s tests -p test_retest.py`

```text
.............F.
======================================================================
FAIL: test_t32_cli_history_seven_rules_and_byte_reproducibility (test_retest.RetestReportTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_retest.py", line 281, in test_t32_cli_history_seven_rules_and_byte_reproducibility
    self.assertEqual(first.returncode, 0, first.stderr)
AssertionError: 1 != 0 : b'Traceback (most recent call last):\r\n  File "C:\\Users\\PC\\anaconda3\\lib\\runpy.py", line 197, in _run_module_as_main\r\n    return _run_code(code, main_globals, None,\r\n  File "C:\\Users\\PC\\anaconda3\\lib\\runpy.py", line 87, in _run_code\r\n    exec(code, run_globals)\r\n  File "C:\\Users\\PC\\Documents\\ChatGPT\\\xec\x97\x90\xec\x8a\xa4\xec\x97\x98 KDT AI \xea\xb5\x90\xec\x9c\xa1 \xeb\xb6\x80\xed\x8a\xb8\xec\xba\xa0\xed\x94\x84\\project\\src\\main.py", line 121, in <module>\r\n    raise SystemExit(main())\r\n  File "C:\\Users\\PC\\Documents\\ChatGPT\\\xec\x97\x90\xec\x8a\xa4\xec\x97\x98 KDT AI \xea\xb5\x90\xec\x9c\xa1 \xeb\xb6\x80\xed\x8a\xb8\xec\xba\xa0\xed\x94\x84\\project\\src\\main.py", line 110, in main\r\n    return run_recipe(args.input_csv, args.recipe, parser)\r\n  File "C:\\Users\\PC\\Documents\\ChatGPT\\\xec\x97\x90\xec\x8a\xa4\xec\x97\x98 KDT AI \xea\xb5\x90\xec\x9c\xa1 \xeb\xb6\x80\xed\x8a\xb8\xec\xba\xa0\xed\x94\x84\\project\\src\\main.py", line 96, in run_recipe\r\n    reports = build_recipe_reports(read_events(input_csv, RECIPE_INPUT_COLUMNS), book.models)\r\n  File "C:\\Users\\PC\\Documents\\ChatGPT\\\xec\x97\x90\xec\x8a\xa4\xec\x97\x98 KDT AI \xea\xb5\x90\xec\x9c\xa1 \xeb\xb6\x80\xed\x8a\xb8\xec\xba\xa0\xed\x94\x84\\project\\src\\recipe_reports.py", line 23, in build_recipe_reports\r\n    counts[decision.rule_id] += 1\r\nKeyError: \'RULE_RETEST\'\r\n'

----------------------------------------------------------------------
Ran 15 tests in 1.277s

FAILED (failures=1)
```
종료 코드: 1

명령: `py -m unittest discover -s tests`

```text
.....................................................
----------------------------------------------------------------------
Ran 53 tests in 6.019s

OK
```
종료 코드: 0

## ④ 고정 샘플 데이터·보고서 (T23–T30, T32)

- T23–T30을 제품별로 담은 고정 입력 102행과 CSV 보고서 3종 생성. 허용 90·거절 12, 등록 제품 12개(미등록 요청 제품은 생성하지 않음).
- 예상 거절 집계: RULE_RECIPE 1 / RULE_SEQ 0 / RULE_INSP_PRE 0 / RULE_NOT_DONE 0 / RULE_FAIL_HOLD 1 / RULE_PRESERVE 4 / RULE_RETEST 6. 실제 결과와 일치.
- 순수 데이터·생성 산출물 단계여서 테스트 선실패 관측은 생략. 저장된 보고서와 별도 디렉터리에서 재생성한 보고서의 바이트 비교, 예상 최종 상태·이유·이력·집계 테스트를 추가했다. 전체 54개 통과.

명령: `py -m src.main data/sample_events_retest.csv --recipe recipes/lamp_models_retest.json`

```text
레시피: recipes/lamp_models_retest.json | SHA-256: 438229b58c9e
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T23 | REGISTER | RULE_RECIPE | 허용 |  | 등록
2 | T23 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
3 | T23 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
4 | T23 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
5 | T23 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
6 | T23 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
7 | T23 | P4 | RULE_FAIL_HOLD | 거절 | FAIL로 보류 중인 제품 | 보류
8 | T24 | REGISTER | RULE_RECIPE | 허용 |  | 등록
9 | T24 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
10 | T24 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
11 | T24 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
12 | T24 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
13 | T24 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
14 | T24 | INSPECT LEAK PASS | RULE_RETEST | 허용 |  | 공정 진행 중(P3 완료)
15 | T24 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
16 | T24 | P5 | RULE_SEQ | 허용 |  | 검사 대기
17 | T24 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
18 | T24 | INSPECT FINAL PASS | RULE_FAIL_HOLD | 허용 |  | 레시피 모의 흐름 완료
19 | T25 | REGISTER | RULE_RECIPE | 허용 |  | 등록
20 | T25 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
21 | T25 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
22 | T25 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
23 | T25 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
24 | T25 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
25 | T26 | REGISTER | RULE_RECIPE | 허용 |  | 등록
26 | T26 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
27 | T26 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
28 | T26 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
29 | T26 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
30 | T26 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
31 | T26 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 보류
32 | T26 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
33 | T26 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
34 | T26 | INSPECT LEAK PASS | RULE_RETEST | 허용 |  | 공정 진행 중(P3 완료)
35 | T27 | REGISTER | RULE_RECIPE | 허용 |  | 등록
36 | T27 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
37 | T27 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
38 | T27 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
39 | T27 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
40 | T27 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
41 | T27 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 보류
42 | T27 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
43 | T27 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 폐기
44 | T27 | P4 | RULE_RETEST | 거절 | 폐기된 제품 | 폐기
45 | T27 | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 폐기된 제품 | 폐기
46 | T27 | INSPECT LIGHT PASS | RULE_RETEST | 거절 | 폐기된 제품 | 폐기
47 | T28_NO_RESULT | REGISTER | RULE_RECIPE | 허용 |  | 등록
48 | T28_NO_RESULT | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
49 | T28_NO_RESULT | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
50 | T28_NO_RESULT | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
51 | T28_NO_RESULT | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 미해결 FAIL 없음 | 공정 진행 중(P3 완료)
52 | T28_PASS | REGISTER | RULE_RECIPE | 허용 |  | 등록
53 | T28_PASS | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
54 | T28_PASS | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
55 | T28_PASS | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
56 | T28_PASS | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
57 | T28_PASS | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 미해결 FAIL 없음 | 공정 진행 중(P3 완료)
58 | T28_OPEN | REGISTER | RULE_RECIPE | 허용 |  | 등록
59 | T28_OPEN | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
60 | T28_OPEN | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
61 | T28_OPEN | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
62 | T28_OPEN | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
63 | T28_OPEN | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
64 | T28_OPEN | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 이미 열린 재검사 요청 | 보류
65 | T28_MODEL_B | REGISTER | RULE_RECIPE | 허용 |  | 등록
66 | T28_MODEL_B | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
67 | T28_MODEL_B | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
68 | T28_MODEL_B | RETEST_REQUEST FINAL | RULE_RECIPE | 거절 | 제품 레시피에 없는 검사 FINAL | 공정 진행 중(P2 완료)
69 | T28_UNREGISTERED | RETEST_REQUEST LEAK | RULE_PRESERVE | 거절 | 미등록 제품 | 미등록
70 | T28_FORMAT | REGISTER | RULE_RECIPE | 허용 |  | 등록
71 | T28_FORMAT | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
72 | T28_FORMAT | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
73 | T28_FORMAT | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
74 | T28_FORMAT | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
75 | T28_FORMAT | RETEST_REQUEST LEAK PASS | RULE_PRESERVE | 거절 | RETEST_REQUEST의 result는 빈칸이어야 함 | 보류
76 | T29 | REGISTER | RULE_RECIPE | 허용 |  | 등록
77 | T29 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
78 | T29 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
79 | T29 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
80 | T29 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
81 | T29 | P5 | RULE_SEQ | 허용 |  | 검사 대기
82 | T29 | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
83 | T29 | INSPECT LIGHT FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
84 | T29 | INSPECT FINAL FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
85 | T29 | RETEST_REQUEST LIGHT | RULE_RETEST | 허용 |  | 보류
86 | T29 | INSPECT LIGHT PASS | RULE_RETEST | 허용 |  | 보류
87 | T29 | RETEST_REQUEST FINAL | RULE_RETEST | 허용 |  | 보류
88 | T29 | INSPECT FINAL PASS | RULE_RETEST | 허용 |  | 레시피 모의 흐름 완료
89 | T30 | REGISTER | RULE_RECIPE | 허용 |  | 등록
90 | T30 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
91 | T30 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
92 | T30 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
93 | T30 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
94 | T30 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
95 | T30 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 보류
96 | T30 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
97 | T30 | INSPECT LEAK PASS | RULE_RETEST | 허용 |  | 공정 진행 중(P3 완료)
98 | T30 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
99 | T30 | P5 | RULE_SEQ | 허용 |  | 검사 대기
100 | T30 | INSPECT LIGHT FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
101 | T30 | RETEST_REQUEST LIGHT | RULE_RETEST | 허용 |  | 보류
102 | T30 | INSPECT LIGHT PASS | RULE_RETEST | 허용 |  | 검사 대기

[제품별 최종 상태]
product_id | model | 최종 상태 | 미완료 이유 | history
T23 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL(재검사 요청됨); LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@5 → 요청@6
T24 | A | 레시피 모의 흐름 완료 |  | LEAK: FAIL@12 → 요청@13 → PASS@14(재검사 1); LIGHT: PASS@17; FINAL: PASS@18
T25 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@23
T26 | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@29 → 요청@30 → FAIL@31(재검사 1) → 요청@33 → PASS@34(재검사 2)
T27 | A | 폐기 | LEAK 재검사 한도 2회 초과 FAIL로 폐기 | LEAK: FAIL@39 → 요청@40 → FAIL@41(재검사 1) → 요청@42 → FAIL@43(재검사 2)
T28_NO_RESULT | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시 | 
T28_PASS | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: PASS@56
T28_OPEN | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL(재검사 요청됨); LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@62 → 요청@63
T28_MODEL_B | B | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; LEAK 미실시; LIGHT 미실시 | 
T28_FORMAT | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@74
T29 | A | 레시피 모의 흐름 완료 |  | LEAK: PASS@82; LIGHT: FAIL@83 → 요청@85 → PASS@86(재검사 1); FINAL: FAIL@84 → 요청@87 → PASS@88(재검사 1)
T30 | A | 검사 대기 | FINAL 미실시 | LEAK: FAIL@93 → 요청@94 → FAIL@95(재검사 1) → 요청@96 → PASS@97(재검사 2); LIGHT: FAIL@100 → 요청@101 → PASS@102(재검사 1)

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_RECIPE | 1
RULE_SEQ | 0
RULE_INSP_PRE | 0
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 1
RULE_PRESERVE | 4
RULE_RETEST | 6

저장 파일:
reports/sample_events_retest_rows.csv
reports/sample_events_retest_products.csv
reports/sample_events_retest_rejections.csv
```
종료 코드: 0

명령: `py -m unittest discover -s tests`

```text
......................................................
----------------------------------------------------------------------
Ran 54 tests in 5.704s

OK
```
종료 코드: 0

명령: `py -m unittest discover -s tests`

```text
......................................................
----------------------------------------------------------------------
Ran 54 tests in 5.396s

OK
```
종료 코드: 0

## ⑤ README (T23–T32)

- 재검사 모드 실행법, 6열 입력 예, 요청/결과 규칙 표, 검사별 상한·폐기 시점과 이유, 상태 우선순위, history와 7개 규칙 보고서, 샘플 수치, 가상 규칙 경계와 제외 범위를 추가했다. 1단계 설명은 보존했다.
- 문서 단계로 새 테스트는 추가하지 않고 위 전체 54개 테스트를 실행했다. 예시 seq·history, 고정 샘플 102/90/12 및 보고서 집계와 문서를 대조했다.
- ce-simplify-code mode:pipeline: 재사용·품질·효율·테스트 가치 관점 독립 검토 완료. 적용 0, 미해결 지적 0. proof-test인 tests/test_retest.py는 유지. 별도 lint/typecheck 설정은 없고 테스트로 검증했다. 설명 주석의 신규 변경은 없어 주석 리뷰는 대상 없음.

명령: `py -m unittest discover -s tests -p test_rules.py`

```text
............
----------------------------------------------------------------------
Ran 12 tests in 0.309s

OK
```
종료 코드: 0

명령: `py -m unittest discover -s tests -p test_recipe.py`

```text
..........................
----------------------------------------------------------------------
Ran 26 tests in 3.452s

OK
```
종료 코드: 0

명령: `py -m unittest discover -s tests -p test_retest.py`

```text
................
----------------------------------------------------------------------
Ran 16 tests in 1.722s

OK
```
종료 코드: 0

명령: `py -m src.main data/sample_events.csv`

```text
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T1 | REGISTER | RULE_SEQ | 허용 |  | 등록
2 | T1 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
3 | T1 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
4 | T1 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
5 | T1 | INSPECT LEAK PASS | RULE_FAIL_HOLD | 허용 |  | 선택한 두 검사까지의 모의 흐름 완료
6 | T2 | REGISTER | RULE_SEQ | 허용 |  | 등록
7 | T2 | MAIN_ASSEMBLY | RULE_SEQ | 거절 | PRE_ASSEMBLY 미완료 | 등록
8 | T3 | REGISTER | RULE_SEQ | 허용 |  | 등록
9 | T3 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
10 | T3 | INSPECT LIGHT PASS | RULE_INSP_PRE | 거절 | MAIN_ASSEMBLY 미완료 | 예비 조립
11 | T4 | REGISTER | RULE_SEQ | 허용 |  | 등록
12 | T4 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
13 | T4 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
14 | T4 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
15 | T5 | REGISTER | RULE_SEQ | 허용 |  | 등록
16 | T5 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
17 | T5 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
18 | T5 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
19 | T5 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
20 | T6 | REGISTER | RULE_SEQ | 허용 |  | 등록
21 | T6 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
22 | T6 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
23 | T6 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
24 | T6 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
25 | T6 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
26 | T7 | REGISTER | RULE_SEQ | 허용 |  | 등록
27 | T7 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
28 | T7 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
29 | T7 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
30 | T7 | INSPECT LEAK PASS | RULE_FAIL_HOLD | 허용 |  | 선택한 두 검사까지의 모의 흐름 완료
31 | T7 | INSPECT LIGHT FAIL | RULE_PRESERVE | 거절 | LIGHT 결과 이미 존재 | 선택한 두 검사까지의 모의 흐름 완료
32 | T8 | REGISTER | RULE_SEQ | 허용 |  | 등록
33 | T8 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
34 | T8 | PRE_ASSEMBLY | RULE_PRESERVE | 거절 | 중복 조립 이벤트 | 예비 조립
35 | T9_UNREGISTERED | MAIN_ASSEMBLY | RULE_PRESERVE | 거절 | 미등록 제품 | 미등록
36 | T9 | REGISTER | RULE_SEQ | 허용 |  | 등록
37 | T9 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
38 | T9 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
39 | T9 | INSPECT LIGHT OK | RULE_PRESERVE | 거절 | 잘못된 result (PASS 또는 FAIL 필요) | 검사 대기

[제품별 최종 상태]
product_id | 최종 상태 | 미완료 이유
T1 | 선택한 두 검사까지의 모의 흐름 완료 | 
T2 | 등록 | PRE_ASSEMBLY 미완료; MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T3 | 예비 조립 | MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T4 | 검사 대기 | LEAK 미실시
T5 | 보류 | LEAK FAIL
T6 | 보류 | LEAK FAIL
T7 | 선택한 두 검사까지의 모의 흐름 완료 | 
T8 | 예비 조립 | MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T9 | 검사 대기 | LIGHT 미실시; LEAK 미실시

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_SEQ | 1
RULE_INSP_PRE | 1
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 0
RULE_PRESERVE | 5

저장 파일:
reports/sample_events_rows.csv
reports/sample_events_products.csv
reports/sample_events_rejections.csv
```
종료 코드: 0

명령: `py -m src.main data/sample_events_v2.csv --recipe recipes/lamp_models.json`

```text
레시피: recipes/lamp_models.json | SHA-256: d7a8976ee178
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T11 | REGISTER | RULE_RECIPE | 허용 |  | 등록
2 | T11 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
3 | T11 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
4 | T11 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
5 | T11 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
6 | T11 | P5 | RULE_SEQ | 허용 |  | 검사 대기
7 | T11 | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
8 | T11 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
9 | T11 | INSPECT FINAL PASS | RULE_FAIL_HOLD | 허용 |  | 레시피 모의 흐름 완료
10 | T12_A | REGISTER | RULE_RECIPE | 허용 |  | 등록
11 | T12_B | REGISTER | RULE_RECIPE | 허용 |  | 등록
12 | T12_A | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
13 | T12_B | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
14 | T12_A | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
15 | T12_B | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
16 | T12_A | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
17 | T12_B | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
18 | T12_A | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
19 | T12_B | P4 | RULE_SEQ | 허용 |  | 검사 대기
20 | T12_B | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
21 | T12_B | INSPECT LIGHT PASS | RULE_FAIL_HOLD | 허용 |  | 레시피 모의 흐름 완료
22 | T13 | REGISTER | RULE_RECIPE | 허용 |  | 등록
23 | T13 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
24 | T13 | P3 | RULE_SEQ | 거절 | P2 미완료 | 공정 진행 중(P1 완료)
25 | T13 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
26 | T14_LEAK | REGISTER | RULE_RECIPE | 허용 |  | 등록
27 | T14_LEAK | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
28 | T14_LEAK | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
29 | T14_LEAK | INSPECT LEAK PASS | RULE_INSP_PRE | 거절 | P3 미완료 | 공정 진행 중(P2 완료)
30 | T14_LIGHT | REGISTER | RULE_RECIPE | 허용 |  | 등록
31 | T14_LIGHT | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
32 | T14_LIGHT | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
33 | T14_LIGHT | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
34 | T14_LIGHT | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
35 | T14_LIGHT | INSPECT LIGHT PASS | RULE_INSP_PRE | 거절 | P5 미완료 | 공정 진행 중(P4 완료)
36 | T15 | REGISTER | RULE_RECIPE | 허용 |  | 등록
37 | T15 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
38 | T15 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
39 | T15 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
40 | T15 | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
41 | T15 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
42 | T15 | P5 | RULE_SEQ | 허용 |  | 검사 대기
43 | T15 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
44 | T16 | REGISTER | RULE_RECIPE | 허용 |  | 등록
45 | T16 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
46 | T16 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
47 | T16 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
48 | T16 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
49 | T16 | P4 | RULE_FAIL_HOLD | 거절 | FAIL로 보류 중인 제품 | 보류
50 | T16 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
51 | T16B | REGISTER | RULE_RECIPE | 허용 |  | 등록
52 | T16B | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
53 | T16B | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
54 | T16B | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
55 | T16B | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
56 | T16B | P5 | RULE_SEQ | 허용 |  | 검사 대기
57 | T16B | INSPECT LIGHT FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
58 | T16B | INSPECT FINAL PASS | RULE_FAIL_HOLD | 허용 |  | 보류
59 | T17_C | REGISTER | RULE_RECIPE | 거절 | model이 비어 있거나 레시피에 없는 모델 | 미등록
60 | T17_A | REGISTER | RULE_RECIPE | 허용 |  | 등록
61 | T17_A | P6 | RULE_RECIPE | 거절 | 제품 레시피에 없는 공정 P6 | 등록
62 | T17_B | REGISTER | RULE_RECIPE | 허용 |  | 등록
63 | T17_B | INSPECT FINAL PASS | RULE_RECIPE | 거절 | 제품 레시피에 없는 검사 FINAL | 등록
64 | T19 | REGISTER | RULE_RECIPE | 허용 |  | 등록
65 | T19 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
66 | T19 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
67 | T19 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
68 | T19 | P4 | RULE_SEQ | 허용 |  | 검사 대기
69 | T19 | P5 | RULE_RECIPE | 거절 | 제품 레시피에 없는 공정 P5 | 검사 대기
70 | T20_MISSING | REGISTER | RULE_RECIPE | 거절 | model이 비어 있거나 레시피에 없는 모델 | 미등록
71 | T20 | REGISTER | RULE_RECIPE | 허용 |  | 등록
72 | T20 | P1 | RULE_PRESERVE | 거절 | REGISTER 이외의 model은 빈칸이어야 함 | 등록
73 | T22 | REGISTER | RULE_RECIPE | 허용 |  | 등록
74 | T22 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
75 | T22 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
76 | T22 | REGISTER | RULE_PRESERVE | 거절 | 이미 등록된 제품 | 공정 진행 중(P2 완료)

[제품별 최종 상태]
product_id | model | 최종 상태 | 미완료 이유
T11 | A | 레시피 모의 흐름 완료 | 
T12_A | A | 공정 진행 중(P4 완료) | P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T12_B | B | 레시피 모의 흐름 완료 | 
T13 | A | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T14_LEAK | A | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T14_LIGHT | A | 공정 진행 중(P4 완료) | P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T15 | A | 검사 대기 | FINAL 미실시
T16 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시
T16B | A | 보류 | LEAK 미실시; LIGHT FAIL
T17_A | A | 등록 | P1 미완료; P2 미완료; P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T17_B | B | 등록 | P1 미완료; P2 미완료; P3 미완료; P4 미완료; LEAK 미실시; LIGHT 미실시
T19 | B | 검사 대기 | LEAK 미실시; LIGHT 미실시
T20 | A | 등록 | P1 미완료; P2 미완료; P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T22 | A | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_RECIPE | 5
RULE_SEQ | 1
RULE_INSP_PRE | 2
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 1
RULE_PRESERVE | 3

저장 파일:
reports/sample_events_v2_rows.csv
reports/sample_events_v2_products.csv
reports/sample_events_v2_rejections.csv
```
종료 코드: 0

## 최종 보존 검증

```text
reports/sample_events_products.csv: SHA-256 unchanged=True
reports/sample_events_rejections.csv: SHA-256 unchanged=True
reports/sample_events_rows.csv: SHA-256 unchanged=True
reports/sample_events_v2_products.csv: SHA-256 unchanged=True
reports/sample_events_v2_rejections.csv: SHA-256 unchanged=True
reports/sample_events_v2_rows.csv: SHA-256 unchanged=True
src/rules.py: SHA-256 unchanged=True
tests/test_rules.py: SHA-256 unchanged=True
tests/test_recipe.py: SHA-256 unchanged=True
handoff/tasks.md: SHA-256 unchanged=True
handoff/decisions.md: SHA-256 unchanged=True
CLAUDE.md: SHA-256 unchanged=True
handoff/reviews/.gitkeep: SHA-256 unchanged=True
handoff/reviews/001-review.md: SHA-256 unchanged=True
handoff/reviews/002-review.md: SHA-256 unchanged=True
.claude/settings.json: SHA-256 unchanged=True
git diff 230f437 -- <protected paths>: no output
git diff --check 230f437 -- src tests recipes data reports README.md: PASS
```

## 최종 대조 보완 (T29)

- 주 에이전트의 기대표 대조에서 새 T29 테스트·샘플의 LEAK PASS가 P5 뒤에 있음을 발견했다. 기대표의 P3 → LEAK PASS → P4 → P5 순서로 새 테스트와 샘플만 정정하고 보고서 3종을 재생성했다. 기대표·기존 테스트·판정 코드는 변경하지 않았다. 이전 샘플 출력 원문은 당시 실행 기록으로 보존하며, 아래가 최종 샘플 출력이다.
- 수정 후에도 102행·허용 90·거절 12 및 제품 상태/거절 집계는 같고, T29 LEAK history의 seq는 82에서 80으로 바뀐다. 전체 54개 테스트 통과.

명령: `py -m src.main data/sample_events_retest.csv --recipe recipes/lamp_models_retest.json`

```text
레시피: recipes/lamp_models_retest.json | SHA-256: 438229b58c9e
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T23 | REGISTER | RULE_RECIPE | 허용 |  | 등록
2 | T23 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
3 | T23 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
4 | T23 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
5 | T23 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
6 | T23 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
7 | T23 | P4 | RULE_FAIL_HOLD | 거절 | FAIL로 보류 중인 제품 | 보류
8 | T24 | REGISTER | RULE_RECIPE | 허용 |  | 등록
9 | T24 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
10 | T24 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
11 | T24 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
12 | T24 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
13 | T24 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
14 | T24 | INSPECT LEAK PASS | RULE_RETEST | 허용 |  | 공정 진행 중(P3 완료)
15 | T24 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
16 | T24 | P5 | RULE_SEQ | 허용 |  | 검사 대기
17 | T24 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
18 | T24 | INSPECT FINAL PASS | RULE_FAIL_HOLD | 허용 |  | 레시피 모의 흐름 완료
19 | T25 | REGISTER | RULE_RECIPE | 허용 |  | 등록
20 | T25 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
21 | T25 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
22 | T25 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
23 | T25 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
24 | T25 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
25 | T26 | REGISTER | RULE_RECIPE | 허용 |  | 등록
26 | T26 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
27 | T26 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
28 | T26 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
29 | T26 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
30 | T26 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
31 | T26 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 보류
32 | T26 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
33 | T26 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
34 | T26 | INSPECT LEAK PASS | RULE_RETEST | 허용 |  | 공정 진행 중(P3 완료)
35 | T27 | REGISTER | RULE_RECIPE | 허용 |  | 등록
36 | T27 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
37 | T27 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
38 | T27 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
39 | T27 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
40 | T27 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
41 | T27 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 보류
42 | T27 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
43 | T27 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 폐기
44 | T27 | P4 | RULE_RETEST | 거절 | 폐기된 제품 | 폐기
45 | T27 | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 폐기된 제품 | 폐기
46 | T27 | INSPECT LIGHT PASS | RULE_RETEST | 거절 | 폐기된 제품 | 폐기
47 | T28_NO_RESULT | REGISTER | RULE_RECIPE | 허용 |  | 등록
48 | T28_NO_RESULT | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
49 | T28_NO_RESULT | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
50 | T28_NO_RESULT | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
51 | T28_NO_RESULT | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 미해결 FAIL 없음 | 공정 진행 중(P3 완료)
52 | T28_PASS | REGISTER | RULE_RECIPE | 허용 |  | 등록
53 | T28_PASS | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
54 | T28_PASS | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
55 | T28_PASS | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
56 | T28_PASS | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
57 | T28_PASS | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 미해결 FAIL 없음 | 공정 진행 중(P3 완료)
58 | T28_OPEN | REGISTER | RULE_RECIPE | 허용 |  | 등록
59 | T28_OPEN | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
60 | T28_OPEN | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
61 | T28_OPEN | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
62 | T28_OPEN | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
63 | T28_OPEN | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
64 | T28_OPEN | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 이미 열린 재검사 요청 | 보류
65 | T28_MODEL_B | REGISTER | RULE_RECIPE | 허용 |  | 등록
66 | T28_MODEL_B | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
67 | T28_MODEL_B | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
68 | T28_MODEL_B | RETEST_REQUEST FINAL | RULE_RECIPE | 거절 | 제품 레시피에 없는 검사 FINAL | 공정 진행 중(P2 완료)
69 | T28_UNREGISTERED | RETEST_REQUEST LEAK | RULE_PRESERVE | 거절 | 미등록 제품 | 미등록
70 | T28_FORMAT | REGISTER | RULE_RECIPE | 허용 |  | 등록
71 | T28_FORMAT | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
72 | T28_FORMAT | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
73 | T28_FORMAT | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
74 | T28_FORMAT | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
75 | T28_FORMAT | RETEST_REQUEST LEAK PASS | RULE_PRESERVE | 거절 | RETEST_REQUEST의 result는 빈칸이어야 함 | 보류
76 | T29 | REGISTER | RULE_RECIPE | 허용 |  | 등록
77 | T29 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
78 | T29 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
79 | T29 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
80 | T29 | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
81 | T29 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
82 | T29 | P5 | RULE_SEQ | 허용 |  | 검사 대기
83 | T29 | INSPECT LIGHT FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
84 | T29 | INSPECT FINAL FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
85 | T29 | RETEST_REQUEST LIGHT | RULE_RETEST | 허용 |  | 보류
86 | T29 | INSPECT LIGHT PASS | RULE_RETEST | 허용 |  | 보류
87 | T29 | RETEST_REQUEST FINAL | RULE_RETEST | 허용 |  | 보류
88 | T29 | INSPECT FINAL PASS | RULE_RETEST | 허용 |  | 레시피 모의 흐름 완료
89 | T30 | REGISTER | RULE_RECIPE | 허용 |  | 등록
90 | T30 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
91 | T30 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
92 | T30 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
93 | T30 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
94 | T30 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
95 | T30 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 보류
96 | T30 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
97 | T30 | INSPECT LEAK PASS | RULE_RETEST | 허용 |  | 공정 진행 중(P3 완료)
98 | T30 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
99 | T30 | P5 | RULE_SEQ | 허용 |  | 검사 대기
100 | T30 | INSPECT LIGHT FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
101 | T30 | RETEST_REQUEST LIGHT | RULE_RETEST | 허용 |  | 보류
102 | T30 | INSPECT LIGHT PASS | RULE_RETEST | 허용 |  | 검사 대기

[제품별 최종 상태]
product_id | model | 최종 상태 | 미완료 이유 | history
T23 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL(재검사 요청됨); LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@5 → 요청@6
T24 | A | 레시피 모의 흐름 완료 |  | LEAK: FAIL@12 → 요청@13 → PASS@14(재검사 1); LIGHT: PASS@17; FINAL: PASS@18
T25 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@23
T26 | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@29 → 요청@30 → FAIL@31(재검사 1) → 요청@33 → PASS@34(재검사 2)
T27 | A | 폐기 | LEAK 재검사 한도 2회 초과 FAIL로 폐기 | LEAK: FAIL@39 → 요청@40 → FAIL@41(재검사 1) → 요청@42 → FAIL@43(재검사 2)
T28_NO_RESULT | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시 | 
T28_PASS | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: PASS@56
T28_OPEN | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL(재검사 요청됨); LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@62 → 요청@63
T28_MODEL_B | B | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; LEAK 미실시; LIGHT 미실시 | 
T28_FORMAT | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@74
T29 | A | 레시피 모의 흐름 완료 |  | LEAK: PASS@80; LIGHT: FAIL@83 → 요청@85 → PASS@86(재검사 1); FINAL: FAIL@84 → 요청@87 → PASS@88(재검사 1)
T30 | A | 검사 대기 | FINAL 미실시 | LEAK: FAIL@93 → 요청@94 → FAIL@95(재검사 1) → 요청@96 → PASS@97(재검사 2); LIGHT: FAIL@100 → 요청@101 → PASS@102(재검사 1)

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_RECIPE | 1
RULE_SEQ | 0
RULE_INSP_PRE | 0
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 1
RULE_PRESERVE | 4
RULE_RETEST | 6

저장 파일:
reports/sample_events_retest_rows.csv
reports/sample_events_retest_products.csv
reports/sample_events_retest_rejections.csv
```
종료 코드: 0

명령: `py -m unittest discover -s tests`

```text
......................................................
----------------------------------------------------------------------
Ran 54 tests in 5.516s

OK
```
종료 코드: 0

## v2 2단계 완료 보고 (T23–T32)

### 결과와 검증

- 재검사 레시피 검증, 검사별 요청·재검사·PASS 복구·상한 FAIL 폐기, 원래 결과 이력 보존, history 열·7개 규칙 집계, 고정 샘플·보고서·README를 구현했다. main에서 아래 작업 커밋을 순서대로 만들었으며, 이 완료 보고도 별도 커밋한다. push·원격 설정 변경·패키지 설치·외부 모델 코드 전송은 하지 않았다.
- 전체 테스트: 착수 전 38개 → ① 41개 → ② 51개 → ③ 53개 → ④·⑤ 및 최종 T29 보완 뒤 54개 통과. 최종 구분 실행은 v1 12개, 1단계 26개, 2단계 16개 통과. 실제 명령·출력 원문은 각 절과 위 최종 실행 기록에 있다.
- `py -m src.main data/sample_events.csv`, `py -m src.main data/sample_events_v2.csv --recipe recipes/lamp_models.json` 재실행 후 기존 보고서 6개의 SHA-256이 착수 전 체크아웃 파일과 모두 동일했다. Git 줄바꿈 정규화를 거치지 않은 비교다.
- `py -m src.main data/sample_events_retest.csv --recipe recipes/lamp_models_retest.json`: 102행, 허용 90·거절 12, 제품 12개. 최신 원문은 「최종 대조 보완(T29)」 뒤에 있다. 새 보고서 3종은 임시 폴더 재생성과 바이트 동일하며, T32는 같은 폴더와 별도 폴더의 반복 stdout·stderr·CSV 3종 바이트 동일을 검증했다.
- 보호 파일(`src/rules.py`, `tests/test_rules.py`, `tests/test_recipe.py`, `tasks.md`, `decisions.md`, `reviews/`, `CLAUDE.md`, `.claude/`)은 착수 전 파일 바이트와 같고 해당 경로의 `git diff 230f437` 출력도 없다. 기존 기대표·테스트를 구현에 맞춰 바꾸지 않았다. 기존 gpt-log 본문도 기준 커밋 대비 변경 없이 이번 기록만 추가했다.

### 기대표 대조

| ID | 최종 실제 결과 |
| --- | --- |
| T23 | 요청 허용 뒤 보류 유지, 횟수 미증가, P4 RULE_FAIL_HOLD 거절 |
| T24 | 요청 뒤 PASS 허용, 보류 해소·공정 재개·완료, 최초 FAIL과 요청·재검사 seq 이력 보존 |
| T25 | 요청 없는 결과 RULE_PRESERVE 거절, 전체 상태 불변 |
| T26 | FAIL 재검사로 요청 소진·1회 증가, 무요청 결과 거절, 새 요청 뒤 PASS는 재검사 2로 허용 |
| T27 | 재검사 2 FAIL 행 허용과 동시에 폐기, 뒤 공정·요청·다른 검사 RULE_RETEST 거절, 전체 상태 불변 |
| T28 | 미실시/PASS/중복 요청 RULE_RETEST, 다른 모델 검사 RULE_RECIPE, 미등록·잘못된 요청 형식 RULE_PRESERVE. 모두 전체 상태 불변 |
| T29 | P3 뒤 LEAK PASS, P4~P5 진행. LIGHT PASS 뒤 FINAL FAIL 보류 유지, FINAL PASS 뒤 완료 |
| T30 | LEAK 재검사 2회 PASS 뒤에도 LIGHT 재검사 1회 별도 허용, 폐기되지 않음 |
| T31 | 0·문자열·bool·일부 모델 설정·예약 공정 오류는 위치 표시·코드 3·이벤트 미처리·보고서 없음. 복수 오류 수집 및 1/5 경계도 확인 |
| T32 | 1단계 정상 형식 요청 RULE_RECIPE 거절, 재검사 모드 stdout·CSV 3종 반복 바이트 동일 |

최종 기대 결과의 불일치는 없다. T29의 새 테스트·샘플 순서 차이는 최종 대조에서 발견해 기대표 순서로 수정한 기록을 위에 남겼다. 기존 1단계의 요청 거절 규칙과 T32 설명의 충돌은 다음 명세 이견으로 공개한다.

### 해석·가정과 명세 이견

- **명세 이견(T32)**: 기존 구현은 inspection이 채워진 요청을 RULE_PRESERVE로 거절했으므로 “1단계 동작 그대로 RULE_RECIPE”라는 설명과 충돌한다. 이번 명시 기대인 RULE_RECIPE를 적용하는 좁은 변경을 했으며 기존 T11–T22와 샘플 출력은 모두 보존했다.
- **명세 이견(결정 근거)**: “미해결 FAIL 최대 1개”라는 과거 결정 근거와 T29의 복수 FAIL이 충돌한다. 현행 기대표에 따라 제품·검사별 요청과 횟수를 독립 관리한다.
- tasks.md의 초안 표시는 사용자 구현 요청·착수 승인에 따라 실행 권한이 있는 것으로 해석했다. 사용자 문서는 그대로 두었다.
- history는 허용된 시도만 기록하고 그룹은 레시피 순서, 그룹 내는 물리적 입력 순서다. seq 중복·감소를 허용하는 기존 입력 계약을 유지한다.
- “2회 초과”라는 보고서 문구는 원문 그대로 두되 폐기는 상한 2에 도달한 FAIL 행에서 발생한다. 상한에서 PASS면 폐기하지 않는다.
- 기본 파일의 상한은 두 모델 모두 2다. 검증은 명시된 1–5 정수 범위만 적용하며 모델별 상한을 일치시키는 추가 정책·새 옵션은 넣지 않았다.

### 리뷰·교훈 기록과 확인 범위

- ce-code-review focused: 주 에이전트의 정확성·요구 충족 검토와 별도 로컬 adversarial 검토 완료. 미해결 지적 0. 독립 검토는 상한 1·2·5, 동시 요청, 형식 오류 뒤 재시도, 다른 요청이 열린 제품의 폐기, 제품 격리, 상한 PASS, 기존/신규 보고서 직렬화도 확인했다. 외부 모델 검토는 실행하지 않았으며 서로 다른 모델의 교차 검증을 주장하지 않는다.
- 주 에이전트가 발견한 T29 테스트·샘플 입력 순서는 반영 완료. 리뷰 002 항목별 판단은 착수 절에 기록했으며 보류된 범위를 추가 수정하지 않았다.
- 리뷰 영수증은 저장소 밖 임시 경로 `C:/Users/PC/AppData/Local/Temp/project-retest-review-e3pg02iw/review.json`에 있으며 코드·테스트·보고서·완료 근거는 모두 저장소에 남겼다. 리뷰 보조 스크립트는 Windows shebang이 Store python3를 선택하고 기본 cp949 디코딩에 실패해 `py -3 -X utf8`로 실행했다. 제품 실행·환경 설정은 변경하지 않았다.
- ce-compound mode:non-interactive 판단: **Documentation skipped**. 핵심 판단은 코드·테스트·README 및 이 로그에 복원 가능하므로 별도 solutions 문서를 중복 생성하지 않았다. 개인 메모리는 저장하지 않았다.
- 검증 범위는 로컬 CLI·CSV와 단위/통합 테스트다. 실제 제조 설비·측정·SL 품질 기준은 이번 구현·검증 범위가 아니다.

### 작업 커밋

- `a02642d`: retest_limit 레시피 검증 (T31)
- `90351c2`: 재검사·보류 해제·폐기 판정 (T23–T30)
- `df14cb1`: history와 7개 규칙 보고서 (T32)
- `4e01653`: 고정 샘플·보고서 (T23–T30, T32)
- `5362304`: README (T23–T32)
- `b32f344`: 기대표의 중간 검사 순서로 새 T29 테스트·샘플 정정


# v2 3단계 구현 (2026-10-18, T33–T41)
## 착수·계획·회귀 기준
- 기준 커밋: `4947d12518c6b0e584204ee3d97710272e84d5b2`. 시작 브랜치 `main`, 작업 트리 깨끗함. 현행 상태 **사용자 확정** 및 decisions.md 승인 확인.
- 사용자 지정 ① T40 검증 → ② T33–T39 판정 → ③ T41 CLI·보고서 → ④ 샘플 → ⑤ README 순서로 실행·테스트·경로 한정 커밋. 확정된 기존 명세를 실행 계획으로 사용하며 별도 계획서·브랜치를 만들지 않음. Native 구현, 외부 모델·서비스 전송 없음. 관련 해결 기록: `.compound-engineering/config.yaml`, `docs/solutions/` 없음.
- 보호: rules.py·기존 테스트 3종, tasks.md·decisions.md·reviews/·CLAUDE.md·.claude/ 무수정.

명령: `py -m unittest discover -s tests`

```text
......................................................
----------------------------------------------------------------------
Ran 54 tests in 5.869s

OK
```
종료 코드: 0

명령(저장소 밖 임시 폴더, PYTHONPATH=저장소): `py -m src.main C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\data\sample_events.csv`

```text
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T1 | REGISTER | RULE_SEQ | 허용 |  | 등록
2 | T1 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
3 | T1 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
4 | T1 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
5 | T1 | INSPECT LEAK PASS | RULE_FAIL_HOLD | 허용 |  | 선택한 두 검사까지의 모의 흐름 완료
6 | T2 | REGISTER | RULE_SEQ | 허용 |  | 등록
7 | T2 | MAIN_ASSEMBLY | RULE_SEQ | 거절 | PRE_ASSEMBLY 미완료 | 등록
8 | T3 | REGISTER | RULE_SEQ | 허용 |  | 등록
9 | T3 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
10 | T3 | INSPECT LIGHT PASS | RULE_INSP_PRE | 거절 | MAIN_ASSEMBLY 미완료 | 예비 조립
11 | T4 | REGISTER | RULE_SEQ | 허용 |  | 등록
12 | T4 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
13 | T4 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
14 | T4 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
15 | T5 | REGISTER | RULE_SEQ | 허용 |  | 등록
16 | T5 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
17 | T5 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
18 | T5 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
19 | T5 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
20 | T6 | REGISTER | RULE_SEQ | 허용 |  | 등록
21 | T6 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
22 | T6 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
23 | T6 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
24 | T6 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
25 | T6 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
26 | T7 | REGISTER | RULE_SEQ | 허용 |  | 등록
27 | T7 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
28 | T7 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
29 | T7 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
30 | T7 | INSPECT LEAK PASS | RULE_FAIL_HOLD | 허용 |  | 선택한 두 검사까지의 모의 흐름 완료
31 | T7 | INSPECT LIGHT FAIL | RULE_PRESERVE | 거절 | LIGHT 결과 이미 존재 | 선택한 두 검사까지의 모의 흐름 완료
32 | T8 | REGISTER | RULE_SEQ | 허용 |  | 등록
33 | T8 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
34 | T8 | PRE_ASSEMBLY | RULE_PRESERVE | 거절 | 중복 조립 이벤트 | 예비 조립
35 | T9_UNREGISTERED | MAIN_ASSEMBLY | RULE_PRESERVE | 거절 | 미등록 제품 | 미등록
36 | T9 | REGISTER | RULE_SEQ | 허용 |  | 등록
37 | T9 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
38 | T9 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
39 | T9 | INSPECT LIGHT OK | RULE_PRESERVE | 거절 | 잘못된 result (PASS 또는 FAIL 필요) | 검사 대기

[제품별 최종 상태]
product_id | 최종 상태 | 미완료 이유
T1 | 선택한 두 검사까지의 모의 흐름 완료 | 
T2 | 등록 | PRE_ASSEMBLY 미완료; MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T3 | 예비 조립 | MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T4 | 검사 대기 | LEAK 미실시
T5 | 보류 | LEAK FAIL
T6 | 보류 | LEAK FAIL
T7 | 선택한 두 검사까지의 모의 흐름 완료 | 
T8 | 예비 조립 | MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T9 | 검사 대기 | LIGHT 미실시; LEAK 미실시

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_SEQ | 1
RULE_INSP_PRE | 1
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 0
RULE_PRESERVE | 5

저장 파일:
reports/sample_events_rows.csv
reports/sample_events_products.csv
reports/sample_events_rejections.csv
```
종료 코드: 0
- `reports/sample_events_rows.csv`: 체크아웃 파일과 바이트 동일=True; SHA-256 `eb4042fb981c2ffe6611117a0ebb5636c552177a894d83a4406a607b08a952c8`
- `reports/sample_events_products.csv`: 체크아웃 파일과 바이트 동일=True; SHA-256 `e2317c768731185c28b5040aea345eb197873e76cf3459adacf25b3ea89c86e6`
- `reports/sample_events_rejections.csv`: 체크아웃 파일과 바이트 동일=True; SHA-256 `72143e7c3410b4a0ac1829f139027fcbca3fb305c7d83586cb0b2f8ac9d6c17f`

명령(저장소 밖 임시 폴더, PYTHONPATH=저장소): `py -m src.main C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\data\sample_events_v2.csv --recipe C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\recipes\lamp_models.json`

```text
레시피: C:/Users/PC/Documents/ChatGPT/에스엘 KDT AI 교육 부트캠프/project/recipes/lamp_models.json | SHA-256: d7a8976ee178
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T11 | REGISTER | RULE_RECIPE | 허용 |  | 등록
2 | T11 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
3 | T11 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
4 | T11 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
5 | T11 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
6 | T11 | P5 | RULE_SEQ | 허용 |  | 검사 대기
7 | T11 | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
8 | T11 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
9 | T11 | INSPECT FINAL PASS | RULE_FAIL_HOLD | 허용 |  | 레시피 모의 흐름 완료
10 | T12_A | REGISTER | RULE_RECIPE | 허용 |  | 등록
11 | T12_B | REGISTER | RULE_RECIPE | 허용 |  | 등록
12 | T12_A | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
13 | T12_B | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
14 | T12_A | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
15 | T12_B | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
16 | T12_A | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
17 | T12_B | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
18 | T12_A | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
19 | T12_B | P4 | RULE_SEQ | 허용 |  | 검사 대기
20 | T12_B | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
21 | T12_B | INSPECT LIGHT PASS | RULE_FAIL_HOLD | 허용 |  | 레시피 모의 흐름 완료
22 | T13 | REGISTER | RULE_RECIPE | 허용 |  | 등록
23 | T13 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
24 | T13 | P3 | RULE_SEQ | 거절 | P2 미완료 | 공정 진행 중(P1 완료)
25 | T13 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
26 | T14_LEAK | REGISTER | RULE_RECIPE | 허용 |  | 등록
27 | T14_LEAK | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
28 | T14_LEAK | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
29 | T14_LEAK | INSPECT LEAK PASS | RULE_INSP_PRE | 거절 | P3 미완료 | 공정 진행 중(P2 완료)
30 | T14_LIGHT | REGISTER | RULE_RECIPE | 허용 |  | 등록
31 | T14_LIGHT | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
32 | T14_LIGHT | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
33 | T14_LIGHT | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
34 | T14_LIGHT | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
35 | T14_LIGHT | INSPECT LIGHT PASS | RULE_INSP_PRE | 거절 | P5 미완료 | 공정 진행 중(P4 완료)
36 | T15 | REGISTER | RULE_RECIPE | 허용 |  | 등록
37 | T15 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
38 | T15 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
39 | T15 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
40 | T15 | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
41 | T15 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
42 | T15 | P5 | RULE_SEQ | 허용 |  | 검사 대기
43 | T15 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
44 | T16 | REGISTER | RULE_RECIPE | 허용 |  | 등록
45 | T16 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
46 | T16 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
47 | T16 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
48 | T16 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
49 | T16 | P4 | RULE_FAIL_HOLD | 거절 | FAIL로 보류 중인 제품 | 보류
50 | T16 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
51 | T16B | REGISTER | RULE_RECIPE | 허용 |  | 등록
52 | T16B | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
53 | T16B | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
54 | T16B | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
55 | T16B | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
56 | T16B | P5 | RULE_SEQ | 허용 |  | 검사 대기
57 | T16B | INSPECT LIGHT FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
58 | T16B | INSPECT FINAL PASS | RULE_FAIL_HOLD | 허용 |  | 보류
59 | T17_C | REGISTER | RULE_RECIPE | 거절 | model이 비어 있거나 레시피에 없는 모델 | 미등록
60 | T17_A | REGISTER | RULE_RECIPE | 허용 |  | 등록
61 | T17_A | P6 | RULE_RECIPE | 거절 | 제품 레시피에 없는 공정 P6 | 등록
62 | T17_B | REGISTER | RULE_RECIPE | 허용 |  | 등록
63 | T17_B | INSPECT FINAL PASS | RULE_RECIPE | 거절 | 제품 레시피에 없는 검사 FINAL | 등록
64 | T19 | REGISTER | RULE_RECIPE | 허용 |  | 등록
65 | T19 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
66 | T19 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
67 | T19 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
68 | T19 | P4 | RULE_SEQ | 허용 |  | 검사 대기
69 | T19 | P5 | RULE_RECIPE | 거절 | 제품 레시피에 없는 공정 P5 | 검사 대기
70 | T20_MISSING | REGISTER | RULE_RECIPE | 거절 | model이 비어 있거나 레시피에 없는 모델 | 미등록
71 | T20 | REGISTER | RULE_RECIPE | 허용 |  | 등록
72 | T20 | P1 | RULE_PRESERVE | 거절 | REGISTER 이외의 model은 빈칸이어야 함 | 등록
73 | T22 | REGISTER | RULE_RECIPE | 허용 |  | 등록
74 | T22 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
75 | T22 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
76 | T22 | REGISTER | RULE_PRESERVE | 거절 | 이미 등록된 제품 | 공정 진행 중(P2 완료)

[제품별 최종 상태]
product_id | model | 최종 상태 | 미완료 이유
T11 | A | 레시피 모의 흐름 완료 | 
T12_A | A | 공정 진행 중(P4 완료) | P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T12_B | B | 레시피 모의 흐름 완료 | 
T13 | A | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T14_LEAK | A | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T14_LIGHT | A | 공정 진행 중(P4 완료) | P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T15 | A | 검사 대기 | FINAL 미실시
T16 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시
T16B | A | 보류 | LEAK 미실시; LIGHT FAIL
T17_A | A | 등록 | P1 미완료; P2 미완료; P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T17_B | B | 등록 | P1 미완료; P2 미완료; P3 미완료; P4 미완료; LEAK 미실시; LIGHT 미실시
T19 | B | 검사 대기 | LEAK 미실시; LIGHT 미실시
T20 | A | 등록 | P1 미완료; P2 미완료; P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T22 | A | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_RECIPE | 5
RULE_SEQ | 1
RULE_INSP_PRE | 2
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 1
RULE_PRESERVE | 3

저장 파일:
reports/sample_events_v2_rows.csv
reports/sample_events_v2_products.csv
reports/sample_events_v2_rejections.csv
```
종료 코드: 0
- `reports/sample_events_v2_rows.csv`: 체크아웃 파일과 바이트 동일=True; SHA-256 `f160067a77135885d3b5c1a5d11fae387102728433093b1dcaf92507c88da633`
- `reports/sample_events_v2_products.csv`: 체크아웃 파일과 바이트 동일=True; SHA-256 `27d129198d56de2add69ba538956457e4c1f6f103ac9d63dfc68ba424ca66791`
- `reports/sample_events_v2_rejections.csv`: 체크아웃 파일과 바이트 동일=True; SHA-256 `0486d5fc2af322959b6d9630e640e5303c647519f19df4ff4e83a63566cdf5a2`

명령(저장소 밖 임시 폴더, PYTHONPATH=저장소): `py -m src.main C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\data\sample_events_retest.csv --recipe C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\recipes\lamp_models_retest.json`

```text
레시피: C:/Users/PC/Documents/ChatGPT/에스엘 KDT AI 교육 부트캠프/project/recipes/lamp_models_retest.json | SHA-256: 438229b58c9e
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T23 | REGISTER | RULE_RECIPE | 허용 |  | 등록
2 | T23 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
3 | T23 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
4 | T23 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
5 | T23 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
6 | T23 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
7 | T23 | P4 | RULE_FAIL_HOLD | 거절 | FAIL로 보류 중인 제품 | 보류
8 | T24 | REGISTER | RULE_RECIPE | 허용 |  | 등록
9 | T24 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
10 | T24 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
11 | T24 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
12 | T24 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
13 | T24 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
14 | T24 | INSPECT LEAK PASS | RULE_RETEST | 허용 |  | 공정 진행 중(P3 완료)
15 | T24 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
16 | T24 | P5 | RULE_SEQ | 허용 |  | 검사 대기
17 | T24 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
18 | T24 | INSPECT FINAL PASS | RULE_FAIL_HOLD | 허용 |  | 레시피 모의 흐름 완료
19 | T25 | REGISTER | RULE_RECIPE | 허용 |  | 등록
20 | T25 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
21 | T25 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
22 | T25 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
23 | T25 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
24 | T25 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
25 | T26 | REGISTER | RULE_RECIPE | 허용 |  | 등록
26 | T26 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
27 | T26 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
28 | T26 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
29 | T26 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
30 | T26 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
31 | T26 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 보류
32 | T26 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
33 | T26 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
34 | T26 | INSPECT LEAK PASS | RULE_RETEST | 허용 |  | 공정 진행 중(P3 완료)
35 | T27 | REGISTER | RULE_RECIPE | 허용 |  | 등록
36 | T27 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
37 | T27 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
38 | T27 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
39 | T27 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
40 | T27 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
41 | T27 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 보류
42 | T27 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
43 | T27 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 폐기
44 | T27 | P4 | RULE_RETEST | 거절 | 폐기된 제품 | 폐기
45 | T27 | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 폐기된 제품 | 폐기
46 | T27 | INSPECT LIGHT PASS | RULE_RETEST | 거절 | 폐기된 제품 | 폐기
47 | T28_NO_RESULT | REGISTER | RULE_RECIPE | 허용 |  | 등록
48 | T28_NO_RESULT | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
49 | T28_NO_RESULT | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
50 | T28_NO_RESULT | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
51 | T28_NO_RESULT | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 미해결 FAIL 없음 | 공정 진행 중(P3 완료)
52 | T28_PASS | REGISTER | RULE_RECIPE | 허용 |  | 등록
53 | T28_PASS | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
54 | T28_PASS | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
55 | T28_PASS | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
56 | T28_PASS | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
57 | T28_PASS | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 미해결 FAIL 없음 | 공정 진행 중(P3 완료)
58 | T28_OPEN | REGISTER | RULE_RECIPE | 허용 |  | 등록
59 | T28_OPEN | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
60 | T28_OPEN | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
61 | T28_OPEN | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
62 | T28_OPEN | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
63 | T28_OPEN | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
64 | T28_OPEN | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 이미 열린 재검사 요청 | 보류
65 | T28_MODEL_B | REGISTER | RULE_RECIPE | 허용 |  | 등록
66 | T28_MODEL_B | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
67 | T28_MODEL_B | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
68 | T28_MODEL_B | RETEST_REQUEST FINAL | RULE_RECIPE | 거절 | 제품 레시피에 없는 검사 FINAL | 공정 진행 중(P2 완료)
69 | T28_UNREGISTERED | RETEST_REQUEST LEAK | RULE_PRESERVE | 거절 | 미등록 제품 | 미등록
70 | T28_FORMAT | REGISTER | RULE_RECIPE | 허용 |  | 등록
71 | T28_FORMAT | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
72 | T28_FORMAT | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
73 | T28_FORMAT | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
74 | T28_FORMAT | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
75 | T28_FORMAT | RETEST_REQUEST LEAK PASS | RULE_PRESERVE | 거절 | RETEST_REQUEST의 result는 빈칸이어야 함 | 보류
76 | T29 | REGISTER | RULE_RECIPE | 허용 |  | 등록
77 | T29 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
78 | T29 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
79 | T29 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
80 | T29 | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
81 | T29 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
82 | T29 | P5 | RULE_SEQ | 허용 |  | 검사 대기
83 | T29 | INSPECT LIGHT FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
84 | T29 | INSPECT FINAL FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
85 | T29 | RETEST_REQUEST LIGHT | RULE_RETEST | 허용 |  | 보류
86 | T29 | INSPECT LIGHT PASS | RULE_RETEST | 허용 |  | 보류
87 | T29 | RETEST_REQUEST FINAL | RULE_RETEST | 허용 |  | 보류
88 | T29 | INSPECT FINAL PASS | RULE_RETEST | 허용 |  | 레시피 모의 흐름 완료
89 | T30 | REGISTER | RULE_RECIPE | 허용 |  | 등록
90 | T30 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
91 | T30 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
92 | T30 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
93 | T30 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
94 | T30 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
95 | T30 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 보류
96 | T30 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
97 | T30 | INSPECT LEAK PASS | RULE_RETEST | 허용 |  | 공정 진행 중(P3 완료)
98 | T30 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
99 | T30 | P5 | RULE_SEQ | 허용 |  | 검사 대기
100 | T30 | INSPECT LIGHT FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
101 | T30 | RETEST_REQUEST LIGHT | RULE_RETEST | 허용 |  | 보류
102 | T30 | INSPECT LIGHT PASS | RULE_RETEST | 허용 |  | 검사 대기

[제품별 최종 상태]
product_id | model | 최종 상태 | 미완료 이유 | history
T23 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL(재검사 요청됨); LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@5 → 요청@6
T24 | A | 레시피 모의 흐름 완료 |  | LEAK: FAIL@12 → 요청@13 → PASS@14(재검사 1); LIGHT: PASS@17; FINAL: PASS@18
T25 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@23
T26 | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@29 → 요청@30 → FAIL@31(재검사 1) → 요청@33 → PASS@34(재검사 2)
T27 | A | 폐기 | LEAK 재검사 한도 2회 초과 FAIL로 폐기 | LEAK: FAIL@39 → 요청@40 → FAIL@41(재검사 1) → 요청@42 → FAIL@43(재검사 2)
T28_NO_RESULT | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시 | 
T28_PASS | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: PASS@56
T28_OPEN | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL(재검사 요청됨); LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@62 → 요청@63
T28_MODEL_B | B | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; LEAK 미실시; LIGHT 미실시 | 
T28_FORMAT | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@74
T29 | A | 레시피 모의 흐름 완료 |  | LEAK: PASS@80; LIGHT: FAIL@83 → 요청@85 → PASS@86(재검사 1); FINAL: FAIL@84 → 요청@87 → PASS@88(재검사 1)
T30 | A | 검사 대기 | FINAL 미실시 | LEAK: FAIL@93 → 요청@94 → FAIL@95(재검사 1) → 요청@96 → PASS@97(재검사 2); LIGHT: FAIL@100 → 요청@101 → PASS@102(재검사 1)

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_RECIPE | 1
RULE_SEQ | 0
RULE_INSP_PRE | 0
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 1
RULE_PRESERVE | 4
RULE_RETEST | 6

저장 파일:
reports/sample_events_retest_rows.csv
reports/sample_events_retest_products.csv
reports/sample_events_retest_rejections.csv
```
종료 코드: 0
- `reports/sample_events_retest_rows.csv`: 체크아웃 파일과 바이트 동일=True; SHA-256 `6674e813936d5d62192d2742a90de18c78ebeddb11c90104f218df4034249963`
- `reports/sample_events_retest_products.csv`: 체크아웃 파일과 바이트 동일=True; SHA-256 `3f6e9f3a24fb758f019c472684a07c87bcec24d0fa9bbf27e54f7eda906afe7e`
- `reports/sample_events_retest_rejections.csv`: 체크아웃 파일과 바이트 동일=True; SHA-256 `d3d6d4f485ef95a92a3c952f8342eb2f0e1325e886a85885c430ac6f975d5d28`

### 최신 리뷰 003 대응
- L1 반영: 기존 승인된 T32 예외(inspection 빈칸은 RULE_PRESERVE, result 기입은 이유 문구 변경)도 보존한다. 이번 작업에서 기존 재검사 규칙을 바꾸지 않는다.
- L2 반영 확인: 사용자가 2단계 사후 확정·3단계 사전 사용자 확정을 기록했다. 보호 문서는 수정하지 않는다.
- L3 보류: 기존 폐기 이유 원문과 샘플 보존을 위해 변경하지 않음.
- L4 보류: 기존 테스트는 명세 충족·사용자 보호 대상이므로 수정하지 않음. 새 설비 검증은 별도 tests/test_equipment.py에서 검증.

### ① T40 검증 추가 후 구현 전 실패 확인

명령: `py -m unittest discover -s tests -p test_equipment.py`

```text
E
======================================================================
ERROR: test_equipment (unittest.loader._FailedTest)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_equipment
Traceback (most recent call last):
  File "C:\Users\PC\anaconda3\lib\unittest\loader.py", line 436, in _find_test_path
    module = self._get_module_from_name(name)
  File "C:\Users\PC\anaconda3\lib\unittest\loader.py", line 377, in _get_module_from_name
    __import__(name)
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 11, in <module>
    from src.equipment import EquipmentError, load_equipment
ModuleNotFoundError: No module named 'src.equipment'


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
```
종료 코드: 1

### ① T40 구현 전 실패 확인(출력 인코딩 보정 후)

명령: `py -m unittest discover -s tests -p test_equipment.py`

```text
E
======================================================================
ERROR: test_equipment (unittest.loader._FailedTest)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_equipment
Traceback (most recent call last):
  File "C:\Users\PC\anaconda3\lib\unittest\loader.py", line 436, in _find_test_path
    module = self._get_module_from_name(name)
  File "C:\Users\PC\anaconda3\lib\unittest\loader.py", line 377, in _get_module_from_name
    __import__(name)
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_equipment.py", line 11, in <module>
    from src.equipment import EquipmentError, load_equipment
ModuleNotFoundError: No module named 'src.equipment'


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)
```
종료 코드: 1

### ① 설비 파일 검증 T40: 전체 회귀

명령: `py -m unittest discover -s tests`

```text
..........................................................
----------------------------------------------------------------------
Ran 58 tests in 6.826s

OK
```
종료 코드: 0

① 완료(T40): 설비 JSON 전체 오류·타입(bool 제외)·경계·ID·레시피 검사 참조·파일/JSON 오류를 검증. 신규 테스트 4개, 기존 54개 무수정 통과. CLI에서 설비 오류는 입력 읽기와 출력/보고서 생성 전에 코드 3. 기본 설정과 오류 fixture 7종 추가. 구현 전 신규 모듈 부재 실패를 확인했다. 최초 실패 로그 수집 때 cp949 출력 오류가 발생하여 테스트 하위 프로세스 인코딩을 UTF-8로 고정하고 원문을 다시 기록했다.

### ② T33–T39 구현 전 실패 확인

명령: `py -m unittest discover -s tests -p test_equipment.py`

```text
....EEEEEEEEEE
======================================================================
ERROR: test_equipment_also_works_without_retest_mode (test_equipment.EquipmentProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_equipment.py", line 111, in setUp
    self.process = RecipeProcess(self.models, self.book)
TypeError: __init__() takes 2 positional arguments but 3 were given

======================================================================
ERROR: test_partial_window_threshold_and_physical_order_not_seq_sorting (test_equipment.EquipmentProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_equipment.py", line 111, in setUp
    self.process = RecipeProcess(self.models, self.book)
TypeError: __init__() takes 2 positional arguments but 3 were given

======================================================================
ERROR: test_priority_format_registration_discard_recipe_equipment_timing_duplicate (test_equipment.EquipmentProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_equipment.py", line 111, in setUp
    self.process = RecipeProcess(self.models, self.book)
TypeError: __init__() takes 2 positional arguments but 3 were given

======================================================================
ERROR: test_t33_triggering_result_is_accepted_and_stops_only_its_equipment (test_equipment.EquipmentProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_equipment.py", line 111, in setUp
    self.process = RecipeProcess(self.models, self.book)
TypeError: __init__() takes 2 positional arguments but 3 were given

======================================================================
ERROR: test_t34_stopped_reject_then_other_equipment_accepts (test_equipment.EquipmentProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_equipment.py", line 111, in setUp
    self.process = RecipeProcess(self.models, self.book)
TypeError: __init__() takes 2 positional arguments but 3 were given

======================================================================
ERROR: test_t35_stopped_retest_keeps_request_then_other_equipment_releases_hold (test_equipment.EquipmentProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_equipment.py", line 111, in setUp
    self.process = RecipeProcess(self.models, self.book)
TypeError: __init__() takes 2 positional arguments but 3 were given

======================================================================
ERROR: test_t36_repeated_retest_fails_scrap_product_without_stopping_equipment (test_equipment.EquipmentProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_equipment.py", line 111, in setUp
    self.process = RecipeProcess(self.models, self.book)
TypeError: __init__() takes 2 positional arguments but 3 were given

======================================================================
ERROR: test_t37_sliding_window_is_separate_from_cumulative_report_counts (test_equipment.EquipmentProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_equipment.py", line 111, in setUp
    self.process = RecipeProcess(self.models, self.book)
TypeError: __init__() takes 2 positional arguments but 3 were given

======================================================================
ERROR: test_t38_equipment_and_format_rejections_preserve_all_state (test_equipment.EquipmentProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_equipment.py", line 111, in setUp
    self.process = RecipeProcess(self.models, self.book)
TypeError: __init__() takes 2 positional arguments but 3 were given

======================================================================
ERROR: test_t39_rejected_early_result_never_counts_or_stops (test_equipment.EquipmentProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_equipment.py", line 111, in setUp
    self.process = RecipeProcess(self.models, self.book)
TypeError: __init__() takes 2 positional arguments but 3 were given

----------------------------------------------------------------------
Ran 14 tests in 1.273s

FAILED (errors=10)
```
종료 코드: 1

### ② 설비 판정과 정지 T33–T39: 전체 회귀

명령: `py -m unittest discover -s tests`

```text
....................................................................
----------------------------------------------------------------------
Ran 68 tests in 6.763s

OK
```
종료 코드: 0

### ③ CLI·보고서 T41 구현 전 실패 확인

명령: `py -m unittest discover -s tests -p test_equipment.py`

```text
..............FFF.
======================================================================
FAIL: test_t41_equipment_with_stage_one_has_seven_rules_and_no_history (test_equipment.EquipmentReportTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_equipment.py", line 374, in test_t41_equipment_with_stage_one_has_seven_rules_and_no_history
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 2 != 0 : b'\xec\x98\xa4\xeb\xa5\x98: CSV \xed\x97\xa4\xeb\x8d\x94\xeb\x8a\x94 seq,product_id,event,inspection,result,model \xec\x9d\xb4\xec\x96\xb4\xec\x95\xbc \xed\x95\xa8\r\n'

======================================================================
FAIL: test_t41_four_reports_history_equipment_order_and_byte_reproducibility (test_equipment.EquipmentReportTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_equipment.py", line 310, in test_t41_four_reports_history_equipment_order_and_byte_reproducibility
    self.assertEqual(first.returncode, 0, first.stderr.decode("utf-8"))
AssertionError: 2 != 0 : 오류: CSV 헤더는 seq,product_id,event,inspection,result,model 이어야 함


======================================================================
FAIL: test_t41_option_dependency_and_mode_specific_headers (test_equipment.EquipmentReportTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_equipment.py", line 353, in test_t41_option_dependency_and_mode_specific_headers
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 0 != 2 : b''

----------------------------------------------------------------------
Ran 18 tests in 3.255s

FAILED (failures=3)
```
종료 코드: 1

### ③ CLI·보고서·설비 표시 T41: 전체 회귀

명령: `py -m unittest discover -s tests`

```text
........................................................................
----------------------------------------------------------------------
Ran 72 tests in 9.175s

OK
```
종료 코드: 0

② 완료(T33–T39): 허용된 최초 결과만 설비별 집계하고 원인 행 반영 뒤 정지. 설비 판정은 형식·등록·폐기·레시피 뒤, 시점·중복 검사 앞에 둠. 재검사·거절은 설비 기록 미반영. 거절 helper는 모든 제품과 모든 설비의 deepcopy 전후 동등 비교. 신규 판정 테스트 10개와 전체 68개 통과. 이전 기록 추가용 stdin 스크립트가 인코딩 오류로 실행되지 않아 이 항목을 이번 커밋에 기록함(검증 원문은 이전 커밋에 보존).

### 해석·가정 / 명세 이견
- 해석: 최근 window건은 결과가 window개 미만이면 현재까지의 최대 window건이다. 기본 설정의 최초 두 결과가 FAIL, FAIL이면 둘째 뒤 정지한다. 별도의 창 충족 대기는 명세에 없다. seq 정렬 없이 물리적 허용 순서로 계산한다.
- 해석: equipment.csv의 counted_results/fail_count는 허용된 최초 결과 누적 건수/누적 FAIL 건수다. 정지 판단용 최근 창과 별개다. T37은 4,2,가동이며 이후 FAIL이면 5,3,정지가 된다.
- 명세 이견: 현재 3단계 요구·기대표와 충돌하여 다르게 구현한 사항 없음. 위 두 항목은 미명시 범위의 해석으로 공개한다. 기존 승인된 T32·폐기 문구 이견은 변경하지 않음.

③ 완료(T41): 7열 CSV를 설비 모드에만 허용, --equipment는 --recipe 필수. 보고서 4종·설비 파일 순서·미사용 설비·BOM·7/8개 규칙 순서·원본 SHA-256·rows 및 history 설비 표시를 검사. 같은 경로 2회와 별도 출력 폴더 1회에서 stdout/4종 CSV 바이트 동일. --equipment 없는 기존 샘플 3종의 보고서 9개도 바이트 동일. 구현 전 헤더·출력 관련 3개 테스트 실패 확인 후 전체 72개 통과.

### ④ 샘플 산출물 생성 전 부재 확인

명령: `py -m unittest discover -s tests -p test_equipment.py`

```text
..............E....
======================================================================
ERROR: test_sample_t33_to_t39_reports_and_all_rejected_state_unchanged (test_equipment.EquipmentReportTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_equipment.py", line 288, in test_sample_t33_to_t39_reports_and_all_rejected_state_unchanged
    with sample.open(encoding="utf-8-sig", newline="") as source:
  File "C:\Users\PC\anaconda3\lib\pathlib.py", line 1252, in open
    return io.open(self, mode, buffering, encoding, errors, newline,
  File "C:\Users\PC\anaconda3\lib\pathlib.py", line 1120, in _opener
    return self._accessor.open(self, flags, mode)
FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\PC\\Documents\\ChatGPT\\에스엘 KDT AI 교육 부트캠프\\project\\data\\sample_events_equipment.csv'

----------------------------------------------------------------------
Ran 19 tests in 3.489s

FAILED (errors=1)
```
종료 코드: 1

명령: `py -m src.main data/sample_events_equipment.csv --recipe recipes/lamp_models_retest.json --equipment recipes/equipment.json`

```text
레시피: recipes/lamp_models_retest.json | SHA-256: 438229b58c9e
설비: recipes/equipment.json | SHA-256: 2e1252ba2c8d
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T36 | REGISTER | RULE_RECIPE | 허용 |  | 등록
2 | T36 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
3 | T36 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
4 | T36 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
5 | T36 | INSPECT LEAK FAIL @LEAK-1 | RULE_FAIL_HOLD | 허용 |  | 보류
6 | T36 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
7 | T36 | INSPECT LEAK FAIL @LEAK-1 | RULE_RETEST | 허용 |  | 보류
8 | T36 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
9 | T36 | INSPECT LEAK FAIL @LEAK-1 | RULE_RETEST | 허용 |  | 폐기
10 | T33_T35_A | REGISTER | RULE_RECIPE | 허용 |  | 등록
11 | T33_T35_A | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
12 | T33_T35_A | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
13 | T33_T35_A | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
14 | T33_T35_A | INSPECT LEAK FAIL @LEAK-2 | RULE_FAIL_HOLD | 허용 |  | 보류
15 | T33_T35_A | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
16 | T33_P2 | REGISTER | RULE_RECIPE | 허용 |  | 등록
17 | T33_P2 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
18 | T33_P2 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
19 | T33_P2 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
20 | T33_P2 | INSPECT LEAK PASS @LEAK-2 | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
21 | T33_P3 | REGISTER | RULE_RECIPE | 허용 |  | 등록
22 | T33_P3 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
23 | T33_P3 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
24 | T33_P3 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
25 | T33_P3 | INSPECT LEAK FAIL @LEAK-2 | RULE_FAIL_HOLD | 허용 |  | 보류
26 | T34 | REGISTER | RULE_RECIPE | 허용 |  | 등록
27 | T34 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
28 | T34 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
29 | T34 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
30 | T34 | INSPECT LEAK PASS @LEAK-2 | RULE_EQUIP | 거절 | 정지된 설비 | 공정 진행 중(P3 완료)
31 | T34 | INSPECT LEAK PASS @LEAK-1 | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
32 | T33_T35_A | INSPECT LEAK PASS @LEAK-2 | RULE_EQUIP | 거절 | 정지된 설비 | 보류
33 | T33_T35_A | INSPECT LEAK PASS @LEAK-1 | RULE_RETEST | 허용 |  | 공정 진행 중(P3 완료)
34 | BUFFER_BEFORE_T37 | REGISTER | RULE_RECIPE | 허용 |  | 등록
35 | BUFFER_BEFORE_T37 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
36 | BUFFER_BEFORE_T37 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
37 | BUFFER_BEFORE_T37 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
38 | BUFFER_BEFORE_T37 | INSPECT LEAK PASS @LEAK-1 | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
39 | T37_1 | REGISTER | RULE_RECIPE | 허용 |  | 등록
40 | T37_1 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
41 | T37_1 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
42 | T37_1 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
43 | T37_1 | INSPECT LEAK FAIL @LEAK-1 | RULE_FAIL_HOLD | 허용 |  | 보류
44 | T37_2 | REGISTER | RULE_RECIPE | 허용 |  | 등록
45 | T37_2 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
46 | T37_2 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
47 | T37_2 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
48 | T37_2 | INSPECT LEAK PASS @LEAK-1 | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
49 | T37_3 | REGISTER | RULE_RECIPE | 허용 |  | 등록
50 | T37_3 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
51 | T37_3 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
52 | T37_3 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
53 | T37_3 | INSPECT LEAK PASS @LEAK-1 | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
54 | T37_4 | REGISTER | RULE_RECIPE | 허용 |  | 등록
55 | T37_4 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
56 | T37_4 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
57 | T37_4 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
58 | T37_4 | INSPECT LEAK FAIL @LEAK-1 | RULE_FAIL_HOLD | 허용 |  | 보류
59 | T38 | REGISTER | RULE_RECIPE | 허용 |  | 등록
60 | T38 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
61 | T38 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
62 | T38 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
63 | T38 | INSPECT LEAK PASS @LEAK-9 | RULE_EQUIP | 거절 | 등록되지 않은 설비 | 공정 진행 중(P3 완료)
64 | T38 | INSPECT LEAK PASS @LIGHT-1 | RULE_EQUIP | 거절 | 검사 종류가 다른 설비 | 공정 진행 중(P3 완료)
65 | T38 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | equipment가 비어 있음 | 공정 진행 중(P3 완료)
66 | T38 | P4 | RULE_PRESERVE | 거절 | INSPECT 이외의 equipment는 빈칸이어야 함 | 공정 진행 중(P3 완료)
67 | BUFFER_BEFORE_T39_1 | REGISTER | RULE_RECIPE | 허용 |  | 등록
68 | BUFFER_BEFORE_T39_1 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
69 | BUFFER_BEFORE_T39_1 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
70 | BUFFER_BEFORE_T39_1 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
71 | BUFFER_BEFORE_T39_1 | INSPECT LEAK PASS @LEAK-1 | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
72 | BUFFER_BEFORE_T39_2 | REGISTER | RULE_RECIPE | 허용 |  | 등록
73 | BUFFER_BEFORE_T39_2 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
74 | BUFFER_BEFORE_T39_2 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
75 | BUFFER_BEFORE_T39_2 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
76 | BUFFER_BEFORE_T39_2 | INSPECT LEAK PASS @LEAK-1 | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
77 | T39_1 | REGISTER | RULE_RECIPE | 허용 |  | 등록
78 | T39_1 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
79 | T39_1 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
80 | T39_1 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
81 | T39_1 | INSPECT LEAK FAIL @LEAK-1 | RULE_FAIL_HOLD | 허용 |  | 보류
82 | T39_EARLY | REGISTER | RULE_RECIPE | 허용 |  | 등록
83 | T39_EARLY | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
84 | T39_EARLY | INSPECT LEAK FAIL @LEAK-1 | RULE_INSP_PRE | 거절 | P3 미완료 | 공정 진행 중(P1 완료)
85 | T39_2 | REGISTER | RULE_RECIPE | 허용 |  | 등록
86 | T39_2 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
87 | T39_2 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
88 | T39_2 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
89 | T39_2 | INSPECT LEAK PASS @LEAK-1 | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
90 | T39_3 | REGISTER | RULE_RECIPE | 허용 |  | 등록
91 | T39_3 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
92 | T39_3 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
93 | T39_3 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
94 | T39_3 | INSPECT LEAK FAIL @LEAK-1 | RULE_FAIL_HOLD | 허용 |  | 보류

[제품별 최종 상태]
product_id | model | 최종 상태 | 미완료 이유 | history
T36 | A | 폐기 | LEAK 재검사 한도 2회 초과 FAIL로 폐기 | LEAK: FAIL@5[LEAK-1] → 요청@6 → FAIL@7[LEAK-1](재검사 1) → 요청@8 → FAIL@9[LEAK-1](재검사 2)
T33_T35_A | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@14[LEAK-2] → 요청@15 → PASS@33[LEAK-1](재검사 1)
T33_P2 | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: PASS@20[LEAK-2]
T33_P3 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@25[LEAK-2]
T34 | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: PASS@31[LEAK-1]
BUFFER_BEFORE_T37 | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: PASS@38[LEAK-1]
T37_1 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@43[LEAK-1]
T37_2 | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: PASS@48[LEAK-1]
T37_3 | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: PASS@53[LEAK-1]
T37_4 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@58[LEAK-1]
T38 | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시 | 
BUFFER_BEFORE_T39_1 | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: PASS@71[LEAK-1]
BUFFER_BEFORE_T39_2 | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: PASS@76[LEAK-1]
T39_1 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@81[LEAK-1]
T39_EARLY | A | 공정 진행 중(P1 완료) | P2 미완료; P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시 | 
T39_2 | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: PASS@89[LEAK-1]
T39_3 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@94[LEAK-1]

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_RECIPE | 0
RULE_SEQ | 0
RULE_INSP_PRE | 1
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 0
RULE_PRESERVE | 2
RULE_RETEST | 0
RULE_EQUIP | 4

[설비별 최종 상태]
equipment | inspection | counted_results | fail_count | state | stopped_at_seq
LEAK-1 | LEAK | 12 | 5 | 정지 | 94
LEAK-2 | LEAK | 3 | 2 | 정지 | 25
LIGHT-1 | LIGHT | 0 | 0 | 가동 | 
FINAL-1 | FINAL | 0 | 0 | 가동 | 

저장 파일:
reports/sample_events_equipment_rows.csv
reports/sample_events_equipment_products.csv
reports/sample_events_equipment_rejections.csv
reports/sample_events_equipment_equipment.csv
```
Exit code: 0

### ④ 固定 샘플·보고서 T33–T41: 전체 회귀

명령: `py -m unittest discover -s tests`

```text
.........................................................................
----------------------------------------------------------------------
Ran 73 tests in 10.264s

OK
```
종료 코드: 0

④ 완료(T33–T41): 고정 입력 94행(허용 87·거절 7), 등록 제품 17개. T36 → T33/T35 최초 FAIL·요청 → T33 정지 → T34 우회 → T35 재검사 → T37 → T38 → T39 순서로 공유 설비의 일회 실행을 구성했다. BUFFER 제품 PASS는 T36/T37의 이전 FAIL이 다음 시나리오 창에 섞이지 않도록 하는 허용 최초 결과이며 숨기지 않고 CSV·보고서에 포함했다. 수기로 산정한 94행·누적 LEAK-1 12/5, LEAK-2 3/2·거절 순서를 신규 샘플 테스트로 검증하고 보고서 4개를 체크아웃 바이트와 비교했다. 전체 73개 통과.

### ⑤ README 설비 모드 문서화: 전체 회귀

명령: `py -m unittest discover -s tests`

```text
.........................................................................
----------------------------------------------------------------------
Ran 73 tests in 10.005s

OK
```
종료 코드: 0

⑤ 완료(T33–T41): README에 설비 모드 켜는 법·7열 입력·설비 JSON 검증·정지 기준·규칙 표·보고서 의미·제외 범위를 추가했다. 원래 WECO의 2σ 측정값 패턴과 가상 PASS/FAIL 기준의 차이를 설명하고 NIST 원출처(https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc32.htm, 2026-10-18 확인)를 연결했다. 새 문서의 CSV 예제는 전 행 7열을 확인. 문서만 변경했으므로 새 단위 테스트는 추가하지 않고 위 전체 73개 회귀와 이미 실행한 샘플 CLI로 검증했다.

### 최종 v1 회귀(T1–T10, 보호 테스트 무수정)

명령: `py -m unittest discover -s tests -p test_rules.py`

```text
............
----------------------------------------------------------------------
Ran 12 tests in 0.303s

OK
```
종료 코드: 0

### 최종 v2 1단계 회귀(T11–T22, 보호 테스트 무수정)

명령: `py -m unittest discover -s tests -p test_recipe.py`

```text
..........................
----------------------------------------------------------------------
Ran 26 tests in 3.516s

OK
```
종료 코드: 0

### 최종 v2 2단계 회귀(T23–T32, 보호 테스트 무수정)

명령: `py -m unittest discover -s tests -p test_retest.py`

```text
................
----------------------------------------------------------------------
Ran 16 tests in 1.698s

OK
```
종료 코드: 0

### 최종 v2 3단계(T33–T41)

명령: `py -m unittest discover -s tests -p test_equipment.py`

```text
...................
----------------------------------------------------------------------
Ran 19 tests in 3.719s

OK
```
종료 코드: 0

Final regression command (temporary cwd): `py -m src.main C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\data\sample_events.csv`

```text
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T1 | REGISTER | RULE_SEQ | 허용 |  | 등록
2 | T1 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
3 | T1 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
4 | T1 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
5 | T1 | INSPECT LEAK PASS | RULE_FAIL_HOLD | 허용 |  | 선택한 두 검사까지의 모의 흐름 완료
6 | T2 | REGISTER | RULE_SEQ | 허용 |  | 등록
7 | T2 | MAIN_ASSEMBLY | RULE_SEQ | 거절 | PRE_ASSEMBLY 미완료 | 등록
8 | T3 | REGISTER | RULE_SEQ | 허용 |  | 등록
9 | T3 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
10 | T3 | INSPECT LIGHT PASS | RULE_INSP_PRE | 거절 | MAIN_ASSEMBLY 미완료 | 예비 조립
11 | T4 | REGISTER | RULE_SEQ | 허용 |  | 등록
12 | T4 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
13 | T4 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
14 | T4 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
15 | T5 | REGISTER | RULE_SEQ | 허용 |  | 등록
16 | T5 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
17 | T5 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
18 | T5 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
19 | T5 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
20 | T6 | REGISTER | RULE_SEQ | 허용 |  | 등록
21 | T6 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
22 | T6 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
23 | T6 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
24 | T6 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
25 | T6 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
26 | T7 | REGISTER | RULE_SEQ | 허용 |  | 등록
27 | T7 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
28 | T7 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
29 | T7 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
30 | T7 | INSPECT LEAK PASS | RULE_FAIL_HOLD | 허용 |  | 선택한 두 검사까지의 모의 흐름 완료
31 | T7 | INSPECT LIGHT FAIL | RULE_PRESERVE | 거절 | LIGHT 결과 이미 존재 | 선택한 두 검사까지의 모의 흐름 완료
32 | T8 | REGISTER | RULE_SEQ | 허용 |  | 등록
33 | T8 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
34 | T8 | PRE_ASSEMBLY | RULE_PRESERVE | 거절 | 중복 조립 이벤트 | 예비 조립
35 | T9_UNREGISTERED | MAIN_ASSEMBLY | RULE_PRESERVE | 거절 | 미등록 제품 | 미등록
36 | T9 | REGISTER | RULE_SEQ | 허용 |  | 등록
37 | T9 | PRE_ASSEMBLY | RULE_SEQ | 허용 |  | 예비 조립
38 | T9 | MAIN_ASSEMBLY | RULE_SEQ | 허용 |  | 검사 대기
39 | T9 | INSPECT LIGHT OK | RULE_PRESERVE | 거절 | 잘못된 result (PASS 또는 FAIL 필요) | 검사 대기

[제품별 최종 상태]
product_id | 최종 상태 | 미완료 이유
T1 | 선택한 두 검사까지의 모의 흐름 완료 | 
T2 | 등록 | PRE_ASSEMBLY 미완료; MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T3 | 예비 조립 | MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T4 | 검사 대기 | LEAK 미실시
T5 | 보류 | LEAK FAIL
T6 | 보류 | LEAK FAIL
T7 | 선택한 두 검사까지의 모의 흐름 완료 | 
T8 | 예비 조립 | MAIN_ASSEMBLY 미완료; LIGHT 미실시; LEAK 미실시
T9 | 검사 대기 | LIGHT 미실시; LEAK 미실시

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_SEQ | 1
RULE_INSP_PRE | 1
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 0
RULE_PRESERVE | 5

저장 파일:
reports/sample_events_rows.csv
reports/sample_events_products.csv
reports/sample_events_rejections.csv
```
Exit code: 0; stdout byte-identical to starting baseline.
- reports/sample_events_rows.csv: byte-identical; SHA-256 eb4042fb981c2ffe6611117a0ebb5636c552177a894d83a4406a607b08a952c8
- reports/sample_events_products.csv: byte-identical; SHA-256 e2317c768731185c28b5040aea345eb197873e76cf3459adacf25b3ea89c86e6
- reports/sample_events_rejections.csv: byte-identical; SHA-256 72143e7c3410b4a0ac1829f139027fcbca3fb305c7d83586cb0b2f8ac9d6c17f

Final regression command (temporary cwd): `py -m src.main C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\data\sample_events_v2.csv --recipe C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\recipes\lamp_models.json`

```text
레시피: C:/Users/PC/Documents/ChatGPT/에스엘 KDT AI 교육 부트캠프/project/recipes/lamp_models.json | SHA-256: d7a8976ee178
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T11 | REGISTER | RULE_RECIPE | 허용 |  | 등록
2 | T11 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
3 | T11 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
4 | T11 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
5 | T11 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
6 | T11 | P5 | RULE_SEQ | 허용 |  | 검사 대기
7 | T11 | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
8 | T11 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
9 | T11 | INSPECT FINAL PASS | RULE_FAIL_HOLD | 허용 |  | 레시피 모의 흐름 완료
10 | T12_A | REGISTER | RULE_RECIPE | 허용 |  | 등록
11 | T12_B | REGISTER | RULE_RECIPE | 허용 |  | 등록
12 | T12_A | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
13 | T12_B | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
14 | T12_A | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
15 | T12_B | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
16 | T12_A | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
17 | T12_B | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
18 | T12_A | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
19 | T12_B | P4 | RULE_SEQ | 허용 |  | 검사 대기
20 | T12_B | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
21 | T12_B | INSPECT LIGHT PASS | RULE_FAIL_HOLD | 허용 |  | 레시피 모의 흐름 완료
22 | T13 | REGISTER | RULE_RECIPE | 허용 |  | 등록
23 | T13 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
24 | T13 | P3 | RULE_SEQ | 거절 | P2 미완료 | 공정 진행 중(P1 완료)
25 | T13 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
26 | T14_LEAK | REGISTER | RULE_RECIPE | 허용 |  | 등록
27 | T14_LEAK | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
28 | T14_LEAK | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
29 | T14_LEAK | INSPECT LEAK PASS | RULE_INSP_PRE | 거절 | P3 미완료 | 공정 진행 중(P2 완료)
30 | T14_LIGHT | REGISTER | RULE_RECIPE | 허용 |  | 등록
31 | T14_LIGHT | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
32 | T14_LIGHT | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
33 | T14_LIGHT | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
34 | T14_LIGHT | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
35 | T14_LIGHT | INSPECT LIGHT PASS | RULE_INSP_PRE | 거절 | P5 미완료 | 공정 진행 중(P4 완료)
36 | T15 | REGISTER | RULE_RECIPE | 허용 |  | 등록
37 | T15 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
38 | T15 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
39 | T15 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
40 | T15 | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
41 | T15 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
42 | T15 | P5 | RULE_SEQ | 허용 |  | 검사 대기
43 | T15 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
44 | T16 | REGISTER | RULE_RECIPE | 허용 |  | 등록
45 | T16 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
46 | T16 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
47 | T16 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
48 | T16 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
49 | T16 | P4 | RULE_FAIL_HOLD | 거절 | FAIL로 보류 중인 제품 | 보류
50 | T16 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
51 | T16B | REGISTER | RULE_RECIPE | 허용 |  | 등록
52 | T16B | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
53 | T16B | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
54 | T16B | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
55 | T16B | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
56 | T16B | P5 | RULE_SEQ | 허용 |  | 검사 대기
57 | T16B | INSPECT LIGHT FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
58 | T16B | INSPECT FINAL PASS | RULE_FAIL_HOLD | 허용 |  | 보류
59 | T17_C | REGISTER | RULE_RECIPE | 거절 | model이 비어 있거나 레시피에 없는 모델 | 미등록
60 | T17_A | REGISTER | RULE_RECIPE | 허용 |  | 등록
61 | T17_A | P6 | RULE_RECIPE | 거절 | 제품 레시피에 없는 공정 P6 | 등록
62 | T17_B | REGISTER | RULE_RECIPE | 허용 |  | 등록
63 | T17_B | INSPECT FINAL PASS | RULE_RECIPE | 거절 | 제품 레시피에 없는 검사 FINAL | 등록
64 | T19 | REGISTER | RULE_RECIPE | 허용 |  | 등록
65 | T19 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
66 | T19 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
67 | T19 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
68 | T19 | P4 | RULE_SEQ | 허용 |  | 검사 대기
69 | T19 | P5 | RULE_RECIPE | 거절 | 제품 레시피에 없는 공정 P5 | 검사 대기
70 | T20_MISSING | REGISTER | RULE_RECIPE | 거절 | model이 비어 있거나 레시피에 없는 모델 | 미등록
71 | T20 | REGISTER | RULE_RECIPE | 허용 |  | 등록
72 | T20 | P1 | RULE_PRESERVE | 거절 | REGISTER 이외의 model은 빈칸이어야 함 | 등록
73 | T22 | REGISTER | RULE_RECIPE | 허용 |  | 등록
74 | T22 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
75 | T22 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
76 | T22 | REGISTER | RULE_PRESERVE | 거절 | 이미 등록된 제품 | 공정 진행 중(P2 완료)

[제품별 최종 상태]
product_id | model | 최종 상태 | 미완료 이유
T11 | A | 레시피 모의 흐름 완료 | 
T12_A | A | 공정 진행 중(P4 완료) | P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T12_B | B | 레시피 모의 흐름 완료 | 
T13 | A | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T14_LEAK | A | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T14_LIGHT | A | 공정 진행 중(P4 완료) | P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T15 | A | 검사 대기 | FINAL 미실시
T16 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시
T16B | A | 보류 | LEAK 미실시; LIGHT FAIL
T17_A | A | 등록 | P1 미완료; P2 미완료; P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T17_B | B | 등록 | P1 미완료; P2 미완료; P3 미완료; P4 미완료; LEAK 미실시; LIGHT 미실시
T19 | B | 검사 대기 | LEAK 미실시; LIGHT 미실시
T20 | A | 등록 | P1 미완료; P2 미완료; P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시
T22 | A | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_RECIPE | 5
RULE_SEQ | 1
RULE_INSP_PRE | 2
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 1
RULE_PRESERVE | 3

저장 파일:
reports/sample_events_v2_rows.csv
reports/sample_events_v2_products.csv
reports/sample_events_v2_rejections.csv
```
Exit code: 0; stdout byte-identical to starting baseline.
- reports/sample_events_v2_rows.csv: byte-identical; SHA-256 f160067a77135885d3b5c1a5d11fae387102728433093b1dcaf92507c88da633
- reports/sample_events_v2_products.csv: byte-identical; SHA-256 27d129198d56de2add69ba538956457e4c1f6f103ac9d63dfc68ba424ca66791
- reports/sample_events_v2_rejections.csv: byte-identical; SHA-256 0486d5fc2af322959b6d9630e640e5303c647519f19df4ff4e83a63566cdf5a2

Final regression command (temporary cwd): `py -m src.main C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\data\sample_events_retest.csv --recipe C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\recipes\lamp_models_retest.json`

```text
레시피: C:/Users/PC/Documents/ChatGPT/에스엘 KDT AI 교육 부트캠프/project/recipes/lamp_models_retest.json | SHA-256: 438229b58c9e
[행별 판정]
seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
1 | T23 | REGISTER | RULE_RECIPE | 허용 |  | 등록
2 | T23 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
3 | T23 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
4 | T23 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
5 | T23 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
6 | T23 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
7 | T23 | P4 | RULE_FAIL_HOLD | 거절 | FAIL로 보류 중인 제품 | 보류
8 | T24 | REGISTER | RULE_RECIPE | 허용 |  | 등록
9 | T24 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
10 | T24 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
11 | T24 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
12 | T24 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
13 | T24 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
14 | T24 | INSPECT LEAK PASS | RULE_RETEST | 허용 |  | 공정 진행 중(P3 완료)
15 | T24 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
16 | T24 | P5 | RULE_SEQ | 허용 |  | 검사 대기
17 | T24 | INSPECT LIGHT PASS | RULE_NOT_DONE | 허용 |  | 검사 대기
18 | T24 | INSPECT FINAL PASS | RULE_FAIL_HOLD | 허용 |  | 레시피 모의 흐름 완료
19 | T25 | REGISTER | RULE_RECIPE | 허용 |  | 등록
20 | T25 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
21 | T25 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
22 | T25 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
23 | T25 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
24 | T25 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
25 | T26 | REGISTER | RULE_RECIPE | 허용 |  | 등록
26 | T26 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
27 | T26 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
28 | T26 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
29 | T26 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
30 | T26 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
31 | T26 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 보류
32 | T26 | INSPECT LEAK PASS | RULE_PRESERVE | 거절 | LEAK 결과 이미 존재 | 보류
33 | T26 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
34 | T26 | INSPECT LEAK PASS | RULE_RETEST | 허용 |  | 공정 진행 중(P3 완료)
35 | T27 | REGISTER | RULE_RECIPE | 허용 |  | 등록
36 | T27 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
37 | T27 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
38 | T27 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
39 | T27 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
40 | T27 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
41 | T27 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 보류
42 | T27 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
43 | T27 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 폐기
44 | T27 | P4 | RULE_RETEST | 거절 | 폐기된 제품 | 폐기
45 | T27 | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 폐기된 제품 | 폐기
46 | T27 | INSPECT LIGHT PASS | RULE_RETEST | 거절 | 폐기된 제품 | 폐기
47 | T28_NO_RESULT | REGISTER | RULE_RECIPE | 허용 |  | 등록
48 | T28_NO_RESULT | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
49 | T28_NO_RESULT | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
50 | T28_NO_RESULT | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
51 | T28_NO_RESULT | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 미해결 FAIL 없음 | 공정 진행 중(P3 완료)
52 | T28_PASS | REGISTER | RULE_RECIPE | 허용 |  | 등록
53 | T28_PASS | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
54 | T28_PASS | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
55 | T28_PASS | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
56 | T28_PASS | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
57 | T28_PASS | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 미해결 FAIL 없음 | 공정 진행 중(P3 완료)
58 | T28_OPEN | REGISTER | RULE_RECIPE | 허용 |  | 등록
59 | T28_OPEN | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
60 | T28_OPEN | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
61 | T28_OPEN | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
62 | T28_OPEN | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
63 | T28_OPEN | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
64 | T28_OPEN | RETEST_REQUEST LEAK | RULE_RETEST | 거절 | 이미 열린 재검사 요청 | 보류
65 | T28_MODEL_B | REGISTER | RULE_RECIPE | 허용 |  | 등록
66 | T28_MODEL_B | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
67 | T28_MODEL_B | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
68 | T28_MODEL_B | RETEST_REQUEST FINAL | RULE_RECIPE | 거절 | 제품 레시피에 없는 검사 FINAL | 공정 진행 중(P2 완료)
69 | T28_UNREGISTERED | RETEST_REQUEST LEAK | RULE_PRESERVE | 거절 | 미등록 제품 | 미등록
70 | T28_FORMAT | REGISTER | RULE_RECIPE | 허용 |  | 등록
71 | T28_FORMAT | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
72 | T28_FORMAT | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
73 | T28_FORMAT | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
74 | T28_FORMAT | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
75 | T28_FORMAT | RETEST_REQUEST LEAK PASS | RULE_PRESERVE | 거절 | RETEST_REQUEST의 result는 빈칸이어야 함 | 보류
76 | T29 | REGISTER | RULE_RECIPE | 허용 |  | 등록
77 | T29 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
78 | T29 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
79 | T29 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
80 | T29 | INSPECT LEAK PASS | RULE_NOT_DONE | 허용 |  | 공정 진행 중(P3 완료)
81 | T29 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
82 | T29 | P5 | RULE_SEQ | 허용 |  | 검사 대기
83 | T29 | INSPECT LIGHT FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
84 | T29 | INSPECT FINAL FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
85 | T29 | RETEST_REQUEST LIGHT | RULE_RETEST | 허용 |  | 보류
86 | T29 | INSPECT LIGHT PASS | RULE_RETEST | 허용 |  | 보류
87 | T29 | RETEST_REQUEST FINAL | RULE_RETEST | 허용 |  | 보류
88 | T29 | INSPECT FINAL PASS | RULE_RETEST | 허용 |  | 레시피 모의 흐름 완료
89 | T30 | REGISTER | RULE_RECIPE | 허용 |  | 등록
90 | T30 | P1 | RULE_SEQ | 허용 |  | 공정 진행 중(P1 완료)
91 | T30 | P2 | RULE_SEQ | 허용 |  | 공정 진행 중(P2 완료)
92 | T30 | P3 | RULE_SEQ | 허용 |  | 공정 진행 중(P3 완료)
93 | T30 | INSPECT LEAK FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
94 | T30 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
95 | T30 | INSPECT LEAK FAIL | RULE_RETEST | 허용 |  | 보류
96 | T30 | RETEST_REQUEST LEAK | RULE_RETEST | 허용 |  | 보류
97 | T30 | INSPECT LEAK PASS | RULE_RETEST | 허용 |  | 공정 진행 중(P3 완료)
98 | T30 | P4 | RULE_SEQ | 허용 |  | 공정 진행 중(P4 완료)
99 | T30 | P5 | RULE_SEQ | 허용 |  | 검사 대기
100 | T30 | INSPECT LIGHT FAIL | RULE_FAIL_HOLD | 허용 |  | 보류
101 | T30 | RETEST_REQUEST LIGHT | RULE_RETEST | 허용 |  | 보류
102 | T30 | INSPECT LIGHT PASS | RULE_RETEST | 허용 |  | 검사 대기

[제품별 최종 상태]
product_id | model | 최종 상태 | 미완료 이유 | history
T23 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL(재검사 요청됨); LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@5 → 요청@6
T24 | A | 레시피 모의 흐름 완료 |  | LEAK: FAIL@12 → 요청@13 → PASS@14(재검사 1); LIGHT: PASS@17; FINAL: PASS@18
T25 | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@23
T26 | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@29 → 요청@30 → FAIL@31(재검사 1) → 요청@33 → PASS@34(재검사 2)
T27 | A | 폐기 | LEAK 재검사 한도 2회 초과 FAIL로 폐기 | LEAK: FAIL@39 → 요청@40 → FAIL@41(재검사 1) → 요청@42 → FAIL@43(재검사 2)
T28_NO_RESULT | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시 | 
T28_PASS | A | 공정 진행 중(P3 완료) | P4 미완료; P5 미완료; LIGHT 미실시; FINAL 미실시 | LEAK: PASS@56
T28_OPEN | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL(재검사 요청됨); LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@62 → 요청@63
T28_MODEL_B | B | 공정 진행 중(P2 완료) | P3 미완료; P4 미완료; LEAK 미실시; LIGHT 미실시 | 
T28_FORMAT | A | 보류 | P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시 | LEAK: FAIL@74
T29 | A | 레시피 모의 흐름 완료 |  | LEAK: PASS@80; LIGHT: FAIL@83 → 요청@85 → PASS@86(재검사 1); FINAL: FAIL@84 → 요청@87 → PASS@88(재검사 1)
T30 | A | 검사 대기 | FINAL 미실시 | LEAK: FAIL@93 → 요청@94 → FAIL@95(재검사 1) → 요청@96 → PASS@97(재검사 2); LIGHT: FAIL@100 → 요청@101 → PASS@102(재검사 1)

[규칙 ID별 거절 건수]
규칙 ID | 거절 건수
RULE_RECIPE | 1
RULE_SEQ | 0
RULE_INSP_PRE | 0
RULE_NOT_DONE | 0
RULE_FAIL_HOLD | 1
RULE_PRESERVE | 4
RULE_RETEST | 6

저장 파일:
reports/sample_events_retest_rows.csv
reports/sample_events_retest_products.csv
reports/sample_events_retest_rejections.csv
```
Exit code: 0; stdout byte-identical to starting baseline.
- reports/sample_events_retest_rows.csv: byte-identical; SHA-256 6674e813936d5d62192d2742a90de18c78ebeddb11c90104f218df4034249963
- reports/sample_events_retest_products.csv: byte-identical; SHA-256 3f6e9f3a24fb758f019c472684a07c87bcec24d0fa9bbf27e54f7eda906afe7e
- reports/sample_events_retest_rejections.csv: byte-identical; SHA-256 d3d6d4f485ef95a92a3c952f8342eb2f0e1325e886a85885c430ac6f975d5d28

Protected-file command: `git diff --exit-code 4947d12 -- src/rules.py tests/test_rules.py tests/test_recipe.py tests/test_retest.py handoff/tasks.md handoff/decisions.md handoff/reviews CLAUDE.md .claude AGENTS.md`
```text
```
Exit code: 0 (no diff).

Whitespace check: `git diff --check 4947d12 -- . :(exclude)handoff/gpt-log.md`
```text
```
Exit code: 0.

## 최종 검토·정리
- ce-work mode:return-to-caller: 다섯 단위의 구현·로컬 검증을 완료하고 주 에이전트가 단순화·리뷰·교훈 판단을 이어받았다. 실행 엔진은 native, 별도 외부 실행 run/브랜치/PR/CI 없음. 각 동작 단위의 기존 테스트 확인·추가 테스트·구현 전 실패·전체 검증·커밋 근거는 위 단계별 원문에 있다. 문서 단위는 새 테스트를 만들지 않고 회귀 및 CSV 예제 구조로 검증했다.
- ce-simplify-code mode:pipeline: 재사용 리뷰는 독립 에이전트가 완료(실익 있는 지적 없음). 품질·효율 리뷰 에이전트 두 개는 사용량 제한으로 실패하여 주 에이전트가 같은 persona 기준으로 품질·효율·테스트 가치·주석 검토를 직접 수행했다. 기존 v1과 신규 설정 검증의 공통화는 보호 범위 확대·회귀 위험에 비해 이익이 없어 수행하지 않았다. 적용: 재사용 0·품질 0·효율 0·테스트 0·주석 0. tests/test_equipment.py는 검증 근거 파일로 보호했고 테스트 설명 주석도 바꾸지 않았다. 프로젝트에 별도 lint/typecheck 설정 없음; 실제 검증은 unittest와 CLI 바이트 비교다.
- 형식 검사: `git diff --check 4947d12 -- . ':(exclude)handoff/gpt-log.md'` 통과. gpt-log는 터미널 출력 원문에 빈 열 뒤 공백·CRLF가 있어 의도적으로 제외했다. 최초 전체 diff 검사의 실패는 그 원문 공백뿐이며 코드·데이터의 오류가 아니다. 원문 공백은 지우지 않았다.
- ce-compound mode:non-interactive 판단: 정지·재검사 분리와 부분 창·누적 집계 해석은 코드·테스트·README 및 이 로그에서 복원 가능하다. 별도 해결 기록이 없으면 재발하거나 상당한 재조사를 요구하는 비자명한 검증된 문제는 없어 문서를 추가하지 않는다. Documentation skipped — durable-learning precondition not met.

### 명세 이견(고정 샘플의 T39 설비)
- 기대표 T39는 LEAK-2를 사용하며 독립 T39 테스트는 그대로 재현·통과한다. 한 번의 고정 샘플 실행에서는 LEAK-2가 T33에서 이미 정지하고 재가동은 범위 밖이므로, 뒤에 이어지는 T39 샘플은 LEAK-1로 같은 거절 미집계·정지 판정을 재현했다. 샘플의 이 차이를 README에도 명시했다. 판정 규칙·기대표·기존 테스트는 바꾸지 않았다.

## 완료 보고 — v2 3단계 T33–T41

- 구현 완료: 설비 파일 검증, 최초 검사만 집계하는 최근 창 정지, 정지 후 최초·재검사 거절과 열린 요청 보존, 7열 CLI, 보고서 4종·설비 표시·SHA-256, 고정 샘플, README.
- 기대표 대조: T33 원인 세 행 허용·세 번째 뒤 정지 / T34 정지 설비 거절 후 다른 설비 허용 / T35 거절 시 요청 유지 후 대체 설비 재검사 1 PASS / T36 제품 폐기·설비 최초 FAIL 1건만 집계 / T37 최근 3건 중 FAIL 1건으로 가동 / T38 네 거절의 전체 상태 불변 / T39 시점 거절 미집계·네 번째 검사 입력 뒤 정지 / T40 설정 오류 코드 3·위치·보고서 미생성 / T41 옵션·헤더 코드 2 및 출력 재현성: 독립 단위 테스트에서 모두 일치.
- 실행 원문: 위 「착수·계획·회귀 기준」에 시작 전체 54개 테스트와 기존 샘플 3종 CLI 원문·9개 보고서 SHA-256, 각 ①–⑤ 항목에 단계별 테스트 원문, 「최종 v1 회귀」·「최종 v2 1단계 회귀」·「최종 v2 2단계 회귀」·「최종 v2 3단계」에 각각 12/26/16/19개 통과 원문이 있다. `py -m unittest discover -s tests`의 마지막 전체 실행은 73개 OK다.
- 샘플 실제 실행: `py -m src.main data/sample_events_equipment.csv --recipe recipes/lamp_models_retest.json --equipment recipes/equipment.json` 종료 코드 0. 전체 터미널 출력 원문을 ④ 단계 위에 기록했다. 94행·허용 87·거절 7·17개 제품. 보고서 4종은 생성 후 별도 임시 폴더 실행과 바이트 비교까지 통과했다.
- 최종 회귀: 위 Final regression command 3종의 실제 stdout 원문과 보고서별 SHA-256을 기록했다. 기존 보고서 9개는 체크아웃 파일과 바이트 동일하고, 터미널 출력 3종도 착수 시점과 바이트 동일하다. 기존 테스트·기대표를 결과에 맞춰 고치지 않았다.
- 해석·가정: 부분 창에서 임계치 도달 즉시 정지, counted_results/fail_count는 누적 최초 결과 집계다. 명세 이견: 고정 샘플 T39의 설비만 LEAK-1로 구성한 이유를 바로 위에 공개했다. 독립 T39는 기대표의 LEAK-2를 그대로 검증한다. 그 밖의 판정 차이 없음.
- 최종 코드 리뷰: ce-code-review focused, 주 에이전트 correctness와 별도 native adversarial 검토에서 재현 결함·남은 지적 없음. 다른 제공자에게 코드를 전송하지 않았다. 독립 리뷰 반환 원문: `Independent equipment accounting/order/rejection invariant checks: 221772`; 유효 window/fails 210개 조합 × 시드 10개에서 불변식 검사 통과. 별도 전체 unittest도 `Ran 73 tests in 9.892s`, `OK`, 종료 코드 0. 이는 독립 검토자가 반환한 근거이며 주 에이전트 실행 원문과 구분한다.
- 검토 receipt: `C:/Users/PC/AppData/Local/Temp/ce-equipment-review-k457aao5/review.json`; native 구현 반환: 같은 폴더 `ce-work-return.json`. 프로젝트 기록은 이 로그가 기준이다.
- 보존 확인: 보호 파일 및 AGENTS.md의 `git diff --exit-code 4947d12 -- ...` 출력 없음·종료 0. handoff/tasks.md·decisions.md·reviews/·CLAUDE.md·.claude/·src/rules.py·기존 테스트 3개·기존 보고서 9개 무수정. main에서만 작업했고 새 브랜치·원격 설정 변경·패키지 설치·push·PR·배포를 하지 않았다.
- 커밋: 회귀 기준 `4d5ab04` → ① T40 `2c528ec` → ② T33–T39 `1cf25d6` → ③ T41 `7ddefae` → ④ T33–T41 `04e6168` → ⑤ T33–T41 `5d5786d` → 이 완료 보고 커밋. 각 단계 전체 테스트 통과 뒤 관련 경로만 커밋했다.

## v2 4단계 착수·회귀 기준 (2026-10-18)

- 현행 작업 상태 **사용자 확정** 확인. main 유지, 시작 작업 트리 깨끗함, 기존 로컬 선행 커밋 1개 보존.
- 관련 해결 기록: `.compound-engineering/config.yaml` 및 `docs/solutions/` 없음.
- 확정 명세의 구현 순서·기대표를 계획으로 재사용한다(계획 중복 생성·원본 변경 없음). 실행은 ce-work mode:return-to-caller의 native 경로, 통합·커밋·최종 리뷰는 주 에이전트 담당.
- ① 생성기/meta T42–43 → ② summary/사유 코드 T45·46·49 → ③ trace T47–48 → ④ 불변식 T44 → ⑤ 생성 산출물 → ⑥ README. 각 단계 전체 테스트와 범위별 커밋.
- 리뷰004: L1 반영(명시적 설비 모드·추가 보고서 별도 경로). L2 보류(재가동 제외、호출부 정지 거절 보존). L3 기존 README 설명·독립 T39 테스트로 이미 반영. L4 보류(사용자 문서 수정 금지). L5 보류(이전 단계의 역사적 범위 설명、이번 범위와 무관).

### 수정 전 실제 실행·출력 원문

```text
$ py -m unittest discover -s tests
.........................................................................
----------------------------------------------------------------------
Ran 73 tests in 9.103s

OK
exit_code=0
$ py -m src.main data/sample_events.csv 
exit_code=0; checked_reports=3; byte_identical=True
$ py -m src.main data/sample_events_v2.csv --recipe recipes/lamp_models.json
exit_code=0; checked_reports=3; byte_identical=True
$ py -m src.main data/sample_events_retest.csv --recipe recipes/lamp_models_retest.json
exit_code=0; checked_reports=3; byte_identical=True
$ py -m src.main data/sample_events_equipment.csv --recipe recipes/lamp_models_retest.json --equipment recipes/equipment.json
exit_code=0; checked_reports=4; byte_identical=True
```

### 실행 기록: stage1-tests

명령·출력 원문: [run-logs/stage1-tests.txt](run-logs/stage1-tests.txt)

```text
$ py -m unittest discover -s tests
...........................................................................
----------------------------------------------------------------------
Ran 75 tests in 10.494s

OK

exit_code=0; elapsed_seconds=10.692279
```

### 생성기 구현의 해석·검증 근거

- T42·T43 테스트를 구현 전에 추가하고 `py -m unittest discover -s tests -p test_generate.py`의 `ModuleNotFoundError: No module named 'src.generate'` / `FAILED (errors=1)`을 관측했다. 구현 후 전체 75개 통과(위 원문).
- 오류 수는 `floor(정상 행 수 × 0.03)`로 정수화한다. 종류별 차이는 최대 1이며 나머지 종류와 삽입 위치는 같은 `random.Random(seed)` 흐름에서 고른다. 기본 시드·확률은 변경하지 않았다.
- 설정의 recipe/equipment 경로는 generator.json의 디렉터리를 기준으로 해석한다. 출력 위치·시각·환경은 메타 내용에 넣지 않는다.
- 정상 행을 먼저 라운드로빈 생성하고 최초 결과만 같은 정지 규칙에 반영한다. 이후 각 물리 위치의 상태에서 반드시 거절되는 오류 행을 추가한다. 오류 후보 위치 선정에도 정상 판정 상태를 사용하므로 정상 행은 바뀌지 않는다.
- 명세 이견(실측, 미해결): seed 42·500개는 완료 497·보류 3·폐기 0, LEAK-2 정지. 폐기 1개 이상이라는 빈 검증 조건을 충족하지 않는다. 정상/고장 FAIL 2%/30%, 요청 70%, 다른 설비 우선, 재검사 한도 2를 그대로 구현했고 난수 소비를 폐기 확보 목적으로 바꾸지 않았다. T44에서 실패를 숨기지 않고 유지한다. 사용자의 지시대로 나머지 구현·검증·단계별 커밋은 계속한다.
- 해석: 중간 검사 설비가 모두 정지하면 생성은 해당 검사에서 끝난다. 기존 판정기의 상태 우선순위는 보존하므로 그 제품은 공정 진행 중으로 표시될 수 있다. 미실시 검사 수와 미완료 이유를 summary/trace에 남긴다.

### 실행 기록: stage2-tests

명령·출력 원문: [run-logs/stage2-tests.txt](run-logs/stage2-tests.txt)

```text
$ py -m unittest discover -s tests
.......................................................................................
----------------------------------------------------------------------
Ran 87 tests in 10.996s

OK

exit_code=0; elapsed_seconds=11.203095
```

### summary 구현 근거·해석

- T45 fixture의 수기 기대값을 구현 전에 테스트에 기록했다. 최초 결과 5/FAIL 1=`0.2000`, 전체 결과 6/FAIL 1=`0.1667`, FPY 1/4=`0.2500`, 완료 2·검사 대기 1·등록 1, 미실시 검사 5, 거절 2.
- 구현 전 `py -m unittest discover -s tests -p test_summary.py`: `ModuleNotFoundError: No module named 'src.summary'`, `Ran 1 test in 0.000s`, `FAILED (errors=1)`. 구현 후 집중 12개 통과, 통합 전체 87개 통과(위 원문).
- 상세 코드 28종은 `src/reason_codes.py`의 (규칙 ID, 정확한 문구/동적 ID 템플릿) 고정 표로 대응한다. 동적 문구는 실제 입력 ID 또는 레시피 공정으로 재구성한 문구만 일치시킨다. 미등록 문구는 summary 실패로 처리한다.
- 최초/전체 지표는 허용된 결과만 센다. 미실시는 검사별·전체에 표시하고, 아직 배정되지 않은 설비로 귀속할 수 없어 설비별 미실시 칸은 비운다. 정지 원인은 최초 결과 창의 물리 행 인덱스와 seq·제품 ID를 별도로 보관한다.
- 품질 파레토는 최초 FAIL 0·재검사 FAIL 양수인 조합도 함께 표시한다. 정지 설비 거절은 별도 절이며 알려진 나머지 사유는 입력 오류 파레토에 포함된다. unknown은 실패하므로 현재 other_rejections는 0이다.

### 실행 기록: stage3-tests

명령·출력 원문: [run-logs/stage3-tests.txt](run-logs/stage3-tests.txt)

```text
$ py -m unittest discover -s tests
...........................................................................................
----------------------------------------------------------------------
Ran 91 tests in 11.542s

OK

exit_code=0; elapsed_seconds=11.747833
```

### trace 검증 근거·해석

- T47·T48 테스트를 먼저 추가하고 `py -m unittest discover -s tests -p test_summary.py`에서 `ModuleNotFoundError: No module named 'src.trace'` / `FAILED (errors=1)`을 관측했다. 구현 후 전체 91개 통과.
- T34 행 26–31만 원래 물리 순서로 표시하고 seq 30의 정지 설비 거절에 LEAK-2 정지 행 25/T33_P3 및 FAIL 행 14/T33_T35_A, 25/T33_P3를 연결했다. 중복·감소 seq 테스트도 물리 행 인덱스 26–31 및 원인 인덱스 14·25로 확인했다.
- summary·trace를 모두 먼저 계산·검증한 뒤 파일을 저장한다. 요청한 trace 중 하나라도 입력에 없으면 종료 2이며 기존 4종 포함 보고서를 새로 만들지 않는다. 반복 --trace, summary 동시 사용과 기존 보고서 바이트 보존을 확인했다.
- 입력에 행은 있으나 등록이 거절된 ID도 추적할 수 있으며 마지막 상태는 미등록으로 표시한다. 파일명에 쓸 수 없는 제품 ID 문자는 percent encoding하여 reports/ 밖 경로가 되지 않게 한다. 일반 제품 ID는 그대로 쓴다.

### 실행 기록: stage4-tests

명령·출력 원문: [run-logs/stage4-tests.txt](run-logs/stage4-tests.txt)

```text
$ py -m unittest discover -s tests
T44 seed=42 products=500 generation_seconds=0.130818 judgment_analysis_seconds=0.069414
T44 seed=7 products=200 generation_seconds=0.043801 judgment_analysis_seconds=0.024872
T44 seed=42 all_rows_deepcopy_invariant_seconds=34.836820
T44 seed=7 all_rows_deepcopy_invariant_seconds=5.670792
................................................................................................
======================================================================
FAIL: test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors (test_generate.GeneratedInvariantTests) (requirement='discarded')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_generate.py", line 157, in test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors
    self.assertGreater(count, 0, "명세 이견: seed42 빈 검증 조건 미충족: " + requirement)
AssertionError: 0 not greater than 0 : 명세 이견: seed42 빈 검증 조건 미충족: discarded

----------------------------------------------------------------------
Ran 97 tests in 53.877s

FAILED (failures=1)

exit_code=1; elapsed_seconds=54.106285
```

### 실행 기록: stage4-simplify-tests

명령·출력 원문: [run-logs/stage4-simplify-tests.txt](run-logs/stage4-simplify-tests.txt)

```text
$ py -m unittest discover -s tests -p test_generate.py -k GeneratorTests
..
----------------------------------------------------------------------
Ran 2 tests in 0.501s

OK

exit_code=0; elapsed_seconds=0.707469
```

### T44 실제 결과·의견과 간소화

- 전체 97개 중 실패 1개: `test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors`, `discarded=0`. 시드 42의 완료·보류·정지 설비·5종 오류 양수 조건은 충족했다. 시드 42/500개와 7/200개 각각 CSV·meta 및 기존 4종+summary+trace의 바이트 재현성, 완료 상태, 정지/폐기 뒤 허용 금지, 거절 집계 분해와 모든 거절의 전체 제품·설비 상태 불변 검사는 통과했다.
- 500개 생성 0.130818초, 판정+분석 0.069414초, 모든 물리 행 deepcopy 불변식 검사 34.836820초. 200개도 deepcopy 검사 5.670792초로 수행했다. 500개 검증을 생략하지 않았다. 전체 테스트 53.877초. 실행 시간은 이 PC의 해당 실행 관측치다.
- **명세 이견 유지:** 재검사 2회의 FAIL까지 요구하는 폐기는 정상 FAIL 2%, 다른 설비 우선 및 빠른 고장 설비 정지 조건에서 희소하다. seed42의 결과가 0인 사실을 숨기지 않았다. 빈 검증 테스트·기대표·기존 테스트·시드·확률은 수정하지 않았다. 사용자가 실패 유지 및 후속 구현·단계별 커밋을 명시했으므로 이 알려진 실패를 포함해 커밋한다.
- ce-simplify-code mode:pipeline의 5개 렌즈 완료. 코드 중복 1건 반영(오류 코드 tuple을 고정 사유 코드 모듈에서 재사용), 중복 설명 주석 1건 삭제, 품질·효율·테스트 변경 없음. 두 proof-test와 기존 4개 테스트 보존. 설정된 별도 lint/typecheck 도구 없음.
- 간소화 전후 seed42 CSV+meta 결합 SHA-256 모두 `88275405bfb6cda618f01e5bef6844c3610f56bb668286cbc3ebaf33f0a2ba3d`, 집중 생성기 테스트 2개 통과(위 원문). 값·순서와 난수 소비가 변하지 않음을 확인했다.

### 실행 기록: stage5-generate

명령·출력 원문: [run-logs/stage5-generate.txt](run-logs/stage5-generate.txt)

```text
$ py -m src.generate --seed 42 --products 500 --out data/generated/gen_seed42.csv
생성: data/generated/gen_seed42.csv
{
  "seed": 42,
  "products": 500,
  "generator_version": "1.0.0",
  "sha256": {
    "config": "d28b9b34edd1aaa43cda8ad5c927d433b45eb6ca70daad8e45b60a9de692625b",
    "recipe": "438229b58c9e8bc4a9f464704c9ace956150e33920fa36f0441add7f354ca7ac",
    "equipment": "fc7e9b06b007846199847ad06d0d9381ca17ae039557c1739816eb2155afbbab"
  },
  "normal_rows": 4020,
  "rows": 4140,
  "injected_errors": {
    "SEQ_SKIP": 24,
    "PRESERVE_BAD_RESULT": 24,
    "PRESERVE_DUP_RESULT": 24,
    "EQUIP_UNKNOWN": 24,
    "RECIPE_UNKNOWN_STEP": 24
  },
  "injection_rate": 0.03
}

exit_code=0; elapsed_seconds=0.260631
```

### 실행 기록: stage5-summary-trace

명령·출력 원문: [run-logs/stage5-summary-trace.txt](run-logs/stage5-summary-trace.txt)

`py -m src.main data/generated/gen_seed42.csv --recipe recipes/lamp_models_retest.json --equipment recipes/equipment_generated.json --summary --trace GEN_0005` — 종료 0, 0.314607초. 전체 stdout·stderr는 위 원문 파일에 보존.

### 실행 기록: stage5-tests

명령·출력 원문: [run-logs/stage5-tests.txt](run-logs/stage5-tests.txt)

```text
$ py -m unittest discover -s tests
T44 seed=42 products=500 generation_seconds=0.111544 judgment_analysis_seconds=0.061856
T44 seed=7 products=200 generation_seconds=0.044143 judgment_analysis_seconds=0.025246
T44 seed=42 all_rows_deepcopy_invariant_seconds=35.363208
T44 seed=7 all_rows_deepcopy_invariant_seconds=5.705319
................................................................................................
======================================================================
FAIL: test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors (test_generate.GeneratedInvariantTests) (requirement='discarded')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_generate.py", line 157, in test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors
    self.assertGreater(count, 0, "명세 이견: seed42 빈 검증 조건 미충족: " + requirement)
AssertionError: 0 not greater than 0 : 명세 이견: seed42 빈 검증 조건 미충족: discarded

----------------------------------------------------------------------
Ran 97 tests in 55.091s

FAILED (failures=1)

exit_code=1; elapsed_seconds=55.292803
```

### 생성 샘플·보고서 확인

- `data/generated/gen_seed42.csv` 4,140행 및 `.meta.json`, `reports/gen_seed42_{rows,products,rejections,equipment,summary}.csv`, 대표 `gen_seed42_trace_GEN_0005.csv` 생성. 실행 명령과 전체 stdout·stderr는 위 stage5 원문 파일에 보존했다(대량 행 출력은 gpt-log에 복제하지 않고 원문 링크).
- summary 실측: 등록 500, 완료 497·보류 3·폐기 0, FPY 482/500=`0.9640`, 최초 FAIL 18/1246=`0.0144`, 전체 FAIL 18/1261=`0.0143`, 거절 검사 72, 미실시 검사 2. 입력 오류 120, 정지 설비 거절 0, 기타 0. 주입 120/4020=`0.0299`, 최종 거절 120/4140=`0.0290`.
- LEAK-2는 seq 1556/GEN_0012에서 정지했으며 창의 FAIL 원인은 1549/GEN_0005, 1556/GEN_0012다. 생성기가 정지 설비를 피했으므로 이 샘플의 정지 후 거절은 0이다. 교차 제품 정지 거절 trace 자체는 T47 고정 샘플에서 검증했다.
- 대표 trace GEN_0005는 LEAK 최초 FAIL@1549[LEAK-2] → 요청@2063 → PASS@2575[LEAK-1](재검사 1) 뒤 LIGHT PASS@3861로 완료한 사례다.
- 단계5 전체 테스트 97개 중 알려진 폐기 양수 조건 1개만 실패. 보호 파일 diff는 출력 없음. 기본값·입력 확률·기대표를 바꾸지 않았다.

### 실행 기록: final-verification

명령·출력 원문: [run-logs/final-verification.txt](run-logs/final-verification.txt)

```text
$ py -c exec(compile(open(r'C:\Users\PC\AppData\Local\Temp\stage4_final_verify.py','rb').read(),'stage4_final_verify','exec'))
sample_events: exit_code=0; byte_identical_reports=3
sample_events_v2: exit_code=0; byte_identical_reports=3
sample_events_retest: exit_code=0; byte_identical_reports=3
sample_events_equipment: exit_code=0; byte_identical_reports=4
seed42: exit_code=0; byte_identical_csv_meta=2; byte_identical_reports=6
protected_files_diff=empty
branch=main; pushes=none

exit_code=0; elapsed_seconds=1.601617
```

### 실행 기록: stage6-tests

명령·출력 원문: [run-logs/stage6-tests.txt](run-logs/stage6-tests.txt)

```text
$ py -m unittest discover -s tests
T44 seed=42 products=500 generation_seconds=0.119105 judgment_analysis_seconds=0.065684
T44 seed=7 products=200 generation_seconds=0.044865 judgment_analysis_seconds=0.025830
T44 seed=42 all_rows_deepcopy_invariant_seconds=38.522261
T44 seed=7 all_rows_deepcopy_invariant_seconds=6.159791
................................................................................................
======================================================================
FAIL: test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors (test_generate.GeneratedInvariantTests) (requirement='discarded')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_generate.py", line 157, in test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors
    self.assertGreater(count, 0, "명세 이견: seed42 빈 검증 조건 미충족: " + requirement)
AssertionError: 0 not greater than 0 : 명세 이견: seed42 빈 검증 조건 미충족: discarded

----------------------------------------------------------------------
Ran 97 tests in 58.413s

FAILED (failures=1)

exit_code=1; elapsed_seconds=58.613959
```

### 실행 기록: seed42-timing

명령·출력 원문: [run-logs/seed42-timing.txt](run-logs/seed42-timing.txt)

```text
$ py -c exec(compile(open(r'C:\Users\PC\AppData\Local\Temp\stage4_timing.py','rb').read(),'stage4_timing','exec'))
T44 seed=42 products=500 generation_seconds=0.108255 judgment_analysis_seconds=0.061041
T44 seed=7 products=200 generation_seconds=0.043860 judgment_analysis_seconds=0.024074
T44 seed=42 all_rows_deepcopy_invariant_seconds=36.688034
seed42_products500_invariants_1_to_6_seconds=37.555677
tests=6; failures=1; errors=0; skipped=0
test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors (test_generate.GeneratedInvariantTests) (requirement='discarded')
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_generate.py", line 157, in test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors
    self.assertGreater(count, 0, "명세 이견: seed42 빈 검증 조건 미충족: " + requirement)
AssertionError: 0 not greater than 0 : 명세 이견: seed42 빈 검증 조건 미충족: discarded


exit_code=1; elapsed_seconds=38.021873
```

### 실행 기록: trace-case-fix-tests

명령·출력 원문: [run-logs/trace-case-fix-tests.txt](run-logs/trace-case-fix-tests.txt)

```text
$ py -m unittest discover -s tests -p test_summary.py
.................
----------------------------------------------------------------------
Ran 17 tests in 2.216s

OK

exit_code=0; elapsed_seconds=2.413501
```

### 실행 기록: final-tests

명령·출력 원문: [run-logs/final-tests.txt](run-logs/final-tests.txt)

```text
$ py -m unittest discover -s tests
T44 seed=42 products=500 generation_seconds=0.118045 judgment_analysis_seconds=0.069694
T44 seed=7 products=200 generation_seconds=0.049292 judgment_analysis_seconds=0.028131
T44 seed=42 all_rows_deepcopy_invariant_seconds=37.744879
T44 seed=7 all_rows_deepcopy_invariant_seconds=5.942913
.................................................................................................
======================================================================
FAIL: test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors (test_generate.GeneratedInvariantTests) (requirement='discarded')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\tests\test_generate.py", line 157, in test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors
    self.assertGreater(count, 0, "명세 이견: seed42 빈 검증 조건 미충족: " + requirement)
AssertionError: 0 not greater than 0 : 명세 이견: seed42 빈 검증 조건 미충족: discarded

----------------------------------------------------------------------
Ran 98 tests in 57.629s

FAILED (failures=1)

exit_code=1; elapsed_seconds=57.847985
```

### 실행 기록: final-byte-verification

명령·출력 원문: [run-logs/final-byte-verification.txt](run-logs/final-byte-verification.txt)

```text
$ py -c exec(compile(open(r'C:\Users\PC\AppData\Local\Temp\stage4_final_verify.py','rb').read(),'stage4_final_verify','exec'))
sample_events: exit_code=0; byte_identical_reports=3
sample_events_v2: exit_code=0; byte_identical_reports=3
sample_events_retest: exit_code=0; byte_identical_reports=3
sample_events_equipment: exit_code=0; byte_identical_reports=4
seed42: exit_code=0; byte_identical_csv_meta=2; byte_identical_reports=6
protected_files_diff=empty
external_changes_byte_preserved=CLAUDE.md,tools/review-loop.ps1
gpt_log_original_prefix_byte_preserved=True
branch=main; pushes=none

exit_code=0; elapsed_seconds=1.640875
```

### 재개·최종 보완 (2026-10-18)

- 중단 전 리뷰에서 Windows의 `p`/`P` trace 파일명 충돌이 발견됐다. **반영:** 전체 입력 제품 ID의 인코딩 파일명이 대소문자 무시 시 충돌할 때만 `!` + 원본 UTF-8 hex 접미사로 분리한다. 일반 ID의 기존 파일명은 유지하고 요청 부분집합·파일시스템 상태에 영향을 받지 않게 했다.
- 회귀 테스트를 먼저 추가해 `py -m unittest discover -s tests -p test_summary.py -k case_colliding`에서 `AssertionError: 1 != 2`, `Ran 1 test in 0.190s`, `FAILED (failures=1)`을 관측했다. 수정 후 집중 17개 통과(원문 trace-case-fix-tests), 커밋 `ffbe89a`.
- 재개 후 최종 전체 테스트는 **98개 중 97개 통과·1개 실패**, 57.629초, 종료 코드 1이다. 실패는 여전히 T44의 `discarded=0` 빈 검증 조건뿐이며 skip이나 expectedFailure로 감추지 않았다. 최종 원문은 final-tests에 있다.
- 500개만 별도로 수행한 불변식 1–6 측정: 생성 0.108255초, 판정+분석 0.061041초, 불변식 6개 전체 37.555677초(그중 모든 행 deepcopy 36.688034초). 생성/최초 판정은 불변식 타이머 전에 수행했다. 이 별도 측정도 폐기 빈 검증 1개 실패이며 오류·skip은 0이다. 원문 seed42-timing 참조.
- README의 생성기·분석·추적 절에 실행법, 지표 정의, 상세 코드 28종, 가정과 한계, 실제 시드42 수치, 실패 조건, trace 파일명 충돌 처리까지 기록했다. 보호 대상 `src/rules.py`·기존 테스트 4개·tasks·decisions·reviews·.claude는 그대로다.
- 재개 당시 작업 범위 밖 `CLAUDE.md`, `tools/review-loop.ps1`에 새 변경이 관측됐다. 두 파일은 수정·스테이징·커밋하지 않는다. 재개 시점 SHA-256과 최종 파일이 바이트 동일함을 확인했다(final-byte-verification). 이를 이번 구현의 변경으로 포함하지 않는다. 원래 gpt-log 내용도 작업 전 원본 바이트를 prefix로 그대로 보존했다.
- 최종 별도 임시 디렉터리에서 기존 샘플 4종의 13개 보고서를 재생성하고 체크아웃 파일과 바이트 동일함을 확인했다. 새 seed42 CSV·meta 2개와 보고서 6개도 같은 방식으로 동일했다. main 유지, push·원격 변경·설치 없음.

## v2 4단계 완료 보고 (2026-10-18)

현행 절 전체의 생성기·meta·summary·상세 사유 코드·trace·불변식 테스트·생성 샘플·보고서·README 구현을 마쳤다. **검증은 전체 통과가 아니다. 최종 98개 중 97개 통과·1개 실패이며, T44 빈 검증의 폐기 양수 조건이 미충족이다.** 이 실패를 유지하라는 명세에 따라 기대표·기존 테스트·시드·확률을 바꾸지 않고 실제 결과를 보고한다.

### 기대표와 불변식 대조

| ID | 실제 결과 |
| --- | --- |
| T42 | 충족: seed42 CSV·meta 바이트 재현, 시드·제품 수·3종 SHA-256·버전·행 수·5종 주입 개수 기록 |
| T43 | 충족: seed42와 seed43 CSV가 다름 |
| T44 | **불일치:** 불변식 1–5는 seed42/500개와 seed7/200개에서 통과. 불변식 6의 폐기 1개 이상은 실제 0개로 실패. 완료 497·보류 3·정지 설비 1·5종 오류 각 24로 나머지 양수 조건은 충족 |
| T45 | 충족: 수기 fixture 4제품, 최초 FAIL 1/5=`0.2000`, 전체 FAIL 1/6=`0.1667`, FPY 1/4=`0.2500`, 거절 2, 미실시 5와 파레토 일치 |
| T46 | 충족: LEAK-2 정지 seq25, 원인 FAIL seq14·25, 정지 설비 거절 2건을 입력 오류 파레토에서 분리 |
| T47 | 충족: T34의 행만 물리 순서로 표시, 정지 행/FAIL 원인의 다른 제품 ID 연결. seq 중복·감소, 반복 trace, Windows p/P 파일 보존도 검사 |
| T48 | 충족: 없는 ID 또는 비설비 summary/trace는 종료 2, 보고서 미생성. 여러 ID 중 하나만 없어도 저장 전에 중단 |
| T49 | 충족: 인위적 미등록 이유 문구에서 summary 실패 |
| T50 | 충족: 기존 샘플 4종을 추가 옵션 없이 재실행, 기존 보고서 13개와 바이트 동일 |

기존 T1–T41 고정 테스트 73개는 수정하지 않고 통과했다. 불변식 5는 200개로 줄이지 않고 500개·200개 모두 **매 물리 행 전에 전체 판정기를 deepcopy**해서 거절 시 전체 제품·설비 상태를 비교했다. 원래 gpt-log 내용과 보호 파일도 보존했다.

### 실제 명령과 출력 원문 위치

수정 전 `py -m unittest discover -s tests`의 73개 통과 출력과 기존 샘플 재생성 3+3+3+4개 바이트 비교 결과는 이 파일의 「v2 4단계 착수·회귀 기준」에 원문으로 기록했다. 이후 원문은 아래 파일에 명령·전체 stdout·stderr·종료 코드·실측 시간을 함께 저장했고 각 단계 절에도 연결했다. 대량 CLI 행 출력도 생략 없이 원문 파일에 있다.

| 실행 | 원문 |
| --- | --- |
| 단계 ① 전체 테스트 75개 PASS | [stage1-tests.txt](run-logs/stage1-tests.txt) |
| 단계 ② 전체 테스트 87개 PASS | [stage2-tests.txt](run-logs/stage2-tests.txt) |
| 단계 ③ 전체 테스트 91개 PASS | [stage3-tests.txt](run-logs/stage3-tests.txt) |
| 단계 ④ 전체 테스트 97개·1개 FAIL | [stage4-tests.txt](run-logs/stage4-tests.txt) |
| 간소화 후 생성기 집중 테스트 2개 PASS | [stage4-simplify-tests.txt](run-logs/stage4-simplify-tests.txt) |
| `py -m src.generate --seed 42 --products 500 --out data/generated/gen_seed42.csv` | [stage5-generate.txt](run-logs/stage5-generate.txt) |
| `py -m src.main data/generated/gen_seed42.csv --recipe recipes/lamp_models_retest.json --equipment recipes/equipment_generated.json --summary --trace GEN_0005` | [stage5-summary-trace.txt](run-logs/stage5-summary-trace.txt) |
| 단계 ⑤ 전체 테스트 97개·1개 FAIL | [stage5-tests.txt](run-logs/stage5-tests.txt) |
| 단계 ⑥ 전체 테스트 97개·1개 FAIL (최종 파일 충돌 회귀 추가 전) | [stage6-tests.txt](run-logs/stage6-tests.txt) |
| 파일 충돌 수정 후 summary/trace 집중 17개 PASS | [trace-case-fix-tests.txt](run-logs/trace-case-fix-tests.txt) |
| 최종 `py -m unittest discover -s tests`: **98개·97 PASS·1 FAIL**, 57.629초 | [final-tests.txt](run-logs/final-tests.txt) |
| 500개 불변식 1–6 별도 측정: 6개·1 FAIL | [seed42-timing.txt](run-logs/seed42-timing.txt) |
| 최종 기존 13개·새 CSV/meta 2개·보고서 6개 바이트 비교 및 보호 확인 | [final-byte-verification.txt](run-logs/final-byte-verification.txt) |

### 실측 시간과 해석·명세 이견

같은 PC에서 시행한 별도 500개 측정값이며 CLI 프로세스 시작 시간과 구분한다.

| 대상 | 초 |
| --- | --- |
| seed42·500개 생성 (CSV/meta 저장 포함) | 0.108255 |
| 500개 입력 판정 + 추적용 분석 기록 | 0.061041 |
| 500개 불변식 1–6 전체 (별도 생성/최초 판정 이후, 재현성 CLI 실행 포함) | 37.555677 |
| 위 불변식 중 매 행 deepcopy 상태 불변 검사 | 36.688034 |

- **명세 이견, 미해결:** seed42에서 폐기 제품이 0이다. 정상 FAIL 2%, LEAK-2 FAIL 30%, FAIL마다 요청 70%, 다른 설비 우선, 재검사 상한 2, 고장 설비의 빠른 정지를 그대로 적용한 결과다. 폐기 양수를 얻으려고 난수 소비·시드·확률을 조정하지 않았다. 생성기의 폐기 로직은 구현됐고 기존 T36/재검사 테스트 및 summary의 폐기 최초 결과 포함 테스트로 확인했지만 지정 seed42의 폐기 가지는 비어 있다.
- 모델 50:50은 추출 확률이다. 주입 수는 정상 행 수의 3%를 내림하고 종류별 차이 최대 1로 배분한다. 주입률 분모는 정상 행, 거절률 분모는 전체 입력이다. 이번 샘플은 120/4020=`0.0299`와 120/4140=`0.0290`이다.
- 중간 검사에서 가동 설비가 없어 멈춘 경우에도 기존 판정기의 상태 문구를 바꾸지 않는다. 미실시 검사·미완료 이유로 설명한다. 동적 이유 문구는 고정 템플릿과 실제 ID로 엄격히 대응한다.
- seed42의 FPY는 `0.9640`, 최초 FAIL률은 `0.0144`, 전체 FAIL률은 `0.0143`이다. **생성 데이터의 확률은 가정이며 실제 설비 진단 근거가 아니다.**

### 산출물·커밋·리뷰 처리

- 코드/설정: `src/generate.py`, `src/summary.py`, `src/reason_codes.py`, `src/trace.py`, `src/main.py`, `recipes/generator.json`, `recipes/equipment_generated.json`.
- 검증: `tests/test_generate.py`, `tests/test_summary.py`, `tests/fixtures/summary_events.csv`. 기존 테스트 4개와 기대표는 수정하지 않았다.
- 생성물: `data/generated/gen_seed42.csv`, `.csv.meta.json`, `reports/gen_seed42_{rows,products,rejections,equipment,summary}.csv`, `reports/gen_seed42_trace_GEN_0005.csv`. README 「생성기·분석·추적」에 설명과 실제 값 수록.
- main에서 단계별 커밋: `1872f39` T42·43 → `e5ccb32` T45·46·49 → `df20244` T47·48 → `f9e5cef` T44 → `9863432` 생성 샘플 → `ffbe89a` trace 충돌 수정 → `26d1382` README. 이 완료 보고도 별도 커밋한다. push·원격 설정 변경·패키지 설치는 하지 않았다.
- 리뷰004 L1 반영, L2·L4·L5 보류와 L3 기존 반영 근거는 착수 절에 항목별로 기록했다. 최종 리뷰의 p/P trace 덮어쓰기 지적은 `ffbe89a`로 반영하고 수정 전 실패·수정 후 17개 PASS·최종 전체 98개 결과로 확인했다. 그 밖에 수집된 7개 리뷰 자료에는 새 수정 지적이 없다. reliability 독립 리뷰 1개는 사용량 제한으로 실패했으므로 그 렌즈를 완료했다고 주장하지 않는다. 외부 모델로 코드 전송 없이 native 검토만 사용했다.
- 재개 중 확인된 별도 `CLAUDE.md`, `tools/review-loop.ps1` 변경은 손대지 않고 커밋에서 제외했다. 최종 상태에서도 재개 시점 바이트를 보존했다.
- ce-work mode:return-to-caller의 구현/로컬 검증을 마치고 주 에이전트가 간소화·리뷰·통합을 수행했다. 구현 항목은 전부 완료했지만 T44 수용 조건 전체를 충족한 상태로 보고하지 않는다. 구현 경로 native, 외부 실행 엔진 없음, 게시 단계 생략.
- ce-compound mode:non-interactive 판단: 해결한 파일명 충돌은 최종 코드·회귀 테스트·README에서 바로 복원할 수 있고, 폐기 빈 검증 이견은 미해결이다. 별도 영구 해결 문서를 만들 근거가 없어 생성하지 않았다. **Documentation skipped — 추가로 보존할 검증된 비자명한 해결 지식 없음.**
- 최종 ce-code-review 취합·validator empty-batch·report 기록까지 완료했다. 원문 [final-review.json](run-logs/final-review.json)의 잔여 actionable finding은 0이며 `full_compliance=false`, T44 부분 충족, 완료 리뷰 7개/사용량 제한으로 실패한 reliability 리뷰 1개를 명시한다. 파일명 충돌 수정은 검토·검증됐지만 이를 전체 테스트 통과나 명세 완전 충족으로 해석하지 않는다.

## 리뷰 005 수정 단계 (2026-10-18)

대상은 `handoff/reviews/005-review.md`의 H1·M1·M2·M3뿐이다. 낮음 L1–L3와 새 기능은 처리하지 않았다. 착수 시 작업 트리는 깨끗했다. 현재 요청의 커밋 금지를 우선해 커밋·스테이징·브랜치 변경·push를 하지 않았다.

### 항목별 판단과 변경

| 항목 | 판단 | 이유·처리 |
| --- | --- | --- |
| H1 (T44) | **보류** | 리뷰 005와 기존 완료 보고에서 확인한 seed42 폐기 0건은 명세 설정 충돌이다. `tasks.md` 불변식 6과 `decisions.md`의 빈 검증 방지 결정은 이 경우 실패를 유지하고 명세 이견으로 보고하도록 명시한다. 시드·확률·재검사 설비 선택·기대값을 바꾸지 않았다. 폐기 조건이나 생성 확률 정책 변경에는 사용자 결정이 필요하며, T44 충족·전체 통과로 보고하지 않는다. 이번 환경에서는 이 실패를 재실행으로 확인하지 못했다. |
| M1 (T45) | **반영, 실행 검증 미완료** | 명세의 반올림을 통상적인 사사오입으로 해석했다. `src/summary.py::_ratio`를 `Decimal`과 `ROUND_HALF_UP`으로 바꾸고 README에 동점 예시를 명시했다. 1/32→`0.0313`, 1/160→`0.0063`, 1/800→`0.0013`, 경계 앞뒤·0·분모 0의 독립 기대값 테스트를 추가했다. 기존 테스트 기대값은 바꾸지 않았다. |
| M2 (T45) | **반영, 실행 검증 미완료** | `src/main.py`에서 meta를 읽은 직후 최상위 객체, `normal_rows`의 0 이상 정수, `injected_errors`의 객체 및 각 값의 0 이상 정수를 검사한다. bool도 정수로 받지 않는다. 위반은 기존 `ValueError` 처리로 메시지·종료 2가 되고, 검사 위치는 보고서 쓰기 전이다. 배열·null·누락·문자열·실수·bool·음수에 대해 종료 코드·메시지·트레이스백 부재·보고서 미생성을 검사하는 CLI 회귀를 추가했다. |
| M3 (T42–T43) | **반영(리뷰 제안 ②), 실행 검증 미완료** | 현재 실패 정책을 유지하고 README에 필요한 조건을 공개했다. 배정된 종류마다 유효 후보가 있어야 하며, 확률 추출이므로 고정된 최소 제품 수로 보장할 수 없다. `seed39/products4`에서 B 부재로 P5 주입이 불가능한 사례는 리뷰 P3의 관측을 인용했다. 오류 메시지에 종류·배정 수·후보 0·B 부재 이유를 추가하고 해당 실패의 CLI 회귀를 추가했다. 후보 없는 종류의 재배분은 5종 균등·3% 조건을 바꾸므로 하지 않았다. 성공 경로의 난수 소비·배분·버전·설정은 그대로다. |

M3의 판단은 읽기 전용 하위 에이전트의 독립 명세 대조와 일치했다. 주 에이전트가 모든 변경과 로그를 통합했다. 다른 읽기 전용 하위 에이전트가 최종 6개 코드·테스트·README 파일을 정적으로 검토했으며, 수정으로 생긴 중간 이상 결함은 발견하지 못했다. 이는 실행 검증이나 공식 리뷰 PASS를 뜻하지 않는다.

### 실제 실행과 검증 한계

수정 전에 회귀 테스트를 추가한 뒤 실행을 시도했지만, 다음 두 명령 모두 테스트 수집 전에 종료됐다. 따라서 red 실패를 관측했다고 보고하지 않는다.

```text
$ py -m unittest discover -s tests -p test_summary.py
No installed Python found!
[exit code 1]

$ py -m unittest discover -s tests -p test_generate.py -k review005
No installed Python found!
[exit code 1]
```

수정 후 사용자가 지정한 전체 테스트 명령의 실제 출력:

```text
$ py -m unittest discover -s tests
No installed Python found!
[exit code 1]
```

`py` 런처는 존재하지만 `py --list-paths`도 `No installed Pythons found!`를 반환했고, `uv python list --only-installed --offline --no-cache`에도 설치된 인터프리터가 표시되지 않았다. 확인한 Python311 디렉터리에는 `python.exe`가 없었다. 패키지·인터프리터 설치, 전역 설정 변경, `python` 별칭 실행은 하지 않았다. 이 환경 결과는 이전 리뷰의 98개 중 97개 통과·T44 1개 실패와 구분한다. 이번에는 테스트가 0개 수집됐으므로 통과·실패 개수와 실행 시간을 새로 보고할 수 없다.

- `git diff --check`: 종료 0. 변경 파일과 보호 경계는 diff로 확인했다.
- `handoff/tasks.md`, `handoff/decisions.md`, `handoff/reviews/`, `CLAUDE.md`, `.claude/`, `src/rules.py`, 기존 테스트 4개, 설정·데이터·보고서 파일에는 변경이 없다. 기존 테스트 본문의 기대값은 그대로 두고 새 회귀만 추가했다.
- 기존 샘플·seed42 산출물 파일은 수정하지 않았다. 재생성 후 바이트 동일 여부와 기존 T1–T50의 실행 회귀는 Python 부재로 **미검증**이다.
- `practical-work-operation`으로 범위·보존·독립 검토를 조율했다. 기존 리뷰가 수정 항목과 검증 기준을 제공하므로 별도 계획 파일은 만들지 않았다. `ce-work mode:return-to-caller`의 로컬 수정 결과는 검증 차단 상태로 반환했다. 커밋·게시 단계는 현재 사용자 지시에 따라 생략했다.
- `ce-simplify-code mode:pipeline`의 재사용·품질·효율·테스트 가치 기준으로 작은 diff를 인라인 점검했다. 필요한 경계 검증과 회귀 테스트를 유지하고 추가 단순화는 하지 않았다. lint/typecheck 설정은 발견되지 않았으며, 실행 테스트는 위와 같이 차단됐다.
- `ce-code-review`의 필수 scope 도구도 `py .../ce-code-review/scripts/review-scope.py --base HEAD --docs-root docs`에서 `No installed Python found!`·종료 1로 중단됐다. 정식 절차의 완료·리뷰 receipt 생성·PASS를 주장하지 않는다. 보완 정적 검토만 수행했다.
- `ce-compound mode:non-interactive` 판단: 실행으로 검증된 새 해결 지식이 없고 H1은 미해결이다. **Documentation skipped — 미검증 변경이나 명세 이견을 영구 해결 문서로 기록하지 않음.**

남은 일은 Python 실행 환경에서 위 전체 명령을 재실행해 새 회귀와 기존 보존 조건을 검증하는 것, 그리고 H1의 사용자 결정이다. 변경은 커밋하지 않은 상태로 루프 스크립트에 남긴다.
