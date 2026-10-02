"""
DISCUSSION ANALYTICS ENGINE

Central aggregation hub that calculates all quantitative metrics:
1. Opinion drift trajectories across rounds.
2. Round-by-round consensus dynamics.
3. Directional pairwise topological agreement [0.0, 1.0].
4. Topological influence matrix with recency decay.
5. NetworkX interaction graph (nodes & directed persuasion edges).
6. Persuasion step signals & citations.
7. Topic-Anchored Semantic Accumulator (TASA) for stable key findings.
"""

from typing import Any, Dict, List, Optional

from src.analytics.metrics.agreement import (
    compute_round_agreement,
    compute_pairwise_topological_agreement,
)
from src.analytics.metrics.influence import compute_topology_influence
from src.analytics.metrics.network_model import OpinionDynamicsNetwork
from src.analytics.metrics.opinion_change import compute_opinion_trajectories
from src.analytics.metrics.key_findings import extract_key_findings
from src.analytics.common import extract_citations, extract_persuasion_signals


class DiscussionAnalyticsEngine:
    """
    Pure in-memory analytics engine.
    Orchestrates trajectory, agreement, influence, citations, key findings, and graph computations.
    """

    def compute_all_metrics(
        self,
        topic: str,
        personas: List[Dict[str, Any]],
        history: List[Dict[str, Any]],
        visibility_matrix: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """Computes and bundles all metrics into the final frontend payload."""

        # 1. Opinion trajectories across rounds per agent
        opinion_change = compute_opinion_trajectories(
            history_rows=history,
            personas=personas,
        )

        # 2. Global round-by-round consensus trajectory (for area chart)
        agreement_trajectory = compute_round_agreement(
            history_rows=history,
        )

        # 3. Pairwise visibility-constrained agreement & normalized distance
        topological_agreement = compute_pairwise_topological_agreement(
            history_rows=history,
            personas=personas,
            visibility_matrix=visibility_matrix,
        )

        # 4. Directed influence matrix (multi-speaker lookback + recency decay)
        influence = compute_topology_influence(
            history_rows=history,
            personas=personas,
            visibility_matrix=visibility_matrix,
            min_turns=2,
            recency_decay=0.85,
        )

        # 5. NetworkX topological interaction graph
        network = OpinionDynamicsNetwork(
            personas=personas,
            opinion_trajectories=opinion_change,
            influence_data=influence,
        )
        network_graph = network.export_graph_data()

        # Format node visuals with avatars and stances for UI
        for idx, node in enumerate(network_graph.get("nodes", [])):
            avatar_num = f"{(idx % 5) + 1:02d}"
            node["avatarUrl"] = f"/avatar/{avatar_num}.png"
            node["currentStance"] = node.get("stance", 0.0)

        # 6. Discrete turn-by-turn signals and citations
        persuasion_signals = extract_persuasion_signals(history)
        citations = extract_citations(history)

        # 7. Topic-Anchored Semantic Accumulator (TASA) for Key Findings
        key_findings = extract_key_findings(
            topic=topic,
            history_rows=history,
            similarity_threshold=0.8,
            heat_threshold=3,
        )

        return {
            "topic": topic,
            "opinion_change": opinion_change,
            "agreement": agreement_trajectory,
            "topological_agreement": topological_agreement,
            "influence": influence,
            "network_graph": network_graph,
            "persuasion_signals": persuasion_signals,
            "citations": citations,
            "key_findings": key_findings,
        }