"use client";

import React, { useState } from "react";
import { SidebarSetup } from "@/mycomponents/SidebarSetup";
import { DebateArena } from "@/mycomponents/DebateArena";
import { AnalyticsDashboard } from "@/mycomponents/AnalyticsDashboard";
import { Persona, DiscussionTurn } from "@/types/simulation";

const INITIAL_PERSONAS: Persona[] = [
  {
    name: "Dr. Aris Thorne",
    background: "Ex-OpenAI Safety Auditor",
    stance: "Mandatory compute licensing and model kill-switches.",
    tone: "Urgent, analytical",
    avatarSeed: "Thorne",
  },
  {
    name: "Sarah Chen",
    background: "Open Source AI Coalition Leader",
    stance: "Preserve open-weights; prevent monopolistic lock-in.",
    tone: "Passionate, pragmatic",
    avatarSeed: "Sarah",
  },
  {
    name: "Marcus Vance",
    background: "EU Policy Regulatory Director",
    stance: "Enforce tiered risk compliance standards under AI Act.",
    tone: "Diplomatic, legalistic",
    avatarSeed: "Marcus",
  },
];

const INITIAL_TURNS: DiscussionTurn[] = [
  {
    id: "turn_1",
    round_number: 1,
    agent_name: "Dr. Aris Thorne",
    content:
      "We cannot treat frontier weights like normal software. If an unaligned model leaks, the cyberattack potential is irreversible. We need verifiable kill-switches.",
    tools_called: [{ name: "search_ai_policy", query: "EU AI Act high risk kill switch" }],
    opinion_snapshot: {
      current_stance_score: 4.2,
      shift_magnitude: 0.0,
      cfg: { guidance_scale_gamma: 0.0, shift_magnitude: 0.0, guidance_vector: 0.0, dynamic: "Anchor Stance" },
    },
    timestamp: "12:00",
  },
  {
    id: "turn_2",
    round_number: 1,
    agent_name: "Sarah Chen",
    content:
      "Kill-switches are technically infeasible on open weights and centralize authority into the hands of three tech monopolies. Innovation requires decentralized audits.",
    tools_called: [{ name: "search_web", query: "frontier open weights safety benchmarks" }],
    opinion_snapshot: {
      current_stance_score: -3.8,
      shift_magnitude: 0.0,
      cfg: { guidance_scale_gamma: 0.0, shift_magnitude: 0.0, guidance_vector: -8.0, dynamic: "Anchor Stance" },
    },
    timestamp: "12:01",
  },
  {
    id: "turn_3",
    round_number: 2,
    agent_name: "Sarah Chen",
    content:
      "I reviewed Dr. Thorne's cyber audit. While a kill-switch is still a non-starter, I concede that compute thresholds over 10^26 FLOPs should require registered audits.",
    opinion_snapshot: {
      current_stance_score: -1.5,
      shift_magnitude: 2.3,
      cfg: { guidance_scale_gamma: 0.287, shift_magnitude: 2.3, guidance_vector: 8.0, dynamic: "Persuaded (28.7% Guided)" },
    },
    timestamp: "12:02",
  },
];

export default function Home() {
  const [topic] = useState("Should governments mandate kill-switches for open-source frontier models?");
  const [personas] = useState<Persona[]>(INITIAL_PERSONAS);
  const [turns, setTurns] = useState<DiscussionTurn[]>(INITIAL_TURNS);
  const [isRunning, setIsRunning] = useState(false);

  const handleStartSimulation = () => {
    setIsRunning(true);
    // Wire your API call or SSE stream here
    setTimeout(() => setIsRunning(false), 3000);
  };

  return (
    <main className="h-screen w-screen bg-background text-foreground grid grid-cols-[300px_1fr_320px] overflow-hidden">
      <SidebarSetup
        personas={personas}
        topic={topic}
        isRunning={isRunning}
        onStart={handleStartSimulation}
      />
      <DebateArena turns={turns} />
      <AnalyticsDashboard turns={turns} personas={personas} />
    </main>
  );
}