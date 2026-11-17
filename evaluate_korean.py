"""Reproducible task smoke evaluation; examples are author-labelled, not a benchmark."""
import ast
import hashlib
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from sentiment_engine import KoreanSentiment, MODEL_ID, REVISION, uncertainty

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "runtime" / "evaluation"
OUT.mkdir(parents=True, exist_ok=True)


def load_app_definitions():
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "set_page_config":
            break
        nodes.append(node)
    namespace = {"__name__": "evaluation"}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace


def metrics(rows, field):
    labels = ["negative", "neutral", "positive"]
    confusion = {actual: {predicted: 0 for predicted in labels} for actual in labels}
    for row in rows:
        confusion[row["label"]][row[field]["choice"]] += 1
    correct = sum(row["label"] == row[field]["choice"] for row in rows)
    f1 = []
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in labels if other != label)
        fn = sum(confusion[label][other] for other in labels if other != label)
        f1.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0)
    accepted = [row for row in rows if not uncertainty(row[field])]
    return {"count": len(rows), "correct": correct, "accuracy": correct / len(rows),
            "macro_f1": sum(f1) / len(f1), "confusion_matrix": confusion,
            "coverage": len(accepted) / len(rows),
            "accuracy_among_accepted": (sum(row["label"] == row[field]["choice"] for row in accepted) / len(accepted)) if accepted else None}


def main():
    source = (ROOT / "korean_eval_cases.json").read_bytes()
    dataset = json.loads(source)
    namespace = load_app_definitions()
    model = KoreanSentiment()
    jev = namespace["load_jev"]()
    rows = []
    for i, case in enumerate(dataset["clear_cases"]):
        start = time.perf_counter()
        primary = model.classify([case["text"]])[0]
        main_seconds = time.perf_counter() - start
        start = time.perf_counter()
        baseline = jev.decide(case["text"], {"overall": namespace["QUESTIONS"]["overall"]})["answers"]["overall"]
        rows.append({**case, "primary": primary, "openjevx": baseline,
                     "primary_seconds": main_seconds, "openjevx_seconds": time.perf_counter() - start})
        print(f"Evaluation {i+1}/{len(dataset['clear_cases'])}: {primary['choice']} / {baseline['choice']} (reference {case['label']})", flush=True)
    regression_text = "음식이 차갑고 주문한 메뉴도 잘못 나왔어요. 다시는 방문하고 싶지 않아요."
    regression = model.analyze(regression_text)
    challenges = [{**case, "result": model.analyze(case["text"])} for case in dataset["challenge_cases"]]
    report = {"created_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
              "dataset_sha256": hashlib.sha256(source).hexdigest(),
              "description": dataset["description"], "model": MODEL_ID, "revision": REVISION,
              "app_sha256": hashlib.sha256((ROOT / "app.py").read_bytes()).hexdigest(),
              "primary_metrics": metrics(rows, "primary"), "openjevx_metrics": metrics(rows, "openjevx"),
              "rows": rows, "user_reported_regression": {"text": regression_text, "result": regression},
              "challenges_unscored": challenges,
              "limitations": ["18 manually labelled clear examples, six per class; not a public independent benchmark",
                              "No training or prompt tuning on these examples; developer chose this small task set",
                              "Mixed/sarcasm examples and the user-reported regression are not included in clear-case accuracy",
                              "Confidence threshold 0.65 and margin 0.15 are uncalibrated display heuristics"]}
    (OUT / "korean_comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"primary": report["primary_metrics"], "openjevx": report["openjevx_metrics"],
                      "regression": regression["answers"], "final_sentence": regression["final_sentence"]}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
