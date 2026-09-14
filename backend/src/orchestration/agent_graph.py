from typing import Dict, List, Literal, Optional
import networkx as nx

TopologyType = Literal["ring", "mesh", "custom"]


class VisibilityGraph:
    """Manages listening permissions and topological connectivity for debate agents."""

    def __init__(
        self,
        agent_names: List[str],
        topology: TopologyType = "ring",
        custom_matrix: Optional[Dict[str, List[str]]] = None,
    ):
        """
        Args:
            agent_names: Ordered list of agent names participating in the debate.
            topology: Preset topology ('ring', 'mesh', or 'custom').
            custom_matrix: Dict mapping {listener: [allowed_speakers_they_can_hear]}.
        """
        # Deduplicate while preserving original order
        self.agent_names: List[str] = list(dict.fromkeys(agent_names))
        self.graph: nx.DiGraph = nx.DiGraph()
        self.graph.add_nodes_from(self.agent_names)

        if custom_matrix is not None:
            self._build_from_custom_matrix(custom_matrix)
        else:
            self._build_preset_topology(topology)

        self.visibility_map: Dict[str, List[str]] = self._sync_visibility_map()

    def _build_preset_topology(self, topology: str) -> None:
        """Constructs graph edges according to standard presets."""
        topo = topology.lower()
        n = len(self.agent_names)
        if n <= 1:
            return

        if topo == "ring":
            # Directed cycle: Speaker i speaks to Listener (i + 1)
            for i in range(n):
                speaker = self.agent_names[i]
                listener = self.agent_names[(i + 1) % n]
                self.graph.add_edge(speaker, listener)

        elif topo == "mesh":
            # Complete graph: Everyone hears everyone except themselves
            for u in self.agent_names:
                for v in self.agent_names:
                    if u != v:
                        self.graph.add_edge(u, v)
        else:
            raise ValueError(
                f"Unsupported topology '{topology}'. Expected 'ring', 'mesh', or pass 'custom_matrix'."
            )

    def _build_from_custom_matrix(self, matrix: Dict[str, List[str]]) -> None:
        """Constructs graph edges from an explicit visibility mapping."""
        valid_agents = set(self.agent_names)
        for listener, speakers in matrix.items():
            if listener not in valid_agents:
                continue
            for speaker in speakers:
                if speaker in valid_agents and speaker != listener:
                    self.graph.add_edge(speaker, listener)

    def _sync_visibility_map(self) -> Dict[str, List[str]]:
        """Extracts {listener: [speakers]} from in-edges (predecessors)."""
        return {
            agent: list(self.graph.predecessors(agent))
            for agent in self.agent_names
        }

    def allow_speaker_for_listener(self, speaker: str, listener: str) -> None:
        """Grants listener visibility to hear speaker."""
        if speaker in self.graph and listener in self.graph and speaker != listener:
            self.graph.add_edge(speaker, listener)
            self.visibility_map = self._sync_visibility_map()

    def hide_speaker_from_listener(self, speaker: str, listener: str) -> None:
        """Revokes listener's visibility to hear speaker."""
        if self.graph.has_edge(speaker, listener):
            self.graph.remove_edge(speaker, listener)
            self.visibility_map = self._sync_visibility_map()

    def get_allowed_speakers_for(self, listener: str) -> List[str]:
        """Returns the list of speakers that 'listener' is allowed to hear."""
        return self.visibility_map.get(listener, [])

    def is_strongly_connected(self) -> bool:
        """Returns True if every agent can reach every other agent through the graph."""
        if len(self.agent_names) <= 1:
            return True
        return nx.is_strongly_connected(self.graph)

    def to_dict(self) -> Dict[str, List[str]]:
        """Exports the visibility matrix in {listener: [speakers]} dictionary format."""
        return self.visibility_map

    @classmethod
    def create_matrix(
        cls,
        agent_names: List[str],
        topology: TopologyType = "ring",
    ) -> Dict[str, List[str]]:
        """Convenience factory method to generate visibility maps in a single line."""
        return cls(agent_names=agent_names, topology=topology).to_dict()