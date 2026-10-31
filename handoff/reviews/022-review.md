검수 모델: gpt-6.1-sol

# 리뷰 022 — 리뷰 021 재검토 및 v2 14단계 사건 추적 검수

검수일: 2026-10-31. 대상: `401f45ae19b53e44cecf9f187868dbc162b04faa..461e3dc`(검수 시 HEAD).

**판정 FIX. 이전 높음 1건은 부분 해결에 그쳐 미해결이고, 이전 중간 2건은 해결됐다. 새 중간 3건을 확인했다. 미해결 수정 요구는 높음 1건·중간 3건, 총 4건이다. 전체 테스트 실행 통과는 런처 오류로 미검증이다.**

기준은 `handoff/tasks.md` 맨 위 현행 14단계 명세·T221–T236·T258–T262 및 완료 단계의 보존 조건이다. 최초 setup-notes, tasks, gpt-log의 수정 설명, decisions, 리뷰 021, 최근 git log와 지정 diff를 대조했다. `practical-work-operation`은 범위 보존과 검증 조율에만 적용했다. 플러그인 리뷰 스킬·보조 에이전트·이전 반례 파일 실행은 사용하지 않았다. `docs/solutions/`와 `.compound-engineering/config.yaml`은 없었으며 과거 docs 문서를 판정 기준으로 삼지 않았다.

## 미해결 지적

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| R21-H1 유지 | 높음 | `src/spc.py:196` | 작은 EWMA 가중치의 한계 붕괴가 남아 명세 식과 다른 경보를 낸다. | P01: 설정 로더가 수용하는 λ=`1e-200`, 중심 0·σ̂=1·L=3, 값 0.1을 12개 넣었다. 750자리 Decimal 독립 계산은 전부 무경보이고 마지막 한계는 약 `1.0392304845413263e-199`다. 실제는 λ 비율과 시작 계수의 곱이 제곱근 전에 언더플로되어 한계 0, 판단 시작 9에서 오경보다. 최소 양수 `5e-324`도 실제 한계 0이고 독립 계산상 약 `5e-323`이다. 기존 `1e-20`과 λ=1은 해결됐다. | 시작 계수뿐 아니라 최종 한계의 중간 곱셈도 스케일을 보존하도록 계산한다. 제곱근 분리 등으로 최종 값이 표현 가능한 경우 0으로 소실되지 않는지 확인한다. 허용 범위를 바꿀 경우 명세 이견으로 공개한다. |
| R22-M1 | 중간 | `src/incident.py:160`, `src/spc.py:480` | 사건의 한계 검증이 서로 모순되는 중복 행을 마지막 값으로 덮어써 숨긴다. | P05: 정상 `limits/sigma_hat`에 값 `999.0`인 동명 행을 추가했다. 잘못된 행→정상 행은 `checked_limits` 통과, 정상 행→잘못된 행은 거절이다. 14단계는 현재 추정과 다른 limits를 거절한다고 하지만 중복 처리 규칙은 정하지 않았다. R21-M1을 고친 `_unique`가 이 소비 경로에는 적용되지 않는다. | `limits`의 이름 유일성을 dict 생성 전에 검사하고 모순된 보고서를 순서와 무관하게 거절한다. 같은 값의 중복도 허용할지 명시한다. |
| R22-M2 | 중간 | `src/spc.py:390` | 새 재생 검증에서 범위 밖 `t`가 처리되지 않아 파일 오류 종료 코드 2 대신 traceback과 종료 코드 1이 나온다. | P04: 길이 120인 정상 소규모 보고서의 첫 행 `t`만 120으로 변경했다. `scenario.values[t]`에서 `IndexError`가 발생해 main의 예외 처리 밖으로 빠졌다. 보고서는 생성하지 않았지만 명세의 파일 오류 처리와 다르다. | 값 접근 전에 `0 <= t < len(scenario.values)` 및 창 범위를 확인하고, 위치를 설명하는 `ValueError`로 거절한다. |
| R22-M3 | 중간 | `handoff/tasks.md:49`, `handoff/tasks.md:91`, `src/incident.py:324` | **명세 이견:** 제품 수 100000 허용과 `제품 번호 = measure_id − 1`이 기존 PLC의 ID 순환과 양립하지 않는다. 허용 범위 안의 65536번째 제품에서 정상 흐름을 끝낼 수 없다. | P06: `products=65536`은 로더가 수용한다. 실제 PLC `_publish`를 순환 경계에 놓으면 제품 번호 65534는 ID 65535로 접수되지만 다음 제품 65535는 ID 1이 되어 StoryPc가 `제품 번호와 측정 ID가 어긋남`으로 거절한다. 기존 `src/plc.py:151`의 순환은 이번에 바뀐 코드가 아니다. 명세에는 순환 이후 번호 대응이 없다. | 기존 PLC 프로토콜 보존을 전제로 사건의 절대 제품 번호와 순환 ID 대응을 정의한다. 지원 범위 변경을 택한다면 명세 이견으로 확정한다. 기대표를 구현에 맞춰 임의 수정하지 않는다. |

H1은 명시된 EWMA 식과 경보가 달라 높음이다. M1은 명세에 없는 중복 입력의 설명되지 않은 우선순위, M2는 파일 오류 처리 불일치, M3는 명세가 다루지 않은 ID 순환과 허용 범위의 모순으로 중간이다. M3의 불일치 거절 자체는 현재 명세의 방어 동작대로이며, 이를 제거하라는 지적이 아니다. 범위 상한과 절대 번호 규칙을 함께 성립시키지 못한 명세 이견이다. 마감·일정·수정 비용으로 심각도를 조정하지 않았다. 새 낮음 수정 요구는 없다.

## 리뷰 021 항목별 재판정 및 Claude 의견

| 이전 항목 | 재판정 | 근거와 의견 수용 범위 |
| --- | --- | --- |
| R21-H1 높음 | **미해결 — 부분 해결** | gpt-log의 `expm1`·`log1p` 변경과 λ=1 예외 설명은 코드와 P01이 뒷받침한다. 이전 입력 `1e-20`의 무경보는 수용하지만 `1e-200`의 제곱 언더플로가 남아 전체 해결로 처리할 수 없다. |
| R21-M1 중간 | **해결** | P02에서 정상/잘못된 방법 행의 양 순서, 모델의 동일값/모순값 중복을 모두 거절했다. 거절 직후 정상 보고서는 수용했다. 해당 방법·모델 행에 `_unique`를 적용했다는 설명을 수용한다. 새로운 limits 소비 경로의 M1과 구분한다. |
| R21-M2 중간 | **해결** | 현재 명세가 moving_average 재계산과 replay 원 측정값 대조를 추가했다. P03에서 결함 확률 0·Cpk 5→6의 실제 측정열 변화 및 rule 결과 동일을 먼저 확인했으며 SPC는 replay 불일치로 종료 2, 보고서 미생성이었다. 이전 반례와 수정한 일치 확인 명세에 대해 해결로 판정한다. 모든 가능한 다른 측정열이 집계·일부 재생 행으로 식별된다는 일반적 증명으로 확대하지 않는다. |

별도 반박은 없으며 gpt-log의 수정 근거를 위 범위에서 수용한다. T215의 “첫 초과 0”에 관한 기존 명세 이견 수용도 유지한다. 수식상 `C⁺_0=1.5`는 한계 1.5를 초과하지 않고 첫 초과는 1이며, 판단 시작 뒤 경보 9는 유지된다. 사전 기대표는 고치지 않았다.

14단계의 “고장 뒤 첫 정지에서만 수리”, 조기 정지 후 F 유지, 마지막 제품 정지 후 복귀 완료에 동의한다. P07은 조기 정지 2회·진짜 정지·수리 뒤 정지 2회(마지막 제품 포함)로 반례를 찾은 뒤 소켓/메모리 값·처분 및 소비 수 14가 같음을 확인했다. 기본 결과에 관한 설명도 P11의 저장본 대조가 뒷받침한다.

## 보존 및 검증 범위

- **전체 기존 테스트 통과는 미검증이다.** 지정 전체 명령을 한 번 직접 호출했으나 `py` 런처가 실패해 unittest는 시작하지 않았다. 재시도·다른 인터프리터를 통한 전체 실행은 하지 않았다. 구현자 기록 `handoff/run-logs/v2-14-tests.txt`의 501개 OK를 이번 직접 실행 결과로 대신하지 않았다.
- P10: 기준 커밋의 기존 테스트 본문 447개를 클래스 경로를 포함한 AST로 비교했다. 445개는 동일하고, `tests/test_spc.py`의 `test_section_sizes`, `test_t255_provenance` 2개는 provenance 4→5 변경에 따라 바뀌었다. `write_spc` 준비 함수에도 새 replay 경로가 추가됐다. 따라서 지정 전체 diff를 두고 기존 테스트가 전부 무수정이라고 보고하지 않는다.
- 위 변경은 별도 리뷰 021 수정 커밋 `94d8ab4`의 공개된 입력·provenance 확장이다. **14단계 커밋만** 비교한 `94d8ab4..HEAD`에는 기존 테스트 수정이 없고 `tests/test_incident.py` 추가만 있다. 이전 단계의 다른 테스트 본문은 유지됐다. 새 입력을 검증하는 021 수정과 14단계의 보존 조건을 구분했다.
- P10: 기준의 설정·데이터·보고서 116개 중 Git 정규화 내용이 달라진 파일은 `recipes/spc_lamp.json`, `reports/spc_lamp_methods.csv` 2개뿐이다. 전자는 replay 키 추가, 후자는 그 설정 해시 변경과 replay provenance 행 추가다. diff상 SPC 지표 행은 그대로다. 이 역시 공개된 021 수정이며 지정 전체 범위의 모든 기존 보고서가 완전히 동일한 것은 아니다. 나머지 114개는 동일했다. Git 정규화 내용 비교를 재생성 바이트 검증과 혼동하지 않았다.
- `94d8ab4..HEAD`에서는 기존 설정·보고서 수정이 없고 incident 설정 1개·보고서 5개 추가만 있다. PLC·Modbus·Plant diff는 요청된 코일/알람/복귀 조건/투입 보류/제품 제거 추가다.
- P11: 임시 폴더에서 **10단계 8개 시나리오 보고서 16개**를 실제 실행·재생성해 저장본과 원시 바이트 동일함을 확인했다. 기본 14단계 CLI의 새 보고서 5개도 저장본과 바이트 동일했고 기본 400제품 실행이 끝났다. 실행 전후 저장소의 reports/recipes/data 파일 122개 원시 바이트도 모두 그대로였다. 다른 이전 단계 보고서는 이번에 재생성하지 않았으므로 Git 내용 보존까지만 확인했다.
- P07–P09는 복구 순서·여러 정지·최종 제품·알람 우선순위·잘못된 목록 거절 뒤 정상 단일 제품 실행을 확인했다. T221–T236·T258–T262 원본 테스트 전체 통과나 65536제품 전체 소켓 완주는 미검증이다. P06은 순환 경계의 실제 PLC 공개 함수와 PC 처리 함수를 연결한 국소 재현이다.
- 생성된 제품 보고서는 모두 tempfile 안에 두었다. 이번 검수가 생성·수정한 파일은 이 리뷰와 `handoff/reviews/probes/test_probe_022.py`뿐이다. 시작 때 이미 있던 `handoff/loop-logs/022-codex.txt`는 변경하지 않았다.

## 이번 반례

파일: `handoff/reviews/probes/test_probe_022.py`. 최초 실행 **11개 중 7개 통과·4개 실패**. 이후 P01에 설정 로더 수용 확인, P10에 변경 메서드 두 개의 정확한 목록 검증을 보강하고 그 두 메서드만 실행했다(1개 통과·1개 실패). import한 기존 테스트 파일의 준비 함수를 이용했지만 기존 테스트 메서드나 이전 반례 파일은 실행하지 않았다.

| 반례 | 입력 | 예상(명세 근거) | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | λ=`1e-20`, `1e-200`, `5e-324`, 1; 중심0·σ̂1·0.1 12개 | 허용 λ에서 EWMA 식과 경보 일치, 최종 양수 한계 보존 | `1e-20`·1은 정상. `1e-200`은 한계0·경보9, `5e-324`도 한계0 | 실패, R21-H1 유지 |
| P02 | 방법 모순 중복 양 순서·모델 동일/상이 중복, 거절 후 정상 | 현행 13단계의 키 유일성 및 거절 뒤 정상 수용 | 중복 4종 모두 거절, 정상 수용 | 통과, R21-M1 해결 |
| P03 | 결함0·Cpk5 생성 후 Cpk6; rule 결과 충돌 | 같은 측정열 대조 목표상 거절2·SPC 보고서 없음 | 원 측정열 다름·rule 같음 확인, replay 불일치로2 | 통과, R21-M2 해결 |
| P04 | 길이120 보고서 첫 `t=120` | 13단계 파일 오류는2, 보고서 없음 | IndexError·종료1, 보고서 없음 | 실패, R22-M2 |
| P05 | limits/sigma_hat 정상 행과999 행의 순서 교환 | 14단계 불일치 거절 목표상 모순을 임의 채택하지 않아야 함 | 잘못된 행 먼저면 수용, 뒤면 거절 | 실패, R22-M1 |
| P06 | 허용 products65536; 실제 PLC ID65535→1 경계와 PC | 지원 범위와 번호 일치 규칙이 함께 성립해야 함. 순환 처리는 명세 누락 | 로더 수용, 제품65534는 접수·65535는 번호 불일치 거절 | 실패, 명세 이견 R22-M3 |
| P07 | 제품14·onset5·강제 정지0,1,5,6,13·대기1 | 조기 정지 후F, 진짜 정지 후N, 반복·최종 정지 복귀, 소켓/메모리 소비 수 일치 | 값·처분 같음, 진짜 정지3번, 합계14, restart→finish | 통과 |
| P08 | CLAMP에서 PC 정지와 가드/클램프 충돌/측정 신호 동시, 이후 코일 해제 | 기존 즉시 알람이26보다 우선, ALARM 코드 보존 | 22·24·25 우선 및 유지 | 통과 |
| P09 | 중첩/None/bool 목록, 대문자CUSUM, 중복cusum; 직후 단일 제품 | 타입·ID·중복 거절3, 후속 유효 실행 정상 | 5종3·보고서 없음, 후속0·보고서5 | 통과 |
| P10 | 기준 테스트 AST447개·기존 산출물116개 | 보존 조건과 021 수정 범위 대조, 14단계 기존 파일 무수정 | 테스트2개·산출물2개만 공개된 SPC 수정, 14단계 기존 테스트/산출물 무수정 | 범위 확인 통과, 실행 통과와 구분 |
| P11 | 기본 station all 및 incident CLI·원본 전후 대조 | T223의16개 보존, 기본 사건 저장본 재현, 실행이 원본 불변 | 16+5개 바이트 동일, 원본122개 불변 | 통과 |

P01–P09의 경계·중복·거절 후 입력·대소문자·순환·다중 정지 조합으로 명세 밖 반례 최소 5개를 충족한다.

## 실행 명령과 결과 원문

전체 테스트는 아래 명령을 **한 번만 직접 실행**했다. 환경 변수 `PYTHONDONTWRITEBYTECODE=1`, `PYTHONIOENCODING=utf-8`을 설정했다.

```powershell
py -m unittest discover -s tests
```

종료 코드 1:

```text
No installed Python found!
```

지정 반례 명령도 직접 실행했다.

```powershell
py -m unittest handoff/reviews/probes/test_probe_022.py
```

종료 코드 1:

```text
No installed Python found!
```

설치된 Python 3.12로 **이번 반례만** 실행했다. 설치·런처·원본 테스트·패키지는 바꾸지 않았다. 자식 CLI도 `-B`와 동일 환경 변수를 썼다.

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -B -m unittest handoff/reviews/probes/test_probe_022.py
```

종료 코드 1, 최초 실행 출력:

```text
P01 weight/alarm/expected/limit/expected_limit: [(1e-20, None, None, 1.0392304845413262e-19, 1.0392304845413264e-19), (1e-200, 9, None, 0.0, 1.0392304845413263e-199), (5e-324, None, None, 0.0, 5e-323), (1.0, None, None, 3.0, 3.0)]
FP02 duplicate orders/model identical+conflicting: ['refused', 'refused', 'refused', 'refused'] ; subsequent valid accepted
.P03 changed values/same rule: exit= 2 오류: anomaly_replay: 현재 측정열과 다름
.P04 out-of-range replay: exit= 1 Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\spc.py", line 538, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\spc.py", line 521, in main
    rows, selected, outcome, written = run(args.config)
                                       ^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\spc.py", line 497, in run
    check_replay(settings.anomaly_replay, splits["holdout"][1])
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\spc.py", line 391, in check_replay
    if int(row["seed"]) != scenario.seed or row["value"] != scenario.values[t]:
                                                            ~~~~~~~~~~~~~~~^^^
IndexError: list index out of range
FP05 contradictory limits bad-first/bad-last: ['accepted', 'refused']
FP06 product/measurement-ID/result: [(65534, 65535, 'accepted'), (65535, 1, '제품 번호와 측정 ID가 어긋남')]
FP07 early x2, true stop, post-repair x2 including final product: socket=memory; counts=14
.P08 simultaneous alarm priority then stop-clear retains codes: [22, 24, 25]
.P09 five malformed list/case/duplicate inputs refused; next single-product CLI succeeds
.P10 existing_tests= 447 changed_bodies= [('tests/test_spc.py', 'ReportTests', 'test_section_sizes'), ('tests/test_spc.py', 'ReportTests', 'test_t255_provenance')] artifacts= 116 documented_SPC_differences= ['recipes/spc_lamp.json', 'reports/spc_lamp_methods.csv']
.P11 src.station stored raw bytes equal: 16
P11 src.incident stored raw bytes equal: 5
P11 all existing reports/config/data raw bytes unchanged by execution: 122
.
======================================================================
FAIL: test_p01_ewma_smaller_lambda_and_endpoints (handoff.reviews.probes.test_probe_022.Probe022.test_p01_ewma_smaller_lambda_and_endpoints)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_022.py", line 72, in test_p01_ewma_smaller_lambda_and_endpoints
    self.assertTrue(all(actual == expected and limit > 0
AssertionError: False is not true : [(1e-20, None, None, 1.0392304845413262e-19, 1.0392304845413264e-19), (1e-200, 9, None, 0.0, 1.0392304845413263e-199), (5e-324, None, None, 0.0, 5e-323), (1.0, None, None, 3.0, 3.0)]

======================================================================
FAIL: test_p04_replay_out_of_range_is_controlled_refusal (handoff.reviews.probes.test_probe_022.Probe022.test_p04_replay_out_of_range_is_controlled_refusal)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_022.py", line 134, in test_p04_replay_out_of_range_is_controlled_refusal
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 1 != 2 : Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\spc.py", line 538, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\spc.py", line 521, in main
    rows, selected, outcome, written = run(args.config)
                                       ^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\spc.py", line 497, in run
    check_replay(settings.anomaly_replay, splits["holdout"][1])
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\spc.py", line 391, in check_replay
    if int(row["seed"]) != scenario.seed or row["value"] != scenario.values[t]:
                                                            ~~~~~~~~~~~~~~~^^^
IndexError: list index out of range


======================================================================
FAIL: test_p05_incident_conflicting_limits_either_order (handoff.reviews.probes.test_probe_022.Probe022.test_p05_incident_conflicting_limits_either_order)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_022.py", line 156, in test_p05_incident_conflicting_limits_either_order
    self.assertEqual(outcomes, ["refused", "refused"])
AssertionError: Lists differ: ['accepted', 'refused'] != ['refused', 'refused']

First differing element 0:
'accepted'
'refused'

- ['accepted', 'refused']
?   ^^^ ^^

+ ['refused', 'refused']
?   ^ ^^^


======================================================================
FAIL: test_p06_measure_id_rollover_within_allowed_products (handoff.reviews.probes.test_probe_022.Probe022.test_p06_measure_id_rollover_within_allowed_products)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_022.py", line 181, in test_p06_measure_id_rollover_within_allowed_products
    self.assertEqual([x[2] for x in outcomes], ["accepted", "accepted"], outcomes)
AssertionError: Lists differ: ['accepted', '제품 번호와 측정 ID가 어긋남'] != ['accepted', 'accepted']

First differing element 1:
'제품 번호와 측정 ID가 어긋남'
'accepted'

- ['accepted', '제품 번호와 측정 ID가 어긋남']
+ ['accepted', 'accepted'] : [(65534, 65535, 'accepted'), (65535, 1, '제품 번호와 측정 ID가 어긋남')]

----------------------------------------------------------------------
Ran 11 tests in 29.952s

FAILED (failures=4)
```

P01에 로더 수용 검사, P10에 정확한 변경 목록 검사를 보강한 뒤 해당 두 메서드만 실행했다.

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -B -m unittest handoff.reviews.probes.test_probe_022.Probe022.test_p01_ewma_smaller_lambda_and_endpoints handoff.reviews.probes.test_probe_022.Probe022.test_p10_preserved_test_bodies_and_artifact_contents
```

종료 코드 1:

```text
P01 weight/alarm/expected/limit/expected_limit: [(1e-20, None, None, 1.0392304845413262e-19, 1.0392304845413264e-19), (1e-200, 9, None, 0.0, 1.0392304845413263e-199), (5e-324, None, None, 0.0, 5e-323), (1.0, None, None, 3.0, 3.0)]
FP10 existing_tests= 447 changed_bodies= [('tests/test_spc.py', 'ReportTests', 'test_section_sizes'), ('tests/test_spc.py', 'ReportTests', 'test_t255_provenance')] artifacts= 116 documented_SPC_differences= ['recipes/spc_lamp.json', 'reports/spc_lamp_methods.csv']
.
======================================================================
FAIL: test_p01_ewma_smaller_lambda_and_endpoints (handoff.reviews.probes.test_probe_022.Probe022.test_p01_ewma_smaller_lambda_and_endpoints)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_022.py", line 76, in test_p01_ewma_smaller_lambda_and_endpoints
    self.assertTrue(all(actual == expected and limit > 0
AssertionError: False is not true : [(1e-20, None, None, 1.0392304845413262e-19, 1.0392304845413264e-19), (1e-200, 9, None, 0.0, 1.0392304845413263e-199), (5e-324, None, None, 0.0, 5e-323), (1.0, None, None, 3.0, 3.0)]

----------------------------------------------------------------------
Ran 2 tests in 9.500s

FAILED (failures=1)
```

전체 테스트 미검증은 환경 한계로 별도 계상하지 않았다. FIX는 독립 반례로 재현한 위 4건에 따른다.

VERDICT: FIX
