"""
NLI STANCE GRADER — Local, Non-LLM Stance Scoring

Purpose:
    Local NLI-based stance scoring for the multi-agent AI Regulation
    simulation.

    The grader compares an agent statement against competing PRO and ANTI
    hypotheses and derives a continuous stance signal in [-5, +5].

    This is an NLI-derived analytical signal, not a ground-truth measurement
    of the agent's actual stance.

Model:
    cross-encoder/nli-deberta-v3-large

    Same 3-way NLI cross-encoder family named in the original spec
    (`docs/Influence-Tracking.md` Section 3). The `-large` variant was
    selected based on the project's NLI benchmarking results for the
    pro/anti stance-scoring task — see the doc's Implementation Notes
    for the actual numbers. This model is a general-purpose NLI model,
    not a stance classifier trained on AI-regulation debate data, so its
    output is treated throughout this file as an NLI-derived stance
    signal, not a validated measurement of stance accuracy. Not
    revisited here; this file only adds inference-time optimizations
    around the already-chosen model.

Key design decisions:
    - Local inference: no LLM/API call per stance evaluation.
    - Dynamic label discovery from model.config.id2label.
    - PRO/ANTI probabilities are normalized independently using a 2-way
      softmax over entailment vs contradiction (neutral excluded, so it
      can't dilute the signal — see stance_utils / Influence-Tracking.md
      for the reasoning). Softmax always runs in float32 regardless of
      model dtype, to avoid fp16 precision loss at the final step.
    - Batched inference for PRO/ANTI hypotheses within a single statement,
      plus an optional evaluate_batch() for scoring a whole discussion
      round (multiple agents) in one forward pass.
    - torch.inference_mode() instead of no_grad() for inference-only
      efficiency (stricter, avoids autograd version-counter bookkeeping).
    - FP16 weights auto-enabled on CUDA (float32 on CPU, where fp16
      matmul isn't accelerated) — see `__init__`'s `dtype` param.
    - Langfuse `evaluator`-typed tracing for observability, consistent
      with OpinionGrader's existing `generation`-typed tracing. Each
      call adds `model`/`device`/`pro_probability`/`anti_probability`/
      `current_stance_score`/`shift_magnitude`/`latency_seconds` as
      span metadata via a single `update_current_span()` call right
      before returning — not incrementally, since Langfuse's decorator
      is known to drop earlier mid-function updates in some SDK
      versions (langfuse/langfuse#7030).
    - Python logging (not print) for container/production diagnostics.

ONNX export + dynamic INT8 quantization:
    Implemented, but as a **separate, opt-in class**
    (`ONNXStanceGrader` in `nli_onnx_grader.py`), not folded into this
    file or enabled by default. Reasons this stays opt-in rather than
    becoming the default:
      - It requires the `optimum[onnxruntime]` extra (`uv sync --extra
        onnx`), which this file has no dependency on otherwise.
      - INT8 quantization trades numerical precision for speed. Whether
        that's an acceptable trade for this task hasn't been measured
        yet against the current PyTorch backend.
      - `scripts/benchmark_nli_backends.py` exists specifically to make
        that measurement (latency + score-consistency across backends)
        before anyone switches `STANCE_GRADER_ENGINE` or touches this
        default. See `docs/NLI-Grader-Optimizations.md` for what to look
        for in its output and how to decide.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from langfuse import get_client, observe

from src.utils.stance_utils import compute_stance_result

logger = logging.getLogger(__name__)

DEFAULT_NLI_MODEL = "cross-encoder/nli-deberta-v3-large"
DEFAULT_MAX_LENGTH = 512


class DebertaStanceGrader:
    """
    Local NLI-based stance grader.

    Public interface (drop-in compatible with `OpinionGrader`):
        evaluate_stance(topic, statement, previous_score)

    Additional:
        evaluate_batch(topic, statements)
            Scores multiple agent statements (e.g. a whole discussion
            round) in a single model forward pass.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_NLI_MODEL,
        max_length: int = DEFAULT_MAX_LENGTH,
        dtype: Optional[Any] = None,
    ):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.model_name = model_name
        self.max_length = max_length
        self._torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # FP16 on GPU: halves model memory and is typically ~1.5-2x
        # faster than FP32 on modern GPUs for encoder classification
        # models like this one, with negligible accuracy impact --
        # unlike ONNX/INT8 below, this needs no new dependency and no
        # conversion step, so it's auto-enabled by default when CUDA is
        # available. Explicitly pass dtype=torch.float32 to disable it
        # (e.g. while debugging a suspected precision issue). No effect
        # on CPU: float16 matmul isn't accelerated there, so we stay in
        # float32 to avoid paying a conversion cost for no benefit.
        if dtype is not None:
            self.dtype = dtype
        else:
            self.dtype = torch.float16 if self.device == "cuda" else torch.float32

        logger.info(
            "Initializing NLI Stance Grader | model=%s | device=%s | dtype=%s",
            model_name,
            self.device,
            self.dtype,
        )

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name, torch_dtype=self.dtype
        ).to(self.device)
        self.model.eval()

        self.entailment_idx, self.contradiction_idx = self._find_label_indices(
            self.model.config.id2label, model_name
        )

        logger.info(
            "NLI model loaded | entailment_idx=%s | contradiction_idx=%s",
            self.entailment_idx,
            self.contradiction_idx,
        )

    @staticmethod
    def _find_label_indices(id2label: Dict[int, str], model_name: str) -> Tuple[int, int]:
        """
        Dynamically identify entailment and contradiction label indices
        from the model's own config, instead of hardcoding them — so
        `model_name` can be swapped without a code change.
        """
        entailment_idx: Optional[int] = None
        contradiction_idx: Optional[int] = None

        for idx, label in id2label.items():
            lowered = label.lower()
            if "entailment" in lowered and "not" not in lowered:
                entailment_idx = int(idx)
            elif "contradiction" in lowered:
                contradiction_idx = int(idx)

        if entailment_idx is None:
            raise ValueError(
                f"Could not find an 'entailment' label in model '{model_name}'. "
                f"id2label={id2label}"
            )

        # Binary NLI / zero-shot-compatible model fallback.
        if contradiction_idx is None:
            if len(id2label) == 2:
                contradiction_idx = next(int(idx) for idx in id2label if int(idx) != entailment_idx)
            else:
                raise ValueError(
                    f"Found entailment but no contradiction label in a "
                    f"{len(id2label)}-class model. id2label={id2label}"
                )

        return entailment_idx, contradiction_idx

    def _score_pairs(self, premises: List[str], hypotheses: List[str]) -> Tuple[float, ...]:
        """
        Run one batched NLI forward pass over parallel (premise,
        hypothesis) pairs and return each pair's entailment probability,
        computed via a 2-way softmax over [entailment, contradiction]
        only (neutral excluded). Handles any batch size >= 1, so both
        `evaluate_stance` (2 pairs: pro/anti for one statement) and
        `evaluate_batch` (2*N pairs across a whole round) share this one
        implementation.
        """
        if len(premises) != len(hypotheses):
            raise ValueError("premises and hypotheses must have the same length.")

        inputs = self.tokenizer(
            premises,
            hypotheses,
            truncation=True,
            max_length=self.max_length,
            padding=True,
            return_tensors="pt",
        ).to(self.device)

        # inference_mode() is stricter than no_grad(): it also skips
        # autograd's version-counter bookkeeping, which no_grad() still
        # does. Safe here since nothing downstream needs backprop.
        with self._torch.inference_mode():
            logits = self.model(**inputs).logits.float()  # upcast for softmax stability
            entail_logits = logits[:, self.entailment_idx]
            contra_logits = logits[:, self.contradiction_idx]
            pair_logits = self._torch.stack([entail_logits, contra_logits], dim=-1)
            pair_probs = self._torch.softmax(pair_logits, dim=-1)
            return tuple(float(p) for p in pair_probs[:, 0].tolist())

    @observe(name="nli_stance_evaluation", as_type="evaluator", capture_input=False)
    def evaluate_stance(
        self,
        topic: str,
        statement: str,
        previous_score: Optional[float] = None,
        pro_proposition: Optional[str] = None,
        anti_proposition: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate one statement's NLI-derived stance toward `topic`.

        Returns:
            {
                "current_stance_score": float,   # -5.0 to +5.0
                "shift_magnitude": float | None,  # vs. previous_score
                "pro_probability": float,
                "anti_probability": float,
                "engine": str,
            }
        """
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
        result["engine"] = self.model_name
        latency_seconds = time.perf_counter() - start_time

        # Update the current span's metadata exactly once, right before
        # returning. Langfuse's @observe decorator is known to drop or
        # overwrite earlier update_current_span() calls made mid-function
        # (see langfuse/langfuse#7030), so a single, final call here is
        # the reliable pattern rather than updating incrementally.
        get_client().update_current_span(
            metadata={
                "model": self.model_name,
                "device": self.device,
                "pro_probability": round(prob_pro, 3),
                "anti_probability": round(prob_anti, 3),
                "current_stance_score": result["current_stance_score"],
                "shift_magnitude": result["shift_magnitude"],
                "latency_seconds": round(latency_seconds, 4),
            }
        )

        logger.debug(
            "NLI stance evaluated | score=%.3f | pro=%.3f | anti=%.3f | shift=%s | latency=%.3fs",
            result["current_stance_score"],
            prob_pro,
            prob_anti,
            result["shift_magnitude"],
            latency_seconds,
        )
        return result

    @observe(name="nli_batch_stance_evaluation", as_type="evaluator", capture_input=False)
    def evaluate_batch(
        self,
        topic: str,
        statements: List[Dict[str, Any]],
        pro_proposition: Optional[str] = None,
        anti_proposition: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Score multiple agent statements (e.g. every agent in one
        discussion round) in a single NLI forward pass instead of one
        pass per agent.

        Args:
            statements: list of
                {"agent_name": str, "statement": str, "previous_score": float | None}

        Returns:
            One result dict per input statement (same shape as
            `evaluate_stance`'s return, plus `"agent_name"`), in the
            same order as `statements`.
        """
        if not statements:
            return []

        start_time = time.perf_counter()

        hypo_pro = pro_proposition or f"The speaker is in favor of {topic}."
        hypo_anti = anti_proposition or f"The speaker is opposed to {topic}."

        # Each statement contributes two (premise, hypothesis) pairs:
        # (statement, pro) and (statement, anti).
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
            result["engine"] = self.model_name
            result["agent_name"] = item.get("agent_name")
            results.append(result)

        latency_seconds = time.perf_counter() - start_time

        # Single metadata update at the end, same rationale as in
        # evaluate_stance(). Per-agent scores are summarized here rather
        # than dumped in full, since Langfuse metadata is meant for
        # at-a-glance debugging, not as the system of record (that's
        # Postgres, via discussion_graph.py / influence_tracker.py).
        get_client().update_current_span(
            metadata={
                "model": self.model_name,
                "device": self.device,
                "batch_size": len(statements),
                "latency_seconds": round(latency_seconds, 4),
                "agent_scores": {
                    r["agent_name"]: r["current_stance_score"] for r in results
                },
            }
        )

        logger.debug(
            "Batch NLI evaluation completed | statements=%d | latency=%.3fs",
            len(statements),
            latency_seconds,
        )
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    grader = DebertaStanceGrader()
    topic = "mandatory licensing for high-compute AI models"
    statement = (
        "We cannot allow unrestricted open weights when national security risks are real. "
        "Strict oversight, licensing, and compliance protocols must be mandatory."
    )

    result = grader.evaluate_stance(topic=topic, statement=statement)
    print("\n=== NLI Evaluation ===")
    print(result)
    assert result["current_stance_score"] > 0
    assert result["shift_magnitude"] is None

    result_2 = grader.evaluate_stance(topic=topic, statement=statement, previous_score=1.0)
    print("\n=== NLI Evaluation With Previous Score ===")
    print(result_2)
    assert result_2["shift_magnitude"] is not None

    batch_results = grader.evaluate_batch(
        topic=topic,
        statements=[
            {"agent_name": "agent_1", "statement": statement, "previous_score": None},
            {"agent_name": "agent_2", "statement": "This regulation is unnecessary red tape.", "previous_score": -1.0},
        ],
    )
    print("\n=== Batch Evaluation ===")
    print(batch_results)
    assert len(batch_results) == 2
    assert batch_results[0]["agent_name"] == "agent_1"

    print("\nSmoke test passed.")
