from typing import Any, Dict, List, Optional

from src.analytics.common import extract_scored_turns, get_agent_names


def compute_topology_influence(
    history_rows: List[Dict[str, Any]],
    personas: List[Dict[str, Any]],
    visibility_matrix: Optional[Dict[str, List[str]]] = None,
    min_turns: int = 3,
) -> Dict[str, Any]:
    """
    Estimates pairwise directed influence matrix based on stance convergence.
    Adheres strictly to the communication graph in visibility_matrix.
    """
    agent_names = get_agent_names(personas)
    allowed_set = set(agent_names)

    influence_matrix: Dict[str, Dict[str, float]] = {
        src: {dst: 0.0 for dst in agent_names}
        for src in agent_names
    }

    valid_turns = extract_scored_turns(history_rows, allowed_agents=allowed_set)

    if len(valid_turns) < min_turns:
        return {
            "status": "insufficient_data",
            "matrix": influence_matrix,
            "scores": {name: 0.0 for name in agent_names},
            "top_influencer": None,
        }

    previous_stance_by_agent: Dict[str, float] = {}

    for index, turn in enumerate(valid_turns):
        target = turn["agent_name"]
        target_new_stance = turn["stance"]

        if index > 0 and target in previous_stance_by_agent:
            prev_turn = valid_turns[index - 1]
            influencer = prev_turn["agent_name"]
            influencer_stance = prev_turn["stance"]

            if influencer != target:
                # Enforce topology visibility: target must be allowed to hear influencer
                is_visible = True
                if visibility_matrix and target in visibility_matrix:
                    is_visible = influencer in visibility_matrix[target]

                if is_visible:
                    target_prev_stance = previous_stance_by_agent[target]
                    dist_before = abs(target_prev_stance - influencer_stance)
                    dist_after = abs(target_new_stance - influencer_stance)
                    convergence = dist_before - dist_after

                    # Only positive convergence counts as persuasion
                    if convergence > 0:
                        influence_matrix[influencer][target] = round(
                            influence_matrix[influencer][target] + convergence, 2
                        )

        previous_stance_by_agent[target] = target_new_stance

    scores = {
        src: round(sum(targets.values()), 2)
        for src, targets in influence_matrix.items()
    }

    top_influencer = None
    if scores:
        best_agent = max(scores, key=lambda k: scores[k])
        if scores[best_agent] > 0:
            top_influencer = best_agent

    return {
        "status": "ok",
        "matrix": influence_matrix,
        "scores": scores,
        "top_influencer": top_influencer,
    }