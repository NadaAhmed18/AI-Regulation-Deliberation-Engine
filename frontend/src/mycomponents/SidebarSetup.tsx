"use client";

import React from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Bot, Play, Settings2 } from "lucide-react";
import { Persona } from "@/types/simulation";

interface SidebarSetupProps {
  personas: Persona[];
  topic: string;
  isRunning: boolean;
  onStart: () => void;
}

export const SidebarSetup: React.FC<SidebarSetupProps> = ({
  personas,
  topic,
  isRunning,
  onStart,
}) => {
  return (
    <div className="flex flex-col h-full gap-4 p-4 border-r border-border/40 bg-card/30">
      {/* Control Card */}
      <Card className="border-border/60 bg-card/60 backdrop-blur">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-cyan-400" />
            Debate Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <span className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">
              Topic
            </span>
            <p className="text-sm font-medium mt-1 leading-snug line-clamp-3 text-foreground/90">
              {topic}
            </p>
          </div>

          <Button
            onClick={onStart}
            disabled={isRunning}
            className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-medium"
          >
            <Play className="w-4 h-4 mr-2" />
            {isRunning ? "Debate in Progress..." : "Start Simulation"}
          </Button>
        </CardContent>
      </Card>

      {/* Stakeholder Personas Card */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs uppercase font-semibold text-muted-foreground flex items-center gap-1.5">
            <Bot className="w-3.5 h-3.5 text-cyan-400" />
            Stakeholder Nodes ({personas.length})
          </span>
          <Badge
            variant="outline"
            className="text-[10px] border-cyan-500/30 text-cyan-400"
          >
            Connected Mesh
          </Badge>
        </div>

        <div className="space-y-2.5 overflow-y-auto pr-1">
          {personas.map((persona) => (
            <Card
              key={persona.name}
              className="p-3 border-border/50 bg-background/50 hover:bg-accent/10 transition-colors"
            >
              <div className="flex items-start gap-3">
                <Avatar className="w-10 h-10 border border-cyan-500/20">
                  <AvatarImage
                    src={`https://api.dicebear.com/7.x/bottts/svg?seed=${encodeURIComponent(
                      persona.avatarSeed,
                    )}`}
                    alt={persona.name}
                  />
                  <AvatarFallback>
                    {persona.name.substring(0, 2)}
                  </AvatarFallback>
                </Avatar>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold truncate text-foreground">
                      {persona.name}
                    </h4>
                  </div>
                  <p className="text-[11px] text-muted-foreground line-clamp-1 mt-0.5">
                    {persona.background}
                  </p>
                  <div className="mt-2 text-[11px] bg-muted/40 p-1.5 rounded border border-border/30 text-foreground/80 line-clamp-2">
                    <span className="text-cyan-400 font-semibold">Stance:</span>{" "}
                    {persona.stance}
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
};
