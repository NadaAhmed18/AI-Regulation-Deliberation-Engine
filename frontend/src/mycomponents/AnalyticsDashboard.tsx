"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import {
  Activity,
  Compass,
  ExternalLink,
  GitGraph,
  Layers,
  ArrowRight,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  Move,
} from "lucide-react";
import {
  DiscussionTurn,
  Persona,
  SimulationAnalytics,
} from "@/types/simulation";
import { SimulationAPI, getAvatarPath } from "@/lib/api";

interface AnalyticsDashboardProps {
  turns: DiscussionTurn[];
  personas: Persona[];
  simulationId?: string;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

const AGENT_COLORS = [
  "#0d9488", // Teal
  "#f59e0b", // Amber
  "#0284c7", // Sky blue
  "#e11d48", // Rose
  "#8b5cf6", // Purple
  "#10b981", // Emerald
  "#f97316", // Orange
  "#6366f1", // Indigo
];

export const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({
  turns,
  personas,
  simulationId,
  isExpanded = false,
  onToggleExpand,
}) => {
  const [analytics, setAnalytics] = useState<SimulationAnalytics | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  // Zoom & Pan state for SVG Graph
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({
    x: 0,
    y: 0,
  });
  const svgRef = useRef<SVGSVGElement | null>(null);

  // Synchronize analytics from API without synchronous setState in effect
  useEffect(() => {
    let isMounted = true;

    SimulationAPI.getAnalytics(simulationId, personas, turns)
      .then((data) => {
        if (isMounted) setAnalytics(data);
      })
      .catch((err) => console.error("Failed to load analytics:", err));

    return () => {
      isMounted = false;
    };
  }, [simulationId, personas, turns]);

  // Compute N-gon Polygon Node Coordinates dynamically based on agent count and expansion
  const graphNodes = useMemo(() => {
    const list = analytics?.nodes?.length
      ? analytics.nodes
      : personas.map((p, idx) => ({
          id: `agent-${idx}`,
          name: p.name,
          avatarUrl: getAvatarPath(idx),
          currentStance: 0,
          role: p.background,
        }));

    const total = list.length || 1;
    const centerX = isExpanded ? 240 : 170;
    const centerY = isExpanded ? 160 : 125;
    const radius = isExpanded ? (total >= 4 ? 115 : 100) : total >= 4 ? 85 : 75;

    return list.map((node, idx) => {
      const angle = -Math.PI / 2 + (2 * Math.PI * idx) / total;
      return {
        ...node,
        index: idx,
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
        color: AGENT_COLORS[idx % AGENT_COLORS.length],
      };
    });
  }, [analytics, personas, isExpanded]);

  const nodeMap = useMemo(() => {
    const map = new Map<string, (typeof graphNodes)[0]>();
    graphNodes.forEach((n) => map.set(n.name, n));
    return map;
  }, [graphNodes]);

  // Zoom handlers
  const handleZoomIn = () =>
    setZoom((prev) => Math.min(Number((prev + 0.25).toFixed(2)), 3.0));
  const handleZoomOut = () =>
    setZoom((prev) => Math.max(Number((prev - 0.25).toFixed(2)), 0.6));
  const handleResetZoom = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  // Wheel zoom on SVG
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    if (e.deltaY < 0) {
      setZoom((prev) => Math.min(Number((prev + 0.15).toFixed(2)), 3.0));
    } else {
      setZoom((prev) => Math.max(Number((prev - 0.15).toFixed(2)), 0.6));
    }
  };

  // Pan handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return; // Left click only
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  };

  const handleMouseUp = () => setIsDragging(false);

  const viewBoxWidth = isExpanded ? 480 : 340;
  const viewBoxHeight = isExpanded ? 320 : 250;

  return (
    <aside className="relative flex flex-col h-full border-l border-border/70 bg-sidebar/50 text-sidebar-foreground select-none transition-all duration-300">
      {/* ======================================================================
          MIDDLE-LEFT HALF-BUBBLE EXPAND / COLLAPSE BUTTON
          ====================================================================== */}
      {onToggleExpand && (
        <button
          onClick={onToggleExpand}
          className="group absolute top-1/2 -left-3.5 -translate-y-1/2 z-40 h-10 w-4 rounded-l-md bg-card dark:bg-card border-y border-l border-border/80 shadow-md hover:bg-teal-50 dark:hover:bg-teal-950/70 hover:border-teal-500/50 flex items-center justify-center cursor-pointer transition-all hover:w-5"
          title={isExpanded ? "Collapse panel" : "Expand panel to 42% width"}
        >
          {isExpanded ? (
            <ChevronRight className="w-3.5 h-3.5 text-muted-foreground group-hover:text-teal-600 dark:group-hover:text-teal-400 transition-colors" />
          ) : (
            <ChevronLeft className="w-3.5 h-3.5 text-muted-foreground group-hover:text-teal-600 dark:group-hover:text-teal-400 transition-colors" />
          )}
        </button>
      )}

      {/* Main Scrollable Content Container */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 scrollbar-thin">
        {/* 1. INTERACTIVE AGENT INFLUENCE GRAPH WITH ZOOM & PAN */}
        <Card className="p-3 bg-card border-border/80 shadow-xs relative overflow-hidden">
          <div className="flex items-center justify-between mb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
              <GitGraph className="w-3.5 h-3.5" />
              Influence Network ({graphNodes.length} Nodes)
            </CardTitle>

            <Badge
              variant="outline"
              className="text-[9px] px-1.5 py-0 h-4 border-teal-500/30 text-teal-700 dark:text-teal-300 font-mono"
            >
              {analytics?.edges.length || 0} Edges
            </Badge>
          </div>

          {/* SVG Graph Viewport */}
          <div
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            className={`w-full ${
              isExpanded ? "h-80" : "h-64"
            } bg-background/60 dark:bg-background/40 rounded-lg border border-border/70 relative flex items-center justify-center overflow-hidden transition-all duration-300 ${
              isDragging ? "cursor-grabbing" : "cursor-grab"
            }`}
          >
            {/* Floating Zoom Controls Bar */}
            <div className="absolute top-2 right-2 z-20 flex items-center gap-1 bg-card/90 dark:bg-card/90 backdrop-blur-xs border border-border/70 p-1 rounded-md shadow-xs">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleZoomIn}
                className="h-6 w-6 p-0 hover:bg-teal-50 dark:hover:bg-teal-950/40 text-muted-foreground hover:text-teal-600 dark:hover:text-teal-400 cursor-pointer"
                title="Zoom in"
              >
                <ZoomIn className="w-3.5 h-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleZoomOut}
                className="h-6 w-6 p-0 hover:bg-teal-50 dark:hover:bg-teal-950/40 text-muted-foreground hover:text-teal-600 dark:hover:text-teal-400 cursor-pointer"
                title="Zoom out"
              >
                <ZoomOut className="w-3.5 h-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleResetZoom}
                className="h-6 w-6 p-0 hover:bg-teal-50 dark:hover:bg-teal-950/40 text-muted-foreground hover:text-teal-600 dark:hover:text-teal-400 cursor-pointer"
                title="Reset zoom & pan"
              >
                <RotateCcw className="w-3 h-3" />
              </Button>
              <span className="text-[9px] font-mono font-semibold px-1 text-teal-700 dark:text-teal-400">
                {Math.round(zoom * 100)}%
              </span>
            </div>

            {/* SVG Content with Zoom & Pan Transforms */}
            <svg
              ref={svgRef}
              viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`}
              className="w-full h-full select-none"
            >
              <defs>
                <marker
                  id="arrowhead-teal"
                  markerWidth="8"
                  markerHeight="8"
                  refX="18"
                  refY="3.5"
                  orient="auto"
                >
                  <polygon
                    points="0 0, 8 3.5, 0 7"
                    className="fill-teal-600 dark:fill-teal-400"
                  />
                </marker>
              </defs>

              <g
                transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}
                style={{
                  transformOrigin: `${viewBoxWidth / 2}px ${viewBoxHeight / 2}px`,
                  transition: isDragging ? "none" : "transform 0.15s ease-out",
                }}
              >
                {/* Directed Weighted Influence Curves */}
                {analytics?.edges.map((edge, idx) => {
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

                  return (
                    <g key={`edge-${idx}-${edge.source}-${edge.target}`}>
                      <path
                        d={`M ${src.x} ${src.y} Q ${cx} ${cy} ${tgt.x} ${tgt.y}`}
                        fill="none"
                        stroke={
                          isHighlighted
                            ? "oklch(0.55 0.13 185)"
                            : "currentColor"
                        }
                        strokeWidth={
                          isHighlighted ? 2.8 : Math.max(1.3, edge.weight * 2.4)
                        }
                        strokeDasharray={edge.weight <= 0.2 ? "3,3" : "none"}
                        markerEnd="url(#arrowhead-teal)"
                        className="text-teal-600/60 dark:text-teal-400/50 transition-all duration-300"
                      />

                      {/* Weight Value Pill */}
                      <g transform={`translate(${cx}, ${cy})`}>
                        <rect
                          x="-14"
                          y="-7"
                          width="28"
                          height="14"
                          rx="4"
                          className="fill-background/95 dark:fill-card stroke-border/80"
                          strokeWidth="0.8"
                        />
                        <text
                          textAnchor="middle"
                          dominantBaseline="middle"
                          className="text-[8px] font-mono font-bold fill-teal-700 dark:fill-teal-300"
                        >
                          w:{edge.weight.toFixed(2)}
                        </text>
                      </g>
                    </g>
                  );
                })}

                {/* Nodes with Avatars and Stance Rings */}
                {graphNodes.map((node) => {
                  const isSelected = selectedAgent === node.name;

                  return (
                    <g
                      key={node.id}
                      transform={`translate(${node.x}, ${node.y})`}
                      className="cursor-pointer group"
                      onClick={() =>
                        setSelectedAgent(isSelected ? null : node.name)
                      }
                    >
                      {isSelected && (
                        <circle
                          r="23"
                          className="fill-teal-500/20 animate-ping"
                        />
                      )}

                      <circle
                        r="18"
                        className={`transition-all duration-200 stroke-2 ${
                          isSelected
                            ? "stroke-teal-500 fill-teal-50 dark:fill-teal-950/70"
                            : "stroke-border group-hover:stroke-teal-500 fill-background"
                        }`}
                      />

                      <clipPath id={`avatar-clip-${node.index}`}>
                        <circle r="15" />
                      </clipPath>

                      <image
                        href={node.avatarUrl}
                        x="-15"
                        y="-15"
                        height="30"
                        width="30"
                        clipPath={`url(#avatar-clip-${node.index})`}
                        preserveAspectRatio="xMidYMid slice"
                      />

                      {/* Agent Label Pill */}
                      <g transform="translate(0, 26)">
                        <rect
                          x="-38"
                          y="-7"
                          width="76"
                          height="14"
                          rx="3.5"
                          className="fill-card/95 dark:fill-card/90 stroke-border/80 shadow-2xs"
                          strokeWidth="0.8"
                        />
                        <text
                          textAnchor="middle"
                          dominantBaseline="middle"
                          className="text-[8px] font-semibold fill-foreground truncate"
                        >
                          {node.name.split(" ")[0]} (
                          {node.currentStance > 0
                            ? `+${node.currentStance.toFixed(1)}`
                            : node.currentStance.toFixed(1)}
                          )
                        </text>
                      </g>
                    </g>
                  );
                })}
              </g>
            </svg>

            {/* Bottom-left interactive guide */}
            <div className="absolute bottom-1.5 left-2 text-[9px] text-muted-foreground flex items-center gap-1 font-mono pointer-events-none bg-background/70 dark:bg-background/60 px-1.5 py-0.5 rounded">
              <Move className="w-2.5 h-2.5 text-teal-600 dark:text-teal-400" />
              <span>Scroll to zoom • Drag to pan</span>
            </div>
          </div>
        </Card>

        {/* 2. REAL-TIME OPINION TRAJECTORY CHART */}
        <Card className="p-3 bg-card border-border/80 shadow-xs">
          <CardHeader className="p-0 pb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
              <Activity className="w-3.5 h-3.5" />
              Opinion Trajectory (-5 to +5)
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div
              className={`${isExpanded ? "h-48" : "h-38"} w-full transition-all duration-300`}
            >
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={analytics?.trajectory || []}
                  margin={{ top: 8, right: 8, left: -28, bottom: 0 }}
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
                    className="text-border"
                    strokeDasharray="2 2"
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--card)",
                      borderColor: "var(--border)",
                      color: "var(--foreground)",
                      fontSize: "10px",
                      borderRadius: "6px",
                    }}
                  />
                  {personas.map((p, idx) => (
                    <Line
                      key={p.name}
                      type="monotone"
                      dataKey={p.name}
                      stroke={AGENT_COLORS[idx % AGENT_COLORS.length]}
                      strokeWidth={selectedAgent === p.name ? 3 : 1.8}
                      dot={{ r: 2.5 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* 3. INFLUENCE & PERSUASION SIGNALS */}
        <Card className="p-3 bg-card border-border/80 shadow-xs">
          <div className="flex items-center justify-between mb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
              <Compass className="w-3.5 h-3.5" />
              CFG Persuasion Signals
            </CardTitle>
            <span className="text-[9px] text-muted-foreground font-mono">
              Recorded Shifts
            </span>
          </div>

          <div className="space-y-1.5">
            {!analytics?.persuasion_signals ||
            analytics.persuasion_signals.length === 0 ? (
              <div className="p-3 text-center text-xs text-muted-foreground bg-muted/20 rounded-md">
                Awaiting discussion turns to calculate persuasion vectors...
              </div>
            ) : (
              analytics.persuasion_signals
                .slice(-3)
                .reverse()
                .map((signal) => (
                  <div
                    key={signal.id}
                    className="p-2 rounded-md bg-muted/40 border border-border/60 text-xs flex flex-col gap-1 transition-all hover:border-teal-500/30"
                  >
                    <div className="flex justify-between items-center font-medium">
                      <div className="flex items-center gap-1 text-[11px] truncate">
                        <span className="text-muted-foreground truncate max-w-[80px]">
                          {signal.source.split(" ")[0]}
                        </span>
                        <ArrowRight className="w-2.5 h-2.5 text-teal-600 dark:text-teal-400 shrink-0" />
                        <span className="font-semibold text-foreground truncate max-w-[80px]">
                          {signal.target.split(" ")[0]}
                        </span>
                      </div>

                      <Badge
                        variant="secondary"
                        className={`text-[9px] font-mono px-1 py-0 h-4 ${
                          signal.shift > 0
                            ? "text-emerald-700 dark:text-emerald-300 bg-emerald-100/60 dark:bg-emerald-950/40"
                            : signal.shift < 0
                              ? "text-rose-700 dark:text-rose-300 bg-rose-100/60 dark:bg-rose-950/40"
                              : "text-muted-foreground"
                        }`}
                      >
                        {signal.shift > 0
                          ? `+${signal.shift.toFixed(1)}`
                          : signal.shift.toFixed(1)}
                      </Badge>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                      <span className="truncate">{signal.dynamic}</span>
                      <span className="font-mono text-teal-700 dark:text-teal-400 font-semibold shrink-0">
                        γ={signal.gamma.toFixed(2)}
                      </span>
                    </div>
                  </div>
                ))
            )}
          </div>
        </Card>

        {/* 4. RAG CITATIONS */}
        <Card className="p-3 bg-card border-border/80 shadow-xs flex-1 min-h-[110px]">
          <div className="flex items-center justify-between mb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
              <ExternalLink className="w-3.5 h-3.5" />
              Cited Knowledge & Sources
            </CardTitle>
            <Layers className="w-3 h-3 text-muted-foreground" />
          </div>

          <div className="space-y-1.5 text-xs">
            {analytics?.citations && analytics.citations.length > 0 ? (
              analytics.citations.map((sourceUrl, idx) => (
                <a
                  key={idx}
                  href={sourceUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 p-1.5 rounded bg-muted/40 hover:bg-teal-50/60 dark:hover:bg-teal-950/40 border border-border/50 text-teal-700 dark:text-teal-300 text-[11px] truncate transition-colors group cursor-pointer"
                >
                  <ExternalLink className="w-3 h-3 shrink-0 text-muted-foreground group-hover:text-teal-600 dark:group-hover:text-teal-400" />
                  <span className="truncate">{sourceUrl}</span>
                </a>
              ))
            ) : (
              <p className="text-[11px] text-muted-foreground italic py-2">
                No external tools or articles cited yet.
              </p>
            )}
          </div>
        </Card>
      </div>
    </aside>
  );
};
