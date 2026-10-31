검수 모델: gpt-6.1-sol

# 리뷰 027 — 리뷰 026 재검토 및 현행 16단계 검수

검수일: 2026-11-01. 대상: `git diff 580214e0e33c98493a991c743c07ea87230e51a5..HEAD`, HEAD `4914c80`. 기준: `handoff/tasks.md` 맨 위 현행 16단계 명세·T267–T281과 완료 단계들의 보존 조건. 지정 diff에는 R26-M1 수정(`37192df`)과 신규 16단계 구현(`4914c80`)이 함께 있다.

**판정 FIX. 이전 R26-M1은 해결됐다. 신규 높음 1건·중간 3건이 남았다.** 기본 설정의 정상 결과는 제출본과 같지만, 유효한 설정 경로 조합으로 입력 보고서를 덮어쓸 수 있다. 낮음 지적은 없다.

AGENTS, setup-notes, tasks, 구현 로그의 관련 변경·의견, decisions, 리뷰 026, 최근 log와 지정 diff를 읽었다. `practical-work-operation`은 작업 조율·보존 확인에만 적용했다. 요청대로 플러그인 리뷰 스킬·보조 에이전트는 사용하지 않았다. 해결 기록 경로 `.compound-engineering/config.yaml`, `docs/solutions/`는 없었다. 검수자가 작성한 저장소 파일은 이 리뷰와 `handoff/reviews/probes/test_probe_027.py`뿐이다. 시작부터 있던 미추적 `handoff/loop-logs/027-codex.txt`는 건드리지 않았다. 제품 코드·원본 테스트·보고서 수정, 설치, commit·push·삭제는 하지 않았다.

## 이전 높음·중간 항목별 판정

리뷰 026의 미해결 항목은 중간 1건이고 높음은 없었다.

| 이전 항목 | 판정 | 반례 이후 확인한 근거 |
| --- | --- | --- |
| R26-M1 / 격리 목록 일부 누락 수용 | 해결 | P01에서 cusum-3의 last_50 전체 및 last_20 제품 195 하나를 각각 제거하면 모두 종료2·기존 HTML 불변이다. P02는 중복 행 및 행 수를 유지한 잘못된 제품 번호도 거절한다. P03은 시작·크기 불일치를 거절하고, 원상 복구 뒤에는 해시 시드가 달라도 제출 HTML과 바이트까지 같다. `src/dashboard.py:521`의 범위 생성과 `:556`의 목록 대조가 실제로 동작한다. |

`handoff/gpt-log.md`의 “story_scope의 시작과 크기로 범위별 제품 번호를 만들고 suspects와 전부 대조하며 정상 화면은 바뀌지 않는다”는 설명에 동의한다. 누락·중복·동일 크기의 잘못된 제품·거절 뒤 복구를 확인한 뒤 내린 판단이다. 이번 항목에 대한 별도 반박은 로그에 없었다. “수정 자체의 판정은 없다”던 상태에 이번 해결 판정을 추가한다.

026이 이미 해결로 판정한 025의 중간 3건은 이번에 이전 반례 파일 전체를 재실행하지 않았다. 변경된 격리 검증은 이번 반례로 확인했고, 관련 없는 기존 검증은 앞선 리뷰의 범위를 유지한다.

## 미해결 지적

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| R27-H1 | 높음 | `src/sizing.py:359`, `src/sizing.py:360`, `src/sizing.py:361` | 출력 경로가 입력 보고서와 같은지 확인하지 않고 덮어써 입력 데이터를 잃는다. | P06: 기존 guard 보고서를 임시 `reports/sizing_lamp_spec.csv`에 복사하고 `guard_report`가 이를 가리키게 하면 종료0으로 파일을 sizing spec으로 바꾼다. 같은 방식으로 `line_report=../reports/sizing_lamp_curve.csv`를 주면 입력 compare가 curve로 바뀐다. 두 입력 모두 그 밖의 조건은 정상이며, 설정의 보고서 파일명에는 제한이 없다. 현행 보존 조건과 T278의 기존 보고서 불변을 위반하고 다음 실행에 필요한 입력도 잃는다. | 쓰기 전에 모든 출력과 설정·입력 파일의 해석한 경로를 대조하고 충돌하면 종료2로 거절한다. 실제 같은 파일을 가리키는 별칭도 고려한다. 거절 시 기존 파일 전부가 보존되는 회귀 검증을 추가한다. |
| R27-M1 | 중간 | `src/sizing.py:186`, `src/sizing.py:189` | 오불합격·오합격 건수가 음수이거나 각 분모보다 커도 유효한 관측 비율로 사용한다. | P05: `false_rejects=-1`, `true_good+1`, `false_accepts=-1`, `true_defects+1`이 모두 종료0이다. 오합격 -0.0004·1.0004를 보고하며 산술 비교 이내를 표시하고, 음수 오불합격은 표시가 0.0000으로 반올림되어 문제도 숨는다. 건수 기반 비율의 정의상 불가능한 입력이다. T277의 빈값·0분모 외 입력에서 잘못되거나 설명할 수 없는 결과이므로 중간이다. 오합격으로 게이지를 골라야 한다는 지적은 아니다. | 정수로 읽은 건수에 `0 <= false_rejects <= true_good`, `0 <= false_accepts <= true_defects`를 적용하고 위반을 입력 오류로 거절한다. |
| R27-M2 | 중간 | `src/sizing.py:76`, `src/sizing.py:376` | 깨진 JSON 설정이 설정 오류3이 아닌 입력·재현 오류2로 분류된다. | P04: 잘린 객체, 끝 쉼표가 있는 객체, 빈 설정 파일이 전부 종료2다. `JSONDecodeError`가 `ValueError` 분기로 들어가기 때문이다. 현행 CLI의 “설정 오류3, 입력·재현 오류2” 설명과 실제 동작이 다르다. 제품 판정이나 파일 내용은 바뀌지 않으므로 오류 분류 불일치인 중간으로 분류한다. | 설정 JSON 구문 오류를 `SizingError`로 변환하거나 별도 처리해 종료3으로 일관되게 반환한다. 기존 결과 파일 불변도 함께 검사한다. |
| R27-M3 | 중간 | `tests/test_sizing.py:289` | T281 테스트가 “모든 test 증분과 수리 경계가 실제 함께 적용됨”을 검증하지 않는다. | P10: 원본 파일을 고치지 않고 이 테스트의 assertion 메서드에 joint 개발 UPH=0, 홀드아웃=999999, 결과=동시 충족이라는 조작 행을 넣었다. 테스트는 그대로 통과했다. 현재 검사는 UPH가 각 경계의 최솟값 이하인지와 결과 문자열의 종류만 보며, 입력 조건·홀드아웃·결과의 정합성을 확인하지 않는다. 명세는 UPH 단조성도 보장하지 않으므로 이 부등식은 T281의 대용이 아니다. | joint에 들어간 설비별 시간과 수리를 경계 행에서 독립적으로 구성해 직접 모의한 값과 대조하고, 정확한 개발·홀드아웃 UPH에 따른 결과도 확인한다. 각 조건을 누락하거나 결과를 조작하면 실패하는 검증을 둔다. |

R27-M3는 **요구를 검증하지 못하는 테스트**에 대한 지적이다. 현재 제품의 joint 구현이 조건을 빠뜨렸다고 주장하지 않는다. 코드상 설비별 증분과 수리 적용을 확인했고 P07의 작은 경로 독립 계산도 일치했다.

## 이번 diff에 집중한 반례

반례 및 모든 파일 출력은 unittest의 `TemporaryDirectory` 안에서만 수행했다. 기존 반례 파일 전체는 실행하지 않았다. P01–P09 실행 뒤 새로 확인한 테스트 검증 공백을 P10으로 추가해 그것만 단독 실행했다. 최종 누적 결과는 **반례 메서드 10개 중 6개 통과·4개 실패**, 실패 세부 사례는 10건이며 위 4개 지적에 해당한다.

| 반례 | 입력 | 예상(명세 근거) | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | cusum-3 last_50 전체 누락 / last_20 제품195 누락 | R26-M1·14단계 범위 안 제품마다 한 행·15단계 부분 화면 거절에 따라2, 이전 HTML 불변 | 각각2, 이전 HTML 불변 | 통과, R26-M1 해결 |
| P02 | 격리 행 중복 / last_20 첫 제품188을187로 교체해 행 수 유지 | 고유 제품 목록이 범위와 달라 거절 | 각각2, 이전 HTML 불변 | 통과 |
| P03 | cusum last_20 시작189·크기20 / 정상 복원 후 해시 시드0·29 | 불일치는 거절, 정상 복원 시 T245의 동일 결과 | 2 뒤0·0, 정상 두 HTML이 제출본과 바이트 동일 | 통과 |
| P04 | `{"line":` / 끝 쉼표 JSON / 빈 설정 파일 | CLI의 설정 오류3, 기존 결과 보존 | 전부2, 기존 결과 보존 | 실패 3사례, R27-M2 |
| P05 | 오불합격 -1·147416(분모147415), 오합격 -1·2586(분모2585) | 건수 비율 정의상 불가능하므로 입력 오류2 | 전부0, 음수·1초과 비율로 보고서 생성 | 실패 4사례, R27-M1 |
| P06 | 정상 guard 입력을 spec 출력 경로에 배치 / 정상 compare 입력을 curve 출력 경로에 배치 | 보존 조건·T278에 따라 기존 입력 바이트 유지 | 전부0, 기존 입력을 신규 보고서로 덮어씀 | 실패 2사례, R27-H1 |
| P07 | 1ms test의 서로 다른 배수 세 개가 같은 증분0; 0시간 skip·재검사2회·정지 경로에 X+1ms·Y+200ms·수리499ms 동시 적용 | T270·T280·T281의 정확한 ms·같은 시간 같은 UPH·원본 보존 | 증분0·0·0과 UPH 동일, 직접 구성한 joint 모의와 일치, 원본 불변 | 통과 |
| P08 | 제출 기본 입력 전체를 임시 복사해 해시 시드19로 sizing 실행 | T278의 동일 산출물·기존 보고서 불변 | 신규3파일 모두 제출본과 바이트 동일, 기존 보고서 불변 | 통과 |
| P09 | 기준/HEAD Git blob 비교 및 이전 7종 샘플 CLI의 빈 임시 reports 재생성 | 기존 테스트 본문·보고서 보존, 정상 이전 동작 유지 | 기존 보고서92개 blob 동일, 샘플32개 재생성 원시 바이트 동일, 원래 테스트 본문 삭제·변경 없음 | 보존 통과; 전체 테스트 통과는 별도 미검증 |
| P10 | T281 assertion에 joint 개발0·홀드아웃999999·동시 충족 조작 행 주입 | 요구를 실제 검증하는 테스트라면 실패 | 원본 T281 assertion이 통과 | 실패, R27-M3 |

## 보존 및 동의·미검증 범위

- 기준 커밋에 이미 있던 보고서 **92개는 전부 Git blob 동일**이다. 기존 제품 코드·설정·데이터 중 바뀐 것은 R26-M1 수정인 `src/dashboard.py`뿐이다. 기존 `tests/test_dashboard.py`에는 회귀 테스트 11줄 추가만 있고 원래 본문의 삭제·변경은 없다. 다른 기존 테스트 파일은 Git blob 동일이다. 파일 전체가 하나도 변경되지 않았다고 표현하지 않는다.
- 16단계 구현 커밋만 직전 `37192df`와 대조하면 `src/tests/recipes/reports` 변경은 신규 파일뿐이다. R26-M1 수정을 16단계의 무관한 기존 코드 변경으로 잘못 집계하지 않았다. dashboard 탭·제출 HTML은 불변이며 sizing 결과를 넣지 않았다.
- v1·모델 레시피·재검사·설비·재가동·로트·측정 샘플 7종을 각각 실제 CLI로 실행해, 빈 임시 reports에 새로 생긴 보고서 **32개**가 제출본과 원시 바이트 동일함을 확인했다. 나머지 기존 보고서까지 모두 이번에 재생성했다고 주장하지 않는다.
- P08은 기본 sizing CLI 전체를 실행한 결과다. 신규 보고서3개가 제출본과 같고, 이전 보고서는 불변이다. 구현 로그의 기본 경계 LEAK22.66초·LIGHT11.11초·FINAL16초·수리660초, 동시 개발179.6563 미충족 설명에 동의한다. 격자 뒤 재충족을 경계로 쓰지 않는 코드와 정확한 Fraction 비교도 확인했다. 경계를 실물 설비 허용값으로 확대하지 않았다.
- 보호 대상 `src/tests/recipes/reports/data`의 파일 목록과 SHA-256 **199개**는 반례 실행 전후 불변이다. 입력 덮어쓰기 재현은 임시 입력에서만 했으며 실제 저장소 자료는 보존했다.
- **전체 기존 테스트 통과는 미검증**이다. 요청한 명령을 직접 단 한 번 실행했으나 `py` 런처가 테스트 시작 전에 실패했다. 구현자의 `v2-16-tests.txt`에 578 tests OK가 있지만 검수자의 직접 통과 결과로 대체하지 않는다. 다른 인터프리터로 전체 테스트를 우회 재실행하지 않았다.
- 브라우저의 화면 폭·테마·JavaScript 끔 시각 검증은 이번 diff의 대상이 아니며 이번 직접 검증은 **미검증**이다. 이전 전체 반례도 재실행하지 않았다. 새 명세 이견은 없다.

## 직접 실행 명령과 결과 원문

PowerShell에서 `PYTHONDONTWRITEBYTECODE=1`, `PYTHONIOENCODING=utf-8` 및 콘솔 UTF-8을 설정했다. 반례의 하위 CLI도 바이트코드 생성을 막고 임시 폴더에서 실행했다.

### 전체 테스트 — 단 한 번 실행

```powershell
py -m unittest discover -s tests
```

종료1, 출력 원문:

```text
No installed Python found!
```

### 요청된 반례 명령

```powershell
py -m unittest handoff/reviews/probes/test_probe_027.py
```

종료1, 출력 원문:

```text
No installed Python found!
```

### 설치된 Python 3.12로 이번 반례 P01–P09 실행

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff/reviews/probes/test_probe_027.py
```

종료1, 출력 원문:

```text
dashboard exit=2 preserved=True stderr=오류: 사건 cusum-3의 격리 범위나 PFMEA 연결이 모자람
dashboard exit=2 preserved=True stderr=오류: 사건 cusum-3의 격리 범위나 PFMEA 연결이 모자람
P01 previous R26-M1 omissions refused
.dashboard exit=2 preserved=True stderr=오류: 사건 cusum-3의 격리 범위나 PFMEA 연결이 모자람
dashboard exit=2 preserved=True stderr=오류: 사건 cusum-3의 격리 범위나 PFMEA 연결이 모자람
P02 duplicate/wrong boundary product refused
.dashboard exit=2 preserved=True stderr=오류: cusum last_20의 범위 크기가 정지 제품과 맞지 않음
P03 rejected inconsistent start; restored dashboard byte-identical twice
.P04 malformed='{"line":' exit=2 stderr=오류: Expecting value: line 1 column 9 (char 8)
FP04 malformed='{"line": "line_lamp.json",}' exit=2 stderr=오류: Expecting property name enclosed in double quotes: line 1 column 27 (char 26)
FP04 malformed='' exit=2 stderr=오류: Expecting value: line 1 column 1 (char 0)
FP05 false_rejects=-1 exit=0 reject=0.0000 accept=0.0124 verdict=가정상 산술 비교 이내
FP05 false_rejects=147416 exit=0 reject=1.0000 accept=0.0124 verdict=초과
FP05 false_accepts=-1 exit=0 reject=0.0002 accept=-0.0004 verdict=가정상 산술 비교 이내
FP05 false_accepts=2586 exit=0 reject=0.0002 accept=1.0004 verdict=가정상 산술 비교 이내
FP06 input/output collision=guard_report exit=0 preserved=False
FP06 input/output collision=line_report exit=0 preserved=False
FP07 equal-ms grids, skip, retest and joint integer-ms oracle match
.P08 full default three sizing reports byte-identical; prior reports unchanged
.P09 prior report blobs=92 unchanged; legacy reports regenerated=32; old test bodies intact
.PRESERVATION protected files=199 unchanged

======================================================================
FAIL: test_p04_malformed_settings_exit_three (handoff.reviews.probes.test_probe_027.Probe027.test_p04_malformed_settings_exit_three) (text='{"line":')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_027.py", line 149, in test_p04_malformed_settings_exit_three
    self.assertEqual(result.returncode, 3, "Malformed configuration must use configuration exit code")
AssertionError: 2 != 3 : Malformed configuration must use configuration exit code

======================================================================
FAIL: test_p04_malformed_settings_exit_three (handoff.reviews.probes.test_probe_027.Probe027.test_p04_malformed_settings_exit_three) (text='{"line": "line_lamp.json",}')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_027.py", line 149, in test_p04_malformed_settings_exit_three
    self.assertEqual(result.returncode, 3, "Malformed configuration must use configuration exit code")
AssertionError: 2 != 3 : Malformed configuration must use configuration exit code

======================================================================
FAIL: test_p04_malformed_settings_exit_three (handoff.reviews.probes.test_probe_027.Probe027.test_p04_malformed_settings_exit_three) (text='')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_027.py", line 149, in test_p04_malformed_settings_exit_three
    self.assertEqual(result.returncode, 3, "Malformed configuration must use configuration exit code")
AssertionError: 2 != 3 : Malformed configuration must use configuration exit code

======================================================================
FAIL: test_p05_impossible_gauge_counts (handoff.reviews.probes.test_probe_027.Probe027.test_p05_impossible_gauge_counts) (key='false_rejects', value='-1')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_027.py", line 169, in test_p05_impossible_gauge_counts
    self.assertEqual(result.returncode, 2, "Impossible observation counts must be refused")
AssertionError: 0 != 2 : Impossible observation counts must be refused

======================================================================
FAIL: test_p05_impossible_gauge_counts (handoff.reviews.probes.test_probe_027.Probe027.test_p05_impossible_gauge_counts) (key='false_rejects', value='147416')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_027.py", line 169, in test_p05_impossible_gauge_counts
    self.assertEqual(result.returncode, 2, "Impossible observation counts must be refused")
AssertionError: 0 != 2 : Impossible observation counts must be refused

======================================================================
FAIL: test_p05_impossible_gauge_counts (handoff.reviews.probes.test_probe_027.Probe027.test_p05_impossible_gauge_counts) (key='false_accepts', value='-1')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_027.py", line 169, in test_p05_impossible_gauge_counts
    self.assertEqual(result.returncode, 2, "Impossible observation counts must be refused")
AssertionError: 0 != 2 : Impossible observation counts must be refused

======================================================================
FAIL: test_p05_impossible_gauge_counts (handoff.reviews.probes.test_probe_027.Probe027.test_p05_impossible_gauge_counts) (key='false_accepts', value='2586')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_027.py", line 169, in test_p05_impossible_gauge_counts
    self.assertEqual(result.returncode, 2, "Impossible observation counts must be refused")
AssertionError: 0 != 2 : Impossible observation counts must be refused

======================================================================
FAIL: test_p06_output_cannot_overwrite_input_report (handoff.reviews.probes.test_probe_027.Probe027.test_p06_output_cannot_overwrite_input_report) (key='guard_report')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_027.py", line 185, in test_p06_output_cannot_overwrite_input_report
    self.assertEqual(target.read_bytes(), before, "Existing input report was overwritten")
AssertionError: b'\xef\xbb\xbfsection,machine,combo,gauge,count,current_seconds[5155 chars]\r\n' != b'\xef\xbb\xbfsection,gauge,operator,multiplier,lower,upper,sta[3659 chars]\r\n' : Existing input report was overwritten

======================================================================
FAIL: test_p06_output_cannot_overwrite_input_report (handoff.reviews.probes.test_probe_027.Probe027.test_p06_output_cannot_overwrite_input_report) (key='line_report')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_027.py", line 185, in test_p06_output_cannot_overwrite_input_report
    self.assertEqual(target.read_bytes(), before, "Existing input report was overwritten")
AssertionError: b'\xef\xbb\xbfkind,machine,multiplier,value_seconds,see[1562 chars]\r\n' != b'\xef\xbb\xbfsection,combo,leak,light,final,area_mm2,s[9400 chars]\r\n' : Existing input report was overwritten

----------------------------------------------------------------------
Ran 9 tests in 97.468s

FAILED (failures=9)
```

### 신규 P10만 추가 확인

아래 실행은 기존 T281 메서드 하나에 조작 자료를 주는 이번 반례다. 원래 테스트 suite나 이전 반례 파일을 실행한 것이 아니다.

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff.reviews.probes.test_probe_027.Probe027.test_p10_joint_requirement_test_rejects_fabricated_result
```

종료1, 출력 원문:

```text
P10 T281 assertion accepts fabricated good_uph=0, holdout=999999, verdict=동시 충족
FPRESERVATION protected files=199 unchanged

======================================================================
FAIL: test_p10_joint_requirement_test_rejects_fabricated_result (handoff.reviews.probes.test_probe_027.Probe027.test_p10_joint_requirement_test_rejects_fabricated_result)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_027.py", line 271, in test_p10_joint_requirement_test_rejects_fabricated_result
    self.fail("T281 assertion must verify actual combined conditions/results rather than an inequality alone")
AssertionError: T281 assertion must verify actual combined conditions/results rather than an inequality alone

----------------------------------------------------------------------
Ran 1 test in 0.886s

FAILED (failures=1)
```

VERDICT: FIX
