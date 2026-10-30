# 현행 작업: v2 7a단계 — 측정값 판정과 공정능력

상태: **사용자 확정** (2026-10-31). 결정 근거는 `handoff/decisions.md`. 1–6단계(아래 명세)는 완료이며, 그 동작과 테스트는 보존한다.

## 목표와 경계
- PASS/FAIL 입력 대신 합성 측정값을 받아 판정기가 결과를 계산하고, Cpk·Ppk를 공식대로 낸다.
- 분포·규격값은 모두 가상 가정이다. 실제 설비 진단이나 SL 기준이 아니다. 기존 고정 문장을 유지한다.
- 제외: 관리도·WECO 정지 규칙(7b), 생산 중간 고장과 규칙 비교 평가(7c), 정규성 검정, 측정 시스템 분석, 외부 패키지.
- **이 단계에 정지 규칙 선택은 없다.** 정지는 기존 FAIL 기반 규칙 그대로이고, 사전 선택 기준도 두지 않는다.

## 보존 조건
- 측정 레시피를 쓰지 않으면 v1·1–6단계의 입력·출력·종료 코드·난수 흐름은 바이트까지 같다.
- `src/rules.py`와 기존 테스트 파일은 수정하지 않는다. 새 테스트는 `tests/test_measurement.py`에 둔다.
- 기존 설정, 샘플, 평가 보고서는 바꾸지 않는다.
- 생성기 버전은 `process_cpk`가 있는 설정에서만 `1.4.0`이다.

## 모드와 헤더
**측정 모드**는 레시피의 검사 항목에 규격이 있을 때 켜진다. 새 파일은 `recipes/lamp_models_measured.json`이다.

| 레시피 | 설비 파일 | CSV 헤더 |
| --- | --- | --- |
| 규격 없음 | 기존과 같음 | 기존과 같음 |
| 규격 있음 | `lot_tracking` 없음·`false` | `seq,product_id,event,inspection,result,model,equipment,value` (8열) |
| 규격 있음 | `lot_tracking: true` | `seq,product_id,event,inspection,result,model,equipment,lot,value` (9열) |

- 측정 레시피는 `--equipment`가 필수다. 없으면 종료 코드 2다.
- 재가동은 열 추가가 아니라 이벤트이므로 헤더와 무관하다.
- 헤더가 다르면 종료 코드 2다.
- 판정기는 측정 + 로트 9열을 지원한다. 생성기는 이 조합을 지원하지 않는다(「생성 설정 검증」).

## 레시피 규격
검사 항목에 `lsl`, `usl`, `unit`을 추가한다.

```json
{"id": "LEAK", "after": "P2", "lsl": null, "usl": "13.000", "unit": "가상 단위"}
```

위반은 모두 종료 코드 3이며 위치를 표시한다.
- 어떤 검사 항목이든 규격을 쓰면 **레시피의 모든 검사 항목**에 세 키가 다 있어야 한다.
- `lsl`, `usl`은 `null` 또는 문자열 소수다. 형식은 `^-?\d+(\.\d+)?$`이고, 부호와 소수점을 뺀 숫자는 30자리 이하다. 숫자형 JSON, 지수 표기, `NaN`, `Infinity`는 거절한다.
- 둘 다 `null`이면 오류다. 둘 다 있으면 `lsl < usl`이어야 한다.
- `unit`은 공백만 있지 않은 문자열이다.
- **같은 검사 ID는 모델이 달라도 규격과 단위가 같아야 한다.** Cpk 묶음이 하나의 규격을 갖게 하기 위해서다.

## 측정 입력
`INSPECT`에서만 `value`를 쓴다. 형식은 자릿수 상한을 포함해 규격과 같고, `Decimal`로 정확히 비교한다. `13`과 `13.000`은 같은 값이다. 입력값은 반올림하지 않고 원문을 보존한다.

판정: 있는 쪽 규격만 보고 `lsl <= value <= usl`이면 PASS, 아니면 FAIL이다. 경계값은 PASS다. 이 판정은 `src/recipe_rules.py`의 공통 함수 하나로 두고 판정기와 생성기가 함께 쓴다.

| 입력 | 판정 | 이유 문구 | 사유 코드 |
| --- | --- | --- | --- |
| `INSPECT`의 `result` 기입 | `RULE_PRESERVE` 거절 | `측정 모드의 INSPECT result는 빈칸이어야 함` | `PRESERVE_RESULT_FIELD` |
| `INSPECT`의 value 빈칸·형식 오류 | `RULE_PRESERVE` 거절 | `value는 소수 형식이어야 함` | `PRESERVE_BAD_VALUE` |
| `INSPECT` 외 행(재가동 포함)의 value 기입 | `RULE_PRESERVE` 거절 | `INSPECT 이외의 value는 빈칸이어야 함` | `PRESERVE_VALUE_FIELD` |

- 재가동의 `result`(`FIXED`, `NO_FAULT`)는 그대로다. `RETEST_REQUEST`의 `result` 빈칸 규칙도 그대로다.
- 검사 순서: 열 구조 → `seq` → `lot` → value 기입 위치 → 측정 `result` 빈칸 → value 형식 → 그 뒤는 기존 순서.
- 재검사도 `INSPECT`이므로 같은 규칙을 쓴다.

## 판정 결과 전달
- `RecipeProcess.apply`는 입력 행을 바꾸지 않는다.
- `Decision`에 `result`(이 행에서 확정된 결과)와 `value`(입력 원문)를 추가한다. 비측정 모드와 재가동 행의 `result`는 입력값이고, 측정 모드의 허용된 `INSPECT`는 계산값, 거절된 `INSPECT`는 빈칸이다.
- `InspectionRecord`와 제품 이력 객체 `InspectionAttempt`에 `value`를 추가하고, `result`는 `Decision.result`에서 받는다. summary, trace, 설비 집계, 생성기 재생이 모두 이 값을 쓴다.
- rows 입력 표시: `INSPECT LEAK PASS @LEAK-1 value=12.300`. 거절된 행은 원문 value를 그대로 보이고 결과는 비운다.
- trace는 측정 모드에서만 `value,lsl,usl` 열을 끝에 추가한다.
- history 표기는 측정 모드에서 `PASS@12[LEAK-1](value=12.300)`이다.

## 공정능력 (`--capability`)
측정 모드에서만 쓴다. 아니면 종료 코드 2다. `reports/<입력>_capability.csv`를 쓴다.

- **대상**: `(검사, 설비)`별 허용된 **최초 측정**의 물리적 행 순서. 재검사 측정은 제외한다.
- **구간**: 그 설비의 허용된 재가동에서 끊는다.
- **부분군**: 구간 안에서 연속 5개씩 묶는다. 구간 끝의 5개 미만은 부분군에서 뺀다. 여러 구간의 완성 부분군은 합친다.
- `Xbarbar`: 부분군 평균의 평균. `Rbar`: 부분군 범위의 평균.
- `sigma_within = Rbar / 2.326`
- `Cpk = min(USL − Xbarbar, Xbarbar − LSL) / (3 × sigma_within)`. 단측이면 있는 쪽만 쓴다. 평균이 규격 밖이면 음수로 표시한다.
- `Ppk`: 대상 전체(부분군에서 뺀 값 포함)의 평균 `m`, 표본 표준편차 `s`(분모 `N−1`)로 `min(USL − m, m − LSL) / (3 × s)`.
- 계산은 `Decimal` 정밀도 100자리로 한다. 계산 중에는 표시 자리수로 양자화하지 않으며, 표시용 `sigma_within`을 Cpk 계산에 다시 쓰지 않는다.

계약은 둘로 나눈다.
- **계산 함수**는 항목마다 `Decimal` 또는 `None`을 돌려준다. `None`은 계산할 수 없는 항목이다.
- **표시 함수**는 `Decimal`을 문자열로, `None`을 빈칸으로 바꾼다. 지수 표기 없는 소수 넷째 자리 `ROUND_HALF_UP`이고, 정밀도 100자리 문맥에서 양자화한다. 표시 결과가 영이면 부호 없이 `0.0000`이다.
- 표본 기준과 `status`는 보고 단계에서만 붙인다.

| 입력 | `xbarbar`, `rbar`, `sigma_within` | `sample_sd` | `cpk` | `ppk` |
| --- | --- | --- | --- | --- |
| `n` 0 | 없음 | 없음 | 없음 | 없음 |
| `n` 1 | 없음 | 없음 | 없음 | 없음 |
| `n` 2 이상, 부분군 0개 | 없음 | 값 | 없음 | `s > 0`이면 값 |
| 부분군 1개 | 값 | 값 | 없음 | `s > 0`이면 값 |
| 부분군 2개 이상 | 값 | 값 | `sigma_within > 0`이면 값 | `s > 0`이면 값 |

보고서의 `status`와 빈칸은 다음과 같다. 위 표에서 없음이면 항상 빈칸이고, 나머지 통계 열은 어떤 상태에서도 계산된 값을 쓴다.

| `status` | 조건 | 값 |
| --- | --- | --- |
| `표본 부족` | 완성 부분군 25개 미만 | `cpk`, `ppk` 빈칸 |
| `변동 없음` | 25개 이상이고 `sigma_within = 0` 또는 `s = 0` | 분모가 0인 값만 빈칸. `Rbar = 0 < s`면 `cpk`만 빈칸 |
| `계산됨` | 그 밖 | 값 표시 |

`계산됨`은 산술 계산이 가능하다는 뜻이다. 25부분군은 이 프로젝트의 표시 기준이며 안정성이나 정규성을 뜻하지 않는다.

열: `section,inspection,equipment,unit,lsl,usl,n,subgroups,xbarbar,rbar,sigma_within,cpk,sample_sd,ppk,status,value`
- 첫 행은 `section=notice`로 고정 문장과 함께 "구간을 합친 값이며 안정 공정의 능력을 보증하지 않는다"를 적는다. 고장·수리 구간을 합친 수치를 공정 능력 보증으로 읽지 않게 하기 위해서다.
- 검사 ID → 설비 ID 순으로 정렬한다. 측정이 0건인 설비도 `표본 부족`으로 한 행을 쓴다.

## 생성기
새 파일 `recipes/generator_measured.json`, `recipes/equipment_measured.json`(재가동 설비, `lot_tracking` 없음).

- `lamp_models_measured.json`은 `lamp_models_retest.json`의 공정·`retest_limit`에 규격만 더한다.
- `equipment_measured.json`은 `equipment_restart.json`과 내용이 같다.
- `generator_measured.json`은 `generator_restart.json`의 `model_weights`, `defective_product_probability` 0.02, `retest_probability` 0.70, `error_rate` 0.03, `restart.delay_rows` 30을 그대로 쓰고 아래 3개 키를 더한다.

| 키 | 값 | 뜻 |
| --- | --- | --- |
| `process_cpk` | 1.33 | **정상품·정상 설비 성분**의 목표 공정능력 |
| `fault_shift_sigma` | `{"LEAK-2": 2.5}` | 수리 전 고장 설비의 평균 이동량. 고장 설비 목록은 이 키다 |
| `defect_shift_sigma` | 5.0 | 결함품 평균 이동량 |

생성식 (검사마다, 재검사도 새로 추출). 생성식은 `float`로 계산하고 규격은 `float`로 바꿔 넣는다.

```text
c = (lsl + usl) / 2
σ = (usl − lsl) / (6 × process_cpk)
평균 = c + (shift_defect + shift_fault) × σ
측정값 = gauss(평균, σ)
```

- `shift_defect`는 결함품이면 `defect_shift_sigma`, 아니면 0이다. `shift_fault`는 수리 전 고장 설비면 그 값, 아니면 0이다. 두 이동은 더한다.
- 이동은 모두 **+ 방향**이다. 수리 뒤 `shift_fault`는 0이다.
- 생성값은 소수 셋째 자리 `ROUND_HALF_UP`이다. 이 반올림은 생성기에만 쓴다. 변환은 정밀도 100자리 문맥의 `Decimal(repr(x)).quantize(Decimal("0.001"), ROUND_HALF_UP)` 하나로 고정한다. `Decimal(x)`로 바꾸지 않는다. 결과는 지수 표기 없는 문자열이고, 영이면 부호를 뺀다.
- 재검사 확률, 모델 비율, 재가동 지연은 기존 키를 쓴다. 판정기에는 결함 여부를 주지 않는다.

### 생성 중 판정
검사 한 건은 다음 순서로 처리한다.

1. `gauss`로 뽑는다.
2. 소수 셋째 자리로 확정한다. 이후에는 이 문자열만 쓰고 원래 실수는 버린다. 예: `13.0004`는 `13.000`이 되어 PASS다.
3. 공통 판정 함수로 결과를 계산한다.
4. 그 결과로 제품 진행, 재검사 요청, 설비 창, 정지와 재가동 예약을 처리한다.
5. CSV에는 `result` 빈칸과 확정 `value`를 쓴다.

- `Generator.normal_events`는 측정 모드에서 `row["result"]` 대신 계산 결과로 설비를 기록한다.
- 측정 모드의 고장 설비 목록은 `fault_shift_sigma`의 키다. `Generator.product`의 확률 분기와 `add_restart`의 `FIXED` 판별이 이 키를 쓴다.
- `inject_errors`의 재생 결과는 생성 중 설비·제품 상태와 같아야 한다. 정상 행이 거절되면 기존처럼 종료 코드 2다.

### 생성 설정 검증
측정 설정은 `process_cpk`가 있는 설정이다. 다음은 모두 파일을 만들기 전에 종료 코드 2다.

- 측정 레시피에 `process_cpk`가 없거나, 비측정 레시피에 `process_cpk`가 있음. 측정 설정은 값이 잘못돼도 측정 설정으로 본다.
- `fault_shift_sigma`나 `defect_shift_sigma` 없음, 또는 `process_cpk` 없이 둘 중 하나가 있음.
- 측정 설정에 허용 키 밖의 키가 있음. 허용 키는 `recipe`, `equipment`, `model_weights`, `defective_product_probability`, `retest_probability`, `error_rate`, `restart`, `process_cpk`, `fault_shift_sigma`, `defect_shift_sigma`다. 따라서 `normal_fail_probability`, `defective_fail_probability`, `faulty_equipment`, `faulty_detection_loss`, `lot_size`, 결함 로트 키, `defective_shift_sigma` 같은 오기는 모두 거절된다.
- 설비 파일의 `lot_tracking: true`, 또는 `restart` 설정 없음.
- 레시피에 `retest_limit` 없음.
- 단측 규격. 생성 설정의 규격은 **모두 양측**이어야 한다. 단측 규격은 판정기만 지원한다.
- `fault_shift_sigma`가 객체가 아니거나, 키가 설비 파일에 없는 설비임. 빈 객체는 허용한다.
- `process_cpk`와 이동량이 유한한 양수가 아님. bool은 거절한다.
- 레시피 규격에서 계산한 `σ`나 이동 합을 더한 평균이 유한하지 않음.
- 생성 중 확정 문자열이 value 자릿수 상한(30자리)을 넘음. 판정할 수 없는 값을 쓰지 않기 위해서이며, 이때도 파일을 만들지 않는다.
- `defective_product_probability`, `retest_probability`, `error_rate`가 없거나 0–1 값이 아님.

버전과 오류 주입 목록은 이 검증을 통과한 모드로 고른다.

### 가정의 FAIL 확률
규격 7–13에서 목표 σ는 `0.751879…`이다. 아래는 반올림 전 정규분포 값이며 최초 투입 기준이다.

| 성분 | 평균 이동 | FAIL 확률 |
| --- | ---: | ---: |
| 정상품·정상 설비 | 0σ | 약 0.0066% |
| 결함품·정상 설비 | +5σ | 약 84.38% |
| 정상품·고장 설비 | +2.5σ | 약 6.81% |
| 결함품·고장 설비 | +7.5σ | 약 99.98% |

결함품 2%를 섞은 FAIL률은 정상 설비 약 1.69%, 고장 설비 약 8.67%다. 뒤 검사는 앞에서 보류·폐기된 제품이 빠지므로 이 비율을 그대로 쓸 수 없다. `process_cpk` 1.33은 정상품·정상 설비 성분의 값이므로, 보고서의 Cpk·Ppk가 1.33과 다른 것만으로 구현 오류라고 판단하지 않는다.

### 오류 주입
측정 모드의 5종은 다음과 같다. 주입 행은 항상 `result`가 빈칸이다.

| 코드 | 주입 행 | 예상 거절 |
| --- | --- | --- |
| `SEQ_SKIP` | 미래 공정 | `RULE_SEQ` |
| `PRESERVE_BAD_VALUE` | `value=abc` | `RULE_PRESERVE` |
| `PRESERVE_DUP_RESULT` | 결과가 있는 검사를 정상값으로 재입력 | `RULE_PRESERVE` |
| `EQUIP_UNKNOWN` | `LEAK-9`, 정상값 | `RULE_EQUIP` |
| `RECIPE_UNKNOWN_STEP` | B 제품 `P5` | `RULE_RECIPE` |

기존 후보 조건은 유지한다. 정상 가동 설비, 중복 결과, 열린 재검사 요청, 재가동 행 제외가 해당한다. 측정 사유 3종의 문구·코드 대응은 측정용 주입 목록과 따로 등록한다.

`src/reason_codes.py`에 측정용 목록을 추가한다. `src/main.py`의 meta 검증은 두 목록 중 입력 모드에 맞는 쪽만 허용하고, summary의 주입 대비 절도 같은 목록을 쓴다.

## 평가
`py -m src.evaluate`에 측정 설정을 주면 7c 전까지 종료 코드 2다. 7a는 `--capability`만 낸다.

## 사전 기대표 (확정. 구현 결과에 맞춰 바꾸지 않는다)
공통: 규격 7~13, 재검사·재가동 켬, 3:2 정지 규칙. 제품은 B 모델로 P1~P2를 마친 상태다. T96–T100과 T110–T112는 함수 호출이며(T112②는 생성 호출), `n`은 값 개수다.

| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T89 | 값 `13`, `13.000`, `7`, `13.001`, `6.999` (제품별 한 건) | PASS, PASS, PASS, FAIL, FAIL. FAIL 제품은 보류. 입력 원문 보존 |
| T90 | value ① 빈칸 ② `abc` ③ `NaN` ④ `Infinity` ⑤ `1e1` ⑥ `+1` ⑦ 숫자 31자리 | 모두 `PRESERVE_BAD_VALUE`, 제품·설비 상태 불변 |
| T91 | ① `INSPECT`에 `result=PASS`, value 정상 ② `result=PASS`, value 빈칸 ③ P1에 value 기입 ④ 재가동에 value 기입 + `FIXED` ⑤ 정지 설비의 value 없는 정상 재가동 `FIXED` | ①② `PRESERVE_RESULT_FIELD` ③④ `PRESERVE_VALUE_FIELD` ⑤ 허용 |
| T92 | 레시피 오류: ① `lsl >= usl` ② 둘 다 null ③ 숫자형 lsl ④ `"NaN"` ⑤ 일부 검사만 규격 ⑥ unit 공백 ⑦ 모델별 LEAK 규격 다름 ⑧ `usl` 숫자 31자리 | 모두 종료 코드 3, 위치 표시, 보고서 미생성 |
| T93 | 헤더: ① 측정 + 8열 ② 측정 + 로트 + 9열 ③ 측정 + 7열 ④ 측정 레시피에 `--equipment` 없음 ⑤ 비측정 + value 열 | ①② 허용 ③④⑤ 종료 코드 2 |
| T94 | 단측: USL 13만, 값 −50, 13, 13.001. LSL 7만, 값 6.999, 7, 1000 | PASS, PASS, FAIL. FAIL, PASS, PASS |
| T95 | 측정 FAIL 제품의 재검사: 값 14 → 요청 → 값 10 | 재검사 PASS, 보류 해제. 재검사는 설비 창에 불산입. history에 두 값 표시. summary의 최초 FAIL은 1건 |
| T96 | 부분군 [9,10,11,10,10], [10,11,9,10,10], 규격 7~13 | `Xbarbar` 10.0000, `Rbar` 2.0000, `sigma_within` 0.8598, `Cpk` 1.1630, `s` 0.6667, `Ppk` 1.5000 |
| T97 | T96 + 나머지 값 12 (n=11) | 부분군 2개 유지, `Cpk` 1.1630, `s` 0.8739, `Ppk` 1.0750 |
| T98 | T96 값, 단측. ① USL 13 ② LSL 7 | 둘 다 `Cpk` 1.1630, `Ppk` 1.5000 |
| T99 | 부분군 [14,15,16,15,15], [15,16,14,15,15], 규격 7~13 | `Cpk` −0.7753, `Ppk` −1.0000 |
| T100 | 부분군 [8,10,12,10,10], [10,12,8,10,10], 규격 7~13 | `Rbar` 4.0000, `Cpk` 0.5815, `Ppk` 0.7500 |
| T101 | CLI. LEAK-1에서 서로 다른 제품의 최초 검사 `10,10,10,10,10,14,14` → 7번째에서 정지 → 재가동 `FIXED` → 다른 제품 8개의 최초 검사 값 전부 `10` | 재가동 전 부분군 1개 + 나머지 2개 제외, 재가동 뒤 부분군 1개 + 나머지 3개 제외. 부분군 2개(끊지 않으면 3개가 되므로 구분됨), `n` 15, `xbarbar` 10.0000, `rbar` 0.0000, `sample_sd` 1.4075, `status` `표본 부족`, `cpk`·`ppk` 빈칸 |
| T102 | 재검사 측정이 섞인 입력 | 재검사 값은 `n`과 부분군에 없음 |
| T103 | CLI, 재가동 없음. 한 설비의 최초 검사: ① `[9,10,11,10,10]` 24회 ② 같은 값 25회 ③ `10` 125개 ④ 측정 0건 설비 ⑤ `[9]×5` 13회 뒤 `[11]×5` 12회 | ① `표본 부족`, `n` 120, 부분군 24, `rbar` 2.0000, `cpk`·`ppk` 빈칸 ② `계산됨`, `Cpk` 1.1630, `s` 0.6350, `Ppk` 1.5748 ③ `변동 없음`, `cpk`·`ppk` 빈칸 ④ `표본 부족`, `n` 0, 통계 열 모두 빈칸 ⑤ `변동 없음`, `rbar` 0.0000, `cpk` 빈칸, `s` 1.0032, `Ppk` 0.9835 |
| T104 | ① 비측정 입력에 `--capability` ② `--capability`와 `--summary --containment` 함께 | ① 종료 코드 2 ② 허용, 각 보고서 생성 |
| T105 | 측정 설정, 시드 42·500개와 7·200개를 두 폴더에서 생성하고 `--summary --containment --capability --trace GEN_0005`로 판정 | CSV·meta·보고서 전체 바이트 동일. 정상 행 전부 허용. 버전 `1.4.0`. CSV에 결함 정보 없음. 결함 여부는 판정에 쓰이지 않음. **시드 42·500개**에서 완료·보류·폐기 제품, 재검사 요청, 설비 정지, 재가동(`FIXED`)이 각 1건 이상이고 capability에 `계산됨` 행이 1개 이상 |
| T106 | 측정 설정, 시드 0–29, 제품 500개. 시드마다 첫 LEAK-2 `FIXED` 행 앞까지(없으면 파일 끝) 허용된 최초 LEAK 측정을 LEAK-1·2·3 모두 같은 구간에서 모아 30개 시드를 합산. 정상품은 meta `defective_products`에 없는 제품이며 이 테스트에서만 쓴다 | ① 전체 제품 합산 평균이 LEAK-2 > LEAK-1, LEAK-2 > LEAK-3 ② LEAK-1·LEAK-3의 정상품 값을 합친 표본 표준편차가 0.6767–0.8271 안 ③ ①의 각 설비 표본과 ②의 표본이 30개 이상이며, 미만이면 실패 |
| T107 | 측정 설정의 오류 주입, 시드 42 | 5종 각각 주입 수 1 이상, 주입 수와 실제 거절 수 일치, 사유 코드가 위 표와 같음 |
| T108 | 설정 오류: ① `process_cpk: 0` ② `fault_shift_sigma: {"LEAK-2": -1}` ③ `normal_fail_probability` 함께 사용 ④ 단측 레시피로 생성 ⑤ `py -m src.evaluate`에 측정 설정 ⑥ 측정 레시피 + `process_cpk` 없음 ⑦ 비측정 레시피 + `process_cpk` ⑧ `lot_tracking: true` 설비 ⑨ `fault_shift_sigma: {"LEAK-9": 2.5}` ⑩ `retest_limit` 없는 측정 레시피 ⑪ `defect_shift_sigma` 대신 `defective_shift_sigma` ⑫ `process_cpk: 1e-320` ⑬ 규격 `lsl` `0`, `usl` `1` 뒤 영 29개 | 모두 종료 코드 2, 파일 미생성 |
| T109 | 측정 입력을 `--recipe recipes/lamp_models_measured.json --equipment recipes/equipment_measured.json --summary --trace <제품ID>`로 실행 | 비율은 계산된 결과로 집계. trace에 `value,lsl,usl`. 입력 CSV의 `result` 빈칸이 FAIL률을 바꾸지 않음 |
| T110 | 함수, 규격 7~13. ① 값 없음 ② `[10]` ③ `[9,10,11,10]` ④ `[9,10,11,10,10]` ⑤ `[10]` 10개 ⑥ `[9,10,11,10,10]` 2회, `usl` `1` 뒤 영 29개, `lsl` null ⑦ `[12,13,14,13,13]`, `[13,14,12,13,13.00002]` | ①② 부분군 0, 모든 통계 `None` ③ 부분군 0, `xbarbar` `None`, `Cpk` `None`, `s` 0.8165, `Ppk` 1.2247 ④ 부분군 1, `xbarbar` 10.0000, `rbar` 2.0000, `Cpk` `None`, `s` 0.7071, `Ppk` 1.4142 ⑤ 부분군 2, `sigma_within` 0, `s` 0, `Cpk`·`Ppk` 모두 `None` ⑥ 계산 오류 없음. 표시 함수 결과가 `E`·`e` 없는 넷째 자리 문자열 ⑦ 계산 함수의 `Cpk`, `Ppk`는 0보다 작은 `Decimal`. 표시 함수 결과는 둘 다 `0.0000` |
| T111 | 함수, 규격 7~13, `process_cpk` 1.33, 이동 2.5·5.0, `gauss`를 평균을 그대로 돌려주도록 고정 | 정상품·정상 설비 `10.000`, 정상품·고장 설비 `11.880`, 결함품·정상 설비 `13.759`, 결함품·고장 설비 `15.639`, 정상품·수리된 고장 설비 `10.000` |
| T112 | 확정과 경계. ① 확정 함수에 `1.2345`, `13.0004`, `13.0005` ② `gauss`를 고정해 생성 값이 `13.0004`인 제품과 `13.0005`인 제품을 각각 생성 | ① `1.235`, `13.000`, `13.001` ② 전자는 CSV `13.000`, PASS로 진행하고 설비 창에 PASS 기록. 후자는 CSV `13.001`, FAIL로 처리하고 설비 창에 FAIL 기록. 두 경우 모두 판정기 재생 결과가 생성 중 상태와 같음 |

## 구현 순서
1. **7a-1**: 레시피 규격, 입력·판정, 결과 전달, summary·trace, T89–T95, T109.
2. **7a-2**: 공정능력, T96–T104, T110.
3. **7a-3**: 생성기, 오류 주입, T105–T108, T111, T112.

각각 커밋하고 7a-3 뒤 검수 루프를 한 번 돌린다.

## 구현 시 주의점
- `src/recipe_rules.py`의 `row["result"]`는 INSPECT 처리와 설비 기록 두 곳에서 쓴다. 계산 결과를 지역 변수로 전달한다.
- 재가동 분기는 일반 필드 검사보다 앞에 있다. value 기입 위치 검사를 그보다 먼저 둔다.
- `src/summary.py`의 검사 경로만 `event["result"]`를 `decision.result`로 바꾸고, 비측정 모드 출력은 같아야 한다. 재가동 이력 경로(`summary.py:85`)의 `FIXED`·`NO_FAULT`는 검사 결과가 아니므로 일괄 교체하지 않는다.
- `_decision`을 거치는 정상·거절·재가동 경로 모두 새 필드를 채운다.
- `src/recipe.py`는 규격 필드, 허용 키, 모델 생성 세 곳을 함께 고친다. 일부 키만 있는 규격을 비측정으로 처리하지 않는다.
- `src/trace.py`는 행 생성, CSV 헤더, 터미널 출력, 재검사 비활성 모드의 history 경로를 모두 고친다.
- `Generator.inject_errors`의 `PRESERVE_BAD_RESULT` 경로는 측정 모드에서 쓰지 않는다.
- `random.Random.gauss`는 내부에 다음 값을 보관한다. 같은 시드의 재현성에는 문제없지만, 호출 순서가 바뀌면 값이 달라진다.

## 산출물
- `src/capability.py`, `src/recipe.py`, `src/recipe_rules.py`, `src/reason_codes.py`, `src/recipe_reports.py`, `src/summary.py`, `src/trace.py`, `src/generate.py`, `src/evaluate.py`, `src/main.py`
- `recipes/lamp_models_measured.json`, `recipes/equipment_measured.json`, `recipes/generator_measured.json`, 샘플 `data/sample_events_measured.csv`와 보고서, `reports/gen_measured_seed42_*`
- `tests/test_measurement.py`, README 「측정값과 공정능력 (v2 7a단계)」 절

## 완료 보고 (반드시 포함)
- 실행 명령과 출력 원문, 전체 테스트 결과, T89–T112 기대·실제 대조
- 시드 42의 설비별 Cpk·Ppk 표와 해석의 한계
- 시드 42의 경로별 건수(완료·보류·폐기·재검사·정지·재가동·오류 5종). 0건이 있으면 시드나 확률을 바꾸지 않고 명세 이견으로 공개한다
- 명세와 다르게 구현한 부분, 또는 "명세 이견" 항목

## 사용자 결정
| 항목 | 확정 값 | 왜 사용자 결정인가 |
| --- | --- | --- |
| 정상 공정 Cpk | 1.33 | 정상품·정상 설비의 FAIL률이 약 0.0066%가 되어 기존 2%와 크게 다름 |
| 고장 이동량 | 2.5σ | 고장 설비의 정상품 FAIL 확률이 약 6.8%. 독립 가정에서 100검사 안 정지 확률이 정상품만으로 약 55%라 기존 FAIL 기반 정지가 늦어짐 |
| 결함 이동량 | 5.0σ | 결함품의 FAIL 확률이 약 84% |
| 규격 값 | LEAK·LIGHT·FINAL 모두 7~13 양측 | 합성 값. 단위는 `가상 단위` |
| 표본 기준 | 완성 부분군 25개 | 500개 생성 시 설비당 검사가 LEAK 약 166건, FINAL 약 125건 이하라 FINAL 등 일부 설비는 `표본 부족`일 수 있음 |

# v2 6단계 명세 (완료, 2026-10-31 · 리뷰 013 PASS)

상태: **사용자 확정** (2026-10-31). 결정 근거는 `handoff/decisions.md`. 1–5단계(아래 명세)는 완료이며, 그 동작과 테스트는 보존한다.

## 목표와 경계
- 설비가 멈췄을 때 **이미 PASS로 지나간 제품 중 어디까지 의심할지**를 뽑고, 방식별 포착률과 격리량을 비교한다.
- 격리는 **분석 보고서**다. 제품 상태, 보류, 재검사를 바꾸지 않는다.
- 분포·확률은 모두 가상 가정이다. 실제 설비 진단이나 SL 기준이 아니다. 기존 고정 문장을 유지한다.
- 제외: 측정값, 관리도, 실제 시각, 생산 중간 고장, 자동 격리, 외부 패키지. 측정값 관련 내용은 7단계에서 따로 명세한다.

## 왜 생성 가정을 바꾸는가
- 기존 결함품은 설비와 무관하게 FAIL 90%, PASS 10%다. 고장 때문에 **더 놓치는** 효과는 모델링되어 있지 않다.
- 현행 설정(고장 FAIL 30%, 결함 2%, 추가 미검출 50%)은 간이 계산에서 실행당 유출이 약 0.11건으로 비교가 성립하지 않는다.
- 그래서 **미세 고장**으로 바꾼다. 아래 값의 간이 계산은 첫 정지까지 약 46검사, 실행당 유출 약 1.26건, 유출 있는 실행 약 56%다. 이 수치는 고장 설비 1대만 본 독립 추정이며 실제 시드 결과가 아니다.

## 보존 조건
- `lot_tracking`이 없거나 `false`이면 v1·1–5단계의 입력·출력·종료 코드·난수 흐름은 바이트까지 같다.
- `src/rules.py`와 기존 테스트 8개 파일(`test_rules`, `test_recipe`, `test_retest`, `test_equipment`, `test_generate`, `test_summary`, `test_restart`, `test_evaluate`)은 수정하지 않는다. 새 테스트는 `tests/test_containment.py`에 둔다.
- 기존 설정 파일, 샘플, `eval_dev`·`eval_holdout`·`eval_baseline` 보고서는 바꾸지 않는다.
- 생성기 버전은 `lot_size`가 있는 설정에서만 `1.3.0`이다. 그 밖의 설정은 기존 버전을 유지한다.

## 모드와 헤더
| 설비 파일 `lot_tracking` | CSV 헤더 | products 열 |
| --- | --- | --- |
| 없음 또는 `false` | 기존 7열. 8열이면 종료 코드 2 | 기존과 같음 |
| `true` | `seq,product_id,event,inspection,result,model,equipment,lot`. 7열이면 종료 코드 2 | `model` 뒤에 `lot` |

- bool 외의 값은 종료 코드 3이다.
- `--equipment` 없이는 로트 모드를 쓸 수 없다. `restart_enabled`와는 독립이다.

## 입력 규칙
`REGISTER`에서만 `lot`을 쓴다. 형식은 `^[A-Z0-9_-]+$`이며 대소문자를 정리하지 않고 비교한다.

검사 순서: 열 구조 → `seq` → `lot` → 그 뒤는 기존 순서. 재가동 행도 같은 순서를 쓰므로, `lot`이 잘못되면 다른 오류가 함께 있어도 `lot` 사유로 거절한다.

| 입력 | 판정 | 이유 문구 | 사유 코드 |
| --- | --- | --- | --- |
| `REGISTER`의 lot 빈칸·형식 오류 | `RULE_PRESERVE` 거절 | `lot이 비어 있거나 형식이 잘못됨` | `PRESERVE_BAD_LOT` |
| `REGISTER` 외 행(재가동 포함)의 lot 기입 | `RULE_PRESERVE` 거절 | `REGISTER 이외의 lot은 빈칸이어야 함` | `PRESERVE_LOT_FIELD` |

이미 등록된 제품을 다른 lot으로 다시 등록하면 기존처럼 `이미 등록된 제품`으로 거절하며 lot은 바뀌지 않는다.

## 격리 보고서 (`--containment`)
`--equipment`가 있을 때만 쓴다. 없으면 종료 코드 2다. 전체 입력 처리 뒤 `reports/<입력>_containment.csv`를 쓴다.

**대상**: 정지 S의 설비 E에서, S 행 이전(S 행 포함)에 `(제품, 검사)` 기준 허용된 **최초 검사 PASS**를 받은 제품이다.
- 재검사 PASS는 대상이 아니다.
- 다른 검사로 보류·폐기된 제품도 포함한다. 불량이 물리적으로 지나갔는지를 보기 때문이다.
- 모든 방식은 **정지 시점까지의 행만** 본다.

**구간**: E에 대해 **허용된** 가장 최근 `EQUIP_RESTART` 다음 행부터 S까지다. 없으면 입력 시작부터다. 다른 설비의 재가동과 거절된 재가동은 구간을 바꾸지 않는다. 모든 방식은 이 구간을 넘어 거슬러 가지 않는다.

| 방식 | 의심 범위 |
| --- | --- |
| `window` | 정지 창 안의 PASS 제품 |
| `last_10` | 구간 안, S를 포함한 E의 허용 최초 검사 최근 10건 중 PASS 제품 |
| `last_20` | 같은 조건의 최근 20건 중 PASS 제품 |
| `lot` | 구간 안에서 E를 PASS했고, 정지 창의 FAIL 제품들이 속한 로트에 있는 제품. `lot_tracking`이 켜져 있을 때만 |
| `since_restart` | 구간 안에서 E를 PASS한 제품 전체 |

`since_restart`는 그 구간의 유출을 구조적으로 모두 포함한다. 기준선(상한)으로 해석한다.

열: `stop_key,equipment,method,row_index,seq,product_id,lot,final_state`
- `row_index`, `seq`는 E의 최초 PASS 행이다. `final_state`는 입력 전체 처리 후 상태다.
- 정렬은 정지 순서 → 위 표의 방식 순서 → `row_index`다. 물리적 행 순서이므로 `seq` 중복·감소와 무관하다.
- 범위가 없는 정지는 행을 쓰지 않는다. 정지가 없으면 헤더만 쓴다.
- 터미널에는 정지·방식별 건수만 표로 낸다.

## 생성기
새 파일 `recipes/equipment_lot.json`(재가동 설비 + `lot_tracking: true`)과 설정 2개를 만든다. 값은 `generator_restart.json`을 잇고 아래만 다르다.

| 키 | `generator_lot.json` | `generator_lot_clustered.json` |
| --- | --- | --- |
| `faulty_equipment` | `{"LEAK-2": 0.10}` | 같음 |
| `lot_size` | 20 | 같음 |
| `faulty_detection_loss` | `{"LEAK-2": 0.5}` | 같음 |
| `defective_product_probability` | 0.05 | 사용하지 않음 |
| `defective_lot_probability` | 없음 | 0.25 |
| `defective_in_lot_probability` | 없음 | 0.2 |

- 두 설정의 기대 결함률은 모두 5%다.
- lot ID는 등록 순서대로 `LOT-0001`부터 `lot_size`개씩 묶는다.
- `faulty_detection_loss`는 수리 전 고장 설비에서 결함품의 FAIL 확률을 `defective_fail_probability × (1 − loss)`로 낮춘다. 값 0.5면 FAIL 0.45, PASS 0.55다. 재검사에도 같은 식을 쓴다. 수리 뒤에는 기존 0.9로 돌아간다.
- **유출**: 결함품이 수리 전 고장 설비에서 최초 검사 PASS를 받은 경우의 제품이다. 결함 여부와 유출은 CSV에 넣지 않고 판정기에 주지 않는다.
- meta에 `lot_size`, `leaked_products`를 추가한다. 평가는 생성기가 기록한 유출 집합을 쓰고, meta의 값은 그 집합을 정렬해 저장한 것이다.
- `src/main.py`의 meta 검증: `leaked_products`는 비어 있지 않은 문자열 배열 항목만 갖고, 중복이 없고, `defective_products`의 부분집합이어야 한다. `defective_products` 없이 `leaked_products`만 있으면 오류다. 등록 제품 여부는 summary에서 기존 `defective_products`와 같이 확인한다. 위반은 종료 코드 2다.
- 오류 주입 5종은 그대로다. 주입 행의 lot은 빈칸이고, 재가동 행은 기존처럼 후보에서 뺀다.

설정 검증(위반은 생성·평가 모두 종료 코드 2, 파일 미생성):
- `lot_size`는 bool을 제외한 양의 정수다. 마지막 로트는 `lot_size`보다 작을 수 있다.
- `faulty_detection_loss`, `defective_lot_probability`, `defective_in_lot_probability`는 유한한 0–1 값이다.
- `faulty_detection_loss`의 키는 `faulty_equipment`에 있는 설비여야 한다. 없는 설비의 손실은 0이다.
- `lot_size` 없이 `faulty_detection_loss`나 집중 로트 키를 쓰면 오류다. 집중 로트 키는 둘 다 있거나 둘 다 없어야 한다.
- `lot_size`가 있으면 설비 파일의 `lot_tracking`이 `true`여야 한다.

## 평가 (`py -m src.evaluate --containment`)

```powershell
py -m src.evaluate --containment --config recipes/generator_lot.json --seeds 0-99 --rules 3:2 --out eval_lot_dev
py -m src.evaluate --containment --config recipes/generator_lot_clustered.json --seeds 0-99 --rules 3:2 --out eval_lot_clustered_dev
py -m src.evaluate --containment --config recipes/generator_lot.json --seeds 1000-1099 --rules 3:2 --out eval_lot_holdout --holdout --selected-from reports/eval_lot_dev_containment.csv
py -m src.evaluate --containment --config recipes/generator_lot_clustered.json --seeds 1000-1099 --rules 3:2 --out eval_lot_clustered_holdout --holdout --selected-from reports/eval_lot_clustered_dev_containment.csv
```

- 정지 규칙은 3:2로 고정한다. 이 단계는 정지 규칙이 아니라 격리 방식을 비교한다. `--containment`에서는 규칙 목록이 정확히 `3:2` 하나여야 한다.
- 설정에 `lot_size`가 없으면 종료 코드 2다. 고장 설비가 여러 대면 기존처럼 거절한다.
- `--containment --holdout`은 `--selected-from`이 필수다. 개발 보고서의 선택 행과 설정 SHA-256을 읽는다. 파일이 없거나, 선택 행이 없거나, SHA가 다르면 종료 코드 2다.
- 개발에서 선택이 없었으면(표본 부족 또는 기준 충족 방식 없음) 홀드아웃은 `검증할 선택 없음`으로 표시하고 종료 코드 0이다.
- 홀드아웃 보고서는 모든 방식의 지표와 **선택 방식의 최종 판정**을 구분해 쓴다. 판정은 선택 방식에 대해서만 낸다.
- 출력은 `reports/<out>_containment.csv`다. 고정 문장, 설정 SHA-256, 생성기 버전을 함께 기록한다.

### 지표 (전체 합산)
실행 r의 유출 집합을 `E_r`, 방식 m이 그 실행의 모든 정지에서 고른 **고유 제품 합집합**을 `C_m,r`로 둔다. 실행별 비율의 평균은 쓰지 않는다.

| 지표 | 식 |
| --- | --- |
| 포착률 | `Σ|C ∩ E| ÷ Σ|E|` |
| 평균 격리량 | `Σ|C| ÷ 실행 수` |
| 격리 정밀도 | `Σ|C ∩ E| ÷ Σ|C|` |
| 평균 잔류 유출 | `Σ|E − C| ÷ 실행 수` |

- 분모가 0이면 빈칸이다. 함께 전체 실행 수, 유출 있는 실행 수, 유출품 합계, 정지 합계를 표시한다.
- 비율은 소수 넷째 자리, 평균은 소수 둘째 자리 `ROUND_HALF_UP`이다.

### 사전 선택 기준 (결과를 보기 전에 고정)
1. **표본 조건**: 개발 시드에서 유출품 합계 ≥ 30이고 유출 있는 실행 ≥ 20이어야 한다. 미달이면 `평가 표본 부족`으로 끝내고 선택하지 않는다.
2. 포착률 ≥ **0.90**인 방식만 남긴다. 정확히 0.90은 통과다.
3. 평균 격리량이 가장 작은 방식을 고른다. 동률이면 위 표의 방식 순서를 쓴다.
4. 독립·집중 설정을 **각각** 판정한다. 후보가 없으면 `기준 충족 방식 없음`으로 끝내고 기준을 완화하지 않는다.
5. 홀드아웃 시드 1000–1099는 개발에서 선택한 방식이 1·2번 조건을 유지하는지만 본다. 표본 조건 미달도 `미확인`이다. 실패해도 다시 고르지 않는다.

## 사전 기대표 (사용자 확정, 2026-10-31. 구현 결과에 맞춰 바꾸지 않는다)
T68–T74 공통: `lamp_models_retest.json`, 재가동·로트 모드, 3:2 규칙. 제품은 B 모델로 등록하고 P1~P2를 마친 상태다. T70·T71은 제품마다 lot을 달리 쓰지 않아도 되는 사례다.

| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T67 | 신규 제품 z를 B 모델, lot `L1`로 등록 | 허용. products의 `lot`은 L1 |
| T68 | ① lot 빈칸 등록 ② `l-1` 등록 ③ P1 행에 lot 기입 ④ 재가동 행에 lot 기입 ⑤ 재가동 행에 lot 기입 + `result=OK` ⑥ 등록된 제품을 다른 lot으로 재등록 | ①② `PRESERVE_BAD_LOT` ③④⑤ `PRESERVE_LOT_FIELD` ⑥ `이미 등록된 제품`. 모두 제품·설비 상태와 lot 불변 |
| T69 | ① 키 없는 설비 파일 + 7열 ② `lot_tracking: false` + 7열 ③ 키 없음 + 8열 ④ `true` + 7열 ⑤ `"lot_tracking": 1` | ①② 기존 출력과 바이트 동일 ③④ 종료 코드 2 ⑤ 종료 코드 3 |
| T70 | LEAK-1에 a·b·c·d PASS, e·f FAIL | 창은 d·e·f, 정지는 f 행. `window`={d}, `last_10`=`last_20`=`since_restart`={a,b,c,d} |
| T71 | T70 뒤 재가동, g PASS, h·i FAIL | 두 번째 정지의 네 방식 범위는 모두 {g}. 첫 정지 범위는 그대로 |
| T72 | T70에서 a·b·e는 L1, c·d·f는 L2 | `lot`={a,b,c,d} |
| T73 | T70에서 a·b·c·d는 L9, e·f는 L1 | `lot`은 0행. `since_restart`는 {a,b,c,d} |
| T74 | ① PASS 없는 정지(a·b FAIL) ② `--containment`를 `--equipment` 없이 ③ 키 없는 설비 파일로 `--containment` ④ 정지 없는 입력 | ① 0행 ② 종료 코드 2 ③ `lot` 방식 없이 네 방식만 ④ 헤더만 |
| T75 | LEAK-1 최초 검사 PASS 12건 뒤 FAIL 2건 | 최근 10건은 PASS 8건, FAIL 2건. `last_10`은 PASS 5–12번째 8건, `last_20`과 `since_restart`는 12건 전부 |
| T76 | a LEAK FAIL @LEAK-1 → 요청 → a LEAK PASS @LEAK-2. b LEAK PASS @LEAK-2 → P3 → P4 → LIGHT FAIL. 이어서 c·d LEAK FAIL @LEAK-2로 정지 | `since_restart`={b}. a는 재검사 PASS라 제외. b의 `final_state`=보류 |
| T77 | 지표 함수: 실행 1 `E={1..9}`, `C={1..9}`, 실행 2 `E={x}`, `C={}` | 포착률 0.9000, 잔류 평균 0.50. 실행별 평균 0.50이 아님 |
| T78 | 지표 함수: `E={p,q,r}`, `C={p,q,s,t}`, 같은 제품이 두 정지에 든 경우 1회 | 포착률 0.6667, 정밀도 0.5000, 격리량 4.00, 잔류 1.00 |
| T79 | 선택 함수. ①–④는 유출 100건, 유출 실행 50회 고정. 방식별 (포착, 격리량): ① `window` (8999/10000, 1), `since_restart` (9/10, 50) ② `last_10` (9/10, 5), `since_restart` (1/1, 50) ③ `window`와 `last_10` 모두 (1/1, 5) ④ 전부 (1/2, 5). ⑤ 유출 29건·유출 실행 50회 ⑥ 유출 100건·유출 실행 19회 | ① `since_restart` ② `last_10` ③ `window` ④ `기준 충족 방식 없음` ⑤⑥ `평가 표본 부족` |
| T80 | 홀드아웃 판정, 선택 방식 `last_10`. ① 유출 100건, 유출 실행 50회, 포착 91건 ② 같은 표본, 포착 89건 ③ 유출 0건 ④ 유출 100건, 유출 실행 19회, 포착 91건 ⑤ 개발 선택 없음 ⑥ 설정 SHA 불일치 | ① `확인` ②③④ `미확인` ⑤ `검증할 선택 없음`, 종료 코드 0 ⑥ 종료 코드 2. ①–④는 다른 방식을 고르지 않음 |
| T81 | `generator_lot.json`, 시드 42·7, 제품 500·200을 두 번 생성·판정 | CSV·meta·보고서 바이트 동일. 정상 행 전부 허용. meta 버전 `1.3.0`. CSV에 결함 정보 없음. 시드 0–29 합계에서 유출품 1건 이상 |
| T82 | T75 입력(제품 p01–p12 PASS, 재가동 없음)에 평가용 유출 집합 `E={p01, p12}` 지정 | `last_10`은 p12 포착, p01 잔류. `since_restart`는 둘 다 포착 |
| T83 | `generator_lot_clustered.json`, 시드 0–29, 시드마다 제품 500개(로트 25개). 결함 로트는 실제 결함품이 1개 이상인 `(seed, lot)` | 고정 표본의 인수 기준: 결함품 합산 비율 0.03~0.07, 결함 로트 비율 ≤ 0.50. `generator_lot.json`의 결함 로트 비율보다 낮음 |
| T84 | 평가 명령 오류: ① `--rules 3:2,5:2` ② `--rules 5:2` ③ `lot_size` 없는 설정 ④ 고장 설비 2대 ⑤ `--holdout`만 있고 `--selected-from` 없음 | 모두 종료 코드 2, 보고서 미생성 |
| T85 | 같은 평가 명령 두 번 | 보고서 바이트 동일 |
| T86 | LEAK-1에 a PASS → LEAK-2 재가동 허용 → LEAK-1 재가동 거절(가동 중) → b PASS, c·d FAIL | LEAK-1 정지의 `since_restart`={a,b}. 다른 설비 재가동과 거절된 재가동은 구간을 바꾸지 않음 |
| T87 | 설정 값 오류: ① `lot_size: 0` ② `lot_size: true` ③ loss 1.5 ④ 고장 목록에 없는 설비의 loss ⑤ `lot_size` 없이 loss ⑥ 집중 키 하나만 ⑦ `lot_size`가 있는데 `lot_tracking` 꺼짐 | 모두 종료 코드 2, 파일 미생성 |
| T88 | meta `leaked_products`: ① `[""]` ② 중복 ③ `defective_products`에 없는 ID ④ `defective_products` 없음 ⑤ 미등록 제품 | ①–⑤ `--summary`에서 종료 코드 2 |

## 구현 순서
1. **6a**: 입력, 로트 모드, 격리 범위, 보고서, T67–T76, T86.
2. **6b**: 생성기, 평가, T77–T85, T87, T88, 개발·홀드아웃 실행.

두 묶음을 각각 커밋하고, 6b 뒤 자동 검토 루프를 한 번 돌린다. 최초 검수는 `gpt-6-astra`, 재검수는 `gpt-6.1-sol`이다.

## 구현 시 주의점
- `EQUIPMENT_INPUT_COLUMNS`는 생성기·판정기·`_invalid_fields`가 함께 쓴다. 로트 열은 모드로 분기하고, 기존 상수를 바꾸지 않는다.
- `_invalid_fields`의 재가동 분기는 일반 검사보다 앞에 있다. lot 검사를 그보다 먼저 둔다.
- `Generator.product`의 결함 추출과 집중 로트 추출은 같은 난수 흐름을 쓴다. `lot_size`가 없으면 난수 소비가 바뀌지 않아야 한다.
- `summary.py`의 `fail_causes`, `stop_history`를 재사용한다. 정지 전 창은 `EquipmentStop.window`에 있다.

## 산출물
- `src/containment.py`, `src/equipment.py`, `src/recipe_rules.py`, `src/reason_codes.py`, `src/recipe_reports.py`, `src/main.py`, `src/generate.py`, `src/evaluate.py`
- `recipes/equipment_lot.json`, `recipes/generator_lot.json`, `recipes/generator_lot_clustered.json`, 샘플 `data/sample_events_lot.csv`와 보고서, `reports/eval_lot_*`
- `tests/test_containment.py`, README 「격리 범위와 로트 (v2 6단계)」 절

## 완료 보고 (반드시 포함)
- 실행 명령과 출력 원문, 전체 테스트 결과, T67–T88 기대·실제 대조
- 방식별 지표 표(독립·집중), 선택 결과, 홀드아웃 판정, 표본 조건 충족 여부
- 명세와 다르게 구현한 부분, 또는 "명세 이견" 항목

## 사용자 결정 (2026-10-31 확정)
| 항목 | 확정 값 | 왜 사용자가 정했나 |
| --- | --- | --- |
| 포착률 기준 | 0.90 | 격리량과 유출 위험의 판단. 결과를 본 뒤 바꿀 수 없음 |
| 표본 조건 | 유출품 ≥ 30, 유출 실행 ≥ 20 | 평가 성립 여부를 가름 |
| 고장 FAIL 확률 | 0.10 | 5단계 0.30에서 변경. 미세 고장 가정 |
| 결함률 | 0.05 | 5단계 0.02에서 변경. 오탐 정지도 함께 늘어남 |
| 추가 검출 손실 | 0.5 | 유출 규모를 정하는 가정 |
| 로트 크기, 결함 로트 가정 | 20, 0.25, 0.2 | `lot` 방식의 성능을 좌우 |
| 소급 건수 | 10, 20 | 비교 범위 |

# v2 5단계 명세 (완료, 2026-10-31 · 리뷰 011 PASS)

상태: **사용자 확정** (2026-10-30). 결정 근거는 이 명세의 「사용자 결정」 표. 1–4단계(아래 명세)는 완료이며, 그 동작과 테스트는 보존한다.

## 목표와 경계
- 정지만 있고 복구가 없는 3단계 설비 모델에 **점검 후 재가동**을 추가한다.
- "규칙대로 판정하는가"를 넘어 **"이 정지 규칙이 좋은 규칙인가"**를 여러 시드의 수치로 평가한다.
- 정지 규칙 선택 기준은 **결과를 보기 전에 고정**하고, 선택에 쓰지 않은 시드로 다시 확인한다.
- 생성 확률·점검 소요·수리 효과는 모두 심어 놓은 가정이다. 결과는 실제 설비 진단이나 공정 개선의 증거가 아니다. 기존 고정 문장을 유지한다.
- 제외: 실제 시각·UPH·OEE, 공정 설비, 로트 ID, 측정값·Cpk, 그래프, 외부 패키지, 고장이 생산 중간에 시작되는 모델, 재가동 취소.

## 착수 근거 (사전 측정, 목표치 아님)
현행 코드, `recipes/generator.json`, 제품 500개, 시드 0–29 30회를 일회성 스크립트로 측정했다. T63에서 평가 도구로 재현한다.

| 항목 | 값 |
| --- | --- |
| LEAK-2 검출 | 30/30회 |
| 정상 설비가 정지한 실행 | 25/30회, 실행당 평균 1.57대 |
| 한 검사 종류의 설비가 전부 정지한 실행 | 14/30회 |
| 미완료 제품 수(보류·폐기 포함) | 최소 10, 중앙값 22, 최대 417 |
| 보류 제품 평균 / 그중 정상품 평균 | 13.73 / 8.50 |

## 보존 조건 (가장 먼저 지킬 것)
- 설비 파일에 `restart_enabled: true`가 없으면 v1·1–4단계의 동작·출력·종료 코드는 바이트까지 같다.
- `recipes/generator.json`, `recipes/equipment.json`, `recipes/equipment_generated.json`과 기존 샘플·seed42 산출물은 바꾸지 않는다.
- `src/rules.py`와 기존 테스트 6개 파일은 수정하지 않는다. 5단계 테스트는 `tests/test_restart.py`, `tests/test_evaluate.py`에 둔다.
- `GENERATOR_VERSION`은 `1.1.0`을 유지한다. 재가동 설정의 생성에만 새 상수 `RESTART_GENERATOR_VERSION = "1.2.0"`을 meta에 기록한다.
- `Analysis.stops`는 설비별 **첫 정지** dict로 유지한다(기존 테스트 사용). 정지 이력은 새 필드 `stop_history`에 둔다.
- `EquipmentBook` 새 필드는 기본값이 있는 뒤쪽 필드로 추가한다.

## 재가동 모드 켜기
- 설비 파일 최상위에 선택 키 `"restart_enabled": true`를 둔다. 값은 bool만 허용하며, 그 밖의 값은 설비 오류(종료 코드 3)다.
- 새 파일 `recipes/equipment_restart.json`: 설비 목록은 `equipment_generated.json`과 같고 `stop_rule`은 `{"window": 3, "fails": 2}`, `restart_enabled`는 `true`다.
- 재가동 모드에서 레시피 공정 ID가 `EQUIP_RESTART`이면 설비 오류(종료 코드 3)다.

## 입력
CSV는 설비 모드와 같은 7열이다. 새 이벤트 `EQUIP_RESTART`만 추가한다.

```csv
seq,product_id,event,inspection,result,model,equipment
31,,EQUIP_RESTART,,NO_FAULT,,LEAK-1
```

- `result`: `FIXED`(이상 발견·조치) 또는 `NO_FAULT`(이상 없음).
- `equipment`: 필수. `product_id`, `inspection`, `model`: 빈칸.
- 이 이벤트가 있어도 `seq`는 기존처럼 양의 정수이고 물리적 행 순서로 처리한다.

## 판정 규칙
검사 순서: 형식 오류 → 없는 설비 → 가동 중인 설비.

| 입력 | 판정 | 이유 문구 | 사유 코드 |
| --- | --- | --- | --- |
| `product_id` 기입 | `RULE_PRESERVE` 거절 | `EQUIP_RESTART의 product_id는 빈칸이어야 함` | `PRESERVE_RESTART_PRODUCT` |
| `inspection` 또는 `model` 기입 | `RULE_PRESERVE` 거절 | `EQUIP_RESTART의 inspection과 model은 빈칸이어야 함` | `PRESERVE_RESTART_FIELDS` |
| `result`가 두 값 외 | `RULE_PRESERVE` 거절 | `잘못된 재가동 결과 (FIXED 또는 NO_FAULT 필요)` | `PRESERVE_BAD_RESTART_RESULT` |
| `equipment` 빈칸 | `RULE_PRESERVE` 거절 | 기존 `equipment가 비어 있음` | 기존 코드 |
| 없는 설비 | `RULE_EQUIP` 거절 | 기존 `등록되지 않은 설비` | 기존 `EQUIP_UNKNOWN` |
| 가동 중인 설비 | `RULE_EQUIP` 거절 | `가동 중인 설비 재가동` | `EQUIP_NOT_STOPPED` |
| 정지 설비 | `RULE_EQUIP` 허용 | | |

새 사유는 모두 입력 오류로 분류한다. 허용되면 다음만 바뀐다.
- `stopped_at_seq`를 비우고 `recent_results`를 초기화한다. 정지 전 FAIL이 재가동 뒤 창에 남지 않게 하기 위해서다.
- `stop_count`, `restart_count`, `last_restart_result`를 갱신한다. `counted_results`, `fail_count`는 누적을 유지한다.
- 제품 상태는 바꾸지 않는다. 보류 자동 해제, 열린 재검사 요청 소진, 원인 제품 재검사는 없다.
- 재검사 결과가 창에 들어가지 않는 규칙은 그대로다.

`stop_count`는 정지가 일어날 때 늘린다.

## 보고서 (재가동 모드에서만 달라짐)
- rows: `product_id` 빈칸, 입력 `EQUIP_RESTART NO_FAULT @LEAK-1`, 상태 `설비 가동` 또는 `설비 정지`(처리 후 그 설비 상태). 거절인데 없는 설비면 상태 `미등록`.
- equipment.csv: 기존 열 뒤에 `stop_count,restart_count,last_restart_result`를 붙인다.
- summary `equipment_stops`: 정지 1건당 1행, key는 `LEAK-1#1`. 정지가 없는 설비는 기존처럼 key `LEAK-1` 1행.
- summary 새 절 `equipment_restarts`: 기존 열을 그대로 쓴다. key `LEAK-1#1`, `equipment`, `row_index`, `seq`, `state`(FIXED/NO_FAULT). `SUMMARY_COLUMNS`는 바꾸지 않는다.
- trace: `정지된 설비` 거절 행은 **그 행 시점에 유효했던 정지**를 가리킨다. 빈 `product_id`는 추적 대상이 아니며 `--trace ""`는 종료 코드 2다.

## 생성기
새 설정 `recipes/generator_restart.json`: `generator.json`과 같은 값에 아래를 더한다. `equipment`는 `equipment_restart.json`이다.

```json
"restart": {"delay_rows": 30}
```

- `restart` 키가 없으면 기존 생성 흐름과 난수 소비가 그대로다.
- **대기**: 같은 검사 설비가 모두 정지하면 재가동 모드에서는 제품 생성을 끝내지 않고, 그 제품은 다음 라운드에 다시 설비를 고른다.
- **재가동 시점**: 설비가 정지한 시점의 행 수 + `delay_rows`에 도달하면 다음 제품 행을 내기 전에 `EQUIP_RESTART` 행을 넣는다. 둘 이상이면 예정 시점, 설비 ID 순이다.
- **교착 방지**: 한 라운드가 대기만으로 끝나면 가장 이른 재가동 행을 예정 시점과 무관하게 넣는다.
- **이유**: 라운드 단위 지연은 쓰지 않는다. 현재 생성기는 모든 제품이 같은 라운드에 같은 공정으로 움직여 한 라운드가 약 500행이고, 짧은 정지도 한 코호트 전체를 건너뛰게 된다. 이 동시 투입 구조 자체는 이번에 바꾸지 않으며 한계로 공개한다.
- **점검 결과**: 수리되지 않은 고장 설비는 `FIXED`, 그 밖에는 `NO_FAULT`다. 난수를 쓰지 않는다. 점검이 항상 맞다는 가정이며 README에 공개한다.
- **수리 효과**: `FIXED` 뒤 그 설비의 FAIL 확률은 정상 확률이다.
- `inject_errors`는 설비 행을 재생하되 오류 주입 후보로 쓰지 않는다. 재가동 행이 거절되면 생성을 실패시킨다.

## 평가 도구 (`py -m src.evaluate`)

```powershell
py -m src.evaluate --config recipes/generator_restart.json --seeds 0-99 --rules 3:2,5:2,5:3,10:3,10:4,20:4 --out eval_dev
py -m src.evaluate --config recipes/generator_restart.json --seeds 1000-1099 --rules 3:2,<선택 규칙> --out eval_holdout
```

- `--products` 기본값은 500이다. 규칙은 `window:fails`로 쓰며 메모리에서만 덮어쓴다. 범위 검증은 설비 파일과 같다.
- 각 규칙·시드 조합을 판정기까지 끝까지 실행한다. 생성 CSV를 저장소에 남기지 않는다.
- 결함 여부·고장 설비는 평가에서만 쓴다. 판정기에는 전달하지 않는다.
- 오류(잘못된 규칙·시드 범위·생성 실패)는 종료 코드 2이며 보고서를 만들지 않는다.
- 출력: `reports/<out>_runs.csv`(규칙·시드별), `reports/<out>_rules.csv`(규칙별 집계), 터미널 표. 집계 파일 첫 행에 고정 문장을 넣고, 설정·레시피·설비 파일의 SHA-256과 생성기 버전을 함께 기록한다.

### 지표 정의
- **정탐 정지**: 정지 시점에 그 설비가 수리되지 않은 고장 설비인 정지. **오탐 정지**: 그 밖의 정지. 수리 뒤 다시 멈춘 고장 설비도 오탐이다.
- **검출률**: 고장 설비를 정탐 정지한 실행 ÷ 실행 수.
- **검출 지연**: 고장 설비의 첫 정지까지 그 설비가 처리한 허용 최초 검사 수(정지 행 포함). 평균은 검출한 실행만 쓴다.
- **정지 정밀도**: 정탐 정지 ÷ 전체 정지. 분모 0이면 빈칸.
- **오탐 정지 수**: 실행당 평균, 오탐이 1건 이상인 실행 수.
- **전면 정지 실행 수**: 한 검사 종류의 설비가 동시에 모두 정지한 적이 있는 실행 수.
- **미완료 제품 수**: 등록 제품 중 `레시피 모의 흐름 완료`가 아닌 제품 수. 보류·폐기를 포함한다. 최소·중앙값·최대.
- **정상품 보류 평균**, **결함품 완료 평균**(유출).
- 비율은 기존처럼 소수 넷째 자리 `ROUND_HALF_UP`, 평균은 소수 둘째 자리.

### 사전 선택 기준 (결과를 보기 전에 고정)
1. 개발 시드 0–99에서 검출률 ≥ 0.95이고 평균 검출 지연 ≤ 10인 규칙만 후보로 남긴다.
2. 실행당 오탐 정지 평균이 가장 낮은 규칙을 고른다.
3. 동률이면 평균 검출 지연 → 미완료 중앙값 → `window` → `fails` 순으로 작은 쪽을 고른다.
4. 후보가 없으면 "기준 충족 규칙 없음"으로 끝낸다. 기준을 완화하지 않고 사용자에게 보고한다.
5. 홀드아웃 시드 1000–1099는 고른 규칙이 1번 기준을 유지하는지만 확인한다. 실패하면 "미확인"으로 기록하고 그 결과로 다시 고르지 않는다.

평가는 규칙을 제안만 한다. 설비 파일의 `stop_rule` 변경은 사용자 결정이다.

## 사전 기대표 (사용자 확정, 2026-10-30. 구현 결과에 맞춰 바꾸지 않는다)
공통: `lamp_models_retest.json`, `equipment_restart.json`. a~f는 B 모델로 P1~P2까지 완료해 LEAK를 할 수 있는 제품이다.

| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T52 | a LEAK FAIL @LEAK-1 → b LEAK FAIL @LEAK-1 → c LEAK PASS @LEAK-1 → `EQUIP_RESTART NO_FAULT LEAK-1` → c LEAK PASS @LEAK-1 | b에서 정지. 첫 c는 `RULE_EQUIP` 거절(`정지된 설비`). 재가동 허용, 설비 가동. 둘째 c 허용 |
| T53 | T52 뒤 d LEAK FAIL @LEAK-1 → e LEAK FAIL @LEAK-1 | d 뒤 가동(창 초기화 확인). e에서 재정지. `stop_count` 2, `restart_count` 1 |
| T54 | a LEAK FAIL @LEAK-1 → `EQUIP_RESTART NO_FAULT LEAK-1` → b LEAK FAIL @LEAK-1 | 재가동 `RULE_EQUIP` 거절(`가동 중인 설비 재가동`), 창 유지. b에서 정지 |
| T55 | 재가동 행을 각각 ① `LEAK-9` ② `product_id=a` ③ `result=OK` ④ `inspection=LEAK` ⑤ `model=A` ⑥ `equipment` 빈칸으로 입력 | ①은 `RULE_EQUIP`, ②~⑥은 `RULE_PRESERVE` 거절. 위 표의 문구. 모든 제품·설비 상태 불변 |
| T56 | a FAIL·b FAIL로 LEAK-1 정지, a `RETEST_REQUEST LEAK` → a LEAK PASS @LEAK-1 → 재가동 → a LEAK PASS @LEAK-1 | 첫 재검사 `RULE_EQUIP` 거절, 요청 유지. 재가동만으로 a 보류 유지. 재가동 뒤 재검사 허용, a 보류 해제. b는 보류 유지 |
| T57 | T52 뒤 a `RETEST_REQUEST LEAK` → a LEAK FAIL @LEAK-1 → b `RETEST_REQUEST LEAK` → b LEAK FAIL @LEAK-1 | 재검사 FAIL 둘 다 허용, 설비 가동 유지(재검사 불산입) |
| T58 | ① `restart_enabled` 없는 설비 파일로 `EQUIP_RESTART` 행 ② `"restart_enabled": "true"` ③ `1` ④ 재가동 모드 레시피에 공정 `EQUIP_RESTART` | ①은 기존처럼 `RULE_PRESERVE` 거절(`product_id가 비어 있음`), 설비 불변 ②~④는 종료 코드 3, 보고서 미생성 |
| T59 | T53 입력을 `--summary --trace c`로 실행 | `equipment_stops`에 `LEAK-1#1`, `LEAK-1#2`, `equipment_restarts`에 `LEAK-1#1`. c의 거절 행 trace는 a·b가 일으킨 첫 정지를 가리킴. 재가동 행은 입력 오류 파레토에 없음 |
| T60 | 재가동 설정, 시드 42/500개와 7/200개를 각각 두 번 생성·판정 | CSV·meta·보고서 바이트 동일. 정상 행과 재가동 행 전부 허용. meta 버전 `1.2.0`. 모든 행에서 거절 전후 전체 제품·설비 상태 동일 |
| T61 | 재가동 설정, 시드 0–29 | 모든 실행에서 검사 대기·공정 진행 중·등록 제품 0개. 시드마다 LEAK-2 `FIXED` 정확히 1회. 설비당 동시에 대기 중인 재가동 예약은 1건 이하 |
| T62 | 수작업 CSV, 고장 설비 `{LEAK-2}`: LEAK-2 최초 검사 PASS·FAIL·PASS·FAIL → `FIXED` → LEAK-1 FAIL·FAIL | 정탐 1, 오탐 1, 검출 지연 4, 정밀도 `0.5000` |
| T63 | `--config recipes/generator.json --seeds 0-29 --rules 3:2` | 위 사전 측정표와 일치: 검출 1.0000, 오탐 실행 25, 오탐 평균 1.57, 전면 정지 14, 미완료 10/22/417, 보류 평균 13.73, 정상품 보류 평균 8.50 |
| T64 | ① 같은 평가 명령 두 번 ② `--rules 5:6` ③ `--seeds 5-3` ④ `--rules 3:2,3:2` | ① 보고서 바이트 동일 ②③ 종료 코드 2, 보고서 미생성 ④ 중복 규칙도 종료 코드 2 |
| T65 | 고정 지표 표로 선택 함수 호출: ① 검출 0.94 규칙 탈락 ② 지연 11 규칙 탈락 ③ 오탐 평균 동률이면 지연이 짧은 쪽 ④ 전부 탈락 | ①② 후보 제외 ③ 지연이 짧은 규칙 ④ `기준 충족 규칙 없음` |
| T66 | 고정 지표로 홀드아웃 판정: ① 검출 0.96·지연 9 ② 검출 0.93 | ① `확인` ② `미확인`, 다른 규칙을 고르지 않음 |

## 구현 시 주의점
- `summary.py`의 `equipment_windows`는 판정기와 별도로 창을 유지한다. 재가동 때 함께 초기화하지 않으면 정지 원인 행이 틀어진다.
- `_invalid_fields`는 `product_id`와 `model`을 먼저 검사하므로, `EQUIP_RESTART`는 재가동 모드에서만 그보다 앞서 분기해야 위 문구가 나온다.
- `_decision`의 설비 표시는 지금 `INSPECT`에만 붙는다.
- `inject_errors`의 `process.products[row["product_id"]]`는 설비 행에서 `KeyError`가 난다.
- `main.py`의 `product_ids`는 빈 ID를 제외해야 한다.
- `tools/review-loop.ps1`과 검수 규칙은 바꾸지 않는다. 검수는 기존 절차(반례 5개 이상)대로 한다.

## 산출물
- `src/equipment.py`, `src/recipe_rules.py`, `src/reason_codes.py`, `src/recipe_reports.py`, `src/summary.py`, `src/trace.py`, `src/generate.py`, 새 `src/evaluate.py`
- `recipes/equipment_restart.json`, `recipes/generator_restart.json`, 샘플 `data/sample_events_restart.csv`와 보고서, `reports/eval_dev_*.csv`, `reports/eval_holdout_*.csv`
- `tests/test_restart.py`, `tests/test_evaluate.py`
- README 「설비 복구와 정지 규칙 평가 (v2 5단계)」 절. 3단계의 "재가동 제외"는 5단계로 대체됐다고 표시한다.

## 완료 보고 (반드시 포함)
- 실행 명령과 출력 원문, 전체 테스트 결과, T52–T66 기대·실제 대조
- 후보 6개 규칙의 지표 표, 선택 결과와 홀드아웃 판정
- 재가동 없는 기존 설정과 재가동 설정의 비교
- 명세와 다르게 구현한 부분, 또는 "명세 이견" 항목

## 사용자 결정 (2026-10-30 확정)
| 항목 | 확정 값 | 왜 사용자가 정했나 |
| --- | --- | --- |
| 검출 기준 | 검출률 ≥ 0.95 | 결과를 본 뒤에는 바꿀 수 없음 |
| 지연 허용 | 평균 10검사 이하 | 불량 유출 위험과 오탐 사이의 경영 판단. 이 값이 선택 결과를 좌우할 수 있음 |
| 점검 소요 | `delay_rows: 30` | 실제 시간이 아닌 가정값. 대기 제품 수에 영향 |
| 후보 규칙 | 3:2, 5:2, 5:3, 10:3, 10:4, 20:4 | 비교 범위 |
| 재가동 결과 값 | `FIXED`, `NO_FAULT` | 점검 기록을 두 값으로 단순화 |

# v2 4단계 명세 (완료, 2026-10-18 · 리뷰 009 PASS)

상태: **사용자 확정** (2026-10-18). 결정 근거는 `handoff/decisions.md`. **사용자가 이 줄을 "사용자 확정"으로 바꾼 뒤에 구현을 시작한다.**
**수정 1 (2026-10-18, 사용자 확정)**: 리뷰 005–007 H1(시드 42 폐기 0개) 해결을 위해 「결함 제품」 가정과 T51을 추가했다. 그 밖의 명세·기대표는 바꾸지 않았다.
1–3단계(아래 명세)는 완료(리뷰 002–004 PASS)이며, 그 동작과 테스트는 보존한다. 범위 축소 없이 아래 전체를 구현한다.

## 목표와 경계
- 시드를 고정한 생성기로 수백 개 제품의 가상 생산 기록을 만들고, 1–3단계 판정기를 대량 입력에서 **불변식**으로 검증한다.
- 판정 결과를 직행률·최초 FAIL률·파레토로 요약하고, 제품 하나의 판정 근거를 다른 제품이 일으킨 설비 정지까지 거슬러 추적한다.
- 생성 확률(예: LEAK-2 30%)은 **심어 놓은 가정**이다. 생성 데이터의 결과는 실제 설비 고장 진단이나 공정 개선의 증거가 아니다. README와 summary 출력에 이 내용을 고정 문장으로 표시한다.
- 제외: 그래프, 외부 패키지, 헤더·CSV 구문 오류 생성(전체 실행을 중단시키므로), 설비 재가동.

## 보존 조건 (가장 먼저 지킬 것)
- v1·1·2·3단계 동작·출력·테스트는 바뀌지 않는다. `--summary`·`--trace`가 없으면 3단계까지와 완전히 같다.
- `src/rules.py`와 기존 테스트 4개 파일(`test_rules.py`, `test_recipe.py`, `test_retest.py`, `test_equipment.py`)은 수정하지 않는다. 4단계 테스트는 `tests/test_generate.py`, `tests/test_summary.py`에 둔다.
- 기존 샘플 보고서는 다시 만들었을 때 체크아웃된 파일과 같아야 한다.
- 리뷰 004 L1: 설비 모드를 보고서 개수(`len(reports) == 4`)로 추정하는 구조에 summary를 덧붙이지 않는다. summary·trace는 **별도 경로**로 계산·저장하고, 모드는 명시적인 값으로 전달한다. 이 때문에 기존 출력이 바뀌면 안 된다.

## 생성기
- 실행: `py -m src.generate --seed 42 --products 500 --out data/generated/gen_seed42.csv` (기본값: `--seed 42`, `--products 500`, `--config recipes/generator.json`)
- 사용하는 설정: 레시피 `recipes/lamp_models_retest.json`, 설비 `recipes/equipment_generated.json`. 둘 다 `generator.json`에 경로로 적는다.
- 난수는 `random.Random(seed)` 하나만 쓴다. 시각·환경을 쓰지 않는다. **재현 기준은 같은 시드 + 같은 설정 파일 + 같은 생성기 버전**이다. 출력 옆에 `<out>.meta.json`을 쓴다: 시드, 제품 수, 설정·레시피·설비 파일의 SHA-256, 생성기 버전 상수, 생성 행 수, 주입 오류 종류별 개수.
- `recipes/equipment_generated.json`: `stop_rule`은 3단계와 같은 `{"window": 3, "fails": 2}`. 설비는 `LEAK-1`, `LEAK-2`, `LEAK-3`, `LIGHT-1`, `LIGHT-2`, `FINAL-1`, `FINAL-2`. (3단계 `equipment.json`은 바꾸지 않는다.)
- `recipes/generator.json` 기본값:
  | 항목 | 값 |
  | --- | --- |
  | 모델 비율 | A 50%, B 50% |
  | 정상 설비 FAIL 확률 | 2% |
  | 고장 설비 | `LEAK-2`, FAIL 확률 30% |
  | 결함 제품 | 제품의 2% (수정 1). 결함품은 **설비와 무관하게** 모든 검사(최초·재검사)의 FAIL 확률 90% |
  | 재검사 요청 확률 | FAIL이 난 검사마다 70% (나머지는 보류로 남김) |
  | 입력 오류 주입률 | 정상 행 수의 3% (아래 5종에 균등 배분) |
- **정상 흐름 생성**: 제품마다 등록 → 레시피 순서대로 공정 → 각 검사를 `after` 시점 직후에 생성. 제품들은 라운드로빈으로 섞어 한 행씩 진행한다(설비 정지가 다른 제품에 영향을 주도록). 검사 설비는 그 검사를 할 수 있고 **생성기가 아는 한 가동 중인** 설비를 순서대로 돌아가며 고른다.
- **생성기의 설비 인식**: 생성기는 3단계 정지 규칙을 자기가 만든 정상 결과에 똑같이 적용해 정지 설비를 피한다. 같은 검사의 설비가 모두 정지했으면 그 제품은 그 검사에서 멈춘다(검사 대기로 남음). 주입한 오류 때문에 판정기와 생성기의 정지 시점이 어긋날 수 있으며, 이는 허용하고 summary에 그대로 드러낸다.
- **결함 제품 (수정 1, 리뷰 005 H1 결정)**: 제품을 만들 때 같은 난수 흐름으로 2% 확률의 결함 여부를 정한다. 결함품의 검사 FAIL 확률은 90%(설비 확률 대신), 정상품은 지금처럼 설비 확률(정상 2%, LEAK-2 30%)을 따른다. 결함 여부는 CSV에 넣지 않고 판정기에도 알리지 않는다(판정기는 숨은 진실을 모른다). meta.json에 결함품 수와 제품 ID 목록(`defective_products`)을 기록하고, 생성기 버전 상수를 올리고, seed42 산출물을 다시 만든다. main.py의 meta 구조 검사도 이 키(제품 ID 문자열 배열, 중복 불가)를 받아들이고 검증한다.
- **재검사**: FAIL이 나면 70% 확률로 `RETEST_REQUEST` → 재검사 결과(가동 중인 설비, 가능하면 처음 FAIL과 다른 설비)를 만든다. 재검사도 FAIL이면 다시 70%로 요청한다. 상한(2회)에서 FAIL이면 폐기로 보고 그 제품의 생성을 끝낸다. PASS면 남은 공정·검사를 이어서 만든다.
- **입력 오류 5종** (정상 행을 바꾸지 않고 **추가로 끼워 넣는다**. 그래서 오류 하나가 뒤 정상 행의 연쇄 거절을 만들지 않는다):
  1. 순서 건너뜀: 아직 차례가 아닌 미래 공정 행 → `RULE_SEQ`
  2. 잘못된 결과 값: `result=OK` → `RULE_PRESERVE`
  3. 중복 결과: 이미 결과가 있는 검사를 요청 없이 다시 입력 → `RULE_PRESERVE`
  4. 없는 설비: `equipment=LEAK-9` → `RULE_EQUIP`
  5. 레시피에 없는 공정: B 제품에 `P5` → `RULE_RECIPE`
  - 주입 위치·종류는 같은 난수 흐름으로 정한다. 주입률의 분모는 **정상 행 수**이며, 최종 거절률과는 다르다(설비 정지 거절 등이 더해짐). summary에 둘을 따로 표시한다.

## 분석 보고서 (`--summary`)
- 실행: `py -m src.main <CSV> --recipe <레시피> --equipment <설비> --summary` (설비 모드에서만. 아니면 종료 코드 2)
- 전체 입력을 끝까지 처리한 뒤 계산한다. 기존 보고서 4종은 그대로 쓰고, 추가로 `reports/<입력파일명>_summary.csv`와 터미널 표를 낸다. summary.csv는 `section,key,value...` 형식의 긴 표 하나로 아래 절을 모두 담는다.
- **지표 정의**
  - 최초 FAIL률(설비별·검사별) = 허용된 최초 검사 FAIL 수 ÷ 허용된 최초 검사 수. 폐기 제품의 최초 결과도 포함한다. 거절된 검사 행과 미검사는 분모에서 빼고 **별도 건수로 표시**한다.
  - 재검사 포함 FAIL률 = 허용된 모든 검사 FAIL ÷ 허용된 모든 검사. 따로 표시한다.
  - 제품 직행률(FPY) = 모든 필수 검사를 **최초 검사에서 PASS**하고 완료한 제품 수 ÷ 등록된 제품 수.
  - 상태 분포: 완료·보류·폐기·검사 대기·공정 진행 중·등록 제품 수.
  - 비율은 소수 넷째 자리 반올림 문자열(예: `0.0312`), 분모 0이면 빈칸.
- **품질 파레토**: (검사, 설비)별 최초 FAIL 수 내림차순, 같으면 검사 ID → 설비 ID 순. 전체 FAIL 수는 옆 열에 함께 표시.
- **입력 오류 파레토**: 거절 행을 **상세 사유 코드**로 묶어 내림차순(같으면 코드 순). 각 행에 `rule_id`도 표시. 코드는 거절 이유 문구와 1:1로 대응하는 고정 표를 `src/` 안에 두고 README에 싣는다(예: `PRESERVE_DUP_RESULT`, `SEQ_SKIP`, `EQUIP_UNKNOWN`, `RECIPE_UNKNOWN_STEP`, `PRESERVE_BAD_RESULT`). 표에 없는 문구가 나오면 summary 생성을 실패시켜 숨은 사유가 없게 한다.
- **설비 정지 영향**은 입력 오류가 아니므로 별도 절로 낸다: 설비별 정지 여부·정지 행·정지 원인 행들(창 안의 FAIL seq), 정지 뒤 거절된 결과 수.
- **주입 대비 결과**: meta.json이 입력 옆에 있으면 주입 오류 종류별 개수와 실제 사유 코드별 거절 수를 나란히 표시한다(없으면 이 절 생략). meta에 `defective_products`가 있으면 **결함품의 최종 상태 분포**(폐기·보류·완료·그 밖)와 **정상품 중 폐기된 수**를 함께 표시한다. 이 절만 숨은 진실(결함 여부)을 쓰며, 판정·다른 지표에는 쓰지 않는다.
- 고정 문장: "생성 데이터의 확률은 가정이며 실제 설비 진단 근거가 아니다."

## 추적 (`--trace 제품ID`)
- `--summary`와 같은 조건(설비 모드)에서 쓴다. 여러 번 줄 수 있다.
- 전체 입력을 끝까지 처리한 뒤 그 제품의 행만 **물리적 행 순서**로 출력한다(`seq` 중복·감소 허용과 일관). 각 행: seq, 입력, 설비, rule_id, 허용/거절, 이유, 처리 후 상태.
- 마지막에 "현재 상태의 근거": 최종 상태, 미완료 이유, history.
- **다른 제품이 원인인 거절**: 그 제품의 행이 `정지된 설비`로 거절됐으면, 그 설비를 정지시킨 행(정지 행과 창 안의 FAIL 행)의 seq·제품 ID를 함께 출력한다.
- 저장: `reports/<입력파일명>_trace_<제품ID>.csv`. 없는 제품 ID면 종료 코드 2, 보고서 미생성.

## 불변식 검증 (`tests/test_generate.py`)
기본 시드 42·500개 생성 결과와 시드 7·200개 생성 결과 각각에 대해:
1. 같은 시드·설정으로 두 번 생성 → CSV·meta.json 바이트 동일. 그 입력의 보고서 4종·summary·trace도 두 번 실행 시 바이트 동일.
2. 완료 제품은 모든 공정과 모든 필수 검사의 현재 결과가 PASS다.
3. 폐기 제품·정지 설비에는 폐기·정지 행 **뒤로** 허용된 행이 없다.
4. 거절 행 수 = 규칙별 거절 집계 합 = 입력 오류 파레토 합 + 설비 정지 거절 수 + 그 밖의 거절 수(각각 summary에 표시).
5. 거절 행 전후로 모든 제품·설비 상태가 같다(판정기를 행마다 복사·비교하는 검증. 500개에서 느리면 시드 7·200개에만 적용하고 그 사실을 기록).
6. **빈 검증 방지**: 시드 42 결과에 완료·보류·폐기 제품, 정지된 설비, 5종 입력 오류가 **각각 1개 이상** 있어야 한다. 없으면 테스트 실패로 두고, 시드·확률을 몰래 바꾸지 말고 "명세 이견"으로 보고한다.
7. 기존 고정 시나리오 테스트(T1–T41)는 그대로 통과한다.

## 사전 기대표 (초안 – 사용자 확정 전)
| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T42 | 시드 42로 두 번 생성 | CSV·meta.json 바이트 동일, meta에 시드·SHA·버전·주입 개수 기록 |
| T43 | 시드 42와 43 | CSV가 다름 |
| T44 | 시드 42 생성 결과를 summary·불변식 검사 | 불변식 1–6 모두 통과 (수정 1 적용 뒤 기준. 기대값은 바꾸지 않음) |
| T51 | (수정 1) 시드 42 생성 meta와 summary | meta에 `defective_products` 기록, 결함품 수 = 목록 길이. summary 「주입 대비 결과」에 결함품 상태 분포와 정상품 폐기 수 표시. CSV에는 결함 여부 열이 없음 |
| T45 | 고정 소형 입력(직접 작성: 제품 4개, 최초 FAIL 1건, 재검사 PASS 1건, 거절 2건) `--summary` | 최초 FAIL률·재검사 포함 FAIL률·FPY·파레토 값이 손으로 계산한 값과 일치(손 계산값을 테스트에 먼저 적는다) |
| T46 | 3단계 샘플(`sample_events_equipment.csv`) `--summary` | 설비 정지 절에 LEAK-2 정지 행과 원인 FAIL 행이 표시되고, 정지 설비 거절은 입력 오류 파레토에 들어가지 않음 |
| T47 | T46 입력 `--trace` (T34의 p4 제품) | 그 제품의 행만 물리 순서로 출력, `정지된 설비` 거절 행에 LEAK-2를 정지시킨 다른 제품 행 seq 표시 |
| T48 | `--trace` 없는 제품 ID / 설비 모드 아님에 `--summary` | 둘 다 종료 코드 2, 보고서 미생성 |
| T49 | 사유 코드 표에 없는 거절 문구(테스트에서 인위적으로 만든 판정) | summary 생성 실패(숨은 사유 없음) |
| T50 | 기존 샘플 4종을 옵션 없이 실행 | 기존 보고서와 바이트 동일 |

## 산출물
- `src/generate.py`, `src/summary.py`(또는 비슷한 이름), `recipes/generator.json`, `recipes/equipment_generated.json`
- `data/generated/gen_seed42.csv`, `gen_seed42.csv.meta.json`과 그 보고서·summary(`reports/gen_seed42_*.csv`), 대표 제품 trace 1개
- `tests/test_generate.py`, `tests/test_summary.py`, T45용 고정 입력은 `tests/fixtures/`
- README 「생성기·분석·추적」 절: 실행법, 지표 정의, 사유 코드 표, 생성 가정과 한계(고정 문장 포함), 시드 42 결과 요약(실행해서 나온 값만)

## 완료 보고 (반드시 포함)
- 실제로 실행한 명령과 출력 원문(기존 회귀, 4단계 테스트, 생성·summary·trace 실행)
- 기대표·불변식과 실제가 다르면 숨기지 말고 보고. 기대표·기존 테스트·시드·확률을 고쳐서 통과시키지 않는다
- 해석·가정, 명세 이견, 실행 시간(500개 생성·판정·불변식 검사 각각)

---

# v2 3단계 명세 (완료, 2026-10-18 · 리뷰 004 PASS)

## 작업: 검사 설비 이상 감지·정지

상태: **사용자 확정** (2026-10-18). 결정 근거는 `handoff/decisions.md`. **사용자가 이 줄을 "사용자 확정"으로 바꾼 뒤에 구현을 시작한다.**
1·2단계(아래 명세)는 완료(리뷰 002·003 PASS)이며, 그 동작과 테스트는 보존한다.

## 목표와 경계
- 검사 결과마다 어느 검사 설비에서 쟀는지 기록한다. 같은 설비에서 최초 검사 FAIL이 몰리면 **제품이 아니라 설비를 의심**해 그 설비를 정지하고, 이후 그 설비의 결과를 받지 않는다.
- 정지 기준(최근 3건 중 2건 FAIL)은 SPC 관리도의 Western Electric 규칙 중 "연속 3점 중 2점" 패턴을 PASS/FAIL 데이터에 맞게 단순화한 **가상 규칙**이다. 실제 SL 기준이나 통계적 관리한계가 아니다.
- 이번 단계 제외: 설비 재가동·점검 이벤트, 로트 ID, 공정 설비, 정지 원인 FAIL 제품의 자동 재검사 요청, 측정값·관리한계 계산.

## 보존 조건 (가장 먼저 지킬 것)
- v1, 1단계, 2단계의 동작·출력·테스트는 바뀌지 않는다. `--equipment`가 없으면 2단계까지와 완전히 같다.
- `src/rules.py`, `tests/test_rules.py`, `tests/test_recipe.py`, `tests/test_retest.py`는 수정하지 않는다. 3단계 테스트는 `tests/test_equipment.py`에 둔다.
- 기존 샘플 보고서(`reports/sample_events_*.csv`, `_v2_*`, `_retest_*`)는 다시 만들었을 때 체크아웃된 파일과 같아야 한다.

## 실행
- `py -m src.main <입력CSV> --recipe <레시피JSON> --equipment <설비JSON>`
- `--equipment`는 `--recipe`와 함께만 쓴다. 없이 쓰면 종료 코드 2. 재검사 레시피와 함께 쓰면 재검사 규칙도 그대로 적용된다.
- 기본 설비 파일: `recipes/equipment.json`

## 설비 파일 형식
```json
{
  "stop_rule": {"window": 3, "fails": 2},
  "equipment": {
    "LEAK-1": "LEAK",
    "LEAK-2": "LEAK",
    "LIGHT-1": "LIGHT",
    "FINAL-1": "FINAL"
  }
}
```
- `equipment`: 설비 ID → 그 설비가 할 수 있는 검사 ID. 설비 ID 형식은 `^[A-Z][A-Z0-9_-]*$`.
- 검증 오류(레시피와 같이 모든 오류 표시, 종료 코드 3): 허용하지 않은 키, `window`·`fails`가 정수가 아니거나(`true` 불가) `1 ≤ fails ≤ window ≤ 20`을 어김, `equipment`가 비어 있음, 설비 ID 형식 위반, 레시피 어느 모델에도 없는 검사 ID를 가리킴.

## 입력 (설비 모드 CSV, 7열)
`seq,product_id,event,inspection,result,model,equipment`
- `equipment`는 `INSPECT` 행에만 필수. 다른 행에서는 빈칸.
- `--equipment`를 줬는데 헤더가 7열이 아니거나, 주지 않았는데 7열이면 CSV 헤더 오류(종료 코드 2).

## 규칙
- 신규 `RULE_EQUIP`: 설비 관련 거절. 거절 집계는 기존 규칙 뒤에 `RULE_EQUIP`를 붙인다(재검사 모드면 8개, 아니면 7개).
- **정지 판정**: 설비마다 **허용된 최초 검사 결과**만 순서대로 센다(재검사 결과·거절 행은 세지 않음). 어떤 행을 허용한 뒤 그 설비의 최근 `window`건 중 FAIL이 `fails`건 이상이면 그 설비를 정지한다. **정지를 일으킨 행 자체는 허용**하고 제품 결과에도 반영한다. 정지는 실행이 끝날 때까지 유지된다.
- **INSPECT 행의 설비 검사** (형식·미등록·폐기·레시피 검사 다음, 검사 시점 검사 전):
  | 조건 | 결과 |
  | --- | --- |
  | 설비 파일에 없는 설비 | 거절 `RULE_EQUIP` (`등록되지 않은 설비`) |
  | 그 검사를 할 수 없는 설비(예: `LIGHT-1`로 LEAK) | 거절 `RULE_EQUIP` (`검사 종류가 다른 설비`) |
  | 정지된 설비 | 거절 `RULE_EQUIP` (`정지된 설비`). 최초 검사든 재검사든 같음. **열린 재검사 요청은 소진되지 않는다** |
- 형식 오류: `INSPECT`의 `equipment` 빈칸, 다른 행의 `equipment` 기입 → `RULE_PRESERVE`.
- 상태 불변: 거절 행은 제품 상태·검사 이력·열린 요청·재검사 횟수·설비 기록·정지 여부를 바꾸지 않는다.

## 보고서 (설비 모드)
- 기존 3종에 더해 `reports/<입력파일명>_equipment.csv`: `equipment,inspection,counted_results,fail_count,state,stopped_at_seq` (설비 파일 순서, state는 `가동`/`정지`, 정지 전이면 stopped_at_seq 빈칸).
- rows의 input 표시에 설비를 붙인다: `INSPECT LEAK FAIL @LEAK-2`.
- 재검사 모드의 history에도 설비를 붙인다: `LEAK: FAIL@5[LEAK-2] → 요청@7 → PASS@9[LEAK-1](재검사 1)`.
- 터미널에 설비 파일 경로와 SHA-256 앞 12자리를 레시피와 함께 출력한다.

## 사전 기대표 (초안 – 사용자 확정 전)
기본: `recipes/lamp_models_retest.json` + `recipes/equipment.json`. 「조립 완료(A)」 = 등록 후 P1~P3까지 진행(LEAK 가능 시점).

| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T33 | 조립 완료 제품 p1, p2, p3의 LEAK를 차례로 LEAK-2에서 FAIL, PASS, FAIL | 세 행 모두 허용. 세 번째 행 뒤 LEAK-2 = 정지(stopped_at_seq = 그 행). p1·p3 보류, p2 진행 가능 |
| T34 | T33 뒤 p4 LEAK PASS @LEAK-2 → p4 LEAK PASS @LEAK-1 | 첫 행 `RULE_EQUIP` 거절(`정지된 설비`), p4 LEAK 결과 없음. 둘째 행 허용 |
| T35 | a의 LEAK FAIL @LEAK-2 → 요청 → (다른 제품 결과로 LEAK-2 정지) → a 재검사 PASS @LEAK-2 → a 재검사 PASS @LEAK-1 | 정지 설비 재검사는 `RULE_EQUIP` 거절, 보류 유지, 요청은 열린 채 유지. LEAK-1 재검사는 허용(재검사 1), 보류 해소 |
| T36 | 한 제품이 LEAK-1에서 최초 FAIL → 요청 → FAIL @LEAK-1 → 요청 → FAIL @LEAK-1 | 제품 폐기. LEAK-1은 **가동 유지**(최초 검사 FAIL 1건만 셈) |
| T37 | LEAK-1 최초 검사 결과 순서 FAIL, PASS, PASS, FAIL (서로 다른 제품) | 정지되지 않음. 최근 3건(PASS, PASS, FAIL) 중 FAIL 1건 |
| T38 | ① 없는 설비 `LEAK-9` ② `LIGHT-1`로 LEAK ③ INSPECT의 equipment 빈칸 ④ 공정 행에 equipment 기입 | ①② `RULE_EQUIP` ③④ `RULE_PRESERVE`. 모두 제품·설비 상태 불변 |
| T39 | LEAK-2에서 FAIL(허용) → 시점이 안 된 제품의 FAIL(`RULE_INSP_PRE` 거절) → PASS(허용) → FAIL(허용) | 거절 행은 세지 않음. 네 번째 행 뒤에 정지(최근 3건 FAIL, PASS, FAIL) |
| T40 | 설비 파일을 각각 ① `window: 0` ② `fails: 4, window: 3` ③ `"window": "3"` ④ 알 수 없는 키 ⑤ 빈 `equipment` ⑥ 레시피에 없는 검사 `AIM`을 가리킴 | 모두 종료 코드 3, 오류 위치 표시, 보고서 미생성 |
| T41 | ① `--equipment` 없이 기존 샘플 3종 실행 ② `--recipe` 없이 `--equipment`만 ③ 7열 CSV를 `--equipment` 없이 ④ 같은 입력을 설비 모드로 두 번 | ① 기존 보고서와 동일 ②③ 종료 코드 2 ④ 보고서 4종·터미널 출력 바이트 동일 |

## 산출물
- `recipes/equipment.json`, `tests/test_equipment.py`(T33–T41, 거절은 제품·설비 전체 상태 불변까지 assert), T40용 파일은 `tests/fixtures/`
- `data/sample_events_equipment.csv`(T33–T39를 담은 고정 입력)와 `reports/sample_events_equipment_*.csv` 4종
- README에 「설비 모드」 절 추가(켜는 법, 정지 기준과 그 출처·한계, 규칙 표, 제외 범위)

## 완료 보고 (반드시 포함)
- 실제로 실행한 명령과 출력 원문(v1·1·2단계 회귀, 3단계 테스트, 샘플 실행)
- 기대표와 실제가 다르면 숨기지 말고 보고. 기대표·기존 테스트를 고쳐서 통과시키지 않는다
- 명세가 모호해 내린 해석·가정, 명세 이견

---

# v2 2단계 명세 (완료, 2026-10-18 · 리뷰 003 PASS)

## 작업: 재검사·폐기

상태: **구현 후 확정** (2026-10-18). 기대표 T23–T32는 구현 전에 작성했고 구현 중 변경 없음. 상태 줄 확정 표시는 구현·리뷰 003 뒤에 했다. 결정 근거는 `handoff/decisions.md`.
1단계(아래 「v2 1단계 명세」)는 완료(리뷰 002 PASS)이며, 그 동작과 테스트는 보존한다.

## 목표와 경계
- FAIL로 보류된 검사를 **재검사 요청 → 재검사 결과**로 처리한다. 재검사 PASS면 그 검사의 보류가 풀리고, 상한까지 FAIL이 이어지면 제품을 폐기한다.
- 원래 FAIL은 지우거나 덮어쓰지 않는다. 모든 시도는 이력으로 남는다.
- 모든 규칙은 가상 규칙이다. 재검사 상한 2회는 실제 SL 기준이 아니다.
- 이번 단계 제외: 설비·로트(3단계), 대량 생성기(4단계), 요청 ID·시도 ID 열 추가, 재검사 설비 지정, 폐기 취소, 레시피별로 다른 상한.

## 보존 조건 (가장 먼저 지킬 것)
- v1: 기존 조건 그대로(T1–T10, v1 보고서 동일).
- 1단계: `--recipe recipes/lamp_models.json`(재검사 설정 없음)의 동작·출력은 바뀌지 않는다. **T11–T22 테스트는 수정하지 않고 통과**해야 하며, `reports/sample_events_v2_*.csv` 3종도 다시 만들었을 때 체크아웃된 파일과 같아야 한다.
- `src/rules.py`, `tests/test_rules.py`, `tests/test_recipe.py`는 수정하지 않는다. 2단계 테스트는 새 파일(`tests/test_retest.py`)에 둔다.

## 재검사 모드 켜기
- 레시피의 **모든 모델**에 `"retest_limit": 2`를 넣으면 재검사 모드다. 하나도 없으면 1단계와 똑같이 동작한다.
- 일부 모델에만 있으면 설정 오류다. `retest_limit`은 1–5 정수(`true`·문자열 불가)여야 한다. 위반은 기존 레시피 검증과 같이 모든 오류를 표시하고 종료 코드 3.
- 기본 재검사 레시피: `recipes/lamp_models_retest.json` (`lamp_models.json`과 같고 두 모델에 `"retest_limit": 2`만 추가).
- `RETEST_REQUEST`는 공정 ID로 쓸 수 없는 예약어에 추가한다(`REGISTER`, `INSPECT`와 같음).
- 실행: `py -m src.main <입력CSV> --recipe recipes/lamp_models_retest.json`

## 입력 (CSV 열은 1단계와 같은 6열)
- 새 이벤트 `RETEST_REQUEST`: `inspection` 칸에 재검사할 검사 ID를 쓰고 `result`·`model`은 빈칸.
- 재검사 결과는 기존과 같은 `INSPECT` 행이다. 그 검사에 **열린 요청이 있을 때** 들어온 `INSPECT`를 그 요청의 재검사로 본다(요청과 결과는 같은 제품·같은 검사로 연결된다).

## 규칙 ID
- 신규 `RULE_RETEST`: 재검사 요청·재검사 결과·폐기와 관련된 판정. 재검사 모드의 거절 집계는 1단계 6개 뒤에 `RULE_RETEST`를 붙인 7개.

## 판정 규칙
**재검사 요청 (`RETEST_REQUEST X`)**
| 조건 | 결과 |
| --- | --- |
| X의 현재 결과가 FAIL이고 열린 요청이 없음 | 허용(`RULE_RETEST`). 요청이 열린다. **보류는 유지**된다 |
| X 결과가 없거나 PASS | 거절 `RULE_RETEST` (`미해결 FAIL 없음`) |
| X에 이미 열린 요청이 있음 | 거절 `RULE_RETEST` (`이미 열린 재검사 요청`) |

**검사 결과 (`INSPECT X`)**
| 조건 | 결과 |
| --- | --- |
| X의 첫 결과 | 1단계와 같음 |
| X에 결과가 있고 열린 요청이 있음 | 재검사로 허용(`RULE_RETEST`). 요청은 닫히고 X의 재검사 횟수 +1 |
| X에 결과가 있고 열린 요청이 없음 | 거절 `RULE_PRESERVE` (`결과 이미 존재`, 1단계 T16과 같음) |

- 재검사 결과가 **PASS**: X의 현재 결과가 PASS가 된다. 다른 검사에 미해결 FAIL이 없으면 보류가 풀리고 멈췄던 공정부터 다시 진행할 수 있다.
- 재검사 결과가 **FAIL**: 보류 유지. 요청은 소진됐으므로 다시 시도하려면 새 요청이 필요하다.
- **폐기**: 재검사 횟수가 `retest_limit`(2)에 도달한 재검사 결과가 FAIL이면, 그 행을 **허용하면서** 제품을 폐기 상태로 바꾼다. 재검사 횟수는 검사마다 따로 센다(허용된 재검사 결과 수 기준, 요청 수 아님).
- 폐기 제품에 들어온 모든 입력(공정·검사·요청)은 거절 `RULE_RETEST` (`폐기된 제품`). 단 형식 오류·중복 등록은 기존 규칙이 먼저다.

**판정 순서** (재검사 모드): 1 형식 오류 `RULE_PRESERVE` → 2 `REGISTER` 처리(1단계와 같음) → 3 미등록 `RULE_PRESERVE` → 4 폐기된 제품 `RULE_RETEST` → 5 레시피에 없는 공정·검사 `RULE_RECIPE` → 6 이벤트별 규칙(공정은 1단계 순서, 검사는 시점 `RULE_INSP_PRE` → 위 표, 요청은 위 표).
- `RETEST_REQUEST`의 형식 오류: `inspection` 빈칸, `result` 또는 `model` 기입 → `RULE_PRESERVE`.
- 상태 불변: 거절 행은 공정 위치·검사 이력·열린 요청·재검사 횟수·폐기 여부를 바꾸지 않는다.

## 상태와 보고서 (재검사 모드)
- 상태 우선순위: `폐기` > `보류` > `레시피 모의 흐름 완료` > `등록` > `공정 진행 중(Pk 완료)` > `검사 대기`.
- 미완료 이유: 1단계 규칙에 더해, 열린 요청이 있는 FAIL은 `X FAIL(재검사 요청됨)`, 폐기 제품은 `X 재검사 한도 2회 초과 FAIL로 폐기`.
- products 열: `product_id,model,state,incomplete_reason,history`. history는 레시피 검사 순서대로 시도가 있는 검사만 `X: FAIL@5 → 요청@7 → PASS@9(재검사 1)` 형식, 검사 사이는 `; `. 숫자는 그 행의 seq.
- rows·rejections 형식은 1단계와 같다(rejections는 7개 규칙).

## 사전 기대표 (초안 – 사용자 확정 전)
표기: `a(A)` = 제품 a를 모델 A로 등록. 「a 보류」 = a(A) → P1~P3 → LEAK FAIL. 레시피는 `recipes/lamp_models_retest.json`.

| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T23 | a 보류 → `RETEST_REQUEST LEAK` → P4 | 요청 허용(`RULE_RETEST`), 보류 유지. P4는 `RULE_FAIL_HOLD` 거절 |
| T24 | a 보류 → 요청 → LEAK PASS → P4 → P5 → LIGHT PASS → FINAL PASS | 재검사 PASS 허용(`RULE_RETEST`), 보류 해소, 이후 모두 허용. a = 완료. history `LEAK: FAIL → 요청 → PASS(재검사 1)` 형식 |
| T25 | a 보류 → LEAK PASS (요청 없음) | `RULE_PRESERVE` 거절, FAIL·보류 유지 |
| T26 | a 보류 → 요청 → LEAK FAIL → LEAK PASS → 요청 → LEAK PASS | 첫 재검사 FAIL 허용·보류 유지. 요청 없는 PASS는 `RULE_PRESERVE` 거절. 새 요청 뒤 PASS 허용(재검사 2), 보류 해소 |
| T27 | a 보류 → 요청 → FAIL → 요청 → FAIL → P4 → `RETEST_REQUEST LEAK` → LIGHT PASS | 두 번째 재검사 FAIL 허용, a = 폐기. 뒤의 세 입력은 모두 `RULE_RETEST` 거절, 상태 불변 |
| T28 | ① LEAK을 아직 안 한 제품에 요청 ② LEAK PASS인 제품에 요청 ③ 열린 요청이 있는데 또 요청 ④ B 제품에 `RETEST_REQUEST FINAL` ⑤ 미등록 제품에 요청 ⑥ 요청 행에 result 기입 | ①②③ `RULE_RETEST` ④ `RULE_RECIPE` ⑤⑥ `RULE_PRESERVE`. 모두 상태 불변 |
| T29 | b(A) → P1~P3 → LEAK PASS → P4~P5 → LIGHT FAIL → FINAL FAIL → 요청 LIGHT → LIGHT PASS → 요청 FINAL → FINAL PASS | LIGHT 재검사 PASS 뒤에도 FINAL FAIL로 보류 유지. FINAL 재검사 PASS 뒤 b = 완료 |
| T30 | a 보류 → 요청 → FAIL → 요청 → PASS(LEAK 재검사 2회 소진) → P4~P5 → LIGHT FAIL → 요청 → LIGHT PASS | LIGHT는 별도 횟수로 재검사 허용(재검사 1), 폐기되지 않음 |
| T31 | 재검사 레시피를 각각 ① `retest_limit: 0` ② `"2"` ③ `true` ④ A에만 `retest_limit` ⑤ 공정 ID `RETEST_REQUEST` | 모두 종료 코드 3, 오류 위치 표시, 보고서 미생성 |
| T32 | ① 1단계 레시피(`lamp_models.json`)로 `RETEST_REQUEST` 행 실행 ② 같은 CSV를 재검사 레시피로 두 번 실행 | ① `RULE_RECIPE` 거절(1단계 동작 그대로) ② 보고서 3종·터미널 출력 바이트 동일 |

## 산출물
- `recipes/lamp_models_retest.json`, `tests/test_retest.py`(T23–T32, 거절은 전체 상태 불변까지 assert), T31용 레시피는 `tests/fixtures/`
- `data/sample_events_retest.csv`(T23–T30을 제품별로 담은 고정 입력)와 `reports/sample_events_retest_*.csv`
- README에 「재검사 모드」 절 추가(켜는 법, 규칙 표, 폐기 기준과 이유, 제외 범위)

## 완료 보고 (반드시 포함)
- 실제로 실행한 명령과 출력 원문(v1·1단계 회귀, 2단계 테스트, 샘플 실행)
- 기대표와 실제가 다르면 숨기지 말고 보고. 기대표·기존 테스트를 고쳐서 통과시키지 않는다
- 명세가 모호해 내린 해석·가정, 명세 이견

---

# v2 1단계 명세 (완료, 2026-10-18 · 리뷰 002 PASS)

## 작업: 모델별 공정 레시피 설정화

상태: **사용자 확정** (2026-10-18). 결정 근거는 `handoff/decisions.md`. 사용자가 확정하면 이 줄을 "사용자 확정"으로 바꾼다.
v1(아래 「v1 명세」)은 완료·동결 상태이며 `v1.0` 기준점으로 보존한다.

## 목표와 경계
- 제품 모델마다 공정 순서와 필수 검사가 다르다. 이를 JSON 레시피로 정의하고, 같은 판정 원칙(순서·검사 시점·보류·이력 보존)을 모델별로 적용한다.
- 모든 공정·검사·모델은 **가상 규칙**이다. SL 실제 공정·기준이 아니다. 최종 상태 "레시피 모의 흐름 완료"는 출하·양품·SL 기준 적합을 뜻하지 않는다.
- 이번 단계 제외: 재검사·보류 해제(2단계), 설비·로트(3단계), 대량 생성기(4단계), 분기·병렬·순환 공정(그래프), 검사 통과를 다음 공정 조건으로 거는 중간 관문, 실행 중 레시피 변경, 등록 정정, 외부 패키지.

## v1 보존 (가장 먼저 지킬 조건)
- `py -m src.main <CSV>`(옵션 없음)는 v1과 **완전히 같게** 동작한다. 입력 5열, 보고서 3종, 규칙 ID 5개, 상태명, 종료 코드 모두 그대로다.
- `src/rules.py`와 `tests/test_rules.py`는 수정하지 않는다. v2 판정은 새 모듈(예: `src/recipe.py`, `src/recipe_rules.py`)에 둔다. 공통으로 쓸 수 있는 작은 함수만 옮기는 것도 하지 않는다(v1 회귀 위험 차단).
- 회귀 확인: T1–T10 무수정 통과, `py -m src.main data/sample_events.csv`로 다시 만든 `reports/sample_events_*.csv` 3종이 커밋된 파일과 바이트 단위로 같다.

## 실행
- v2: `py -m src.main <입력CSV> --recipe <레시피JSON>`
- 테스트: `py -m unittest discover -s tests` (v1·v2 테스트 모두)
- 기본 레시피 파일: `recipes/lamp_models.json`

## 레시피 형식 (선형)
```json
{
  "A": {
    "steps": ["P1", "P2", "P3", "P4", "P5"],
    "inspections": [
      {"id": "LEAK",  "after": "P3"},
      {"id": "LIGHT", "after": "P5"},
      {"id": "FINAL", "after": "P5"}
    ]
  },
  "B": {
    "steps": ["P1", "P2", "P3", "P4"],
    "inspections": [
      {"id": "LEAK",  "after": "P2"},
      {"id": "LIGHT", "after": "P4"}
    ]
  }
}
```
- `steps`의 배열 순서가 곧 공정 순서다. 등록(`REGISTER`)은 공정 수에 포함하지 않는다.
- `after`: 그 검사를 입력할 수 있는 가장 이른 시점(해당 공정 완료 뒤). 검사 PASS를 다음 공정 진행 조건으로 걸지는 않는다.
- 모델·공정·검사 ID 형식: 대문자 영문으로 시작하고 대문자·숫자·`_`만 사용(`^[A-Z][A-Z0-9_]*$`). 비교는 대소문자·공백까지 정확히 일치.
- 허용 키는 모델 아래 `steps`, `inspections`, 검사 항목 아래 `id`, `after`뿐이다.

## 레시피 검증 (T18)
이벤트를 처리하기 전에 레시피 전체를 검사한다. 오류가 하나라도 있으면:
- 이벤트를 하나도 처리하지 않고, 보고서 파일을 만들지 않는다.
- **발견한 모든 오류**를 위치와 함께 출력한다(예: `A.steps[2]: 공정 ID 중복 P1`).
- 종료 코드 **3**으로 끝낸다. (v1의 입력 파일·CSV 오류는 기존대로 2)

오류로 볼 것: JSON 형식 오류, 최상위가 객체가 아님, 모델이 0개, `steps`가 배열이 아니거나 비어 있음, 공정 ID 중복, `REGISTER`·`INSPECT`를 공정 ID로 사용, `inspections`가 배열이 아니거나 비어 있음, 검사 ID 중복, `after` 누락, `after`가 그 모델에 없는 공정, 허용하지 않은 키(예: `next`), ID 형식 위반.

## 입력 형식 (v2 CSV)
`seq,product_id,event,inspection,result,model`
- `event`: `REGISTER` | `INSPECT` | 그 제품 레시피의 공정 ID(예: `P3`)
- `model`: `REGISTER` 행에만 쓴다. 다른 행에서는 빈칸.
- `inspection`, `result`: `INSPECT` 행에만 쓴다(`result`는 `PASS` | `FAIL`).
- `seq`, `product_id` 규칙과 물리적 행 순서 처리는 v1과 같다.
- `--recipe`를 줬는데 헤더가 v2 6열이 아니면 기존 CSV 오류와 같이 종료 코드 2. `--recipe` 없이 v2 헤더를 주면 v1 헤더 오류(종료 코드 2).

## 규칙 ID (v2)
| 규칙 ID | 의미 |
| --- | --- |
| `RULE_RECIPE` | **신규.** 레시피에 없는 모델로 등록, 등록 행의 `model` 빈칸, 그 제품의 레시피에 없는 공정·검사 |
| `RULE_SEQ` | 공정은 레시피 순서대로 한 단계씩. 앞 공정을 건너뛰면 거절 |
| `RULE_INSP_PRE` | 검사의 `after` 공정이 끝나기 전 검사 입력은 거절 |
| `RULE_NOT_DONE` | 공정이나 필수 검사가 남아 있으면 완료 불가 |
| `RULE_FAIL_HOLD` | FAIL이 하나라도 있으면 보류. **보류 제품의 다음 공정 입력은 거절**한다. 아직 실시하지 않은 다른 검사의 최초 결과는 시점 조건을 만족하면 받는다(v1과 같음) |
| `RULE_PRESERVE` | 형식 오류(열·seq·product_id·result 값·빈칸 규칙), 미등록 제품, 중복 등록(다른 모델 포함), 이미 지난 공정 재입력, 같은 검사 두 번째 결과 |

**판정 순서** (한 행이 여러 조건에 걸리면 먼저 걸린 것 하나로 거절):
1. 형식 오류 → `RULE_PRESERVE`
2. `REGISTER`: 이미 등록됨 → `RULE_PRESERVE` / `model` 빈칸·레시피에 없는 모델 → `RULE_RECIPE`
3. 미등록 제품 → `RULE_PRESERVE`
4. 그 제품 레시피에 없는 공정·검사 → `RULE_RECIPE`
5. 공정 입력: 이미 지난 공정 → `RULE_PRESERVE` / 보류 중 → `RULE_FAIL_HOLD` / 건너뜀 → `RULE_SEQ`
6. 검사 입력: `after` 공정 미완료 → `RULE_INSP_PRE` / 이미 결과 있음 → `RULE_PRESERVE`

**허용 행의 rule_id**: 등록 → `RULE_RECIPE`, 공정 → `RULE_SEQ`, 검사 → 반영 후 보류 또는 완료면 `RULE_FAIL_HOLD`, 아니면 `RULE_NOT_DONE`.

**상태 불변**: 거절된 행은 모든 제품의 공정 위치·검사 결과·모델을 바꾸지 않는다. 검증을 모두 통과한 뒤 한 번만 반영한다.

## 상태와 미완료 이유
- 상태 우선순위: `보류`(FAIL 있음) > `레시피 모의 흐름 완료`(모든 공정 + 모든 검사 PASS) > `등록`(공정 0개) > `공정 진행 중(Pk 완료)` > `검사 대기`(공정은 다 끝났고 검사가 남음)
- 미완료 이유: 남은 공정을 레시피 순서대로 `Pk 미완료`, 이어서 검사를 레시피 순서대로 `X 미실시` 또는 `X FAIL`. 구분자는 `; `.

## 보고서 (v2)
- 파일: `reports/<입력파일명>_rows.csv`, `_products.csv`, `_rejections.csv` (v1과 같은 3종)
- rows 열: v1과 같음. products 열: `product_id,model,state,incomplete_reason`. rejections: 규칙 ID 6개 모두(0건 포함), 위 표 순서.
- 터미널 첫머리에 사용한 레시피 경로와 내용의 SHA-256 앞 12자리를 출력한다. 재현성 기준은 **같은 CSV + 같은 레시피**다.

## 사전 기대표 (초안 – 사용자 확정 전. 확정 후에는 구현 결과에 맞춰 바꾸지 않는다)
표기: `a(A)` = 제품 a를 모델 A로 등록. 레시피는 위 `recipes/lamp_models.json` 기준.

| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T11 | a(A) → P1~P5 → LEAK PASS → LIGHT PASS → FINAL PASS | 모두 허용. a = 레시피 모의 흐름 완료 |
| T12 | a(A), b(B) 등록 → 두 제품 공정을 섞어 입력(a는 P1~P4, b는 P1~P4) → b LEAK PASS, LIGHT PASS | b = 완료. a = 공정 진행 중(P4 완료), 미완료 이유 `P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시`. 두 제품 판정이 섞이지 않음 |
| T13 | a(A) → P1 → P3 → P2 | P3는 `RULE_SEQ` 거절(`P2 미완료`), a는 P1 유지. 이어지는 P2는 허용 |
| T14 | ① a(A) → P1~P2 → LEAK PASS ② c(A) → P1~P4 → LIGHT PASS | ① `RULE_INSP_PRE` 거절(`P3 미완료`) ② `RULE_INSP_PRE` 거절(`P5 미완료`). 둘 다 결과 미저장 |
| T15 | a(A) → P1~P3 → LEAK PASS → P4~P5 → LIGHT PASS | LEAK는 공정 중간에 허용. 최종 a = 검사 대기, 미완료 이유 `FINAL 미실시` |
| T16 | a(A) → P1~P3 → LEAK FAIL → P4 → LEAK PASS | LEAK FAIL 허용, a = 보류. P4는 `RULE_FAIL_HOLD` 거절, a는 P3 유지. LEAK PASS는 `RULE_PRESERVE` 거절, FAIL 유지 |
| T16b | a(A) → P1~P5 → LIGHT FAIL → FINAL PASS | LIGHT FAIL로 보류. FINAL PASS는 허용(아직 없던 검사의 최초 결과), 보류 유지 |
| T17 | ① c(C) 등록(없는 모델) ② A 제품에 P6 ③ B 제품에 FINAL 검사 | 모두 `RULE_RECIPE` 거절. ①은 제품 미생성, ②③은 기존 상태 불변 |
| T18 | 레시피를 각각 ① 빈 steps ② `P1,P2,P1` ③ 검사 ID 중복 ④ steps가 문자열 ⑤ 알 수 없는 키 `next` ⑥ `after`가 없는 공정 ⑦ 위 오류 두 개를 한 파일에 | 모두 종료 코드 3, 보고서 미생성, 이벤트 미처리. ⑦은 두 오류가 모두 출력됨 |
| T19 | b(B) → P1~P4 → P5 | P5는 A에만 있는 공정이므로 `RULE_RECIPE` 거절. b 상태 불변 |
| T20 | ① 등록 행의 model 빈칸 ② 공정 행에 model 기입 | ① `RULE_RECIPE` 거절, 제품 미생성 ② `RULE_PRESERVE` 거절, 상태 불변 |
| T21 | 같은 CSV를 ① 같은 레시피로 두 번 ② LEAK `after`만 다른 레시피로 실행 | ① 보고서 3종과 터미널 출력이 바이트 단위로 같음 ② 해당 LEAK 행의 판정이 달라짐(예: B의 LEAK after P3이면 P2 뒤 LEAK는 `RULE_INSP_PRE`) |
| T22 | a(A) → P1~P2 → a를 B로 다시 REGISTER | `RULE_PRESERVE` 거절(`이미 등록된 제품`). a는 모델 A, P2 완료 유지 |

## 산출물
- `recipes/lamp_models.json` (위 레시피)
- `src/` v2 모듈, `src/main.py`에 `--recipe` 옵션 추가(옵션 없을 때 경로는 v1 그대로)
- `tests/test_recipe.py`: T11–T22 각각 테스트. 거절 사례는 전체 제품 상태 불변까지 assert. T18·T21용 레시피는 `tests/fixtures/`에 둔다
- `data/sample_events_v2.csv`: T11–T17, T19, T20, T22를 제품별로 담은 고정 입력과 그 보고서 `reports/sample_events_v2_*.csv`
- README에 v2 절 추가(실행법, 레시피 형식, 규칙 표, v1과의 관계, 제외 범위). v1 절은 지우지 않는다

## 완료 보고 (반드시 포함)
- 실제로 실행한 명령과 출력 원문(v1 회귀, v2 테스트, 샘플 실행)
- 기대표와 실제 결과가 다르면 숨기지 말고 보고한다. 기대표·테스트를 고쳐서 통과시키지 않는다
- 명세가 모호해 내린 해석·가정 목록

---

# v1 명세 (완료·동결, 2026-10-17)

## 작업: 교육용 가상 조립·검사 공정의 진행 조건 판정기 (Python CLI)

상태: 사용자 확정 (2026-10-17). 이 PC에서는 `python`이 Store 안내로 연결되므로 실행 명령만 `py`로 바꿨다. 나머지는 사용자 원문 그대로다.

## 배경과 경계
- 위치: project/ (현재 docs만 있고 src, tests는 비어 있음)
- 제조기술개발 직무 지원용 교육 프로젝트. 모든 공정 순서·검사 조건은 가상 규칙이며 SL 실제 기준이 아님.
- 점등(LIGHT)·누설(LEAK) 결과는 실측값이 아닌 합성 PASS/FAIL 입력.
- 핵심 질문: "이 제품이 다음 단계로 진행해도 되는가? 안 된다면 어떤 입력과 규칙 때문인가?"
- 마감이 임박함. 아래 범위만 구현하고 기능을 추가하지 말 것.

## 제외 (구현 금지)
재검사 요청·승인·보류 해제, DB, 사용자·권한, 웹 UI·차트, LLM/LangGraph/RAG, 외부 패키지.
FAIL 제품은 이번 버전에서 계속 보류됨. 새 PASS로 덮어써서 해결하면 안 됨.

## 기술 조건
- Python 3 표준 라이브러리만 사용. 테스트는 unittest.
- 실행: py -m src.main <입력CSV> → 터미널 보고서 출력 + reports/ 아래 CSV 저장
- 테스트: py -m unittest discover -s tests
- 같은 입력을 다시 실행하면 판정 결과가 같아야 함(시각·난수를 판정에 쓰지 말 것).

## 입력 형식 (CSV)
seq,product_id,event,inspection,result
- event: REGISTER | PRE_ASSEMBLY | MAIN_ASSEMBLY | INSPECT
- inspection, result: INSPECT일 때만 사용 (LIGHT|LEAK, PASS|FAIL), 나머지 event에서는 빈칸

## 규칙 (각 규칙에 ID를 붙여 보고서에 표시)
- RULE_SEQ: REGISTER → PRE_ASSEMBLY → MAIN_ASSEMBLY 순서. 선행 단계가 없으면 거절.
- RULE_INSP_PRE: MAIN_ASSEMBLY 완료 전 INSPECT는 거절.
- RULE_NOT_DONE: LIGHT·LEAK 중 하나라도 결과가 없으면 "검사 대기"이며 완료 불가.
- RULE_FAIL_HOLD: 하나라도 FAIL이면 "보류". 두 검사가 모두 PASS일 때만 "선택한 두 검사까지의 모의 흐름 완료".
- RULE_PRESERVE: 같은 제품·같은 검사의 두 번째 결과, 중복 조립 이벤트, 미등록 제품, 잘못된 값은 거절. 거절된 입력은 제품 상태와 기존 결과를 절대 바꾸지 않음.

## 반드시 지킬 설계 조건
- 판정 로직(src/rules.py 등)과 입출력(src/main.py)을 분리.
- 거절 시 "메시지만 출력하고 상태는 바뀌는" 오류가 없도록, 검증을 모두 통과한 뒤에만 상태를 변경.
- 최종 상태명 "모의 흐름 완료"는 출하·양품·SL 기준 적합을 뜻하지 않는다고 README에 명시.

## 보고서 형식
1) 행별: seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태
2) 제품별 최종 상태와 미완료 이유
3) 규칙 ID별 거절 건수 집계

## 사전 기대표 (사용자가 확정함. 구현 결과에 맞춰 이 표를 바꾸지 말 것)
| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T1 | 등록→예비→본조립→LIGHT PASS→LEAK PASS | 모의 흐름 완료 |
| T2 | 등록→본조립(예비 없음) | 거절 RULE_SEQ, 상태 '등록' 유지 |
| T3 | 등록→예비→LIGHT PASS(본조립 전) | 거절 RULE_INSP_PRE, 결과 저장 안 됨 |
| T4 | 조립 완료→LIGHT PASS, LEAK 없음 | 검사 대기, 미완료 이유 'LEAK 미실시' |
| T5 | 조립 완료→LIGHT PASS→LEAK FAIL | 보류, 이유 'LEAK FAIL' |
| T6 | T5 뒤 LEAK PASS 추가 입력 | 거절 RULE_PRESERVE, 원래 FAIL·보류 유지 |
| T7 | T1 뒤 LIGHT FAIL 추가 입력 | 거절 RULE_PRESERVE, 완료 상태·원래 PASS 유지 |
| T8 | 예비 조립 두 번 | 두 번째 거절, 상태 변화 없음 |
| T9 | 미등록 제품 이벤트, result='OK' 같은 잘못된 값 | 거절, 다른 제품 상태 영향 없음 |
| T10 | 같은 입력 CSV를 두 번 실행 | 두 보고서의 판정 열이 동일 |

## 산출물
- src/, tests/ (T1–T10을 각각 테스트로. T2·T3·T6·T7·T8·T9는 거절 후 '상태 불변'까지 assert)
- data/sample_events.csv (T1–T9를 제품별로 담은 고정 입력)
- README.md를 이 범위로 갱신(실행법, 가상 규칙 경계, 제외 범위·한계).
  docs/requirements.md는 삭제하지 말고 맨 위에 "재검사 범위는 이번 버전에서 제외, 현행 기준은 README" 한 줄만 추가.

## 완료 보고 (반드시 포함)
- 실제로 실행한 명령과 출력 원문(테스트 결과 포함)
- 기대표와 실제 결과가 다른 항목이 있으면 숨기지 말고 그대로 보고. 기대표나 테스트를 고쳐서 통과시키지 말 것.
- 구현하면서 내린 해석·가정 목록 (명세가 모호했던 부분)
