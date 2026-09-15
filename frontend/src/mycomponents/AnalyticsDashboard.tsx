"use client";

import React, { useState, useMemo, useRef } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tooltip as UITooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
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
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Globe,
  Calculator,
  Info,
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

/**
 * Clean, uncompressed explanation mark with comfortable width (360px-400px)
 * preventing cramped 5-line text wrapping.
 */
const MetricInfoBadge: React.FC<{
  title: string;
  whatItIs: string;
  calculation: string;
}> = ({ title, whatItIs, calculation }) => {
  return (
    <TooltipProvider delay={150}>
      <UITooltip>
        <TooltipTrigger>
          <button
            type="button"
            className="inline-flex items-center text-muted-foreground/70 hover:text-teal-600 transition-colors p-0.5 rounded cursor-pointer"
            aria-label={`Info: ${title}`}
          >
            <HelpCircle className="w-3.5 h-3.5" />
          </button>
        </TooltipTrigger>
        <TooltipContent
          side="left"
          sideOffset={8}
          className="w-[360px] sm:w-[400px] max-w-[90vw] p-3.5 bg-card border border-border text-foreground shadow-xl rounded-xl space-y-2.5 z-50 select-text leading-normal flow-root"
        >
          {/* 1. Header */}
          <div className="px-3.5 py-2.5 bg-muted/40 dark:bg-muted/20 border-b border-border/70 flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1 rounded-md bg-teal-500/10 text-teal-600 dark:text-teal-400 shrink-0">
                <HelpCircle className="w-4 h-4" />
              </div>
              <span className="font-bold text-xs text-foreground truncate">
                {title}
              </span>
            </div>
            <span className="text-[9.5px] font-mono font-medium px-1.5 py-0.5 rounded bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 border border-teal-500/30 shrink-0">
              Metric Guide
            </span>
          </div>

          <div className="p-3.5 space-y-3">
            {/* 2. Content / Overview */}
            <div className="space-y-1">
              <span className="text-[9.5px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                <Info className="w-3 h-3 text-teal-600 dark:text-teal-400" />
                Overview & Meaning
              </span>
              <p className="text-xs text-foreground/90 leading-relaxed pl-0.5">
                {whatItIs}
              </p>
            </div>

            {/* 3. Calculation Method */}
            <div className="space-y-1.5">
              <span className="text-[9.5px] font-bold uppercase tracking-wider text-teal-700 dark:text-teal-400 flex items-center gap-1">
                <Calculator className="w-3 h-3" />
                Calculation Method
              </span>
              <div className="bg-muted/60 dark:bg-background/80 border border-border/80 rounded-lg p-2.5 text-[10.5px] font-mono leading-relaxed text-foreground shadow-2xs">
                <p className="whitespace-pre-wrap break-words">{calculation}</p>
              </div>
            </div>
          </div>
        </TooltipContent>
      </UITooltip>
    </TooltipProvider>
  );
};

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

  const [expandedDomains, setExpandedDomains] = useState<
    Record<string, boolean>
  >({});

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
  const influenceScores = useMemo(
    () => analytics?.influence?.scores || {},
    [analytics]
  );
  const maxInfluenceScore = useMemo(() => {
    const vals = Object.values(influenceScores);
    return vals.length > 0 ? Math.max(...vals, 1) : 1;
  }, [influenceScores]);

  // Group policy citations by domain
  const groupedCitations = useMemo(() => {
    const citations = analytics?.citations || [];
    const map = new Map<string, { count: number; urls: Set<string> }>();

    citations.forEach((rawUrl) => {
      try {
        const urlObj = new URL(rawUrl);
        const domain = urlObj.hostname.replace(/^www\./, "");
        if (!map.has(domain)) {
          map.set(domain, { count: 0, urls: new Set() });
        }
        const entry = map.get(domain)!;
        entry.count += 1;
        entry.urls.add(rawUrl);
      } catch {
        const fallbackDomain = "External Policy Documents";
        if (!map.has(fallbackDomain)) {
          map.set(fallbackDomain, { count: 0, urls: new Set() });
        }
        const entry = map.get(fallbackDomain)!;
        entry.count += 1;
        entry.urls.add(rawUrl);
      }
    });

    return Array.from(map.entries())
      .map(([domain, data]) => ({
        domain,
        count: data.count,
        urls: Array.from(data.urls),
      }))
      .sort((a, b) => b.count - a.count);
  }, [analytics?.citations]);

  const toggleDomainExpand = (domain: string) => {
    setExpandedDomains((prev) => ({ ...prev, [domain]: !prev[domain] }));
  };

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

  const viewBoxWidth = isExpanded ? 480 : 330;
  const viewBoxHeight = isExpanded ? 290 : 240;

  return (
    <aside className="relative z-30 flex flex-col h-full min-h-0 border-l border-border/70 bg-sidebar/50 text-sidebar-foreground transition-all duration-300">
      {/* Expand/Collapse Handle */}
      {onToggleExpand && (
        <button
          onClick={onToggleExpand}
          style={{ cursor: "pointer" }}
          className="group absolute top-1/2 -left-3.5 -translate-y-1/2 z-50 h-10 w-4 rounded-l-md bg-card border-y border-l border-border shadow-md hover:bg-teal-50 dark:hover:bg-teal-950/70 flex items-center justify-center cursor-pointer transition-all hover:w-5"
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

      {/* Clean Header without Tabs or Hyperlinks */}
      <div className="p-3 border-b border-border/60 bg-sidebar shrink-0 flex items-center justify-between">
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

      {/* Feed (Top KPI cards removed as requested) */}
      <div
        ref={containerRef}
        className="flex-1 min-h-0 overflow-y-auto p-3 space-y-3.5 scrollbar-thin"
      >
        {/* 1. Influence Network Graph with Corrected Arrow Geometry */}
        <Card className="p-3 bg-card border-border shadow-xs relative overflow-hidden">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
                <GitGraph className="w-3.5 h-3.5" />
                Influence Network ({graphNodes.length} Nodes)
              </CardTitle>
              <MetricInfoBadge
                title="Opinion Dynamics Network"
                whatItIs="Directed topological graph illustrating persuasion vectors between stakeholders."
                calculation="Nodes show active stances [-5.0, +5.0]. Curved Bézier arrows represent directed persuasion; arrow thickness is proportional to accumulated persuasion points."
              />
            </div>
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
                className="h-5 w-5 p-0 cursor-pointer"
              >
                <ZoomIn className="w-3 h-3" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setZoom((z) => Math.max(z - 0.2, 0.6))}
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
                {/* Arrowhead marker: Tip is at x=9, y=5 */}
                <marker
                  id="arrowhead"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto"
                >
                  <path
                    d="M 0 1.5 L 9 5 L 0 8.5 z"
                    className="fill-teal-600 dark:fill-teal-400"
                  />
                </marker>
              </defs>

              <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                {/* Directed Edges: Calculated to touch outer node boundary cleanly */}
                {analytics?.edges?.map((edge, i) => {
                  const src = nodeMap.get(edge.source);
                  const tgt = nodeMap.get(edge.target);
                  if (!src || !tgt) return null;

                  const dx = tgt.x - src.x;
                  const dy = tgt.y - src.y;

                  // Curvature offset
                  const curvature = 0.22;
                  const cx = (src.x + tgt.x) / 2 - dy * curvature;
                  const cy = (src.y + tgt.y) / 2 + dx * curvature;

                  // Outer node circle radius = 17px
                  const nodeRadius = 18;

                  // Start point on source boundary
                  const dSrcX = cx - src.x;
                  const dSrcY = cy - src.y;
                  const distSrc = Math.hypot(dSrcX, dSrcY) || 1;
                  const startX = src.x + (dSrcX / distSrc) * nodeRadius;
                  const startY = src.y + (dSrcY / distSrc) * nodeRadius;

                  // End point on target boundary (arrow touches outer ring)
                  const dTgtX = cx - tgt.x;
                  const dTgtY = cy - tgt.y;
                  const distTgt = Math.hypot(dTgtX, dTgtY) || 1;
                  const endX = tgt.x + (dTgtX / distTgt) * (nodeRadius + 2);
                  const endY = tgt.y + (dTgtY / distTgt) * (nodeRadius + 2);

                  const isHighlighted =
                    selectedAgent === edge.source ||
                    selectedAgent === edge.target;
                  const weight =
                    typeof edge.weight === "number" ? edge.weight : 0.5;

                  return (
                    <g key={`edge-${i}`}>
                      <path
                        d={`M ${startX} ${startY} Q ${cx} ${cy} ${endX} ${endY}`}
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
                        className="text-teal-600/65 dark:text-teal-400/55 transition-colors"
                      />
                    </g>
                  );
                })}

                {/* Nodes with Full Names on badges */}
                {graphNodes.map((n) => {
                  const isSel = selectedAgent === n.name;
                  const fullName = n.name || n.id || "Agent";
                  const stanceStr =
                    n.currentStance > 0
                      ? `+${n.currentStance.toFixed(1)}`
                      : n.currentStance.toFixed(1);
                  const labelText = `${fullName} (${stanceStr})`;
                  const pillWidth = Math.max(80, labelText.length * 5.6 + 14);

                  return (
                    <g
                      key={n.id}
                      transform={`translate(${n.x}, ${n.y})`}
                      onClick={() => setSelectedAgent(isSel ? null : n.name)}
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

                      {/* Dynamic width badge showing the Full Name */}
                      <g transform="translate(0, 24)">
                        <rect
                          x={-pillWidth / 2}
                          y="-7"
                          width={pillWidth}
                          height="14"
                          rx="4"
                          className="fill-card/95 stroke-border/80 shadow-xs"
                          strokeWidth="0.8"
                        />
                        <text
                          textAnchor="middle"
                          dominantBaseline="middle"
                          className="text-[8px] font-bold fill-foreground"
                        >
                          {labelText}
                        </text>
                      </g>
                    </g>
                  );
                })}
              </g>
            </svg>

            <div className="absolute bottom-1.5 left-2 text-[8.5px] text-muted-foreground flex items-center gap-1 font-mono pointer-events-none">
              <Move className="w-2.5 h-2.5 text-teal-600" />
              <span>Drag to pan • Scroll to zoom</span>
            </div>
          </div>
        </Card>

        {/* 2. Smoothed Opinion Trajectory (Connected Dots + Wide Tooltip) */}
        <Card className="p-3 bg-card border-border shadow-xs">
          <CardHeader className="p-0 pb-2 flex-row items-center justify-between">
            <div className="flex items-center gap-1.5">
              <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
                <Activity className="w-3.5 h-3.5" />
                Smoothed Opinion Curves
              </CardTitle>
              <MetricInfoBadge
                title="Opinion Drift Trajectories"
                whatItIs="Tracks continuous stance drift [-5.0, +5.0] for every panelist across discussion rounds."
                calculation="Each turn is graded via DeBERTa-v3 NLI continuous 2-way softmax. Stances are forward-filled across rounds to ensure continuous lines with visible markers."
              />
            </div>
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
                  <RechartsTooltip
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
                      connectNulls={true}
                      dot={{
                        r: 3.5,
                        strokeWidth: 1.5,
                        stroke: AGENT_COLORS[idx % AGENT_COLORS.length],
                        fill: "var(--card)",
                      }}
                      activeDot={{ r: 5.5 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* 3. Consensus Dynamics */}
        <Card className="p-3 bg-card border-border shadow-xs">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
                <Scale className="w-3.5 h-3.5" />
                Consensus Dynamics (Agreement)
              </CardTitle>
              <MetricInfoBadge
                title="Consensus Over Rounds"
                whatItIs="Chronological agreement tracking whether the deliberation is converging toward consensus or polarizing over time."
                calculation="Calculated per round across all active agents' most recent stances: 1.0 - (mean absolute pairwise diff / 10.0). Scores range from 0.0 (extreme polarization) to 1.0 (unanimous consensus)."
              />
            </div>
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
                <RechartsTooltip
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
                  dot={{ r: 3, fill: "#0d9488" }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* 4. Influence Power Rankings */}
        <Card className="p-3 bg-card border-border shadow-xs space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
                <Award className="w-3.5 h-3.5" />
                Persuasion Power Rankings
              </CardTitle>
              <MetricInfoBadge
                title="Persuasion Power Ranking"
                whatItIs="Total outbound persuasion effect generated by each stakeholder across the debate."
                calculation="Sum of outgoing edge weights from this agent in the influence matrix. Convergence only counts if the listener is permitted to hear the agent in the listening matrix."
              />
            </div>
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
                    <span
                      className="font-semibold text-foreground flex items-center gap-1 truncate max-w-[200px]"
                      title={pName}
                    >
                      {pName}{" "}
                      {isLead && (
                        <Award className="w-3 h-3 text-amber-500 inline shrink-0" />
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

        {/* 5. Persuasion Signals with Full Names */}
        <Card className="p-3 bg-card border-border shadow-xs space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
                <TrendingUp className="w-3.5 h-3.5" />
                Persuasion Signals Log
              </CardTitle>
              <MetricInfoBadge
                title="Persuasion Shift Signals"
                whatItIs="Step-by-step record whenever a speaker successfully persuades or polarizes a listener."
                calculation="Magnitude Δ = Current_Stance - Prior_Stance. Guidance scale γ = |Δ| * 0.05. Categorized as Convergence (moving closer) or Polarization (moving further away)."
              />
            </div>
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
                .slice(-5)
                .reverse()
                .map((sig) => {
                  // Display Full Names without truncation
                  const src = String(sig.source || "Group Deliberation");
                  const tgt = String(sig.target || "Panelist");
                  const shiftVal =
                    typeof sig.shift === "number" ? sig.shift : 0;

                  return (
                    <div
                      key={sig.id}
                      className="p-2 rounded-md bg-muted/30 border border-border/60 text-xs flex items-center justify-between gap-2"
                    >
                      <div className="flex items-center gap-1.5 min-w-0 flex-1 pr-1">
                        <span
                          className="text-muted-foreground font-medium text-[11px] truncate max-w-[120px]"
                          title={src}
                        >
                          {src}
                        </span>
                        <ArrowRight className="w-3 h-3 text-teal-600 dark:text-teal-400 shrink-0" />
                        <span
                          className="font-semibold text-foreground text-[11px] truncate max-w-[120px]"
                          title={tgt}
                        >
                          {tgt}
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className="text-[9px] text-muted-foreground truncate hidden sm:inline">
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

        {/* 6. Grouped & Expandable Policy Citations */}
        <Card className="p-3 bg-card border-border shadow-xs space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
                <ExternalLink className="w-3.5 h-3.5" />
                Policy Citations by Domain
              </CardTitle>
              <MetricInfoBadge
                title="Grouped Policy Evidence"
                whatItIs="External regulatory, legal, and empirical documentation cited by agents during deliberation."
                calculation="Aggregated across turns, grouped by root domain, with citation frequency counts and interactive links."
              />
            </div>
            <Layers className="w-3 h-3 text-muted-foreground" />
          </div>

          <div className="space-y-1.5 text-xs">
            {groupedCitations.length > 0 ? (
              groupedCitations.map((grp) => {
                const isDomainExpanded = Boolean(expandedDomains[grp.domain]);

                return (
                  <div
                    key={grp.domain}
                    className="rounded-md border border-border/60 bg-muted/20 overflow-hidden"
                  >
                    <button
                      type="button"
                      onClick={() => toggleDomainExpand(grp.domain)}
                      className="w-full flex items-center justify-between p-2 hover:bg-muted/40 transition-colors text-left cursor-pointer"
                    >
                      <div className="flex items-center gap-1.5 min-w-0 pr-1">
                        <Globe className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400 shrink-0" />
                        <span className="font-semibold text-[11px] text-foreground truncate">
                          {grp.domain}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <Badge
                          variant="secondary"
                          className="text-[9px] font-mono px-1.5 py-0 h-4"
                        >
                          {grp.count}{" "}
                          {grp.count === 1 ? "citation" : "citations"}
                        </Badge>
                        {isDomainExpanded ? (
                          <ChevronUp className="w-3 h-3 text-muted-foreground" />
                        ) : (
                          <ChevronDown className="w-3 h-3 text-muted-foreground" />
                        )}
                      </div>
                    </button>

                    {isDomainExpanded && (
                      <div className="p-2 pt-0 space-y-1 border-t border-border/30 bg-muted/10">
                        {grp.urls.map((url, idx) => (
                          <a
                            key={idx}
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1.5 p-1 rounded hover:bg-teal-50 dark:hover:bg-teal-950/40 text-[10.5px] text-teal-700 dark:text-teal-300 transition-colors group/item"
                          >
                            <ExternalLink className="w-3 h-3 shrink-0 text-muted-foreground group-hover/item:text-teal-600" />
                            <span className="truncate">{url}</span>
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })
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
