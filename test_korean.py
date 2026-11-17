import unittest
import copy
import csv
import io
import json
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from sentiment_engine import KoreanSentiment, sentences, uncertainty, sentence_composition
from evaluate_korean import load_app_definitions


class SentenceTests(unittest.TestCase):
    def test_final_sentence_and_decimals(self):
        self.assertEqual(sentences("맛은 괜찮아요. 다시 가고 싶지는 않아요.")[-1], "다시 가고 싶지는 않아요.")
        self.assertEqual(sentences("가격은 3.5달러입니다. 괜찮아요.")[0], "가격은 3.5달러입니다.")
        self.assertEqual(sentences("맛있어요!다음에 또 올게요.")[-1], "다음에 또 올게요.")
        self.assertEqual(sentences("한 문장뿐입니다"), ["한 문장뿐입니다"])

    def test_uncertain_is_not_neutral(self):
        raw = {"choice": "negative", "probabilities": {"negative": 0.4, "positive": 0.35, "neutral": 0.25}}
        self.assertTrue(uncertainty(raw))
        self.assertEqual(raw["choice"], "negative")
        self.assertFalse(uncertainty({"probabilities": {"neutral": 0.9, "negative": 0.05, "positive": 0.05}}))

    def test_neutral_and_sentence_coexistence_are_separate(self):
        def answer(label, probability=0.9):
            return {"choice": label, "probabilities": {name: probability if name == label else (1-probability)/2
                                                       for name in ("positive", "negative", "neutral")}}
        result = {"answers": {"overall": answer("neutral")}, "sentences": [answer("positive"), answer("negative")]}
        before = copy.deepcopy(result)
        self.assertEqual(sentence_composition(result)["status"], "coexistence_observed")
        self.assertEqual(result, before)
        self.assertEqual(sentence_composition({"sentences": [answer("neutral")]})["status"], "coexistence_not_observed")
        self.assertEqual(sentence_composition({"sentences": [answer("positive", 0.4), answer("negative")]})["status"], "insufficient_evidence")
        self.assertEqual(sentence_composition({})["status"], "unavailable")


class RealModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = KoreanSentiment()

    def test_user_regression_and_separate_ending(self):
        text = "음식이 차갑고 주문한 메뉴도 잘못 나왔어요. 다시는 방문하고 싶지 않아요."
        result = self.model.analyze(text)
        self.assertEqual(result["answers"]["overall"]["choice"], "negative")
        self.assertEqual(result["answers"]["final"]["choice"], "negative")
        self.assertEqual(result["final_sentence"], "다시는 방문하고 싶지 않아요.")
        for answer in result["answers"].values():
            self.assertAlmostEqual(sum(answer["probabilities"].values()), 1, places=5)

    def test_truncation_and_sentence_limit_are_explicit(self):
        text = "이 제품에 대한 설명입니다. " * 100
        result = self.model.analyze(text)
        self.assertTrue(result["answers"]["overall"]["truncated"])
        self.assertTrue(result["sentence_limit_applied"])
        self.assertEqual(len(result["sentences"]), 20)

    def test_real_app_and_failed_comparison_do_not_replace_primary(self):
        app = str(Path(__file__).with_name("app.py"))
        at = AppTest.from_file(app, default_timeout=120).run()
        at.button[3].click().run()
        self.assertTrue(at.warning)
        self.assertFalse(at.session_state.history)
        at.checkbox(key="compare_jev").uncheck().run()
        at.text_area[0].input("음식이 차갑고 주문한 메뉴도 잘못 나왔어요. 다시는 방문하고 싶지 않아요.")
        at.button[3].click().run()
        self.assertFalse(at.error)
        self.assertFalse(at.exception)
        displayed = {metric.label: metric.value for metric in at.metric}
        self.assertEqual(displayed["전체 원문 분류"], "부정")
        self.assertEqual(displayed["마지막 문장 평가"], "부정")
        record = at.session_state.history[0]
        self.assertNotIn("comparison", record)
        self.assertEqual(record["model"], "Horizon-Labs/multilingual-sentiment-small")
        # The optional comparison must not destroy a successful primary result.
        at.checkbox(key="compare_jev").check().run()
        at.button[3].click().run()
        self.assertFalse(at.exception)
        self.assertFalse(at.error)
        record = at.session_state.history[0]
        self.assertIn("comparison", record)
        self.assertEqual(record["result"]["answers"]["overall"]["choice"], "negative")
        self.assertEqual(record["comparison"]["final_sentence"], record["final_sentence"])
        export_history = load_app_definitions()["export_history"]
        csv_bytes = export_history([record])
        rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
        self.assertEqual(rows[1][1], record["review"])
        self.assertEqual(rows[1][7], record["model"])
        self.assertEqual(rows[1][8], record["final_sentence"])
        unsafe = {**record, "review": "=1+1", "final_sentence": "=2+2"}
        protected = list(csv.reader(io.StringIO(export_history([unsafe]).decode("utf-8-sig"))))
        self.assertTrue(protected[1][1].startswith("'="))
        self.assertTrue(protected[1][8].startswith("'="))
        out = Path(__file__).resolve().parent / "runtime" / "evaluation"
        out.mkdir(parents=True, exist_ok=True)
        (out / "korean_sample_history.csv").write_bytes(csv_bytes)
        (out / "korean_sample_result.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        with patch("sentiment_engine.compare_with_jev", side_effect=RuntimeError("test comparison failure")):
            at.button[3].click().run()
        self.assertFalse(at.exception)
        record = at.session_state.history[0]
        self.assertIn("comparison_error", record)
        self.assertNotIn("comparison", record)
        self.assertEqual(record["result"]["answers"]["overall"]["choice"], "negative")
        at.text_area[0].input("새 입력").run()
        self.assertTrue(any("이전" in item.value for item in at.info))
        at.button[4].click().run()
        self.assertFalse(at.exception)
        self.assertFalse(at.session_state.history)

    def test_hotel_mixed_review_keeps_raw_neutral_and_flags_jev(self):
        at = AppTest.from_file(str(Path(__file__).with_name("app.py")), default_timeout=120).run()
        text = "위치는 편리하고 직원도 친절했어요. 하지만 방에서 담배 냄새가 심하게 나서 다시 묵고 싶지는 않아요."
        at.text_area[0].input(text)
        at.button[3].click().run()
        self.assertFalse(at.exception)
        self.assertFalse(at.error)
        displayed = {metric.label: metric.value for metric in at.metric}
        self.assertEqual(displayed["전체 원문 분류"], "중립 / 균형")
        self.assertEqual(displayed["문장 감정 구성"], "긍정·부정 공존")
        self.assertEqual(displayed["마지막 문장 평가"], "부정")
        record = at.session_state.history[0]
        self.assertEqual(record["result"]["answers"]["overall"]["choice"], "neutral")
        self.assertEqual(record["interpretation"]["status"], "coexistence_observed")
        self.assertTrue(any(item.value.startswith("Jev 전체: 판단 불확실") for item in at.text))
        self.assertTrue(any(item.value.startswith("Jev 마지막 문장: 판단 불확실") for item in at.text))
        csv_bytes = load_app_definitions()["export_history"]([record])
        row = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8-sig"))))[1]
        self.assertEqual(row[13], "coexistence_observed")
        self.assertEqual(row[14:16], ["True", "True"])
        out = Path(__file__).resolve().parent / "runtime/evaluation"
        out.mkdir(parents=True, exist_ok=True)
        (out / "hotel_interpretation_result.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main(verbosity=2)
