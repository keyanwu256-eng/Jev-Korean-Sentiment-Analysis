# 증거 자료 안내

## 공식 API 접입 테스트

`official_integration_tests.txt`는 모의 HTTP 응답을 이용한 계약 및 UI 테스트 기록이다. 실제 공식 Jev를 호출하지 않았으며 공식 모델의 정확도나 실제 계정 인증 성공을 증명하지 않는다. 공식 라이브 실행은 본인 TypeSafe 키로 별도 확인해야 한다. 현재 로컬 검증은 `verify_project.py`가 명시적으로 로컬 OpenJevX를 선택해 실행한다.

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
