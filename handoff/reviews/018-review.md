검수 모델: gpt-6.1-sol

# 리뷰 018 — 리뷰 017 재검토 및 현행 v2 11단계 검수

검수일: 2026-10-31. **판정 FIX. 이전 높음 2건·중간 1건은 해결됐다. 신규 미해결 높음 2건·중간 2건으로 수정 요구는 4건이다.** 전체 테스트는 지정 명령을 한 번 직접 호출했으나 런처 오류로 시작되지 않아 **미검증**이다. 이번 반례는 설치된 Python 3.12로 실행해 최종 14개 중 11개 통과·3개 실패다. 실패 3개는 아래 지적과 연결되며, 나머지 중간 1건은 기존 테스트의 검증 공백이다.

## 범위와 수행 경계

- 기준: `handoff/tasks.md` 맨 위 11단계 명세·T172–T189 및 아래 완료 단계의 보존 조건. `docs/`의 과거 문서는 판정 기준으로 사용하지 않았다.
- 근거: `AGENTS.md`, `handoff/setup-notes.md`, `handoff/tasks.md`, `handoff/gpt-log.md`, `handoff/decisions.md`, `017-review.md`, 최근 git 이력, 지정 diff, 관련 소스·테스트·설정·보고서. `docs/solutions/`와 `.compound-engineering/config.yaml`은 없다.
- `practical-work-operation`은 범위·검증 조율에만 적용했다. 플러그인 리뷰 스킬·보조 에이전트는 사용하지 않았다. 이전 반례는 필요한 부분을 읽었으며 import하거나 실행하지 않았다.
- 작성한 파일은 이 파일과 `handoff/reviews/probes/test_probe_018.py`뿐이다. 제품 코드·기존 테스트·설정·보고서는 수정하지 않았다. commit·push·설치·삭제를 하지 않았다. 시작부터 있던 미추적 `handoff/loop-logs/018-codex.txt`는 건드리지 않았다. 출력은 `tempfile` 안에만 만들었고 `PYTHONDONTWRITEBYTECODE=1`로 실행했다.

검토 명령:

~~~text
git diff 63af1957fe73225c1cf8cb8ab4fe8051a6e4e3c9..HEAD
git log -8 --oneline
git status --short
git diff --check 63af195..HEAD
~~~

HEAD: `49dfc799712aebfab3517dfb84f5464b0f96c1e8`. 지정 범위는 다음 세 커밋이다.

~~~text
49dfc79 feat(T172-T189): compare synthetic mean-shift detection methods
4f3f153 docs(T172-T189): confirm stage 11 spec after Sol review
a70f499 fix(T158,T160): apply review 017 reset, framing and value order fixes
~~~

## 이전 높음·중간 항목별 판정

| 이전 항목 | 심각도 | 판정 | 근거 |
| --- | --- | --- | --- |
| R17-H1 | 높음 | **해결** | `src/plc.py:192`에서 복귀 시 공개 측정 워드도 지운다. P01은 음수 측정 공개 → 가드 알람 → 불가능한 reset 거절 → 수동 해제와 새 reset → 다음 제품 공개를 검증했다. 거절 때 워드 유지, 유효 복귀 때 `[0,0]`, ID=1·처리 수=0 유지, PC 소유 코일 유지, 다음 ID=2·값=2.500을 확인했다. gpt-log의 수정 설명을 수용한다. |
| R17-H2 | 높음 | **해결** | `src/modbus.py:224`, `:285`, `:293`이 완성 프레임을 먼저 처리하고 손상에서 닫는다. P02는 유효 FC06 두 개 → 손상 프레임 → 유효 쓰기를 붙인 동일 48바이트의 모든 47개 분할 경계를 서버의 실제 수신 루프에 넣었다. 모두 앞의 쓰기 두 개와 응답 두 개만 보존하고 손상 뒤 쓰기는 처리하지 않았다. P12의 실제 소켓 시나리오 재생도 일치했다. |
| R17-M1 | 중간 | **해결** | `src/station.py:129`가 제품 번호를 정수로 정렬한다. P03은 mock 자료가 아닌 시드 0·10001제품의 각 최초 측정을 ID별로 독립 추출해 모든 위치의 번호·값 대응을 확인했다. gpt-log가 순서를 제품 번호로 확정한 설명을 수용한다. P12에서 기존 20제품 보고서 16개도 바이트 동일했다. |

R17-L1도 지정 diff의 `git diff --check`가 출력 없이 종료 코드 0인 것으로 해소를 확인했다. 수정 요구에 세지 않는다. 017에서 해결된 016 항목의 관련 소스·테스트에는 이번 범위의 추가 변경이 없다.

## 신규 지적 사항

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| R18-H1 | 높음 | `src/anomaly.py:93`, `:141` | 범위를 벗어난 큰 정수 설정이 입력 오류 종료 3 대신 처리되지 않은 예외로 종료 1이 된다. | 현행 명세 `tasks.md:18`, T187은 타입·범위 위반을 종료 3으로 정한다. P05의 JSON `min_detection=10**400`은 명백히 0–1 범위 밖이다. `_number`가 `math.isfinite`에 정수를 넘기며 float 변환 `OverflowError`를 내고 `main`도 이를 처리하지 않는다. 실제 종료 1·traceback, 보고서 미생성을 확인했다. 단순히 NaN을 넣은 기존 사례와 다른 정수 변환 경계다. | 정수와 실수의 유한성 검사를 변환 오류 없이 수행하고 범위 검증을 입력 오류 경로로 연결한다. 다른 수치 키에도 같은 경계를 확인하고 위치 포함 종료 3·traceback 없음·보고서 미생성을 검증한다. |
| R18-H2 | 높음 | `src/anomaly.py:200`, `:538` | `rule_3_2`가 생성기에서 참조한 설비 설정의 임의 정지 규칙을 사용해 다른 방법으로 바뀐다. | 명세 방법 표는 최근 3건 FAIL 2건으로 고정하고, generator에서는 규격·Cpk·결함 확률·결함 이동을 읽도록 한다. P06은 임시 측정 generator가 참조하는 설비 규칙만 유효한 5:3으로 바꿨다. 고장 onset=10, FAIL 위치 9·10에서 3:2는 t=10에 경보여야 하지만 `rule_outcomes`는 무경보다. 설정은 거절되지 않는다. 보고서 ID는 여전히 `rule_3_2`이므로 지표와 방법 선택도 다른 규칙에 근거하게 된다. | 비교용 3:2를 명세대로 고정하거나, 지원하지 않는 설비 규칙의 generator를 명시적으로 거절한다. 다른 이전 단계 규칙과 조합해도 3:2라는 이름으로 다른 규칙을 평가하지 않는지 확인한다. |
| R18-M1 | 중간 | `handoff/tasks.md:156`; `src/anomaly.py:545` | **명세 이견:** 조기 경보 재생을 한 행으로 남긴다는 설명과 같은 줄의 구간 공식이 서로 다르다. | onset=20, 첫 경보 a=19이면 명시 공식은 시작 15·끝 19이므로 5행이다. P07의 실제 `replay_rows`도 `early`인 t=15…19 다섯 행을 낸다. “조기 경보면 경보 행 하나”라는 설명에는 맞지 않는다. T189는 a=onset−50만 검사하므로 이 충돌이 드러나지 않는다. 구현은 구간 공식에는 맞으므로 일방적으로 높은 심각도의 코드 오답으로 판정하지 않았다. | 공식대로 가까운 조기 경보의 맥락을 포함할지, 모든 조기 경보를 한 행으로 제한할지 명세에서 확정한다. onset−1·onset−5·onset−6 경계를 함께 검증하고 설명·구현을 일치시킨다. 검수자는 기대표를 바꾸지 않았다. |
| R18-M2 | 중간 | `tests/test_anomaly.py:122` | T177의 검증 자료 변경 테스트가 바뀐 자료를 소비하지 않아 데이터 분리 요구를 실제로 검증하지 못한다. | 127행은 새로 만든 validation 목록의 `values[0]`을 바꾼 뒤 목록을 버린다. 특징도 다시 만들지 않는다. 126·128행은 같은 `train`을 `fit_model`에 다시 전달하며, `run`이 어떤 분할을 학습에 전달하는지도 실행하지 않는다. 따라서 validation 변경 줄을 통째로 없애도 같은 결정성 비교만 한다. 현재 구현의 `run:704–705`는 train만 학습하므로 실제 누수 결함을 주장하는 항목은 아니다. P10은 변경된 validation 특징이 비교 결과를 바꾸는 것을 확인하면서 모델 불변도 확인했다. | 변경 전·후 validation이 실제 전달되는 실행 경로를 사용하고 그 변경이 평가에 소비되는지 검증한다. 동시에 학습 함수가 train만 받는지 또는 실제 출력 모델·표준화 값이 불변인지 확인하도록 T177을 보강한다. |

높음은 모두 명세에 정해진 입력 처리·판정과 다르다는 영향으로 정했다. 중간 두 건은 각각 명세 모순과 테스트 검증 공백이다. 일정이나 수정 비용은 판단에 사용하지 않았다.

## 반례별 입력·예상·실제·판단

반례 파일: `handoff/reviews/probes/test_probe_018.py`. P01–P10은 이번 diff의 상태·오류·경계·기존 모드 조합을 겨냥했고, P11–P14는 보존·제출 결과 검증이다.

| ID | 입력 | 예상·명세 근거 | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | −1.250 공개 후 알람, 불가능한 reset, 유효 복귀, 다음 제품 | 거절은 값 유지, 복귀는 값만 소거하고 ID·처리 수·PC 코일 보존, 다음 ID 증가(T158) | 공개 워드 소거, ID1·수0·코일 유지, 다음 ID2·2.500 | 통과, R17-H1 해결 |
| P02 | 유효 쓰기 2개+손상+유효 쓰기, 47개 바이트 분할 | 손상 앞 완성 요청 보존, 뒤 요청 미처리(T160) | 모두 heartbeat=9, 응답 2개, 손상 뒤 88 미적용 | 통과, R17-H2 해결 |
| P03 | 실제 generator 시드0·10001제품, 최초 LEAK를 ID별 추출 | gpt-log에서 확정한 제품 번호 순서 유지 | 10001개 모두 독립 ID 대응 일치 | 통과, R17-M1 해결 |
| P04 | 중첩 null/목록, bool, 1과1.0 중복, 빈 검사명, 무한대 후 각각 정상 입력 | 위반 종료3·무보고서, 다음 정상 실행 성공(설정 규칙) | 8개 변형 모두 예상대로 | 통과 |
| P05 | `min_detection=10**400` | 범위 위반 종료3·무보고서(T187) | `OverflowError`, 종료1·무보고서 | 실패, R18-H1 |
| P06 | generator의 이전 단계 규칙5:3, FAIL 위치9·10, onset10 | 비교용 3:2는 t10 경보(방법 표) | 무경보, 설정은 허용 | 실패, R18-H2 |
| P07 | onset20, logistic 첫 경보19 | 한 행이라는 설명은 `[19]`, 명시 공식은 `[15…19]` | `early` 5행 `[15…19]` | 설명 기준 반례 실패, R18-M1 명세 이견 |
| P08 | 음수·중복·동률 점수, 60개 임의 격자 | 후보 압축과 전수 탐색의 선택·지표·후보 수 동일(임계값 규칙) | 모두 동일 | 통과 |
| P09 | 이동량2개, 창2, onset=window, 맞닿는 시드 범위, 전 방법 미달 | 순환 배정·경계 레이블 정확, 미달 완화/재선택 없음(설정·선택 규칙) | 배정0/.5/0/2, 양성8, 선택 없음, 임계값 없는 4행 지표 빈칸 | 통과; `mod 3`은 기본 목록에 대한 식으로 해석 |
| P10 | validation 특징 전체+100, 실제 비교에 전달 | 학습 표준화·계수 불변(T177), 바뀐 평가 자료는 실제 소비 | 평가 보고서 변경·모델 전체 동일 | 통과; R18-M2의 제품 누수 주장 아님 |
| P11 | 지정 기준 및 수정 완료 커밋과 보호 파일 비교, 기존 메서드 AST | 기존 자산 보존·기존 검증 약화 없음 | 보호 blob159개 동일, 11단계 이전 경로165개 무변경, 기존 검증 유지 | 통과; 파일 전체 무수정과 구분 |
| P12 | 시드42·20제품, 기존 8개 시나리오 실제 소켓 재실행 | 기존 보고서 동일(T171·T188 보존) | 16개 모두 제출 파일과 바이트 동일 | 통과 |
| P13 | 작은 11단계 설정 두 임시 폴더 실행, 기존 파일 해시 | 보고서3개 바이트 동일·기존 파일 불변(T186·T188) | 모두 동일, 기존 설정·data·reports109개 SHA-256 불변 | 통과 |
| P14 | 기본780시나리오 재생성, 제출 모델 계수로 평가·보고서 재계산 | 제출 표준화·창 수·최종 경사·지표·재생 행 일치 | 3개 보고서 바이트 동일, logistic·확인·h=.9675 | 통과; 2000회 최적화 재실행은 아님 |

## Claude 의견 수용과 보존 검증 한계

- 반례 탐색 뒤 gpt-log의 R17 수정 설명 3건을 수용한다. 다만 순서 기준을 “명세에 정했다”는 기록과 달리 `tasks.md:419`에는 여전히 “순서대로”라고만 적혀 있다. 이번 판정은 gpt-log의 명시적인 제품 번호 정의와 구현·P03의 일치를 근거로 해결 처리한다.
- 누적 최댓값에 포함되지 않은 후보를 생략해도 바로 위 누적 최댓값 후보와 첫 경보가 같고, 동률에서는 큰 h가 유리하다는 설명을 수용한다. P08의 60개 격자에서도 전수 탐색과 지표·선택이 같고, P14의 기본 후보 수는 moving_average=24644, logistic=7849로 제출물과 같았다.
- 기본 결과 `logistic`, 홀드아웃 `확인`, 최종 경사 노름 `0.0043102869779180425` 및 `수렴 미달` 표시를 P14 범위에서 확인했다. P14는 제출된 계수를 사용했다. **기본 설정의 2000회 학습을 새로 두 번 실행해 계수·파일 재현성을 확인한 것은 아니며 그 부분은 미검증**이다. 작은 설정의 독립 학습·3개 파일 바이트 재현성은 P13이 확인했다.
- **기존 테스트 무수정:** 지정 범위에는 017 수정에 필요한 `test_modbus.py`, `test_station.py` 회귀 추가와 `test_plc.py` 기존 한 메서드 이름 변경·검증 추가가 있다. 파일 전체가 무수정이라고 보고하지 않는다. P11은 다른 기존 메서드의 AST 동일 및 이름이 바뀐 메서드의 기존 assert 보존을 확인했다. 017 수정 완료 커밋 `a70f499..HEAD`만 분리하면 기존 src/tests/recipes/data/reports 165개는 모두 무변경이다.
- **기존 보고서 동일:** 지정 기준에 존재한 reports 78개는 모두 git blob 동일하다. P12는 이번 소스 변경의 직접 영향을 받는 10단계 보고서 16개를 실제 재실행해 바이트 일치까지 확인했다. 나머지 62개는 관련 기존 소스·설정·파일 보존을 확인했으며 생성 명령 재실행은 **미검증**이다. P13 실행 전후 해시에는 기존·신규 보고서와 설정·자료를 합친 109개가 포함된다.
- **전체 기존 테스트 통과:** 지정 명령을 한 번 직접 실행했으나 런처 실패로 **미검증**이다. 직접 실행 파일로 전체 tests를 재시도하지 않았다. 제출 `handoff/run-logs/v2-stage11-tests.txt`의 `Ran 358 tests in 146.957s / OK`는 작성자 측 기록이며 이번 독립 통과 결과로 바꾸어 쓰지 않는다. 런처 실패의 원인이 샌드박스라는 설명도 원인까지 독립 확정하지 않았다.
- 실제 PLC·설비는 이 소프트웨어 모의 검수의 대상이 아니다. 추가 반례 실행은 설치된 Python 3.12이며 `py`/Python 3.9 실행은 **미검증**이다.

## 실행 명령과 결과 원문

전체 테스트: **한 번 호출**, 종료 코드 1. 테스트 본문은 시작되지 않았다.

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'; py -m unittest discover -s tests
~~~

~~~text
No installed Python found!
~~~

지정 반례 명령: 종료 코드 1, 테스트 본문 시작 전 런처 실패.

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'; py -m unittest handoff/reviews/probes/test_probe_018.py
~~~

~~~text
No installed Python found!
~~~

설치된 실행 파일로 이번 반례만 실행했다. 최초 실행은 14개·19.471초·실패4개였다. 그중 P01 하나는 검수자가 주소표 전체 코일 목록(16개)을 PC 소유 코일 2개 목록으로 잘못 비교한 **반례 코드 오류**였다. 제품 코드 문제가 아니며 두 코일을 정확한 주소로 비교하도록 이 반례 파일만 고쳤다. 같은 실행 명령의 최종 결과를 아래에 그대로 붙인다. 수정으로 기대 동작을 완화하지 않았다. 전체 tests 또는 이전 반례 파일은 재실행하지 않았다.

P01만 수정 후 재검증한 명령·결과: 종료 코드 0.

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONIOENCODING='utf-8'; & 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff.reviews.probes.test_probe_018.DiffProbes.test_p01_reset_rejected_then_valid_then_new_publish
~~~

~~~text
.
----------------------------------------------------------------------
Ran 1 test in 0.000s

OK
P01: rejected reset preserves words; accepted reset clears words, keeps ID/count/coils; next ID=2
~~~

이번 반례 파일 전체의 최종 실행: 종료 코드 1, **14개 중 11개 통과·3개 실패**.

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONIOENCODING='utf-8'; & 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff/reviews/probes/test_probe_018.py
~~~

~~~text
....FFF.......
======================================================================
FAIL: test_p05_huge_out_of_range_integer_is_config_error (handoff.reviews.probes.test_probe_018.DiffProbes.test_p05_huge_out_of_range_integer_is_config_error)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_018.py", line 166, in test_p05_huge_out_of_range_integer_is_config_error
    self.assertEqual(result.returncode, 3, result.stderr)
AssertionError: 1 != 3 : Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\anomaly.py", line 740, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\anomaly.py", line 723, in main
    rows, selected, outcome, written = run(args.config)
                                       ^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\anomaly.py", line 702, in run
    settings = load_settings(path)
               ^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\anomaly.py", line 178, in load_settings
    errors = _check(data)
             ^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\anomaly.py", line 141, in _check
    if not _number(data[key]):
           ^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\anomaly.py", line 93, in _number
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                                                                               ^^^^^^^^^^^^^^^^^^^^
OverflowError: int too large to convert to float


======================================================================
FAIL: test_p06_generator_other_rule_does_not_relabel_baseline (handoff.reviews.probes.test_probe_018.DiffProbes.test_p06_generator_other_rule_does_not_relabel_baseline)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_018.py", line 187, in test_p06_generator_other_rule_does_not_relabel_baseline
    self.assertEqual(actual, expected, 'The named 3:2 method must not silently become 5:3')
AssertionError: None != 10 : The named 3:2 method must not silently become 5:3

======================================================================
FAIL: test_p07_near_onset_early_replay_spec_disagreement (handoff.reviews.probes.test_probe_018.DiffProbes.test_p07_near_onset_early_replay_spec_disagreement)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_018.py", line 199, in test_p07_near_onset_early_replay_spec_disagreement
    self.assertEqual([row['t'] for row in rows], [19], 'Spec prose says an early alarm leaves one row')
AssertionError: Lists differ: [15, 16, 17, 18, 19] != [19]

First differing element 0:
15
19

First list contains 4 additional elements.
First extra element 1:
16

- [15, 16, 17, 18, 19]
+ [19] : Spec prose says an early alarm leaves one row

----------------------------------------------------------------------
Ran 14 tests in 19.508s

FAILED (failures=3)
P01: rejected reset preserves words; accepted reset clears words, keeps ID/count/coils; next ID=2
P02: all 47 two-chunk splits preserve both valid writes; no post-damage write
P03: all 10001 first measurements retain numeric product identity
P04: 8 nested/type/bool/duplicate errors exit 3; each following valid run succeeds
P05: min_detection=10**400: exit=1; overflow=True
P06: generator=5:3, method=rule_3_2; actual alarm=None expected=10
P07: onset=20 first alarm=19; early replay t=[15, 16, 17, 18, 19]; formula says 15..19, prose says one row
P08: 60 negative/duplicate/tie score grids match exhaustive candidate evaluation
P09: 2 shifts and touching seed ranges accepted; boundary labels correct; no method is reselected
P10: changed validation is actually consumed by compare; model and training standardizer unchanged
P11: 159 old protected blobs identical; all 165 predecessor paths unchanged by stage 11; old test assertions retained
P12: all 8 actual-socket station scenarios reproduce all 16 submitted reports byte-for-byte
P13: small runs repeat all 3 reports byte-for-byte; 109 existing files retain SHA-256
P14: default 780 scenarios, training scaling/labels/final gradient and all 3 artifacts verified with saved coefficients; optimization not rerun
~~~

VERDICT: FIX
