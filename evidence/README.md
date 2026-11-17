# 증거 자료 안내

## 기존 실험 자료

- `notebook_recorded_results.json`: 기존 Notebook 셀 10(0부터 센 번호)의 저장된 비교 출력. 참고 정답은 셀 12에서 추출했다. 10개, 일치 6개, 전체 정답 일치 4개, 마지막 평가의 동일 정답 일치 3개를 재집계했다.
- `notebook_results.md`, `notebook_results.csv`: 위 자료를 읽어 생성한 10개 리뷰 비교표. 모델을 새로 실행해 얻은 값이 아니다.
- `notebook_agreement.png`, `notebook_accuracy.png`: Notebook 셀 11, 13에 저장된 PNG를 그대로 추출했다. 이미지가 저장된 시점의 실험이며 현재 웹 앱 화면이 아니다.

## 2026-11-17 실제 확인

- `app_initial.png`: 실제 실행 중인 로컬 Streamlit 첫 화면. 검증용 서버 포트는 8502다.
- `verification.json`: 실제 AppTest 및 모델 로딩 시도의 결과. `BLOCKED_MODEL_LOAD`는 분석 실패 상태이며 통과를 뜻하지 않는다.
- `model_load_failure.txt`: NumPy C 확장 로딩 실패 traceback. 개인 홈 경로는 마스킹했다.
- `code_integrity_excerpt.txt`: Windows Code Integrity에서 관찰한 차단 사건의 요약. 개인 경로는 포함하지 않았다.

성공한 현재 분석 화면과 다운로드 파일은 이번 검사에서 생성하지 못했으므로 포함하지 않았다. 환경 복구 후 저장소에서 `python verify_project.py`를 실행해 현재 모델 JSON·샘플 CSV·검증 결과를 생성하고 성공 화면을 추가해야 한다.
