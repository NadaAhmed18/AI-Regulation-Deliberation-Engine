"""
NLI STANCE GRADER (CPU-Optimized ONNX Runtime)

Lightweight NLI stance scoring using DeBERTa-v3-small on CPU.
Derives continuous stance signals in [-5.0, +5.0] using 2-way softmax.
"""

import logging
import time
from typing import Any, Dict, List, Mapping, Optional

import numpy as np
import onnxruntime as ort
from langfuse import get_client, observe
from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer

from src.utils.stance_utils import compute_stance_result

logger = logging.getLogger(__name__)

DEFAULT_NLI_MODEL = "cross-encoder/nli-deberta-v3-small"
DEFAULT_MAX_LENGTH = 512


class DebertaStanceGrader:
    """CPU-targeted ONNX stance grader utilizing DeBERTa-v3-small."""

    def __init__(
        self,
        model_name: str = DEFAULT_NLI_MODEL,
        max_length: int = DEFAULT_MAX_LENGTH,
    ):
        self.model_name = model_name
        self.max_length = max_length

        logger.info("Initializing CPU ONNX Grader | model=%s", model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

        # Configure session specifically for CPU deployment
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        try:
            self.model = ORTModelForSequenceClassification.from_pretrained(
                model_name,
                provider="CPUExecutionProvider",
                session_options=session_options,
            )
        except Exception:
            logger.info("Exporting '%s' to ONNX format for CPU execution...", model_name)
            self.model = ORTModelForSequenceClassification.from_pretrained(
                model_name,
                export=True,
                provider="CPUExecutionProvider",
                session_options=session_options,
            )

        self.entailment_idx, self.contradiction_idx = self._find_label_indices(
            getattr(self.model.config, "id2label", None)
        )

    @staticmethod
    def _find_label_indices(id2label: Optional[Mapping[Any, str]]) -> tuple[int, int]:
        """Identifies entailment and contradiction indices dynamically."""
        entail_idx, contra_idx = None, None
        if id2label:
            for idx, label in id2label.items():
                name = str(label).lower()
                if "entail" in name and "not" not in name:
                    entail_idx = int(idx)
                elif "contra" in name:
                    contra_idx = int(idx)

        return (
            entail_idx if entail_idx is not None else 0,
            contra_idx if contra_idx is not None else 2,
        )

    def _score_pairs(self, premises: List[str], hypotheses: List[str]) -> List[float]:
        """Batched CPU forward pass returning 2-way softmax P(entailment)."""
        inputs = self.tokenizer(
            premises,
            hypotheses,
            truncation=True,
            max_length=self.max_length,
            padding=True,
            return_tensors="np",
        )
        logits: np.ndarray = self.model(**inputs).logits

        # Vectorized 2-way softmax over [entailment, contradiction]
        pair_logits = logits[:, [self.entailment_idx, self.contradiction_idx]]
        exp_logits = np.exp(pair_logits - np.max(pair_logits, axis=-1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)
        return probs[:, 0].tolist()

    @observe(name="nli_stance_evaluation", as_type="evaluator", capture_input=False)
    def evaluate_stance(
        self,
        topic: str,
        statement: str,
        previous_score: Optional[float] = None,
        pro_proposition: Optional[str] = None,
        anti_proposition: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluates single statement stance on [-5.0, +5.0] scale."""
        start = time.perf_counter()
        hypo_pro = pro_proposition or f"The speaker is in favor of {topic}."
        hypo_anti = anti_proposition or f"The speaker is opposed to {topic}."

        prob_pro, prob_anti = self._score_pairs(
            premises=[statement, statement],
            hypotheses=[hypo_pro, hypo_anti],
        )

        result: Dict[str, Any] = dict(
            compute_stance_result(prob_pro, prob_anti, previous_score=previous_score)
        )
        result["engine"] = f"{self.model_name} (onnx-cpu)"
        latency = round(time.perf_counter() - start, 4)

        try:
            get_client().update_current_span(
                metadata={
                    "model": self.model_name,
                    "backend": "onnxruntime-cpu",
                    "pro_probability": round(prob_pro, 3),
                    "anti_probability": round(prob_anti, 3),
                    "current_stance_score": result["current_stance_score"],
                    "shift_magnitude": result["shift_magnitude"],
                    "latency_seconds": latency,
                }
            )
        except Exception:
            pass

        return result

    @observe(name="nli_batch_stance_evaluation", as_type="evaluator", capture_input=False)
    def evaluate_batch(
        self,
        topic: str,
        statements: List[Dict[str, Any]],
        pro_proposition: Optional[str] = None,
        anti_proposition: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Batched evaluation across multiple statements."""
        if not statements:
            return []

        start = time.perf_counter()
        hypo_pro = pro_proposition or f"The speaker is in favor of {topic}."
        hypo_anti = anti_proposition or f"The speaker is opposed to {topic}."

        premises = [s["statement"] for s in statements for _ in (0, 1)]
        hypotheses = [h for _ in statements for h in (hypo_pro, hypo_anti)]

        probs = self._score_pairs(premises, hypotheses)

        results: List[Dict[str, Any]] = []
        for idx, item in enumerate(statements):
            prob_pro, prob_anti = probs[idx * 2], probs[idx * 2 + 1]
            res: Dict[str, Any] = dict(
                compute_stance_result(prob_pro, prob_anti, previous_score=item.get("previous_score"))
            )
            res["engine"] = f"{self.model_name} (onnx-cpu)"
            res["agent_name"] = item.get("agent_name")
            results.append(res)

        try:
            get_client().update_current_span(
                metadata={
                    "model": self.model_name,
                    "backend": "onnxruntime-cpu",
                    "batch_size": len(statements),
                    "latency_seconds": round(time.perf_counter() - start, 4),
                }
            )
        except Exception:
            pass

        return results