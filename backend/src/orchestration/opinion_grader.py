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