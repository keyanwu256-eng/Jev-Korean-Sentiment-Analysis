"""Rebuild evidence with the real cached model; run from the repository folder."""
import ast
import csv
import hashlib
import io
import json
import platform
import time
import traceback
from datetime import datetime, timezone, timedelta
from importlib.metadata import version
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "evidence"
OUT.mkdir(exist_ok=True)
notebook = next(ROOT.glob("*.ipynb"))
nb = json.loads(notebook.read_text(encoding="utf-8"))


def assignment(cell, name):
    for node in ast.parse("".join(nb["cells"][cell]["source"])).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(name)


reviews = assignment(9, "reviews")
truth = assignment(12, "true_labels")
old_questions = assignment(10, "comparison_questions")
recorded = []
for output in nb["cells"][10]["outputs"]:
    for line in "".join(output.get("text", [])).splitlines():
        if line.startswith("{"):
            recorded.append(ast.literal_eval(line))
assert len(recorded) == 10
old_matches = sum(r["전체 감성"] == r["최종 평가"] for r in recorded)
old_overall_correct = sum(r["전체 감성"] == t for r, t in zip(recorded, truth))
old_final_correct = sum(r["최종 평가"] == t for r, t in zip(recorded, truth))
assert (old_matches, old_overall_correct, old_final_correct) == (6, 4, 3)
(OUT / "notebook_recorded_results.json").write_text(json.dumps({
    "source": notebook.name, "source_cell_zero_based": 10,
    "description": "Existing saved notebook output, not a new execution",
    "questions": old_questions, "rows": recorded, "reference_labels": truth,
    "matches": old_matches, "overall_correct": old_overall_correct, "final_correct": old_final_correct,
}, ensure_ascii=False, indent=2), encoding="utf-8")

# Execute only imports, constants and function definitions from the app, without its UI.
source = (ROOT / "app.py").read_text(encoding="utf-8")
tree = ast.parse(source)
nodes = []
for node in tree.body:
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "set_page_config":
        break
    nodes.append(node)
namespace = {"__name__": "project_verification"}
exec(compile(ast.Module(body=nodes, type_ignores=[]), "app.py", "exec"), namespace)
started = time.perf_counter()
try:
    jev = namespace["load_jev"]()
except Exception:
    failure = traceback.format_exc()
    # Share dependency evidence without publishing a personal filesystem path.
    failure = failure.replace(str(Path.home()), "<USER_HOME>")
    failure = failure.replace(str(ROOT), "<PROJECT>")
    (OUT / "model_load_failure.txt").write_text(failure, encoding="utf-8")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90).run()
    at.radio(key="provider").set_value("로컬 OpenJevX").run()
    assert not at.exception
    at.button[3].click().run()
    assert at.warning and not at.session_state.history
    at.button[2].click().run()
    assert at.text_area[0].value == namespace["EXAMPLES"]["혼합 리뷰"]
    at.button[3].click().run()
    assert at.error and at.exception and not at.session_state.history
    report = {
        "created_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "status": "BLOCKED_MODEL_LOAD",
        "passed_checks": ["Initial page renders", "Empty review is rejected", "Mixed example fills input", "Model load error is shown and no false result is stored"],
        "blocked_checks": ["Real model analysis", "Result probability rendering", "History and download end-to-end"],
        "failure_evidence": "model_load_failure.txt", "python": platform.python_version(),
        "packages": {p: version(p) for p in ["streamlit", "huggingface-hub", "numpy", "onnxruntime", "tokenizers"]},
        "app_sha256": hashlib.sha256(source.encode()).hexdigest(),
    }
    (OUT / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    raise SystemExit(2)
fresh = []
for i, review in enumerate(reviews):
    result = jev.decide(review, namespace["QUESTIONS"])
    fresh.append({"id": i + 1, "review": review, "reference_label": truth[i], "result": result})
    print(f"Model evaluation {i+1}/10", flush=True)
labels = {"positive": "긍정", "negative": "부정", "neutral": "중립"}
metrics = {
    "count": len(fresh),
    "matches": sum(r["result"]["answers"]["overall"]["choice"] == r["result"]["answers"]["final"]["choice"] for r in fresh),
    "overall_correct": sum(labels[r["result"]["answers"]["overall"]["choice"]] == r["reference_label"] for r in fresh),
    "final_correct_against_same_overall_reference": sum(labels[r["result"]["answers"]["final"]["choice"]] == r["reference_label"] for r in fresh),
}
(OUT / "current_app_results.json").write_text(json.dumps({
    "created_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "app_sha256": hashlib.sha256(source.encode()).hexdigest(),
    "provider": "openjevx", "model_revision": namespace["MODEL_REVISION"], "questions": namespace["QUESTIONS"],
    "metrics": metrics, "seconds": round(time.perf_counter() - started, 2), "rows": fresh,
}, ensure_ascii=False, indent=2), encoding="utf-8")

checks = []
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
at.radio(key="provider").set_value("로컬 OpenJevX").run()
assert not at.exception
at.button[3].click().run()
assert at.warning and not at.session_state.history
checks.append("Empty input produces a warning and adds no history")
at.button[2].click().run()
assert at.text_area[0].value == namespace["EXAMPLES"]["혼합 리뷰"]
at.button[3].click().run()
assert not at.exception and not at.error and len(at.metric) == 2
assert len(at.session_state.history) == 1 and len(at.json) == 1
checks.append("Example input, real model analysis, two result cards, JSON and history render without errors")
record = at.session_state.history[0]
exported = namespace["export_history"]([record])
rows = list(csv.reader(io.StringIO(exported.decode("utf-8-sig"))))
assert len(rows) == 2 and rows[1][1] == record["review"]
(OUT / "sample_history.csv").write_bytes(exported)
(OUT / "sample_result.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
checks.append("CSV output round trips correctly with Korean text; sample CSV and JSON saved")
at.text_area[0].input("changed input").run()
assert any("이전" in item.value for item in at.info)
checks.append("Editing input preserves prior result with a stale-result notice")
at.button[4].click().run()
assert not at.exception and not at.session_state.history and "latest" not in at.session_state
checks.append("Clear history removes stored records and latest result")
report = {"created_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
          "provider": "openjevx", "official_live_tested": False,
          "status": "PASS", "checks": checks, "python": platform.python_version(),
          "packages": {p: version(p) for p in ["streamlit", "huggingface-hub", "numpy", "onnxruntime", "tokenizers"]},
          "app_sha256": hashlib.sha256(source.encode()).hexdigest()}
(OUT / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"verification": report, "current_metrics": metrics}, ensure_ascii=False), flush=True)
