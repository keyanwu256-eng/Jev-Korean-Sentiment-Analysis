import csv
import importlib.util
import io
import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta

import streamlit as st
from huggingface_hub import hf_hub_download
from huggingface_hub.errors import LocalEntryNotFoundError
from jev_api import DEFAULT_MODEL, JevAPIError, decide_official

REPO_ID = "muthuishere/openjevx"
MODEL_REVISION = "5399cb82a1eafad35575a6eaff5e2c5de5a8fc7e"
logger = logging.getLogger(__name__)
LABELS = {"positive": "긍정", "negative": "부정", "neutral": "중립 / 혼합"}
EXAMPLES = {
    "긍정 리뷰": "음식이 정말 맛있고 직원들도 친절했어요. 다음에 꼭 다시 방문하고 싶어요.",
    "부정 리뷰": "음식이 차갑고 직원도 불친절했어요. 가격도 비싸서 다시 가고 싶지 않아요.",
    "혼합 리뷰": "음식은 정말 맛있었지만, 직원이 불친절하고 음식도 너무 늦게 나와서 다시 방문하고 싶지는 않아요.",
}
QUESTIONS = {
    "overall": {
        "type": "choice",
        "instructions": "리뷰의 전체적인 내용을 기준으로 감성을 판단하세요.",
        "criteria": {"positive": "전체적으로 긍정적인 평가", "negative": "전체적으로 부정적인 평가", "neutral": "긍정과 부정이 혼합되거나 중립적인 평가"},
    },
    "final": {
        "type": "choice",
        "instructions": "리뷰의 마지막 평가를 중심으로 감성을 판단하세요.",
        "criteria": {"positive": "마지막 평가가 긍정적임", "negative": "마지막 평가가 부정적임", "neutral": "마지막 평가가 중립적이거나 불분명함"},
    },
}


def model_file(filename):
    """Use cached files without contacting the Hub on every startup."""
    try:
        return hf_hub_download(REPO_ID, filename, revision=MODEL_REVISION, local_files_only=True)
    except LocalEntryNotFoundError:
        return hf_hub_download(REPO_ID, filename, revision=MODEL_REVISION)


@st.cache_resource(show_spinner=False)
def load_jev():
    spec = importlib.util.spec_from_file_location("openjevx", model_file("openjevx.py"))
    if spec is None or spec.loader is None:
        raise ImportError("OpenJevX 모듈을 불러올 수 없습니다.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.OpenJevX(model=model_file("openjevx.w8.onnx"),
                           tokenizer=model_file("tokenizer.json"), config=model_file("config.json"))


def choose_example(name):
    st.session_state.review = EXAMPLES[name]


def export_history(records):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["분석 시각", "리뷰", "전체 감성", "전체 confidence", "최종 평가", "최종 confidence", "소요 시간(초)", "모델 출처", "모델"])
    for record in records:
        answers = record["result"]["answers"]
        review = record["review"]
        # Keep user input from becoming a spreadsheet formula.
        if review.lstrip().startswith(("=", "+", "-", "@")):
            review = "'" + review
        row = [record["created_at"], review]
        for key in ("overall", "final"):
            answer = answers[key]
            row.extend([LABELS[answer["choice"]], answer["confidence"]])
        writer.writerow(row + [record["seconds"], record.get("provider", "openjevx"), record.get("resolved_model") or record.get("requested_model", MODEL_REVISION)])
    return output.getvalue().encode("utf-8-sig")


st.set_page_config(page_title="Jev 리뷰 감성 연구실", page_icon="📝", layout="wide")
st.session_state.setdefault("history", [])
st.title("📝 Jev 한국어 리뷰 감성 연구실")
st.write("리뷰 전체의 인상과 마지막 평가를 비교하고, 모델의 감성 확률을 살펴보세요.")

with st.sidebar:
    st.header("분석 모델")
    provider = st.radio("모델 선택", ["공식 Jev API", "로컬 OpenJevX"], key="provider")
    official = provider == "공식 Jev API"
    api_key = ""
    requested_model = DEFAULT_MODEL
    consent = False
    if official:
        configured_key = os.environ.get("TYPESAFE_API_KEY", "").strip()
        if not configured_key:
            try:
                configured_key = str(st.secrets.get("TYPESAFE_API_KEY", "")).strip()
            except FileNotFoundError:
                pass
        entered_key = st.text_input("TypeSafe API 키 (현재 세션만)", type="password", key="typesafe_key",
                                    help="키를 채팅, 코드 또는 GitHub에 붙여 넣지 마세요.")
        api_key = entered_key.strip() or configured_key
        st.caption("키 설정됨" if api_key else "공식 모드는 TypeSafe API 키가 필요합니다.")
        requested_model = st.text_input("공식 모델", value=DEFAULT_MODEL, key="official_model").strip()
        st.link_button("TypeSafe 콘솔에서 키 준비", "https://console.typesafe.ai")
        consent = st.checkbox("리뷰를 TypeSafe로 전송하며 API 사용 요금이 발생할 수 있음을 확인했습니다.", key="api_consent")
    else:
        st.info("로컬 모드는 첫 실행에 약 600MB를 다운로드합니다. 이후 캐시를 사용합니다.")
    st.header("분석 가이드")
    st.markdown("1. 리뷰를 입력하거나 예시를 선택하세요.\n2. **감성 분석하기**를 누르세요.\n3. 두 기준의 결과와 확률을 비교하세요.")
    st.caption("확률은 모델의 상대적인 판단이며 정확도를 보장하지 않습니다. 중립에는 혼합 감성도 포함됩니다. 두 기준이 같아도 리뷰에 혼합 감성이 없다는 뜻은 아닙니다.")
    st.caption("공식 모드는 TypeSafe 서버에서, 로컬 모드는 이 컴퓨터에서 분석합니다. 기록은 세션 내 최대 50개이며 모델 출처를 함께 저장합니다.")

analysis_tab, history_tab, guide_tab = st.tabs(["리뷰 분석", "분석 기록", "프로젝트 소개"])
with analysis_tab:
    st.subheader("어떤 리뷰를 분석할까요?")
    for column, name in zip(st.columns(3), EXAMPLES):
        column.button(name, on_click=choose_example, args=(name,), use_container_width=True)
    review = st.text_area("한국어 리뷰", key="review", height=140, max_chars=1200,
                          placeholder="음식은 맛있었지만 서비스가 너무 느렸어요.")
    st.caption(f"{len(review)} / 1,200자 · 긴 리뷰는 모델의 토큰 한도에 따라 뒷부분이 잘릴 수 있습니다.")
    if st.button("감성 분석하기", type="primary", use_container_width=True):
        if not review.strip():
            st.warning("리뷰를 먼저 입력해 주세요.")
        elif official and not api_key:
            st.warning("왼쪽에서 TypeSafe API 키를 입력하거나 로컬 OpenJevX를 선택하세요.")
        elif official and not consent:
            st.warning("공식 API로 리뷰 전송 및 요금 안내를 먼저 확인하세요.")
        else:
            with st.spinner("모델을 준비하고 리뷰를 분석하고 있습니다..."):
                try:
                    started = time.perf_counter()
                    result = (decide_official(review.strip(), QUESTIONS, api_key, requested_model)
                              if official else load_jev().decide(review.strip(), QUESTIONS))
                    record = {"review": review.strip(), "result": result,
                              "provider": "typesafe_official" if official else "openjevx",
                              "requested_model": requested_model if official else REPO_ID,
                              "resolved_model": result.get("model") if official else MODEL_REVISION,
                              "seconds": round(time.perf_counter() - started, 2),
                              "created_at": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")}
                    st.session_state.latest = record
                    st.session_state.history.insert(0, record)
                    del st.session_state.history[50:]
                except JevAPIError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    if official:
                        st.error("공식 API 처리 중 예상하지 못한 오류가 발생했습니다. 키는 출력하지 않았습니다.")
                    else:
                        logger.exception("Jev 감성 분석 실패")
                        st.error("분석 중 오류가 발생했습니다.")
                        st.exception(exc)

    if "latest" in st.session_state:
        record = st.session_state.latest
        answers = record["result"]["answers"]
        st.divider()
        st.subheader("최근 분석 결과")
        st.text(record["review"])
        record_provider = record.get("provider", "openjevx")
        st.caption(f"모델 출처: {record_provider} · 모델: {record.get('resolved_model') or record.get('requested_model', MODEL_REVISION)}")
        if record_provider != ("typesafe_official" if official else "openjevx"):
            st.info("모델 선택이 변경되었습니다. 아래 결과는 이전 모델의 결과입니다. 다시 분석하면 새 모델을 사용합니다.")
        if review.strip() != record["review"]:
            st.info("입력 내용이 변경되었습니다. 아래 결과는 이전에 분석한 리뷰의 결과입니다.")
        st.caption(f"분석 시각: {record['created_at']} · 모델 준비 및 분석: {record['seconds']:.2f}초")
        for column, key, title in zip(st.columns(2), ("overall", "final"), ("전체 감성", "마지막 평가")):
            with column:
                answer = answers[key]
                st.metric(title, LABELS[answer["choice"]])
                st.caption(f"모델 confidence: {answer['confidence']:.1%} · 아래 막대는 후보별 확률입니다.")
                for label, description in LABELS.items():
                    probability = answer["probabilities"].get(label, 0)
                    st.progress(min(1.0, max(0.0, probability)), text=f"{description} · {probability:.1%}")
                if max(answer["probabilities"].values()) < 0.6:
                    st.caption("가장 높은 감성 확률이 60% 미만입니다. 결과를 신중하게 해석하세요.")
        if answers["overall"]["choice"] == answers["final"]["choice"]:
            st.success("전체 인상과 마지막 평가에 대한 모델의 판단이 같습니다.")
        else:
            st.warning("전체 인상과 마지막 평가가 다르게 분류되었습니다. 리뷰의 마무리와 전체 내용을 함께 살펴보세요.")
        with st.expander("원본 결과 및 판단 기준"):
            st.json({"provider": record_provider, "result": record["result"], "questions": QUESTIONS})
        st.download_button("이 결과 JSON 다운로드", json.dumps(record, ensure_ascii=False, indent=2),
                           file_name="jev_result.json", mime="application/json")

with history_tab:
    history = st.session_state.history
    st.subheader(f"분석 기록 · {len(history)}개")
    if not history:
        st.info("리뷰를 분석하면 이곳에 기록이 쌓입니다.")
    else:
        st.download_button("전체 기록 CSV 다운로드", export_history(history),
                           file_name="jev_history.csv", mime="text/csv")
        if st.button("분석 기록 지우기"):
            st.session_state.history = []
            st.session_state.pop("latest", None)
            st.rerun()
        for record in history:
            answers = record["result"]["answers"]
            with st.expander(f"{record['created_at']} · {record['review'][:45]}"):
                st.text(record["review"])
                st.caption(f"모델 출처: {record.get('provider', 'openjevx')} · {record.get('resolved_model') or record.get('requested_model', MODEL_REVISION)}")
                st.text(f"전체 감성: {LABELS[answers['overall']['choice']]} / 마지막 평가: {LABELS[answers['final']['choice']]}")

with guide_tab:
    st.subheader("프로젝트 목적")
    st.write("같은 한국어 리뷰를 두 가지 질문으로 분석해 판단 기준에 따른 감성 분류 차이를 관찰합니다.")
    st.markdown("- **전체 감성**: 리뷰 전체에 대한 평가\n- **마지막 평가**: 리뷰 마지막의 평가를 중심으로 한 판단\n- **공식 모드**: TypeSafe Jev HTTP API\n- **로컬 모드**: 커뮤니티 OpenJevX · ONNX Runtime CPU")
    st.caption("공식 API 기능 추가와 실제 공식 모델 평가 완료는 다릅니다. API 키를 설정하고 성공한 공식 결과를 확인해야 공식 실행 증거가 생깁니다. 기존 Notebook 결과는 OpenJevX 결과입니다.")
    st.subheader("결과를 해석할 때")
    st.write("이 모델의 한국어 감성 분류 정확도는 별도로 검증하지 않았습니다. 반어법, 이중 부정, 긴 문장에서는 부정확할 수 있습니다. 마지막 평가 역시 모델에 지시한 판단 기준이며, 마지막 문장만 따로 추출해 분석하는 방식은 아닙니다.")
    st.write("프로젝트 평가에는 사람이 정답을 붙인 긍정·부정·혼합 리뷰를 준비해 모델 결과와 비교하는 방법을 권장합니다.")
