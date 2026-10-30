검수 모델: gpt-6.1-sol

# 리뷰 013 — 리뷰 012 수정 재검토

검수일: 2026-10-31. **이전 높음 2건·중간 1건 모두 해결. 새 높음·중간·낮음 없음. 미해결 수정 요구 0건.**

기준은 `handoff/tasks.md` 맨 위 「현행 작업」의 명세·T67–T88와 완료된 1–5단계 보존 조건이다. `handoff/setup-notes.md`, `handoff/gpt-log.md`의 관련 구현·수정 기록, `handoff/decisions.md`, 012 리뷰, 최근 git log와 작업 트리 diff를 대조했다. `docs/`의 과거 명세는 판정 기준으로 쓰지 않았다. `docs/solutions/`와 `.compound-engineering/config.yaml`은 없다.

작업 조율에 `practical-work-operation`만 적용했다. 요청대로 플러그인 리뷰 스킬·보조 에이전트·이전 반례 전체 재실행은 사용하지 않았다. 검수 산출물은 이 파일과 `handoff/reviews/probes/test_probe_013.py`뿐이다. 시작부터 존재한 미추적 `handoff/loop-logs/013-codex.txt`는 수정하지 않았다.

검토 범위:

```text
git diff f3484b70e20cdc4effa1f474dd86d34e4c6a4949..HEAD
HEAD: 6a4debd5e56b69776d8dd5f056614c9243d8379d
6a4debd fix: apply review 012 (loop 1/3)

handoff/gpt-log.md
handoff/loop-logs/012-claude.txt
src/containment.py
src/generate.py
tests/test_containment.py
```

`git diff --check f3484b70e20cdc4effa1f474dd86d34e4c6a4949..HEAD`는 출력 없이 종료 코드 0이었다.

## 이전 높음·중간 항목별 판정

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 | 재검토 판정 |
| --- | --- | --- | --- | --- | --- | --- |
| H1 | 높음 | `src/containment.py:51`, `tests/test_containment.py:431` | 정지 없는 평가에서 지표가 사라지고 선택 있는 홀드아웃이 오류로 끝났던 문제 | `run_scopes`가 적용 가능한 방식별로 서로 독립인 빈 집합을 먼저 만든다. 전체 테스트의 무정지 개발·홀드아웃 회귀 검사와 P01–P04가 통과했다. 무정지이나 유출 8건인 경우도 다섯 방식 모두 포착률 0.0000·격리량 0.00·잔류 평균 4.00을 유지한다. 다섯 선택 방식 각각 무정지 홀드아웃에서 종료 0·미확인이며 재선택하지 않는다. | 추가 수정 요구 없음 | **해결** |
| H2 | 높음 | `src/generate.py:239`, `tests/test_containment.py:320` | 큰 정수 확률이 OverflowError·종료 1을 일으켰던 문제 | 타입 → 0–1 범위 → 유한성 순서라 큰 정수는 float 변환에 도달하지 않는다. P05는 loss·두 집중 확률 각각 ±10**400을 두 CLI에 넣은 12개 경우 모두 종료 2·traceback 없음·파일 미생성을 확인했다. P06은 NaN·±inf·bool·다른 타입·경계 바로 바깥 거절과 0·1·-0.0·경계 안쪽 허용을 확인했다. | 추가 수정 요구 없음 | **해결** |
| M1 | 중간 | `tests/test_containment.py:250` | T81이 CSV만 비교하고 두 meta·판정 보고서는 비교하지 않았던 문제 | 각 시드 42/500·7/200에 대해 별도 폴더에 같은 파일명으로 생성하고 실제 `src.main --summary --containment`를 실행한다. CSV·meta·reports 전체 파일의 상대경로와 바이트를 사전으로 비교한다. meta와 격리 보고서의 존재도 단정하며 기존 버전·헤더·주입 오류 수 단정을 유지한다. 강화된 T81을 포함한 전체 165개 테스트가 통과했다. | 추가 수정 요구 없음 | **해결** |

새 지적 사항은 없다. 기대표를 수정하지 않았고, 이번 변경에 관해 새 사용자 결정을 요구할 명세 모순도 발견하지 못했다.

## 이번 diff에 집중한 반례

파일: `handoff/reviews/probes/test_probe_013.py`. P01–P07이 기대표에 없는 추가 조합·경계 반례이며, P08–P11은 요청된 보존 검증이다. 생성 파일·설정·보고서는 모두 `tempfile.TemporaryDirectory` 안에만 썼다.

| ID | 입력 | 예상(명세 근거) | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | 입력 0행, lot on/off × restart on/off 4조합. 반환된 window 집합에 표식 추가 후 다른 방식·재호출 확인 | 로트·재가동은 독립. 적용 방식은 빈 집합이고 비로트에는 lot 없음. 정지 없으면 격리 CSV의 데이터 행 없음. 호출·방식 간 집합 공유 없음 | 네 조합 모두 기대 방식·빈 집합, build_containment는 빈 목록. 표식이 다른 방식·다음 호출에 전파되지 않음 | 통과 |
| P02 | 결함률 1·결함 FAIL 0·오류율 0, 고장 설비 LEAK-2의 FAIL 0, 12제품 × 2시드 | 정지가 없어도 유출은 분모에 남음. 각 방식 포착 0, 정밀도 빈칸, 격리 평균 0, 잔류 평균은 유출/실행 수 | 유출 8·유출 실행 2·정지 0. 다섯 방식 모두 포착률 0.0000·정밀도 빈칸·격리 평균 0.00·잔류 평균 4.00 | 통과 |
| P03 | SHA 일치하는 개발 선택 fixture에서 다섯 방식을 각각 선택, 홀드아웃 1제품·정지/유출 0 | T80의 선택 방식 미확인과 선택 유지 규칙을 모든 방식에 적용. 모든 방식 지표도 존재 | 다섯 CLI 모두 종료 0, 선택 방식만 미확인, selection 행 없음, 다섯 방식 지표 존재 | 통과 |
| P04 | 정지 있는 실행 E={a}, C={a}와 무정지 실행 E={d} 혼합. 두 번째 실행은 lot을 잘못 쓴 FAIL 거절 직후 정상 PASS | 거절은 상태를 바꾸지 않음. 무정지 실행도 분모에 포함. 지표는 전체 합산이며 분석은 상태 불변 | 거절 FAIL 뒤 PASS 허용·정지 없음. 모든 방식의 포착률·격리 평균·잔류 평균 각각 1/2. 분석 전후 제품·설비 동일 | 통과 |
| P05 | 세 확률 필드 각각 양수/음수 401자리 정수, 생성·평가 CLI 양쪽 | 유한한 0–1 값 위반은 두 CLI 모두 종료 2, 파일 미생성 | 12개 CLI 모두 종료 2, traceback 없음, 설정 외 파일/폴더 없음 | 통과 |
| P06 | 세 필드 각각 NaN·±inf·bool·None·문자열·list·dict·0 바로 아래·1 바로 위, 그리고 0·1·-0.0·0 바로 위·1 바로 아래 | bool을 포함한 비수치와 비유한·범위 밖은 거절. 유한한 0–1 경계는 허용 | 잘못된 값 33개 ValueError, 유효 경계 15개 허용 | 통과 |
| P07 | 큰 음수 loss로 생성 거절 뒤 같은 설정 경로·출력 경로에 정상 설정을 써 다시 생성·판정 | 거절된 설정은 부분 산출물을 남기지 않음. 후속 정상 입력은 정상 생성·판정 | 최초 종료 2, 후속 생성·summary·containment 종료 0, 규칙 8개의 rejection_count 모두 0, 버전 1.3.0 | 통과. 검수 반례의 집계 형식 오해를 바로잡고 이 1개만 재실행 |
| P08 | 5단계 완료 기준 d12e92e의 tests·rules.py·recipes·data·reports 기존 추적 경로 비교 | 기존 테스트 8개·rules.py·설정·샘플·보고서 무수정 | 기존 추적 파일 81개 모두 변경 없음 | 통과 |
| P09 | v1·v2 1/2/3/5단계 샘플과 seed42 생성·summary·trace 2개 재실행 | 완료 단계 보존 조건: 보고서·CSV·meta 바이트 동일 | 보고서 26개와 CSV/meta 2개 모두 저장된 파일과 바이트 동일 | 통과 |
| P10 | 이전 개발 6규칙×100시드, 홀드아웃 100시드, baseline 100시드 재평가 | eval_dev·eval_holdout·eval_baseline 보존 | 보고서 6개 모두 바이트 동일 | 통과 |
| P11 | 현행 로트 샘플, 독립/집중 설정 개발·홀드아웃 각각 100시드 재평가 | H1 수정이 제출된 격리 보고서 값을 바꾸지 않는지 확인 | 샘플 6개·평가 4개 모두 바이트 동일 | 통과 |

P07 초안은 `rejections.csv`를 개별 거절 행 목록으로 오해해 빈 목록을 기대했다. 실제 파일은 규칙별 집계 8행이며 모두 0이었다. `src/recipe_reports.py`의 기존 집계 형식을 확인하고 **검수용 반례만** “8행·거절 횟수 전부 0” 단정으로 고쳤다. 제품 코드·기존 테스트·명세는 바꾸지 않았다. 최초 11개 실행 중 다른 10개는 통과했고, 수정한 P07만 별도 재실행해 통과했다. 전체 테스트는 이 반례 수정 후 반복하지 않았다.

## 보존 조건과 Claude 의견 판정

- 기존 8개 테스트 파일과 `src/rules.py`는 5단계 완료 기준과 동일하고, 전체 테스트 실제 실행은 165개 통과했다. `lot_tracking` 없음/false의 보고서 동일성도 기존 T69가 통과했다.
- 기존 설정·샘플·보고서는 저장된 파일의 무변경만 확인한 것이 아니라, P09·P10에서 임시 폴더에 재생성해 바이트 비교까지 했다. seed42 CSV/meta 동일성으로 기존 생성 난수 흐름의 대표 사례도 확인했다.
- 반례 후 H1의 빈 집합 초기화 설명에 동의한다. 정지 없는 실행도 실행·유출 분모에서 빠지지 않으며, 비로트의 방식 수와 정지 없는 개별 격리 보고서 출력도 보존된다(P01–P04).
- “기존 평가에서는 빠진 방식을 이미 빈 집합으로 셌으므로 제출 보고서 값은 바뀌지 않는다”는 Claude의 설명을 받아들인다. 코드 경로뿐 아니라 P11의 제출 보고서 10개 재생성·바이트 일치로 확인했다. 구현자가 재생성하지 못했다는 사실을 미해결 결함으로 세지 않는다.
- H2에서 범위를 유한성보다 먼저 검사하는 수정에 동의한다. int는 허용 범위 안이면 0·1뿐이므로 OverflowError 경로가 없고, NaN·inf·bool·경계 검사도 유지된다(P05–P07).
- M1의 meta·보고서 묶음 비교 강화에 동의한다. 실제 두 번의 판정을 거쳐 파일명과 내용 전체를 비교하므로 이전 검증 누락을 해결한다.
- 이번 수정 기록에는 기존 지적을 기각해 달라는 별도 반박은 없었다. 세 수정의 근거와 기존 보고서 보존 설명을 검증해 모두 해결로 처리했다.

## 테스트 실행 명령과 결과 원문

### 지정 명령 직접 실행

프로세스 환경에만 아래 두 값을 설정했다. 파일·영구 환경은 바꾸지 않았다.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
py -m unittest discover -s tests
```

```text
No installed Python found!
```

종료 코드 1. 테스트는 시작되지 않았다. **지정 py 런처를 통한 전체 테스트 실행은 미검증**이다.

```powershell
py -m unittest handoff/reviews/probes/test_probe_013.py
```

```text
No installed Python found!
```

종료 코드 1. 반례도 이 명령에서는 시작되지 않았다.

### 설치된 Python으로 전체 테스트 실제 실행 1회

기존 설치 Python 3.12.10을 사용했다. 테스트 파일·단정은 수정하지 않았으며, 테스트가 시작하는 자식 프로세스의 첫 인자 `py`만 같은 인터프리터로 바꾸는 메모리 내 어댑터를 썼다. 아래 전체 테스트는 한 번만 실행했다. 지정 명령의 성공이나 Python 3.9 검증으로 보고하지 않는다.

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
.....................................................................................................................................................................
----------------------------------------------------------------------
Ran 165 tests in 131.898s

OK
T44 seed=42 products=500 generation_seconds=0.170492 judgment_analysis_seconds=0.122259
T44 seed=7 products=200 generation_seconds=0.087465 judgment_analysis_seconds=0.033842
T44 seed=42 all_rows_deepcopy_invariant_seconds=61.582899
T44 seed=7 all_rows_deepcopy_invariant_seconds=7.895771
```

종료 코드 0. 기존 138개와 6단계 테스트를 포함한 165개 통과.

### 이번 반례·보존 검증 최초 실행

반례 CLI는 `sys.executable`을 사용하므로 아래에서는 별도 어댑터를 쓰지 않았다.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff/reviews/probes/test_probe_013.py
```

```text
......F..P01: four lot/restart combinations; independent empty sets; no report rows
P02: no stops, leaks=8; capture=0.0000; residual=4.00
P03: all five selected methods exit 0 / unconfirmed; no reselection
P04: rejected FAIL does not stop; mixed runs capture/quarantine/residual=1/2; state unchanged
P05: +/- 10**400 in all three probability fields; 12 CLI errors exit 2; no output
P06: 33 invalid type/nonfinite/outside-boundary cases rejected; 15 valid boundary cases accepted
P08: protected pre-stage6 tracked files unchanged: 81
P09: existing reports byte-identical: 26 ; CSV/meta: 2
P10 completed: eval_dev
P10 completed: eval_holdout
P10 completed: eval_baseline
.P10: previous evaluation reports byte-identical: 6
P11 completed: lot
P11 completed: lot_clustered
.
======================================================================
FAIL: test_p07_rejected_configuration_then_valid_run_same_destination (handoff.reviews.probes.test_probe_013.FocusedProbes.test_p07_rejected_configuration_then_valid_run_same_destination)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_013.py", line 199, in test_p07_rejected_configuration_then_valid_run_same_destination
    self.assertEqual(rows, [])
AssertionError: Lists differ: [{'rule_id': 'RULE_RECIPE', 'rejection_cou[374 chars]'0'}] != []

First list contains 8 additional elements.
First extra element 0:
{'rule_id': 'RULE_RECIPE', 'rejection_count': '0'}

+ []
- [{'rejection_count': '0', 'rule_id': 'RULE_RECIPE'},
-  {'rejection_count': '0', 'rule_id': 'RULE_SEQ'},
-  {'rejection_count': '0', 'rule_id': 'RULE_INSP_PRE'},
-  {'rejection_count': '0', 'rule_id': 'RULE_NOT_DONE'},
-  {'rejection_count': '0', 'rule_id': 'RULE_FAIL_HOLD'},
-  {'rejection_count': '0', 'rule_id': 'RULE_PRESERVE'},
-  {'rejection_count': '0', 'rule_id': 'RULE_RETEST'},
-  {'rejection_count': '0', 'rule_id': 'RULE_EQUIP'}]

----------------------------------------------------------------------
Ran 11 tests in 287.373s

FAILED (failures=1)
P11: current sample/evaluation reports byte-identical: 10
```

종료 코드 1. 유일한 실패 P07은 위에서 설명한 검수 반례의 집계 형식 오해다.

### P07 실패 원인 확인을 위한 단독 재현

수정 전 단독 실행으로 동일 실패를 확인했다.

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff.reviews.probes.test_probe_013.FocusedProbes.test_p07_rejected_configuration_then_valid_run_same_destination
```

```text
F
======================================================================
FAIL: test_p07_rejected_configuration_then_valid_run_same_destination (handoff.reviews.probes.test_probe_013.FocusedProbes.test_p07_rejected_configuration_then_valid_run_same_destination)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_013.py", line 199, in test_p07_rejected_configuration_then_valid_run_same_destination
    self.assertEqual(rows, [])
AssertionError: Lists differ: [{'rule_id': 'RULE_RECIPE', 'rejection_cou[374 chars]'0'}] != []

First list contains 8 additional elements.
First extra element 0:
{'rule_id': 'RULE_RECIPE', 'rejection_count': '0'}

+ []
- [{'rejection_count': '0', 'rule_id': 'RULE_RECIPE'},
-  {'rejection_count': '0', 'rule_id': 'RULE_SEQ'},
-  {'rejection_count': '0', 'rule_id': 'RULE_INSP_PRE'},
-  {'rejection_count': '0', 'rule_id': 'RULE_NOT_DONE'},
-  {'rejection_count': '0', 'rule_id': 'RULE_FAIL_HOLD'},
-  {'rejection_count': '0', 'rule_id': 'RULE_PRESERVE'},
-  {'rejection_count': '0', 'rule_id': 'RULE_RETEST'},
-  {'rejection_count': '0', 'rule_id': 'RULE_EQUIP'}]

----------------------------------------------------------------------
Ran 1 test in 0.585s

FAILED (failures=1)
```

종료 코드 1.

### 검수 반례 P07 수정 후 해당 항목만 재실행

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff.reviews.probes.test_probe_013.FocusedProbes.test_p07_rejected_configuration_then_valid_run_same_destination
```

```text
.
----------------------------------------------------------------------
Ran 1 test in 0.518s

OK
P07: rejected config leaves no partial output; corrected config generates and judges successfully
```

종료 코드 0. 최종 반례 파일의 11개 항목은 최초 실행에서 통과한 10개와 수정 후 통과한 P07로 모두 확인했다. 원래 py 런처와 Python 3.9에서는 테스트 미검증이며, 이는 저장소의 미해결 높음·중간 문제로 세지 않는다.

VERDICT: PASS
