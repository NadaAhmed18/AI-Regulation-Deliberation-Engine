import axios from "axios";
import {
    Persona,
    DiscussionTurn,
    DebateHistoryItem,
    SimulationAnalytics,
    PredefinedTopic,
    SimulationDetail,
} from "@/types/simulation";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "/api";

export const getAvatarPath = (index: number): string => {
    const avatarNum = String((index % 5) + 1).padStart(2, "0");
    return `/avatar/${avatarNum}.png`;
};

export const apiClient = axios.create({
    baseURL: BACKEND_URL,
    headers: { "Content-Type": "application/json" },
    // Increased to 90s: Frontier LLM reasoning + RAG tool searches can exceed 45s
    timeout: 90000,
});

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

export interface HealthCheckResponse {
    status: "healthy" | "degraded" | "unhealthy";
    neo4j: boolean;
    postgres: boolean;
    message?: string;
}

export const SimulationAPI = {
    async checkHealth(): Promise<HealthCheckResponse> {
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
        const response = await apiClient.get<{ data?: PredefinedTopic[] } | PredefinedTopic[]>("/topics/predefined");
        const data = response.data;
        if (Array.isArray(data)) return data;
        if (data && "data" in data && Array.isArray(data.data)) return data.data;
        return [];
    },

    async getInitialHistory(): Promise<DebateHistoryItem[]> {
        const response = await apiClient.get<{ data?: DebateHistoryItem[] } | DebateHistoryItem[]>("/simulations/history-list");
        const data = response.data;
        if (Array.isArray(data)) return data;
        if (data && "data" in data && Array.isArray(data.data)) return data.data;
        return [];
    },

    async getSimulation(id: string): Promise<SimulationDetail> {
        const response = await apiClient.get<{ data?: SimulationDetail } | SimulationDetail>(
            `/simulations/${encodeURIComponent(id)}`
        );
        const data = response.data;
        return ("data" in data && data.data ? data.data : data) as SimulationDetail;
    },

    async deleteHistoryItem(id: string): Promise<boolean> {
        await apiClient.delete(`/simulations/${encodeURIComponent(id)}`);
        return true;
    },

    async generatePersonas(
        topic: string,
        numAgents: number = 3,
        customPrompt?: string,
        defaultMemoryType: "sliding_window" | "summary" | "full" = "sliding_window"
    ): Promise<Persona[]> {
        const clampedCount = Math.max(2, Math.min(numAgents, 5));
        const response = await apiClient.post<{ data?: Persona[] } | Persona[]>("/personas/generate", {
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
        const response = await apiClient.post<{ simulation_id?: string; data?: { simulation_id: string } }>(
            "/simulations/start",
            {
                topic,
                personas,
                memory_strategy: memoryStrategy,
                visibility_matrix: visibilityMatrix,
            }
        );
        const simId = response.data.simulation_id || response.data.data?.simulation_id;
        if (!simId) throw new Error("Backend did not return a valid simulation_id.");
        return { simulation_id: simId };
    },

    async nextTurn(simulationId: string): Promise<{ turn: DiscussionTurn; analytics: SimulationAnalytics } | null> {
        if (!simulationId?.trim()) return null;
        try {
            const response = await apiClient.post(`/simulations/${encodeURIComponent(simulationId)}/next-turn`);
            return response.data?.data || response.data;
        } catch (error) {
            if (axios.isAxiosError(error) && error.response?.status === 404) return null;
            throw error;
        }
    },

    async getAnalytics(simulationId?: string, roundNumber?: number): Promise<SimulationAnalytics> {
        if (!simulationId?.trim()) {
            return {
                nodes: [],
                edges: [],
                trajectory: [],
                agreement: [],
                topological_agreement: {
                    matrix: {},
                    agent_scores: {},
                    network_agreement: 1.0,
                },
                persuasion_signals: [],
                citations: [],
                key_findings: [],
            };
        }
        const params = roundNumber !== undefined ? { round_number: roundNumber } : {};
        const response = await apiClient.get(`/simulations/${encodeURIComponent(simulationId)}/analytics`, { params });
        const data = response.data;
        return ("data" in data && data.data ? data.data : data) as SimulationAnalytics;
    },

    /**
     * SSE Stream Consumer for live turn execution
     * Hardened with anti-buffering headers and cross-platform line-break handling.
     */
    streamTurn(
        simulationId: string,
        callbacks: {
            onSpeakerSelected?: (data: { speaker: string; round: number; avatarSeed?: string }) => void;
            onThinking?: (token: string) => void;
            onToken?: (token: string) => void;
            onToolStart?: (tool: { name: string; arguments: unknown }) => void;
            onToolEnd?: (result: { name: string; observation: string }) => void;
            onComplete?: (data: { turn: DiscussionTurn; analytics: SimulationAnalytics }) => void;
            onError?: (err: string) => void;
        },
        intervention?: string
    ): () => void {
        const controller = new AbortController();
        const queryParams = intervention ? `?intervention=${encodeURIComponent(intervention)}` : "";
        const basePath = BACKEND_URL.endsWith("/") ? BACKEND_URL.slice(0, -1) : BACKEND_URL;
        const url = `${basePath}/simulations/${encodeURIComponent(simulationId)}/stream-turn${queryParams}`;

        (async () => {
            try {
                const response = await fetch(url, {
                    // CRITICAL: POST bypasses Cloudflare Quick Tunnel's edge buffer
                    method: "POST",
                    signal: controller.signal,
                    headers: {
                        "Accept": "text/event-stream",
                        "Cache-Control": "no-cache",
                        "Pragma": "no-cache",
                    },
                });

                if (!response.ok) {
                    throw new Error(`HTTP error stream status: ${response.status}`);
                }

                const reader = response.body?.getReader();
                if (!reader) throw new Error("No response body reader available.");

                const decoder = new TextDecoder("utf-8");
                let buffer = "";

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const chunks = buffer.split(/\r?\n\r?\n/);
                    buffer = chunks.pop() || "";

                    for (const chunk of chunks) {
                        if (!chunk.trim()) continue;
                        let eventType = "message";
                        let dataStr = "";

                        for (const line of chunk.split(/\r?\n/)) {
                            if (line.startsWith("event:")) {
                                eventType = line.slice(6).trim();
                            } else if (line.startsWith("data:")) {
                                dataStr = line.slice(5).trim();
                            }
                        }

                        if (!dataStr) continue;

                        try {
                            const parsed = JSON.parse(dataStr);
                            if (eventType === "speaker_selected" || parsed.type === "speaker_selected") {
                                callbacks.onSpeakerSelected?.({
                                    speaker: parsed.speaker,
                                    round: parsed.round,
                                    avatarSeed: parsed.avatarSeed,
                                });
                            } else if (eventType === "thinking" || parsed.type === "thinking") {
                                callbacks.onThinking?.(parsed.content || "");
                            } else if (eventType === "token" || parsed.type === "token") {
                                callbacks.onToken?.(parsed.content || "");
                            } else if (eventType === "tool_start" || parsed.type === "tool_start") {
                                callbacks.onToolStart?.({ name: parsed.tool_name, arguments: parsed.arguments });
                            } else if (eventType === "tool_end" || parsed.type === "tool_end") {
                                callbacks.onToolEnd?.({ name: parsed.tool_name, observation: parsed.observation });
                            } else if (eventType === "turn_complete" || parsed.type === "turn_complete") {
                                callbacks.onComplete?.({ turn: parsed.turn, analytics: parsed.analytics });
                            } else if (eventType === "error" || parsed.type === "error") {
                                callbacks.onError?.(parsed.message || "Streaming execution error.");
                            }
                        } catch {
                            // Ignore non-JSON keepalive/ping comments
                        }
                    }
                }
            } catch (err: unknown) {
                if (!(err instanceof Error && err.name === "AbortError")) {
                    callbacks.onError?.(extractErrorMessage(err));
                }
            }
        })();

        return () => controller.abort();
    },
};