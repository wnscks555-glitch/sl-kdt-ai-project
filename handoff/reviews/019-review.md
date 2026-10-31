검수 모델: gpt-6-astra

# 리뷰 019 — 제출 전 7a·8·9·10·11단계 최종 검수

검수일: 2026-10-31. 대상 HEAD: `77bb902702aed85b8d69223a5014fffde389c9e3`.

**판정 FIX. 신규 미해결 높음 3건·중간 1건, 수정 요구 4건이다. 리뷰 014–018의 기존 높음·중간 18건은 해당 지적 범위에서 해결됐다.** 이전 R16-H4의 입력 변환 수정은 유효하지만, 그 뒤 보고서 표시 경로에서 별도의 수치 예외가 확인됐다. 낮음은 수정 요구에 포함하지 않았다.

전체 테스트는 `py` 런처 실패 후 지정 Python 3.12로 직접 실행했다. 360개 실행에서 내부 `py` 호출에 의한 실패 항목 132개가 발생했다. 기존 파일을 수정하지 않고 이 호출만 현재 인터프리터로 연결한 보조 실행은 **360개 모두 통과**했다. 직접 실행과 보조 실행을 같은 결과로 표시하지 않는다. 새 반례는 **20개 메서드 중 16개 통과, 4개 메서드 실패(서브테스트 포함 실패 항목 5개)**다.

## 미해결 지적

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| R19-H1 | 높음 | `src/anomaly.py:198`, `src/station.py:118` | 같은 수치의 측정 규격을 문자열 표기 차이 때문에 서로 다른 규격으로 판정한다. | P03은 A의 `7.000/13.000`을 보존하고 B만 `7/13`으로 쓴다. 공통 `load_setup`·레시피 검증은 정상 허용하지만 10단계 `load_values`와 11단계 `load_process`는 모두 “모든 모델에서 같은 양측 규격이어야 함”으로 거절한다. 두 함수가 원문 문자열 튜플을 사전 키로 쓰기 때문이다. 7a는 Decimal 수치 동등성을 사용하며 `tests/test_measurement.py:280`도 다른 표기를 명시적으로 허용한다. 10·11단계가 공유 측정 설정에 공개되지 않은 추가 제한을 붙여, 지원하는 설정의 허용/거절 판정이 단계에 따라 달라진다. | 규격 동등성은 공통 레시피의 Decimal 의미를 재사용하고 원문 보존은 별도로 유지한다. 표기가 다른 동등 규격을 생성기→스테이션→이상 검출로 연결하는 검증을 추가한다. |
| R19-H2 | 높음 | `src/modbus.py:306`, `src/modbus.py:323`, `src/modbus.py:333` | 응답 1초 제한이 완성 응답의 마감 시간이 아니라 개별 `recv`의 무수신 시간으로만 적용된다. | `tasks.md:386`은 응답 제한 초과 시 실행 중단·종료 2·보고서 미생성을 정한다. P11은 정상 FC03 응답 11바이트를 0.15초마다 1바이트씩 보내며, 각 조각 간격은 1초보다 짧다. 응답 전체가 **1.656초** 걸려도 예외 없이 `[7]`을 받는다. `_receive`가 반복 수신할 때 요청 시작 이후 경과 시간을 차감하지 않는다. T170의 완전 무응답 시험만으로 이 경계를 검증하지 못한다. | 요청별 절대 마감 시각을 두고 남은 시간만 수신에 사용한다. 분할 응답이 제한 전에 완성되는 경우와 제한 뒤 완성되는 경우를 검증하고, 후자는 `ModbusTimeout`→실행 중단으로 연결한다. 명세를 무수신 제한으로 바꾸려면 현재의 응답 제한과 다른 계약임을 명세 이견으로 먼저 공개한다. |
| R19-H3 | 높음 | `src/line.py:627`, `src/line.py:633`, `src/line.py:801` | 명세상 허용한 긴 시간 문자열은 정확히 파싱된 뒤 보고서 출력에서 처리되지 않은 예외로 종료된다. | P07은 기본 설정의 `period_seconds`만 `123456789012345678901234567890.123`으로 바꾸고 개발 0·홀드아웃 1000·제품 1개로 실행한다. 이 문자열은 `tasks.md:503`의 문법·범위를 만족하며 자릿수 상한도 없다. `_seconds`는 정확한 정수로 고쳐졌지만 `show`의 Decimal 나눗셈·넷째 자리 양자화는 기본 28자리 문맥을 사용한다. 실제 `net_seconds` 출력에서 `decimal.InvalidOperation`, traceback, 종료 1이다. 명세가 허용한 입력의 정확한 수치 보고 경로가 끊긴다. | 입력으로 허용한 자릿수를 보고 단계까지 수용하는 정밀도 또는 정수·분수 기반 반올림을 사용한다. 파서 단독 검사에 더해 긴 값의 전체 CLI·CSV 표시를 검증한다. 새 상한을 정한다면 묵시적 반올림이나 traceback 대신 명세와 위치 포함 입력 오류에 반영한다. |
| R19-M1 | 중간 | `src/plc.py:163` | 같은 판정 거절 쌍이 다른 쌍을 사이에 두고 다시 오면 중복 기록된다. | `tasks.md:368`은 같은 쌍의 거절을 한 번만 기록한다고 정한다. P09는 동일한 WAIT_JUDGE에서 `(2,1)→(1,3)→(2,1)→(0,0)→(1,3)`을 입력한다. 서로 다른 거절 쌍은 2개지만 실제 거절 사건은 4개다. `self.rejected`가 직전 쌍 하나만 보관한다. T165④의 “같은 쌍 2스캔 유지”만 통과하며 비연속 중복은 걸러내지 못한다. 유효 판정의 상태 전이나 인터록 우회는 확인되지 않았고, 보고 기록 계약의 불일치이므로 중간이다. | 한 측정의 판정 대기 구간에서 이미 기록한 쌍을 기억하고 새 측정 공개 시 비운다. 연속·비연속 중복, `(0,0)` 사이의 반복, 그 뒤 정상 판정 접수를 함께 검증한다. |

H1은 기존에 유효한 측정 설정의 거절, H2는 명시한 시간 초과 처리의 우회, H3은 허용 입력의 정확한 보고 계약 위반을 근거로 높음이다. 기본 제출 설정에서 재현되지 않는다는 사실이나 수정 비용·일정으로 심각도를 낮추지 않았다. M1은 잘못된 판정 접수나 제품 상태 변경이 아니라 기록 불일치다.

## 리뷰 014–018 항목별 재판정

코드·회귀 테스트를 확인하고 전체 보조 테스트를 실행했다. 아래에서 P 번호는 이번 `test_probe_019.py`를 가리킨다. 이전 리뷰의 통과 선언만으로 해결을 승계하지 않았다.

| 이전 항목 | 심각도 | 현재 판정 | 현재 근거 |
| --- | --- | --- | --- |
| 014 H1 | 높음 | 해결 | `generate.check_measured_config`가 합성 분포의 OverflowError를 값 오류로 변환한다. P04의 `10**308` 이동량 합은 traceback 없이 종료 2, 파일 없음. |
| 014 H2 | 높음 | 해결 | `confirm_value`가 양자화 전 자릿수를 검사한다. P04의 Cpk `1e-307`은 종료 2·파일 없음. 극소수·음수·반올림 경계도 확인했다. |
| 014 M1 | 중간 | 해결 | T108이 사례별 독립 경로와 정상 기반 설정을 사용하고 각 오류 문구를 단정한다. 해당 테스트를 포함한 360개 보조 실행 통과. |
| 015 H3 | 높음 | 해결 | `_report_reference`가 헤더 존재와 행의 None 셀을 구분한다. P05의 짧은 행은 거절하고 실제 빈 셀은 허용. 기존 열 누락 회귀도 통과. |
| 015 M2 | 중간 | 해결 | `build_markdown`이 현재 근거·조치 근거·관측값을 표시한다. 제출 Markdown에서 PF-03/04 참조, PF-05 조치 근거, PF-06 0.8525를 확인했고 회귀도 통과. |
| 016 H1 | 높음 | 해결 | `read_line_file`의 구조·generator 검사와 `load_line`의 step 문자열 검사가 경로/집합 연산보다 먼저다. T134 구조 오류 회귀 통과. |
| 016 H2 | 높음 | 해결 | `machine_order`가 LEAK/LIGHT/FINAL 순서를 고정하고 선택 키·조합 표기에 사용한다. 키 순서 회귀 통과. |
| 016 H3 | 높음 | 해결 | `product_routes`가 제품 등록 순서를 보존한다. 10001개 제품의 번호 순서 회귀 통과. |
| 016 H4 | 높음 | 해결(원 지적 범위) | `_seconds`는 문자열 분해와 정수 연산으로 정확히 변환하며 기존 긴 값 회귀 통과. 이번 P07의 실패는 뒤의 **표시 경로**이고 R19-H3으로 별도 보고한다. |
| 016 M1 | 중간 | 해결 | 중복 predecessors를 위치 포함 입력 오류로 거절한다. 중복 선행 회귀 통과. |
| 016 M2 | 중간 | 해결 | `run`이 실제 작성 경로만 반환한다. 배치 불가 분기의 두 CSV 안내 회귀 통과. |
| 017 H1 | 높음 | 해결 | `_recover`가 공개 워드 3·4도 지운다. P08은 거절된 리셋→수동 해제→새 리셋에서 ID 유지·워드/판정 비움·PC 코일 보존 확인. |
| 017 H2 | 높음 | 해결 | `FrameBuffer`가 손상 전 완성 프레임을 돌려주고 서버가 처리 후 닫는다. P10의 모든 분할 경계에서 앞선 FC06/FC16만 적용, 뒤 손상 이후 쓰기 없음. 실제 서버 분할 회귀도 통과. |
| 017 M1 | 중간 | 해결(해석 수용) | `load_values`가 제품 번호를 정수로 정렬한다. 실제 10001제품 회귀 통과. decisions의 제품 번호 순서 해석은 9단계와도 일관되고 기존 20제품 출력은 유지된다. |
| 018 H1 | 높음 | 해결 | `_number`가 큰 정수를 float로 변환하지 않고 한계와 비교한다. P14의 네 수치 키 `10**400`은 위치 포함 종료 3·traceback/보고서 없음. |
| 018 H2 | 높음 | 해결 | `rule_outcomes`는 생성 설비 설정과 무관한 상수 3·2를 사용한다. P14의 FAIL 위치 9·10은 t=10 경보. 수정된 5:3 설비 조합 회귀도 통과. |
| 018 M1 | 중간 | 해결(공식 우선 해석 수용) | decisions에 공식 우선 해석이 공개됐고 구현도 일치한다. P14가 onset−6·−5·−1 경계를 확인했다. 명세 본문의 남은 요약 문장은 아래 낮음으로 기록한다. |
| 018 M2 | 중간 | 해결 | 새 T177이 실제 CLI를 두 번 실행해 검증 분할 변경이 평가 결과에 반영되는 동시에 mean/scale/weight/bias/windows가 불변임을 확인한다. 보조 전체 실행에서 통과. P13은 별도로 홀드아웃 변경이 선택·임계값·학습을 바꾸지 않음을 확인했다. |

Claude의 위 수정 설명은 반례와 현재 코드가 뒷받침하는 범위에서 수용한다. “사용자 PC에서 테스트 통과”는 이번 결과의 근거로 대신 쓰지 않았다.

## 사전 기준·분리·명세 이견

- 지정 범위 `git log bb73241..HEAD`, `git diff bb73241..HEAD`의 코드·테스트·설정·보고서·README·handoff 기록을 대조했다. 명세 확정 커밋은 순서대로 `314a909`, `4daa65a`, `3616dad`, `7e9f623`, `4f3f153`이며 각 구현보다 앞선다. tasks.md는 이 다섯 확정 커밋에서만 바뀌었다. `4f3f153..HEAD`의 tasks.md diff는 없다. 확인한 저장소 이력에서는 **결과를 본 뒤 기준을 완화한 흔적이 없다**. 커밋 밖에서 언제 어떤 실험을 봤는지까지 입증하는 주장은 하지 않는다.
- PF-01/02/06의 0.80/0.95/0.90, 라인의 개발 양품 UPH·택트·바닥→면적/총 대수/조합 순 선택, 이상 검출의 오탐 2·전체 0.90·이동량 0.70→지연 비용 순 선택이 코드와 제출물에서 유지된다. PF-02·PF-06 미달, 로지스틱 수렴 미달도 숨기지 않는다.
- `anomaly.run`은 train만 `fit_model`에 넣는다. 표준화·가중치에 validation/holdout이 들어가는 경로는 발견하지 못했다. 임계값은 validation의 양자화 점수로 고르고, 방법 선택도 validation 지표만 사용한다. holdout 지표를 계산하는 코드가 선택 호출보다 앞에 있지만 선택 입력에 섞이지 않으며 P13에서 실제 변경을 통해 확인했다.
- 라인은 holdout 경로를 미리 생성하지만 `compare`의 선택에는 dev_routes만 사용한다. 선택 후 한 조합만 holdout에서 확인하며 다시 고르지 않는다. 미리 읽는 실행 순서와 선택 자료로 쓰는 것은 구분했다.
- T143은 기대표의 180/90이 산술 오류라는 Claude 해석에 동의한다. 10초×2제품=20초, 검사합격 2×3600/20=360, 양품 1×3600/20=180이다. 기대표를 고치지 않았다. 수리·재검사·수율·계획 정지의 중복 반영도 찾지 못했다.
- **낮음 L1 / `handoff/tasks.md:156` / 문제:** “조기 경보면 경보 행 하나”는 여전히 너무 넓은 문장이다. **근거:** decisions의 공식 우선 해석과 달리 onset−1은 5행이다(P14). **제안:** 추후 설명을 onset−5 이하/이전 경계에 맞춰 정리한다. 이 리뷰는 사용자가 기준으로 지정한 decisions의 해석을 수용하므로 별도의 미해결 중간으로 중복 계상하지 않는다. 사용자 최종 승인 여부를 검수자가 바꾼 것은 아니다.

## 독립 계산과 문서 대조

| 대상 | 독립 확인 | 결과 |
| --- | --- | --- |
| Cpk·Ppk | P02는 3구간·나머지 포함 264값을 51부분군으로 직접 계산. P17은 제출 CSV의 허용 최초 측정·재가동을 따로 묶고 100자리 Decimal로 재계산 | 7개 설비의 n·부분군 일치, 표시 대상 5개 설비의 Cpk·Ppk 모두 일치. 재검사·거절 행 제외 및 미완성군의 Ppk 포함 확인 |
| PFMEA | P19는 시드 0–29의 원시 사건·최종 상태·합성 결함 표식을 별도로 집계 | `defect_escape` 16/307, `all_defect_first_fail` 350/398, `leak_defect_first_fail` 273/307, 재검사 통과 49/192, 정상 손실 47/14693, 정지 28/30, 미정지 2/30, 지연 1751/28, 정상 정지 20/32205 모두 일치 |
| 효과 기준 | P05는 2/3과 소수 28자리 기준을 직접 Fraction 비교. 제출 PF-06은 6단계 문자열 값 0.8525를 사용 | 반올림 전 비교와 `미충족` 일치. 1.3.0 외부 보고서와 1.4.0 측정 지표를 구분 |
| 라인 양품 UPH | P06은 버퍼 0·2서버·동시 수리·유출 결합의 종료 시각을 손계산. P20은 선택 조합의 경로별 양품/합격/유출과 총 종료 시각으로 비율 계산 | 개발 양품 14646, 합격 14662, 유출 16, 288432000ms → 182.8008. 홀드아웃 양품 14663, 합격 14680, 유출 17, 284292000ms → 185.6781. 서버별 작업+막힘+수리 시간이 관측 시간 이내 |
| 이상 검출 노출·지연 | P12는 첫 판단 시점·조기·동시·미검출 조합 손계산. P16은 제출 계수로 점수를 다시 만들고 첫 경보·노출·비용·정책 직접 집계 | 아래 원시 집계와 보고서 6행·정책 3행 일치 |
| 보고서 재생 확률 | P15는 window_values·ewma_prev·model.csv로 특징/표준화/z/p 직접 계산 | 35행, 최대 확률 차이 `5.39814859479e-11`(십진 10자리 출력 오차 범위) |

| 분할·방법 | 검출/고장 120 | 지연 비용 합 | 정상 경보/노출 |
| --- | ---: | ---: | ---: |
| 검증 3:2 | 47 | 17943 | 36/62914 |
| 검증 이동평균 | 118 | 2988 | 12/67614 |
| 검증 로지스틱 | 120 | 1774 | 4/68838 |
| 홀드아웃 3:2 | 45 | 18008 | 38/63450 |
| 홀드아웃 이동평균 | 113 | 4207 | 22/66568 |
| 홀드아웃 로지스틱 | 119 | 1734 | 5/69272 |

README 7a의 설비별 표, 8단계 지표·조치·대안 표, 9단계 12조합 표와 선택·홀드아웃, 10단계 8시나리오, 11단계 6방법행·정책·수렴 문장을 제출 보고서와 대조했다. 이 표들에서 수치 불일치는 찾지 못했다. 7a의 491/6/3 및 결함 6개 설명도 제품 보고서·meta와 부합한다. “합성”, “가상”, “소프트웨어 모의”, “실무/실제 설비/CAD/예지보전 아님”이 각 절에 명시돼 있다. README에 공고의 기술 요건이나 SL 실제 공정 사실을 추가로 단정한 문장은 발견하지 못했다. 채용 공고 원문과 실제 장비 동작을 검증한 것은 아니다.

## 이번 반례

원본 코드·tests·설정은 수정하지 않았다. P01–P14 중 최소 8개 이상은 기대표에 없는 경계·순서 조합이다. 파일 출력은 전부 tempfile 아래에만 한다.

| 반례 | 입력 | 예상·명세 근거 | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | a/A 두 제품 FAIL→정지→a 재검사 요청→빈 값·소문자 설비·정지 설비·공백 값→정상 다른 설비 | 거절 상태 불변, 요청 보존, 정상 재검사만 PASS, 설비 최초 창 제외 | 모두 일치 | 통과 |
| P02 | 129·4·131값의 세 구간, 불완전군과 평균 차이 | 구간별 완성군 51, 전체 n264, Cpk/Ppk 서로 다른 모집합 | 직접 산식과 동일 | 통과 |
| P03 | 같은 규격 A 7.000/13.000, B 7/13 | 공통 측정 설정의 수치 동등성 유지 | 생성 설정 허용, station/anomaly 둘 다 거절 | 실패 → H1 |
| P04 | 정수 이동 10**308 합, Cpk 1e-307, 음수·극소수·양자화 경계 | 거대 분포/문자열 종료2·미생성, HALF_UP 보존 | 일치 | 통과 |
| P05 | provenance 있는 보고서의 짧은 행과 실제 빈 셀, 2/3 긴 기준 | 부재 거절·빈칸 허용·정확한 효과 판정 | 일치 | 통과 |
| P06 | 수작업 1초→검사 2대 10초, 버퍼0, 앞2제품 수리100초, 결함 통과1개 | 종료122초, 양품3/합격4/유출1, 검사작업40초·수리200서버초 | 일치 | 통과 |
| P07 | 30자리 정수부 시간으로 전체 라인 CLI | 허용 문법·정확한 계산·보고 | Decimal 예외·종료1 | 실패 → H3 |
| P08 | 유효 판정과 가드 열림 동시→불가능 리셋→수동 해제→새 리셋 | 가드 우선·게이트OFF, 워드/판정 비움·ID/PC코일 보존 | 일치 | 통과 |
| P09 | 거절쌍 A→B→A→빈쌍→B | 동일 측정 대기에서 2개 쌍 각1회 | 4개 거절 사건 | 실패 → M1 |
| P10 | FC06·FC16 뒤 손상·후속 정상 요청, 모든 바이트 분할, 잘못된 FC16 | 앞2개만 처리, 손상뒤 미처리, 거절 부분쓰기 없음 | 일치 | 통과 |
| P11 | 1초 제한, 정상 응답을 0.15초 간격 분할 | 완성 응답 마감 초과 예외 | 1.656초에 정상 반환 | 실패 → H2 |
| P12 | 판단시점4, 정상/고장6/8, 경보4/5/6/10/없음 | 노출21·오탐2·비용12·의심14 | 일치 | 통과 |
| P13 | 학습·검증 유지, 홀드아웃 시드200대→600대 | 홀드아웃 지표만 바뀌고 선택·임계값·학습 유지 | 일치 | 통과 |
| P14 | 큰 정수 4키, 초반 FAIL 뒤 경보시점, onset−6/−5/−1 | 종료3·3:2고정·공식 재생 범위 | 일치 | 통과 |
| P15 | 제출 model/replay의 원 측정·이전 EWMA | 직접 확률 재계산 일치 | 최대오차 5.40e-11 | 통과 |
| P16 | 검증·홀드아웃 480시나리오·3방법 독립 집계 | 보고서 노출·지연·검출·정책 일치 | 6행·정책3행 일치 | 통과 |
| P17 | 제출 측정 CSV를 최초/재가동 구간으로 독립 분해 | 설비별 능력 통계와 보고 일치 | 7설비 일치 | 통과 |
| P18 | bb73241 보호 파일 git blob | 기존 테스트·설정·data·reports·rules 보존 | 96개 동일(기존 보고서42개 포함) | 통과 |
| P19 | PFMEA 개발30시드 원시 사건 별도 집계 | 실행별 비율 평균이 아닌 분자/분모 합산 | 9지표 일치 | 통과 |
| P20 | 라인 선택조합 개발30·홀드아웃30시드 | 경로 양품 수/총 종료시간, 시간 중복 없음 | 182.8008/185.6781 일치 | 통과 |

초기 검수 반례의 P01은 장비 창 필드명을 `window`로 잘못 참조했고 `recent_results`로 바로잡았다. 초기 P03은 원본과 같은 표기를 넣어 변화를 만들지 못해 B를 `7/13`으로 수정했다. 이 두 검수 코드 오류는 제품 결함으로 세지 않았다. 마지막 실행의 실패 5항목은 위 네 지적과 정확히 대응한다.

## 실행·보존 기록

`handoff/setup-notes.md`를 먼저 읽었고 tasks·decisions·gpt-log의 7a–11 및 014–018 수정 기록을 확인했다. `docs/`의 옛 명세를 기준으로 사용하지 않았다. `practical-work-operation`은 조율·보존에만 적용했다. 사용자 지시대로 플러그인 리뷰 스킬과 보조 에이전트는 사용하지 않았다.

`git diff --check bb73241..HEAD -- src tests recipes README.md`는 출력 없이 종료 0. 전체 범위 diff-check는 과거 loop-logs의 공백 경고로 종료 1이며 제품 코드 결함으로 계상하지 않았다. 시작부터 있던 `handoff/loop-logs/019-codex.txt`는 검수 루프 소유 파일로 건드리지 않았다. 이번 검수의 저장소 쓰기는 이 리뷰와 `probes/test_probe_019.py` 두 파일뿐이다. 커밋·푸시·설치·원본 수정·저장소 파일 삭제를 하지 않았다.

기존 보호 파일의 blob 비교와 보조 전체 테스트는 통과했다. 7a 이후 각 단계의 원래 테스트에 들어간 변경은 이전 리뷰에 따른 수정이며, 새 단계가 앞 단계 테스트를 임의로 고친 흔적은 확인되지 않았다. Python 3.9와 사용자 PC의 `py` 정상 연결 환경은 이 세션에서 미검증이다.

## README 명령 재현

README의 `py -m src.*` 명령 21개를 모두 새 `tempfile.TemporaryDirectory`에서 실행했다. recipes/data를 임시 폴더에 복사하고, `PYTHONPATH`는 원본 저장소, `PYTHONIOENCODING=utf-8`, `PYTHONDONTWRITEBYTECODE=1`로 두었다. 아래 명령의 선두 `py`만 설치된 `C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe`로 대체했으며 인자·기본 설정은 그대로다. 11단계 기본 실행은 1회, 242.765초에 처음부터 끝까지 완료했다.

**21명령 모두 종료 0, 실제 새로 생성한 보고서 78개 모두 체크아웃된 제출물과 바이트 일치.** v1.1.0·v1.4.0의 CSV/meta 4개도 바이트 일치했다. 보고서 폴더를 미리 복사해서 일치한 것으로 센 것이 아니다. PFMEA의 이전 보고서 근거는 모듈 ROOT의 원본 자료를 읽는 기존 동작을 유지했다. 나머지 기존 보고서 3개(`eval_lot_clustered_dev_containment.csv`, `eval_lot_clustered_holdout_containment.csv`, `gen_seed42_trace_GEN_0030.csv`)는 README 실행 명령에 없어 이번 전체 재생 대상에는 포함되지 않으며 P18의 기존 blob 보존으로 확인했다. 이 세 파일의 이번 재생은 미검증이다.

실행 결과 원문(명령·종료·경과 시간과 바이트 비교):

~~~text
py -m src.anomaly recipes/anomaly_lamp.json -> exit=0 seconds=242.765
py -m src.main data/sample_events.csv -> exit=0 seconds=0.203
py -m src.main data/sample_events_v2.csv --recipe recipes/lamp_models.json -> exit=0 seconds=0.235
py -m src.main data/sample_events_retest.csv --recipe recipes/lamp_models_retest.json -> exit=0 seconds=0.219
py -m src.main data/sample_events_equipment.csv --recipe recipes/lamp_models_retest.json --equipment recipes/equipment.json -> exit=0 seconds=0.218
py -m src.generate --seed 42 --products 500 --out data/generated/gen_seed42.csv -> exit=0 seconds=0.297
py -m src.main data/generated/gen_seed42.csv --recipe recipes/lamp_models_retest.json --equipment recipes/equipment_generated.json --summary --trace GEN_0005 -> exit=0 seconds=0.375
py -m src.main data/sample_events_restart.csv --recipe recipes/lamp_models_retest.json --equipment recipes/equipment_restart.json --summary --trace f -> exit=0 seconds=0.219
py -m src.evaluate --seeds 0-99 --rules 3:2,5:2,5:3,10:3,10:4,20:4 --out eval_dev -> exit=0 seconds=119.125
py -m src.evaluate --seeds 1000-1099 --rules 3:2 --out eval_holdout --holdout -> exit=0 seconds=17.250
py -m src.evaluate --config recipes/generator.json --seeds 0-99 --rules 3:2 --out eval_baseline --holdout -> exit=0 seconds=13.625
py -m src.main data/sample_events_lot.csv --recipe recipes/lamp_models_retest.json --equipment recipes/equipment_lot.json --summary --containment -> exit=0 seconds=0.203
py -m src.evaluate --containment --config recipes/generator_lot.json --seeds 0-99 --rules 3:2 --out eval_lot_dev -> exit=0 seconds=18.953
py -m src.evaluate --containment --config recipes/generator_lot.json --seeds 1000-1099 --rules 3:2 --out eval_lot_holdout --holdout --selected-from reports/eval_lot_dev_containment.csv -> exit=0 seconds=18.578
py -m src.main data/sample_events_measured.csv --recipe recipes/lamp_models_measured.json --equipment recipes/equipment_measured.json --summary --trace c --capability -> exit=0 seconds=0.219
py -m src.generate --seed 42 --products 500 --config recipes/generator_measured.json --out data/generated/gen_measured_seed42.csv -> exit=0 seconds=0.344
py -m src.main data/generated/gen_measured_seed42.csv --recipe recipes/lamp_models_measured.json --equipment recipes/equipment_measured.json --summary --containment --capability --trace GEN_0005 -> exit=0 seconds=0.390
py -m src.pfmea data/pfmea_lamp.csv --config recipes/generator_measured.json --seeds 0-29 --products 500 -> exit=0 seconds=8.860
py -m src.line recipes/line_lamp.json --seeds 0-29 --holdout-seeds 1000-1029 --products 500 -> exit=0 seconds=20.422
py -m src.station recipes/plc_station.json --seed 42 --products 20 --scenario normal -> exit=0 seconds=0.281
py -m src.station recipes/plc_station.json --scenario all -> exit=0 seconds=0.516
REPORTS_COMPARED=78 MISMATCHES=[]
data\generated\gen_seed42.csv bytes_equal=True
data\generated\gen_seed42.csv.meta.json bytes_equal=True
data\generated\gen_measured_seed42.csv bytes_equal=True
data\generated\gen_measured_seed42.csv.meta.json bytes_equal=True
anomaly_lamp_methods.csv SHA256=8a95ad63ba7995a4b6e659e59e7b65e4c961d69be933fe2ef3791276e8e89e75
anomaly_lamp_model.csv SHA256=53ca142c36ffdf374be1d5ee1c1b378d64b826f7b463cc42b5b51f198e4165a3
anomaly_lamp_replay.csv SHA256=635bd656023a8c2c89163ce0445495d765e2295a0ed5da67247c82fcb98e799e
~~~

## 테스트 실행 명령과 결과 원문

실행 시 캐시 생성을 막기 위해 `PYTHONDONTWRITEBYTECODE=1`을 사용했다. 아래는 통과 결과와 런처 실패를 분리한 기록이다.

### 지정 명령과 직접 인터프리터 실행

~~~powershell
py -m unittest discover -s tests
~~~

~~~text
No installed Python found!
~~~

종료 코드 1. 이어서 사용자가 지정한 대체 명령을 한 번 직접 실행했다:

~~~powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest discover -s tests
~~~

종료 코드 1. 360개를 실행했으나 하위 프로세스의 py 연결 때문에 실패 항목 132개였다. 아래 완료 출력은 원문 그대로이며, 출력 중 경로의 한글 깨짐도 고치지 않았다. 진행 점의 앞부분은 생략하고 실패 진단과 최종 결과를 보존했다.

<details>
<summary>직접 실행 실패 진단과 최종 결과 원문</summary>

~~~text
..F......................................................................................................................................FFFFFFFFFFFFFFFFFF.................................FFF................FFFFFFFF.F........................................FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF...F........FF.FFFFFFFFFFF.FF..FFF
======================================================================
FAIL: test_t80_no_selection_exits_zero (test_containment.CommandTests.test_t80_no_selection_exits_zero)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 421, in test_t80_no_selection_exits_zero
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t80_runs_without_stops_keep_every_method (test_containment.CommandTests.test_t80_runs_without_stops_keep_every_method)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 440, in test_t80_runs_without_stops_keep_every_method
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t84_bad_commands_exit_two_without_reports (test_containment.CommandTests.test_t84_bad_commands_exit_two_without_reports) (case=('--config', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\generator_lot.json', '--rules', '3:2,5:2'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 384, in test_t84_bad_commands_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t84_bad_commands_exit_two_without_reports (test_containment.CommandTests.test_t84_bad_commands_exit_two_without_reports) (case=('--config', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\generator_lot.json', '--rules', '5:2'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 384, in test_t84_bad_commands_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t84_bad_commands_exit_two_without_reports (test_containment.CommandTests.test_t84_bad_commands_exit_two_without_reports) (case=('--config', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\generator_restart.json', '--rules', '3:2'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 384, in test_t84_bad_commands_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t84_bad_commands_exit_two_without_reports (test_containment.CommandTests.test_t84_bad_commands_exit_two_without_reports) (case=('--config', 'C:\\Users\\PC\\AppData\\Local\\Temp\\tmp2f35wvbr\\two.json', '--rules', '3:2'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 384, in test_t84_bad_commands_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t84_bad_commands_exit_two_without_reports (test_containment.CommandTests.test_t84_bad_commands_exit_two_without_reports) (case=('--config', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\generator_lot.json', '--rules', '3:2', '--holdout'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 384, in test_t84_bad_commands_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t85_same_command_same_report (test_containment.CommandTests.test_t85_same_command_same_report)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 391, in test_t85_same_command_same_report
    self.assertEqual(cli(directory, *arguments, "--out", name, module="src.evaluate").returncode, 0)
AssertionError: 112 != 0

======================================================================
FAIL: test_t81_reproducible_and_truth_stays_out_of_csv (test_containment.GeneratorTests.test_t81_reproducible_and_truth_stays_out_of_csv) (seed=42)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 262, in test_t81_reproducible_and_truth_stays_out_of_csv
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t81_reproducible_and_truth_stays_out_of_csv (test_containment.GeneratorTests.test_t81_reproducible_and_truth_stays_out_of_csv) (seed=7)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 262, in test_t81_reproducible_and_truth_stays_out_of_csv
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t87_huge_integer_probability_is_a_setting_error (test_containment.GeneratorTests.test_t87_huge_integer_probability_is_a_setting_error) (change=['faulty_detection_loss'])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 335, in test_t87_huge_integer_probability_is_a_setting_error
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_huge_integer_probability_is_a_setting_error (test_containment.GeneratorTests.test_t87_huge_integer_probability_is_a_setting_error) (change=['defective_in_lot_probability', 'defective_lot_probability'])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 335, in test_t87_huge_integer_probability_is_a_setting_error
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_invalid_settings (test_containment.GeneratorTests.test_t87_invalid_settings) (change={'lot_size': 0})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 317, in test_t87_invalid_settings
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_invalid_settings (test_containment.GeneratorTests.test_t87_invalid_settings) (change={'lot_size': True})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 317, in test_t87_invalid_settings
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_invalid_settings (test_containment.GeneratorTests.test_t87_invalid_settings) (change={'faulty_detection_loss': {'LEAK-2': 1.5}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 317, in test_t87_invalid_settings
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_invalid_settings (test_containment.GeneratorTests.test_t87_invalid_settings) (change={'faulty_detection_loss': {'LEAK-1': 0.5}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 317, in test_t87_invalid_settings
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_invalid_settings (test_containment.GeneratorTests.test_t87_invalid_settings) (change={'lot_size': None})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 317, in test_t87_invalid_settings
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_invalid_settings (test_containment.GeneratorTests.test_t87_invalid_settings) (change={'defective_lot_probability': 0.25})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 317, in test_t87_invalid_settings
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t87_invalid_settings (test_containment.GeneratorTests.test_t87_invalid_settings) (change={'equipment': 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\equipment_restart.json'})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 317, in test_t87_invalid_settings
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t69_mode_and_header_combinations (test_containment.InputTests.test_t69_mode_and_header_combinations)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 106, in test_t69_mode_and_header_combinations
    self.assertEqual(cli(one, str(SAMPLE), *arguments, str(PLAIN_EQUIPMENT)).returncode, 0)
AssertionError: 112 != 0

======================================================================
FAIL: test_t88_leaked_products_validation (test_containment.MetaTests.test_t88_leaked_products_validation) (change={'leaked_products': ['']})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 362, in test_t88_leaked_products_validation
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t88_leaked_products_validation (test_containment.MetaTests.test_t88_leaked_products_validation) (change={'leaked_products': ['GEN_0001', 'GEN_0001']})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 362, in test_t88_leaked_products_validation
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t88_leaked_products_validation (test_containment.MetaTests.test_t88_leaked_products_validation) (change={'leaked_products': ['GEN_0002']})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 362, in test_t88_leaked_products_validation
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t88_leaked_products_validation (test_containment.MetaTests.test_t88_leaked_products_validation) (change={'defective_products': None})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 362, in test_t88_leaked_products_validation
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t88_leaked_products_validation (test_containment.MetaTests.test_t88_leaked_products_validation) (change={'defective_products': ['GEN_9999'], 'leaked_products': ['GEN_9999']})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 362, in test_t88_leaked_products_validation
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t74_empty_and_mode_cases (test_containment.ScopeTests.test_t74_empty_and_mode_cases)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_containment.py", line 157, in test_t74_empty_and_mode_cases
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t40_invalid_fixtures_exit_three_without_reports (test_equipment.EquipmentFileTests.test_t40_invalid_fixtures_exit_three_without_reports) (name='equipment_window_zero.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 59, in test_t40_invalid_fixtures_exit_three_without_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t40_invalid_fixtures_exit_three_without_reports (test_equipment.EquipmentFileTests.test_t40_invalid_fixtures_exit_three_without_reports) (name='equipment_fails_exceeds.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 59, in test_t40_invalid_fixtures_exit_three_without_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t40_invalid_fixtures_exit_three_without_reports (test_equipment.EquipmentFileTests.test_t40_invalid_fixtures_exit_three_without_reports) (name='equipment_window_string.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 59, in test_t40_invalid_fixtures_exit_three_without_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t40_invalid_fixtures_exit_three_without_reports (test_equipment.EquipmentFileTests.test_t40_invalid_fixtures_exit_three_without_reports) (name='equipment_unknown_keys.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 59, in test_t40_invalid_fixtures_exit_three_without_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t40_invalid_fixtures_exit_three_without_reports (test_equipment.EquipmentFileTests.test_t40_invalid_fixtures_exit_three_without_reports) (name='equipment_empty.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 59, in test_t40_invalid_fixtures_exit_three_without_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t40_invalid_fixtures_exit_three_without_reports (test_equipment.EquipmentFileTests.test_t40_invalid_fixtures_exit_three_without_reports) (name='equipment_unknown_inspection.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 59, in test_t40_invalid_fixtures_exit_three_without_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t40_invalid_fixtures_exit_three_without_reports (test_equipment.EquipmentFileTests.test_t40_invalid_fixtures_exit_three_without_reports) (name='equipment_multiple_errors.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 59, in test_t40_invalid_fixtures_exit_three_without_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_sample_t33_to_t39_reports_and_all_rejected_state_unchanged (test_equipment.EquipmentReportTests.test_sample_t33_to_t39_reports_and_all_rejected_state_unchanged)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 311, in test_sample_t33_to_t39_reports_and_all_rejected_state_unchanged
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 112 != 0 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_equipment_with_stage_one_has_seven_rules_and_no_history (test_equipment.EquipmentReportTests.test_t41_equipment_with_stage_one_has_seven_rules_and_no_history)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 406, in test_t41_equipment_with_stage_one_has_seven_rules_and_no_history
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 112 != 0 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_four_reports_history_equipment_order_and_byte_reproducibility (test_equipment.EquipmentReportTests.test_t41_four_reports_history_equipment_order_and_byte_reproducibility)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 342, in test_t41_four_reports_history_equipment_order_and_byte_reproducibility
    self.assertEqual(first.returncode, 0, first.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t41_option_dependency_and_mode_specific_headers (test_equipment.EquipmentReportTests.test_t41_option_dependency_and_mode_specific_headers) (recipe=None, equipment=WindowsPath('C:/Users/PC/Documents/ChatGPT/������ KDT AI ���� ��Ʈķ��/project/recipes/equipment.json'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 379, in test_t41_option_dependency_and_mode_specific_headers
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 112 != 2 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_option_dependency_and_mode_specific_headers (test_equipment.EquipmentReportTests.test_t41_option_dependency_and_mode_specific_headers) (recipe=None, equipment=None)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 379, in test_t41_option_dependency_and_mode_specific_headers
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 112 != 2 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_option_dependency_and_mode_specific_headers (test_equipment.EquipmentReportTests.test_t41_option_dependency_and_mode_specific_headers) (recipe=WindowsPath('C:/Users/PC/Documents/ChatGPT/������ KDT AI ���� ��Ʈķ��/project/recipes/lamp_models_retest.json'), equipment=None)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 379, in test_t41_option_dependency_and_mode_specific_headers
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 112 != 2 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_option_dependency_and_mode_specific_headers (test_equipment.EquipmentReportTests.test_t41_option_dependency_and_mode_specific_headers)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 385, in test_t41_option_dependency_and_mode_specific_headers
    self.assertEqual(result.returncode, 2, result.stderr)
AssertionError: 112 != 2 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_without_equipment_all_nine_legacy_reports_unchanged (test_equipment.EquipmentReportTests.test_t41_without_equipment_all_nine_legacy_reports_unchanged) (name='sample_events')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 393, in test_t41_without_equipment_all_nine_legacy_reports_unchanged
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 112 != 0 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_without_equipment_all_nine_legacy_reports_unchanged (test_equipment.EquipmentReportTests.test_t41_without_equipment_all_nine_legacy_reports_unchanged) (name='sample_events_v2')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 393, in test_t41_without_equipment_all_nine_legacy_reports_unchanged
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 112 != 0 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t41_without_equipment_all_nine_legacy_reports_unchanged (test_equipment.EquipmentReportTests.test_t41_without_equipment_all_nine_legacy_reports_unchanged) (name='sample_events_retest')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_equipment.py", line 393, in test_t41_without_equipment_all_nine_legacy_reports_unchanged
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 112 != 0 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_holdout_flag_never_selects (test_evaluate.CommandTests.test_holdout_flag_never_selects)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_evaluate.py", line 108, in test_holdout_flag_never_selects
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t64_bad_arguments_exit_two_without_reports (test_evaluate.CommandTests.test_t64_bad_arguments_exit_two_without_reports) (seeds='0-1', rules='5:6')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_evaluate.py", line 102, in test_t64_bad_arguments_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t64_bad_arguments_exit_two_without_reports (test_evaluate.CommandTests.test_t64_bad_arguments_exit_two_without_reports) (seeds='5-3', rules='3:2')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_evaluate.py", line 102, in test_t64_bad_arguments_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t64_bad_arguments_exit_two_without_reports (test_evaluate.CommandTests.test_t64_bad_arguments_exit_two_without_reports) (seeds='0-1', rules='3:2,3:2')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_evaluate.py", line 102, in test_t64_bad_arguments_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t64_bad_arguments_exit_two_without_reports (test_evaluate.CommandTests.test_t64_bad_arguments_exit_two_without_reports) (seeds='x', rules='3:2')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_evaluate.py", line 102, in test_t64_bad_arguments_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t64_bad_arguments_exit_two_without_reports (test_evaluate.CommandTests.test_t64_bad_arguments_exit_two_without_reports) (seeds='0-1', rules='3')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_evaluate.py", line 102, in test_t64_bad_arguments_exit_two_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t64_same_command_same_reports (test_evaluate.CommandTests.test_t64_same_command_same_reports)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_evaluate.py", line 88, in test_t64_same_command_same_reports
    self.assertEqual(cli(directory, *arguments, "--out", "one").returncode, 0)
AssertionError: 112 != 0

======================================================================
FAIL: test_t44_csv_meta_and_six_reports_repeat_for_both_seeds (test_generate.GeneratedInvariantTests.test_t44_csv_meta_and_six_reports_repeat_for_both_seeds) (seed=42)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_generate.py", line 137, in test_t44_csv_meta_and_six_reports_repeat_for_both_seeds
    self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t44_csv_meta_and_six_reports_repeat_for_both_seeds (test_generate.GeneratedInvariantTests.test_t44_csv_meta_and_six_reports_repeat_for_both_seeds) (seed=7)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_generate.py", line 137, in test_t44_csv_meta_and_six_reports_repeat_for_both_seeds
    self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_review005_m3_missing_candidate_explains_failure_without_output (test_generate.GeneratorTests.test_review005_m3_missing_candidate_explains_failure_without_output)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_generate.py", line 90, in test_review005_m3_missing_candidate_explains_failure_without_output
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_csv_physical_order_and_malformed_rows_are_reported_without_state_changes (test_recipe.RecipeCommandLineTests.test_csv_physical_order_and_malformed_rows_are_reported_without_state_changes)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 460, in test_csv_physical_order_and_malformed_rows_are_reported_without_state_changes
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_header_mode_mismatch_and_input_errors_exit_two_without_reports (test_recipe.RecipeCommandLineTests.test_header_mode_mismatch_and_input_errors_exit_two_without_reports) (csv_path=WindowsPath('C:/Users/PC/AppData/Local/Temp/tmptxfvp52i/events.csv'), recipe=None)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 443, in test_header_mode_mismatch_and_input_errors_exit_two_without_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

======================================================================
FAIL: test_header_mode_mismatch_and_input_errors_exit_two_without_reports (test_recipe.RecipeCommandLineTests.test_header_mode_mismatch_and_input_errors_exit_two_without_reports) (csv_path=WindowsPath('C:/Users/PC/Documents/ChatGPT/������ KDT AI ���� ��Ʈķ��/project/data/sample_events.csv'), recipe=WindowsPath('C:/Users/PC/Documents/ChatGPT/������ KDT AI ���� ��Ʈķ��/project/recipes/lamp_models.json'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 443, in test_header_mode_mismatch_and_input_errors_exit_two_without_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

======================================================================
FAIL: test_header_mode_mismatch_and_input_errors_exit_two_without_reports (test_recipe.RecipeCommandLineTests.test_header_mode_mismatch_and_input_errors_exit_two_without_reports) (csv_path=WindowsPath('C:/Users/PC/AppData/Local/Temp/tmptxfvp52i/missing.csv'), recipe=WindowsPath('C:/Users/PC/Documents/ChatGPT/������ KDT AI ���� ��Ʈķ��/project/recipes/lamp_models.json'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 443, in test_header_mode_mismatch_and_input_errors_exit_two_without_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

======================================================================
FAIL: test_sample_v2_matches_expected_products_and_rejection_counts (test_recipe.RecipeCommandLineTests.test_sample_v2_matches_expected_products_and_rejection_counts)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 491, in test_sample_v2_matches_expected_products_and_rejection_counts
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='empty_steps.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='duplicate_steps.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='duplicate_inspections.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='string_steps.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='unknown_key.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='unknown_after.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='multiple_errors.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='invalid_structure.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='invalid_json.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='array_root.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='empty_models.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports (test_recipe.RecipeCommandLineTests.test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports) (name='missing.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 382, in test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t21_same_csv_and_recipe_repeat_byte_identically_and_after_changes_decision (test_recipe.RecipeCommandLineTests.test_t21_same_csv_and_recipe_repeat_byte_identically_and_after_changes_decision)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_recipe.py", line 399, in test_t21_same_csv_and_recipe_repeat_byte_identically_and_after_changes_decision
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t58_bad_flag_or_reserved_step_exit_three (test_restart.ModeTests.test_t58_bad_flag_or_reserved_step_exit_three) (flag='true')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_restart.py", line 174, in test_t58_bad_flag_or_reserved_step_exit_three
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t58_bad_flag_or_reserved_step_exit_three (test_restart.ModeTests.test_t58_bad_flag_or_reserved_step_exit_three) (flag=1)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_restart.py", line 174, in test_t58_bad_flag_or_reserved_step_exit_three
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t58_bad_flag_or_reserved_step_exit_three (test_restart.ModeTests.test_t58_bad_flag_or_reserved_step_exit_three)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_restart.py", line 181, in test_t58_bad_flag_or_reserved_step_exit_three
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t31_invalid_fixtures_stop_before_events_and_reports (test_retest.RetestRecipeTests.test_t31_invalid_fixtures_stop_before_events_and_reports) (name='retest_zero.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 51, in test_t31_invalid_fixtures_stop_before_events_and_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t31_invalid_fixtures_stop_before_events_and_reports (test_retest.RetestRecipeTests.test_t31_invalid_fixtures_stop_before_events_and_reports) (name='retest_string.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 51, in test_t31_invalid_fixtures_stop_before_events_and_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t31_invalid_fixtures_stop_before_events_and_reports (test_retest.RetestRecipeTests.test_t31_invalid_fixtures_stop_before_events_and_reports) (name='retest_bool.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 51, in test_t31_invalid_fixtures_stop_before_events_and_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t31_invalid_fixtures_stop_before_events_and_reports (test_retest.RetestRecipeTests.test_t31_invalid_fixtures_stop_before_events_and_reports) (name='retest_partial.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 51, in test_t31_invalid_fixtures_stop_before_events_and_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t31_invalid_fixtures_stop_before_events_and_reports (test_retest.RetestRecipeTests.test_t31_invalid_fixtures_stop_before_events_and_reports) (name='retest_reserved.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 51, in test_t31_invalid_fixtures_stop_before_events_and_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_t31_invalid_fixtures_stop_before_events_and_reports (test_retest.RetestRecipeTests.test_t31_invalid_fixtures_stop_before_events_and_reports) (name='retest_multiple_errors.json')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 51, in test_t31_invalid_fixtures_stop_before_events_and_reports
    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
AssertionError: 112 != 3 : No installed Python found!


======================================================================
FAIL: test_sample_t23_to_t30_reports_match_fixed_input (test_retest.RetestReportTests.test_sample_t23_to_t30_reports_match_fixed_input)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 264, in test_sample_t23_to_t30_reports_match_fixed_input
    self.assertEqual(result.returncode, 0, result.stderr)
AssertionError: 112 != 0 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t32_cli_history_seven_rules_and_byte_reproducibility (test_retest.RetestReportTests.test_t32_cli_history_seven_rules_and_byte_reproducibility)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_retest.py", line 314, in test_t32_cli_history_seven_rules_and_byte_reproducibility
    self.assertEqual(first.returncode, 0, first.stderr)
AssertionError: 112 != 0 : b'No installed Python found!\r\n'

======================================================================
FAIL: test_t10_identical_input_produces_identical_stdout_and_csv_bytes (test_rules.CommandLineTests.test_t10_identical_input_produces_identical_stdout_and_csv_bytes)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_rules.py", line 199, in test_t10_identical_input_produces_identical_stdout_and_csv_bytes
    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta=[])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta=None)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'injected_errors': {}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': '24', 'injected_errors': {}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24.0, 'injected_errors': {}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': True, 'injected_errors': {}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': -1, 'injected_errors': {}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': []})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'SEQ_SKIP': '1'}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'SEQ_SKIP': 1.0}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'SEQ_SKIP': True}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'SEQ_SKIP': None}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'SEQ_SKIP': -1}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'SEQ_SKIP': 1, 'FOO': 5}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'FOO': 0}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review005_m2_invalid_meta_exits_2_without_reports (test_summary.SummaryTests.test_review005_m2_invalid_meta_exits_2_without_reports) (meta={'normal_rows': 24, 'injected_errors': {'EQUIP_STOPPED': 1}})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 309, in test_review005_m2_invalid_meta_exits_2_without_reports
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['ZZZ'], options=('--summary',))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['ZZZ'], options=('--summary', '--trace', 'a'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['A'], options=('--summary',))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['A'], options=('--summary', '--trace', 'a'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=[' a'], options=('--summary',))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=[' a'], options=('--summary', '--trace', 'a'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['a '], options=('--summary',))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['a '], options=('--summary', '--trace', 'a'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['a', 'ZZZ'], options=('--summary',))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['a', 'ZZZ'], options=('--summary', '--trace', 'a'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['ghost'], options=('--summary',))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_review008_m1_cli_rejects_unregistered_ids_before_any_report (test_summary.SummaryTests.test_review008_m1_cli_rejects_unregistered_ids_before_any_report) (defective=['ghost'], options=('--summary', '--trace', 'a'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 166, in test_review008_m1_cli_rejects_unregistered_ids_before_any_report
    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t45_cli_summary_is_separate_and_legacy_four_reports_are_unchanged (test_summary.SummaryTests.test_t45_cli_summary_is_separate_and_legacy_four_reports_are_unchanged)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 265, in test_t45_cli_summary_is_separate_and_legacy_four_reports_are_unchanged
    self.assertEqual(legacy.returncode, 0, legacy.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t48_summary_requires_equipment_without_creating_reports (test_summary.SummaryTests.test_t48_summary_requires_equipment_without_creating_reports) (options=('--summary',))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 286, in test_t48_summary_requires_equipment_without_creating_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

======================================================================
FAIL: test_t48_summary_requires_equipment_without_creating_reports (test_summary.SummaryTests.test_t48_summary_requires_equipment_without_creating_reports) (options=('--recipe', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\lamp_models_retest.json', '--summary'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 286, in test_t48_summary_requires_equipment_without_creating_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=None)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective='a')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective={})
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=[1])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=[True])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=[[]])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=[''])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=['  '])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=['a', 'a'])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 2 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=[])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t51_cli_defective_meta_validation_before_any_report (test_summary.SummaryTests.test_t51_cli_defective_meta_validation_before_any_report) (defective=['a', 'b'])
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 133, in test_t51_cli_defective_meta_validation_before_any_report
    self.assertEqual(result.returncode, 2 if defective in invalid else 0,
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t47_case_colliding_product_ids_keep_distinct_reproducible_files (test_summary.TraceTests.test_t47_case_colliding_product_ids_keep_distinct_reproducible_files)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 394, in test_t47_case_colliding_product_ids_keep_distinct_reproducible_files
    self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t47_cli_repeated_trace_and_summary_use_separate_files (test_summary.TraceTests.test_t47_cli_repeated_trace_and_summary_use_separate_files)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 360, in test_t47_cli_repeated_trace_and_summary_use_separate_files
    self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8"))
AssertionError: 112 != 0 : No installed Python found!


======================================================================
FAIL: test_t48_unknown_trace_and_non_equipment_modes_create_no_reports (test_summary.TraceTests.test_t48_unknown_trace_and_non_equipment_modes_create_no_reports) (options=('--trace', 'T34'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 380, in test_t48_unknown_trace_and_non_equipment_modes_create_no_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

======================================================================
FAIL: test_t48_unknown_trace_and_non_equipment_modes_create_no_reports (test_summary.TraceTests.test_t48_unknown_trace_and_non_equipment_modes_create_no_reports) (options=('--recipe', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\lamp_models_retest.json', '--trace', 'T34'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 380, in test_t48_unknown_trace_and_non_equipment_modes_create_no_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

======================================================================
FAIL: test_t48_unknown_trace_and_non_equipment_modes_create_no_reports (test_summary.TraceTests.test_t48_unknown_trace_and_non_equipment_modes_create_no_reports) (options=('--recipe', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\lamp_models_retest.json', '--equipment', 'C:\\Users\\PC\\Documents\\ChatGPT\\������ KDT AI ���� ��Ʈķ��\\project\\recipes\\equipment.json', '--summary', '--trace', 'T34', '--trace', 'NO_SUCH_PRODUCT'))
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\������ KDT AI ���� ��Ʈķ��\project\tests\test_summary.py", line 380, in test_t48_unknown_trace_and_non_equipment_modes_create_no_reports
    self.assertEqual(result.returncode, 2)
AssertionError: 112 != 2

----------------------------------------------------------------------
Ran 360 tests in 123.456s

FAILED (failures=132)
T44 seed=42 products=500 generation_seconds=0.127199 judgment_analysis_seconds=0.061111
T44 seed=7 products=200 generation_seconds=0.050637 judgment_analysis_seconds=0.025885
T44 seed=42 all_rows_deepcopy_invariant_seconds=40.232474
T44 seed=7 all_rows_deepcopy_invariant_seconds=6.071324
~~~

</details>

### 테스트 파일 무수정 보조 실행

`test_probe_019.run_legacy_suite`는 이 프로세스의 `subprocess.Popen`에서 실행 파일 이름이 정확히 `py`인 호출만 `sys.executable`로 바꾼다. 나머지 명령·인자·환경·테스트 본문은 유지한다. 테스트·설정 파일 수정, 런처 설치, 시스템 설정 변경은 없다. 이 보조 연결을 일반 환경의 원래 명령 통과로 주장하지 않는다.

~~~powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -c "from handoff.reviews.probes.test_probe_019 import run_legacy_suite; import sys; sys.exit(not run_legacy_suite().wasSuccessful())"
~~~

종료 코드 0. 결과 원문:

~~~text
................................................................................................................................................................................................................................................................................................................................
----------------------------------------------------------------------
Ran 360 tests in 165.930s

OK
T44 seed=42 products=500 generation_seconds=0.130917 judgment_analysis_seconds=0.079714
T44 seed=7 products=200 generation_seconds=0.060924 judgment_analysis_seconds=0.022161
T44 seed=42 all_rows_deepcopy_invariant_seconds=45.215866
T44 seed=7 all_rows_deepcopy_invariant_seconds=6.124377
~~~

### 이번 반례 최종 실행

~~~powershell
py -m unittest handoff/reviews/probes/test_probe_019.py
~~~

~~~text
No installed Python found!
~~~

종료 코드 1. 설치된 인터프리터로 실행했다:

~~~powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff/reviews/probes/test_probe_019.py
~~~

최종 종료 코드 1. 총 20개 메서드, 네 메서드에서 실패 항목 5개(규격 동등성은 두 로더 서브테스트). 완료 출력 원문:

~~~text
P19 PFMEA raw totals={'defect_escape': [16, 307], 'all_defect_first_fail': [350, 398], 'leak_defect_first_fail': [273, 307], 'leak_defect_retest_pass': [49, 192], 'normal_reject': [47, 14693], 'fault_stop_run': [28, 30], 'fault_no_stop_run': [2, 30], 'fault_stop_delay': [1751, 28], 'normal_stop_rate': [20, 32205]}
.P20 development good 14646 passed 14662 escaped 16 elapsed_ms 288432000 good_uph 182.8008
P20 holdout good 14663 passed 14680 escaped 17 elapsed_ms 284292000 good_uph 185.6781
.
======================================================================
FAIL: test_p03_equal_numeric_specs_across_shared_loaders (handoff.reviews.probes.test_probe_019.Probe019.test_p03_equal_numeric_specs_across_shared_loaders) (loader='anomaly')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_019.py", line 136, in test_p03_equal_numeric_specs_across_shared_loaders
    loader()
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_019.py", line 131, in <lambda>
    ('anomaly', lambda: anomaly.load_process(replace(SETTINGS, generator=path))),
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\anomaly.py", line 201, in load_process
    raise ValueError(settings.inspection + ": 모든 모델에서 같은 양측 규격이어야 함")
ValueError: LEAK: 모든 모델에서 같은 양측 규격이어야 함

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_019.py", line 138, in test_p03_equal_numeric_specs_across_shared_loaders
    self.fail('equal numeric specifications were rejected: ' + str(error))
AssertionError: equal numeric specifications were rejected: LEAK: 모든 모델에서 같은 양측 규격이어야 함

======================================================================
FAIL: test_p03_equal_numeric_specs_across_shared_loaders (handoff.reviews.probes.test_probe_019.Probe019.test_p03_equal_numeric_specs_across_shared_loaders) (loader='station')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_019.py", line 136, in test_p03_equal_numeric_specs_across_shared_loaders
    loader()
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_019.py", line 132, in <lambda>
    ('station', lambda: station.load_values(replace(station.load_station(ROOT/'recipes/plc_station.json'),
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\station.py", line 121, in load_values
    raise ValueError(station.inspection + ": 모든 모델에서 같은 양측 규격이어야 함")
ValueError: LEAK: 모든 모델에서 같은 양측 규격이어야 함

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_019.py", line 138, in test_p03_equal_numeric_specs_across_shared_loaders
    self.fail('equal numeric specifications were rejected: ' + str(error))
AssertionError: equal numeric specifications were rejected: LEAK: 모든 모델에서 같은 양측 규격이어야 함

======================================================================
FAIL: test_p07_line_long_seconds_end_to_end (handoff.reviews.probes.test_probe_019.Probe019.test_p07_line_long_seconds_end_to_end)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_019.py", line 182, in test_p07_line_long_seconds_end_to_end
    self.assertEqual(result.returncode,0,result.stderr)
AssertionError: 1 != 0 : Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 1024, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 1004, in main
    outcome, rows, paths = run(args.line, args.seeds, args.holdout_seeds, args.products)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 979, in run
    balance_rows(line, ratios, heuristic, optimal, visits, good_rate))
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 801, in balance_rows
    rows += [summary("net_seconds", show(Fraction(line.net, 1000))), summary("takt_seconds", show(takt / 1000)),
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 633, in show
    return _fixed(Decimal(fraction.numerator) / Decimal(fraction.denominator))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\src\line.py", line 627, in _fixed
    return format(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), ".4f")
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
decimal.InvalidOperation: [<class 'decimal.InvalidOperation'>]


======================================================================
FAIL: test_p09_repeated_rejected_pair_after_intervening_pair (handoff.reviews.probes.test_probe_019.Probe019.test_p09_repeated_rejected_pair_after_intervening_pair)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_019.py", line 203, in test_p09_repeated_rejected_pair_after_intervening_pair
    self.assertEqual(len(rejected),2,repr(rejected))
AssertionError: 4 != 2 : ['판정 거절: ID 불일치', '판정 거절: 판정 값 오류', '판정 거절: ID 불일치', '판정 거절: 판정 값 오류']

======================================================================
FAIL: test_p11_modbus_total_response_deadline (handoff.reviews.probes.test_probe_019.Probe019.test_p11_modbus_total_response_deadline)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project\handoff\reviews\probes\test_probe_019.py", line 239, in test_p11_modbus_total_response_deadline
    with self.assertRaises(modbus.ModbusTimeout):
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: ModbusTimeout not raised

----------------------------------------------------------------------
Ran 20 tests in 20.309s

FAILED (failures=5)
~~~

반례 작성 중 같은 명령의 중간 실행은 아래와 같았다. 첫 P01의 검수 코드 오류와 P03 입력 구성 오류는 위에서 공개했고, 제품 파일은 바꾸지 않았다.

~~~text
Ran 15 tests in 3.560s
FAILED (failures=3, errors=1)

Ran 18 tests in 8.626s
FAILED (failures=5)
~~~

런처 원인 확인 과정에서 다음 단일 진단 호출은 존재하지 않는 클래스명을 지정해 테스트를 실행하지 못했다. 전체 테스트 실패나 제품 결함으로 계상하지 않는다.

~~~powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest tests.test_anomaly.FeatureTests.test_t177_validation_does_not_change_training
~~~

~~~text
ERROR: FeatureTests (unittest.loader._FailedTest.FeatureTests)
AttributeError: module 'tests.test_anomaly' has no attribute 'FeatureTests'

Ran 1 test in 0.001s
FAILED (errors=1)
~~~

VERDICT: FIX
