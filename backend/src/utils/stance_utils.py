"""
Stance Scoring Utilities

Pure, model-agnostic math for turning a pair of "pro" / "anti" entailment
probabilities into the project's stance score `S` and its shift over time.
See `docs/Influence-Tracking.md` Section 3.A for the original spec:

    S = (S_pro - S_anti) * 5.0                       (clamped to [-5.0, +5.0])
    Shift = S_t - S_(t-1)

This is deliberately split out of `orchestration/nli_grader.py` so that:
    - Any local NLI grader (`DebertaStanceGrader`, or a future swap to a
      different cross-encoder) computes `S` the exact same way.
    - Week 4 analytics (opinion-shift charts, re-scoring/auditing stored
      `opinion_snapshot` rows) can reuse the identical formula instead of
      re-deriving it from the doc, which is how score drift between the
      live grader and offline analysis tends to happen.
    - The formula can be unit-tested on its own, with no model, tokenizer,
      or GPU/CPU involved.

Note: this module intentionally does NOT compute the interpersonal
*convergence delta* (Influence-Tracking.md Section 4.A) — that compares
two different agents' stances to build the influence graph, whereas the
functions here compute a single agent's own stance and its shift from its
own previous turn. Keep the two concepts separate; see
`orchestration/influence_tracker.py` for the convergence-delta math.
"""

from typing import Dict, Optional

# Scale bounds matching the `opinion_snapshot.current_stance_score` schema.
STANCE_MIN = -5.0
STANCE_MAX = 5.0
STANCE_SCALE = 5.0


def compute_stance_score(
    pro_probability: float,
    anti_probability: float,
    decimals: int = 2,
) -> float:
    """
    Compute the continuous stance score `S` on the [-5.0, +5.0] scale from
    a pair of entailment probabilities:

        S = (P_pro - P_anti) * 5.0

    Note on what this value actually measures: `P_pro`/`P_anti` are each
    an NLI model's entailment probability for a specific hypothesis
    sentence (e.g. "this statement supports the topic"), not a directly
    measured "probability the agent holds this stance." `S` is therefore
    an *NLI-derived stance signal* — a useful, cheap, reproducible proxy —
    not a ground-truth stance measurement. Treat it accordingly when
    interpreting or reporting results (e.g. avoid phrasing like "the model
    determined the agent is 73% pro-regulation").

    Args:
        pro_probability: P(entailment) for the "supports the topic"
            hypothesis, in [0.0, 1.0].
        anti_probability: P(entailment) for the "opposes the topic"
            hypothesis, in [0.0, 1.0].
        decimals: rounding precision applied before clamping.

    Returns:
        The stance score, rounded and clamped to [-5.0, +5.0].
    """
    raw_score = (pro_probability - anti_probability) * STANCE_SCALE
    return max(STANCE_MIN, min(STANCE_MAX, round(raw_score, decimals)))


def compute_shift_magnitude(
    current_score: float,
    previous_score: Optional[float],
    decimals: int = 2,
) -> Optional[float]:
    """
    Signed change in an agent's own stance between two of its turns:

        Shift = S_t - S_(t-1)

    Positive means the agent moved toward the "pro" end of the scale
    relative to its own previous score; negative means it moved toward
    "anti".

    Args:
        current_score: This turn's stance score.
        previous_score: The agent's stance score from its own previous
            turn, or `None` if this is the agent's first-ever scored
            turn (there is no previous turn to compare against). `None`
            is distinct from `0.0`: `0.0` is a genuine neutral prior
            score, while `None` means "no prior score exists yet."
            Conflating the two would make an agent's first turn always
            register as a shift toward or away from neutral, which
            isn't a real shift at all.

    Returns:
        The signed shift, rounded — or `None` if `previous_score` is
        `None` (no shift can be computed without a prior score).
    """
    if previous_score is None:
        return None
    return round(current_score - previous_score, decimals)


def compute_stance_result(
    pro_probability: float,
    anti_probability: float,
    previous_score: Optional[float] = None,
    decimals: int = 2,
) -> Dict[str, Optional[float]]:
    """
    Convenience wrapper bundling `compute_stance_score` and
    `compute_shift_magnitude` into the shape graders return. Useful for
    any caller that only has raw pro/anti probabilities on hand (a new
    grader implementation, a batched re-scoring job, a notebook doing
    Week 4 opinion-shift analysis) and doesn't want to hand-roll the dict.

    Args:
        previous_score: The agent's own previous stance score, or `None`
            if this is its first scored turn. Defaults to `None` — not
            `0.0` — so a first turn is never silently treated as
            "shifted from neutral." Callers that DO have a real previous
            score (e.g. fetched from `discussion_history` in PostgreSQL)
            should pass it explicitly.

    Returns:
        {
            "current_stance_score": float,           # -5.0 to +5.0
            "shift_magnitude": float | None,          # None on first turn
            "pro_probability": float,                 # rounded to 3 decimals
            "anti_probability": float,                # rounded to 3 decimals
        }
    """
    current = compute_stance_score(pro_probability, anti_probability, decimals=decimals)
    shift = compute_shift_magnitude(current, previous_score, decimals=decimals)
    return {
        "current_stance_score": current,
        "shift_magnitude": shift,
        "pro_probability": round(pro_probability, 3),
        "anti_probability": round(anti_probability, 3),
    }


if __name__ == "__main__":
    # Quick sanity check — no model/tokenizer needed.
    result = compute_stance_result(pro_probability=0.91, anti_probability=0.04, previous_score=1.0)
    print("Stance result (with prior score):", result)
    assert result["current_stance_score"] == 4.35
    assert result["shift_magnitude"] == 3.35

    first_turn_result = compute_stance_result(pro_probability=0.91, anti_probability=0.04)
    print("Stance result (first turn, no prior score):", first_turn_result)
    assert first_turn_result["shift_magnitude"] is None, "First turn must not report a shift."

    print("stance_utils smoke test passed.")
