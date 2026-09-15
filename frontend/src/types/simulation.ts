export interface PersonaMemoryConfig {
    type: "sliding_window" | "summary" | "full" | string;
    window_size?: number;
}

export interface Persona {
    name: string;
    background: string;
    stance: string;
    tone: string;
    avatarSeed: string;
    memory_config?: PersonaMemoryConfig;
}

export interface CFGMetrics {
    guidance_scale_gamma: number;
    shift_magnitude: number;
    guidance_vector?: number;
    dynamic: string;
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
    tools_called?: Array<{ name: string; query?: string; result_preview?: string }>;
    retrieved_sources?: string[];
    opinion_snapshot: OpinionSnapshot;
    timestamp?: string;
}

export interface DebateHistoryItem {
    id: string;
    title: string;
    topic?: string;
    category: "Today" | "Yesterday" | "6 days ago" | "Month ago" | "Long time ago" | string;
    agentsCount: number;
    roundsCount: number;
    turn_count?: number;
    status?: string;
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

export interface RoundAgreement {
    round: number;
    agreement_score: number;
    classification: "High Consensus" | "Moderate Alignment" | "Significant Polarization" | "Extreme Polarization" | string;
}

export interface TopologyInfluence {
    status: string;
    matrix: Record<string, Record<string, number>>;
    scores: Record<string, number>;
    top_influencer: string | null;
}

export interface SimulationAnalytics {
    nodes: GraphNodeData[];
    edges: GraphEdgeData[];
    trajectory: Array<Record<string, number | string>>;
    agreement?: RoundAgreement[];
    influence?: TopologyInfluence;
    persuasion_signals: Array<{
        id: string;
        source: string;
        target: string;
        shift: number;
        gamma: number;
        dynamic: string;
        reasoning?: string;
    }>;
    citations: string[];
    is_replay?: boolean;
    current_round?: number | null;
}

export interface PredefinedTopic {
    id: string;
    title: string;
    tag: string;
    description: string;
}

export interface SimulationDetail {
    simulation_id: string;
    topic: string;
    status: string;
    memory_strategy: PersonaMemoryConfig;
    personas: Persona[];
    visibility_matrix?: Record<string, string[]>;
    created_at?: string;
    turns: DiscussionTurn[];
    analytics: SimulationAnalytics;
}

// Live Streaming SSE Event Types
export interface LiveStreamState {
    speaker: string;
    round: number;
    avatarSeed?: string;
    thinking: string;
    tokens: string;
    toolCall?: {
        name: string;
        arguments?: unknown;
        observation?: string;
        status: "running" | "done";
    };
}