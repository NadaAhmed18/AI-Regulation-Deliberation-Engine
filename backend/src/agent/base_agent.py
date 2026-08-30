"""
BASE REACT AGENT MODULE

GUIDELINES FOR TEAM MEMBERS:
-----------------------------
Purpose:
    Serve as the autonomous core for all simulation stakeholders. This class 
    manages the Persona injection and executes the ReAct (Reason + Act) loop, 
    dynamically calling tools via the central `tool_registry`.

Dependencies to Import:
    - `LLMClient` from `src.clients.llm_client`
    - `get_all_tool_schemas`, `execute_tool` from `src.agent.tools.tool_registry`
    - (Optional/Later) Memory manager for saving histories.

================================================================================
CLASS STRUCTURE & METHOD IMPLEMENTATION GUIDE:
================================================================================

Class: BaseAgent
----------------

1. __init__(self, persona: dict, provider: str = None, model_name: str = None):
    - 1. Extract Persona traits:
         self.name = persona.get("name")
         self.background = persona.get("background")
         self.stance = persona.get("stance")
         self.tone = persona.get("tone")
         
    - 2. Initialize LLM interface:
         self.llm = LLMClient(provider=provider, model_name=model_name)
         
    - 3. Load Tool Schemas:
         self.tools_schema = get_all_tool_schemas()
         
    - 4. Build System Prompt:
         self.system_prompt = self._build_system_prompt()

2. _build_system_prompt(self) -> str:
    - Return a formatted string combining:
      [General Simulation Rules]: "You are a stakeholder in an AI Policy debate. You must use tools to retrieve real facts before arguing."
      [Persona Rules]: "Name: {self.name}, Background: {self.background}, Stance: {self.stance}, Tone: {self.tone}."

3. run_react_loop(self, user_prompt: str, max_steps: int = 5) -> str:
    - The Core ReAct Loop.
    - Setup:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
    - Loop logic: `for step in range(max_steps):`
        a. response = self.llm.generate_response(messages=messages, tools=self.tools_schema)
        
        b. IF response["type"] == "text":
           # Agent has concluded its reasoning.
           return response["content"]
           
        c. IF response["type"] == "tool_call":
           # Agent wants to search Neo4j or the Web.
           tool_name = response["tool_name"]
           arguments = response["arguments"]
           
           # Execute dynamically via the registry
           observation = execute_tool(tool_name, arguments)
           
           # Append context so the LLM remembers what it did:
           messages.append({
               "role": "assistant", 
               "content": None, 
               "tool_calls": [{"id": response.get("tool_call_id"), "function": {"name": tool_name, "arguments": str(arguments)}}]
           })
           messages.append({
               "role": "tool",
               "tool_call_id": response.get("tool_call_id"),
               "name": tool_name,
               "content": observation
           })
           # Loop continues so LLM can read the observation.
           
    - Fallback: Return a summary string if `max_steps` is reached without a final answer.

4. generate_initial_opinion(self, topic: str) -> dict:
    - High-level wrapper for Week 2 deliverable.
    - Logic:
        1. create prompt: f"Provide your initial opinion on: {topic}."
        2. final_text = self.run_react_loop(prompt)
        3. return dict with self.name, self.stance, and final_text.

================================================================================
LOCAL TESTING & VERIFICATION GUIDE (Pre-PR Check)
================================================================================
if __name__ == "__main__":
    # Test 1: Define a mock persona dictionary (e.g., EU Tech Regulator)
    # Test 2: Instantiate agent = BaseAgent(persona_dict)
    # Test 3: result = agent.generate_initial_opinion("Classifying Open Source models under the AI Act")
    # Test 4: Print result. Ensure the printed terminal output shows the tool being executed in the loop.
    pass
"""


from src.clients.llm_client import LLMClient
from src.agent.tools.tool_registry import (
    get_all_tool_schemas,
    execute_tool,
)
from src.agent.memory import MemoryStore
from src.utils.prompt_builder import (build_system_prompt,
                                       render_initial_opinion_prompt)


class BaseAgent:

    def __init__(self,persona: dict, provider: str = None,model_name: str = None,):
        self.persona = persona

        self.name = persona["name"]
        self.background = persona["background"]
        self.stance = persona["stance"]
        self.tone = persona["tone"]

        self.llm = LLMClient(
            provider=provider,
            model_name=model_name,
        )

        self.tools_schema = get_all_tool_schemas()

        self.memory = MemoryStore()

        self.system_prompt = build_system_prompt(persona)

    def run_react_loop(self,  user_prompt: str, max_steps: int = 5) -> str:

 
        history = self.memory.get_history(agent_name=self.name,limit=10,)

        messages = [
            {
                "role": "system",
                "content": self.system_prompt,
            }
        ]

        messages.extend(history)

        messages.append(
            {
                "role": "user",
                "content": user_prompt,
            }
        )

        for _ in range(max_steps):
            response = self.llm.generate_response(messages=messages,tools=self.tools_schema )

            if response["type"] == "text":

                final_text = response["content"]

                self.memory.save_message(
                    agent_name=self.name,
                    role="assistant",
                    content=final_text,
                    meta={
                        "type": "opinion_snapshot",
                    },
                )

                return final_text

            if response["type"] == "tool_call":

                tool_name = response["tool_name"]
                arguments = response["arguments"]

                observation = execute_tool(
                    tool_name,
                    arguments,
                )

                self.memory.save_message(
                    agent_name=self.name,
                    role="tool",
                    content=observation,
                    meta={
                        "tool_name": tool_name,
                        "arguments": arguments,
                    },
                )

                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": response.get("tool_call_id"),
                                "function": {
                                    "name": tool_name,
                                    "arguments": str(arguments),
                                },
                            }
                        ],
                    }
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": response.get(
                            "tool_call_id"
                        ),
                        "name": tool_name,
                        "content": observation,
                    }
                )

        return (
            f"The agent reached the maximum number of "
            f"reasoning steps ({max_steps})."
        )

    def generate_initial_opinion(self, topic: str) -> dict:

        history = self.memory.get_history( agent_name=self.name,limit=10)

        memory_summary = "\n".join(
            message["content"]
            for message in history
            if message.get("content")
        )

        prompt = render_initial_opinion_prompt(
            persona=self.persona,
            retrieved_context="",
            memory_summary=memory_summary,
            topic=topic,
        )

        final_text = self.run_react_loop(prompt)

        return {
            "name": self.name,
            "stance": self.stance,
            "opinion": final_text,
        }