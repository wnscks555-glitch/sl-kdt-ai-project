# 현행 작업: v2 15단계 — 시연 대시보드

상태: **Sol 검토 뒤 진행 확정** (2026-10-31, 사용자 지시). 결정 근거는 `handoff/decisions.md`. 1–14단계(아래 명세)는 완료이며, 그 동작과 테스트는 보존한다.

## 목표와 경계
- 이미 나온 보고서를 읽어 한 화면에서 볼 수 있는 HTML 파일 하나를 만든다. 면접과 포트폴리오에서 바로 보여 주기 위해서다.
- 새 계산을 하지 않는다. 화면의 모든 수치는 보고서 파일에서 읽은 값이다. 예외는 로지스틱 기여값 `w_j × s_j` 표시용 곱셈 하나이고, 합이 보고서의 `z`와 맞는지 확인한다.
- 표현은 "합성 결과 대시보드"다. "실시간 모니터링 시스템", "MES", "HMI 개발 경험"으로 쓰지 않는다.
- 제외: 서버, 실시간 갱신, 외부 라이브러리·CDN·웹폰트, 사용자 입력 저장, 판정 변경.

## 보존 조건
- 기존 코드, 설정, 테스트, 기존 보고서는 수정하지 않는다. README에 절을 덧붙이는 것만 예외다.
- 새 코드는 `src/dashboard.py`, 새 테스트는 `tests/test_dashboard.py`다.
- HTML은 표준 라이브러리로 만든다. CSS와 JavaScript는 파일 안에 넣는다. 외부 URL을 만들지 않는다.

## 입력
| 절 | 파일 |
| --- | --- |
| 측정·Cpk | `reports/gen_measured_seed42_capability.csv` |
| 측정 시스템 | `reports/msa_lamp_grr.csv`, `reports/msa_lamp_guard.csv` |
| 이상 검출 | `reports/anomaly_lamp_methods.csv`, `reports/anomaly_lamp_model.csv`, `reports/anomaly_lamp_replay.csv`, `reports/spc_lamp_methods.csv`, `reports/spc_lamp_chart.csv` |
| PFMEA | `reports/pfmea_lamp_report.csv` |
| 라인 | `reports/line_lamp_compare.csv`, `reports/line_lamp_layout.svg` |
| PLC | `reports/plc_station_<scenario>.csv` 8개 |
| 사건 | `reports/incident_lamp_timeline.csv`, `reports/incident_lamp_compare.csv`, `reports/incident_lamp_suspects.csv` |

파일이나 필요한 열이 없으면 종료 코드 2이고 HTML을 만들지 않는다. 일부만 있는 화면을 내지 않는다. 로지스틱 수렴 상태는 `anomaly_lamp_model.csv`의 `fit, status`와 `fit, gradient_norm` 행에서 읽는다.

## 화면
맨 위에 고정 문구를 둔다. "모든 값은 합성 데이터와 소프트웨어 모의 결과입니다. 실제 설비, 실제 라인, SL 기준이 아닙니다."

탭 8개다. **HTML은 내용을 먼저 다 담고, JavaScript는 탭 전환과 재생만 더한다.** JavaScript가 꺼져 있으면 모든 절이 세로로 보이고, 그래프와 표도 그대로 보인다. PLC 탭은 시나리오 8개 전부의 요약과, 상태·알람·출력·이벤트가 바뀐 주기의 표를 정적 HTML로 넣는다. 재생 슬라이더만 JavaScript가 필요하다.

| 탭 | 내용 |
| --- | --- |
| 개요 | 절마다 핵심 수치 한 줄과 사전 기준 결과. 미충족 항목도 그대로 표시 |
| 측정 | 설비별 Cpk·Ppk 표, 표본 부족 표시 |
| 측정 시스템 | 게이지별 %GRR, ndc, 판정, 가드밴드 선택 |
| 이상 검출 | 방법 비교 표(11·13단계), 이동량별 검출률 막대, 관리도 선 그래프, 로지스틱 수렴 상태, 경보 행의 `b + Σ w_j s_j` 기여값과 임계값 |
| PFMEA | 행별 근거·관측값·효과 판정. S·O·D 빈칸은 빈칸으로 표시 |
| 라인 | 조합 표, 레이아웃 SVG |
| PLC | 시나리오 선택, 주기 슬라이더, 상태 다이어그램, 출력 램프 재생 |
| 사건 | 사건 ID별 연결(측정값 → 경보 근거 → 정지 코일 → 알람 → 복구 조건 → 격리 제품 → PFMEA 행), 방법별 타임라인, 의심 생산량·포착 표 |

- 그래프는 인라인 SVG로 직접 그린다. 축과 범례를 넣고, 수치 표를 같이 둔다. 색만으로 구분하지 않는다.
- 밝은·어두운 테마를 `prefers-color-scheme`으로 따른다. 폭 375px에서 가로 스크롤이 생기지 않는다.
- 보고서의 문자열은 정적 HTML에서 `html.escape(quote=True)`로 이스케이프한다.
- 재생 자료는 `<script type="application/json">`에 넣는다. `json.dumps(sort_keys=True)` 뒤 `<`, `>`, `&`, U+2028, U+2029를 `\uXXXX`로 바꾼다. `</`만 막으면 `<!--`와 `<script>` 조합이 스크립트 파싱 상태를 바꿀 수 있기 때문이다.
- JavaScript는 화면에 글자를 넣을 때 `textContent`만 쓴다. `innerHTML`, `eval`, `document.write`를 쓰지 않는다.
- SVG는 넣기 전에 `xml.etree`로 파싱해 **허용 목록**으로 검사한다. 하나라도 어긋나면 종료 코드 2다.
  - 원문에 `<!DOCTYPE`, `<!ENTITY`, `<?`(XML 선언 제외)가 있으면 거절한다.
  - 허용 요소: `svg, defs, marker, line, path, rect, text`. 이름공간은 `http://www.w3.org/2000/svg`만이다. `foreignObject`, `script`, `style`, `image`, `use`, `a`, 애니메이션 요소는 목록에 없으므로 거절된다.
  - 허용 속성: `class, d, fill, font-family, font-size, height, id, marker-end, markerHeight, markerWidth, orient, refX, refY, stroke, stroke-dasharray, text-anchor, width, x, x1, x2, y, y1, y2, viewBox`. `on*`, `style`, `href`, 이름공간 속성은 목록에 없으므로 거절된다.
  - 값 안의 참조는 `url(#id)`만 허용하고 `id`가 같은 문서에 있어야 한다. 값에 `:`나 `\`가 있으면 거절한다.

## 실행과 결과
```powershell
py -m src.dashboard --out reports/dashboard.html
```
- 저장소 뿌리의 보고서를 읽는다. `--root`로 바꿀 수 있다. 다른 인자는 없다.
- `--out`은 쓰기 전에 검사한다. 확장자가 `.html`이고, 해석한 경로가 `<root>/reports/` 바로 아래여야 한다. 입력 파일과 같은 경로이거나 심볼릭 링크이면 거절한다. 위반은 종료 코드 2이고 아무것도 쓰지 않는다.
- 같은 입력은 바이트까지 같다. 생성 시각, 절대 경로, 시드 외 실행 정보를 넣지 않는다.
- 파일은 임시 이름으로 쓴 뒤 교체한다. 실패하면 이전 파일을 건드리지 않는다.
- 크기는 5MB 이하다. 넘으면 종료 코드 2다.

## 사전 기대표
| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T237 | 정상 실행 | 종료 0, `html.parser`로 파싱 성공, 태그 짝 일치, 탭 8개 |
| T238 | 고정 문구 | 첫 절보다 앞에 정확히 포함 |
| T239 | 수치 대조: 7a Cpk, 8단계 효과 판정, 9단계 선택 UPH, 11·13단계 선택과 지연 비용, 12단계 %GRR, 14단계 정지 위치 | 각 값이 보고서 문자열과 같음. 하드코딩 없음(보고서 값을 바꾼 복사본에서 화면 값도 바뀜) |
| T240 | 미충족 표시: PF-02, PF-06, `anomaly_lamp_model.csv`의 수렴 미달과 경사 노름 | 화면에 그대로 있음. 모델 보고서 값을 바꾸면 화면도 바뀜 |
| T241 | S·O·D 빈칸 | 빈칸. 0이나 추정값 없음 |
| T242 | 필수 파일 하나 없음, 필수 열 없음, SVG: `script`, `foreignObject`, `on*` 속성, `style` 속성, `href`, `animate`, `<!DOCTYPE`, `url(http://…)`, `url(#없는id)`, 깨진 XML | 종료 코드 2, 이전 HTML 불변 |
| T243 | 보고서 값에 `<script>alert(1)</script>`, `</script>`, `<!--<script>`, `&lt;`, 큰따옴표. 값이 정적 표와 재생 JSON 양쪽에 들어가는 경우 | 실행 태그 없음. `html.parser`로 script 요소 수가 고정 수와 같음. JSON을 `json.loads`로 되읽으면 원문과 같음 |
| T244 | 외부 참조 검사 | 파일 전체에 `http://`, `https://`, `//` 스킴 참조, `file:`, `data:`, `@import`, 외부 `url(`, `src=`, `<link` 없음. SVG 이름공간 선언은 예외로 허용. 현재 레이아웃의 `url(#arrow)`는 통과 |
| T245 | 두 폴더에서 반복 | HTML 바이트 동일, 절대 경로 없음 |
| T246 | PLC 재생 자료 | 시나리오 8개의 주기 수와 마지막 상태가 CSV와 같음 |
| T247 | 크기 | 5MB 이하 |
| T248 | 실행 뒤 기존 파일 | 기존 설정·보고서 바이트 불변, 전체 기존 테스트 통과 |
| T263 | JavaScript 없는 내용: `html.parser`로 `<script>`를 뺀 본문 | 시나리오 8개의 요약과 변화 행 표, 탭 8개의 절 제목, 표, SVG 그래프가 다 있음. 재생 슬라이더 외에 빠지는 내용 없음 |
| T264 | `--out`: `reports/anomaly_lamp_methods.csv`, `reports/spc_lamp_chart.csv`를 `.html`로 바꾼 입력 경로와 같은 경로, `reports` 밖, `reports/sub/x.html`, 확장자 없음 | 종료 코드 2, 입력 바이트 불변 |
| T265 | 기여값: `anomaly_lamp_replay.csv`의 `alarm = 1` 행 | `b + Σ w_j s_j`가 `z`와 소수 여덟째 자리까지 맞음. 어긋나게 바꾼 복사본은 종료 코드 2 |
| T266 | 사건 연결: 사건 탭 | `story`의 사건 ID마다 측정값, 경보 근거, 코일 프레임, 알람, 복구 조건, 격리 제품 수, PFMEA 행이 있음. 값은 보고서 문자열과 같음 |

브라우저 확인은 테스트와 별도로 한다. Claude가 내장 브라우저에서 폭 1280·375, 밝은·어두운 테마, **JavaScript를 끈 상태**를 열어 확인하고, 볼 수 없으면 그대로 밝힌다.

## 구현 순서
1. **15-1**: 입력 읽기, 검증, 이스케이프, 출력 경로, T242–T244, T264.
2. **15-2**: 탭·표·그래프·재생, T237–T241, T245–T248, T263, T265–T266.
3. **15-3**: 브라우저 확인, README.

# v2 14단계 명세 (구현 완료, 2026-10-31, 사용자 승인 전)

상태: **Sol 검토 뒤 진행 확정** (2026-10-31, 사용자 지시). 결정 근거는 `handoff/decisions.md`. 1–13단계(아래 명세)는 완료이며, 그 동작과 테스트는 보존한다.

## 목표와 경계
- 지금까지 따로 도는 기능을 한 사건으로 잇는다. **측정 평균 이동 → 경보 → PC가 PLC에 정지 요청 → 알람 → 수동 해제·제품 제거·리셋 → 재가동 → 의심 제품 범위 → PFMEA 근거**다.
- 같은 측정열에 3:2, EWMA, CUSUM을 적용해 정지 시점, 의심 생산량, 격리 포착을 비교한다.
- 표현은 "합성 고장 시나리오의 경보–정지–격리 추적"이다. "사고 대응 경험", "라인 정지 대응 실무"로 쓰지 않는다. 전부 한 PC 안의 소프트웨어 모의다.
- 제외: 판정기·기존 생성기 변경, 여러 스테이션, 실제 수리 시간 추정, 재발 방지 자동 판단, 외부 패키지.

## 보존 조건
- 기존 설정, 테스트, 보고서는 수정하지 않는다. README에 절을 덧붙이는 것만 예외다.
- `src/plc.py`, `src/modbus.py`, `src/station.py`는 아래 추가만 허용한다. PC가 새 코일을 쓰지 않으면 동작이 같아야 한다. 10단계 보고서 16개는 바이트 그대로다.
- 새 코드는 `src/incident.py`, 새 테스트는 `tests/test_incident.py`, 새 설정은 `recipes/incident_lamp.json`이다.
- 측정은 `anomaly.measure`, 관리도 상태는 `spc`의 한계와 같은 식, 판정은 `judge_value`다.

## 10단계 추가
- 코일 10 `pc_stop`을 추가한다. 쓰기는 PC, FC05, 초기 0이다. `WRITABLE_COILS`에 더한다.
- 스캔 2단계 즉시 알람에 **PC 정지 요청(26)**을 측정 신호 이상 뒤 순서로 넣는다. 코일이 참이면 `ALARM`으로 전이한다.
- 리셋 조건 `_recoverable`에 `pc_stop` 거짓을 더한다.
- 모의 설비에 `feed_hold` 속성을 추가한다. 기본은 거짓이다. 참이면 다음 제품이 들어오지 않는다. 10단계 실행은 이 값을 건드리지 않는다.
- 모의 설비에 `remove_product()`를 추가한다. 작업자 제거다. `part_present`, `seated`, `direction_ok`를 내리고, `product`를 1 늘리고, `feed_hold`를 켠다. 그 측정값은 다시 쓰지 않는다. 제거 뒤 복귀 완료까지 제품이 없어야 `_recoverable`이 참이 되기 때문이다.
- 사건 실행은 10단계 `run_scenario`를 고치지 않고 `src/incident.py`의 자체 주기로 돈다. 한 주기의 순서는 같다(`plant.update` → `plc.scan` → PC).

## 설정 `recipes/incident_lamp.json`
```json
{
  "station": "plc_station.json",
  "spc": "spc_lamp.json",
  "spc_report": "../reports/spc_lamp_methods.csv",
  "pfmea": "../data/pfmea_lamp.csv",
  "products": 400,
  "onset_product": 200,
  "shift_sigma": 1.5,
  "repair_cycles": 30,
  "max_cycles": 20000,
  "story_seed": 3042,
  "summary_seeds": "3000-3099",
  "methods": ["rule_3_2", "ewma_chart", "cusum"],
  "scopes": ["last_20", "last_50", "change_point"],
  "pfmea_links": ["PF-02", "PF-06"]
}
```
- 경로는 설정 파일 폴더 기준이다. 없으면 종료 코드 2다. `pfmea_links`의 ID가 표에 없으면 종료 코드 3이다.

| 키 | 타입 | 범위 |
| --- | --- | --- |
| `station`, `spc`, `spc_report`, `pfmea` | 문자열 | 비어 있지 않음 |
| `products` | 정수 | 1–65535. `measure_id`가 65535 뒤 순환하므로 `제품 번호 = measure_id − 1`이 성립하는 범위다(리뷰 022) |
| `onset_product` | 정수 | 1 이상 `products` 이하. 1부터 센다 |
| `shift_sigma` | 유한한 수 | 0 초과 100 이하 |
| `repair_cycles` | 정수 | 1–100000 |
| `max_cycles` | 정수 | 1–10000000. `plc_station.json`의 `max_cycles`는 쓰지 않는다. 제품당 정상 24주기라 400제품에 9,600주기가 들고, 그 설정은 10단계 값으로 보존한다 |
| `story_seed` | 정수 | 0 이상 2³¹−1 − 1000000 이하 |
| `summary_seeds` | 문자열 | `시작-끝`. 정수, 시작 ≤ 끝, 끝 ≤ 2³¹−1 − 1000000 |
| `methods`, `scopes` | 문자열 목록 | 표의 ID. 비어 있지 않고 중복 없음. `change_point`를 쓰면 `cusum`이 있어야 함 |
| `pfmea_links` | 문자열 목록 | 비어 있지 않고 중복 없음 |

- 없는 키, 허용 밖 키, 타입·범위 위반은 종료 코드 3이다. bool은 숫자가 아니다. `10**400`도 종료 코드 3이다.
- `story_seed`와 `summary_seeds`는 11·13단계의 학습·검증·홀드아웃 시드와 겹칠 수 없다(종료 코드 3). 사건 평가에 한계 추정 자료를 다시 쓰지 않기 위해서다.

## 설정 일치 확인
어긋나면 종료 코드 2이고 보고서를 쓰지 않는다.
- `station.generator`와 `spc → anomaly.generator`가 같은 파일이고, `station.inspection`과 `anomaly.inspection`이 같다. 두 경로로 얻은 규격·`center`·`sigma`·결함 확률·결함 이동이 같다.
- `reports/spc_lamp_methods.csv`의 `limits` 행이 없거나, `spc`와 `anomaly` 설정으로 다시 추정한 한계와 `repr` 문자열이 다르면 거절한다.

## 측정열
시드 하나에 두 열을 전체 제품 번호에 대해 미리 만든다. 번호 `n`은 0부터 센다.

- **고장 열** `F[n]`: `random.Random(시드)`로 `n = 0…`의 값을 `anomaly.measure`로 만든다. `n ≥ o`이면 고장 이동 `shift_sigma`를 쓴다. `o = onset_product − 1`이다.
- **수리 뒤 열** `N[n]`: `random.Random(시드 + 1000000)`으로 `n = 0…`의 값을 고장 이동 0으로 만든다.

두 열은 방법과 무관하게 같다. 제품 `n`의 값은 수리 전이면 `F[n]`, 수리 뒤면 `N[n]`이다. 수리는 **`a ≥ o`인 첫 정지**에서만 일어나고, 그 제품 다음부터 `N`을 쓴다. 수리 효과의 가정이다. 고장이 시작되기 전의 정지는 고칠 것이 없으므로 재가동 뒤에도 `F`를 그대로 쓰고, 고장은 예정대로 시작한다.

방법 상태는 **구간** 단위다. 구간은 시작 또는 재가동부터 다음 정지까지다. 구간 안 인덱스 `s`는 0부터 세고, 제품 번호 `n`은 전체 번호다.

| ID | 경보 (판단은 `s ≥ 9`) |
| --- | --- |
| `rule_3_2` | 구간 안 최근 3건 중 FAIL 2건. 창은 구간 첫 제품부터 쌓는다 |
| `ewma_chart` | 13단계 식. `t` 자리에 `s`를 쓴다 |
| `cusum` | 13단계 식. 경보 뒤 변화 시점을 구간 안에서 추정해 `구간 시작 번호 + 위치`로 전체 번호로 바꾼다 |

판단 시작 `9`는 11단계의 `window − 1`을 설정에서 읽은 값이다. 한계와 `σ̂`는 13단계 1단계 추정값이다.

**정지가 여러 번일 수 있다.** 경보는 언제나 정지로 이어지고, 재가동 뒤 상태를 초기값으로 돌려 다시 판단한다. 모든 정지를 `stops`에 기록한다.

## 사건 순서 (소켓 실행)
`story_seed`로 방법마다 실제 Modbus TCP로 돌린다.

1. 정상 운전은 10단계 주기다. PC는 `WAIT_JUDGE`에서 값을 복원해 판정을 쓴다.
2. PC는 새 `measure_id`를 볼 때 방법 상태를 갱신한다. 제품 번호는 `measure_id − 1`이고 사건 동안 `plant.product`와 같다. 어긋나면 종료 코드 2다. 경보면 판정을 쓰지 않고 `pc_stop` 코일을 켠다. 그 제품 번호를 정지 위치로 **이때 고정**한다.
3. PLC는 다음 스캔에 알람 26으로 전이한다. 클램프는 진입 값을 유지한다.
4. PC는 `REG_ALARM = 26`을 읽은 주기에 `manual_release`를 켠다. 알람 전에 켜면 상승 에지를 놓치므로 순서를 지킨다. 모의 설비가 클램프를 연다.
5. PC가 `clamp_open`(이산 입력)을 읽어 참이면 `remove_product()`를 호출한다. 제품이 빠지고 투입이 멈춘다.
6. 제거 주기부터 `repair_cycles` 주기를 기다린다. 이 동안 PC 하트비트는 유지한다.
7. PC가 `pc_stop`, `manual_release`를 끈다. 다음 주기에 `reset`을 켠다. `REG_STATE = IDLE`, `REG_ALARM = 0`을 읽으면 `reset`을 끄고 `feed_hold`를 끈다. 이 주기가 재가동이다.
8. 남은 제품을 처리한다. 방법 상태는 초기값으로 되돌리고 구간을 새로 시작한다.

알람 26이 아닌 알람이 나면 종료 코드 2다. 합성 흐름에서 일어나면 안 되는 일이고 복구를 추측하지 않는다.

**완료 조건**은 소비한 제품 수다. `plant.product = products`이고 PLC가 `IDLE`이며 제품이 없을 때 끝난다. 끝나면 `OK + NG + aborted = products`를 단정한다. `aborted`는 판정 없이 제거한 제품 수이고 `plc.processed`, OK, NG에 들어가지 않는다. 기존 `processed < products` 조건은 쓰지 않는다. 끝까지 처리하지 못하고 `max_cycles`를 넘으면 종료 코드 2다.

마지막 제품에서 정지하면 복귀 뒤 들어올 제품이 없으므로 재가동 기록 뒤 바로 끝난다.

## 격리 범위
정지 제품 번호를 `a`(0부터)라 한다. 후보 범위는 `a`를 포함한다.

| ID | 시작 |
| --- | --- |
| `last_20` | `max(0, a − 19)` |
| `last_50` | `max(0, a − 49)` |
| `change_point` | `cusum` 변화 시점 추정(전체 번호). `cusum`이 아니면 해당 없음 |

`a`는 **`a ≥ o`인 첫 정지**의 제품 번호다. 없으면 범위도 없다. 고장 전 정지만 있는 실행과 무정지 실행은 범위를 만들지 않는다. `scopes`에서 방법에 맞지 않는 조합은 표에 빈칸으로 둔다.

## 지표
`o = onset_product − 1`(0부터)이라 한다.

| 지표 | 정의 |
| --- | --- |
| `stops` | 전체 정지 수 |
| `false_stops` | `a` 말고 나머지 정지 수. 고장 전 정지와 수리 뒤 정지를 합친다 |
| `detection` | `a`가 있으면 `detected`, `a`는 없고 정지가 있으면 `early`, 정지가 없으면 `missed` |
| `delay` | `a − o`. `a`가 없으면 빈칸 |
| `suspect_measured` | 고장 이동 값 `F[n]`(`n ≥ o`)을 측정한 제품 수. `suspect_passed + suspect_failed + suspect_aborted`다 |
| `suspect_passed` | 그중 OK로 배출된 제품 수. 작은 이동이라 대부분 여기 들어가며, 이 수가 격리의 대상이다 |
| `suspect_failed` | 그중 NG로 배출된 제품 수 |
| `suspect_aborted` | 그중 판정 없이 제거된 제품 수 |
| `captured` | `a`가 있고 범위가 `[o, a]`를 다 덮으면 참. `a`가 없으면 거짓 |
| `captured_parts` | 범위 안 `suspect_passed` 제품 수. 범위가 없으면 0 |
| `scope_size` | 범위의 제품 수. 범위가 없으면 빈칸 |
| `over_scope` | 범위 안에서 고장 이동 값이 아닌 제품 수. 범위가 없으면 빈칸 |

## 요약 (소켓 없음)
`summary_seeds`의 시드마다 방법별로 같은 두 열을 메모리에서 돌려 정지 위치와 지표를 낸다. 메모리 실행은 위 측정열·구간·수리 규칙을 그대로 쓰고, 설비 주기만 빠진다. 비교는 분수, 표시는 소수 넷째 자리 `ROUND_HALF_UP`이다. 선택은 하지 않는다. 표를 그대로 낸다.

| 요약 | 분모 |
| --- | --- |
| `detected`, `early`, `missed` | 수 |
| `mean_delay` | `detected` 실행 수. 0이면 빈칸. 미검출을 빼므로 위 수를 함께 읽는다 |
| `mean_suspect_passed`, `mean_stops`, `mean_false_stops` | 전체 실행 수 |
| `run_capture_rate` | `captured` 참인 실행 수 / 전체 실행 수 |
| `part_capture_rate` | 합산 `captured_parts` / 합산 `suspect_passed`. 분모 0이면 빈칸 |
| `mean_scope_size`, `mean_over_scope` | 범위가 있는 실행 수. 0이면 빈칸 |

## 실행과 보고서
```powershell
py -m src.incident recipes/incident_lamp.json
```
- **사건 ID**는 `<method>-<정지 순번>`이다. 예: `cusum-1`. 한 정지의 측정값, 경보 근거, 정지 코일, 알람, 복구 조건, 격리 제품, PFMEA 행이 이 ID로 이어진다.
- `reports/incident_lamp_timeline.csv`: `method, incident_id, cycle, product, event, detail`. 사건만 적는다. `event`는 `fault_start, alarm, pc_stop, alarm_26, release, clamp_open, remove, reset, restart, finish`다. `alarm`의 `detail`에 측정값, 판단값, 한계를 적는다(`rule_3_2`는 최근 3건 판정). `pc_stop`의 `detail`에 프레임 순번을 적는다. `reset`의 `detail`에 복귀 조건 값을 적는다. `fault_start`, `finish`는 사건 ID가 빈칸이다. 정렬은 방법 순서, 주기, 같은 주기 안의 발생 순서다.
- `reports/incident_lamp_compare.csv`의 열: `section, method, scope, name, value, stops, false_stops, detection, a, delay, suspect_measured, suspect_passed, suspect_failed, suspect_aborted, captured, captured_parts, scope_start, scope_size, over_scope, seeds`.

| 절 | 행 | 내용 |
| --- | --- | --- |
| `notice` | 1 | 합성 경고 문장 |
| `story` | 방법마다 1 | `story_seed` 소켓 실행의 지표 |
| `story_scope` | 방법×범위 | `scope`, `captured`, `captured_parts`, `scope_start`, `scope_size`, `over_scope` |
| `summary` | 방법×요약 지표 | `name`, `value`, `seeds` |
| `summary_scope` | 방법×범위×요약 지표 | `scope`, `name`, `value`, `seeds` |

- `reports/incident_lamp_suspects.csv`: `method, incident_id, scope, product, value, fault_value, disposition`. `story_seed`의 범위 안 제품마다 한 행이다. `fault_value`는 `1`·`0`, `disposition`은 `OK`·`NG`·`aborted`다.
- `reports/incident_lamp_modbus.csv`: `cusum` 방법의 **`a` 정지** 전후 20주기 프레임 16진수다. 열은 10단계 프레임 기록에 `incident_id`를 더한 것이다. `a`가 없으면 헤더만 있고 `compare`의 `story`로 사유가 보인다.
- `reports/incident_lamp_pfmea.md`: `pfmea_links` 행의 고장 모드와 이번 사건의 관측값을 사건 ID별로 나란히 적는다. 조치 판단은 쓰지 않는다. S·O·D는 건드리지 않는다.
- 같은 입력은 바이트까지 같다. 실행 시각, 포트, 절대 경로는 쓰지 않는다.
- 설정 오류는 종료 코드 3, 인자·파일 오류와 응답 제한 초과는 종료 코드 2다. 보고서는 전부 성공한 뒤에 쓴다.

## 사전 기대표
| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T221 | `plc.py`: `CHECK`에서 `pc_stop` 참 / 가드 열림과 동시 / `ALARM` 중 켬 | 알람 26 / 22 / 코드 유지 |
| T222 | 알람 26, 복귀 조건 충족, `pc_stop` 참인 채 리셋 / 거짓 뒤 새 상승 | `ALARM` 유지 / `IDLE`, `measure_id` 유지 |
| T223 | FC05 코일 10 / PC가 쓰지 않는 10단계 시나리오 8개 | 에코 / 보고서 16개 바이트 불변 |
| T224 | `remove_product()` / `feed_hold` 참인 동안 / 끈 뒤 | 입력 내림, `product` 1 증가, 값 소비 없음 / 다음 제품 안 들어옴(복구 대기 30주기) / `arrive` 지연 뒤 들어옴 |
| T225 | 같은 시드 측정열 / 방법 3개 | 값 동일. 번호 `o − 1`, `o`, `o + 1`에서 이동 적용이 맞음 |
| T226 | 재가동 뒤 값: 방법별 정지 위치가 다름 | 같은 번호 같은 값 `N[n]`, 이동 없음. `a < o` 정지 뒤에는 `F[n]` 유지 |
| T227 | 사건 순서: `cusum` 강제 경보, 소켓 | 판정 없음, 알람 26, Q0 유지 → 알람을 읽은 뒤 해제 → 제거 → 복구 대기 동안 제품 없음 → 리셋 → 재가동 → 남은 제품 처리, 순서가 표와 같음 |
| T228 | 경보 제품 / 전체 | 판정 안 씀, OK·NG 수에 없음, `aborted` 기록 / `OK + NG + aborted = products`, 마지막 제품 정지도 끝남 |
| T229 | 무경보 | 정지 없이 끝, `missed`, `captured` 거짓, `captured_parts` 0 |
| T230 | 범위: `a=10`, `a=100`, `change_point=90` | `last_20` 0–10, 81–100. `last_50` 0–10, 51–100. 90–100 |
| T231 | 지표: `o=100, a=110`, 범위 `100–110` / `105–110` / 정지 `95`만 / 정지 `95`, `120` | 포착 참·`over_scope` 0 / 거짓 / `early`, 포착 거짓, `[o, a]`가 비었다고 참이 되지 않음 / `a=120`, `false_stops` 1 |
| T232 | 소켓 실행과 메모리 실행의 정지 목록 | `story_seed`의 모든 방법에서 정지 위치 목록과 OK·NG·aborted 수가 같음 |
| T233 | 잘못된 설정: 없는 키, 허용 밖 키, `onset_product` 0, `onset_product` > `products`, 없는 방법, 중복 범위, `cusum` 없는 `change_point`, 없는 PFMEA ID, 빈 `pfmea_links`, `products: 10**400`, NaN, bool, 학습 시드와 겹치는 `story_seed`·`summary_seeds`, 시드 문자열 오류 | 종료 코드 3 |
| T234 | `limits` 행 없음, 없는 파일, `max_cycles` 초과, 재계산과 다른 `limits`, 생성 설정 불일치, 알람 26이 아닌 알람 | 종료 코드 2, 보고서 미생성 |
| T235 | 두 폴더에서 반복 | 보고서 5개 바이트 동일 |
| T236 | 실행 뒤 기존 파일 | 기존 설정·보고서 바이트 불변, `data/pfmea_lamp.csv` 불변, 전체 기존 테스트 통과 |
| T258 | 구간 초기화: 재가동 뒤 첫 제품 / 재가동 뒤 `s = 8`, `s = 9`에 초과 / 변화 시점 구간 위치 5, 구간 시작 200 | `s = 0`, EWMA 시작값 복귀, 누적합 0 / 경보는 `s = 9`부터 / 전체 번호 205 |
| T259 | 다중 정지: 고장 전 정지 뒤 재가동 | 고장이 예정대로 시작, 다시 판단 |
| T260 | 포착 합산: 실행 2개 `captured` 참·거짓, 합산 분자 분모 / `detected` 0 | `run_capture_rate` 1/2, `part_capture_rate` 합산 값 / `mean_delay` 빈칸 |
| T261 | 사건 ID: `story` 실행 | 경보, 코일 프레임, 알람, 격리 제품, PFMEA 절이 같은 ID로 이어짐. `pc_stop` 행의 프레임 순번이 실제 FC05 코일 10 프레임 |
| T262 | 400제품 기본 설정 | `max_cycles` 안에 끝남 |

## 구현 순서
1. **14-1**: PLC·서버 추가, T221–T224.
2. **14-2**: 측정열, 구간, 사건 주기, T225–T229, T232, T258–T259, T262.
3. **14-3**: 범위, 지표, 요약, 보고서, T230–T231, T233–T236, T260–T261.

# v2 13단계 명세 (구현 완료, 2026-10-31, 사용자 승인 전)

상태: **Sol 검토 뒤 진행 확정** (2026-10-31, 사용자 지시). 결정 근거는 `handoff/decisions.md`. 1–12단계(아래 명세)는 완료이며, 그 동작과 테스트는 보존한다.

## 목표와 경계
- 11단계와 같은 측정열에 X̄-R, 런 규칙, EWMA, CUSUM 관리도를 적용해 경보 성능을 같은 지표로 비교한다.
- 전통 관리도가 3:2 규칙이 놓친 작은 평균 이동을 얼마나 잡는지, 로지스틱 회귀와 비교해 어떤지 보여 준다.
- 표현은 "합성 측정열의 SPC 관리도 비교"다. "SPC 운영 경험", "공정 관리 실무"로 쓰지 않는다. 성능은 같은 평균 이동 가정 안에서만 뜻이 있다.
- 제외: 11단계 선택 변경, 판정기·생성기 변경, 관리 한계 재추정, 비정규 보정, 외부 패키지.

## 보존 조건
- 기존 코드, 설정, 테스트, 기존 보고서는 수정하지 않는다. README에 절을 덧붙이는 것만 예외다. **11단계 보고서와 선택은 그대로 둔다.**
- 새 코드는 `src/spc.py`, 새 테스트는 `tests/test_spc.py`, 새 설정은 `recipes/spc_lamp.json`이다.
- 측정열과 분할은 `anomaly.build_split`, 지표는 `anomaly.measure_alarms`·`passes`를 그대로 쓴다. 판단 횟수 분모는 아래 정의로 별도 계산한다.

## 설정 `recipes/spc_lamp.json`
```json
{
  "anomaly": "anomaly_lamp.json",
  "anomaly_report": "../reports/anomaly_lamp_methods.csv",
  "anomaly_model": "../reports/anomaly_lamp_model.csv",
  "anomaly_replay": "../reports/anomaly_lamp_replay.csv",
  "subgroup": 5,
  "ewma_lambda": 0.2,
  "ewma_l": 3,
  "cusum_k": 0.5,
  "cusum_h": 5
}
```
- 경로는 설정 파일 폴더 기준이다. 없으면 종료 코드 2다.
- `subgroup`은 5로 고정한다. 상수 표가 이 값이다.
- EWMA 시변 한계의 `1 − (1−λ)^{2(t+1)}`은 `expm1`·`log1p`로 계산해 작은 λ에서 0이 되지 않게 한다(리뷰 021).
- `ewma_lambda`는 0 초과 1 이하, `ewma_l`, `cusum_k`, `cusum_h`는 유한한 양수다. `cusum_k`만 0을 허용하지 않는 이유는 기준값 없는 표류를 막기 위해서다.
- 없는 키, 허용 밖 키, 타입·범위 위반은 종료 코드 3이다. bool은 숫자가 아니다.
- 네 조정 값은 교과서 기본값이고, 결과를 본 뒤 바꾸지 않는다.

## 11단계 보고서와의 일치 확인
파일 해시는 파일을 식별할 뿐 같은 측정열임을 증명하지 못한다. 그래서 네 가지를 확인한다. 어긋나면 비교를 거절하고 종료 코드 2다.

1. `anomaly_model`의 `setting` 행(`generator`, `inspection`, `window`, `ewma_lambda`)과 `split` 행이 현재 `anomaly` 설정과 같다.
2. 현재 설정으로 `rule_3_2`를 다시 계산해 `anomaly_report`의 `validation`·`holdout` 행, 이동량별 행과 문자열이 같다. `rule_3_2`는 학습이 필요 없고 측정열에만 의존한다. 다만 FAIL만 보므로 측정값이 달라도 같은 결과가 나올 수 있다(리뷰 021).
3. 보고서 임계값으로 `moving_average`를 다시 계산해 `validation`·`holdout` 행과 문자열이 같다. 임계값이 없으면 건너뛴다.
4. `anomaly_replay`의 시드, `value`, `window_values`가 현재 홀드아웃 위치 1 시나리오의 측정값과 같다. 측정열 자체를 직접 비교한다.
- 설정·모델 보고서·방법 보고서의 필수 키가 두 번 나오면 값이 같아도 거절한다.

`reports/spc_lamp_methods.csv`의 `provenance` 행에 세 보고서와 두 설정의 SHA-256을 적는다.

## 1단계 추정 (학습 분할만)
학습 분할의 **정상 시나리오**만 쓴다. 측정값은 11단계의 정규화 값 `x = (value − c) / σ`다. 각 시나리오를 앞에서부터 5건씩 끊고 남는 값은 버린다.

```text
X̄̄ = 부분군 평균의 평균,  R̄ = 부분군 범위의 평균
σ̂ = R̄ / 2.326
UCL_x, LCL_x = X̄̄ ± 0.577 R̄
UCL_r = 2.114 R̄,  LCL_r = 0
σ_x̄ = 0.577 R̄ / 3
```

합성 결함값을 빼지 않는다. 한계가 이 값만큼 넓어지는 것을 README에 공개한다. 검증·홀드아웃·고장 시나리오는 추정에 쓰지 않는다.

- 정상 시나리오가 없거나, 시나리오 길이가 5 미만이어서 부분군이 0개면 추정 불가이고 종료 코드 2다.
- `R̄ = 0`이면 `σ̂ = 0`이라 위치 표준화와 한계가 정의되지 않는다. 종료 코드 2이고 보고서를 쓰지 않는다. 합성 자료에서 나오지 않는 입력이지만 나눗셈 오류로 끝내지 않는다.
- `limits` 행은 14단계가 읽는다. 이름과 값은 아래 **보고서**의 표를 따른다.

## 방법
판단 시점은 11단계와 같은 `t ≥ window − 1`, 기본 `t ≥ 9`다. 첫 경보만 본다. 경보 뒤 재설정하지 않는다.

부분군 방법은 5건마다 한 번만 판단한다. 길이 400의 무경보 열에서 판단은 `t = 9, 14, …, 399`의 79회다. 측정 1건마다 판단하는 11단계와 달리 최대 4건의 대기 지연이 있고, 이 지연은 `mean_delay_cost`에 그대로 들어간다. 불리해도 보정하지 않고 보고서의 `decision_interval`, `max_wait`로 공개한다.

| ID | 판단 위치 | 경보 조건 |
| --- | --- | --- |
| `xbar_r` | 부분군이 끝나는 `t = 4, 9, 14, …` 중 `t ≥ 9` | X̄가 한계 밖이거나 `R > UCL_r` |
| `xbar_we` | 같음 | `xbar_r` 또는 아래 런 규칙 |
| `ewma_chart` | 매 측정 `t ≥ 9` | `|z_t − X̄̄| > L σ̂ √(λ/(2−λ) · (1 − (1−λ)^{2(t+1)}))` |
| `cusum` | 매 측정 `t ≥ 9` | `C⁺_t > h σ̂` 또는 `C⁻_t > h σ̂` |

**런 규칙**: 부분군 평균의 위치 `q = (X̄ − X̄̄) / σ_x̄`로 본다. 시나리오의 첫 부분군부터 세고, 그 결과는 판단 위치에서만 인정한다. 위쪽과 아래쪽을 따로 세고, 경계값은 포함하지 않는다.

| ID | 위쪽 조건 (아래쪽은 부호 반대) |
| --- | --- |
| `run_2of3` | 최근 3점 중 2점 이상이 `q > 2` |
| `run_4of5` | 최근 5점 중 4점 이상이 `q > 1` |
| `run_8` | 최근 8점이 모두 `q > 0` |

점이 모자라면 그 규칙은 거짓이다. 정확히 2인 점은 `run_2of3`에 세지 않지만 `run_4of5`, `run_8`에는 센다. 정확히 0인 점은 어느 쪽에도 세지 않는다.

**EWMA**: `z_{-1} = X̄̄`, `z_t = λ x_t + (1−λ) z_{t−1}`.

**CUSUM**: `C⁺_{-1} = C⁻_{-1} = 0`, `C⁺_t = max(0, C⁺_{t−1} + x_t − X̄̄ − kσ̂)`, `C⁻_t = max(0, C⁻_{t−1} − x_t + X̄̄ − kσ̂)`.

**변화 시점 추정**: `cusum` 경보가 위쪽이면 경보 전 `C⁺`가 마지막으로 0이었던 위치의 다음 측정이다. 아래쪽도 같다. 0이었던 적이 없으면 0이다. 14단계 격리 범위에 쓴다.

## 지표와 선택 (결과 전 고정)
- 지표는 11단계와 같다. `detection_rate`, 이동량별 검출률, `early`, `missed`, `mean_delay_cost`, `false_per_1000`.
- **`false_per_1000`의 분모는 측정 수다.** 11단계는 측정마다 판단하므로 판단 수와 같고, 관리도의 부분군 방법도 같은 측정 1,000건당으로 비교한다. 이 값이 선택 조건에 들어간다.
- 참고값 `false_per_1000_decisions`는 같은 오경보를 판단 1,000회당으로 낸다. 부분군 방법에서 판단 수는 노출 구간에 든 판단 위치의 수다. 측정별 방법에서는 `false_per_1000`과 같다. 선택에 쓰지 않는다.
- 참고값 `restricted_mean_run`: 정상 시나리오에서 첫 판단 측정부터 첫 경보 측정까지의 측정 수 평균이다. 무경보는 관측 끝 `length − window + 1`로 자른다. `no_alarm`에 무경보 시나리오 수를 함께 쓴다. **일반적인 ARL이 아니라 관측 구간으로 제한한 평균**이므로 보고서와 README에서 ARL로 부르지 않는다.
- 참고값 `mean_detected_delay`: 11단계와 같은 검출 사례만의 평균 지연이다. 비용과 혼동하지 않게 이름을 그대로 둔다.
- **선택**: 검증 분할에서 11단계의 세 조건(`false_per_1000 ≤ 2`, `detection_rate ≥ 0.90`, 이동량별 `≥ 0.70`)을 만족하는 관리도 중 `mean_delay_cost`가 가장 작은 방법이다. 동률이면 표의 순서다. 없으면 `기준 충족 관리도 없음`이고 완화하지 않는다.
- **홀드아웃**: 선택이 세 조건을 유지하면 `확인`, 아니면 `미달`이다. 다시 고르지 않는다.
- **11단계와의 대조**: `anomaly_report`의 `validation`, `holdout` 행을 그대로 옮겨 참고 행으로 낸다. 선택 후보에 넣지 않는다. 행이 없으면 종료 코드 2다. 11단계 선택과 비교한 문장은 선택 뒤 평균 지연 비용을 나란히 적는 것까지만 한다.

## 민감도 (참고, 선택에 쓰지 않음)
정상 기준에 결함이 섞여 한계가 넓어지는 영향을 분리해서 본다.

- **깨끗한 기준**: 같은 학습 시드의 정상 시나리오를 `defect_probability = 0`인 `Process`로 다시 만들어 한계를 추정한다. 그 한계를 같은 검증·홀드아웃 측정열에 적용한다. 절 `clean_limits`, `clean_holdout`으로 낸다. 정상 혼합 기준의 평균·분산이 결함으로 움직인다는 설명을 `notice`에 넣는다.
- **첫 경보 규칙**: 절 `triggers`에 `xbar_we`의 첫 경보를 낸 규칙별 시나리오 수(`limit`, `range`, `run_2of3`, `run_4of5`, `run_8`)를 분할별로 낸다. 한 판단에서 여러 규칙이 함께 참이면 표의 순서로 앞선 규칙 하나에 세고, 함께 참이었던 수를 `joint`로 따로 낸다. 런 규칙 추가가 오경보를 늘리는 정도를 `xbar_r`과 나란히 볼 수 있다.

## 실행과 보고서
```powershell
py -m src.spc recipes/spc_lamp.json
```
- `reports/spc_lamp_methods.csv`의 열: `section, method, shift, split, name, value, decision_interval, max_wait, detection_rate, early, missed, mean_delay_cost, mean_detected_delay, false_per_1000, false_per_1000_decisions, restricted_mean_run, no_alarm`.

| 절 | 행 | 내용 |
| --- | --- | --- |
| `notice` | 1 | 합성 경고 문장 |
| `provenance` | 5 | `name`에 파일 이름, `value`에 SHA-256 |
| `limits` | 15 | `name`: `center, sigma, xbarbar, rbar, sigma_hat, ucl_x, lcl_x, ucl_r, sigma_xbar, subgroups, ewma_lambda, ewma_l, cusum_k, cusum_h, window`. `value`는 `repr`로 그대로 복원되는 값 |
| `validation`, `holdout` | 방법마다 1 | 지표 |
| `validation_shift`, `holdout_shift` | 방법×이동량 | `shift`, `detection_rate` |
| `reference` | 3×2 | `split`별 11단계 행의 지표를 그대로 옮긴 것 |
| `clean_limits` | 8 | `xbarbar`부터 `sigma_xbar`까지와 `subgroups` |
| `clean_holdout` | 방법마다 1 | 지표 |
| `triggers` | 분할×규칙 | `split`, `name`, `value` |
| `selection` | 2 | `value`에 선택 또는 `기준 충족 관리도 없음`, 홀드아웃 결과 |

- 표시는 소수 넷째 자리 `ROUND_HALF_UP`이다. 방법 순서는 표의 순서, 이동량은 오름차순이다.
- `reports/spc_lamp_chart.csv`의 열: `seed, shift, onset, t, value, x, z, ewma_limit, c_plus, c_minus, xbar, range`. 홀드아웃 위치 1 시나리오의 측정마다 한 행이고, `xbar`, `range`는 부분군 끝 행에만 있다. 값은 소수 열째 자리다. 15단계 도표에 쓴다.
- 같은 입력은 바이트까지 같다. 설정 오류는 종료 코드 3, 인자·파일 오류는 종료 코드 2다.

## 사전 기대표
| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T205 | 부분군 `1,2,3,4,5`, `2,3,4,5,6` | `X̄̄` 3.5, `R̄` 4, `σ̂` 1.7197, 한계 5.808, 1.192, `UCL_r` 8.456, `σ_x̄` 0.7693 |
| T206 | 남는 값: 시나리오 길이 12 | 부분군 2개, 나머지 2건 버림 |
| T207 | 정상 2개·고장 2개 시나리오의 고장 값 변경, 검증 값 변경 | 추정값 불변 |
| T208 | 부분군 판단: 길이 20에서 `t=4`에 한계 밖, 뒤는 정상 / `t=14`에 한계 밖 | 경보 없음(판단 시점 전) / 경보 14 |
| T209 | `R > UCL_r`, X̄ 정상 | `xbar_r` 경보 |
| T210 | 규칙별 함수, 위치 열 ① `2.5, 0, 2.5` ② `2.5, 0, -2.5` ③ `1.5, 1.5, 0, 1.5, 1.5` ④ `0.5` 8개 ⑤ `0.5` 7개 뒤 `-0.5` | ① `run_2of3` 마지막 점 참 ② `run_2of3` 거짓 ③ `run_4of5` 마지막 점 참, `run_2of3` 거짓 ④ `run_8` 마지막 점 참, 일곱째 점 거짓, 다른 규칙 거짓 ⑤ `run_8` 거짓 |
| T211 | 규칙별 함수, 경계 ① `2, 0, 2` ② `1, 1, 0, 1, 1` ③ `0.5, 0.5, 0.5, 0, 0.5, 0.5, 0.5, 0.5` ④ `2` 5개 | ① `run_2of3` 거짓 ② `run_4of5` 거짓 ③ `run_8` 거짓 ④ `run_2of3` 거짓, `run_4of5` 참 |
| T212 | EWMA `X̄̄ 0, σ̂ 1, λ 0.2, L 3`, `x_0 = 1` | `z_0` 0.2, 한계 0.6, 큰 `t`의 한계는 1에 수렴 |
| T213 | EWMA `t = 3`에 첫 초과 / `t = 9`에 첫 초과 | 무시하고 이후 첫 초과 / 경보 9 |
| T214 | 누적합 함수(판단 시작 전 규칙 없음) `X̄̄ 0, σ̂ 1, k 0.5, h 1.5`, `x = 1, 1, 0, 2` | `C⁺` 0.5, 1, 0.5, 2. 첫 초과 3. 변화 시점 0 |
| T215 | 누적합 함수, `x = 0, 0, 1, 2`, 같은 조정 값, 아래쪽 대칭 입력 / 경보 함수 `x = 2` 12개 | 위 변화 시점 2, 아래도 2 / 첫 초과 0이지만 판단 시작 때문에 경보 9 |
| T216 | 선택: ① 넷 다 통과, 비용 40·30·20·10 ② 동률 ③ 이동량 0.60 ④ 전부 미달 | ① `cusum` ② 표의 순서 ③ 탈락 ④ `기준 충족 관리도 없음` |
| T217 | 홀드아웃 함수, `anomaly_report` 행 누락 | `확인`, `미달`, `검증할 선택 없음` / 종료 코드 2 |
| T218 | 잘못된 설정: 없는 키, 허용 밖 키, `subgroup` 4, `ewma_lambda` 0, `cusum_k` 0, `cusum_h: 10**400`, NaN, bool | 종료 코드 3, 보고서 미생성 |
| T219 | 두 폴더에서 반복 | 보고서 2개 바이트 동일 |
| T220 | 실행 뒤 기존 파일 | 11단계 보고서 포함 기존 파일 바이트 불변, 전체 기존 테스트 통과 |
| T251 | 판단 분모: 길이 400 무경보 정상 열, `xbar_r` / `cusum` / `t=19` 오경보 `xbar_r` | 판단 79, 측정 노출 391 / 판단 391, 측정 노출 391 / 판단 3, 측정 노출 11 |
| T252 | `restricted_mean_run`: 길이 400, window 10. 경보 `t=9`, `t=108`, 무경보 | 1, 100, 391 (평균 164). `no_alarm` 1 |
| T253 | 추정 불가: 정상 시나리오 없음, 길이 4, 모든 값 같음(`R̄=0`) | 종료 코드 2, 보고서 미생성, 나눗셈 오류 없음 |
| T254 | 일치 확인: `setting` 값 변경, `split` 범위 변경, `rule_3_2` 행 수치 변경, `length`만 바꾼 설정 | 종료 코드 2, 보고서 미생성 |
| T255 | `provenance`: 입력 파일 변경 | SHA-256 행이 바뀌고 나머지 절 형식 유지 |
| T256 | 깨끗한 기준: 결함 확률 0으로 만든 학습 값 / 같은 검증 측정열 | `clean_limits`가 결함 혼합 한계보다 좁음 / 검증·홀드아웃 측정값 불변, `selection` 불변 |
| T257 | `triggers`: 한 판단에서 `limit`과 `run_2of3` 동시 참 | `limit`에 세고 `joint` 1 |

## 구현 순서
1. **13-1**: 1단계 추정, 네 방법, T205–T215.
2. **13-2**: 지표·선택, 일치 확인, 민감도, 보고서, T216–T220, T251–T257.

# v2 12단계 명세 (구현 완료, 2026-10-31 · 리뷰 020 지적 수정, 사용자 승인 전)

상태: **Sol 검토 뒤 진행 확정** (2026-10-31, 사용자 지시). 결정 근거는 `handoff/decisions.md`. 1–11단계(아래 명세)는 완료이며, 그 동작과 테스트는 보존한다.

## 목표와 경계
- 합성 측정 시스템 3종에 교차 Gage R&R을 적용해 반복성·재현성을 분리하고, 측정 오차가 Cpk와 오판정에 주는 영향을 계산하고, 가드밴드를 사전 기준으로 고른다.
- 공고의 "검사/측정 시스템 개발"에 닿는 분석 연습이다. 표현은 "합성 측정 시스템 분석 연습", "합성 Gage R&R 계산"이다. "MSA 수행", "측정 시스템 개발 경험", "게이지 평가 실무"로 쓰지 않는다.
- 실제 게이지, 실제 작업자, 실제 부품이 아니다. 판정 기준 표의 10%·30%는 널리 쓰이는 관행 값을 연습에 빌린 것이며 SL 기준이 아니다.
- 제외: 편의성(bias)·선형성·안정성 연구, 계수형 MSA, 판정기 동작 변경, 외부 패키지.

## 보존 조건
- 기존 코드, 설정, 테스트, 기존 보고서는 수정하지 않는다. README에 절을 덧붙이는 것만 예외다.
- 새 코드는 `src/msa.py`, 새 테스트는 `tests/test_msa.py`, 새 설정은 `recipes/msa_lamp.json`이다.
- 값 확정은 `confirm_value`, 판정은 `judge_value`다. 규격은 `two_sided_item`으로 읽는다.

## 설정 `recipes/msa_lamp.json`
```json
{
  "generator": "generator_measured.json",
  "inspection": "LEAK",
  "parts": 10,
  "operators": 3,
  "trials": 3,
  "study_seed": 42,
  "gauges": {
    "good": {"repeatability": 0.08, "operator": 0.05, "interaction": 0.0},
    "marginal": {"repeatability": 0.25, "operator": 0.15, "interaction": 0.05},
    "poor": {"repeatability": 0.50, "operator": 0.30, "interaction": 0.15}
  },
  "guard_multipliers": ["0", "0.5", "1", "1.5", "2", "2.5", "3"],
  "products": 5000,
  "dev_seeds": "0-29",
  "holdout_seeds": "1000-1029",
  "max_false_accept": 0.05
}
```
- `generator`는 설정 파일 폴더 기준 경로다. 없거나 측정 설정이 아니면 종료 코드 2다.

| 키 | 타입 | 범위 |
| --- | --- | --- |
| `generator`, `inspection` | 문자열 | 비어 있지 않음 |
| `parts` | 정수 | 2–10. K3 표의 범위 |
| `operators` | 정수 | 2–3. K2 표의 범위 |
| `trials` | 정수 | 2–3. K1 표의 범위 |
| `study_seed` | 정수 | 0 이상 2³¹−1 이하 |
| `gauges` | 객체 | 1–10개. 이름은 `^[a-z][a-z0-9_]{0,31}$` |
| 게이지 값 | 유한한 수 | 공정 σ에 대한 비율. 0 이상 100 이하. `repeatability`만 0 초과 |
| `guard_multipliers` | 문자열 목록 | 비어 있지 않음, 소수 문자열 `^\d+(\.\d+)?$`, 수치로 중복 없음, 오름차순 |
| `products` | 정수 | 1–1000000 |
| `dev_seeds`, `holdout_seeds` | 문자열 | `시작-끝`. 둘 다 0 이상 2³¹−1 이하 정수, 시작 ≤ 끝 |
| `max_false_accept` | 유한한 수 | 0–1 |

- 개발·홀드아웃 시드는 겹칠 수 없다. 없는 키, 허용 밖 키, 타입·범위 위반은 종료 코드 3이다. bool은 숫자가 아니다. 범위를 넘는 큰 정수도 위 범위 위반이고, `10**400`처럼 float로 바꿀 수 없는 값도 예외 없이 종료 코드 3이다.

## 자료 생성
공정: `c = (lsl + usl) / 2`, `σ = (usl − lsl) / (6 × process_cpk)`.

게이지 하나의 연구는 시드 `study_seed + 게이지 순서`(설정 순서, 0부터)의 `random.Random` 하나로 만든다. 호출 순서는 다음과 같다.
1. 부품 `i`마다 `gauss(c, σ)`로 참값
2. 작업자 `j`마다 `gauss(0, operator × σ)`로 편차
3. `(i, j)`마다 `gauss(0, interaction × σ)`로 교호작용. 값이 0이어도 호출한다
4. `i → j → k` 순서로 측정마다 `gauss(0, repeatability × σ)`로 오차

측정값은 참값 + 편차 + 교호작용 + 오차를 `confirm_value`로 확정한 문자열이다.

## 교차 분산 분석
`p`, `o`, `r`을 부품, 작업자, 반복 수라 한다. 계산은 소수 문자열에서 만든 `Fraction`으로 하고, 제곱근과 F 확률만 float다.

```text
SS_part = o r Σ(ȳ_i − ȳ)²              df = p − 1
SS_op   = p r Σ(ȳ_j − ȳ)²              df = o − 1
SS_int  = r ΣΣ(ȳ_ij − ȳ_i − ȳ_j + ȳ)²  df = (p − 1)(o − 1)
SS_e    = ΣΣΣ(y − ȳ_ij)²               df = p o (r − 1)
```

- `F = MS_int / MS_e`, `p_int = P(F(df_int, df_e) ≥ F)`. `MS_e = 0`이면 `MS_int > 0`일 때 `p_int = 0`, `MS_int = 0`일 때 `p_int = 1`이다.
- `p_int > 0.25`이면 교호작용을 오차에 합친다. `MS_e' = (SS_int + SS_e) / (df_int + df_e)`, `σ²_int = 0`, 분모 항 `M = MS_e'`.
- 그 밖에는 `MS_e' = MS_e`, `σ²_int = max(0, (MS_int − MS_e) / r)`, `M = MS_int`.
- `σ²_e = MS_e'`, `σ²_op = max(0, (MS_op − M) / (p r))`, `σ²_part = max(0, (MS_part − M) / (o r))`.
- `EV² = σ²_e`, `AV² = σ²_op + σ²_int`, `GRR² = EV² + AV²`, `PV² = σ²_part`, `TV² = GRR² + PV²`.

F 꼬리 확률은 정규화 불완전 베타 함수를 연분수로 구한다. `P(F(d1, d2) ≥ x) = I_{d2/(d2 + d1 x)}(d2/2, d1/2)`.

## 평균·범위법 대조
분산 분석 결과를 다른 식으로 확인하는 참고값이다. 판정에는 쓰지 않는다.

- `EV = R̄ × K1`. `R̄`은 부품·작업자 칸 `p × o`개의 범위 평균이다. `K1`: r=2 0.8862, r=3 0.5908
- `AV = √max(0, (X̄_diff × K2)² − EV² / (p r))`. `X̄_diff`는 작업자별 전체 평균의 최댓값 − 최솟값이다. `K2`: o=2 0.7071, o=3 0.5231
- `PV = R_p × K3`. `R_p`는 부품별 전체 평균의 최댓값 − 최솟값이다. `K3`: p=2 0.7071, 3 0.5231, 4 0.4467, 5 0.4030, 6 0.3742, 7 0.3534, 8 0.3375, 9 0.3249, 10 0.3146
- K1의 값은 칸 수가 많을 때의 근삿값이다. 칸 수에 따른 `d₂*` 보정을 하지 않는 고정 상수 근사임을 README에 밝힌다. 칸이 적은 연구(`p × o`가 작을 때)에서는 근사가 거칠다. 그래서 이 표는 참고값이고 판정에 쓰지 않는다.

## 지표와 판정

| 지표 | 정의 |
| --- | --- |
| `pct_grr` | `100 × GRR / TV`. `TV = 0`이면 빈칸 |
| `pct_tolerance` | `100 × 6 GRR / (usl − lsl)` |
| `ndc` | `floor(1.41 × PV / GRR)`. `GRR = 0`이면 빈칸 |
| `verdict` | `pct_grr < 10` 허용, `10 ≤ pct_grr ≤ 30` 조건부, `> 30` 부적합. 빈칸이면 판정 불가 |
| `ndc_ok` | `ndc ≥ 5`면 참, 아니면 거짓. `ndc`가 빈칸이면 빈칸(계산 불가). 거짓과 구분한다 |

**Cpk 영향**: 공정이 중앙이라 가정하고 관측 Cpk를 계산한다. `Cpk_obs = (usl − lsl) / (6 √(σ² + GRR²))`. 설정의 `process_cpk`를 참값으로 삼는다.

## 가드밴드 모의
게이지별로, 시드마다 `products`개를 다음 순서로 만든다. `random.Random(시드)` 하나를 쓴다.
1. `random() < defective_product_probability`이면 결함이다
2. `gauss(c + 결함 이동 × σ, σ)`로 참값을 뽑아 `confirm_value`로 확정한다
3. `gauss(0, m)`을 더해 측정값을 `confirm_value`로 확정한다. `m = σ √(repeatability² + operator² + interaction²)`

- 모의의 `m`은 설정 값이고, 가드밴드 폭의 `GRR`은 연구에서 추정한 값이다. 작업자 분산을 측정마다 독립으로 뽑는 단순화를 README에 공개한다.
- 참 불량은 참값을 `judge_value`로 판정한 FAIL이다.
- 합격 한계는 소수 셋째 자리로 **항상 안쪽으로** 자른다. 하한은 `lsl + g × GRR`을 올림, 상한은 `usl − g × GRR`을 내림한다. `ROUND_HALF_UP`을 쓰면 12.9995가 13.000이 되어 규격 밖 값을 합격시키기 때문이다. `GRR`은 `repr(GRR)`로, `g`는 소수 문자열로 분수에 옮겨 정확히 계산한다(리뷰 020).
- 측정값은 `하한 ≤ 값 ≤ 상한`이면 합격이다. `g = 0`이면 `judge_value`와 같다. 하한이 상한 이상이면 그 후보는 `가드 불가`다.
- `false_accept` = 참 불량 중 합격 / 참 불량 수. 참 불량이 0이면 빈칸이고 조건 미달이다.
- `false_reject` = 참 양품 중 불합격 / 참 양품 수. 참 양품이 0이면 빈칸이고 최소화 비교에서 제외한다.
- `가드 불가` 후보는 두 값이 빈칸이고 선택에서 제외한다.
- 시드 합산 원시 값을 더한다. 비교는 분수, 표시는 소수 넷째 자리 `ROUND_HALF_UP`이다.

## 가드밴드 선택 (결과 전 고정)
게이지마다 개발 시드에서 `false_accept ≤ max_false_accept`인 후보 중 `false_reject`가 가장 작은 `g`를 고른다. 동률이면 작은 `g`다. 없으면 `기준 충족 가드밴드 없음`이고 완화하지 않는다. 홀드아웃은 선택이 조건을 유지하면 `확인`, 아니면 `미달`이다. 다시 고르지 않는다. 선택이 없으면 `검증할 선택 없음`이다. 게이지 자체는 고르지 않고 게이지별로 보고한다.

## 작업자 고정 편차 민감도 (참고, 선택에 쓰지 않음)
독립 추출 단순화가 숨기는 위험을 드러낸다. 작업자가 고정 편차를 가진 채 연속 측정하는 경우를 게이지별로 본다.

- 입력은 선택된 `g`와 홀드아웃 시드다. 선택이 없으면 그 게이지는 `검증할 선택 없음` 한 행이다.
- 작업자 `j`(0부터)의 고정 편차는 `d_j = (2j / (o − 1) − 1) × operator × σ`다. `o=3`이면 `−1, 0, +1`배이고 `o=2`이면 `−1, +1`배다. 난수가 아니다.
- 제품 번호 `n`(0부터)은 작업자 `n mod o`가 측정한다. 측정값은 참값 + `gauss(d_j, m')`이다. `m' = σ √(repeatability² + interaction²)`.
- 호출 순서는 가드밴드 모의와 같다(`random()`, 참값 `gauss`, 측정 `gauss`). 같은 시드의 참값 열이 모의와 같다.
- 작업자별 `false_accept`, `false_reject`를 낸다. 합산 방식은 가드밴드 모의와 같다.

## 실행과 보고서
```powershell
py -m src.msa recipes/msa_lamp.json
```
- 정렬은 전부 설정의 게이지 순서, 그 안에서 입력 순서다. 번호는 1부터 쓴다. 빈칸은 "계산 불가"다.
- `reports/msa_lamp_study.csv`: `gauge, part, operator, trial, value`.
- `reports/msa_lamp_grr.csv`: `gauge, ss_part, ss_op, ss_int, ss_e, df_part, df_op, df_int, df_e, ms_part, ms_op, ms_int, ms_e, p_int, pooled, var_e, var_op, var_int, var_part, ev, av, grr, pv, tv, pct_grr, pct_tolerance, ndc, ndc_ok, verdict, ar_ev, ar_av, ar_pv, cpk_true, cpk_obs`. 값은 소수 넷째 자리 `ROUND_HALF_UP`, `p_int`는 여섯째 자리, `pooled`·`ndc_ok`는 `1`·`0`·빈칸이다.
- `reports/msa_lamp_guard.csv`: `section, gauge, operator, multiplier, lower, upper, status, true_defects, false_accepts, false_accept, true_good, false_rejects, false_reject, value`.
  - `notice`: 합성 경고 문장 한 행.
  - `development`: 게이지×후보마다 한 행. `가드 불가`는 `status`에 적는다.
  - `selection`: 게이지마다 한 행. `multiplier`가 선택이고, 없으면 `value`에 `기준 충족 가드밴드 없음`.
  - `holdout`: 게이지마다 한 행. 선택값의 지표와 `value`에 `확인`·`미달`·`검증할 선택 없음`.
  - `operator_sensitivity`: 게이지×작업자마다 한 행.
- 같은 입력은 바이트까지 같다. 설정 오류는 종료 코드 3, 인자·파일 오류는 종료 코드 2다. 보고서는 전부 계산된 뒤에 쓴다.

## 사전 기대표
| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T190 | `p=o=r=2`. 부품1 작업자1 `1,3`, 부품1 작업자2 `3,5`, 부품2 작업자1 `5,7`, 부품2 작업자2 `7,9` | SS 32, 8, 0, 8. `p_int` 1, 합침. `σ²_e` 1.6, `σ²_op` 1.6, `σ²_part` 7.6, `σ²_int` 0. `pct_grr` 54.43, `ndc` 2 |
| T191 | 같은 구성. `1,2`, `3,4`, `3,4`, `1,2` | SS 0, 0, 8, 2. `p_int` 0.0161, 합치지 않음. `σ²_e` 0.5, `σ²_int` 3.75, `σ²_op` 0, `σ²_part` 0. `pct_grr` 100, `ndc` 0 |
| T192 | ① 모든 값이 같음 ② 칸 안 오차 0, 교호작용 있음 `1,1`, `3,3`, `3,3`, `1,1` | ① 오류 없음. `pct_grr`, `ndc` 빈칸, 판정 불가 ② `p_int` 0, `σ²_e` 0, `σ²_int` 4 |
| T193 | F 꼬리: `(1,1,1)`, `(2,10,3)`, `(1,4,16)`, 큰 값 `(1,4,1e6)` | 0.5, 0.0954, 0.0161, 0에 가까운 유한값 |
| T194 | T190 자료의 평균·범위법 | EV 1.7724, AV 1.1021, PV 2.8284 |
| T195 | `pct_grr` 9.999, 10, 30, 30.001 / `ndc` 4, 5 | 허용, 조건부, 조건부, 부적합 / 거짓, 참 |
| T196 | 규격 7~13, `process_cpk` 1.33, `GRR = 0.5σ`, `0` | `Cpk_obs` 1.1896, 1.33 |
| T197 | 같은 시드 두 번, 난수를 평균으로 돌려주는 stub | 연구 동일. 행 수 90. 호출 순서가 명세와 같음. 교호작용 0이어도 호출 |
| T198 | 규격 7~13, `g` 1.5, `GRR` 0.1 / `g` 40, `GRR` 0.1 / `g` 0.5, `GRR` 0.001 | 한계 7.150, 12.850 / `가드 불가` / 7.001, 12.999 (안쪽 자름, 13.000이면 실패) |
| T199 | `g=0`에서 (참, 측정): `(13.100, 12.900)`, `(12.900, 13.100)`, `(10.000, 10.000)`, `(13.100, 13.200)` / 참 양품 0건 또는 참 불량 0건의 묶음 | 참 불량 2 중 합격 1, 참 양품 2 중 불합격 1 / 각 비율 빈칸. 참 불량 0은 조건 미달, 참 양품 0은 비교 제외 |
| T200 | 후보 `(g, false_accept, false_reject)`: `(0, 0.06, 0.01)`, `(1, 0.05, 0.03)`, `(2, 0.05, 0.03)`, `(3, 0.01, 0.09)` / 전부 0.06 | `1` 선택 / `기준 충족 가드밴드 없음` |
| T201 | 홀드아웃 함수 | `확인`, `미달`, `검증할 선택 없음`. 다시 고르지 않음 |
| T202 | 잘못된 설정: 없는 키, 허용 밖 키, 게이지 안 허용 밖 키, 잘못된 게이지 이름, `parts` 11, `trials` 4, `repeatability` 0, 음수 `operator`, 정렬 안 된 후보, 중복 후보(`"1"`, `"1.0"` 포함), 빈 후보, `products: 10**400`, `study_seed: 2³¹`, NaN, bool, 시드 문자열 `5-1`·`abc`·`-1-3`, 겹치는 시드, 비측정 설정 | 비측정 설정은 종료 코드 2, 나머지는 종료 코드 3. 보고서 미생성 |
| T203 | 두 폴더에서 반복 | 보고서 3개 바이트 동일 |
| T204 | 실행 뒤 기존 파일 | 기존 설정·보고서 바이트 불변, 전체 기존 테스트 통과 |
| T249 | 작업자 민감도: `o=3`, `operator=0.15`, σ=1 / `o=2` / 난수 stub / 같은 시드 참값 | `d_j` −0.15, 0, 0.15 / −0.15, 0.15 / 제품 0, 1, 2, 3의 작업자 0, 1, 2, 0, `m'` 사용 / 가드밴드 모의와 같음 |
| T250 | 보고서 열: 보고서 3개 | 헤더가 명세의 열 순서와 같고 `ndc` 빈칸 때 `ndc_ok` 빈칸 |

## 구현 순서
1. **12-1**: 분산 분석, F 꼬리, 평균·범위법, 지표, T190–T196.
2. **12-2**: 자료 생성, 가드밴드, 선택, 민감도, 보고서, T197–T204, T249–T250.

# v2 11단계 명세 (구현 완료, 2026-10-31 · 리뷰 018·019 지적 수정, 사용자 승인 전)

상태: **Sol 검토 뒤 진행 확정** (2026-10-31, 사용자 지시). 결정 근거는 `handoff/decisions.md`. 1–10단계(아래 명세)는 완료이며, 그 동작과 테스트는 보존한다.

## 목표와 경계
- 생산 도중 측정 평균이 이동하는 합성 측정열에서, 기존 3:2 규칙, 단순 이동평균 임계값, 직접 구현한 로지스틱 회귀의 경보 성능을 같은 자료로 비교한다.
- 목표는 사전 예측이 아니라 **평균 이동 뒤의 변화 검출**이다. 표현은 "합성 공정 이상 검출", "합성 홀드아웃 시나리오 평가"다. 예지보전 구현이나 이상 예측으로 쓰지 않는다.
- 성능은 같은 평균 이동 가정 안에서만 뜻이 있다. 실제 설비 데이터가 아니다.
- 제외: 신경망, 외부 패키지, 특징 자동 선택, 판정기와 기존 생성기 변경, 온라인 학습.

## 보존 조건
- 기존 코드, 설정, 테스트, 기존 보고서는 수정하지 않는다. README에 이 단계의 절을 덧붙이는 것만 예외다.
- 새 코드는 `src/anomaly.py`, 새 테스트는 `tests/test_anomaly.py`, 새 설정은 `recipes/anomaly_lamp.json`이다.
- 측정열은 기존 생성기를 거치지 않는다. 정지가 측정 순서를 바꾸지 않게 하기 위해서다. 판정은 `judge_value`, 값 확정은 `confirm_value`를 쓴다.

## 설정 `recipes/anomaly_lamp.json`
허용 밖 키, 없는 키, 타입·범위 위반은 종료 코드 3이다. 중첩 객체도 같다. bool은 숫자로 인정하지 않고, 수치는 유한해야 한다. `generator`는 설정 파일 폴더 기준 경로다.

| 키 | 값 | 규칙 |
| --- | --- | --- |
| `generator` | `generator_measured.json` | 측정 설정. 규격, `process_cpk`, 결함 확률, `defect_shift_sigma`를 여기서 읽는다 |
| `inspection` | `LEAK` | 양측 규격의 검사 |
| `length` | 400 | 정수, `onset_max`보다 큼 |
| `onset_min`, `onset_max` | 100, 300 | 정수, `window ≤ onset_min ≤ onset_max` |
| `shifts` | `[1.0, 1.5, 2.5]` | 비어 있지 않고 서로 다른 양수 목록 |
| `window` | 10 | 2 이상의 정수 |
| `ewma_lambda` | 0.2 | 0 초과 1 이하 |
| `splits` | 아래 구조 | 키는 `train`, `validation`, `holdout`, 값은 `{"seed_start": 정수 ≥ 0, "count": 정수}`. `count`는 `2 × len(shifts)`의 양의 배수. 시드 범위 `[seed_start, seed_start + count)`가 겹치면 위반 |
| `learning_rate`, `l2` | 0.1, 0.001 | 양수 |
| `iterations` | 2000 | 1 이상의 정수 |
| `false_limit` | 2 | 1,000건당 오탐 상한 |
| `min_detection`, `min_shift_detection` | 0.90, 0.70 | 0–1 |
| `repair_minutes` | 10 | 양수 |

```json
"splits": {
  "train": {"seed_start": 0, "count": 300},
  "validation": {"seed_start": 1000, "count": 240},
  "holdout": {"seed_start": 2000, "count": 240}
}
```

## 원천 측정열
시나리오 하나는 설비 한 대의 측정 `length`건이다.

```text
c = (lsl + usl) / 2, σ = (usl − lsl) / (6 × process_cpk)
측정값 = confirm_value(gauss(c + (결함 이동 + 고장 이동) × σ, σ))
```

**분할과 배정**

| 분할 | 시드 | 수 | 정상 | 고장 | 쓰임 |
| --- | --- | ---: | ---: | ---: | --- |
| 학습 | 0–299 | 300 | 150 | 이동량별 50 | 로지스틱 회귀 가중치, 표준화 |
| 검증 | 1000–1239 | 240 | 120 | 이동량별 40 | 임계값, 방법 선택 |
| 홀드아웃 | 2000–2239 | 240 | 120 | 이동량별 40 | 선택 확인, 정책 모의 |

분할 안의 위치 `i`(0부터)가 짝수면 정상이고, 홀수면 고장이며 이동량은 `shifts[((i − 1) / 2) mod 3]`이다.

**난수 호출 순서**: 시나리오 시드로 `random.Random`을 만든다. 고장이면 먼저 `randint(onset_min, onset_max)`로 `onset`을 뽑는다. 그 뒤 측정 `t = 0…length−1`마다 `random()`으로 결함 여부를 뽑고, `gauss`로 값을 뽑는다. 정상 시나리오도 결함을 뽑는다. `t ≥ onset`이면 고장 이동을 더한다.

## 판단 시점과 레이블
- 판단 시점은 모든 방법이 같다. `t ≥ window − 1`이다. 기본값은 `t ≥ 9`다. 특징은 `t`와 그 이전 값만 쓴다.
- **학습 레이블**: 고장 시나리오에서 `t ≥ onset`이면 1, 그 밖은 0이다.
- 학습 표본은 판단 시점의 창 전체다. 양성·음성 창 수를 보고서에 쓴다. 클래스 비율 보정은 하지 않는다. 고장 시나리오 비율 50%와 창의 양성 비율은 다르다.

## 특징
측정값을 `x = (value − c) / σ`로 정규화한다. 창은 현재값을 포함한 `[t − window + 1, t]`다.

| 특징 | 정의 |
| --- | --- |
| `mean` | 창 평균 |
| `sd` | 창 표본 표준편차(`N−1`) |
| `max` | 창 최댓값 |
| `slope` | 창 안의 시간 `0…window−1`에 대한 최소제곱 기울기 |
| `ewma` | `z_0 = λ·x_0`, `z_t = λ·x_t + (1−λ)·z_{t−1}`. 시나리오 시작부터 계산 |
| `fail_share` | 창의 원 측정값을 `judge_value`로 판정한 FAIL 비율 |

**표준화**: 학습 분할의 전체 창에서 특징별 평균과 모집단 표준편차를 구한다. 표준편차가 0이면 1로 나눈다. 검증·홀드아웃에도 이 값을 쓴다.

## 방법

| ID | 판단값 | 조정 값 |
| --- | --- | --- |
| `rule_3_2` | 최근 3건 중 FAIL 2건 이상이면 경보 | 없음 |
| `moving_average` | `mean ≥ h` | `h` |
| `logistic` | `p ≥ h` | 가중치, `h` |

**3:2 규칙**: FAIL 창은 `t = 0`부터 기존 `EquipmentState.record`와 같게 쌓는다. 비교에서는 다른 방법과 같은 판단 시점 `t ≥ 9`의 첫 참만 경보로 인정한다. 기존 동작 재현 함수는 별도로 두고 `t = 1`의 정지도 그대로 낸다.

**로지스틱 회귀**
```text
z = b + w·s
p = 1 / (1 + exp(−z))     (z ≥ 0)
p = exp(z) / (1 + exp(z)) (z < 0)
J = (1/N) Σ [max(z, 0) − y z + log1p(exp(−|z|))] + (λ/2) Σ w_j²     (절편 제외)
∂J/∂w_j = (1/N) Σ (p − y) s_j + λ w_j,  ∂J/∂b = (1/N) Σ (p − y)
```

`z`를 자르지 않는다. 부호별 식은 어떤 `z`에서도 넘침 없이 계산되고, 손실과 경사가 같은 식이다. 배치 경사 하강이고, 가중치 초기값은 0이다. 난수를 쓰지 않으므로 같은 자료는 같은 가중치를 낸다. 마지막 갱신 뒤의 계수로 전체 경사(절편 포함)의 유클리드 노름을 구해 보고하고, `1e-3`보다 크면 `수렴 미달`로 표시한다. 실패로 처리하지 않는다.

## 지표
시나리오마다 첫 경보 위치 `a`를 구한다. 없으면 `무경보`다.

| 고장 시나리오 분류 | 조건 | 지연 비용 |
| --- | --- | --- |
| `detected` | `a ≥ onset` | `a − onset` |
| `early` | `a < onset` | `length − onset` |
| `missed` | 무경보 | `length − onset` |

| 지표 | 정의 |
| --- | --- |
| `detection_rate` | `detected` / 고장 시나리오. 이동량별로도 낸다 |
| `early`, `missed` | 건수 |
| `mean_delay_cost` | 모든 고장 시나리오의 지연 비용 평균. 조기 오탐과 무경보가 유리해지지 않는다 |
| `mean_detected_delay` | `detected`의 지연 평균. 참고값 |
| `false_per_1000` | 정상 노출의 경보 수 / 정상 노출 판단 시점 수 × 1000 |

**정상 노출**: 판단 시점이 대상이다. 정상 시나리오는 `[window−1, 끝]`, 고장 시나리오는 `[window−1, onset−1]`이다. 경보가 나면 그 측정까지 세고 그 시나리오의 노출을 끝낸다. 노출이 0이면 표시는 빈칸이다.

합산은 시나리오별 원시 값을 더한다. 비교는 분수로 하고 표시는 소수 넷째 자리 `ROUND_HALF_UP`이다.

## 임계값과 방법 선택 (결과 전 고정)
**임계값 후보**: 검증 분할의 판단값을 소수 넷째 자리 `ROUND_HALF_UP`으로 양자화한 고유값과, 가장 큰 값보다 큰 `무경보` 후보다. 비교는 양자화한 판단값으로 한다. 후보별 평가는 시나리오의 누적 최댓값을 정렬·이진 탐색해 전체 창을 다시 돌지 않는다. 후보 수를 보고서에 쓴다.

**임계값 선택**: 다음을 모두 만족하는 후보 중 `mean_delay_cost`가 가장 작은 값이다. 동률이면 큰 `h`다. 없으면 그 방법은 `임계값 없음`이고 선택 대상에서 빠지며 지표 칸을 비운다.
1. `false_per_1000 ≤ 2`
2. `detection_rate ≥ 0.90`
3. 이동량별 `detection_rate ≥ 0.70`

**방법 선택**: 검증에서 위 세 조건을 만족하는 방법 중 `mean_delay_cost`가 가장 작은 방법이다. 동률이면 `rule_3_2`, `moving_average`, `logistic` 순이다. `rule_3_2`도 같은 조건을 적용한다. 없으면 `기준 충족 방법 없음`이고 완화하지 않는다. 로지스틱이 선택되지 않아도 결과를 바꾸지 않는다.

**홀드아웃**은 선택 방법이 세 조건을 유지하면 `확인`, 아니면 `미달`이다. 다시 고르지 않는다. 선택이 없으면 `검증할 선택 없음`이다.

## 정책 모의
경보 성능과 나눠서 낸다. 홀드아웃 분할에서 임계값이 있는 방법마다 계산한다. 정지 뒤 생산 변화와 설비 전환은 모의하지 않는다.

| 항목 | 정의 |
| --- | --- |
| `suspect_output` | 고장 시나리오 평균. `detected`는 `a − onset + 1`(경보 측정 포함), `early`와 `missed`는 `length − onset` |
| `false_stops` | `false_per_1000`과 같은 값 |
| `stop_minutes` | 시나리오 1,000개당 첫 경보 수 × `repair_minutes`. 단위는 가상 분 |

## 실행과 보고서
```powershell
py -m src.anomaly recipes/anomaly_lamp.json
```

- `reports/anomaly_lamp_methods.csv`, `reports/anomaly_lamp_model.csv`, `reports/anomaly_lamp_replay.csv`를 쓴다.
- 같은 입력은 바이트까지 같다. 설정 오류는 종료 코드 3, 인자·파일 오류는 종료 코드 2다.
- `methods.csv` 절: `notice`, `validation`, `validation_shift`, `holdout`, `holdout_shift`, `policy`, `selection`.
- `model.csv`: 분할 시드, 양성·음성 창 수, 특징별 표준화 값과 가중치, 절편, 임계값, 경사 노름, 후보 수.
- `model.csv`에 `generator`, `inspection`, `window`, `ewma_lambda`도 적는다. 재생 행을 다시 계산하는 데 필요하다.
- `replay.csv`: `logistic` 한 방법의 경보가 어떻게 나왔는지 설명한다. 대상은 홀드아웃의 첫 고장 시나리오(위치 1)다. `logistic`이 선택되지 않아도 쓴다.
  - 첫 경보를 `a`라 할 때 시작은 `max(window − 1, min(onset − 5, a))`, 끝은 `a`다. 그래서 조기 경보면 경보 행 하나만 남는다.
  - 무경보나 임계값 없음이면 `a`가 없다. 시작은 `max(window − 1, onset − 5)`, 끝은 `min(onset + 20, length − 1)`이다.
  - 열: `seed`, `method`, `onset`, `status`, `t`, `value`, `window_values`(창의 원 측정값을 공백으로 이음), `ewma_prev`, 특징 6개, 표준화값 6개, `z`, `p`, `threshold`, `alarm`.
  - `status`는 `early`, `detected`, `missed`, `임계값 없음`이다. 임계값 없음이면 `threshold`, `alarm`은 빈칸이다.

## 사전 기대표 (초안)
공통: 규격 7~13, `process_cpk` 1.33, 이동 2.5·5.0, 기본값은 설정대로다.

| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T172 | 측정 함수, `gauss(μ,σ)=μ` | 정상 `10.000`, 고장 2.5σ `11.880`, 결함 `13.759`, 결함+고장 `15.639`, `onset − 1`은 `10.000`, `onset`은 `11.880` |
| T173 | 같은 시드 두 번, 위치 `i`별 배정 | 측정열 동일. `i=0` 정상, `i=1` 1.0σ, `i=3` 1.5σ, `i=5` 2.5σ, `i=7` 1.0σ. 학습 분할의 정상 150, 이동량별 50 |
| T174 | 정규화 값 창 `[0,0,0,0,0,0,0,0,0,10]`, 시간 `0…9` | `mean` 1.0000, `max` 10.0000, `sd` 3.1623, `slope` 0.5455, `fail_share` 0.1000 |
| T175 | `t` 뒤 값 변경 | `t`까지의 특징 불변 |
| T176 | `splits` 시드 겹침 | 종료 코드 3 |
| T177 | 검증 측정열 변경 | 표준화 값과 가중치 불변. 영분산 특징은 1로 나눔 |
| T178 | 좌표 `-2,-1,1,2`, 레이블 `0,0,1,1`, 임계값 0.5 | 정확도 1.0, 같은 입력은 같은 가중치, 경사 노름은 마지막 계수 기준. `z`가 ±40, ±1000이어도 오류 없고 손실이 유한 |
| T179 | 임계값 함수, 정상 노출 1000, 고장 3개(이동량 1개). 후보 `(h, 오탐, 검출률, 지연 비용)`: `(0.2, 3, 1.0, 1)`, `(0.3, 2, 1.0, 5)`, `(0.4, 2, 1.0, 5)`, `(0.5, 1, 2/3, 3)` | `0.4` 선택(0.2는 오탐 초과, 0.5는 검출 미달, 동률은 큰 값). 모두 미달이면 `임계값 없음` |
| T180 | `length` 400, `onset` 200, 경보 위치 `199`, `200`, `210`, 없음 | `early` 비용 200, `detected` 0, `detected` 10, `missed` 200. 평균 비용 102.5, `detection_rate` 0.5, `mean_detected_delay` 5 |
| T181 | 노출: 정상 시나리오 `length` 400 무경보, 정상 시나리오 경보 위치 9, 고장 `onset` 100 무경보 | 판단 시점 391, 1, 91로 합 483. 경보 1건. `false_per_1000` 2.0704로 상한 2 초과 |
| T182 | 방법 선택: ① 셋 다 통과, 비용 30·20·10 ② 동률 ③ 이동량별 0.60인 방법 ④ 전부 미달 | ① `logistic` ② 표의 순서 ③ 탈락 ④ `기준 충족 방법 없음` |
| T183 | FAIL 열 `F F P P …` | 재현 함수는 `t=1`에 정지. 비교 함수는 `t=9` 이후 첫 참만 인정. 재현 함수의 판정이 `EquipmentState.record`와 모든 위치에서 같음 |
| T184 | 정책: `onset` 200, `length` 400, 경보 200, 205, 없음, 150 | `suspect_output` 1, 6, 200, 200. 평균 101.75 |
| T185 | 홀드아웃 함수 | `확인`, `미달`, `검증할 선택 없음`. 다시 고르지 않음 |
| T186 | 전체 실행을 두 폴더에서 반복. 단위 테스트는 시나리오·반복 수를 줄인 설정으로, 기본 설정은 실행 기록으로 확인 | 보고서 3개 바이트 동일 |
| T187 | 잘못된 설정: 없는 키, 허용 밖 키, `splits` 안의 허용 밖 키, `window` 1, `onset_min > onset_max`, `shifts` 빈 목록, `shifts` 중복, `iterations` 0.5, `count`가 배수 아님, NaN, bool 값, 비측정 설정 | 비측정 설정은 종료 코드 2, 나머지는 종료 코드 3. 보고서 미생성 |
| T188 | 실행 뒤 기존 파일 | 기존 설정·보고서 바이트 불변, 전체 기존 테스트 통과 |
| T189 | 재생 함수: ① 경보 있음(`a = onset + 3`) ② 조기 경보(`a = onset − 50`) ③ 무경보 ④ 임계값 없음 | ① `onset − 5`부터 `a`까지 ② 경보 행 하나, `early` ③④ `onset + 20`까지, `missed`와 `임계값 없음`. ④는 `threshold`, `alarm` 빈칸. 각 행의 `window_values`, `ewma_prev`, `model.csv`로 다시 계산한 `p`가 같음 |

## 구현 순서
1. **11-1**: 측정열, 분할, 특징, T172–T177.
2. **11-2**: 로지스틱 회귀, 임계값, 지표, 선택, T178–T185.
3. **11-3**: 보고서, T186–T189.

## 산출물
- `src/anomaly.py`, `tests/test_anomaly.py`, `recipes/anomaly_lamp.json`
- `reports/anomaly_lamp_methods.csv`, `reports/anomaly_lamp_model.csv`, `reports/anomaly_lamp_replay.csv`
- README 절. 표현 규칙과 한계 포함

## 사용자 확인
| 항목 | 초안 값 | 왜 확인이 필요한가 |
| --- | --- | --- |
| 이동량 | 1.0, 1.5, 2.5σ | 작은 이동을 넣어야 방법 차이가 드러남 |
| 시나리오 수 | 학습 300, 검증 240, 홀드아웃 240 | 이동량별 동수 배정 |
| 창 크기 | 10 | 짧으면 민감하고 길면 지연이 늘어남 |
| 오탐 기준 | 정상 노출 1,000건당 2건 이하 | 정상 설비 정지를 얼마나 허용할지 정함 |
| 검출 기준 | 전체 0.90, 이동량별 0.70 이상 | 선택 조건 |

# v2 10단계 명세 (구현 완료, 2026-10-31 · 리뷰 017 지적 수정, 사용자 승인 전)

상태: **Sol 검토 뒤 진행 확정** (2026-10-31, 사용자 지시). 결정 근거는 `handoff/decisions.md`. 1–9단계(아래 명세)는 완료이며, 그 동작과 테스트는 보존한다.

## 목표와 경계
- LEAK 검사 스테이션 한 곳의 시퀀스를 스캔 주기 상태 기계로 모의하고, 판정 PC와 Modbus TCP로 측정값·판정·정지 신호를 주고받는다.
- 모의다. 실제 PLC, IEC 61131 프로그램, 실제 설비, 기능 안전 시스템이 아니다. 표현은 "Python 기반 PLC 스캔 모의", "소프트웨어 간 Modbus TCP 통신 구현"이고, 정지는 "통신 타임아웃 시 정지 상태로 전이하는 소프트웨어 모의"다.
- 제외: 래더 다이어그램, 실제 입출력, 보안 기능, 여러 스테이션, 외부 패키지.

## 보존 조건
- `src/rules.py`, 기존 테스트, 기존 설정, 샘플, 기존 보고서는 수정하지 않는다. README에 이 단계의 절을 덧붙이는 것만 예외다.
- 판정은 `judge_value`를 그대로 쓴다. 원문 value 문자열은 PC 쪽 기록에 남기고, 변환은 통신 어댑터만 한다.
- 새 코드는 `src/plc.py`, `src/modbus.py`, `src/station.py`, 새 테스트는 `tests/test_plc.py`, `tests/test_modbus.py`, `tests/test_station.py`다.

## 스캔 주기
시간은 스캔 번호다. 실제 시계를 쓰지 않는다. 스캔 하나는 가상 100ms다. 시작 스캔 번호는 0이고 첫 스캔은 1이다. **스캔마다 상태 전이는 전체에서 많아야 한 번이다.** 처리 순서는 다음과 같다.

1. **입력 스냅샷**: 입력 비트, 측정 원값, 보유 레지스터, 코일을 한 번에 복사한다. 스캔 중 값이 바뀌어도 그 스캔은 스냅샷만 본다.
2. **즉시 알람 검사**: `ALARM`이 아닌 상태에서 가드 열림(22), PC 하트비트(21), 클램프 모순(24), 측정 신호 이상(25)을 이 순서로 본다. 해당하면 `ALARM`으로 전이하고 3·4를 건너뛴다.
3. **정상 전이**: 현재 상태의 전이 조건이 참이면 전이한다. 다음 상태의 카운터는 0이다.
4. **타임아웃**: 전이가 없으면 카운터를 1 올리고, `카운터 > 키 값`이면 그 상태의 알람으로 전이한다. 전이 조건이 만료 스캔에 참이면 3에서 전이하므로 알람이 아니다.
5. **출력 갱신**: 새 상태의 기본 출력을 계산하고 인터록을 마지막에 적용한다.
6. **하트비트**: PLC 하트비트를 1 올린다.

PLC의 주소표 쓰기(출력, 입력 레지스터, 판정 레지스터 지우기)는 스캔 안에서 한 번에 끝난다. 실행 규약상 스캔 중 처리되는 Modbus 요청은 없다.

**초기값**

| 대상 | 초기값 |
| --- | --- |
| 상태, 카운터, 알람 코드 | `IDLE`, 0, 0 |
| 코일, 입력 레지스터, 보유 레지스터 | 모두 0 |
| 이전 출력 Q0–Q4 | 거짓 |
| 이전 `reset`, 이전 `manual_release` | 거짓 |
| PC 하트비트 마지막 변경 스캔 | 0. 시작 뒤 `heartbeat_scans`까지 유예 |
| PC 쪽 PLC 하트비트 마지막 변경 주기 | 0 |
| 마지막 거절 쌍 | 없음 |

## 입력과 출력

| 번호 | 입력 비트 | 뜻 |
| --- | --- | --- |
| I0 | `part_present` | 제품 도착 |
| I1 | `seated` | 착좌 확인 |
| I2 | `direction_ok` | 방향 확인 |
| I3 | `clamp_closed` | 클램프 닫힘 |
| I4 | `clamp_open` | 클램프 열림 |
| I5 | `guard_closed` | 가드 닫힘 |
| I6 | `measure_done` | 측정 완료 |

측정 원값은 모의 설비가 입력과 함께 주는 문자열이다.

| 번호 | 출력 코일 | 뜻 |
| --- | --- | --- |
| Q0 | `clamp_cmd` | 클램프 지령 |
| Q1 | `measure_cmd` | 측정 지령 |
| Q2 | `gate_ok` | OK 배출 |
| Q3 | `gate_ng` | NG 배출 |
| Q4 | `alarm_lamp` | 알람 표시 |

## 상태
상태 번호는 입력 레지스터 0에 그대로 쓴다.

| 번호 | 상태 | 기본 출력 | 전이 조건 | 다음 | 타임아웃 키·알람 |
| ---: | --- | --- | --- | --- | --- |
| 0 | `IDLE` | 없음 | `part_present`이고 `measure_done` 거짓 | `CHECK` | 없음 |
| 1 | `CHECK` | 없음 | `seated`, `direction_ok` | `CLAMP` | `check_scans` 30, 11 |
| 2 | `CLAMP` | Q0 | `clamp_closed` | `MEASURE` | `clamp_scans` 20, 12 |
| 3 | `MEASURE` | Q0, Q1 | 유효한 측정 완료 | `PUBLISH` | `measure_scans` 50, 13 |
| 4 | `PUBLISH` | Q0 | 항상. 변환 실패는 알람 23 | `WAIT_JUDGE` | 없음 |
| 5 | `WAIT_JUDGE` | Q0 | 유효한 판정 쌍 접수 | `UNCLAMP` | `judge_scans` 30, 14 |
| 6 | `UNCLAMP` | 없음 | `clamp_open` | `DISCHARGE` | `unclamp_scans` 20, 15 |
| 7 | `DISCHARGE` | 판정대로 Q2 또는 Q3 | `part_present` 거짓 | `IDLE` | `discharge_scans` 30, 16 |
| 8 | `ALARM` | Q4. Q0은 진입 값 유지 | 리셋 조건 | `IDLE` | 없음 |

- 측정값은 `MEASURE`에서 유효한 측정 완료를 본 스캔의 측정 원값으로 확정한다. 이때 입력 레지스터는 바꾸지 않는다.
- 유효한 측정 완료는 `measure_done` 참, 이전 Q1 참, `clamp_closed` 참, `clamp_open` 거짓이다.
- `PUBLISH`의 변환이 성공하면 그 스캔에 다음을 한 번에 한다. 보유 레지스터 1–2를 0으로 지움 → 입력 레지스터 3·4에 측정값 기록 → `measure_id` 증가 → `WAIT_JUDGE` 진입. 변환이 실패하면 `measure_id`는 그대로다. 그래서 PC가 새 ID를 볼 때 PLC는 이미 `WAIT_JUDGE`이고, 그 뒤 쓴 판정은 지워지지 않는다.
- 처리 제품 수는 `DISCHARGE`에서 `IDLE`로 갈 때 1 오른다. 16비트이고 65535 다음은 0이다.
- 먼저 난 알람을 유지한다. `ALARM`에서는 새 알람으로 코드를 바꾸지 않는다.

**알람 코드**: 11 착좌·방향, 12 클램프, 13 측정, 14 판정, 15 클램프 해제, 16 배출, 21 PC 하트비트, 22 가드, 23 측정값 변환, 24 클램프 모순, 25 측정 신호 이상.

**클램프 모순**: `clamp_closed`와 `clamp_open`이 함께 참이면 알람 24다. 둘 다 거짓은 이동 중이므로 정상이다.

**측정 신호 이상**: 다음이면 알람 25다. 측정 지령 전에 남아 있는 완료 신호와, 클램프가 풀린 채 온 완료 신호를 측정값으로 쓰지 않기 위해서다.
- `CHECK`나 `CLAMP`에서 `measure_done`이 참
- `MEASURE`에서 `measure_done`이 참인데 이전 Q1 거짓, `clamp_closed` 거짓, `clamp_open` 참 중 하나

`IDLE`은 `measure_done`이 거짓이 될 때까지 기다린다.

**인터록**: 입력은 기본 출력과 이전 출력이다. 출력 갱신의 마지막에 적용한다.
- `clamp_cmd`를 거짓에서 참으로 바꾸려면 `seated`, `direction_ok`, `guard_closed`가 모두 참이어야 한다. 이미 참이면 유지한다.
- `measure_cmd`는 `clamp_closed`, `clamp_open` 거짓, `guard_closed`가 모두 참일 때만 참이다.
- `gate_ok`와 `gate_ng`를 동시에 요청하면 **둘 다 거짓**이다.
- 게이트는 `clamp_open`이 참이고 `clamp_closed`가 거짓일 때만 참이다.
- `ALARM`에서 Q1, Q2, Q3은 거짓이다.

**알람 복구**
- `manual_release` 코일의 상승 에지를 `ALARM`에서 보면 래치하고, 래치가 있는 동안 Q0을 거짓으로 둔다. 코일을 꺼도 래치는 남는다. 다른 상태의 에지는 무시한다. 끄는 동작이므로 가드가 열려 있어도 적용한다.
- 리셋은 코일 `reset`의 상승 에지다. 에지 기억값은 상태와 관계없이 매 스캔 갱신한다. 그 스캔의 스냅샷에서 다음이 모두 참일 때만 `IDLE`로 간다. 하나라도 거짓이면 무시하고 다음 상승 에지를 기다린다.
  - `guard_closed`
  - `현재 스캔 − 마지막 변경 스캔 ≤ heartbeat_scans`
  - `clamp_open`이 참이고 `clamp_closed`가 거짓
  - `part_present`가 거짓
- 즉 작업자가 클램프를 풀고 제품을 치운 뒤에만 복귀한다. 제품 제거는 모의 설비의 입력 변경이다.
- 복귀 때 측정값, 판정 레지스터, 카운터, 알람 코드, `manual_release` 래치를 지운다. `measure_id`와 처리 제품 수는 유지한다. 중단된 제품은 `aborted`로 기록한다. 코일 `reset`과 `manual_release`는 PC가 끈다. PLC는 이 두 코일을 쓰지 않는다.

## Modbus TCP
소켓과 표준 라이브러리만 쓴다. 주소는 0부터 센다. Unit ID는 1이다. 모든 영역의 주소 범위는 0–15다. 범위 안의 미배정 주소는 읽으면 0을 돌려주고, 쓰면 예외 02다.

| 기능 코드 | 뜻 | 수량 | 정상 응답 PDU |
| --- | --- | --- | --- |
| 0x01 | Read Coils | 1–2000 | 기능, 바이트 수, 낮은 주소가 LSB인 비트. 남는 비트는 0 |
| 0x02 | Read Discrete Inputs | 1–2000 | 위와 같음 |
| 0x03 | Read Holding Registers | 1–125 | 기능, 바이트 수, 큰 바이트 먼저 |
| 0x04 | Read Input Registers | 1–125 | 위와 같음 |
| 0x05 | Write Single Coil | 값 `0xFF00`, `0x0000`만 | 요청 에코 |
| 0x06 | Write Single Register | | 요청 에코 |
| 0x10 | Write Multiple Registers | 1–123 | 기능, 시작 주소, 수량 |

**검증 순서**: 기능 → PDU 길이와 바이트 수 → 수량·값 → 주소 범위와 쓰기 권한.

| 조건 | 처리 |
| --- | --- |
| 프로토콜 ID가 0이 아님, 길이가 2–254 밖 | 프레임 손상. 연결 종료 |
| Unit ID가 1이 아님 | 응답 없이 그 프레임만 버림 |
| 지원하지 않는 기능 | 예외 01 |
| PDU 길이가 기능 형식과 다름, FC16 바이트 수 ≠ 수량×2, 수량·코일 값 위반 | 예외 03 |
| 시작 주소 + 수량이 16 초과, 쓰기 요청의 미배정·쓰기 금지 주소, 아래 쓰기 형식 위반 | 예외 02 |
| 처리 중 내부 오류 | 예외 04 |

- 프레임 전체 길이는 `6 + Length`다. `Length`는 Unit ID를 포함한다.
- FC16은 시작 주소 1, 수량 2만 받는다. FC06은 주소 0만 받는다. 그 밖의 쓰기는 값이 맞아도 예외 02다. PC 쓰기의 주소는 이 둘과 FC05의 코일 8·9뿐이다.
- 쓰기는 응답을 보내기 전에 주소표에 적용한다.
- 수신은 길이 기반 버퍼다. 분할·병합 수신을 모두 처리한다. 미완성 프레임에서 EOF가 오면 그 프레임을 버리고 연결을 닫는다.
- 쓰기 요청은 전체가 유효할 때만 적용한다. 부분 변경은 없다.
- 예외 응답은 `기능 | 0x80`, 예외 코드다. 트랜잭션 ID는 그대로 돌려준다.
- 클라이언트는 트랜잭션 ID, 프로토콜, Unit ID, 기능, 길이, 바이트 수, 에코 내용을 모두 확인한다. 다르면 오류로 보고 연결을 닫는다.
- 트랜잭션 ID는 클라이언트가 1부터 올리고 65535 다음은 1이다.

**주소표**

| 영역 | 주소 | 이름 | 쓰기 | 값 |
| --- | --- | --- | --- | --- |
| 코일 | 0–4 | Q0–Q4 | PLC만 | |
| 코일 | 8 | `reset` | PC | 초기 0 |
| 코일 | 9 | `manual_release` | PC | 초기 0 |
| 입력 | 0–6 | I0–I6 | 모의 설비만 | |
| 입력 레지스터 | 0 | 상태 번호 | PLC | 0–8 |
| 입력 레지스터 | 1 | 알람 코드 | PLC | 0은 없음 |
| 입력 레지스터 | 2 | `measure_id` | PLC | 초기 0, 측정마다 1씩 증가, 65535 다음 1 |
| 입력 레지스터 | 3, 4 | 측정값 상위·하위 워드 | PLC | |
| 입력 레지스터 | 5 | PLC 하트비트 | PLC | 매 스캔 +1, 65535 다음 0 |
| 입력 레지스터 | 6 | 처리 제품 수 | PLC | |
| 보유 레지스터 | 0 | PC 하트비트 | PC, FC06 | 주기마다 +1, 65535 다음 0 |
| 보유 레지스터 | 1 | `judge_id` | PC, FC16만. PLC는 진입 때 지움 | |
| 보유 레지스터 | 2 | 판정 | PC, FC16만. PLC는 진입 때 지움 | 1 PASS, 2 FAIL |

**측정값 변환**: `Decimal(문자열) × 1000`이 정수이고 −2147483648–2147483647이면 변환한다. 2의 보수이고 상위 워드가 앞선다. `-0.001`은 `FFFF FFFF`, 최솟값 `-2147483.648`은 `8000 0000`, 최댓값 `2147483.647`은 `7FFF FFFF`다. `1.2300`은 정확히 표현되므로 허용하고, `1.2345`는 변환 불가다. 워드는 수치만 나르며 `10.25`와 `10.250`의 차이는 기록의 원문으로만 남는다. 생성기는 항상 소수 셋째 자리다. PC는 두 워드를 부호 있는 32비트로 합쳐 1000으로 나눈 소수 셋째 자리 문자열로 복원하고 `judge_value`에 넣는다. 기록의 원문은 모의 설비가 준 문자열이고, 복원값과 수치가 같아야 한다.

**판정 접수**
- 판정은 FC16 한 번으로 레지스터 1–2를 함께 쓴다. 서버는 스캔 사이에 요청을 처리하므로 PLC는 두 값을 한 쌍으로 본다.
- 접수는 `WAIT_JUDGE` 진입 스캔의 다음 스캔부터 본다. `(0, 0)`은 미접수다.
- `judge_id == measure_id`이고 판정이 1 또는 2이면 그 스캔에 접수하고 전이한다. `(0, 0)`이 아닌 다른 쌍은 무시하고 기록에 거절 사유를 남긴다. 같은 쌍의 거절은 한 번만 기록한다.
- `measure_id`는 0으로 돌아가지 않으므로 `(0, 0)`과 겹치지 않는다. 진입 때 지우므로 ID가 순환해도 오래된 판정이 남지 않는다.
- PC는 읽은 상태가 5이고 `measure_id`가 마지막으로 판정한 ID와 다를 때만, 측정값을 복원해 판정을 한 번 쓴다.

**하트비트 감시**
- PLC는 스냅샷의 PC 하트비트가 직전 스냅샷과 달라진 마지막 스캔을 기억한다. `현재 스캔 − 마지막 변경 스캔 > heartbeat_scans`(10)이면 알람 21이다. 연결이 살아 있어도 값이 멈추면 같다.
- PC는 자기 주기 번호로 센다. PLC 하트비트가 `plc_stale_cycles`(20)보다 오래 바뀌지 않으면 기록에 `PLC 무응답`을 남기고 판정을 쓰지 않는다.

## 시연 실행
```powershell
py -m src.station recipes/plc_station.json --seed 42 --products 20 --scenario normal
```

**실행 규약**
- 서버는 `127.0.0.1`의 임시 포트에서 백그라운드 스레드로 소켓을 처리한다. 주소표 접근은 잠금으로 보호한다.
- 한 주기는 `모의 설비 갱신 → PLC 스캔 1회 → PC 주기 1회`다. PC 주기는 요청을 보내고 응답을 받을 때까지 기다린다. 다음 주기는 그 뒤에 시작하므로 결과가 실제 시각에 의존하지 않는다.
- PC는 응답을 다 받거나 소켓을 닫은 뒤에야 주기를 끝낸다. 쓰기는 응답 전에 적용되므로, PLC 스캔이 시작될 때 처리 중인 요청은 없다. 이것이 주기 경계다.
- EOF나 응답 검증 오류면 PC가 연결을 닫고 그 주기의 통신 실패를 기록한 뒤 주기는 진행한다. 재접속하지 않는다. 그래서 끊김 뒤에도 스캔이 돌고 알람 21이 난다.
- 소켓 응답 제한 시간은 1초다. 초과하면 늦은 쓰기가 다음 스캔의 앞뒤 어디에 적용될지 정할 수 없으므로, 결과를 믿을 수 없는 실행으로 보고 종료 코드 2로 멈춘다. 보고서는 쓰지 않는다.
- 기록은 메모리에 모으고, 실행이 끝까지 성공했을 때만 파일로 쓴다.
- PC 주기의 요청 순서는 하트비트 쓰기, 상태·값 읽기, 필요하면 판정 쓰기다.

**설정 `recipes/plc_station.json`**
```json
{
  "generator": "generator_measured.json",
  "inspection": "LEAK",
  "heartbeat_scans": 10,
  "plc_stale_cycles": 20,
  "timeouts": {"check_scans": 30, "clamp_scans": 20, "measure_scans": 50,
               "judge_scans": 30, "unclamp_scans": 20, "discharge_scans": 30},
  "delays": {"arrive": 2, "seat": 1, "clamp_close": 3, "measure": 5,
             "clamp_open": 3, "discharge": 2},
  "post_alarm_cycles": 20,
  "max_cycles": 5000
}
```
- `generator`는 설정 파일 폴더 기준 경로다. 파일이 없거나 측정 설정이 아니면 종료 코드 2다.
- 나머지 수치는 bool이 아닌 1 이상의 정수다. 없는 키, 허용 밖 키, 타입·범위 위반은 종료 코드 3이다. 중첩 객체도 같다.

**모의 설비**: 입력 초기값은 `clamp_open`, `guard_closed`가 참이고 나머지는 거짓이다. 설비는 직전 스캔의 출력과 자기 상태만 본다. 트리거가 참인 것을 처음 본 주기를 p라 하면 지연 N인 신호는 p+N 주기의 갱신에서 바뀐다. 트리거가 그 전에 거짓이 되면 예약을 취소한다. 설비 갱신이 끝난 뒤 주입을 덮어쓴다.

| 트리거 | 그 주기에 | 지연 뒤 |
| --- | --- | --- |
| 제품 없음, 남은 제품 있음 | | `arrive` 뒤 `part_present` 참 |
| `part_present` 참 | | `seat` 뒤 `seated`, `direction_ok` 참 |
| Q0 참 | `clamp_open` 거짓 | `clamp_close` 뒤 `clamp_closed` 참 |
| Q0 거짓, 클램프가 닫힘 또는 이동 중 | `clamp_closed` 거짓 | `clamp_open` 뒤 `clamp_open` 참 |
| Q1 참 | | `measure` 뒤 `measure_done` 참, 측정 원값 제공 |
| Q1 거짓 | `measure_done` 거짓, 측정 원값 비움 | |
| Q2 또는 Q3 참 | | `discharge` 뒤 `part_present`, `seated`, `direction_ok` 거짓, 다음 제품으로 |

**측정값**: 측정 설정의 시드로 `normal_events`를 만들어 LEAK 최초 측정 value를 순서대로 쓴다. 판정은 `judge_value`다.

**시나리오**: N번째 제품은 `처리 제품 수 + 1 = N`인 제품이다. PLC 스캔 직후 상태로, 표시된 제품이 표시된 상태에 처음 들어간 주기 c를 잡고 끝까지 유지한다. PC 쪽 주입은 c 주기의 PC 주기부터, 입력 주입은 c+1 주기의 설비 갱신부터 적용한다. 종료는 제품을 다 처리했거나, 알람 뒤 `post_alarm_cycles`가 지났을 때다. `max_cycles`를 넘으면 종료 코드 2다.

| 시나리오 | 주입 | 기대 |
| --- | --- | --- |
| `normal` | 없음 | 20개 처리, 알람 없음 |
| `seat_ng` | 5번째 제품 `CHECK`, `seated` 거짓 | 처리 4, 알람 11. 5번째 제품 도착부터 종료까지 Q0 켜진 적 없음 |
| `clamp_stuck` | 5번째 제품 `CLAMP`, `clamp_closed` 거짓 | 처리 4, 알람 12 |
| `judge_lost` | 5번째 제품 `WAIT_JUDGE`, PC가 판정을 안 씀, 하트비트 유지 | 처리 4, 알람 14. 5번째 제품 배출 없음 |
| `pc_silent` | 5번째 제품 `MEASURE`, PC 하트비트 정지, 연결 유지 | 처리 4, 알람 21. 5번째 제품 배출 없음 |
| `disconnect` | 5번째 제품 `MEASURE`, PC 소켓 닫음 | 처리 4, 알람 21. 5번째 제품 배출 없음 |
| `guard_open` | 5번째 제품 `MEASURE`, `guard_closed` 거짓 | 처리 4, 알람 22. 알람 스캔 출력부터 Q1 거짓 |
| `stale_judge` | 5번째 제품 `WAIT_JUDGE`, `judge_id = measure_id − 1`로 전송 | 처리 4, 거절 기록 1건, 알람 14 |

**기록**
- `reports/plc_station_<scenario>.csv`: 주기, 상태, 알람, 출력, 처리 수, 사건(`판정 접수`, `판정 거절: 사유` 등), 원문 value.
- `reports/plc_station_<scenario>_modbus.csv`: 주기, 순번, 방향, 기능, 16진수. PC 쪽에서 완성된 프레임 단위로 요청·응답 순서대로 적는다. 소켓 수신 조각은 기록 단위가 아니다. 서버 스레드는 기록을 쓰지 않는다. 트랜잭션 ID는 1부터라 결정적이다. 연결 종료는 방향 `close`로 한 줄 적는다.
- 실제 포트, 시각, 절대 경로는 쓰지 않는다.
- 터미널에 처리 수, OK·NG 수, 알람, 마지막 PC 하트비트 변경 스캔을 낸다.

## 사전 기대표 (초안)
T153–T158은 `src/plc.py`만 호출한다. 표기가 없는 입력은 정상 값이다. 정상 값은 모의 설비 초기값이고, PC 하트비트는 매 스캔 1씩 오른다.

| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T153 | 스캔 함수 안에서 입력 객체를 바꾸는 콜백 | 그 스캔은 스냅샷 값만 사용 |
| T154 | 스캔별 변화: 1 `part_present` 참 / 2 `seated`, `direction_ok` 참 / 3 `clamp_open` 거짓, `clamp_closed` 참 / 4 `measure_done` 참, 측정 원값 `10.250` / 5 `measure_done` 거짓 / 6 판정 쌍 `(1, 1)` / 7 `clamp_closed` 거짓, `clamp_open` 참 / 8 `part_present`, `seated`, `direction_ok` 거짓 | 스캔 1–8의 상태 번호 1, 2, 3, 4, 5, 6, 7, 0. 스캔마다 전이 1번. 스캔 5에 `measure_id` 1, 워드 `0000 280A`, 판정 레지스터 0. 스캔 8에 처리 수 1 |
| T155 | `CHECK` 진입 스캔을 s라 함. ① `seated` 거짓 유지 ② s+31 스캔에 `seated` 참 | ① s+30까지 `CHECK`, s+31에 알람 11 ② s+31에 `CLAMP` |
| T156 | 인터록 함수: ① Q0 이전 거짓, 요청 참, `seated` 거짓 ② Q0 이전 참, `seated` 거짓 ③ Q1 요청, `clamp_closed` 거짓 ④ Q1 요청, 닫힘·열림 둘 다 참 ⑤ Q2·Q3 동시 요청 ⑥ Q2 요청, `clamp_open` 거짓 ⑦ `ALARM`에서 Q2 요청 | ① Q0 거짓 ② Q0 참 ③④ Q1 거짓 ⑤ Q2·Q3 거짓 ⑥⑦ Q2 거짓 |
| T157 | ① 같은 스캔에 가드 열림·PC 하트비트 초과 ② 알람 12 뒤 가드 열림 ③ 닫힘·열림 동시 참 ④ `CLAMP`에서 `measure_done` 참 ⑤ `MEASURE`에서 `measure_done` 참, `clamp_closed` 거짓 ⑥ `PUBLISH` 변환 불가 값 | ① 22 ② 12 유지 ③ 24 ④⑤ 25, 측정값 미확정 ⑥ 23, `measure_id` 그대로 |
| T158 | `ALARM`, 코드 12. ① 클램프 닫힘에서 리셋 ② `manual_release` 상승 뒤 코일을 끄고 클램프 열림, 제품 있음, 리셋 ③ 제품 제거 뒤 `reset` 참 유지 ④ `reset` 거짓 뒤 참 | ①②③ `ALARM` 유지, ②는 래치로 Q0 거짓 유지 ④ `IDLE`. 판정·카운터 비움, `measure_id` 유지 |
| T159 | 프레임을 1바이트씩 수신, 프레임 2개 병합 수신, 미완성 뒤 EOF | 앞 둘은 요청 수만큼 처리, 셋째는 응답 없이 닫힘 |
| T160 | 프로토콜 ID 1, 길이 1, 길이 255, 값을 모두 담은 FC10 수량 124(길이 255), Unit ID 2 | 앞 넷은 연결 종료, 다섯째는 응답 없이 다음 요청 처리 |
| T161 | 예외: ① FC 0x07 ② FC03 주소 16 ③ FC03 주소 15 수량 2 ④ FC03 수량 0 ⑤ FC03 수량 126 ⑥ FC01 수량 2001 ⑦ FC10 주소 1 수량 124 바이트 수 248, 값 2바이트만(길이 9) ⑧ FC10 바이트 수 불일치 ⑨ FC05 값 `0x1234` ⑩ FC05 코일 0 ⑪ FC06 주소 1 ⑫ FC03 PDU가 3바이트 ⑬ FC10 주소 0 수량 123 전체 값 ⑭ FC10 주소 2 수량 1 ⑮ FC10 주소 0 수량 3 ⑯ FC05 코일 7 | ① 01 ②③ 02 ④⑤⑥⑦⑧⑨ 03 ⑩⑪ 02 ⑫ 03 ⑬⑭⑮⑯ 02. 쓰기 변경 없음 |
| T162 | 정상 응답: FC01 시작 0, 코일 0·2·9 참, 수량 10(미배정 5–7 포함) | 바이트 `05 02`, 바이트 수 2. FC05·06 에코, FC10 시작·수량 반환 |
| T163 | 클라이언트: 트랜잭션 ID 다름, 기능 다름, 바이트 수 틀림, 에코 다름 | 모두 오류 후 연결 닫음 |
| T164 | 측정값 변환: `10.250`, `-0.001`, `2147483.647`, `-2147483.648`, `2147483.648`, `-2147483.649`, `1.2300`, `1.2345` | `0000 280A`, `FFFF FFFF`, `7FFF FFFF`, `8000 0000`, 불가, 불가, 1230, 불가. 가능한 값은 왕복 일치 |
| T165 | ① `measure_id` 65535 다음 ② 이전 ID 판정 ③ 판정 값 3 ④ 같은 쌍 2스캔 유지 ⑤ FC06으로 판정 쓰기 ⑥ `WAIT_JUDGE` 진입 스캔 직후 쓴 정상 판정 | ① 1 ②③ 거절 ④ 거절 기록 1건 ⑤ 예외 02 ⑥ 지워지지 않고 다음 스캔에 접수 |
| T166 | ① 연결 유지, PC 하트비트가 마지막으로 바뀐 스캔을 s라 함 ② 시작 뒤 변경 없음 | ① s+10까지 정상, s+11에 알람 21 ② 스캔 10까지 정상, 스캔 11에 알람 21 |
| T167 | 시나리오 8개, 시드 42, 제품 20 | 표의 기대와 일치 |
| T168 | 시나리오 8개를 두 폴더에서 실행 | 기록 CSV 전체 바이트 동일 |
| T169 | `normal` | OK·NG 수가 같은 value의 `judge_value` 결과와 일치, 기록의 원문 value가 생성값과 같음 |
| T170 | 설정 오류: 음수 타임아웃, 없는 키, 허용 밖 키, 중첩 객체의 허용 밖 키, bool 값은 종료 3. 비측정 설정, 없는 시나리오, `max_cycles` 초과, 응답 없는 가짜 서버의 제한 시간 초과는 종료 2 | 표대로, 보고서 미생성 |
| T171 | 실행 뒤 기존 파일 | 기존 설정·보고서 바이트 불변, 전체 기존 테스트 통과 |

## 구현 순서
1. **10-1**: `src/plc.py`, T153–T158.
2. **10-2**: `src/modbus.py`, T159–T166.
3. **10-3**: `src/station.py`, 시나리오, T167–T171.

## 산출물
- `src/plc.py`, `src/modbus.py`, `src/station.py`, `recipes/plc_station.json`, 테스트 3개
- `reports/plc_station_<scenario>.csv`, `reports/plc_station_<scenario>_modbus.csv` 각 8개
- README 절, 표현 규칙 포함

## 사용자 확인
| 항목 | 초안 값 |
| --- | --- |
| 대상 | LEAK 스테이션 한 곳 |
| 타임아웃 | 위 표 |
| 지원 기능 코드 | 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x10 |
| 측정값 표현 | 부호 있는 32비트, 배율 1000 |
| 복귀 조건 | 가드 닫힘, PC 정상, 클램프 열림, 제품 제거 뒤 리셋 |
| 측정 신호 이상 | 알람 25 추가 |
| 응답 제한 시간 초과 | 실행 중단, 보고서 미생성 |

# v2 9단계 명세 (구현 완료, 2026-10-31 · 리뷰 016 지적 수정, 사용자 승인 전)

상태: **사용자 위임 확정** (2026-10-31). 결정 근거는 `handoff/decisions.md`. 1–8단계(아래 명세)는 완료이며, 그 동작과 테스트는 보존한다.

## 목표와 경계
- 합성 혼류 라인의 작업을 작업장에 배치하고, 택트타임·병목·양품 UPH를 계산하고, 검사기 대수별 조합을 사전 기준으로 비교한다.
- 시간과 치수는 모두 가상 가정이다. 실제 라인, 실제 설비 사양, SL 기준이 아니다. 레이아웃 도식은 CAD 도면이 아니다.
- 조합 비교는 **고정 경로·정지 시나리오에 조건부인 용량 비교**다. 설비 증설의 품질·신뢰성 효과를 평가하지 않는다.
- 제외: 무작위 작업 시간, 작업자 배치, 물류 대차, 투입 순서 최적화, CAD 출력, 판정기·생성기 변경.
- 판정기와 시뮬레이터는 별개다. `delay_rows`를 시간으로 쓰지 않는다.

## 보존 조건
- `src/rules.py`, 기존 테스트, 기존 설정, 샘플, 보고서는 수정하지 않는다.
- 새 코드는 `src/line.py`, 새 테스트는 `tests/test_line.py`, 새 설정은 `recipes/line_lamp.json`이다.

## 입력 `recipes/line_lamp.json`
허용 키 밖의 키는 오류다. 시간은 `^[0-9]+(\.[0-9]{1,3})?$` 문자열 초이고 내부에서 정수 밀리초로 바꾼다. 치수와 수량은 bool이 아닌 정수다.

| 키 | 값 | 규칙 |
| --- | --- | --- |
| `generator` | `generator_measured.json` | 측정 설정. 이 파일 기준 상대 경로 |
| `period_seconds` | `"28800.000"` | 양수 |
| `planned_stop_seconds` | `"3000.000"` | 0 이상, `period_seconds`보다 작음 |
| `demand_units` | 1300 | 기간 안의 양품 수요. 양의 정수 |
| `buffer_units` | 2 | 0 이상의 정수 |
| `repair_seconds` | `"600.000"` | 0 이상 |
| `elements` | 아래 표 | 1–12개 |
| `machines` | 아래 표 | 검사 요소마다 하나 |
| `manual_station` | `{"width_mm": 1200, "depth_mm": 1000}` | 양의 정수 |
| `floor` | 아래 값 | 양의 정수 |

`floor`: `length_mm` 20000, `width_mm` 7000, `aisle_mm` 1000, `pitch_mm` 300, `gap_mm` 200.

**작업 요소**: `id`, `step`, `seconds`(`A`, `B`), `predecessors`. `step`은 레시피의 공정 또는 검사 ID다. 모델 키는 레시피 모델과 정확히 같다.

| id | step | A | B | 선행 |
| --- | --- | ---: | ---: | --- |
| P1-1 | P1 | 9 | 9 | |
| P1-2 | P1 | 7 | 7 | P1-1 |
| P2-1 | P2 | 11 | 10 | P1-2 |
| P2-2 | P2 | 6 | 6 | P2-1 |
| P3-1 | P3 | 12 | 9 | P2-2 |
| P3-2 | P3 | 5 | 5 | P3-1 |
| LEAK | LEAK | 34 | 34 | P3-2 |
| P4-1 | P4 | 10 | 10 | LEAK |
| P4-2 | P4 | 8 | 6 | P4-1 |
| P5-1 | P5 | 9 | 0 | P4-2 |
| LIGHT | LIGHT | 18 | 18 | P5-1 |
| FINAL | FINAL | 15 | 0 | LIGHT |

**검사기**: 검사 시간은 `load + clamp + test + unload`다. 합이 그 검사 요소의 시간과 모델마다 같아야 한다. B의 FINAL처럼 시간이 0인 모델은 검사 대상이 아니다.

| 검사 | 후보 대수 | load | clamp | test | unload | `width_mm` | `depth_mm` | `service_mm` |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LEAK | 1, 2, 3 | 5 | 3 | 22 | 4 | 1500 | 1200 | 300 |
| LIGHT | 1, 2 | 3 | 2 | 11 | 2 | 1200 | 1000 | 300 |
| FINAL | 1, 2 | 3 | 2 | 8 | 2 | 1200 | 1000 | 300 |

`load`, `unload`는 수작업 또는 로더 구간이고, `clamp`, `test`는 자동 구간으로 표시한다. `service_mm`은 설비 뒤의 보전 공간이다.

검증 위반은 종료 코드 3이고 위치를 표시한다.
- 형식, 범위, 없는 키, 허용 밖 키, 모델 시간 키 누락.
- 요소 ID 중복, 없는 선행 요소, 순환, 요소 13개 이상.
- `step`이 측정 레시피에 없음. 레시피의 공정이나 검사인데 요소가 없음.
- 레시피에 있는 모델·공정인데 그 공정의 시간 합이 0. 레시피에 없는 모델·공정인데 시간이 0보다 큼.
- 공정 순서 위반: 모델의 앞 공정 요소가 뒤 공정 요소의 조상이 아님.
- 검사 순서 위반: 모델의 `inspections` 목록에서 앞선 검사가 뒤 검사의 조상이 아님.
- `after` 위반: 검사의 `after` 공정 요소가 검사 요소의 조상이 아님. `after`는 **최소 선행 조건**이다. 라인은 공유 검사장 하나를 두므로 B의 LEAK도 P3 뒤에서 한다. 판정기도 이 순서를 허용한다.
- 검사 요소의 `machines` 항목 없음, 후보 대수가 빈 목록이거나 오름차순 양의 정수가 아님, 구간 합 불일치.

## 정의
비교는 모두 정수·분수로 정확히 한다. 표시만 소수 넷째 자리 `ROUND_HALF_UP`이다.

```text
순가동 시간 = period_seconds − planned_stop_seconds
택트타임 = 순가동 시간 / demand_units
목표 양품 UPH = demand_units × 3600 / 순가동 시간
수작업 하한 = max(모델별 ceil(수작업 합 / 택트타임))
작업장 수 하한 = 수작업 하한 + 검사 요소 수
```

- 부하가 택트 안에 드는 조건은 `부하_ms × demand_units ≤ 순가동_ms`다.
- 기본값의 택트타임은 19.8462초, 목표 양품 UPH는 181.3953이다.
- 계획 정지는 택트타임에서 한 번, 수리는 시뮬레이션에서 한 번, 재검사는 검사기 점유에서 한 번, 수율은 양품 집계에서 한 번만 반영한다.
- 모델 비율은 측정 설정의 `model_weights`를 합으로 나눈 분수다.

## 작업 배치
- 검사 요소는 자기 작업장을 혼자 쓴다. 수작업 요소는 작업장으로 묶는다.
- 작업장은 직선 순서다. 어떤 요소도 선행 요소보다 앞 작업장에 있으면 안 되고, 같은 작업장 안에서는 선행 관계를 지킨다.
- **제약**: 수작업 작업장은 모든 모델에서 부하가 택트 안에 든다. 혼류 평균으로 판정하지 않는다.
- **목적함수 키**: `(수작업 작업장 수, 유휴 제곱합, 배치 키)`의 사전순 최소. 유휴 제곱합은 수작업 작업장과 모델마다 `비율 × (택트 − 부하)²`의 합이다. 배치 키는 작업장별 요소 ID 튜플의 튜플이다. 요소는 입력 순서로 적는다.
- **전수 탐색**: 위 키로 모든 실현 가능 배치의 최적을 찾는다. 부분집합 동적 계획을 쓴다.
- **휴리스틱**: RPW다. 요소의 가중치는 자기와 모든 후행 요소의 모델 비율 가중 시간 합이다. 현재 작업장에 넣을 수 있는 요소(선행 완료, 모든 모델에서 택트 안, 검사 요소 아님) 중 가중치가 가장 큰 요소를 넣는다. 동률이면 입력 순서가 앞선 요소다. 넣을 요소가 없으면 작업장을 닫는다. 다음 요소가 검사 요소뿐이면 그 검사가 자기 작업장을 차지한다.
- 보고서는 작업장 수 하한, 휴리스틱 결과, 전수 탐색 최적값을 구분하고 `gap = 휴리스틱 작업장 수 − 최적 작업장 수`를 쓴다.
- 어떤 요소가 택트를 넘으면 `배치 불가`로 표시하고 조합 비교를 하지 않은 채 종료 코드 0으로 끝낸다.
- 조합 비교의 라인은 전수 탐색 최적 배치다.

## 제품 경로
측정 설정을 시드마다 `Generator(...).normal_events(products)`로 생성해 분석한다. 실행 순서는 개발 시드로 배치·선택을 확정한 뒤 홀드아웃을 쓴다.

제품 경로는 다음을 갖는다.
- `model`
- `attempts`: 검사별 허용된 측정 수
- `completed`: 판정 상태가 완료인가
- `defective`: 생성기의 합성 결함 표식
- `end_inspection`: 완료가 아니면 마지막으로 측정한 검사, 측정이 없으면 빈칸
- `stops`: 이 제품의 최초 측정이 설비 정지를 일으킨 검사의 집합

**양품은 `completed`이고 `defective`가 아닌 제품이다.** 검사합격은 `completed` 전체다. 결함 유출은 `completed`이고 `defective`인 제품이다.

경로와 정지는 설비 3·2·2대 기준으로 생성한 외생 입력이다. 대수를 바꿔도 다시 생성하지 않는다. 그래서 후보들의 양품 수는 같고 종료 시각만 다르다. 생성기 설정의 수리 지연과 재검사 설비 변경은 이 비교에 쓰지 않는다. 라인의 B는 LEAK 앞에 P3를 하므로 LEAK에서 끝난 B는 생성 경로보다 P3 작업을 한 번 더 한다. 보고서 고지에 이 가정들을 적는다.

## 가상 시계
정수 밀리초의 사건 기반 시뮬레이션이다. 무작위 값은 쓰지 않는다. 시뮬레이터의 입력은 작업장 목록, 제품 경로, `buffer_units`, 수리 시간이다.

**이동 대상**: 제품의 다음 대상은 현재 뒤의 작업장 중 그 제품이 실제로 일할 첫 작업장이다. 시간 합이 0인 작업장과 시도가 없는 검사장은 지나친다. `end_inspection` 검사가 끝나면 대상은 라인 밖이다.

**작업장**: 서버 수는 수작업 1, 검사는 조합의 대수다. 서버 선택은 번호가 작은 빈 서버다. 각 작업장의 입력 버퍼는 `buffer_units`개이고 FIFO다. 첫 작업장은 버퍼를 쓰지 않는다.

**서비스 시간**: 수작업은 그 모델의 부하다. 검사는 `시도 횟수 × 검사 시간`이다. 재검사는 같은 검사기를 이어서 점유한다.

**같은 시각의 처리**: 사건 시각마다 다음을 변화가 없을 때까지 반복한다.
1. 작업장을 뒤에서 앞으로, 서버 번호 순으로 본다. 작업이 끝난 제품을 대상으로 보낸다. 대상이 라인 밖이면 나간다. 대상 작업장의 버퍼가 비어 있고 빈 서버가 있으면 서비스를 시작한다. 그렇지 않고 버퍼에 자리가 있으면 버퍼 끝에 넣는다. 둘 다 아니면 서버를 점유한 채 막힌다. 막힌 제품이 건너뛴 작업장은 쓰지 않는다.
2. 작업장을 뒤에서 앞으로 본다. 버퍼 앞 제품부터 빈 서버에 넣는다.
3. 투입 대기 맨 앞 제품을 첫 작업장의 빈 서버에 넣는다. 제품 번호 순이다. 앞 제품을 앞지르지 않는다.

**정지**: `stops`에 그 검사가 있는 제품이 서버를 떠나는 순간 그 서버가 `repair_seconds` 동안 멈춘다. 수리 인원 제약은 없다. 여러 서버가 동시에 수리될 수 있다. 수리가 끝나면 빈 서버다.

**종료**: 마지막 제품이 라인을 떠난 시각이 종료 시각이다. 첫 제품은 0에 투입된다. 시간 지표는 `[0, 종료 시각]`과 겹치는 구간만 센다. 종료 뒤 수리는 빼고, 남은 제품이 있는데 다음 사건이 없으면 `교착`으로 종료 코드 2다.

| 출력 | 정의 |
| --- | --- |
| `pass_uph` | 검사합격 수 × 3600 / 종료 시각 |
| `good_uph` | 양품 수 × 3600 / 종료 시각 |
| `escaped` | 결함 유출 수 |
| `utilization` | 작업장의 작업 시간 합 / (서버 수 × 종료 시각) |
| `blocked_share` | 작업장의 막힌 시간 합 / (서버 수 × 종료 시각) |
| `repair_share` | 작업장의 수리 시간 합 / (서버 수 × 종료 시각) |
| `mean_wait_seconds` | 버퍼 대기 시간 합 / 라인을 지나간 제품 수 |
| `bottleneck` | `utilization`이 가장 큰 작업장, 동률이면 앞 작업장 |

시드 합산은 시간과 건수의 합을 더해 비로 계산한다. 작업장 지표도 `총 작업 시간 / (서버 수 × 총 종료 시각)`이고, `bottleneck`은 합산 값으로 정한다.

## 설비 사양 검토
```text
visits(I) = I의 전체 시도 수 / 투입 제품 수       (개발 시드)
양품률 = 양품 수 / 투입 제품 수                   (개발 시드)
명목 사이클타임 상한 = 택트타임 × 대수 / visits(I)
양품 보정 상한 = 택트타임 × 대수 × 양품률 / visits(I)
허용 test 시간 = 상한 − (load + clamp + unload)
```

- `visits`가 0이면 상한 칸은 `대상 없음`이다.
- `가상 검사 시간 ≤ 명목 상한`이면 `손실 미반영 명목 조건 충족`이다. `≤ 양품 보정 상한`이면 `양품 보정 조건 충족`이다.
- 수리 손실은 이 표에 넣지 않는다. 시뮬레이션의 `good_uph`가 보여 준다. 표의 보정을 시뮬레이션에 다시 곱하지 않는다.
- 사양 비교표 열: 검사, 대수, 명목 상한, 양품 보정 상한, 양품 보정 허용 test 시간, 가상 검사 시간, 자동 구간 초, 충족 표시, 점유 면적.
- **점유 면적** = 대수 × `width_mm` × (`depth_mm` + `service_mm`)이다.

## 조합 비교 (사전 선택 기준)
후보는 LEAK·LIGHT·FINAL 대수의 조합 12개다.

**기준 (결과 전 고정)**
1. 개발 시드의 합산 `good_uph` ≥ 목표 양품 UPH
2. 모든 수작업 작업장이 택트 안에 있음
3. 레이아웃이 바닥 제약을 만족함

비교는 반올림 전 값으로 한다. 선택은 기준을 모두 만족한 조합 중 점유 면적 합이 가장 작은 조합이다. 동률이면 총 대수가 적은 조합, 그다음 `(leak, light, final)` 사전순이다. 없으면 `기준 충족 조합 없음`이며 기준을 완화하지 않는다.

홀드아웃은 개발 선택만 확인한다. 선택 조합의 합산 `good_uph`가 목표 이상이면 `확인`, 아니면 `미달`이다. 다시 고르지 않는다. 선택이 없으면 `검증할 선택 없음`이다.

## 레이아웃 도식
`reports/line_lamp_layout.svg`로 낸다. 선택 조합이 없으면 면적 합이 가장 작은 조합을 그리고 제목에 `기준 미달 조합`이라고 적는다. 좌표와 제약 계산은 같은 함수의 값을 쓴다.

- 왼쪽 투입, 오른쪽 배출의 직선 배치다.
- 수작업 작업장 외형은 `width_mm × depth_mm`이다.
- 검사장 외형 폭은 `width_mm`, 깊이는 `대수 × (depth_mm + service_mm) + (대수 − 1) × gap_mm`이다. 검사기는 y 방향으로 쌓는다.
- 버퍼 칸 길이는 `buffer_units × pitch_mm`이고, 작업장 사이마다 한 칸이다. `buffer_units`가 0이면 칸 길이도 0이다.
- **라인 길이** = 작업장 폭 합 + 버퍼 칸 길이 합이다. `floor.length_mm` 이하여야 한다.
- **라인 폭** = 가장 깊은 작업장 깊이 + `aisle_mm × 2`다. `floor.width_mm` 이하여야 한다.
- 기본값에서 라인 길이는 14,100mm다. LEAK 대수별 라인 폭은 1대 3,500mm, 2대 5,200mm, 3대 6,900mm다.
- 그림에 작업장 ID·요소·대수, 폭·깊이 치수, 버퍼, 보전 공간, 투입·배출, 통로, 제품 동선 화살표, 합성 고지 문구를 넣는다.
- 바닥 제약을 넘으면 기준 3 미달이고 그림 제목에도 표시한다. SVG는 같은 입력에서 바이트까지 같다.

## 실행과 보고서
```powershell
py -m src.line recipes/line_lamp.json --seeds 0-29 --holdout-seeds 1000-1029 --products 500
```

- 두 시드 옵션은 필수다. 두 범위가 겹치면 종료 코드 2다. 위 범위가 제출 실행의 값이다.
- `reports/line_lamp_balance.csv`, `reports/line_lamp_compare.csv`, `reports/line_lamp_layout.svg`를 쓴다. 이름은 입력 파일 stem에서 얻는다.
- 입력 오류는 종료 코드 3, 인자·파일·교착은 종료 코드 2다. 측정 설정이 아니면 종료 코드 2다.
- 같은 입력은 전체 산출물이 바이트까지 같다.

`balance.csv` 열: `section,key,station,elements,model,load_seconds,idle_seconds,value,text`

| `section` | 내용 |
| --- | --- |
| `notice` | 기존 가정 문장, `시간과 치수는 가상이며 실제 설비 사양이 아니다.`, 경로 가정 문장 |
| `summary` | 순가동 시간, 택트타임, 목표 UPH, 수작업 하한, 작업장 수 하한, 휴리스틱 작업장 수, 최적 작업장 수, `gap`, 수작업 밸런스율 |
| `heuristic`, `optimal` | 작업장·모델별 부하와 유휴 |
| `visit` | 검사별 `visits`, 양품률 |
| `spec` | 사양 비교표. `key`는 `검사:대수`, 값은 `text`에 `열=값;` 형식으로 입력 순서대로 적는다 |

**수작업 밸런스율** = 모델 비율 가중 수작업 시간 합 / (수작업 작업장 수 × 택트타임)이다.

`compare.csv` 열: `section,combo,leak,light,final,area_mm2,seeds,products,station,pass_uph,good_uph,escaped,utilization,blocked_share,repair_share,mean_wait_seconds,bottleneck,meets_uph,meets_takt,meets_floor,reject_reason,selected,value`

| `section` | 내용 |
| --- | --- |
| `notice` | 조건부 비교 문장과 고지 |
| `development` | 조합마다 1행. `selected`는 이 절에만 있고 값이 `선택`인 행은 많아야 1개다 |
| `station` | 조합·작업장마다 1행. 개발 시드 합산. 배치가 불가하면 없고 그때는 SVG도 쓰지 않는다 |
| `holdout` | 선택 조합 1행. 없으면 없음 |
| `selection` | 선택 결과 1행 |

`reject_reason`은 기준 미달 항목을 `uph;takt;floor` 순으로 적는다. 이상 처리량은 조합 밖 정보로 `text`에 싣지 않는다.

## 사전 기대표
T136–T143의 시뮬레이션은 경로를 직접 준다. 제품은 별도 표기가 없으면 완료·정상이고, 작업장은 서버 1개다.

| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T130 | 기본 입력의 정의 | 순가동 25800초, 택트타임 19.8462, 목표 UPH 181.3953, 수작업 하한 4, 작업장 수 하한 7 |
| T131 | 기본 입력의 최적 배치 | 수작업 작업장 5개, 전체 8개. A 부하 `16,17,17,10,17`, B 부하 `16,16,14,10,6`, 유휴 제곱합 82551/338 |
| T132 | 요소 시간 `4,4,3,3,3,3`, 선행 없음, 단일 모델, 택트 10 | 최적 2개, 휴리스틱 3개, `gap` 1. 둘 다 제약을 지킴 |
| T133 | 혼류 작업장: 부하 A 25, B 10, 비율 0.5, 택트 21.5. 비정수 택트: 부하 19.846초와 19.847초, 택트 25800/1300 | 평균 17.5여도 위반. 19.846은 허용, 19.847은 위반 |
| T134 | 입력 오류: ① 순환 ② 없는 선행 ③ 없는 `step` ④ 레시피 공정 누락 ⑤ A의 P5 시간 0 ⑥ B의 P5 시간 양수 ⑦ `after` 위반 ⑧ LIGHT·FINAL 순서 위반 ⑨ 후보 대수 내림차순 ⑩ 후보 빈 목록 ⑪ 음수 시간 ⑫ 소수 넷째 자리 ⑬ `planned_stop >= period` ⑭ 요소 13개 ⑮ 모델 시간 키 누락 ⑯ `buffer_units` 음수 ⑰ `buffer_units` 소수 ⑱ 구간 합 불일치 ⑲ 허용 밖 키 | 모두 종료 코드 3, 위치 표시, 보고서 미생성 |
| T135 | 인자 오류: 비측정 설정, 잘못된 시드, 제품 0, 겹치는 시드 범위 | 모두 종료 코드 2, 보고서 미생성 |
| T136 | 작업장 2개, 시간 10·20, 버퍼 0, 제품 3개 | 종료 시각 70초. S1 막힘 20초. S2 `utilization` 0.8571, `good_uph` 154.2857 |
| T137 | 같은 라인, 버퍼 1 | 종료 시각 70초, S1 막힘 0초 |
| T138 | 검사 1대 10초, 제품 3개, 시도 `1,2,1` | 서비스 10·20·10초, 종료 시각 40초, 양품 3개, `good_uph` 270.0000 |
| T139 | 검사 1대 10초, 제품 2개, 첫 제품 `stops`, 수리 100초. 별도 사례: 제품 1개, `stops` | 첫 사례는 둘째가 110초에 시작, 종료 120초, `repair_share` 0.8333. 별도 사례는 종료 10초, `repair_share` 0 |
| T140 | 검사 2대 10초, 제품 3개, 수리 100초. ① 정지 없음 ② 첫 제품만 `stops` ③ 첫째·둘째 `stops` | ① 종료 20초 ② 종료 20초, 셋째는 서버 2 ③ 종료 120초 |
| T141 | B 제품 3개. S1 1초, S2 B 시간 0, S3 10초, 버퍼 0 | 둘째는 S1에서 막힘, S2를 쓰지 않음. 종료 시각 31초 |
| T142 | 끝 검사가 LEAK인 제품, 뒤에 작업장 2개 | LEAK 서비스 뒤 나가고, 뒤 작업장 작업 시간 0, 양품 0, 검사합격 0 |
| T143 | 결함품이 완료된 경로 1개, 정상 완료 1개, 작업장 1개 10초 | `pass_uph` 180.0000, `good_uph` 90.0000, `escaped` 1 |
| T144 | `visits`: LEAK 시도 합 110, 제품 100, 택트 21.5, 대수 2, 양품률 0.8, 검사 34초, 고정 구간 12초 | 명목 상한 39.0909, 양품 보정 상한 31.2727, 양품 보정 허용 test 19.2727. 명목 충족, 양품 보정 미충족 |
| T145 | 시도 합 0 | 상한 `대상 없음`, 오류 없음 |
| T146 | 실행 전체를 두 폴더에서 반복, 시드 0–0, 1000–1000, 제품 50 | 세 산출물 바이트 동일 |
| T147 | 기본 입력의 CLI, 시드 0–0, 1000–1000, 제품 50 | `development` 12행, `station` 96행, `selected=선택` 최대 1행, `selection` 1행 |
| T148 | 선택 함수. 후보 `(면적, 총 대수, 조합)`: ① `(10,4,(2,1,1))` 통과, `(12,3,(1,1,1))` 통과 ② `(10,5,(2,2,1))`, `(10,4,(2,1,1))` 통과 ③ `(10,4,(2,1,1))`, `(10,4,(1,2,1))` 통과 ④ 전부 미달 | ① `(2,1,1)` ② `(2,1,1)` ③ `(1,2,1)` ④ `기준 충족 조합 없음` |
| T149 | 홀드아웃 함수: 선택 UPH 181.3953 미만, 이상, 선택 없음 | `미달`, `확인`, `검증할 선택 없음`. 다른 조합을 고르지 않음 |
| T150 | 레이아웃 함수: 기본 입력, 조합 `(1,1,1)`, `(2,1,1)`, `(3,1,1)` | 라인 길이 14100, 라인 폭 3500, 5200, 6900. 바닥 폭 6000이면 `(3,1,1)`만 `meets_floor=False`. 점유 면적 합 `(2,1,1)`은 7,620,000mm² |
| T151 | SVG | XML로 파싱됨. 작업장 8개의 `<rect>`, 투입·배출·보전·치수·고지 문구 포함. 치수 숫자가 레이아웃 함수 값과 같음. 바닥 초과 입력이면 제목에 표시 |
| T152 | 실행 뒤 판정기·생성기 산출물 | 기존 설정과 보고서 바이트 불변, 전체 기존 테스트 통과 |

## 구현 순서
1. **9-1**: 입력 검증, 정의, 배치, T130–T135, T144, T145.
2. **9-2**: 가상 시계, T136–T143.
3. **9-3**: 경로 추출, 조합 비교, 선택, SVG, 보고서, T146–T152.

## 산출물
- `src/line.py`, `tests/test_line.py`, `recipes/line_lamp.json`
- `reports/line_lamp_balance.csv`, `reports/line_lamp_compare.csv`, `reports/line_lamp_layout.svg`
- README 「라인 밸런싱과 레이아웃 도식 (v2 9단계)」 절. 표현 규칙과 한계 포함

## 완료 보고 (반드시 포함)
- 실행 명령과 출력 원문, 전체 테스트 결과, T130–T152 기대·실제 대조
- 조합 12개 표와 선택·홀드아웃 결과, 해석의 한계
- 명세와 다르게 구현한 부분, 또는 "명세 이견" 항목

## 위임 확정 값
| 항목 | 값 | 비고 |
| --- | --- | --- |
| 수요·시간 | 1300대, 28800초, 계획 정지 3000초 | 합성 가정 |
| 작업 요소·치수·구간 시간 | 위 표 | 합성 가정. 결과를 본 뒤 바꾸지 않음 |
| 수리 시간 | 600초 | 합성 가정 |
| 버퍼 | 2 | 합성 가정 |
| 선택 기준 | 위 기준 3개, 면적 최소 | 결과를 본 뒤 바꾸지 않음 |

# v2 8단계 명세 (구현 완료, 2026-10-31 · 리뷰 015 지적 수정, 사용자 승인 전)

상태: **사용자 위임 확정** (2026-10-31). 결정 근거는 `handoff/decisions.md`. 1–7a단계(아래 명세)는 완료이며, 그 동작과 테스트는 보존한다.

## 목표와 경계
- 합성 램프 공정의 고장 모드를 PFMEA 형식으로 정리하고, 현재 관리와 조치를 판정 규칙·테스트·평가 수치에 연결한다.
- 조치마다 목적·사전 성공 기준·관측 결과·잔여 위험을 묶어 보여 주고, 재검사 조건 대안을 같은 시드로 비교한다.
- **연습이다.** 실제 공정, 실제 고객 영향, 실무 PFMEA 경험이 아니다. 기존 고정 문장을 유지하고 모든 보고서에 연습임을 표시한다.
- 프로그램은 심각도·발생도·검출도를 추정하지 않는다. 합성 수치는 참고 관측치이고 점수 환산표가 아니다. 제출 표의 점수 칸은 비운다.
- 제외: 실제 라인 데이터, AIAG/VDA AP 표, DFMEA, 관리계획서, 측정 시스템 분석.

## 보존 조건
- `src/rules.py`, 기존 테스트, 기존 설정, 샘플, 보고서는 수정하지 않는다. 판정기·생성기 동작은 바꾸지 않는다.
- 새 코드는 `src/pfmea.py`, 새 테스트는 `tests/test_pfmea.py`다.

## 입력 표 `data/pfmea_lamp.csv`
UTF-8 BOM CSV다. 값을 다듬지 않는다. 열은 정확히 다음 순서다.

`id,failure_type,process_step,function_requirement,failure_mode,effect,cause,prevention_control,detection_control,severity,occurrence,detection,evidence,evidence_note,action,action_owner,action_state,action_goal,control_before,control_after,success_reference,success_op,success_value,action_evidence,residual_risk,post_severity,post_occurrence,post_detection`

| 열 | 규칙 |
| --- | --- |
| `id` | `PF-` + 두 자리 숫자, 중복 불가, 행은 `id` 오름차순 |
| `failure_type` | `product`(제품 불량), `equipment`(설비 이상), `record`(데이터 기록 오류) |
| `process_step` | 측정 레시피의 공정 또는 검사 ID, 또는 `ALL` |
| `function_requirement`, `failure_mode`, `effect`, `cause` | 공백만 있으면 안 됨 |
| `prevention_control`, `detection_control` | 공백 불가. 없으면 `없음` |
| `severity`, `occurrence`, `detection` | `^(10\|[1-9])$`. 셋 다 있거나 셋 다 빈칸 |
| `evidence` | **현재 관리**의 근거 참조. `;`로 구분. 빈칸 가능 |
| `evidence_note` | `evidence`가 있으면 필수. 이 근거가 이 고장 모드와 왜 관련되는지 쓴다 |

조치 열의 허용 조합은 다음과 같다. 표 밖 조합은 오류다.

| `action_state` | `action`, `action_owner`, `action_goal` | `control_before`, `control_after` | `success_*` 3열 | `action_evidence` | `residual_risk` | `post_*` 3열 |
| --- | --- | --- | --- | --- | --- | --- |
| 빈칸 (조치 없음) | 빈칸 | 빈칸 | 빈칸 | 빈칸 | 빈칸 | 빈칸 |
| `계획` | 필수 | 빈칸 | 셋 다 있거나 셋 다 빈칸 | 빈칸 | 빈칸 | 빈칸 |
| `완료` | 필수 | 필수 | 빈칸 | 필수 | 빈칸 | 빈칸 |
| `효과 확인` | 필수 | 필수 | 필수 | 필수 | 필수 | 셋 다 있거나 셋 다 빈칸 |

- `control_before`, `control_after`는 조치 전후 점수가 평가하는 관리 상태다. 버전이나 T 번호를 적는다.
- `success_reference`는 `metric:` 또는 `report:` 참조 1개다. `success_op`는 `>=` 또는 `<=`다. `success_value`는 `^-?[0-9]+(\.[0-9]+)?$`이다.
- `post_*` 점수는 조치 전 점수가 있어야 쓸 수 있다.
- 오류는 모두 종료 코드 3이고 `행번호.열이름` 위치를 표시하며 보고서를 만들지 않는다. 행번호는 헤더 다음 행을 1로 센다.

## 근거 참조
형식은 `종류:값`이다. 참조 앞뒤 공백, 빈 조각, 같은 칸의 중복 참조는 오류다. 없는 대상도 오류다. 모두 종료 코드 3이다.

| 종류 | 값 | 확인 방법 | 관측 대상 |
| --- | --- | --- | --- |
| `rule` | `RULE_SEQ` 등 | 규칙 ID 목록과 `RULE_RETEST`, `RULE_EQUIP` | `record` |
| `reason` | `SEQ_SKIP` 등 | `REASON_CODES` | `record` |
| `test` | `tests/파일.py::클래스::메서드` | `ast`로 파일을 읽어 메서드 존재 확인. 실행하지 않음. 구문 오류도 위반 | `record` |
| `metric` | 지표 ID | 이번 실행에서 계산 | 지표의 대상 |
| `report` | `eval_lot_dev_containment:since_restart:capture_rate` | 아래 보고서 규칙 | `product` |

**보고서 근거**: `reports/<파일>.csv`에서 `section=method`이고 해당 `method`인 행이 정확히 하나여야 한다. 열은 `capture_rate`, `mean_quarantine`, `precision`, `mean_residual`만 허용한다. 값이 빈칸이면 값 없음이고, 소수 형식이 아니면 오류다. 생성기 버전, 시드, 제품 수, 설정 SHA-256은 그 보고서의 `section=provenance`에서 읽고, 없으면 오류다. 같은 보고서의 `section=selection` 값이 있으면 `text`에 함께 싣는다.

**근거 판정**은 현재 관리의 `evidence`만 본다. `action_evidence`는 존재 확인만 한다.

| `evidence_status` | 조건 |
| --- | --- |
| `근거 없음` | 참조가 0개 |
| `근거 부족` | 행의 `failure_type`과 관측 대상이 같은 참조가 없음 |
| `값 없음` | 대상이 맞는 참조가 있으나 `metric`·`report`뿐이고 값이 모두 없음 |
| `연결됨` | 그 밖 |

- `product`·`equipment` 행에는 `rule`, `reason`, `test`의 관측 대상이 맞지 않는다. 입력 오류 거절 테스트는 데이터 기록 오류의 근거일 뿐이기 때문이다.
- `record` 행에 제품 지표만 있으면 `근거 부족`이다.
- `연결됨`은 참조가 이어졌다는 뜻이고, 관리 효과가 검증됐다는 뜻이 아니다. 보고서에 이 문장을 고정한다.

## 지표
측정 설정을 시드마다 `Generator(seed, config, models, book).normal_events(products)`로 생성해 정상 행만 `build_analysis`로 분석한다. `build_rows`는 쓰지 않으므로 오류 주입 후보 부족이 지표를 막지 않는다. 판정 결과는 실제 판정 경로에서 얻고, 결함 표식은 지표 계산에만 쓴다.

합산은 실행별 원시 분자·분모를 더한다. 제품은 `(시드, product_id)`로 구분한다. 분모가 0이면 값 없음이다.

| ID | 대상 | 범위 | 분자 | 분모 |
| --- | --- | --- | --- | --- |
| `defect_escape` | product | 전체 흐름, 실행 끝 상태 | 완료 상태 결함품 | 결함품 |
| `all_defect_first_fail` | product | 모든 검사 | 결함품의 허용된 최초 측정 중 FAIL | 결함품의 허용된 최초 측정 |
| `leak_defect_first_fail` | product | LEAK | 결함품의 LEAK 최초 측정 중 FAIL | 결함품의 LEAK 최초 측정 |
| `leak_defect_retest_pass` | product | LEAK | LEAK 재검사가 있고 최종 LEAK 결과가 PASS인 결함품 | LEAK 재검사가 있는 결함품 |
| `normal_reject` | product | 전체 흐름, 실행 끝 상태 | 보류·폐기 상태 정상품 | 정상품 |
| `fault_stop_run` | equipment | 고장 설비 | 1회 이상 정지한 (실행, 고장 설비) 쌍 | (실행, 고장 설비) 쌍 |
| `fault_no_stop_run` | equipment | 고장 설비 | 정지하지 않은 쌍 | (실행, 고장 설비) 쌍 |
| `fault_stop_delay` | equipment | 고장 설비, 첫 정지까지 | 정지한 쌍의 첫 정지까지 최초 측정 수 합 | 정지한 쌍 |
| `normal_stop_rate` | equipment | 고장 키에 없는 모든 설비, 실행 전체 | 정지 횟수 | 허용된 최초 측정 수 |

- 고장 설비는 `fault_shift_sigma`의 키다. 0대면 `fault_*` 지표의 분모가 0이라 값이 없다. 여러 대면 쌍 단위로 세며, `fault_detail` 절에 설비별 정지 쌍·전체 쌍을 낸다.
- `fault_stop_delay`는 시간이나 비율이 아니라 **검출된 쌍의 평균 최초 측정 건수**다. 미검출 쌍은 빠지므로 `fault_no_stop_run`과 함께 읽는다. `fault_stop_delay`는 소수 넷째 자리 값으로, 나머지도 소수 넷째 자리 `ROUND_HALF_UP`으로 표시한다.
- 고장 설비의 측정은 수리 뒤 포함 `normal_stop_rate`에 어떤 경우에도 넣지 않는다. `NO_FAULT` 재가동을 거친 정상 설비의 측정은 넣는다.
- 제품 지표는 실행 전체다. 고장·수리와 무관하게 모든 제품과 측정을 쓴다.
- `defect_escape`, `all_defect_first_fail`, `normal_reject`, `normal_stop_rate`는 행별 보고서에 `전체 흐름 참고값`으로 표시한다.
- 고정 문장: `최초 FAIL률은 원인 발생률이 아니고, 설비 정지율은 제품 불량 검출률이 아니다.`

## 대안 비교
PF-05의 조치 근거다. 측정 설정에서 `retest_probability`만 바꾼 세 조건을 같은 시드 범위로 실행해 지표를 나란히 낸다.

| 조건 | `retest_probability` |
| --- | --- |
| `current` | 설정값 (0.70) |
| `half` | 0.35 |
| `none` | 0.00 |

- `section=alternative` 행에 조건별 `defect_escape`, `leak_defect_retest_pass`, `normal_reject`, `all_defect_first_fail`을 분자·분모·값으로 낸다.
- 난수 흐름이 달라지므로 같은 제품의 짝지은 비교가 아니다. 합산 비교만 뜻한다. 프로그램은 대안을 고르지 않는다.
- `current`의 값은 `metric` 절의 값과 같아야 한다.

## 효과 판정과 점수
`효과 확인` 행은 `success_reference`의 값을 사전 기준과 비교한다.

| `effect_result` | 조건 |
| --- | --- |
| `충족` | 값이 기준을 만족 |
| `미충족` | 값이 기준을 만족하지 않음 |
| `값 없음` | 값이 없음 |

- 기준 비교는 소수 넷째 자리로 표시한 값이 아니라 `Decimal` 계산값으로 한다. `metric`은 분자/분모, `report`는 보고서 문자열이다.
- 이것은 현재 관리의 성능 확인이다. 다른 가정의 이전 단계와 비교한 개선 전후 수치가 아니다. 보고서에 이 문장을 고정한다.
- 미충족이어도 프로그램 오류가 아니다. 기준을 바꾸지 않고 그대로 보고한다.

S·O·D는 1–10 정수이고 프로젝트 자체 기준 `docs/pfmea_scale.md`를 쓴다. AIAG/VDA 평가표나 AP가 아니다.

- `rpn = S × O × D`, `post_rpn`도 같다. RPN으로 합격을 판정하지 않는다.
- `severity >= 9`이면 `priority=우선`이다. 빈칸은 저위험이 아니라 `S≥9 표시 대상 아님`이다.
- 조치 전후 점수가 모두 있으면 `rpn_change = post_rpn − rpn`을 표시한다. 차이만큼 위험이 줄었다는 뜻은 아니다. 조치 전후 관리 상태는 `control_before`, `control_after`로 읽는다.
- 점수가 없으면 `score_status=점수 대기`, 있으면 `점수 입력`이다.

`docs/pfmea_scale.md`는 다음을 정한다.
- S는 가정한 영향, O는 원인과 예방 관리, D는 검출 대상·시점·관리의 유효성을 기준으로 삼는다.
- 각 점수를 1–2, 3–4, 5–6, 7–8, 9–10 다섯 구간으로 문장 설명한다.
- 합성 수치는 참고 관측치이며 점수로 환산하지 않는다. 고장을 처음부터 넣은 실행의 정지율은 O가 아니고, 최초 FAIL률의 여집합은 곧바로 D가 아니다.

## 실행과 보고서
```powershell
py -m src.pfmea data/pfmea_lamp.csv --config recipes/generator_measured.json --seeds 0-29 --products 500
```

- `reports/pfmea_lamp_report.csv`, `reports/pfmea_lamp_report.md`를 쓴다. 이름은 입력 파일 stem에서 얻는다.
- 같은 입력은 바이트까지 같다. 실행 시각을 쓰지 않는다.
- 측정 설정이 아니면 종료 코드 2다. `--seeds` 형식은 `src.evaluate`와 같다. 제품 수는 1 이상이다. 파일 오류도 종료 코드 2다. 입력 표 오류는 종료 코드 3이다. 규칙은 표 검증을 지표 계산보다 먼저 한다.

CSV 열은 `section`, 입력 표의 모든 열, 그리고 다음 열이다.

`score_status,rpn,post_rpn,priority,rpn_change,evidence_status,effect_result,reference,condition,target,scope,numerator,denominator,value,generator_version,config_sha256,recipe_sha256,equipment_sha256,seeds,products,assumption,text`

| `section` | 내용 |
| --- | --- |
| `notice` | 고정 문장 4개: 합성 연습, 기존 가정, 지표 해석, `연결됨`·효과 판정의 의미 |
| `item` | 표의 행마다 1행. 입력 열 전부와 계산 열 |
| `evidence` | 행과 현재 관리 참조마다 1행 |
| `action` | `효과 확인` 행마다 1행. `reference`, 관측값, 기준, `effect_result` |
| `metric` | 지표마다 1행. 분자·분모·값·범위·출처 SHA 3개·시드·제품 수 |
| `fault_detail` | 고장 설비마다 1행 |
| `alternative` | 조건·지표마다 1행 |
| `coverage` | `failure_type`별 행 수와 `evidence_status`별 건수 |

- `metric` 참조의 `assumption`은 `7a 측정 설정`이다.
- `report` 참조의 `assumption`은 `이전 단계 가정, 7a 결과 아님`이다. 분자·분모는 빈칸이고 출처는 그 보고서의 provenance다.
- Markdown 보고서는 첫 줄에 연습임을 적고, 행마다 기능 → 고장 모드 → 영향 → 원인 → 현재 관리 → 근거 → 조치 → 사전 기준과 결과 → 잔여 위험을 적은 뒤, 지표 표와 대안 표를 싣는다. 값이 없는 칸은 `-`다.

## 제출 표의 내용
`data/pfmea_lamp.csv`는 6행이다. 점수와 `post_*`는 빈칸이다. `effect`와 `cause`는 합성 공정의 가정이며 실제 불량 사례가 아니다.

| ID | 유형 | 대상 | 기능 | 고장 모드 | 현재 관리 근거 | 조치와 사전 기준 |
| --- | --- | --- | --- | --- | --- | --- |
| PF-01 | product | LEAK | LEAK 검사가 기밀 규격 초과 제품을 걸러 낸다 | 결함품이 LEAK에서 PASS | `leak_defect_first_fail`, `defect_escape` | 측정값 판정, `효과 확인`, `leak_defect_first_fail >= 0.80` |
| PF-02 | equipment | LEAK | LEAK 설비가 치우침 없이 측정한다 | 측정 평균이 위로 이동 | `fault_stop_run`, `fault_no_stop_run`, `fault_stop_delay`, `normal_stop_rate` | 재가동 기록, `효과 확인`, `fault_stop_run >= 0.95` |
| PF-03 | record | ALL | 공정 순서대로 기록한다 | 앞 공정 누락 입력 | `rule:RULE_SEQ`, `reason:SEQ_SKIP`, 테스트 | 없음 |
| PF-04 | record | ALL | 모델의 레시피 공정만 기록한다 | 다른 모델의 공정 입력 | `reason:RECIPE_UNKNOWN_STEP`, 테스트 | 없음 |
| PF-05 | product | LEAK | 재검사가 결함품을 다시 걸러 낸다 | 결함품이 재검사에서 PASS | `leak_defect_retest_pass`, `normal_reject` | 재검사 조건 대안 비교, `완료`, 근거는 대안 테스트 |
| PF-06 | product | ALL | 정지 뒤 의심 제품 **후보 목록**을 만든다 | 유출품이 후보 목록에서 누락 | `report:eval_lot_dev_containment:since_restart:capture_rate` | 격리 후보 보고서, `효과 확인`, `report:...:capture_rate >= 0.90` |

- 사전 기준은 표에 적은 값이고 결과를 본 뒤 바꾸지 않는다. 0.95와 0.90은 5·6단계의 선택 기준을 그대로 쓴 값이고, 0.80은 가정한 결함품 FAIL 확률 약 84%에서 정한 값이다.
- PF-06은 후보 목록 보고서다. 자동 격리가 아니고 제품 상태를 바꾸지 않는다. 6단계 가정의 값이다.

## 사전 기대표
공통 초기 상태 F: 측정 레시피, 재가동 설비. 모든 제품은 B 모델로 등록하고 P1·P2까지 마친다. 입력은 CSV 행을 `build_analysis`에 넣어 실제 판정 경로로 만든다. 행의 조치 열은 표기가 없으면 빈칸이다.

- a(결함): LEAK-1 값 14 → 요청 → LEAK-1 값 10 → P3 → P4 → LIGHT-1 값 10
- b(결함): LEAK-2 값 14
- c(정상): LEAK-3 값 10 → P3 → P4 → LIGHT-1 값 10
- d(정상): LEAK-3 값 14

| ID | 입력 | 기대 결과 |
| --- | --- | --- |
| T113 | 제출 표, 시드 0–1, 제품 50 | 종료 0, 두 보고서 생성. 6개 행 모두 `점수 대기`, RPN 빈칸 |
| T114 | 같은 입력을 두 폴더에서 실행 | CSV·Markdown 전체 바이트 동일 |
| T115 | F의 제품 지표 | `defect_escape` 1/2, `all_defect_first_fail` 2/3, `leak_defect_first_fail` 2/2, `leak_defect_retest_pass` 1/1, `normal_reject` 1/2 |
| T116 | 고장 설비 LEAK-2. 실행 ①: 서로 다른 제품의 최초 검사로 LEAK-2 값 `10,14,14`, LEAK-1 값 `14,14`. 실행 ②: LEAK-2 값 `10`, LEAK-1 값 `10`. 나머지 설비 측정 없음 | `fault_stop_run` 1/2, `fault_no_stop_run` 1/2, `fault_stop_delay` 3/1, `normal_stop_rate` 1/3 |
| T117 | 분모 0: 결함품·재검사 없는 실행, 고장 설비 0대 | 결함·`fault_*` 지표 값 없음, 오류 없음 |
| T118 | 고장 LEAK-2. 다른 제품으로 값 `14,14` 정지 → `FIXED` → 값 `14,14` 정지. LEAK-1은 다른 제품으로 값 `14,14` 정지 → `NO_FAULT` → 값 `10` | `fault_stop_delay` 2/1, `normal_stop_rate` 1/3. LEAK-2의 측정·정지는 분자·분모에 없음, LEAK-1의 재가동 뒤 측정은 있음 |
| T119 | 합산: 실행별 `1/1`, `0/9` | 합산 `1/10`, 값 0.1000. 같은 `GEN_0001`이 두 실행에 있어도 각각 센다 |
| T120 | 고장 설비 2대: 실행 1개에서 한 대만 정지 | `fault_stop_run` 1/2, `fault_no_stop_run` 1/2, `fault_detail` 2행, 두 지표 분자 합이 분모와 같음 |
| T121 | 표 오류: ① 열 순서 ② 중복 id ③ `id` 형식 ④ `id` 역순 ⑤ `failure_type` ⑥ 없는 `process_step` ⑦ `severity`만 입력 ⑧ `11` ⑨ `01` ⑩ 공백만 있는 `effect` ⑪ `evidence_note` 없음 ⑫ 조치 없이 담당 입력 ⑬ `계획`에 `action_evidence` ⑭ `완료`에 근거 없음 ⑮ `효과 확인`에 `success_value` 없음 ⑯ `효과 확인`에 `residual_risk` 없음 ⑰ `계획`에 `post_severity` ⑱ 조치 전 점수 없이 `post_*` ⑲ `success_op`가 `>` ⑳ `success_reference`가 `test:` | 모두 종료 코드 3, 위치 표시, 보고서 미생성 |
| T122 | 근거 오류: ① 없는 규칙 ② 없는 사유 코드 ③ 없는 테스트 파일 ④ 없는 메서드 ⑤ 없는 지표 ⑥ 없는 보고서 ⑦ 없는 방식 ⑧ 허용 밖 열 ⑨ 알 수 없는 종류 ⑩ 빈 조각 ⑪ 앞뒤 공백 ⑫ 중복 참조 ⑬ 비수치 보고서 값 ⑭ 같은 방식 행 2개 ⑮ provenance 없는 보고서 ⑯ 구문 오류 테스트 파일 | 모두 종료 코드 3, 위치 표시, 보고서 미생성 |
| T123 | `evidence_status`: ① 근거 빈칸 ② `product` + `test`만 ③ `product` + `metric:fault_stop_run` ④ `equipment` + `metric:fault_stop_run` ⑤ `record` + `reason:SEQ_SKIP` ⑥ `product` + 분모 0 지표뿐 ⑦ `record` + `metric:defect_escape`뿐 ⑧ `evidence` 빈칸 + `action_evidence` 있음 | ① `근거 없음` ②③ `근거 부족` ④⑤ `연결됨` ⑥ `값 없음` ⑦ `근거 부족` ⑧ `근거 없음` |
| T124 | 점수: S 8, O 3, D 4, 조치 후 S 8, O 2, D 4, `효과 확인`. 다른 행: S 9, O 1, D 1 | `rpn` 96, `post_rpn` 64, `rpn_change` −32, `priority` 빈칸, `점수 입력`. 다른 행은 `rpn` 9, `priority` `우선` |
| T125 | `report:eval_lot_dev_containment:since_restart:capture_rate`, `>= 0.90` | 값 0.8525, 생성기 버전 `1.3.0`, 시드 `0-99`, `effect_result` `미충족`, 분자·분모 빈칸, `selection` 문구가 `text`에 있음 |
| T126 | `metric` 기준: 값 2/3과 `>= 0.6667`, `<= 0.6667`, 분모 0 | `미충족`, `충족`, `값 없음` (표시값이 아니라 계산값으로 비교) |
| T127 | 비측정 설정, 잘못된 시드, 제품 0, 없는 입력 파일 | 모두 종료 코드 2, 보고서 미생성 |
| T128 | 대안 비교, 시드 0–1, 제품 50 | 조건 3개·지표 4개 12행. `current`가 `metric` 값과 같음. `none`의 `leak_defect_retest_pass` 값 없음 |
| T129 | 제출 표 + 시드 0–29, 제품 500 | 6개 행 모두 `연결됨`, 점수 칸 빈칸, `notice` 4행, `metric` 9행, 생성기 버전 `1.4.0`, `action` 3행, 고정 문장이 CSV와 Markdown에 있고 `AIAG/VDA`를 평가 방식으로 표시하지 않음. 입력 표와 기존 보고서 바이트 불변 |

## 구현 순서
1. **8-1**: 입력 표 검증, 근거 해석, 점수, T121–T124, T127.
2. **8-2**: 지표, 효과 판정, 대안 비교, T115–T120, T125, T126, T128.
3. **8-3**: 보고서, 제출 표, 기준표 문서, T113, T114, T129.

각각 커밋하고 뒤에 검수 루프를 한 번 돌린다.

## 산출물
- `src/pfmea.py`, `tests/test_pfmea.py`, `data/pfmea_lamp.csv`, `docs/pfmea_scale.md`
- `reports/pfmea_lamp_report.csv`, `reports/pfmea_lamp_report.md`
- README 「합성 공정 PFMEA 연습 (v2 8단계)」 절, 표현 규칙 포함

## 완료 보고 (반드시 포함)
- 실행 명령과 출력 원문, 전체 테스트 결과, T113–T129 기대·실제 대조
- 지표 9개와 대안 3조건의 분자·분모·값, 효과 판정 결과, 해석의 한계
- 명세와 다르게 구현한 부분, 또는 "명세 이견" 항목

## 사용자 몫
- S·O·D 점수 입력. 점수를 넣으면 보고서를 다시 실행한다. 점수가 없어도 프로그램은 완료 상태다.
- `effect`와 `cause` 문장을 자기 말로 고치기. 면접에서 설명할 수 있어야 한다.

# v2 7a단계 명세 (구현 완료, 2026-10-31 · 리뷰 014 지적 수정, 사용자 승인 전)

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
