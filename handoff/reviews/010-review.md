# 리뷰 010 — v2 5단계 최초 검수

검수일: 2026-10-30. 검수자: Codex. **미해결 높음 1건, 중간 4건으로 FIX**다. 중간 2건은 명세 이견이며 기대표를 임의로 수정하지 않았다. 낮음 1건은 기록만 하고 수정 요구 수에 포함하지 않는다.

전체 테스트 134개는 통과했다. 별도 반례·보존 검증 13개 중 8개 통과, 5개 실패다. 실패를 일으킨 구현은 수정하지 않았다.

## 1. 범위와 기준

- 지정 범위: git diff 400081f9735cc584ac5299e72c75a7515fca57d9..HEAD, 같은 범위의 git log.
- 검수 HEAD: ea3079d359753ee5b95b0b67bdf923da621a59bd.
- 커밋 5개: 3fe8e23 명세·역할 교체, 7a814f8 재가동, d228810 평가, 2718372 결과 기록, ea3079d GEN_0030 trace 추가.
- 기준: handoff/tasks.md:1의 현행 명세·T52–T66, 아래 완료 단계의 보존 조건. setup-notes.md, gpt-log.md의 5단계 구현 기록, decisions.md, 최근 git log·작업 트리 diff·변경 파일을 확인했다. 이전 docs/ 문서는 판정 기준으로 쓰지 않았다.
- 시작 시 추적 파일의 미커밋 변경은 없었고 handoff/loop-logs/010-codex.txt만 미추적 파일로 이미 존재했다. 이 로그는 이번 검수 산출물이 아니다.
- practical-work-operation과 ce-code-review의 범위·요구 대조·독립 검토 관점을 적용했다. 사용자의 두 파일 쓰기 제한을 우선해 별도 스킬 산출물·교훈 파일은 만들지 않았다. 보조 에이전트 1개는 읽기 전용으로 생성기·평가기를 독립 검토했고, 재현과 최종 판정은 주 에이전트가 확인했다. 외부 모델 CLI로 코드를 보내지 않았다.
- docs/solutions/와 .compound-engineering/config.yaml은 없어 재사용할 해결 기록은 없었다.

## 2. 지적 사항

### H1 — 재가동 비활성 상태의 합법적 기존 공정명이 생성 결과를 바꾼다

- **심각도: 높음**
- **파일:줄:** src/generate.py:141
- **문제:** inject_errors가 모드 확인 없이 이름이 EQUIP_RESTART인 모든 행을 오류 주입 후보에서 제외한다. 이 이름은 재가동 모드에서만 예약된 공정명이며 이전 모드에서는 합법적인 제품 공정명이다.
- **근거:** P07은 기존 두 모델의 맨 앞에 EQUIP_RESTART 공정을 추가하고 실제 load_recipe가 허용함을 확인했다. 재가동 키 없는 기존 설정·시드 42·60개로 기준 커밋의 Generator를 메모리에 불러 현행 Generator와 비교했다. 정상 행·주입 종류별 건수는 동일하지만 **최종 CSV의 첫 차이가 24행**에서 발생한다. 비교에서 공유하는 판정기·모델·설비 조건은 같으므로 새 무조건 분기가 원인이다. tasks.md:24의 이전 동작·바이트 보존과 restart 없는 생성 흐름·난수 소비 보존에 어긋난다. 기본 샘플 보존 검사가 통과해도 이 반례는 남는다.
- **제안:** 실제 설비 재가동 이벤트인 경우에만 후보에서 제외한다. 재가동 비활성 상태의 같은 이름 제품 공정을 포함해 이전 생성 행·오류 위치가 그대로임을 회귀 검증한다.

### M1 — 해당 검사 설비가 아예 없으면 생성·평가가 끝나지 않는다

- **심각도: 중간**
- **파일:줄:** src/generate.py:65, src/generate.py:129
- **문제:** 선택할 설비가 없는 이유를 모두 일시 정지로 취급한다. 설비 목록에 해당 검사 종류가 전혀 없으면 재가동 예약도 생기지 않아 대기에서 벗어나지 못한다.
- **근거:** P05는 설비 목록을 {"LEAK-1": "LEAK"}로 제한하고 고장·정상 FAIL·결함·오류 주입 확률을 0으로 두었다. 설비 로더는 이 목록을 허용한다. 제품 2개·시드 0·규칙 3:2로 평가하면 4초 내 종료하지 않아 자식 프로세스를 timeout으로 종료했다. 코드는 yield None → 같은 flow 유지 → 빈 예약 때문에 교착 방지 분기 건너뜀을 반복하며 상태를 바꿀 사건이 없다. 단순히 실행이 느린 상황이 아니다. 명세가 직접 다루지 않은 구성에서 명확한 오류 대신 무한 대기하므로 중간이다.
- **제안:** 필요한 검사 종류에 설비가 있는지 생성 전 검증하거나, 대기 중이고 진행·예약이 모두 없는 경우 원인을 포함한 생성 오류를 반환한다. 평가 CLI는 종료 2·보고서 미생성으로 처리한다. 이전 모드의 허용 범위는 별도로 보존한다.

### M2 — T63의 전체 보류 평균 13.73을 계산·출력·검증하지 않는다

- **심각도: 중간**
- **파일:줄:** src/evaluate.py:24, src/evaluate.py:79, tests/test_evaluate.py:51, handoff/gpt-log.md:3591
- **문제:** 전체 보류 수와 평균이 지표에서 빠졌다. 정상품 보류 평균만 출력하고 T63을 모두 재현했다고 보고한다.
- **근거:** tasks.md:21과 T63(tasks.md:141)은 전체 보류 평균 **13.73**, 정상품 보류 평균 **8.50**을 각각 요구한다. P11의 실제 평가 명령은 종료 0이고 8.50을 출력하지만 13.73이 없다. RunMetrics, 실행별 CSV, 집계 CSV 모두 전체 보류를 저장하지 않는다. 기존 T63 테스트도 이 기대값을 단언하지 않는다. 결과가 틀렸다는 주장보다 필수 지표 누락과 완료 보고의 범위 초과가 문제다.
- **제안:** 실행별 전체 보류 수와 집계 평균을 추가하고 T63의 두 보류 지표를 각각 검증한다. 출력 원문과 완료 보고를 실제 검증 범위에 맞춘다.

### M3 — 명세 이견: 다중 고장 설비의 검출률 단위를 공개 없이 바꿨다

- **심각도: 중간**
- **파일:줄:** src/evaluate.py:72, src/evaluate.py:86, handoff/tasks.md:107
- **문제:** 명세는 “고장 설비를 정탐 정지한 실행 ÷ 실행 수”인데 구현은 “검출된 설비 수 ÷ (실행 수 × 고장 설비 수)”다. 고장 설비가 여러 대일 때 결과와 후보 선정이 달라진다.
- **근거:** P06은 고장 설비 두 대 중 LEAK-2만 정탐한 실행 1개다. 문구를 한 대 이상 검출한 실행 기준으로 읽으면 1/1이지만 실제는 **1/2**다. 만약 모든 고장 설비를 검출한 실행을 뜻한다면 0/1이므로 그 해석 역시 1/2와 다르다. gpt-log.md:3581은 평균 검출 지연의 설비·실행 단위 해석만 밝히며 검출률 변경은 설명하지 않는다. 고장 설비 1대인 제출 결과에는 차이가 없지만 여러 대인 경우의 계약은 정해지지 않았다.
- **제안:** 다중 고장 시 “하나 이상 검출한 실행”, “모두 검출한 실행”, “설비·실행 단위 검출” 중 의도한 지표를 명세 이견으로 확정하고 분자·분모·출력 설명·테스트를 맞춘다. 이번 검수에서는 기대표를 고치거나 한 해석을 사용자 결정으로 간주하지 않았다.

### M4 — 명세 이견: delay_rows의 행 기준과 실제 출력이 다르다

- **심각도: 중간**
- **파일:줄:** src/generate.py:125, src/generate.py:185, README.md:489, handoff/tasks.md:85
- **문제:** 재가동 예약은 오류 주입 전 행 수로 계산하고 나중에 오류 행을 끼운다. 최종 CSV에서는 공개한 “30행 뒤”보다 늦게 재가동한다. 정상 행만 센다는 설명은 없다.
- **근거:** P12의 기본 재가동 설정·시드 42·500개에서 최종 CSV의 (정지 행, 재가동 행, 사이 행 수)는 LEAK-2 (1571,1603,31), LEAK-2 (1895,1928,32), FINAL-1 (3964,3997,32)다. 예정 행 수에 도달한 뒤에도 다음 제품 행이 들어간다. 정상 생성 단계에서는 사이 행 수가 30이다. 명세는 판정의 물리 행 순서를 정하고 재가동 지연에서도 “행 수”라고만 하므로 거절된 주입 행을 제외하는 별도 기준은 공개되지 않았다. 모호한 입력 단위와 실제 설명의 불일치로 중간이며, 최종 물리 행 기준이라고 확정해 코드 변경을 단정하지 않는다.
- **제안:** 정상 생성 행만 세는 의도라면 그 단위를 명세·README·평가 조건에 명확히 공개하고 승인된 해석으로 기록한다. 최종 CSV 물리 행이 기준이라면 오류 삽입을 포함해 재가동 일정을 지키고 영향을 받는 평가 결과를 다시 산출한다.

### L1 — 현행 명세의 변경 금지 문구가 역할 교체 기록과 충돌한다 (기록만)

- **심각도: 낮음**
- **파일:줄:** handoff/tasks.md:152, handoff/setup-notes.md:53, tools/review-loop.ps1:1
- **문제:** 현행 명세는 자동 루프·검수 규칙을 바꾸지 말라고 하지만 같은 범위에서 역할 교체를 위해 루프·AGENTS·CLAUDE·설정이 바뀌었다.
- **근거:** 사용자 결정 기록은 5단계부터 구현 Claude·검수 Codex를 승인하고 이번 사용자 요청 역시 Codex 검수다. 따라서 이 교체를 무조건 미승인 기능 변경으로 간주하지 않는다. 다만 명세 문구는 그 예외를 반영하지 않았다.
- **제안:** 역할 교체는 허용된 변경이고 영향 기준·반례 절차는 유지한다는 뜻으로 문서의 경계를 정리할 수 있다. 낮음이므로 수정 요구로 세지 않는다.

## 3. 보존 조건과 기대표 대조

| 확인 항목 | 실제 확인 | 판정 |
| --- | --- | --- |
| src/rules.py·기존 테스트 6개 무수정 | 지정 범위 diff에 수정·삭제 없음. tests에는 새 파일 2개만 추가 | 충족 |
| 기존 레시피·생성 설정·샘플·seed42 산출물 무수정 | recipes/data/reports diff는 새 파일만 추가 | 충족 |
| 기존 테스트 무수정 통과 | 기존 108개를 포함한 전체 134개 실제 실행·통과 | 충족 |
| 기존 샘플 4종 보고서 | 임시 폴더 재생성, 13개 바이트 비교(P09) | 충족 |
| seed42 CSV·meta·보고서 | CSV·meta와 보고서 7개(기존 6개 + 이번에 추가한 GEN_0030 trace) 바이트 비교(P09) | 충족 |
| 재가동 없는 모든 합법 입력의 보존 | 합법적 공정명 EQUIP_RESTART 반례(P07) | **불충족 H1** |
| 생성기 버전 | 기존 1.1.0 유지, restart 설정만 1.2.0. P09·P10 및 기존 테스트 확인 | 충족 |
| 첫 정지 dict·새 이력 | Analysis.stops 첫 객체 유지, 두 차례 정지 trace가 물리 행 기준으로 분리(P02) | 충족 |
| EquipmentBook 뒤쪽 기본값 필드 | restart_enabled: bool = False가 기존 필드 뒤 | 충족 |
| 저장소 원본 유지 | 검수 중 src/tests/recipes/data/reports 등 추적 파일 diff 없음 | 충족 |

| 기대표 | 기대·실제 대조 |
| --- | --- |
| T52 | 정지→거절→재가동→재입력 허용: 해당 테스트 통과 |
| T53 | 창 초기화·재정지·누적 2/1: 해당 테스트 통과, P02에서 물리 순서·이력도 확인 |
| T54 | 가동 중 재가동 거절·창 유지: 해당 테스트 통과, P01 중복 재가동에서도 상태 불변 |
| T55 | 형식·없는 설비의 6가지 거절·상태 보존: 해당 테스트 통과, P01에 복합 오류 우선순위 추가 |
| T56 | 거절 후 열린 요청 유지, 재가동만으로 제품 보류 해제 안 함: 해당 테스트 통과 |
| T57 | 재검사 FAIL의 정지 창 제외: 해당 테스트 통과 |
| T58 | 이전 모드 거절, 잘못된 flag/예약 공정 오류 3·무보고서: 해당 테스트 통과, P03 대소문자·빈값 확인 |
| T59 | 정지별 summary·재가동 절·당시 원인 trace: 해당 테스트 통과. 제출 재가동 샘플 6개 보고서도 별도 재생성 바이트 동일 |
| T60 | 두 시드·규모의 재현성은 P10에서 CSV·meta·보고서 6종 모두 확인. P13은 42/500의 4,141행·7/200의 1,672행을 전부 재생하고 각 거절 120/48건의 전체 제품·설비 deepcopy 상태 불변 확인 |
| T61 | 0–29 모든 제품 최종 상태·LEAK-2 FIXED 1회 테스트 통과. 예약 중복 방지는 정지 설비 선택 제외·재가동 시 pop 흐름으로 확인. 기존 테스트의 open_stops는 최종 잔량만 검사하므로 시간상 동시 예약 검증과는 구분 |
| T62 | 정탐 1·오탐 1·지연 4·정밀도 0.5000 및 수리 후 오탐 테스트 통과. 다중 고장 해석은 M3 별도 |
| T63 | 검출 1.0000·오탐 실행 25·평균 1.57·전면 정지 14·미완료 10/22/417·정상품 보류 8.50 일치. **전체 보류 13.73은 빠짐(M2)** |
| T64 | 반복 실행 바이트 동일, 잘못된 규칙·시드·중복 규칙 종료 2·무보고서: 해당 테스트 통과 |
| T65 | 후보 제외·동률 순서·후보 없음 테스트 통과. P08에서 반올림 전 임계값·동률 판단 추가 확인 |
| T66 | 확인/미확인·재선택 금지 테스트 통과. --holdout 보고서 selection 없음 |

P13은 먼저 분석 결과를 얻고 모든 행의 두 번째 판정을 대조하며 예상 거절 행 직전에 전체 상태를 deepcopy한다. 실제 판정이 예상과 달라지면 즉시 실패하므로 예상에 없던 거절을 건너뛰지 않는다. 기존 T60 테스트의 상태 불변 검사는 7/60만 대상으로 했으므로 이 검수에서 요구된 두 규모를 보완했다.

## 4. 반례별 입력·예상·실제

파일: handoff/reviews/probes/test_probe_010.py. 출력은 테스트 내부 tempfile에서만 만들었다. 실패 반례는 실제 결함·명세 이견을 드러내도록 실패 상태로 남겼다.

| 번호 | 입력 | 예상·근거 | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | 중복 seq, seq=0·제품 기입·검사 기입·소문자 결과·없는 설비가 겹친 재가동, 수정 후 재가동·즉시 중복 | 형식→없는 설비→가동 상태 순서, 거절 상태 불변(현행 판정 규칙) | 오류 우선순위 일치, 모든 거절 불변, 정상 재가동·다음 검사 허용 | 통과 |
| P02 | 두 차례 정지·재가동, seq 90/2/1 중복·역순 | seq가 아닌 물리 행 기준 trace, 첫 정지 보존 | c는 a;b, f는 d;e, 정지별 거절 각 1개·종료 상태 재가동 | 통과 |
| P03 | restart false/true × event/result/equipment 소문자·빈칸 | 정확한 값 일치, 이전 모드의 product_id 오류 유지, 상태 불변 | 모두 거절·불변, 이전 모드 이유 유지 | 통과 |
| P04 | delay=0, stop rule 1:1, LEAK-2 FAIL 확률 1·나머지 0 | 경계값 허용, 정지 다음 행 재가동·수리 효과 | 정지 1건, 바로 다음 행 FIXED, 정상 행 모두 허용, 예약 잔여 없음 | 통과 |
| P05 | LEAK 설비만 있는 유효 설비 파일, 제품 2개·확률 모두 0 | 복구 불가능한 생성 구성은 명시적 종료 2·무보고서(평가 오류 규약) | 예약 없는 무한 대기, 4초 timeout | **실패 M1** |
| P06 | 고장 2대 중 1대 검출한 실행 1개 | 실행 단위 문구를 한 대 이상 검출로 읽으면 1/1(tasks:107); 여러 대 해석은 명세 이견 | 설비 단위 1/2 | **실패 M3** |
| P07 | 이전 모드·합법 공정 EQUIP_RESTART·시드 42/60 | 기존 흐름·난수·바이트 보존 | 정상 행 동일하지만 오류 삽입 뒤 24행부터 다름 | **실패 H1** |
| P08 | 검출률 0.94999, 지연 10.00001, 오탐 1.004 대 1.003 | 표시 반올림으로 임계·동률 판정을 바꾸지 않음 | 모두 정확한 Fraction 기준 선택 | 통과 |
| P09 | 이전 샘플 4종 + seed42 생성·summary·두 trace | 기존 파일과 바이트 동일 | 보고서 20개 + CSV·meta 동일 | 통과 |
| P10 | 재가동 시드 42/500, 7/200 각각 독립 두 번 | CSV·meta·보고서 동일(T60) | 두 쌍 모두 8개 파일 바이트 동일 | 통과 |
| P11 | baseline 0–29 평가 CLI | T63의 13.73·8.50 모두 출력 | 8.50만 출력, 전체 보류 지표 없음 | **실패 M2** |
| P12 | delay=30·기본 오류 주입 3%·42/500 | 물리 행 기준이라면 사이 행 30을 넘기기 전에 재가동(tasks:85); 정상 행 기준 여부 명세 이견 | 사이 행 31/32/32 | **실패 M4** |
| P13 | 재가동 42/500·7/200 전 행 재생·전체 상태 비교 | 모든 거절이 제품·설비 전체 상태 보존(T60) | 총 5,813행 대조, 168개 거절 모두 불변 | 통과 |

## 5. 실제 테스트 명령과 출력 원문

### 런처 환경과 우회 범위

처음에는 요청된 명령을 그대로 실행했다. 두 명령 모두 종료 코드 1이며 테스트를 수집하지 못했다.

```text
py -m unittest discover -s tests
No installed Python found!

py -m unittest handoff/reviews/probes/test_probe_010.py
No installed Python found!
```

py -0p도 설치된 Python을 찾지 못했지만 기존 C:\Users\PC\anaconda3\python.exe는 Python 3.9.13으로 실행됐다. 검수 코드는 bootstrap_unittest에서 tempfile에 이 실행 파일의 py.exe 복사본과 해당 Python DLL만 두고 자식 프로세스의 PATH·PYTHONHOME을 지정했다. 기존 테스트의 subprocess(["py", ...])도 동일 런타임으로 실행된다. 런처·레지스트리·패키지·원본 테스트를 수정하지 않았고 PYTHONDONTWRITEBYTECODE=1로 pyc 생성을 막았다. 따라서 아래는 **원래 런처 정상 동작의 증거가 아니라 기존 Python 3.9.13에서 원본 테스트를 실행한 결과**다.

실제 실행 셸 명령:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\PC\anaconda3\python.exe' -c "from handoff.reviews.probes.test_probe_010 import bootstrap_unittest; raise SystemExit(bootstrap_unittest(['-m','unittest','discover','-s','tests']))"
```

출력 원문(종료 0):

```text
Temporary py.exe alias -> C:\Users\PC\anaconda3\python.exe
Command: py -m unittest discover -s tests
......................................................................................................................................
----------------------------------------------------------------------
Ran 134 tests in 84.285s

OK
T44 seed=42 products=500 generation_seconds=0.132143 judgment_analysis_seconds=0.079645
T44 seed=7 products=200 generation_seconds=0.053548 judgment_analysis_seconds=0.031936
T44 seed=42 all_rows_deepcopy_invariant_seconds=44.443481
T44 seed=7 all_rows_deepcopy_invariant_seconds=6.687189
```

최종 반례 파일 실행 명령:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\PC\anaconda3\python.exe' -c "from handoff.reviews.probes.test_probe_010 import bootstrap_unittest; raise SystemExit(bootstrap_unittest(['-m','unittest','handoff/reviews/probes/test_probe_010.py']))"
```

출력 원문(종료 1):

```text
Temporary py.exe alias -> C:\Users\PC\anaconda3\python.exe
Command: py -m unittest handoff/reviews/probes/test_probe_010.py
....FFF.P09: 20 reports + seed42 CSV/meta byte-identical
.P10: seed=42 products=500 CSV/meta/6 reports byte-identical
P10: seed=7 products=200 CSV/meta/6 reports byte-identical
.FP12 final CSV stop/restart/intervening rows: [('LEAK-2', 1571, 1603, 31), ('LEAK-2', 1895, 1928, 32), ('FINAL-1', 3964, 3997, 32)]
FP13: seed=42 products=500 all 4141 rows replayed, 120 rejected full states unchanged
P13: seed=7 products=200 all 1672 rows replayed, 48 rejected full states unchanged
.
======================================================================
FAIL: test_p05_missing_inspection_equipment_must_terminate (handoff.reviews.probes.test_probe_010.Probe010)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_010.py", line 172, in test_p05_missing_inspection_equipment_must_terminate
    result = cli(directory, "src.evaluate", "--config", directory / "config.json",
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_010.py", line 78, in cli
    return subprocess.run([sys.executable, "-m", module, *map(str, arguments)], cwd=directory,
  File "C:\Users\PC\anaconda3\lib\subprocess.py", line 507, in run
    stdout, stderr = process.communicate(input, timeout=timeout)
  File "C:\Users\PC\anaconda3\lib\subprocess.py", line 1134, in communicate
    stdout, stderr = self._communicate(input, endtime, timeout)
  File "C:\Users\PC\anaconda3\lib\subprocess.py", line 1510, in _communicate
    raise TimeoutExpired(self.args, orig_timeout)
subprocess.TimeoutExpired: Command '['C:\\Users\\PC\\AppData\\Local\\Temp\\review010-runtime-jlxjshfg\\py.exe', '-m', 'src.evaluate', '--config', 'C:\\Users\\PC\\AppData\\Local\\Temp\\tmpgsiidv5c\\config.json', '--products', '2', '--seeds', '0-0', '--rules', '3:2', '--out', 'missing']' timed out after 4 seconds

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_010.py", line 175, in test_p05_missing_inspection_equipment_must_terminate
    self.fail("Valid equipment subset leaves generator waiting forever without any pending restart (4 s timeout)")
AssertionError: Valid equipment subset leaves generator waiting forever without any pending restart (4 s timeout)

======================================================================
FAIL: test_p06_multiple_faults_detection_rate_is_per_run (handoff.reviews.probes.test_probe_010.Probe010)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_010.py", line 183, in test_p06_multiple_faults_detection_rate_is_per_run
    self.assertEqual(actual, 1, "One of one runs detected faulty equipment; spec denominator is runs, not equipment-runs")
AssertionError: Fraction(1, 2) != 1 : One of one runs detected faulty equipment; spec denominator is runs, not equipment-runs

======================================================================
FAIL: test_p07_legacy_step_named_restart_preserves_generation (handoff.reviews.probes.test_probe_010.Probe010)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_010.py", line 208, in test_p07_legacy_step_named_restart_preserves_generation
    self.assertIsNone(mismatch, "Restart disabled, valid legacy process ID changes generated CSV at row %s" % mismatch)
AssertionError: 24 is not None : Restart disabled, valid legacy process ID changes generated CSV at row 24

======================================================================
FAIL: test_p11_t63_total_held_average_is_reported (handoff.reviews.probes.test_probe_010.Probe010)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_010.py", line 272, in test_p11_t63_total_held_average_is_reported
    self.assertIn("13.73", text, "T63 requires both total held mean 13.73 and normal held mean 8.50")
AssertionError: '13.73' not found in 'rule | runs | detection_rate | mean_delay | stop_precision | mean_false_stops | false_stop_runs | full_outage_runs | unfinished_min | unfinished_median | unfinished_max | mean_normal_held | mean_defective_completed | criteria\r\n3:2 | 30 | 1.0000 | 11.97 | 0.3896 | 1.57 | 25 | 14 | 10 | 22.0 | 417 | 8.50 | 0.13 | 미확인\r\n생성 데이터의 확률은 가정이며 실제 설비 진단 근거가 아니다.\r\n기준 충족 규칙 없음\r\n저장 파일: reports/baseline_rules.csv, reports/baseline_runs.csv\r\n' : T63 requires both total held mean 13.73 and normal held mean 8.50

======================================================================
FAIL: test_p12_delay_rows_after_error_insertion (handoff.reviews.probes.test_probe_010.Probe010)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_010.py", line 288, in test_p12_delay_rows_after_error_insertion
    self.assertTrue(all(gap[3] <= config["restart"]["delay_rows"] for gap in gaps),
AssertionError: False is not true : A due restart must precede the next product row; error insertion delays it: [('LEAK-2', 1571, 1603, 31), ('LEAK-2', 1895, 1928, 32), ('FINAL-1', 3964, 3997, 32)]

----------------------------------------------------------------------
Ran 13 tests in 12.423s

FAILED (failures=5)
```

반례는 작성 도중 10개(3실패, 7.206초), 12개(5실패, 11.825초)를 실행했고 경고 제거·요구 규모 보완 후 위 최종 13개를 실행했다. 실패 예상값을 실제에 맞춰 바꾸거나 expectedFailure로 숨기지 않았다. 전체 원본 테스트는 코드 변경이 없어 재실행을 늘리지 않았다.

## 6. 평가 보고서·Claude 의견 대조

저장된 개발 600행·홀드아웃 100행·기존 설정 100행의 실행별 지표를 읽고 규칙별 집계를 다시 계산했다. 집계 CSV 전체 행과 설정·레시피·설비 SHA-256이 일치했다. 다음 표는 이 재집계 확인 결과이며 이번 검수에서 800개 조합을 모두 다시 생성했다는 뜻은 아니다.

| 규칙(개발 0–99) | 검출률 | 지연 평균 | 오탐 평균 | 정밀도 | 전면 정지 실행 | 기준 |
| --- | --- | --- | --- | --- | --- | --- |
| 3:2 | 1.0000 | 9.71 | 1.90 | 0.3448 | 3 | 충족·선택 |
| 5:2 | 1.0000 | 7.84 | 3.49 | 0.2227 | 6 | 충족 |
| 5:3 | 1.0000 | 19.77 | 0.14 | 0.8772 | 0 | 지연 초과 |
| 10:3 | 1.0000 | 11.31 | 0.89 | 0.5291 | 0 | 지연 초과 |
| 10:4 | 1.0000 | 17.40 | 0.07 | 0.9346 | 0 | 지연 초과 |
| 20:4 | 1.0000 | 13.64 | 0.51 | 0.6623 | 0 | 지연 초과 |

- **동의:** 사전 고정 기준에서 3:2 선택. 반례 P08로 반올림 경계도 확인했고 저장 실행값 재집계도 같은 규칙을 선택했다.
- **동의:** 제출 홀드아웃은 검출률 1.0000·지연 8.47로 “확인”이고 selection 절이 없다. --holdout 추가는 재선택 방지 목적에 부합하며 해당 CLI 테스트도 통과했다. 선택 규칙이 기준 규칙과 같을 때 3:2,3:2 대신 3:2만 실행하는 것은 T64의 중복 금지와 양립한다.
- **동의:** 제출 보고서 기준으로 재가동 유무 비교 시 전면 정지 49→3, 미완료 최대 417→26, 결함품 완료 평균 0.16→0.30이다. README가 결함품 완료 증가의 원인을 추론으로 구분한 점도 타당하다. 인과 설명 자체는 이번 검수에서 미검증이다.
- **부분 동의:** 기존 테스트 6개·기존 기본 산출물 보존 주장은 diff·P09로 확인했다. 모든 이전 합법 구성까지 보존한다는 일반화는 H1 때문에 불가하다.
- **부분 동의:** T52–T66 “모두 통과”는 테스트 실행 결과로는 맞지만 명세 전체 충족을 뜻하지 않는다. T63은 M2가 남고 기존 T60 테스트는 meta·보고서 재현성과 요구된 두 규모의 상태 불변을 충분히 검사하지 않아 P10·P13으로 보완했다.
- **동의:** summary 정지 상태를 “재가동/정지”로 구분한 해석은 P02와 제출 샘플에서 일관되고 정지 시점별 원인이 보존된다.
- **명세 이견:** 고장 여러 대의 지연 단위 해석은 구현 로그에 있지만 검출률 단위까지 확정한 근거는 없다(M3). 오류 주입 전 행 수만으로 점검 소요를 재는 해석도 공개되지 않았다(M4).
- 검수 조건: 생성 확률·점검 소요·수리 효과는 합성 가정이다. 저장된 수치의 계산 일치는 실제 공정 개선 효과의 검증이 아니다.

미검증 범위: 개발·홀드아웃·기존 설정 800개 조합의 전체 재생성, 자동 루프의 다음 수정·커밋 단계, 원래 Windows py 런처의 설치 인식 복구. 이는 구현 결함과 구분했다. 이번 검수에서 원본 수정·커밋·푸시·패키지 설치·저장소 파일 삭제는 수행하지 않았다.

VERDICT: FIX
