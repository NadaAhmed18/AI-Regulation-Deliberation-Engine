from typing import Dict
import networkx as nx

def get_visible_messages(graph: nx.DiGraph,agent_name: str, 
                         round_messages: Dict[str, str]) -> Dict[str, str]:
 
    if agent_name not in graph:
        return {}

    allowed_senders = set(graph.predecessors(agent_name))
    return {
        sender: msg
        for sender, msg in round_messages.items()
        if sender in allowed_senders
    }


if __name__ == "__main__":
    from src.agent.agent_graph import build_agent_graph
    g = build_agent_graph(["A", "B", "C"])
    print("Edges:", list(g.edges()))
    fake_round = {"A": "msg from A", "B": "msg from B", "C": "msg from C"}
    for name in ["A", "B", "C"]:
        print(f"{name} sees:", get_visible_messages(g, name, fake_round))