from typing import Any, Dict, List

import networkx as nx


class OpinionDynamicsNetwork:
    """
    Builds a directed graph representing opinion dynamics.

    Nodes represent agents.
    Edges represent detected influence between agents.
    """

    def __init__(
        self,
        personas: List[Dict[str, Any]],
        opinion_trajectories: Dict[str, List[Dict[str, Any]]],
        influence_data: Dict[str, Any],
    ):
        self.personas = personas
        self.opinion_trajectories = opinion_trajectories
        self.influence_data = influence_data

        self.graph = nx.DiGraph()

        self._build_graph()

    def _build_graph(self) -> None:
        """Build agent nodes and directed influence edges."""

        for persona in self.personas:
            agent_name = persona["name"]

            trajectory = self.opinion_trajectories.get(agent_name, [])

            final_stance = (
                trajectory[-1]["stance"]
                if trajectory
                else None
            )

            net_shift = 0.0

            if len(trajectory) >= 2:
                net_shift = round(
                    trajectory[-1]["stance"]
                    - trajectory[0]["stance"],
                    2,
                )

            self.graph.add_node(
                agent_name,
                stance=final_stance,
                shift=net_shift,
            )

        influence_matrix = self.influence_data.get("matrix", {})

        for source, targets in influence_matrix.items():
            for target, weight in targets.items():

                if source == target:
                    continue

                if weight > 0:
                    self.graph.add_edge(
                        source,
                        target,
                        weight=round(float(weight), 2),
                    )

    def export_graph_data(self) -> Dict[str, Any]:
        """
        Export graph in JSON-friendly format for the frontend.
        """

        nodes = []

        for node_name, attributes in self.graph.nodes(data=True):
            nodes.append(
                {
                    "id": node_name,
                    **attributes,
                }
            )

        edges = []

        for source, target, attributes in self.graph.edges(data=True):
            edges.append(
                {
                    "source": source,
                    "target": target,
                    **attributes,
                }
            )

        return {
            "nodes": nodes,
            "edges": edges,
        }

    def get_persuasion_rankings(self) -> List[Dict[str, Any]]:
        """
        Rank agents by total outgoing influence.
        """

        rankings = []

        for agent_name in self.graph.nodes:
            total_influence = sum(
                data.get("weight", 0.0)
                for _, _, data in self.graph.out_edges(
                    agent_name,
                    data=True,
                )
            )

            rankings.append(
                {
                    "agent": agent_name,
                    "influence_score": round(
                        total_influence,
                        2,
                    ),
                }
            )

        rankings.sort(
            key=lambda item: item["influence_score"],
            reverse=True,
        )

        return rankings