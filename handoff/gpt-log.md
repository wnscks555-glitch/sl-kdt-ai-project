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
