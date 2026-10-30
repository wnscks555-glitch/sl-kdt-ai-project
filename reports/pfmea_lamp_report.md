# 합성 공정 PFMEA 연습

합성 공정의 PFMEA 연습이며 실제 공정, 고객 영향, 실무 PFMEA가 아니다.

생성 데이터의 확률은 가정이며 실제 설비 진단 근거가 아니다.

최초 FAIL률은 원인 발생률이 아니고, 설비 정지율은 제품 불량 검출률이 아니다.

연결됨은 참조가 이어졌다는 뜻이고 관리 효과의 검증이 아니다. 효과 판정은 현재 관리의 성능 확인이며 개선 전후 비교가 아니다. 합성 수치는 참고 관측치이고 점수 환산표가 아니다.

## PF-01 결함품이 LEAK에서 PASS

- 유형: product
- 대상: LEAK
- 기능: LEAK 검사가 기밀 규격 초과 제품을 걸러 낸다
- 영향(가정): 기밀 규격을 벗어난 제품이 다음 공정으로 넘어감 (합성 가정)
- 원인(가정): 규격 초과 정도가 작아 측정값이 상한 안에 들어옴 (합성 가정)
- 예방 관리: 없음
- 검출 관리: LEAK 측정값을 규격과 비교해 자동 판정
- 점수: 점수 대기
- 근거 상태: 연결됨
- 근거 참조: metric:leak_defect_first_fail;metric:defect_escape
- 근거 설명: 결함 표식이 있는 제품의 LEAK 판정과 최종 완료 여부를 합성 실행에서 직접 센다
- 조치: PASS/FAIL 입력을 측정값 판정으로 교체
- 조치 상태: 효과 확인
- 조치 목적: 결함품이 LEAK 최초 측정에서 FAIL로 판정되게 한다
- 조치 전 관리: 6단계 PASS/FAIL 입력
- 조치 후 관리: 7a 측정값 판정 (T89)
- 조치 근거: test:tests/test_measurement.py::JudgmentTests::test_t89_boundaries_are_pass_and_raw_value_is_kept
- 잔여 위험: 상한 안으로 들어온 결함품은 측정 판정으로 걸러지지 않는다
- 사전 기준: metric:leak_defect_first_fail >= 0.80
- 관측값: 0.8893
- 효과 판정: 충족

## PF-02 측정 평균이 위로 이동

- 유형: equipment
- 대상: LEAK
- 기능: LEAK 설비가 치우침 없이 측정한다
- 영향(가정): 정상품이 FAIL로 보류되고 FAIL 기반 정지가 늦어짐 (합성 가정)
- 원인(가정): 설비 상태 변화로 측정 평균이 이동 (합성 가정)
- 예방 관리: 없음
- 검출 관리: 최근 3건 중 2건 FAIL이면 설비 정지
- 점수: 점수 대기
- 근거 상태: 연결됨
- 근거 참조: metric:fault_stop_run;metric:fault_no_stop_run;metric:fault_stop_delay;metric:normal_stop_rate
- 근거 설명: 고장을 넣은 설비의 정지 여부와 정상 설비의 오탐 정지를 함께 본다
- 조치: 정지 뒤 재가동 결과 기록
- 조치 상태: 효과 확인
- 조치 목적: 고장 설비가 실행 안에서 정지되게 한다
- 조치 전 관리: 4단계 정지 뒤 재가동 없음
- 조치 후 관리: 5단계 재가동 기록 (T52)
- 조치 근거: test:tests/test_restart.py::JudgeTests::test_t52_stop_restart_resume
- 잔여 위험: 값이 규격 안에 머무는 평균 이동은 FAIL 기반 규칙으로 늦게 드러난다
- 사전 기준: metric:fault_stop_run >= 0.95
- 관측값: 0.9333
- 효과 판정: 미충족

## PF-03 앞 공정 누락 입력

- 유형: record
- 대상: ALL
- 기능: 공정 순서대로 기록한다
- 영향(가정): 제품 이력이 실제 순서와 달라짐 (합성 가정)
- 원인(가정): 입력 순서 실수 (합성 가정)
- 예방 관리: 없음
- 검출 관리: RULE_SEQ가 해당 행을 거절
- 점수: 점수 대기
- 근거 상태: 연결됨
- 근거 참조: rule:RULE_SEQ;reason:SEQ_SKIP;test:tests/test_recipe.py::RecipeProcessTests::test_t13_skipped_step_is_rejected_then_correct_next_step_is_accepted;test:tests/test_measurement.py::GeneratorTests::test_t107_injections_match_rejections
- 근거 설명: 데이터 기록 오류를 거절하는 규칙과 테스트다. 물리 불량 예방의 근거가 아니다
- 조치: -
- 조치 상태: -
- 조치 목적: -
- 조치 전 관리: -
- 조치 후 관리: -
- 조치 근거: -
- 잔여 위험: -

## PF-04 다른 모델의 공정 입력

- 유형: record
- 대상: ALL
- 기능: 모델의 레시피 공정만 기록한다
- 영향(가정): 제품 이력에 레시피 밖 공정이 남음 (합성 가정)
- 원인(가정): 모델 혼동 (합성 가정)
- 예방 관리: 없음
- 검출 관리: RULE_RECIPE가 해당 행을 거절
- 점수: 점수 대기
- 근거 상태: 연결됨
- 근거 참조: reason:RECIPE_UNKNOWN_STEP;test:tests/test_measurement.py::GeneratorTests::test_t107_injections_match_rejections
- 근거 설명: 데이터 기록 오류를 거절하는 규칙과 테스트다. 물리 불량 예방의 근거가 아니다
- 조치: -
- 조치 상태: -
- 조치 목적: -
- 조치 전 관리: -
- 조치 후 관리: -
- 조치 근거: -
- 잔여 위험: -

## PF-05 결함품이 재검사에서 PASS

- 유형: product
- 대상: LEAK
- 기능: 재검사가 결함품을 다시 걸러 낸다
- 영향(가정): 한 번 FAIL한 결함품이 다음 공정으로 넘어감 (합성 가정)
- 원인(가정): 재검사가 새 측정이라 규격 안 값이 나올 수 있음 (합성 가정)
- 예방 관리: 없음
- 검출 관리: 재검사 한도 초과 FAIL이면 폐기
- 점수: 점수 대기
- 근거 상태: 연결됨
- 근거 참조: metric:leak_defect_retest_pass;metric:normal_reject
- 근거 설명: 재검사로 통과한 결함품과 보류·폐기된 정상품을 함께 봐야 재검사의 득실을 판단할 수 있다
- 조치: 재검사 확률 대안 3조건 비교
- 조치 상태: 완료
- 조치 목적: 재검사를 줄일 때 결함품 통과와 정상품 손실이 어떻게 달라지는지 본다
- 조치 전 관리: 재검사 확률 0.70 단일 조건
- 조치 후 관리: 대안 비교 보고서 (T128)
- 조치 근거: test:tests/test_pfmea.py::AlternativeTests::test_t128_alternatives
- 잔여 위험: -

## PF-06 유출품이 후보 목록에서 누락

- 유형: product
- 대상: ALL
- 기능: 정지 뒤 의심 제품 후보 목록을 만든다
- 영향(가정): 의심 제품을 다시 확인하지 못함 (합성 가정)
- 원인(가정): 정지 전에 통과한 유출품이 후보 범위 밖에 있음 (합성 가정)
- 예방 관리: 없음
- 검출 관리: 정지별 격리 후보 보고서. 자동 격리가 아니며 제품 상태를 바꾸지 않는다
- 점수: 점수 대기
- 근거 상태: 연결됨
- 근거 참조: report:eval_lot_dev_containment:since_restart:capture_rate
- 근거 설명: 6단계 합성 평가의 유출품 포착률이다. 7a 측정 설정의 결과가 아니다
- 조치: 정지별 후보 목록 보고서
- 조치 상태: 효과 확인
- 조치 목적: 유출품 대부분이 후보 목록에 들어가게 한다
- 조치 전 관리: 5단계 격리 보고서 없음
- 조치 후 관리: 6단계 --containment (T70)
- 조치 근거: test:tests/test_containment.py::ScopeTests::test_t71_restart_splits_the_segment
- 잔여 위험: 재가동 뒤 전체를 후보로 잡아 후보 수가 많고 정밀도가 낮다
- 사전 기준: report:eval_lot_dev_containment:since_restart:capture_rate >= 0.90
- 관측값: 0.8525
- 효과 판정: 미충족

## 지표

| 지표 | 범위 | 분자 | 분모 | 값 |
| --- | --- | --- | --- | --- |
| metric:defect_escape | 전체 흐름, 실행 끝 상태 | 16 | 307 | 0.0521 |
| metric:all_defect_first_fail | 모든 검사 | 350 | 398 | 0.8794 |
| metric:leak_defect_first_fail | LEAK | 273 | 307 | 0.8893 |
| metric:leak_defect_retest_pass | LEAK | 49 | 192 | 0.2552 |
| metric:normal_reject | 전체 흐름, 실행 끝 상태 | 47 | 14693 | 0.0032 |
| metric:fault_stop_run | 고장 설비 | 28 | 30 | 0.9333 |
| metric:fault_no_stop_run | 고장 설비 | 2 | 30 | 0.0667 |
| metric:fault_stop_delay | 고장 설비, 첫 정지까지 | 1751 | 28 | 62.5357 |
| metric:normal_stop_rate | 고장 키에 없는 모든 설비, 실행 전체 | 20 | 32205 | 0.0006 |

## 재검사 대안 비교 (합산 비교, 제품 짝 비교 아님)

| 조건 | 지표 | 분자 | 분모 | 값 |
| --- | --- | --- | --- | --- |
| current | defect_escape | 16 | 307 | 0.0521 |
| current | leak_defect_retest_pass | 49 | 192 | 0.2552 |
| current | normal_reject | 47 | 14693 | 0.0032 |
| current | all_defect_first_fail | 350 | 398 | 0.8794 |
| half | defect_escape | 4 | 307 | 0.0130 |
| half | leak_defect_retest_pass | 16 | 80 | 0.2000 |
| half | normal_reject | 86 | 14693 | 0.0059 |
| half | all_defect_first_fail | 322 | 364 | 0.8846 |
| none | defect_escape | 1 | 307 | 0.0033 |
| none | leak_defect_retest_pass | 0 | 0 | - |
| none | normal_reject | 146 | 14693 | 0.0099 |
| none | all_defect_first_fail | 306 | 344 | 0.8895 |
