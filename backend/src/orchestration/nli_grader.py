"""
NLI STANCE GRADER — Local, Non-LLM Stance Scoring

Purpose:
    Fast, local alternative to `OpinionGrader` (which calls a remote LLM
    via OpenRouter/DeepSeek for every stance evaluation). Runs a local
    Natural Language Inference (NLI) cross-encoder that scores an agent's
    statement against two competing hypotheses and derives a continuous
    stance score from the entailment probabilities.

    This produces an *NLI-derived stance signal*, not a literal measurement
    of the agent's stance — see `stance_utils.compute_stance_score`'s
    docstring for why that distinction matters when interpreting results.

    See `docs/Influence-Tracking.md` Section 3 for the original spec and
    math, and its "Implementation Notes" subsection for the full list of
    deviations from that spec and why.

Model: `cross-encoder/nli-deberta-v3-large` (see docs/Influence-Tracking.md
    Section 3 Implementation Notes for the comparison against the spec's
    original `-small` model and the zero-shot-specific `MoritzLaurer`
    models benchmarked alongside it).

Label handling (robust to model swaps):
    `_find_label_indices()` reads the model's own `config.id2label` at
    load time instead of hardcoding indices, so swapping `model_name` to
    a different compatible NLI/zero-shot model works without a code
    change.

Two-way (entailment vs. contradiction) softmax, not three-way:
    `cross-encoder/nli-deberta-v3-large` outputs THREE classes
    (contradiction / entailment / neutral) — unlike a binary
    (entailment / not_entailment) zero-shot model, where a full softmax
    over all logits and a 2-way softmax over just [entailment, other]
    give identical numbers, so the distinction was invisible before this
    model swap. With a 3-way model it is NOT identical: a full 3-way
    softmax lets "neutral" probability mass dilute the entailment score.
    `_get_entailment_probs()` softmaxes ONLY the entailment and
    contradiction logits for each hypothesis (discarding neutral
    entirely), matching how `transformers.pipeline(
    "zero-shot-classification", ..., multi_label=True)` scores each
    hypothesis independently — which is what this project's own model
    benchmarking (`compare_nli_models.py` / `benchmark_nli_models.py`)
    actually used. Without this, this grader's live scores would
    silently diverge from the numbers that were benchmarked to justify
    picking this model. This is a no-op for a binary model (nothing to
    discard), so `model_name` can still be swapped back to one without
    changing behavior for that case.

Hypothesis phrasing: "simple" form, not "verbose"
    `f"The speaker is in favor of {topic}."` / `f"The speaker is opposed
    to {topic}."`, not the longer `f"This statement supports and argues
    in favor of {topic}."` form. Benchmarking BOTH phrasings on the same
    ~15 statements across all 3 candidate models showed the simple form
    scored equal-or-better in every case (e.g. this model's own small
    sibling, `cross-encoder/nli-deberta-v3-small`, went from 53.3% to
    73.3% sign-accuracy on the simple phrasing alone) — see
    `benchmark_nli_models.py`'s `LABEL_VARIANTS` results. Use
    `pro_proposition`/`anti_proposition` below to override per-call if a
    specific topic needs different wording.

Batched inference:
    `_get_entailment_probs()` batches the pro/anti hypothesis pairs into
    a single forward pass instead of two sequential calls.

Dependency note:
    `torch` and `sentence-transformers` (which pulls in `transformers`)
    are already project dependencies (see `pyproject.toml`) — no new
    dependency is needed for this file.
"""

from typing import Any, Dict, List, Optional, Tuple

from src.utils.stance_utils import compute_stance_result

DEFAULT_NLI_MODEL = "cross-encoder/nli-deberta-v3-large"


class DebertaStanceGrader:
    """
    Local NLI-based stance grader. Same public interface as the spec in
    `docs/Influence-Tracking.md` (`evaluate_stance(topic, statement,
    previous_score)`), so it can replace or run alongside `OpinionGrader`
    in `discussion_graph.py`'s `node_grade_opinion` without changing that
    node's calling code.
    """

    def __init__(self, model_name: str = DEFAULT_NLI_MODEL):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        print(f"[*] Initializing local NLI Stance Grader: {model_name}")
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(self.device)
        self.model.eval()
        self._torch = torch

        self.entailment_idx, self.contradiction_idx = self._find_label_indices(
            self.model.config.id2label, model_name
        )

    @staticmethod
    def _find_label_indices(id2label: Dict[int, str], model_name: str) -> Tuple[int, int]:
        """
        Find (entailment_idx, contradiction_idx) by reading the model's
        own label config instead of hardcoding indices. Works for both
        binary (entailment/not_entailment) and classic 3-way
        (contradiction/neutral/entailment) label sets.

        For a binary model there is no literal "contradiction" label —
        in that case the sole remaining index (its "not_entailment"
        class) is used as the contradiction/"other" side of the 2-way
        softmax in `_get_entailment_probs`. This reproduces exactly what
        a full softmax over 2 logits would give (there's nothing else to
        discard), so binary models keep working unchanged if
        `model_name` is swapped back to one.

        Args:
            model_name: The model actually being loaded (not necessarily
                `DEFAULT_NLI_MODEL` — a caller may have passed a
                different `model_name` to `__init__`). Included so the
                error message below names whichever model was really
                configured.

        Raises:
            ValueError: if no "entailment" label is found at all (the
                configured model isn't an NLI/zero-shot entailment model,
                so this should fail loudly rather than silently score
                against the wrong logit); or if the label set has more
                than 2 classes but none of them is literally
                "contradiction" (an unrecognized 3+-way label scheme
                that needs to be checked manually).
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
                f"Could not find an 'entailment' label in this model's config "
                f"(id2label={id2label}). Is '{model_name}' actually an "
                f"NLI/zero-shot model?"
            )

        if contradiction_idx is None:
            if len(id2label) == 2:
                # Binary model: the only other index is "not_entailment",
                # which stands in for "contradiction" here.
                contradiction_idx = next(int(idx) for idx in id2label if int(idx) != entailment_idx)
            else:
                raise ValueError(
                    f"Found an 'entailment' label but no 'contradiction' "
                    f"label in a label set with more than 2 classes "
                    f"(id2label={id2label}) for model '{model_name}'. This "
                    f"label scheme isn't recognized -- please check it "
                    f"manually before using it here."
                )

        return entailment_idx, contradiction_idx

    def _get_entailment_probs(self, premise: str, hypotheses: List[str]) -> Tuple[float, ...]:
        """
        Run a single batched forward pass over `premise` paired with each
        hypothesis in `hypotheses`, and return P(entailment) for each
        pair — normalized ONLY against that pair's contradiction logit
        (any "neutral" logit is discarded entirely; see this module's
        docstring for why that matters for this specific model).
        """
        premises = [premise] * len(hypotheses)
        inputs = self.tokenizer(
            premises,
            hypotheses,
            truncation=True,
            max_length=512,
            padding=True,
            return_tensors="pt",
        ).to(self.device)

        with self._torch.no_grad():
            logits = self.model(**inputs).logits  # shape: (len(hypotheses), num_labels)
            entail_logits = logits[:, self.entailment_idx]
            contra_logits = logits[:, self.contradiction_idx]
            # Softmax over just these two columns per row -- discards
            # "neutral" (if present) instead of letting it dilute the
            # entailment probability. dim=-1 here is the [entail, contra]
            # pair axis, not the batch axis, so each hypothesis is
            # normalized independently of the others (matching
            # multi_label=True zero-shot scoring, not multi-class).
            pair_logits = self._torch.stack([entail_logits, contra_logits], dim=-1)  # (N, 2)
            pair_probs = self._torch.softmax(pair_logits, dim=-1)
            return tuple(float(p) for p in pair_probs[:, 0].tolist())

    def evaluate_stance(
        self,
        topic: str,
        statement: str,
        previous_score: Optional[float] = None,
        pro_proposition: Optional[str] = None,
        anti_proposition: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Score a statement's stance toward `topic` on a -5.0..+5.0 scale
        (same scale as `OpinionGrader`, for drop-in compatibility with
        the `opinion_snapshot` schema in `docs/Influence-Tracking.md`).

        Args:
            topic: The discussion topic. Used to build the default
                pro/anti hypotheses if `pro_proposition`/`anti_proposition`
                are not given.
            statement: The agent's latest statement (the "premise").
            previous_score: The agent's own previous stance score, or
                `None` if this is its first scored turn (see
                `stance_utils.compute_shift_magnitude` for why `None`
                and `0.0` are handled differently). The caller (e.g.
                `discussion_graph.py`'s `node_grade_opinion`, via
                `PostgresClient.get_last_stance_score`) is responsible
                for fetching the agent's real previous score — this
                method holds no state between calls.
            pro_proposition: Optional override for the "pro" hypothesis.
                The default (`"The speaker is in favor of {topic}."`)
                works for most topics, but a topic phrased as a bare noun
                phrase ("AI regulation") can make a *qualified* statement
                (e.g. "licensing is fine for frontier models but not
                small labs") score inconsistently, since the NLI model is
                judging entailment of a vague hypothesis rather than a
                specific proposition. For topics where that matters, pass
                a specific proposition instead, e.g.
                `pro_proposition="Mandatory licensing for high-compute AI
                models should be required."`
            anti_proposition: Optional override for the "anti" hypothesis,
                analogous to `pro_proposition`. If one of
                `pro_proposition`/`anti_proposition` is given, the other
                should generally be given too, so both hypotheses refer
                to the same specific proposition.

        Returns:
            {
                "current_stance_score": float,        # -5.0 to +5.0
                "shift_magnitude": float | None,       # None if previous_score was None
                "pro_probability": float,              # 0.0 to 1.0
                "anti_probability": float,              # 0.0 to 1.0
                "engine": str,                          # the model_name used
            }
        """
        hypo_pro = pro_proposition or f"The speaker is in favor of {topic}."
        hypo_anti = anti_proposition or f"The speaker is opposed to {topic}."

        prob_pro, prob_anti = self._get_entailment_probs(
            premise=statement,
            hypotheses=[hypo_pro, hypo_anti],
        )

        result = compute_stance_result(
            pro_probability=prob_pro,
            anti_probability=prob_anti,
            previous_score=previous_score,
        )
        result["engine"] = self.model.name_or_path
        return result


if __name__ == "__main__":
    # Live smoke test — requires downloading the model on first run
    # (network access + ~1.6GB disk for the -large checkpoint). Run as:
    #   python -m src.orchestration.nli_grader
    # Note: this model is noticeably slower than a "-small" model on
    # CPU (~4-8s/call in local benchmarking) -- expected given its size.
    grader = DebertaStanceGrader()
    topic = "mandatory licensing for high-compute AI models"
    statement = (
        "We cannot allow unrestricted open weights when national security risks are real. "
        "Strict oversight, licensing, and compliance protocols must be mandatory."
    )
    result = grader.evaluate_stance(topic=topic, statement=statement)
    print("NLI Evaluation Result (first turn, no previous_score):", result)
    assert result["current_stance_score"] > 0, "Expected a pro-regulation statement to score positive."
    assert result["shift_magnitude"] is None, "First turn should report no shift."

    result_2 = grader.evaluate_stance(topic=topic, statement=statement, previous_score=1.0)
    print("NLI Evaluation Result (with previous_score=1.0):", result_2)
    assert result_2["shift_magnitude"] is not None

    print("Smoke test passed.")
