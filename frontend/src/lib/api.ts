import axios from "axios";
import {
    Persona,
    DiscussionTurn,
    DebateHistoryItem,
    SimulationAnalytics,
    GraphNodeData,
    GraphEdgeData,
    PredefinedTopic,
} from "@/types/simulation";

// Resolve URL safely: Browser client code only sees NEXT_PUBLIC_* variables
const BACKEND_HOST = process.env.NEXT_PUBLIC_BACKEND_HOST || "localhost";
const BACKEND_PORT = process.env.NEXT_PUBLIC_BACKEND_PORT || "8000";
const BACKEND_URL =
    process.env.NEXT_PUBLIC_API_URL || `http://${BACKEND_HOST}:${BACKEND_PORT}/api`;

const USE_MOCK = false;
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export const getAvatarPath = (index: number): string => {
    const avatarNum = String((index % 5) + 1).padStart(2, "0");
    return `/avatar/${avatarNum}.png`;
};

// ============================================================================
// AXIOS CLIENT CONFIGURATION
// ============================================================================
export const apiClient = axios.create({
    baseURL: BACKEND_URL,
    headers: {
        "Content-Type": "application/json",
    },
    timeout: 45000,
});

/**
 * Standardizes Axios error messages for UI alerts
 */
export const extractErrorMessage = (error: unknown): string => {
    if (axios.isAxiosError(error)) {
        const data = error.response?.data;
        if (data && typeof data === "object") {
            if ("message" in data) return String(data.message);
            if ("detail" in data) return String(data.detail);
        }
        return error.message || "Network error communicating with the debate server.";
    }
    return error instanceof Error ? error.message : "An unexpected error occurred.";
};

// ============================================================================
// MOCK REPOSITORIES (FALLBACK)
// ============================================================================
const PREDEFINED_TOPICS: PredefinedTopic[] = [
    {
        id: "topic-1",
        title: "Should governments mandate hardware-level kill-switches for frontier open-source AI?",
        tag: "Frontier Security",
        description: "Focuses on dual-use weight proliferation, foundry locks, and existential risk prevention.",
    },
    {
        id: "topic-2",
        title: "EU AI Act Article 51: Should training clusters >10^26 FLOPs face strict third-party audit vetoes?",
        tag: "Regulatory Compliance",
        description: "Balancing European single-market innovation with systemic catastrophe mitigation.",
    },
    {
        id: "topic-3",
        title: "Should AI developers be held strictly liable for copyright infringement in pre-training data scraping?",
        tag: "IP & Synthetic Data",
        description: "Fair use doctrines vs fair compensation for human creators in the age of generative models.",
    },
    {
        id: "topic-4",
        title: "Autonomous algorithmic trading agents: Mandate simulated sandbox isolation before exchange deployment?",
        tag: "Financial Stability",
        description: "Flash crash prevention, collusion between emergent LLM agents, and regulatory kill-circuits.",
    },
];

let MOCK_HISTORY: DebateHistoryItem[] = [
    { id: "sim-1", title: "Mandatory Kill-Switches for Frontier AI Models", category: "Today", agentsCount: 3, roundsCount: 3 },
    { id: "sim-2", title: "EU AI Act Systemic Risk Article 51 Enforcement", category: "Yesterday", agentsCount: 4, roundsCount: 4 },
    { id: "sim-3", title: "Copyright Liability on Synthetic Pre-training Data", category: "6 days ago", agentsCount: 3, roundsCount: 3 },
];

const MOCK_PERSONAS_POOL: Persona[] = [
    {
        name: "Dr. Aris Thorne",
        background: "Former Frontier Lab Alignment Lead, independent safety auditor.",
        stance: "Mandatory compute verification is non-negotiable.",
        tone: "Urgent, analytical, assertive",
        avatarSeed: "Thorne",
        memory_config: { type: "sliding_window", window_size: 4 },
    },
    {
        name: "Sarah Chen",
        background: "Open-Source AI Advocate and Decentralized Research Chair.",
        stance: "Decentralized weights ensure algorithmic resilience and prevent monopolies.",
        tone: "Passionate, evidence-driven, pragmatic",
        avatarSeed: "Sarah",
        memory_config: { type: "sliding_window", window_size: 4 },
    },
    {
        name: "Marcus Vance",
        background: "Senior Legal Counsel for Global Tech Governance & EU AI Act.",
        stance: "Proportional, tiered oversight balances safety and innovation.",
        tone: "Diplomatic, procedural, balanced",
        avatarSeed: "Marcus",
        memory_config: { type: "summary", window_size: 4 },
    },
];

let dynamicTurnsQueue: DiscussionTurn[] = [];
let mockTurnIndex = 0;

// ============================================================================
// API SERVICE METHODS
// ============================================================================
export interface HealthCheckResponse {
    status: "healthy" | "degraded" | "unhealthy";
    neo4j: boolean;
    postgres: boolean;
    message?: string;
}

export const SimulationAPI = {
    async checkHealth(): Promise<HealthCheckResponse> {
        if (USE_MOCK) {
            await delay(50);
            return { status: "healthy", neo4j: true, postgres: true, message: "Mock Mode" };
        }
        try {
            const response = await apiClient.get("/health");
            const payload = response.data?.data || response.data;
            return {
                status: payload.status || "healthy",
                neo4j: Boolean(payload.neo4j),
                postgres: Boolean(payload.postgres),
                message: payload.message,
            };
        } catch (error) {
            return {
                status: "unhealthy",
                neo4j: false,
                postgres: false,
                message: extractErrorMessage(error),
            };
        }
    },

    async getPredefinedTopics(): Promise<PredefinedTopic[]> {
        if (USE_MOCK) {
            await delay(80);
            return PREDEFINED_TOPICS;
        }
        const response = await apiClient.get<{ success?: boolean; data?: PredefinedTopic[] } | PredefinedTopic[]>("/topics/predefined");
        const data = response.data;
        if (Array.isArray(data)) return data;
        if (data && "data" in data && Array.isArray(data.data)) return data.data;
        return PREDEFINED_TOPICS;
    },

    async getInitialHistory(): Promise<DebateHistoryItem[]> {
        if (USE_MOCK) {
            await delay(80);
            return [...MOCK_HISTORY];
        }
        const response = await apiClient.get<{ success?: boolean; data?: DebateHistoryItem[] } | DebateHistoryItem[]>("/simulations/history-list");
        const data = response.data;
        if (Array.isArray(data)) return data;
        if (data && "data" in data && Array.isArray(data.data)) return data.data;
        return [];
    },

    async deleteHistoryItem(id: string): Promise<boolean> {
        if (USE_MOCK) {
            await delay(60);
            MOCK_HISTORY = MOCK_HISTORY.filter((item) => item.id !== id);
            return true;
        }
        await apiClient.delete(`/simulations/${encodeURIComponent(id)}`);
        return true;
    },

    async generatePersonas(
        topic: string,
        numAgents: number = 3,
        customPrompt?: string,
        defaultMemoryType: "sliding_window" | "summary" | "full" = "sliding_window"
    ): Promise<Persona[]> {
        const clampedCount = Math.max(2, Math.min(numAgents, 6));

        if (USE_MOCK) {
            await delay(400);
            return MOCK_PERSONAS_POOL.slice(0, clampedCount).map((p) => ({
                ...p,
                memory_config: { type: defaultMemoryType, window_size: 4 },
            }));
        }

        const response = await apiClient.post<{ success?: boolean; data?: Persona[] } | Persona[]>("/personas/generate", {
            topic,
            num_agents: clampedCount,
            custom_prompt: customPrompt || "",
            default_memory_type: defaultMemoryType,
        });

        const data = response.data;
        if (Array.isArray(data)) return data;
        if (data && "data" in data && Array.isArray(data.data)) return data.data;
        return [];
    },

    async startSimulation(
        topic: string,
        personas: Persona[],
        memoryStrategy = { type: "sliding_window", window_size: 4 },
        visibilityMatrix?: Record<string, string[]>
    ): Promise<{ simulation_id: string }> {
        if (personas.length < 2) {
            throw new Error("A debate requires at least 2 stakeholder personas.");
        }

        if (USE_MOCK) {
            await delay(400);
            dynamicTurnsQueue = [];
            mockTurnIndex = 0;
            return { simulation_id: `sim_${Date.now()}` };
        }

        const response = await apiClient.post<{ simulation_id?: string; data?: { simulation_id: string } }>("/simulations/start", {
            topic,
            personas,
            memory_strategy: memoryStrategy,
            visibility_matrix: visibilityMatrix,
        });

        const simId = response.data.simulation_id || response.data.data?.simulation_id;
        if (!simId) throw new Error("Backend did not return a valid simulation_id.");
        return { simulation_id: simId };
    },

    async nextTurn(simulationId: string): Promise<DiscussionTurn | null> {
        if (!simulationId || !simulationId.trim()) return null;

        if (USE_MOCK) {
            await delay(1000);
            if (mockTurnIndex >= dynamicTurnsQueue.length) return null;
            const turn = dynamicTurnsQueue[mockTurnIndex];
            mockTurnIndex++;
            return turn;
        }

        try {
            const response = await apiClient.post<{ data?: DiscussionTurn } | DiscussionTurn>(
                `/simulations/${encodeURIComponent(simulationId)}/next-turn`
            );
            const data = response.data;
            if (data && "id" in data) return data as DiscussionTurn;
            if (data && "data" in data && data.data) return data.data;
            return null;
        } catch (error) {
            if (axios.isAxiosError(error) && error.response?.status === 404) {
                return null; // Discussion ended or round reached max
            }
            throw error;
        }
    },

    async continueSimulation(
        simulationId: string,
        interventionPrompt?: string,
        steps: number = 1
    ): Promise<{ success: boolean; newTurnsCount: number }> {
        if (!simulationId || !simulationId.trim()) {
            throw new Error("No active simulation to continue.");
        }

        if (USE_MOCK) {
            await delay(600);
            return { success: true, newTurnsCount: steps };
        }

        const response = await apiClient.post<{ success: boolean; newTurnsCount: number }>(
            `/simulations/${encodeURIComponent(simulationId)}/continue`,
            {
                intervention: interventionPrompt || null,
                steps,
            }
        );
        return response.data;
    },

    async getAnalytics(
        simulationId?: string,
        currentPersonas: Persona[] = [],
        currentTurns: DiscussionTurn[] = []
    ): Promise<SimulationAnalytics> {
        // Prevent fetching if no simulationId exists yet; generate local initial snapshot
        if (!simulationId || !simulationId.trim() || USE_MOCK) {
            const personas = currentPersonas.length > 0 ? currentPersonas : MOCK_PERSONAS_POOL.slice(0, 3);
            const turns = currentTurns;

            const nodes: GraphNodeData[] = personas.map((p, idx) => {
                const latestTurn = [...turns].reverse().find((t) => t.agent_name === p.name);
                return {
                    id: `agent-${idx}`,
                    name: p.name,
                    avatarUrl: getAvatarPath(idx),
                    currentStance: latestTurn?.opinion_snapshot.current_stance_score ?? 0,
                    role: p.background,
                };
            });

            const edges: GraphEdgeData[] = [];
            turns.forEach((turn) => {
                const influencer = turn.opinion_snapshot.influencer;
                if (influencer && influencer !== turn.agent_name) {
                    const weight = Math.abs(turn.opinion_snapshot.shift_magnitude || 0.5);
                    edges.push({
                        source: influencer,
                        target: turn.agent_name,
                        weight: Number(weight.toFixed(2)),
                        dynamic: turn.opinion_snapshot.cfg?.dynamic,
                        round: turn.round_number,
                    });
                }
            });

            const roundsMap: Record<number, Record<string, number | string>> = {};
            turns.forEach((turn) => {
                const r = turn.round_number;
                if (!roundsMap[r]) roundsMap[r] = { round: `R${r}` };
                roundsMap[r][turn.agent_name] = turn.opinion_snapshot.current_stance_score;
            });

            return {
                nodes,
                edges,
                trajectory: Object.values(roundsMap),
                persuasion_signals: turns
                    .filter((t) => t.opinion_snapshot.influencer)
                    .map((t) => ({
                        id: t.id,
                        source: t.opinion_snapshot.influencer!,
                        target: t.agent_name,
                        shift: t.opinion_snapshot.shift_magnitude,
                        gamma: t.opinion_snapshot.cfg?.guidance_scale_gamma ?? 0,
                        dynamic: t.opinion_snapshot.cfg?.dynamic ?? "Shift",
                    })),
                citations: Array.from(new Set(turns.flatMap((t) => t.retrieved_sources || []).filter(Boolean))),
            };
        }

        const response = await apiClient.get<{ data?: SimulationAnalytics } | SimulationAnalytics>(
            `/simulations/${encodeURIComponent(simulationId)}/analytics`
        );
        const data = response.data;
        if ("nodes" in data) return data;
        if (data && "data" in data && data.data) return data.data;
        throw new Error("Failed to parse analytics payload");
    },
};