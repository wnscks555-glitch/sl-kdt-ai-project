검수 모델: gpt-6.1-sol

# 리뷰 015 — 리뷰 014 재검토 및 현행 v2 8단계 검수

검수일: 2026-10-31. **VERDICT: FIX. 이전 H1·H2·M1은 해결. 신규 미해결 높음 1건(H3)·중간 1건(M2), 수정 요구 2건. 낮음 지적 없음.** 이번 반례 14개 중 11개 통과·3개 실패다. 전체 테스트 지정 명령은 한 번만 직접 실행했으나 `py` 런처가 Python을 찾지 못해 시작되지 않았다. 전체 테스트 통과 여부는 **미검증**이다.

## 범위와 수행

기준은 `handoff/tasks.md:1` 현행 8단계 명세·T113–T129 및 아래 완료 단계의 보존 조건이다. `handoff/setup-notes.md`, `handoff/tasks.md`, `handoff/gpt-log.md`의 관련 구현·014 수정 기록, `handoff/decisions.md`, 이전 `014-review.md`, 최근 이력·diff와 실제 코드·테스트·제출물을 대조했다. 과거 `docs/` 명세를 검수 기준으로 사용하지 않았다. 새 산출물인 점수 기준표는 현행 명세에 대한 구현물로만 확인했다.

`practical-work-operation`을 범위·보존·검증 조율에 적용했다. 사용자 지시에 따라 플러그인 리뷰 스킬·보조 에이전트·이전 반례 파일 전체 실행을 사용하지 않았다. 이번에 작성한 파일은 `handoff/reviews/015-review.md`, `handoff/reviews/probes/test_probe_015.py`뿐이다. 제품 코드·기존 테스트를 수정하거나 커밋·푸시·설치·삭제하지 않았다. 시작부터 있던 미추적 `handoff/loop-logs/015-codex.txt`는 건드리지 않았다. 모든 재생 산출물은 반례 내부 임시 폴더에만 썼다.

검토 명령:

```text
git diff 3d3b2fd83a69b667b1d22ba9856015ed2aea5879..HEAD
git log -6 --oneline
git log --format='%h %s' 3d3b2fd..HEAD
git diff --check 3d3b2fd83a69b667b1d22ba9856015ed2aea5879..HEAD
```

HEAD: `96374f210743bb004748ffbc37cacfc58c56ff1b`. 지정 범위는 14파일이다. diff 검사는 출력 없이 종료 0. 범위 내 커밋:

```text
96374f2 feat(T113-T129): add synthetic PFMEA practice with evidence links
4daa65a docs(T113-T129): confirm stage 8 spec by user delegation
885abbf fix(T108): apply review 014 numeric bounds and independent cases
```

## 이전 높음·중간 항목별 판정

| 이전 ID | 심각도 | 판정 | 수정·반례 근거 |
| --- | --- | --- | --- |
| H1 | 높음 | **해결** | `src/generate.py:362`–`:368`의 분포 계산에서 `OverflowError`를 설정 오류로 변환한다. P01에서 개별적으로 유한한 정수 이동량 `10**308` 두 개, Cpk 0.1의 합성 분포가 traceback 없이 종료 2였고 CSV/meta가 없었다. |
| H2 | 높음 | **해결** | `src/generate.py:40`–`:48`에서 양자화 전 정수부 자릿수를 확인한다. P02의 Cpk `1e-307`·시드 42·20제품도 종료 2·자릿수 오류·파일 미생성이었다. P04에서 극소 양수·음수, 양·음의 반올림 경계, 30자리 경계와 큰 음수를 추가 확인했다. |
| M1 | 중간 | **해결** | `tests/test_measurement.py:554`, `:565`, `:718`에서 사례별 이름으로 독립 파일을 만들고 정상 기본 설정에 오류 하나씩 적용한다. 사례별 오류 문구와 CSV/meta 미생성을 단정한다. P03에서 서로 다른 파일에 Cpk 0과 정상 1.33이 보존됨을 확인했고, 수정된 T108 메서드 자체(설정 14사례 및 측정 평가 거절)도 단독 실행해 통과했다. |

`gpt-log.md:3731` 이후의 세 수정 설명은 위 반례 결과와 일치하므로 받아들인다. 런처 실패 때문에 제품 코드를 바꾸지 않았다는 판단에도 동의한다. 다만 “사용자 PC에서 전체 테스트 정상 실행” 주장은 이 세션에서 확인되지 않았다. 제출 로그의 225개 통과 기록을 이번 독립 실행 결과로 대체하지 않는다.

## 신규 지적 사항

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| H3 | 높음 | `src/pfmea.py:116` | 실제 보고서에 없는 열을 빈 값으로 취급해 존재하지 않는 근거를 허용한다. | P08은 유효한 method·provenance가 있고 `precision` 열만 있는 보고서를 `report:probe:m:capture_rate`로 참조한다. `check_table`은 오류 없이 성공하고 근거 상태를 `값 없음`으로 판정했다. `tasks.md:47`은 없는 참조 대상을 오류·종료 3으로 정하며, `:57`의 빈 값 허용은 존재하는 열의 빈 셀에 대한 규칙이다. `.get(column, "")`이 열 부재를 빈 셀과 합쳐 입력 오류 경로를 우회한다. | 보고서 헤더에 요청한 열이 있는지와 해당 행의 셀 존재 여부를 검사한다. 실제 빈 문자열과 열·셀 부재를 구분해 후자는 `행번호.evidence` 또는 해당 참조 칸의 표 오류로 거절한다. 열이 있으나 값이 빈 정상 사례는 계속 허용하는 회귀를 함께 둔다. |
| M2 | 중간 | `src/pfmea.py:452` (`:459`–`:468` 관련) | Markdown이 현재 관리·조치의 근거 참조와 외부 보고서 관측값을 누락한다. | P09의 `reason:SEQ_SKIP`·`reason:RECIPE_UNKNOWN_STEP` 두 참조가 Markdown에서 모두 사라졌다. P10은 CSV용 action 행에 `0.314159`·`미충족`이 정확히 있어도 Markdown에는 기준과 `미충족`만 있고 관측값이 없다. 실제 제출 Markdown도 PF-03/04의 테스트·사유 참조, PF-05의 조치 근거, PF-06의 관측값 `0.8525`가 없다. `tasks.md:5`–`:7`의 근거·관측 결과 연결 목적과 `:160`의 행별 근거·기준과 결과 표시를 충족하지 못한다. | 행별로 현재 관리 참조·조치 근거를 표시하고, 효과 확인 행에는 기준·관측값·판정을 함께 표시한다. 외부 보고서 값은 현재 측정 지표 표에 없으므로 해당 행에서 읽을 수 있게 한다. 근거 상태·설명만 있는 출력과 실제 참조·값을 포함한 출력을 구별하는 회귀 검증을 둔다. |

H3은 명세의 없는 대상 거절 규칙과 다른 판정이므로 높음이다. M2는 CSV에 있는 근거·관측 결과를 Markdown에서 확인할 수 없는 보고서 불일치이므로 중간이다. 두 건의 심각도에는 일정·수정 비용을 반영하지 않았다. 기대표를 변경하거나 새로운 사용자 결정을 요구할 명세 이견은 없다. 구현을 8-1~8-3별 커밋 대신 한 커밋으로 묶은 절차 차이는 Claude가 공개했으며, 별도의 동작 수정 요구로 세지 않는다.

## 이번 반례

파일: `handoff/reviews/probes/test_probe_015.py`. P01–P03은 이전 지적의 독립 재확인, P04–P10은 이번 변경에 집중한 명세·기대표 밖 경계·조합·보고서 반례, P11–P14는 보존·제출물 재생 검증이다. 이전 반례 파일을 import하거나 실행하지 않았다.

| ID | 입력 | 예상·명세 근거 | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | Cpk 0.1, 결함·설비 이동량 각각 정수 `10**308` | 비유한 합성 분포는 종료 2·파일 미생성 (`:373`, `:383`) | 종료 2, 분포 오류, traceback·CSV/meta 없음 | 통과·H1 해결 |
| P02 | Cpk `1e-307`, 오류율 0, 시드 42·20제품 | 생성 문자열 자릿수 초과는 종료 2·파일 미생성 (`:384`) | 종료 2, 자릿수 오류, traceback·CSV/meta 없음 | 통과·H2 해결 |
| P03 | T108 helper로 0 Cpk·음수 설비 이동량을 서로 다른 이름에 기록하고 수정 T108 단독 실행 | 서로 다른 오류를 독립 입력·오류 이유로 검증해야 함 | 경로 독립, Cpk 0·1.33 유지, 14설정 사례 및 평가 거절 검증 통과 | 통과·M1 해결 |
| P04 | ±`1e-300`, ±`0.0005`, `1e26`, ±`1e27`, `1e100`, `-1e308` | HALF_UP·음수 영 제거·30자리 제한을 모두 보존 | 극소수 `0.000`, 반올림 ±`0.001`, `1e26` 허용, 나머지 큰 값 ValueError | 통과 |
| P05 | 소문자 규칙·중복·빈 조각·앞/뒤 공백 참조를 차례로 넣고 정상 참조 입력 | 표 오류가 지표 계산보다 먼저 발생. 원문 보존 (`:17`, `:47`, `:141`) | 5종 모두 `1.evidence` 오류, collect 미호출·원문 불변·보고서 없음, 다음 정상 표 허용 | 통과 |
| P06 | 고장 설비·결함품 없음, 재검사 0, 오류율 1, 시드 7–8·제품 각 1개 | 오류 주입 후보 부족과 무관하게 정상 행 분석, 실행별 분모 합산 (`:73`–`:75`) | 정상 제품 분모 2, 결함·fault 분모 0, detail 빈 값, 정상 측정 존재 | 통과 |
| P07 | seq 모두 1. LEAK-1 정지 후 같은 설비 재검사 거절→다른 설비 재검사 PASS→FIXED→최초 측정. 고장 목록에는 무측정 FINAL-2도 포함 | 물리 행 순서, 거절·재검사 제외, 수리 후에도 고장 설비는 정상 지표에서 제외. 무측정 고장 쌍도 분모 포함 (`:81`–`:90`) | 거절 1, 정지 1/2·미정지 1/2·지연 2/1, 정상 정지율 0/0, 재검사 PASS 1/1, FINAL-2 detail 0/1 | 통과 |
| P08 | 요청한 `capture_rate` 열이 없고 `precision`만 있는 보고서 참조 | 없는 참조 대상은 표 오류 (`:47`, `:57`) | 허용, `evidence_status=값 없음` | **실패 → H3** |
| P09 | 현재 근거 `reason:SEQ_SKIP`, 완료 조치 근거 `reason:RECIPE_UNKNOWN_STEP` | 행별 근거를 Markdown에서도 확인 가능 (`:160`) | 두 참조 모두 누락 | **실패 → M2** |
| P10 | 임시 외부 보고서 관측값 0.314159, 사전 기준 ≥0.4, 효과 확인 | 기준·관측 결과를 행에 연결 (`:7`, `:160`) | action 값·판정은 0.314159·미충족. Markdown 관측값 누락 | **실패 → M2** |
| P11 | 기준 커밋 보호 파일·기존 테스트 AST 및 8단계 커밋 비교 | 기존 파일·관련 없는 테스트 본문 보존 | 117개 보호 blob 일치, 기존 보고서 57개 포함. 측정 테스트는 요구된 M1 수정 외 기존 메서드 동일. 8단계 테스트 변경은 새 파일뿐 | 통과 |
| P12 | v1·v2 샘플 및 기존·측정 seed42·500제품 재생 | 기존 판정·생성·보고서 동일 | 보고서 47개, 생성 CSV/meta 4개 바이트 일치 | 통과 |
| P13 | 기존 dev 6규칙·holdout·baseline 및 독립/집중 로트 dev·holdout 재평가 | 기존 평가 보고서 동일 | 평가 보고서 10개 바이트 일치 | 통과 |
| P14 | 제출 PFMEA 표·시드 0–29·500제품, 서로 다른 임시 폴더에서 두 번 실행 | 동일 입력 바이트 재현·입력 불변 (T114·T129) | CSV·Markdown 모두 두 번 및 제출물과 바이트 일치, 입력 표 불변 | 통과 |

## 보존 조건과 동의하는 판단

- **기존 테스트 수정 범위:** 기준 커밋의 테스트 10개 중 9파일과 fixtures는 그대로다. `test_measurement.py`의 helper 2개·T108 변경 및 자릿수 테스트 추가는 이전 M1·H2 해결 범위이며, 그 밖의 기존 클래스 메서드는 AST로 동일함을 확인했다. 8단계 구현 자체(`885abbf..HEAD`)는 기존 테스트를 수정하지 않고 `test_pfmea.py`만 추가했다. “모든 기존 테스트 파일이 지정 기준 대비 무수정”이라고 보고하지 않는다.
- **기존 테스트 통과:** 전체 명령이 런처 오류로 시작되지 않아 이번 세션의 전체 통과는 미검증이다. 대체 인터프리터로 전체 테스트를 다시 실행하지 않았다. 수정된 T108의 단독 성공과 반례 성공을 전체 테스트 성공으로 확대하지 않는다.
- **기존 보고서 동일:** 보호 blob 비교에 더해, 기존 보고서 **57개 전부(샘플·생성 47 + 평가 10)**를 임시 폴더에서 재생성해 제출본과 바이트 비교했다. 기존·측정 seed42 CSV/meta **4개**도 재생 일치했다. `src/rules.py`, 기존 설정·샘플·자료도 보호 blob에 포함된다.
- **반례 후 동의:** Claude의 원시 분자·분모 합산, 오류 주입 전 정상 행만 분석, 고장 설비의 수리 후 정상율 제외, 미측정 고장 쌍 포함 설명은 P06·P07과 `run_counts` 코드에 부합한다. P01–P04는 수치 수정이 기존 반올림·자릿수 경계를 유지함을 뒷받침한다.
- **제출물 설명:** P14로 제출 CSV·Markdown 재현성과 입력 불변에 동의한다. 외부 보고서 값과 현재 측정 설정을 구분하는 CSV 경로, 정확한 Fraction 기준 비교도 코드로 확인했다. PF-02·PF-06 미충족을 오류로 삼거나 기준을 완화하지 않은 판단은 타당하다. 다만 재현되는 Markdown에도 M2가 존재하므로 바이트 재현만으로 보고서 내용 완결성을 인정하지 않는다.
- **검증 한계:** Python 3.9 및 사용자 PC의 `py` 성공은 미검증이다. 아래 추가 반례·재생은 설치된 Python **3.12.10**에서 실행했다. 모든 가능한 사용자 설정·시드를 전수 검사한 것은 아니다.

## 실행 명령과 결과 원문

콘솔 UTF-8 출력과 `PYTHONDONTWRITEBYTECODE=1`을 설정했다. 테스트 파일 이외 캐시 파일 생성을 막았으며, 기존 테스트 파일을 고치거나 런처를 설치·변경하지 않았다.

### 전체 테스트 — 지정 명령 직접 1회

```powershell
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
py -m unittest discover -s tests
```

```text
No installed Python found!
```

종료 1. 테스트 발견·실행 자체가 시작되지 않았다. 전체 테스트는 재실행하지 않았다.

### 이번 반례 — 지정 명령 직접 실행

```powershell
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
py -m unittest handoff/reviews/probes/test_probe_015.py
```

```text
No installed Python found!
```

종료 1. 이 지정 명령을 통한 반례 성공은 미검증이다.

### 설치된 Python으로 이번 반례만 실행

```powershell
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff/reviews/probes/test_probe_015.py
```

종료 1. 반례 14개 실행, 11개 통과·3개 실패. P03 안에서는 수정된 기존 T108 메서드만 별도로 실행했다. 아래는 실행 중 수집한 stdout·stderr 원문이다.

```text
P01: integer shift overflow => exit 2; CSV/meta absent
.P02: huge finite sample => exit 2; CSV/meta absent
.P03: independent files retained; targeted T108 (14 config cases + evaluation) passed
.P04: half-up, signed zero, 30-digit boundary and huge negatives passed
.P05: five invalid case/duplicate/empty/whitespace refs rejected before generation; next valid row accepted
.P06: 2 seeds x 1 product; no faults/defects; error_rate=1 does not invoke injection
.P07: repeated seq; rejected retest excluded; repaired faulty measurements excluded; unseen fault pair retained
.FFFP11: protected blobs=117; old reports=57; 7a methods preserved except requested M1 fix; stage 8 adds only test_pfmea.py
.P12: replayed reports byte-identical=47; generated CSV/meta=4
.P13 replayed: eval_dev
P13 replayed: eval_holdout
P13 replayed: eval_baseline
P13 replayed: lot
P13 replayed: lot_clustered
P13: evaluation reports byte-identical=10
.P14: submitted PFMEA CSV/Markdown match two independent replays; input unchanged
.
======================================================================
FAIL: test_p08_missing_report_column_is_not_a_blank_value (handoff.reviews.probes.test_probe_015.DiffProbes.test_p08_missing_report_column_is_not_a_blank_value)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_015.py", line 201, in test_p08_missing_report_column_is_not_a_blank_value
    self.fail('missing capture_rate column accepted; evidence_status=' + status)
AssertionError: missing capture_rate column accepted; evidence_status=값 없음

======================================================================
FAIL: test_p09_markdown_retains_current_and_action_evidence (handoff.reviews.probes.test_probe_015.DiffProbes.test_p09_markdown_retains_current_and_action_evidence)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_015.py", line 209, in test_p09_markdown_retains_current_and_action_evidence
    self.assertEqual(missing, [], 'Markdown dropped evidence references')
AssertionError: Lists differ: ['reason:SEQ_SKIP', 'reason:RECIPE_UNKNOWN_STEP'] != []

First list contains 2 additional elements.
First extra element 0:
'reason:SEQ_SKIP'

- ['reason:SEQ_SKIP', 'reason:RECIPE_UNKNOWN_STEP']
+ [] : Markdown dropped evidence references

======================================================================
FAIL: test_p10_markdown_retains_external_observation (handoff.reviews.probes.test_probe_015.DiffProbes.test_p10_markdown_retains_external_observation)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_015.py", line 223, in test_p10_markdown_retains_external_observation
    self.assertIn('0.314159', build_markdown(report), 'external observed value absent from Markdown')
AssertionError: '0.314159' not found in '# 합성 공정 PFMEA 연습\n\n합성 공정의 PFMEA 연습이며 실제 공정, 고객 영향, 실무 PFMEA가 아니다.\n\n생성 데이터의 확률은 가정이며 실제 설비 진단 근거가 아니다.\n\n최초 FAIL률은 원인 발생률이 아니고, 설비 정지율은 제품 불량 검출률이 아니다.\n\n연결됨은 참조가 이어졌다는 뜻이고 관리 효과의 검증이 아니다. 효과 판정은 현재 관리의 성능 확인이며 개선 전후 비교가 아니다. 합성 수치는 참고 관측치이고 점수 환산표가 아니다.\n\n## PF-01 m\n\n- 유형: product\n- 대상: ALL\n- 기능: f\n- 영향(가정): e\n- 원인(가정): c\n- 예방 관리: 없음\n- 검출 관리: 없음\n- 점수: 점수 대기\n- 근거 상태: 연결됨\n- 근거 설명: note\n- 조치: action\n- 조치 상태: 효과 확인\n- 조치 목적: goal\n- 조치 전 관리: T1\n- 조치 후 관리: T2\n- 잔여 위험: risk\n- 사전 기준: report:probe:m:capture_rate >= 0.4\n- 효과 판정: 미충족\n\n## 지표\n\n| 지표 | 범위 | 분자 | 분모 | 값 |\n| --- | --- | --- | --- | --- |\n| metric:defect_escape | 전체 흐름, 실행 끝 상태 | 0 | 0 | - |\n| metric:all_defect_first_fail | 모든 검사 | 0 | 0 | - |\n| metric:leak_defect_first_fail | LEAK | 0 | 0 | - |\n| metric:leak_defect_retest_pass | LEAK | 0 | 0 | - |\n| metric:normal_reject | 전체 흐름, 실행 끝 상태 | 0 | 0 | - |\n| metric:fault_stop_run | 고장 설비 | 0 | 0 | - |\n| metric:fault_no_stop_run | 고장 설비 | 0 | 0 | - |\n| metric:fault_stop_delay | 고장 설비, 첫 정지까지 | 0 | 0 | - |\n| metric:normal_stop_rate | 고장 키에 없는 모든 설비, 실행 전체 | 0 | 0 | - |\n\n## 재검사 대안 비교 (합산 비교, 제품 짝 비교 아님)\n\n| 조건 | 지표 | 분자 | 분모 | 값 |\n| --- | --- | --- | --- | --- |\n' : external observed value absent from Markdown

----------------------------------------------------------------------
Ran 14 tests in 181.075s

FAILED (failures=3)
```

VERDICT: FIX
