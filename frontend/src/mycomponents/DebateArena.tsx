"use client";

import React, { useState, useEffect } from "react";
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
} from "lucide-react";
import { DiscussionTurn, Persona, PredefinedTopic } from "@/types/simulation";
import { SimulationAPI, getAvatarPath } from "@/lib/api";

interface DebateArenaProps {
  turns: DiscussionTurn[];
  personas: Persona[];
  topic: string;
  isRunning: boolean;
  isConfiguring: boolean;
  onStartSimulation: () => void;
  onUpdateTopic: (topic: string) => void;
  onUpdatePersonas: (personas: Persona[]) => void;
  onContinueSimulation: (interventionPrompt?: string) => Promise<void>;
  onOpenConfig: () => void;
}

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

  // Custom Persona Form State
  const [showCustomPersonaForm, setShowCustomPersonaForm] = useState(false);
  const [customName, setCustomName] = useState("");
  const [customBackground, setCustomBackground] = useState("");
  const [customTone, setCustomTone] = useState("");

  // Intervention State
  const [interventionText, setInterventionText] = useState("");
  const [isContinuing, setIsContinuing] = useState(false);

  useEffect(() => {
    SimulationAPI.getPredefinedTopics()
      .then(setPredefinedTopics)
      .catch((err) => console.error("Failed to load topics:", err));
  }, []);

  // Handler: Selecting a predefined topic updates topic WITHOUT clearing existing custom personas
  const handleTopicSelect = (newTopic: string) => {
    onUpdateTopic(newTopic);
  };

  // Handler: Explicitly regenerate personas for current topic & count
  const handleRegenerateForTopic = async (count: number) => {
    setIsGeneratingPersonas(true);
    try {
      const generated = await SimulationAPI.generatePersonas(
        topic,
        count,
        llmPrompt,
      );
      onUpdatePersonas(generated);
    } catch (err) {
      console.error("Failed to generate personas:", err);
    } finally {
      setIsGeneratingPersonas(false);
    }
  };

  // Handler: Add Custom Persona (capped at 6)
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
    };

    onUpdatePersonas([...personas, newPersona]);
    setCustomName("");
    setCustomBackground("");
    setCustomTone("");
    setShowCustomPersonaForm(false);
  };

  // Handler: Remove individual persona
  const handleRemovePersona = (indexToRemove: number) => {
    onUpdatePersonas(personas.filter((_, idx) => idx !== indexToRemove));
  };

  // Handler: Continue debate
  const handleContinue = async () => {
    if (isContinuing) return;
    setIsContinuing(true);
    try {
      await onContinueSimulation(interventionText);
      setInterventionText("");
    } finally {
      setIsContinuing(false);
    }
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
      <div className="flex flex-col h-full bg-background/50 overflow-y-auto p-6 scrollbar-thin">
        <div className="max-w-3xl w-full mx-auto space-y-6">
          {/* Header */}
          <div className="text-center space-y-2">
            <Badge
              variant="outline"
              className="border-teal-500/30 text-teal-700 dark:text-teal-300 px-2.5 py-0.5"
            >
              <Sparkles className="w-3 h-3 mr-1 text-teal-500" />
              Graph Deliberation Engine
            </Badge>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Configure Autonomous Debate
            </h1>
            <p className="text-xs text-muted-foreground max-w-lg mx-auto">
              Select or formulate a topic, configure 2 to 6 stakeholder nodes,
              and start the graph-grounded debate.
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
                Personas stay saved when changing topic
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {predefinedTopics.map((pt) => {
                const isSelected = topic === pt.title;
                return (
                  <div
                    key={pt.id}
                    onClick={() => handleTopicSelect(pt.title)}
                    className={`p-2.5 rounded-lg border text-left cursor-pointer transition-all ${
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
                placeholder="Type any AI regulation or governance question..."
                className="w-full text-xs p-2.5 rounded-md bg-background border border-border/80 text-foreground focus:outline-none focus:ring-1 focus:ring-teal-500 transition-all resize-none"
              />
            </div>
          </Card>

          {/* 2. Stakeholders Management (Limit: 2 to 6) */}
          <Card className="p-4 bg-card border-border/80 shadow-xs space-y-3.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-bold uppercase tracking-wider text-teal-700 dark:text-teal-400 flex items-center gap-1.5">
                  <Bot className="w-3.5 h-3.5" />
                  2. Stakeholder Personas ({personas.length}/6 Nodes)
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
                {/* Agent Count Selector (Supports 2, 3, 4, 5, 6) */}
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
                      title={`Generate ${count} stakeholders`}
                    >
                      {count}
                    </button>
                  ))}
                </div>

                {/* Custom Persona Button (Disabled when 6 reached) */}
                <Button
                  size="sm"
                  variant="outline"
                  disabled={personas.length >= 6}
                  onClick={() => setShowCustomPersonaForm((prev) => !prev)}
                  className="h-7 px-2 text-xs border-teal-500/40 text-teal-700 dark:text-teal-300 hover:bg-teal-50 dark:hover:bg-teal-950/40 cursor-pointer disabled:opacity-50"
                  title={
                    personas.length >= 6
                      ? "Max 6 personas reached"
                      : "Add custom persona"
                  }
                >
                  <UserPlus className="w-3.5 h-3.5 mr-1" />
                  Custom
                </Button>
              </div>
            </div>

            {/* Custom Persona Form */}
            {showCustomPersonaForm && (
              <form
                onSubmit={handleAddCustomPersona}
                className="p-3 rounded-lg bg-teal-50/50 dark:bg-teal-950/30 border border-teal-500/30 space-y-2.5 animate-in fade-in duration-200"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-teal-800 dark:text-teal-300 flex items-center gap-1.5">
                    <UserPlus className="w-3 h-3" />
                    Add Custom Stakeholder Persona ({personas.length}/6)
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowCustomPersonaForm(false)}
                    className="text-muted-foreground hover:text-foreground p-0.5 cursor-pointer"
                  >
                    <X className="w-3 h-3" />
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
                      placeholder="e.g. Hardware Security Officer, Confidential Computing Consortium"
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
                      placeholder="Tone (e.g. Skeptical, rigorous, empirical)"
                      value={customTone}
                      onChange={(e) => setCustomTone(e.target.value)}
                      className="w-full text-xs px-2.5 py-1.5 rounded-md bg-background border border-border/80 text-foreground focus:outline-none focus:ring-1 focus:ring-teal-500"
                    />
                  </div>
                  <Button
                    type="submit"
                    size="sm"
                    className="h-7 text-xs bg-teal-600 hover:bg-teal-700 text-white dark:bg-teal-500 dark:text-teal-950 cursor-pointer"
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
                placeholder="Give prompt to LLM (e.g., 'Include an open-source hacker and an EU AI Act auditor')..."
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
                {isGeneratingPersonas ? "Generating..." : "Generate with LLM"}
              </Button>
            </div>

            {/* Persona Preview Cards (Without Stance) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 pt-1">
              {personas.map((persona, idx) => (
                <div
                  key={`${persona.name}-${idx}`}
                  className="p-2.5 rounded-md bg-muted/30 border border-border/60 flex flex-col justify-between gap-2 group relative transition-all hover:border-teal-500/30"
                >
                  <div className="flex items-start gap-2">
                    <Avatar className="w-9 h-9 border border-teal-500/30 shrink-0">
                      <AvatarImage
                        src={getAvatarPath(idx)}
                        alt={persona.name}
                      />
                      <AvatarFallback>
                        {persona.name.substring(0, 2)}
                      </AvatarFallback>
                    </Avatar>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-semibold text-foreground truncate">
                          {persona.name}
                        </h4>
                        <button
                          onClick={() => handleRemovePersona(idx)}
                          className="opacity-0 group-hover:opacity-100 hover:text-destructive hover:bg-destructive/10 p-1 rounded transition-all text-muted-foreground cursor-pointer"
                          title="Remove persona"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                      <Badge
                        variant="secondary"
                        className="text-[9px] px-1 py-0 h-3.5 bg-muted text-muted-foreground border-none font-normal"
                      >
                        {persona.tone}
                      </Badge>
                    </div>
                  </div>

                  <p className="text-[11px] text-foreground/80 leading-snug line-clamp-2 bg-background/60 p-1.5 rounded border border-border/40">
                    {persona.background}
                  </p>
                </div>
              ))}
            </div>

            {/* Minimum 2 Warning Notice */}
            {personas.length < 2 && (
              <div className="p-2 rounded-md bg-rose-50 dark:bg-rose-950/30 border border-rose-500/30 flex items-center gap-2 text-rose-800 dark:text-rose-300 text-xs">
                <AlertCircle className="w-4 h-4 shrink-0 text-rose-600 dark:text-rose-400" />
                <span>
                  A multi-agent debate requires at least{" "}
                  <strong>2 agents</strong> (1 vs 1) to form graph communication
                  edges.
                </span>
              </div>
            )}
          </Card>

          {/* Launch Debate Action */}
          <div className="pt-2">
            <Button
              onClick={onStartSimulation}
              disabled={!canStart}
              className="w-full h-11 text-sm font-semibold bg-teal-600 hover:bg-teal-700 text-white dark:bg-teal-500 dark:hover:bg-teal-400 dark:text-teal-950 shadow-md transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Play className="w-4 h-4 mr-2 fill-current" />
              {isRunning
                ? "Starting Simulation..."
                : personas.length < 2
                  ? "At least 2 Agents Required to Start"
                  : `Start Graph Simulation (${personas.length} Agents)`}
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

      {/* Intervention Bar */}
      <div className="p-3 border-t border-border/60 bg-background/80 backdrop-blur">
        <div className="max-w-3xl mx-auto flex items-center gap-2">
          <input
            type="text"
            value={interventionText}
            onChange={(e) => setInterventionText(e.target.value)}
            disabled={isRunning || isContinuing}
            placeholder="Inject human intervention prompt (e.g. 'How would compute verification impact open-source startups?')..."
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
              <span>Expanding...</span>
            ) : (
              <>
                <PlusCircle className="w-3.5 h-3.5 mr-1" />
                <span>Continue Round</span>
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};
