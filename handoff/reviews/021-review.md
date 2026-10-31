검수 모델: gpt-6.1-sol

# 리뷰 021 — 리뷰 020 재검토 및 v2 13단계 SPC 검수

검수일: 2026-10-31. 대상: `5d46efe9975be42e18fb5b99ceda726e55984c88..05329f2ba9e21e95f5e586ea5513ae7ccfbed33e`.

**판정 FIX. 리뷰 020의 높음 3건은 모두 해결됐다. 새 SPC 변경에서 높음 1건·중간 2건을 확인했다. 미해결 수정 요구는 3건이다.** 낮음은 수정 요구로 세지 않는다. 전체 기존 테스트 실행 통과는 런처 오류로 미검증이다.

기준은 `handoff/tasks.md` 맨 위 13단계 명세·T205–T220·T251–T257과 이전 단계 보존 조건이다. setup-notes, tasks의 보존 조건, gpt-log의 수정 설명·명세 이견, decisions, 리뷰 020, 최근 git log와 지정 diff를 대조했다. `practical-work-operation`은 작업 조율·보존 확인에만 적용했다. 플러그인 리뷰 스킬·보조 에이전트·이전 반례 파일 실행은 사용하지 않았다. `docs/solutions/`와 `.compound-engineering/config.yaml`은 없었으며 이전 docs 문서를 판정 기준으로 삼지 않았다.

**미해결 지적**

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| R21-H1 | 높음 | `src/spc.py:186` | 허용되는 작은 EWMA 가중치에서 유한 시간 한계가 0으로 무너져 명세와 다른 경보를 낸다. | P04: 설정 로더가 수용하는 λ=`1e-20`, L=3, 중심 0, σ̂=1, 값 0.1을 12번, 판단 시작 9. 90자리 Decimal로 명세 식을 독립 계산하면 모든 시점에서 한계 안이다. t=9의 한계는 약 `9.486832980505138e-20`, z는 약 `1e-20`이다. 실제 `1-weight`가 1.0으로 반올림되어 한계가 0.0이 되고 t=9에 오경보한다. tasks의 λ 범위와 EWMA 식에는 이 입력을 제외하는 조건이 없다. | `log1p`·`expm1` 또는 안정적인 분산 재귀식 등으로 작은 λ에서도 양수 한계를 보존한다. 최소 양수 부근까지 중간 곱셈의 언더플로도 확인한다. 자릿수·범위 제한을 추가하려면 명세 이견으로 공개한다. |
| R21-M1 | 중간 | `src/spc.py:316` | 서로 모순되는 참조 행을 중복 키 덮어쓰기로 숨겨, 같은 행 집합이 순서에 따라 비교 허용·거절로 갈린다. | P07: 정상 `validation,rule_3_2` 행을 복제하고 비용만 `999.0000`으로 변경했다. 잘못된 행→정상 행이면 종료 0으로 보고서를 만들고, 정상 행→잘못된 행이면 종료 2다. 검증 전에 dict로 줄이므로 앞쪽 불일치가 사라진다. 명세가 중복 입력의 우선순위를 정하지 않았는데도 마지막 행을 임의 채택한다. | 참조 보고서의 필수 키 중복을 dict 생성 전에 검출한다. 특히 서로 다른 값의 중복은 종료 2로 거절하고, 모델의 setting/split 행도 같은 유일성 기준을 명시한다. |
| R21-M2 | 중간 | `handoff/tasks.md:39`, `src/spc.py:327`, `src/spc.py:337` | **명세 이견:** `rule_3_2` 결과 일치만으로 같은 측정열임을 확인할 수 없다. 생성기 내용이 바뀌어도 과거 11단계 결과와 새 SPC를 혼합 비교할 수 있다. | P08: 결함 확률 0·Cpk 5인 generator.json으로 정상적인 11단계 보고서를 만든 뒤, 같은 파일의 Cpk만 6으로 변경했다. 실제 validation 측정열이 달라졌지만 `rule_outcomes`는 완전히 같았다. 파일명·분할·설정 행과 검증/홀드아웃의 rule 집계 검사를 모두 통과하여 SPC가 종료 0으로 과거 참고 행을 복사했다. 구현은 명세에 열거된 두 검사를 수행한다. 문제는 서로 다른 측정열이 같은 rule 결과로 압축될 수 있다는 명세의 누락이다. | 11단계 결과와 실제 측정열을 묶는 검증 근거를 명세에 추가한다. 기존 11단계 산출물 보존을 전제로 현재 조건의 11단계 결과를 임시 위치에서 재생성·대조하는 방법 등을 정한다. 현재 generator 해시만 새로 기록하는 것으로 과거 보고서의 원본까지 증명했다고 간주하지 않는다. |

H1은 명시한 수식과 다른 경보 판정이다. M1은 명세에 없는 중복 입력에서의 설명되지 않은 판정이고, M2는 명세가 충분히 다루지 않은 생성기 변경에서 비교 근거가 성립하지 않는 문제다. M1은 서로 다른 바이트의 두 입력 파일을 비교한 것이며, 같은 바이트 입력의 비결정성으로 주장하지 않는다. M2는 제시된 검사 절차를 구현하지 않았다는 지적이 아니라 그 절차의 불충분성이다. 빈도·마감·일정·수정 비용으로 심각도를 조정하지 않았다.

**리뷰 020 항목별 판정 및 Claude 의견**

| 이전 항목 | 심각도 | 재판정 | 근거 |
| --- | --- | --- | --- |
| R20-H1 | 높음 | 해결 | `src/msa.py:412–415`가 Fraction과 정수 ceil/floor로 전체 한계를 계산한다. P01은 미세 양수 `10^-35`, 음수 규격, 0 배수, `10^40` 배수를 확인했다. 미세 폭은 7.001/12.999이고 큰 폭은 None이다. P02의 큰 배수 CLI도 종료 0·보고서 3개·가드 불가를 확인했다. |
| R20-H2 | 높음 | 해결 | `src/msa.py:479`가 Decimal quantize 대신 정수 기반 `line.show`를 사용한다. P02의 유효 Cpk=`1e200` 전체 CLI가 종료 0·보고서 3개로 끝나고 관측 Cpk도 `1e200`이다. P03의 양·음 반올림 동점도 HALF_UP과 맞는다. |
| R20-H3 | 높음 | 해결 | `src/msa.py:350`이 `cpk / hypot(1, GRR/σ)`를 사용한다. P03의 σ=`1e-200`, GRR=0 및 양수 비율에서 제곱 언더플로 없이 식과 일치했다. P02에서 H2 수정 뒤 전체 보고 경로까지 완주했다. |

gpt-log의 세 수정 설명은 위 새 반례와 코드가 뒷받침하므로 수용한다. 세 항목에 대한 별도 반박은 없었다. 이전 반례 파일 전체를 다시 실행하지 않았다.

T215에 대한 Claude의 명세 이견도 수용한다. `C⁺_0 = 2 − 0.5 = 1.5`는 `hσ̂=1.5`를 **초과하지 않는다**. 수식대로 첫 초과는 1이고 판단 시작 뒤 첫 경보는 9다. 사전 기대표는 수정하지 않았다. 낮음 기록: `handoff/tasks.md:140`의 “첫 초과 0”은 수식과 모순되는 설명문이다. 핵심 기대인 경보 9는 유지되므로 별도의 중간 이상 수정 요구로 세지 않는다. 제안은 이 명세 이견을 결정 기록에서 명확히 하는 것이다. 기존 “마지막 거절 쌍” 문구의 낮음도 새 수정 요구로 다시 세지 않는다.

**보존 및 현행 요구 확인**

- P10에서 기준 커밋의 기존 `test_*` 본문 **397개**가 클래스 경로를 포함한 AST 기준으로 동일했다. 기존 테스트 삭제·본문 변경은 없고 `tests/test_msa.py`에는 020 수정 회귀 3개만 추가됐다. 본문 보존은 확인했지만 전체 테스트 실행 통과와 구분한다.
- P10에서 기존 설정·데이터·보고서 **113개**의 Git 정규화 내용 해시가 모두 같았다. 그중 기존 보고서는 84개다. 저장소의 LF/CRLF 차이를 정규화한 검사이므로 이것만으로 재생성 바이트 일치를 주장하지 않는다.
- P11·P12에서 tempfile 아래 실제 CLI로 **기존 보고서 16개**(기본 MSA 3개, v1·v2·재검사·설비 샘플 13개)를 다시 생성하여 체크아웃된 저장본과 원시 바이트까지 같음을 확인했다. 이번에 재생성하지 않은 기존 보고서는 Git 내용 보존만 확인했다.
- P11에서 새 기본 SPC 보고서 2개도 저장본과 바이트 동일했고, 별도 두 번째 임시 폴더 실행과도 바이트 동일했다. SPC가 읽은 기존 `anomaly_lamp_*` 보고서 3개는 실행 전후 원시 바이트가 동일했다. 전체 11단계 학습을 다시 수행하지는 않았다.
- `6a4a2c9..HEAD`의 13단계 구현은 기존 코드·테스트·설정·데이터·보고서를 수정하지 않고 SPC 파일을 추가했다. 지정 전체 diff에 있는 기존 msa 코드·테스트 수정은 그 앞의 별도 020 수정 커밋이다. 필요한 재검토 수정과 13단계의 보존 위반을 혼동하지 않았다.
- 부분군 추정은 학습 정상 시나리오만 쓰고 잔여 값을 버린다. 런 규칙은 첫 부분군부터 누적하되 판단 시점 이후에만 인정한다. P05의 비정렬 시작 시점·범위/런 동시 경보·아래쪽 CUSUM과 P06의 403개 구간 판단 수가 식과 일치했다.
- 선택은 validation의 Metrics만 사용하고 holdout으로 다시 고르지 않는다. `clean_holdout`과 참조 행도 후보에 넣지 않는다. 기본 결과의 `기준 충족 관리도 없음` 및 README 표는 재생성 보고서와 일치했다. gpt-log의 기준 미달 결과 유지 설명을 수용한다.
- `load_reference`·`check_model`의 설정 불일치·누락 검사는 존재하지만, P07·P08의 문제가 남는다. 나머지 T205–T220·T251–T257의 원본 테스트 실행 통과는 이번 환경에서 미검증이다. 구현자 로그의 447개 OK를 이번 직접 실행 결과로 대신하지 않았다.

**이번 반례**

파일: `handoff/reviews/probes/test_probe_021.py`. 총 12개 메서드 중 **9개 통과·3개 실패**다. P04·P07은 첫 실행 뒤 검증 근거를 보강하여 두 메서드만 다시 실행했고 동일한 제품 문제를 확인했다. 아래 실제 열은 보강 실행까지 반영했다.

| 반례 | 입력 | 예상 및 명세 근거 | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | 가드 `10^-35`, 음수·양수 규격, 0, `10^40` | 12단계의 정확한 안쪽 자름. 양수 폭을 없애지 않고 불가능 폭은 None | 7.001/12.999, 음수 대칭, 0 보존, 큰 폭 None | 통과, H1 해결 |
| P02 | 최소 연구·제품 30, 큰 배수 CLI와 Cpk=`1e200` CLI | 허용 입력 정상 종료, 보고서 3개. 큰 폭은 가드 불가, 무오차 Cpk 보존 | 두 실행 모두 종료 0·보고서 3개, 값 일치 | 통과, H1–H3 해결 |
| P03 | σ=`1e-200`, 1, `1e100`과 GRR/σ=0·0.5·2, ±1.23445 표시 | Cpk 영향 식의 스케일 관계 및 HALF_UP | 비율 일치, 1.2345·-1.2345 | 통과 |
| P04 | 유효 λ=`1e-20`, 중심0·σ̂1·L3, 0.1 12개 | EWMA 식의 정확한 독립 계산상 전부 한계 안, 무경보 | 한계0·경보9, Decimal 및 안정식과 불일치 | 실패 → H1 |
| P05 | 판단 시작10, 앞선 두 부분군 q=2.5, 세 번째에서 range/run 겹침; 음수 CUSUM | 첫 부분군부터 런 누적, 다음 판단14, range 우선·joint1; 아래쪽 변화시점2 | 경보14, range/run 동시, range1·joint1, 변화시점2 | 통과 |
| P06 | first=2..14·last=0..30의 403구간, 부분군 끝 사이 onset 및 조기 경보 | 구간 내 t%5=4인 개수, 노출 종료는 기존 anomaly 규칙 | 전부 일치, 판단당 오경보 `2000/2` | 통과 |
| P07 | 동일 키의 정상 rule 행과 비용999 행, 순서 교환 | 명세 이외의 모순 입력은 임의 채택하지 않고 종료2가 필요 | 잘못된 행이 먼저면 0, 뒤면 2 | 실패 → M1 |
| P08 | 결함0·Cpk5로 만든 기존 결과, generator 내용만 Cpk6으로 변경 | 같은 측정열 비교라는 목표상 다른 원자료는 거절해야 함. 현 검사 절차의 충분성에 대한 명세 이견 | 측정열 다름·rule 결과 같음 확인 후 종료0 | 실패 → M2 |
| P09 | 루트 배열·bool·NaN·필수 키 누락 뒤 정상 입력 | 잘못된 설정은 3·SPC 보고서 없음, 그 뒤 정상 입력은 정상 실행 | 네 거절 및 후속 종료0 | 통과 |
| P10 | 기준 커밋 기존 테스트·설정·데이터·보고서 | 기존 본문 및 산출물 내용 보존 | 397개 본문·113개 파일 일치 | 통과, 실행 통과와 구분 |
| P11 | 기본 MSA·SPC CLI, SPC 별도 폴더 반복 | 기존 MSA 저장본 유지, 새 SPC 저장본 재현·결정성, 11단계 입력 보고서 불변 | 3+2개 동일, 반복 동일, 원본3개 불변 | 통과 |
| P12 | v1·v2·재검사·설비 기존 샘플 CLI | 이전 단계의 체크아웃 보고서와 바이트 동일 | 각각 3·3·3·4개 동일 | 통과 |

P01의 음수 규격, P03의 스케일 조합, P04·P05·P06·P07·P08·P09 등 최소 5개 이상이 명세·기대표 밖의 입력·규칙 조합이다. 생성 파일은 모두 tempfile 안에 두었고 저장소 reports/data를 덮어쓰지 않았다.

**실행 명령과 결과**

전체 테스트는 아래 명령을 **한 번만 직접 호출**했다. 런처가 실패하여 unittest는 시작하지 못했다. 전체 테스트 재시도·우회 실행은 하지 않았다.

~~~powershell
py -m unittest discover -s tests
~~~

종료 코드 1, 출력 원문:

~~~text
No installed Python found!
~~~

지정 반례 명령도 직접 호출했다. 반례 실행에는 `PYTHONDONTWRITEBYTECODE=1`을 적용했다.

~~~powershell
py -m unittest handoff/reviews/probes/test_probe_021.py
~~~

종료 코드 1, 출력 원문:

~~~text
No installed Python found!
~~~

설치된 Python 3.12 인터프리터로 **이번 반례만** 실행했다. 환경·런처·원본 테스트·패키지는 바꾸지 않았다. `PYTHONIOENCODING=utf-8`, `PYTHONDONTWRITEBYTECODE=1`을 적용했고 자식 CLI도 `-B`로 실행했다.

~~~powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -B -m unittest handoff/reviews/probes/test_probe_021.py
~~~

종료 코드 1, 출력 원문(첫 실행 당시 P04·P07은 보강 전):

~~~text
P01 tiny/negative/huge/zero guards: correct
.P02 large_guard: exit=0, reports=3
P02 large_cpk: exit=0, reports=3
.P03 scale and signed HALF_UP: correct
.P04 alarm=9 limit=0.0 expected_no_alarm stable_limit=1.0392304845413262e-19
F.P05 prewarm, range/run priority and lower CUSUM: correct
P06 403 offgrid intervals and pre-onset exposure: correct
.P07 conflicting reference duplicates exit=0
FP08 different_measurements=True identical_rule_outcomes=True exit=0
FP09 structural/bool/NaN/missing refusal followed by valid run: correct
.P10 original_test_bodies=397 unchanged_git_artifacts=113
.P11 src.msa stored_bytes_equal=3
P11 src.spc stored_bytes_equal=2
P11 anomaly input reports raw bytes unchanged; SPC repeat identical
.P12 sample_events raw_bytes_equal=3
P12 sample_events_v2 raw_bytes_equal=3
P12 sample_events_retest raw_bytes_equal=3
P12 sample_events_equipment raw_bytes_equal=4
.
======================================================================
FAIL: test_p04_tiny_valid_ewma_lambda_keeps_positive_limit (handoff.reviews.probes.test_probe_021.Probe021.test_p04_tiny_valid_ewma_lambda_keeps_positive_limit)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_021.py", line 133, in test_p04_tiny_valid_ewma_lambda_keeps_positive_limit
    self.assertIsNone(actual, "Valid lambda collapses the EWMA limit to zero")
AssertionError: 9 is not None : Valid lambda collapses the EWMA limit to zero

======================================================================
FAIL: test_p07_conflicting_duplicate_reference_rows_must_not_be_hidden (handoff.reviews.probes.test_probe_021.Probe021.test_p07_conflicting_duplicate_reference_rows_must_not_be_hidden)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_021.py", line 169, in test_p07_conflicting_duplicate_reference_rows_must_not_be_hidden
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 0 != 2 :

======================================================================
FAIL: test_p08_rule_metrics_collision_does_not_prove_same_measurements (handoff.reviews.probes.test_probe_021.Probe021.test_p08_rule_metrics_collision_does_not_prove_same_measurements)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_021.py", line 186, in test_p08_rule_metrics_collision_does_not_prove_same_measurements
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 0 != 2 :

----------------------------------------------------------------------
Ran 12 tests in 48.008s

FAILED (failures=3)
~~~

첫 실행 뒤 P04에 설정 수용 확인·90자리 독립 계산을 추가하고, 출력 한계를 12번째 시점이 아닌 실제 경보 시점에 맞췄다. P07에는 중복 행 순서를 바꾼 실행을 추가했다. 바뀐 두 메서드만 실행했다.

~~~powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -B -m unittest handoff.reviews.probes.test_probe_021.Probe021.test_p04_tiny_valid_ewma_lambda_keeps_positive_limit handoff.reviews.probes.test_probe_021.Probe021.test_p07_conflicting_duplicate_reference_rows_must_not_be_hidden
~~~

종료 코드 1, 출력 원문:

~~~text
P04 alarm=9 limit=0.0 expected_no_alarm stable_limit=9.486832980505138e-20
FP07 conflicting reference duplicate order exits=(0, 2)
F
======================================================================
FAIL: test_p04_tiny_valid_ewma_lambda_keeps_positive_limit (handoff.reviews.probes.test_probe_021.Probe021.test_p04_tiny_valid_ewma_lambda_keeps_positive_limit)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_021.py", line 143, in test_p04_tiny_valid_ewma_lambda_keeps_positive_limit
    self.assertIsNone(actual, "Valid lambda collapses the EWMA limit to zero")
AssertionError: 9 is not None : Valid lambda collapses the EWMA limit to zero

======================================================================
FAIL: test_p07_conflicting_duplicate_reference_rows_must_not_be_hidden (handoff.reviews.probes.test_probe_021.Probe021.test_p07_conflicting_duplicate_reference_rows_must_not_be_hidden)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_021.py", line 182, in test_p07_conflicting_duplicate_reference_rows_must_not_be_hidden
    self.assertEqual(actual, (2, 2), first.stderr + second.stderr)
AssertionError: Tuples differ: (0, 2) != (2, 2)

First differing element 0:
0
2

- (0, 2)
?  ^

+ (2, 2)
?  ^
 : 오류: anomaly_report: validation의 rule_3_2가 현재 측정열과 다름


----------------------------------------------------------------------
Ran 2 tests in 0.939s

FAILED (failures=2)
~~~

전체 테스트 미검증은 실행 환경의 한계이며 제품 결함으로 계상하지 않았다. FIX는 독립 반례로 재현한 H1·M1·M2에 따른다. 이번 검수가 생성·수정한 파일은 이 리뷰와 `test_probe_021.py`뿐이다. 시작 때부터 존재한 `handoff/loop-logs/021-codex.txt`는 변경하지 않았다.

VERDICT: FIX
