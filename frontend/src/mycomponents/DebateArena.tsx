"use client";

import React, { useState, useEffect, useMemo } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
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
  Trash2,
  X,
  AlertCircle,
  Network,
  Eye,
  EyeOff,
  Cpu,
  Plus,
} from "lucide-react";
import { DiscussionTurn, Persona, PredefinedTopic } from "@/types/simulation";
import { SimulationAPI, getAvatarPath, extractErrorMessage } from "@/lib/api";

interface DebateArenaProps {
  turns: DiscussionTurn[];
  personas: Persona[];
  topic: string;
  isRunning: boolean;
  isConfiguring: boolean;
  errorMessage?: string | null;
  onClearError?: () => void;
  onError?: (message: string) => void;
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

const computeDefaultVisibility = (
  personas: Persona[],
  topology: "ring" | "mesh",
): Record<string, string[]> => {
  if (personas.length < 2) return {};
  const matrix: Record<string, string[]> = {};
  const names = personas.map((p, idx) => p.name.trim() || `Agent ${idx + 1}`);

  if (topology === "ring") {
    for (let i = 0; i < names.length; i++) {
      const listener = names[i];
      const speaker = names[(i - 1 + names.length) % names.length];
      matrix[listener] = [speaker];
    }
  } else if (topology === "mesh") {
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
  errorMessage,
  onClearError,
  onError,
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

  // Pure Global Memory Strategy (Applied to all agents)
  const [globalMemoryType, setGlobalMemoryType] = useState<
    "sliding_window" | "summary" | "full"
  >("sliding_window");

  // Topology & Graph Visibility Matrix
  const [topologyMode, setTopologyMode] = useState<"ring" | "mesh" | "custom">(
    "ring",
  );
  const [customVisibilityMatrix, setCustomVisibilityMatrix] = useState<
    Record<string, string[]>
  >({});
  const [showVisibilityEditor, setShowVisibilityEditor] = useState(false);

  // Advance Stepping Controller State
  const [interventionText, setInterventionText] = useState("");
  const [selectedSteps, setSelectedSteps] = useState<number>(1);
  const [isContinuing, setIsContinuing] = useState(false);

  useEffect(() => {
    SimulationAPI.getPredefinedTopics()
      .then(setPredefinedTopics)
      .catch((err) => {
        console.error("Failed to load topics:", err);
        onError?.(extractErrorMessage(err));
      });
  }, [onError]);

  const activeVisibilityMatrix = useMemo(() => {
    if (topologyMode === "custom") return customVisibilityMatrix;
    return computeDefaultVisibility(personas, topologyMode);
  }, [personas, topologyMode, customVisibilityMatrix]);

  // Synchronize global memory change across all current personas
  const handleMemoryTypeChange = (
    type: "sliding_window" | "summary" | "full",
  ) => {
    setGlobalMemoryType(type);
    const updated = personas.map((p) => ({
      ...p,
      memory_config: { type, window_size: 4 },
    }));
    onUpdatePersonas(updated);
  };

  // Set agent count (clamped to max 5) without calling LLM
  const handleSetAgentCount = (targetCount: number) => {
    const clampedCount = Math.max(2, Math.min(targetCount, 5));
    if (clampedCount === personas.length) return;

    if (clampedCount > personas.length) {
      const addedCount = clampedCount - personas.length;
      const newPersonas: Persona[] = Array.from(
        { length: addedCount },
        (_, i) => ({
          name: "",
          background: "",
          stance: "",
          tone: "Analytical, professional",
          avatarSeed: `Agent-${personas.length + i + 1}`,
          memory_config: { type: globalMemoryType, window_size: 4 },
        }),
      );
      onUpdatePersonas([...personas, ...newPersonas]);
    } else {
      onUpdatePersonas(personas.slice(0, clampedCount));
    }
  };

  const handleAddSinglePersona = () => {
    if (personas.length >= 5) return;
    const newPersona: Persona = {
      name: "",
      background: "",
      stance: "",
      tone: "Analytical, professional",
      avatarSeed: `Agent-${personas.length + 1}`,
      memory_config: { type: globalMemoryType, window_size: 4 },
    };
    onUpdatePersonas([...personas, newPersona]);
  };

  const handleUpdatePersonaField = (
    index: number,
    field: keyof Persona,
    value: string,
  ) => {
    const updated = [...personas];
    updated[index] = { ...updated[index], [field]: value };
    onUpdatePersonas(updated);
  };

  const handleRemovePersona = (indexToRemove: number) => {
    onUpdatePersonas(personas.filter((_, idx) => idx !== indexToRemove));
  };

  // Generate personas via LLM on demand (max 5)
  const handleGenerateWithLLM = async () => {
    const count = personas.length >= 2 ? Math.min(personas.length, 5) : 3;
    setIsGeneratingPersonas(true);
    onClearError?.();
    try {
      const generated = await SimulationAPI.generatePersonas(
        topic,
        count,
        llmPrompt,
        globalMemoryType,
      );
      onUpdatePersonas(generated);
    } catch (err) {
      onError?.(`Failed to generate personas: ${extractErrorMessage(err)}`);
    } finally {
      setIsGeneratingPersonas(false);
    }
  };

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

  const handleContinue = async () => {
    if (isContinuing) return;
    setIsContinuing(true);
    onClearError?.();
    try {
      await onContinueSimulation(interventionText, selectedSteps);
      setInterventionText("");
    } catch (err) {
      onError?.(extractErrorMessage(err));
    } finally {
      setIsContinuing(false);
    }
  };

  const handleLaunchSimulation = () => {
    onClearError?.();
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

  // Validation: 2 to 5 agents, all must have a name & background filled in
  const hasIncompletePersonas = personas.some(
    (p) => !p.name.trim() || !p.background.trim(),
  );
  const canStart =
    !isRunning &&
    personas.length >= 2 &&
    personas.length <= 5 &&
    !hasIncompletePersonas;

  // ==========================================================================
  // VIEW 1: CONFIGURATION MODE
  // ==========================================================================
  if (isConfiguring || (turns.length === 0 && !isRunning)) {
    return (
      <div className="flex flex-col h-full bg-background/50 overflow-y-auto p-4 sm:p-6 scrollbar-thin">
        <div className="max-w-4xl w-full mx-auto space-y-5">
          {/* Header */}
          <div className="text-center space-y-1.5">
            <div className="flex items-center justify-center gap-2">
              <Badge
                variant="outline"
                className="border-teal-500/30 text-teal-700 dark:text-teal-300 px-2.5 py-0.5"
              >
                <Sparkles className="w-3 h-3 mr-1 text-teal-500" />
                Multi-Agent Deliberation Engine
              </Badge>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
              Configure Autonomous Deliberation
            </h1>
            <p className="text-xs text-muted-foreground max-w-lg mx-auto">
              Select a debate topic, customize your stakeholder personas
              directly, and choose your deliberation graph.
            </p>
          </div>

          {/* Error Alert */}
          {errorMessage && (
            <Alert
              variant="destructive"
              className="relative pr-9 border-rose-500/50 bg-rose-50 dark:bg-rose-950/40 text-rose-900 dark:text-rose-200"
            >
              <AlertCircle className="h-4 w-4" />
              <AlertTitle className="text-xs font-bold">
                Configuration Error
              </AlertTitle>
              <AlertDescription className="text-xs">
                {errorMessage}
              </AlertDescription>
              {onClearError && (
                <button
                  onClick={onClearError}
                  className="absolute top-2.5 right-2.5 text-muted-foreground hover:text-foreground cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </Alert>
          )}

          {/* 1. Topic Selection */}
          <Card className="p-4 bg-card border-border/80 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 dark:text-teal-400 flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5" />
                1. Deliberation Topic
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
              {predefinedTopics.map((pt) => {
                const isSelected = topic === pt.title;
                return (
                  <div
                    key={pt.id}
                    onClick={() => onUpdateTopic(pt.title)}
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
                Or enter a custom debate topic:
              </label>
              <textarea
                rows={2}
                value={topic}
                onChange={(e) => onUpdateTopic(e.target.value)}
                placeholder="Type any AI regulation or governance question..."
                className="w-full text-xs p-2.5 rounded-md bg-background border border-border/80 text-foreground focus:outline-none focus:ring-1 focus:ring-teal-500 resize-none"
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
                className="h-6 text-[10px] text-teal-700 dark:text-teal-300 hover:bg-teal-50 p-1"
              >
                {showVisibilityEditor
                  ? "Hide Matrix"
                  : "Customize Edge Visibility"}
              </Button>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] text-muted-foreground font-medium">
                Preset:
              </span>
              <div className="flex items-center gap-1 bg-muted/60 p-0.5 rounded-md border border-border/70">
                <button
                  type="button"
                  onClick={() => setTopologyMode("ring")}
                  className={`px-3 py-1 rounded text-[10px] font-semibold cursor-pointer ${
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
                  className={`px-3 py-1 rounded text-[10px] font-semibold cursor-pointer ${
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

            {showVisibilityEditor && personas.length >= 2 && (
              <div className="p-3 bg-muted/20 border border-border/60 rounded-md space-y-2 animate-in fade-in">
                <p className="text-[10px] text-muted-foreground">
                  Toggle visibility permissions between specific agents:
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-[10px] border-collapse">
                    <thead>
                      <tr className="border-b border-border/50 text-left text-muted-foreground">
                        <th className="p-1.5 font-medium">Listener</th>
                        {personas.map((speaker, sIdx) => (
                          <th
                            key={sIdx}
                            className="p-1.5 font-medium text-center truncate max-w-[90px]"
                          >
                            {
                              (
                                speaker.name.trim() || `Agent ${sIdx + 1}`
                              ).split(" ")[0]
                            }
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {personas.map((listener, lIdx) => {
                        const lName =
                          listener.name.trim() || `Agent ${lIdx + 1}`;
                        return (
                          <tr
                            key={lIdx}
                            className="border-b border-border/30 hover:bg-muted/30"
                          >
                            <td className="p-1.5 font-semibold text-foreground truncate max-w-[130px]">
                              {lName}
                            </td>
                            {personas.map((speaker, sIdx) => {
                              const sName =
                                speaker.name.trim() || `Agent ${sIdx + 1}`;
                              if (sName === lName) {
                                return (
                                  <td
                                    key={sIdx}
                                    className="p-1.5 text-center text-muted-foreground/40 font-mono"
                                  >
                                    self
                                  </td>
                                );
                              }
                              const isAllowed = (
                                activeVisibilityMatrix[lName] || []
                              ).includes(sName);
                              return (
                                <td key={sIdx} className="p-1.5 text-center">
                                  <button
                                    type="button"
                                    onClick={() =>
                                      toggleVisibility(lName, sName)
                                    }
                                    className={`p-1.5 rounded cursor-pointer transition-all ${
                                      isAllowed
                                        ? "bg-emerald-500/10 text-emerald-600"
                                        : "bg-rose-500/10 text-rose-500"
                                    }`}
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
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </Card>

          {/* 3. Stakeholders & Direct Editable Cards */}
          <Card className="p-4 bg-card border-border/80 shadow-xs space-y-3.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 dark:text-teal-400 flex items-center gap-1.5">
                <Bot className="w-3.5 h-3.5" />
                3. Stakeholders ({personas.length}/5 Nodes)
              </span>

              <div className="flex items-center gap-2">
                {/* Agent Count Selector (Max 5) */}
                <div className="flex items-center gap-1 bg-muted/60 p-0.5 rounded-md border border-border/70">
                  {[2, 3, 4, 5].map((count) => (
                    <button
                      key={count}
                      type="button"
                      onClick={() => handleSetAgentCount(count)}
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold transition-all cursor-pointer ${
                        personas.length === count
                          ? "bg-teal-600 text-white"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                      title={`Set to ${count} slots`}
                    >
                      {count}
                    </button>
                  ))}
                </div>

                <Button
                  size="sm"
                  variant="outline"
                  disabled={personas.length >= 5}
                  onClick={handleAddSinglePersona}
                  className="h-7 px-2 text-xs border-teal-500/40 text-teal-700 dark:text-teal-300 cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5 mr-1" />
                  Add Node
                </Button>
              </div>
            </div>

            {/* Pure Global Memory Strategy Selector */}
            <div className="flex items-center justify-between p-2.5 rounded-lg bg-muted/30 border border-border/50">
              <div className="flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />
                <span className="text-xs font-medium text-foreground">
                  Debate Memory Strategy:
                </span>
                <span className="text-[10px] text-muted-foreground hidden sm:inline">
                  (Applied globally to all agents)
                </span>
              </div>
              <div className="flex items-center gap-1">
                {(["sliding_window", "summary", "full"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => handleMemoryTypeChange(m)}
                    className={`text-[10px] px-2.5 py-1 rounded font-medium cursor-pointer transition-all ${
                      globalMemoryType === m
                        ? "bg-teal-600 text-white shadow-xs font-semibold"
                        : "text-muted-foreground hover:text-foreground bg-background border border-border/60"
                    }`}
                  >
                    {m === "sliding_window"
                      ? "Sliding Window"
                      : m === "summary"
                        ? "Summary"
                        : "Full Memory"}
                  </button>
                ))}
              </div>
            </div>

            {/* Prompt LLM to Auto-Fill Personas with descriptive placeholder */}
            <div className="flex gap-2 p-2 rounded-lg bg-teal-50/40 dark:bg-teal-950/20 border border-teal-500/30">
              <input
                type="text"
                value={llmPrompt}
                onChange={(e) => setLlmPrompt(e.target.value)}
                placeholder="e.g. Include an EU compliance auditor, an open-source researcher, and a Big Tech lobbyist with opposing stances..."
                className="flex-1 text-xs px-3 py-1.5 rounded-md bg-background border border-border/80 text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-teal-500"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={handleGenerateWithLLM}
                disabled={isGeneratingPersonas}
                className="text-xs border-teal-500/40 bg-teal-600 text-white hover:bg-teal-700 dark:bg-teal-500 dark:text-teal-950 shrink-0 cursor-pointer"
              >
                <Wand2 className="w-3.5 h-3.5 mr-1" />
                {isGeneratingPersonas
                  ? "Generating..."
                  : `Generate (${personas.length >= 2 ? Math.min(personas.length, 5) : 3})`}
              </Button>
            </div>

            {/* Editable Persona Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              {personas.length === 0 ? (
                <div className="md:col-span-2 py-8 text-center border border-dashed border-border/70 rounded-xl space-y-2 bg-muted/10">
                  <Bot className="w-6 h-6 mx-auto text-teal-500/60" />
                  <p className="text-xs font-medium text-foreground">
                    No Stakeholders Configured
                  </p>
                  <p className="text-[11px] text-muted-foreground max-w-xs mx-auto">
                    Select a slot count above (2–5) to enter details manually,
                    or click Generate to have AI create them.
                  </p>
                </div>
              ) : (
                personas.map((persona, idx) => (
                  <div
                    key={idx}
                    className="p-3.5 rounded-xl bg-card border border-border/80 flex flex-col justify-between gap-2.5 shadow-2xs hover:border-teal-500/40 transition-all"
                  >
                    {/* Card Header: Avatar & Name Input */}
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2.5 min-w-0 flex-1">
                        <Avatar className="w-9 h-9 border border-teal-500/30 shrink-0">
                          <AvatarImage
                            src={getAvatarPath(idx)}
                            alt={persona.name || `Node ${idx + 1}`}
                          />
                          <AvatarFallback>
                            {(persona.name || `N${idx + 1}`).substring(0, 2)}
                          </AvatarFallback>
                        </Avatar>
                        <div className="min-w-0 flex-1">
                          <input
                            type="text"
                            value={persona.name}
                            onChange={(e) =>
                              handleUpdatePersonaField(
                                idx,
                                "name",
                                e.target.value,
                              )
                            }
                            placeholder={`Agent ${idx + 1} Name...`}
                            className="w-full text-xs font-bold text-foreground bg-transparent border-b border-border/60 focus:border-teal-500 focus:outline-none py-0.5"
                          />
                          <span className="text-[9px] text-muted-foreground block mt-0.5">
                            Node {idx + 1}
                          </span>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => handleRemovePersona(idx)}
                        className="text-muted-foreground hover:text-destructive p-1 rounded cursor-pointer"
                        title="Remove Node"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    {/* Card Body: Background */}
                    <textarea
                      rows={2}
                      value={persona.background}
                      onChange={(e) =>
                        handleUpdatePersonaField(
                          idx,
                          "background",
                          e.target.value,
                        )
                      }
                      placeholder="Affiliation, role & background (e.g. AI Safety Auditor, European Institute)..."
                      className="w-full text-xs text-foreground/90 p-2 rounded-lg bg-muted/20 border border-border/50 focus:border-teal-500 focus:outline-none resize-none leading-relaxed"
                    />

                    {/* Card Footer: Tone Input */}
                    <div className="flex items-center justify-between gap-2 pt-1.5 border-t border-border/40 text-[10px]">
                      <div className="flex items-center gap-1.5 flex-1 min-w-0">
                        <span className="text-muted-foreground shrink-0 font-medium text-[10px]">
                          Tone:
                        </span>
                        <input
                          type="text"
                          value={persona.tone}
                          onChange={(e) =>
                            handleUpdatePersonaField(
                              idx,
                              "tone",
                              e.target.value,
                            )
                          }
                          placeholder="e.g. Skeptical, empirical, rigorous..."
                          className="w-full text-[10px] text-foreground bg-transparent border-b border-border/40 focus:border-teal-500 focus:outline-none py-0.5"
                        />
                      </div>
                      <span className="text-[9px] text-muted-foreground/70 font-mono shrink-0">
                        Node {idx + 1}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>

          {/* Launch Simulation */}
          <div className="pt-2">
            <Button
              onClick={handleLaunchSimulation}
              disabled={!canStart}
              className="w-full h-11 text-sm font-semibold bg-teal-600 hover:bg-teal-700 text-white dark:bg-teal-500 dark:text-teal-950 shadow-md cursor-pointer disabled:opacity-40"
            >
              <Play className="w-4 h-4 mr-2 fill-current" />
              {isRunning
                ? "Starting Simulation..."
                : personas.length < 2
                  ? "At least 2 Agents Required"
                  : hasIncompletePersonas
                    ? "Please fill in Name and Background for all Agents"
                    : `Start Simulation (${personas.length} Agents, ${topologyMode.toUpperCase()} Topology)`}
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
      {/* Header */}
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
          className="h-7 text-xs border-border/80"
        >
          <Sliders className="w-3 h-3 mr-1" />
          Settings
        </Button>
      </div>

      {/* Chat Messages */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4 max-w-3xl mx-auto pb-4">
          {turns.map((turn) => {
            const stance = turn.opinion_snapshot.current_stance_score;
            const shift = turn.opinion_snapshot.shift_magnitude;
            const cfg = turn.opinion_snapshot.cfg;
            const avatarSrc = getAgentAvatar(turn.agent_name);

            return (
              <div key={turn.id} className="flex items-start gap-3 group">
                <Avatar className="w-9 h-9 border border-teal-500/20 shrink-0">
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
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300"
                          : stance < 0
                            ? "bg-rose-100 text-rose-800 dark:bg-rose-950/80 dark:text-rose-300"
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
                          className="text-[9px] text-teal-700 dark:text-teal-300 font-mono"
                        >
                          {tool.name === "search_web" ? (
                            <Globe className="w-2.5 h-2.5 mr-1" />
                          ) : (
                            <Database className="w-2.5 h-2.5 mr-1" />
                          )}
                          {tool.name}
                        </Badge>
                      ))}
                    </div>
                  )}

                  <Card className="p-3.5 bg-card border-border/70 text-xs leading-relaxed text-foreground rounded-tl-none">
                    {turn.content}
                  </Card>

                  {cfg && (
                    <div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground font-mono">
                      <span className="flex items-center gap-1">
                        {shift > 0 ? (
                          <TrendingUp className="w-3 h-3 text-emerald-600" />
                        ) : shift < 0 ? (
                          <TrendingDown className="w-3 h-3 text-rose-600" />
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

      {/* Stepping Controller */}
      <div className="p-3 border-t border-border/60 bg-background/80 backdrop-blur">
        <div className="max-w-3xl mx-auto flex items-center justify-between gap-2">
          <div className="flex items-center gap-1 bg-muted/60 p-1 rounded-md border border-border/70 shrink-0">
            {[1, 2, 3].map((step) => (
              <button
                key={step}
                type="button"
                onClick={() => setSelectedSteps(step)}
                className={`px-2 py-1 rounded text-[10px] font-semibold cursor-pointer ${
                  selectedSteps === step
                    ? "bg-teal-600 text-white"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                +{step} Step{step > 1 ? "s" : ""}
              </button>
            ))}
          </div>

          <Button
            size="sm"
            onClick={handleContinue}
            disabled={isRunning || isContinuing}
            className="h-8 px-4 text-xs bg-teal-600 hover:bg-teal-700 text-white font-medium cursor-pointer"
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
