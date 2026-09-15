"use client";

import React, { useState, useMemo, useRef } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import {
  Activity,
  GitGraph,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Move,
  ArrowRight,
  Scale,
  Award,
  Layers,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import {
  DiscussionTurn,
  Persona,
  SimulationAnalytics,
} from "@/types/simulation";
import { getAvatarPath } from "@/lib/api";

interface AnalyticsDashboardProps {
  analytics: SimulationAnalytics | null;
  turns: DiscussionTurn[];
  personas: Persona[];
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

const AGENT_COLORS = [
  "#0d9488",
  "#f59e0b",
  "#0284c7",
  "#e11d48",
  "#8b5cf6",
  "#10b981",
  "#f97316",
];

export const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({
  analytics,
  personas,
  isExpanded = false,
  onToggleExpand,
}) => {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({
    x: 0,
    y: 0,
  });

  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const graphNodes = useMemo(() => {
    const list = analytics?.nodes?.length
      ? analytics.nodes
      : personas.map((p, idx) => ({
          id: p.name || `agent-${idx}`,
          name: p.name || `Agent ${idx + 1}`,
          avatarUrl: getAvatarPath(idx),
          currentStance: 0,
          role: p.background,
        }));

    const total = list.length || 1;
    const centerX = isExpanded ? 240 : 165;
    const centerY = isExpanded ? 145 : 120;
    const radius = isExpanded ? (total >= 4 ? 110 : 95) : total >= 4 ? 80 : 70;

    return list.map((node, idx) => {
      const rawName = node.name || node.id || `Agent ${idx + 1}`;
      const name = String(rawName);
      const angle = -Math.PI / 2 + (2 * Math.PI * idx) / total;

      return {
        ...node,
        id: String(node.id || name),
        name,
        avatarUrl: node.avatarUrl || getAvatarPath(idx),
        currentStance:
          typeof node.currentStance === "number" ? node.currentStance : 0,
        index: idx,
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
        color: AGENT_COLORS[idx % AGENT_COLORS.length],
      };
    });
  }, [analytics, personas, isExpanded]);

  const nodeMap = useMemo(() => {
    const map = new Map<string, (typeof graphNodes)[0]>();
    graphNodes.forEach((n) => {
      map.set(n.name, n);
      map.set(n.id, n);
    });
    return map;
  }, [graphNodes]);

  const latestAgreement = useMemo(() => {
    if (!analytics?.agreement || analytics.agreement.length === 0) return null;
    return analytics.agreement[analytics.agreement.length - 1];
  }, [analytics]);

  const topInfluencer = analytics?.influence?.top_influencer || null;
  const influenceScores = analytics?.influence?.scores || {};
  const maxInfluenceScore = useMemo(() => {
    const vals = Object.values(influenceScores);
    return vals.length > 0 ? Math.max(...vals, 1) : 1;
  }, [influenceScores]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  };
  const handleMouseUp = () => setIsDragging(false);

  const scrollToSection = (id: string) => {
    const elem = document.getElementById(id);
    elem?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const viewBoxWidth = isExpanded ? 480 : 330;
  const viewBoxHeight = isExpanded ? 290 : 240;

  return (
    <aside className="relative flex flex-col h-full border-l border-border/70 bg-sidebar/50 text-sidebar-foreground select-none transition-all duration-300">
      {/* Explicit Hand Pointer on Toggle Button */}
      {onToggleExpand && (
        <button
          onClick={onToggleExpand}
          style={{ cursor: "pointer" }}
          className="group absolute top-1/2 -left-3.5 -translate-y-1/2 z-40 h-10 w-4 rounded-l-md bg-card border-y border-l border-border shadow-md hover:bg-teal-50 dark:hover:bg-teal-950/70 flex items-center justify-center cursor-pointer transition-all hover:w-5"
          title={isExpanded ? "Collapse Panel" : "Expand to 42%"}
        >
          {isExpanded ? (
            <ChevronRight
              style={{ pointerEvents: "none" }}
              className="w-3.5 h-3.5 text-muted-foreground group-hover:text-teal-600"
            />
          ) : (
            <ChevronLeft
              style={{ pointerEvents: "none" }}
              className="w-3.5 h-3.5 text-muted-foreground group-hover:text-teal-600"
            />
          )}
        </button>
      )}

      {/* Header & Quick Anchor Links */}
      <div className="p-3 border-b border-border/60 bg-sidebar shrink-0 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-teal-700 dark:text-teal-400 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" />
            Deliberation Analytics
          </span>
          <Badge
            variant="outline"
            className="text-[9px] font-mono border-teal-500/30 text-teal-700 dark:text-teal-300"
          >
            Live Metrics
          </Badge>
        </div>

        <div className="flex items-center gap-1 overflow-x-auto scrollbar-none pb-0.5">
          {[
            "overview",
            "network",
            "trajectory",
            "consensus",
            "influence",
            "sources",
          ].map((sec) => (
            <button
              key={sec}
              onClick={() => scrollToSection(`sec-${sec}`)}
              style={{ cursor: "pointer" }}
              className="px-2 py-0.5 rounded text-[9px] font-medium bg-muted/60 hover:bg-teal-50 dark:hover:bg-teal-950/50 hover:text-teal-600 transition-colors shrink-0 cursor-pointer capitalize"
            >
              {sec}
            </button>
          ))}
        </div>
      </div>

      {/* Unified Single-Page Analytics Feed */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto p-3 space-y-3.5 scrollbar-thin"
      >
        {/* 1. Overview KPIs */}
        <div id="sec-overview" className="grid grid-cols-2 gap-2">
          <Card className="p-2.5 bg-card border-border/80 shadow-2xs">
            <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1">
              <span className="flex items-center gap-1 font-semibold text-foreground">
                <Scale className="w-3 h-3 text-teal-600 dark:text-teal-400" />
                Consensus
              </span>
              {latestAgreement && (
                <span className="font-mono text-[9px]">
                  R{latestAgreement.round}
                </span>
              )}
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-lg font-bold font-mono text-teal-700 dark:text-teal-300">
                {latestAgreement
                  ? `${Math.round(latestAgreement.agreement_score * 100)}%`
                  : "N/A"}
              </span>
              <span className="text-[10px] font-medium text-muted-foreground truncate">
                {latestAgreement?.classification || "Evaluating..."}
              </span>
            </div>
          </Card>

          <Card className="p-2.5 bg-card border-border/80 shadow-2xs">
            <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1">
              <span className="flex items-center gap-1 font-semibold text-foreground">
                <Award className="w-3 h-3 text-amber-500" />
                Top Persuader
              </span>
              {topInfluencer && (
                <span className="font-mono text-[9px] text-amber-600 dark:text-amber-400 font-bold">
                  ★ {influenceScores[topInfluencer] || 0}
                </span>
              )}
            </div>
            <p className="text-xs font-bold text-foreground truncate">
              {topInfluencer ? topInfluencer.split(" ")[0] : "None identified"}
            </p>
          </Card>
        </div>

        {/* 2. Influence Network Graph */}
        <Card
          id="sec-network"
          className="p-3 bg-card border-border shadow-xs relative overflow-hidden"
        >
          <div className="flex items-center justify-between mb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
              <GitGraph className="w-3.5 h-3.5" />
              Influence Network ({graphNodes.length} Nodes)
            </CardTitle>
            <Badge
              variant="outline"
              className="text-[9px] border-teal-500/30 text-teal-700 dark:text-teal-300 font-mono"
            >
              {analytics?.edges?.length || 0} Directed Edges
            </Badge>
          </div>

          <div
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            className={`w-full ${isExpanded ? "h-68" : "h-56"} bg-background/50 rounded-lg border border-border relative overflow-hidden flex items-center justify-center transition-all ${
              isDragging ? "cursor-grabbing" : "cursor-grab"
            }`}
          >
            <div className="absolute top-2 right-2 z-20 flex items-center gap-1 bg-card/90 border border-border p-1 rounded-md shadow-2xs">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setZoom((z) => Math.min(z + 0.2, 2.5))}
                style={{ cursor: "pointer" }}
                className="h-5 w-5 p-0 cursor-pointer"
              >
                <ZoomIn className="w-3 h-3" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setZoom((z) => Math.max(z - 0.2, 0.6))}
                style={{ cursor: "pointer" }}
                className="h-5 w-5 p-0 cursor-pointer"
              >
                <ZoomOut className="w-3 h-3" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setZoom(1);
                  setPan({ x: 0, y: 0 });
                }}
                style={{ cursor: "pointer" }}
                className="h-5 w-5 p-0 cursor-pointer"
              >
                <RotateCcw className="w-3 h-3" />
              </Button>
            </div>

            <svg
              ref={svgRef}
              viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`}
              className="w-full h-full select-none"
            >
              <defs>
                <marker
                  id="arrowhead"
                  markerWidth="7"
                  markerHeight="7"
                  refX="17"
                  refY="3.5"
                  orient="auto"
                >
                  <polygon
                    points="0 0, 7 3.5, 0 7"
                    className="fill-teal-600 dark:fill-teal-400"
                  />
                </marker>
              </defs>

              <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                {analytics?.edges?.map((edge, i) => {
                  const src = nodeMap.get(edge.source);
                  const tgt = nodeMap.get(edge.target);
                  if (!src || !tgt) return null;

                  const dx = tgt.x - src.x;
                  const dy = tgt.y - src.y;
                  const cx = (src.x + tgt.x) / 2 - dy * 0.18;
                  const cy = (src.y + tgt.y) / 2 + dx * 0.18;
                  const isHighlighted =
                    selectedAgent === edge.source ||
                    selectedAgent === edge.target;
                  const weight =
                    typeof edge.weight === "number" ? edge.weight : 0.5;

                  return (
                    <g key={`edge-${i}`}>
                      <path
                        d={`M ${src.x} ${src.y} Q ${cx} ${cy} ${tgt.x} ${tgt.y}`}
                        fill="none"
                        stroke={
                          isHighlighted
                            ? "oklch(0.55 0.13 185)"
                            : "currentColor"
                        }
                        strokeWidth={
                          isHighlighted ? 2.5 : Math.max(1.2, weight * 2.2)
                        }
                        markerEnd="url(#arrowhead)"
                        className="text-teal-600/60 dark:text-teal-400/50 transition-colors"
                      />
                    </g>
                  );
                })}

                {graphNodes.map((n) => {
                  const isSel = selectedAgent === n.name;
                  const safeName = (n.name || n.id || "Agent").split(" ")[0];

                  return (
                    <g
                      key={n.id}
                      transform={`translate(${n.x}, ${n.y})`}
                      onClick={() => setSelectedAgent(isSel ? null : n.name)}
                      style={{ cursor: "pointer" }}
                      className="cursor-pointer group"
                    >
                      {isSel && (
                        <circle
                          r="22"
                          className="fill-teal-500/20 animate-ping"
                        />
                      )}
                      <circle
                        r="17"
                        className={`transition-all duration-150 stroke-2 ${
                          isSel
                            ? "stroke-teal-500 fill-teal-50 dark:fill-teal-950"
                            : "stroke-border group-hover:stroke-teal-500 fill-background"
                        }`}
                      />
                      <clipPath id={`avatar-clip-${n.index}`}>
                        <circle r="14" />
                      </clipPath>
                      <image
                        href={n.avatarUrl}
                        x="-14"
                        y="-14"
                        height="28"
                        width="28"
                        clipPath={`url(#avatar-clip-${n.index})`}
                      />
                      <g transform="translate(0, 24)">
                        <rect
                          x="-32"
                          y="-6"
                          width="64"
                          height="12"
                          rx="3"
                          className="fill-card/95 stroke-border/80"
                          strokeWidth="0.6"
                        />
                        <text
                          textAnchor="middle"
                          dominantBaseline="middle"
                          className="text-[7.5px] font-bold fill-foreground"
                        >
                          {safeName} (
                          {n.currentStance > 0
                            ? `+${n.currentStance.toFixed(1)}`
                            : n.currentStance.toFixed(1)}
                          )
                        </text>
                      </g>
                    </g>
                  );
                })}
              </g>
            </svg>

            <div className="absolute bottom-1.5 left-2 text-[8.5px] text-muted-foreground flex items-center gap-1 font-mono pointer-events-none">
              <Move className="w-2.5 h-2.5 text-teal-600" />
              <span>Drag to pan</span>
            </div>
          </div>
        </Card>

        {/* 3. Smoothed Opinion Trajectory */}
        <Card
          id="sec-trajectory"
          className="p-3 bg-card border-border shadow-xs"
        >
          <CardHeader className="p-0 pb-2 flex-row items-center justify-between">
            <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
              <Activity className="w-3.5 h-3.5" />
              Smoothed Opinion Curves
            </CardTitle>
            <span className="text-[9px] font-mono text-muted-foreground">
              Range: [-5.0, +5.0]
            </span>
          </CardHeader>
          <CardContent className="p-0">
            <div className={`${isExpanded ? "h-44" : "h-36"} w-full`}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={analytics?.trajectory || []}
                  margin={{ top: 5, right: 10, left: -26, bottom: 0 }}
                >
                  <XAxis
                    dataKey="round"
                    stroke="currentColor"
                    className="text-muted-foreground"
                    fontSize={9}
                    tickLine={false}
                  />
                  <YAxis
                    domain={[-5, 5]}
                    stroke="currentColor"
                    className="text-muted-foreground"
                    fontSize={9}
                    tickLine={false}
                  />
                  <ReferenceLine
                    y={0}
                    stroke="currentColor"
                    strokeDasharray="2 2"
                    className="text-border"
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--card)",
                      borderColor: "var(--border)",
                      fontSize: "10px",
                      borderRadius: "6px",
                    }}
                  />
                  {personas.map((p, idx) => (
                    <Line
                      key={p.name || idx}
                      type="monotone"
                      dataKey={p.name}
                      stroke={AGENT_COLORS[idx % AGENT_COLORS.length]}
                      strokeWidth={selectedAgent === p.name ? 3 : 1.8}
                      dot={{ r: 2 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* 4. Consensus Dynamics */}
        <Card
          id="sec-consensus"
          className="p-3 bg-card border-border shadow-xs"
        >
          <div className="flex items-center justify-between mb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
              <Scale className="w-3.5 h-3.5" />
              Consensus Dynamics (Agreement Score)
            </CardTitle>
            {latestAgreement && (
              <Badge className="text-[9px] bg-teal-600 text-white font-mono px-1.5 py-0 h-4">
                {latestAgreement.classification}
              </Badge>
            )}
          </div>
          <div className={`${isExpanded ? "h-36" : "h-28"} w-full`}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={analytics?.agreement || []}
                margin={{ top: 5, right: 10, left: -26, bottom: 0 }}
              >
                <defs>
                  <linearGradient
                    id="agreeGradient"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop offset="5%" stopColor="#0d9488" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#0d9488" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="round"
                  stroke="currentColor"
                  className="text-muted-foreground"
                  fontSize={9}
                  tickLine={false}
                />
                <YAxis
                  domain={[0, 1]}
                  stroke="currentColor"
                  className="text-muted-foreground"
                  fontSize={9}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--card)",
                    borderColor: "var(--border)",
                    fontSize: "10px",
                    borderRadius: "6px",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="agreement_score"
                  stroke="#0d9488"
                  fill="url(#agreeGradient)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* 5. Influence Power Rankings */}
        <Card
          id="sec-influence"
          className="p-3 bg-card border-border shadow-xs space-y-2.5"
        >
          <div className="flex items-center justify-between">
            <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
              <Award className="w-3.5 h-3.5" />
              Persuasion Power Rankings
            </CardTitle>
            <span className="text-[9px] text-muted-foreground font-mono">
              Outgoing Weight
            </span>
          </div>

          <div className="space-y-2">
            {personas.map((persona, idx) => {
              const pName = persona.name || `Agent ${idx + 1}`;
              const score = influenceScores[pName] || 0;
              const barPercent = Math.min(
                100,
                Math.round((score / maxInfluenceScore) * 100),
              );
              const isLead = topInfluencer === pName && score > 0;

              return (
                <div key={pName} className="space-y-1">
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="font-semibold text-foreground flex items-center gap-1 truncate max-w-[170px]">
                      {pName}{" "}
                      {isLead && (
                        <Award className="w-3 h-3 text-amber-500 inline" />
                      )}
                    </span>
                    <span className="font-mono text-teal-700 dark:text-teal-400 font-bold">
                      {score.toFixed(2)}
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-muted/60 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${isLead ? "bg-amber-500" : "bg-teal-600"}`}
                      style={{ width: `${barPercent}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        {/* 6. Persuasion Signals Log */}
        <Card className="p-3 bg-card border-border shadow-xs space-y-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
              <TrendingUp className="w-3.5 h-3.5" />
              Recorded Persuasion Signals
            </CardTitle>
            <span className="text-[9px] text-muted-foreground font-mono">
              CFG Shifts
            </span>
          </div>

          <div className="space-y-1.5">
            {!analytics?.persuasion_signals ||
            analytics.persuasion_signals.length === 0 ? (
              <p className="text-[11px] text-muted-foreground italic py-2 text-center">
                Awaiting debate turns to calculate persuasion vectors...
              </p>
            ) : (
              analytics.persuasion_signals
                .slice(-4)
                .reverse()
                .map((sig) => {
                  const src = String(sig.source || "Deliberation").split(
                    " ",
                  )[0];
                  const tgt = String(sig.target || "Agent").split(" ")[0];
                  const shiftVal =
                    typeof sig.shift === "number" ? sig.shift : 0;

                  return (
                    <div
                      key={sig.id}
                      className="p-2 rounded-md bg-muted/30 border border-border/60 text-xs flex items-center justify-between"
                    >
                      <div className="flex items-center gap-1 truncate text-[11px]">
                        <span className="text-muted-foreground truncate max-w-[70px]">
                          {src}
                        </span>
                        <ArrowRight className="w-2.5 h-2.5 text-teal-600 dark:text-teal-400 shrink-0" />
                        <span className="font-semibold text-foreground truncate max-w-[70px]">
                          {tgt}
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <span className="text-[9px] text-muted-foreground truncate">
                          {sig.dynamic || "Shift"}
                        </span>
                        <Badge
                          variant="secondary"
                          className={`text-[9px] font-mono px-1 py-0 h-4 ${
                            shiftVal > 0
                              ? "text-emerald-700 dark:text-emerald-300 bg-emerald-100/60 dark:bg-emerald-950/40"
                              : "text-rose-700 dark:text-rose-300 bg-rose-100/60 dark:bg-rose-950/40"
                          }`}
                        >
                          {shiftVal > 0
                            ? `+${shiftVal.toFixed(1)}`
                            : shiftVal.toFixed(1)}
                        </Badge>
                      </div>
                    </div>
                  );
                })
            )}
          </div>
        </Card>

        {/* 7. Sources */}
        <Card
          id="sec-sources"
          className="p-3 bg-card border-border shadow-xs space-y-2"
        >
          <div className="flex items-center justify-between">
            <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
              <ExternalLink className="w-3.5 h-3.5" />
              Retrieved Policy Citations
            </CardTitle>
            <Layers className="w-3 h-3 text-muted-foreground" />
          </div>

          <div className="space-y-1.5 text-xs">
            {analytics?.citations && analytics.citations.length > 0 ? (
              analytics.citations.map((url, i) => (
                <a
                  key={i}
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ cursor: "pointer" }}
                  className="flex items-center gap-1.5 p-1.5 rounded bg-muted/40 hover:bg-teal-50/60 dark:hover:bg-teal-950/40 border border-border/50 text-teal-700 dark:text-teal-300 text-[11px] truncate transition-colors group cursor-pointer"
                >
                  <ExternalLink className="w-3 h-3 shrink-0 text-muted-foreground group-hover:text-teal-600" />
                  <span className="truncate">{url}</span>
                </a>
              ))
            ) : (
              <p className="text-[11px] text-muted-foreground italic py-2 text-center">
                No policy documents cited yet in this session.
              </p>
            )}
          </div>
        </Card>
      </div>
    </aside>
  );
};
