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
