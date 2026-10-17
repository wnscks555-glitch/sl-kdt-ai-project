# 작업: 교육용 가상 조립·검사 공정의 진행 조건 판정기 (Python CLI)

상태: 사용자 확정 (2026-10-17). 이 PC에서는 `python`이 Store 안내로 연결되므로 실행 명령만 `py`로 바꿨다. 나머지는 사용자 원문 그대로다.

## 배경과 경계
- 위치: project/ (현재 docs만 있고 src, tests는 비어 있음)
- 제조기술개발 직무 지원용 교육 프로젝트. 모든 공정 순서·검사 조건은 가상 규칙이며 SL 실제 기준이 아님.
- 점등(LIGHT)·누설(LEAK) 결과는 실측값이 아닌 합성 PASS/FAIL 입력.
- 핵심 질문: "이 제품이 다음 단계로 진행해도 되는가? 안 된다면 어떤 입력과 규칙 때문인가?"
- 마감이 임박함. 아래 범위만 구현하고 기능을 추가하지 말 것.

## 제외 (구현 금지)
재검사 요청·승인·보류 해제, DB, 사용자·권한, 웹 UI·차트, LLM/LangGraph/RAG, 외부 패키지.
FAIL 제품은 이번 버전에서 계속 보류됨. 새 PASS로 덮어써서 해결하면 안 됨.

## 기술 조건
- Python 3 표준 라이브러리만 사용. 테스트는 unittest.
- 실행: py -m src.main <입력CSV> → 터미널 보고서 출력 + reports/ 아래 CSV 저장
- 테스트: py -m unittest discover -s tests
- 같은 입력을 다시 실행하면 판정 결과가 같아야 함(시각·난수를 판정에 쓰지 말 것).

## 입력 형식 (CSV)
seq,product_id,event,inspection,result
- event: REGISTER | PRE_ASSEMBLY | MAIN_ASSEMBLY | INSPECT
- inspection, result: INSPECT일 때만 사용 (LIGHT|LEAK, PASS|FAIL), 나머지 event에서는 빈칸

## 규칙 (각 규칙에 ID를 붙여 보고서에 표시)
- RULE_SEQ: REGISTER → PRE_ASSEMBLY → MAIN_ASSEMBLY 순서. 선행 단계가 없으면 거절.
- RULE_INSP_PRE: MAIN_ASSEMBLY 완료 전 INSPECT는 거절.
- RULE_NOT_DONE: LIGHT·LEAK 중 하나라도 결과가 없으면 "검사 대기"이며 완료 불가.
- RULE_FAIL_HOLD: 하나라도 FAIL이면 "보류". 두 검사가 모두 PASS일 때만 "선택한 두 검사까지의 모의 흐름 완료".
- RULE_PRESERVE: 같은 제품·같은 검사의 두 번째 결과, 중복 조립 이벤트, 미등록 제품, 잘못된 값은 거절. 거절된 입력은 제품 상태와 기존 결과를 절대 바꾸지 않음.

## 반드시 지킬 설계 조건
- 판정 로직(src/rules.py 등)과 입출력(src/main.py)을 분리.
- 거절 시 "메시지만 출력하고 상태는 바뀌는" 오류가 없도록, 검증을 모두 통과한 뒤에만 상태를 변경.
- 최종 상태명 "모의 흐름 완료"는 출하·양품·SL 기준 적합을 뜻하지 않는다고 README에 명시.

## 보고서 형식
1) 행별: seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
2) 제품별 최종 상태와 미완료 이유
3) 규칙 ID별 거절 건수 집계

## 사전 기대표 (사용자가 확정함. 구현 결과에 맞춰 이 표를 바꾸지 말 것)
| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T1 | 등록→예비→본조립→LIGHT PASS→LEAK PASS | 모의 흐름 완료 |
| T2 | 등록→본조립(예비 없음) | 거절 RULE_SEQ, 상태 '등록' 유지 |
| T3 | 등록→예비→LIGHT PASS(본조립 전) | 거절 RULE_INSP_PRE, 결과 저장 안 됨 |
| T4 | 조립 완료→LIGHT PASS, LEAK 없음 | 검사 대기, 미완료 이유 'LEAK 미실시' |
| T5 | 조립 완료→LIGHT PASS→LEAK FAIL | 보류, 이유 'LEAK FAIL' |
| T6 | T5 뒤 LEAK PASS 추가 입력 | 거절 RULE_PRESERVE, 원래 FAIL·보류 유지 |
| T7 | T1 뒤 LIGHT FAIL 추가 입력 | 거절 RULE_PRESERVE, 완료 상태·원래 PASS 유지 |
| T8 | 예비 조립 두 번 | 두 번째 거절, 상태 변화 없음 |
| T9 | 미등록 제품 이벤트, result='OK' 같은 잘못된 값 | 거절, 다른 제품 상태 영향 없음 |
| T10 | 같은 입력 CSV를 두 번 실행 | 두 보고서의 판정 열이 동일 |

## 산출물
- src/, tests/ (T1–T10을 각각 테스트로. T2·T3·T6·T7·T8·T9는 거절 후 '상태 불변'까지 assert)
- data/sample_events.csv (T1–T9를 제품별로 담은 고정 입력)
- README.md를 이 범위로 갱신(실행법, 가상 규칙 경계, 제외 범위·한계).
  docs/requirements.md는 삭제하지 말고 맨 위에 "재검사 범위는 이번 버전에서 제외, 현행 기준은 README" 한 줄만 추가.

## 완료 보고 (반드시 포함)
- 실제로 실행한 명령과 출력 원문(테스트 결과 포함)
- 기대표와 실제 결과가 다른 항목이 있으면 숨기지 말고 그대로 보고. 기대표나 테스트를 고쳐서 통과시키지 말 것.
- 구현하면서 내린 해석·가정 목록 (명세가 모호했던 부분)
