"use client";

import React from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Globe,
  Database,
  Sparkles,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";
import { DiscussionTurn } from "@/types/simulation";

interface DebateArenaProps {
  turns: DiscussionTurn[];
}

export const DebateArena: React.FC<DebateArenaProps> = ({ turns }) => {
  return (
    <div className="flex flex-col h-full bg-background/50">
      {/* Arena Header */}
      <div className="p-4 border-b border-border/40 flex items-center justify-between backdrop-blur">
        <div>
          <h2 className="text-sm font-semibold tracking-wide flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-cyan-400" />
            Live Deliberation Arena
          </h2>
          <p className="text-xs text-muted-foreground">
            Autonomous turn-taking with dynamic tool calls
          </p>
        </div>
        <Badge variant="outline" className="border-cyan-500/30 text-cyan-400">
          Round {turns.length > 0 ? turns[turns.length - 1].round_number : 0}
        </Badge>
      </div>

      {/* Chat Messages */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4 max-w-3xl mx-auto">
          {turns.map((turn) => {
            const stance = turn.opinion_snapshot.current_stance_score;
            const shift = turn.opinion_snapshot.shift_magnitude;
            const cfg = turn.opinion_snapshot.cfg;

            return (
              <div key={turn.id} className="flex items-start gap-3 group">
                <Avatar className="w-9 h-9 border border-border">
                  <AvatarImage
                    src={`https://api.dicebear.com/7.x/bottts/svg?seed=${encodeURIComponent(
                      turn.agent_name,
                    )}`}
                    alt={turn.agent_name}
                  />
                  <AvatarFallback>
                    {turn.agent_name.substring(0, 2)}
                  </AvatarFallback>
                </Avatar>

                <div className="flex-1 min-w-0">
                  {/* Speaker Meta & Stance Badge */}
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-semibold text-foreground">
                      {turn.agent_name}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      Round {turn.round_number}
                    </span>

                    {/* Stance Pill */}
                    <Badge
                      variant="secondary"
                      className={`text-[10px] font-mono ml-auto ${
                        stance > 0
                          ? "bg-emerald-950/60 text-emerald-400 border-emerald-800"
                          : stance < 0
                            ? "bg-rose-950/60 text-rose-400 border-rose-800"
                            : "bg-muted text-muted-foreground"
                      }`}
                    >
                      Stance:{" "}
                      {stance > 0 ? `+${stance.toFixed(1)}` : stance.toFixed(1)}
                    </Badge>
                  </div>

                  {/* Tool Usage Badges (ReAct indicators) */}
                  {turn.tools_called && turn.tools_called.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {turn.tools_called.map((tool, idx) => (
                        <Badge
                          key={idx}
                          variant="outline"
                          className="text-[10px] bg-background/80 text-cyan-300 border-cyan-500/30 flex items-center gap-1 py-0.5"
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

                  {/* Message Bubble */}
                  <Card className="p-3.5 bg-card/60 border-border/50 text-xs leading-relaxed text-foreground/90 rounded-tl-none">
                    {turn.content}
                  </Card>

                  {/* CFG / Opinion Shift Feedback Footer */}
                  {cfg && (
                    <div className="mt-1.5 flex items-center gap-2 text-[10px] text-muted-foreground px-1 font-mono">
                      <span className="flex items-center gap-1">
                        {shift > 0 ? (
                          <TrendingUp className="w-3 h-3 text-emerald-400" />
                        ) : shift < 0 ? (
                          <TrendingDown className="w-3 h-3 text-rose-400" />
                        ) : (
                          <Minus className="w-3 h-3 text-muted-foreground" />
                        )}
                        Δ{" "}
                        {shift > 0 ? `+${shift.toFixed(2)}` : shift.toFixed(2)}
                      </span>
                      <span>•</span>
                      <span>CFG γ: {cfg.guidance_scale_gamma.toFixed(2)}</span>
                      <span>•</span>
                      <span className="text-cyan-400/90">{cfg.dynamic}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </ScrollArea>
    </div>
  );
};
