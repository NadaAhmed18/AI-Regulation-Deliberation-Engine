import {
    Persona,
    DiscussionTurn,
    DebateHistoryItem,
    SimulationAnalytics,
    GraphNodeData,
    GraphEdgeData,
    PredefinedTopic,
} from "@/types/simulation";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
const USE_MOCK = true;

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export const getAvatarPath = (index: number): string => {
    const avatarNum = String((index % 5) + 1).padStart(2, "0");
    return `/avatar/${avatarNum}.png`;
};

// ============================================================================
// 1. MOCK DATA REPOSITORIES
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
    {
        id: "sim-1",
        title: "Mandatory Kill-Switches for Frontier AI Models",
        category: "Today",
        agentsCount: 3,
        roundsCount: 3,
    },
    {
        id: "sim-2",
        title: "EU AI Act Systemic Risk Article 51 Enforcement",
        category: "Yesterday",
        agentsCount: 4,
        roundsCount: 4,
    },
    {
        id: "sim-3",
        title: "Copyright Liability on Synthetic Pre-training Data",
        category: "6 days ago",
        agentsCount: 3,
        roundsCount: 3,
    },
    {
        id: "sim-4",
        title: "Autonomous Agent Financial Sandbox Compliance",
        category: "Month ago",
        agentsCount: 3,
        roundsCount: 5,
    },
    {
        id: "sim-5",
        title: "National Frontier Compute Threshold Licensing (>10^26 FLOPs)",
        category: "Long time ago",
        agentsCount: 4,
        roundsCount: 3,
    },
];

// Pool of 6 distinct stakeholder personas with default memory_config
const MOCK_PERSONAS_POOL: Persona[] = [
    {
        name: "Dr. Aris Thorne",
        background: "Former Frontier Lab Alignment Lead, independent safety auditor.",
        stance: "",
        tone: "Urgent, analytical, assertive",
        avatarSeed: "Thorne",
        memory_config: { type: "sliding_window", window_size: 4 },
    },
    {
        name: "Sarah Chen",
        background: "Open-Source AI Advocate and Decentralized Research Chair.",
        stance: "",
        tone: "Passionate, evidence-driven, pragmatic",
        avatarSeed: "Sarah",
        memory_config: { type: "sliding_window", window_size: 4 },
    },
    {
        name: "Marcus Vance",
        background: "Senior Legal Counsel for Global Tech Governance & EU AI Act.",
        stance: "",
        tone: "Diplomatic, procedural, balanced",
        avatarSeed: "Marcus",
        memory_config: { type: "summary", window_size: 4 },
    },
    {
        name: "Dr. Elena Rostova",
        background: "Distributed Hardware & Semiconductor Cryptography Specialist.",
        stance: "",
        tone: "Rigorous, empirical, skeptical",
        avatarSeed: "Elena",
        memory_config: { type: "sliding_window", window_size: 4 },
    },
    {
        name: "Tariq Mansour",
        background: "Emerging Tech Policy Director, Global South Digital Sovereignty.",
        stance: "",
        tone: "Strategic, direct, egalitarian",
        avatarSeed: "Tariq",
        memory_config: { type: "full", window_size: 4 },
    },
    {
        name: "Prof. Hiroshi Tanaka",
        background: "Chair of Computational Ethics & Autonomous Systems Verification.",
        stance: "",
        tone: "Measured, philosophical, cautious",
        avatarSeed: "Tanaka",
        memory_config: { type: "summary", window_size: 4 },
    },
];

let dynamicTurnsQueue: DiscussionTurn[] = [];
let mockTurnIndex = 0;

const DEFAULT_TURNS: DiscussionTurn[] = [
    {
        id: "turn_1",
        round_number: 1,
        agent_name: "Dr. Aris Thorne",
        content:
            "Allowing unrestricted weights at frontier scales introduces irreversible dual-use risk. Once model weights with automated vulnerability exploitation capabilities leak, no post-hoc fine-tuning can patch them. We require strict hardware kill-switches and mandatory audit access.",
        tools_called: [{ name: "search_ai_policy", query: "frontier model compute threshold kill switch" }],
        retrieved_sources: ["https://en.wikipedia.org/wiki/Artificial_Intelligence_Act"],
        opinion_snapshot: {
            current_stance_score: 4.2,
            shift_magnitude: 0.0,
            reasoning: "Reinforced hardline security position based on weight irreversibility.",
            cfg: {
                guidance_scale_gamma: 0.0,
                shift_magnitude: 0.0,
                guidance_vector: 0.0,
                dynamic: "Anchor Stance",
            },
        },
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
    {
        id: "turn_2",
        round_number: 1,
        agent_name: "Sarah Chen",
        content:
            "Hardware kill-switches are fundamentally incompatible with open-source computing. They consolidate power into the hands of three proprietary chip foundries and cloud cartels. Security through obscurity has failed every time in computer science; distributed auditing is the only scalable defense.",
        tools_called: [{ name: "search_web", query: "open source AI cyber vulnerability benchmarks 2026" }],
        retrieved_sources: ["https://mcit.gov.eg/en/Artificial_Intelligence"],
        opinion_snapshot: {
            current_stance_score: -4.0,
            shift_magnitude: -0.2,
            influencer: "Dr. Aris Thorne",
            reasoning: "Reacted strongly against centralized foundry control.",
            cfg: {
                guidance_scale_gamma: -0.024,
                shift_magnitude: -0.2,
                guidance_vector: 8.2,
                dynamic: "Polarized / Backfire Effect",
            },
        },
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
    {
        id: "turn_3",
        round_number: 2,
        agent_name: "Marcus Vance",
        content:
            "Both viewpoints identify legitimate systemic vulnerabilities. Under Article 51 of the EU AI Act, we don't need a binary ban or total deregulation. We can mandate third-party red-teaming for training clusters exceeding 10^26 FLOPs while preserving weight accessibility for low-compute research.",
        tools_called: [{ name: "search_ai_policy", query: "Article 51 systemic risk thresholds" }],
        retrieved_sources: ["https://en.wikipedia.org/wiki/Artificial_Intelligence_Act"],
        opinion_snapshot: {
            current_stance_score: 0.5,
            shift_magnitude: 0.5,
            influencer: "Sarah Chen",
            reasoning: "Introduced a compromise framework bridging regulatory oversight with open access.",
            cfg: {
                guidance_scale_gamma: 0.11,
                shift_magnitude: 0.5,
                guidance_vector: 4.5,
                dynamic: "Pragmatic Compromise",
            },
        },
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
    {
        id: "turn_4",
        round_number: 2,
        agent_name: "Sarah Chen",
        content:
            "I can concede ground to Marcus's proposal. If compute thresholds are explicitly tied to verifiable FLOP measurements (>10^26) rather than vague subjective criteria, open-source developers under that ceiling remain protected while systemic actors are held accountable.",
        opinion_snapshot: {
            current_stance_score: -1.2,
            shift_magnitude: 2.8,
            influencer: "Marcus Vance",
            reasoning: "Accepted quantitative compute threshold exemption.",
            cfg: {
                guidance_scale_gamma: 0.622,
                shift_magnitude: 2.8,
                guidance_vector: 4.5,
                dynamic: "Persuaded (Guided at 62.2%)",
            },
        },
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
];

// ============================================================================
// 2. API SERVICE METHODS
// ============================================================================
export const SimulationAPI = {
    /**
     * System Health Check: Neo4j, Postgres, & Backend Service
     */
    async checkHealth(): Promise<{ status: string; neo4j: boolean; postgres: boolean; message?: string }> {
        if (USE_MOCK) {
            await delay(50);
            return { status: "healthy", neo4j: true, postgres: true, message: "Mock services active" };
        }
        try {
            const res = await fetch(`${BACKEND_URL}/health`);
            if (!res.ok) throw new Error(`Health check HTTP error ${res.status}`);
            return await res.json();
        } catch (error) {
            return { status: "unhealthy", neo4j: false, postgres: false, message: String(error) };
        }
    },

    async getPredefinedTopics(): Promise<PredefinedTopic[]> {
        if (USE_MOCK) {
            await delay(80);
            return PREDEFINED_TOPICS;
        }
        const res = await fetch(`${BACKEND_URL}/topics/predefined`);
        if (!res.ok) throw new Error("Failed to fetch predefined topics");
        return res.json();
    },

    async getInitialHistory(): Promise<DebateHistoryItem[]> {
        if (USE_MOCK) {
            await delay(80);
            return [...MOCK_HISTORY];
        }
        const res = await fetch(`${BACKEND_URL}/simulations/history-list`);
        if (!res.ok) throw new Error("Failed to fetch history");
        return res.json();
    },

    async deleteHistoryItem(id: string): Promise<boolean> {
        if (USE_MOCK) {
            await delay(60);
            MOCK_HISTORY = MOCK_HISTORY.filter((item) => item.id !== id);
            return true;
        }
        const res = await fetch(`${BACKEND_URL}/simulations/${id}`, { method: "DELETE" });
        if (!res.ok) throw new Error("Failed to delete item");
        return true;
    },

    /**
     * Generates personas between 2 and 6 agents with memory configurations
     */
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

        const res = await fetch(`${BACKEND_URL}/personas/generate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                topic,
                num_agents: clampedCount,
                custom_prompt: customPrompt,
                default_memory_type: defaultMemoryType,
            }),
        });
        if (!res.ok) throw new Error("Failed to generate personas");
        return res.json();
    },

    /**
     * Starts simulation with visibility matrix and memory strategy
     */
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
            dynamicTurnsQueue = [...DEFAULT_TURNS];
            mockTurnIndex = 0;
            return { simulation_id: `sim_${Date.now()}` };
        }

        const res = await fetch(`${BACKEND_URL}/simulations/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                topic,
                personas,
                memory_strategy: memoryStrategy,
                visibility_matrix: visibilityMatrix,
            }),
        });
        if (!res.ok) throw new Error("Failed to start simulation");
        return res.json();
    },

    async nextTurn(simulationId: string): Promise<DiscussionTurn | null> {
        if (USE_MOCK) {
            await delay(1100);
            if (mockTurnIndex >= dynamicTurnsQueue.length) return null;
            const turn = dynamicTurnsQueue[mockTurnIndex];
            mockTurnIndex++;
            return turn;
        }

        const res = await fetch(`${BACKEND_URL}/simulations/${simulationId}/next-turn`, {
            method: "POST",
        });
        if (!res.ok) throw new Error("Failed to fetch next turn");
        return res.json();
    },

    /**
     * Stepping & Continuation Controller:
     * Advances the simulation by `steps` (default 1) with an optional intervention prompt.
     */
    async continueSimulation(
        simulationId: string,
        interventionPrompt?: string,
        steps: number = 1
    ): Promise<{ success: boolean; newTurnsCount: number }> {
        if (USE_MOCK) {
            await delay(600);
            const currentRound =
                dynamicTurnsQueue.length > 0
                    ? dynamicTurnsQueue[dynamicTurnsQueue.length - 1].round_number + 1
                    : 3;

            const extendedTurns: DiscussionTurn[] = [];
            for (let i = 0; i < steps; i++) {
                const turn: DiscussionTurn = {
                    id: `turn_ext_${Date.now()}_${i}`,
                    round_number: currentRound + Math.floor(i / 2),
                    agent_name: i % 2 === 0 ? "Dr. Aris Thorne" : "Sarah Chen",
                    content: interventionPrompt && i === 0
                        ? `Addressing intervention: "${interventionPrompt}" — We must prioritize cryptographic verification at cluster boundaries.`
                        : `Advancing round discussion step ${i + 1}. Continuing evidence synthesis based on incoming neighbor remarks.`,
                    tools_called: i % 2 === 0 ? [{ name: "search_ai_policy", query: "frontier safety audit monitoring" }] : [],
                    retrieved_sources: ["https://en.wikipedia.org/wiki/Artificial_Intelligence_Act"],
                    opinion_snapshot: {
                        current_stance_score: i % 2 === 0 ? 2.1 : -0.8,
                        shift_magnitude: i % 2 === 0 ? -0.4 : 0.6,
                        influencer: i % 2 === 0 ? "Marcus Vance" : "Dr. Aris Thorne",
                        reasoning: "Refined stance according to new round evidence.",
                        cfg: {
                            guidance_scale_gamma: 0.35,
                            shift_magnitude: 0.5,
                            guidance_vector: 2.5,
                            dynamic: "Adaptive Convergence",
                        },
                    },
                    timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                };
                extendedTurns.push(turn);
            }

            dynamicTurnsQueue.push(...extendedTurns);
            return { success: true, newTurnsCount: steps };
        }

        const res = await fetch(`${BACKEND_URL}/simulations/${simulationId}/continue`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ intervention: interventionPrompt, steps }),
        });
        if (!res.ok) throw new Error("Failed to continue simulation");
        return res.json();
    },

    async getAnalytics(
        simulationId?: string,
        currentPersonas: Persona[] = [],
        currentTurns: DiscussionTurn[] = []
    ): Promise<SimulationAnalytics> {
        if (USE_MOCK) {
            await delay(100);
            const personas = currentPersonas.length > 0 ? currentPersonas : MOCK_PERSONAS_POOL.slice(0, 3);
            const turns = currentTurns.length > 0 ? currentTurns : DEFAULT_TURNS;

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
                    const weight = Math.abs(
                        turn.opinion_snapshot.cfg?.guidance_scale_gamma ??
                        turn.opinion_snapshot.shift_magnitude ??
                        0.5
                    );
                    const existing = edges.find(
                        (e) => e.source === influencer && e.target === turn.agent_name
                    );
                    if (existing) {
                        existing.weight = Number(weight.toFixed(2));
                        existing.dynamic = turn.opinion_snapshot.cfg?.dynamic;
                    } else {
                        edges.push({
                            source: influencer,
                            target: turn.agent_name,
                            weight: Number(weight.toFixed(2)),
                            dynamic: turn.opinion_snapshot.cfg?.dynamic,
                            round: turn.round_number,
                        });
                    }
                }
            });

            if (edges.length === 0 && personas.length > 1) {
                for (let i = 0; i < personas.length; i++) {
                    const next = (i + 1) % personas.length;
                    edges.push({
                        source: personas[i].name,
                        target: personas[next].name,
                        weight: 0.2,
                        dynamic: "Connected Link",
                    });
                }
            }

            const roundsMap: Record<number, Record<string, number | string>> = {};
            turns.forEach((turn) => {
                const r = turn.round_number;
                if (!roundsMap[r]) roundsMap[r] = { round: `R${r}` };
                roundsMap[r][turn.agent_name] = turn.opinion_snapshot.current_stance_score;
            });

            const persuasion_signals = turns
                .filter((t) => t.opinion_snapshot.influencer)
                .map((t) => ({
                    id: t.id,
                    source: t.opinion_snapshot.influencer!,
                    target: t.agent_name,
                    shift: t.opinion_snapshot.shift_magnitude,
                    gamma: t.opinion_snapshot.cfg?.guidance_scale_gamma ?? 0,
                    dynamic: t.opinion_snapshot.cfg?.dynamic ?? "Opinion Shift",
                }));

            const citations = Array.from(
                new Set(turns.flatMap((t) => t.retrieved_sources || []).filter(Boolean))
            );

            return {
                nodes,
                edges,
                trajectory: Object.values(roundsMap),
                persuasion_signals,
                citations,
            };
        }

        const res = await fetch(`${BACKEND_URL}/simulations/${simulationId}/analytics`);
        if (!res.ok) throw new Error("Failed to fetch analytics");
        return res.json();
    },
};