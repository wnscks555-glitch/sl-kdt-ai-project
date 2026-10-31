검수 모델: gpt-6.1-sol

# 리뷰 020 — 리뷰 019 재검토 및 v2 12단계 검수

검수일: 2026-10-31. 대상: `4955767cc1a88ea7efc25703133878309a06e022..12c061768c75f80f8bf67d11fa0c73e6b9bc6848`.

**판정 FIX. 리뷰 019의 높음 3건·중간 1건은 모두 해결됐다. 이번 diff의 새 MSA 코드에서 높음 3건을 확인했다. 미해결 수정 요구는 3건이다.** 낮음은 수정 요구로 세지 않는다.

기준은 `handoff/tasks.md` 맨 위 12단계 명세·기대표와 이전 단계 보존 조건이다. setup-notes, tasks, gpt-log, decisions, 리뷰 019, 최근 git log와 지정 diff를 읽었다. 플러그인 리뷰 스킬·보조 에이전트는 사용하지 않았다. 작업 조율에만 로컬 `practical-work-operation`을 적용했다. `docs/solutions/`와 `.compound-engineering/`는 없었으며, 이전 docs 문서를 판정 기준으로 삼지 않았다.

**미해결 지적**

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| R20-H1 | 높음 | `src/msa.py:405`, `src/msa.py:407`, `src/msa.py:408` | 가드밴드의 정확한 안쪽 자름이 Decimal 기본 28자리 문맥 때문에 깨진다. 큰 정상 배수는 예외로 종료한다. | P06: `g=10^-35`, GRR=0.1, 규격 7~13. 명세 tasks:48·112의 제한 없는 소수 문자열과 정확한 계산에 따르면 한계는 7.001/12.999다. 실제는 7.000/13.000으로, 양수 폭이 덧셈에서 사라져 경계 측정값을 합격시킨다. P07: 문법상 유효한 `g=10^40`은 `가드 불가`여야 하지만 CLI가 quantize의 InvalidOperation으로 종료 1, 보고서 미생성이다. 두 입력 모두 설정 검증을 통과한다. | 곱셈·덧셈·양자화 전체의 정밀도를 입력 자릿수와 소수 자릿수에 맞추거나 정확한 분수/정수 연산으로 계산한다. 큰 폭은 정확히 가드 불가로 처리한다. 미세 양수와 큰 배수의 CLI·경계 판정 회귀를 함께 둔다. 자릿수 상한을 추가하려면 별도의 명세 이견으로 공개한다. |
| R20-H2 | 높음 | `src/msa.py:471`, `src/msa.py:492` | 유효한 큰 공정 Cpk를 읽은 뒤 보고서 표시에서 처리되지 않은 수치 예외가 발생한다. | P09: 공정 Cpk만 `1e200`으로 바꾼 측정 생성 설정은 기존 `check_measured_config`를 통과한다. MSA는 parts/operators/trials=2, 제품 30, 개발 0·홀드아웃 100으로 실행했다. 측정값은 전부 10.000으로 확정 가능하지만, `cpk_true`를 표시할 때 재사용한 `anomaly.show`의 28자리 quantize에서 InvalidOperation이 발생해 종료 1이다. tasks:56·102·144에 이 유한한 양수 Cpk를 배제하는 상한은 없다. 이는 R19-H3의 line.show 수정과 별개인 새 MSA 표시 경로다. | MSA가 수용하는 수치의 자릿수를 보고 단계까지 보존하는 표시 함수를 사용한다. 기존 anomaly 코드를 바꾸지 않고도 MSA 안에서 처리할 수 있다. 큰 Cpk의 보고서 전체 경로를 검증한다. |
| R20-H3 | 높음 | `src/msa.py:348` | 0이 아닌 작은 σ를 제곱하면서 0으로 언더플로시켜 관측 Cpk 계산이 0 나눗셈으로 실패한다. | P14: P09와 같은 유효한 규격 7~13·Cpk=`1e200`에서 σ=`6/(6*1e200)`는 약 `1e-200`이고 0이 아니다. 확정 연구의 GRR=0이면 tasks:102의 식과 T196의 무오차 성질상 관측 Cpk는 원래 Cpk다. 직접 호출은 `sigma ** 2 == 0.0` 때문에 ZeroDivisionError다. P09 CLI에서는 H2가 먼저 발생하므로, H3의 근거는 이 독립 계산 반례이며 CLI가 H3까지 진행됐다고 주장하지 않는다. | 직접 제곱의 언더플로를 피하는 `hypot` 또는 비율 기반의 안정된 계산을 사용한다. H2 표시 수정 뒤에도 같은 입력이 전체 보고서까지 완주하는지 확인한다. |

H1은 명시한 합격 한계와 다른 판정 및 허용 입력의 예외 종료, H2·H3은 허용 측정 설정의 계산·보고 계약 위반을 근거로 높음이다. 입력의 실무상 빈도나 수정 비용은 심각도에 반영하지 않았다.

**리뷰 019 항목별 판정**

| 이전 항목 | 심각도 | 재판정 | 현재 근거 |
| --- | --- | --- | --- |
| R19-H1 | 높음 | 해결 | `two_sided_item`이 Decimal 수치로 비교하고 station/anomaly가 이를 함께 쓴다. P01은 A의 7.000/13.000을 보존하고 B만 7/13으로 변경했다. 공통 측정 설정 검증, station의 12제품 생성, anomaly 및 새 MSA의 규격 로드가 모두 성공했다. |
| R19-H2 | 높음 | 해결 | 요청마다 절대 deadline을 만들고 조각 수신마다 남은 시간을 적용한다. P04의 0.04초 간격 11바이트 응답은 총 제한 0.2초를 넘기면 ModbusTimeout 및 연결 닫힘이다. P05는 연결을 유지한 채 제한보다 긴 요청 간 대기 후 두 번째 정상 요청도 성공해, 마감이 요청마다 새로 잡힘을 확인했다. |
| R19-H3 | 높음 | 해결 | `line.show`가 정수·분수 연산으로 ROUND_HALF_UP을 구현한다. P02의 긴 시간 전체 CLI·CSV와 양/음의 반올림 경계가 일치했다. P13의 기본 라인 보고서 3개도 저장된 파일과 바이트 동일하다. 새 MSA의 H2는 이 수정의 미해결로 중복 계상하지 않는다. |
| R19-M1 | 중간 | 해결 | 측정별 거절 집합을 두고 새 측정 공개 때 비운다. P03의 A→B→빈 쌍→A→B→A에서 서로 다른 두 쌍만 각 한 번 기록됐다. 거절 중 WAIT_JUDGE·판정·처리 수는 유지되고 정상 접수·배출 후 새 측정에서는 같은 거절 쌍을 다시 기록한다. |

gpt-log의 네 수정 설명은 위 반례와 현재 코드가 뒷받침하므로 수용한다. 네 항목에 대한 별도 반박은 없었다. 이전 반례 파일은 실행하지 않았다. 014–018의 전체 반례 재감사도 하지 않았으며, 이번 변경에 직접 관련된 경로와 아래 보존 검증을 수행했다.

**보존·현행 명세 확인**

- 기존 테스트의 `test_*` 본문 360개가 기준 커밋과 AST 기준으로 동일하다. 수정된 기존 테스트 파일은 새 회귀 시험 추가와 Modbus FakeServer 보조 코드 보강이며, 기존 테스트 본문 제거·변경은 없다. **본문 보존은 통과이고, 실행 통과는 미검증이다.**
- 기준 커밋의 설정·데이터·보고서 109개는 Git 정규화 내용 해시가 전부 동일하다. 저장소가 `core.autocrlf=true`이고 기존 파일의 실제 LF/CRLF가 섞여 있어 이 검사는 줄바꿈을 정규화했다. 이것만으로 원시 바이트 재생성 일치를 주장하지 않는다.
- P13은 저장소 원본을 건드리지 않고 tempfile 아래에서 실제 기본 CLI를 실행했다. 이번 변경의 영향을 받는 기존 라인 3개·스테이션 16개·이상 검출 3개, **기존 보고서 합계 22개가 저장된 파일과 원시 바이트까지 동일**하다. 새 MSA 보고서 3개도 저장된 결과와 동일했다. 그 밖의 기존 보고서는 Git 내용 보존만 확인했으며 재생성은 하지 않았다.
- 12단계 구현 커밋 `e93b5c9..HEAD`에서는 앞선 코드·테스트 수정이 없고 새 msa 코드·테스트·설정·보고서와 README 추가가 들어갔다. 지정 전체 diff에 보이는 기존 코드 수정은 그 앞의 019 수정 커밋이다. 기존 설정·데이터·보고서의 수정 diff는 없다.
- 분산 분석의 SS·자유도·합침 조건·분산 성분은 현재 명세와 일치한다. P10의 비균등 값 연구는 총제곱합 분해 및 이동/3배 확대 불변성을 정확한 Fraction으로 통과했다. T190–T201·T249–T250의 테스트 원문도 기대표와 대조했지만 해당 기존 테스트의 실행 통과를 주장하지 않는다.
- P11은 홀드아웃만 바꿔 개발 행과 선택이 불변이고 홀드아웃 집계만 바뀜을 확인했다. 선택 기준을 완화하거나 홀드아웃으로 다시 선택하는 경로는 찾지 못했다. gpt-log의 “확정한 참값에 오차를 더한다” 해석과 제곱 비율을 이용한 %GRR 계산은 명세의 순서·산식과 부합해 수용한다.
- README의 12단계 %GRR·판정·선택 배수·홀드아웃 값·작업자 민감도 표는 재생성한 보고서와 일치했다. “합성”, 고정 K1 근사, 독립 작업자 오차 단순화, 민감도의 참고값 성격도 공개돼 있다.
- 낮음 기록: `handoff/tasks.md:410`의 초기값 표는 여전히 “마지막 거절 쌍: 없음”이라고 써서 현재 집합 구현을 정확히 설명하지 않는다. 동작 영향이 없으며 수정 요구로 세지 않는다. 019의 낮음 L1도 이번에 수정되지 않았고 중간 이상으로 다시 세지 않았다.
- 새로운 기대표를 수정하지 않았다. 12단계 명세와 구현은 같은 커밋이므로 Git 이력만으로 결과 전 고정 시점까지 입증하지는 못한다. gpt-log의 고정 설명과 충돌하는 결과 후 완화 증거는 이번 diff에서 발견하지 못했다.

**이번 반례**

파일은 `handoff/reviews/probes/test_probe_020.py`다. 최종 14개 메서드의 확인 결과는 **10개 통과, 3개 assertion 실패, 1개 수치 예외**다. P13은 최초 실행에서 확인했고, 나머지 13개는 마지막 실행 결과다. P06·P07은 같은 H1로 묶었다. P12의 중간 검수 코드 오류는 바로잡고 재확인했으며 제품 지적으로 세지 않았다.

| 반례 | 입력 | 예상·명세 근거 | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | A는 7.000/13.000, B는 7/13인 설정을 station/anomaly/msa에 공유 | 공통 규격의 수치 동등성 유지, 정상 로드 | 세 경로 성공, station 12제품 | 통과·R19-H1 해결 |
| P02 | 30자리 정수부 period, ±0.00005와 ±1/3 | 허용 긴 시간의 정확한 순가동 표시 및 HALF_UP | net_seconds 123456789012345678901234564890.1230, 반올림 일치 | 통과·R19-H3 해결 |
| P03 | 같은 거절쌍을 빈쌍·다른 쌍 사이에 반복, 정상 배출 후 새 측정에서 재사용 | 한 측정에서 각 1회, 거절 상태 불변, 새 측정은 새 기록 | 각 1회, 정상 접수·처리 후 새 거절 1회 | 통과·R19-M1 해결 |
| P04 | 응답을 0.04초마다 1바이트, 총 마감 0.2초 | 총 응답 마감 초과 중단·연결 닫힘 | ModbusTimeout, closed | 통과·R19-H2 해결 |
| P05 | 정상 요청 뒤 0.55초 대기, 제한 0.5초로 같은 연결에서 재요청 | 요청마다 마감 초기화 | 두 번 모두 [7] | 통과 |
| P06 | g=10^-35, GRR=0.1, 규격 7~13 | 정확히 양수인 폭을 안쪽으로 잘라 7.001/12.999 | 7.000/13.000 | 실패→H1 |
| P07 | 유효 후보 g=10^40, 작은 실제 MSA CLI | 가드 불가, 선택 없음, 정상 보고 | InvalidOperation, 종료 1 | 실패→H1 |
| P08 | 게이지 null·배열·개행 이름, 0/00.000 중복, 겹친 시드, bool, 빈 inspection | 타입·중복·범위 위반 종료 3, 파일 없음 | 7개 서브테스트 모두 일치 | 통과 |
| P09 | 공통 생성 검증 통과 Cpk=1e200, 최소 연구, 제품 30 | 10.000 확정 연구와 큰 Cpk를 정상 보고 | cpk_true 표시 InvalidOperation, 종료 1 | 실패→H2 |
| P10 | 3×2×3 비균등 연구를 1000000 이동·3배 확대 | 총 SS 분해, SS·분산 9배, 합침·판정 불변 | 정확히 일치 | 통과 |
| P11 | 개발 자료 고정, 홀드아웃 100→700–702 변경 | 개발 집계·선택 불변, 평가 집계 변경 | 일치 | 통과 |
| P12 | 기준 커밋의 test_* 본문과 기존 설정·데이터·보고서 | 기존 본문 및 Git 내용 보존 | 360개·109개 일치 | 통과, 전체 테스트 실행과 구분 |
| P13 | 기본 line/station/anomaly/msa CLI를 임시 폴더에서 실행 | 기존 보고서 동일, 새 제출 보고서 재현 | 기존 22개·신규 3개 바이트 동일 | 통과 |
| P14 | Cpk=1e200, σ=6/(6×Cpk), GRR=0 | 무오차이면 관측 Cpk=원래 Cpk | σ² 언더플로로 ZeroDivisionError | 오류→H3 |

P03의 새 측정 조합, P05–P11 및 P14 등 최소 5개 이상은 기대표에 없는 입력·경계 조합이다. 모든 생성 파일은 tempfile 아래에만 썼고 저장소 reports/data를 덮어쓰지 않았다.

**실행 명령과 결과**

모든 Python 실행에 `PYTHONDONTWRITEBYTECODE=1`을 적용했고, 반례와 자식 CLI는 UTF-8 출력을 사용했다. 아래 전체 테스트 명령은 **한 번만 호출**했다. 런처가 시작하지 못해 unittest가 0개도 실행되지 않았고, 전체 테스트 재시도·우회 실행은 하지 않았다. 구현자가 남긴 397개 OK 로그는 이번 직접 검증으로 대체하지 않았다.

~~~powershell
py -m unittest discover -s tests
~~~

종료 코드 1, 출력 원문:

~~~text
No installed Python found!
~~~

지정 반례 명령도 직접 호출했다.

~~~powershell
py -m unittest handoff/reviews/probes/test_probe_020.py
~~~

종료 코드 1, 출력 원문:

~~~text
No installed Python found!
~~~

설치된 인터프리터로 이번 반례만 실행했다. 시스템 설정·런처·원본 테스트는 바꾸지 않았다.

~~~powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff/reviews/probes/test_probe_020.py
~~~

이 최초 실행 시 파일은 P01–P13이었다. 출력의 진행·집계 원문은 다음과 같다. 실패 4개 중 P06·P07·P09는 제품 지적이고, P12는 Git blob LF와 실제 파일 CRLF를 직접 비교한 검수 코드 오류였다.

~~~text
.....FF.F..FP13 src.line regenerated_equal=3
P13 src.station regenerated_equal=16
P13 src.anomaly regenerated_equal=3
P13 src.msa regenerated_equal=3
.
----------------------------------------------------------------------
Ran 13 tests in 264.160s

FAILED (failures=4)
~~~

P12를 Git filters로 재구성하도록 바꾸고 P14를 추가한 중간 확인 명령:

~~~powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff.reviews.probes.test_probe_020.Probe020.test_p12_original_test_bodies_and_committed_artifacts_unchanged handoff.reviews.probes.test_probe_020.Probe020.test_p14_observed_cpk_with_nonzero_subsquare_sigma
~~~

중간 실행 집계 원문:

~~~text
Ran 2 tests in 1.326s

FAILED (failures=1, errors=1)
~~~

여기서 P12는 기존 `recipes/anomaly_lamp.json`의 실제 LF를 CRLF 재구성본과 비교해 실패했다. P14는 `observed_cpk(1.33, 1e-200, 0.0)`의 ZeroDivisionError였다. P12는 최종적으로 Git 정규화 해시 비교로 고쳤고 P14는 P09와 같은 실제 설정의 Cpk·σ 조합으로 맞췄다. 제품 코드는 수정하지 않았다.

~~~powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff.reviews.probes.test_probe_020.Probe020.test_p12_original_test_bodies_and_committed_artifacts_unchanged
~~~

종료 코드 0, 출력 원문:

~~~text
P12 original_test_bodies=360 git_unchanged_artifacts=109
.
----------------------------------------------------------------------
Ran 1 test in 7.186s

OK
~~~

최종 파일에서 이미 바이트 일치를 확인한 P13만 제외하고 나머지 13개를 실행했다. P13의 긴 모델 학습·보고서 재생성은 반복하지 않았다.

~~~powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -c "import unittest; from handoff.reviews.probes.test_probe_020 import Probe020; names = [name for name in unittest.defaultTestLoader.getTestCaseNames(Probe020) if not name.startswith('test_p13_')]; result = unittest.TextTestRunner().run(unittest.TestSuite(Probe020(name) for name in names)); raise SystemExit(not result.wasSuccessful())"
~~~

종료 코드 1, 최종 출력 원문:

~~~text
.....FF.F..P12 original_test_bodies=360 git_unchanged_artifacts=109
.E
======================================================================
ERROR: test_p14_observed_cpk_with_nonzero_subsquare_sigma (handoff.reviews.probes.test_probe_020.Probe020.test_p14_observed_cpk_with_nonzero_subsquare_sigma)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_020.py", line 282, in test_p14_observed_cpk_with_nonzero_subsquare_sigma
    self.assertEqual(msa.observed_cpk(cpk, sigma, 0.0), cpk)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\msa.py", line 348, in observed_cpk
    return cpk * sigma / math.sqrt(sigma ** 2 + grr ** 2)
           ~~~~~~~~~~~~^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
ZeroDivisionError: float division by zero

======================================================================
FAIL: test_p06_positive_subprecision_guard_still_rounds_inward (handoff.reviews.probes.test_probe_020.Probe020.test_p06_positive_subprecision_guard_still_rounds_inward)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_020.py", line 175, in test_p06_positive_subprecision_guard_still_rounds_inward
    self.assertEqual(actual, (Decimal("7.001"), Decimal("12.999")), repr(actual))
AssertionError: Tuples differ: (Decimal('7.000'), Decimal('13.000')) != (Decimal('7.001'), Decimal('12.999'))

First differing element 0:
Decimal('7.000')
Decimal('7.001')

- (Decimal('7.000'), Decimal('13.000'))
?               ^              ^ ^^^

+ (Decimal('7.001'), Decimal('12.999'))
?               ^              ^ ^^^
 : (Decimal('7.000'), Decimal('13.000'))

======================================================================
FAIL: test_p07_large_valid_guard_is_unavailable_not_crash (handoff.reviews.probes.test_probe_020.Probe020.test_p07_large_valid_guard_is_unavailable_not_crash)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_020.py", line 180, in test_p07_large_valid_guard_is_unavailable_not_crash
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 1 != 0 : Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\msa.py", line 618, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\msa.py", line 599, in main
    grr_rows, guard_rows, written = run(args.config)
                                    ^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\msa.py", line 584, in run
    studies, grr_rows, guard_rows = analyze(settings, process, config["process_cpk"])
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\msa.py", line 575, in analyze
    guard_rows.extend(guard_gauge(name, gauge, result.grr, settings, process))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\msa.py", line 524, in guard_gauge
    candidates = candidates_of(settings, process, grr)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\msa.py", line 518, in candidates_of
    return [Candidate(multiplier, acceptance_limits(item.lsl, item.usl, multiplier, grr))
                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\msa.py", line 407, in acceptance_limits
    lower = (Decimal(lsl) + width).quantize(unit, rounding=ROUND_CEILING)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
decimal.InvalidOperation: [<class 'decimal.InvalidOperation'>]


======================================================================
FAIL: test_p09_valid_large_process_cpk_completes_reports (handoff.reviews.probes.test_probe_020.Probe020.test_p09_valid_large_process_cpk_completes_reports)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_020.py", line 202, in test_p09_valid_large_process_cpk_completes_reports
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 1 != 0 : Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\msa.py", line 618, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\msa.py", line 599, in main
    grr_rows, guard_rows, written = run(args.config)
                                    ^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\msa.py", line 584, in run
    studies, grr_rows, guard_rows = analyze(settings, process, config["process_cpk"])
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\msa.py", line 574, in analyze
    grr_rows.append(grr_row(name, study, result, tolerance, process, cpk))
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\msa.py", line 492, in grr_row
    "ar_ev": _text(ar_ev), "ar_av": _text(ar_av), "ar_pv": _text(ar_pv), "cpk_true": _text(cpk),
                                                                                     ^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\msa.py", line 471, in _text
    return show(Fraction(value)) if digits == 4 else "%.*f" % (digits, value)
           ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\anomaly.py", line 594, in show
    return str(number.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
decimal.InvalidOperation: [<class 'decimal.InvalidOperation'>]


----------------------------------------------------------------------
Ran 13 tests in 11.864s

FAILED (failures=3, errors=1)

~~~

전체 테스트 무수정 실행 통과는 런처 오류로 미검증이다. 실행 환경의 실패를 제품 결함으로 계상하지 않았고, FIX는 위에서 독립 재현한 H1–H3에 따른다. 이번 검수가 생성·수정한 파일은 이 리뷰와 test_probe_020.py 두 개뿐이다. 시작 때부터 있던 handoff/loop-logs/020-codex.txt는 변경하지 않았다.

VERDICT: FIX
