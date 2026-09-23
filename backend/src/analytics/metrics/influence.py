from typing import Any, Dict, List, Optional
from src.analytics.common import extract_scored_turns, get_agent_names


def compute_topology_influence(
    history_rows: List[Dict[str, Any]],
    personas: List[Dict[str, Any]],
    visibility_matrix: Optional[Dict[str, List[str]]] = None,
    min_turns: int = 2,
    recency_decay: float = 0.85,
) -> Dict[str, Any]:
    """
    Estimates a pairwise directed influence matrix based on stance convergence.
    
    Fixes applied:
    1. Multi-turn Lookback: Resolves topological mismatches by checking all visible 
       speakers in the agent's listening graph, not just index - 1.
    2. Recency Decay: Prioritizes recent speakers while crediting earlier speakers 
       in multi-agent deliberations.
    3. Lowers cold-start threshold from 3 to 2 turns.
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

    # Track chronological positions and latest stances
    latest_stance_by_agent: Dict[str, float] = {}
    latest_turn_idx_by_agent: Dict[str, int] = {}

    for turn_idx, turn in enumerate(valid_turns):
        target = turn["agent_name"]
        target_new_stance = turn["stance"]

        # Only evaluate shift if this agent has taken an earlier turn (has a baseline)
        if target in latest_stance_by_agent:
            target_prev_stance = latest_stance_by_agent[target]
            stance_delta = abs(target_new_stance - target_prev_stance)

            # If the agent's stance actually shifted
            if stance_delta >= 0.02:
                # Determine who the target is topologically permitted to hear
                if visibility_matrix and target in visibility_matrix:
                    permitted_speakers = set(visibility_matrix[target]) - {target}
                else:
                    permitted_speakers = set(agent_names) - {target}

                # Check convergence against all visible speakers who have spoken previously
                for influencer in permitted_speakers:
                    if influencer in latest_stance_by_agent:
                        influencer_stance = latest_stance_by_agent[influencer]

                        dist_before = abs(target_prev_stance - influencer_stance)
                        dist_after = abs(target_new_stance - influencer_stance)
                        convergence = dist_before - dist_after

                        # Positive convergence: Target moved closer to this influencer
                        if convergence > 0:
                            # Calculate turns elapsed since this influencer last spoke
                            turns_elapsed = max(1, turn_idx - latest_turn_idx_by_agent[influencer])
                            decay = recency_decay ** (turns_elapsed - 1)
                            weighted_convergence = convergence * decay

                            influence_matrix[influencer][target] = round(
                                influence_matrix[influencer][target] + weighted_convergence, 
                                2
                            )

        # Update latest stance and turn index for the target
        latest_stance_by_agent[target] = target_new_stance
        latest_turn_idx_by_agent[target] = turn_idx

    # Tally total outbound influence score per agent
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