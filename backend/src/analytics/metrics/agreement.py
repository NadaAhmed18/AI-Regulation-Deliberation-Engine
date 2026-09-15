from itertools import combinations
from typing import Any, Dict, List

from src.analytics.common import extract_scored_turns


def compute_round_agreement(
    history_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Computes an agreement score [0.0, 1.0] for each discussion round.
    Calculated across ALL participating agents based on their latest stance up to that round.
    1.0 = absolute consensus, 0.0 = extreme polarization.
    """
    valid_turns = extract_scored_turns(history_rows)
    if not valid_turns:
        return []

    # Group turns chronologically by round
    turns_by_round: Dict[int, List[Dict[str, Any]]] = {}
    for turn in valid_turns:
        turns_by_round.setdefault(turn["round_number"], []).append(turn)

    results: List[Dict[str, Any]] = []
    latest_stances_by_agent: Dict[str, float] = {}

    for round_number in sorted(turns_by_round.keys()):
        # Update latest known stance for the agent(s) who spoke in this round
        for turn in turns_by_round[round_number]:
            latest_stances_by_agent[turn["agent_name"]] = turn["stance"]

        active_stances = list(latest_stances_by_agent.values())

        if len(active_stances) <= 1:
            # Only 1 agent has spoken so far in the debate
            agreement_score = 1.0
        else:
            differences = [abs(a - b) for a, b in combinations(active_stances, 2)]
            mean_diff = sum(differences) / len(differences)
            # 10.0 is the maximum possible stance distance across [-5.0, +5.0]
            raw_score = 1.0 - (mean_diff / 10.0)
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