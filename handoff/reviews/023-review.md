검수 모델: gpt-6.1-sol

# 리뷰 023 — 리뷰 022 재검토 및 v2 15단계 대시보드 검수

검수일: 2026-10-31. 대상: adfbb7fdeced951b5e3eb109f603b29c98267bbb..7d9c886de4c795d2f8481499ba6bc57708385029（검수 시 HEAD）.

**판정 FIX. 리뷰 022의 미해결 높음 1건·중간 3건은 모두 해결됐다. 이번 diff에서 새 높음 2건·중간 5건을 확인했다. 전체 테스트는 지정 명령을 한 번 직접 실행했으나 py 런처 오류로 시작하지 못해 통과 여부는 미검증이다.**

기준은 handoff/tasks.md 맨 위 현행 15단계 명세·T237–T248·T263–T266 및 이전 단계 보존 조건이다. setup-notes, tasks, gpt-log, decisions, 리뷰 022, 최근 git log와 지정 diff를 읽었다. 022 수정 커밋 3fe0761과 대시보드 추가 커밋 7d9c886을 구분했다. practical-work-operation은 범위·보존·검증 조율에만 적용했다. 플러그인 리뷰 스킬·보조 에이전트·이전 반례 파일 실행은 사용하지 않았다. docs/solutions/와 .compound-engineering/config.yaml은 없으며 과거 docs 문서는 판정 기준으로 사용하지 않았다.

## 새 미해결 지적

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| R23-H1 | 높음 | src/dashboard.py:116 | SVG 참조 검사가 대소문자를 구분해 외부 참조를 수용하고 이전 HTML을 교체한다. | P05: 허용된 rect의 fill에 URL(//example.invalid/p.svg#p), uRl(//example.invalid/p.svg#p)를 각각 넣었다. 두 경우 모두 종료 0, 이전 HTML 변경이다. 검사식은 소문자 url(만 찾고, 이 입력에는 콜론·역슬래시도 없다. 현행 SVG 허용 규칙은 같은 문서의 url(#id)만 허용하고 T242·T244는 외부 참조 거절·이전 HTML 보존을 요구한다. 외부 URL 문자열이 들어간 HTML 생성을 확인했으며 실제 브라우저의 외부 요청 실행은 검증하지 않았다. | 참조 함수의 대소문자까지 검사하고 허용된 내부 참조만 통과시킨다. 혼합 대소문자의 외부·없는 ID 참조도 종료 2이며 이전 HTML이 유지되는지 확인한다. |
| R23-H2 | 높음 | src/dashboard.py:286 | 첫 번째 경보 행만 검사해 이후 경보의 기여값 불일치를 놓친다. | P06: 정상 alarm=1 행 뒤에 t를 1 늘리고 z만 99.0000000000으로 바꾼 두 번째 alarm=1 행을 추가했다. 종료 0이며 이전 HTML이 교체됐다. next가 첫 경보만 고르므로 두 번째 행은 검사·표시되지 않는다. T265는 alarm=1 행의 합과 z 일치, 불일치 복사본 종료 2를 요구한다. | 모든 경보 행의 합을 검사하고 해당 기여값을 표시한다. 여러 경보 중 뒤쪽 행만 틀린 경우도 거절한다. |
| R23-M1 | 중간 | src/dashboard.py:290 | NaN을 기여값 일치로 취급해 신뢰할 수 없는 결과를 출력한다. | P07: 유일한 경보의 z를 nan으로 바꾸면 종료 0이고 HTML이 생성된다. float 변환은 성공하지만 abs(... − nan) > 1e-8은 거짓이어서 검사를 통과한다. 명세가 비유한 입력을 직접 다루지는 않지만 유한한 기여값 합과 NaN의 일치는 성립하지 않는다. | bias·가중치·특징값·z와 계산 결과의 유한성을 먼저 확인하고 비유한 값은 종료 2로 거절한다. |
| R23-M2 | 중간 | src/dashboard.py:390 | PFMEA 탭이 행별 근거와 관측값을 빠뜨린다. | P08: PF-01 evidence 행의 reference를 metric:probe_023_reference, value를 0.123456789023으로 바꾼 복사본은 종료 0이지만 두 값 모두 PFMEA의 정적 표 셀에 없다. 함수는 item 행의 evidence_status와 effect_result만 출력한다. 현행 화면 명세의 “행별 근거·관측값·효과 판정” 중 근거 식별과 관측값이 누락됐다. | item과 evidence 행을 ID로 연결해 근거 참조·조건·관측값을 보고서 문자열대로 표시한다. 실제 사용하는 필수 열도 입력 검사에 포함한다. |
| R23-M3 | 중간 | src/dashboard.py:387 | 이상 검출 그래프에 대응하는 정적 수치 표가 없다. | P09: CUSUM c_plus 한 값을 876.543219023으로 바꾸면 종료 0이고 선 그래프에는 반영되지만 이상 검출 절의 정적 표 셀에는 그 값이 없다. 반환하는 표는 방법 비교와 로지스틱 기여값뿐이며 관리도 시계열·이동량별 검출률 수치 표가 없다. 명세는 그래프에 수치 표를 함께 두고 JavaScript 없이도 내용을 보이도록 요구한다. JSON·포인터 툴팁은 정적 수치 표를 대신하지 못한다. | 관리도 시계열과 이동량별 검출률의 수치 표를 정적 HTML로 함께 제공한다. 보고서 원문 값이 표에 있는지 검사한다. |
| R23-M4 | 중간 | src/dashboard.py:298 | 모든 설비가 표본 부족인 정상 형태의 보고서를 표시하지 못한다. | P10: capability 행 모두 n=1, cpk·ppk 빈칸, status=표본 부족으로 두고 파일·열을 유지했다. 종료 2, “min() iterable argument is empty”가 나온다. 빈 Cpk를 전부 제거한 뒤 min을 호출하기 때문이다. 명세는 표본 부족 표시를 요구하며 적어도 하나의 유효 Cpk가 있어야 한다는 제한은 없다. | 유효 Cpk가 없는 경우 개요에도 표본 부족을 표시하고 측정 표를 계속 만든다. 빈 값을 0이나 추정값으로 채우지 않는다. |
| R23-M5 | 중간 | handoff/tasks.md:16 / src/dashboard.py:643 | 명세 이견: 실제 필수 입력 incident_lamp_pfmea.md가 현행 입력 표에 빠져 있다. | P13: 현행 입력 표에 적힌 파일 22개를 모두 복사해 실행했으나 종료 2, “입력 파일 없음: incident_lamp_pfmea.md”다. gpt-log는 PFMEA 연결을 위해 입력을 추가했다고 공개했지만 기준 명세에는 반영되지 않았다. 입력 목록대로 자료를 준비해도 대시보드를 만들 수 없다. | 현행 입력 명세에 해당 파일과 필수 구조를 추가해 실제 계약과 맞추거나, 명시된 입력만으로 연결할 수 있도록 구현한다. 사전 기대표를 결과에 맞춰 바꾸지 않는다. |

H1·H2는 명시된 거절 조건에서 성공 판정하고 이전 산출물을 교체하므로 높음이다. M1·M4는 명세가 직접 규정하지 않은 비유한 값·전체 표본 부족 조합의 잘못된 처리다. M2·M3는 요구한 표시 내용과 실제 출력의 불일치이며, M5는 기준 입력 명세와 실제 필수 의존성의 불일치다. 이 영향으로 중간을 정했다. 마감·일정·수정 비용으로 심각도를 낮추지 않았다. 낮음 수정 요구는 없다.

## 리뷰 022 항목별 재판정 및 Claude 의견

| 이전 항목 | 재판정 | 근거와 수용 범위 |
| --- | --- | --- |
| R21-H1 유지 / 높음 | 해결 | P01에서 λ=5e-324·1e-200·1e-20·0.2·1의 12회 갱신을 750자리 Decimal 독립 수식과 비교했다. 경보가 일치하고 한계는 양수다. 작은 두 λ의 마지막 한계는 각각 5e-323, 1.0392304845413263e-199로 독립 결과와 같다. 제곱근을 분리했다는 gpt-log의 수정 설명을 수용한다. 모든 유한 부동소수점 조합에 대한 일반적 증명으로 확대하지 않는다. |
| R22-M1 / 중간 | 해결 | P02에서 정상/999.0 limits 행의 양 순서와 동일값 중복을 모두 거절했다. 거절 직후 정상 보고서는 수용했다. load_limits에 _unique를 적용했다는 설명을 수용한다. |
| R22-M2 / 중간 | 해결 | P03에서 t=측정열 길이, t=-1, 시작 전으로 넘치는 창, 빈 창이 모두 ValueError로 거절됐으며 직후 정상 창은 수용됐다. IndexError 이전에 범위를 검사한다는 설명을 수용한다. main이 ValueError를 종료 2로 처리하는 경로도 코드로 확인했다. 이번에 해당 변조를 SPC 전체 CLI로 다시 실행하지는 않았다. |
| R22-M3 / 중간·명세 이견 | 해결 | products 상한 65535가 코드와 현행 14단계 명세에 함께 반영됐다. P04에서 65536·100000·bool 거절, 1·65535 수용을 확인했다. 기존 PLC ID 순환을 유지하며 지원 범위를 제한했다는 설명을 수용한다. 65535제품 전체 소켓 완주는 미검증이다. |

이번 gpt-log에는 이전 지적을 부정하는 별도 반박은 없으며, 수정 근거와 범위 축소 설명을 위 검증 범위에서 받아들였다. 022에서 이미 해결된 R21-M1·M2는 이번 diff에서 관련 본체를 다시 변경하지 않았고 이전 반례 파일을 재실행하지 않았다.

대시보드의 relative --out을 --root 기준으로 해석한 설명, HTML 내용을 먼저 넣고 details를 브라우저 기본 동작으로 펼치는 해석에는 동의한다. P11의 경로 거절 뒤 정상 실행·이스케이프·입력 보존·두 뿌리 반복 결과가 이를 뒷받침한다. 사건 PFMEA 연결을 위해 Markdown 입력을 추가한 이유도 타당하지만, 현행 명세에서 그 입력이 누락된 R23-M5는 남는다.

## 보존 조건과 검증 범위

- 전체 테스트 명령은 한 번 직접 호출했으나 py 런처가 실패했다. 따라서 “기존 테스트 전체 통과”는 미검증이다. handoff/run-logs/v2-15-tests.txt의 531개 OK는 구현자 기록이며 이번 직접 실행 결과로 대신하지 않았다. 다른 인터프리터로 전체 테스트를 재실행하지 않았다.
- P12에서 기준 커밋의 기존 테스트 메서드 501개를 클래스명·메서드명을 포함한 AST로 비교했다. 500개는 동일하고 tests/test_incident.py의 ConfigTests.test_t233_invalid_values 1개에 products=65536 거절 입력만 추가됐다. tests/test_spc.py에는 회귀 테스트 3개가 추가됐으며 기존 본문 변경은 없다.
- 따라서 전체 지정 diff를 두고 “기존 테스트가 전부 무수정”이라고 보고할 수는 없다. 위 변경은 별도 022 수정 커밋 3fe0761의 공개된 범위 제한 검증이며 기존 검증을 약화시키지 않는다. 15단계 추가만 비교한 3fe0761..HEAD에서는 기존 코드·설정·테스트·보고서를 수정하지 않았고 tests/test_dashboard.py와 reports/dashboard.html 등이 추가됐다. 이 범위 구분으로 보존 조건을 평가했으며 수정 검증 추가 자체를 새 회귀로 계상하지 않았다.
- 기준 커밋의 recipes/reports/data 산출물 122개는 HEAD와 Git 정규화 내용이 모두 같았다. Git 내용 비교를 실행 후 원시 바이트 재현과 구분했다.
- P12는 tempfile에서 10단계 all 시나리오 보고서 16개, 기본 14단계 사건 보고서 5개를 실제 CLI 실행으로 다시 만들어 저장본과 원시 바이트 동일함을 확인했다. 변경된 EWMA 식을 쓰는 SPC 그래프 CSV도 정상 학습 시나리오에서 한계를 다시 추정해 400행을 재생성했고 원시 바이트가 같았다. SPC 방법 비교 보고서 전체 및 다른 모든 이전 단계 보고서를 재생성한 것은 아니다.
- P12 실행 전후 저장소의 reports/recipes/data 123개 파일 원시 바이트가 그대로였다. P11에서는 임시 복사 입력 23개도 실행 후 그대로였고, 두 --root에서 만든 HTML은 서로 및 저장된 reports/dashboard.html과 바이트 동일했다.
- 이번 검수에서 실제 브라우저 화면·375px 레이아웃·테마·JavaScript 끄기·외부 요청 여부는 독립 검증하지 않았다. gpt-log의 브라우저 확인은 구현자의 기록으로 읽었으며, “스크립트를 제거한 사본” 확인을 실제 JavaScript 설정 끄기와 같은 검증으로 보고하지 않았다.
- 생성 보고서는 모두 tempfile에 두었다. 이번 검수가 최종 생성·수정한 저장소 파일은 이 리뷰와 probes/test_probe_023.py뿐이다. 시작부터 존재한 handoff/loop-logs/023-codex.txt는 검수자가 수정하지 않았다. 커밋·푸시·설치·원본 코드 수정은 하지 않았다.

## 이번 반례

최종 반례 파일: handoff/reviews/probes/test_probe_023.py. P01–P10·P13은 경계값·중복·거절 직후 정상 입력·빈 값·대소문자·규칙 겹침을 포함한 diff 집중 반례다. 기존 테스트나 이전 반례 파일의 테스트 메서드는 실행하지 않았다.

| 반례 | 입력 | 예상과 명세 근거 | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | λ=5e-324·1e-200·1e-20·0.2·1, 중심0·σ̂1·0.1 12개 | 13단계 EWMA 식과 경보 일치, 표현 가능한 양수 한계 보존 | Decimal 독립 계산과 일치, 한계 양수 | 통과, 이전 H1 해결 |
| P02 | limits 동일 키 정상/999 양 순서·동일값 중복, 이후 정상 | 모순을 순서로 숨기지 않고 중복 거절, 정상 수용 | 3종 거절·정상 수용 | 통과, 이전 M1 해결 |
| P03 | 길이3의 t=3·-1·초과/빈 창, 이후 정상 | 파일 오류는 제어된 거절, 정상은 수용 | ValueError·정상 수용 | 통과, 이전 M2 해결 |
| P04 | products=65536·100000·bool, 이후1·65535 | 수정한 지원 범위·타입 준수 | 잘못된 값 거절, 경계 수용 | 통과, 이전 M3 해결 |
| P05 | SVG fill의 URL/uRl과 // 외부 참조, 이전 HTML 존재 | 내부 참조만 허용, 종료2·이전 HTML 불변 | 양쪽 종료0·이전 HTML 변경 | 실패, R23-H1 |
| P06 | 첫 경보 정상, 두 번째 경보 z=99 | T265상 모든 경보 합 검증, 종료2·이전 HTML 불변 | 종료0·이전 HTML 변경 | 실패, R23-H2 |
| P07 | 경보 z=nan | 유한 합과의 일치 불성립, 거절 | 종료0·HTML 생성 | 실패, R23-M1 |
| P08 | PF-01 evidence 참조와 관측값만 변경 | PFMEA 행별 근거·관측값을 정적 표에 표시 | 종료0, 참조·관측값 표에 없음 | 실패, R23-M2 |
| P09 | CUSUM c_plus=876.543219023 | 그래프와 수치 표를 함께 제공 | 종료0, 해당 정적 수치 표 없음 | 실패, R23-M3 |
| P10 | 모든 capability n=1·Cpk/Ppk 빈칸·표본 부족 | 제한되지 않은 표본 부족을 표시 | 종료2, min 빈 입력 오류 | 실패, R23-M4 |
| P11 | 잘못된 경로3종 후 정상, JSON 공격 문자열·두 root | 경로 거절·문자열 왕복·입력 불변·결정적 출력 | 입력23개 불변, 두 HTML 및 저장본 동일 | 통과 |
| P12 | 기존 테스트501개·기존 산출물122개, station/incident CLI와 SPC chart | 보존 범위를 구분하고 저장본 재현 | 기존 테스트1개만 공개된 입력 추가, 기존 산출물 내용 불변, 16+5+1 보고서 바이트 동일 | 검증한 범위 통과, 전체 테스트 실행과 구분 |
| P13 | 현행 입력 표의22개 파일만 복사 | 선언된 입력으로 정상 실행 | 종료2, 미기재 Markdown 파일 요구 | 실패, 명세 이견 R23-M5 |

최초 P01–P12 실행은 12개 중 6개 통과·6개 실패였다. P11의 출력문에 입력 수를 24로 잘못 적었던 부분을 실제 len=23으로 바로잡고, 추가한 P13과 함께 해당 두 메서드만 실행했다(1개 통과·1개 실패). 최종 파일의 서로 다른 반례 13개 중 확인된 실패는 7개이며 전체 테스트 실행 수와 혼동하지 않았다.

추가로 시험했던 P14(XML text 루트·CDATA)의 “실행 script 생성” 가설은 html.parser에서 입증되지 않았다. 실제 script ID 목록은 기본 3개와 같았고 원문 루트 거절에 대한 별도 명시도 충분하지 않아 해당 단정을 철회했다. 이 후보는 최종 반례 파일과 지적 건수에서 제외했다. 그때의 실제 실패 출력도 아래에 남겼다. 실제 브라우저에서 해당 후보가 안전하다는 결론도 내리지 않는다.

## 실행 명령과 결과 원문

환경 변수 PYTHONDONTWRITEBYTECODE=1, PYTHONIOENCODING=utf-8을 설정했다.

전체 테스트는 다음 명령을 한 번만 직접 실행했다.

~~~powershell
py -m unittest discover -s tests
~~~

종료 코드 1:

~~~text
No installed Python found!
~~~

지정 반례 명령도 직접 실행했다.

~~~powershell
py -m unittest handoff/reviews/probes/test_probe_023.py
~~~

종료 코드 1:

~~~text
No installed Python found!
~~~

기존 설치 Python 3.12로 이번 반례만 실행했다. 설치·런처 설정·원본 테스트는 변경하지 않았다.

~~~powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -B -m unittest handoff/reviews/probes/test_probe_023.py
~~~

종료 코드 1, 최초 12개 출력:

~~~text
P01 lambda/actual/Decimal limit: [(5e-324, 5e-323, 5e-323), (1e-200, 1.0392304845413263e-199, 1.0392304845413263e-199), (1e-20, 1.0392304845413262e-19, 1.0392304845413264e-19), (0.2, 0.997636022563906, 0.997636022563906), (1.0, 3.0, 3.0)]
.P02 contradictory both orders + identical duplicate refused; valid accepted
.P03 t=length, negative, oversized/empty window refused; valid accepted
.P04 products 65536/100000/bool refused; 1/65535 accepted
.P05 function/exit/old-preserved: [('URL', 0, False), ('uRl', 0, False)]
FP06 second alarm z=99 exit/old-preserved: 0 False
FP07 alarm z=nan exit: 0
FP08 PF-01 evidence reference/value in PFMEA table: [False, False]
FP09 CUSUM source value in static detect table: False
FP10 all n=1/blank Cpk/Ppk exit/stderr: 2 오류: min() iterable argument is empty
FP11 rejected paths then valid; JSON roundtrip; 24 inputs unchanged; two roots/stored HTML identical
.P12 reproduced byte-identical src.station 16
P12 reproduced byte-identical src.incident 5
P12 regenerated SPC chart 400 rows byte-identical
P12 base tests/artifacts/changed test: 501 122 [('tests/test_incident.py', 'ConfigTests', 'test_t233_invalid_values')] ; watched raw files unchanged: 123
.
======================================================================
FAIL: test_p05_svg_mixed_case_external_reference_and_atomic_refusal (handoff.reviews.probes.test_probe_023.Probe023.test_p05_svg_mixed_case_external_reference_and_atomic_refusal)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_023.py", line 163, in test_p05_svg_mixed_case_external_reference_and_atomic_refusal
    self.assertEqual(results, [("URL", 2, True), ("uRl", 2, True)])
AssertionError: Lists differ: [('URL', 0, False), ('uRl', 0, False)] != [('URL', 2, True), ('uRl', 2, True)]

First differing element 0:
('URL', 0, False)
('URL', 2, True)

- [('URL', 0, False), ('uRl', 0, False)]
?          ^  ^^^^            ^  ^^^^

+ [('URL', 2, True), ('uRl', 2, True)]
?          ^  ^^^            ^  ^^^


======================================================================
FAIL: test_p06_second_alarm_mismatch_is_not_ignored (handoff.reviews.probes.test_probe_023.Probe023.test_p06_second_alarm_mismatch_is_not_ignored)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_023.py", line 178, in test_p06_second_alarm_mismatch_is_not_ignored
    self.assertEqual(result.returncode, 2)
AssertionError: 0 != 2

======================================================================
FAIL: test_p07_nan_cannot_satisfy_contribution_equality (handoff.reviews.probes.test_probe_023.Probe023.test_p07_nan_cannot_satisfy_contribution_equality)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_023.py", line 190, in test_p07_nan_cannot_satisfy_contribution_equality
    self.assertEqual(result.returncode, 2)
AssertionError: 0 != 2

======================================================================
FAIL: test_p08_pfmea_evidence_and_observation_are_static_cells (handoff.reviews.probes.test_probe_023.Probe023.test_p08_pfmea_evidence_and_observation_are_static_cells)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_023.py", line 207, in test_p08_pfmea_evidence_and_observation_are_static_cells
    self.assertEqual(found, [True, True])
AssertionError: Lists differ: [False, False] != [True, True]

First differing element 0:
False
True

- [False, False]
+ [True, True]

======================================================================
FAIL: test_p09_chart_values_have_static_numeric_table (handoff.reviews.probes.test_probe_023.Probe023.test_p09_chart_values_have_static_numeric_table)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_023.py", line 222, in test_p09_chart_values_have_static_numeric_table
    self.assertTrue(present)
AssertionError: False is not true

======================================================================
FAIL: test_p10_all_insufficient_capability_is_displayable (handoff.reviews.probes.test_probe_023.Probe023.test_p10_all_insufficient_capability_is_displayable)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_023.py", line 235, in test_p10_all_insufficient_capability_is_displayable
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 2 != 0 : 오류: min() iterable argument is empty


----------------------------------------------------------------------
Ran 12 tests in 24.192s

FAILED (failures=6)
~~~

P11 출력문 정정과 P13 추가 후 해당 두 메서드만 실행했다.

~~~powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -B -m unittest handoff.reviews.probes.test_probe_023.Probe023.test_p11_escape_recovery_determinism_and_readonly_inputs handoff.reviews.probes.test_probe_023.Probe023.test_p13_documented_input_manifest_is_sufficient
~~~

종료 코드 1:

~~~text
P11 rejected paths then valid; JSON roundtrip; inputs unchanged: 23 ; two roots/stored HTML identical
.P13 documented manifest only exit/stderr: 2 오류: 입력 파일 없음: incident_lamp_pfmea.md
F
======================================================================
FAIL: test_p13_documented_input_manifest_is_sufficient (handoff.reviews.probes.test_probe_023.Probe023.test_p13_documented_input_manifest_is_sufficient)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_023.py", line 322, in test_p13_documented_input_manifest_is_sufficient
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 2 != 0 : 오류: 입력 파일 없음: incident_lamp_pfmea.md


----------------------------------------------------------------------
Ran 2 tests in 2.288s

FAILED (failures=1)
~~~

최종 지적과 파일에서 제외한 P14 후보의 당시 실행 기록이다.

~~~powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -B -m unittest handoff.reviews.probes.test_probe_023.Probe023.test_p14_xml_text_root_cdata_cannot_create_html_script
~~~

종료 코드 1:

~~~text
P14 XML text-root/CDATA exit/script IDs/old-preserved: 0 ['plc-data', 'chart-data', None] False
F
======================================================================
FAIL: test_p14_xml_text_root_cdata_cannot_create_html_script (handoff.reviews.probes.test_probe_023.Probe023.test_p14_xml_text_root_cdata_cannot_create_html_script)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_023.py", line 346, in test_p14_xml_text_root_cdata_cannot_create_html_script
    self.assertEqual(result.returncode, 2)
AssertionError: 0 != 2

----------------------------------------------------------------------
Ran 1 test in 0.379s

FAILED (failures=1)
~~~

git diff --check는 종료 0, 출력 없음이었다. 전체 테스트 미검증은 환경 한계로 별도 결함 건수에 넣지 않았다. FIX는 위 재현된 새 미해결 7건에 따른다.

VERDICT: FIX
