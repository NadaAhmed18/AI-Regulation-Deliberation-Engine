"""
ORCHESTRATOR — Token-Weighted Fair Turn Routing

Zero-latency (<1ms) participant selection:
1. Opening Phase: Any agent who has not spoken (0 tokens) is prioritized.
   (Turn 1 naturally picks randomly among all agents).
2. Deliberation Phase: Inverse-token deficit weighting equalizes airtime
   while excluding the immediate previous speaker to prevent monologues.
"""

import random
from typing import List, Dict, Any, Optional
from langfuse import observe


class Orchestrator:
    def __init__(self, base_smoothing_tokens: int = 150):
        # Smoothing prevents the most active speakers from reaching a 0% selection probability
        self.base_smoothing_tokens = base_smoothing_tokens

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Fast token approximation (~1.33 tokens per word)."""
        return max(1, int(len(text.split()) * 1.33)) if text else 0

    def _get_token_usage(self, personas: List[Dict[str, Any]], history: List[Dict[str, Any]]) -> Dict[str, int]:
        """Sums cumulative spoken tokens per agent from discussion history."""
        tokens = {p["name"]: 0 for p in personas}
        for row in history:
            speaker = row.get("agent_name")
            if speaker in tokens:
                tokens[speaker] += self._estimate_tokens(row.get("content", ""))
        return tokens

    @observe(name="orchestrator_routing")
    def decide_next_speaker(
        self,
        personas: List[Dict[str, Any]],
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Selects the next speaker based on airtime equality in <1ms."""
        names = [p["name"] for p in personas]
        if not names:
            raise ValueError("No personas provided to orchestrator.")
        if len(names) == 1:
            return names[0]

        turns = history or []
        tokens_by_agent = self._get_token_usage(personas, turns)

        # Exclude immediate previous speaker to prevent consecutive self-replies
        last_speaker = turns[-1].get("agent_name") if turns else None
        candidates = [name for name in names if name != last_speaker] or names

        # 1. Unheard Agents Phase (Handles Turn 1 and opening statements)
        unheard = [name for name in candidates if tokens_by_agent[name] == 0]
        if unheard:
            return random.choice(unheard)

        # 2. Deficit-Weighted Airtime Balancing
        candidate_tokens = [tokens_by_agent[name] for name in candidates]
        max_tokens = max(candidate_tokens)

        # The fewer tokens an agent has spoken, the higher their selection weight
        weights = [
            (max_tokens - tokens_by_agent[name]) + self.base_smoothing_tokens
            for name in candidates
        ]

        return random.choices(candidates, weights=weights, k=1)[0]