검수 모델: gpt-6.1-sol

# 리뷰 017 — 리뷰 016 재검토 및 현행 v2 10단계 검수

검수일: 2026-10-31. **판정 FIX. 016의 높음 4건·중간 2건은 모두 해결됐다. 신규 미해결 높음 2건·중간 1건, 수정 요구 3건이다. 낮음 1건은 기록만 한다.** 전체 테스트는 지정 명령을 한 번 직접 실행했으나 `py` 런처 오류로 시작되지 않아 **미검증**이다. 추가 반례는 설치된 Python 3.12로 별도 실행했으며 18개 중 15개 통과·3개 실패다. P09의 순서 해석을 좁힌 뒤 해당 반례만 다시 실행했고 실패를 확인했다.

## 범위와 수행 경계

- 기준: `handoff/tasks.md` 맨 위 현행 10단계 명세·T153–T171 및 아래 완료 단계들의 보존 조건. 과거 `docs/` 문서를 판정 기준으로 삼지 않았다.
- 읽은 근거: `AGENTS.md`, `handoff/setup-notes.md`, 현행·보존 명세, `handoff/gpt-log.md`의 016 대응 및 10단계 구현 기록, `handoff/decisions.md`, `016-review.md`, 최근 이력, 지정 diff와 작업 트리 diff, 관련 소스·테스트·제출물. `docs/solutions/`와 `.compound-engineering/`는 없었다.
- `practical-work-operation`은 범위·검증 조율에만 적용했다. 플러그인 리뷰 스킬과 보조 에이전트는 사용하지 않았다. 이전 반례는 참고 자료로 읽었으며 import하거나 실행하지 않았다.
- 작성 대상은 이 파일과 `handoff/reviews/probes/test_probe_017.py`뿐이다. 제품 코드·기존 테스트·설정·보고서는 수정하지 않았다. commit·push·설치·삭제도 하지 않았다. 시작부터 존재한 미추적 `handoff/loop-logs/017-codex.txt`는 건드리지 않았다. 출력은 `tempfile` 폴더만 쓰고, 실행에는 `PYTHONDONTWRITEBYTECODE=1`을 설정했다.

검토 범위:

~~~text
git diff 18f3244e586c66efb060a200748ebf33f401b104..HEAD
git log -8 --oneline
git diff -- src tests
git diff --check 18f3244e586c66efb060a200748ebf33f401b104..HEAD
~~~

HEAD: `c73ae476ea6cf1990e6c55a98c2152ebb5bc49d5`. 지정 범위의 커밋:

~~~text
c73ae47 feat(T167-T171): run station scenarios over Modbus and record frames
e36d9a8 feat(T153-T158): add PLC scan state machine and interlocks
c7bf199 feat(T159-T166): add Modbus TCP frames, server and client
7e9f623 docs(T153-T171): confirm stage 10 spec after Sol review
64c6d1e fix(T134,T147): apply review 016 input, ordering and output fixes
~~~

## 이전 높음·중간 항목별 판정

| 이전 항목 | 심각도 | 판정 | 근거 |
| --- | --- | --- | --- |
| R16-H1 | 높음 | **해결** | `src/line.py:228`의 사전 구조·generator 검사와 `:279`의 step 타입 검사. P01은 이전 네 사례를 포함해 null·빈 문자열·객체·bool 등 9개 변형에서 위치 포함 종료 3, traceback 없음, 보고서 없음 및 다음 정상 실행 성공을 확인했다. gpt-log의 수정 설명을 받아들인다. |
| R16-H2 | 높음 | **해결** | `src/line.py:872`의 고정 설비 순서를 compare에 적용한다. P03에서 같은 면적 동률 사례를 JSON 키의 모든 6개 순열로 검사했고 선택·조합 표기가 모두 LEAK/LIGHT/FINAL=`2-1-2`였다. 함수의 순서 반환만 보는 검증에 그치지 않았다. |
| R16-H3 | 높음 | **해결** | `src/line.py:779`가 등록 순서를 쓴다. P04에서 실제 생성기 시드 0·10001제품의 경로 번호가 정확히 1…10001이다. 아래 R17-M1은 새 `station.load_values`의 별도 문제이며 이 수정의 해결을 취소하지 않는다. |
| R16-H4 | 높음 | **해결** | `src/line.py:150`이 문자열 분해·정수 연산을 사용한다. P05에서 이전 긴 값과 0·선행 0·소수 자릿수 경계·123자리 밀리초까지 정확히 변환했다. |
| R16-M1 | 중간 | **해결** | `src/line.py:293`이 중복 선행 요소를 위치 포함 입력 오류로 거절한다. P02에서 명확한 거절과 이후 원본의 최적 8작업장 배치를 확인했다. 명세에 없던 중복을 입력 오류로 정했다는 gpt-log 설명을 받아들인다. |
| R16-M2 | 중간 | **해결** | `src/line.py:970`, `:992`, `:1019`가 실제 작성한 경로를 반환·표시한다. P06의 배치 불가 CLI에서 CSV 두 개만 생성·안내하고 SVG는 안내하지 않았다. |

016에서 해결로 처리한 015 항목도 되돌리는 변경이 없다. `src/pfmea.py`와 해당 테스트·보고서의 보존 및 P17 재생 일치를 확인했다. 016의 T143 산술 반박 수용도 유지한다. 작업 10초·서버 1개·2제품의 종료는 20초이고 정의상 pass_uph=360, good_uph=180이다. 현행 파일 아래의 T143 기대표는 여전히 180/90이지만 기대표를 고치거나 이 모순을 구현 결함으로 다시 세지 않았다. “어떤 요소가 택트를 넘으면”은 수작업 요소를 뜻한다는 Claude 설명도 016의 해석, 병렬 검사 대수 정의 및 기본 최적 배치와 일치한다.

## 신규 지적 사항

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| R17-H1 | 높음 | `src/plc.py:184–192` | 알람 복귀가 내부 문자열만 지우고 외부에 공개한 측정 워드를 남긴다. | `tasks.md:107`은 복귀 때 측정값을 지우고 measure_id·처리 수를 유지하도록 정한다. P07은 실제 정상 시퀀스로 10.250을 공개한 뒤 가드 알람, 수동 해제, 제품 제거 및 유효한 reset 상승 에지를 넣었다. IDLE·내부 value=''·판정 레지스터 0·aborted·ID 유지까지는 맞지만 입력 레지스터 3–4는 `[0,10250]`으로 여전히 10.250이다. `_recover`와 후속 `_write` 어디에서도 두 워드를 비우지 않는다. | 복귀 작업에서 두 측정 워드도 지우고, 내부 값과 Modbus 공개 값 모두 비워지는지 확인한다. ID·처리 수 유지와 PC 소유 코일 보존을 함께 검증한다. |
| R17-H2 | 높음 | `src/modbus.py:223–235`, `:283–286` | 뒤의 손상 프레임이 앞의 유효한 완성 요청까지 소실시켜, 동일 바이트 스트림의 쓰기 결과가 recv 분할에 따라 달라진다. | P08은 유효한 FC06(heartbeat=7) 뒤에 protocol ID=1 프레임을 붙인 동일 바이트열을 세 방식으로 전달했다. 별도 수신과 손상 헤더 5바이트까지만 첫 조각에 붙인 수신은 `(보유 레지스터 0, 응답 수)=(7,1)`, 한 번에 병합한 수신은 `(0,0)`이다. `feed`가 정상 프레임을 이미 버퍼에서 제거해 지역 목록에 넣은 뒤 후속 헤더에서 예외를 던지면 `_serve`는 그 목록을 받지 못하고 종료한다. `tasks.md:136`의 분할·병합 처리와 같은 입력 결과 불변 조건에 어긋나며, 유효한 쓰기·응답이 사라진다. | 완성된 정상 프레임을 스트림 순서대로 처리한 뒤 손상 프레임에서 닫도록 수신/처리 경계를 조정한다. 유효한 쓰기 뒤의 손상 프레임을 합치거나 분할해도 앞선 쓰기·응답이 동일한지 검증한다. |
| R17-M1 | 중간 | `src/station.py:114`, `:122–128`; 명세 `handoff/tasks.md:217` | **명세 이견:** 측정값을 “순서대로” 쓴다는 말에 순서 기준이 빠져 있고, 구현은 제품 ID를 문자열 정렬해 10000번 경계에서 제품 번호 순서까지 바꾼다. | P09 최종 반례는 시드 0·10001제품에서 각 제품의 최초 LEAK 값을 독립 추출하고 함수 설명의 제품 순서를 번호로 해석해 비교했다. 1001번째 값은 GEN_1001의 10.516이어야 하지만 GEN_10000의 10.290이 들어간다. normal_events 최초 측정의 발생 순서를 뜻해도 sorted가 그 순서를 버린다. 명세가 발생 순서/제품 번호 순서 중 어느 쪽인지 직접 확정하지 않았으므로 높음으로 단정하지 않고 중간으로 올린다. 9단계의 번호 순서 조건을 10단계에 자동 이식한 판정도 아니다. | 최초 측정 발생 순서인지 생성 제품 번호 순서인지 명세에 밝히고 그 순서를 유지한다. 제품 순서라면 번호를 정수로 비교하고 ID와 값의 대응을 독립 검사한다. 기존 20제품 제출물에 영향이 생기는 선택이면 그 변경도 공개한다. 기대표는 검수자가 바꾸지 않는다. |
| R17-L1 | 낮음 | `src/modbus.py:408` | 파일 끝에 불필요한 빈 줄이 있다. | 지정 diff의 `git diff --check`가 `new blank line at EOF`를 출력하고 실행 도구의 종료 코드는 1이었다. 동작 영향은 없다. | 기록만 한다. 수정 요구에 세지 않는다. |

R17-H2는 실제 TCP가 분할할 위치를 예측해 실행한 테스트가 아니다. 결정적인 recv 대역을 서버의 실제 `_serve`·FrameBuffer·PDU 처리에 연결해 세 경계를 강제로 재현한 검사다. 실제 소켓의 정상 시나리오는 P18에서 별도로 실행했다.

## 반례별 입력·예상·실제·판단

반례 파일: `handoff/reviews/probes/test_probe_017.py`. P07–P14는 기대표 밖의 상태·오류·경계 조합이며, P01–P06은 이번 수정의 직접 재검증이다.

| ID | 입력 | 예상·명세 근거 | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | 이전 형식 오류와 null·공백 generator·객체/null/bool step 등 9개 → 정상 CLI | 위치 포함 종료 3, 파일 없음, 다음 정상 실행 가능(9단계 입력 오류 규칙) | 9개 모두 맞고 다음 실행 성공 | 통과·R16-H1 해결 |
| P02 | 동일 선행 ID 두 번 → 원본 배치 | 명확한 거절, 원본의 가능 판정을 훼손하지 않음 | 중복 위치 오류, 원본 최적 8개 | 통과·R16-M1 해결 |
| P03 | 같은 면적 동률 경로, machines 키 6개 순열 | 고정 (leak,light,final) 사전순 선택 | 전부 선택·표기 2-1-2 | 통과·R16-H2 해결 |
| P04 | 실제 측정 생성기 시드 0·10001제품 | 경로 번호 1…10001(9단계 투입 순서) | 전체 일치 | 통과·R16-H3 해결 |
| P05 | 0, 000.001, 1.01, 이전 긴 값, 120자리 정수부+.999 | 정수 밀리초 정확, 중간 반올림 없음 | 전체 일치·오류 없음 | 통과·R16-H4 해결 |
| P06 | 수요 2600·임시 폴더에서 배치 불가 CLI | 종료 0, CSV 두 개만 생성·안내 | 전체 일치 | 통과·R16-M2 해결 |
| P07 | 10.250 공개 뒤 가드 알람 → 수동 해제 → 제품 제거 → reset | 측정·판정 비움, ID·처리 수 유지, aborted(:107) | 내부 문자열만 비고 측정 워드 [0,10250] 유지 | 실패·R17-H1 |
| P08 | 정상 FC06(0,7)+손상 프로토콜 프레임을 3방식 recv | 같은 바이트열의 정상 선행 쓰기·응답 동일, 손상에서 종료(:136) | (7,1)/(0,0)/(7,1) | 실패·R17-H2 |
| P09 | 시드 0·10001제품의 최초 LEAK 값, 독립 제품 번호 기준 | 함수 설명의 제품 순서라면 1…10001. 명세의 순서 기준은 누락(:217) | 1001번째 10.516 대신 GEN_10000의 10.290 | 실패·R17-M1 명세 이견 |
| P10 | WAIT_JUDGE에 구판정 존재 → 권한 위반 FC16 → 스캔 거절 → 정상 FAIL 쌍 | 권한 오류는 기존 쌍 불변, 뒤 정상 쌍 한 번 접수(:135–137, 판정 접수) | 예외 02·불변·거절 뒤 정상 접수, UNCLAMP·FAIL | 통과 |
| P11 | WAIT_JUDGE 스냅샷 직후 판정 쌍과 클램프 입력을 동시에 변경 | 이번 스캔은 옛 값, 다음 스캔 한 번 전이(스캔 규칙) | WAIT_JUDGE 유지 → UNCLAMP, 조기 게이트 없음 | 통과 |
| P12 | 판정 대기 만료 스캔에 정상 쌍 또는 틀린 ID | 정상은 전이 우선, 틀린 쌍은 거절 후 알람 14(전이·타임아웃 순서) | 각각 UNCLAMP/ALARM 14, 게이트 없음 | 통과 |
| P13 | 하트비트 만료 중 reset 상승 → heartbeat 복구, reset 유지 → 새 상승 | 실패한 상승 소비, 복구 후 새 에지 필요(:100–107) | 유지 중 ALARM, 새 상승에 IDLE | 통과 |
| P14 | 30자리 이내 정확한 값·음수 0·선행 0, 미세한 비정수·잘못된 문자열 → 정상 값 | 정확한 왕복, 불가능 값 거절, 뒤 정상 값 영향 없음(:160·7a 공통 형식) | 전체 일치 | 통과 |
| P15 | 기준 커밋과 보호 파일 비교, 기존 테스트 메서드 AST 대조 | 승인된 016 수정 외 보존, 기존 검증 본문 무변경 | 보호 140개·기존 보고서 62개 동일, line 기존 메서드 28개 동일, 10단계 직전 142개 모두 동일 | 통과·보존 |
| P16 | 기존 샘플 7종 및 일반/측정 생성 seed42·500제품 재생 | 이전 단계 판정·보고서·생성물 동일 | 보고서 47개 및 생성 CSV/meta 4개 바이트 동일 | 통과·보존 |
| P17 | PFMEA 0–29·500, 라인 0–29/1000–1029·500 재생 | 수정 후에도 기존 제출 산출물 동일 | PFMEA 2개·라인 3개 모두 바이트 동일 | 통과·보존 |
| P18 | 8시나리오·seed42·20제품, 임시 폴더 두 개 | 시나리오 결과와 기록 결정성(T167–T169) | normal=20/OK19/NG1/알람0, 나머지=처리4·각 알람 일치, 16개 보고서가 두 번 모두 제출본과 동일 | 통과 |

## Claude 의견 수용 및 검증 한계

반례 탐색 후, 016의 여섯 수정 설명은 모두 받아들인다. gpt-log의 정상 20개·OK19·NG1 및 8시나리오 결과와 결정성 주장도 P18의 독립 실행으로 확인했다. 측정값 변환의 60자리 문맥은 기존 공통 형식의 최대 30자리 입력을 수용하고 P14가 경계에서 정확성을 확인했으므로 근거 없이 정밀도 문제를 추가하지 않았다. 반면 “알람 복구 단위 테스트 확인”은 측정 레지스터 소거까지 증명하지 않아 R17-H1이 남는다.

- **기존 테스트 무수정:** 016 수정 커밋은 기존 `tests/test_line.py`의 import를 조정하고 회귀를 추가했다. 파일 전체가 바이트 불변이라고 보고하지 않는다. 기존 클래스의 28개 메서드 본문은 AST 동일이며 기존 검증을 바꾸지 않았다. 다른 기존 테스트는 바이트 동일이다. 10단계만 분리한 `64c6d1e..HEAD`에서는 기존 소스·테스트·설정·자료·보고서 142개 모두 변경이 없다.
- **기존 보고서 동일:** 016 기준 보고서 62개 전부 blob 동일. 그중 52개는 이번에 실제 재생해 바이트 일치했다(P16 47개, P17 5개). 나머지 eval 보고서 10개는 소스·설정·파일 보존을 확인했고 평가 명령 자체는 다시 실행하지 않아 **재실행 미검증**이다.
- **기존 전체 테스트 통과:** 요청한 `py -m unittest discover -s tests`는 딱 한 번 호출했고 런처에서 실패했다. 직접 실행 파일로 전체 테스트를 재시도하지 않았다. 제출 `handoff/run-logs/v2-stage10-tests.txt`의 `Ran 321 tests in 172.255s / OK`는 작성자 측 증거로 구분한다. 런처 실패가 샌드박스 때문이라는 과거 설명의 원인은 이번에도 독립 확정하지 않았다.
- **추가 반례 환경:** `py` 반례 명령도 런처에서 실패했으므로, 이미 설치된 Python 3.12.10의 실행 파일로 이 반례 파일만 실행했다. `py`·Python 3.9 환경에서의 정상 실행은 **미검증**이다. 이전 반례 파일 전체 또는 일부를 재실행하지 않았다.
- **P09 해석 조정:** 최초 실행은 normal_events 최초 측정의 발생 순서를 기대했다. 생성기가 여러 제품·모델의 사건을 교차 생성함을 확인하고, 함수가 명시한 제품 순서에 한정해 번호 순서로 기대를 좁혔다. 이 한 메서드만 수정·재실행해 1001번째 불일치를 재확인했다. 초기의 “3번째 발생 순서 불일치”를 숫자 순서 결함의 증거로 쓰지 않는다. 명세의 순서 선택은 R17-M1로 따로 공개한다.
- SVG는 바이트 재생까지 확인했으며 화면 렌더링은 **미검증**이다. 실제 PLC·설비 동작은 이번 소프트웨어 모의 검수의 대상이 아니다.

## 실행 명령과 결과 원문

전체 테스트: 한 번 실행, 종료 코드 1.

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONIOENCODING='utf-8'; py -m unittest discover -s tests
~~~

~~~text
No installed Python found!
~~~

지정 반례 명령: 런처 실패, 종료 코드 1.

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONIOENCODING='utf-8'; py -m unittest handoff/reviews/probes/test_probe_017.py
~~~

~~~text
No installed Python found!
~~~

추가 반례 파일 실행: 전체 tests 재실행 아님. 종료 코드 1. 아래는 P09 기대 순서를 좁히기 전의 실행 원문이다.

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONIOENCODING='utf-8'; & 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff/reviews/probes/test_probe_017.py
~~~

~~~text
P01: 9 malformed variants exit 3; no reports; next valid run succeeds
.P02: duplicate edge rejected at its location; original optimal has 8 stations
.P03: all 6 machine-key permutations select and label LEAK/LIGHT/FINAL=2-1-2
.P04: real generated routes 1..10001 remain in numeric order
.P05: zero, leading zeros, fractional and 123-digit milliseconds remain exact
.P06: infeasible balance announces exactly the 2 CSV files actually written
.P07: after accepted reset state=IDLE; value=''; words=[0, 10250]; measure_id=1
FP08: identical bytes, 3 recv segmentations -> (heartbeat, replies)=[(7, 1), (0, 0), (7, 1)]
FP09: first wrong station measurement position=3; actual/expected around 1001=['9.438', '9.590', '10.290', '9.318', '10.516', '9.363']/['9.543', '10.048', '9.056', '10.569', '10.612', '10.082']
FP10: invalid FC16 leaves old pair; rejection followed by valid FAIL pair accepts once
.P11: post-snapshot judge/input changes ignored now and accepted next scan; one transition
.P12: valid judge wins at expiry; invalid judge is rejected then alarm 14 in same scan
.P13: failed reset edge consumed while heartbeat stale; recovery needs a fresh edge
.P14: 30-digit exact values round-trip; nonintegral/invalid values rejected; next valid value exact
.P15: 140 protected old files identical; 62 old reports identical; 28 original line test methods unchanged; all 142 stage-10 predecessor files unchanged
.P16: 47 legacy reports and 4 generated CSV/meta files replay byte-identically
.P17: PFMEA 2 and line 3 submitted artifacts replay byte-identically after R16 fixes
.P18: all 8 scenarios repeat across 2 folders and all 16 reports match submitted bytes
.
======================================================================
FAIL: test_p07_reset_clears_published_words_but_keeps_id_and_count (handoff.reviews.probes.test_probe_017.DiffProbes.test_p07_reset_clears_published_words_but_keeps_id_and_count)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_017.py", line 209, in test_p07_reset_clears_published_words_but_keeps_id_and_count
    self.assertEqual(actual, [0, 0], 'Recovery must clear the published measurement as well as the internal string')
AssertionError: Lists differ: [0, 10250] != [0, 0]

First differing element 1:
10250
0

- [0, 10250]
?     ----

+ [0, 0] : Recovery must clear the published measurement as well as the internal string

======================================================================
FAIL: test_p08_valid_prefix_not_lost_when_bad_frame_is_coalesced (handoff.reviews.probes.test_probe_017.DiffProbes.test_p08_valid_prefix_not_lost_when_bad_frame_is_coalesced)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_017.py", line 223, in test_p08_valid_prefix_not_lost_when_bad_frame_is_coalesced
    self.assertEqual(results, [(7, 1)] * 3, 'A later damaged frame must not erase a preceding complete valid request')
AssertionError: Lists differ: [(7, 1), (0, 0), (7, 1)] != [(7, 1), (7, 1), (7, 1)]

First differing element 1:
(0, 0)
(7, 1)

- [(7, 1), (0, 0), (7, 1)]
+ [(7, 1), (7, 1), (7, 1)] : A later damaged frame must not erase a preceding complete valid request

======================================================================
FAIL: test_p09_station_values_follow_generator_order_past_9999 (handoff.reviews.probes.test_probe_017.DiffProbes.test_p09_station_values_follow_generator_order_past_9999)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_017.py", line 236, in test_p09_station_values_follow_generator_order_past_9999
    self.assertEqual(actual, expected, 'LEAK first measurements must retain normal_events product order')
AssertionError: Lists differ: ['9.766', '11.043', '7.934', '9.737', '10.527', '11.525', '9.9[95113 chars]279'] != ['9.766', '11.043', '10.527', '9.945', '11.779', '9.409', '10.[95113 chars]799']

First differing element 2:
'7.934'
'10.527'

Diff is 186854 characters long. Set self.maxDiff to None to see it. : LEAK first measurements must retain normal_events product order

----------------------------------------------------------------------
Ran 18 tests in 37.261s

FAILED (failures=3)
~~~

P09의 최종 기대(제품 번호 순서)만 재실행: 종료 코드 1.

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONIOENCODING='utf-8'; & 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff.reviews.probes.test_probe_017.DiffProbes.test_p09_station_values_follow_numeric_product_order_past_9999
~~~

~~~text
P09: first wrong station measurement position=1001; actual/expected around 1001=['9.438', '9.590', '10.290', '9.318', '10.516', '9.363']/['9.438', '9.590', '10.516', '9.363', '8.876', '11.166']
F
======================================================================
FAIL: test_p09_station_values_follow_numeric_product_order_past_9999 (handoff.reviews.probes.test_probe_017.DiffProbes.test_p09_station_values_follow_numeric_product_order_past_9999)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_017.py", line 238, in test_p09_station_values_follow_numeric_product_order_past_9999
    self.assertEqual(actual, expected, 'LEAK first measurements must retain numeric product order across 9999/10000')
AssertionError: Lists differ: ['9.7[9558 chars] '10.290', '9.318', '10.516', '9.363', '8.876'[85566 chars]279'] != ['9.7[9558 chars] '10.516', '9.363', '8.876', '11.166', '8.631'[85566 chars]318']

First differing element 1000:
'10.290'
'10.516'

Diff is 125246 characters long. Set self.maxDiff to None to see it. : LEAK first measurements must retain numeric product order across 9999/10000

----------------------------------------------------------------------
Ran 1 test in 0.830s

FAILED (failures=1)
~~~

VERDICT: FIX
