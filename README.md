# 교육용 가상 조립·검사 공정의 진행 조건 판정기

제품별 등록·조립 이벤트와 점등(`LIGHT`)·누설(`LEAK`) 검사 결과를 CSV로 받아, 다음 단계 진행 가능 여부와 거절 이유를 판정하는 Python CLI입니다. 현행 명세와 사전 기대표 v1(T1–T10)·v2 1단계(T11–T22)는 [handoff/tasks.md](handoff/tasks.md)에 있습니다. `docs/`의 문서는 재검사를 포함했던 이전 범위의 기록입니다.

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
