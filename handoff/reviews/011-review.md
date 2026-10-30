검수 모델: gpt-6.1-sol

# 리뷰 011 — 리뷰 010 수정 재검토

검수일: 2026-10-31. 검수 HEAD: dc4ebb1f3a770e1efcf2524c64c0ff48b170e33b.

**PASS. 이전 높음 1건·중간 4건 모두 해결. 새 미해결 높음·중간 0건.** 기존 낮음 L1은 기록만 유지하며 수정 요구로 세지 않는다.

전체 테스트는 실제 수집·실행 1회, **138개 통과(97.989초)**다. 이번 반례·보존 검증 **11개도 모두 통과(2.769초)**했다. 원래 Windows `py` 런처는 설치 인식에 실패했으므로 아래 실행 환경과 실제 명령을 함께 기록한다.

## 1. 범위와 기준

- 지정 diff: `git diff 2bed3d6083149355195b1648b6477dea715c694d..HEAD`. 같은 범위의 커밋과 작업 트리 diff도 확인했다.
- 커밋: 699b333(010 수정), b1b1149(평가 산출물 재생성), 2657e88(재검토 모델·FIX 후 재개), dc4ebb1(M3·M4 결정 기록).
- 판정 기준: `handoff/tasks.md` 맨 위 현행 명세·T52–T66와 아래 완료 단계의 보존 조건. M3·M4는 `handoff/decisions.md:59–60`의 명시적 승인으로 모호성을 해소했다. 기대표는 바꾸지 않았다.
- 배경·이전 주장: setup-notes.md, tasks.md, gpt-log.md의 구현·수정 기록, decisions.md, 010-review.md를 대조했다. 이전 docs 문서를 현행 기준으로 사용하지 않았다.
- `practical-work-operation`은 범위 보존·검증 조율에만 적용했다. 사용자 지시에 따라 플러그인 리뷰 스킬과 보조 에이전트를 사용하지 않았다. docs/solutions 및 .compound-engineering/config.yaml은 없었다.
- 시작 시 추적 파일의 미커밋 변경은 없고 `handoff/loop-logs/011-codex.txt`만 이미 미추적 상태였다. 이번 작성 대상은 이 리뷰와 `probes/test_probe_011.py`뿐이다. 생성·CLI 출력은 테스트 안의 tempfile에서만 만들었다. 이전 반례 파일은 실행하지 않았다.

## 2. 이전 높음·중간 항목별 판정

| 항목 / 심각도 / 파일:줄 | 문제와 수정 | 재검증 근거 | 판정·제안 |
| --- | --- | --- | --- |
| H1 / 높음 / src/generate.py:146 | 이전 모드의 합법적인 공정명 EQUIP_RESTART까지 오류 주입 후보에서 제외하던 분기에 restart_enabled 조건을 추가 | P01: 해당 공정을 앞·중간·끝에 넣고 시드 7·42, 각 60개 생성. 4단계 기준 400081f의 Generator를 메모리에 읽어 정상 행·오류 삽입 후 전 행·종류별 개수·최종 RNG 상태를 비교한 6개 조합 전부 동일. 기존 테스트 추가분도 통과 | **해결.** Claude의 모드 한정 수정에 동의. 추가 수정 요구 없음 |
| M1 / 중간 / src/generate.py:65 | 영구적으로 없는 검사 설비와 일시 정지 설비를 구분하지 못해 무한 대기하던 경우에 ValueError 추가 | P03: LEAK 설비만 있는 구성에서 generate·evaluate 모두 LIGHT 설비 부재를 설명하며 종료 2, 파일 미생성. P02: 비활성 모드의 같은 구성은 기존 생성 결과 유지. P04: 존재하는 설비의 정지는 delay 0·1·100에서도 대기·재가동 후 5개 전부 완료 | **해결.** 무한 대기 방지와 이전 모드 보존 주장에 동의. 추가 수정 요구 없음 |
| M2 / 중간 / src/evaluate.py:39, src/evaluate.py:97, src/evaluate.py:195 | 누락됐던 전체 보류 held·mean_held를 실행·집계·CSV·터미널 표에 추가 | 전체 테스트의 T63은 기존 지표와 함께 보류 13.73·정상품 보류 8.50 확인. P05는 보류·폐기·완료·검사 대기를 섞어 전체 보류 2·정상품 보류 1 및 두 실행 평균 1.00·0.50 확인. P06은 거절·재가동이 보류 집계를 지우지 않음을 확인. P11은 저장된 새 열과 집계를 대조 | **해결.** 누락 지표 추가와 완료 보고 정정에 동의. 후속 재생성 커밋도 확인했으므로 앞선 로그의 재생성 미수행 상태는 해소됨 |
| M3 / 중간·명세 이견 / src/evaluate.py:89, src/evaluate.py:148 | 검출률을 실행 수 분모로 계산하고, 단위가 미정인 다중 고장 설정을 평가에서 거절 | decisions.md:60이 이 처리 방식을 승인. README.md:501에 종료 2 제한 공개. P07: 두 고장 항목의 확률이 0이어도 선언된 고장 설비가 두 대면 이전·재가동 두 모드 모두 종료 2·무보고서. P08: 고장 0대는 빈 검출률, 한 대 미검출은 0이며 지연은 빈 값·후보 없음. 추가 회귀 테스트 통과 | **해결.** 다중 고장에 대한 임의 지표를 외부 평가 결과로 내지 않는 승인된 제한에 동의. 추가 수정 요구 없음 |
| M4 / 중간·명세 이견 / README.md:489, handoff/decisions.md:59 | 정상 생성 행 기준 delay_rows와 최종 CSV 물리 행 간격 차이를 공개 | decisions.md:59에서 오류 주입 전 정상 생성 행 기준을 명시적으로 승인. P09: 시드 42·500개에서 정상 행 간격 [30,30,30], 오류 삽입 후 [31,32,32]로 README의 공개 설명과 일치 | **해결.** 코드를 바꾸지 않는 근거는 수정 비용이 아니라 사용자 결정과 관측된 동작의 일치다. 추가 수정 요구 없음 |

위 동의는 이번 반례를 실행한 뒤 내린 판정이다. M3·M4를 Claude의 설명만으로 승인된 것으로 취급하지 않았으며, 별도 사용자 결정 기록을 확인했다.

## 3. 새 지적과 기존 낮음 기록

새 높음·중간 지적은 없다.

- **낮음 / handoff/tasks.md:152 / 문제:** 검토 루프·규칙 변경 금지 문구는 역할 교체·재검토 모델 변경을 반영하지 않은 채 남아 있다(010 L1의 문서 경계 문제).
- **근거:** 역할 교체는 decisions.md:58에 승인 기록이 있고, 이번 사용자는 gpt-6.1-sol 재검토·반례 범위·테스트 1회 조건을 직접 지정했다. 해당 모델·절차 사용을 미승인 코드 동작으로 판정하지 않는다.
- **제안:** 추후 문서를 정리할 때 승인된 검토 운영 변경과 제품 기능 변경의 경계를 명시할 수 있다. 동작에 영향 없는 기존 낮음 기록이며 수정 요구 수에는 포함하지 않는다.

## 4. 반례 입력·예상·실제·판단

파일: `handoff/reviews/probes/test_probe_011.py`. P01–P09는 이번 수정 및 승인된 해석에 집중한 명세 밖 입력·경계 반례이고, P10–P11은 보존 확인이다.

| 반례 | 입력 | 예상 및 명세 근거 | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | 재가동 비활성, EQUIP_RESTART 공정을 앞·중간·끝에 삽입, 시드 7·42, 제품 60개 | 현행 보존 조건 및 restart 없는 난수 소비 보존: 이전 생성기와 전 행·주입 개수·RNG 동일 | 6개 조합 모두 동일 | 통과, H1 재발 없음 |
| P02 | 재가동 비활성, LEAK-1만 존재, FAIL·결함·주입 0, 제품 4개 | 부재 설비 오류 분기는 재가동 대기에만 적용. 이전 모드는 기존처럼 진행 가능한 행까지만 생성 | 4단계 기준과 정상·최종 행 동일 | 통과, M1 수정의 이전 모드 회귀 없음 |
| P03 | 재가동 활성, LEAK-1만 존재, seed 0·제품 2개, generate와 evaluate CLI | 없는 LIGHT 설비는 재가동으로 생기지 않음. 생성 실패는 종료 2·출력 미생성 | 두 CLI 모두 원인 메시지·종료 2, CSV·meta·reports 없음 | 통과, M1 해결 |
| P04 | 검사별 설비 1대, LEAK-1 확실한 고장, 규칙 1:1, 지연 0·1·100, 제품 5개, 재검사 확률 1 | 존재하는 정지 설비는 오류가 아니라 대기·교착 방지·FIXED 수리 후 재개 | 각 조건에서 재가동 1회, 모든 행 허용, 5/5 완료, 예약 잔량 0 | 통과, 부재 설비 방어가 정상 대기를 막지 않음 |
| P05 | 보류 정상 a·보류 결함 b·폐기 결함 c·완료 d·검사 대기 e 및 빈 실행 | 전체 보류는 현재 보류만 세며 폐기·대기는 미완료에만 포함. 평균은 실행 수 분모 | 미완료/전체 보류/정상품 보류 4/2/1, 두 실행 평균 1.00/0.50, runs의 held [2,0] | 통과, M2 집계·출력 일치 |
| P06 | 정지 뒤 소문자 fixed 거절 → FIXED 허용 → 같은 재가동 중복 거절 → 다른 제품 PASS | 거절은 상태 불변, 재가동은 보류 해제 안 함. 최초 정탐은 유지 | 거절 두 번 모두 전체 제품·설비 불변, 보류/정상품 보류 2/1, 정탐/오탐/검출 1/0/1 | 통과, 새 지표가 거절·재가동에 왜곡되지 않음 |
| P07 | 고장 항목 2개, 각각 FAIL 확률 0, 재가동 활성·비활성 | decisions.md:60은 선언된 다중 고장 설정 자체를 거절 | 두 모드 모두 종료 2·여러 대 메시지·reports 없음 | 통과, M3 제한의 경계 일치 |
| P08 | 고장 목록 빈 값 또는 LEAK-2 한 대 확률 0, 정상 FAIL·결함·주입 0, 시드 0–1 | 분모 대상이 없으면 빈 검출률, 고장 미검출이면 0, 지연 없음, 기준 충족 규칙 없음 | 빈 값/0 구분, 보류 0, 두 실행 모두 지연 빈 값·선택 없음 | 통과, 0대·미검출 경계 일치 |
| P09 | 기본 재가동 설정, 시드 42·500개, 오류 삽입 전후 분석 | decisions.md:59의 승인 단위에서 지연 30. 최종 CSV는 주입 오류만큼 늘 수 있음 | 정상 [30,30,30], 최종 [31,32,32] | 통과, M4 승인 해석과 동일 |
| P10 | 기존 샘플 4종, 기존 설정 seed42 재생성·판정·summary·trace | 이전 단계의 기존 보고서 및 seed42 산출물 바이트 보존 | 보고서 20개와 CSV·meta가 체크아웃 원본과 모두 동일 | 통과 |
| P11 | 개발 600·홀드아웃 100·기존 설정 100행의 저장 평가 보고서 | M2 수정은 새 열 추가이며 기존 지표 불변. normal_held ≤ held ≤ unfinished, mean_held는 실행별 held 평균 | 기존 열 전체 셀·행 순서 보존. 800행 경계 및 규칙별 mean_held 재집계 일치 | 통과. 800개 조합 전체 재생성을 뜻하지 않음 |

## 5. 이전 단계 보존·현재 기대표 확인

| 조건 | 확인 결과 |
| --- | --- |
| 기존 테스트 6개·src/rules.py 무수정 | 지정 diff 및 4단계 기준 400081f..HEAD에서 변경 없음. tests/test_rules.py, test_recipe.py, test_retest.py, test_equipment.py, test_generate.py, test_summary.py 보존 |
| 기존 108개 테스트 통과 | 원본 무수정 상태로 전체 138개에 포함되어 실제 통과 |
| 기존 recipes 3개·샘플·seed42 산출물 무수정 | 이번 diff에서 recipes·data 변경 없음. 4단계 이후 관련 diff도 신규 재가동 파일·신규 trace만 추가 |
| 기존 보고서 동일 | P10에서 기존 샘플 보고서 13개와 seed42 보고서 7개, CSV·meta를 tempfile에 재생성해 바이트 비교 |
| 이전 합법 구성 보존 | P01·P02로 수정된 분기의 공정명·설비 부재 조합을 이전 Generator와 직접 대조 |
| 버전·첫 정지·EquipmentBook 보존 | 해당 구현은 이번 diff에서 변경 없음. 전체 기존 테스트와 P10의 meta 바이트 비교 통과 |
| T52–T59 | 기존 해당 테스트 통과. 판정기·summary·trace는 이번 diff에서 바뀌지 않음. P06에서 거절·재가동·보류 상태 경계 추가 확인 |
| T60–T61 | 기존 해당 테스트 통과. 이번 변경은 부재 설비 방어와 비활성 모드 공정명 후보 처리에 한정. 재가동 전체 행 deepcopy·두 규모의 확장 검증은 010 리뷰의 P10·P13 증거를 재사용하며 이전 반례 파일을 재실행하지 않음 |
| T62–T63 | 해당 테스트 및 추가 회귀 통과. T63 보류 13.73·정상품 보류 8.50 단정 포함. P05–P08에서 새 집계·검출률 경계 확인 |
| T64–T66 | 해당 CLI·선택·홀드아웃 테스트 통과. 새 보류 열은 후보 선정 키에 추가되지 않았고 P11에서 기존 집계·selection 결과 보존 |
| 자동 검토 루프 | 변경된 모델 선택·FIX 재개·생성 프롬프트를 정적으로 대조. 다음 외부 CLI 호출·수정·커밋 단계는 실행하지 않음 |

## 6. 실제 테스트 명령과 출력 원문

### 런처 환경

최초 직접 실행(종료 1, 테스트 수집·실행 없음):

```text
py -m unittest discover -s tests
No installed Python found!
```

`py -0p`도 설치를 찾지 못했으나 기존 `C:\Users\PC\anaconda3\python.exe -V`는 Python 3.9.13이었다. 이번 반례 파일의 bootstrap_unittest가 tempfile에 해당 실행 파일의 py.exe 복사본과 python39.dll을 두고 자식 환경의 PATH·PYTHONHOME을 지정했다. 기존 테스트 내부의 subprocess(["py", ...])도 같은 실행기를 사용한다. 설치·레지스트리·기존 테스트를 변경하지 않았으며 PYTHONDONTWRITEBYTECODE=1로 pyc 생성을 막았다. 이는 원래 런처가 복구됐다는 뜻은 아니다.

### 전체 테스트 — 실제 실행 1회

실제 셸 명령:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\PC\anaconda3\python.exe' -c "from handoff.reviews.probes.test_probe_011 import bootstrap_unittest; raise SystemExit(bootstrap_unittest(['-m','unittest','discover','-s','tests']))"
```

출력 원문(종료 0):

```text
Temporary py.exe alias -> C:\Users\PC\anaconda3\python.exe
Command: py -m unittest discover -s tests
..........................................................................................................................................
----------------------------------------------------------------------
Ran 138 tests in 97.989s

OK
T44 seed=42 products=500 generation_seconds=0.119257 judgment_analysis_seconds=0.069639
T44 seed=7 products=200 generation_seconds=0.053467 judgment_analysis_seconds=0.024983
T44 seed=42 all_rows_deepcopy_invariant_seconds=50.531946
T44 seed=7 all_rows_deepcopy_invariant_seconds=7.572631
```

### 이번 반례·보존 검증

실제 셸 명령:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\PC\anaconda3\python.exe' -c "from handoff.reviews.probes.test_probe_011 import bootstrap_unittest; raise SystemExit(bootstrap_unittest(['-m','unittest','handoff/reviews/probes/test_probe_011.py']))"
```

출력 원문(종료 0):

```text
Temporary py.exe alias -> C:\Users\PC\anaconda3\python.exe
Command: py -m unittest handoff/reviews/probes/test_probe_011.py
P01: 6 legacy-name cases, normal/final rows, counts and RNG state identical
.P02: absent inspection equipment, restart disabled: legacy rows preserved
.P03: missing LIGHT equipment: generate/evaluate exit 2, no generated files
.P04: delay 0/1/100, existing stopped equipment recovers, 5/5 products complete
.P05: mixed states -> unfinished/held/normal_held=4/2/1; means=1.00/0.50
.P06: lowercase and duplicate restarts rejected without mutation; held remains 2/1
.P07: two declared faults at p=0 rejected in both modes, exit 2/no reports
.P08: zero faults -> blank rate; one undetected fault -> 0; held=0/no selection
.P09: approved normal-row gaps=[30, 30, 30]; final-CSV gaps=[31, 32, 32]
.P10: 20 reports plus seed42 CSV/meta byte-identical to checkout
.P11: 800 stored runs: all old cells preserved; held bounds/means agree
.
----------------------------------------------------------------------
Ran 11 tests in 2.769s

OK
```

## 7. Claude 의견과 검증 한계

- H1·M1의 수정 방향과 기존 모드 보존 주장에 동의한다. 기본 샘플만이 아니라 P01–P04의 비표준 공정명·설비 부재·지연 경계로 확인했다.
- M2의 누락 인정 및 새 지표 보완에 동의한다. 후속 재생성으로 기존 열 값은 유지되고 새 열이 저장돼 있다. P11은 이 보존과 집계 일치를 확인한 것으로, 개발·홀드아웃 800개 조합을 이번에 모두 재생성했다는 주장은 하지 않는다.
- M3·M4의 최초 보류 사유만으로 해결 처리하지 않았다. 후속 사용자 결정 두 건과 P07–P09, README의 공개 내용이 일치하므로 해결로 처리했다.
- 선택 3:2·홀드아웃 확인 결과는 이번 변경 뒤에도 저장 보고서의 기존 셀과 동일하다. 실제 설비 개선·진단 효과의 증거로 확대하지 않는다.
- 미검증: 원래 Windows py 런처의 설치 인식 복구, 자동 루프의 다음 외부 실행·커밋, 평가 800개 조합 전체 재생성. 이번 diff에 대한 미해결 코드 지적으로 간주하지 않는다.
- 소스·기존 테스트·설정·데이터·보고서 원본을 수정하지 않았다. 커밋·푸시·패키지 설치·저장소 파일 삭제를 수행하지 않았다. 별도 교훈 문서는 만들지 않았다.

VERDICT: PASS
