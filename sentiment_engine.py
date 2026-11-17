"""Local Korean-capable sentiment classification, with raw outputs preserved."""
import json
import os
import re
from pathlib import Path

MODEL_ID = "Horizon-Labs/multilingual-sentiment-small"
REVISION = "e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac"
MAX_TOKENS = 512
MAX_SENTENCES = 20


def sentences(text):
    """Lightweight sentence heuristic, not a Korean morphological parser."""
    parts = re.split(r'(?<=[!?。！？])\s*|(?<=\.)\s+(?=\S)|(?<=\.)\s*(?=[가-힣A-Za-z“])|\n+', text.strip())
    return [part.strip() for part in parts if part.strip()] or [text.strip()]


def uncertainty(answer, threshold=0.65, margin=0.15):
    values = sorted(answer["probabilities"].values(), reverse=True)
    return values[0] < threshold or values[0] - values[1] < margin


def sentence_composition(result):
    """A sentence-level observation, never a replacement for the raw label."""
    items = result.get("sentences", [])
    counts = {"positive": 0, "negative": 0, "neutral": 0, "uncertain": 0}
    for item in items:
        counts["uncertain" if uncertainty(item) else item["choice"]] += 1
    if not items:
        status = "unavailable"
    elif counts["positive"] and counts["negative"]:
        status = "coexistence_observed"
    elif counts["uncertain"] or result.get("sentence_limit_applied") or any(item.get("truncated") for item in items):
        status = "insufficient_evidence"
    else:
        status = "coexistence_not_observed"
    return {"method": "confident_sentence_labels", "status": status, "counts": counts,
            "scope": "analyzed_sentences_only", "does_not_override_raw_prediction": True}


def compare_with_jev(jev, review, final_sentence, questions):
    overall = jev.decide(review, {"overall": questions["overall"]})
    final = jev.decide(final_sentence, {"final": questions["final"]})
    return {"answers": {**overall["answers"], **final["answers"]}, "final_sentence": final_sentence}


class KoreanSentiment:
    def __init__(self):
        import numpy as np
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from huggingface_hub.errors import LocalEntryNotFoundError
        from tokenizers import Tokenizer

        self.np = np
        cache = os.environ.get("JEV_SENTIMENT_CACHE") or str(Path(__file__).resolve().parent / "runtime" / "model_cache")

        def get(name):
            try:
                return hf_hub_download(MODEL_ID, name, revision=REVISION, cache_dir=cache, local_files_only=True)
            except LocalEntryNotFoundError:
                return hf_hub_download(MODEL_ID, name, revision=REVISION, cache_dir=cache)

        config = json.loads(Path(get("config.json")).read_text(encoding="utf-8"))
        self.labels = {int(key): value.lower() for key, value in config["id2label"].items()}
        if set(self.labels.values()) != {"negative", "neutral", "positive"}:
            raise ValueError("Unexpected model labels")
        self.tokenizer = Tokenizer.from_file(get("tokenizer.json"))
        self.tokenizer.no_padding()
        self.tokenizer.no_truncation()
        options = ort.SessionOptions()
        options.intra_op_num_threads = min(4, os.cpu_count() or 1)
        self.session = ort.InferenceSession(get("onnx/model_quantized.onnx"), sess_options=options,
                                           providers=["CPUExecutionProvider"])
        self.input_names = {item.name for item in self.session.get_inputs()}
        self.pad_id = config.get("pad_token_id", 0)

    def classify(self, texts):
        np = self.np
        # Tokenize fully to report truncation, then keep one explicit limit.
        encodings = self.tokenizer.encode_batch(texts)
        counts = [len(e.ids) for e in encodings]
        length = min(MAX_TOKENS, max(counts))
        ids = np.full((len(texts), length), self.pad_id, dtype=np.int64)
        mask = np.zeros_like(ids)
        for i, encoding in enumerate(encodings):
            tokens = encoding.ids[:MAX_TOKENS]
            if counts[i] > MAX_TOKENS:
                tokens[-1] = encoding.ids[-1]  # retain final separator token
            ids[i, :len(tokens)] = tokens
            mask[i, :len(tokens)] = 1
        available = {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)}
        if not self.input_names <= available.keys():
            raise ValueError("Unsupported ONNX input schema")
        logits = self.session.run(None, {name: available[name] for name in self.input_names})[0]
        logits = logits - logits.max(axis=-1, keepdims=True)
        probabilities = np.exp(logits)
        probabilities /= probabilities.sum(axis=-1, keepdims=True)
        outputs = []
        for i, row in enumerate(probabilities):
            distribution = {self.labels[j]: float(p) for j, p in enumerate(row)}
            choice = max(distribution, key=distribution.get)
            outputs.append({"type": "choice", "choice": choice, "confidence": distribution[choice],
                            "probabilities": distribution, "tokens": counts[i], "truncated": counts[i] > MAX_TOKENS})
        return outputs

    def analyze(self, review):
        all_sentences = sentences(review)
        selected = all_sentences if len(all_sentences) <= MAX_SENTENCES else all_sentences[:MAX_SENTENCES - 1] + all_sentences[-1:]
        unique = list(dict.fromkeys([review, *selected]))
        classified = dict(zip(unique, self.classify(unique)))
        return {"answers": {"overall": classified[review], "final": classified[all_sentences[-1]]},
                "sentences": [{"text": text, **classified[text]} for text in selected],
                "final_sentence": all_sentences[-1], "sentence_count": len(all_sentences),
                "sentence_limit_applied": len(selected) < len(all_sentences),
                "model": MODEL_ID, "revision": REVISION, "provider": "local_multilingual_sentiment"}
