from typing import Any, Dict, List, Optional

from src.analytics.metrics.agreement import compute_round_agreement
from src.analytics.metrics.influence import compute_topology_influence
from src.analytics.metrics.network_model import OpinionDynamicsNetwork
from src.analytics.metrics.opinion_change import compute_opinion_trajectories
from src.analytics.common import extract_citations, extract_persuasion_signals

class DiscussionAnalyticsEngine:
    """
    Pure in-memory analytics engine.
    Orchestrates trajectory, agreement, influence, citations, and graph computations.
    """

    def compute_all_metrics(
        self,
        topic: str,
        personas: List[Dict[str, Any]],
        history: List[Dict[str, Any]],
        visibility_matrix: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """Computes and bundles all metrics into the final frontend payload."""
        opinion_change = compute_opinion_trajectories(
            history_rows=history,
            personas=personas,
        )

        agreement = compute_round_agreement(
            history_rows=history,
        )

        influence = compute_topology_influence(
            history_rows=history,
            personas=personas,
            visibility_matrix=visibility_matrix,
        )

        network = OpinionDynamicsNetwork(
            personas=personas,
            opinion_trajectories=opinion_change,
            influence_data=influence,
        )
        network_graph = network.export_graph_data()

        # Format node visuals with avatars for UI
        for idx, node in enumerate(network_graph.get("nodes", [])):
            avatar_num = f"{(idx % 5) + 1:02d}"
            node["avatarUrl"] = f"/avatar/{avatar_num}.png"
            node["currentStance"] = node.get("stance", 0.0)

        persuasion_signals = extract_persuasion_signals(history)
        citations = extract_citations(history)

        return {
            "topic": topic,
            "opinion_change": opinion_change,
            "agreement": agreement,
            "influence": influence,
            "network_graph": network_graph,
            "persuasion_signals": persuasion_signals,
            "citations": citations,
        }