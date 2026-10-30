검수 모델: gpt-6-astra

# 리뷰 012 — v2 6단계 첫 검토

검수일: 2026-10-31. **미해결 높음 2건, 중간 1건. 수정 요구 3건. 낮음 없음.**

기준은 `handoff/tasks.md` 맨 위 「현행 작업」과 T67–T88, 아래 완료 단계의 보존 조건이다. `setup-notes.md`, `gpt-log.md`, `decisions.md`와 지정 커밋 범위의 diff/log를 대조했다. 이전 `docs/` 명세를 기준으로 사용하지 않았다. CE 설정 및 `docs/solutions/`는 없다. 작업 조율·검수 스킬의 기준 확인과 근거 검증을 적용하되, 지정된 두 파일 외 기록을 만드는 절차는 수행하지 않았다.

검토 범위:

```text
git diff d12e92e48c9cfc0bc716d54a39d169120ca581f8..HEAD
git log d12e92e48c9cfc0bc716d54a39d169120ca581f8..HEAD

HEAD: f89332fb785531cc10332f1fb2369aed6d7c2ecd
f89332f docs(T67-T88): mark the lot-method explanation as unverified
7eaba57 docs(T67-T88): record stage 6 results and restore overwritten stage5 log
a0e3f64 feat(T77-T85,T87,T88): add lot generator and containment evaluation
a9ec403 feat(T67-T76,T86): add lot mode and containment scope report
ad38ff2 docs(T67-T88): confirm stage 6 spec and fix containment selection criteria
9c298f7 docs(T52-T66): record user approval of review 011
```

## 지적 사항

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| H1 | 높음 | `src/evaluate.py:251`, `src/evaluate.py:341` | 정지가 없는 평가에서는 모든 방식의 지표가 사라지고, 개발 선택이 있는 홀드아웃은 `미확인` 대신 종료 코드 2로 끝난다. | `run_scopes`는 정지 0건이면 빈 dict를 돌려주며, 지표 함수는 어느 실행에도 나타나지 않는 방식을 건너뛴다. P04는 정상적인 무정지 설정에서 방식 행이 0개였다. P05는 실제 제공 설정·시드 1000·제품 1개와 SHA가 일치하는 `last_10` 선택 fixture를 사용했으며 `오류: 'last_10'`으로 종료했다. 현행 지표 명세는 모든 방식의 지표와 실행·유출·정지 합계를 요구하고, T80③과 사전 기준 5는 유출 0/표본 부족을 `미확인`으로 정한다. 함수 단독 T80 테스트만으로는 이 CLI 경로를 잡지 못한다. | 정지가 없어도 적용 가능한 방식마다 빈 격리 집합을 유지해 지표를 계산한다. 유출·격리 분모가 0이면 비율은 빈칸, 실행 수가 양수이면 평균은 0.00으로 출력한다. 선택 방식의 지표가 존재하도록 하고 무정지 개발·선택 있는 홀드아웃을 CLI 회귀 테스트에 포함한다. |
| H2 | 높음 | `src/generate.py:241` | 범위를 벗어난 큰 정수 확률값을 설정 오류로 처리하지 못해 생성·평가가 종료 코드 1과 traceback으로 끝난다. | P06의 `faulty_detection_loss={"LEAK-2": 10**400}`는 정상 JSON 정수지만 허용 범위 밖이다. `math.isfinite`가 범위 비교보다 먼저 정수를 float로 변환하다 `OverflowError`를 내며 두 CLI의 예외 처리에서 빠진다. 현행 「설정 검증」은 유한한 0–1 값 위반에 대해 생성·평가 **모두 종료 코드 2**를 명시한다. 사용 빈도나 수정 비용이 아니라 이 명시적 종료 계약 위반으로 높음이다. | 타입 확인 후 0–1 범위를 먼저 비교하거나 큰 정수에도 안전하게 유한성을 검사하고 기존 `ValueError` 경로로 처리한다. loss뿐 아니라 같은 검사를 쓰는 집중 로트 확률도 확인한다. |
| M1 | 중간 | `tests/test_containment.py:253` | T81 테스트가 두 번째 meta와 보고서 재현성을 실제로 검증하지 않는다. | 두 번 생성하지만 두 번째 반환값을 버리고 `one.csv`와 `two.csv`만 비교한다. meta 파일은 읽어 비교하지 않고 판정 보고서도 생성하지 않는다. T81은 CSV·meta·보고서의 바이트 동일성을 모두 요구한다. P13으로 현 구현의 두 시드에서 세 범주 모두 동일함을 별도로 확인했으므로 현재 재현성 결함을 주장하는 것은 아니다. 제출 테스트가 해당 요구의 회귀를 검출하지 못하는 문제다. | 새 테스트 파일 안에서 두 meta 파일 및 판정 보고서 묶음을 바이트 비교한다. 기존 8개 테스트 파일은 보존한다. |

H1의 두 증상(P04·P05)은 같은 원인이므로 한 건으로 묶었다. H2는 생성·평가 두 하위 사례의 실패를 한 건으로 묶었다. M1은 구현 판정 오류와 구별되는 테스트 검증 누락이다.

## 반례와 추가 보존 검증

파일: `handoff/reviews/probes/test_probe_012.py`. P01–P08은 기대표 그대로의 재실행을 넘는 반례 탐색이며, P09–P13은 보존·산출물 검증이다. 모든 임시 설정·입력·보고서는 테스트의 `tempfile.TemporaryDirectory` 안에만 썼다.

| ID | 입력 | 예상과 명세 근거 | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | 열 초과+seq 0+소문자 lot+미등록 모델을 함께 넣은 등록, 거절 후 같은 제품 정상 등록, 공백·개행·소문자·전각 lot으로 중복 등록 후 P1 | 열 구조 → seq → lot 순서. 거절은 상태 불변이고 정상 후속 행은 허용 | 순서대로 해당 사유로 거절, 모든 상태 불변, L1 유지, P1 허용 | 통과 |
| P02 | seq 900→3→3→2, lot을 잘못 기입한 PASS 뒤 정상 PASS, 정지 중 거절 PASS, 재가동 후 정상 PASS | 물리 행 순서로 범위 계산. 거절 및 정지 이후 PASS는 이전 정지 범위에서 제외. 분석은 상태 불변 | 첫 정지 `since_restart=[a,b]`, seq=[900,3], row_index=[19,21]. 거절 2행 제외, 미래 f 제외, 상태 불변 | 통과 |
| P03 | 재검사 없는 1단계 레시피 + lot=true + restart=false, PASS 1건·FAIL 2건 | 로트 모드는 재가동·재검사와 독립. 다섯 방식 모두 a 포함 | 모든 행 허용, 다섯 방식 모두 {a}, lot L1 보존 | 통과 |
| P04 | 정상/고장 FAIL 0, 결함률 0, 오류율 0, 두 시드·40제품으로 격리 개발 평가 | 다섯 방식의 실행 2·유출 0·정지 0, 비율 빈칸, 평균 0.00, 표본 부족 | 종료 0이나 방식 지표·표본 합계 행 모두 없음 | 실패 → H1 |
| P05 | 제공 로트 설정, 시드 1000·제품 1개, 동일 SHA와 `last_10` 선택 행이 있는 개발 보고서 fixture로 홀드아웃 | 유출/정지 0이면 선택 방식 `미확인`, 종료 0. T80③ 및 표본 조건 | 종료 2, `오류: 'last_10'` | 실패 → H1. 제출 개발 결과를 바꾼 것이 아닌 독립 fixture |
| P06 | 정상 JSON의 loss 값에 401자리 정수, 생성·평가 양쪽 CLI | 범위 밖 확률은 종료 2와 파일 미생성 | 두 CLI 모두 `OverflowError: int too large to convert to float`, 종료 1 | 실패 2개 → H2 |
| P07 | 결함 추출 0, 최초 결과 난수 .40, 요청 0, 재검사 .50; 수리 전/후 비교 | loss .5이면 재검사 임계 .45라 PASS, 수리 후 .9라 FAIL. 재검사 PASS는 유출 아님 | 각각 [FAIL,PASS] / [FAIL,FAIL], 유출 목록 빈칸 | 통과 |
| P08 | 제공 독립 설정 seed 15·500제품 | 정지가 없는 고장 설비의 유출은 격리 집합에 들어가지 않으며 분모에는 남음 | LEAK-2 정지 없음. 해당 설비에서 최초 PASS한 결함품 7개가 잔류 | 통과. `since_restart` 전역 포착률 1 미만의 구체적인 반례 설명 |
| P09 | 기준 커밋의 tests·rules.py·recipes·data·reports 기존 추적 경로와 작업 트리 비교 | 보호 대상 기존 파일 무수정 | 기존 추적 파일 81개 변경 없음 | 통과 |
| P10 | v1·v2 1/2/3/5단계 샘플, 기존 seed42 생성·summary·trace 2개 재실행 | 기존 보고서 및 CSV/meta 바이트 동일 | 보고서 26개 및 CSV/meta 2개 일치 | 통과 |
| P11 | 기존 개발 6규칙×100시드, 홀드아웃 100시드, baseline 100시드 재평가 | 기존 `eval_dev`·`eval_holdout`·`eval_baseline` 불변 | 보고서 6개 모두 바이트 일치 | 통과 |
| P12 | 6단계 샘플 및 독립/집중 개발·홀드아웃 각 100시드 재평가 | 제출 보고서 재현 | 샘플 6개+평가 4개 모두 바이트 일치 | 통과 |
| P13 | seed42/500 및 seed7/200을 각 두 번 생성·판정, summary·containment 포함 | T81 CSV·meta·보고서 바이트 동일 | 각 8개 파일(CSV, meta, 보고서 6종)이 모두 동일 | 통과. M1의 누락 검증을 이번 검수에서 별도로 수행 |

## 현행 기대표 대조

| 기대표 | 확인 결과 |
| --- | --- |
| T67–T69 | 등록 lot·products 열, 오류 우선순위·상태 보존, 헤더/모드 조합 통과. P01·P03으로 경계 보강 |
| T70–T76 | 창/최근 N/로트/재가동 구간, 재검사 PASS 제외, 다른 검사 보류 포함 통과. P02로 물리 순서·미래 행 제외 확인 |
| T77–T79 | 전체 합산, 정밀도·잔류, 0.90 원값 경계·동률·표본 기준 통과 |
| T80 | 기존 함수/선택 파일/선택 없음 테스트 통과. 단, **무정지이며 선택이 있는 CLI 조합은 실패(H1)** |
| T81 | 기존 테스트 통과. P13에서 CSV·meta·보고서 두 시드 재현까지 확인. 제출 테스트 누락은 M1 |
| T82–T83 | last_10 안/밖 유출, 집중 설정 결함률·결함 로트 비율 테스트 통과 |
| T84–T85 | 잘못된 규칙·설정·홀드아웃 인자 거절과 같은 명령의 보고서 재현 통과 |
| T86 | 다른 설비/거절된 재가동이 구간을 자르지 않는 테스트 통과 |
| T87 | 표에 적힌 7종 오류 통과. 추가 큰 정수 경계는 실패(H2) |
| T88 | 잘못된 유출 목록·중복·부분집합·결함 목록 없음·미등록 ID 거절 통과 |

T67–T88 표 자체는 수정하지 않았다. 새 사용자 판단을 요구할 정도의 명세 모순은 발견하지 않았다. `since_restart`의 “그 구간” 상한은 **실제로 정지가 발생한 구간**의 상한으로 해석해야 한다. 모든 실행에서 고장 설비가 정지한다거나 전체 유출을 100% 포착한다는 보장은 아니다(P08).

## Claude의 의견에 동의하는 부분과 근거

- 반례 후에도 로트 형식 검사 순서, 거절 행의 상태 보존, 허용된 같은 설비 재가동만 구간을 자르는 방식에 동의한다. 기존 테스트 및 P01–P03의 추가 조합에서 확인했다.
- 격리는 제품 상태를 바꾸지 않는 분석이라는 설명에 동의한다. P02는 분석 호출 전후 제품·설비·입력·정지·재가동 상태를 비교했다.
- 두 설정 모두 표본은 충분하지만 선택할 방식이 없다는 결론에 동의한다. P12가 제출 평가 보고서 4개 전체를 다시 계산해 동일 바이트임을 확인했다. 개발 선택이 없으므로 홀드아웃에서 다시 선택하지 않은 것도 맞다.
- 개발 독립/집중에서 `lot`이 낮은 이유를 **미검증 추정**으로 표시한 것은 적절하다. 이번 검수도 그 인과 가설 전체를 검증하지 않았다. P08의 무정지 실행은 `since_restart` 잔류의 구체적인 한 사례만 설명한다.
- `--selected-from`을 해당 홀드아웃 모드 밖에서 거절하고 lot 설비에 lot_size 없는 생성 설정을 거절한다는 추가 해석은 기록에 공개되어 있으며 코드와 일치한다.
- 5단계 테스트 로그 복원 과정에서 기준 커밋의 `stage5-tests.txt` 내용이 새 `v2-stage5-tests.txt`로 동일하게 옮겨졌음을 diff로 확인했다. 실제 보호 대상 보고서·설정·샘플은 바뀌지 않았다.

재계산된 평가 요약(포착률 / 평균 격리량):

| 방식 | 독립 개발 | 집중 개발 | 독립 홀드아웃 | 집중 홀드아웃 |
| --- | --- | --- | --- | --- |
| window | 0.0410 / 5.65 | 0.0204 / 7.30 | 0.0310 / 5.65 | 0.0360 / 7.48 |
| last_10 | 0.1475 / 41.06 | 0.1156 / 51.88 | 0.1938 / 41.23 | 0.1982 / 53.90 |
| last_20 | 0.2787 / 84.96 | 0.2585 / 106.31 | 0.2868 / 85.35 | 0.3514 / 110.12 |
| lot | 0.0738 / 22.85 | 0.0816 / 21.63 | 0.0930 / 22.87 | 0.1171 / 21.50 |
| since_restart | 0.8525 / 294.69 | 0.8231 / 323.01 | 0.9845 / 299.04 | 0.9910 / 333.10 |
| 유출품 / 유출 실행 | 122 / 61 | 147 / 55 | 129 / 53 | 111 / 48 |
| 판정 | 기준 충족 방식 없음 | 기준 충족 방식 없음 | 검증할 선택 없음 | 검증할 선택 없음 |

## 테스트 실행 명령과 결과 원문

### 지정 명령 직접 실행

공통으로 `PYTHONDONTWRITEBYTECODE=1`, `PYTHONIOENCODING=utf-8`를 현재 프로세스에만 설정했다. 파일이나 영구 환경 설정은 바꾸지 않았다.

```powershell
py -m unittest discover -s tests
```

```text
No installed Python found!
```

종료 코드 1. 테스트가 시작되지 않았다.

```powershell
py -m unittest handoff/reviews/probes/test_probe_012.py
```

```text
No installed Python found!
```

종료 코드 1. 반례도 이 명령으로는 시작되지 않았다. `py -0p` 역시 `No installed Pythons found!`였다. 따라서 **원래 py 런처 경로의 실행은 미검증**이다. 이 환경 문제를 저장소 결함으로 세지 않는다.

### 설치된 실행 파일로 기존 테스트 추가 실행

기존 Python 3.12.10 실행 파일은 동작했다. 아래 명령은 unittest와 기존 테스트 파일·단정·제품 코드를 그대로 실행한다. 테스트 내부의 자식 프로세스 인자에서 첫 항목 `py`만 동일한 `sys.executable`로 바꾸는 메모리 내 어댑터를 썼다. 설치·레지스트리 수정·소스 수정은 없다. 이 결과를 원래 런처가 성공했다고 보고하지 않는다.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
@'
import runpy, subprocess, sys
original = subprocess.Popen
class InstalledPython(original):
    def __init__(self, args, *a, **kw):
        if isinstance(args, (list, tuple)) and args and args[0] == 'py':
            args = [sys.executable, *args[1:]]
        super().__init__(args, *a, **kw)
subprocess.Popen = InstalledPython
sys.argv = ['unittest', 'discover', '-s', 'tests']
runpy.run_module('unittest', run_name='__main__')
'@ | & 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -
```

```text
...................................................................................................................................................................
----------------------------------------------------------------------
Ran 163 tests in 95.065s

OK
T44 seed=42 products=500 generation_seconds=0.143207 judgment_analysis_seconds=0.084427
T44 seed=7 products=200 generation_seconds=0.048349 judgment_analysis_seconds=0.031987
T44 seed=42 all_rows_deepcopy_invariant_seconds=40.291093
T44 seed=7 all_rows_deepcopy_invariant_seconds=6.444858
```

종료 코드 0. 기존 138개를 포함한 163개 통과. 기존 테스트 8개 파일과 `src/rules.py`는 기준 커밋과 동일하다. Python 3.9나 py 런처로 선택되는 별도 버전에서는 실행하지 않았다.

### 반례·보존 검증 추가 실행

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff/reviews/probes/test_probe_012.py
```

```text
...FFFF.......
======================================================================
FAIL: test_p04_no_stop_development_has_all_zero_metrics (handoff.reviews.probes.test_probe_012.AdversarialProbes.test_p04_no_stop_development_has_all_zero_metrics)
No stops still means five empty C sets, not absence of the methods.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_012.py", line 141, in test_p04_no_stop_development_has_all_zero_metrics
    self.assertEqual([r["method"] for r in metrics], list(METHODS), repr(rows))
AssertionError: Lists differ: [] != ['window', 'last_10', 'last_20', 'lot', 'since_restart']

Second list contains 5 additional elements.
First extra element 0:
'window'

- []
+ ['window', 'last_10', 'last_20', 'lot', 'since_restart'] : [{'section': 'notice', 'method': '', 'runs': '', 'leak_runs': '', 'leaks': '', 'stops': '', 'capture_rate': '', 'mean_quarantine': '', 'precision': '', 'mean_residual': '', 'value': '생성 데이터의 확률은 가정이며 실제 설비 진단 근거가 아니다.'}, {'section': 'provenance', 'method': 'config_sha256', 'runs': '', 'leak_runs': '', 'leaks': '', 'stops': '', 'capture_rate': '', 'mean_quarantine': '', 'precision': '', 'mean_residual': '', 'value': '087b20de0c80277e1301ce0f292a17734c7482c9955651d01a4637e2bb98c170'}, {'section': 'provenance', 'method': 'recipe_sha256', 'runs': '', 'leak_runs': '', 'leaks': '', 'stops': '', 'capture_rate': '', 'mean_quarantine': '', 'precision': '', 'mean_residual': '', 'value': '438229b58c9e8bc4a9f464704c9ace956150e33920fa36f0441add7f354ca7ac'}, {'section': 'provenance', 'method': 'equipment_sha256', 'runs': '', 'leak_runs': '', 'leaks': '', 'stops': '', 'capture_rate': '', 'mean_quarantine': '', 'precision': '', 'mean_residual': '', 'value': '737871b388d3dfeb65c24d899c59f5f1a6e210e3ba8c06d39a7bdcf7d55d01a0'}, {'section': 'provenance', 'method': 'generator_version', 'runs': '', 'leak_runs': '', 'leaks': '', 'stops': '', 'capture_rate': '', 'mean_quarantine': '', 'precision': '', 'mean_residual': '', 'value': '1.3.0'}, {'section': 'provenance', 'method': 'seeds', 'runs': '', 'leak_runs': '', 'leaks': '', 'stops': '', 'capture_rate': '', 'mean_quarantine': '', 'precision': '', 'mean_residual': '', 'value': '0-1'}, {'section': 'provenance', 'method': 'products', 'runs': '', 'leak_runs': '', 'leaks': '', 'stops': '', 'capture_rate': '', 'mean_quarantine': '', 'precision': '', 'mean_residual': '', 'value': '40'}, {'section': 'selection', 'method': '', 'runs': '', 'leak_runs': '', 'leaks': '', 'stops': '', 'capture_rate': '', 'mean_quarantine': '', 'precision': '', 'mean_residual': '', 'value': '평가 표본 부족'}]

======================================================================
FAIL: test_p05_selected_holdout_without_stops_is_unconfirmed (handoff.reviews.probes.test_probe_012.AdversarialProbes.test_p05_selected_holdout_without_stops_is_unconfirmed)
A valid selection followed by zero events must say unconfirmed, not error.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_012.py", line 163, in test_p05_selected_holdout_without_stops_is_unconfirmed
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 2 != 0 : 오류: 'last_10'


======================================================================
FAIL: test_p06_huge_integer_probability_is_a_clean_configuration_error (handoff.reviews.probes.test_probe_012.AdversarialProbes.test_p06_huge_integer_probability_is_a_clean_configuration_error) (module='src.generate')
Valid JSON integer outside [0,1] must exit 2, just like 1.5 or NaN.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_012.py", line 178, in test_p06_huge_integer_probability_is_a_clean_configuration_error
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 1 != 2 : Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 333, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 324, in main
    meta = generate(args.seed, args.products, args.out, args.config)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 293, in generate
    generator, normal, rows, counts = build_rows(seed, products, config, recipe.models, equipment)
                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 282, in build_rows
    generator = Generator(seed, config, models, equipment)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 41, in __init__
    check_lot_config(config, equipment_book)
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 259, in check_lot_config
    if not isinstance(loss, dict) or not all(unit(value) for value in loss.values()):
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 259, in <genexpr>
    if not isinstance(loss, dict) or not all(unit(value) for value in loss.values()):
                                             ^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 241, in unit
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
                                           ^^^^^^^^^^^^^^^^^^^^
OverflowError: int too large to convert to float


======================================================================
FAIL: test_p06_huge_integer_probability_is_a_clean_configuration_error (handoff.reviews.probes.test_probe_012.AdversarialProbes.test_p06_huge_integer_probability_is_a_clean_configuration_error) (module='src.evaluate')
Valid JSON integer outside [0,1] must exit 2, just like 1.5 or NaN.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_012.py", line 178, in test_p06_huge_integer_probability_is_a_clean_configuration_error
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 1 != 2 : Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\evaluate.py", line 405, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\evaluate.py", line 380, in main
    runs, stops, provenance = evaluate_containment(args.config, seeds, parse_rules(args.rules), args.products)
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\evaluate.py", line 314, in evaluate_containment
    generator, _, rows, _ = build_rows(seed, products, config, recipe.models, ruled)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 282, in build_rows
    generator = Generator(seed, config, models, equipment)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 41, in __init__
    check_lot_config(config, equipment_book)
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 259, in check_lot_config
    if not isinstance(loss, dict) or not all(unit(value) for value in loss.values()):
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 259, in <genexpr>
    if not isinstance(loss, dict) or not all(unit(value) for value in loss.values()):
                                             ^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 241, in unit
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
                                           ^^^^^^^^^^^^^^^^^^^^
OverflowError: int too large to convert to float


----------------------------------------------------------------------
Ran 13 tests in 231.029s

FAILED (failures=4)
P09 protected tracked files unchanged: 81
P10 old sample/seed42 reports byte-identical: 26 ; CSV/meta: 2
P11 old evaluation reports byte-identical: 6
P12 submitted lot reports byte-identical: 10
P13 T81 CSV/meta/6 reports reproduce: seeds 42/500 and 7/200
```

종료 코드 1. 테스트 메서드 13개 중 10개 통과, 3개 메서드에서 4개 실패(P06의 생성·평가 subTest 각 1개 포함). 실패를 기대 실패로 바꾸거나 검증을 약화하지 않았다. 실패 내용은 H1·H2에 연결했다.

## 보존·검수 한계

- 저장소 내 작성 대상은 이 리뷰와 `probes/test_probe_012.py` 두 파일뿐이다. `src/`, `tests/`, `CLAUDE.md`, `.claude/` 및 기존 산출물은 수정하지 않았다. commit·push·패키지 설치를 하지 않았다.
- 시작할 때 이미 존재하던 미추적 `handoff/loop-logs/012-codex.txt`는 검토 루프 로그이며 직접 수정하지 않았다.
- 보호 대상 기존 추적 파일 81개 무변경, 기존 보고서 32개와 seed42 CSV/meta 2개 재생성 일치, 신규 제출 보고서 10개 재현을 확인했다. `git diff --check`는 출력 없이 종료 0이었다.
- 전체 테스트의 통과는 위에 명시한 Python 3.12.10 대체 실행 조건에서의 결과다. 원래 `py` 런처 환경 문제는 남아 있다.
- T81 현재 산출물은 재현되지만 제출 테스트의 누락(M1)은 남아 있고, 무정지 홀드아웃(H1)과 큰 정수 설정 오류 처리(H2)도 수정되지 않았다.

VERDICT: FIX
