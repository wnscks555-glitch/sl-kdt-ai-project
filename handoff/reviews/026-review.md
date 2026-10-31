검수 모델: gpt-6.1-sol

# 리뷰 026 — 리뷰 025 수정 재검토

검수일: 2026-11-01. 대상: `git diff 9fe96d4f8774c24c4bcc8b503b35f0695343b11f..HEAD`, 현재 HEAD `e69a742`. 기준: `handoff/tasks.md` 맨 위 현행 15단계 명세·T237–T248·T263–T266과 이전 단계 보존 조건.

**판정 FIX. 이전 중간 3건의 기존 재현은 해결됐다. 추가 반례에서 중간 1건(R26-M1)을 확인했다. 높음·낮음 신규 지적은 없다.**

전체 테스트는 요청한 명령으로 한 번 시도했지만 `py` 런처가 테스트 시작 전에 실패했다. **기존 테스트 무수정은 확인했으나, 전체 테스트 통과는 미검증이다.** 반례는 요청한 `py` 명령 실패 뒤 설치된 Python 3.12 실행 파일로 검증했다. 환경 실패를 제품 결함으로 세지 않았다.

AGENTS, setup-notes, tasks, gpt-log, decisions, 리뷰 025, 최근 log와 지정 diff를 읽었다. practical-work-operation은 조율·보존 확인에만 적용했고 플러그인 리뷰 스킬·보조 에이전트는 사용하지 않았다. 검수자가 작성한 저장소 파일은 이 리뷰와 `handoff/reviews/probes/test_probe_026.py`뿐이다. 시작 때부터 있던 미추적 `handoff/loop-logs/026-codex.txt`는 건드리지 않았다. 제품 코드·원본 테스트·보고서 수정, 설치, commit·push·삭제는 하지 않았다.

## 이전 높음·중간 항목별 판정

리뷰 025의 미해결 항목은 중간 3건이며 높음은 없었다.

| 기존 항목 | 판정 | 반례 이후 확인한 근거 |
| --- | --- | --- |
| R25-M1 / 계산 불가 MSA 표시 실패 | 해결 | P01에서 유효한 process_cpk=1e6, products=12, 개발 시드7·홀드아웃1007로 실제 MSA CLI 실행. 세 게이지의 pct_grr가 빈칸이며 대시보드는 종료0, 판정 불가와 안내를 표시한다. P02는 빈칸·숫자0·정상값의 혼합에서 빈칸 막대만 생략하고 표와 0을 보존한다. `src/dashboard.py:362`의 필터와 빈값 막대 생략은 설명대로 동작한다. |
| R25-M2 / 무경보·임계값 없음 거절 | 해결 | P03은 작은 이동량·엄격한 기준의 실제 anomaly → spc → dashboard CLI 연결이다. 임계값·alarm이 빈칸인 재생과 미선택 방법을 종료0으로 표시한다. P04는 replay_rows가 만든 실제 missed 자료를 수용하고, 같은 무경보 자료에서 필수 bias를 제거하면 종료2·이전 HTML 보존, 복구하면 성공한다. 경보 공집합 허용이 모델 필수값 검증을 없애지 않았다. |
| R25-M3 / 필수 PFMEA 누락 수용 및 모든 사건 연결의 명세 이견 | 해결(기존 지적 범위) | P05에서 cusum-3 연결 전부 또는 그중 PF-06 하나만 제거하면 종료2·이전 HTML 보존, 복원 후 종료0. P08은 오경보 사건에 임의 PFMEA를 붙이면 거절함을 확인했다. 전체 11개 정지 중 고장 뒤 첫 정지 2개만 실제 격리·PFMEA 연결을 가진다는 구현자의 설명은 `src/incident.py:596`의 suspect_rows와 `:622`의 pfmea_text, 14단계 a 정의에 근거가 있어 수용한다. 나머지 9개는 해당 없음과 고장 전/수리 뒤 이유를 표시한다. 부분 격리 목록의 완전성은 별도로 발견한 R26-M1이다. |

`gpt-log.md`의 M1·M2 수정 설명과 M3의 PFMEA 누락 거절 설명에 동의한다. M3의 명세 이견은 고장 없는 정지에 격리 수치를 지어내지 않고 이유를 보이는 해석으로 해결 처리한다. T266 기대표는 수정하지 않았다. decisions에는 “Claude 처리(사용자 승인 전)”으로 남아 있으므로 사용자 최종 승인까지 있었다고 보고하지 않는다.

025가 해결로 판정한 020–024 및 중단 후 선반영 항목은 이번 검수에서 이전 반례 파일을 재실행하지 않았다. 이번 diff에서 앞 단계 코드·설정·보고서가 바뀌지 않았다는 근거와 025의 기존 검증 범위를 유지하며, 이번에 모두 새로 동적 검증했다고 확대하지 않는다.

## 미해결 지적

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| R26-M1 | 중간 | `src/dashboard.py:532`, `src/dashboard.py:542`, `src/dashboard.py:544` | 고장 뒤 첫 정지의 격리 목록이 일부 빠져도, 다른 격리 행이 하나라도 남아 있으면 완전한 입력으로 처리한다. 같은 HTML의 사건 연결과 범위 요약이 서로 모순된다. | P06: cusum-3의 last_50 제품 50행만 제거. compare의 story_scope에는 scope_size=50이 그대로지만 CLI는 종료0이며 이전 HTML을 교체한다. 사건 연결은 last_20 20, change_point 7만 보여 last_50이 사라진다. P07: last_20의 제품 한 행만 제거하면 사건 연결은 last_20 19, 범위 요약은 20인 상태로 종료0·이전 HTML 교체. 코드가 실제 남은 행 수만 세고 `not scope`만 검사해 범위별 누락을 놓친다. 현행 명세의 부분 화면 거절·T266 사건별 격리 연결, 14단계의 “범위 안 제품마다 한 행” 계약과 맞지 않는다. | 고장 뒤 첫 정지별로 compare의 해당 story_scope에서 적용되는 범위·scope_size와 suspects의 범위별 고유 제품 목록을 대조한다. 범위 전체 누락·일부 제품 누락·중복을 검출해 종료2로 거절하고 기존 HTML을 보존한다. 적용 대상이 아닌 change_point의 빈칸은 실제 적용 범위와 구분한다. |

새로 검증한 것은 불완전한 입력의 수용과 화면 내부 불일치다. 정상 입력의 판정 변경이나 데이터 손실로 확대하지 않고 **중간**으로 분류한다. 검수용 임시 HTML의 교체는 확인했으나 원본 저장소 보고서는 바꾸지 않았다. 이 누락 수용이 이번 수정에서 처음 생겼다고 단정하지 않는다. 새 검증 분기가 부분 누락까지 막지는 못한다는 추가 발견이다.

## 이번 diff에 집중한 반례

모든 변경·출력은 각 unittest 안의 TemporaryDirectory에서 수행했다. 예상은 기대표를 새로 고친 값이 아니라 아래 기존 계약에 근거했다.

| 반례 | 입력 | 예상(명세 근거) | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | 실제 MSA, process_cpk=1e6·products12·시드7/1007 | T192·T250의 계산 불가 결과도 표시 | 빈 pct_grr 3행, upstream0·dashboard0, 판정 불가 안내 | 통과, M1 해결 |
| P02 | 게이지별 pct_grr 빈칸·0.0000·정상값 혼합 | 계산 불가와 숫자0을 구분하고 표 보존 | 빈 막대만 생략, 숫자0과 모든 행 표시 | 통과 |
| P03 | shifts0.01/0.02/0.03·false_limit1e-9 등으로 실제 anomaly와 spc 실행 | T189 임계값 없음 허용, 존재하는 지표 표시 | upstream 모두0·dashboard0, 상태와 빈 지표 설명 | 통과, M2 해결 |
| P04 | replay_rows의 최대 점수+1 임계값으로 missed 생성 → 필수 bias 삭제 → 복원 | T189 무경보 수용, 모델 필수값 누락 거절, 복원 후 정상 | 0 → 2·이전 HTML 불변 → 0 | 통과 |
| P05 | cusum-3 PFMEA 전체/한 항목 제거, 별도로 격리 행 전체 제거, 복원 | T266 고장 뒤 첫 정지의 필수 연결 누락 거절 | 모두2·이전 HTML 불변, PFMEA 복원 후0 | 통과, 기존 M3 누락 재현 해결 |
| P06 | cusum-3 last_50 제품 50행만 제거, 다른 범위와 compare 보존 | 범위별 필수 격리 연결 누락이므로2·기존 HTML 보존 | 0·HTML 교체, 연결 표에서 last_50만 사라짐 | 실패, R26-M1 |
| P07 | cusum-3 last_20 제품 한 행만 제거 | 14단계 범위별 제품 계약과 compare의 20을 충족 못하므로 거절 | 0·HTML 교체, 연결19·요약20 | 실패, R26-M1의 같은 원인 |
| P08 | PFMEA 고장 모드 칸에 파이프 문자, 이어 고장 전 cusum-1 임의 연결 | 유효 문자열 수용, a 이외 연결은 거절, 해당 없음 이유 표시 | 파이프 처리 성공, 임의 연결2·이전 HTML 보존, 전/후 이유 표시 | 통과 |
| P09 | 실제 line CLI의 선택 없음과 균형 해 없음, 뒤 경우에 이전 실행의 위험 SVG 잔존 | 9단계의 유효한 빈 결과 표시, 현재 결과와 무관한 SVG는 싣지 않음 | upstream0·dashboard0, 선택 없음 표시, 잔존 SVG 제외 | 통과, 추가 수정 동의 |
| P10 | 기준 커밋의 기존 파일 비교와 7종 sample CLI 임시 재생성 | 기존 테스트·보고서 보존, 재생성 보고서 바이트 동일 | 기존 보고서91·이전 테스트45개 Git blob 동일, 샘플 보고서32개 원시 바이트 동일 | 보존 확인; 전체 테스트 실행 통과는 별도 미검증 |
| P11 | 기본 입력으로 dashboard 2회 생성, 전후 입력 비교 | T245·T247·T248 결정성·크기·입력 보존 | 271177바이트, 두 번과 제출 HTML 동일, 입력 불변 | 통과 |

P10은 첫 실행 때 체크아웃 CSV의 CRLF와 Git blob의 LF를 직접 비교하는 **반례 도구의 오류**로 실패했다. 이를 기준/현재 Git blob끼리 비교하고 worktree 변경 여부를 별도로 확인하도록 고쳤다. 이어 P10만 관련 실패 반례와 재실행해 통과했다. 제품 결함으로 집계하지 않았다. 최종 유효 결과는 P01–P11의 누적 판정으로 **9건 통과·2건 실패**, 두 제품 실패는 동일 중간 항목 하나다.

## 보존과 검증 범위

- 지정 diff에서 src·tests·recipes·data·reports 중 바뀐 것은 현재 단계의 `src/dashboard.py`, `tests/test_dashboard.py`, `reports/dashboard.html`뿐이다. 이전 단계 코드·설정·데이터는 불변이고 이전 단계 테스트45개·보고서91개는 기준과 Git blob 바이트까지 같다. 현행 대시보드 테스트에는 삭제 없이 101줄이 추가됐다.
- 임시 폴더에서 v1·모델 레시피·재검사·설비·재가동·로트·측정 샘플 CLI 7종을 실행해 보고서32개가 제출본과 **원시 바이트까지 동일**함을 확인했다. 기존91개 전부를 이번에 재생성했다고 주장하지 않는다.
- 검수 전후 보호 파일 src/tests/recipes/reports/data **193개**의 SHA-256과 파일 목록이 불변이다. 대시보드가 읽은 임시 입력도 반복 실행 전후 불변이다.
- 025에서 검증한 12–14단계의 기본 전체 재현은 이번 diff에서 생산 코드·입력이 그대로여서 재사용했다. 이번에는 오류가 났던 MSA·anomaly·SPC와 추가 line 조건을 직접 실행했다.
- 전체 테스트의 실제 통과, 브라우저의 375/1280·테마·JavaScript 끔 시각 검증은 **미검증**이다. 구현자의 `handoff/run-logs/v2-freeze-tests.txt`에는 549 tests OK가 있지만 이번 직접 실행 결과로 인용하지 않는다.

## 직접 실행 명령과 결과 원문

PowerShell 프로세스에서 `PYTHONDONTWRITEBYTECODE=1`로 바이트코드 파일 생성을 막고 콘솔 UTF-8을 설정했다. 파일 출력은 테스트의 임시 폴더에만 썼다.

### 전체 테스트 — 단 한 번 실행

명령:

```powershell
py -m unittest discover -s tests
```

종료1, 출력 원문:

```text
No installed Python found!
```

테스트가 시작되지 않았다. 사용자 지시에 따라 전체 테스트를 다시 실행하거나 다른 인터프리터로 전체 suite를 우회 실행하지 않았다.

### 요청된 반례 명령

```powershell
py -m unittest handoff/reviews/probes/test_probe_026.py
```

종료1, 출력 원문:

```text
No installed Python found!
```

### 설치된 Python으로 이번 반례만 실행

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff/reviews/probes/test_probe_026.py
```

종료1, 최초 실행 출력 원문(아래 P10 실패는 CRLF 비교 도구 오류이며 후속 실행에서 해결):

```text
P01 actual MSA exit=0 blank_GRR=3 dashboard=0
.P02 mixed blank/zero/nonzero GRR preserves rows and skips only blank bar
.P03 actual anomaly -> SPC -> dashboard exit=0; missing thresholds shown
.refusal actual_exit=2 previous_preserved=True stderr=오류: 로지스틱 기여값 입력이 모자람
P04 generated missed replay accepted; missing bias refused; recovery accepted
.refusal actual_exit=2 previous_preserved=True stderr=오류: 사건 cusum-3의 격리 범위나 PFMEA 연결이 모자람
refusal actual_exit=2 previous_preserved=True stderr=오류: 사건 cusum-3의 격리 범위나 PFMEA 연결이 모자람
refusal actual_exit=2 previous_preserved=True stderr=오류: 사건 cusum-3의 격리 범위나 PFMEA 연결이 모자람
P05 whole/one-PFMEA/whole-suspect omissions refused; restored input succeeds
.P06 input missing cusum-3 last_50=50 rows, compare still requires scope_size=50
refusal actual_exit=0 previous_preserved=False stderr=
FP07 input missing one cusum-3 last_20 product; compare requires 20, actual rows=19
refusal actual_exit=0 previous_preserved=False stderr=
Frefusal actual_exit=2 previous_preserved=True stderr=오류: 고장 뒤 첫 정지와 사건 연결이 맞지 않음
P08 failure-mode pipe accepted; false-stop link refused; both reasons shown
.P09 actual line outputs: no selection and no balance accepted; stale SVG excluded
.FP11 dashboard bytes=271177 repeated/submitted equal; all input bytes unchanged
.PRESERVATION original source/tests/recipes/reports/data files=193 unchanged

======================================================================
FAIL: test_p06_one_entire_scope_missing (handoff.reviews.probes.test_probe_026.Probe026.test_p06_one_entire_scope_missing)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_026.py", line 180, in test_p06_one_entire_scope_missing
    self.refused()
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_026.py", line 89, in refused
    self.assertEqual(result.returncode, 2, "Incomplete true-stop links must be refused")
AssertionError: 0 != 2 : Incomplete true-stop links must be refused

======================================================================
FAIL: test_p07_one_scope_product_missing (handoff.reviews.probes.test_probe_026.Probe026.test_p07_one_scope_product_missing)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_026.py", line 189, in test_p07_one_scope_product_missing
    self.refused()
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_026.py", line 89, in refused
    self.assertEqual(result.returncode, 2, "Incomplete true-stop links must be refused")
AssertionError: 0 != 2 : Incomplete true-stop links must be refused

======================================================================
FAIL: test_p10_frozen_files_and_legacy_reports (handoff.reviews.probes.test_probe_026.Probe026.test_p10_frozen_files_and_legacy_reports)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_026.py", line 232, in test_p10_frozen_files_and_legacy_reports
    self.assertEqual((ROOT / name).read_bytes(), subprocess.check_output(["git", "show", BASE + ":" + name], cwd=ROOT), name)
AssertionError: b'\xe[171 chars]alue\r\nnotice,,,,,,,,,,,,,,"\xed\x95\xa9\xec\[2415 chars]\r\n' != b'\xe[171 chars]alue\nnotice,,,,,,,,,,,,,,"\xed\x95\xa9\xec\x8[2353 chars]b8\n' : reports/anomaly_lamp_methods.csv

----------------------------------------------------------------------
Ran 11 tests in 9.082s

FAILED (failures=3)
```

### 반례 도구 수정 후 관련 반례만 재확인

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff.reviews.probes.test_probe_026.Probe026.test_p06_one_entire_scope_missing handoff.reviews.probes.test_probe_026.Probe026.test_p07_one_scope_product_missing handoff.reviews.probes.test_probe_026.Probe026.test_p10_frozen_files_and_legacy_reports
```

종료1, 출력 원문:

```text
P06 input missing cusum-3 last_50=50 rows, compare still requires scope_size=50
refusal actual_exit=0 previous_preserved=False stderr=
accepted incomplete chain: <tr><td>cusum-3</td><td>207</td><td>value=10.948 C+=5.7999 C-=0.0000 bound=5.7383</td><td>frame=20639</td><td>5045</td><td>guard_closed=1 clamp_open=1 clamp_closed=0 part_present=0 pc_stop=0</td><td>last_20 20, change_point 7</td><td>PF-02, PF-06</td></tr>
FP07 input missing one cusum-3 last_20 product; compare requires 20, actual rows=19
refusal actual_exit=0 previous_preserved=False stderr=
accepted incomplete chain: <tr><td>cusum-3</td><td>207</td><td>value=10.948 C+=5.7999 C-=0.0000 bound=5.7383</td><td>frame=20639</td><td>5045</td><td>guard_closed=1 clamp_open=1 clamp_closed=0 part_present=0 pc_stop=0</td><td>last_20 19, last_50 50, change_point 7</td><td>PF-02, PF-06</td></tr>
FP10 baseline report/test blobs=136 byte-identical; legacy regenerated reports=32 byte-identical
.PRESERVATION original source/tests/recipes/reports/data files=193 unchanged

======================================================================
FAIL: test_p06_one_entire_scope_missing (handoff.reviews.probes.test_probe_026.Probe026.test_p06_one_entire_scope_missing)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_026.py", line 185, in test_p06_one_entire_scope_missing
    self.refused()
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_026.py", line 94, in refused
    self.assertEqual(result.returncode, 2, "Incomplete true-stop links must be refused")
AssertionError: 0 != 2 : Incomplete true-stop links must be refused

======================================================================
FAIL: test_p07_one_scope_product_missing (handoff.reviews.probes.test_probe_026.Probe026.test_p07_one_scope_product_missing)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_026.py", line 194, in test_p07_one_scope_product_missing
    self.refused()
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_026.py", line 94, in refused
    self.assertEqual(result.returncode, 2, "Incomplete true-stop links must be refused")
AssertionError: 0 != 2 : Incomplete true-stop links must be refused

----------------------------------------------------------------------
Ran 3 tests in 11.211s

FAILED (failures=2)
```

이전 반례 파일 전체 실행은 하지 않았다. 위 반례 실행은 이번 파일만 대상으로 한다.

VERDICT: FIX
