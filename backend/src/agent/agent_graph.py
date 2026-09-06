import json
import random
from pathlib import Path
from typing import List, Optional
from src.config import DEFAULT_EXTRA_EDGE_PROBABILITY, DEFAULT_SEED
import networkx as nx



def build_agent_graph(
    agent_names: List[str],
    extra_edge_probability: float = DEFAULT_EXTRA_EDGE_PROBABILITY,
    seed: int = DEFAULT_SEED,
) -> nx.DiGraph:

    if len(agent_names) < 2:
        raise ValueError(
            f"Need at least 2 agents to build a graph, got {len(agent_names)}."
        )

    rng = random.Random(seed)
    graph = nx.DiGraph()
    graph.add_nodes_from(agent_names)

    n = len(agent_names)
    for i in range(n):
        source = agent_names[i]
        target = agent_names[(i + 1) % n]
        graph.add_edge(source, target, kind="base_cycle")

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            source, target = agent_names[i], agent_names[j]
            if graph.has_edge(source, target):
                continue  # already part of the base cycle
            if rng.random() < extra_edge_probability:
                graph.add_edge(source, target, kind="enrichment")

    return graph


def is_strongly_connected(graph: nx.DiGraph) -> bool:

    if graph.number_of_nodes() == 0:
        return False
    return nx.is_strongly_connected(graph)


def get_neighbors(graph: nx.DiGraph, agent_name: str) -> List[str]:
    if agent_name not in graph:
        return []
    return list(graph.successors(agent_name))


def save_graph_config(graph: nx.DiGraph, path: str = "docs/graph_config.json") -> None:

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    config = {
        "nodes": list(graph.nodes()),
        "edges": [
            {"source": u, "target": v, "kind": data.get("kind", "unknown")}
            for u, v, data in graph.edges(data=True)
        ],
        "strongly_connected": is_strongly_connected(graph),
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"[Agent Graph] 💾 Saved graph config to: {out_path}")


def load_graph_config(path: str = "docs/graph_config.json") -> nx.DiGraph:
  
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    graph = nx.DiGraph()
    graph.add_nodes_from(config["nodes"])
    for edge in config["edges"]:
        graph.add_edge(edge["source"], edge["target"], kind=edge["kind"])

    return graph



if __name__ == "__main__":
    agent_names = ["Persona_A", "Persona_B"]

    graph = build_agent_graph(agent_names)

    print(f"Nodes: {list(graph.nodes())}")
    print(f"Edges: {list(graph.edges())}")
    print(f"Strongly connected: {is_strongly_connected(graph)}")

    for name in agent_names:
        print(f"  {name} can reach: {get_neighbors(graph, name)}")

    save_graph_config(graph)

    reloaded = load_graph_config()
    print(f"Reloaded graph strongly connected: {is_strongly_connected(reloaded)}")