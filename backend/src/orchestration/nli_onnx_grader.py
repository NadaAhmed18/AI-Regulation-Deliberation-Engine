"""
ONNX STANCE GRADER — Optional, CPU-Oriented Local Inference Backend

An opt-in alternative to `orchestration/nli_grader.py`'s
`DebertaStanceGrader`, using ONNX Runtime (via Hugging Face `optimum`)
instead of PyTorch, with optional dynamic INT8 quantization on top.

Why this is a SEPARATE class, not folded into `DebertaStanceGrader`:
    - It requires `optimum[onnxruntime]`, which cannot currently be
      installed alongside this project's `sentence-transformers>=6.0.0`
      (every published `optimum[onnxruntime]` version pins
      `transformers<5.0`, while `sentence-transformers>=6.0.0` requires
      `transformers>=5.0.0` -- a genuine, currently unresolvable
      conflict, confirmed via `uv sync` failing on it). This module
      must be run from a **separate Python environment**
      (`pip install torch transformers optimum[onnxruntime] langfuse`),
      not this project's `uv`-managed one. See
      `docs/NLI-Grader-Optimizations.md` Section 2.1a for the full story
      and exact setup commands.
    - Export + quantization is a real, model-specific correctness risk
      here, not a generic given: DeBERTa-v2/v3's disentangled attention
      mechanism uses custom ops that have historically been more
      finicky to export/quantize cleanly than a standard BERT-style
      encoder. This class's output is NOT assumed equivalent to the
      PyTorch backend's — it needs to be checked, which is exactly what
      `scripts/benchmark_nli_backends.py` does (latency + max
      entailment-probability difference across backends, on real
      statements).
    - Whether it's actually *faster* depends entirely on the deployment
      target. ONNX Runtime's main advantage is CPU inference; on GPU,
      `DebertaStanceGrader`'s FP16 path is usually competitive or better
      with far less integration risk (no export step, no quantization
      accuracy question).

Decision rule (see docs/NLI-Grader-Optimizations.md for the full
writeup): only switch `STANCE_GRADER_ENGINE`/this class into real use
after running the benchmark script on the actual target hardware and
confirming both (a) a meaningful latency win over the PyTorch backend
there, and (b) that its entailment probabilities are close enough to
PyTorch's that `stance_utils.compute_stance_score` produces materially
the same stance score and shift.

Not implemented here (deliberately):
    - Static (calibration-based) quantization. Dynamic quantization
      needs no calibration dataset and is the standard first thing to
      try for encoder classification models; static quantization is a
      further, riskier step with its own calibration-set-selection
      questions — not worth adding until dynamic quantization is shown
      to be insufficient on the benchmark.
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langfuse import get_client, observe

from src.orchestration.nli_grader import DEFAULT_NLI_MODEL, DebertaStanceGrader
from src.utils.stance_utils import compute_stance_result

logger = logging.getLogger(__name__)

DEFAULT_ONNX_CACHE_DIR = "models/onnx/nli-deberta-v3-large"


def _pairwise_softmax(pair_logits) -> List[float]:
    """
    Minimal 2-way softmax over a (N, 2) array, returning P(entailment)
    for each row (index 0). Implemented by hand with plain math instead
    of pulling in scipy/torch, since this file's whole point is to have
    a lean, ONNX-Runtime-only inference path.
    """
    import math

    probs = []
    for entail_logit, contra_logit in pair_logits:
        m = max(entail_logit, contra_logit)
        exp_entail = math.exp(entail_logit - m)
        exp_contra = math.exp(contra_logit - m)
        probs.append(exp_entail / (exp_entail + exp_contra))
    return probs


class ONNXStanceGrader:
    """
    ONNX Runtime-backed stance grader. Same public interface as
    `DebertaStanceGrader` (`evaluate_stance`, `evaluate_batch`), so it
    can be substituted wherever that class is used — but only after
    benchmarking, per this module's docstring.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_NLI_MODEL,
        cache_dir: str = DEFAULT_ONNX_CACHE_DIR,
        quantize: bool = True,
        max_length: int = 512,
    ):
        try:
            from optimum.onnxruntime import ORTModelForSequenceClassification, ORTQuantizer
            from optimum.onnxruntime.configuration import AutoQuantizationConfig
        except ImportError as exc:
            raise ImportError(
                "ONNXStanceGrader requires 'optimum[onnxruntime]', which "
                "cannot be installed into this project's main uv-managed "
                "environment (conflicts with sentence-transformers>=6.0.0 "
                "-- see docs/NLI-Grader-Optimizations.md Section 2.1a). "
                "Run this from a separate venv: "
                "pip install torch transformers optimum[onnxruntime] langfuse"
            ) from exc

        from transformers import AutoTokenizer

        self.model_name = model_name
        self.max_length = max_length
        self.quantized = quantize
        cache_path = Path(cache_dir)
        quantized_file = "model_quantized.onnx"
        plain_file = "model.onnx"

        if quantize and (cache_path / quantized_file).exists():
            logger.info("Loading cached quantized ONNX model from %s", cache_path)
            self.model = ORTModelForSequenceClassification.from_pretrained(
                cache_path, file_name=quantized_file
            )
        elif not quantize and (cache_path / plain_file).exists():
            logger.info("Loading cached ONNX model from %s", cache_path)
            self.model = ORTModelForSequenceClassification.from_pretrained(
                cache_path, file_name=plain_file
            )
        else:
            logger.info(
                "Exporting %s to ONNX (first run; cached under %s after this)",
                model_name, cache_path,
            )
            cache_path.mkdir(parents=True, exist_ok=True)
            ort_model = ORTModelForSequenceClassification.from_pretrained(model_name, export=True)

            if quantize:
                quantizer = ORTQuantizer.from_pretrained(ort_model)
                # avx2 is the broadly-compatible default for x86 CPUs.
                # Pass a different AutoQuantizationConfig (e.g.
                # .avx512_vnni(...) or .arm64(...)) if your deployment
                # target is known and more specific than "generic x86".
                qconfig = AutoQuantizationConfig.avx2(is_static=False, per_channel=False)
                quantizer.quantize(save_dir=str(cache_path), quantization_config=qconfig)
                self.model = ORTModelForSequenceClassification.from_pretrained(
                    cache_path, file_name=quantized_file
                )
            else:
                ort_model.save_pretrained(str(cache_path))
                self.model = ORTModelForSequenceClassification.from_pretrained(
                    cache_path, file_name=plain_file
                )

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.tokenizer.save_pretrained(str(cache_path))

        # Reuse the exact same dynamic label-discovery logic as the
        # PyTorch backend, so both backends agree on which logit index
        # means "entailment"/"contradiction" for this model -- avoids
        # maintaining two copies of that lookup.
        self.entailment_idx, self.contradiction_idx = DebertaStanceGrader._find_label_indices(
            self.model.config.id2label, model_name
        )

        logger.info(
            "ONNX NLI grader ready | model=%s | quantized=%s | entailment_idx=%s | contradiction_idx=%s",
            model_name, quantize, self.entailment_idx, self.contradiction_idx,
        )

    def _score_pairs(self, premises: List[str], hypotheses: List[str]) -> Tuple[float, ...]:
        if len(premises) != len(hypotheses):
            raise ValueError("premises and hypotheses must have the same length.")

        inputs = self.tokenizer(
            premises,
            hypotheses,
            truncation=True,
            max_length=self.max_length,
            padding=True,
            return_tensors="pt",
        )
        outputs = self.model(**inputs)
        logits = outputs.logits.detach().cpu().tolist()

        pair_logits = [
            (row[self.entailment_idx], row[self.contradiction_idx]) for row in logits
        ]
        return tuple(_pairwise_softmax(pair_logits))

    @observe(name="onnx_nli_stance_evaluation", as_type="evaluator", capture_input=False)
    def evaluate_stance(
        self,
        topic: str,
        statement: str,
        previous_score: Optional[float] = None,
        pro_proposition: Optional[str] = None,
        anti_proposition: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Same contract as `DebertaStanceGrader.evaluate_stance`."""
        start_time = time.perf_counter()

        hypo_pro = pro_proposition or f"The speaker is in favor of {topic}."
        hypo_anti = anti_proposition or f"The speaker is opposed to {topic}."

        prob_pro, prob_anti = self._score_pairs(
            premises=[statement, statement],
            hypotheses=[hypo_pro, hypo_anti],
        )

        result = compute_stance_result(
            pro_probability=prob_pro,
            anti_probability=prob_anti,
            previous_score=previous_score,
        )
        result["engine"] = f"{self.model_name} (onnx{'-int8' if self.quantized else ''})"
        latency_seconds = time.perf_counter() - start_time

        get_client().update_current_span(
            metadata={
                "model": self.model_name,
                "backend": "onnxruntime",
                "quantized": self.quantized,
                "pro_probability": round(prob_pro, 3),
                "anti_probability": round(prob_anti, 3),
                "current_stance_score": result["current_stance_score"],
                "shift_magnitude": result["shift_magnitude"],
                "latency_seconds": round(latency_seconds, 4),
            }
        )

        logger.debug(
            "ONNX NLI stance evaluated | score=%.3f | pro=%.3f | anti=%.3f | latency=%.3fs",
            result["current_stance_score"], prob_pro, prob_anti, latency_seconds,
        )
        return result

    @observe(name="onnx_nli_batch_stance_evaluation", as_type="evaluator", capture_input=False)
    def evaluate_batch(
        self,
        topic: str,
        statements: List[Dict[str, Any]],
        pro_proposition: Optional[str] = None,
        anti_proposition: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Same contract as `DebertaStanceGrader.evaluate_batch`."""
        if not statements:
            return []

        start_time = time.perf_counter()

        hypo_pro = pro_proposition or f"The speaker is in favor of {topic}."
        hypo_anti = anti_proposition or f"The speaker is opposed to {topic}."

        premises: List[str] = []
        hypotheses: List[str] = []
        for item in statements:
            premises.extend([item["statement"], item["statement"]])
            hypotheses.extend([hypo_pro, hypo_anti])

        probs = self._score_pairs(premises=premises, hypotheses=hypotheses)

        results: List[Dict[str, Any]] = []
        for index, item in enumerate(statements):
            prob_pro, prob_anti = probs[index * 2], probs[index * 2 + 1]
            result = compute_stance_result(
                pro_probability=prob_pro,
                anti_probability=prob_anti,
                previous_score=item.get("previous_score"),
            )
            result["engine"] = f"{self.model_name} (onnx{'-int8' if self.quantized else ''})"
            result["agent_name"] = item.get("agent_name")
            results.append(result)

        latency_seconds = time.perf_counter() - start_time
        get_client().update_current_span(
            metadata={
                "model": self.model_name,
                "backend": "onnxruntime",
                "quantized": self.quantized,
                "batch_size": len(statements),
                "latency_seconds": round(latency_seconds, 4),
                "agent_scores": {r["agent_name"]: r["current_stance_score"] for r in results},
            }
        )
        return results


if __name__ == "__main__":
    # Manual smoke test -- NOT run as part of any automated check, since
    # it requires `optimum[onnxruntime]` installed and will export +
    # cache the model on first run. Use `scripts/benchmark_nli_backends.py`
    # for the real PyTorch-vs-ONNX comparison.
    logging.basicConfig(level=logging.INFO)

    grader = ONNXStanceGrader(quantize=True)
    topic = "mandatory licensing for high-compute AI models"
    statement = (
        "We cannot allow unrestricted open weights when national security risks are real. "
        "Strict oversight, licensing, and compliance protocols must be mandatory."
    )
    result = grader.evaluate_stance(topic=topic, statement=statement)
    print("\n=== ONNX NLI Evaluation ===")
    print(result)
    assert result["current_stance_score"] > 0
    print("\nSmoke test passed (manual run only).")
