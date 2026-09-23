"""
AGREEMENT & CONSENSUS METRICS

Calculates:
1. Pairwise normalized stance distances [0.0, 1.0] and agreement scores.
2. Directional visibility-masked alignment matrices.
3. Chronological round-by-round consensus dynamics.
"""

from itertools import combinations
from typing import Any, Dict, List, Optional
from src.analytics.common import extract_scored_turns, get_agent_names

STANCE_SPAN = 10.0  # Max distance between -5.0 and +5.0


def compute_pairwise_topological_agreement(
    history_rows: List[Dict[str, Any]],
    personas: List[Dict[str, Any]],
    visibility_matrix: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    """
    Computes pairwise normalized distance and agreement between agents,
    strictly masked by who each agent is topologically allowed to hear.
    
    Returns:
        - matrix: {listener: {speaker: {"distance": float, "agreement": float, "is_visible": bool}}}
        - agent_scores: {agent_name: float} (average agreement with visible peers)
        - network_agreement: float (overall network consensus across visible edges)
    """
    agent_names = get_agent_names(personas)
    valid_turns = extract_scored_turns(history_rows, allowed_agents=set(agent_names))

    # 1. Collect latest stance for every agent who has spoken
    latest_stances: Dict[str, float] = {}
    for turn in valid_turns:
        latest_stances[turn["agent_name"]] = turn["stance"]

    # 2. Build pairwise matrix
    matrix: Dict[str, Dict[str, Any]] = {
        listener: {} for listener in agent_names
    }
    agent_averages: Dict[str, Optional[float]] = {}
    all_visible_agreements: List[float] = []

    for listener in agent_names:
        # Determine allowed visible speakers for this listener
        if visibility_matrix and listener in visibility_matrix:
            permitted = set(visibility_matrix[listener]) - {listener}
        else:
            permitted = set(agent_names) - {listener}  # Mesh / all-see-all

        listener_stance = latest_stances.get(listener)
        visible_agreements_for_listener: List[float] = []

        for speaker in agent_names:
            if speaker == listener:
                continue

            speaker_stance = latest_stances.get(speaker)
            is_visible = speaker in permitted

            # If both have spoken, compute normalized distance and agreement
            if listener_stance is not None and speaker_stance is not None:
                raw_diff = abs(listener_stance - speaker_stance)
                norm_distance = round(raw_diff / STANCE_SPAN, 3)          # [0.0, 1.0]
                norm_agreement = round(1.0 - norm_distance, 3)             # [0.0, 1.0]

                matrix[listener][speaker] = {
                    "distance": norm_distance,
                    "agreement": norm_agreement,
                    "is_visible": is_visible,
                }

                if is_visible:
                    visible_agreements_for_listener.append(norm_agreement)
                    all_visible_agreements.append(norm_agreement)
            else:
                # One or both agents have not yet spoken
                matrix[listener][speaker] = {
                    "distance": None,
                    "agreement": None,
                    "is_visible": is_visible,
                }

        # Average agreement for this listener with only their visible peers
        if visible_agreements_for_listener:
            avg = sum(visible_agreements_for_listener) / len(visible_agreements_for_listener)
            agent_averages[listener] = round(avg, 2)
        else:
            agent_averages[listener] = 1.0 if listener_stance is not None else None

    # Overall network consensus across all visible edges
    network_agreement = (
        round(sum(all_visible_agreements) / len(all_visible_agreements), 2)
        if all_visible_agreements
        else 1.0
    )

    return {
        "matrix": matrix,
        "agent_scores": agent_averages,
        "network_agreement": network_agreement,
    }


def compute_round_agreement(
    history_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Computes global agreement score [0.0, 1.0] across all active agents per round.
    1.0 = absolute consensus, 0.0 = extreme polarization.
    """
    valid_turns = extract_scored_turns(history_rows)
    if not valid_turns:
        return []

    turns_by_round: Dict[int, List[Dict[str, Any]]] = {}
    for turn in valid_turns:
        turns_by_round.setdefault(turn["round_number"], []).append(turn)

    results: List[Dict[str, Any]] = []
    latest_stances_by_agent: Dict[str, float] = {}

    for round_number in sorted(turns_by_round.keys()):
        for turn in turns_by_round[round_number]:
            latest_stances_by_agent[turn["agent_name"]] = turn["stance"]

        active_stances = list(latest_stances_by_agent.values())

        if len(active_stances) <= 1:
            agreement_score = 1.0
        else:
            differences = [abs(a - b) for a, b in combinations(active_stances, 2)]
            mean_diff = sum(differences) / len(differences)
            raw_score = 1.0 - (mean_diff / STANCE_SPAN)
            agreement_score = round(max(0.0, min(1.0, raw_score)), 2)

        if agreement_score >= 0.75:
            classification = "High Consensus"
        elif agreement_score >= 0.50:
            classification = "Moderate Alignment"
        elif agreement_score >= 0.25:
            classification = "Significant Polarization"
        else:
            classification = "Extreme Polarization"

        results.append({
            "round": round_number,
            "agreement_score": agreement_score,
            "classification": classification,
        })

    return results