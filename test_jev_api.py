"""Contract/UI tests use simulated official responses, never paid API calls."""
import copy
import io
import json
import unittest
import urllib.error
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from streamlit.testing.v1 import AppTest

from jev_api import JevAPIError, decide_official

QUESTIONS = {qid: {"type": "choice", "instructions": "Classify sentiment",
                   "criteria": {"positive": "positive", "negative": "negative", "neutral": "neutral"}}
             for qid in ("overall", "final")}
FIXTURE = {"model": "jev-1.13.0", "answers": {
    qid: {"type": "choice", "choice": "positive", "confidence": 0.8,
          "probabilities": {"positive": 0.9, "negative": 0.05, "neutral": 0.05}}
    for qid in QUESTIONS}, "usage": {"input_tokens": 100, "output_tokens": 20}}


@contextmanager
def response_fixture(data):
    opener = MagicMock()
    opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(data).encode()
    with patch("jev_api.urllib.request.build_opener", return_value=opener):
        yield opener


class OfficialContractTests(unittest.TestCase):
    def test_payload_auth_and_response(self):
        with response_fixture(FIXTURE) as opener:
            result = decide_official("test review", QUESTIONS, "synthetic-test-key")
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.typesafe.ai/v1/systemone")
        self.assertEqual(request.get_header("Authorization"), "Bearer synthetic-test-key")
        self.assertEqual(json.loads(request.data)["questions"], QUESTIONS)
        self.assertEqual(json.loads(request.data)["state"], "test review")
        self.assertEqual(result, FIXTURE)
        self.assertNotIn("synthetic-test-key", json.dumps(result))
        self.assertEqual(opener.open.call_count, 1)

    def test_missing_key_does_not_connect(self):
        with patch("jev_api.urllib.request.build_opener") as opener:
            with self.assertRaises(JevAPIError):
                decide_official("review", QUESTIONS, "")
            opener.assert_not_called()

    def test_http_error_is_sanitized_and_not_retried(self):
        for code in (401, 402, 403, 429, 500, 302):
            with self.subTest(code=code), patch("jev_api.urllib.request.build_opener") as factory:
                factory.return_value.open.side_effect = urllib.error.HTTPError(
                    "https://api.typesafe.ai", code, "synthetic-secret-in-message", {}, io.BytesIO(b"secret"))
                with self.assertRaises(JevAPIError) as caught:
                    decide_official("review", QUESTIONS, "synthetic-test-key")
                self.assertIn(str(code), str(caught.exception))
                self.assertNotIn("secret", str(caught.exception))
                self.assertEqual(factory.return_value.open.call_count, 1)

    def test_network_failure_is_not_retried(self):
        with patch("jev_api.urllib.request.build_opener") as factory:
            factory.return_value.open.side_effect = TimeoutError("sensitive")
            with self.assertRaises(JevAPIError) as caught:
                decide_official("review", QUESTIONS, "synthetic-test-key")
            self.assertNotIn("sensitive", str(caught.exception))
            self.assertEqual(factory.return_value.open.call_count, 1)

    def test_invalid_schema_does_not_become_result(self):
        variants = [{}, copy.deepcopy(FIXTURE), copy.deepcopy(FIXTURE), copy.deepcopy(FIXTURE)]
        variants[1]["answers"]["overall"]["choice"] = "unknown"
        variants[2]["answers"]["overall"]["confidence"] = float("nan")
        variants[3]["answers"]["overall"]["probabilities"]["positive"] = 0
        for data in variants:
            with self.subTest(data=data), response_fixture(data), self.assertRaises(JevAPIError):
                decide_official("review", QUESTIONS, "synthetic-test-key")

    def test_ui_requires_key_and_consent_then_records_provider(self):
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": ""}):
            at = AppTest.from_file(str(Path(__file__).with_name("app.py")), default_timeout=60).run()
            self.assertFalse(at.exception)
            self.assertEqual(at.radio[0].value, "공식 Jev API")
            at.text_area[0].input("음식이 정말 맛있어요.")
            with patch("jev_api.decide_official", return_value=FIXTURE) as call:
                at.button[3].click().run()
                call.assert_not_called()
                at.text_input(key="typesafe_key").input("synthetic-test-key").run()
                at.button[3].click().run()
                call.assert_not_called()
                at.checkbox(key="api_consent").check().run()
                at.button[3].click().run()
                call.assert_called_once()
            self.assertFalse(at.exception)
            self.assertFalse(at.error)
            self.assertEqual(len(at.metric), 2)
            record = at.session_state.history[0]
            self.assertEqual(record["provider"], "typesafe_official")
            self.assertEqual(record["resolved_model"], "jev-1.13.0")
            self.assertNotIn("synthetic-test-key", json.dumps(record))
            # Simulated success must not be mistaken for a real official run.
            at.radio(key="provider").set_value("로컬 OpenJevX").run()
            self.assertTrue(any("이전 모델" in x.value for x in at.info))
            at.radio(key="provider").set_value("공식 Jev API").run()
            at.text_input(key="typesafe_key").input("synthetic-test-key").run()
            at.checkbox(key="api_consent").check().run()
            with patch("jev_api.decide_official", side_effect=JevAPIError("test failure")):
                at.button[3].click().run()
            self.assertTrue(at.error)
            self.assertFalse(at.exception)
            self.assertEqual(len(at.session_state.history), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
