"""
ORCHESTRATOR — Token-Weighted Fair Turn Routing

Replaces costly, high-latency LLM routing with a sub-millisecond,
token-inverse selection policy:
1. Turn 1 (Opening): Starts completely randomly among all personas.
2. Turns 2..N (Openings phase): Any agent with 0 tokens gets priority.
3. Mid-Debate: Softmax/inverse-token weighting favors agents with lower
   cumulative token consumption while excluding the immediate previous speaker.
"""

import random
from typing import List, Dict, Any, Optional
from langfuse import observe


class Orchestrator:
    """Fast, deterministic-probabilistic debate moderator."""

    def __init__(self, base_smoothing_tokens: int = 150):
        # Base smoothing prevents highest-talking agents from dropping to 0% chance
        self.base_smoothing_tokens = base_smoothing_tokens

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Fast token approximation based on word count (~1.33 tokens per word)."""
        if not text:
            return 0
        words = len(text.strip().split())
        return max(1, int(words * 1.33))

    def _calculate_cumulative_tokens(
        self,
        personas: List[Dict[str, Any]],
        history: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """Calculates total spoken tokens per persona across the simulation."""
        token_counts: Dict[str, int] = {p["name"]: 0 for p in personas}

        for row in history:
            speaker = row.get("agent_name")
            content = row.get("content", "")
            if speaker in token_counts:
                token_counts[speaker] += self._estimate_tokens(content)

        return token_counts

    @observe(name="orchestrator_routing")
    def decide_next_speaker(
        self,
        topic: str,
        personas: List[Dict[str, Any]],
        history: Optional[List[Dict[str, Any]]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Selects the next speaker in <1ms based on participation equality.
        
        Args:
            topic: Debate topic (kept for interface consistency).
            personas: List of debate persona dictionaries.
            history: Ordered list of discussion_history DB rows.
            messages: Optional fallback message list if raw DB rows aren't provided.
        """
        persona_names = [p["name"] for p in personas]
        if not persona_names:
            raise ValueError("No personas provided to orchestrator.")

        if len(persona_names) == 1:
            return persona_names[0]

        # Normalize turns from either history rows or context messages
        turns = history or []
        if not turns and messages:
            # Fallback parsing if caller only passed messages
            for m in messages:
                content = m.get("content", "")
                if content.startswith("[") and "]:" in content:
                    speaker = content[1 : content.index("]:")]
                    turns.append({"agent_name": speaker, "content": content})

        # =====================================================================
        # TIER 1: First turn of the simulation -> Pick randomly
        # =====================================================================
        if not turns:
            chosen = random.choice(persona_names)
            print(f"[Orchestrator] 🎲 Opening turn: randomly selected '{chosen}'.")
            return chosen

        # Identify immediate previous speaker
        last_speaker = turns[-1].get("agent_name")

        # Exclude immediate speaker to prevent consecutive monologues
        eligible_personas = [p for p in persona_names if p != last_speaker]
        if not eligible_personas:
            eligible_personas = persona_names

        # Compute cumulative token consumption
        tokens_by_agent = self._calculate_cumulative_tokens(personas, turns)

        # =====================================================================
        # TIER 2: Unheard agents get 100% priority (Opening statements phase)
        # =====================================================================
        unheard_agents = [name for name in eligible_personas if tokens_by_agent.get(name, 0) == 0]
        if unheard_agents:
            chosen = random.choice(unheard_agents)
            print(f"[Orchestrator] 🎙️ Opening phase: selected unheard agent '{chosen}'.")
            return chosen

        # =====================================================================
        # TIER 3: Inverse-Token Weighted Selection (Equalizing airtime)
        # =====================================================================
        candidate_tokens = [tokens_by_agent.get(name, 0) for name in eligible_personas]
        max_tokens = max(candidate_tokens)

        # Deficit weight: the fewer tokens an agent has spoken, the higher the weight
        weights = [
            (max_tokens - tokens_by_agent.get(name, 0)) + self.base_smoothing_tokens
            for name in eligible_personas
        ]

        # Sample based on weights
        chosen = random.choices(eligible_personas, weights=weights, k=1)[0]
        
        print(
            f"[Orchestrator] ⚖️ Selected '{chosen}' "
            f"(Tokens: {tokens_by_agent.get(chosen, 0)} | Airtime weights: "
            f"{dict(zip(eligible_personas, weights))})"
        )
        return chosen