"""Official TypeSafe HTTP adapter. Credentials never enter returned records."""
import json
import math
import re
import urllib.error
import urllib.request

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-1.13.0"


class JevAPIError(Exception):
    """A safe user-facing error; never includes server bodies or credentials."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_result(result, questions):
    if not isinstance(result, dict) or not isinstance(result.get("answers"), dict):
        raise JevAPIError("공식 API 응답 형식이 올바르지 않습니다.")
    for qid, question in questions.items():
        answer = result["answers"].get(qid)
        if not isinstance(answer, dict):
            raise JevAPIError("공식 API 응답에 필요한 답변이 없습니다.")
        options = question["criteria"]
        probabilities = answer.get("probabilities")
        if answer.get("type") != "choice" or answer.get("choice") not in options:
            raise JevAPIError("공식 API의 분류 결과를 확인할 수 없습니다.")
        if not isinstance(probabilities, dict) or set(probabilities) != set(options):
            raise JevAPIError("공식 API의 감성 확률 항목이 올바르지 않습니다.")
        values = [answer.get("confidence"), *probabilities.values()]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
            raise JevAPIError("공식 API의 확률 값이 올바르지 않습니다.")
        if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=0.02):
            raise JevAPIError("공식 API의 확률 합계가 올바르지 않습니다.")
    # Whitelist fields so unexpected server metadata cannot reach exports.
    clean = {"answers": {qid: {key: result["answers"][qid][key]
                               for key in ("type", "choice", "confidence", "probabilities")}
                         for qid in questions}}
    resolved = result.get("model")
    if isinstance(resolved, str) and re.fullmatch(r"jev-[A-Za-z0-9._-]{1,64}", resolved):
        clean["model"] = resolved
    usage = result.get("usage")
    if isinstance(usage, dict):
        clean["usage"] = {key: value for key, value in usage.items()
                          if key in ("input_tokens", "output_tokens") and type(value) is int and value >= 0}
    return clean


def decide_official(review, questions, api_key, model=DEFAULT_MODEL):
    key = api_key.strip()
    if not key:
        raise JevAPIError("TypeSafe API 키를 먼저 설정하세요. Hugging Face 토큰과는 다릅니다.")
    if any(char.isspace() for char in key):
        raise JevAPIError("API 키에 공백이나 줄바꿈이 포함되어 있습니다.")
    if not re.fullmatch(r"jev-[A-Za-z0-9._-]{1,64}", model):
        raise JevAPIError("모델 이름은 jev-로 시작하는 올바른 식별자여야 합니다.")
    payload = {"model": model, "state": review, "questions": questions}
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
    try:
        # No retries: a network failure may happen after the server billed a call.
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=60) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise JevAPIError("공식 API 응답이 예상 크기를 초과했습니다.")
        result = json.loads(raw)
    except urllib.error.HTTPError as exc:
        messages = {
            400: "요청 또는 모델 설정을 확인하세요.",
            401: "API 키가 유효하지 않습니다. TypeSafe 키를 확인하세요.",
            402: "TypeSafe 계정의 잔액 또는 결제 상태를 확인하세요.",
            403: "이 계정 또는 모델에 대한 접근 권한이 없습니다.",
            404: "요청한 모델을 사용할 수 없습니다. 모델 이름을 확인하세요.",
            429: "요청 한도에 도달했습니다. 잠시 후 다시 시도하세요.",
        }
        raise JevAPIError(f"공식 Jev API 오류 ({exc.code}): " + messages.get(exc.code, "서비스 상태를 확인하고 잠시 후 다시 시도하세요.")) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise JevAPIError("공식 Jev 연결에 실패했거나 시간이 초과되었습니다. 자동 재요청하지 않았습니다. 계정 사용 내역을 확인한 뒤 다시 시도하세요.") from None
    except (ValueError, UnicodeError):
        raise JevAPIError("공식 API가 올바른 JSON을 반환하지 않았습니다.") from None
    return validate_result(result, questions)
