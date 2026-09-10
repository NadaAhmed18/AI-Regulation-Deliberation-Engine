import json
import re
from typing import Dict, Any
from langfuse import observe

from src.clients.llm_client import LLMClient
from src.utils.prompt_builder import render_prompt

class OpinionGrader:
    def __init__(self):
        self.llm = LLMClient()

    @observe(as_type="generation", name="grade_opinion_shift")
    def evaluate_stance(self, topic: str, agent_name: str, original_stance: str, latest_statement: str, previous_score: float = 0.0) -> Dict[str, Any]:
        """
        Evaluates an agent's latest statement to determine their current mathematical stance (-5.0 to 5.0).
        """
        prompt = render_prompt(
            "opinion_grader",
            topic=topic,
            agent_name=agent_name,
            original_stance=original_stance,
            latest_statement=latest_statement
        )

        messages = [
            {"role": "system", "content": "You are a JSON-only evaluation API."},
            {"role": "user", "content": prompt}
        ]

        response = self.llm.generate_response(messages, response_format="json_object")
        content = response.get("content", "")

        # Default fallback in case of LLM parsing failure
        result = {
            "current_stance_score": previous_score,
            "shift_magnitude": 0.0,
            "reasoning": "Failed to parse opinion shift from LLM."
        }

        try:
            # Regex to cleanly extract the JSON object
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                
                result["current_stance_score"] = float(parsed.get("current_stance_score", previous_score))
                result["shift_magnitude"] = float(parsed.get("shift_magnitude", 0.0))
                result["reasoning"] = str(parsed.get("reasoning", "Evaluated successfully."))
                
                # Sanity check bounds (-5.0 to 5.0)
                result["current_stance_score"] = max(-5.0, min(5.0, result["current_stance_score"]))
                
        except Exception as e:
            print(f"[!] Opinion Grader Error: {e} | Raw Output: {content}")

        return result


if __name__ == "__main__":
    # Test runner: python -m src.orchestration.opinion_grader
    print("\n" + "=" * 60)
    print(" smoke test: OpinionGrader ".center(60, "="))
    print("=" * 60)

    grader = OpinionGrader()
    test_topic = "Should frontier open-source AI models require government licenses?"
    agent = "Sarah Chen"
    baseline_stance = "Strongly pro-open source; opposes centralized licensing."

    # Turn 1: Defiant statement
    turn_1_text = (
        "Mandating licenses for open weights centralizes technology into the hands of cloud monopolies. "
        "Open security auditing is strictly superior to government gatekeeping."
    )
    res_1 = grader.evaluate_stance(
        topic=test_topic,
        agent_name=agent,
        original_stance=baseline_stance,
        latest_statement=turn_1_text,
        previous_score=0.0
    )
    print(f"\n[Turn 1 Output for {agent}]:")
    print(json.dumps(res_1, indent=2))

    # Turn 2: Concession / shift statement
    turn_2_text = (
        "While I remain opposed to broad bans, I can concede that models trained on compute clusters "
        "exceeding 10^26 FLOPs pose unique systemic risks that merit third-party verification."
    )
    res_2 = grader.evaluate_stance(
        topic=test_topic,
        agent_name=agent,
        original_stance=baseline_stance,
        latest_statement=turn_2_text,
        previous_score=res_1["current_stance_score"]
    )
    print(f"\n[Turn 2 Output after Concession (Shift Delta: {res_2['shift_magnitude']})]:")
    print(json.dumps(res_2, indent=2))