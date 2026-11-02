검수 모델: gpt-6.1-sol

# 리뷰 028 — 리뷰 027 재검토 및 현행 17·18단계 검수

검수일: 2026-11-02. 대상: `git diff 0a0be8842d289bede5286359b3b5d090783f2e36..HEAD`, HEAD `011a471`. 기준: `handoff/tasks.md` 맨 위 현행 작업, 본문보다 우선하는 「검토 반영」, T284–T303, 이전 단계 보존 조건. 지정 diff에는 027 수정 `f7223a6`과 신규 17·18단계 `011a471`이 함께 있다.

**판정 FIX. 이전 중간 3건은 해결됐다. 이전 높음 1건은 부분 해결이며, 새 높음 1건·중간 1건이 있다. 미해결 합계는 높음 2건·중간 1건이다.** 정상 제출 결과는 재현됐지만 입력 파일을 잃는 두 경로와 SECOM의 빈 분석 대상 처리가 남았다. 낮음 1건은 기록만 한다.

AGENTS, setup-notes, tasks, gpt-log의 관련 수정·의견, decisions, 027 리뷰, 최근 log와 지정 diff를 읽었다. `practical-work-operation`은 조율·보존 확인에만 사용했다. 요청대로 플러그인 리뷰 스킬과 보조 에이전트는 사용하지 않았다. `.compound-engineering/config.yaml`, `docs/solutions/`는 없다. 이번 검수자가 작성한 저장소 파일은 이 리뷰와 `handoff/reviews/probes/test_probe_028.py`뿐이다. 시작부터 있던 미추적 `handoff/loop-logs/028-codex.txt`는 건드리지 않았다. 제품 코드·원본 테스트·제출 보고서 수정, 설치, commit·push·파일 삭제는 하지 않았다. 생성·덮어쓰기 반례는 모두 unittest의 임시 폴더 안에서 실행했다.

## 이전 높음·중간 항목별 판정

| 이전 항목 | 판정 | 반례 이후 확인한 근거 |
| --- | --- | --- |
| R27-H1 / 출력이 입력을 덮어씀 | **부분 해결, 높음 유지** | P03: guard·compare·balance 각각의 직접 경로와 하드링크 별칭 6사례는 모두 종료2·파일 불변이다. `check_outputs`의 resolve·samefile 검사가 실제 동작한다. 그러나 P04: 라인이 간접 참조하는 생성기를 `reports/sizing_lamp_sheet.md`에 두면 종료0으로 그 입력을 sheet로 덮어쓴다. 보호 목록에 생성기·그 하위 입력이 빠져 있다. |
| R27-M1 / 음수·분모 초과 건수 | **해결** | P02: 오불합격·오합격 각각 -1·분모+1을 거절한다. 경계 0·분모는 정확한 비율 0·1로 받는다. `src/sizing.py:193`의 포함 범위 검사가 잘못된 비율만 차단한다. |
| R27-M2 / 깨진 JSON 종료 분류 | **해결** | P01: 잘린 객체·끝 쉼표·빈 파일·UTF-8 오류가 전부 종료3이고 보고서는 불변이다. 정상 JSON을 복원한 뒤 종료0이며 모든 임시 보고서 바이트가 거절 전과 같다. |
| R27-M3 / T281 검증 공백 | **해결** | P05: 현재 T281 테스트 메서드를 그대로 호출하되 joint 개발 UPH·홀드아웃 UPH·판정 문자열을 각각 조작하면 모두 AssertionError다. 코드도 경계 행으로 스테이션과 수리를 재구성하고 직접 모의 결과와 비교하며, 0이 아닌 각 증분·수리의 누락도 검사한다. 원본 테스트 파일은 수정하지 않았다. |

`handoff/gpt-log.md`에는 027에 대한 별도 반박은 없고 수정 설명이 있다. 건수 범위, JSON 분류, T281 직접 대조 설명에는 위 반례 후 동의한다. 입력 보호 설명은 **직접 열거한 5개 입력에 한해서** 근거가 있다. 간접 생성기를 포함한 전체 입력 보존까지 해결됐다는 해석에는 P04 때문에 동의하지 않는다. 제품 코드의 joint 계산을 바꾸지 않았다는 설명은 diff와 일치한다.

## 미해결 높음·중간

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| R27-H1 (잔존) | 높음 | `src/sizing.py:301`, `src/sizing.py:303` | 입력 보호 목록에 라인이 참조하는 생성기가 없어 출력으로 덮어쓸 수 있다. | P04: 정상 생성기 JSON을 임시 `reports/sizing_lamp_sheet.md`에 두고 라인의 `generator`가 이를 가리키게 했다. 생성기의 recipe·equipment 상대 경로는 새 위치에 맞춰 동일 원본을 가리킨다. 같은 개발·홀드아웃 보고서로 기준선 재현을 통과한 뒤 종료0, 생성기 바이트가 sheet 본문으로 바뀐다. 직접 입력 충돌은 고쳤지만 간접 입력의 데이터 손실과 이전 단계 보존 조건 위반이 남는다. | 생성기 및 그 생성기가 읽는 recipe·equipment를 포함해 실제 입력 경로를 수집하고, 모든 출력과 resolve·samefile로 대조한 뒤 쓰기 시작한다. 간접 입력 충돌도 종료2·전 파일 불변으로 검증한다. |
| R28-H1 | 높음 | `src/secom.py:422`, `src/secom.py:429` | SECOM 출력과 원자료가 하드링크이면 문자열 경로 비교를 통과해 원자료를 덮어쓴다. | P06: 정상 해시의 `recipes/data.txt`와 `reports/check_features.csv`를 같은 파일의 하드링크로 만들었다. 설정과 값은 정상이다. 종료0 후 원자료가 특징 CSV로 바뀌었다(`preserved=False`). `Path.resolve()`는 하드링크를 합치지 않으며 `_write_csv`는 같은 파일을 직접 잘라 쓴다. 실제 데이터 손실이므로 높음이다. | 출력 쓰기 전에 존재하는 입력·출력의 samefile도 검사한다. SECOM이 간접 참조하는 입력까지 보호 목록에 넣고, 충돌 거절 시 원자료·기존 보고서 불변을 확인한다. |
| R28-M1 | 중간 | `src/secom.py:339`, `src/secom.py:341`, `src/secom.py:294` | 합격 관측이 없는 단계가 있으면 분석 제외 사유를 처리하다가 합성 비교 계산에서 예외로 종료한다. | P07: 80행의 유효한 값·라벨에서 1·2단계 합격 수가 0/0, 0/40이면 `ZeroDivisionError`, 40/0이면 None 비율을 정렬하다 `TypeError`다. 세 경우 모두 traceback·종료1이다. 특징 제외 처리는 있어도 선택 특징이 0개인 뒤 합성 비교를 무조건 호출한다. 명세가 이 전체 입력 조합의 결과를 명시하지는 않으므로 중간으로 분류한다. | 합성 비교에 필요한 각 단계 길이를 먼저 검사한다. 계산 불가 상태와 제외 사유를 보고하거나 설명 있는 입력 오류2로 처리하고, 0개 관측으로 비율을 만들지 않는다. |

## 낮음 및 명세 이견 — 수정 요구 수에 포함하지 않음

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| R28-L1 / 명세 이견 | 낮음 | `handoff/tasks.md:9` | 현행 입력 설명의 특징 수 591과 실제 고정 자료·보고서의 특징 수 590이 다르다. | 고정 해시 자료로 재생성한 summary의 `features=590`, 제출 특징 CSV의 데이터 행 590개, 분석416+상수122+결측52=590이다. README도 590으로 적었다. 591개를 강제하는 코드나 누락 열 증거는 없으며 현재 계산 판정에는 영향이 없다. | 특징과 라벨을 구분해 명세의 자료 소개 문구를 일치시킨다. 이 검수에서는 명세·기대표·원자료를 고치지 않았다. |

「검토 반영」이 본문보다 우선하므로, 전체 결측률 대신 1단계 결측률로 선택하는 것, 모멘트 왜도·첨도, 첫 30개 검증 시드의 순수열·혼합열 비교, leave 뒤 release·down 허용은 명세 위반으로 올리지 않는다. T300 원래 문구와 후속 규칙의 차이도 이미 명시된 우선순위로 판단했다.

## 이번 diff에 집중한 반례

이전 반례 파일 전체는 실행하지 않았다. 이번 파일에는 unittest 메서드 10개가 있고, 최종 유효 결과는 **7개 통과·3개 실패**다. 실패 메서드는 P04·P06·P07이며 P07에는 실패 세부 사례 3개가 있다. 첫 실행의 P10에는 검수자가 필수 CLI 옵션을 빠뜨린 오류가 있었으며 수정 후 P10만 다시 실행해 통과했다. 이 실행 오류를 제품 결함으로 세지 않았다.

| 반례 | 입력 | 예상(명세 근거) | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | 잘린·끝 쉼표·빈·UTF-8 오류 설정, 그 직후 정상 설정 복원 | T275 설정3, 보고서 보존, 정상 복원 후 동일 결과 | 3·3·3·3 뒤0, 보고서 전부 동일 | 통과, R27-M2 해결 |
| P02 | 오불합격·오합격 -1·분모+1 및 0·분모 | T283 불가능한 건수 거절, 포함 경계 허용 | 불가능 4사례 거절, 경계 4사례 비율0·1 | 통과, R27-M1 해결 |
| P03 | guard·compare·balance 입력을 출력과 동일 경로 또는 다른 이름의 하드링크로 지정 | T282·보존 조건:2·파일 불변 | 6사례 모두2·불변 | 통과, 직접 입력 보호 확인 |
| P04 | 생성기를 sheet 출력 위치에 두고 라인 설정에서 간접 참조 | 입력 보존, 쓰기 전 충돌 거절 | 0, 생성기 소실 | 실패, R27-H1 잔존 |
| P05 | 현재 T281에 joint 개발0·홀드아웃999999·판정 동시 충족을 각각 주입 | 요구를 실제 검증하면 조작 행 거절 | 3개 모두 AssertionError | 통과, R27-M3 해결 |
| P06 | SECOM 정상 원자료와 features 출력이 서로 다른 이름의 하드링크 | 데이터 보존, 같은 파일 쓰기 거절 | 0, 원자료 바이트 변경 | 실패, R28-H1 |
| P07 | 80행, 단계별 합격 값 수 0/0·0/40·40/0 | 제외 사유 또는 설명 있는 오류, 처리되지 않은 예외 없음 | 모두1·traceback, 0분모 또는 None 정렬 오류 | 실패 3사례, R28-M1 |
| P08 | 1단계40개, 2단계에 NaN·불합격999·15·NaN·9 | 검토 반영·T290·T291: 결측·불합격 제외, EWMA 갱신 안 함 | n1=40·n2=2·선택1, I·EWMA가 [15,9] 직접 계산과 동일 | 통과 |
| P09 | 병렬2대, B모델 첫 공정 건너뜀, 검사 시도0–2, 정지·수리·버퍼0–2의 25개 조합; 전 공정 시간0 제품 | T297–T300: 기록 전후 결과 동일, 제품당 leave1회, 원본 불변 | 25개 조합 모두 동일·불변; 시간0 제품은 시각0의 leave 하나 | 통과 |
| P10 | 기준/HEAD blob 대조, 제출 조건으로 9단계·신규 재생·실제 고정 해시 SECOM을 임시 reports에 재생성 | 이전 보고서 동일, 기존 테스트 보존, 정상 신규 결과 재현 | 이전95개 blob 동일, 9단계3개·재생HTML1개·SECOM3개 원시 바이트 동일 | 통과; 전체 테스트 통과는 미검증 |

## 보존 조건 및 동의 범위

- 기준 커밋의 기존 보고서 **95개는 모두 Git blob 동일**이다. P10은 빈 임시 reports에서 제출 조건(개발0–29·홀드아웃1000–1029·제품500)으로 9단계 보고서3개를 실제 재생성해 제출본과 원시 바이트까지 대조했다. 신규 재생HTML·SECOM 보고서3개도 제출본과 동일하며 그 실행 전 생긴 보고서들은 불변이었다. 나머지 기존 보고서 전부를 재생성했다고 주장하지 않는다.
- 기존 테스트 중 지정 diff에서 바뀐 파일은 `tests/test_sizing.py` 하나다. 027 지적에 따른 회귀 추가 및 T281 검증 교체이며 이를 “전 diff에서 기존 테스트 파일 무수정”이라고 표현하지 않는다. **17·18단계 구현 커밋만 `f7223a6..HEAD`로 대조하면, 이전부터 있던 모든 테스트는 바이트 그대로**다. 원본 테스트 코드를 바꾸어 신규 기능을 통과시킨 변경은 없다.
- `src/line.py`는 시뮬레이션 사건을 기록하는 선택 인자·호출을 추가했다. P09에서 반환 결과·원본 객체 보존을 확인했고 실제 9단계 보고서도 동일했다. `on_event=None`일 때 계산을 바꾸지 않았다는 Claude 설명에는 이 범위에서 동의한다.
- SECOM 제출 결과의 분석416개, I 중앙값0.0108·순수열0.0020·혼합열0.0201, EWMA0.0482·0.0013·0.0141은 실제 고정 해시 자료로 재생성해 확인했다. 합격 행 비율을 오경보율·검출률로 확대하지 않은 보고서 해석에도 동의한다. 1단계 결측률 선택과 결측·불합격에서 EWMA를 갱신하지 않는 동작은 P08로 확인했다.
- `src/tests/recipes/reports/data`의 파일 내용 SHA-256 목록 **213개는 반례 실행 전후 불변**이다. 원자료 손실 재현 대상은 임시 복사본뿐이다.
- **기존 전체 테스트 무수정 통과는 미검증**이다. 아래 지정 명령은 직접 한 번 실행했지만 py 런처가 테스트 시작 전에 실패했다. 구현자의 `handoff/run-logs/v2-17-18-tests.txt`에는 606 tests OK가 있으나 검수자의 직접 통과 결과로 대체하지 않는다. 다른 인터프리터로 전체 테스트를 우회 재실행하지 않았다.
- 브라우저의 실제 애니메이션·버튼·슬라이더·속도·폭·테마 및 JavaScript 끔 상태의 시각 검증은 **미검증**이다. 이번 HTML 검증은 정상 생성·제출본 바이트 동일 및 소스 확인 범위다. 라이선스 출처 페이지의 외부 재조회도 하지 않았다.

## 직접 실행 명령과 결과

PowerShell에서 `PYTHONDONTWRITEBYTECODE=1`, `PYTHONIOENCODING=utf-8`을 설정했다. 반례 하위 CLI도 같은 환경이고 저장소 밖 임시 폴더에서 실행한다.

### 전체 테스트 — 단 한 번 실행

```powershell
py -m unittest discover -s tests
```

종료1, 출력 원문:

```text
No installed Python found!
```

### 지정 반례 명령

```powershell
py -m unittest handoff/reviews/probes/test_probe_028.py
```

종료1, 출력 원문:

```text
No installed Python found!
```

### 설치된 Python 3.12로 이번 반례 실행

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff/reviews/probes/test_probe_028.py
```

종료1. 결과 원문 중 최종 요약·진단 출력은 아래와 같다. 긴 unittest traceback은 생략하며 실패 원인과 검수자 P10 실행 오류를 뒤에 구분했다.

```text
Ran 10 tests in 11.948s

FAILED (failures=6)
P01 invalid=b'{"line":' exit=3
P01 invalid=b'{"line":"a",}' exit=3
P01 invalid=b'' exit=3
P01 invalid=b'\xff' exit=3
P01 restored valid input: exit=0, all reports identical
P02 four impossible counts refused; four inclusive boundary ratios valid
P03 guard_report hardlink=False exit=2
P03 guard_report hardlink=True exit=2
P03 line_report hardlink=False exit=2
P03 line_report hardlink=True exit=2
P03 balance_report hardlink=False exit=2
P03 balance_report hardlink=True exit=2
P04 indirect generator exit=0 preserved=False
P05 actual revised T281 rejects each of three corrupted joint fields
P06 data hardlink exit=0 preserved=False
P07 phase good=0/0 exit=1 stderr=['ZeroDivisionError: division by zero']
P07 phase good=0/40 exit=1 stderr=['ZeroDivisionError: division by zero']
P07 phase good=40/0 exit=1 stderr=["TypeError: '<' not supported between instances of 'NoneType' and 'NoneType'"]
P08 missing/failed values excluded; phase2 count=2; I and EWMA independent oracle match
P09 25 parallel/skip/retest/repair combinations and all-zero service: callback invariant
PRESERVATION repository protected files=213 unchanged
```

실패 원문의 핵심 메시지:

```text
AssertionError: 0 != 2 : Indirect input must not be overwritten
AssertionError: 0 != 2 : Same underlying input file must be refused
```

P07은 표의 세 예외를 포함하는 stderr 때문에 `assertNotIn("Traceback", result.stderr, ...)`가 각 사례에서 실패했다. 나머지 1건은 P10의 최초 호출에 검수자가 `--seeds`, `--holdout-seeds`를 빠뜨린 오류다. 해당 오류 원문:

```text
AssertionError: 2 != 0 : usage: line.py [-h] --seeds SEEDS --holdout-seeds HOLDOUT_SEEDS
               [--products PRODUCTS]
               line
line.py: error: the following arguments are required: --seeds, --holdout-seeds
```

현재 반례 파일은 제출 compare에서 시드·제품 수를 읽어 그 옵션을 명시한다. 이 수정 뒤 P10만 재실행했다. 전체 테스트 및 이전 반례를 다시 실행하지 않았다.

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff.reviews.probes.test_probe_028.Probe028.test_p10_git_preservation_and_default_regeneration
```

종료0, 출력 원문:

```text
.
----------------------------------------------------------------------
Ran 1 test in 25.622s

OK
P10 old report blobs=95 unchanged; new-feature commit preserves old tests; line reports=3 regenerated identical; replay and SECOM submitted reports identical
PRESERVATION repository protected files=213 unchanged
```

VERDICT: FIX
