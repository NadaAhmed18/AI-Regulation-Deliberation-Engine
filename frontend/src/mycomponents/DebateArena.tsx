"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import {
  Sparkles,
  TrendingUp,
  TrendingDown,
  Minus,
  Play,
  Wand2,
  Bot,
  Sliders,
  CheckCircle2,
  Trash2,
  X,
  AlertCircle,
  Network,
  Eye,
  EyeOff,
  Plus,
  Radio,
  Brain,
  Terminal,
  FastForward,
  ChevronDown,
  ChevronUp,
  Info,
  Send,
  ExternalLink,
  BookOpen,
} from "lucide-react";
import {
  DiscussionTurn,
  Persona,
  PredefinedTopic,
  LiveStreamState,
} from "@/types/simulation";
import { SimulationAPI, getAvatarPath, extractErrorMessage } from "@/lib/api";

/**
 * Parses raw text with brackets like 【source 1†https://...】 into clean inline hyperlinks
 * and generates structured bottom references.
 */
interface ParsedContentResult {
  formattedParts: React.ReactNode[];
  references: Array<{
    index: number;
    url: string;
    domain: string;
    path: string;
    locator?: string;
  }>;
}

function parseAndFormatContent(
  content: string,
  extraSources: string[] = [],
): ParsedContentResult {
  const urlMap = new Map<string, number>();
  const references: Array<{
    index: number;
    url: string;
    domain: string;
    path: string;
    locator?: string;
  }> = [];

  // Register a URL and assign a continuous 1-based index
  const registerUrl = (rawUrl: string, locator?: string): number => {
    const cleanUrl = rawUrl.trim();
    if (urlMap.has(cleanUrl)) {
      const existingIdx = urlMap.get(cleanUrl)!;
      if (locator && !references[existingIdx - 1]?.locator) {
        references[existingIdx - 1].locator = locator;
      }
      return existingIdx;
    }

    const newIdx = references.length + 1;
    urlMap.set(cleanUrl, newIdx);

    let domain = cleanUrl;
    let path = "";
    try {
      const u = new URL(cleanUrl);
      domain = u.hostname.replace(/^www\./, "");
      path = u.pathname;
    } catch {
      domain = cleanUrl.replace(/^https?:\/\//, "").split("/")[0] || cleanUrl;
    }

    references.push({ index: newIdx, url: cleanUrl, domain, path, locator });
    return newIdx;
  };

  // Pre-seed known URLs from tool execution into reference indices
  extraSources.forEach((src) => {
    if (src && (src.startsWith("http://") || src.startsWith("https://"))) {
      registerUrl(src);
    }
  });

  // 1. Matches ANY bracketed citation: 【...】
  const bracketCitationRegex = /【([^】]+)】/g;

  const segments: React.ReactNode[] = [];
  let lastIdx = 0;
  let match: RegExpExecArray | null;

  while ((match = bracketCitationRegex.exec(content)) !== null) {
    const textBefore = content.substring(lastIdx, match.index);
    if (textBefore) {
      segments.push(renderMarkdownFormatting(textBefore, `txt-${lastIdx}`));
    }

    // Normalize unicode spaces (e.g. \u202F, \u00A0) to standard spaces
    const rawInner = match[1];
    const inner = rawInner.replace(/[\u202F\u00A0\r\n\t]/g, " ").trim();

    // Strategy A: Direct URL inside tag? (e.g. 【https://...】 or 【source 1†https://...】)
    const directUrlMatch = inner.match(/https?:\/\/[^\s】]+/i);

    // Strategy B: Parse index and locator (e.g. "source 1†L23-L28", "source 2†L1-L4", "2†source", "1")
    let sourceNum: number | null = null;
    let locator: string | undefined = undefined;

    if (inner.includes("†")) {
      const parts = inner.split("†").map((p) => p.trim());
      const numMatchLeft = parts[0].match(/\d+/);
      const numMatchRight = parts[1].match(/\d+/);

      if (numMatchLeft) {
        sourceNum = parseInt(numMatchLeft[0], 10);
        if (
          parts[1].toLowerCase() !== "source" &&
          !parts[1].startsWith("http")
        ) {
          locator = parts[1]; // e.g. "L23-L28"
        }
      } else if (numMatchRight) {
        sourceNum = parseInt(numMatchRight[0], 10);
      }
    } else {
      const numMatch = inner.match(/\d+/);
      if (numMatch) {
        sourceNum = parseInt(numMatch[0], 10);
      }
    }

    let targetUrl = "";
    let displayIdx = 0;

    if (directUrlMatch) {
      targetUrl = directUrlMatch[0];
      displayIdx = registerUrl(targetUrl, locator);
    } else if (sourceNum !== null) {
      // 1-based index pointing to extraSources
      const candidateUrl = extraSources[sourceNum - 1];
      if (candidateUrl) {
        targetUrl = candidateUrl;
        displayIdx = registerUrl(targetUrl, locator);
      } else {
        displayIdx = sourceNum;
      }
    }

    // Render clickable footnote badge if URL resolved, or clean pill if unresolved
    if (targetUrl) {
      segments.push(
        <a
          key={`ref-${match.index}`}
          href={targetUrl}
          target="_blank"
          rel="noopener noreferrer"
          title={`${targetUrl}${locator ? ` (${locator})` : ""}`}
          className="inline-flex items-center mx-0.5 px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-teal-500/15 text-teal-700 dark:text-teal-300 hover:bg-teal-500/30 hover:underline align-baseline group"
        >
          [{displayIdx}]
        </a>,
      );
    } else {
      segments.push(
        <span
          key={`ref-fallback-${match.index}`}
          title={
            locator
              ? `Source ${sourceNum || displayIdx} (${locator})`
              : `Source ${sourceNum || displayIdx}`
          }
          className="inline-flex items-center mx-0.5 px-1.5 py-0.2 rounded text-[9.5px] font-mono font-semibold bg-muted text-muted-foreground border border-border/50 align-baseline"
        >
          [{displayIdx || sourceNum || "Ref"}]
        </span>,
      );
    }

    lastIdx = match.index + match[0].length;
  }

  const remaining = content.substring(lastIdx);
  if (remaining) {
    segments.push(renderMarkdownFormatting(remaining, `txt-${lastIdx}`));
  }

  return { formattedParts: segments, references };
}

function renderMarkdownFormatting(
  text: string,
  keyPrefix: string,
): React.ReactNode {
  // Simple bold markdown parser (**text**)
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <span key={keyPrefix}>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={i} className="font-semibold text-foreground">
              {part.slice(2, -2)}
            </strong>
          );
        }
        return part;
      })}
    </span>
  );
}

interface DebateArenaProps {
  turns: DiscussionTurn[];
  personas: Persona[];
  topic: string;
  isRunning: boolean;
  isConfiguring: boolean;
  liveState: LiveStreamState | null;
  errorMessage?: string | null;
  onClearError?: () => void;
  onError?: (message: string) => void;
  onStartSimulation: (config?: {
    memoryStrategy: { type: string; window_size: number };
    visibilityMatrix: Record<string, string[]>;
  }) => void;
  onUpdateTopic: (topic: string) => void;
  onUpdatePersonas: (personas: Persona[]) => void;
  onStepTurn: (stepsCount?: number, intervention?: string) => void;
}

export const DebateArena: React.FC<DebateArenaProps> = ({
  turns,
  personas,
  topic,
  isRunning,
  isConfiguring,
  liveState,
  errorMessage,
  onClearError,
  onError,
  onStartSimulation,
  onUpdateTopic,
  onUpdatePersonas,
  onStepTurn,
}) => {
  const [predefinedTopics, setPredefinedTopics] = useState<PredefinedTopic[]>(
    [],
  );
  const [llmPrompt, setLlmPrompt] = useState("");
  const [isGeneratingPersonas, setIsGeneratingPersonas] = useState(false);
  const [globalMemoryType] = useState<"sliding_window" | "summary" | "full">(
    "sliding_window",
  );
  const [topologyMode, setTopologyMode] = useState<"ring" | "mesh" | "custom">(
    "ring",
  );
  const [customMatrix, setCustomMatrix] = useState<Record<string, string[]>>(
    {},
  );
  const [showMatrixEditor, setShowMatrixEditor] = useState(false);
  const [showThinkingPanel, setShowThinkingPanel] = useState(true);
  const [selectedAgentFilter, setSelectedAgentFilter] = useState<string | null>(
    null,
  );
  const [showSessionDetails, setShowSessionDetails] = useState(false);
  const [interventionInput, setInterventionInput] = useState("");

  const turnsScrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    SimulationAPI.getPredefinedTopics()
      .then(setPredefinedTopics)
      .catch((err) => onError?.(extractErrorMessage(err)));
  }, [onError]);

  useEffect(() => {
    if (turnsScrollRef.current) {
      turnsScrollRef.current.scrollTop = turnsScrollRef.current.scrollHeight;
    }
  }, [turns.length, liveState?.tokens, liveState?.thinking]);

  const activeVisibilityMatrix = useMemo(() => {
    if (topologyMode === "custom") return customMatrix;
    const matrix: Record<string, string[]> = {};
    const names = personas.map((p, i) => p.name.trim() || `Agent ${i + 1}`);
    if (topologyMode === "ring") {
      names.forEach((name, i) => {
        matrix[name] = [names[(i - 1 + names.length) % names.length]];
      });
    } else {
      names.forEach((name) => {
        matrix[name] = names.filter((s) => s !== name);
      });
    }
    return matrix;
  }, [personas, topologyMode, customMatrix]);

  const handleSetAgentCount = (count: number) => {
    const clamped = Math.max(2, Math.min(count, 5));
    if (clamped === personas.length) return;
    if (clamped > personas.length) {
      const added: Persona[] = Array.from(
        { length: clamped - personas.length },
        (_, i) => ({
          name: "",
          background: "",
          stance: "",
          tone: "Analytical, professional",
          avatarSeed: `agent_${personas.length + i + 1}`,
          memory_config: { type: globalMemoryType, window_size: 4 },
        }),
      );
      onUpdatePersonas([...personas, ...added]);
    } else {
      onUpdatePersonas(personas.slice(0, clamped));
    }
  };

  const handleGenerateWithAI = async () => {
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
      onError?.(extractErrorMessage(err));
    } finally {
      setIsGeneratingPersonas(false);
    }
  };

  const toggleVisibility = (listener: string, speaker: string) => {
    const base =
      topologyMode === "custom" ? customMatrix : activeVisibilityMatrix;
    const current = base[listener] || [];
    const updated = current.includes(speaker)
      ? current.filter((s) => s !== speaker)
      : [...current, speaker];
    setCustomMatrix({ ...base, [listener]: updated });
    setTopologyMode("custom");
  };

  const getAgentAvatar = (name: string): string => {
    const idx = personas.findIndex((p) => p.name === name);
    return getAvatarPath(idx !== -1 ? idx : 0);
  };

  const currentRound =
    turns.length > 0 ? turns[turns.length - 1].round_number : 0;
  const filteredTurns = useMemo(() => {
    if (!selectedAgentFilter) return turns;
    return turns.filter((t) => t.agent_name === selectedAgentFilter);
  }, [turns, selectedAgentFilter]);

  const handleSendIntervention = () => {
    if (!interventionInput.trim() || isRunning) return;
    onStepTurn(1, interventionInput);
    setInterventionInput("");
  };

  if (isConfiguring) {
    const hasIncomplete = personas.some(
      (p) => !p.name.trim() || !p.background.trim(),
    );
    const canLaunch = !isRunning && personas.length >= 2 && !hasIncomplete;

    return (
      <div className="flex flex-col h-full min-h-0 bg-background/50 overflow-y-auto p-4 sm:p-6 scrollbar-thin">
        <div className="max-w-4xl w-full mx-auto space-y-5 pb-8">
          <div className="text-center space-y-1.5">
            <Badge
              variant="outline"
              className="border-teal-500/30 text-teal-700 dark:text-teal-300 px-2.5 py-0.5"
            >
              <Sparkles className="w-3 h-3 mr-1 text-teal-500" />
              Deliberation Session Setup
            </Badge>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
              Configure Autonomous Deliberation
            </h1>
            <p className="text-xs text-muted-foreground max-w-lg mx-auto">
              Select a debate topic, establish your panel of stakeholder
              personas, and configure communication edges.
            </p>
          </div>

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

          {/* Topic */}
          <Card className="p-4 bg-card border-border/80 shadow-xs space-y-3">
            <span className="text-xs font-bold uppercase tracking-wider text-teal-700 dark:text-teal-400 flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5" />
              1. Deliberation Topic
            </span>

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
                        <CheckCircle2 className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />
                      )}
                    </div>
                    <p className="text-xs font-medium line-clamp-2 leading-snug">
                      {pt.title}
                    </p>
                  </div>
                );
              })}
            </div>

            <textarea
              rows={2}
              value={topic}
              onChange={(e) => onUpdateTopic(e.target.value)}
              placeholder="Or enter a custom AI regulation topic..."
              className="w-full text-xs p-2.5 rounded-md bg-background border border-border/80 text-foreground focus:outline-none focus:ring-1 focus:ring-teal-500 resize-none"
            />
          </Card>

          {/* Topology */}
          <Card className="p-4 bg-card border-border/80 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 dark:text-teal-400 flex items-center gap-1.5">
                <Network className="w-3.5 h-3.5" />
                2. Communication Topology
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowMatrixEditor((v) => !v)}
                className="h-6 text-[10px] text-teal-700 dark:text-teal-300 cursor-pointer"
              >
                {showMatrixEditor ? "Hide Matrix" : "Customize Edge Visibility"}
              </Button>
            </div>

            <div className="flex items-center gap-2">
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
                  Directed Ring (A → B → C)
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
                  Full Mesh (All-to-All)
                </button>
              </div>
              {topologyMode === "custom" && (
                <Badge
                  variant="outline"
                  className="text-[9px] border-amber-500 text-amber-600"
                >
                  Custom Edge Matrix
                </Badge>
              )}
            </div>

            {showMatrixEditor && personas.length >= 2 && (
              <div className="p-3 bg-muted/20 border border-border/60 rounded-md overflow-x-auto">
                <table className="w-full text-[10px]">
                  <thead>
                    <tr className="border-b border-border/50 text-muted-foreground">
                      <th className="p-1 text-left">Listener</th>
                      {personas.map((s, idx) => (
                        <th
                          key={idx}
                          className="p-1 text-center truncate max-w-[80px]"
                        >
                          {(s.name || `P${idx + 1}`).split(" ")[0]}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {personas.map((listener, lIdx) => {
                      const lName = listener.name.trim() || `Agent ${lIdx + 1}`;
                      return (
                        <tr key={lIdx} className="border-b border-border/30">
                          <td className="p-1 font-semibold">{lName}</td>
                          {personas.map((speaker, sIdx) => {
                            const sName =
                              speaker.name.trim() || `Agent ${sIdx + 1}`;
                            if (sName === lName)
                              return (
                                <td
                                  key={sIdx}
                                  className="p-1 text-center opacity-30"
                                >
                                  —
                                </td>
                              );
                            const isAllowed = (
                              activeVisibilityMatrix[lName] || []
                            ).includes(sName);
                            return (
                              <td key={sIdx} className="p-1 text-center">
                                <button
                                  type="button"
                                  onClick={() => toggleVisibility(lName, sName)}
                                  className={`p-1 rounded cursor-pointer ${isAllowed ? "text-emerald-600 bg-emerald-500/10" : "text-rose-500 bg-rose-500/10"}`}
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
            )}
          </Card>

          {/* Stakeholders */}
          <Card className="p-4 bg-card border-border/80 shadow-xs space-y-3.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-teal-700 dark:text-teal-400 flex items-center gap-1.5">
                <Bot className="w-3.5 h-3.5" />
                3. Stakeholder Personas ({personas.length}/5)
              </span>

              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1 bg-muted/60 p-0.5 rounded-md border border-border/70">
                  {[2, 3, 4, 5].map((cnt) => (
                    <button
                      key={cnt}
                      type="button"
                      onClick={() => handleSetAgentCount(cnt)}
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold cursor-pointer ${
                        personas.length === cnt
                          ? "bg-teal-600 text-white"
                          : "text-muted-foreground"
                      }`}
                    >
                      {cnt}
                    </button>
                  ))}
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={personas.length >= 5}
                  onClick={() => handleSetAgentCount(personas.length + 1)}
                  className="h-7 text-xs cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5 mr-1" /> Add
                </Button>
              </div>
            </div>

            <div className="flex gap-2 p-2 rounded-lg bg-teal-50/40 dark:bg-teal-950/20 border border-teal-500/30">
              <input
                type="text"
                value={llmPrompt}
                onChange={(e) => setLlmPrompt(e.target.value)}
                placeholder="Optional AI prompt: e.g. Open source researcher vs EU AI compliance officer..."
                className="flex-1 text-xs px-3 py-1.5 rounded-md bg-background border border-border text-foreground"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={handleGenerateWithAI}
                disabled={isGeneratingPersonas}
                className="text-xs bg-teal-600 text-white hover:bg-teal-700 shrink-0 cursor-pointer"
              >
                <Wand2 className="w-3.5 h-3.5 mr-1" />
                {isGeneratingPersonas ? "Generating..." : "Generate with AI"}
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              {personas.map((persona, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-card border border-border flex flex-col gap-2 shadow-2xs"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <Avatar className="w-8 h-8 border border-teal-500/30 shrink-0">
                        <AvatarImage
                          src={getAvatarPath(idx)}
                          alt={persona.name || `Agent ${idx + 1}`}
                        />
                        <AvatarFallback>
                          {(persona.name || `A${idx + 1}`).substring(0, 2)}
                        </AvatarFallback>
                      </Avatar>
                      <input
                        type="text"
                        value={persona.name}
                        onChange={(e) => {
                          const u = [...personas];
                          u[idx] = { ...u[idx], name: e.target.value };
                          onUpdatePersonas(u);
                        }}
                        placeholder={`Agent ${idx + 1} Name...`}
                        className="w-full text-xs font-bold bg-transparent border-b border-border focus:border-teal-500 focus:outline-none"
                      />
                    </div>
                    {personas.length > 2 && (
                      <button
                        onClick={() =>
                          onUpdatePersonas(personas.filter((_, i) => i !== idx))
                        }
                        className="text-muted-foreground hover:text-destructive p-1 cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  <textarea
                    rows={2}
                    value={persona.background}
                    onChange={(e) => {
                      const u = [...personas];
                      u[idx] = { ...u[idx], background: e.target.value };
                      onUpdatePersonas(u);
                    }}
                    placeholder="Background & professional affiliation..."
                    className="w-full text-xs p-2 rounded-lg bg-muted/20 border border-border/50 focus:outline-none resize-none"
                  />

                  <div className="flex items-center gap-1.5 text-[10px]">
                    <span className="text-muted-foreground font-medium">
                      Tone:
                    </span>
                    <input
                      type="text"
                      value={persona.tone}
                      onChange={(e) => {
                        const u = [...personas];
                        u[idx] = { ...u[idx], tone: e.target.value };
                        onUpdatePersonas(u);
                      }}
                      className="flex-1 bg-transparent border-b border-border/40 focus:outline-none text-[10px]"
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Button
            onClick={() =>
              onStartSimulation({
                memoryStrategy: { type: globalMemoryType, window_size: 4 },
                visibilityMatrix: activeVisibilityMatrix,
              })
            }
            disabled={!canLaunch}
            className="w-full h-11 text-sm font-semibold bg-teal-600 hover:bg-teal-700 text-white shadow-md disabled:opacity-40 cursor-pointer"
          >
            <Play className="w-4 h-4 mr-2 fill-current" />
            {isRunning
              ? "Starting Session..."
              : `Start Simulation (${personas.length} Agents)`}
          </Button>
        </div>
      </div>
    );
  }

  // =========================================================================
  // VIEW 2: ARENA VIEW (FORMATTED CITATIONS & FOOTNOTES)
  // =========================================================================
  return (
    <>
      <div className="flex flex-col h-full min-h-0 bg-background/50 overflow-hidden">
        {/* Header */}
        <div className="p-3 border-b border-border/50 flex items-center justify-between bg-background/80 backdrop-blur-sm shrink-0">
          <div className="min-w-0 flex-1 pr-2">
            <div className="flex items-center gap-2">
              <Radio
                className={`w-3.5 h-3.5 ${isRunning ? "text-teal-500 animate-pulse" : "text-muted-foreground"}`}
              />
              <h2 className="text-xs font-bold uppercase tracking-wider text-foreground">
                Deliberation Arena
              </h2>
              <Badge
                variant="outline"
                className="border-teal-500/30 text-teal-700 dark:text-teal-300 font-mono text-[9px]"
              >
                Round {currentRound}
              </Badge>
            </div>
            <p className="text-[11px] text-muted-foreground truncate mt-0.5">
              {topic}
            </p>
          </div>

          <div className="hidden md:flex items-center gap-1 mr-2">
            <button
              onClick={() => setSelectedAgentFilter(null)}
              style={{ cursor: "pointer" }}
              className={`px-2 py-0.5 rounded text-[10px] font-medium transition-all cursor-pointer ${
                selectedAgentFilter === null
                  ? "bg-teal-600 text-white"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              All Turns
            </button>
            {personas.map((p) => (
              <button
                key={p.name}
                onClick={() =>
                  setSelectedAgentFilter(
                    selectedAgentFilter === p.name ? null : p.name,
                  )
                }
                style={{ cursor: "pointer" }}
                className={`px-2 py-0.5 rounded text-[10px] font-medium transition-all cursor-pointer ${
                  selectedAgentFilter === p.name
                    ? "bg-teal-600 text-white"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                title={p.name}
              >
                {/* Full name without .split(" ")[0] */}
                {p.name || "Agent"}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1.5">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowSessionDetails(true)}
              className="h-7 text-xs border-border/80 cursor-pointer"
            >
              <Info className="w-3.5 h-3.5 mr-1 text-teal-600 dark:text-teal-400" />
              Session Info
            </Button>
          </div>
        </div>

        {/* Turn Feed */}
        <div
          ref={turnsScrollRef}
          className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4 scrollbar-thin"
        >
          <div className="space-y-4 max-w-3xl mx-auto pb-6">
            {!isRunning && filteredTurns.length === 0 && (
              <div className="py-16 text-center space-y-2 text-muted-foreground">
                <Bot className="w-8 h-8 mx-auto opacity-40 text-teal-600" />
                <p className="text-sm font-medium text-foreground">
                  No deliberation turns recorded yet
                </p>
                <p className="text-xs">
                  Click &quot;Next Turn (+1)&quot; below to begin the debate.
                </p>
              </div>
            )}

            {filteredTurns.map((turn) => {
              const stance = turn.opinion_snapshot?.current_stance_score ?? 0;
              const shift = turn.opinion_snapshot?.shift_magnitude ?? 0;
              const cfg = turn.opinion_snapshot?.cfg;
              const avatar = getAgentAvatar(turn.agent_name);

              // Parse citations out of text and build structured inline links + references
              const { formattedParts, references } = parseAndFormatContent(
                turn.content || "",
                turn.retrieved_sources || [],
              );

              return (
                <div
                  key={turn.id}
                  className="flex items-start gap-3 group animate-in fade-in duration-200"
                >
                  <Avatar className="w-9 h-9 border border-teal-500/20 shrink-0 mt-0.5">
                    <AvatarImage src={avatar} alt={turn.agent_name} />
                    <AvatarFallback>
                      {(turn.agent_name || "AG").substring(0, 2)}
                    </AvatarFallback>
                  </Avatar>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-bold text-foreground">
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
                        {stance > 0
                          ? `+${stance.toFixed(1)}`
                          : stance.toFixed(1)}
                      </Badge>
                    </div>

                    {turn.tools_called && turn.tools_called.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-1.5">
                        {turn.tools_called.map((tool, idx) => (
                          <Badge
                            key={idx}
                            variant="outline"
                            className="text-[9px] text-teal-700 dark:text-teal-300 font-mono"
                          >
                            <Terminal className="w-2.5 h-2.5 mr-1" />
                            {tool.name}
                          </Badge>
                        ))}
                      </div>
                    )}

                    <Card className="p-3.5 bg-card border-border/80 text-xs leading-relaxed text-foreground rounded-tl-none shadow-xs">
                      <div>{formattedParts}</div>

                      {/* Clean References Footer */}
                      {references.length > 0 && (
                        <div className="mt-3 pt-2.5 border-t border-border/50 space-y-1.5">
                          <span className="text-[9.5px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                            <BookOpen className="w-3 h-3 text-teal-600 dark:text-teal-400" />
                            Cited Sources & Evidence ({references.length})
                          </span>
                          <div className="grid grid-cols-1 gap-1">
                            {references.map((ref) => (
                              <a
                                key={ref.index}
                                href={ref.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-1.5 p-1.5 rounded bg-muted/40 hover:bg-teal-50 dark:hover:bg-teal-950/50 text-[10.5px] text-teal-700 dark:text-teal-300 transition-colors border border-border/40 group/link"
                              >
                                <span className="font-mono font-bold text-teal-600 dark:text-teal-400 text-[9.5px] shrink-0">
                                  [{ref.index}]
                                </span>
                                <span className="font-semibold text-foreground truncate max-w-[140px]">
                                  {ref.domain}
                                </span>
                                {ref.locator && (
                                  <span className="px-1 py-0.2 text-[9px] font-mono bg-teal-500/10 text-teal-600 dark:text-teal-400 rounded border border-teal-500/20 shrink-0">
                                    {ref.locator}
                                  </span>
                                )}
                                <span className="text-muted-foreground truncate flex-1 text-[10px]">
                                  {ref.path || "/"}
                                </span>
                                <ExternalLink className="w-3 h-3 text-muted-foreground group-hover/link:text-teal-600 shrink-0" />
                              </a>
                            ))}
                          </div>
                        </div>
                      )}
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
                          {shift > 0
                            ? `+${shift.toFixed(2)}`
                            : shift.toFixed(2)}
                        </span>
                        <span>•</span>
                        <span>
                          γ: {cfg.guidance_scale_gamma?.toFixed(2) || "0.00"}
                        </span>
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

            {/* Live Streaming Box */}
            {isRunning && liveState && (
              <div className="flex items-start gap-3 border-l-2 border-teal-500 pl-3 py-1 animate-in fade-in">
                <Avatar className="w-9 h-9 border-2 border-teal-500 animate-pulse shrink-0">
                  <AvatarImage
                    src={getAgentAvatar(liveState.speaker)}
                    alt={liveState.speaker}
                  />
                  <AvatarFallback>
                    {(liveState.speaker || "SP").substring(0, 2)}
                  </AvatarFallback>
                </Avatar>

                <div className="flex-1 min-w-0 space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-teal-600 dark:text-teal-400 flex items-center gap-1">
                      <Radio className="w-3 h-3 animate-ping" />
                      {liveState.speaker} is deliberating...
                    </span>
                    <Badge variant="outline" className="text-[9px] font-mono">
                      Round {liveState.round}
                    </Badge>
                  </div>

                  {liveState.thinking && (
                    <div className="rounded-lg bg-teal-950/20 border border-teal-500/30 p-2 text-xs">
                      <div
                        onClick={() => setShowThinkingPanel((v) => !v)}
                        className="flex items-center justify-between text-[10px] font-semibold text-teal-600 dark:text-teal-400 cursor-pointer select-none"
                      >
                        <span className="flex items-center gap-1">
                          <Brain className="w-3 h-3" />
                          Inner Reasoning / Thought Stream
                        </span>
                        {showThinkingPanel ? (
                          <ChevronUp className="w-3 h-3" />
                        ) : (
                          <ChevronDown className="w-3 h-3" />
                        )}
                      </div>
                      {showThinkingPanel && (
                        <p className="mt-1.5 text-[11px] text-muted-foreground font-mono whitespace-pre-wrap leading-tight max-h-32 overflow-y-auto">
                          {liveState.thinking}
                        </p>
                      )}
                    </div>
                  )}

                  {liveState.toolCall && (
                    <div className="flex items-center gap-2 p-1.5 rounded-md bg-muted/60 border border-border text-[10px] font-mono text-teal-700 dark:text-teal-300">
                      <Terminal className="w-3 h-3 animate-spin" />
                      <span>Executing Tool: {liveState.toolCall.name}</span>
                      {liveState.toolCall.status === "done" && (
                        <span className="text-emerald-600 font-bold ml-auto">
                          Done
                        </span>
                      )}
                    </div>
                  )}

                  <Card className="p-3.5 bg-card/90 border-teal-500/40 text-xs leading-relaxed rounded-tl-none min-h-[50px] shadow-sm">
                    {liveState.tokens ? (
                      <span className="whitespace-pre-wrap">
                        {parseAndFormatContent(liveState.tokens).formattedParts}
                      </span>
                    ) : (
                      <span className="text-muted-foreground italic flex items-center gap-1">
                        <Sparkles className="w-3 h-3 animate-pulse" />{" "}
                        Formulating response...
                      </span>
                    )}
                  </Card>
                </div>
              </div>
            )}

            {/* Steer / Next Turn CTA */}
            {!isRunning && turns.length > 0 && (
              <div className="p-4 rounded-xl bg-teal-50/70 dark:bg-teal-950/30 border border-teal-500/30 space-y-3 animate-in fade-in">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="relative flex h-2.5 w-2.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-teal-500" />
                    </span>
                    <span className="text-xs font-bold text-teal-950 dark:text-teal-200">
                      Ready for Round {currentRound + 1}
                    </span>
                  </div>
                  <span className="text-[10px] text-muted-foreground font-mono">
                    All agents listened • Next speaker queued
                  </span>
                </div>

                <div className="flex gap-2">
                  <input
                    type="text"
                    value={interventionInput}
                    onChange={(e) => setInterventionInput(e.target.value)}
                    onKeyDown={(e) =>
                      e.key === "Enter" && handleSendIntervention()
                    }
                    placeholder="Optional: Steer debate with custom counter-argument or prompt..."
                    className="flex-1 text-xs px-3 py-1.5 rounded-md bg-background border border-border/80 focus:outline-none focus:ring-1 focus:ring-teal-500"
                  />
                  <Button
                    size="sm"
                    onClick={handleSendIntervention}
                    disabled={!interventionInput.trim() || isRunning}
                    className="h-8 px-3 text-xs bg-teal-700 hover:bg-teal-800 text-white cursor-pointer"
                  >
                    <Send className="w-3 h-3 mr-1" />
                    Inject & Step
                  </Button>
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <Button
                    onClick={() => onStepTurn(1)}
                    className="flex-1 h-9 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold shadow-xs cursor-pointer"
                  >
                    <Play className="w-3.5 h-3.5 mr-1.5 fill-current" />
                    Continue Debate (Next Turn)
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => onStepTurn(3)}
                    className="h-9 px-3 text-xs border-teal-500/40 text-teal-700 dark:text-teal-300 hover:bg-teal-50 dark:hover:bg-teal-950/50 cursor-pointer"
                  >
                    <FastForward className="w-3 h-3 mr-1" />
                    Advance +3 Turns
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Persistent Bottom Bar */}
        <div className="p-3 border-t border-border/60 bg-background/90 backdrop-blur flex items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-1.5">
            <Button
              size="sm"
              onClick={() => onStepTurn(1)}
              disabled={isRunning}
              className="h-8 px-3.5 text-xs bg-teal-600 hover:bg-teal-700 text-white font-medium cursor-pointer disabled:opacity-50"
            >
              <Play className="w-3 h-3 mr-1.5 fill-current" />
              {isRunning ? "Deliberating..." : "Next Turn (+1)"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onStepTurn(3)}
              disabled={isRunning}
              className="h-8 px-2.5 text-xs border-teal-500/30 text-teal-700 dark:text-teal-300 hover:bg-teal-50 dark:hover:bg-teal-950/40 cursor-pointer disabled:opacity-50"
            >
              <FastForward className="w-3 h-3 mr-1" />
              +3 Turns
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onStepTurn(5)}
              disabled={isRunning}
              className="h-8 px-2.5 text-xs border-teal-500/30 text-teal-700 dark:text-teal-300 hover:bg-teal-50 dark:hover:bg-teal-950/40 cursor-pointer disabled:opacity-50"
            >
              +5 Turns
            </Button>
          </div>

          <span className="text-[10px] text-muted-foreground font-mono">
            {turns.length} turns recorded • Topology:{" "}
            {topologyMode.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Session Details Modal */}
      {showSessionDetails && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="max-w-lg w-full rounded-xl bg-card border border-border p-5 shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-border/50 pb-2.5">
              <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
                <Info className="w-4 h-4 text-teal-600 dark:text-teal-400" />
                Active Session Details
              </h3>
              <button
                onClick={() => setShowSessionDetails(false)}
                className="text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <span className="font-semibold text-muted-foreground text-[10px] uppercase tracking-wider block">
                  Topic
                </span>
                <p className="text-foreground font-medium mt-0.5">{topic}</p>
              </div>

              <div>
                <span className="font-semibold text-muted-foreground text-[10px] uppercase tracking-wider block mb-1">
                  Stakeholders ({personas.length})
                </span>
                <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                  {personas.map((p, idx) => (
                    <div
                      key={idx}
                      className="p-2 rounded bg-muted/40 border border-border/50 flex items-start gap-2"
                    >
                      <Avatar className="w-6 h-6 border border-teal-500/30 shrink-0 mt-0.5">
                        <AvatarImage src={getAvatarPath(idx)} alt={p.name} />
                        <AvatarFallback>
                          {(p.name || "A").substring(0, 2)}
                        </AvatarFallback>
                      </Avatar>
                      <div className="min-w-0 flex-1">
                        <p className="font-bold text-foreground truncate">
                          {p.name}
                        </p>
                        <p className="text-[11px] text-muted-foreground leading-tight">
                          {p.background}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <span className="font-semibold text-muted-foreground text-[10px] uppercase tracking-wider block mb-1">
                  Listening Matrix
                </span>
                <div className="p-2 rounded bg-muted/30 border border-border/40 text-[11px]">
                  {personas.map((listener, i) => {
                    const lName = listener.name || `Agent ${i + 1}`;
                    const allowed = activeVisibilityMatrix[lName] || [];
                    return (
                      <div
                        key={i}
                        className="flex items-center justify-between py-0.5"
                      >
                        <span className="font-semibold">{lName} hears:</span>
                        <span className="text-muted-foreground font-mono">
                          {allowed.length > 0 ? allowed.join(", ") : "None"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-2 border-t border-border/50">
              <Button
                size="sm"
                onClick={() => setShowSessionDetails(false)}
                className="text-xs h-8 bg-teal-600 hover:bg-teal-700 text-white cursor-pointer"
              >
                Close Inspector
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
