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

한 번 정지하면 재가동하지 않으므로 고정 샘플의 T39는 아직 가동 중인 LEAK-1에서 같은 판정을 재현합니다. 독립 T39 단위 테스트는 기대표의 LEAK-2를 그대로 사용합니다.

### 이번 단계 제외 범위

(3단계 당시 제외한 설비 재가동·점검 이벤트는 v2 5단계에서 추가했습니다.) 로트 ID, 공정 설비, 정지 원인 FAIL 제품의 자동 재검사 요청, 측정값·관리한계 계산은 포함하지 않습니다. 실제 설비 제어나 실제 제조 품질 판정을 수행하지 않습니다.

## 생성기·분석·추적 (v2 4단계)

시드가 고정된 합성 생산 기록으로 판정기를 대량 검증하고, 최초 검사 품질·입력 오류·설비 정지 영향을 따로 분석합니다. 앞 절들은 각 개발 단계의 범위를 기록한 것입니다.

**생성 데이터의 확률은 가정이며 실제 설비 진단 근거가 아니다.**

### 실행

프로젝트 루트에서 실행합니다. 외부 패키지는 필요하지 않습니다.

```powershell
py -m src.generate --seed 42 --products 500 --out data/generated/gen_seed42.csv
py -m src.main data/generated/gen_seed42.csv --recipe recipes/lamp_models_retest.json --equipment recipes/equipment_generated.json --summary --trace GEN_0005
py -m unittest discover -s tests
```

생성기의 기본값은 `--seed 42`, `--products 500`, `--config recipes/generator.json`입니다. 설정의 `recipe`, `equipment` 경로는 설정 파일이 있는 디렉터리를 기준으로 해석합니다. 기본 레시피는 `lamp_models_retest.json`, 설비는 별도의 `equipment_generated.json`이며 기존 `equipment.json`은 그대로입니다.

`--summary`와 `--trace`는 `--recipe`·`--equipment`가 있는 설비 모드에서만 사용하며 아니면 종료 코드 2입니다. trace는 `--trace T34 --trace T33_T35_A`처럼 반복할 수 있습니다. 입력에 없는 제품 ID를 하나라도 요청하면 코드 2이며 기존 보고서 4종을 포함해 보고서를 새로 저장하지 않습니다. 입력에 행이 있으나 등록되지 않은 ID는 거절 이력을 추적하고 최종 상태를 `미등록`으로 표시합니다.

추가 옵션이 없으면 기존 실행 경로와 보고서가 유지됩니다. summary·trace는 기존 보고서 반환 묶음에 붙이지 않고 별도의 분석·저장 경로로 처리합니다. 출력 CSV는 기존처럼 UTF-8 BOM과 CSV 줄 끝을 사용합니다.

| 출력 | 내용 |
| --- | --- |
| `data/generated/gen_seed42.csv` | 생성된 입력 7열 |
| `data/generated/gen_seed42.csv.meta.json` | 시드·제품 수·생성기 버전·설정/레시피/설비 원본 SHA-256·정상/전체 행 수·오류 종류별 주입 수·결함품 수(`defective_count`)와 ID 목록(`defective_products`) |
| `reports/gen_seed42_{rows,products,rejections,equipment}.csv` | 기존 형식의 보고서 4종 |
| `reports/gen_seed42_summary.csv` | `section,key,value,...` 긴 표 하나 |
| `reports/gen_seed42_trace_GEN_0005.csv` | 대표 제품의 물리 행 순서·처리 후 상태·최종 근거 |

### 생성 가정과 재현 조건

생성기 버전은 `1.1.0`이며, **같은 시드 + 같은 설정·참조 파일 바이트 + 같은 생성기 버전**에서 CSV와 meta가 바이트 단위로 같습니다. 난수는 `random.Random(seed)` 하나만 사용하고 시각·환경·출력 경로는 난수와 메타 내용에 넣지 않습니다. 설정 파일의 줄 끝도 SHA-256 원본 바이트에 포함됩니다.

| 가정 | 기본값 |
| --- | --- |
| 모델 비율 | A 50%, B 50%의 추출 확률 |
| 정상 설비 FAIL | 2% |
| 고장으로 가정한 설비 | LEAK-2, FAIL 30% |
| 결함 제품 | 제품당 2% 확률로 한 번 추출. 결함품의 모든 최초·재검사 FAIL은 설비와 무관하게 90% |
| FAIL 후 재검사 요청 | 매 FAIL마다 70%, 재검사 상한 2회 |
| 입력 오류 주입 | 정상 행 수의 3%, 정수화는 내림, 5종 균등(차이 최대 1) |
| 설비 | LEAK 3대, LIGHT·FINAL 각 2대 |
| 정지 | 허용된 최초 결과의 최근 최대 3건 중 FAIL 2건 |

제품별로 등록 → 레시피 공정 → `after` 직후 검사 순서를 만들고, 제품 사이에는 한 행씩 라운드로빈으로 섞습니다. 검사를 할 수 있는 가동 설비를 순환 선택하고, 재검사는 가능하면 해당 검사의 처음 FAIL 설비와 다른 설비를 씁니다. 생성기도 최초 결과에 같은 정지 규칙을 적용합니다. 같은 검사 설비가 모두 정지하면 그 제품의 생성을 해당 검사에서 끝냅니다. 기존 판정 상태 정의에 따라 중간 검사에서 멈춘 제품이 `공정 진행 중`으로 표시될 수 있으며 미실시 검사와 미완료 이유를 함께 확인해야 합니다.

모델을 모두 추첨한 뒤 제품별 등록 전에 같은 난수 흐름으로 결함 여부를 한 번 정합니다. 결함품은 설비 확률 대신 FAIL 90%를 쓰며, 정상품은 기존 설비 확률을 따릅니다. 결함 여부는 CSV나 판정기 입력에 포함하지 않고 meta에만 기록합니다. summary의 「주입 대비 결과」(`injection_comparison`)에서만 결함품의 최종 상태와 정상품의 폐기 수를 비교합니다. 이 가정은 재검사로 설비를 바꿔도 제품 자체의 결함 때문에 FAIL이 반복될 수 있다는 뜻입니다.

오류 5종은 미래 공정 건너뜀·`result=OK`·요청 없는 중복 결과·없는 설비 `LEAK-9`·B 제품의 `P5`입니다. 정상 행을 바꾸지 않고 당시 상태에서 거절될 위치에 추가합니다. 주입 종류의 나머지 배분과 위치 선택도 같은 난수 흐름을 씁니다. 주입률의 분모는 정상 행 수이고 최종 거절률의 분모는 오류를 포함한 전체 입력 행 수입니다. 둘은 다른 지표이며 정지 설비 거절이 추가되면 더 달라질 수 있습니다. meta가 옆에 없으면 주입 대비 절은 생략합니다.

제품 수가 양수여도 배정된 오류 종류마다 유효한 주입 위치가 있어야 생성할 수 있습니다. 모델은 확률로 추출하므로 고정된 최소 제품 수로 이 조건을 보장할 수 없습니다. 예를 들어 `--seed 39 --products 4`는 B 제품이 없는데 B의 `P5` 오류가 1건 배정되어 실패합니다. 이 경우 다른 종류로 재배분하지 않고, 오류 종류·배정 수·후보 부재 이유를 표시하며 종료 코드 2로 끝납니다. CSV와 meta를 쓰기 전에 중단하므로 기존 출력도 덮어쓰지 않습니다.

옆에 있는 meta.json은 객체이고 `normal_rows`가 0 이상의 정수이며 `injected_errors`가 값이 0 이상의 정수인 객체여야 합니다. 키는 주입 오류 5종 코드(`SEQ_SKIP`, `PRESERVE_BAD_RESULT`, `PRESERVE_DUP_RESULT`, `EQUIP_UNKNOWN`, `RECIPE_UNKNOWN_STEP`)만 허용하며, 빠진 종류는 0건으로 표시합니다. 구조·값 타입·키가 잘못되면 메시지와 함께 종료 코드 2로 끝나며 보고서를 쓰지 않습니다.

`defective_products`는 선택 항목이며, 있으면 비어 있지 않은 제품 ID 문자열의 배열이어야 하고 중복 ID는 허용하지 않습니다. 빈 배열은 결함품 0개입니다. 목록의 ID는 입력 CSV에서 등록이 허용된 제품의 ID와 대소문자·앞뒤 공백까지 정확히 일치해야 합니다. 구조 오류나 미등록 ID는 보고서를 저장하기 전에 종료 코드 2로 처리합니다. 「그 밖」은 등록·공정 진행 중·검사 대기 등 실제 등록된 결함품의 나머지 상태만 셉니다. 해당 키가 없는 이전 meta의 주입 비교 출력은 유지합니다.

그래프·헤더/CSV 구문 오류 생성·설비 재가동은 포함하지 않습니다. 확률은 실측 추정치가 아니며 정지로 관측이 일찍 끝나는 선택 효과도 있습니다. 예를 들어 LEAK-2가 두 번 FAIL 뒤 멈췄다고 관측 FAIL률 100%를 실제 고장 확률로 해석할 수 없습니다.

### 지표와 긴 표의 절

| 지표/절 | 정의 |
| --- | --- |
| 최초 FAIL률 | 허용된 최초 FAIL 수 / 허용된 최초 결과 수. 설비별·검사별·전체, 폐기 제품의 최초 결과도 포함 |
| 재검사 포함 FAIL률 | 허용된 모든 FAIL 수 / 허용된 모든 검사 결과 수 |
| FPY | 모든 필수 검사를 최초 PASS하고 완료한 제품 수 / 등록된 제품 수 |
| 상태 분포 | 완료·보류·폐기·검사 대기·공정 진행 중·등록. 등록 제품 총수는 별도 표시 |
| 거절·미실시 | FAIL률 분모에서 제외하고 `rejected_count`, `unperformed_count`로 표시. 미실시는 검사별/전체, 미배정 설비에는 귀속하지 않음 |
| 품질 파레토 | (검사, 설비)의 최초 FAIL 수 내림차순, 동률은 검사 ID·설비 ID 순. 전체 FAIL도 옆 열에 표시하며 재검사 FAIL만 있는 조합도 포함 |
| 입력 오류 파레토 | 상세 사유 코드 건수 내림차순, 동률은 코드 순. 각 코드에 rule_id 표시 |
| 설비 정지 영향 | 설비별 상태·정지 물리 행/seq/제품 ID·창의 FAIL 원인 행들·정지 후 거절 결과 수 |
| 거절 합계 | 전체 거절 = 규칙별 거절 합 = 입력 오류 파레토 합 + 정지 설비 거절 + 기타 거절 |
| 주입 대비 | meta의 오류 종류별 주입 수와 실제 상세 사유 코드 거절 수를 나란히 표시. TOTAL 주입률은 주입 수 / 정상 행 수. 결함 목록이 있으면 결함품의 폐기·보류·완료·그 밖 수와 정상품 폐기 수도 표시 |

비율은 소수 넷째 자리까지 사사오입한 문자열이며(예: `1/32 = 0.03125` → `0.0313`) 분모 0은 빈칸입니다. summary의 `product_metrics`, `status_distribution`, `inspection_metrics`, `equipment_metrics`, `quality_pareto`, `input_error_pareto`, `equipment_stops`, `rejection_totals`, `rule_rejections`, `injection_comparison`, `notice` 절에서 위 값을 확인합니다. `injection_comparison`은 meta가 있을 때만 나옵니다.

### 고정 상세 사유 코드

`src/reason_codes.py`가 원본 표입니다. 규칙 ID와 정확한 이유 문구의 쌍으로 변환하며 `{inspection}`, `{event}`는 실제 입력 ID, `{step}`은 레시피 공정으로 재구성한 템플릿입니다. 표에 없는 문구는 summary를 실패시켜 숨은 사유로 묶지 않습니다. `EQUIP_STOPPED`는 입력 오류 파레토에서 제외하고 설비 정지 영향 절에 셉니다. 현재 표에 해당하는 나머지는 모두 입력 오류이므로 기타 거절은 0입니다.

| 상세 코드 | rule_id | 이유 문구 |
| --- | --- | --- |
| PRESERVE_COLUMNS | RULE_PRESERVE | CSV 열 수 또는 값 누락 |
| PRESERVE_BAD_SEQ | RULE_PRESERVE | seq는 양의 정수여야 함 |
| PRESERVE_EMPTY_PRODUCT | RULE_PRESERVE | product_id가 비어 있음 |
| PRESERVE_EMPTY_EVENT | RULE_PRESERVE | event가 비어 있음 |
| PRESERVE_MODEL_FIELD | RULE_PRESERVE | REGISTER 이외의 model은 빈칸이어야 함 |
| PRESERVE_EMPTY_INSPECTION | RULE_PRESERVE | inspection이 비어 있음 |
| PRESERVE_BAD_RESULT | RULE_PRESERVE | 잘못된 result (PASS 또는 FAIL 필요) |
| PRESERVE_RETEST_RESULT | RULE_PRESERVE | RETEST_REQUEST의 result는 빈칸이어야 함 |
| PRESERVE_INSPECTION_FIELDS | RULE_PRESERVE | INSPECT 이외의 inspection과 result는 빈칸이어야 함 |
| PRESERVE_EMPTY_EQUIPMENT | RULE_PRESERVE | equipment가 비어 있음 |
| PRESERVE_EQUIPMENT_FIELD | RULE_PRESERVE | INSPECT 이외의 equipment는 빈칸이어야 함 |
| PRESERVE_DUP_REGISTER | RULE_PRESERVE | 이미 등록된 제품 |
| PRESERVE_UNREGISTERED | RULE_PRESERVE | 미등록 제품 |
| PRESERVE_DUP_RESULT | RULE_PRESERVE | {inspection} 결과 이미 존재 |
| PRESERVE_PAST_STEP | RULE_PRESERVE | 이미 지난 공정 재입력 |
| RECIPE_UNKNOWN_MODEL | RULE_RECIPE | model이 비어 있거나 레시피에 없는 모델 |
| RECIPE_RETEST_DISABLED | RULE_RECIPE | 재검사 모드가 아닌 레시피 |
| RECIPE_UNKNOWN_INSPECTION | RULE_RECIPE | 제품 레시피에 없는 검사 {inspection} |
| RECIPE_UNKNOWN_STEP | RULE_RECIPE | 제품 레시피에 없는 공정 {event} |
| SEQ_SKIP | RULE_SEQ | {step} 미완료 |
| INSP_TOO_EARLY | RULE_INSP_PRE | {step} 미완료 |
| FAIL_HOLD | RULE_FAIL_HOLD | FAIL로 보류 중인 제품 |
| RETEST_DISCARDED | RULE_RETEST | 폐기된 제품 |
| RETEST_ALREADY_OPEN | RULE_RETEST | 이미 열린 재검사 요청 |
| RETEST_NO_FAIL | RULE_RETEST | 미해결 FAIL 없음 |
| EQUIP_UNKNOWN | RULE_EQUIP | 등록되지 않은 설비 |
| EQUIP_WRONG_INSPECTION | RULE_EQUIP | 검사 종류가 다른 설비 |
| EQUIP_STOPPED | RULE_EQUIP | 정지된 설비 |

### trace 읽기

전체 입력 처리가 끝난 뒤 선택한 제품의 행만 **물리적 입력 순서**로 표시합니다. `row_index`는 헤더를 제외하고 1부터 센 데이터 행이며 `seq`의 중복·감소와 무관합니다. 각 행의 입력·설비·규칙·허용/거절·이유·처리 후 상태, 마지막 `current_state`의 최종 상태·미완료 이유·history를 확인합니다. 파일명에 쓸 수 없는 제품 ID 문자는 percent encoding합니다. 전체 입력에 `p`와 `P`처럼 Windows에서 파일명이 충돌하는 ID가 있으면 해당 ID에만 `!`와 원본 UTF-8 바이트의 16진수 접미사를 붙입니다. 요청한 ID의 부분집합이나 기존 파일 유무와 관계없이 같은 이름을 사용합니다.

정지 설비 거절 행에는 `stop_row_index`, `stop_seq`, `stop_product_id`와 `cause_row_indices`, `cause_seqs`, `cause_product_ids`가 붙습니다. 기존 설비 샘플을 `--trace T34`로 실행하면 seq 30 거절의 근거가 정지 행 25/T33_P3, FAIL 행 14/T33_T35_A와 25/T33_P3임을 확인할 수 있습니다. 다른 제품의 원인 행은 근거 열에만 연결하므로 선택 제품의 행 순서는 유지됩니다.

### 시드 42 실행 결과와 검증 한계

위 명령을 이 PC에서 실행한 결과입니다. 전체 원문은 `handoff/gpt-log.md`의 완료 보고와 연결된 `handoff/run-logs/`에 있습니다.

| 항목 | 실제 결과 |
| --- | --- |
| 등록 제품 | 500 |
| 정상 행 / 추가 오류 행 / 전체 행 | 4,018 / 120 / 4,138 |
| 완료 / 보류 / 폐기 | 487 / 9 / 4 |
| 결함품 | 추출 6개: 폐기 4 / 보류 2 / 완료 0 / 그 밖 0. 정상품 폐기 0 |
| FPY | 470/500 = `0.9400` |
| 최초 FAIL률 | 30/1,236 = `0.0243` |
| 재검사 포함 FAIL률 | 38/1,261 = `0.0301` |
| 거절 검사 / 미실시 검사 | 72 / 12 |
| 주입률 / 최종 거절률 | 120/4,018 = `0.0299` / 120/4,138 = `0.0290` |
| 입력 오류 / 정지 설비 거절 / 기타 | 120 / 0 / 0 |
| 오류 5종 | 각각 주입 24·실제 거절 24 |
| 정지 설비 | LEAK-2, seq 1571/GEN_0030, 원인 FAIL seq 1559/GEN_0018·1571/GEN_0030. FINAL-1, seq 3962/GEN_0195, 원인 FAIL seq 3960/GEN_0192·3962/GEN_0195 |

대표 trace `GEN_0005`는 LEAK 최초 PASS@1546[LEAK-2], LIGHT 최초 PASS@3087[LIGHT-2] 뒤 완료한 제품입니다.

수정 1 적용 뒤 전체 테스트 105개가 통과했습니다. T44의 빈 검증 조건은 폐기 4개를 포함해 모두 충족하며, 기존 기대값·시드·설비 확률·재검사 요청 확률은 유지했습니다. 결함품 2%는 추출 확률이므로 500개 중 정확히 10개를 보장하지 않습니다. 이는 실제 불량률의 추정이나 진단 결과가 아닙니다.

`tests/test_generate.py`는 시드 42/500개와 7/200개에서 CSV·meta·기존 보고서 4종·summary·trace 재현성, 완료 제품의 모든 공정/PASS, 정지·폐기 뒤 허용 금지, 거절 합계, **모든 행마다 판정기를 deepcopy한 뒤 거절 전후 전체 제품·설비 상태 동일성**을 검사합니다. 500개 검사도 생략하지 않았습니다. `tests/test_summary.py`는 손계산 4제품 fixture(T45), 정지·입력 오류 분리(T46), 물리 순서와 교차 제품 trace(T47), 잘못된 옵션·없는 ID의 무출력 파일(T48), 미등록 이유 실패(T49)를 검사합니다. 기존 T1–T41 테스트 4개 파일과 `src/rules.py`는 수정하지 않았고 기존 샘플 보고서 13개도 재생성 바이트 비교를 통과했습니다.

## 설비 복구와 정지 규칙 평가 (v2 5단계)

정지만 있던 설비 모델에 점검 후 재가동을 추가하고, 정지 규칙을 여러 시드의 수치로 평가합니다. 이 단계부터 구현은 Claude Code, 읽기 전용 검수는 Codex(`gpt-6-astra`)가 맡습니다.

**생성 데이터의 확률은 가정이며 실제 설비 진단 근거가 아니다.** 점검 소요·수리 효과도 가정입니다.

### 재가동

설비 파일에 `"restart_enabled": true`가 있을 때만 켜집니다. 없으면 이전 단계의 입력과 출력이 그대로입니다. 7열 CSV에 새 이벤트 하나를 씁니다.

```csv
seq,product_id,event,inspection,result,model,equipment
24,,EQUIP_RESTART,,NO_FAULT,,LEAK-1
```

`result`는 `FIXED`(이상 발견·조치) 또는 `NO_FAULT`(이상 없음)이고 `product_id`, `inspection`, `model`은 빈칸입니다. 재가동은 정지 설비에만 허용합니다. 재가동하면 정지 판단 창을 비웁니다. 누적 건수는 유지합니다. 보류 해제나 열린 재검사 요청 소진은 하지 않습니다. 새 거절 사유 코드는 `EQUIP_NOT_STOPPED`, `PRESERVE_RESTART_PRODUCT`, `PRESERVE_RESTART_FIELDS`, `PRESERVE_BAD_RESTART_RESULT`입니다.

```powershell
py -m src.main data/sample_events_restart.csv --recipe recipes/lamp_models_retest.json --equipment recipes/equipment_restart.json --summary --trace f
```

재가동 모드의 equipment 보고서에는 `stop_count,restart_count,last_restart_result`가 붙습니다. summary의 `equipment_stops`는 정지 1건당 1행(`LEAK-1#1`)이고 `equipment_restarts` 절이 추가됩니다. trace의 정지 거절 행은 그 행 시점에 유효했던 정지를 가리킵니다.

### 생성기 가정

`recipes/generator_restart.json`은 기본 설정에 `"restart": {"delay_rows": 30}`을 더합니다. 설비가 멈추면 30행 뒤 재가동 행을 넣습니다. 이 행 수는 오류 주입 전 정상 생성 행 기준입니다. 주입 오류 행은 나중에 끼워 넣으므로 최종 CSV에서는 정지와 재가동 사이가 30행보다 길 수 있습니다. 같은 검사 설비가 모두 멈추면 제품은 끝나지 않고 기다립니다. 점검은 항상 맞다고 가정해 수리되지 않은 고장 설비는 `FIXED`, 나머지는 `NO_FAULT`입니다. `FIXED` 뒤 그 설비의 FAIL 확률은 정상값입니다. 생성기 버전은 재가동 설정에서만 `1.2.0`입니다.

**한계:** 실제 시각이 없습니다. 제품이 같은 라운드에 같은 공정을 함께 지나가는 동시 투입 구조라, 행 수는 비가동 시간이 아닙니다. 고장은 생산 시작부터 존재합니다.

### 평가

```powershell
py -m src.evaluate --seeds 0-99 --rules 3:2,5:2,5:3,10:3,10:4,20:4 --out eval_dev
py -m src.evaluate --seeds 1000-1099 --rules 3:2 --out eval_holdout --holdout
py -m src.evaluate --config recipes/generator.json --seeds 0-99 --rules 3:2 --out eval_baseline --holdout
```

`--holdout`은 규칙을 고르지 않고 기준 충족만 표시합니다. 정탐은 정지 시점에 수리되지 않은 고장 설비의 정지, 나머지는 오탐입니다. 검출 지연은 고장 설비의 첫 정지까지 처리한 최초 검사 수입니다. 미완료는 완료가 아닌 제품 전체로 보류·폐기를 포함합니다. 보류는 전체 보류 평균(`mean_held`)과 그중 정상품 보류 평균(`mean_normal_held`)을 따로 냅니다. 검출률은 고장 설비를 정탐 정지한 실행 ÷ 실행 수입니다. 고장 설비가 여러 대인 설정은 검출률 단위가 정해지지 않아 종료 코드 2로 거절합니다.

선택 기준은 결과를 보기 전에 고정했습니다(`handoff/decisions.md`, 2026-10-30): 검출률 0.95 이상, 평균 지연 10 이하 규칙 중 오탐 평균이 가장 낮은 규칙. 시드 1000–1099는 확인에만 씁니다.

### 평가 결과

재가동 설정, 제품 500개, 시드 0–99입니다.

| 규칙 | 검출률 | 평균 지연 | 정지 정밀도 | 오탐 평균 | 전면 정지 실행 | 기준 |
| --- | --- | --- | --- | --- | --- | --- |
| 3:2 | 1.0000 | 9.71 | 0.3448 | 1.90 | 3 | **충족, 선택** |
| 5:2 | 1.0000 | 7.84 | 0.2227 | 3.49 | 6 | 충족 |
| 10:3 | 1.0000 | 11.31 | 0.5291 | 0.89 | 0 | 지연 초과 |
| 20:4 | 1.0000 | 13.64 | 0.6623 | 0.51 | 0 | 지연 초과 |
| 10:4 | 1.0000 | 17.40 | 0.9346 | 0.07 | 0 | 지연 초과 |
| 5:3 | 1.0000 | 19.77 | 0.8772 | 0.14 | 0 | 지연 초과 |

- 사전 기준으로는 현행 3:2가 선택됩니다. 홀드아웃(시드 1000–1099)에서도 검출률 1.0000, 평균 지연 8.47로 기준을 유지했습니다(`확인`).
- 선택됐다고 오탐 문제가 해결된 것은 아닙니다. 3:2의 정지 정밀도는 약 0.34로, 정지 3건 중 2건가량이 오탐입니다. 오탐 평균을 낮추려면 검출 지연을 늘려야 하는 교환 관계가 수치로 드러났습니다.
- 재가동 효과(3:2, 시드 0–99): 전면 정지 실행은 49회에서 3회로, 미완료 최대는 417개에서 26개로 줄었습니다. 대신 결함품 완료 평균은 0.16에서 0.30으로 늘었습니다. 재가동 없이는 멈춰 있던 제품까지 끝까지 흐르기 때문으로 보이며, 원인은 별도로 검증하지 않았습니다.
- 평가는 규칙을 제안만 합니다. 설비 파일의 `stop_rule`은 바꾸지 않았습니다.

### 이번 단계 제외 범위

실제 시각·UPH·OEE, 공정 설비, 로트 ID, 측정값·Cpk, 그래프, 생산 중간에 시작되는 고장, 재가동 취소는 포함하지 않습니다.

## 격리 범위와 로트 (v2 6단계)

설비가 멈췄을 때 이미 PASS로 지나간 제품 중 어디까지 의심할지 뽑고, 방식별 포착률과 격리량을 비교합니다. 격리는 분석 보고서이며 제품 상태를 바꾸지 않습니다.

**생성 데이터의 확률은 가정이며 실제 설비 진단 근거가 아니다.** 이 단계의 생성 가정은 5단계와 달라 수치를 직접 비교할 수 없습니다.

### 로트 모드

설비 파일에 `"lot_tracking": true`가 있을 때만 켜집니다. CSV는 기존 7열 뒤에 `lot`을 붙인 8열이고, `REGISTER`에서만 씁니다. 형식은 `^[A-Z0-9_-]+$`입니다. products 보고서에는 `model` 뒤에 `lot` 열이 붙습니다.

```powershell
py -m src.main data/sample_events_lot.csv --recipe recipes/lamp_models_retest.json --equipment recipes/equipment_lot.json --summary --containment
```

### 격리 보고서

`--containment`는 설비 모드에서 `reports/<입력>_containment.csv`를 만듭니다. 대상은 정지 시점까지 그 설비에서 최초 검사 PASS를 받은 제품입니다. 재검사 PASS는 제외하고, 다른 검사로 보류·폐기된 제품은 포함합니다. 구간은 그 설비의 허용된 가장 최근 재가동 이후입니다.

| 방식 | 의심 범위 |
| --- | --- |
| `window` | 정지 창 안의 PASS 제품 |
| `last_10`, `last_20` | 구간의 최근 10·20개 최초 검사 중 PASS 제품 |
| `lot` | 구간의 PASS 제품 중 정지 창 FAIL 제품과 같은 로트 |
| `since_restart` | 구간의 PASS 제품 전체 |

### 평가

`generator_lot.json`은 결함을 제품별 독립으로, `generator_lot_clustered.json`은 로트에 몰리게 만듭니다. 두 설정 모두 기대 결함률 5%, 고장 FAIL 0.10, 추가 검출 손실 0.5(결함품 FAIL 0.45)입니다. 유출은 결함품이 수리 전 고장 설비에서 최초 검사 PASS를 받은 경우입니다.

```powershell
py -m src.evaluate --containment --config recipes/generator_lot.json --seeds 0-99 --rules 3:2 --out eval_lot_dev
py -m src.evaluate --containment --config recipes/generator_lot.json --seeds 1000-1099 --rules 3:2 --out eval_lot_holdout --holdout --selected-from reports/eval_lot_dev_containment.csv
```

선택 기준은 결과를 보기 전에 고정했습니다(`handoff/decisions.md`, 2026-10-31): 유출품 30건 이상, 유출 실행 20회 이상이면 포착률 0.90 이상 방식 중 평균 격리량이 가장 작은 방식. 지표는 실행별 평균이 아니라 전체 합산입니다.

### 평가 결과

정지 규칙 3:2, 제품 500개, 개발 시드 0–99입니다.

| 방식 | 독립 포착률 | 독립 격리량 | 집중 포착률 | 집중 격리량 |
| --- | --- | --- | --- | --- |
| `window` | 0.0410 | 5.65 | 0.0204 | 7.30 |
| `lot` | 0.0738 | 22.85 | 0.0816 | 21.63 |
| `last_10` | 0.1475 | 41.06 | 0.1156 | 51.88 |
| `last_20` | 0.2787 | 84.96 | 0.2585 | 106.31 |
| `since_restart` | 0.8525 | 294.69 | 0.8231 | 323.01 |

- 표본 조건은 충족했습니다(독립 유출 122건·61회, 집중 147건·55회).
- **두 설정 모두 `기준 충족 방식 없음`입니다.** 사전 기준대로 어떤 방식도 고르지 않았고, 기준을 완화하지 않았습니다. 홀드아웃은 `검증할 선택 없음`입니다.
- 포착률이 가장 높은 `since_restart`도 500개 중 평균 295개 이상을 격리해 실용적이지 않습니다. 격리 정밀도는 모든 방식에서 0.01 미만입니다.
- `since_restart`의 미포착은 소수 실행에 몰립니다. 독립 18건은 4회, 집중 26건은 5회 실행에서 나왔습니다. 원인은 검증하지 않았습니다.
- 홀드아웃 시드의 `since_restart` 포착률은 0.9845, 0.9910이지만, 개발 시드 판정을 바꾸는 근거로 쓰지 않습니다.
- 집중 설정에서도 `lot` 방식의 포착률은 낮습니다. 격리 기준이 정지를 일으킨 FAIL 제품의 로트라서, 그 제품들이 고장 설비의 오판정이면 결함 로트와 무관하기 때문으로 추정합니다. 이 원인은 검증하지 않았습니다.

### 이번 단계 제외 범위

측정값, 관리도, 실제 시각, 생산 중간 고장, 자동 격리는 포함하지 않습니다.

## 측정값과 공정능력 (v2 7a단계)

레시피의 검사 항목에 규격이 있으면 측정 모드가 켜집니다. CSV는 `value` 열에 측정값을 받고, 판정기가 PASS/FAIL을 계산합니다. 규격과 분포는 모두 가상 가정이며 실제 설비 진단이나 고객 기준이 아닙니다.

```powershell
py -m src.main data/sample_events_measured.csv --recipe recipes/lamp_models_measured.json --equipment recipes/equipment_measured.json --summary --trace c --capability
py -m src.generate --seed 42 --products 500 --config recipes/generator_measured.json --out data/generated/gen_measured_seed42.csv
py -m src.main data/generated/gen_measured_seed42.csv --recipe recipes/lamp_models_measured.json --equipment recipes/equipment_measured.json --summary --containment --capability --trace GEN_0005
```

- 헤더는 `seq,product_id,event,inspection,result,model,equipment,value`입니다. 로트 설비면 `lot` 뒤에 `value`가 옵니다.
- `INSPECT`의 `result`는 빈칸이어야 합니다. 값은 원문을 보존하고 `Decimal`로 비교하며, 경계값은 PASS입니다.
- 재검사도 측정값으로 판정하지만 설비 창과 공정능력에는 넣지 않습니다.

### 공정능력 계산

- 대상은 `(검사, 설비)`별 허용된 최초 측정입니다. 재가동에서 구간을 끊고 구간 안에서 연속 5개씩 부분군을 만듭니다.
- `sigma_within = Rbar / 2.326`이고 Cpk는 이 값으로, Ppk는 전체 표본 표준편차(`N−1`)로 계산합니다.
- 완성 부분군이 25개 미만이면 `표본 부족`으로 Cpk·Ppk를 비웁니다. 25는 이 프로젝트의 표시 기준이며, `계산됨`은 산술 계산이 가능하다는 뜻입니다. 공정 안정성이나 정규성을 뜻하지 않습니다.

### 시드 42 결과 (합성 데이터)

| 검사 | 설비 | n | 부분군 | Cpk | Ppk | 상태 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| FINAL | FINAL-1 | 122 | 24 | | | 표본 부족 |
| FINAL | FINAL-2 | 122 | 24 | | | 표본 부족 |
| LEAK | LEAK-1 | 169 | 33 | 1.1743 | 1.0915 | 계산됨 |
| LEAK | LEAK-2 | 163 | 32 | 0.5215 | 0.5010 | 계산됨 |
| LEAK | LEAK-3 | 168 | 33 | 1.2057 | 1.2079 | 계산됨 |
| LIGHT | LIGHT-1 | 247 | 49 | 1.1795 | 1.1368 | 계산됨 |
| LIGHT | LIGHT-2 | 246 | 49 | 1.3168 | 1.2732 | 계산됨 |

- 제품 500개 중 완료 491, 보류 6, 폐기 3입니다. 결함품 6개는 폐기 3, 보류 3이고 완료는 0개입니다. 보류 6개 중 3개는 정상품이며, 정상품 폐기는 0개입니다.
- LEAK-2는 평균이 약 1.7 높고 Cpk가 가장 낮습니다. 고장 수치가 수리 뒤 구간과 섞인 값이므로 이 설비의 능력값으로 읽으면 안 됩니다.
- LEAK-2의 정지는 전체 4,126행 중 2,558번째 행에서 한 번뿐입니다. 값이 규격 안으로 이동하면 FAIL 기반 정지는 늦다는 것을 보여 주며, 이 단계는 규칙을 바꾸지 않았습니다.
- `process_cpk` 1.33은 정상품·정상 설비 성분의 가정입니다. 보고서의 값이 1.33과 다른 것은 결함품과 표본 변동이 섞이기 때문이고, 구현 오류의 근거가 아닙니다.

### 이번 단계 제외 범위

관리도와 정지 규칙 변경, 생산 중간 고장, 규칙 비교 평가, 정규성 검정, 측정 시스템 분석은 포함하지 않습니다.
