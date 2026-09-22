from typing import Any, Dict, List, Optional


def find_largest_opinion_shift(
    trajectories: Dict[str, List[Dict[str, Any]]],
    min_shift: float = 1.0,
) -> Optional[Dict[str, Any]]:
    """
    Find the agent with the largest net opinion shift.

    Net shift = final stance - initial stance.
    Returns None if no meaningful shift is found.
    """

    best_agent = None
    best_initial = None
    best_final = None
    best_shift = 0.0

    for agent_name, points in trajectories.items():
        # We need at least two stance points to measure a shift.
        if len(points) < 2:
            continue

        initial_stance = float(points[0]["stance"])
        final_stance = float(points[-1]["stance"])
        net_shift = final_stance - initial_stance

        # Compare absolute values because both positive and negative
        # movements can represent a significant opinion change.
        if abs(net_shift) > abs(best_shift):
            best_agent = agent_name
            best_initial = initial_stance
            best_final = final_stance
            best_shift = net_shift

    # Do not create a finding for very small or nonexistent changes.
    if best_agent is None or abs(best_shift) < min_shift:
        return None

    return {
        "type": "largest_opinion_shift",
        "title": "Largest Opinion Shift",
        "text": (
            f"{best_agent} showed the largest opinion shift "
            f"({best_shift:+.1f} points)."
        ),
        "agent": best_agent,
        "value": round(best_shift, 2),
        "evidence": {
            "initial_stance": round(best_initial, 2),
            "final_stance": round(best_final, 2),
            "net_shift": round(best_shift, 2),
        },
    }
def find_most_influential_agent(
    influence_result: Dict[str, Any],
    min_influence: float = 0.01,
) -> Optional[Dict[str, Any]]:
    """
    Find the agent with the highest total measured influence.
    Returns None when influence data is insufficient or no meaningful
    influence was detected.
    """

    if influence_result.get("status") != "ok":
        return None

    influence_scores = influence_result.get("scores", {})

    if not influence_scores:
        return None

    best_agent = max(
        influence_scores,
        key=lambda agent: influence_scores[agent],
    )

    best_score = float(influence_scores[best_agent])

    if best_score < min_influence:
        return None

    return {
        "type": "most_influential_agent",
        "title": "Most Influential Agent",
        "text": (
            f"{best_agent} had the highest measured influence "
            f"with a score of {best_score:.2f}."
        ),
        "agent": best_agent,
        "value": round(best_score, 2),
        "evidence": {
            "influence_score": round(best_score, 2),
        },
    }
def find_strongest_influence_connection(
    influence_result: Dict[str, Any],
    min_influence: float = 0.01,
) -> Optional[Dict[str, Any]]:
    """
    Find the strongest measured influence relationship
    between two different agents.
    """

    if influence_result.get("status") != "ok":
        return None

    influence_matrix = influence_result.get("matrix", {})

    if not influence_matrix:
        return None

    best_source = None
    best_target = None
    best_score = 0.0

    for source_agent, targets in influence_matrix.items():
        for target_agent, score in targets.items():
            score = float(score)

            # Ignore self-influence.
            if source_agent == target_agent:
                continue

            if score > best_score:
                best_source = source_agent
                best_target = target_agent
                best_score = score

    if (
        best_source is None
        or best_target is None
        or best_score < min_influence
    ):
        return None

    return {
        "type": "strongest_influence_connection",
        "title": "Strongest Influence Connection",
        "text": (
            f"The strongest measured influence was "
            f"{best_source} → {best_target} "
            f"with a score of {best_score:.2f}."
        ),
        "source_agent": best_source,
        "target_agent": best_target,
        "value": round(best_score, 2),
        "evidence": {
            "source": best_source,
            "target": best_target,
            "influence_score": round(best_score, 2),
        },
    }
def generate_key_findings(
    trajectories: Dict[str, List[Dict[str, Any]]],
    influence_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Generate deterministic key findings from existing analytics results.
    No LLM or external API calls are used.
    """

    findings = []

    opinion_shift = find_largest_opinion_shift(trajectories)
    if opinion_shift is not None:
        findings.append(opinion_shift)

    most_influential = find_most_influential_agent(influence_result)
    if most_influential is not None:
        findings.append(most_influential)

    strongest_connection = find_strongest_influence_connection(
        influence_result
    )
    if strongest_connection is not None:
        findings.append(strongest_connection)

    return findings