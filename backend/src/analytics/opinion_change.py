from typing import Any, Dict, List


def compute_opinion_trajectories(
    history_rows: List[Dict[str, Any]],
    personas: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build stance trajectories for every agent across discussion rounds.

    Each trajectory point contains:
    - round: discussion round number
    - stance: current stance score
    - change: difference from the agent's previous recorded stance
    """

    agent_names = [persona["name"] for persona in personas]

    trajectories: Dict[str, List[Dict[str, Any]]] = {
        name: [] for name in agent_names
    }

    latest_by_round_agent: Dict[tuple, float] = {}

    for row in history_rows:
        opinion_snapshot = row.get("opinion_snapshot")

        if not opinion_snapshot:
            continue

        stance = opinion_snapshot.get("current_stance_score")

        if stance is None:
            continue

        round_number = row.get("round_number")
        agent_name = row.get("agent_name")

        if round_number is None or agent_name not in trajectories:
            continue

        latest_by_round_agent[(round_number, agent_name)] = float(stance)

    for agent_name in agent_names:
        agent_points = [
            (round_number, stance)
            for (round_number, name), stance in latest_by_round_agent.items()
            if name == agent_name
        ]

        agent_points.sort(key=lambda item: item[0])

        previous_stance = None

        for round_number, stance in agent_points:
            change = (
                None
                if previous_stance is None
                else round(stance - previous_stance, 2)
            )

            trajectories[agent_name].append(
                {
                    "round": round_number,
                    "stance": round(stance, 2),
                    "change": change,
                }
            )

            previous_stance = stance

    return trajectories