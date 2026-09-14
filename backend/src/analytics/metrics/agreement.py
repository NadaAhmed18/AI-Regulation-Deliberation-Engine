from itertools import combinations
from typing import Any, Dict, List

from src.analytics.common import extract_scored_turns


def compute_round_agreement(
    history_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Computes an agreement score [0.0, 1.0] for each discussion round.
    1.0 = absolute consensus, 0.0 = extreme polarization.
    """
    valid_turns = extract_scored_turns(history_rows)
    stances_by_round: Dict[int, List[float]] = {}

    for turn in valid_turns:
        stances_by_round.setdefault(turn["round_number"], []).append(turn["stance"])

    results: List[Dict[str, Any]] = []

    for round_number in sorted(stances_by_round.keys()):
        stances = stances_by_round[round_number]

        if len(stances) <= 1:
            agreement_score = 1.0
        else:
            differences = [abs(a - b) for a, b in combinations(stances, 2)]
            mean_diff = sum(differences) / len(differences)
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