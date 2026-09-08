"""
AGENT VISIBILITY & GRAPH TOPOLOGY

Defines which agents are allowed to listen to each other.
Acts as the communication graph for Week 3.
"""

import networkx as nx
from typing import List, Dict, Optional


class VisibilityGraph:
    def __init__(self, agent_names: List[str], topology: str = "ring", custom_matrix: Optional[Dict[str, List[str]]] = None):
        """
        Args:
            agent_names: List of persona names in the debate.
            topology: 'ring' (A->B->C->A), 'mesh' (all see all), or 'custom'.
            custom_matrix: Dict where key = listener, value = list of agents they can hear.
                           e.g., {"Agent A": ["Agent B"]} -> Agent A only hears Agent B (Agent C is hidden).
        """
        self.agent_names = agent_names
        self.graph = nx.DiGraph()
        
        if custom_matrix:
            self.visibility_map = custom_matrix
            self._build_from_custom_matrix()
        else:
            self.visibility_map = {}
            self._build_preset_topology(topology)

    def _build_preset_topology(self, topology: str):
        n = len(self.agent_names)
        for name in self.agent_names:
            self.graph.add_node(name)

        if topology == "ring":
            # Directed ring: Agent 0 listens to Agent n-1, Agent 1 listens to Agent 0, etc.
            # Speaker -> Listener
            for i in range(n):
                speaker = self.agent_names[i]
                listener = self.agent_names[(i + 1) % n]
                self.graph.add_edge(speaker, listener)

        elif topology == "mesh":
            # Everyone listens to everyone
            for u in self.agent_names:
                for v in self.agent_names:
                    if u != v:
                        self.graph.add_edge(u, v)

        self._sync_visibility_map_from_graph()

    def _build_from_custom_matrix(self):
        for name in self.agent_names:
            self.graph.add_node(name)

        for listener, speakers in self.visibility_map.items():
            for speaker in speakers:
                # Directed edge: speaker -> listener
                self.graph.add_edge(speaker, listener)

    def _sync_visibility_map_from_graph(self):
        """Updates the internal dictionary: {listener: [allowed_speakers]}"""
        self.visibility_map = {
            agent: list(self.graph.predecessors(agent))
            for agent in self.agent_names
        }

    def hide_speaker_from_listener(self, speaker: str, listener: str):
        """Removes visibility: listener will no longer see speaker's messages."""
        if self.graph.has_edge(speaker, listener):
            self.graph.remove_edge(speaker, listener)
            self._sync_visibility_map_from_graph()

    def allow_speaker_for_listener(self, speaker: str, listener: str):
        """Adds visibility: listener will see speaker's messages."""
        self.graph.add_edge(speaker, listener)
        self._sync_visibility_map_from_graph()

    def is_strongly_connected(self) -> bool:
        """
        Acceptance Test check: Returns True if every agent can reach every other agent
        directly or indirectly through the graph.
        """
        if len(self.agent_names) <= 1:
            return True
        return nx.is_strongly_connected(self.graph)

    def get_allowed_speakers_for(self, listener: str) -> List[str]:
        """Returns the list of agent names that 'listener' is allowed to hear."""
        return self.visibility_map.get(listener, [])