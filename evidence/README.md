# 증거 자료 안내

## 사용자가 제공한 화면의 오류 사례

`error_cases.json`은 대화에 제공된 스크린샷에서 표시값을 수동 전사한 3개 사례다. 원본 이미지와 다운로드 JSON은 저장소에 없으며, 누락된 값은 null로 남겼다. 새 추론이나 정밀 로그가 아니다. 원문·사람 해석·부분 실패 구분은 [ERROR_CASES.md](../ERROR_CASES.md)를 참고한다. 이 사례들로 일반 정확도를 계산하지 않는다.

## 최신 한국어 주 분석 및 Jev 비교

- `korean_comparison.json`: 사전 고정한 명확한 한국어 18개를 두 모델로 실제 분류한 원시 결과. 혼합/반어 6개 및 알려진 오류 사례는 별도 기록. 새 모델 18/18, OpenJevX 8/18은 작은 자가 작성 테스트의 결과이며 일반 성능으로 확대할 수 없다.
- `korean_tests.txt`: 실제 로컬 모델을 이용한 7개 기능 테스트. 마지막 문장·중립과 혼합 관찰 분리·불확실성·입력 잘림·기록·대조 실패 처리 확인.
- `korean_sample_result.json`, `korean_sample_history.csv`: 최신 두 모델 실제 성공 결과와 CSV 내용. 테스트 로그의 `test comparison failure`는 주 모델 결과가 보존되는지 확인하기 위해 의도적으로 주입한 예외다.
- `verification.json`: 최신 검증 상태와 코드 해시.
- `hotel_interpretation_result.json`: 실제 호텔 혼합 리뷰의 전체 neutral, 문장별 긍정·부정 공존, 마지막 문장 negative 및 낮은 확률의 Jev 원시 출력. 원시 라벨은 유지했다.
- `openjevx_verification_legacy.json`, `current_app_results.json`, `sample_history.csv`, `sample_result.json`: 개선 이전의 OpenJevX 단일 모델 검증 및 샘플. 최신 주 모델 출력으로 간주하지 않는다.

기존 Notebook 실험, 초기 화면 및 DLL 오류 기록은 아래에 개선 과정의 과거 증거로 보존한다.

## 기존 실험 자료

- `notebook_recorded_results.json`: 기존 Notebook 셀 10(0부터 센 번호)의 저장된 비교 출력. 참고 정답은 셀 12에서 추출했다. 10개, 일치 6개, 전체 정답 일치 4개, 마지막 평가의 동일 정답 일치 3개를 재집계했다.
- `notebook_results.md`, `notebook_results.csv`: 위 자료를 읽어 생성한 10개 리뷰 비교표. 모델을 새로 실행해 얻은 값이 아니다.
- `notebook_agreement.png`, `notebook_accuracy.png`: Notebook 셀 11, 13에 저장된 PNG를 그대로 추출했다. 이미지가 저장된 시점의 실험이며 현재 웹 앱 화면이 아니다.

## 2026-11-17 오전 실제 확인 및 오후 복구

- `app_initial.png`: 실제 실행 중인 로컬 Streamlit 첫 화면. 검증용 서버 포트는 8502다.
- `verification.json`: 오후 독립 환경에서 실제 모델과 앱 흐름이 통과한 최종 결과. 상태는 `PASS`다.
- `model_load_failure.txt`: NumPy C 확장 로딩 실패 traceback. 개인 홈 경로는 마스킹했다.
- `code_integrity_excerpt.txt`: Windows Code Integrity에서 관찰한 차단 사건의 요약. 개인 경로는 포함하지 않았다.

`model_load_failure.txt`와 Code Integrity 요약은 오전의 복구 전 기록이다. 오후에는 `.venv`에 공식 PyPI 패키지를 설치한 뒤 실행에 성공했다. `current_app_results.json`은 실제 10개 리뷰의 현재 앱 추론, `sample_result.json`과 `sample_history.csv`는 실제 샘플 분석에서 얻었다. 브라우저 성공 화면은 사용자 Esc로 자동 조작이 중단되어 아직 포함하지 않았다. 초기 화면과 자동 테스트 증거를 구분한다.
