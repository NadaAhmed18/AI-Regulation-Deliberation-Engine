import json
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


def _normalize_snapshot(raw_snapshot: Any) -> Optional[Dict[str, Any]]:
    """Guarantees opinion_snapshot is a dict, resolving stringified JSON."""
    if isinstance(raw_snapshot, dict):
        return raw_snapshot
    if isinstance(raw_snapshot, str) and raw_snapshot.strip():
        try:
            parsed = json.loads(raw_snapshot)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def extract_scored_turns(
    history_rows: List[Dict[str, Any]],
    allowed_agents: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Filters and normalizes discussion turns containing valid opinion snapshots.
    Guarantees 'stance' as float and 'round_number' as int.
    Safely parses JSON strings.
    """
    valid_turns: List[Dict[str, Any]] = []

    for row in history_rows:
        opinion_snapshot = _normalize_snapshot(row.get("opinion_snapshot"))
        if not opinion_snapshot:
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

        # Safely parse retrieved sources
        sources = row.get("retrieved_sources") or []
        if isinstance(sources, str):
            try:
                sources = json.loads(sources)
            except Exception:
                sources = []

        valid_turns.append({
            "id": row.get("id"),
            "round_number": round_num,
            "agent_name": agent_name,
            "stance": numeric_stance,
            "opinion_snapshot": opinion_snapshot,
            "retrieved_sources": sources,
        })

    return valid_turns


def extract_citations(history_rows: List[Dict[str, Any]]) -> List[str]:
    """Extracts and deduplicates all sources cited across debate turns."""
    sources: Set[str] = set()
    for turn in history_rows:
        raw_sources = turn.get("retrieved_sources") or []
        if isinstance(raw_sources, str):
            try:
                raw_sources = json.loads(raw_sources)
            except Exception:
                raw_sources = []
        for src in raw_sources:
            clean_src = str(src).strip()
            if clean_src:
                sources.add(clean_src)
    return sorted(list(sources))


def extract_persuasion_signals(history_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extracts step-by-step stance shifts.
    Resolves the prior speaker automatically if 'influencer' is missing from the snapshot.
    """
    signals: List[Dict[str, Any]] = []
    last_speaker: Optional[str] = None

    for turn in history_rows:
        snapshot = _normalize_snapshot(turn.get("opinion_snapshot")) or {}
        shift_mag = snapshot.get("shift_magnitude")
        current_agent = turn.get("agent_name")

        if shift_mag is not None:
            try:
                float_shift = float(shift_mag)
            except (ValueError, TypeError):
                float_shift = 0.0

            if abs(float_shift) >= 0.01:
                # If explicit influencer is recorded, use it; otherwise use the preceding speaker
                detected_source = snapshot.get("influencer")
                if not detected_source or detected_source == "Group Deliberation":
                    detected_source = last_speaker if (last_speaker and last_speaker != current_agent) else "Group Deliberation"

                signals.append({
                    "id": str(turn.get("id")),
                    "round": turn.get("round_number", 1),
                    "source": detected_source,
                    "target": current_agent,
                    "shift": float_shift,
                    "gamma": round(abs(float_shift) * 0.05, 4),
                    "dynamic": "Convergence" if float_shift > 0 else "Polarization",
                    "reasoning": snapshot.get("reasoning", f"Stance shifted by {float_shift:+.2f}"),
                })

        if current_agent:
            last_speaker = current_agent

    return signals