from typing import Any, Dict, List, Optional, Set


def get_agent_names(personas: List[Dict[str, Any]]) -> List[str]:
    """Extracts unique persona names preserving original order."""
    seen: Set[str] = set()
    names: List[str] = []
    for p in personas:
        name = p.get("name")
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def extract_scored_turns(
    history_rows: List[Dict[str, Any]],
    allowed_agents: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Filters and normalizes discussion turns containing valid opinion snapshots.
    Guarantees 'stance' as float and 'round_number' as int.
    """
    valid_turns: List[Dict[str, Any]] = []

    for row in history_rows:
        opinion_snapshot = row.get("opinion_snapshot")
        if not isinstance(opinion_snapshot, dict):
            continue

        stance = opinion_snapshot.get("current_stance_score")
        if stance is None:
            continue

        agent_name = row.get("agent_name")
        if not agent_name:
            continue

        if allowed_agents is not None and agent_name not in allowed_agents:
            continue

        try:
            numeric_stance = float(stance)
        except (ValueError, TypeError):
            continue

        raw_round = row.get("round_number")
        try:
            round_num = int(raw_round) if raw_round is not None else 1
        except (ValueError, TypeError):
            round_num = 1

        valid_turns.append({
            "id": row.get("id"),
            "round_number": round_num,
            "agent_name": agent_name,
            "stance": numeric_stance,
            "opinion_snapshot": opinion_snapshot,
            "retrieved_sources": row.get("retrieved_sources") or [],
        })

    return valid_turns


def extract_citations(history_rows: List[Dict[str, Any]]) -> List[str]:
    """Extracts and deduplicates all sources cited across debate turns."""
    sources: Set[str] = set()
    for turn in history_rows:
        for src in turn.get("retrieved_sources") or []:
            clean_src = str(src).strip()
            if clean_src:
                sources.add(clean_src)
    return sorted(list(sources))


def extract_persuasion_signals(history_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extracts step-by-step stance shifts and dynamic signals."""
    signals: List[Dict[str, Any]] = []
    for turn in history_rows:
        snapshot = turn.get("opinion_snapshot") or {}
        shift_mag = snapshot.get("shift_magnitude")

        if shift_mag is not None and shift_mag != 0.0:
            signals.append({
                "id": str(turn.get("id")),
                "round": turn.get("round_number"),
                "source": snapshot.get("influencer") or "Group Deliberation",
                "target": turn.get("agent_name"),
                "shift": float(shift_mag),
                "gamma": round(abs(float(shift_mag)) * 0.05, 4),
                "dynamic": "Convergence" if float(shift_mag) > 0 else "Polarization",
                "reasoning": snapshot.get("reasoning", ""),
            })
    return signals