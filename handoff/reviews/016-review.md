검수 모델: gpt-6.1-sol

# 리뷰 016 — 리뷰 015 재검토 및 현행 v2 9단계 검수

검수일: 2026-10-31. **판정 FIX. 이전 미해결 H3·M2는 모두 해결. 신규 미해결 높음 4건·중간 2건, 수정 요구 6건이다.** 낮음 지적은 없다. 이번 반례 16개 중 10개 통과·6개 실패이며, P03의 하위 사례 4개를 포함한 unittest 실패 기록은 9개다. 전체 테스트는 지정 명령으로 한 번만 실행했으나 런처 오류로 시작되지 않아 **미검증**이다.

## 범위와 보존 경계

기준은 handoff/tasks.md:1 현행 9단계 명세·T130–T152와 아래 완료 단계의 보존 조건이다. setup-notes.md, tasks.md, gpt-log.md의 이전 검토 대응 및 현행 완료 보고, decisions.md, 015-review.md, 최근 이력과 지정 diff를 읽고 코드·테스트·제출물과 대조했다. 과거 docs/ 문서를 판정 기준으로 삼지 않았다. docs/solutions/와 .compound-engineering/는 없었다.

practical-work-operation을 범위·검증 조율에 적용했다. 사용자 지시대로 플러그인 리뷰 스킬과 보조 에이전트는 사용하지 않았다. 이전 반례 파일은 참고 자료로 읽었지만 import하거나 실행하지 않았다. 이번 저장소 작성 대상은 이 리뷰와 handoff/reviews/probes/test_probe_016.py뿐이다. 제품 코드·기존 테스트·설정·보고서를 수정하거나 commit·push·설치·삭제하지 않았다. 시작부터 있던 미추적 handoff/loop-logs/016-codex.txt는 건드리지 않았다. 테스트 생성물은 모두 tempfile 임시 폴더에 썼고 PYTHONDONTWRITEBYTECODE=1로 캐시 생성을 막았다.

검토 범위:

~~~text
git diff 1c976f9797bc7782faf977e65ee0fceb3cee75d5..HEAD
git log -6 --oneline
git diff --check 1c976f9797bc7782faf977e65ee0fceb3cee75d5..HEAD
~~~

HEAD는 a517816a6dd6437cb4eeada304adf3d8829cc6c3이다. 지정 범위는 15파일이며 diff --check는 출력 없이 종료 0이었다. 범위 내 커밋:

~~~text
a517816 feat(T130-T152): add line balancing, virtual clock and layout schematic
3616dad docs(T130-T152): confirm stage 9 spec by user delegation
ee0ecb2 fix(T122,T129): apply review 015 report column and Markdown evidence
~~~

## 이전 높음·중간 항목별 판정

| 이전 항목 | 심각도 | 판정 | 근거 |
| --- | --- | --- | --- |
| 015 H3 | 높음 | **해결** | src/pfmea.py:114와 :120이 없는 헤더 열과 짧은 행의 None을 거절한다. P01에서 두 오류가 1.evidence 표 오류가 되고 실제 빈 셀은 허용됨을 확인했다. 오류 뒤 정상 숫자 참조도 성공했다. gpt-log.md:3780의 수정 설명을 받아들인다. |
| 015 M2 | 중간 | **해결** | src/pfmea.py:461, :464, :469에서 현재 근거·조치 근거·관측값을 출력한다. P02에서 두 항목을 함께 넣어 올바른 항목에 외부 관측값 0.314159와 미충족 판정이 연결됨을 확인했다. P14는 수정된 제출 CSV·Markdown 전체를 재생 일치시켰다. gpt-log.md:3781의 설명을 받아들인다. |
| 015에서 해결 처리한 H1 | 높음 | 해결 상태 유지 | P12에서 src/generate.py를 포함한 기존 소스 blob이 015 기준 커밋과 동일함을 확인했다. 정수 이동량 분포 오류 변환을 되돌린 변경이 없다. 해당 이전 반례를 다시 실행하지는 않았다. |
| 015에서 해결 처리한 H2 | 높음 | 해결 상태 유지 | 같은 blob 비교로 confirm_value의 자릿수 보호가 그대로임을 확인했다. 이번 R16-H4는 새 src/line.py의 별도 시간 파서 문제다. 이전 생성기 반례를 다시 실행하지 않았다. |
| 015에서 해결 처리한 M1 | 중간 | 해결 상태 유지 | tests/test_measurement.py는 015 기준과 바이트 동일하다. 독립 사례별 파일을 쓰는 T108 수정은 보존됐다. 이전 T108 단독 반례를 다시 실행하지 않았다. |

gpt-log.md의 “사용자 PC에서 전체 테스트 실행” 기록과 제출 실행 로그의 249개 OK는 작성자 측 증거로 확인했다. 이번 환경에서는 같은 py 명령이 시작되지 않았으므로 독립 전체 통과 결과로 옮겨 적지 않는다. 실패 원인이 검수 샌드박스인지까지는 확정하지 않았다.

## 신규 지적 사항

아래 ID는 이번 리뷰의 새 항목이며 이전 H3·M2와 구분한다. 심각도는 영향으로만 정했다.

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| R16-H1 | 높음 | src/line.py:929, :267 | 형식·필수 키 오류가 명세의 입력 오류 경로를 벗어난다. | P03에서 generator 키 누락은 종료 2, 최상위 배열·숫자 generator·배열 step은 traceback과 종료 1이었다. tasks.md:61–64, :191은 형식·없는 키 등의 위반을 위치 포함 종료 3으로 정한다. run이 검증 전에 raw["generator"]를 읽고 경로 연산을 하며, step은 타입 확인 없이 집합 조회에 쓰인다. 네 경우 모두 보고서 미생성은 지켰지만 오류 판정·종료 코드는 다르다. | generator를 읽기 전에 최상위 구조·필수 키·경로 값 타입을 검증하고, step도 문자열인지 확인해 LineError로 위치를 보고한다. 파일 접근 실패의 종료 2와 구별한다. 네 사례를 CLI 경로에서 검증한다. |
| R16-H2 | 높음 | src/line.py:852, :866 | 설비 JSON 키 순서가 사전 선택 기준의 동률 우선순위를 바꾼다. 조합 표기 순서도 함께 뒤집힌다. | P05는 동일한 최적 배치·경로·설비 값에서 machines 키 순서만 LEAK/LIGHT/FINAL에서 FINAL/LIGHT/LEAK로 바꾼다. 면적 9,180,000mm²·총 5대이고 모두 기준을 만족하는 두 조합 중 원래는 (2,1,2), 재배열 뒤에는 실제 LEAK/LIGHT/FINAL=(2,2,1)을 선택했다. tasks.md:167의 마지막 키는 입력 키 순서와 관계없이 (leak, light, final)이다. list(line.machines)로 만든 키를 비교와 combo 표시 모두에 재사용한다. | 후보 비교 키와 combo 표시를 LEAK/LIGHT/FINAL의 고정 순서로 만들고, 사양표 등 입력 순서를 요구하는 출력과 분리한다. JSON 키 재배열에서도 동률 선택·조합 표기가 동일한 회귀를 둔다. |
| R16-H3 | 높음 | src/line.py:760 | 제품 번호 10000부터 문자열 정렬이 실제 투입 순서를 바꾼다. | P06은 실제 측정 생성기·시드 0·10001제품으로 경로를 추출했다. 1001번째 경로가 GEN_1001 대신 GEN_10000이고, 경계 순서는 998,999,1000,10000,10001,1001,…이었다. tasks.md:125는 제품 번호 순으로 투입하고 앞지르지 않도록 한다. products 상한은 없으며 4자리 zfill은 5자리 번호를 막지 않는다. 혼류 부하·재검사·정지가 있는 라인의 입력 순서를 바꾸므로 가상 시계 결과의 전제가 달라진다. | 생성 시 등록 순서를 보존하거나 생성기 제품 번호의 정수 부분으로 정렬한다. 9999/10000 경계에서 추출 순서와 투입 순서를 확인한다. |
| R16-H4 | 높음 | src/line.py:154 | 허용된 문자열 초가 정수 밀리초 변환 중 묵시적으로 반올림된다. | P07의 123456789012345678901234567890.123은 명세 정규식에 맞고 자릿수 상한도 없다. 기대 정수는 123456789012345678901234567890123ms이지만 실제는 123456789012345678901234567900000ms이며 오류 목록은 비었다. Decimal 곱셈이 기본 28자리 문맥에 제한된다. tasks.md:17의 정수 밀리초 변환과 :72의 정확한 정수·분수 계산을 위반한다. | 문자열의 정수부·소수부를 정수 연산으로 변환하거나 입력 길이를 수용하는 정밀도를 사용한다. 지원 상한을 도입하려면 명세에 공개하고 입력 위치 오류로 거절하며, 허용 입력을 조용히 바꾸지 않는다. |
| R16-M1 | 중간 | src/line.py:398 | 중복 선행 ID를 허용한 뒤 서로 다른 의존성 비트로 해석해 가능한 배치를 불가로 판정한다. | P04에서 P1-2의 predecessors만 ["P1-1","P1-1"]로 바꾸면 load_line은 허용하고 휴리스틱은 기존대로 8개 작업장을 찾지만 전수 탐색은 None이다. needs의 sum에서 같은 비트를 두 번 더해 다음 비트로 올림하기 때문이다. 명세는 선행 목록 중복의 처리 방식을 직접 정하지 않으므로 중간으로 분류했다. | 중복을 명확한 입력 오류로 거절하거나 의존성 집합으로 처리한다. 허용한다면 비트 합산 전에 중복을 없애고 휴리스틱·최적 탐색의 실현 가능 판정이 같아지는지 검증한다. |
| R16-M2 | 중간 | src/line.py:995 | 배치 불가로 SVG를 만들지 않은 실행에서도 SVG가 저장됐다고 보고한다. | P08의 demand_units=2600은 종료 0·배치 불가이며 실제 파일은 line_balance.csv와 line_compare.csv 두 개다. stdout의 저장 파일 목록에는 존재하지 않는 line_layout.svg가 포함된다. tasks.md의 배치 불가 분기는 SVG를 쓰지 않도록 정하며, 이 동작 자체는 맞다. 생성 여부를 확인하는 CLI 보고가 실제 산출물과 불일치한다. | run이 실제 생성한 경로를 반환하거나 배치 결과에 따라 저장 목록을 구성한다. SVG 미생성 분기는 CSV 두 파일만 저장됐다고 표시한다. |

## 명세 이견과 Claude 의견 수용

**T143의 산술 반박을 받아들인다.** tasks.md:236의 기대표는 pass_uph=180, good_uph=90이지만 서비스 10초·서버 1개·완료 제품 2개이면 종료는 20초다. 정의대로 2×3600/20=360, 1×3600/20=180이다. P11은 종료·완료 수·양품 수·유출 수를 함께 확인해 Claude의 계산을 지지했다. 정의를 따르는 구현과 테스트에 수정 요구를 추가하지 않는다. 기대표는 고치지 않았으며, 표와 정의의 모순은 이 명세 이견으로 남긴다.

tasks.md:95의 “어떤 요소가 택트를 넘으면”을 검사 요소까지 포함해 문자 그대로 읽으면 기본 LEAK 34초 > 택트 19.8462초인 T131의 정상 최적 배치와 양립하지 않는다. 이번 검수는 :90의 수작업 제약·검사기 병렬 대수 정의·T131을 함께 읽어 수작업 요소에 대한 제한으로 해석했다. 이는 명세의 범위 표현 누락이며, 기본 검사 요소를 배치 불가로 바꾸라는 요구가 아니다. 명세를 직접 수정하지 않았다.

후보들의 품질 경로를 다시 생성하지 않는 조건부 용량 비교라는 설명, 중복 손실 반영을 피한 정의, 서버를 떠나는 순간 수리를 시작한다는 설명은 코드와 P09·P10·P15에 부합한다. 9-1~9-3을 한 구현 커밋으로 묶었다는 절차 차이는 공개되어 있고 별도의 동작 수정 요구로 세지 않는다.

## 이번 반례와 검증 결과

파일: handoff/reviews/probes/test_probe_016.py. P01–P02는 015 수정 재검증, P03–P10·P16은 이번 diff의 형식·순서·중복·경계·정지 조합 반례, P11은 명세 이견의 독립 계산, P12–P15는 보존·제출물 검증이다.

| ID | 입력 | 예상·명세 근거 | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | 없는 보고서 열 → 짧은 행 → 빈 셀 → 정상 숫자 참조 | 앞 둘은 표 오류, 빈 실제 셀은 허용, 다음 정상 참조도 허용(8단계 근거 참조 규칙) | 앞 둘 ValueError 및 1.evidence 오류, 빈 값 유지, 다음 0.314159 허용 | 통과·015 H3 해결 |
| P02 | 두 PFMEA 항목에 현재 근거·완료 조치 근거·외부 관측값 배치 | 근거와 외부 값·판정이 올바른 항목에 표시(8단계 보고서 목적) | 두 참조·조치 참조·0.314159·미충족 표시, 앞 항목에 관측값 혼입 없음 | 통과·015 M2 해결 |
| P03 | generator 누락, 최상위 [], 숫자 generator, 배열 step | 모두 위치 포함 종료 3, 보고서 없음(:61–64, :191) | 각각 종료 2/1/1/1, 뒤 셋 traceback. 보고서 없음 | 실패 4개 하위 사례 → R16-H1 |
| P04 | P1-2의 동일 선행 ID 두 번 | 명시적 거절 또는 동일 의존성으로 처리. 허용 뒤 설명 불가한 배치 불가 판정은 없어야 함 | 허용·휴리스틱 8개·최적 None | 실패 → R16-M1 |
| P05 | 순가동 47,560.020초, 최적 배치, A 20개, LIGHT/FINAL 시도 쌍은 테스트에 고정. machines 키 순서만 역전 | 동률이면 항상 실제 (LEAK,LIGHT,FINAL)=(2,1,2), 입력 순서 무관(:167) | 원래 (2,1,2), 역전 (2,2,1). 면적 둘 다 9,180,000 | 실패 → R16-H2 |
| P06 | 실제 측정 생성기 시드 0·10001제품 | 제품 번호 순서 1…10001(:125) | 첫 역전 위치 1001, 실제 GEN_10000 | 실패 → R16-H3 |
| P07 | 허용 문법의 긴 양수 문자열 초 | 정확한 정수 밀리초, 중간 반올림 없음(:17, :72) | 기대 123456789012345678901234567890123, 실제 123456789012345678901234567900000 | 실패 → R16-H4 |
| P08 | 기본 설정의 수요만 2600, 임시 폴더 CLI | 배치 불가·종료 0, SVG 없음, 저장 안내도 실제 파일과 일치 | CSV 두 개만 생성했지만 SVG도 저장했다고 표시 | 실패 → R16-M2 |
| P09 | 검사 서버 2개, 둘 다 정지, 하류 5초·버퍼 0, 검사 10초·수리 100초·3제품 | 막힘이 서버 2의 수리 시작도 늦춤(:123, :127) | 종료 125초·막힘 5초·수리 합 200초, 검사 작업 30초·하류 15초 | 통과 |
| P10 | B는 첫 작업장 시간 0, 뒤 작업장 2초, 다음 A는 첫 1초·뒤 1초. visits=0 별도 경계 | B는 첫 작업장을 건너뛰고 A는 상류에서 막힘; 방문 0은 대상 없음 | 종료 3초, 첫 작업장 작업·막힘 각 1초; cycle_limits None | 통과 |
| P11 | T143 두 제품 직접 경로 | 정의에 따른 종료 20초·UPH 360/180·유출 1 | 모두 일치 | 통과·산술 반박 수용 |
| P12 | 015 기준 보호 blob·PFMEA 수정 뒤 9단계 경계 blob 비교 | 승인된 015 수정 외 기존 소스·테스트·설정·자료·보고서 보존 | 보호 133개, 기존 보고서 58개 동일. 9단계 직전의 136개 전부 동일. PFMEA 테스트는 11줄 추가·삭제 0 | 통과 |
| P13 | v1–측정 샘플 7종, 기존/측정 seed42·500제품 재생 | 기존 판정·생성·보고서 동일 | 보고서 47개 및 생성 CSV/meta 4개 바이트 동일 | 통과 |
| P14 | PFMEA 제출 표·시드 0–29·500제품 재생 | 015 수정 제출 CSV·Markdown과 동일, 입력 표 불변 | 두 산출물 모두 바이트 동일, 입력 불변 | 통과 |
| P15 | 라인 제출 실행 시드 0–29·1000–1029·각 500제품 | 제출 balance.csv·compare.csv·SVG와 동일 | 세 파일 모두 바이트 동일 | 통과 |
| P16 | bool 버퍼 수량 오류 직후 정상 입력, 임시 폴더 두 개 | 오류는 종료 3·파일 없음, 다음 정상 실행은 동일 산출물(:17, :61, T146) | 거절 뒤 보고서 없음, 두 정상 실행의 세 파일 바이트 동일 | 통과 |

## 보존 조건과 검증 한계

- **기존 테스트 무수정:** 지정 기준 대비 tests/test_pfmea.py의 기존 두 메서드 안에 015 해결용 검증 11줄을 추가한 예외가 있다. 기존 줄 삭제·변경은 없고 다른 기존 테스트는 모두 바이트 동일하다. 9단계 자체는 ee0ecb2 이후 기존 테스트를 수정하지 않고 test_line.py만 추가했다. 따라서 지정 범위 전체가 “기존 테스트 파일 완전 무수정”이라고 과장하지 않는다.
- **기존 보고서 동일:** 지정 기준에 있던 보고서 59개 중 PFMEA Markdown만 015 M2의 승인 범위에서 15줄이 추가됐다. 나머지 58개는 blob이 동일하다. 9단계 직전 ee0ecb2 기준으로는 기존 보고서 전부 동일하다. P13은 기존 샘플·생성 보고서 47개를 실제 재생했고 P14는 PFMEA CSV·수정 Markdown 두 개를 재생 일치시켰다.
- **평가 보고서:** 기존 eval_*.csv 10개는 소스·설정과 함께 blob 보존을 확인했다. 이번에는 장시간 평가 명령을 다시 실행하지 않았으므로 새 평가 실행에 의한 재생 일치는 미검증이다. 과거 015의 재생 결과를 이번 실행처럼 기재하지 않는다.
- **기존 전체 테스트 통과:** 지정 명령은 딱 한 번 호출했고 런처 단계에서 실패했다. 대체 실행 파일로 전체 테스트를 재시도하지 않았다. 제출 로그의 249개 통과는 작성자 측 결과이며 T152의 독립 전체 통과는 이번에 확인하지 못했다.
- **신규 제출물:** P15의 전체 제출 조건 재생으로 README의 선택 2-1-1·개발 양품 UPH 182.8008·홀드아웃 185.6781 및 제출 파일의 재현성에 동의한다. 이 고정 설정의 성공은 위 경계 입력 결함을 해소하지 않는다.
- **실행 환경:** 아래 추가 반례는 설치된 Python 3.12.10 실행 파일을 직접 지정해 한 번 실행했다. Python 3.9와 py 런처의 정상 동작은 미검증이다. SVG의 바이트 재생은 확인했으나 실제 화면 렌더링은 검증하지 않았다.

## 실행 명령과 결과 원문

전체 테스트(한 번만 실행, 종료 코드 1):

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONIOENCODING='utf-8'; py -m unittest discover -s tests
~~~

~~~text
No installed Python found!
~~~

지정 반례 명령(런처 실패, 종료 코드 1):

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONIOENCODING='utf-8'; py -m unittest handoff/reviews/probes/test_probe_016.py
~~~

~~~text
No installed Python found!
~~~

추가 반례 실행(전체 테스트 재실행 아님, 종료 코드 1):

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONIOENCODING='utf-8'; & 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff/reviews/probes/test_probe_016.py
~~~

~~~text
P01: missing column/short row rejected; blank retained; following numeric reference accepted
.P02: current/action references and external observation retained under the correct item
.P03 missing generator: exit=2; traceback=False; reports=False
FP03 top-level array: exit=1; traceback=True; reports=False
FP03 numeric generator path: exit=1; traceback=True; reports=False
FP03 array step: exit=1; traceback=True; reports=False
FP04: duplicate accepted; optimal=None; heuristic stations=8
FP05: key order=('LEAK', 'LIGHT', 'FINAL'); chosen LEAK/LIGHT/FINAL=(2, 1, 2); area=9180000
P05: key order=('FINAL', 'LIGHT', 'LEAK'); chosen LEAK/LIGHT/FINAL=(2, 2, 1); area=9180000
FP06: routes=10001; first mismatch at position=1001; actual slice=[998, 999, 1000, 10000, 10001, 1001, 1002, 1003]
FP07: expected_ms=123456789012345678901234567890123; actual_ms=123456789012345678901234567900000; errors=[]
FP08: files=['line_balance.csv', 'line_compare.csv']; stdout='고정 경로·정지 시나리오에 조건부인 용량 비교다. 설비 증설의 품질·신뢰성 효과를 평가하지 않는다.\n배치 불가\n저장 파일: reports/line_balance.csv, reports/line_compare.csv, reports/line_layout.svg\n'
FP09: blocked release at 15s delays server-2 repair; end=125s, blocking=5s, repair=200s
.P10: B bypasses first station; A blocks there 1s; absent inspection has no limit
.P11: T143 formula supports Claude: end=20s, pass_uph=360, good_uph=180, escaped=1
.P12: base protected blobs=133; old reports protected=58; all stage-9 predecessor blobs=136; PFMEA regression tests additions=11/deletions=0
.P13: legacy report replays byte-identical=47; generated CSV/meta=4
.P14: corrected PFMEA CSV/Markdown match a fresh full submitted-input replay; table unchanged
.P15: submitted line CSV/CSV/SVG match a fresh full submitted-input replay
.P16: boolean count rejected without reports; following valid run reproducible across 2 folders
.
======================================================================
FAIL: test_p03_malformed_line_input_must_exit_3 (handoff.reviews.probes.test_probe_016.DiffProbes.test_p03_malformed_line_input_must_exit_3) (case='missing generator')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_016.py", line 136, in test_p03_malformed_line_input_must_exit_3
    self.assertEqual(result.returncode, 3, result.stderr)
AssertionError: 2 != 3 : 오류: 'generator'


======================================================================
FAIL: test_p03_malformed_line_input_must_exit_3 (handoff.reviews.probes.test_probe_016.DiffProbes.test_p03_malformed_line_input_must_exit_3) (case='top-level array')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_016.py", line 136, in test_p03_malformed_line_input_must_exit_3
    self.assertEqual(result.returncode, 3, result.stderr)
AssertionError: 1 != 3 : Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 1000, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 979, in main
    outcome, rows, selected = run(args.line, args.seeds, args.holdout_seeds, args.products)
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 929, in run
    config, _, recipe, book = load_setup(path.parent / raw["generator"])
                                                       ~~~^^^^^^^^^^^^^
TypeError: list indices must be integers or slices, not str


======================================================================
FAIL: test_p03_malformed_line_input_must_exit_3 (handoff.reviews.probes.test_probe_016.DiffProbes.test_p03_malformed_line_input_must_exit_3) (case='numeric generator path')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_016.py", line 136, in test_p03_malformed_line_input_must_exit_3
    self.assertEqual(result.returncode, 3, result.stderr)
AssertionError: 1 != 3 : Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 1000, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 979, in main
    outcome, rows, selected = run(args.line, args.seeds, args.holdout_seeds, args.products)
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 929, in run
    config, _, recipe, book = load_setup(path.parent / raw["generator"])
                                         ~~~~~~~~~~~~^~~~~~~~~~~~~~~~~~
TypeError: unsupported operand type(s) for /: 'WindowsPath' and 'int'


======================================================================
FAIL: test_p03_malformed_line_input_must_exit_3 (handoff.reviews.probes.test_probe_016.DiffProbes.test_p03_malformed_line_input_must_exit_3) (case='array step')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_016.py", line 136, in test_p03_malformed_line_input_must_exit_3
    self.assertEqual(result.returncode, 3, result.stderr)
AssertionError: 1 != 3 : Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 1000, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 979, in main
    outcome, rows, selected = run(args.line, args.seeds, args.holdout_seeds, args.products)
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 932, in run
    line = load_line(path, recipe.models)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 267, in load_line
    if step not in steps | inspections:
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: unhashable type: 'list'


======================================================================
FAIL: test_p04_duplicate_predecessor_does_not_destroy_feasible_balance (handoff.reviews.probes.test_probe_016.DiffProbes.test_p04_duplicate_predecessor_does_not_destroy_feasible_balance)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_016.py", line 155, in test_p04_duplicate_predecessor_does_not_destroy_feasible_balance
    self.assertEqual(best, balance(), 'An accepted repeated edge must not change its dependency set')
AssertionError: None != Balance(stations=(('P1-1', 'P1-2'), ('P2-[144 chars]169)) : An accepted repeated edge must not change its dependency set

======================================================================
FAIL: test_p05_machine_key_order_must_not_change_canonical_tie_break (handoff.reviews.probes.test_probe_016.DiffProbes.test_p05_machine_key_order_must_not_change_canonical_tie_break)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_016.py", line 179, in test_p05_machine_key_order_must_not_change_canonical_tie_break
    self.assertEqual(selections, [(2, 1, 2), (2, 1, 2)])
AssertionError: Lists differ: [(2, 1, 2), (2, 2, 1)] != [(2, 1, 2), (2, 1, 2)]

First differing element 1:
(2, 2, 1)
(2, 1, 2)

- [(2, 1, 2), (2, 2, 1)]
?                  ---

+ [(2, 1, 2), (2, 1, 2)]
?                 +++


======================================================================
FAIL: test_p06_product_number_boundary_9999_10000 (handoff.reviews.probes.test_probe_016.DiffProbes.test_p06_product_number_boundary_9999_10000)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_016.py", line 188, in test_p06_product_number_boundary_9999_10000
    self.assertIsNone(first, 'Input order must follow product number across the four-digit boundary')
AssertionError: 1001 is not None : Input order must follow product number across the four-digit boundary

======================================================================
FAIL: test_p07_long_valid_seconds_are_exact_integer_milliseconds (handoff.reviews.probes.test_probe_016.DiffProbes.test_p07_long_valid_seconds_are_exact_integer_milliseconds)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_016.py", line 197, in test_p07_long_valid_seconds_are_exact_integer_milliseconds
    self.assertEqual(actual, expected)
AssertionError: 123456789012345678901234567900000 != 123456789012345678901234567890123

======================================================================
FAIL: test_p08_no_balance_cli_reports_only_files_actually_saved (handoff.reviews.probes.test_probe_016.DiffProbes.test_p08_no_balance_cli_reports_only_files_actually_saved)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_016.py", line 211, in test_p08_no_balance_cli_reports_only_files_actually_saved
    self.assertNotIn('line_layout.svg', result.stdout, 'The no-SVG branch must not announce a saved SVG')
AssertionError: 'line_layout.svg' unexpectedly found in '고정 경로·정지 시나리오에 조건부인 용량 비교다. 설비 증설의 품질·신뢰성 효과를 평가하지 않는다.\n배치 불가\n저장 파일: reports/line_balance.csv, reports/line_compare.csv, reports/line_layout.svg\n' : The no-SVG branch must not announce a saved SVG

----------------------------------------------------------------------
Ran 16 tests in 38.627s

FAILED (failures=9)
~~~

VERDICT: FIX
