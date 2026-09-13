from typing import Any, Dict, List, Optional


def compute_topology_influence(
    history_rows: List[Dict[str, Any]],
    personas: List[Dict[str, Any]],
    visibility_matrix: Optional[Dict[str, List[str]]] = None,
    min_turns: int = 3,
) -> Dict[str, Any]:
    """
    Estimate directed influence between agents based on stance convergence.

    The visibility matrix follows:
        {listener: [allowed_speakers]}

    Influence is counted only when a target agent moves closer to the
    previous speaker's stance.
    """

    agent_names = [persona["name"] for persona in personas]

    influence_matrix: Dict[str, Dict[str, float]] = {
        source: {
            target: 0.0
            for target in agent_names
        }
        for source in agent_names
    }

    valid_turns = []

    for row in history_rows:
        opinion_snapshot = row.get("opinion_snapshot")

        if not opinion_snapshot:
            continue

        stance = opinion_snapshot.get("current_stance_score")

        if stance is None:
            continue

        agent_name = row.get("agent_name")

        if agent_name not in agent_names:
            continue

        valid_turns.append(
            {
                "agent_name": agent_name,
                "stance": float(stance),
            }
        )

    if len(valid_turns) < min_turns:
        return {
            "status": "insufficient_data",
            "matrix": influence_matrix,
            "scores": {
                name: 0.0
                for name in agent_names
            },
            "top_influencer": None,
        }

    previous_stance_by_agent: Dict[str, float] = {}

    for index, turn in enumerate(valid_turns):
        target = turn["agent_name"]
        target_new_stance = turn["stance"]

        if index > 0 and target in previous_stance_by_agent:
            previous_turn = valid_turns[index - 1]

            influencer = previous_turn["agent_name"]
            influencer_stance = previous_turn["stance"]

            if influencer != target:
                allowed = True

                if visibility_matrix is not None and target in visibility_matrix:
                    allowed_speakers = visibility_matrix[target]
                    allowed = influencer in allowed_speakers

                if allowed:
                    target_previous_stance = previous_stance_by_agent[target]

                    distance_before = abs(
                        target_previous_stance - influencer_stance
                    )

                    distance_after = abs(
                        target_new_stance - influencer_stance
                    )

                    convergence = distance_before - distance_after

                    if convergence > 0:
                        influence_matrix[influencer][target] += round(
                            convergence, 2
                        )

        previous_stance_by_agent[target] = target_new_stance

    scores = {
        source: round(sum(targets.values()), 2)
        for source, targets in influence_matrix.items()
    }

    top_influencer = None

    if scores:
        best_agent = max(scores, key=scores.get)

        if scores[best_agent] > 0:
            top_influencer = best_agent

    return {
        "status": "ok",
        "matrix": influence_matrix,
        "scores": scores,
        "top_influencer": top_influencer,
    }