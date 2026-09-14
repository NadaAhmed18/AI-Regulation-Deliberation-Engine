from typing import Any, Dict, List

from src.analytics.common import extract_scored_turns, get_agent_names


def compute_opinion_trajectories(
    history_rows: List[Dict[str, Any]],
    personas: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Builds chronological stance trajectories for every agent across rounds.
    Output per point: round, stance, and shift from previous turn.
    """
    agent_names = get_agent_names(personas)
    valid_turns = extract_scored_turns(history_rows, allowed_agents=set(agent_names))

    trajectories: Dict[str, List[Dict[str, Any]]] = {
        name: [] for name in agent_names
    }

    # Deduplicate within round if multiple turns occurred per round (keeps latest)
    latest_by_round_agent: Dict[tuple, float] = {}
    for turn in valid_turns:
        latest_by_round_agent[(turn["round_number"], turn["agent_name"])] = turn["stance"]

    for agent in agent_names:
        agent_points = [
            (rnd, stance)
            for (rnd, name), stance in latest_by_round_agent.items()
            if name == agent
        ]
        agent_points.sort(key=lambda item: item[0])

        previous_stance = None
        for rnd, stance in agent_points:
            change = (
                None
                if previous_stance is None
                else round(stance - previous_stance, 2)
            )

            trajectories[agent].append({
                "round": rnd,
                "stance": round(stance, 2),
                "change": change,
            })
            previous_stance = stance

    return trajectories