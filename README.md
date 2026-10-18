# 교육용 가상 조립·검사 공정의 진행 조건 판정기

제품별 등록·조립 이벤트와 점등(`LIGHT`)·누설(`LEAK`) 검사 결과를 CSV로 받아, 다음 단계 진행 가능 여부와 거절 이유를 판정하는 Python CLI입니다. 현행 명세와 사전 기대표 v1(T1–T10)·v2 1단계(T11–T22)·2단계(T23–T32)는 [handoff/tasks.md](handoff/tasks.md)에 있습니다. `docs/`의 문서는 이전 범위의 기록입니다.

아래 기본 실행과 5열 입력 설명은 동결된 v1입니다. 모델별 레시피를 사용하는 v2는 뒤의 「v2 1단계: 모델별 레시피」에서 설명합니다.

모든 공정 순서와 검사 조건은 **교육용 가상 규칙이며 SL 실제 기준이 아닙니다.** 점등·누설 결과는 실측값이 아닌 합성 `PASS`/`FAIL` 입력입니다. **「선택한 두 검사까지의 모의 흐름 완료」는 출하·양품·SL 기준 적합을 뜻하지 않습니다.**

## 실행과 테스트

Python 3 표준 라이브러리만 사용하며 별도 패키지 설치가 필요 없습니다. 이 PC의 실행 환경은 Python 3.9.13이고, `python` 명령은 Microsoft Store 안내로 연결되므로 `py`를 사용합니다. 저장소 `project/`에서 실행합니다.

```powershell
py -m src.main data/sample_events.csv
py -m unittest discover -s tests
```

다른 입력은 `py -m src.main <입력CSV>`로 실행합니다. 터미널에는 행별 판정, 제품별 최종 상태·미완료 이유, 규칙별 거절 건수를 출력합니다. 파일을 읽을 수 없거나 CSV 구조가 잘못되면 오류를 표시하고 종료합니다. 개별 행의 값이 잘못된 경우에는 그 행을 거절하고 다음 행을 계속 처리합니다.

## 입력 형식

첫 행은 다음 열 이름과 순서를 사용합니다.

```csv
seq,product_id,event,inspection,result
1,EXAMPLE,REGISTER,,
2,EXAMPLE,PRE_ASSEMBLY,,
3,EXAMPLE,MAIN_ASSEMBLY,,
4,EXAMPLE,INSPECT,LIGHT,PASS
5,EXAMPLE,INSPECT,LEAK,PASS
```

- `seq`: 양의 정수인 행 표식입니다. 중복이나 비단조 증가를 허용하며, 판정은 `seq`로 정렬하지 않고 CSV에 기록된 물리적 행 순서로 진행합니다.
- `product_id`: 빈 값이나 공백만 있는 값은 거절합니다. 각 제품의 상태는 독립적으로 관리합니다.
- `event`: `REGISTER`, `PRE_ASSEMBLY`, `MAIN_ASSEMBLY`, `INSPECT` 중 하나입니다.
- `inspection`, `result`: `INSPECT`에서만 각각 `LIGHT` 또는 `LEAK`, `PASS` 또는 `FAIL`을 사용합니다. 다른 이벤트에서는 두 칸을 비웁니다.

이벤트·검사·결과 값은 위 대문자와 정확히 일치해야 합니다. 잘못된 값은 `RULE_PRESERVE`로 거절하며, 거절된 행은 제품 상태와 기존 검사 결과를 바꾸지 않습니다.

## 판정 규칙과 상태

| 규칙 ID | 의미 |
| --- | --- |
| `RULE_SEQ` | `REGISTER` → `PRE_ASSEMBLY` → `MAIN_ASSEMBLY` 순서를 지킵니다. 선행 조립 단계 없이 진행하면 거절합니다. |
| `RULE_INSP_PRE` | 본조립 완료 전 검사 입력을 거절합니다. |
| `RULE_NOT_DONE` | 본조립 후 두 검사 중 하나라도 결과가 없으면 검사 대기이며 완료할 수 없습니다. |
| `RULE_FAIL_HOLD` | 하나라도 `FAIL`이면 보류합니다. 두 검사가 모두 `PASS`일 때만 선택한 두 검사까지의 모의 흐름 완료입니다. |
| `RULE_PRESERVE` | 같은 검사에 두 번째 결과 입력, 중복 등록·조립, 미등록 제품 이벤트, 잘못된 값을 거절하고 기존 상태·결과를 보존합니다. |

제품 상태는 `등록` → `예비 조립` → `검사 대기`로 진행합니다. 본조립 뒤 검사 결과가 모두 `PASS`이면 `선택한 두 검사까지의 모의 흐름 완료`, 하나라도 `FAIL`이면 `보류`입니다. `FAIL`은 미실시 검사보다 우선하므로 다른 검사가 아직 없어도 보류입니다.

`FAIL` 뒤에도 아직 실시하지 않은 다른 검사의 최초 결과는 입력할 수 있습니다. 이미 입력한 검사 결과는 바꿀 수 없으며, 새 `PASS`를 덧붙여도 기존 `FAIL`과 보류 상태가 유지됩니다.

## 저장 보고서

현재 작업 디렉터리의 `reports/`에 다음 세 파일을 UTF-8 BOM CSV로 저장합니다. 입력이 `data/sample_events.csv`이면 파일 이름은 다음과 같습니다.

| 파일 | 열 |
| --- | --- |
| `reports/sample_events_rows.csv` | `seq,product_id,input,rule_id,decision,rejection_reason,state` — 입력별 적용 규칙, 허용·거절, 거절 이유, 처리 후 상태 |
| `reports/sample_events_products.csv` | `product_id,state,incomplete_reason` — 제품별 최종 상태와 미완료 이유 |
| `reports/sample_events_rejections.csv` | `rule_id,rejection_count` — 다섯 규칙별 거절 건수, 0건인 규칙 포함 |

파일 이름의 `sample_events`는 입력 파일의 확장자를 뺀 이름입니다. 같은 입력을 다시 실행하면 같은 파일에 덮어쓰며, 시각·난수를 판정에 사용하지 않아 터미널과 CSV 결과가 동일합니다.

## 샘플과 검증 범위

`data/sample_events.csv`는 T1–T9 상황을 제품별로 담은 고정 합성 입력입니다. T1은 정상 완료, T2는 예비 조립 누락, T3은 본조립 전 검사, T4는 `LEAK` 미실시, T5는 `LEAK FAIL`, T6은 `FAIL` 뒤 결과 덮어쓰기 시도, T7은 완료 뒤 결과 덮어쓰기 시도, T8은 중복 예비 조립, T9는 미등록 제품 이벤트와 잘못된 검사 결과를 다룹니다.

`tests/`는 T1–T10을 각각 검증합니다. T2·T3·T6·T7·T8·T9는 거절 후 상태·기존 결과 보존도 확인하며, T10은 같은 입력을 두 번 실행했을 때 판정이 같은지 확인합니다. 실제 실행 명령·출력과 구현 해석은 [handoff/gpt-log.md](handoff/gpt-log.md)에 기록합니다.

## 제외 범위와 한계

재검사 요청·승인·보류 해제, DB, 사용자·권한, 웹 UI·차트, LLM·LangGraph·RAG, 외부 패키지는 구현 범위에서 제외합니다. 제품 상태는 입력 CSV를 처음부터 처리해 계산하며, 보고서가 이전 실행의 상태를 불러오는 저장소 역할을 하지는 않습니다. 실제 측정·설비 연동이나 실제 제조 품질 판정을 수행하지 않습니다.

## v2 1단계: 모델별 레시피

모델마다 선형 공정 순서와 필수 검사를 JSON으로 정의합니다. 모델 A·B와 공정·검사 조건은 모두 **가상 규칙이며 SL 실제 공정·기준이 아닙니다. 「레시피 모의 흐름 완료」도 출하·양품·SL 기준 적합을 뜻하지 않습니다.**

### 실행과 v1의 관계

`--recipe`를 줄 때만 v2로 실행합니다. 기본 레시피 파일은 [recipes/lamp_models.json](recipes/lamp_models.json)이며, 자동으로 선택되지는 않습니다.

```powershell
py -m src.main data/sample_events_v2.csv --recipe recipes/lamp_models.json
py -m unittest discover -s tests
```

옵션 없는 `py -m src.main data/sample_events.csv`는 기존 v1 판정·5열 입력·3개 보고서·5개 규칙·상태명·종료 코드를 유지합니다. `src/rules.py`와 `tests/test_rules.py`는 그대로이며, v2 판정은 `src/recipe_rules.py`에 있습니다. v2 실행에 5열 CSV를 주거나 v1 실행에 6열 CSV를 주면 헤더 오류로 종료합니다.

### v2 입력

헤더는 다음 6개 열을 순서까지 정확히 사용합니다.

```csv
seq,product_id,event,inspection,result,model
1,EXAMPLE,REGISTER,,,B
2,EXAMPLE,P1,,,
3,EXAMPLE,P2,,,
4,EXAMPLE,INSPECT,LEAK,PASS,
```

- `REGISTER`에서만 `model`을 기입합니다. 등록 후 모델 변경·재등록은 거절합니다.
- `event`는 `REGISTER`, `INSPECT`, 또는 등록한 모델 레시피의 공정 ID입니다.
- `INSPECT`에서만 `inspection`, `result`를 기입합니다. 결과는 `PASS` 또는 `FAIL`입니다. 다른 행의 두 칸과 등록 이외 행의 `model`은 빈칸이어야 합니다.
- `seq`는 v1처럼 양의 정수 표식이며 중복·감소를 허용합니다. 물리적 행 순서로 처리합니다.
- `product_id`는 빈값·공백만 있는 값을 거절하고, 앞뒤 공백을 포함해 그대로 구분합니다. 모델·공정·검사·결과도 대소문자와 공백을 정리하지 않고 정확히 비교합니다.

### 레시피 형식과 검증

기본 레시피는 다음과 같습니다.

```json
{
  "A": {
    "steps": ["P1", "P2", "P3", "P4", "P5"],
    "inspections": [
      {"id": "LEAK", "after": "P3"},
      {"id": "LIGHT", "after": "P5"},
      {"id": "FINAL", "after": "P5"}
    ]
  },
  "B": {
    "steps": ["P1", "P2", "P3", "P4"],
    "inspections": [
      {"id": "LEAK", "after": "P2"},
      {"id": "LIGHT", "after": "P4"}
    ]
  }
}
```

`steps`의 배열 순서가 공정 순서입니다. 등록은 공정 수에 포함하지 않습니다. `after`는 검사 입력이 가능한 가장 이른 시점으로, 해당 공정을 마친 뒤에 검사할 수 있습니다. **검사 PASS를 다음 공정의 진행 조건으로 걸지는 않습니다.**

모델·공정·검사 ID는 `^[A-Z][A-Z0-9_]*$` 형식입니다. 최상위 객체에는 모델이 하나 이상 있어야 하고 각 모델의 `steps`, `inspections`는 비어 있지 않은 배열이어야 합니다. 모델 안의 공정 ID·검사 ID는 각각 중복할 수 없고 `REGISTER`, `INSPECT`는 공정 ID로 사용할 수 없습니다. 검사의 `after`는 반드시 그 모델에 존재하는 공정이어야 합니다. 허용 키는 모델 아래 `steps`, `inspections`, 검사 아래 `id`, `after`뿐입니다.

이벤트를 읽기 전에 레시피 전체를 검증합니다. 오류가 있으면 위치(예: `A.steps[2]`)와 함께 발견한 모든 오류를 출력하고 **종료 코드 3**으로 끝냅니다. 이벤트를 처리하거나 보고서를 생성하지 않습니다. JSON 문법 오류는 파싱 위치를 출력하며, 파일 읽기·디코딩 실패도 레시피 오류입니다. 입력 파일·CSV 헤더·파싱 오류는 기존처럼 **종료 코드 2**입니다. 개별 데이터 행의 거절은 보고서에 기록하고 다음 행을 처리하며 정상 실행의 종료 코드는 0입니다.

### v2 규칙과 상태

| 규칙 ID | 의미 |
| --- | --- |
| `RULE_RECIPE` | 등록 모델이 비었거나 레시피에 없을 때, 제품 레시피에 없는 공정·검사일 때 거절합니다. 허용 등록에도 이 ID를 표시합니다. |
| `RULE_SEQ` | 레시피 공정을 한 단계씩 진행합니다. 앞 공정을 건너뛰면 거절합니다. 허용 공정에도 이 ID를 표시합니다. |
| `RULE_INSP_PRE` | 검사의 `after` 공정 완료 전 검사 입력을 거절합니다. |
| `RULE_NOT_DONE` | 공정이나 필수 검사가 남으면 완료할 수 없습니다. 허용 검사 반영 후 보류·완료가 아니면 이 ID를 표시합니다. |
| `RULE_FAIL_HOLD` | 하나라도 FAIL이면 보류하고 이후 공정 입력을 거절합니다. 허용 검사 반영 후 보류 또는 완료여도 이 ID를 표시합니다. |
| `RULE_PRESERVE` | 형식 오류, 미등록 제품, 중복 등록, 이미 지난 공정 재입력, 같은 검사의 두 번째 결과를 거절합니다. |

한 행이 여러 조건에 걸리면 형식 오류 → 중복 등록/등록 모델 → 미등록 제품 → 제품 레시피에 없는 공정·검사 순서로 검사합니다. 공정은 이미 지난 공정 → 보류 → 건너뜀, 검사는 `after` 미완료 → 결과 중복 순서로 검사합니다. **거절된 행은 모든 제품의 모델·공정 위치·검사 결과를 바꾸지 않습니다.**

상태는 FAIL이 있는 `보류`, 모든 공정과 모든 검사 PASS를 만족한 `레시피 모의 흐름 완료`, 공정 0개의 `등록`, 일부 공정을 마친 `공정 진행 중(Pk 완료)`, 모든 공정을 마쳤지만 검사가 남은 `검사 대기`로 구분합니다. Pk 자리에는 실제 마지막 공정 ID를 표시합니다. 미완료 이유는 남은 공정의 `Pk 미완료`를 배열 순서로, 이어서 검사별 `X 미실시` 또는 `X FAIL`을 레시피 순서로 나열하며 `; `로 구분합니다.

보류 중에도 아직 실시하지 않은 다른 검사의 최초 결과는 `after` 조건을 만족하면 받습니다. 원래 FAIL은 보존되므로 보류가 해제되지는 않습니다.

### v2 보고서와 재현성

터미널 첫 줄에는 사용한 레시피 경로와 **파일 원본 내용의 SHA-256 앞 12자리**를 표시합니다. v2의 재현성 기준은 같은 CSV와 같은 레시피이며 시각·난수를 사용하지 않습니다.

| 파일 | 열 |
| --- | --- |
| `reports/sample_events_v2_rows.csv` | `seq,product_id,input,rule_id,decision,rejection_reason,state` (v1과 같은 열) |
| `reports/sample_events_v2_products.csv` | `product_id,model,state,incomplete_reason` |
| `reports/sample_events_v2_rejections.csv` | `rule_id,rejection_count` (위 표의 6개 규칙 순서, 0건 포함) |

저장 위치·파일명·UTF-8 BOM·덮어쓰기 방식은 v1과 같습니다. 고정 샘플은 T11–T17(T16b 포함), T19, T20, T22를 담은 76행으로, 허용 64행·거절 12행과 14개 제품을 포함합니다. `tests/test_recipe.py`는 T11–T22, 거절 시 전체 제품 상태 보존, 레시피 오류 전체 표시와 이벤트 미처리, 레시피 변경에 따른 판정 차이, stdout·CSV 3종의 바이트 재현성을 검증합니다.

### v2 1단계 제외 범위

재검사·보류 해제, 설비·로트, 대량 생성기, 분기·병렬·순환 공정, 검사 PASS를 다음 공정 조건으로 거는 중간 관문, 실행 중 레시피 변경, 등록 정정, 외부 패키지는 포함하지 않습니다. 기존 v1의 DB·권한·웹 UI·LLM 및 실제 측정·품질 판정 제외도 유지합니다.

## 재검사 모드 (v2 2단계)

FAIL로 보류된 검사에 요청을 열고, 다음 검사 결과를 재검사로 처리합니다. PASS면 해당 검사의 보류가 풀립니다. 다른 미해결 FAIL이 없으면 멈췄던 공정부터 재개할 수 있습니다. 최초 FAIL과 모든 허용된 요청·시도는 이력에 남습니다.

**공정·검사·재검사·폐기는 모두 교육용 가상 규칙입니다. 재검사 상한 2회는 SL 실제 기준이 아니며, 모의 흐름 완료는 출하·양품·SL 기준 적합을 뜻하지 않습니다.**

### 켜는 법과 입력

```powershell
py -m src.main data/sample_events_retest.csv --recipe recipes/lamp_models_retest.json
py -m unittest discover -s tests
```

[재검사 레시피](recipes/lamp_models_retest.json)는 기존 `lamp_models.json`의 두 모델에 `"retest_limit": 2`만 추가한 설정입니다. **모든 모델**에 이 키가 있어야 재검사 모드가 켜집니다. 하나도 없으면 1단계의 보고서 4열·6개 규칙 집계를 사용합니다. 일부 모델에만 있거나 값이 1–5 정수가 아니면 위치별 전체 오류를 출력하고 종료 코드 3으로 끝내며 보고서는 만들지 않습니다. `true`, `false`, `"2"`, `2.0`은 정수가 아닙니다. 기본 제공 상한은 검사당 2회입니다. `RETEST_REQUEST`도 `REGISTER`, `INSPECT`처럼 공정 ID로 사용할 수 없는 예약어입니다.

CSV는 1단계와 같은 6열입니다. `RETEST_REQUEST`의 `inspection`에 검사 ID를 쓰고 `result`, `model`은 비웁니다. 다음 `INSPECT`는 **같은 제품·같은 검사**에 열린 요청이 있을 때 재검사 결과가 됩니다.

```csv
seq,product_id,event,inspection,result,model
1,a,REGISTER,,,A
2,a,P1,,,
3,a,P2,,,
4,a,P3,,,
5,a,INSPECT,LEAK,FAIL,
6,a,RETEST_REQUEST,LEAK,,
7,a,INSPECT,LEAK,PASS,
8,a,P4,,,
```

### 규칙과 폐기 기준

| 입력·조건 | 판정과 상태 |
| --- | --- |
| 현재 FAIL이며 열린 요청 없음 → 요청 | `RULE_RETEST` 허용, 요청 열림, 보류 유지. 요청만으로 횟수는 늘지 않음 |
| 미실시·PASS 검사에 요청 | `RULE_RETEST` 거절: `미해결 FAIL 없음` |
| 열린 요청에 다시 요청 | `RULE_RETEST` 거절: `이미 열린 재검사 요청` |
| 검사의 최초 결과 | 1단계 검사 시점·판정 유지. 보류 중에도 아직 안 한 다른 검사의 최초 결과는 시점 조건을 만족하면 허용 |
| 결과 있음 + 열린 요청 → 검사 | `RULE_RETEST` 허용, 요청 닫힘, 해당 검사 재검사 횟수 +1 |
| 결과 있음 + 요청 없음 → 검사 | `RULE_PRESERVE` 거절: `결과 이미 존재` |
| 재검사 PASS | 해당 검사 현재 결과가 PASS. 다른 FAIL이 없으면 보류 해소 |
| 재검사 FAIL, 상한 미달 | 보류 유지. 다시 검사하려면 새 요청 필요 |
| 재검사 FAIL, 상한 도달 | 그 FAIL 행을 **허용하면서 폐기** |
| 폐기 후 공정·검사·요청 | `RULE_RETEST` 거절: `폐기된 제품` |

횟수는 **검사마다 별도**이며 허용된 재검사 결과만 셉니다. 기본 상한 2에서 최초 FAIL → 재검사 1 FAIL → 재검사 2 FAIL이면 폐기합니다. 두 번째 재검사가 PASS이면 폐기하지 않습니다. 반복 FAIL의 공정 투입을 막고, 폐기 원인 결과를 거절로 지우지 않기 위한 가상 기준입니다. 검사 하나가 PASS가 되어도 다른 검사에 FAIL이 남으면 보류를 유지합니다.

판정 순서는 형식 오류 → 등록 처리(중복 등록 포함) → 미등록 → 폐기 → 모델 레시피에 없는 공정·검사 → 이벤트별 규칙입니다. 폐기 후에도 형식 오류·중복 등록은 `RULE_PRESERVE`가 먼저입니다. 요청에 `inspection`이 없거나 `result`·`model`을 쓰면 형식 오류입니다. 재검사 모드가 아닌 레시피에 정상 형식의 요청을 입력하면 `RULE_RECIPE`로 거절합니다. **거절은 공정 위치·현재 결과·이력·열린 요청·횟수·폐기 상태를 바꾸지 않습니다.**

### 상태·보고서와 고정 샘플

상태 우선순위는 `폐기` → `보류` → `레시피 모의 흐름 완료` → `등록` → `공정 진행 중(Pk 완료)` → `검사 대기`입니다. 요청 중인 FAIL의 미완료 이유에는 `LEAK FAIL(재검사 요청됨)`을 표시합니다. 폐기 이유는 `LEAK 재검사 한도 2회 초과 FAIL로 폐기`로 표시하며, 여기서 “초과”는 두 번째 재검사 FAIL에 도달한 시점을 뜻합니다.

| 보고서 | 형식 |
| --- | --- |
| `reports/sample_events_retest_rows.csv` | 기존과 같은 `seq,product_id,input,rule_id,decision,rejection_reason,state` |
| `reports/sample_events_retest_products.csv` | `product_id,model,state,incomplete_reason,history` |
| `reports/sample_events_retest_rejections.csv` | 기존 6개 규칙 뒤에 `RULE_RETEST` 추가, 0건 포함 7개 |

history 예: `LEAK: FAIL@5 → 요청@6 → PASS@7(재검사 1)`. 시도가 있는 검사만 레시피 검사 순서로 표시하고 검사 사이는 `; `로 나눕니다. 그룹 안에서는 입력된 순서를 유지하며 `@` 뒤 숫자는 입력 행의 seq입니다. 거절된 요청·결과는 이력에 추가하지 않습니다.

[고정 샘플](data/sample_events_retest.csv)은 T23–T30을 제품별로 담은 102행으로, 허용 90·거절 12와 등록 제품 12개를 포함합니다. 거절 집계는 `RULE_RECIPE 1`, `RULE_SEQ 0`, `RULE_INSP_PRE 0`, `RULE_NOT_DONE 0`, `RULE_FAIL_HOLD 1`, `RULE_PRESERVE 4`, `RULE_RETEST 6`입니다. `tests/test_retest.py`는 T23–T32, 전체 상태 불변, 복수 FAIL·동시 요청·검사별 횟수, 보고서와 터미널 출력의 바이트 재현성을 검사합니다. 같은 경로의 입력과 레시피로 실행하면 동일한 결과를 만듭니다.

### 이번 단계 제외 범위

설비·로트, 대량 생성기, 요청 ID·시도 ID 열 추가, 재검사 설비 지정, 폐기 취소, 레시피별 다른 상한 정책은 포함하지 않습니다. 분기·병렬·순환 공정, 중간 검사 관문, 실행 중 레시피 변경, 등록 정정과 실제 측정·품질 판정도 제외합니다.

## 설비 모드 (v2 3단계)

검사마다 사용한 설비를 기록하고, 같은 설비의 허용된 최초 검사에서 FAIL이 몰리면 그 설비를 정지합니다. 제품의 검사 결과와 재검사·폐기 규칙은 그대로 적용합니다.

### 켜는 법과 입력

```powershell
py -m src.main data/sample_events_equipment.csv --recipe recipes/lamp_models_retest.json --equipment recipes/equipment.json
py -m unittest discover -s tests
```

`--equipment`는 `--recipe`와 함께만 사용합니다. 재검사 설정이 없는 `lamp_models.json`과도 함께 쓸 수 있습니다. `--equipment`가 없으면 기존 v1·1단계·2단계의 입력과 출력이 유지됩니다. 설비 파일은 자동 선택되지 않습니다.

설비 모드의 CSV 헤더는 순서까지 다음 7열이어야 합니다. `equipment`는 `INSPECT`에서만 필수이며 등록·공정·재검사 요청에서는 비웁니다. `model`은 등록에만 쓰고, 재검사 요청에는 `inspection`만 씁니다.

```csv
seq,product_id,event,inspection,result,model,equipment
1,a,REGISTER,,,A,
2,a,P1,,,,
3,a,P2,,,,
4,a,P3,,,,
5,a,INSPECT,LEAK,FAIL,,LEAK-2
6,a,RETEST_REQUEST,LEAK,,,
7,a,INSPECT,LEAK,PASS,,LEAK-1
```

설비 옵션 없이 7열 CSV를 쓰거나 설비 모드에 다른 헤더를 쓰면 종료 코드 2입니다. `--recipe` 없이 설비 옵션만 써도 코드 2입니다.

### 설비 파일과 정지 기준의 출처·한계

[recipes/equipment.json](recipes/equipment.json)은 모델과 무관하게 공유하는 설비 ID와 담당 검사, 정지 규칙을 정의합니다.

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

허용된 **최초 검사 결과만** 설비별 입력 순서로 셉니다. 최근 최대 `window`건 중 FAIL이 `fails`건 이상이면 원인 행을 허용·기록한 직후 설비를 정지합니다. 재검사와 거절 행은 세지 않습니다. 기본값에서는 FAIL → PASS → FAIL의 세 번째 뒤 정지하며, FAIL → FAIL이면 두 번째 뒤 정지합니다. FAIL → PASS → PASS → FAIL은 최근 3건 중 FAIL이 하나여서 가동을 유지합니다. `seq`가 중복·감소해도 물리적인 처리 순서를 따릅니다. 정지는 실행이 끝날 때까지 유지합니다.

이 기준은 Western Electric 관리도 규칙의 “연속 3점 중 2점” 패턴을 PASS/FAIL에 맞게 단순화한 **교육용 가상 규칙**입니다. [NIST의 WECO 규칙 설명](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc32.htm)은 측정값이 중심선 같은 쪽의 2σ 경계를 넘는 패턴을 다룹니다(확인: 2026-10-18). 여기서는 측정값·평균·σ·관리한계를 계산하지 않습니다. **원래 통계 규칙과 동일하지 않으며, 업계 공통 설비 정지 기준이나 SL 실제 기준으로 검증된 숫자가 아닙니다.** 설비 고장을 확정하지도 않습니다.

설비 ID는 `^[A-Z][A-Z0-9_-]*$` 형식이고 `equipment`는 비어 있지 않아야 합니다. 담당 검사는 레시피의 어느 모델에라도 있어야 합니다. 최상위 허용 키는 `stop_rule`, `equipment`, 정지 규칙 키는 `window`, `fails`뿐입니다. 두 수는 `1 ≤ fails ≤ window ≤ 20`의 정수여야 하며 bool·문자열·소수는 거절합니다. 누락·잘못된 구조·알 수 없는 키·ID·참조 오류를 위치와 함께 모두 표시합니다. 파일 읽기·인코딩·JSON 오류도 종료 코드 3이며 이벤트 처리와 보고서 생성 전에 중단합니다.

### 설비 규칙과 상태 보존

| 조건 | 판정 |
| --- | --- |
| 설비 목록에 없는 설비 | `RULE_EQUIP` 거절: `등록되지 않은 설비` |
| 담당 검사와 다른 검사 | `RULE_EQUIP` 거절: `검사 종류가 다른 설비` |
| 정지 설비의 최초 검사·재검사 | `RULE_EQUIP` 거절: `정지된 설비` |
| INSPECT의 equipment 빈칸 | `RULE_PRESERVE` 거절 |
| 다른 이벤트의 equipment 기입 | `RULE_PRESERVE` 거절 |
| 허용된 최초 검사로 정지 임계치 도달 | 원인 행 허용, 제품에 결과 반영, 설비 정지 |

판정 순서는 형식 → 등록·미등록 → 폐기 → 레시피 → 설비(등록·종류·정지) → 검사 시점 → 기존 최초·재검사 규칙입니다. 정지 설비에서 거절된 재검사는 열린 요청을 소진하지 않습니다. 그 요청으로 가동 중인 같은 종류의 다른 설비에서 재검사할 수 있습니다. **모든 거절은 전체 제품 상태·이력·요청·횟수·폐기 여부와 전체 설비 기록·정지 상태를 바꾸지 않습니다.**

### 보고서와 고정 샘플

기존 3종에 `reports/<입력파일명>_equipment.csv`가 추가됩니다. 터미널에는 레시피와 설비 파일 경로·원본 SHA-256 앞 12자리를 표시하고 설비별 최종 상태도 출력합니다.

| 설비 보고서 열 | 의미 |
| --- | --- |
| `equipment`, `inspection` | 설비 파일에 적힌 순서의 설비 ID와 담당 검사 |
| `counted_results`, `fail_count` | 허용된 최초 결과의 누적 건수와 그중 누적 FAIL 건수. 정지 판단용 최근 창과 별개 |
| `state` | `가동` 또는 `정지` |
| `stopped_at_seq` | 정지를 일으킨 입력의 seq. 가동이면 빈칸 |

미사용 설비도 0건·가동으로 표시합니다. rows의 입력 예는 `INSPECT LEAK FAIL @LEAK-2`이고, 재검사 모드의 history 예는 `LEAK: FAIL@5[LEAK-2] → 요청@6 → PASS@7[LEAK-1](재검사 1)`입니다. 거절 결과는 history에 넣지 않습니다. 거절 집계는 기존 규칙 뒤에 `RULE_EQUIP`를 붙여, 재검사 모드는 8개·아니면 7개입니다. 파일 인코딩·저장 위치는 기존과 같고 같은 입력·설정·경로에서는 보고서 4종과 터미널 출력이 바이트 단위로 재현됩니다.

[고정 샘플](data/sample_events_equipment.csv)은 T33–T39를 담은 94행(허용 87·거절 7), 제품 17개입니다. T33과 T35는 같은 최초 FAIL·요청·정지 이력을 공유하고, `BUFFER_` 제품의 허용 PASS로 공유 설비의 이전 창을 정리합니다. LEAK-2는 seq 25에서 누적 3건/FAIL 2건으로, LEAK-1은 seq 94에서 누적 12건/FAIL 5건으로 정지합니다. LIGHT-1·FINAL-1은 미사용·가동입니다. 거절은 `RULE_EQUIP 4`, `RULE_PRESERVE 2`, `RULE_INSP_PRE 1`이며 나머지 규칙은 0건입니다. `tests/test_equipment.py`에서 T33–T41, 모든 거절의 전체 상태 불변, 파일 오류, 기존 보고서 9개 보존과 출력 재현성을 검증합니다.

### 이번 단계 제외 범위

설비 재가동·점검 이벤트, 로트 ID, 공정 설비, 정지 원인 FAIL 제품의 자동 재검사 요청, 측정값·관리한계 계산은 포함하지 않습니다. 실제 설비 제어나 실제 제조 품질 판정을 수행하지 않습니다.
