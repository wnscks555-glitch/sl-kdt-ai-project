검수 모델: gpt-6-astra

# 리뷰 025 — 제출 전 최종 검토

검수일: 2026-11-01. 대상: `e93b5c9..9c082410a377848e4ef137f60d6017deac0ec750`의 diff·log, README 첫 화면 전체와 12–15단계. 기준은 `handoff/tasks.md`의 12·13·14·15단계 명세·T190–T266, 이전 단계 보존 조건, `handoff/decisions.md`다.

**판정 FIX. 미해결 중간 3건이다. 새 높음은 확인하지 않았다.** 기존 리뷰 020–024의 높음·중간 지적은 아래 재현 범위에서 해결됐다. 중단된 025의 P11–P14도 각 반례를 통과했다. 다만 P12의 선택 없음 처리와 별개로, 실제 무경보 재생 자료까지 이어지는 경로에는 M2가 남는다. 낮음 기록은 수정 요구로 세지 않는다.

README의 보고서 재현 순서를 임시 폴더에서 끝까지 실행했다. **기존 19개·신규 11개, 합계 30개 보고서가 제출본과 원시 바이트까지 동일**하다. 대시보드 재생성도 동일하며 270745바이트다. 실행 전후 원본 reports/data/recipes 파일 123개는 불변이다. 전체 테스트는 직접 실행했으나 내부 `py` 런처 문제로 완전 통과를 확인하지 못했다. 브라우저 실행은 하지 않았다.

setup-notes, tasks, gpt-log, decisions, 리뷰 020–024, 구현자 동결 로그, 지정 Git 이력을 읽었다. 플러그인 리뷰 스킬과 보조 에이전트는 사용하지 않았다. practical-work-operation은 작업 조율과 보존 확인에만 적용했다. 코드 수정·커밋·푸시·설치·원본 파일 삭제는 하지 않았다.

## 미해결 지적

| ID | 심각도 | 파일:줄 | 문제 | 근거 | 제안 |
| --- | --- | --- | --- | --- | --- |
| R25-M1 | 중간 | `src/dashboard.py:356` | 12단계가 정상적으로 생성하는 계산 불가 결과를 대시보드가 표시하지 못한다. | P17: 임시 복사본의 유효한 process_cpk=1e6, products=12, 개발 시드7·홀드아웃1007로 실제 MSA CLI를 실행했다. 종료0이고 연구값이 10.000으로 같아 세 게이지의 pct_grr·ndc가 빈칸, verdict가 판정 불가다. 이는 T192·T250의 정의된 결과다. 이어 대시보드는 빈 pct_grr를 float로 바꾸다 종료2(`could not convert string to float: ''`)다. 기본 제출본의 수치 오류는 아니지만 12→15단계의 유효한 출력 계약을 잇지 못한다. | 계산 불가 행은 빈칸과 판정 불가로 표에 유지한다. 수치가 없는 막대는 계산에서 제외하고, 전부 없을 때도 표와 설명을 만든다. 실제 MSA에서 만든 빈값 보고서를 입력하는 회귀 검증을 둔다. |
| R25-M2 | 중간 | `src/dashboard.py:298` | 경보 행이 반드시 있어야 한다고 가정해, 유효한 무경보·임계값 없음 재생 보고서를 입력 오류로 거절한다. | P18: 제출 모델을 읽어 11단계 replay_rows로 임계값 없음과 전체 점수보다 높은 임계값의 무경보 자료를 각각 생성했다. 두 자료 모두 26행이며 status는 임계값 없음·missed다. 기존 11단계 명세 T189는 이 형태를 명시하고, T265는 존재하는 alarm=1 행을 검사하라고 한다. 실제 CLI는 두 경우 모두 종료2, 로지스틱 기여값 입력이 모자람이다. P12는 선택 행만 바꾸고 기존 경보 행을 남겼기 때문에 이 경로를 검증하지 않았다. | 모델의 필수 필드 검증과 경보 목록의 공집합을 구분한다. 무경보·임계값 없음 상태를 표시하고 기여값 표만 생략한다. 임계값이 없는 경우 방법별 수치·이동량 행도 없을 수 있으므로 11단계의 실제 산출물 형태로 연결 시험한다. |
| R25-M3 | 중간 | `src/dashboard.py:514`, `src/incident.py:630`, `tests/test_dashboard.py:334` | 사건의 필수 PFMEA 연결이 없어도 빈칸으로 성공하며, 모든 사건 ID를 잇는다는 명세와 실제 연결 범위가 다르다. | P19: 제출 자료의 사건 연결 11개 중 PFMEA가 있는 것은 ewma_chart-3·cusum-3 두 개뿐이다. 나머지 9개는 빈칸이다. 추가로 격리 대상임이 분명한 cusum-3의 PFMEA 두 행만 임시 복사본에서 제거해도 종료0이며 이전 HTML을 교체한다. links.get(..., ())가 누락을 숨긴다. T266과 화면 명세는 사건 ID마다 PFMEA 행 연결을 요구하지만 기존 테스트는 product==a인 사건으로 범위를 좁혀 검사한다. | 적어도 고장 뒤 첫 정지 a의 필수 PFMEA 연결 누락은 검출해 부분 화면을 성공으로 내지 않는다. **명세 이견:** 14단계의 격리 범위는 a에만 존재하는 반면 T266은 모든 사건 ID라고 한다. 조기·수리 뒤 정지는 해당 없음과 이유를 표시할지, PFMEA 관측 연결은 계속 만들지 명확히 정한다. 기대표를 구현에 맞춰 임의 변경하지 말고 전체 사건 ID와 필수 연결의 유실을 검증한다. |

M1·M2는 유효한 다른 단계 결과를 소비하지 못하는 미공개 제한이고, M3는 설명·연결 내용과 명세의 불일치 및 불완전 입력의 무표시 수용이다. 기본 수치 판정 변경·데이터 손실로 과장하지 않고 중간으로 분류했다. 마감·빈도·수정 비용은 심각도에 반영하지 않았다. M3는 고장 전·수리 뒤 정지에도 억지 격리 범위를 만들라는 요구가 아니다.

## 리뷰 020–024 항목별 재판정

| 기존 항목 | 기존 심각도 | 재판정 | 현재 근거 |
| --- | --- | --- | --- |
| R20-H1 | 높음 | 해결 | msa.py:410의 Fraction·정수 ceil/floor. P01의 양·음 규격, g=10^-35, g=10^40에서 정확한 안쪽 한계와 가드 불가. 기본 MSA 3개 보고서도 바이트 재현. |
| R20-H2 | 높음 | 해결 | msa.py:474의 정수 기반 표시 경로. P01에서 1e200이 정확한 긴 문자열로 표시된다. 원본 MSA 테스트 실행 경로에서도 이 항목의 실패가 관측되지 않았다. |
| R20-H3 | 높음 | 해결 | msa.py:348의 cpk/hypot(1,GRR/sigma). P01의 sigma=1e-200, GRR/sigma=0·0.5·2가 독립식과 일치한다. |
| R21-H1 및 리뷰022 유지 항목 | 높음 | 해결 | spc.py:197에서 제곱근을 분리했다. P05의 lambda=1e-20·1e-200·5e-324·1을 750자리 Decimal 식과 17시점 대조했다. 양수 한계를 보존하고 경보가 일치한다. |
| R21-M1 | 중간 | 해결 | spc.py:336·347의 _unique. P25가 방법·모델의 상이값 양 순서와 동일값 중복을 모두 거절하고 직후 정상 입력은 수용한다. |
| R21-M2 | 중간·명세 이견 | 해결 | check_values와 check_replay가 추가됐고 현재 명세에 공개돼 있다. P25는 Cpk5·6에 대응하는 sigma=0.2·1/6, 같은 FAIL 열·다른 측정값을 만든 뒤 정상 replay는 수용, 다른 측정열은 거절함을 확인했다. 임의의 모든 과거 산출물 동일성을 증명한 것으로 확대하지 않는다. |
| R22-M1 | 중간 | 해결 | spc.py:482의 limits 유일성 검사. P06에서 모순 행의 앞·뒤 배치와 같은 값 중복 모두 거절한다. |
| R22-M2 | 중간 | 해결 | spc.py:385의 창 시작·측정 범위 검사. P06의 t=-1 및 length에서 ValueError로 거절하며 이후 정상 replay는 수용한다. |
| R22-M3 | 중간·명세 이견 | 해결 | incident.py:34와 tasks의 products 상한이 65535로 일치한다. P06에서 65536·bool·10^400을 거절한다. 기존 PLC 순환 규칙은 바꾸지 않았다. |
| R23-H1 | 높음 | 해결 | P10의 URL/uRl 외부 참조·없는 ID 거절. P16은 숫자 엔티티를 이용한 외부 참조와 이름공간 변형까지 검사하고 CLI 종료2·기존 HTML 보존을 확인했다. |
| R23-H2 | 높음 | 해결 | contribution_rows가 모든 경보를 순회한다. P09에서 잘못된 z의 경보를 앞·뒤에 넣어 모두 거절한다. |
| R23-M1 | 중간 | 해결 | NaN·Infinity 입력 및 유한 입력의 곱셈 오버플로를 모두 거절한다. P09와 P24가 입력·결과 유한성을 나눠 확인했다. R24-H1과 중복 집계하지 않는다. |
| R23-M2 | 중간 | 해결 | PFMEA item과 evidence를 정적 표에 출력한다. P10의 마크업 포함 reference가 실행 태그 없이 원문 셀로 복원된다. 원본 evidence 표 열과 현재 필수 열 목록도 일치한다. |
| R23-M3 | 중간 | 해결 | 이동량별 검출률과 관리도 시계열의 정적 수치 표가 있다. P10에서 중간 c_plus 변경값이 정적 td에 그대로 나타난다. |
| R23-M4 | 중간 | 해결 | P10에서 모든 Cpk/Ppk 빈칸일 때 유효한 Cpk 없음·표본 부족을 표시한다. 새 M1은 별도 MSA pct_grr 경로다. |
| R23-M5 | 중간·명세 이견 | 해결 | tasks 입력 표에 incident_lamp_pfmea.md가 명시됐다. P20은 명시 입력으로 생성에 성공했다. 파일 존재와 내부 사건 연결 완전성은 별개이며 후자는 새 M3다. |
| R24-H1 | 높음 | 해결 | dashboard.py:304가 기여값과 합계의 유한성을 z 대조 전에 검사한다. P24에서 유한 가중치 +1e308/-1e308·특징2·z1은 종료2, 이전 HTML 보존. 정상 자료로 되돌리면 종료0·제출 HTML과 바이트 동일이다. |

위 수정 설명에 동의한다. 각 판정은 코드 읽기뿐 아니라 위 반례 탐색 이후 내렸다. gpt-log의 별도 반박은 없었으며, 수정 완료 주장 전체를 근거 없이 그대로 인용하지 않았다.

## 중단된 025 P11–P14 직접 재검증

| 항목 | 판정 | 근거와 한계 |
| --- | --- | --- |
| P11 XML 주석/HTML 해석 차이 | 해결 | 기존 공격 문자열을 CLI로 실행하면 종료2·이전 HTML 불변이다. check_svg는 선언을 제외한 <!·<?를 거절한다. P16의 주석 종료 변형·CDATA·처리 지시·DOCTYPE/ENTITY·숫자 엔티티 URL·접두 이름공간 script·다른 이름공간도 거절한다. 정상 XML 선언은 제거하며 이스케이프된 text는 통과한다. 새 우회 실행 태그는 이 범위에서 찾지 못했다. 브라우저 실행까지 검증한 주장은 하지 않는다. |
| P12 선택 없음 | 해당 반례 해결 | overview_section에서 선택 방법의 holdout 행이 없어도 선택 없음 문구를 표시한다. 기존 P12 통과. 경보가 없는 유효한 replay까지 처리하는지는 별도이며 새 M2로 남긴다. |
| P13 EWMA 상·하한 | 해결 | P13이 line_chart에 실제 전달한 시계열을 검사했다. 중심 0.09518934133333334, 마지막 폭 1.1476662059에 대해 하한 -1.0524768645666667·상한 1.2428555472333334이며 중심선도 있다. 폭 자체를 상한으로 잘못 그리는 문제는 해소됐다. |
| P14 수리 시드 누출 | 해결 | P14가 수리열과 학습 정상열이 실제로 같은 시드에서 같은 값임을 먼저 확인한 뒤 거절을 검증했다. P21은 story/summary 각각의 seed+1000000이 train·validation·holdout에 겹치는 6개 경우를 거절하고 인접한 비중복 시드를 수용했다. |

## 사전 기준·계산·단계 연결 검증

- **결과 후 조정:** 각 최초 구현 커밋의 msa·spc·incident 설정과 현재 설정을 비교했다. SPC의 anomaly_replay 경로 추가를 제외하면 수치·시드·조정값은 동일하다(P15). 지정 이력에서 결과 후 기준 완화나 홀드아웃 재선택 경로는 발견하지 못했다. 다만 명세와 구현이 같은 최초 커밋에 들어 있어 Git만으로 결과 확인보다 먼저 기준을 정한 시각까지 독립 입증할 수는 없다. decisions의 사전 고정 기록과 모순되는 변경은 없다.
- **선택과 평가 분리:** MSA는 개발 집계에서 가드를 고른 뒤 선택한 가드만 홀드아웃에 적용하고 작업자 민감도는 선택에 쓰지 않는다. P03에서 홀드아웃 시드만 바꿔 개발 행·선택 불변을 확인했다. SPC는 정상 학습 시나리오에서만 한계를 추정하고 검증 분할에서만 선택한다. P22의 학습 고장값 변경·홀드아웃값 변경·clean_limits 변경이 각각 추정·선택에 새지 않았다. 14단계는 선택하지 않고 비교한다.
- **MSA 독립 계산:** 제출 study의 270개 값을 Fraction으로 읽어 SS 네 항, 자유도, MS, 분산 성분, %GRR, %공차, ndc를 다시 계산했다. F 꼬리는 구현의 연분수 대신 정수 매개변수 베타 CDF의 이항합으로 계산했다. good/marginal/poor의 %GRR 13.3878/36.5763/64.6174, p_int 0.691563/0.346478/0.502165가 보고서와 일치했다. 비합침 연구를 큰 상수만큼 이동하고 7배 확대했을 때 SS·분산은 정확히 49배다(P02).
- **가드 분모:** 보고서의 오합격·오불합격률을 각각 true_defects·true_good으로 재계산했다. 추가 5제품 반례는 참 불량3·양품2이므로 1/3·1/2이며 전체5로 나누지 않았다(P03). 미세 가드·음수 규격·큰 가드와 높은 Cpk도 확인했다(P01).
- **SPC 독립 계산:** 학습 정상 시나리오로 한계 8항을 별도 산식으로 계산해 repr까지 대조했다. Xbar-R, 런 규칙, EWMA, CUSUM을 별도 반복문으로 실행하고 검증·홀드아웃 8개 방법 행의 검출률·early·missed·지연 비용·검출 사례 평균 지연·측정당 및 판단당 오경보·제한 평균·no_alarm·이동량별 검출률을 비교했다(P04). 전부 일치했다. 578개 비정렬 경계 구간에서 부분군 판단 수를 실제 t%5==4 위치 개수와 대조했다(P05).
- **11→13→14:** 11단계 측정값·설정·reference 검사와 13단계의 repr 한계를 사용하는 14단계 checked_limits를 확인했다. P06·P25의 중복·범위·다른 원측정 거절을 통과했다. 기본 재현은 11단계부터 14단계까지 순서대로 이어져 모든 제출 파일과 바이트 동일했다.
- **10 위의 14 복구:** 코일10, 알람26의 기존 즉시 알람 뒤 우선순위, pc_stop 해제 후 새 reset 상승, feed_hold와 remove_product 추가만 기존 3개 파일에 들어 있다. P07은 제품24개에 정지0·1·9·10·23을 강제로 배치했다. 조기 정지 후 F 유지, 첫 고장 뒤 정지 다음부터 N 사용, 판정 없는 제거, 알람 다음 해제, 제거 뒤 대기·리셋·재가동, 마지막 제품 정지 후 완료가 성립한다. 소켓과 메모리의 값·처분이 같고 OK+NG+aborted=24다. 기본 400제품 실행도 max_cycles 안에서 완료했다.
- **사건 요약 독립 계산:** Flow/Tracker를 쓰지 않는 별도 상태·검출 반복문으로 기본 100시드·세 방법을 계산했다(P08). 검출 23/100/100, 평균 지연 95.4348/6.4800/5.6900, 평균 의심 통과 172.4500/6.4300/5.6300과 모든 summary_scope 비율이 일치했다. 포착 실행률 분모는 전체 실행, 제품 포착률은 합산 의심 통과, 범위 평균은 범위가 있는 실행으로 각각 구분했다.
- **대시보드:** 정적 HTML의 표·8개 절·PLC 8시나리오 자료와 이스케이프 경로를 확인했다. JSON의 꺾쇠·&·U+2028/2029는 안전한 이스케이프 뒤 원문으로 복원된다. JavaScript는 textContent를 쓰며 외부 스크립트·스타일 로드는 없다. 새 XML/HTML 반례에 대한 결과는 P16과 위 표의 범위다. 기여값의 원본 비유한 값·계산 오버플로·나중 경보 오류를 거절한다(P09·P24). M1–M3를 제외한 검증을 대시보드의 모든 입력에 대한 안전성 증명으로 확대하지 않는다.

## README·보고서·보존 대조

P23은 11단계 비교 6행, MSA 결과·가드·작업자 민감도 9행, SPC 비교 8행, 사건 story 3행·요약 3행·범위 7행, 합계 **36행을 보고서 열과 셀 단위로 대조**했다. 모두 일치한다. README의 정수/소수 문자열, 빈칸, 판단 간격·이동량별 열 순서까지 비교했다.

첫 화면의 5단계 3:2 선택·확인, 6단계 기준 충족 방식 없음, 7a 기준 없이 수치 보고, 8단계 PF-01 충족/PF-02·06 미충족, 9단계 2-1-1·확인, 10단계 8시나리오, 11단계 logistic·홀드아웃 확인·수렴 미달, 12단계 가드 확인, 13단계 선택 없음, 14단계 비교만, 15단계 표시 전용을 앞선 각 절과 대조했다. 결과 요약의 모순은 찾지 못했다. 9단계의 양품 UPH와 통과 UPH는 서로 다른 지표임을 구분했다.

README 12–15단계는 실제 경험으로 주장하지 않고 합성·모의임을 반복해서 밝힌다. MSA의 작은 부품 표본, K1 근사, 작업자 독립 잡음, SPC의 결함 혼합 한계·관측 제한 평균, 사건 수리 효과의 가정과 단일 스테이션 한계도 공개돼 있다. 다만 15단계의 사건 연결 설명은 M3처럼 실제 모든 ID에 구현돼 있지는 않다.

- 기준 커밋에 존재한 src/tests/recipes/data/reports 파일 171개 중 지정 diff에서 바뀐 것은 허용된 src/plc.py·src/modbus.py·src/station.py뿐이다(P15). 기존 테스트 파일 16개·test 메서드 367개는 무수정이다. 기준의 recipes/data/reports 파일 109개도 Git 내용상 변경이 없다.
- 12–15단계 새 파일 자체에 대한 후속 리뷰 수정은 위 보존 대상과 구분했다. SPC replay 경로·provenance 추가와 안전성 보강은 공개된 수정이며 사전 선택 수치 변경이 아니다.
- P20은 임시 폴더에 src/recipes/data를 복사하고, README 순서보다 앞 단계의 대시보드 선행 입력 4개(capability, PFMEA, line compare, line SVG)는 제출본을 복사했다. 이어 MSA→anomaly→SPC→station all→incident→dashboard를 실제 실행했다. 복사한 선행 4개를 이번에 재생성했다고 주장하지 않는다.
- 기존 보고서 재생성은 anomaly 3개·station 16개, 신규는 MSA 3개·SPC 2개·incident 5개·dashboard 1개다. 합계30개가 바이트 동일이고 dashboard를 한 번 더 생성해도 같았다. 다른 이전 단계 보고서는 Git 보존 확인이며 이번 재생성 검증과 구분한다.
- **브라우저 미검증:** 실제 375/1280px 화면, 테마, 브라우저에서 JavaScript를 끈 상태, 실제 DOM 재생 및 실제 외부 요청 여부를 직접 확인하지 않았다. gpt-log의 기존 브라우저 확인은 구현자 기록이다. 이번은 CLI·정적 HTML·코드·바이트 검증이다.

낮음 기록: T215의 “첫 초과 0”은 계속 식과 모순된다. C+_0=2−0.5=1.5는 한계1.5를 초과하지 않으므로 첫 초과는1, 판단 시작 뒤 경보는9다. Claude의 식 우선 해석을 수용하고 기대표는 고치지 않았다. R22의 제품 상한 축소와 R23의 PFMEA 입력 추가 역시 기술적 해결은 수용하지만 decisions의 “Claude 처리·사용자 승인 전”을 최종 사용자 승인으로 바꾸어 표현하지 않는다.

## 반례 목록

기존 `test_probe_025.py`를 이어 썼다. 기존 P01–P15·P20을 보존하고 P16–P19·P21–P25를 추가했다. P11의 조건부 Chrome 실행은 제거해 이번 검수에서는 브라우저를 호출하지 않는다. **서로 다른 테스트 메서드 25개를 실행했고 22개 통과, 3개 메서드에서 제품 실패(서브테스트 포함 실패 기록4건)**다. P11·P18의 변경 후 재실행은 별도 성공·실패로 중복 집계하지 않는다. 새 출력은 모두 tempfile 안에만 썼다.

| 반례 | 입력 | 예상·명세 근거 | 실제 | 판단 |
| --- | --- | --- | --- | --- |
| P01 | ±규격, g=10^-35·10^40, Cpk1e200·극소 sigma | 정확한 안쪽 한계·안정 계산 | 일치 | 통과 |
| P02 | 제출 연구270값, 비합침 자료를 큰 이동·7배 확대 | SS 분해·분산49배, 독립 베타 확률·지표 일치 | 전부 일치 | 통과 |
| P03 | 참 불량3·양품2, 홀드아웃만 변경 | 분모3/2, 개발·선택 불변 | 1/3·1/2, 불변 | 통과 |
| P04 | 모든 검증·홀드아웃 시나리오, 네 관리도 독립 구현 | 한계·검출·지연·노출·이동량별 지표 일치 | 일치 | 통과 |
| P05 | 최소 양수 등 lambda4종, 판단 구간578개 | Decimal 식·실제 부분군 위치 수와 같음 | 일치 | 통과 |
| P06 | 중복 limits 양 순서·동일값, replay 음수/끝, 제품65536/bool/거대정수 | 거절 뒤 정상 입력 수용 | 일치 | 통과 |
| P07 | 정지0·1·9·10·23, 제품24개, 소켓/메모리 | 조기·수리 뒤·최종 정지의 값·순서·소비 수 일치 | 일치 | 통과 |
| P08 | 100시드의 독립 사건 반복문 | 요약 및 범위별 분모·분자 일치 | 일치 | 통과 |
| P09 | NaN/Infinity, 반대 부호 오버플로, 잘못된 나중 경보 | 기여값 불일치 거절 | 일치 | 통과 |
| P10 | 스크립트 문자열·Unicode·모든 Cpk빈칸·중간 차트값·혼합 URL | 정적 이스케이프·JSON 원문·빈값 표시·참조 거절 | 일치 | 통과 |
| P11 | XML 주석으로 숨긴 HTML script | 종료2·이전 HTML 보존 | 2·보존 | 통과 |
| P12 | 11단계 선택 행을 선택 없음으로 변경 | 결과 표시 | 선택 없음 표시 | 해당 반례 통과 |
| P13 | EWMA 중심≠0인 기본 보고서 | 중심±폭의 상·하한 | 두 시계열 일치 | 통과 |
| P14 | 수리 시드와 학습 정상 시드 중복 | 동일 열 확인 후 평가 거절 | 거절 | 통과 |
| P15 | 기준 파일·각 최초 recipe와 현재 비교 | 허용 변경만, 수치 불변 | 171개 중 허용3개만 변경 | 통과 |
| P16 | 주석·CDATA·PI·ENTITY·엔티티 URL·접두/다른 이름공간 8종, 직후 정상 SVG | 위험 변형 거절·기존 HTML 보존, 선언 제거 후 정상 수용 | 전부 일치, script3개 | 통과 |
| P17 | 실제 MSA로 생성한 3게이지 판정 불가·빈 %GRR | 유효 결과를 표와 상태로 표시 | float('') 오류·종료2 | 실패→M1 |
| P18 | 실제 replay_rows의 임계값 없음·missed 각26행 | 유효한 무경보 상태 표시 | 두 경우 종료2 | 실패2건→M2 |
| P19 | 제출 11개 사건 및 cusum-3 PFMEA 연결 행만 제거 | 연결 범위 명확, 필수 연결 누락을 성공으로 숨기지 않음 | 기본9개 빈칸, 제거본도0·HTML 교체 | 실패→M3 |
| P20 | README 보고서 CLI 전체, dashboard 반복 | 제출30개 원시 바이트 동일·원본 불변 | 30개 동일·원본123개 불변 | 통과 |
| P21 | 수리 story/summary 시드가 세 분할 각각과 중복, 인접 비중복 | 6종 거절·비중복 수용 | 일치 | 통과 |
| P22 | 학습 고장값·홀드아웃값·깨끗한 기준 한계 변경 | 정상 추정·검증 선택에 유입되지 않음 | 불변 | 통과 |
| P23 | README 수치표36행과 원보고서 | 열·문자열·빈칸 일치 | 일치 | 통과 |
| P24 | 유한 입력 반대 부호 오버플로 CLI, 거절 후 정상 | 종료2·기존 HTML 보존, 복구 결과 제출본 동일 | 일치 | 통과 |
| P25 | reference/model 중복·순서·동일값, 같은 FAIL 다른 측정열 | 모순 거절, 값 동일성 별도 검사 | 일치 | 통과 |

P01·P02·P03·P05·P06·P07·P09·P10·P11·P14·P16–P19·P21·P22·P24·P25의 경계·순서·거절 뒤 입력·빈값·중복·이전 모드 조합으로 명세 밖 반례 최소8개를 충족한다.

## 실행 명령과 결과

Python 실행에는 PYTHONDONTWRITEBYTECODE=1을 적용했다. 반례와 자식 CLI에는 PYTHONIOENCODING=utf-8도 적용했다. 시스템 런처·PATH·원본 테스트를 바꾸지 않았다.

**전체 테스트: 지정 런처 한 번, 지정 Python 대안 한 번.**

```powershell
py -m unittest discover -s tests
```

종료1, 출력 원문:

```text
No installed Python found!
```

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest discover -s tests
```

종료1. 결과 끝부분 원문:

```text
----------------------------------------------------------------------
Ran 541 tests in 192.068s

FAILED (failures=132)
T44 seed=42 products=500 generation_seconds=0.130460 judgment_analysis_seconds=0.074306
T44 seed=7 products=200 generation_seconds=0.045380 judgment_analysis_seconds=0.025100
T44 seed=42 all_rows_deepcopy_invariant_seconds=40.776033
T44 seed=7 all_rows_deepcopy_invariant_seconds=7.066570
```

수신된 상세 출력의 AssertionError 형태는 다음과 같다(원문 발췌):

```text
AssertionError: 112 != 0 : No installed Python found!
AssertionError: 112 != 2 : No installed Python found!
AssertionError: 112 != 3 : No installed Python found!
AssertionError: 112 != 0 : b'No installed Python found!\r\n'
AssertionError: 112 != 2 : b'No installed Python found!\r\n'
AssertionError: 112 != 0
AssertionError: 112 != 2
```

원인: test_containment·equipment·evaluate·generate·recipe·restart·retest·rules·summary의 CLI 시험이 내부에서 다시 `py`를 실행한다. 외부 테스트 프로세스를 Python312로 바꾸어도 이 자식 런처는 그대로 실패한다. 수신된 126개 FAIL 상세의 assertion은 모두 반환 코드112이며, 출력 상한으로 나머지6개 상세는 생략됐다. 따라서 132개 상세를 전부 개별 확인했다고 주장하지 않는다. **런처로 식별된 실패는 제품 회귀로 세지 않으며, 전체 테스트 무수정 통과는 미검증**이다. 새로운 12–15단계 모듈의 테스트 실패는 수신 출력에서 관측되지 않았다.

구현자 `handoff/run-logs/v2-freeze-tests.txt`의 별도 기록은 다음과 같으며 이번 직접 검증을 대신하지 않는다:

```text
----------------------------------------------------------------------
Ran 541 tests in 236.789s

OK
```

**기존 025 반례16개와 전체 재현:**

```powershell
py -m unittest handoff/reviews/probes/test_probe_025.py
```

종료1:

```text
No installed Python found!
```

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff/reviews/probes/test_probe_025.py
```

이 호출 시 파일은 기존16개 메서드였다. 종료0. 결과와 재현 출력 원문 발췌:

```text
P01 exact inward limits, large guard, Cpk 1e200: OK
P02 good pct_grr 13.3878 p_int 0.691563
P02 marginal pct_grr 36.5763 p_int 0.346478
P02 poor pct_grr 64.6174 p_int 0.502165
P03 report denominators, 3:2 truth classes, changed holdout: OK
P04 validation xbar_r 0.1417 12.6079
P04 validation xbar_we 0.1250 13.6737
P04 validation ewma_chart 0.2333 7.1114
P04 validation cusum 0.2667 7.1459
P04 holdout xbar_r 0.1167 13.6145
P04 holdout xbar_we 0.1083 14.6953
P04 holdout ewma_chart 0.3667 5.4651
P04 holdout cusum 0.3750 6.0219
P05 tiny EWMA 750-digit reference and 578 decision intervals: OK
P06 duplicate limits both orders, replay bounds, product limits: OK
P07 24 products, stops 0/1/9/10/23, socket=memory, recovery sequence: OK
P08 rule_3_2 {'detected': '23', 'early': '8', 'missed': '69', 'mean_delay': '95.4348', 'mean_suspect_passed': '172.4500', 'mean_stops': '0.4000', 'mean_false_stops': '0.1700'}
P08 ewma_chart {'detected': '100', 'early': '0', 'missed': '0', 'mean_delay': '6.4800', 'mean_suspect_passed': '6.4300', 'mean_stops': '3.4100', 'mean_false_stops': '2.4100'}
P08 cusum {'detected': '100', 'early': '0', 'missed': '0', 'mean_delay': '5.6900', 'mean_suspect_passed': '5.6300', 'mean_stops': '3.4500', 'mean_false_stops': '2.4500'}
P09 R23/R24 NaN, infinity, opposing overflow and later alarm rejection: OK
P10 escaped static cells, round-trip JSON, missing Cpk, chart cells, mixed-case SVG: OK
P13 center 0.09518934133333334 width 1.1476662059 actual lower/upper -1.0524768645666667 1.2428555472333334 plotted [('z', 2.4240050941), ('상한', 1.2428555472333334), ('하한', -1.0524768645666667)]
P15 base protected files 171 only permitted PLC additions; numerical recipes unchanged
P20 src.msa exit=0 byte_equal=3
P20 src.anomaly exit=0 byte_equal=3
P20 src.spc exit=0 byte_equal=2
P20 src.station exit=0 byte_equal=16
P20 src.incident exit=0 byte_equal=5
P20 src.dashboard exit=0 byte_equal=1
.
----------------------------------------------------------------------
Ran 16 tests in 276.560s

OK
P20 reports=30 byte-identical; original files=123 unchanged; dashboard repeated
```

P20이 실제 실행한 자식 명령은 임시 폴더를 cwd로 하여 지정 Python312의 `-B -m`으로 다음 모듈·인자를 순서대로 호출한 것이다. `py` 부분만 런처 대안으로 대체했다.

```text
src.msa recipes/msa_lamp.json
src.anomaly recipes/anomaly_lamp.json
src.spc recipes/spc_lamp.json
src.station recipes/plc_station.json --scenario all
src.incident recipes/incident_lamp.json
src.dashboard --root <TemporaryDirectory> --out reports/dashboard.html
```

**추가8개 반례 실행 명령:**

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff.reviews.probes.test_probe_025.Probe025.test_p16_svg_xml_html_variants_and_recovery handoff.reviews.probes.test_probe_025.Probe025.test_p17_valid_degenerate_msa_reaches_dashboard handoff.reviews.probes.test_probe_025.Probe025.test_p18_valid_replay_without_alarm handoff.reviews.probes.test_probe_025.Probe025.test_p19_incident_links_cannot_silently_disappear handoff.reviews.probes.test_probe_025.Probe025.test_p21_repair_seed_isolation_all_splits handoff.reviews.probes.test_probe_025.Probe025.test_p22_estimation_selection_and_sensitive_limits_isolation handoff.reviews.probes.test_probe_025.Probe025.test_p23_readme_numeric_tables_match_reports handoff.reviews.probes.test_probe_025.Probe025.test_p24_overflow_cli_preserves_output_then_recovers
```

종료1. assertion·결과 발췌(원문):

```text
.FFFF....
AssertionError: 2 != 0 : Valid T192/T250 output must be displayed: 오류: could not convert string to float: ''
AssertionError: 2 != 0 : Valid no-alarm replay must not require an alarm: 오류: 로지스틱 기여값 입력이 모자람
AssertionError: 2 != 0 : Valid no-alarm replay must not require an alarm: 오류: 로지스틱 기여값 입력이 모자람
AssertionError: 0 != 2 : Required T266 true-stop linkage must not silently become blank
----------------------------------------------------------------------
Ran 8 tests in 5.889s

FAILED (failures=4)
P16 eight XML/HTML, entity, namespace and reference variants refused; safe recovery: OK
P17 upstream=0 blank_pct_grr=3 dashboard= 2 stderr= 오류: could not convert string to float: ''
P18 upstream_status= 임계값 없음 rows= 26 dashboard= 2 stderr= 오류: 로지스틱 기여값 입력이 모자람
P18 upstream_status= missed rows= 26 dashboard= 2 stderr= 오류: 로지스틱 기여값 입력이 모자람
P19 submitted incident chains= 11 missing PFMEA= ['ewma_chart-1', 'ewma_chart-2', 'ewma_chart-4', 'ewma_chart-5', 'cusum-1', 'cusum-2', 'cusum-4', 'cusum-5', 'cusum-6']
P19 removed true-stop PFMEA: exit= 0 preserved= False
P21 shifted story/summary overlap with every split refused; adjacent seed accepted
P22 fault-train, holdout and clean-limit mutations do not enter estimation/selection
P23 README independent table-cell/report matches= 36
P24 opposing finite overflow CLI exit=2, old HTML preserved, restored output identical
```

**P11 변경 후 확인·P25 추가 확인:**

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff.reviews.probes.test_probe_025.Probe025.test_p11_svg_xml_comment_is_not_html_comment handoff.reviews.probes.test_probe_025.Probe025.test_p25_reference_duplicates_and_measurement_collision
```

종료0, 출력 원문:

```text
..
----------------------------------------------------------------------
Ran 2 tests in 0.470s

OK
P11 CLI 2 previous_preserved True
P25 reference/model duplicate orders rejected; identical FAIL series, changed values refused
```

**P18 임계값 경계 보강 후 재확인:** 무경보 임계값을 최대 양자화 점수+10000에서 명세 후보 형태인 최대 점수+1(9963, 확률0.9963)로 낮춰 같은 실패가 남는지 확인했다.

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe' -m unittest handoff.reviews.probes.test_probe_025.Probe025.test_p18_valid_replay_without_alarm
```

종료1. 결과 원문 발췌:

```text
FF
AssertionError: 2 != 0 : Valid no-alarm replay must not require an alarm: 오류: 로지스틱 기여값 입력이 모자람
AssertionError: 2 != 0 : Valid no-alarm replay must not require an alarm: 오류: 로지스틱 기여값 입력이 모자람
----------------------------------------------------------------------
Ran 1 test in 1.539s

FAILED (failures=2)
P18 upstream_status= 임계값 없음 rows= 26 dashboard= 2 stderr= 오류: 로지스틱 기여값 입력이 모자람
P18 upstream_status= missed rows= 26 dashboard= 2 stderr= 오류: 로지스틱 기여값 입력이 모자람
```

최종 `git diff --check`는 종료0이며 공백 오류가 없다. Git의 LF→CRLF 안내만 출력됐다. 검수자의 저장소 변경은 이 리뷰와 `handoff/reviews/probes/test_probe_025.py`뿐이다. 원본 테스트·제품 코드·보고서·기대표는 수정하지 않았다. 최종 FIX의 근거는 환경 실패가 아니라 위 중간3건이다.

VERDICT: FIX
