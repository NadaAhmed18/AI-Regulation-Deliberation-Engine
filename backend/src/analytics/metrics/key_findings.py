"""
Topic-Anchored Semantic Accumulator (TASA)

Extracts persistent, low-variance Key Findings and distinct policy sub-topics
using online vector clustering and one-time micro-LLM distillation.
"""

import hashlib
import logging
from typing import Any, Dict, List, Optional, Set
import numpy as np

from src.clients.llm_client import LLMClient
from src.config import EMBEDDING_MODEL
from src.utils.embedder import Embedder
from src.utils.prompt_builder import render_prompt

logger = logging.getLogger(__name__)

# Global in-memory cache to guarantee the LLM is NEVER called twice for the same cluster
_DISTILLED_STATEMENTS_CACHE: Dict[str, str] = {}

# Global vector cache so we NEVER re-embed already processed turn content
_EMBEDDING_CACHE: Dict[str, np.ndarray] = {}

# Global singletons
_EMBEDDER_INSTANCE: Optional[Embedder] = None
_LLM_INSTANCE: Optional[LLMClient] = None


def _get_embedder() -> Embedder:
    global _EMBEDDER_INSTANCE
    if _EMBEDDER_INSTANCE is None:
        _EMBEDDER_INSTANCE = Embedder(model_name=EMBEDDING_MODEL)
    return _EMBEDDER_INSTANCE


def _get_llm() -> LLMClient:
    global _LLM_INSTANCE
    if _LLM_INSTANCE is None:
        _LLM_INSTANCE = LLMClient()
    return _LLM_INSTANCE


class KeyFindingCluster:
    def __init__(
        self,
        cluster_id: str,
        topic: str,
        initial_vector: np.ndarray,
        first_snippet: str,
        agent_name: str,
        round_num: int,
        stance: float,
    ):
        self.id = cluster_id
        self.topic = topic
        self.centroid: np.ndarray = initial_vector / (np.linalg.norm(initial_vector) + 1e-9)
        self.snippets: List[str] = [first_snippet]
        self.heat: int = 1
        self.first_round: int = round_num
        self.last_round: int = round_num
        self.supporting_agents: Set[str] = set()
        self.opposing_agents: Set[str] = set()
        self.canonical_statement: Optional[str] = None
        self.is_confirmed: bool = False

        self._record_agent_stance(agent_name, stance)

    def _record_agent_stance(self, agent_name: str, stance: float):
        if stance >= 0.2:
            self.supporting_agents.add(agent_name)
            self.opposing_agents.discard(agent_name)
        elif stance <= -0.2:
            self.opposing_agents.add(agent_name)
            self.supporting_agents.discard(agent_name)

    def add_turn(self, vector: np.ndarray, snippet: str, agent_name: str, round_num: int, stance: float):
        norm_v = vector / (np.linalg.norm(vector) + 1e-9)
        
        # DAMPED CENTROID UPDATE:
        # Cap the effective weight to 4. This prevents the centroid from becoming a "black hole"
        # that averages out over 15 turns and swallows all unrelated sub-topics.
        effective_weight = min(self.heat, 4)
        self.centroid = (self.centroid * effective_weight + norm_v) / (effective_weight + 1)
        self.centroid = self.centroid / (np.linalg.norm(self.centroid) + 1e-9)

        if len(self.snippets) < 6:
            self.snippets.append(snippet)

        self.heat += 1
        self.last_round = max(self.last_round, round_num)
        self._record_agent_stance(agent_name, stance)

    def distill_summary(self, llm_client: LLMClient) -> None:
        """Synthesizes arguments into an 8 to 14 word thematic policy finding."""
        # Use first and latest snippets to capture progression
        selected_snippets = self.snippets[:2] + self.snippets[-2:] if len(self.snippets) > 3 else self.snippets
        cache_key = hashlib.md5(" ".join(selected_snippets).encode()).hexdigest()

        if cache_key in _DISTILLED_STATEMENTS_CACHE:
            self.canonical_statement = _DISTILLED_STATEMENTS_CACHE[cache_key]
            self.is_confirmed = True
            return

        formatted = "\n".join(f"- {s[:280]}..." for s in selected_snippets)
        try:
            prompt = render_prompt("key_finding_distiller", topic=self.topic, snippets=formatted)
        except Exception:
            prompt = (
                f"Topic: '{self.topic}'\n"
                f"Arguments:\n{formatted}\n\n"
                "Synthesize the overarching thematic contention in 8 to 14 words. "
                "Return ONLY the distilled finding string."
            )

        try:
            res = llm_client.generate_response(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            distilled = res.get("content", "").strip().strip('"').strip("'")
            if not distilled or len(distilled.split()) < 4:
                distilled = self.snippets[0][:90] + "..."
        except Exception as e:
            logger.warning(f"Error distilling cluster: {e}")
            distilled = self.snippets[0][:90] + "..."

        _DISTILLED_STATEMENTS_CACHE[cache_key] = distilled
        self.canonical_statement = distilled
        self.is_confirmed = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "statement": self.canonical_statement or (self.snippets[0][:90] + "..."),
            "heat": self.heat,
            "status": "confirmed" if self.is_confirmed else "candidate",
            "supporting_agents": sorted(list(self.supporting_agents)),
            "opposing_agents": sorted(list(self.opposing_agents)),
            "first_round": self.first_round,
            "last_round": self.last_round,
        }


def extract_key_findings(
    topic: str,
    history_rows: List[Dict[str, Any]],
    similarity_threshold: float = 0.80, 
    heat_threshold: int = 2,
) -> List[Dict[str, Any]]:
    """Extracts diverse, stable key findings across debate rounds."""
    if not history_rows:
        return []

    embedder = _get_embedder()
    llm = _get_llm()
    clusters: List[KeyFindingCluster] = []

    sorted_turns = sorted(history_rows, key=lambda t: (t.get("round_number", 1), t.get("id", 0)))

    for turn in sorted_turns:
        content = (turn.get("content") or "").strip()
        if len(content.split()) < 12:
            continue

        agent_name = turn.get("agent_name", "Unknown")
        round_num = turn.get("round_number", 1)
        snapshot = turn.get("opinion_snapshot") or {}
        if isinstance(snapshot, str):
            import json
            try:
                snapshot = json.loads(snapshot)
            except Exception:
                snapshot = {}

        try:
            stance = float(snapshot.get("current_stance_score", 0.0))
        except (ValueError, TypeError):
            stance = 0.0

        content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
        if content_hash in _EMBEDDING_CACHE:
            vector = _EMBEDDING_CACHE[content_hash]
        else:
            try:
                vector = embedder.embed([content], is_query=True)[0]
                _EMBEDDING_CACHE[content_hash] = vector
            except Exception as e:
                logger.error(f"Vector embedding failed: {e}")
                continue

        norm_v = vector / (np.linalg.norm(vector) + 1e-9)

        best_cluster: Optional[KeyFindingCluster] = None
        best_sim: float = -1.0

        for c in clusters:
            sim = float(np.dot(c.centroid, norm_v))
            if sim > best_sim:
                best_sim = sim
                best_cluster = c

        # Only merge if similarity is exceptionally high (distinct sub-arguments)
        if best_cluster and best_sim >= similarity_threshold:
            best_cluster.add_turn(
                vector=vector,
                snippet=content,
                agent_name=agent_name,
                round_num=round_num,
                stance=stance,
            )
        else:
            new_id = f"kf_{content_hash[:8]}"
            new_cluster = KeyFindingCluster(
                cluster_id=new_id,
                topic=topic,
                initial_vector=vector,
                first_snippet=content,
                agent_name=agent_name,
                round_num=round_num,
                stance=stance,
            )
            clusters.append(new_cluster)

    # Distill after all debate turns are mapped
    confirmed_clusters: List[KeyFindingCluster] = [c for c in clusters if c.heat >= heat_threshold]

    for c in confirmed_clusters:
        if not c.canonical_statement:
            c.distill_summary(llm)

    confirmed_dicts = [c.to_dict() for c in confirmed_clusters if c.is_confirmed]
    confirmed_dicts.sort(key=lambda k: k["heat"], reverse=True)
    return confirmed_dicts