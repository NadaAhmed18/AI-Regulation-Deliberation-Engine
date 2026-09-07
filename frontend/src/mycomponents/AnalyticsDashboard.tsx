"use client";

import React from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { Activity, Compass, ExternalLink } from "lucide-react";
import { DiscussionTurn, Persona } from "@/types/simulation";

interface AnalyticsDashboardProps {
  turns: DiscussionTurn[];
  personas: Persona[];
}

export const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({
  turns,
  personas,
}) => {
  // Transform turns into time-series chart data
  const chartData = React.useMemo(() => {
    const roundsMap: Record<number, any> = {};

    turns.forEach((turn) => {
      const r = turn.round_number;
      if (!roundsMap[r]) {
        roundsMap[r] = { round: `R${r}` };
      }
      roundsMap[r][turn.agent_name] =
        turn.opinion_snapshot.current_stance_score;
    });

    return Object.values(roundsMap);
  }, [turns]);

  const colors = ["#06b6d4", "#f59e0b", "#ec4899", "#8b5cf6"];

  return (
    <div className="flex flex-col h-full gap-4 p-4 border-l border-border/40 bg-card/30 overflow-y-auto">
      {/* Chart: Stance Trajectory */}
      <Card className="border-border/60 bg-card/60">
        <CardHeader className="pb-2">
          <CardTitle className="text-xs font-semibold uppercase tracking-wider flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            Opinion Trajectory (-5 to +5)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={chartData}
                margin={{ top: 10, right: 10, left: -25, bottom: 0 }}
              >
                <XAxis
                  dataKey="round"
                  stroke="#64748b"
                  fontSize={10}
                  tickLine={false}
                />
                <YAxis
                  domain={[-5, 5]}
                  stroke="#64748b"
                  fontSize={10}
                  tickLine={false}
                />
                <ReferenceLine y={0} stroke="#334155" strokeDasharray="3 3" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0f172a",
                    borderColor: "#334155",
                    fontSize: "11px",
                  }}
                />
                {personas.map((p, idx) => (
                  <Line
                    key={p.name}
                    type="monotone"
                    dataKey={p.name}
                    stroke={colors[idx % colors.length]}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* CFG Guidance & Persuasion Dynamics */}
      <Card className="border-border/60 bg-card/60">
        <CardHeader className="pb-2">
          <CardTitle className="text-xs font-semibold uppercase tracking-wider flex items-center gap-2">
            <Compass className="w-4 h-4 text-amber-400" />
            CFG Guidance & Persuasion
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2.5">
          {turns
            .slice(-3)
            .reverse()
            .map((turn) => {
              const cfg = turn.opinion_snapshot.cfg;
              if (!cfg) return null;

              return (
                <div
                  key={turn.id}
                  className="p-2 rounded bg-background/50 border border-border/40 text-xs"
                >
                  <div className="flex justify-between items-center font-medium">
                    <span className="truncate text-foreground/90">
                      {turn.agent_name}
                    </span>
                    <span
                      className={`text-[10px] font-mono ${cfg.guidance_scale_gamma < 0 ? "text-rose-400" : "text-cyan-400"}`}
                    >
                      γ = {cfg.guidance_scale_gamma.toFixed(2)}
                    </span>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {cfg.dynamic}
                  </p>
                </div>
              );
            })}
        </CardContent>
      </Card>

      {/* Sources Feed */}
      <Card className="border-border/60 bg-card/60 flex-1">
        <CardHeader className="pb-2">
          <CardTitle className="text-xs font-semibold uppercase tracking-wider flex items-center gap-2">
            <ExternalLink className="w-4 h-4 text-cyan-400" />
            Cited Knowledge & URLs
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1.5 text-xs text-muted-foreground">
          <p className="text-[11px] truncate text-cyan-400/80 hover:underline cursor-pointer">
            https://en.wikipedia.org/wiki/Artificial_Intelligence_Act
          </p>
          <p className="text-[11px] truncate text-cyan-400/80 hover:underline cursor-pointer">
            https://mcit.gov.eg/en/Artificial_Intelligence
          </p>
        </CardContent>
      </Card>
    </div>
  );
};
