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
  Flame,
  CheckCircle2,
  XCircle,
  Download,
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
  topic?: string;
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
 * Metric explanation mark: styled directly on TooltipTrigger to prevent <button> nesting
 * and positioned on the far right of card headers.
 */
const MetricInfoBadge: React.FC<{
  title: string;
  whatItIs: string;
  calculation: string;
}> = ({ title, whatItIs, calculation }) => {
  return (
    <TooltipProvider delay={150}>
      <UITooltip>
        <TooltipTrigger
          className="inline-flex items-center justify-center text-muted-foreground/70 hover:text-teal-600 transition-colors p-1 rounded-md hover:bg-muted/50 cursor-pointer shrink-0"
          aria-label={`Info: ${title}`}
        >
          <HelpCircle className="w-3.5 h-3.5" />
        </TooltipTrigger>
        <TooltipContent
          side="left"
          sideOffset={8}
          className="w-[360px] sm:w-[400px] max-w-[90vw] p-3.5 bg-card border border-border text-foreground shadow-xl rounded-xl space-y-2.5 z-50 select-text leading-normal flow-root"
        >
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
            <div className="space-y-1">
              <span className="text-[9.5px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                <Info className="w-3 h-3 text-teal-600 dark:text-teal-400" />
                Overview & Meaning
              </span>
              <p className="text-xs text-foreground/90 leading-relaxed pl-0.5">
                {whatItIs}
              </p>
            </div>

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
  turns,
  personas,
  topic,
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

  const viewBoxWidth = isExpanded ? 480 : 330;
  const viewBoxHeight = isExpanded ? 310 : 255;

  // Extract pairwise agreement score [0.0, 1.0] between any two agents
  const getPairwiseAgreement = useMemo(() => {
    return (agentA: string, agentB: string): number => {
      const topoMatrix = analytics?.topological_agreement?.matrix;
      if (topoMatrix) {
        const scoreAB = topoMatrix[agentA]?.[agentB]?.agreement;
        const scoreBA = topoMatrix[agentB]?.[agentA]?.agreement;
        if (typeof scoreAB === "number") return scoreAB;
        if (typeof scoreBA === "number") return scoreBA;
      }
      // Direct stance proximity fallback
      const nodeA = analytics?.nodes?.find(
        (n) => n.name === agentA || n.id === agentA,
      );
      const nodeB = analytics?.nodes?.find(
        (n) => n.name === agentB || n.id === agentB,
      );
      if (
        nodeA &&
        nodeB &&
        typeof nodeA.currentStance === "number" &&
        typeof nodeB.currentStance === "number"
      ) {
        const diff = Math.abs(nodeA.currentStance - nodeB.currentStance);
        return Math.max(0, Math.min(1, 1 - diff / 10));
      }
      return 0.5;
    };
  }, [analytics]);

  // =========================================================================
  // AGREEMENT-DRIVEN POSITIONING (Distance proportional to agreement)
  // =========================================================================
  const graphNodes = useMemo(() => {
    const rawList = analytics?.nodes?.length
      ? analytics.nodes
      : personas.map((p, idx) => ({
          id: p.name || `agent-${idx}`,
          name: p.name || `Agent ${idx + 1}`,
          avatarUrl: getAvatarPath(idx),
          currentStance: 0,
          role: p.background,
        }));

    const total = rawList.length || 1;
    const centerX = viewBoxWidth / 2;
    const centerY = viewBoxHeight / 2 - 2;

    // Seed positions along an alignment axis based on stance to break rigid polygons
    const positions = rawList.map((node, idx) => {
      const rawName = node.name || node.id || `Agent ${idx + 1}`;
      const name = String(rawName);
      const stance =
        typeof node.currentStance === "number" ? node.currentStance : 0;

      // Proponents spread to the right, opponents to the left, staggered vertically
      const normStance = stance / 5.0; // [-1.0, 1.0]
      const spreadX = isExpanded ? 130 : 95;
      const spreadY = isExpanded ? 85 : 65;
      const verticalOffset =
        (idx % 2 === 0 ? 1 : -1) * (0.4 + 0.3 * (idx / total)) * spreadY;

      return {
        id: String(node.id || name),
        name,
        avatarUrl: node.avatarUrl || getAvatarPath(idx),
        currentStance: stance,
        index: idx,
        x: centerX + normStance * spreadX + (idx % 2 === 0 ? 12 : -12),
        y: centerY + verticalOffset,
        color: AGENT_COLORS[idx % AGENT_COLORS.length],
      };
    });

    // Distance bounds:
    // High agreement (0.9) -> targets ~80px (close neighbors with overlapping green circles)
    // Low agreement (0.1) -> targets ~190px (far apart across the canvas)
    const minDist = isExpanded ? 84 : 76;
    const maxDist = isExpanded ? 205 : 160;

    // 40 spring relaxation iterations to converge on true agreement-distance representation
    for (let step = 0; step < 40; step++) {
      for (let i = 0; i < positions.length; i++) {
        for (let j = i + 1; j < positions.length; j++) {
          const a = positions[i];
          const b = positions[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const curDist = Math.hypot(dx, dy) || 1;

          const agreement = getPairwiseAgreement(a.name, b.name);
          const targetDist = minDist + (1.0 - agreement) * (maxDist - minDist);

          // Spring force towards target distance
          const delta = (curDist - targetDist) / curDist;
          const force = delta * 0.16;

          a.x += dx * force;
          a.y += dy * force;
          b.x -= dx * force;
          b.y -= dy * force;

          // Hard anti-collision limit so avatar cards never overlap
          if (curDist < minDist) {
            const push = ((minDist - curDist) / curDist) * 0.45;
            a.x -= dx * push;
            a.y -= dy * push;
            b.x += dx * push;
            b.y += dy * push;
          }
        }

        // Center gravity
        positions[i].x += (centerX - positions[i].x) * 0.025;
        positions[i].y += (centerY - positions[i].y) * 0.025;

        // Viewport padding
        const padX = 48;
        const padY = 34;
        positions[i].x = Math.max(
          padX,
          Math.min(viewBoxWidth - padX, positions[i].x),
        );
        positions[i].y = Math.max(
          padY,
          Math.min(viewBoxHeight - padY, positions[i].y),
        );
      }
    }

    return positions;
  }, [
    analytics,
    personas,
    isExpanded,
    viewBoxWidth,
    viewBoxHeight,
    getPairwiseAgreement,
  ]);

  const nodeMap = useMemo(() => {
    const map = new Map<string, (typeof graphNodes)[0]>();
    graphNodes.forEach((n) => {
      map.set(n.name, n);
      map.set(n.id, n);
    });
    return map;
  }, [graphNodes]);

  // Determine individual green circular aura visibility
  const agentAgreementStatus = useMemo(() => {
    const statusMap = new Map<
      string,
      { hasHighAgreement: boolean; maxScore: number }
    >();
    graphNodes.forEach((a) => {
      let maxScore = 0;
      graphNodes.forEach((b) => {
        if (a.name !== b.name) {
          const score = getPairwiseAgreement(a.name, b.name);
          if (score > maxScore) maxScore = score;
        }
      });
      // Green circle ONLY appears if agreement is legitimately high (>= 0.72)
      statusMap.set(a.name, {
        hasHighAgreement: maxScore >= 0.72,
        maxScore,
      });
    });
    return statusMap;
  }, [graphNodes, getPairwiseAgreement]);

  const latestAgreement = useMemo(() => {
    if (!analytics?.agreement || analytics.agreement.length === 0) return null;
    return analytics.agreement[analytics.agreement.length - 1];
  }, [analytics]);

  const topInfluencer = analytics?.influence?.top_influencer || null;
  const influenceScores = useMemo(
    () => analytics?.influence?.scores || {},
    [analytics],
  );
  const maxInfluenceScore = useMemo(() => {
    const vals = Object.values(influenceScores);
    return vals.length > 0 ? Math.max(...vals, 1) : 1;
  }, [influenceScores]);

  // Group citations by domain
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

  // =========================================================================
  // DOWNLOAD DELIBERATION REPORT
  // =========================================================================
  const handleDownloadReport = () => {
    const reportTopic =
      topic ||
      (analytics as unknown as { topic?: string })?.topic ||
      "AI Deliberation Session";
    const dateStr = new Date().toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });

    const consensusScore = latestAgreement
      ? Math.round(latestAgreement.agreement_score * 100)
      : 0;
    const consensusClass = latestAgreement
      ? latestAgreement.classification
      : "Unknown";

    let md = `# Deliberation Report: ${reportTopic}\n\n`;
    md += `**Date:** ${dateStr}  \n`;
    md += `**Total Recorded Turns:** ${turns.length}  \n`;
    md += `**Participating Panelists:** ${personas.length}  \n`;
    md += `**Network Consensus Index:** ${consensusScore}% (${consensusClass})  \n\n`;

    md += `---\n\n## 1. Stakeholder Panel & Final Stances\n\n`;
    personas.forEach((p) => {
      const node = graphNodes.find((n) => n.name === p.name);
      const stance = node
        ? node.currentStance > 0
          ? `+${node.currentStance.toFixed(2)}`
          : node.currentStance.toFixed(2)
        : "0.00";
      md += `### ${p.name}\n`;
      md += `- **Background:** ${p.background}\n`;
      md += `- **Tone:** ${p.tone}\n`;
      md += `- **Final Graded Stance:** \`${stance}\`\n`;
      md += `- **Persuasion Influence Score:** \`${(influenceScores[p.name] || 0).toFixed(2)}\`\n\n`;
    });

    if (analytics?.key_findings && analytics.key_findings.length > 0) {
      md += `## 2. Distilled Key Findings (TASA Consensus Engine)\n\n`;
      analytics.key_findings.forEach((kf, idx) => {
        md += `${idx + 1}. **"${kf.statement}"**\n`;
        md += `   - **Deliberation Heat:** ${kf.heat} turns (Rounds ${kf.first_round}-${kf.last_round})\n`;
        md += `   - **Supporting Panelists:** ${kf.supporting_agents?.join(", ") || "None"}\n`;
        md += `   - **Opposing Panelists:** ${kf.opposing_agents?.join(", ") || "None"}\n\n`;
      });
    }

    if (
      analytics?.persuasion_signals &&
      analytics.persuasion_signals.length > 0
    ) {
      md += `## 3. Notable Persuasion & Polarization Shifts\n\n`;
      analytics.persuasion_signals.forEach((sig) => {
        const sign =
          sig.shift > 0 ? `+${sig.shift.toFixed(2)}` : sig.shift.toFixed(2);
        md += `- **Round ${sig.id?.split("_")[0] || "•"}:** ${sig.source} influenced **${sig.target}** (Δ ${sign}, Dynamic: ${sig.dynamic})\n`;
      });
      md += `\n`;
    }

    if (groupedCitations.length > 0) {
      md += `## 4. Regulatory & Empirical Citations Bibliography\n\n`;
      groupedCitations.forEach((grp) => {
        md += `### ${grp.domain} (${grp.count} citation${grp.count === 1 ? "" : "s"})\n`;
        grp.urls.forEach((u) => {
          md += `- <${u}>\n`;
        });
        md += `\n`;
      });
    }

    const blob = new Blob([md], { type: "text/markdown;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `deliberation-report-${Date.now()}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
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

  return (
    <aside className="relative z-30 flex flex-col h-full min-h-0 border-l border-border/70 bg-sidebar/50 text-sidebar-foreground transition-all duration-300">
      {/* Expand/Collapse Toggle Button */}
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

      {/* Header */}
      <div className="p-3 border-b border-border/60 bg-sidebar shrink-0 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <div className="p-1 rounded-md bg-teal-500/10 text-teal-600 dark:text-teal-400 shrink-0">
            <Sparkles className="w-3.5 h-3.5" />
          </div>
          <span className="text-xs font-bold uppercase tracking-wider text-teal-800 dark:text-teal-300 truncate">
            Deliberation Analytics
          </span>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <Button
            size="sm"
            variant="outline"
            onClick={handleDownloadReport}
            className="h-6 px-2 text-[10px] font-semibold border-teal-500/30 text-teal-700 dark:text-teal-300 hover:bg-teal-50 dark:hover:bg-teal-950/60 cursor-pointer"
            title="Download full deliberation analysis report"
          >
            <Download className="w-3 h-3 mr-1" />
            Report
          </Button>
          {isExpanded && latestAgreement && (
            <Badge
              variant="outline"
              className="text-[9px] font-mono border-teal-500/40 text-teal-700 dark:text-teal-300 bg-teal-50/50 dark:bg-teal-950/40"
            >
              Consensus: {Math.round(latestAgreement.agreement_score * 100)}%
            </Badge>
          )}
        </div>
      </div>

      {/* Main Analytics Feed */}
      <div
        ref={containerRef}
        className="flex-1 min-h-0 overflow-y-auto p-3 space-y-3.5 scrollbar-thin"
      >
        {/* ===================================================================
            1. INFLUENCE NETWORK GRAPH (Clean Overlapping Circles & Stance Distances)
            =================================================================== */}
        <Card className="p-3 bg-card border-border shadow-xs relative overflow-hidden">
          {/* Header: Title Left, Explanation Mark Far Right */}
          <div className="flex items-center justify-between w-full mb-2">
            <div className="flex items-center gap-1.5 min-w-0">
              <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400 truncate">
                <GitGraph className="w-3.5 h-3.5 shrink-0" />
                Network Topology
              </CardTitle>
              {isExpanded && (
                <Badge
                  variant="outline"
                  className="text-[9px] border-emerald-500/30 text-emerald-700 dark:text-emerald-300 font-mono shrink-0 ml-1"
                >
                  Green Halos = Agreement
                </Badge>
              )}
            </div>

            <div className="flex items-center shrink-0 ml-2">
              <MetricInfoBadge
                title="Topological Agreement & Influence Network"
                whatItIs="Displays directed persuasion vectors between agents. Distance reflects agreement: aligned agents draw together, while polarized agents spread apart."
                calculation="Agents with agreement ≥ 72% display glowing circular halos that overlap. Opposing agents sit farther apart with no green background."
              />
            </div>
          </div>

          <div
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            className={`w-full ${isExpanded ? "h-72" : "h-60"} bg-background/60 rounded-xl border border-border/80 relative overflow-hidden flex items-center justify-center transition-all ${
              isDragging ? "cursor-grabbing" : "cursor-grab"
            }`}
          >
            {/* Viewport Reset / Zoom Controls */}
            <div className="absolute top-2 right-2 z-20 flex items-center gap-1 bg-card/90 backdrop-blur border border-border p-1 rounded-md shadow-2xs">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setZoom((z) => Math.min(z + 0.2, 2.5))}
                className="h-5 w-5 p-0 cursor-pointer"
                title="Zoom In"
              >
                <ZoomIn className="w-3 h-3" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setZoom((z) => Math.max(z - 0.2, 0.6))}
                className="h-5 w-5 p-0 cursor-pointer"
                title="Zoom Out"
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
                title="Reset View"
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
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerUnits="userSpaceOnUse"
                  markerWidth="7.5"
                  markerHeight="7.5"
                  orient="auto"
                >
                  <path
                    d="M 0 1.5 L 8.5 5 L 0 8.5 z"
                    className="fill-teal-600/80 dark:fill-teal-400/80"
                  />
                </marker>
                <marker
                  id="arrowhead-active"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerUnits="userSpaceOnUse"
                  markerWidth="8.5"
                  markerHeight="8.5"
                  orient="auto"
                >
                  <path d="M 0 1.5 L 8.5 5 L 0 8.5 z" fill="#0d9488" />
                </marker>

                <radialGradient id="softGreenHalo">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.45" />
                  <stop offset="65%" stopColor="#10b981" stopOpacity="0.18" />
                  <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                </radialGradient>
              </defs>

              <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                {/* =========================================================
                    LAYER 1: CLEAN GREEN CIRCULAR HALOS (Overlapping if Agree)
                    ========================================================= */}
                {graphNodes.map((node) => {
                  const status = agentAgreementStatus.get(node.name);
                  if (!status || !status.hasHighAgreement) return null;

                  const haloR = isExpanded ? 46 : 38;
                  const opacity = Math.min(
                    0.9,
                    0.45 + (status.maxScore - 0.72) * 1.5,
                  );

                  return (
                    <circle
                      key={`halo-${node.id}`}
                      cx={node.x}
                      cy={node.y}
                      r={haloR}
                      fill="url(#softGreenHalo)"
                      opacity={opacity}
                      className="pointer-events-none transition-all duration-300"
                    />
                  );
                })}

                {/* =========================================================
                    LAYER 2: DIRECTED PERSUASION EDGES
                    ========================================================= */}
                {analytics?.edges?.map((edge, i) => {
                  const src = nodeMap.get(edge.source);
                  const tgt = nodeMap.get(edge.target);
                  if (!src || !tgt) return null;

                  const dx = tgt.x - src.x;
                  const dy = tgt.y - src.y;

                  const curvature = 0.2;
                  const cx = (src.x + tgt.x) / 2 - dy * curvature;
                  const cy = (src.y + tgt.y) / 2 + dx * curvature;

                  const nodeRadius = 17;

                  const dSrcX = cx - src.x;
                  const dSrcY = cy - src.y;
                  const distSrc = Math.hypot(dSrcX, dSrcY) || 1;
                  const startX = src.x + (dSrcX / distSrc) * nodeRadius;
                  const startY = src.y + (dSrcY / distSrc) * nodeRadius;

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
                        stroke={isHighlighted ? "#0d9488" : "currentColor"}
                        strokeWidth={
                          isHighlighted ? 2.2 : Math.max(1.1, weight * 1.8)
                        }
                        markerEnd={
                          isHighlighted
                            ? "url(#arrowhead-active)"
                            : "url(#arrowhead)"
                        }
                        className="text-teal-600/70 dark:text-teal-400/60 transition-colors"
                      />
                    </g>
                  );
                })}

                {/* =========================================================
                    LAYER 3: AGENT NODES
                    ========================================================= */}
                {graphNodes.map((n) => {
                  const isSel = selectedAgent === n.name;
                  const fullName = n.name || n.id || "Agent";
                  const stanceStr =
                    n.currentStance > 0
                      ? `+${n.currentStance.toFixed(1)}`
                      : n.currentStance.toFixed(1);
                  const labelText = `${fullName} (${stanceStr})`;
                  const pillWidth = Math.max(78, labelText.length * 5.4 + 14);

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
                        className={`transition-all duration-200 stroke-2 ${
                          isSel
                            ? "stroke-teal-500 fill-teal-50 dark:fill-teal-950"
                            : "stroke-border/80 group-hover:stroke-teal-500 fill-card"
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
                          x={-pillWidth / 2}
                          y="-7"
                          width={pillWidth}
                          height="14"
                          rx="4"
                          className="fill-card/95 stroke-border/90 shadow-2xs"
                          strokeWidth="0.8"
                        />
                        <text
                          textAnchor="middle"
                          dominantBaseline="middle"
                          className="text-[8px] font-bold fill-foreground select-none"
                        >
                          {labelText}
                        </text>
                      </g>
                    </g>
                  );
                })}
              </g>
            </svg>

            <div className="absolute bottom-1.5 left-2 text-[8px] text-muted-foreground flex items-center gap-1 font-mono pointer-events-none">
              <Move className="w-2.5 h-2.5 text-teal-600" />
              <span>Pan & Zoom enabled</span>
            </div>
          </div>
        </Card>

        {/* ===================================================================
            2. TASA DISTILLED KEY FINDINGS
            =================================================================== */}
        {analytics?.key_findings && analytics.key_findings.length > 0 && (
          <Card className="p-3 bg-card border-border shadow-xs space-y-2.5">
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center gap-1.5 min-w-0">
                <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400 truncate">
                  <Flame className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                  Distilled Key Findings
                </CardTitle>
                {isExpanded && (
                  <Badge
                    variant="outline"
                    className="text-[9px] font-mono border-amber-500/40 text-amber-600 shrink-0 ml-1"
                  >
                    {analytics.key_findings.length} Confirmed
                  </Badge>
                )}
              </div>

              <div className="flex items-center shrink-0 ml-2">
                <MetricInfoBadge
                  title="Topic-Anchored Semantic Accumulator (TASA)"
                  whatItIs="Online semantic clustering identifying persistent, high-heat policy contentions and emerging consensus findings across debate rounds."
                  calculation="Statements are embedded and clustered at cosine threshold ≥ 0.84 with damped centroid anchoring. Once heat reaches ≥ 2 turns, a dedicated micro-LLM permanently distills the thematic policy finding."
                />
              </div>
            </div>

            <div className="space-y-2">
              {analytics.key_findings.map((finding) => (
                <div
                  key={finding.id}
                  className="p-2.5 rounded-lg bg-muted/30 border border-border/70 space-y-1.5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-xs font-semibold text-foreground leading-snug">
                      &quot;{finding.statement}&quot;
                    </p>
                    <Badge
                      variant="secondary"
                      className="text-[9px] font-mono px-1.5 py-0 h-4 shrink-0 bg-amber-100 text-amber-900 dark:bg-amber-950/60 dark:text-amber-300"
                    >
                      <Flame className="w-2.5 h-2.5 mr-0.5 inline fill-current" />
                      Heat {finding.heat}
                    </Badge>
                  </div>

                  <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1 border-t border-border/40">
                    <div className="flex items-center gap-1 flex-wrap">
                      {finding.supporting_agents?.map((a) => (
                        <span
                          key={a}
                          className="inline-flex items-center gap-0.5 px-1 py-0.2 rounded bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 font-medium text-[9px]"
                        >
                          <CheckCircle2 className="w-2.5 h-2.5" />
                          {a.split(" ")[0]}
                        </span>
                      ))}
                      {finding.opposing_agents?.map((a) => (
                        <span
                          key={a}
                          className="inline-flex items-center gap-0.5 px-1 py-0.2 rounded bg-rose-500/10 text-rose-700 dark:text-rose-300 font-medium text-[9px]"
                        >
                          <XCircle className="w-2.5 h-2.5" />
                          {a.split(" ")[0]}
                        </span>
                      ))}
                    </div>
                    <span className="font-mono text-[9px] text-muted-foreground shrink-0">
                      Rounds {finding.first_round}-{finding.last_round}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* ===================================================================
            3. SMOOTHED OPINION CURVES
            =================================================================== */}
        <Card className="p-3 bg-card border-border shadow-xs">
          <CardHeader className="p-0 pb-2 flex-row items-center justify-between w-full">
            <div className="flex items-center gap-1.5 min-w-0">
              <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400 truncate">
                <Activity className="w-3.5 h-3.5 shrink-0" />
                Smoothed Opinion Curves
              </CardTitle>
              {isExpanded && (
                <span className="text-[9px] font-mono text-muted-foreground shrink-0 ml-1">
                  Range: [-5.0, +5.0]
                </span>
              )}
            </div>

            <div className="flex items-center shrink-0 ml-2">
              <MetricInfoBadge
                title="Opinion Drift Trajectories"
                whatItIs="Tracks continuous stance drift [-5.0, +5.0] for every panelist across discussion rounds."
                calculation="Each turn is graded via DeBERTa-v3 NLI continuous 2-way softmax. Stances are forward-filled across rounds to ensure continuous lines with visible markers."
              />
            </div>
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

        {/* ===================================================================
            4. CONSENSUS DYNAMICS
            =================================================================== */}
        <Card className="p-3 bg-card border-border shadow-xs">
          <div className="flex items-center justify-between w-full mb-2">
            <div className="flex items-center gap-1.5 min-w-0">
              <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400 truncate">
                <Scale className="w-3.5 h-3.5 shrink-0" />
                Consensus Dynamics
              </CardTitle>
              {latestAgreement && (
                <Badge className="text-[9px] bg-teal-600 text-white font-mono px-1.5 py-0 h-4 shrink-0 ml-1">
                  {latestAgreement.classification}
                </Badge>
              )}
            </div>

            <div className="flex items-center shrink-0 ml-2">
              <MetricInfoBadge
                title="Consensus Over Rounds"
                whatItIs="Chronological agreement tracking whether the deliberation is converging toward consensus or polarizing over time."
                calculation="Calculated per round across all active agents' most recent stances: 1.0 - (mean absolute pairwise diff / 10.0). Scores range from 0.0 (extreme polarization) to 1.0 (unanimous consensus)."
              />
            </div>
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

        {/* ===================================================================
            5. PERSUASION POWER RANKINGS
            =================================================================== */}
        <Card className="p-3 bg-card border-border shadow-xs space-y-2.5">
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-1.5 min-w-0">
              <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400 truncate">
                <Award className="w-3.5 h-3.5 shrink-0" />
                Persuasion Power Rankings
              </CardTitle>
              {isExpanded && (
                <span className="text-[9px] text-muted-foreground font-mono shrink-0 ml-1">
                  Outgoing Weight
                </span>
              )}
            </div>

            <div className="flex items-center shrink-0 ml-2">
              <MetricInfoBadge
                title="Persuasion Power Ranking"
                whatItIs="Total outbound persuasion effect generated by each stakeholder across the debate."
                calculation="Sum of outgoing edge weights from this agent in the influence matrix. Convergence only counts if the listener is permitted to hear the agent in the listening matrix."
              />
            </div>
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
                      className={`h-full rounded-full transition-all duration-500 ${
                        isLead ? "bg-amber-500" : "bg-teal-600"
                      }`}
                      style={{ width: `${barPercent}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        {/* ===================================================================
            6. PERSUASION SIGNALS LOG
            =================================================================== */}
        <Card className="p-3 bg-card border-border shadow-xs space-y-2">
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-1.5 min-w-0">
              <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400 truncate">
                <TrendingUp className="w-3.5 h-3.5 shrink-0" />
                Persuasion Signals Log
              </CardTitle>
              {isExpanded && (
                <span className="text-[9px] text-muted-foreground font-mono shrink-0 ml-1">
                  CFG Shifts
                </span>
              )}
            </div>

            <div className="flex items-center shrink-0 ml-2">
              <MetricInfoBadge
                title="Persuasion Shift Signals"
                whatItIs="Step-by-step record whenever a speaker successfully persuades or polarizes a listener."
                calculation="Magnitude Δ = Current_Stance - Prior_Stance. Guidance scale γ = |Δ| * 0.05. Categorized as Convergence (moving closer) or Polarization (moving further away)."
              />
            </div>
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

        {/* ===================================================================
            7. GROUPED POLICY CITATIONS
            =================================================================== */}
        <Card className="p-3 bg-card border-border shadow-xs space-y-2">
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-1.5 min-w-0">
              <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-teal-700 dark:text-teal-400 truncate">
                <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                Policy Citations by Domain
              </CardTitle>
            </div>

            <div className="flex items-center shrink-0 ml-2 gap-1.5">
              <Layers className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
              <MetricInfoBadge
                title="Grouped Policy Evidence"
                whatItIs="External regulatory, legal, and empirical documentation cited by agents during deliberation."
                calculation="Aggregated across turns, grouped by root domain, with citation frequency counts and interactive links."
              />
            </div>
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
