검수 모델: gpt-6.1-sol

# 리뷰 014 — v2 7a단계 최초 검수

검수일: 2026-10-31. **미해결 높음 2건·중간 1건, 수정 요구 3건. 낮음 지적 없음.** 기존 테스트는 인터프리터 연결을 보정한 실행에서 205개 통과했으나, 추가 반례 12개 중 3개가 실패했다. 제품 코드와 기존 테스트는 수정하지 않았다.

## 범위와 기준

기준은 `handoff/tasks.md` 맨 위 현행 작업의 명세·T89–T112 및 아래 완료 단계들의 보존 조건이다. `handoff/setup-notes.md`, `handoff/gpt-log.md`, `handoff/decisions.md`, 실제 소스·테스트·설정·제출 보고서를 대조했다. `docs/`의 과거 명세는 기준으로 사용하지 않았다. `.compound-engineering/config.yaml`과 `docs/solutions/`는 없다.

`practical-work-operation`을 작업 조율에 적용하고 `ce-code-review`의 읽기 전용 검수 지침을 참고했다. 사용자 지정 두 파일 외 산출물을 만드는 스킬 절차와 외부 모델 검토·보조 에이전트는 사용하지 않았다. 구현·커밋·푸시·설치·삭제는 하지 않았다. 시작부터 존재한 미추적 `handoff/loop-logs/014-codex.txt`는 건드리지 않았다.

검토 명령:

```text
git diff dc7f523e1a529f2c1d270bbe8a3e1daf651eb701..HEAD
git log dc7f523e1a529f2c1d270bbe8a3e1daf651eb701..HEAD
git diff --check dc7f523e1a529f2c1d270bbe8a3e1daf651eb701..HEAD
```

HEAD: `d93b38d8f664feec08f0a38d5c8890106c674aff`. `diff --check`는 출력 없이 종료 0. 변경 범위는 36파일이며, 기존 테스트 수정 없이 `tests/test_measurement.py`를 추가했다. 지정 범위의 커밋 전체는 다음과 같다.

```text
d93b38d docs(T105): correct seed 42 defect counts in README
6767823 feat(T105-T108,T111,T112): generate measured events and document stage 7a
ed969f1 feat(T96-T104,T110): report Cpk and Ppk per inspection equipment
3c79230 feat(T89-T95,T109): judge measured values and report computed results
314a909 docs(T89-T112): confirm stage 7a spec and record plan changes
bb73241 docs(T67-T88): record user approval of review 013
```

## 지적 사항

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| H1 | 높음 | `src/generate.py:360` (`:352`, `:450` 관련) | 큰 정수 이동량의 합을 float 계산에 넣을 때 예외가 빠져나가 종료 코드 1이 된다. | P05: 기본 측정 설정에서 `process_cpk=0.1`, `defect_shift_sigma=10**308`, `fault_shift_sigma={"LEAK-2":10**308}`. 각각은 유한한 양수로 검사를 통과하지만 합 `2*10**308`을 `shift * sigma`에서 float로 변환하다 `OverflowError`가 난다. 이 설정의 합성 평균도 유한 범위를 벗어난다. `tasks.md:149`·`:159`는 이런 분포를 파일 생성 전 종료 2로 거절하도록 명시한다. 실제는 traceback·종료 1이며 파일은 생성되지 않았다. | 분포 유도 계산의 수치 overflow를 설정 오류로 변환하고 CLI가 종료 2로 끝나게 한다. 개별 값뿐 아니라 합·분모·평균 계산의 overflow도 검사한다. P05 조건을 회귀 검증한다. |
| H2 | 높음 | `src/generate.py:43` (`:45`, `:450` 관련) | 유한하지만 매우 큰 생성값이 30자리 제한 검사에 도달하기 전에 `decimal.InvalidOperation`으로 종료 1이 된다. | P06: 기본 설정에서 `process_cpk=1e-307`, `error_rate=0`, 시드 42·20제품. sigma와 최대 이동 평균은 유한해 설정 검증을 통과한다. 첫 측정 확정에서 정밀도 100으로 수백 자리 수를 `.001`에 양자화하다 실패한다. `tasks.md:149`·`:160`은 생성값의 30자리 초과도 파일 생성 전 종료 2로 처리하도록 정한다. 실제는 traceback·종료 1이며 CSV/meta는 없다. `confirm_value(1e100)` 단독 호출에서도 같은 원인을 확인했다. | 양자화 전 표현 가능한 자릿수를 검사하거나 해당 Decimal 예외를 명시적인 값 오류로 변환한다. 기존 `Decimal(repr(x))`·`ROUND_HALF_UP` 규약은 유지하고 P06을 회귀 검증한다. |
| M1 | 중간 | `tests/test_measurement.py:701` (`:554`, `:564`, `:712` 관련) | T108의 설정 오류 사례들이 같은 임시 파일을 덮어써 독립적인 입력을 검증하지 못한다. | `setup_paths`는 항상 `folder/config.json`, `recipe_with`는 항상 같은 `recipe.json`을 반환한다. 8개 `configs` 원소를 모두 만든 후 복사하므로 실제 8파일에는 마지막 거대 규격 설정이 똑같이 복사된다. 첫 0 Cpk·음수 이동·금지 키·단측·없는 설비·재검사 한도 없음·극소 Cpk 사례를 각각 실행한 증거가 아니다. 뒤 `variant`의 기반에도 거대 규격이 남아 일부 사례가 다른 원인으로 거절되어도 통과할 수 있다. P07은 실제 helper의 첫 두 호출만으로 두 설정의 Cpk가 모두 1.33이고 경로가 하나임을 재현했다. | 설정과 레시피를 사례별 독립 경로에 즉시 저장하거나, 각 사례를 만들자마자 실행한다. 깨끗한 정상 설정을 기반으로 조건 하나씩 바꾸고 해당 오류 이유 및 CSV/meta·보고서 미생성을 단정한다. |

H1·H2는 일반적인 명세 밖 입력의 단순 예외가 아니다. 현행 명세가 직접 정한 수치 오류 처리·종료 코드와 다르므로 AGENTS.md의 영향 기준에 따라 높음이다. M1은 요구를 실제로 검증하지 못하는 테스트이므로 중간이다. 기대표는 수정하지 않았다. 이번 지적을 해결하기 위해 새 사용자 결정을 요구하는 명세 이견은 없다.

## 반례 탐색

파일: `handoff/reviews/probes/test_probe_014.py`. P01–P08이 기대표의 단일 사례와 다른 추가 입력·조합·수치 경계·검증기 자체의 반례이며, P09–P12는 보존 및 제출물 재생 검증이다. 생성 파일과 보고서는 모두 테스트 내부의 `tempfile.TemporaryDirectory` 안에만 썼다.

| ID | 입력 | 예상과 명세 근거 | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | FAIL→재검사 요청 뒤 소문자 설비, 31자리 초과 값, 소문자 이벤트+value를 차례로 입력. 직후 원문 `00010.0000`으로 다른 설비에서 재검사 | 필드·설비 오류는 상태와 요청을 보존. 정상 재검사는 PASS, 원문 보존, 설비 창 불산입 | 세 거절 전후 전체 제품·설비 및 입력 동일. 후속 PASS, 재검사 횟수 1, 새 설비 최초 검사 수 0 | 통과 |
| P02 | 측정+로트+재가동. 설비 정지 후 재가동 행에 lot와 value를 함께 넣고 하나씩 제거 | 명세 검사 순서 lot→value. 거절은 상태 보존. 정상 재가동은 창만 초기화 | lot 오류 우선, 다음 value 오류. 두 거절 후 전체 상태 동일. 정상 재가동 후 제품 불변·창 비움 | 통과 |
| P03 | 단측 LSL을 모델마다 `0`·`-0000.000`으로 표현. `-0.000`과 `-0.`+0 27개+`1` 입력. 그 뒤 한 모델의 unit만 변경 | 동등한 수치 규격 허용, 경계 PASS, 매우 작은 음수 FAIL, 같은 검사 단위 불일치 거절 | PASS·FAIL 정확 비교, 동등 규격 로딩 성공, unit 불일치 RecipeError | 통과 |
| P04 | LEAK-1·2의 최초 측정을 교차 입력하고 모든 seq를 1로 반복. 가동 설비의 재가동 거절 및 정지 설비의 재가동 허용 뒤 추가 측정 | 물리 순서 기준. 허용된 해당 설비 재가동만 구간 분리 | 거절 1, 허용 재가동 1. 두 설비 각 n=9·부분군 1이며 거절 재가동은 구간을 나누지 않음 | 통과 |
| P05 | 유한한 양의 정수 이동량 각각 `10**308`, Cpk 0.1 | 비유한 분포는 종료 2·파일 미생성 | `OverflowError`, 종료 1, CSV/meta 없음 | **실패 → H1** |
| P06 | 양의 유한 Cpk `1e-307`로 유한한 거대 측정값 생성 | 30자리 초과는 종료 2·파일 미생성 | `decimal.InvalidOperation`, 종료 1, CSV/meta 없음 | **실패 → H2** |
| P07 | T108 helper로 0 Cpk와 음수 이동 사례를 만든 뒤 나중에 파일 읽기 | 각 오류가 독립 입력으로 보존되어야 요구를 검증할 수 있음 | 경로 하나, 두 파일의 Cpk 모두 1.33. 첫 조건 소실 | **실패 → M1** |
| P08 | 약 10^15의 중심에 10^-15 간격인 30자리 측정값 125개, 음수 표시 영 경계 | Decimal 정밀도 100, 변동을 소실하지 않음, 지수 표기 없음, 음수 영 제거 | n=125·부분군 25, sigma 양수·Cpk 계산, 고정 소수 표기, `-0.000049`→`0.0000` | 통과 |
| P09 | 기준 커밋의 tests·rules.py·recipes·data·reports 추적 파일 비교 | 기존 파일 무수정 | 96개 Git blob 해시 일치, 기존 테스트 9파일 동일 | 통과 |
| P10 | v1·v2 1/2/3/5/6단계 샘플, 기존 생성 seed42·500제품 및 summary·trace 재생 | 기존 보고서·난수 흐름 대표 산출물 동일 | 보고서 32개와 생성 CSV/meta 2개 바이트 일치 | 통과 |
| P11 | 기존 dev 6규칙×100시드, holdout·baseline 및 독립/집중 로트 dev·holdout 재평가 | 기존 평가 보고서 동일, 선택 기준 보존 | 평가 보고서 10개 모두 바이트 일치 | 통과 |
| P12 | 측정 seed42·500제품 재생성 및 샘플·생성 자료 판정·summary·containment·capability·trace | 제출된 CSV/meta와 측정 보고서의 실제 재생 결과 동일 | 보고서 15개와 측정 CSV/meta 2개 바이트 일치 | 통과 |

## 보존 조건과 Claude 의견 판정

- **기존 테스트 무수정 통과:** 기준 커밋에 있던 테스트 9파일의 해시가 모두 같고, 아래 인터프리터 어댑터 실행에서 기존 165개+신규 40개=205개가 통과했다. `src/rules.py`도 동일하다.
- **기존 보고서 동일:** 파일이 변경되지 않았다는 정적 확인에 더해, 임시 폴더에서 기존 보고서 전체 42개(샘플·생성 32, 평가 10)를 재생성해 바이트 비교했다. 기존 seed42 CSV/meta도 일치했다. 비측정 생성기의 모든 가능한 시드·사용자 정의 설정을 전수 비교한 것은 아니다.
- **기본 측정 동작에 동의:** 반례 후 Decimal 비교, 거절 상태 불변, 재검사 창 제외, 재가동 구간 분리 설명에 동의한다. P01–P04·P08과 T89–T104·T109–T112 테스트가 근거다. `capability` 계산과 표시 분리, 반올림 전 sigma로 Cpk를 계산하는 경로도 소스로 확인했다.
- **재현성과 제출 수치에 동의:** P12가 제출된 측정 보고서 전체를 재현했고, T105·T106·T107도 통과했다. 시드 42의 완료 491·보류 6·폐기 3, LEAK-2 정지/재가동 각 1회, 5종 오류 각 24건, capability 계산됨 5설비·표본 부족 2설비라는 설명을 받아들인다. 고장·수리 구간이 합쳐진 Cpk를 실제 설비 능력으로 보증하지 않는 한계 표기도 명세와 맞는다.
- **T108 전체 일치 보고에는 동의하지 않음:** `gpt-log.md`의 T108 일치 표기는 M1 때문에 각 사례의 실행 증거가 되지 못한다. 신규 숫자 경계 P05·P06도 명시된 오류 처리를 위반한다. 전체 테스트가 녹색이라는 사실만으로 현행 명세 전체 충족을 선언할 수 없다.

## 테스트 명령과 결과 원문

### 지정 명령 직접 실행

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
py -m unittest discover -s tests
```

```text
No installed Python found!
```

종료 1. 런처가 설치 Python을 찾지 못해 테스트가 시작되지 않았다.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
py -m unittest handoff/reviews/probes/test_probe_014.py
```

```text
No installed Python found!
```

종료 1. **지정 py 런처의 두 명령을 통한 성공은 미검증**이다. 아래 결과를 지정 명령의 성공이나 Python 3.9 검증으로 보고하지 않는다.

### 설치 Python으로 전체 테스트 실행

먼저 아래 명령으로 실행했다. 테스트의 자식 프로세스에 남은 `py` 호출 때문에 132개 하위 사례가 실패했다. 기존 테스트 파일은 고치지 않았다.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest discover -s tests
```

종료 1. 실패 상세와 종료 결과의 수집 원문은 접은 영역에 붙인다. 이 첫 실행은 UTF-8 환경을 지정하지 않아 경로의 한글이 깨져 수집되었다.

<details>
<summary>어댑터 없는 첫 실행: 실패 상세 및 결과 원문</summary>

```text
.....................FFFFFFFFFFFFFFFFFF.................................FFF................FFFFFFFF.F............FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF...F........FF.FFFFFFFFFFF.FF..FFF
======================================================================
FAIL: test_t80_no_selection_exits_zero (test_containment.CommandTests.test_t80_no_selection_exits_zero)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 421, in test_t80_no_selection_exits_zero
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t80_runs_without_stops_keep_every_method (test_containment.CommandTests.test_t80_runs_without_stops_keep_every_method)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 440, in test_t80_runs_without_stops_keep_every_method
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t84_bad_commands_exit_two_without_reports (test_containment.CommandTests.test_t84_bad_commands_exit_two_without_reports) (case=('--config', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\generator_lot.json', '--rules', '3:2,5:2'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 384, in test_t84_bad_commands_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t84_bad_commands_exit_two_without_reports (test_containment.CommandTests.test_t84_bad_commands_exit_two_without_reports) (case=('--config', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\generator_lot.json', '--rules', '5:2'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 384, in test_t84_bad_commands_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t84_bad_commands_exit_two_without_reports (test_containment.CommandTests.test_t84_bad_commands_exit_two_without_reports) (case=('--config', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\generator_restart.json', '--rules', '3:2'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 384, in test_t84_bad_commands_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t84_bad_commands_exit_two_without_reports (test_containment.CommandTests.test_t84_bad_commands_exit_two_without_reports) (case=('--config', 'C:\\Users\\PC\\AppData\\Local\\Temp\\tmp2gfwf_ok\\two.json', '--rules', '3:2'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 384, in test_t84_bad_commands_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t84_bad_commands_exit_two_without_reports (test_containment.CommandTests.test_t84_bad_commands_exit_two_without_reports) (case=('--config', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\generator_lot.json', '--rules', '3:2', '--holdout'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 384, in test_t84_bad_commands_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t85_same_command_same_report (test_containment.CommandTests.test_t85_same_command_same_report)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 391, in test_t85_same_command_same_report
    self.assertEqual(cli(directory, *arguments, "--out", name, module="src.evaluate").returncode, 0)
AssertionError: 112 != 0

======================================================================
FAIL: test_t81_reproducible_and_truth_stays_out_of_csv (test_containment.GeneratorTests.test_t81_reproducible_and_truth_stays_out_of_csv) (seed=42)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 262, in test_t81_reproducible_and_truth_stays_out_of_csv
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t81_reproducible_and_truth_stays_out_of_csv (test_containment.GeneratorTests.test_t81_reproducible_and_truth_stays_out_of_csv) (seed=7)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 262, in test_t81_reproducible_and_truth_stays_out_of_csv
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t87_huge_integer_probability_is_a_setting_error (test_containment.GeneratorTests.test_t87_huge_integer_probability_is_a_setting_error) (change=['faulty_detection_loss'])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 335, in test_t87_huge_integer_probability_is_a_setting_error
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_huge_integer_probability_is_a_setting_error (test_containment.GeneratorTests.test_t87_huge_integer_probability_is_a_setting_error) (change=['defective_in_lot_probability', 'defective_lot_probability'])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 335, in test_t87_huge_integer_probability_is_a_setting_error
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_invalid_settings (test_containment.GeneratorTests.test_t87_invalid_settings) (change={'lot_size': 0})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 317, in test_t87_invalid_settings
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_invalid_settings (test_containment.GeneratorTests.test_t87_invalid_settings) (change={'lot_size': True})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 317, in test_t87_invalid_settings
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_invalid_settings (test_containment.GeneratorTests.test_t87_invalid_settings) (change={'faulty_detection_loss': {'LEAK-2': 1.5}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 317, in test_t87_invalid_settings
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_invalid_settings (test_containment.GeneratorTests.test_t87_invalid_settings) (change={'faulty_detection_loss': {'LEAK-1': 0.5}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 317, in test_t87_invalid_settings
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_invalid_settings (test_containment.GeneratorTests.test_t87_invalid_settings) (change={'lot_size': None})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 317, in test_t87_invalid_settings
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_invalid_settings (test_containment.GeneratorTests.test_t87_invalid_settings) (change={'defective_lot_probability': 0.25})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 317, in test_t87_invalid_settings
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_invalid_settings (test_containment.GeneratorTests.test_t87_invalid_settings) (change={'equipment': 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\equipment_restart.json'})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 317, in test_t87_invalid_settings
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t69_mode_and_header_combinations (test_containment.InputTests.test_t69_mode_and_header_combinations)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 106, in test_t69_mode_and_header_combinations
    self.assertEqual(cli(one, str(SAMPLE), *arguments, str(PLAIN_EQUIPMENT)).returncode, 0)
AssertionError: 112 != 0

======================================================================
FAIL: test_t88_leaked_products_validation (test_containment.MetaTests.test_t88_leaked_products_validation) (change={'leaked_products': ['']})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 362, in test_t88_leaked_products_validation
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t88_leaked_products_validation (test_containment.MetaTests.test_t88_leaked_products_validation) (change={'leaked_products': ['GEN_0001', 'GEN_0001']})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 362, in test_t88_leaked_products_validation
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t88_leaked_products_validation (test_containment.MetaTests.test_t88_leaked_products_validation) (change={'leaked_products': ['GEN_0002']})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 362, in test_t88_leaked_products_validation
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t88_leaked_products_validation (test_containment.MetaTests.test_t88_leaked_products_validation) (change={'defective_products': None})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 362, in test_t88_leaked_products_validation
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t88_leaked_products_validation (test_containment.MetaTests.test_t88_leaked_products_validation) (change={'defective_products': ['GEN_9999'], 'leaked_products': ['GEN_9999']})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 362, in test_t88_leaked_products_validation
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t74_empty_and_mode_cases (test_containment.ScopeTests.test_t74_empty_and_mode_cases)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 157, in test_t74_empty_and_mode_cases
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t40_invalid_fixtures_exit_three_without_reports (test_equipment.EquipmentFileTests.test_t40_invalid_fixtures_exit_three_without_reports) (name='equipment_window_zero.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 59, in test_t40_invalid_fixtures_exit_three_without_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t40_invalid_fixtures_exit_three_without_reports (test_equipment.EquipmentFileTests.test_t40_invalid_fixtures_exit_three_without_reports) (name='equipment_fails_exceeds.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 59, in test_t40_invalid_fixtures_exit_three_without_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t40_invalid_fixtures_exit_three_without_reports (test_equipment.EquipmentFileTests.test_t40_invalid_fixtures_exit_three_without_reports) (name='equipment_window_string.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 59, in test_t40_invalid_fixtures_exit_three_without_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t40_invalid_fixtures_exit_three_without_reports (test_equipment.EquipmentFileTests.test_t40_invalid_fixtures_exit_three_without_reports) (name='equipment_unknown_keys.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 59, in test_t40_invalid_fixtures_exit_three_without_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t40_invalid_fixtures_exit_three_without_reports (test_equipment.EquipmentFileTests.test_t40_invalid_fixtures_exit_three_without_reports) (name='equipment_empty.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 59, in test_t40_invalid_fixtures_exit_three_without_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t40_invalid_fixtures_exit_three_without_reports (test_equipment.EquipmentFileTests.test_t40_invalid_fixtures_exit_three_without_reports) (name='equipment_unknown_inspection.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 59, in test_t40_invalid_fixtures_exit_three_without_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t40_invalid_fixtures_exit_three_without_reports (test_equipment.EquipmentFileTests.test_t40_invalid_fixtures_exit_three_without_reports) (name='equipment_multiple_errors.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 59, in test_t40_invalid_fixtures_exit_three_without_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_sample_t33_to_t39_reports_and_all_rejected_state_unchanged (test_equipment.EquipmentReportTests.test_sample_t33_to_t39_reports_and_all_rejected_state_unchanged)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 311, in test_sample_t33_to_t39_reports_and_all_rejected_state_unchanged
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 112 != 0 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_equipment_with_stage_one_has_seven_rules_and_no_history (test_equipment.EquipmentReportTests.test_t41_equipment_with_stage_one_has_seven_rules_and_no_history)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 406, in test_t41_equipment_with_stage_one_has_seven_rules_and_no_history
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 112 != 0 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_four_reports_history_equipment_order_and_byte_reproducibility (test_equipment.EquipmentReportTests.test_t41_four_reports_history_equipment_order_and_byte_reproducibility)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 342, in test_t41_four_reports_history_equipment_order_and_byte_reproducibility
    self.assertEqual(first.returncode, 0, first.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t41_option_dependency_and_mode_specific_headers (test_equipment.EquipmentReportTests.test_t41_option_dependency_and_mode_specific_headers) (recipe=None, equipment=WindowsPath('C:/Users/PC/Documents/ChatGPT/������ KDT AI ���� ��Ʈķ��/project/recipes/equipment.json'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 379, in test_t41_option_dependency_and_mode_specific_headers
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 112 != 2 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_option_dependency_and_mode_specific_headers (test_equipment.EquipmentReportTests.test_t41_option_dependency_and_mode_specific_headers) (recipe=None, equipment=None)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 379, in test_t41_option_dependency_and_mode_specific_headers
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 112 != 2 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_option_dependency_and_mode_specific_headers (test_equipment.EquipmentReportTests.test_t41_option_dependency_and_mode_specific_headers) (recipe=WindowsPath('C:/Users/PC/Documents/ChatGPT/������ KDT AI ���� ��Ʈķ��/project/recipes/lamp_models_retest.json'), equipment=None)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 379, in test_t41_option_dependency_and_mode_specific_headers
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 112 != 2 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_option_dependency_and_mode_specific_headers (test_equipment.EquipmentReportTests.test_t41_option_dependency_and_mode_specific_headers)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 385, in test_t41_option_dependency_and_mode_specific_headers
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 112 != 2 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_without_equipment_all_nine_legacy_reports_unchanged (test_equipment.EquipmentReportTests.test_t41_without_equipment_all_nine_legacy_reports_unchanged) (name='sample_events')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 393, in test_t41_without_equipment_all_nine_legacy_reports_unchanged
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 112 != 0 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_without_equipment_all_nine_legacy_reports_unchanged (test_equipment.EquipmentReportTests.test_t41_without_equipment_all_nine_legacy_reports_unchanged) (name='sample_events_v2')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 393, in test_t41_without_equipment_all_nine_legacy_reports_unchanged
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 112 != 0 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_without_equipment_all_nine_legacy_reports_unchanged (test_equipment.EquipmentReportTests.test_t41_without_equipment_all_nine_legacy_reports_unchanged) (name='sample_events_retest')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 393, in test_t41_without_equipment_all_nine_legacy_reports_unchanged
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 112 != 0 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_holdout_flag_never_selects (test_evaluate.CommandTests.test_holdout_flag_never_selects)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_evaluate.py", line 108, in test_holdout_flag_never_selects
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t64_bad_arguments_exit_two_without_reports (test_evaluate.CommandTests.test_t64_bad_arguments_exit_two_without_reports) (seeds='0-1', rules='5:6')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_evaluate.py", line 102, in test_t64_bad_arguments_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t64_bad_arguments_exit_two_without_reports (test_evaluate.CommandTests.test_t64_bad_arguments_exit_two_without_reports) (seeds='5-3', rules='3:2')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_evaluate.py", line 102, in test_t64_bad_arguments_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t64_bad_arguments_exit_two_without_reports (test_evaluate.CommandTests.test_t64_bad_arguments_exit_two_without_reports) (seeds='0-1', rules='3:2,3:2')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_evaluate.py", line 102, in test_t64_bad_arguments_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t64_bad_arguments_exit_two_without_reports (test_evaluate.CommandTests.test_t64_bad_arguments_exit_two_without_reports) (seeds='x', rules='3:2')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_evaluate.py", line 102, in test_t64_bad_arguments_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t64_bad_arguments_exit_two_without_reports (test_evaluate.CommandTests.test_t64_bad_arguments_exit_two_without_reports) (seeds='0-1', rules='3')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_evaluate.py", line 102, in test_t64_bad_arguments_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t64_same_command_same_reports (test_evaluate.CommandTests.test_t64_same_command_same_reports)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_evaluate.py", line 88, in test_t64_same_command_same_reports
    self.assertEqual(cli(directory, *arguments, "--out", "one").returncode, 0)
AssertionError: 112 != 0

======================================================================
FAIL: test_t44_csv_meta_and_six_reports_repeat_for_both_seeds (test_generate.GeneratedInvariantTests.test_t44_csv_meta_and_six_reports_repeat_for_both_seeds) (seed=42)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_generate.py", line 137, in test_t44_csv_meta_and_six_reports_repeat_for_both_seeds
    self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t44_csv_meta_and_six_reports_repeat_for_both_seeds (test_generate.GeneratedInvariantTests.test_t44_csv_meta_and_six_reports_repeat_for_both_seeds) (seed=7)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_generate.py", line 137, in test_t44_csv_meta_and_six_reports_repeat_for_both_seeds
    self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_review005_m3_missing_candidate_explains_failure_without_output (test_generate.GeneratorTests.test_review005_m3_missing_candidate_explains_failure_without_output)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_generate.py", line 90, in test_review005_m3_missing_candidate_explains_failure_without_output
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_csv_physical_order_and_malformed_rows_are_reported_without_state_changes (test_recipe.RecipeCommandLineTests.test_csv_physical_order_and_malformed_rows_are_reported_without_state_changes)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 460, in test_csv_physical_order_and_malformed_rows_are_reported_without_state_changes
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_header_mode_mismatch_and_input_errors_exit_two_without_reports (test_recipe.RecipeCommandLineTests.test_header_mode_mismatch_and_input_errors_exit_two_without_reports) (csv_path=WindowsPath('C:/Users/PC/AppData/Local/Temp/tmpf5efms4r/events.csv'), recipe=None)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 443, in test_header_mode_mismatch_and_input_errors_exit_two_without_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

======================================================================
FAIL: test_header_mode_mismatch_and_input_errors_exit_two_without_reports (test_recipe.RecipeCommandLineTests.test_header_mode_mismatch_and_input_errors_exit_two_without_reports) (csv_path=WindowsPath('C:/Users/PC/Documents/ChatGPT/������ KDT AI ���� ��Ʈķ��/project/data/sample_events.csv'), recipe=WindowsPath('C:/Users/PC/Documents/ChatGPT/������ KDT AI ���� ��Ʈķ��/project/recipes/lamp_models.json'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 443, in test_header_mode_mismatch_and_input_errors_exit_two_without_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

======================================================================
FAIL: test_header_mode_mismatch_and_input_errors_exit_two_without_reports (test_recipe.RecipeCommandLineTests.test_header_mode_mismatch_and_input_errors_exit_two_without_reports) (csv_path=WindowsPath('C:/Users/PC/AppData/Local/Temp/tmpf5efms4r/missing.csv'), recipe=WindowsPath('C:/Users/PC/Documents/ChatGPT/������ KDT AI ���� ��Ʈķ��/project/recipes/lamp_models.json'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 443, in test_header_mode_mismatch_and_input_errors_exit_two_without_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

======================================================================
FAIL: test_sample_v2_matches_expected_products_and_rejection_counts (test_recipe.RecipeCommandLineTests.test_sample_v2_matches_expected_products_and_rejection_counts)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 491, in test_sample_v2_matches_expected_products_and_rejection_counts
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='empty_steps.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='duplicate_steps.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='duplicate_inspections.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='string_steps.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='unknown_key.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='unknown_after.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='multiple_errors.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='invalid_structure.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='invalid_json.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='array_root.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='empty_models.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='missing.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t21_same_csv_and_recipe_repeat_byte_identically_and_after_changes_decision (test_recipe.RecipeCommandLineTests.test_t21_same_csv_and_recipe_repeat_byte_identically_and_after_changes_decision)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 399, in test_t21_same_csv_and_recipe_repeat_byte_identically_and_after_changes_decision
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t58_bad_flag_or_reserved_step_exit_three (test_restart.ModeTests.test_t58_bad_flag_or_reserved_step_exit_three) (flag='true')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_restart.py", line 174, in test_t58_bad_flag_or_reserved_step_exit_three
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t58_bad_flag_or_reserved_step_exit_three (test_restart.ModeTests.test_t58_bad_flag_or_reserved_step_exit_three) (flag=1)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_restart.py", line 174, in test_t58_bad_flag_or_reserved_step_exit_three
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t58_bad_flag_or_reserved_step_exit_three (test_restart.ModeTests.test_t58_bad_flag_or_reserved_step_exit_three)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_restart.py", line 181, in test_t58_bad_flag_or_reserved_step_exit_three
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t31_invalid_fixtures_stop_before_events_and_reports (test_retest.RetestRecipeTests.test_t31_invalid_fixtures_stop_before_events_and_reports) (name='retest_zero.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 51, in test_t31_invalid_fixtures_stop_before_events_and_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t31_invalid_fixtures_stop_before_events_and_reports (test_retest.RetestRecipeTests.test_t31_invalid_fixtures_stop_before_events_and_reports) (name='retest_string.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 51, in test_t31_invalid_fixtures_stop_before_events_and_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t31_invalid_fixtures_stop_before_events_and_reports (test_retest.RetestRecipeTests.test_t31_invalid_fixtures_stop_before_events_and_reports) (name='retest_bool.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 51, in test_t31_invalid_fixtures_stop_before_events_and_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t31_invalid_fixtures_stop_before_events_and_reports (test_retest.RetestRecipeTests.test_t31_invalid_fixtures_stop_before_events_and_reports) (name='retest_partial.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 51, in test_t31_invalid_fixtures_stop_before_events_and_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t31_invalid_fixtures_stop_before_events_and_reports (test_retest.RetestRecipeTests.test_t31_invalid_fixtures_stop_before_events_and_reports) (name='retest_reserved.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 51, in test_t31_invalid_fixtures_stop_before_events_and_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t31_invalid_fixtures_stop_before_events_and_reports (test_retest.RetestRecipeTests.test_t31_invalid_fixtures_stop_before_events_and_reports) (name='retest_multiple_errors.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 51, in test_t31_invalid_fixtures_stop_before_events_and_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_sample_t23_to_t30_reports_match_fixed_input (test_retest.RetestReportTests.test_sample_t23_to_t30_reports_match_fixed_input)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 264, in test_sample_t23_to_t30_reports_match_fixed_input
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 112 != 0 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t32_cli_history_seven_rules_and_byte_reproducibility (test_retest.RetestReportTests.test_t32_cli_history_seven_rules_and_byte_reproducibility)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 314, in test_t32_cli_history_seven_rules_and_byte_reproducibility
    self.assertEqual(first.returncode, 0, first.stderr)
AssertionError: 112 != 0 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t10_identical_input_produces_identical_stdout_and_csv_bytes (test_rules.CommandLineTests.test_t10_identical_input_produces_identical_stdout_and_csv_bytes)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_rules.py", line 199, in test_t10_identical_input_produces_identical_stdout_and_csv_bytes
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta=[])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta=None)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'injected_errors': {}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': '24', 'injected_errors': {}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24.0, 'injected_errors': {}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': True, 'injected_errors': {}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': -1, 'injected_errors': {}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': []})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'SEQ_SKIP': '1'}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'SEQ_SKIP': 1.0}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'SEQ_SKIP': True}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'SEQ_SKIP': None}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'SEQ_SKIP': -1}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'SEQ_SKIP': 1, 'FOO': 5}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'FOO': 0}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'EQUIP_STOPPED': 1}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['ZZZ'], options=('--summary',))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['ZZZ'], options=('--summary', '--trace', 'a'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['A'], options=('--summary',))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['A'], options=('--summary', '--trace', 'a'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=[' a'], options=('--summary',))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=[' a'], options=('--summary', '--trace', 'a'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['a '], options=('--summary',))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['a '], options=('--summary', '--trace', 'a'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['a', 'ZZZ'], options=('--summary',))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['a', 'ZZZ'], options=('--summary', '--trace', 'a'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['ghost'], options=('--summary',))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['ghost'], options=('--summary', '--trace', 'a'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t45_cli_summary_is_separate_and_legacy_four_reports_are_unchanged (test_summary.SummaryTests.test_t45_cli_summary_is_separate_and_legacy_four_reports_are_unchanged)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 265, in test_t45_cli_summary_is_separate_and_legacy_four_reports_are_unchanged
    self.assertEqual(legacy.returncode, 0, legacy.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t48_summary_requires_equipment_without_creating_reports (test_summary.SummaryTests.test_t48_summary_requires_equipment_without_creating_reports) (options=('--summary',))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 286, in test_t48_summary_requires_equipment_without_creating_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

======================================================================
FAIL: test_t48_summary_requires_equipment_without_creating_reports (test_summary.SummaryTests.test_t48_summary_requires_equipment_without_creating_reports) (options=('--recipe', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\lamp_models_retest.json', '--summary'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 286, in test_t48_summary_requires_equipment_without_creating_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=None)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective='a')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective={})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=[1])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=[True])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=[[]])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=[''])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=['  '])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=['a', 'a'])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=[])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=['a', 'b'])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t47_case_colliding_product_ids_keep_distinct_reproducible_files (test_summary.TraceTests.test_t47_case_colliding_product_ids_keep_distinct_reproducible_files)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 394, in test_t47_case_colliding_product_ids_keep_distinct_reproducible_files
    self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t47_cli_repeated_trace_and_summary_use_separate_files (test_summary.TraceTests.test_t47_cli_repeated_trace_and_summary_use_separate_files)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 360, in test_t47_cli_repeated_trace_and_summary_use_separate_files
    self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t48_unknown_trace_and_non_equipment_modes_create_no_reports (test_summary.TraceTests.test_t48_unknown_trace_and_non_equipment_modes_create_no_reports) (options=('--trace', 'T34'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 380, in test_t48_unknown_trace_and_non_equipment_modes_create_no_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

======================================================================
FAIL: test_t48_unknown_trace_and_non_equipment_modes_create_no_reports (test_summary.TraceTests.test_t48_unknown_trace_and_non_equipment_modes_create_no_reports) (options=('--recipe', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\lamp_models_retest.json', '--trace', 'T34'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 380, in test_t48_unknown_trace_and_non_equipment_modes_create_no_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

======================================================================
FAIL: test_t48_unknown_trace_and_non_equipment_modes_create_no_reports (test_summary.TraceTests.test_t48_unknown_trace_and_non_equipment_modes_create_no_reports) (options=('--recipe', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\lamp_models_retest.json', '--equipment', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\equipment.json', '--summary', '--trace', 'T34', '--trace', 'NO_SUCH_PRODUCT'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 380, in test_t48_unknown_trace_and_non_equipment_modes_create_no_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

----------------------------------------------------------------------
Ran 205 tests in 62.821s

FAILED (failures=132)
T44 seed=42 products=500 generation_seconds=0.094929 judgment_analysis_seconds=0.050925
T44 seed=7 products=200 generation_seconds=0.036313 judgment_analysis_seconds=0.020535
T44 seed=42 all_rows_deepcopy_invariant_seconds=27.023401
T44 seed=7 all_rows_deepcopy_invariant_seconds=4.480637
```

</details>

그 뒤 기존 설치 Python 3.12.10에서, 자식 명령의 첫 인자가 `py`일 때만 같은 인터프리터로 연결하는 메모리 내 어댑터를 사용했다. 소스·테스트의 단정·파일 및 영구 환경은 변경하지 않았다.

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
.............................................................................................................................................................................................................
----------------------------------------------------------------------
Ran 205 tests in 80.499s

OK
T44 seed=42 products=500 generation_seconds=0.090598 judgment_analysis_seconds=0.053638
T44 seed=7 products=200 generation_seconds=0.035849 judgment_analysis_seconds=0.019650
T44 seed=42 all_rows_deepcopy_invariant_seconds=27.302812
T44 seed=7 all_rows_deepcopy_invariant_seconds=4.525672
```

종료 0. 전체 205개 통과.

### 이번 반례 및 보존 검증

반례 CLI는 `sys.executable`을 사용하므로 아래 실행에는 어댑터가 필요 없다.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff/reviews/probes/test_probe_014.py
```

```text
....FFF...P01: three overlapping invalid inputs preserve all state and request; raw-value retest PASS
P02: measured+lot restart validates lot before value; rejected restarts preserve state
P03: signed zero and 30-digit negative value compared exactly; unit mismatch rejected
P04: repeated seq; only accepted restart cuts its equipment; n=9/groups=1 for each
P05: exit=1; OverflowError=True
P06: exit=1; InvalidOperation=True
P07: saved process_cpk values=[1.33, 1.33]; distinct fixture paths=1
P08: 29-digit high-offset tiny variation retains nonzero sigma and fixed-point Cpk
P09: protected tracked files unchanged=96; legacy test files=9
P10: legacy reports byte-identical=32; CSV/meta=2
P11 completed: eval_dev
P11 completed: eval_holdout
P11 completed: eval_baseline
P11 completed: lot
P11 completed: lot_clustered
..
======================================================================
FAIL: test_p05_integer_shift_overflow_is_controlled_configuration_error (handoff.reviews.probes.test_probe_014.AdversarialTests.test_p05_integer_shift_overflow_is_controlled_configuration_error)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_014.py", line 166, in test_p05_integer_shift_overflow_is_controlled_configuration_error
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 1 != 2 : Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 458, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 449, in main
    meta = generate(args.seed, args.products, args.out, args.config)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 418, in generate
    generator, normal, rows, counts = build_rows(seed, products, config, recipe.models, equipment)
                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 407, in build_rows
    generator = Generator(seed, config, models, equipment)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 57, in __init__
    self.measured = check_measured_config(config, models, equipment_book)
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 360, in check_measured_config
    if not math.isfinite(sigma) or not math.isfinite((lsl + usl) / 2 + shift * sigma):
                                                                       ~~~~~~^~~~~~~
OverflowError: int too large to convert to float


======================================================================
FAIL: test_p06_huge_finite_draw_is_controlled_digit_limit_error (handoff.reviews.probes.test_probe_014.AdversarialTests.test_p06_huge_finite_draw_is_controlled_digit_limit_error)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_014.py", line 176, in test_p06_huge_finite_draw_is_controlled_digit_limit_error
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 1 != 2 : Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 458, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 449, in main
    meta = generate(args.seed, args.products, args.out, args.config)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 418, in generate
    generator, normal, rows, counts = build_rows(seed, products, config, recipe.models, equipment)
                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 408, in build_rows
    normal = generator.normal_events(products)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 199, in normal_events
    step = next(flow)
           ^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 142, in product
    value = self.measure(item, equipment, defective)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 86, in measure
    return confirm_value(self.rng.gauss(center + shift * sigma, sigma))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\generate.py", line 43, in confirm_value
    rounded = Decimal(repr(number)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
decimal.InvalidOperation: [<class 'decimal.InvalidOperation'>]


======================================================================
FAIL: test_p07_t108_settings_must_not_alias_one_fixture (handoff.reviews.probes.test_probe_014.AdversarialTests.test_p07_t108_settings_must_not_alias_one_fixture)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_014.py", line 190, in test_p07_t108_settings_must_not_alias_one_fixture
    self.assertEqual(values[0]['process_cpk'], 0,
AssertionError: 1.33 != 0 : The first T108 case was overwritten before execution

----------------------------------------------------------------------
Ran 12 tests in 169.372s

FAILED (failures=3)
P11: legacy evaluation reports byte-identical=10
P12: measured reports byte-identical=15; CSV/meta=2
```

종료 1. 12개 중 통과 9개, H1·H2·M1을 재현하는 실패 3개를 그대로 남겼다.

반례 완료 후 P03·P08 콘솔 메시지의 자릿수 설명만 중립적인 표현으로 바로잡았다. 입력·기대·단정은 바꾸지 않았고 해당 두 반례만 다시 실행했다.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff.reviews.probes.test_probe_014.AdversarialTests.test_p03_negative_one_sided_precision_and_equivalent_specs handoff.reviews.probes.test_probe_014.AdversarialTests.test_p08_capability_small_variation_retains_decimal_precision
```

```text
..
----------------------------------------------------------------------
Ran 2 tests in 0.007s

OK
P03: signed zero and tiny negative value compared exactly; unit mismatch rejected
P08: high-offset tiny variation retains nonzero sigma and fixed-point Cpk
```

종료 0. H1·H2·M1은 미해결이다.

VERDICT: FIX
