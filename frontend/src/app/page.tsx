"use client";

import React, { useState } from "react";
import { SidebarSetup } from "@/mycomponents/SidebarSetup";
import { DebateArena } from "@/mycomponents/DebateArena";
import { AnalyticsDashboard } from "@/mycomponents/AnalyticsDashboard";
import {
  Persona,
  DiscussionTurn,
  SimulationAnalytics,
  LiveStreamState,
} from "@/types/simulation";
import { SimulationAPI, extractErrorMessage } from "@/lib/api";

export default function Home() {
  const [topic, setTopic] = useState<string>(
    "Should governments mandate hardware-level kill-switches for frontier open-source AI?",
  );
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [turns, setTurns] = useState<DiscussionTurn[]>([]);
  const [simulationId, setSimulationId] = useState<string>("");
  const [analytics, setAnalytics] = useState<SimulationAnalytics | null>(null);

  // Execution & Live Stream states
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [isConfiguring, setIsConfiguring] = useState<boolean>(true);
  const [liveState, setLiveState] = useState<LiveStreamState | null>(null);
  const [isAnalyticsExpanded, setIsAnalyticsExpanded] =
    useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // History sync trigger for Sidebar
  const [historyRefreshKey, setHistoryRefreshKey] = useState<number>(0);

  // 1 SINGLE ENDPOINT: Retrieves topic, personas, turns, and analytics at once
  const handleSelectSimulation = async (id: string) => {
    setIsRunning(false);
    setErrorMessage(null);
    setSimulationId(id);

    try {
      const data = await SimulationAPI.getSimulation(id);

      setTopic(data.topic);
      setPersonas(data.personas || []);
      setTurns(data.turns || []);
      setAnalytics(data.analytics || null);

      setIsConfiguring(false);
    } catch (err) {
      setErrorMessage(`Failed to load debate: ${extractErrorMessage(err)}`);
    }
  };

  const handleNewDebate = () => {
    setSimulationId("");
    setIsConfiguring(true);
    setTurns([]);
    setAnalytics(null);
    setLiveState(null);
    setErrorMessage(null);
  };

  const runStreamingTurn = (
    targetSimId: string,
    intervention?: string,
  ): Promise<void> => {
    return new Promise((resolve) => {
      SimulationAPI.streamTurn(
        targetSimId,
        {
          onSpeakerSelected: ({ speaker, round, avatarSeed }) => {
            setLiveState({
              speaker,
              round,
              avatarSeed,
              thinking: "",
              tokens: "",
            });
          },
          onThinking: (token) => {
            setLiveState((prev) =>
              prev ? { ...prev, thinking: prev.thinking + token } : prev,
            );
          },
          onToken: (token) => {
            setLiveState((prev) =>
              prev ? { ...prev, tokens: prev.tokens + token } : prev,
            );
          },
          onToolStart: (tool) => {
            setLiveState((prev) =>
              prev
                ? {
                    ...prev,
                    toolCall: {
                      name: tool.name,
                      arguments: tool.arguments,
                      status: "running",
                    },
                  }
                : prev,
            );
          },
          onToolEnd: (tool) => {
            setLiveState((prev) =>
              prev && prev.toolCall
                ? {
                    ...prev,
                    toolCall: {
                      ...prev.toolCall,
                      status: "done",
                      observation: tool.observation,
                    },
                  }
                : prev,
            );
          },
          onComplete: ({ turn, analytics: updatedAnalytics }) => {
            setTurns((prev) => [...prev, turn]);
            if (updatedAnalytics) setAnalytics(updatedAnalytics);
            setLiveState(null);
            resolve();
          },
          onError: (err) => {
            setErrorMessage(err);
            setLiveState(null);
            resolve();
          },
        },
        intervention,
      );
    });
  };

  const handleStartSimulation = async (config?: {
    memoryStrategy: { type: string; window_size: number };
    visibilityMatrix: Record<string, string[]>;
  }) => {
    if (personas.length < 2) return;
    setIsRunning(true);
    setIsConfiguring(false);
    setTurns([]);
    setErrorMessage(null);

    try {
      const { simulation_id } = await SimulationAPI.startSimulation(
        topic,
        personas,
        config?.memoryStrategy,
        config?.visibilityMatrix,
      );
      setSimulationId(simulation_id);
      setHistoryRefreshKey((k) => k + 1);

      await runStreamingTurn(simulation_id);
    } catch (err) {
      setErrorMessage(extractErrorMessage(err));
    } finally {
      setIsRunning(false);
    }
  };

  const handleStepTurn = async (
    stepsCount: number = 1,
    intervention?: string,
  ) => {
    if (!simulationId || isRunning) return;
    setIsRunning(true);
    setErrorMessage(null);

    try {
      for (let i = 0; i < stepsCount; i++) {
        // Pass intervention only on the first stepped turn
        const activeIntervention = i === 0 ? intervention : undefined;
        await runStreamingTurn(simulationId, activeIntervention);
      }
    } catch (err) {
      setErrorMessage(extractErrorMessage(err));
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <main
      className={`h-screen max-h-screen w-screen max-w-screen overflow-hidden bg-background text-foreground grid grid-rows-[100vh] transition-all duration-300 ${
        isAnalyticsExpanded
          ? "grid-cols-[280px_minmax(0,1fr)_42%]"
          : "grid-cols-[280px_minmax(0,1fr)_340px]"
      }`}
    >
      <SidebarSetup
        currentSimulationId={simulationId}
        activeTopic={topic}
        agentsCount={personas.length}
        isRunning={isRunning}
        onNewDebate={handleNewDebate}
        onSelectSimulation={handleSelectSimulation}
        onGoToActiveSession={() => setIsConfiguring(false)}
        refreshTrigger={historyRefreshKey}
        onError={setErrorMessage}
      />

      <DebateArena
        turns={turns}
        personas={personas}
        topic={topic}
        isRunning={isRunning}
        isConfiguring={isConfiguring}
        liveState={liveState}
        errorMessage={errorMessage}
        onClearError={() => setErrorMessage(null)}
        onError={setErrorMessage}
        onStartSimulation={handleStartSimulation}
        onUpdateTopic={setTopic}
        onUpdatePersonas={setPersonas}
        onStepTurn={handleStepTurn}
      />

      <AnalyticsDashboard
        analytics={analytics}
        turns={turns}
        personas={personas}
        isExpanded={isAnalyticsExpanded}
        onToggleExpand={() => setIsAnalyticsExpanded((v) => !v)}
      />
    </main>
  );
}
