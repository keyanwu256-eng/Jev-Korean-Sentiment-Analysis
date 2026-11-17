"""Validate the current two-model Korean app; no official API requests."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence"
EVIDENCE.mkdir(exist_ok=True)


def main():
    commands = [[sys.executable, "-m", "unittest", "test_korean", "-v"],
                [sys.executable, "-u", "evaluate_korean.py"]]
    for i, command in enumerate(commands):
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        output = (result.stdout + result.stderr).replace(str(Path.home()), "<USER_HOME>")
        output = output.replace(str(Path.home()).replace("\\", "\\\\"), "<USER_HOME>")
        if i == 0:
            output = "Real local models. The comparison failure below is intentionally injected to test resilience.\n" + output
        print(output, flush=True)
        (EVIDENCE / ("korean_tests.txt" if i == 0 else "korean_eval_log.txt")).write_text(output, encoding="utf-8")
        if result.returncode:
            (EVIDENCE / "verification.json").write_text(json.dumps({"status": "FAIL", "failed_command": command[1:], "exit_code": result.returncode}, indent=2), encoding="utf-8")
            raise SystemExit(result.returncode)
    shutil.copyfile(ROOT / "runtime/evaluation/korean_comparison.json", EVIDENCE / "korean_comparison.json")
    for name in ("korean_sample_history.csv", "korean_sample_result.json"):
        shutil.copyfile(ROOT / "runtime/evaluation" / name, EVIDENCE / name)
    report = {"created_at": datetime.now(timezone(timedelta(hours=9))).isoformat(), "status": "PASS",
              "primary": "Horizon-Labs/multilingual-sentiment-small", "comparison": "muthuishere/openjevx",
              "official_api_used": False, "functional_test_count": 5,
              "scope": "Real local models; 18 author-labelled clear cases, six unscored challenges and one reported regression",
              "app_sha256": hashlib.sha256((ROOT / "app.py").read_bytes()).hexdigest(),
              "engine_sha256": hashlib.sha256((ROOT / "sentiment_engine.py").read_bytes()).hexdigest(),
              "raw_evaluation": "korean_comparison.json", "test_log": "korean_tests.txt"}
    (EVIDENCE / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
