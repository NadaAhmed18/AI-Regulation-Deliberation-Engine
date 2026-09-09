import json
import re
from typing import Dict, Any, Optional
from langfuse import observe

from src.clients.llm_client import LLMClient
from src.utils.prompt_builder import render_prompt
from src.utils.stance_utils import compute_shift_magnitude


class OpinionGrader:
    def __init__(self):
        self.llm = LLMClient()

    @observe(as_type="generation", name="grade_opinion_shift")
    def evaluate_stance(
        self,
        topic: str,
        agent_name: str,
        original_stance: str,
        latest_statement: str,
        previous_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates an agent's latest statement to determine their current
        mathematical stance (-5.0 to 5.0), using an LLM as the grader.

        Args:
            previous_score: The agent's own previous stance score in this
                simulation, or `None` if this is their first scored turn.
                `None` (not `0.0`) matters here for two reasons: (1) it is
                passed into the prompt so the LLM is explicitly told
                "no prior score exists" rather than being handed a
                fabricated neutral baseline to compute a shift against,
                and (2) `shift_magnitude` below is computed with
                `stance_utils.compute_shift_magnitude`, the exact same
                helper `DebertaStanceGrader` (`nli_grader.py`) uses — so
                both graders treat a missing prior score identically
                instead of each re-deriving the None-vs-0.0 rule
                slightly differently.
        """
        previous_score_text = (
            "None (this is the agent's first scored turn — do not "
            "report a shift_magnitude, use 0.0)"
            if previous_score is None
            else f"{previous_score:.2f}"
        )

        prompt = render_prompt(
            "opinion_grader",
            topic=topic,
            agent_name=agent_name,
            original_stance=original_stance,
            latest_statement=latest_statement,
            previous_score=previous_score_text,
        )

        messages = [
            {"role": "system", "content": "You are a JSON-only evaluation API."},
            {"role": "user", "content": prompt}
        ]

        response = self.llm.generate_response(messages, response_format="json_object")
        content = response.get("content", "")

        # Default fallback in case of LLM parsing failure. `current_stance_score`
        # falls back to `previous_score` if there is one (best available
        # estimate — assume unchanged), or 0.0 (neutral) only if there is
        # no previous score to fall back to.
        fallback_score = previous_score if previous_score is not None else 0.0
        result = {
            "current_stance_score": fallback_score,
            "shift_magnitude": compute_shift_magnitude(fallback_score, previous_score),
            "reasoning": "Failed to parse opinion shift from LLM."
        }

        try:
            # Regex to cleanly extract the JSON object
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))

                result["current_stance_score"] = float(parsed.get("current_stance_score", fallback_score))
                result["reasoning"] = str(parsed.get("reasoning", "Evaluated successfully."))

                # Sanity check bounds (-5.0 to 5.0)
                result["current_stance_score"] = max(-5.0, min(5.0, result["current_stance_score"]))

                # shift_magnitude is only meaningful if there was a
                # previous score to shift from; don't trust an LLM-
                # reported shift against a baseline that doesn't exist.
                result["shift_magnitude"] = compute_shift_magnitude(result["current_stance_score"], previous_score)

        except Exception as e:
            print(f"[!] Opinion Grader Error: {e} | Raw Output: {content}")

        return result
        
if __name__ == "__main__":
    print("=== OpinionGrader Smoke Test ===")

    grader = OpinionGrader()

    topic = "AI Regulation under the EU AI Act"
    agent_name = "Marcus Chen"
    original_stance = (
        "Supports AI innovation and is cautious about regulatory "
        "burden on startups and SMEs."
    )

    # -----------------------------
    # Turn 1: First scored statement
    # -----------------------------
    statement_1 = (
        "The EU AI Act can provide useful safeguards, "
        "but startups need proportional compliance requirements."
    )

    result_1 = grader.evaluate_stance(
        topic=topic,
        agent_name=agent_name,
        original_stance=original_stance,
        latest_statement=statement_1,
        previous_score=None,
    )

    print("\n--- Turn 1 ---")
    print(f"Statement: {statement_1}")
    print(f"Current stance: {result_1['current_stance_score']}")
    print(f"Shift magnitude: {result_1['shift_magnitude']}")
    print(f"Reasoning: {result_1['reasoning']}")

    # -----------------------------
    # Turn 2: Use Turn 1 score
    # -----------------------------
    statement_2 = (
        "After considering the risks of discrimination and lack of "
        "transparency, I now support stronger AI regulation."
    )

    result_2 = grader.evaluate_stance(
        topic=topic,
        agent_name=agent_name,
        original_stance=original_stance,
        latest_statement=statement_2,
        previous_score=result_1["current_stance_score"],
    )

    print("\n--- Turn 2 ---")
    print(f"Statement: {statement_2}")
    print(f"Previous stance: {result_1['current_stance_score']}")
    print(f"Current stance: {result_2['current_stance_score']}")
    print(f"Shift magnitude: {result_2['shift_magnitude']}")
    print(f"Reasoning: {result_2['reasoning']}")

    print("\n=== Smoke Test Passed ===")