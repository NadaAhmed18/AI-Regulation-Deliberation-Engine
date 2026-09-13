from itertools import combinations
from typing import Any, Dict, List


def compute_round_agreement(
    history_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Compute an agreement score for each discussion round.

    Score range:
    - 1.0 = complete agreement
    - 0.0 = maximum polarization
    """

    stances_by_round: Dict[int, List[float]] = {}

    for row in history_rows:
        opinion_snapshot = row.get("opinion_snapshot")

        if not opinion_snapshot:
            continue

        stance = opinion_snapshot.get("current_stance_score")
        round_number = row.get("round_number")

        if stance is None or round_number is None:
            continue

        stances_by_round.setdefault(round_number, []).append(float(stance))

    results: List[Dict[str, Any]] = []

    for round_number in sorted(stances_by_round):
        stances = stances_by_round[round_number]

        if len(stances) == 1:
            agreement_score = 1.0
        else:
            differences = [
                abs(a - b)
                for a, b in combinations(stances, 2)
            ]

            mean_difference = sum(differences) / len(differences)

            agreement_score = 1 - (mean_difference / 10)
            agreement_score = max(0.0, min(1.0, agreement_score))
            agreement_score = round(agreement_score, 2)

        if agreement_score >= 0.75:
            classification = "High Consensus"
        elif agreement_score >= 0.50:
            classification = "Moderate Alignment"
        elif agreement_score >= 0.25:
            classification = "Significant Polarization"
        else:
            classification = "Extreme Polarization"

        results.append(
            {
                "round": round_number,
                "agreement_score": agreement_score,
                "classification": classification,
            }
        )

    return results