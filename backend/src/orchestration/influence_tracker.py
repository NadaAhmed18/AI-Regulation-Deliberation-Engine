"""
INFLUENCE TRACKER — Interpersonal Convergence/Influence Matrix

Purpose:
    Implements `docs/Influence-Tracking.md` Section 4: given the ordered
    turn-by-turn discussion history (each turn already scored by
    `DebertaStanceGrader`/`OpinionGrader` — see `nli_grader.py` /
    `opinion_grader.py`), compute a directed adjacency matrix where
    `matrix[A][B]` is how much Agent A's speech appears to have moved
    Agent B's stance toward A's own stance.

Deliberately separate from the stance grader:
    `nli_grader.py` / `opinion_grader.py` answer "what does THIS agent
    think, right now?" for one agent's own statement. This module answers
    a different question — "did Agent A's message move Agent B?" — which
    needs TWO agents' stance histories, not one. Mixing the two concerns
    into one class would make the grader harder to test in isolation and
    would couple stance scoring to a specific notion of "who spoke right
    before whom," which is a discussion-engine concern, not a scoring one.

Two fixes vs. the spec's reference implementation:

1. `None` vs `0.0` for "no known stance yet" (same principle as
   `stance_utils.compute_shift_magnitude`, applied here per-agent):
   The spec's reference implementation initializes every agent's
   `current_stances[name]` to `0.0` before the discussion starts. That
   conflates "this agent's stance is genuinely neutral" with "this agent
   hasn't been scored yet, so no stance is known" — which can register a
   large, spurious "influence" event on an agent's very first turn,
   measured against a `0.0` nobody ever actually held. This
   implementation tracks each agent's known stance as `Optional[float]`
   (`None` until scored) and skips the convergence calculation whenever
   either endpoint's stance is still unknown.

2. Every turn updates the *speaker's own* tracked stance, not only the
   turn's "target": the spec's reference loop only ever writes
   `current_stances[target] = ...`, so an agent's own first turn is never
   recorded into `current_stances` unless that agent later appears as
   someone else's "target" — meaning the very first speaker's real
   opening stance is silently lost (replaced by whatever pre-seeded
   default value is used) for as long as they keep speaking as
   "influencer" without ever being scored as "target" first. This
   implementation records `current_stances[row["agent_name"]]` on every
   row, unconditionally, so an agent's latest known stance is always
   available (as themselves, not only when someone else's turn happens
   to follow theirs).
"""

from typing import Any, Dict, List, Optional


def compute_influence_matrix(
    history_rows: List[Dict[str, Any]],
    personas: List[Dict[str, Any]],
) -> Dict[str, Dict[str, float]]:
    """
    Parse ordered discussion history and construct a directed adjacency
    matrix where edge weight represents cumulative persuasion.

    Args:
        history_rows: Discussion turns in chronological order (e.g. rows
            from PostgreSQL's `discussion_history`, ordered by
            `round_number`/`id`/`created_at`). Each row must have
            `"agent_name"` and `"opinion_snapshot"` with a
            `"current_stance_score"` key. Rows that are not an agent
            utterance (e.g. a system/orchestrator row, if any ever get
            logged to the same table) should be filtered out by the
            caller before calling this function — every row here is
            assumed to be one agent's scored turn.
        personas: The discussion's persona configs, each with at least a
            `"name"` key. Used only to seed every participant into the
            output matrix (so an agent who never influenced or was never
            influenced still appears with all-zero rows/columns, rather
            than being silently absent from the result).

    Returns:
        `matrix[influencer_name][target_name] -> float`, the cumulative
        positive convergence Agent `influencer_name` produced in Agent
        `target_name` across the discussion. Only positive convergence
        (Agent B moving toward Agent A) accumulates weight; polarization
        (moving away) and zero-change turns contribute nothing, per the
        spec (Section 4.A) — the matrix represents persuasion, not
        general interaction volume. A comparison is skipped entirely
        (contributes nothing, in either direction) whenever the target's
        or the influencer's stance isn't known yet at that point in the
        discussion — see this module's docstring, point 1.
    """
    agent_names = [p["name"] for p in personas]
    matrix: Dict[str, Dict[str, float]] = {src: {dst: 0.0 for dst in agent_names} for src in agent_names}

    # Each agent's most recently known stance score. `None` until that
    # agent's own first scored turn appears in `history_rows`.
    current_stances: Dict[str, Optional[float]] = {name: None for name in agent_names}

    for i, row in enumerate(history_rows):
        target = row["agent_name"]
        target_new_stance = row["opinion_snapshot"]["current_stance_score"]

        if i > 0:
            influencer = history_rows[i - 1]["agent_name"]

            if influencer != target:
                target_prev_stance = current_stances.get(target)
                influencer_stance = current_stances.get(influencer)

                # Skip if either endpoint has no known stance yet (the
                # target's first-ever turn, or the influencer hasn't been
                # scored at all — e.g. history starts mid-window).
                if target_prev_stance is not None and influencer_stance is not None:
                    dist_prev = abs(target_prev_stance - influencer_stance)
                    dist_new = abs(target_new_stance - influencer_stance)
                    delta = dist_prev - dist_new

                    if delta > 0:
                        matrix[influencer][target] += round(delta, 2)

        # Record this turn's speaker's own latest stance UNCONDITIONALLY —
        # not only when they happen to be a comparison's "target" — so a
        # future turn that follows THIS agent can look up their real,
        # current stance rather than a stale or fabricated default.
        current_stances[target] = target_new_stance

    return matrix


if __name__ == "__main__":
    # Smoke test — no DB, no model, pure function. Alternating turns
    # (Elena, Marcus, Elena, Marcus), Marcus moving toward Elena's stance
    # on his second turn.
    personas = [{"name": "Elena"}, {"name": "Marcus"}]

    history_rows = [
        {"agent_name": "Elena", "opinion_snapshot": {"current_stance_score": 4.0}},
        {"agent_name": "Marcus", "opinion_snapshot": {"current_stance_score": -3.0}},
        {"agent_name": "Elena", "opinion_snapshot": {"current_stance_score": 4.0}},   # unchanged
        {"agent_name": "Marcus", "opinion_snapshot": {"current_stance_score": -1.0}},  # moved toward Elena
    ]

    matrix = compute_influence_matrix(history_rows, personas)
    print("Influence matrix:", matrix)

    assert matrix["Elena"]["Marcus"] == 2.0, f"Expected 2.0, got {matrix['Elena']['Marcus']}"
    assert matrix["Marcus"]["Elena"] == 0.0, "Elena's stance did not change; no influence to record."
    print("influence_tracker smoke test passed.")
