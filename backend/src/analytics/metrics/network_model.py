from typing import Any, Dict, List
import networkx as nx

from src.analytics.common import get_agent_names


class OpinionDynamicsNetwork:
    """
    Constructs a directed graph of agent interaction.
    Nodes store final stance and total net shift.
    Edges store cumulative persuasion weight.
    """

    def __init__(
        self,
        personas: List[Dict[str, Any]],
        opinion_trajectories: Dict[str, List[Dict[str, Any]]],
        influence_data: Dict[str, Any],
    ):
        self.personas = personas
        self.agent_names = get_agent_names(personas)
        self.opinion_trajectories = opinion_trajectories
        self.influence_data = influence_data
        self.graph = nx.DiGraph()

        self._build_graph()

    def _build_graph(self) -> None:
        """Adds agent nodes and directed influence edges to the graph."""
        for persona in self.personas:
            agent_name = persona["name"]
            trajectory = self.opinion_trajectories.get(agent_name, [])

            final_stance = trajectory[-1]["stance"] if trajectory else None
            net_shift = 0.0
            if len(trajectory) >= 2:
                net_shift = round(trajectory[-1]["stance"] - trajectory[0]["stance"], 2)

            self.graph.add_node(
                agent_name,
                stance=final_stance,
                shift=net_shift,
                role=persona.get("background", "Panelist"),
            )

        influence_matrix = self.influence_data.get("matrix", {})
        for source, targets in influence_matrix.items():
            for target, weight in targets.items():
                if source != target and weight > 0:
                    self.graph.add_edge(
                        source,
                        target,
                        weight=round(float(weight), 2),
                    )

    def export_graph_data(self) -> Dict[str, Any]:
        """Exports graph in JSON format expected by frontend visualization components."""
        nodes = [
            {"id": node, **attrs}
            for node, attrs in self.graph.nodes(data=True)
        ]
        edges = [
            {"source": u, "target": v, **attrs}
            for u, v, attrs in self.graph.edges(data=True)
        ]
        return {"nodes": nodes, "edges": edges}

    def get_persuasion_rankings(self) -> List[Dict[str, Any]]:
        """Ranks agents by their cumulative outgoing persuasion weight."""
        rankings = []
        for agent in self.graph.nodes:
            total_influence = sum(
                data.get("weight", 0.0)
                for _, _, data in self.graph.out_edges(agent, data=True)
            )
            rankings.append({
                "agent": agent,
                "influence_score": round(total_influence, 2),
            })

        rankings.sort(key=lambda item: item["influence_score"], reverse=True)
        return rankings