# Streamlit 앱 실행

Python 3.11 환경에서 실행합니다.

Windows에서는 `Setup_Jev.bat`를 처음 한 번 실행하여 프로젝트 전용 `.venv`와 패키지를 준비합니다. 설치가 끝나면 `Start_Jev.bat`를 더블 클릭하세요. 이 개발 PC의 `.venv`는 2026-11-17에 설치 및 실제 모델 검증을 완료했습니다.

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

브라우저에서 http://localhost:8501 을 엽니다.
`Start_Jev.bat`는 프로젝트 폴더의 `.venv`를 사용합니다. 사용 중에는 시작 창을 닫지 마세요. `CONNECTING`이면 서버 연결이 끊긴 상태이므로 시작 파일을 실행하고 브라우저를 새로고침하세요. 기존 Conda 환경은 DLL 차단 이력이 있으므로 이 프로젝트는 새 독립 환경을 사용합니다.

## 기능

- 한국어 원문 주 분석: Horizon-Labs/multilingual-sentiment-small (한국어 지원 다국어 모델)
- OpenJevX는 별도 대조 분석이며 왼쪽 체크박스로 켜고 끌 수 있습니다.
- 마지막 문장은 실제 추출 후 별도 분석합니다. 중립과 불확실 판단을 구분합니다.
- 첫 실행 시 주 모델 약 300MB를 `runtime/model_cache`에 받습니다. 모든 추론은 로컬이며 공식 키나 API 요금이 없습니다.
- 한국어 리뷰의 전체 감성과 마지막 평가 비교
- 긍정·부정·혼합 리뷰 예시
- 감성 확률 표시
- 세션 내 최대 50개 분석 기록
- CSV 및 JSON 다운로드

첫 분석에는 약 600MB 모델을 다운로드하며 이후 캐시를 사용합니다. 공개 모델이므로 HF_TOKEN은 필수가 아닙니다. 토큰을 코드에 저장하지 마세요.

분석 기록은 세션 종료 시 사라질 수 있으므로 필요한 결과는 다운로드하세요. 한국어 분류 정확도는 별도로 검증하지 않았으며, 확률은 정확도를 보장하지 않습니다. 마지막 평가 역시 모델에 전달하는 질문 기준이며 마지막 문장만 따로 추출하는 방식은 아닙니다.
