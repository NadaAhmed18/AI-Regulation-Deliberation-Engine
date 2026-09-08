export interface PersonaMemoryConfig {
    type: "sliding_window" | "summary" | "full" | string;
    window_size?: number;
}

export interface Persona {
    name: string;
    background: string;
    stance: string;
    tone: string;
    avatarSeed: string; // Used for unique deterministic avatars
    memory_config?: PersonaMemoryConfig;
}

export interface CFGMetrics {
    guidance_scale_gamma: number;
    shift_magnitude: number;
    guidance_vector: number;
    dynamic: string; // e.g. "Persuaded (28.6%)", "Polarized (Backfire)"
}

export interface OpinionSnapshot {
    current_stance_score: number;
    shift_magnitude: number;
    influencer?: string;
    cfg?: CFGMetrics;
    reasoning?: string;
}

export interface DiscussionTurn {
    id: string;
    round_number: number;
    agent_name: string;
    content: string;
    tools_called?: Array<{ name: string; query?: string }>;
    retrieved_sources?: string[];
    opinion_snapshot: OpinionSnapshot;
    timestamp: string;
}

export interface DebateHistoryItem {
    id: string;
    title: string;
    category: "Today" | "Yesterday" | "6 days ago" | "Month ago" | "Long time ago";
    agentsCount: number;
    roundsCount: number;
}

export interface GraphNodeData {
    id: string;
    name: string;
    avatarUrl: string;
    currentStance: number;
    role?: string;
}

export interface GraphEdgeData {
    source: string;
    target: string;
    weight: number;
    dynamic?: string;
    round?: number;
}

export interface SimulationAnalytics {
    nodes: GraphNodeData[];
    edges: GraphEdgeData[];
    trajectory: Array<Record<string, number | string>>;
    persuasion_signals: Array<{
        id: string;
        source: string;
        target: string;
        shift: number;
        gamma: number;
        dynamic: string;
    }>;
    citations: string[];
}

export interface PredefinedTopic {
    id: string;
    title: string;
    tag: string;
    description: string;
}