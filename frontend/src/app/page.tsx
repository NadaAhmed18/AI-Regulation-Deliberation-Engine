"use client";

import React, { useState, useEffect } from "react";
import { SidebarSetup } from "@/mycomponents/SidebarSetup";
import { DebateArena } from "@/mycomponents/DebateArena";
import { AnalyticsDashboard } from "@/mycomponents/AnalyticsDashboard";
import { Persona, DiscussionTurn } from "@/types/simulation";
import { SimulationAPI, extractErrorMessage } from "@/lib/api";

export default function Home() {
  const [topic, setTopic] = useState<string>(
    "Should governments mandate hardware-level kill-switches for frontier open-source AI?",
  );
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [turns, setTurns] = useState<DiscussionTurn[]>([]);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [isConfiguring, setIsConfiguring] = useState<boolean>(true);
  const [simulationId, setSimulationId] = useState<string>("");
  const [isAnalyticsExpanded, setIsAnalyticsExpanded] =
    useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Generate initial personas
  useEffect(() => {
    SimulationAPI.generatePersonas(topic, 3)
      .then(setPersonas)
      .catch((err) => setErrorMessage(extractErrorMessage(err)));
  }, [topic]);

  const handleTopicChange = (selectedTopic: string) => {
    setTopic(selectedTopic);
    setIsConfiguring(true);
    setTurns([]);
    setErrorMessage(null);
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

      let turn = await SimulationAPI.nextTurn(simulation_id);
      while (turn !== null) {
        setTurns((prev) => [...prev, turn!]);
        turn = await SimulationAPI.nextTurn(simulation_id);
      }
    } catch (err) {
      setErrorMessage(extractErrorMessage(err));
    } finally {
      setIsRunning(false);
    }
  };

  const handleContinueSimulation = async (
    interventionPrompt?: string,
    steps: number = 1,
  ) => {
    if (!simulationId) return;
    setIsRunning(true);
    setErrorMessage(null);

    try {
      await SimulationAPI.continueSimulation(
        simulationId,
        interventionPrompt,
        steps,
      );

      let turn = await SimulationAPI.nextTurn(simulationId);
      while (turn !== null) {
        setTurns((prev) => [...prev, turn!]);
        turn = await SimulationAPI.nextTurn(simulationId);
      }
    } catch (err) {
      setErrorMessage(extractErrorMessage(err));
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <main
      className={`h-screen w-screen bg-background text-foreground grid transition-all duration-300 overflow-hidden ${
        isAnalyticsExpanded
          ? "grid-cols-[280px_1fr_42%]"
          : "grid-cols-[280px_1fr_340px]"
      }`}
    >
      <SidebarSetup
        personas={personas}
        topic={topic}
        isRunning={isRunning}
        onError={setErrorMessage}
        onNew={() => {
          setIsConfiguring(true);
          setTurns([]);
          setErrorMessage(null);
        }}
        onSelectTopic={handleTopicChange}
      />
      <DebateArena
        turns={turns}
        personas={personas}
        topic={topic}
        isRunning={isRunning}
        isConfiguring={isConfiguring}
        errorMessage={errorMessage}
        onClearError={() => setErrorMessage(null)}
        onError={setErrorMessage}
        onStartSimulation={handleStartSimulation}
        onUpdateTopic={setTopic}
        onUpdatePersonas={setPersonas}
        onContinueSimulation={handleContinueSimulation}
        onOpenConfig={() => setIsConfiguring(true)}
      />
      <AnalyticsDashboard
        turns={turns}
        personas={personas}
        simulationId={simulationId}
        isExpanded={isAnalyticsExpanded}
        onToggleExpand={() => setIsAnalyticsExpanded((prev) => !prev)}
      />
    </main>
  );
}
