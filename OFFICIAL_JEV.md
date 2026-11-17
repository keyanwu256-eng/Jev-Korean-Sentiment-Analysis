# 공식 Jev 연결 안내

**작성자: 오가암**

공식 TypeSafe Jev 모드를 추가했다. 기존 커뮤니티 OpenJevX 모드도 선택할 수 있으며, API 실패 시 다른 모델로 몰래 전환하지 않는다.

## 사용 방법

1. `Start_Jev.bat`로 실행하고 `http://localhost:8501`을 연다.
2. 왼쪽에서 **공식 Jev API**를 선택한다(기본 선택).
3. [공식 TypeSafe 콘솔](https://console.typesafe.ai)에서 본인 계정의 API 접근 권한과 키를 준비한다. Hugging Face 토큰은 사용할 수 없다.
4. 앱의 **TypeSafe API 키** 비밀번호 입력란에 붙여 넣는다. 이 값은 현재 세션에 사용하며 분석 결과·CSV·JSON에 넣지 않는다. 키를 채팅이나 GitHub에 올리지 않는다.
5. 모델 식별자를 확인한다. 기본값은 공식 문서의 예시에 나온 `jev-1.13.0`이다. 계정에서 지원하지 않으면 콘솔에서 확인한 모델 식별자로 바꾼다. `jev-latest` 사용 시 실제 반환 모델도 기록한다.
6. 리뷰가 TypeSafe 서버로 전송되고 사용 요금이 생길 수 있다는 체크박스를 확인하고 분석을 누른다.
7. 결과의 모델 출처가 `typesafe_official`인지 확인하고 JSON을 다운로드한다. `openjevx`는 로컬 모델 결과다.

브라우저와 로컬 서버 간에는 이 개발 앱의 HTTP 연결을 사용하므로 개발 PC의 localhost에서만 사용한다. 비밀번호 입력란은 화면에서 값을 가릴 뿐 암호화 저장소를 뜻하지 않는다. 공유 PC에서 사용 후 페이지를 닫는다.

## 키를 반복 입력하지 않으려면

프로젝트 폴더의 `.streamlit/secrets.toml.example`을 참고해 본인 컴퓨터에서만 `.streamlit/secrets.toml`을 만든다. `TYPESAFE_API_KEY` 값에 키를 설정한다. 또는 서버 실행 환경의 동명 환경변수를 설정한다. 앱은 화면 입력 → 환경변수 → Streamlit secrets 순으로 사용한다.

실제 `secrets.toml`과 `.env`는 `.gitignore`로 제외한다. 예제 파일에는 실제 키를 넣지 않는다. 기록이나 내보내기에는 API 키를 포함하지 않는다.

## 구현과 검증 범위

- `POST https://api.typesafe.ai/v1/systemone`에 Bearer 인증, 모델·리뷰·두 Choice 질문을 전송한다.
- 60초 타임아웃, 자동 재시도 없음. 오류 후 재실행 전 계정 사용 내역을 확인한다.
- 응답의 분류 후보·확률·confidence를 검증하며, 오류 응답 본문과 인증 헤더는 화면·로그에 출력하지 않는다.
- 모델 출처, 요청 모델, 반환 모델(응답에 있는 경우)을 기록한다. 공식 confidence와 선택 후보 확률은 같다고 가정하지 않는다.
- `python -m unittest test_jev_api -v`는 HTTP 응답을 모의 처리하는 6개 접입/오류/UI 테스트다. 유료 API 호출을 하지 않으며 공식 모델 성능 검증이 아니다.
- **개발 중 실제 TypeSafe 키를 제공받지 않았으므로 공식 API의 라이브 실행은 아직 미검증이다.** 기존 Notebook 및 로컬 실험 결과를 공식 결과라고 주장하지 않는다. 본인 키로 성공한 공식 JSON을 저장해야 공식 실행 증거가 생긴다.

## 공식 참고 자료

- [TypeSafe Quick start — HTTP 요청과 Raw response](https://docs.typesafe.ai/introduction/quickstart)
- [Choice 응답과 confidence](https://docs.typesafe.ai/primitives/choice)

키 준비 또는 계정 접근 승인은 계정 소유자가 직접 수행한다. 이 기능을 추가했다는 사실만으로 수업에서 요구한 공식 실행 증거가 자동으로 충족되는 것은 아니다.
