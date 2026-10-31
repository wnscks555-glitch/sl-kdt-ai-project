검수 모델: gpt-6.1-sol

# 리뷰 024 — 리뷰 023 재검토

검수일: 2026-10-31. 지정 범위: `64188b7b77da14203cd3e48dca1d71843deb914c..HEAD`. 검수 시 HEAD: `53f3314`.

**판정 FIX. 이전 높음 2건·중간 5건 중 6건은 해결됐고 R23-M1은 부분 해결이다. 유한한 입력의 곱셈 오버플로로 잘못된 z를 수용하고 이전 HTML을 교체하는 높음 1건이 남는다. 전체 테스트는 지정 명령을 한 번 직접 실행했으나 런처 오류로 시작하지 못했다.**

기준은 `handoff/tasks.md` 맨 위 현행 15단계 명세·T237–T248·T263–T266과 이전 단계 보존 조건이다. setup-notes, tasks, gpt-log, decisions, 리뷰 023, 최근 git log와 지정 diff를 읽었다. `practical-work-operation`은 범위·보존·검증 조율에만 적용했다. 요청대로 플러그인 리뷰 스킬·보조 에이전트·이전 반례 파일 실행은 사용하지 않았다. `docs/solutions/`와 `.compound-engineering/`는 없으며 과거 docs 문서를 판정 기준으로 사용하지 않았다.

## 미해결 지적

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| R24-H1 (R23-M1 부분 미해결) | 높음 | src/dashboard.py:300 | 입력 유한성 검사 뒤 곱셈 결과·합계의 유한성을 확인하지 않아, 잘못된 기여값 합을 z와 일치한다고 수용한다. | P04: mean 가중치 `1e308`, sd 가중치 `-1e308`, 나머지 가중치·bias `0`, 경보의 s_mean·s_sd `2`, 나머지 특징값 `0`, z `1`로 변경했다. 모든 입력은 유한하다. 350자리 Decimal 독립 계산의 합은 정확히 `0`으로 z와 다르다. 실제 float 곱셈은 `inf`·`-inf`, 합은 NaN이 되며, 301행의 `abs(NaN - 1) > 1e-8`은 거짓이다. CLI는 종료 `0`, 정적 표에 `inf`·`-inf`를 출력하고 기존 HTML을 교체했다. T265의 불일치 복사본 종료 `2`와 맞지 않는다. | 특징별 곱셈 결과와 bias를 더한 합계의 유한성을 확인한 뒤 z를 비교한다. 계산 결과가 비유한 값이면 종료 `2`로 거절하고 기존 HTML을 보존한다. 유한한 입력이 오버플로하는 회귀 사례를 포함한다. |

R23-M1의 원래 NaN 입력은 이번 P03에서 거절됐다. 그러나 P04는 **유한한 입력**만 사용하고 합이 `0`인데 z를 `1`로 바꾼 경우다. 따라서 비유한 원본 입력에 관한 중간 사례를 그대로 반복한 것이 아니라, 명시된 T265 거절 조건에서 성공하고 이전 산출물을 교체한 사례로 높음 판정했다. 일정·빈도·수정 비용으로 심각도를 낮추지 않았다. 별도 중간·낮음 지적은 없다.

## 리뷰 023 항목별 재판정과 Claude 의견

| 이전 항목 | 재판정 | 반례 확인과 수용 근거 |
| --- | --- | --- |
| R23-H1 / 높음 | 해결 | P01의 `URL(//example.invalid/x.svg#p)`, `uRl(//example.invalid/x.svg#p)`, `URL(#missing)`, `url(#missing)` 모두 종료 2, 이전 HTML 보존. 거절 직후 원래 SVG의 `url(#arrow)`는 종료 0이다. 소문자 정규화로 혼합 대소문자 참조를 검사한다는 설명을 수용한다. |
| R23-H2 / 높음 | 해결 | P02의 올바른 경보 2행은 순서를 뒤집어도 기여값 표 2개를 표시한다. z가 틀린 경보를 앞·뒤에 각각 두면 모두 종료 2, 이전 HTML 보존이다. 모든 경보를 순회한다는 설명을 수용한다. 기여값 계산 자체의 비유한 결과는 R24-H1로 구분했다. |
| R23-M1 / 중간 | 부분 해결, 미해결 유지 | P03의 NaN·inf·-Infinity를 bias·weight·feature·z에 넣은 12개 경우는 모두 종료 2, 이전 HTML 보존이며 정상 복구도 성공한다. `_finite`로 입력을 검사했다는 설명은 사실이다. P04에서 계산 결과 검사 누락이 재현돼 완전 해결로는 수용하지 않는다. 위 R24-H1에 통합했으며 중복 집계하지 않는다. |
| R23-M2 / 중간 | 해결 | P05의 PFMEA evidence 행 순서를 뒤집고 같은 ID의 행을 추가했다. 마크업·따옴표·U+2028이 있는 reference, scope, 분자 0, 분모 024, 관측값 0.000024가 각각 정적 표 셀에 원문대로 있고 빈 값도 유지된다. script 실행 태그는 생기지 않는다. 근거·관측값 표 추가와 필수 열 추가를 수용한다. |
| R23-M3 / 중간 | 해결 | P06에서 관리도 중간 행의 7개 수치와 11·13단계 이동량별 검출률 21개를 서로 다른 문자열로 바꿨다. 모두 이상 검출 절의 정적 td에 있다. 그래프와 함께 정적 수치 표를 추가했다는 설명을 수용한다. JSON이나 SVG 좌표에 문자열이 있는 것만으로 통과시키지 않았다. |
| R23-M4 / 중간 | 해결 | P08의 capability 7행을 모두 n=1·Cpk/Ppk 빈칸·표본 부족으로 두면 종료 0이며 개요와 측정 표가 이를 표시한다. 한 행만 유효한 Cpk/Ppk로 되돌리고 순서를 뒤집으면 개요가 그 Cpk를 고르고 측정 표가 Ppk를 보존한다. 기본값 처리 설명을 수용한다. |
| R23-M5 / 중간·명세 이견 | 해결 | 현행 입력 표에 `incident_lamp_pfmea.md`와 사건 ID·PFMEA 행 표라는 설명이 추가됐고 기대표는 바뀌지 않았다. P09에서 명세 입력 목록만 추출·확장한 23개 파일로 생성에 성공했다. 입력 명세와 실제 의존성을 맞췄다는 설명을 수용한다. decisions에는 Claude 처리·사용자 승인 전으로 기록돼 있으며 이를 최종 사용자 승인으로 표현하지 않는다. |

이번 gpt-log에는 이전 지적을 부정하는 반박은 없고 각 항목을 수정했다고 기록돼 있다. 위 동의는 반례 탐색 이후 해당 범위에서 내렸다. 관리도 수치 표를 details 안에 넣는 방식은 이전 검토에서 수용한 해석과 같고, 실제 표 내용이 정적 HTML에 들어 있다.

## 보존 조건과 검증 범위

- P10은 대시보드 추가 직전 `3fe0761`에 있던 `src/`, `tests/`, `recipes/`, `data/`, `reports/`의 기존 파일 190개를 HEAD와 원시 바이트로 비교해 모두 동일함을 확인했다. 그중 기존 설정·데이터·보고서 산출물은 122개다. 이번 diff는 이전 단계 코드·설정·테스트·보고서를 변경하지 않았다. 새 대시보드의 코드·테스트·HTML 수정은 별도로 구분했다.
- 리뷰 023 기준 커밋의 기존 테스트 메서드 531개를 AST로 비교했다. 변경된 기존 메서드는 새 15단계 파일 `tests/test_dashboard.py`의 `PageTests.test_t241_blank_scores`, `RefusalTests.test_t242_svg_rules` 2개다. 전자는 PFMEA item 표를 새 evidence 표 앞까지로 한정하며 S·O·D 빈칸 3개 검증을 유지하고, 후자는 SVG 거절 입력 3개를 더한다. 이전 1–14단계 테스트 파일은 바이트 그대로다. 따라서 이번 diff 전체를 두고 모든 기존 테스트가 문자 그대로 무수정이라고 주장하지 않는다.
- 기존 테스트 **실행 통과**는 미검증이다. 지정 전체 테스트 명령은 아래처럼 한 번 직접 실행했으나 `py` 런처가 실패했다. gpt-log와 `handoff/run-logs/v2-freeze-tests.txt`의 535개 OK는 구현자 기록이며 직접 확인한 결과로 대신하지 않았다. 다른 인터프리터로 전체 테스트를 재실행하지 않았다.
- P09에서 명세 입력 23개의 바이트가 실행 전후 그대로였고, 임시 폴더 2곳에서 만든 HTML과 저장된 `reports/dashboard.html`이 바이트까지 같았다. 크기는 264149바이트로 5MB 이하이다. 기존 단계 보고서를 이번에 다시 생성하지는 않았다. 기존 보고서 동일성은 위 122개 산출물 비교로 확인했다.
- 새 반례만 기존 설치 Python 3.12로 실행했다. 최종 반례 10개 중 서로 다른 9개가 통과했고 P04 1개가 제품 결함으로 실패했다. 최초 실행 P10은 검수자가 변경 메서드 목록에서 SVG 테스트의 입력 추가를 빠뜨려 실패했다. 이 검수 테스트의 기대 목록을 실제 diff대로 고친 뒤 P10만 재확인했고 통과했다. P04에는 독립 Decimal 검증을 더해 함께 재확인했으며 여전히 실패했다. 전체 테스트나 이전 반례 파일의 재실행과 구분한다.
- 브라우저에서 새 표의 실제 375px 배치·테마·JavaScript 끔을 직접 확인하지는 않았다. 이번 확인은 CLI·정적 HTML·바이트 비교 범위다. gpt-log의 브라우저 확인 기록을 독립 검증 결과로 바꾸어 보고하지 않는다.

## 이번 반례

파일: `handoff/reviews/probes/test_probe_024.py`. 기존 반례·테스트 파일을 import하여 실행하지 않았고, 파일 출력은 tempfile 아래에만 했다.

| 반례 | 입력 | 예상과 명세 근거 | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | 혼합 대소문자 외부 참조·없는 ID 4종, 직후 정상 내부 참조 | SVG 허용 규칙·T242/T244: 위반 종료 2·이전 HTML 보존, 정상 수용 | 4종 거절·보존, 복구 종료 0 | 통과, H1 해결 |
| P02 | 정상 경보 2행의 양 순서, z 오류 행의 앞/뒤 배치 | T265: 모든 경보 표시·합계 검사 | 정상은 표 2개, 오류는 양 순서 모두 종료 2·보존 | 통과, H2 해결 |
| P03 | NaN/inf/-Infinity × bias/weight/feature/z, 직후 정상 입력 | 기여값 합은 비유한 값과 일치할 수 없음, 기존 M1 재검증 | 12종 종료 2·보존, 복구 종료 0 | 통과, M1의 입력 검사 수정 확인 |
| P04 | 유한 가중치 ±1e308, 특징 2, bias/다른 항 0, z=1 | T265: 독립 합 0이 z와 다르므로 종료 2·이전 HTML 보존 | 종료 0, inf/-inf 표기, 이전 HTML 교체 | 실패, R24-H1 |
| P05 | 역순 PFMEA 행, 중복 ID의 evidence, 마크업·U+2028·빈칸·0 | 행별 근거·관측값·T241/T243: 원문 셀·이스케이프·빈 점수 보존 | 각 값의 정적 셀 확인, 실행 script 없음 | 통과, M2 해결 |
| P06 | 관리도 중간 행 7수치·이동량별 검출률 21개 변경 | 그래프 수치 표·T263: 원문 값을 정적 셀로 제공 | 28개 모두 정적 td에 있음 | 통과, M3 해결 |
| P07 | 새 필수 열 10종 각각 삭제, 마지막 정상 복구 | 필요한 열 없음·T242: 종료 2·이전 HTML 보존 | 10종 거절·보존, 복구 종료 0 | 통과, 필수 열 추가의 거절 경로 확인 |
| P08 | 전체 7설비 표본 부족, 이후 한 설비만 유효·역순 | 측정 표본 부족 표시·T239: 빈 값 보존, 유효 Cpk/Ppk 표시 | 두 경우 종료 0, 개요·측정 표 내용 일치 | 통과, M4 해결 |
| P09 | 명세 입력 목록만 사용, 서로 다른 뿌리 2곳 | 입력 계약·T245/T247/T248: 생성·결정성·크기·입력 보존 | 입력 23개 충분, 불변, 저장 HTML과 동일·264149바이트 | 통과, M5 해결 |
| P10 | 대시보드 전 파일 190개·리뷰 023의 테스트 메서드 531개 | 이전 단계 보존 조건: 기존 파일·검증 보존 | 기존 파일 전부 동일, 새 15단계 테스트 메서드 2개만 공개된 범위로 수정 | 정정 후 통과, 실행 통과와 구분 |

## 테스트 명령과 실행 결과

셸에서 `PYTHONDONTWRITEBYTECODE=1`을 설정했고 반례 실행에는 `PYTHONIOENCODING=utf-8`도 설정했다. 설치·런처 설정은 바꾸지 않았다.

전체 테스트는 다음 명령을 한 번만 직접 실행했다.

~~~powershell
py -m unittest discover -s tests
~~~

종료 코드 1:

~~~text
No installed Python found!
~~~

지정 반례 명령도 직접 실행했다.

~~~powershell
py -m unittest handoff/reviews/probes/test_probe_024.py
~~~

종료 코드 1:

~~~text
No installed Python found!
~~~

기존 설치 인터프리터로 이번 반례만 실행했다.

~~~powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -B -m unittest handoff/reviews/probes/test_probe_024.py
~~~

종료 코드 1, 최초 실행 결과:

~~~text
P01 four SVG case/reference refusals preserve old HTML; valid recovery exit=0
.P02 both valid alarm orders display 2 tables; either mismatch order exit=2/old preserved
.P03 12 nonfinite input cases exit=2/old preserved; valid recovery exit=0
.P04 finite input overflow exit=0; inf/-inf cells=True/True; old_preserved=False
FP05 reversed/duplicate PFMEA ID evidence, markup, empty and zero: all exact static cells, escaped
.P06 7 middle-row chart strings and 21 shift strings occur in static cells
.P07 10 newly required missing columns exit=2/old preserved; recovery exit=0
.P08 all 7 short samples display; mixed/reversed rows retain sole Cpk/Ppk
.P09 manifest 23 files sufficient/unchanged; two roots and stored HTML byte-identical (264149 bytes)
.F
======================================================================
FAIL: test_p04_finite_inputs_product_overflow_must_not_match_z (handoff.reviews.probes.test_probe_024.Probe024.test_p04_finite_inputs_product_overflow_must_not_match_z)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_024.py", line 188, in test_p04_finite_inputs_product_overflow_must_not_match_z
    self.assertEqual(result.returncode, 2, "nonfinite arithmetic incorrectly accepted as z=1")
AssertionError: 0 != 2 : nonfinite arithmetic incorrectly accepted as z=1

======================================================================
FAIL: test_p10_preserved_blobs_and_test_bodies (handoff.reviews.probes.test_probe_024.Probe024.test_p10_preserved_blobs_and_test_bodies)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_024.py", line 331, in test_p10_preserved_blobs_and_test_bodies
    self.assertEqual(changed_methods, [("tests/test_dashboard.py", "PageTests", "test_t241_blank_scores")])
AssertionError: Lists differ: [('te[57 chars]res'), ('tests/test_dashboard.py', 'RefusalTes[23 chars]es')] != [('te[57 chars]res')]

First list contains 1 additional elements.
First extra element 1:
('tests/test_dashboard.py', 'RefusalTests', 'test_t242_svg_rules')

- [('tests/test_dashboard.py', 'PageTests', 'test_t241_blank_scores'),
?                                                                    ^

+ [('tests/test_dashboard.py', 'PageTests', 'test_t241_blank_scores')]
?                                                                    ^

-  ('tests/test_dashboard.py', 'RefusalTests', 'test_t242_svg_rules')]

----------------------------------------------------------------------
Ran 10 tests in 24.863s

FAILED (failures=2)
~~~

P10의 검수 테스트 기대 목록 정정과 P04의 Decimal 독립 계산 추가 후 해당 두 메서드만 실행했다.

~~~powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -B -m unittest handoff.reviews.probes.test_probe_024.Probe024.test_p04_finite_inputs_product_overflow_must_not_match_z handoff.reviews.probes.test_probe_024.Probe024.test_p10_preserved_blobs_and_test_bodies
~~~

종료 코드 1:

~~~text
P04 finite input overflow exit=0; inf/-inf cells=True/True; old_preserved=False
P04 independent Decimal sum=0; report z=1
FP10 pre-dashboard preserved blobs=190 (artifacts=122); prior review test bodies=531, only changed=[('tests/test_dashboard.py', 'PageTests', 'test_t241_blank_scores'), ('tests/test_dashboard.py', 'RefusalTests', 'test_t242_svg_rules')]
.
======================================================================
FAIL: test_p04_finite_inputs_product_overflow_must_not_match_z (handoff.reviews.probes.test_probe_024.Probe024.test_p04_finite_inputs_product_overflow_must_not_match_z)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_024.py", line 197, in test_p04_finite_inputs_product_overflow_must_not_match_z
    self.assertEqual(result.returncode, 2, "nonfinite arithmetic incorrectly accepted as z=1")
AssertionError: 0 != 2 : nonfinite arithmetic incorrectly accepted as z=1

----------------------------------------------------------------------
Ran 2 tests in 15.163s

FAILED (failures=1)
~~~

`git diff --check 64188b7..HEAD`는 종료 0, 출력 없음이었다. 검수자가 생성·수정한 저장소 파일은 이 리뷰와 `probes/test_probe_024.py`뿐이다. 시작부터 존재한 `handoff/loop-logs/024-codex.txt`는 검수자가 수정하지 않았다. 코드·원본 테스트 수정, commit·push·설치·파일 삭제는 하지 않았다. 전체 테스트 미검증 자체를 결함으로 계상하지 않았으며 FIX는 R24-H1에 따른다.

VERDICT: FIX
