"use client";

import React, { useState, useEffect, useMemo } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Globe,
  Database,
  Sparkles,
  TrendingUp,
  TrendingDown,
  Minus,
  Play,
  Wand2,
  Bot,
  PlusCircle,
  Radio,
  Sliders,
  CheckCircle2,
  UserPlus,
  Trash2,
  X,
  AlertCircle,
  Network,
  Eye,
  EyeOff,
  Cpu,
  Activity,
  Layers,
} from "lucide-react";
import { DiscussionTurn, Persona, PredefinedTopic } from "@/types/simulation";
import { SimulationAPI, getAvatarPath } from "@/lib/api";

interface DebateArenaProps {
  turns: DiscussionTurn[];
  personas: Persona[];
  topic: string;
  isRunning: boolean;
  isConfiguring: boolean;
  onStartSimulation: (config?: {
    memoryStrategy: { type: string; window_size: number };
    visibilityMatrix: Record<string, string[]>;
  }) => void;
  onUpdateTopic: (topic: string) => void;
  onUpdatePersonas: (personas: Persona[]) => void;
  onContinueSimulation: (
    interventionPrompt?: string,
    steps?: number,
  ) => Promise<void>;
  onOpenConfig: () => void;
}

// Pure helper: computes default matrix without triggering state effects
const computeDefaultVisibility = (
  personas: Persona[],
  topology: "ring" | "mesh",
): Record<string, string[]> => {
  if (personas.length < 2) return {};
  const matrix: Record<string, string[]> = {};
  const names = personas.map((p) => p.name);

  if (topology === "ring") {
    // Directed ring: Person i receives messages from Person (i - 1 + n) % n
    for (let i = 0; i < names.length; i++) {
      const listener = names[i];
      const speaker = names[(i - 1 + names.length) % names.length];
      matrix[listener] = [speaker];
    }
  } else if (topology === "mesh") {
    // Everyone listens to everyone
    for (const listener of names) {
      matrix[listener] = names.filter((s) => s !== listener);
    }
  }
  return matrix;
};

export const DebateArena: React.FC<DebateArenaProps> = ({
  turns,
  personas,
  topic,
  isRunning,
  isConfiguring,
  onStartSimulation,
  onUpdateTopic,
  onUpdatePersonas,
  onContinueSimulation,
  onOpenConfig,
}) => {
  const [predefinedTopics, setPredefinedTopics] = useState<PredefinedTopic[]>(
    [],
  );
  const [llmPrompt, setLlmPrompt] = useState<string>("");
  const [isGeneratingPersonas, setIsGeneratingPersonas] = useState(false);

  // System Health Status
  const [healthStatus, setHealthStatus] = useState<string>("checking...");

  // Custom Persona Form State
  const [showCustomPersonaForm, setShowCustomPersonaForm] = useState(false);
  const [customName, setCustomName] = useState("");
  const [customBackground, setCustomBackground] = useState("");
  const [customTone, setCustomTone] = useState("");

  // Memory & Visibility Matrix Configuration
  const [globalMemoryType, setGlobalMemoryType] = useState<
    "sliding_window" | "summary" | "full"
  >("sliding_window");
  const [topologyMode, setTopologyMode] = useState<"ring" | "mesh" | "custom">(
    "ring",
  );
  const [customVisibilityMatrix, setCustomVisibilityMatrix] = useState<
    Record<string, string[]>
  >({});
  const [showVisibilityEditor, setShowVisibilityEditor] = useState(false);

  // Stepping & Continuation Controller State
  const [interventionText, setInterventionText] = useState("");
  const [selectedSteps, setSelectedSteps] = useState<number>(1);
  const [isContinuing, setIsContinuing] = useState(false);

  // Health check & predefined topics on mount
  useEffect(() => {
    SimulationAPI.checkHealth()
      .then((res) =>
        setHealthStatus(
          res.status === "healthy" ? "All systems active" : "Warning: degraded",
        ),
      )
      .catch(() => setHealthStatus("Offline / Mock"));

    SimulationAPI.getPredefinedTopics()
      .then(setPredefinedTopics)
      .catch((err) => console.error("Failed to load topics:", err));
  }, []);

  // Compute active matrix using useMemo (prevents cascading re-renders)
  const activeVisibilityMatrix = useMemo(() => {
    if (topologyMode === "custom") {
      return customVisibilityMatrix;
    }
    return computeDefaultVisibility(personas, topologyMode);
  }, [personas, topologyMode, customVisibilityMatrix]);

  const handleTopicSelect = (newTopic: string) => {
    onUpdateTopic(newTopic);
  };

  const handleRegenerateForTopic = async (count: number) => {
    setIsGeneratingPersonas(true);
    try {
      const generated = await SimulationAPI.generatePersonas(
        topic,
        count,
        llmPrompt,
        globalMemoryType,
      );
      onUpdatePersonas(generated);
    } catch (err) {
      console.error("Failed to generate personas:", err);
    } finally {
      setIsGeneratingPersonas(false);
    }
  };

  const handleAddCustomPersona = (e: React.FormEvent) => {
    e.preventDefault();
    if (personas.length >= 6) return;
    if (!customName.trim() || !customBackground.trim()) return;

    const newPersona: Persona = {
      name: customName.trim(),
      background: customBackground.trim(),
      tone: customTone.trim() || "Objective, analytical",
      stance: "",
      avatarSeed: customName.trim(),
      memory_config: { type: globalMemoryType, window_size: 4 },
    };

    onUpdatePersonas([...personas, newPersona]);
    setCustomName("");
    setCustomBackground("");
    setCustomTone("");
    setShowCustomPersonaForm(false);
  };

  const handleRemovePersona = (indexToRemove: number) => {
    onUpdatePersonas(personas.filter((_, idx) => idx !== indexToRemove));
  };

  // Toggle visibility: Can listener hear speaker?
  const toggleVisibility = (listener: string, speaker: string) => {
    const base =
      topologyMode === "custom"
        ? customVisibilityMatrix
        : activeVisibilityMatrix;
    const currentAllowed = base[listener] || [];
    const updatedAllowed = currentAllowed.includes(speaker)
      ? currentAllowed.filter((s) => s !== speaker)
      : [...currentAllowed, speaker];

    setCustomVisibilityMatrix({
      ...base,
      [listener]: updatedAllowed,
    });
    setTopologyMode("custom");
  };

  // Cycle memory type for an individual persona
  const cyclePersonaMemory = (idx: number) => {
    const memoryOrder = ["sliding_window", "summary", "full"];
    const updated = [...personas];
    const current = updated[idx].memory_config?.type || globalMemoryType;
    const nextIdx = (memoryOrder.indexOf(current) + 1) % memoryOrder.length;
    updated[idx] = {
      ...updated[idx],
      memory_config: {
        type: memoryOrder[nextIdx],
        window_size: 4,
      },
    };
    onUpdatePersonas(updated);
  };

  const handleContinue = async () => {
    if (isContinuing) return;
    setIsContinuing(true);
    try {
      await onContinueSimulation(interventionText, selectedSteps);
      setInterventionText("");
    } finally {
      setIsContinuing(false);
    }
  };

  const handleLaunchSimulation = () => {
    onStartSimulation({
      memoryStrategy: { type: globalMemoryType, window_size: 4 },
      visibilityMatrix: activeVisibilityMatrix,
    });
  };

  const getAgentAvatar = (name: string): string => {
    const idx = personas.findIndex((p) => p.name === name);
    return getAvatarPath(idx !== -1 ? idx : 0);
  };

  const currentRound =
    turns.length > 0 ? turns[turns.length - 1].round_number : 0;
  const canStart = !isRunning && personas.length >= 2 && personas.length <= 6;

  // ==========================================================================
  // VIEW 1: CONFIGURATION MODE
  // ==========================================================================
  if (isConfiguring || (turns.length === 0 && !isRunning)) {
    return (
      <div className="flex flex-col h-full bg-background/50 overflow-y-auto p-4 sm:p-6 scrollbar-thin">
        <div className="max-w-4xl w-full mx-auto space-y-5">
          {/* Header & Health Status */}
          <div className="text-center space-y-1.5">
            <div className="flex items-center justify-center gap-2">
              <Badge
                variant="outline"
                className="border-teal-500/30 text-teal-700 dark:text-teal-300 px-2.5 py-0.5"
              >
                <Sparkles className="w-3 h-3 mr-1 text-teal-500" />
                Multi-Agent Discussion Engine
              </Badge>
              <Badge
                variant="secondary"
                className="text-[10px] text-muted-foreground flex items-center gap-1"
              >
                <Activity className="w-2.5 h-2.5 text-emerald-500" />
                {healthStatus}
              </Badge>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
              Configure Autonomous Deliberation
            </h1>
            <p className="text-xs text-muted-foreground max-w-lg mx-auto">
              Select topic, configure communication graph edges, and customize
              agent memory models.
            </p>
          </div>

          {/* 1. Topic Selection */}
          <Card className="p-4 bg-card border-border/80 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 dark:text-teal-400 flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5" />
                1. Deliberation Topic
              </span>
              <span className="text-[10px] text-muted-foreground">
                Personas preserved when switching topics
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
              {predefinedTopics.map((pt) => {
                const isSelected = topic === pt.title;
                return (
                  <div
                    key={pt.id}
                    onClick={() => handleTopicSelect(pt.title)}
                    className={`p-3 rounded-lg border text-left cursor-pointer transition-all ${
                      isSelected
                        ? "bg-teal-50/80 dark:bg-teal-950/40 border-teal-500 text-teal-950 dark:text-teal-200 shadow-2xs"
                        : "bg-muted/30 border-border/60 hover:bg-muted/60 text-foreground"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1 mb-1">
                      <span className="text-[10px] font-semibold text-teal-600 dark:text-teal-400">
                        {pt.tag}
                      </span>
                      {isSelected && (
                        <CheckCircle2 className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400 shrink-0" />
                      )}
                    </div>
                    <p className="text-xs font-medium line-clamp-2 leading-snug">
                      {pt.title}
                    </p>
                  </div>
                );
              })}
            </div>

            <div className="space-y-1">
              <label className="text-[11px] font-medium text-muted-foreground">
                Or enter custom debate topic:
              </label>
              <textarea
                rows={2}
                value={topic}
                onChange={(e) => onUpdateTopic(e.target.value)}
                placeholder="Type any AI governance question..."
                className="w-full text-xs p-2.5 rounded-md bg-background border border-border/80 text-foreground focus:outline-none focus:ring-1 focus:ring-teal-500 transition-all resize-none"
              />
            </div>
          </Card>

          {/* 2. Communication Topology & Visibility Matrix */}
          <Card className="p-4 bg-card border-border/80 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 dark:text-teal-400 flex items-center gap-1.5">
                <Network className="w-3.5 h-3.5" />
                2. Graph Topology & Visibility
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowVisibilityEditor((prev) => !prev)}
                className="h-6 text-[10px] text-teal-700 dark:text-teal-300 hover:bg-teal-50 dark:hover:bg-teal-950/50 p-1"
              >
                {showVisibilityEditor
                  ? "Hide Matrix"
                  : "Customize Edge Visibility"}
              </Button>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] text-muted-foreground font-medium">
                Topology:
              </span>
              <div className="flex items-center gap-1 bg-muted/60 p-0.5 rounded-md border border-border/70">
                <button
                  type="button"
                  onClick={() => setTopologyMode("ring")}
                  className={`px-3 py-1 rounded text-[10px] font-semibold transition-all cursor-pointer ${
                    topologyMode === "ring"
                      ? "bg-teal-600 text-white"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Directed Ring (A → B → C → A)
                </button>
                <button
                  type="button"
                  onClick={() => setTopologyMode("mesh")}
                  className={`px-3 py-1 rounded text-[10px] font-semibold transition-all cursor-pointer ${
                    topologyMode === "mesh"
                      ? "bg-teal-600 text-white"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Full Mesh (All see All)
                </button>
                {topologyMode === "custom" && (
                  <Badge
                    variant="outline"
                    className="text-[9px] border-amber-500 text-amber-500"
                  >
                    Custom Matrix
                  </Badge>
                )}
              </div>
            </div>

            {/* Visibility Matrix Editor */}
            {showVisibilityEditor && personas.length >= 2 && (
              <div className="p-3 bg-muted/20 border border-border/60 rounded-md space-y-2 animate-in fade-in">
                <p className="text-[10px] text-muted-foreground">
                  Toggle an eye icon to show/hide messages between specific
                  agents:
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-[10px] border-collapse">
                    <thead>
                      <tr className="border-b border-border/50 text-left text-muted-foreground">
                        <th className="p-1.5 font-medium">Listener</th>
                        {personas.map((speaker) => (
                          <th
                            key={speaker.name}
                            className="p-1.5 font-medium text-center truncate max-w-[90px]"
                          >
                            {speaker.name.split(" ")[0]}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {personas.map((listener) => (
                        <tr
                          key={listener.name}
                          className="border-b border-border/30 hover:bg-muted/30"
                        >
                          <td className="p-1.5 font-semibold text-foreground truncate max-w-[130px]">
                            {listener.name}
                          </td>
                          {personas.map((speaker) => {
                            if (speaker.name === listener.name) {
                              return (
                                <td
                                  key={speaker.name}
                                  className="p-1.5 text-center text-muted-foreground/40 font-mono"
                                >
                                  self
                                </td>
                              );
                            }
                            const isAllowed = (
                              activeVisibilityMatrix[listener.name] || []
                            ).includes(speaker.name);
                            return (
                              <td
                                key={speaker.name}
                                className="p-1.5 text-center"
                              >
                                <button
                                  type="button"
                                  onClick={() =>
                                    toggleVisibility(
                                      listener.name,
                                      speaker.name,
                                    )
                                  }
                                  className={`p-1.5 rounded cursor-pointer transition-all ${
                                    isAllowed
                                      ? "bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20"
                                      : "bg-rose-500/10 text-rose-500 hover:bg-rose-500/20"
                                  }`}
                                  title={
                                    isAllowed
                                      ? `${listener.name} can hear ${speaker.name}`
                                      : `${speaker.name} is hidden from ${listener.name}`
                                  }
                                >
                                  {isAllowed ? (
                                    <Eye className="w-3 h-3" />
                                  ) : (
                                    <EyeOff className="w-3 h-3" />
                                  )}
                                </button>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </Card>

          {/* 3. Stakeholders & Per-Agent Memory (1-col on mobile, 2-col / 2x2 on desktop) */}
          <Card className="p-4 bg-card border-border/80 shadow-xs space-y-3.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-bold uppercase tracking-wider text-teal-700 dark:text-teal-400 flex items-center gap-1.5">
                  <Bot className="w-3.5 h-3.5" />
                  3. Stakeholders ({personas.length}/6 Nodes)
                </span>
                {personas.length < 2 && (
                  <Badge
                    variant="destructive"
                    className="text-[9px] px-1 py-0 h-4"
                  >
                    Min 2 required
                  </Badge>
                )}
              </div>

              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1 bg-muted/60 p-0.5 rounded-md border border-border/70">
                  <span className="text-[10px] text-muted-foreground px-1 font-medium">
                    Preset:
                  </span>
                  {[2, 3, 4, 5, 6].map((count) => (
                    <button
                      key={count}
                      onClick={() => handleRegenerateForTopic(count)}
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold transition-all cursor-pointer ${
                        personas.length === count
                          ? "bg-teal-600 text-white shadow-2xs"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {count}
                    </button>
                  ))}
                </div>

                <Button
                  size="sm"
                  variant="outline"
                  disabled={personas.length >= 6}
                  onClick={() => setShowCustomPersonaForm((prev) => !prev)}
                  className="h-7 px-2 text-xs border-teal-500/40 text-teal-700 dark:text-teal-300 hover:bg-teal-50 dark:hover:bg-teal-950/40 cursor-pointer"
                >
                  <UserPlus className="w-3.5 h-3.5 mr-1" />
                  Custom
                </Button>
              </div>
            </div>

            {/* Global Memory Selector */}
            <div className="flex items-center justify-between p-2 rounded-md bg-muted/30 border border-border/50">
              <div className="flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />
                <span className="text-xs font-medium text-foreground">
                  Global Memory Default:
                </span>
              </div>
              <div className="flex items-center gap-1">
                {(["sliding_window", "summary", "full"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setGlobalMemoryType(m)}
                    className={`text-[10px] px-2 py-0.5 rounded capitalize font-medium transition-all cursor-pointer ${
                      globalMemoryType === m
                        ? "bg-teal-600 text-white shadow-xs"
                        : "text-muted-foreground hover:text-foreground bg-background border border-border/60"
                    }`}
                  >
                    {m.replace("_", " ")}
                  </button>
                ))}
              </div>
            </div>

            {/* Custom Persona Form */}
            {showCustomPersonaForm && (
              <form
                onSubmit={handleAddCustomPersona}
                className="p-3.5 rounded-lg bg-teal-50/50 dark:bg-teal-950/30 border border-teal-500/30 space-y-2.5 animate-in fade-in duration-200"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-teal-800 dark:text-teal-300 flex items-center gap-1.5">
                    <UserPlus className="w-3.5 h-3.5" />
                    Add Stakeholder Persona ({personas.length}/6)
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowCustomPersonaForm(false)}
                    className="text-muted-foreground hover:text-foreground p-0.5 cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  <div>
                    <label className="text-[10px] font-medium text-muted-foreground block mb-0.5">
                      Name
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Dr. Alex Mercer"
                      value={customName}
                      onChange={(e) => setCustomName(e.target.value)}
                      className="w-full text-xs px-2.5 py-1.5 rounded-md bg-background border border-border/80 text-foreground focus:outline-none focus:ring-1 focus:ring-teal-500"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="text-[10px] font-medium text-muted-foreground block mb-0.5">
                      Background / Role
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Open Source Architect, Confidential Computing Consortium"
                      value={customBackground}
                      onChange={(e) => setCustomBackground(e.target.value)}
                      className="w-full text-xs px-2.5 py-1.5 rounded-md bg-background border border-border/80 text-foreground focus:outline-none focus:ring-1 focus:ring-teal-500"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <div className="flex-1">
                    <input
                      type="text"
                      placeholder="Tone (e.g. Skeptical, empirical, rigorous)"
                      value={customTone}
                      onChange={(e) => setCustomTone(e.target.value)}
                      className="w-full text-xs px-2.5 py-1.5 rounded-md bg-background border border-border/80 text-foreground focus:outline-none focus:ring-1 focus:ring-teal-500"
                    />
                  </div>
                  <Button
                    type="submit"
                    size="sm"
                    className="h-8 text-xs bg-teal-600 hover:bg-teal-700 text-white dark:bg-teal-500 dark:text-teal-950 cursor-pointer"
                  >
                    Add to Debate
                  </Button>
                </div>
              </form>
            )}

            {/* Prompt LLM for Personas */}
            <div className="flex gap-2">
              <input
                type="text"
                value={llmPrompt}
                onChange={(e) => setLlmPrompt(e.target.value)}
                placeholder="Prompt LLM to tailor personas (e.g., 'Include an AI safety auditor and an open-source hacker')..."
                className="flex-1 text-xs px-3 py-2 rounded-md bg-background border border-border/80 text-foreground focus:outline-none focus:ring-1 focus:ring-teal-500"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleRegenerateForTopic(personas.length || 3)}
                disabled={isGeneratingPersonas}
                className="text-xs border-teal-500/40 text-teal-700 dark:text-teal-300 hover:bg-teal-50 dark:hover:bg-teal-950/40 shrink-0 cursor-pointer"
              >
                <Wand2 className="w-3.5 h-3.5 mr-1 text-teal-500" />
                {isGeneratingPersonas ? "Generating..." : "Generate"}
              </Button>
            </div>

            {/* PERSONA PREVIEW: 1-col on mobile, 2-col (2x2) on desktop */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              {personas.map((persona, idx) => {
                const memType = persona.memory_config?.type || globalMemoryType;
                return (
                  <div
                    key={`${persona.name}-${idx}`}
                    className="p-3.5 rounded-xl bg-card border border-border/80 flex flex-col justify-between gap-2.5 shadow-2xs hover:border-teal-500/40 transition-all"
                  >
                    {/* Top Row: Avatar + Name + Delete */}
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <Avatar className="w-10 h-10 border border-teal-500/30 shrink-0 shadow-xs">
                          <AvatarImage
                            src={getAvatarPath(idx)}
                            alt={persona.name}
                          />
                          <AvatarFallback>
                            {persona.name.substring(0, 2)}
                          </AvatarFallback>
                        </Avatar>
                        <div className="min-w-0">
                          <h4 className="text-xs font-bold text-foreground truncate">
                            {persona.name}
                          </h4>
                          <span className="text-[10px] text-muted-foreground block truncate">
                            Node {idx + 1}
                          </span>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => handleRemovePersona(idx)}
                        className="text-muted-foreground/60 hover:text-destructive p-1 rounded transition-colors cursor-pointer shrink-0"
                        title="Remove persona"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    {/* Middle: Background */}
                    <p className="text-xs text-foreground/80 leading-relaxed line-clamp-3 bg-muted/20 p-2.5 rounded-lg border border-border/40">
                      {persona.background}
                    </p>

                    {/* Dedicated Footer: Full Width (Zero Tag Overflow) */}
                    <div className="flex items-center justify-between gap-2 pt-1 border-t border-border/40 text-[10px]">
                      <span
                        className="text-muted-foreground truncate max-w-[65%]"
                        title={persona.tone}
                      >
                        Tone:{" "}
                        <span className="font-medium text-foreground">
                          {persona.tone}
                        </span>
                      </span>

                      <button
                        type="button"
                        onClick={() => cyclePersonaMemory(idx)}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-teal-500/10 text-teal-700 dark:text-teal-300 hover:bg-teal-500/20 border border-teal-500/30 font-mono text-[9px] cursor-pointer shrink-0"
                        title="Click to toggle memory strategy"
                      >
                        <Layers className="w-2.5 h-2.5" />
                        {memType.replace("_", " ")}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {personas.length < 2 && (
              <div className="p-2.5 rounded-md bg-rose-50 dark:bg-rose-950/30 border border-rose-500/30 flex items-center gap-2 text-rose-800 dark:text-rose-300 text-xs">
                <AlertCircle className="w-4 h-4 shrink-0 text-rose-600 dark:text-rose-400" />
                <span>
                  A debate requires at least 2 agents to construct graph
                  communication channels.
                </span>
              </div>
            )}
          </Card>

          {/* Launch Debate Action */}
          <div className="pt-2">
            <Button
              onClick={handleLaunchSimulation}
              disabled={!canStart}
              className="w-full h-11 text-sm font-semibold bg-teal-600 hover:bg-teal-700 text-white dark:bg-teal-500 dark:hover:bg-teal-400 dark:text-teal-950 shadow-md transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Play className="w-4 h-4 mr-2 fill-current" />
              {isRunning
                ? "Starting Simulation..."
                : personas.length < 2
                  ? "At least 2 Agents Required"
                  : `Start Graph Simulation (${personas.length} Agents, ${topologyMode.toUpperCase()} Topology)`}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // ==========================================================================
  // VIEW 2: ACTIVE DEBATE ARENA
  // ==========================================================================
  return (
    <div className="flex flex-col h-full bg-background/50 overflow-hidden">
      {/* Arena Header */}
      <div className="p-3.5 border-b border-border/40 flex items-center justify-between backdrop-blur bg-background/80">
        <div className="min-w-0 pr-2">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-teal-600 dark:text-teal-400 animate-pulse shrink-0" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-foreground truncate">
              Live Deliberation Arena
            </h2>
            <Badge
              variant="outline"
              className="border-teal-500/30 text-teal-700 dark:text-teal-300 font-mono text-[9px] px-1.5"
            >
              Round {currentRound}
            </Badge>
          </div>
          <p className="text-[11px] text-muted-foreground truncate mt-0.5">
            {topic}
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={onOpenConfig}
          className="h-7 text-xs border-border/80 hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer shrink-0"
        >
          <Sliders className="w-3 h-3 mr-1" />
          Settings
        </Button>
      </div>

      {/* Chat Feed */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4 max-w-3xl mx-auto pb-4">
          {turns.map((turn) => {
            const stance = turn.opinion_snapshot.current_stance_score;
            const shift = turn.opinion_snapshot.shift_magnitude;
            const cfg = turn.opinion_snapshot.cfg;
            const avatarSrc = getAgentAvatar(turn.agent_name);

            return (
              <div key={turn.id} className="flex items-start gap-3 group">
                <Avatar className="w-9 h-9 border border-teal-500/20 shadow-xs shrink-0">
                  <AvatarImage src={avatarSrc} alt={turn.agent_name} />
                  <AvatarFallback>
                    {turn.agent_name.substring(0, 2)}
                  </AvatarFallback>
                </Avatar>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-semibold text-foreground">
                      {turn.agent_name}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      Round {turn.round_number}
                    </span>

                    <Badge
                      variant="secondary"
                      className={`text-[10px] font-mono ml-auto ${
                        stance > 0
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border-emerald-500/30"
                          : stance < 0
                            ? "bg-rose-100 text-rose-800 dark:bg-rose-950/80 dark:text-rose-300 border-rose-500/30"
                            : "bg-muted text-muted-foreground"
                      }`}
                    >
                      Stance:{" "}
                      {stance > 0 ? `+${stance.toFixed(1)}` : stance.toFixed(1)}
                    </Badge>
                  </div>

                  {turn.tools_called && turn.tools_called.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-1.5">
                      {turn.tools_called.map((tool, idx) => (
                        <Badge
                          key={idx}
                          variant="outline"
                          className="text-[9px] bg-background/80 text-teal-700 dark:text-teal-300 border-teal-500/30 flex items-center gap-1 py-0.5 font-mono"
                        >
                          {tool.name === "search_web" ? (
                            <Globe className="w-2.5 h-2.5" />
                          ) : (
                            <Database className="w-2.5 h-2.5" />
                          )}
                          {tool.name}
                        </Badge>
                      ))}
                    </div>
                  )}

                  <Card className="p-3.5 bg-card border-border/70 text-xs leading-relaxed text-foreground shadow-2xs rounded-tl-none">
                    {turn.content}
                  </Card>

                  {cfg && (
                    <div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground px-1 font-mono">
                      <span className="flex items-center gap-1">
                        {shift > 0 ? (
                          <TrendingUp className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                        ) : shift < 0 ? (
                          <TrendingDown className="w-3 h-3 text-rose-600 dark:text-rose-400" />
                        ) : (
                          <Minus className="w-3 h-3 text-muted-foreground" />
                        )}
                        Δ{" "}
                        {shift > 0 ? `+${shift.toFixed(2)}` : shift.toFixed(2)}
                      </span>
                      <span>•</span>
                      <span>CFG γ: {cfg.guidance_scale_gamma.toFixed(2)}</span>
                      <span>•</span>
                      <span className="text-teal-700 dark:text-teal-400 font-medium">
                        {cfg.dynamic}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </ScrollArea>

      {/* Stepping & Intervention Controller Bar */}
      <div className="p-3 border-t border-border/60 bg-background/80 backdrop-blur">
        <div className="max-w-3xl mx-auto flex items-center gap-2">
          <div className="flex items-center gap-1 bg-muted/60 p-1 rounded-md border border-border/70 shrink-0">
            {[1, 2, 3].map((step) => (
              <button
                key={step}
                type="button"
                onClick={() => setSelectedSteps(step)}
                className={`px-2 py-1 rounded text-[10px] font-semibold transition-all cursor-pointer ${
                  selectedSteps === step
                    ? "bg-teal-600 text-white shadow-2xs"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                +{step} Step{step > 1 ? "s" : ""}
              </button>
            ))}
          </div>

          <input
            type="text"
            value={interventionText}
            onChange={(e) => setInterventionText(e.target.value)}
            disabled={isRunning || isContinuing}
            placeholder="Inject human intervention prompt (optional)..."
            className="flex-1 text-xs px-3 py-2 rounded-md bg-card border border-border/80 text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-teal-500"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleContinue();
              }
            }}
          />

          <Button
            size="sm"
            onClick={handleContinue}
            disabled={isRunning || isContinuing}
            className="h-8 px-3 text-xs bg-teal-600 hover:bg-teal-700 text-white dark:bg-teal-500 dark:hover:bg-teal-400 dark:text-teal-950 font-medium cursor-pointer shrink-0"
          >
            {isContinuing ? (
              <span>Stepping...</span>
            ) : (
              <>
                <PlusCircle className="w-3.5 h-3.5 mr-1" />
                <span>
                  Advance {selectedSteps} Step{selectedSteps > 1 ? "s" : ""}
                </span>
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};
