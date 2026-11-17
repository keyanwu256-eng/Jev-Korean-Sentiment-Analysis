import csv
import importlib.util
import io
import json
import logging
import time
from datetime import datetime, timezone, timedelta

import streamlit as st
from huggingface_hub import hf_hub_download
from huggingface_hub.errors import LocalEntryNotFoundError
from sentiment_engine import KoreanSentiment, MODEL_ID as SENTIMENT_ID, REVISION as SENTIMENT_REVISION, compare_with_jev, uncertainty

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


@st.cache_resource(show_spinner=False)
def load_korean():
    return KoreanSentiment()


def choose_example(name):
    st.session_state.review = EXAMPLES[name]


def export_history(records):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["분석 시각", "리뷰", "전체 원시 분류", "전체 확률", "마지막 원시 분류", "마지막 확률", "소요 시간(초)", "주 분석 모델", "마지막 문장", "전체 판단 보류", "마지막 판단 보류", "Jev 전체", "Jev 마지막"])
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
        comparison = record.get("comparison", {}).get("answers", {})
        fields = row + [record["seconds"], record.get("model", REPO_ID),
                        record.get("final_sentence", ""), uncertainty(answers["overall"]),
                        uncertainty(answers["final"]), comparison.get("overall", {}).get("choice", ""),
                        comparison.get("final", {}).get("choice", "")]
        writer.writerow(["'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value
                         for value in fields])
    return output.getvalue().encode("utf-8-sig")


st.set_page_config(page_title="Jev 리뷰 감성 연구실", page_icon="📝", layout="wide")
st.session_state.setdefault("history", [])
st.title("📝 Jev 한국어 리뷰 감성 연구실")
st.write("한국어 원문을 직접 분석하고 마지막 문장을 따로 평가합니다. Jev 결과와 비교해 보세요.")

with st.sidebar:
    st.header("분석 설정")
    compare_jev = st.checkbox("OpenJevX 대조 분석 함께 실행", value=True, key="compare_jev")
    st.caption("주 결과는 한국어 지원 감성 모델입니다. Jev는 별도 대조 결과로 표시합니다. 모두 로컬 실행이며 공식 API 키가 필요 없습니다.")
    st.header("분석 가이드")
    st.markdown("1. 리뷰를 입력하거나 예시를 선택하세요.\n2. **감성 분석하기**를 누르세요.\n3. 두 기준의 결과와 확률을 비교하세요.")
    st.info("첫 실행에는 감성 모델 약 300MB를 다운로드합니다. Jev 대조 모델은 별도로 약 600MB이며 이후 캐시를 사용합니다.")
    st.caption("최대 확률이 65% 미만이거나 상위 두 확률 차이가 15%p 미만이면 판단을 보류합니다. 중립과 불확실은 다릅니다. 이 기준은 검증된 정확도 보장이 아닙니다.")
    st.caption("리뷰는 로컬 모델에서 분석합니다. 기록은 현재 세션에만 보관되며 최대 50개입니다.")

analysis_tab, history_tab, guide_tab = st.tabs(["리뷰 분석", "분석 기록", "프로젝트 소개"])
with analysis_tab:
    st.subheader("어떤 리뷰를 분석할까요?")
    for column, name in zip(st.columns(3), EXAMPLES):
        column.button(name, on_click=choose_example, args=(name,), use_container_width=True)
    review = st.text_area("한국어 리뷰", key="review", height=140, max_chars=1200,
                          placeholder="음식은 맛있었지만 서비스가 너무 느렸어요.")
    st.caption(f"{len(review)} / 1,200자 · 전체 분석은 최대 512토큰입니다. 마지막 문장은 별도로 분석합니다.")
    if st.button("감성 분석하기", type="primary", use_container_width=True):
        if not review.strip():
            st.warning("리뷰를 먼저 입력해 주세요.")
        else:
            with st.spinner("모델을 준비하고 리뷰를 분석하고 있습니다..."):
                try:
                    started = time.perf_counter()
                    result = load_korean().analyze(review.strip())
                    record = {"review": review.strip(), "result": result,
                              "model": SENTIMENT_ID, "revision": SENTIMENT_REVISION,
                              "final_sentence": result["final_sentence"],
                              "seconds": round(time.perf_counter() - started, 2),
                              "created_at": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")}
                    if compare_jev:
                        try:
                            jev = load_jev()
                            record["comparison"] = {"model": REPO_ID, "revision": MODEL_REVISION,
                                                    **compare_with_jev(jev, review.strip(), result["final_sentence"], QUESTIONS)}
                        except Exception:
                            logger.exception("OpenJevX 대조 분석 실패")
                            record["comparison_error"] = "Jev 대조 분석에 실패했습니다. 주 모델 결과는 유지됩니다."
                    record["seconds"] = round(time.perf_counter() - started, 2)
                    st.session_state.latest = record
                    st.session_state.history.insert(0, record)
                    del st.session_state.history[50:]
                except Exception as exc:
                    logger.exception("Jev 감성 분석 실패")
                    st.error("분석 중 오류가 발생했습니다.")
                    st.exception(exc)

    if "latest" in st.session_state:
        record = st.session_state.latest
        answers = record["result"]["answers"]
        st.divider()
        st.subheader("최근 분석 결과")
        st.text(record["review"])
        st.caption(f"주 분석 모델: {record.get('model', REPO_ID + ' (이전 기록)')}")
        if record.get("final_sentence"):
            st.text("마지막 평가에 사용한 문장: " + record["final_sentence"])
        if record["result"].get("sentence_limit_applied"):
            st.warning("문장이 많아 문장별 표시는 처음 19개와 마지막 문장으로 제한했습니다.")
        if review.strip() != record["review"]:
            st.info("입력 내용이 변경되었습니다. 아래 결과는 이전에 분석한 리뷰의 결과입니다.")
        st.caption(f"분석 시각: {record['created_at']} · 모델 준비 및 분석: {record['seconds']:.2f}초")
        for column, key, title in zip(st.columns(2), ("overall", "final"), ("전체 감성", "마지막 평가")):
            with column:
                answer = answers[key]
                held = uncertainty(answer)
                st.metric(title, "판단 불확실" if held else LABELS[answer["choice"]])
                st.caption(f"모델 원시 분류: {LABELS[answer['choice']]} · 최대 확률 {max(answer['probabilities'].values()):.1%}")
                if answer.get("truncated"):
                    st.warning("입력이 512토큰을 넘어 뒷부분이 잘렸습니다.")
                for label, description in LABELS.items():
                    probability = answer["probabilities"].get(label, 0)
                    st.progress(min(1.0, max(0.0, probability)), text=f"{description} · {probability:.1%}")
                if held:
                    st.warning("확률이 낮거나 후보 간 차이가 작습니다. 중립으로 확정하지 말고 원문을 확인하세요.")
        if any(uncertainty(answer) for answer in answers.values()):
            st.info("불확실한 판단이 포함되어 있습니다. 두 원시 분류가 같아도 정답이라는 뜻은 아닙니다.")
        elif answers["overall"]["choice"] == answers["final"]["choice"]:
            st.info("전체와 마지막 문장의 분류가 같습니다. 정답 여부를 보장하지 않습니다.")
        else:
            st.warning("전체 인상과 마지막 평가가 다르게 분류되었습니다. 리뷰의 마무리와 전체 내용을 함께 살펴보세요.")
        sentence_results = record["result"].get("sentences", [])
        if sentence_results:
            with st.expander("문장별 분석 보기"):
                for item in sentence_results:
                    st.text(item["text"])
                    st.caption(f"{'판단 불확실 · ' if uncertainty(item) else ''}원시 분류: {LABELS[item['choice']]} · 최대 확률 {item['confidence']:.1%}")
            strong = {item["choice"] for item in sentence_results if not uncertainty(item)}
            if {"positive", "negative"} <= strong:
                st.info("문장별로 긍정과 부정이 함께 관찰됩니다. 전체 리뷰의 단일 라벨과 구분해서 해석하세요.")
        if record.get("comparison_error"):
            st.warning(record["comparison_error"])
        if record.get("comparison"):
            st.subheader("OpenJevX 대조 결과 — 주 결과와 다른 모델")
            for key, title in (("overall", "전체"), ("final", "마지막 문장")):
                answer = record["comparison"]["answers"][key]
                st.text(f"Jev {title}: {LABELS[answer['choice']]} · 최대 확률 {max(answer['probabilities'].values()):.1%}")
            st.caption("두 모델의 분류는 다를 수 있습니다. Jev의 결과를 주 모델 결과로 덮어쓰지 않습니다.")
        with st.expander("원본 결과 및 판단 기준"):
            st.json({"result": record["result"], "comparison": record.get("comparison"), "jev_questions": QUESTIONS})
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
                st.caption("모델: " + record.get("model", REPO_ID + " (이전 기록)"))
                st.text(f"전체 감성: {LABELS[answers['overall']['choice']]} / 마지막 평가: {LABELS[answers['final']['choice']]}")

with guide_tab:
    st.subheader("프로젝트 목적")
    st.write("같은 한국어 리뷰를 두 가지 질문으로 분석해 판단 기준에 따른 감성 분류 차이를 관찰합니다.")
    st.markdown("- **주 분석**: Horizon-Labs multilingual-sentiment-small (한국어 지원 다국어 감성 모델)\n- **전체 감성**: 한국어 원문 직접 분류\n- **마지막 평가**: 마지막 문장을 추출하여 별도 분류\n- **대조 분석**: 커뮤니티 OpenJevX · 질문을 통한 분류\n- **실행**: 두 모델 모두 로컬 ONNX CPU · 번역 및 공식 API 사용 없음")
    st.subheader("결과를 해석할 때")
    st.write("정확도는 데이터에 따라 달라집니다. 반어법, 이중 부정, 혼합 감성에서는 오분류할 수 있습니다. 문장 분리는 구두점과 줄바꿈에 따른 간단한 규칙이며 마지막 절을 의미적으로 추출하는 방식은 아닙니다. 원시 분류와 판단 보류를 구분합니다.")
    st.write("프로젝트 평가에는 사람이 정답을 붙인 긍정·부정·혼합 리뷰를 준비해 모델 결과와 비교하는 방법을 권장합니다.")
