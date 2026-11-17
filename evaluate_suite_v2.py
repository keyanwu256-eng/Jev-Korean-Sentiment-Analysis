"""Run the frozen six-category set without training or changing the application."""
import csv
import hashlib
import io
import json
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

from evaluate_korean import load_app_definitions
from sentiment_engine import KoreanSentiment, MODEL_ID, REVISION, sentence_composition, uncertainty, compare_with_jev

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence"
LABELS = {"positive": "긍정", "negative": "부정", "neutral": "중립"}
CATEGORIES = {"positive": "명확한 긍정", "negative": "명확한 부정", "neutral": "중립 사실",
              "mixed": "균형 혼합", "sarcasm": "반어", "indirect_dissatisfaction": "간접 불만"}


def digest(path):
    # Text newline normalization keeps the manifest portable across Git CRLF/LF checkouts.
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def score(rows, model, answer, target):
    correct = sum(row[model]["answers"][answer]["choice"] == row[target] for row in rows)
    accepted = [row for row in rows if not uncertainty(row[model]["answers"][answer])]
    high_wrong = [row["id"] for row in rows if row[model]["answers"][answer]["choice"] != row[target]
                  and max(row[model]["answers"][answer]["probabilities"].values()) >= 0.9]
    return {"count": len(rows), "correct": correct, "reference_agreement": correct / len(rows),
            "accepted_count": len(accepted), "coverage": len(accepted) / len(rows),
            "accepted_correct": sum(row[model]["answers"][answer]["choice"] == row[target] for row in accepted),
            "high_confidence_disagreements": high_wrong}


def summarize(rows):
    result = {}
    for model in ("primary", "openjevx"):
        result[model] = {
            "overall": score(rows, model, "overall", "overall_reference"),
            "final_standalone": score(rows, model, "final", "final_standalone_reference"),
            "final_contextual_intent": score(rows, model, "final", "final_contextual_reference"),
        }
    return result


def export_csv(rows):
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["id", "type", "review", "overall_reference", "primary_raw", "primary_max_probability", "primary_abstained",
                     "jev_raw", "jev_max_probability", "jev_abstained", "final_sentence", "standalone_reference", "contextual_reference",
                     "primary_final", "jev_final", "sentence_composition"])
    for row in rows:
        a, b = row["primary"]["answers"], row["openjevx"]["answers"]
        writer.writerow([row["id"], row["category"], row["text"], row["overall_reference"], a["overall"]["choice"],
                         max(a["overall"]["probabilities"].values()), uncertainty(a["overall"]), b["overall"]["choice"],
                         max(b["overall"]["probabilities"].values()), uncertainty(b["overall"]), row["primary"]["final_sentence"],
                         row["final_standalone_reference"], row["final_contextual_reference"], a["final"]["choice"], b["final"]["choice"],
                         row["composition"]["status"]])
    return buf.getvalue().encode("utf-8-sig")


def write_report(report):
    lines = ["# 고정된 신규 한국어 36개 사례 평가", "", "**작성자: 오가암**", "",
             "긍정·부정·중립·혼합·반어·간접 불만 각 6개를 새로 작성해 출력 확인 전에 고정했다. 앱·모델·질문·보류 임계값을 바꾸지 않고 두 모델에 같은 원문을 입력했다.", "",
             "**독립 공개 벤치마크가 아니다.** 참고 라벨은 개발/AI 보조로 작성한 잠정 기준이며 별도 사람 평가자의 합의를 받지 않았다. 유형별 6개뿐이므로 일반 성능이나 통계적 우열로 확대하지 않는다. 알려진 세 오류 문장은 포함하지 않았지만 그 유형을 이미 알고 작성했으므로 완전한 블라인드 테스트라고 주장하지 않는다.", "",
             f"- 데이터 고정 시각: {report['freeze']['frozen_at']}", f"- 평가 시각: {report['completed_at']}",
             f"- 고정 데이터 SHA-256: `{report['dataset_sha256']}`", f"- 실행 모델: `{MODEL_ID}` / `{report['openjevx_model']}`", "",
             "## 유형별 전체 원문 분류의 참고 기준 일치", "",
             "보류된 결과도 원시 분류 일치 계산에 포함했다. coverage는 보류하지 않고 표시한 비율이며, 아래에서는 편의상 개수로 보인다. 모델 확률은 정확도가 아니다.", "",
             "| 유형 | 수 | 주 모델 일치 | OpenJevX 일치 | 주 모델 보류 없음 | Jev 보류 없음 |", "|---|---:|---:|---:|---:|---:|"]
    for category in CATEGORIES:
        summary = report["by_category"][category]
        a, b = summary["primary"]["overall"], summary["openjevx"]["overall"]
        lines.append(f"| {CATEGORIES[category]} | {a['count']} | {a['correct']}/{a['count']} | {b['correct']}/{b['count']} | {a['accepted_count']}/{a['count']} | {b['accepted_count']}/{b['count']} |")
    a, b = report["total"]["primary"]["overall"], report["total"]["openjevx"]["overall"]
    lines.append(f"| 합계 | 36 | {a['correct']}/36 ({a['reference_agreement']:.1%}) | {b['correct']}/36 ({b['reference_agreement']:.1%}) | {a['accepted_count']}/36 | {b['accepted_count']}/36 |")
    lines += ["", "여섯 유형의 수는 같지만 전체 참고 라벨은 긍정 6개·중립 12개·부정 18개로 불균형하다. 합계만으로 비교하지 말고 유형별 결과를 함께 읽어야 한다."]
    lines += ["", "균형 혼합의 전체 참고 라벨은 이번 평가 규약상 neutral이다. 혼합 댓글의 정답에는 가중치·도메인에 따른 해석 차이가 있으므로 이를 최종 만족도 정확도로 읽지 않는다.", "",
              "## 마지막 문장의 두 가지 평가", "",
              "두 모델의 마지막 문장 출력은 문장을 단독으로 입력한 결과다. **독립 문장의 표면 감성**과 **본문 속 마지막 발언의 의도**를 별도 참고 기준으로 비교한다. 반어의 칭찬이나 간접적인 선택 문장은 두 기준이 다를 수 있다. 문맥 의도 불일치는 문맥을 안 주는 현 방식의 한계를 나타내며, 단독 문장 태스크의 오류와 같다고 단정하지 않는다.", "",
              "| 유형 | 주 모델: 단독 문장 기준 | 주 모델: 문맥 의도 기준 | Jev: 단독 문장 기준 | Jev: 문맥 의도 기준 |", "|---|---:|---:|---:|---:|"]
    for category in CATEGORIES:
        summary = report["by_category"][category]
        numbers = [summary[m][k]["correct"] for m in ("primary", "openjevx") for k in ("final_standalone", "final_contextual_intent")]
        lines.append(f"| {CATEGORIES[category]} | " + " | ".join(f"{n}/6" for n in numbers) + " |")
    lines += ["", "이번 표본에서 주 모델은 명확한 긍정·부정·중립 전체 분류에서 각각 6/6으로 일치했다. 반면 반어 전체 분류는 2/6, 반어의 문맥 속 결말 의도는 0/6으로 취약했다. 간접 불만은 전체 문맥을 읽는 분류는 5/6이었으나 마지막 문장만으로 문맥 의도를 맞힌 것은 1/6이었다. 이는 이번 작은 표본의 관찰이며 성능 보장이 아니다."]
    lines += ["", "## 문장별 긍정·부정 공존", "",
              f"균형 혼합 6개 중 공존을 명시적으로 관찰한 사례: **{report['mixed_composition']['confirmed']}/6**. 판단 불확실: {report['mixed_composition']['uncertain']}/6. 공존 미관찰: {report['mixed_composition']['not_observed']}/6.",
              "반어의 표면 칭찬과 불만이 함께 분류되는 것은 진짜 만족 감정의 혼합을 이해했다는 뜻이 아니므로, 반어는 이 혼합 검사의 점수에서 제외했다. 개별 원문과 공존 결과는 전체 기록에 보존했다.", "",
              "## 어떤 유형에서 문제가 남았는가", ""]
    for category in CATEGORIES:
        group = [row for row in report["rows"] if row["category"] == category]
        wrong = [row["id"] for row in group if row["primary"]["answers"]["overall"]["choice"] != row["overall_reference"]]
        high = report["by_category"][category]["primary"]["overall"]["high_confidence_disagreements"]
        lines.append(f"- **{CATEGORIES[category]}**: 이 표본에서 주 모델 전체 분류 불일치 {len(wrong)}/6. 사례: {', '.join(wrong) if wrong else '없음'}. 최대 확률 90% 이상 불일치: {', '.join(high) if high else '없음'}.")
    lines += ["", "원시 예측은 수정하지 않았다. 정답과 맞지 않는 결과를 제거하거나 임계값을 바꾸지 않았다. 향후 개선에는 이번 사례와 별도의 새 평가셋과 사람 검수가 필요하다.", "",
              "## 전체 36개 결과", "", "| ID | 유형 | 전체 참고 | 주 모델 원시 | Jev 원시 | 주 모델 보류 |", "|---|---|---|---|---|---|"]
    for row in report["rows"]:
        a, b = row["primary"]["answers"]["overall"], row["openjevx"]["answers"]["overall"]
        lines.append(f"| {row['id']} | {CATEGORIES[row['category']]} | {LABELS[row['overall_reference']]} | {LABELS[a['choice']]} | {LABELS[b['choice']]} | {'예' if uncertainty(a) else '아니오'} |")
    lines += ["", "## 재현 및 증거", "", "- [고정 데이터](evaluation_suite_v2.json) / [실행 전 고정 기록](evidence/evaluation_suite_v2_freeze.json)",
              "- [전체 원문·확률·문장별 결과 JSON](evidence/evaluation_suite_v2_results.json)", "- [Excel용 CSV](evidence/evaluation_suite_v2_results.csv)",
              "- [평가 스크립트](evaluate_suite_v2.py): `.venv\\Scripts\\python.exe evaluate_suite_v2.py`", "",
              "첫 다운로드 이외에는 로컬 모델로 실행하며 공식 API 호출이 없다. 재실행은 결과 파일을 갱신한다. 데이터/코드가 고정 기록과 달라지면 실행을 중단한다. 주석·문서 및 실행 기록을 추가한 것 외에 앱과 분류 코드는 변경하지 않았다.", ""]
    (ROOT / "EVALUATION_V2.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    dataset_path = ROOT / "evaluation_suite_v2.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    frozen = json.loads((EVIDENCE / "evaluation_suite_v2_freeze.json").read_text(encoding="utf-8"))
    dataset_hash = digest(dataset_path)
    assert dataset_hash == frozen["dataset_sha256"], "Frozen dataset was modified"
    assert len(dataset["cases"]) == 36
    assert Counter(case["category"] for case in dataset["cases"]) == {category: 6 for category in CATEGORIES}
    assert len({case["id"] for case in dataset["cases"]}) == 36
    for name, expected in frozen["primary_and_comparison_code_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            portable = json.loads((EVIDENCE / "evaluation_suite_v2_source_normalized.json").read_text(encoding="utf-8"))
            assert digest(ROOT / name) == portable["normalized_sha256"][name], f"Frozen model/application code changed: {name}"
    started = datetime.now(timezone(timedelta(hours=9))).isoformat()
    namespace = load_app_definitions()
    model = KoreanSentiment()
    jev = namespace["load_jev"]()
    rows = []
    for case in dataset["cases"]:
        start = time.perf_counter()
        primary = model.analyze(case["text"])
        primary_seconds = time.perf_counter() - start
        start = time.perf_counter()
        comparison = compare_with_jev(jev, case["text"], primary["final_sentence"], namespace["QUESTIONS"])
        row = {**case, "primary": primary, "openjevx": comparison, "composition": sentence_composition(primary),
               "primary_seconds": primary_seconds, "comparison_seconds": time.perf_counter() - start}
        rows.append(row)
        # Save every completed case; no silent removal or result-based retries.
        (ROOT / "runtime/evaluation/suite_v2_progress.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{len(rows)}/36 {case['id']}: primary={primary['answers']['overall']['choice']} / Jev={comparison['answers']['overall']['choice']} / reference={case['overall_reference']}", flush=True)
    mixed = [row for row in rows if row["category"] == "mixed"]
    composition_counts = Counter(row["composition"]["status"] for row in mixed)
    report = {"suite_id": dataset["suite_id"], "started_at": started,
              "completed_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
              "dataset_sha256": dataset_hash, "freeze": frozen, "policy": dataset["policy"],
              "primary_model": MODEL_ID, "primary_revision": REVISION,
              "openjevx_model": namespace["REPO_ID"], "openjevx_revision": namespace["MODEL_REVISION"],
              "model_code_changed": False, "official_api_used": False, "total": summarize(rows),
              "by_category": {category: summarize([row for row in rows if row["category"] == category]) for category in CATEGORIES},
              "mixed_composition": {"count": 6, "confirmed": composition_counts["coexistence_observed"],
                                    "uncertain": composition_counts["insufficient_evidence"], "not_observed": composition_counts["coexistence_not_observed"]},
              "rows": rows}
    (EVIDENCE / "evaluation_suite_v2_results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (EVIDENCE / "evaluation_suite_v2_results.csv").write_bytes(export_csv(rows))
    write_report(report)
    print(json.dumps({category: {model_name: report["by_category"][category][model_name]["overall"] for model_name in ("primary", "openjevx")}
                      for category in CATEGORIES}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
