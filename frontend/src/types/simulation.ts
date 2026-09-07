export interface Persona {
    name: string;
    background: string;
    stance: string;
    tone: string;
    avatarSeed: string; // Used for unique deterministic avatars
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