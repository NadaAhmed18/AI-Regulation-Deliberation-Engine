"use client";

import React, { useState, useEffect } from "react";
import { SidebarSetup } from "@/mycomponents/SidebarSetup";
import { DebateArena } from "@/mycomponents/DebateArena";
import { AnalyticsDashboard } from "@/mycomponents/AnalyticsDashboard";
import { Persona, DiscussionTurn } from "@/types/simulation";
import { SimulationAPI } from "@/lib/api";

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

  // Load initial personas once on mount
  useEffect(() => {
    SimulationAPI.generatePersonas(topic, 3).then(setPersonas);
  }, [topic]);

  // Topic change preserves personas so custom ones are not lost
  const handleTopicChange = (selectedTopic: string) => {
    setTopic(selectedTopic);
    setIsConfiguring(true);
    setTurns([]);
  };

  const handleStartSimulation = async () => {
    if (personas.length < 2) return;
    setIsRunning(true);
    setIsConfiguring(false);
    setTurns([]);

    try {
      const { simulation_id } = await SimulationAPI.startSimulation(
        topic,
        personas,
      );
      setSimulationId(simulation_id);

      let turn = await SimulationAPI.nextTurn(simulation_id);
      while (turn !== null) {
        setTurns((prev) => [...prev, turn!]);
        turn = await SimulationAPI.nextTurn(simulation_id);
      }
    } catch (err) {
      console.error("Simulation execution error:", err);
    } finally {
      setIsRunning(false);
    }
  };

  const handleContinueSimulation = async (interventionPrompt?: string) => {
    if (!simulationId) return;
    setIsRunning(true);

    try {
      await SimulationAPI.continueSimulation(simulationId, interventionPrompt);

      let turn = await SimulationAPI.nextTurn(simulationId);
      while (turn !== null) {
        setTurns((prev) => [...prev, turn!]);
        turn = await SimulationAPI.nextTurn(simulationId);
      }
    } catch (err) {
      console.error("Error continuing simulation:", err);
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
        onNew={() => {
          setIsConfiguring(true);
          setTurns([]);
        }}
        onSelectTopic={handleTopicChange}
      />
      <DebateArena
        turns={turns}
        personas={personas}
        topic={topic}
        isRunning={isRunning}
        isConfiguring={isConfiguring}
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
