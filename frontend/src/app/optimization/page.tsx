"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Zap,
  ArrowRight,
  ArrowLeft,
  Play,
  Pause,
  RotateCcw,
  ChevronLeft,
  Cpu,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  Maximize2,
  Minimize2,
  Search,
  Radio,
  Server,
  Filter,
} from "lucide-react";

export default function OptimizationSlidesPage() {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isPlayingBoth, setIsPlayingBoth] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const beforeVideoRef = useRef<HTMLVideoElement>(null);
  const afterVideoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const totalSlides = 5;

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        setCurrentSlide((s) => Math.min(s + 1, totalSlides - 1));
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        setCurrentSlide((s) => Math.max(s - 1, 0));
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const toggleSyncPlayback = () => {
    if (!beforeVideoRef.current || !afterVideoRef.current) return;
    if (isPlayingBoth) {
      beforeVideoRef.current.pause();
      afterVideoRef.current.pause();
      setIsPlayingBoth(false);
    } else {
      beforeVideoRef.current.play();
      afterVideoRef.current.play();
      setIsPlayingBoth(true);
    }
  };

  const restartVideos = () => {
    if (!beforeVideoRef.current || !afterVideoRef.current) return;
    beforeVideoRef.current.currentTime = 0;
    afterVideoRef.current.currentTime = 0;
    beforeVideoRef.current.play();
    afterVideoRef.current.play();
    setIsPlayingBoth(true);
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen?.();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen?.();
      setIsFullscreen(false);
    }
  };

  return (
    <div
      ref={containerRef}
      className="flex flex-col h-screen max-h-screen w-screen overflow-hidden bg-background text-foreground select-none"
    >
      {/* Top Navbar */}
      <header className="h-16 border-b border-border/70 px-6 flex items-center justify-between bg-card/70 backdrop-blur-md shrink-0 z-20">
        <div className="flex items-center gap-4">
          <Link href="/">
            <Button
              variant="outline"
              size="sm"
              className="h-9 px-3 gap-2 border-teal-500/30 text-teal-700 dark:text-teal-300 hover:bg-teal-500/10 cursor-pointer font-medium"
            >
              <ChevronLeft className="w-4 h-4" />
              <span>Exit to Arena</span>
            </Button>
          </Link>
          <div className="h-5 w-px bg-border" />
          <div className="flex items-center gap-2.5">
            <span className="p-1.5 rounded-lg bg-teal-500/10 text-teal-600 dark:text-teal-400 font-bold">
              <Zap className="w-5 h-5" />
            </span>
            <div>
              <h1 className="text-sm font-bold tracking-tight text-foreground flex items-center gap-2">
                Deliberation Engine: Latency & Architectural Optimization
              </h1>
              <span className="text-[11px] text-muted-foreground font-mono">
                Benchmark Trace Audit: 82.58s → 1.29s (63.7× Real-Time Speedup)
              </span>
            </div>
          </div>
        </div>

        {/* Slide Progress / Controls */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            {Array.from({ length: totalSlides }).map((_, idx) => (
              <button
                key={idx}
                onClick={() => setCurrentSlide(idx)}
                className={`h-2.5 rounded-full transition-all cursor-pointer ${
                  currentSlide === idx
                    ? "w-8 bg-teal-600 dark:bg-teal-400 shadow-xs"
                    : "w-2.5 bg-muted hover:bg-muted-foreground/50"
                }`}
                title={`Go to slide ${idx + 1}`}
              />
            ))}
          </div>

          <span className="text-xs font-mono font-semibold px-2 py-1 rounded bg-muted/60 text-muted-foreground">
            SLIDE {currentSlide + 1} OF {totalSlides}
          </span>

          <div className="flex items-center gap-1.5">
            <Button
              variant="outline"
              size="sm"
              disabled={currentSlide === 0}
              onClick={() => setCurrentSlide((s) => Math.max(s - 1, 0))}
              className="h-9 w-9 p-0 cursor-pointer"
            >
              <ArrowLeft className="w-4 h-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={currentSlide === totalSlides - 1}
              onClick={() =>
                setCurrentSlide((s) => Math.min(s + 1, totalSlides - 1))
              }
              className="h-9 w-9 p-0 cursor-pointer"
            >
              <ArrowRight className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleFullscreen}
              className="h-9 w-9 p-0 cursor-pointer hidden md:flex text-muted-foreground hover:text-foreground"
            >
              {isFullscreen ? (
                <Minimize2 className="w-4 h-4" />
              ) : (
                <Maximize2 className="w-4 h-4" />
              )}
            </Button>
          </div>
        </div>
      </header>

      {/* Main Slide Stage (Maximized Viewport) */}
      <main className="flex-1 min-h-0 overflow-y-auto px-6 py-4 flex flex-col justify-center items-center">
        <div className="w-full max-w-[96vw] xl:max-w-[1780px] h-full flex flex-col justify-between">
          {/* =========================================================================
              SLIDE 1: EXPANDED VIDEO DUEL (BEFORE VS AFTER)
             ========================================================================= */}
          {currentSlide === 0 && (
            <div className="flex flex-col h-full justify-between gap-4 animate-in fade-in zoom-in-95 duration-200">
              <div className="flex items-center justify-between border-b border-border/60 pb-3 shrink-0">
                <div>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="outline"
                      className="border-teal-500/30 text-teal-700 dark:text-teal-300 font-mono text-xs px-2.5 py-0.5"
                    >
                      SLIDE 1 • EMPIRICAL REPLAY DUEL
                    </Badge>
                    <span className="text-xs text-muted-foreground font-mono">
                      Single Deliberation Step Execution
                    </span>
                  </div>
                  <h2 className="text-2xl font-black tracking-tight text-foreground mt-1">
                    Side-by-Side Execution Replay: 82.58s vs 1.29s
                  </h2>
                </div>

                {/* Video Playback Synchronizer */}
                <div className="flex items-center gap-3 bg-muted/40 border border-border/80 px-3.5 py-1.5 rounded-xl shadow-2xs">
                  <Button
                    size="sm"
                    onClick={toggleSyncPlayback}
                    className="h-8 px-3.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold cursor-pointer gap-2"
                  >
                    {isPlayingBoth ? (
                      <Pause className="w-3.5 h-3.5 fill-current" />
                    ) : (
                      <Play className="w-3.5 h-3.5 fill-current" />
                    )}
                    <span>
                      {isPlayingBoth ? "Pause Both" : "Play Synced Videos"}
                    </span>
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={restartVideos}
                    className="h-8 px-2.5 gap-1.5 cursor-pointer border-border"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Reset</span>
                  </Button>
                  <div className="h-4 w-px bg-border" />
                  <span className="text-[11px] font-mono text-muted-foreground">
                    Both videos normalized at 1.0× playback speed
                  </span>
                </div>
              </div>

              {/* Huge Side-by-Side Video Players */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 flex-1 min-h-0 items-center">
                {/* BEFORE VIDEO */}
                <Card className="p-4 bg-card border-rose-500/30 shadow-md flex flex-col h-full justify-between">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full bg-rose-500 animate-pulse" />
                      <span className="font-bold text-sm uppercase tracking-wider text-rose-600 dark:text-rose-400">
                        Before: Blocking Architecture (Trace da99009b)
                      </span>
                    </div>
                    <Badge
                      variant="destructive"
                      className="font-mono text-xs px-2.5 py-1 font-bold"
                    >
                      82.58s Latency
                    </Badge>
                  </div>

                  <div className="relative rounded-xl overflow-hidden bg-black/90 aspect-video border border-border/80 flex items-center justify-center flex-1 max-h-[500px]">
                    <video
                      ref={beforeVideoRef}
                      controls
                      playsInline
                      className="w-full h-full object-contain"
                    >
                      <source src="/video/Before.mp4" type="video/mp4" />
                      Your browser does not support HTML video.
                    </video>
                  </div>

                  <div className="mt-3 grid grid-cols-4 gap-2 pt-2.5 border-t border-border/60 text-xs font-mono">
                    <div className="bg-muted/40 p-2 rounded">
                      <span className="text-[10px] text-muted-foreground block">
                        Model
                      </span>
                      <span className="font-semibold truncate block">
                        DeepSeek-v4-Flash
                      </span>
                    </div>
                    <div className="bg-rose-500/10 p-2 rounded text-rose-700 dark:text-rose-300">
                      <span className="text-[10px] block opacity-80">
                        Tool Ingestion
                      </span>
                      <span className="font-bold">47.28s (Blocked)</span>
                    </div>
                    <div className="bg-rose-500/10 p-2 rounded text-rose-700 dark:text-rose-300">
                      <span className="text-[10px] block opacity-80">
                        Stance Grading
                      </span>
                      <span className="font-bold">17.62s (Remote LLM)</span>
                    </div>
                    <div className="bg-muted/40 p-2 rounded">
                      <span className="text-[10px] text-muted-foreground block">
                        Prefill Context
                      </span>
                      <span className="font-semibold text-rose-500">
                        24,111 Tokens
                      </span>
                    </div>
                  </div>
                </Card>

                {/* AFTER VIDEO */}
                <Card className="p-4 bg-card border-emerald-500/40 shadow-md flex flex-col h-full justify-between">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full bg-emerald-500 animate-ping" />
                      <span className="font-bold text-sm uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                        After: Streaming & Decoupled Engine (Trace dd51916e)
                      </span>
                    </div>
                    <Badge className="bg-emerald-600 hover:bg-emerald-600 text-white font-mono text-xs px-2.5 py-1 font-bold">
                      1.29s Latency (63.7× Speedup)
                    </Badge>
                  </div>

                  <div className="relative rounded-xl overflow-hidden bg-black/90 aspect-video border border-border/80 flex items-center justify-center flex-1 max-h-[500px]">
                    <video
                      ref={afterVideoRef}
                      controls
                      playsInline
                      className="w-full h-full object-contain"
                    >
                      <source src="/video/After.mp4" type="video/mp4" />
                      Your browser does not support HTML video.
                    </video>
                  </div>

                  <div className="mt-3 grid grid-cols-4 gap-2 pt-2.5 border-t border-border/60 text-xs font-mono">
                    <div className="bg-muted/40 p-2 rounded">
                      <span className="text-[10px] text-muted-foreground block">
                        Model
                      </span>
                      <span className="font-semibold text-teal-600 dark:text-teal-400 truncate block">
                        gpt-oss-120b
                      </span>
                    </div>
                    <div className="bg-emerald-500/10 p-2 rounded text-emerald-700 dark:text-emerald-300">
                      <span className="text-[10px] block opacity-80">
                        TTFT Latency
                      </span>
                      <span className="font-bold">0.544s (544ms)</span>
                    </div>
                    <div className="bg-emerald-500/10 p-2 rounded text-emerald-700 dark:text-emerald-300">
                      <span className="text-[10px] block opacity-80">
                        Local ONNX Stance
                      </span>
                      <span className="font-bold">0.39s (ONNX-CPU)</span>
                    </div>
                    <div className="bg-muted/40 p-2 rounded">
                      <span className="text-[10px] text-muted-foreground block">
                        Prefill Context
                      </span>
                      <span className="font-semibold text-emerald-600">
                        2,163 Tokens (-91%)
                      </span>
                    </div>
                  </div>
                </Card>
              </div>
            </div>
          )}

          {/* =========================================================================
              SLIDE 2: ABSOLUTE TIME-AXIS COMPARATIVE SPAN TIMELINE (NOT PERCENTAGES)
             ========================================================================= */}
          {currentSlide === 1 && (
            <div className="flex flex-col h-full justify-between gap-4 animate-in fade-in zoom-in-95 duration-200">
              <div className="border-b border-border/60 pb-2.5 shrink-0">
                <Badge
                  variant="outline"
                  className="border-teal-500/30 text-teal-700 dark:text-teal-300 font-mono text-xs px-2.5 py-0.5"
                >
                  SLIDE 2 • ABSOLUTE TIME-AXIS AUDIT
                </Badge>
                <h2 className="text-2xl font-black tracking-tight text-foreground mt-1">
                  Comparative Trace Timeline (Seconds Scale: 0s to 85s)
                </h2>
                <p className="text-xs text-muted-foreground">
                  Dismantling deceptive relative-percentage charts. Both traces
                  are rendered on the same absolute chronological 85-second
                  linear scale.
                </p>
              </div>

              {/* Component Legend */}
              <div className="flex flex-wrap items-center gap-3 p-3 bg-muted/40 border border-border/70 rounded-xl text-xs font-mono shrink-0">
                <span className="font-bold text-foreground mr-1 uppercase text-[10px]">
                  Span Legend:
                </span>
                <div className="flex items-center gap-1.5">
                  <span className="w-3.5 h-3.5 rounded bg-amber-500" />
                  <span>Router / Orchestration</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3.5 h-3.5 rounded bg-sky-500" />
                  <span>LLM Tool Decision</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3.5 h-3.5 rounded bg-rose-600" />
                  <span>Synchronous Tool Execution (Scrape / Neo4j)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3.5 h-3.5 rounded bg-indigo-600" />
                  <span>Speech Synthesis Generation</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3.5 h-3.5 rounded bg-purple-600" />
                  <span>Remote LLM Stance Grader</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3.5 h-3.5 rounded bg-emerald-500" />
                  <span>Local ONNX-CPU NLI Stance Evaluation</span>
                </div>
              </div>

              {/* The Absolute Timeline Scale Canvas */}
              <Card className="p-6 bg-card border-border shadow-md space-y-6 flex-1 flex flex-col justify-center">
                {/* Time Axis Ticks (0s to 85s) */}
                <div className="space-y-1">
                  <div className="relative w-full h-5 border-b border-border/80 text-[10px] font-mono text-muted-foreground">
                    <span className="absolute left-0">0.0s</span>
                    <span className="absolute left-[11.7%]">10s</span>
                    <span className="absolute left-[23.5%]">20s</span>
                    <span className="absolute left-[35.2%]">30s</span>
                    <span className="absolute left-[47.0%]">40s</span>
                    <span className="absolute left-[58.8%]">50s</span>
                    <span className="absolute left-[70.5%]">60s</span>
                    <span className="absolute left-[82.3%]">70s</span>
                    <span className="absolute left-[94.1%]">80s</span>
                    <span className="absolute right-0 text-foreground font-bold">
                      85.0s
                    </span>
                  </div>

                  {/* Grid Lines */}
                  <div className="relative w-full h-3">
                    {[0, 10, 20, 30, 40, 50, 60, 70, 80, 85].map((tick) => (
                      <div
                        key={tick}
                        style={{ left: `${(tick / 85) * 100}%` }}
                        className="absolute top-0 bottom-0 w-px bg-border/40"
                      />
                    ))}
                  </div>
                </div>

                {/* BEFORE BAR (82.58s = 97.1% of track) */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="font-bold text-rose-600 dark:text-rose-400 flex items-center gap-2 text-sm">
                      <AlertTriangle className="w-4 h-4" />
                      Trace da99009b (Before): 82.58 Seconds Total Duration
                    </span>
                    <span className="text-muted-foreground">
                      deepseek-v4-flash • Synchronous Tool Blocking
                    </span>
                  </div>

                  {/* Absolute width bar: 82.58 / 85 = 97.15% */}
                  <div className="relative w-full h-11 bg-muted/30 rounded-lg p-0.5 border border-border/80">
                    <div
                      style={{ width: "97.15%" }}
                      className="h-full rounded flex text-[11px] font-mono text-white font-semibold overflow-hidden shadow-sm"
                    >
                      <div
                        style={{ width: `${(1.85 / 82.58) * 100}%` }}
                        className="bg-amber-500 flex items-center justify-center truncate px-1"
                        title="Orchestration Routing: 1.85s"
                      >
                        1.9s
                      </div>
                      <div
                        style={{ width: `${(4.84 / 82.58) * 100}%` }}
                        className="bg-sky-500 flex items-center justify-center truncate px-1"
                        title="LLM Tool Decision: 4.84s"
                      >
                        4.8s
                      </div>
                      <div
                        style={{ width: `${(47.28 / 82.58) * 100}%` }}
                        className="bg-rose-600 flex items-center justify-center truncate px-2 font-black tracking-wide"
                        title="execute_tool: 47.28s"
                      >
                        47.28s Sync Ingestion Crawl (Playwright + Voyage +
                        Neo4j)
                      </div>
                      <div
                        style={{ width: `${(10.92 / 82.58) * 100}%` }}
                        className="bg-indigo-600 flex items-center justify-center truncate px-1"
                        title="Speech Generation: 10.92s"
                      >
                        10.9s
                      </div>
                      <div
                        style={{ width: `${(17.62 / 82.58) * 100}%` }}
                        className="bg-purple-600 flex items-center justify-center truncate px-1 font-bold"
                        title="Remote LLM Grader: 17.62s"
                      >
                        17.62s Grader
                      </div>
                    </div>
                  </div>
                </div>

                {/* AFTER BAR (1.295s = 1.52% of track) */}
                <div className="space-y-2 pt-2">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-2 text-sm">
                      <CheckCircle2 className="w-4 h-4" />
                      Trace dd51916e (After): 1.295 Seconds Total Duration
                      (63.7× Faster)
                    </span>
                    <span className="text-teal-600 dark:text-teal-400 font-semibold">
                      openai/gpt-oss-120b • Streaming + ONNX Local Grader
                    </span>
                  </div>

                  {/* Absolute width bar: 1.295 / 85 = 1.52% */}
                  <div className="relative w-full h-11 bg-muted/30 rounded-lg p-0.5 border border-border/80 flex items-center">
                    <div
                      style={{ width: "1.52%" }}
                      className="h-full rounded bg-emerald-500 shadow-md flex items-center justify-center text-[10px] text-white font-black shrink-0"
                      title="Total Turn: 1.295s"
                    >
                      ⚡
                    </div>

                    {/* Zoomed callout pointing to this 1.3s sliver */}
                    <div className="ml-3 flex items-center gap-2 text-xs font-mono">
                      <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-500/30">
                        1.295s Complete Turn
                      </span>
                      <span className="text-muted-foreground">
                        (Routing: 0.001s • Speech Generation: 0.818s • Local
                        ONNX: 0.390s • Tool: 0s blocking)
                      </span>
                    </div>
                  </div>
                </div>
              </Card>

              {/* Exact Metrics Data Table */}
              <div className="grid grid-cols-5 gap-3 shrink-0 text-xs font-mono">
                <div className="p-2.5 rounded-lg bg-card border border-border">
                  <span className="text-muted-foreground text-[10px] block">
                    Orchestrator Routing
                  </span>
                  <div className="font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                    0.001s{" "}
                    <span className="line-through text-rose-500 font-normal text-[10px] ml-1">
                      1.85s
                    </span>
                  </div>
                </div>
                <div className="p-2.5 rounded-lg bg-card border border-border">
                  <span className="text-muted-foreground text-[10px] block">
                    LLM Tool Call Phase
                  </span>
                  <div className="font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                    0.00s{" "}
                    <span className="line-through text-rose-500 font-normal text-[10px] ml-1">
                      4.84s
                    </span>
                  </div>
                </div>
                <div className="p-2.5 rounded-lg bg-card border border-border">
                  <span className="text-muted-foreground text-[10px] block">
                    Web Search & Scraping
                  </span>
                  <div className="font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                    0.00s (Queue){" "}
                    <span className="line-through text-rose-500 font-normal text-[10px] ml-1">
                      47.28s
                    </span>
                  </div>
                </div>
                <div className="p-2.5 rounded-lg bg-card border border-border">
                  <span className="text-muted-foreground text-[10px] block">
                    Speech Synthesis (Gen)
                  </span>
                  <div className="font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                    0.82s (TTFT 0.54s){" "}
                    <span className="line-through text-rose-500 font-normal text-[10px] ml-1">
                      10.92s
                    </span>
                  </div>
                </div>
                <div className="p-2.5 rounded-lg bg-card border border-border">
                  <span className="text-muted-foreground text-[10px] block">
                    NLI Stance Grader
                  </span>
                  <div className="font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                    0.39s (ONNX-CPU){" "}
                    <span className="line-through text-rose-500 font-normal text-[10px] ml-1">
                      17.62s
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* =========================================================================
              SLIDE 3: THE 6 ARCHITECTURAL PILLARS OF OPTIMIZATION
             ========================================================================= */}
          {currentSlide === 2 && (
            <div className="flex flex-col h-full justify-between gap-4 animate-in fade-in zoom-in-95 duration-200">
              <div className="border-b border-border/60 pb-2.5 shrink-0">
                <Badge
                  variant="outline"
                  className="border-teal-500/30 text-teal-700 dark:text-teal-300 font-mono text-xs px-2.5 py-0.5"
                >
                  SLIDE 3 • ARCHITECTURAL INTERVENTIONS
                </Badge>
                <h2 className="text-2xl font-black tracking-tight text-foreground mt-1">
                  How We Slashed 81.3 Seconds: The 6 Core Engineering Solutions
                </h2>
                <p className="text-xs text-muted-foreground">
                  Systemic refactoring across model routing, background
                  ingestion queues, prompt budgeting, search depth, and local
                  runtime compilation.
                </p>
              </div>

              {/* 6 Grid Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 flex-1 items-stretch">
                {/* 1. Ingestion Queue */}
                <Card className="p-4 bg-card border-border shadow-xs flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 text-teal-600 dark:text-teal-400 font-bold text-xs uppercase tracking-wider mb-2">
                      <Server className="w-4 h-4" />
                      1. Queue-Based Ingestion vs Unified Tool Trap
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Replaced synchronous Playwright (<code>crawl4ai</code>)
                      and Neo4j Cypher writes inside the LLM turn loop with an
                      asynchronous daemon <strong>processing queue</strong>.
                    </p>
                  </div>
                  <div className="mt-3 p-2 rounded bg-teal-500/10 border border-teal-500/20 text-[11px] font-mono text-teal-700 dark:text-teal-300">
                    Impact: Tool blocking dropped from 47.28s to 0.00s in
                    critical path.
                  </div>
                </Card>

                {/* 2. Tavily Basic */}
                <Card className="p-4 bg-card border-border shadow-xs flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 text-teal-600 dark:text-teal-400 font-bold text-xs uppercase tracking-wider mb-2">
                      <Search className="w-4 h-4" />
                      2. Tavily Search Depth: &quot;Advanced&quot; →
                      &quot;Basic&quot;
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Switched search mode from deep web crawling to lightweight
                      snippet extraction. Returns targeted passages in under
                      600ms rather than pulling entire raw DOM trees.
                    </p>
                  </div>
                  <div className="mt-3 p-2 rounded bg-teal-500/10 border border-teal-500/20 text-[11px] font-mono text-teal-700 dark:text-teal-300">
                    Impact: Fast evidence grounding with zero timeout penalties.
                  </div>
                </Card>

                {/* 3. OpenRouter Latency Preference */}
                <Card className="p-4 bg-card border-border shadow-xs flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 text-teal-600 dark:text-teal-400 font-bold text-xs uppercase tracking-wider mb-2">
                      <Radio className="w-4 h-4" />
                      3. OpenRouter Provider Routing Rules
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Explicitly configured provider ordering to{" "}
                      <code>order: [&quot;latency&quot;]</code>. Bypasses
                      overloaded cloud endpoints that previously caused up to
                      106s cold-start freezes.
                    </p>
                  </div>
                  <div className="mt-3 p-2 rounded bg-teal-500/10 border border-teal-500/20 text-[11px] font-mono text-teal-700 dark:text-teal-300">
                    Impact: Eliminates upstream queue stalls; TTFT stabilized at
                    544ms.
                  </div>
                </Card>

                {/* 4. Reasoning Token Governance */}
                <Card className="p-4 bg-card border-border shadow-xs flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 text-teal-600 dark:text-teal-400 font-bold text-xs uppercase tracking-wider mb-2">
                      <Cpu className="w-4 h-4" />
                      4. Reasoning Token Reduction &amp; Bounding
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Tamed DeepSeek unconstrained CoT by clamping{" "}
                      <code>max_tokens: 3000</code> and passing{" "}
                      <code>
                        reasoning: &#123; effort: &quot;low&quot; &#125;
                      </code>
                      . Restricts thought generation to under 25 tokens.
                    </p>
                  </div>
                  <div className="mt-3 p-2 rounded bg-teal-500/10 border border-teal-500/20 text-[11px] font-mono text-teal-700 dark:text-teal-300">
                    Impact: Prevents rambling internal monologue; saved 25+
                    seconds.
                  </div>
                </Card>

                {/* 5. Token-by-Token SSE Streaming */}
                <Card className="p-4 bg-card border-border shadow-xs flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 text-teal-600 dark:text-teal-400 font-bold text-xs uppercase tracking-wider mb-2">
                      <Zap className="w-4 h-4" />
                      5. Real-Time SSE Token-by-Token Streaming
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Replaced blocking REST polling with Server-Sent Events
                      (SSE). Users witness speech synthesis immediately as
                      tokens emerge instead of a 5+ second freezing pause.
                    </p>
                  </div>
                  <div className="mt-3 p-2 rounded bg-teal-500/10 border border-teal-500/20 text-[11px] font-mono text-teal-700 dark:text-teal-300">
                    Impact: Perceived latency drops to ~500ms (instant
                    interactivity).
                  </div>
                </Card>

                {/* 6. URL Grouping & ONNX Grader */}
                <Card className="p-4 bg-card border-border shadow-xs flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 text-teal-600 dark:text-teal-400 font-bold text-xs uppercase tracking-wider mb-2">
                      <Filter className="w-4 h-4" />
                      6. URL Grouping &amp; Local ONNX Grader
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Grouped and deduplicated discovered domain citations to
                      eliminate redundant search calls. Replaced the 17.6s
                      remote stance LLM with a local quantized{" "}
                      <code>cross-encoder</code>.
                    </p>
                  </div>
                  <div className="mt-3 p-2 rounded bg-teal-500/10 border border-teal-500/20 text-[11px] font-mono text-teal-700 dark:text-teal-300">
                    Impact: Stance evaluation finished locally in 390ms (97.8%
                    speedup).
                  </div>
                </Card>
              </div>
            </div>
          )}

          {/* =========================================================================
              SLIDE 4: EMBEDDED INTERACTIVE NLI CPU BENCHMARK
             ========================================================================= */}
          {currentSlide === 3 && (
            <div className="flex flex-col h-full justify-between gap-3 animate-in fade-in zoom-in-95 duration-200">
              <div className="flex items-center justify-between border-b border-border/60 pb-2.5 shrink-0">
                <div>
                  <Badge
                    variant="outline"
                    className="border-teal-500/30 text-teal-700 dark:text-teal-300 font-mono text-xs px-2.5 py-0.5"
                  >
                    SLIDE 4 • LOCAL INFERENCE BENCHMARK
                  </Badge>
                  <h2 className="text-2xl font-black tracking-tight text-foreground mt-1 flex items-center gap-2">
                    <Cpu className="w-6 h-6 text-teal-600 dark:text-teal-400" />
                    Local NLI Stance Grader: ONNX vs. Remote LLM
                  </h2>
                </div>

                <div className="flex items-center gap-3">
                  <Badge className="bg-teal-600 text-white font-mono text-xs px-3 py-1">
                    0.39s (ONNX-CPU) vs 17.62s (Remote LLM)
                  </Badge>
                  <a
                    href="/cpu_benchmark_interactive.html"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs text-teal-700 dark:text-teal-300 hover:underline font-mono"
                  >
                    <span>Open Standalone Tab</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>

              {/* Interactive Iframe Embedding cpu_benchmark_interactive.html */}
              <div className="w-full flex-1 min-h-[500px] rounded-xl border border-border overflow-hidden bg-card shadow-sm">
                <iframe
                  src="/cpu_benchmark_interactive.html"
                  title="CPU Benchmark Interactive Report"
                  className="w-full h-full border-none"
                />
              </div>

              <div className="flex items-center justify-between text-xs font-mono text-muted-foreground p-2 rounded-lg bg-muted/40 border border-border/60 shrink-0">
                <span>
                  Engine:{" "}
                  <code>cross-encoder/nli-deberta-v3-small (onnx-cpu)</code>
                </span>
                <span className="text-emerald-600 dark:text-emerald-400 font-bold">
                  Zero cloud network hops • 100% deterministic local inference
                </span>
              </div>
            </div>
          )}

          {/* =========================================================================
              SLIDE 5: COMPLETE BENCHMARK ROADMAP & SUMMARY
             ========================================================================= */}
          {currentSlide === 4 && (
            <div className="flex flex-col h-full justify-between gap-4 animate-in fade-in zoom-in-95 duration-200">
              <div className="border-b border-border/60 pb-2.5 shrink-0">
                <Badge
                  variant="outline"
                  className="border-teal-500/30 text-teal-700 dark:text-teal-300 font-mono text-xs px-2.5 py-0.5"
                >
                  SLIDE 5 • FULL BENCHMARK ROADMAP
                </Badge>
                <h2 className="text-2xl font-black tracking-tight text-foreground mt-1">
                  Empirical Evolution Matrix: Traces 1 Through 5
                </h2>
                <p className="text-xs text-muted-foreground">
                  Summary audit of single-step debate execution across
                  consecutive empirical traces.
                </p>
              </div>

              {/* Master Benchmark Table */}
              <Card className="p-0 bg-card border-border overflow-hidden shadow-md flex-1 flex flex-col justify-center">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/60 border-b border-border text-muted-foreground text-xs uppercase tracking-wider">
                      <tr>
                        <th className="p-4 font-bold">Milestone / Trace</th>
                        <th className="p-4 font-bold">Orchestrate</th>
                        <th className="p-4 font-bold">Tool Decision</th>
                        <th className="p-4 font-bold">Tool Runtime</th>
                        <th className="p-4 font-bold">Speech Gen</th>
                        <th className="p-4 font-bold">Stance Grader</th>
                        <th className="p-4 font-bold">Total Step Latency</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60 font-mono text-xs">
                      <tr>
                        <td className="p-4 font-sans font-bold">
                          Trace 1: Sequential ReAct (Baseline)
                        </td>
                        <td className="p-4">4.04s</td>
                        <td className="p-4">10.62s</td>
                        <td className="p-4">7.76s (3 calls)</td>
                        <td className="p-4">15.05s</td>
                        <td className="p-4">7.89s</td>
                        <td className="p-4 font-bold text-foreground">
                          63.62s
                        </td>
                      </tr>
                      <tr className="bg-rose-500/5">
                        <td className="p-4 font-sans font-bold text-rose-600 dark:text-rose-400">
                          Trace 2: Unified Tool Trap (da99009b)
                        </td>
                        <td className="p-4">1.85s</td>
                        <td className="p-4">4.84s</td>
                        <td className="p-4 text-rose-600 font-bold">
                          47.28s (Blocked)
                        </td>
                        <td className="p-4">10.92s</td>
                        <td className="p-4 text-rose-600 font-bold">17.57s</td>
                        <td className="p-4 font-black text-rose-600 dark:text-rose-400 text-sm">
                          82.58s
                        </td>
                      </tr>
                      <tr>
                        <td className="p-4 font-sans font-bold">
                          Trace 3: Decoupled Ingestion
                        </td>
                        <td className="p-4">1.83s</td>
                        <td className="p-4">13.21s</td>
                        <td className="p-4 text-emerald-600 font-bold">
                          8.71s
                        </td>
                        <td className="p-4">15.60s</td>
                        <td className="p-4">9.00s</td>
                        <td className="p-4 font-bold text-foreground">
                          48.46s
                        </td>
                      </tr>
                      <tr>
                        <td className="p-4 font-sans font-bold">
                          Trace 4: 2-Query Context Budget
                        </td>
                        <td className="p-4">6.81s</td>
                        <td className="p-4">4.18s</td>
                        <td className="p-4 text-emerald-600">5.30s</td>
                        <td className="p-4 text-rose-500 font-bold">
                          39.38s (Unbounded CoT)
                        </td>
                        <td className="p-4 text-emerald-600">2.59s</td>
                        <td className="p-4 font-bold text-foreground">
                          58.37s
                        </td>
                      </tr>
                      <tr className="bg-teal-500/10">
                        <td className="p-4 font-sans font-bold text-teal-700 dark:text-teal-300">
                          Trace 5: Streaming + gpt-oss-120b + ONNX (dd51916e)
                        </td>
                        <td className="p-4 text-emerald-600 font-bold">
                          0.001s
                        </td>
                        <td className="p-4 text-emerald-600 font-bold">
                          0.00s
                        </td>
                        <td className="p-4 text-emerald-600 font-bold">
                          0.00s (Queue)
                        </td>
                        <td className="p-4 text-emerald-600 font-bold">
                          0.82s (TTFT 0.54s)
                        </td>
                        <td className="p-4 text-emerald-600 font-bold">
                          0.39s (ONNX)
                        </td>
                        <td className="p-4 font-black text-emerald-600 dark:text-emerald-400 text-sm">
                          1.29s (63.7× Faster)
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </Card>

              {/* Bottom CTA */}
              <div className="flex items-center justify-between p-4 rounded-xl bg-teal-50/50 dark:bg-teal-950/20 border border-teal-500/30 shrink-0">
                <div>
                  <span className="font-bold text-foreground text-sm block">
                    Real-Time Deliberation Achieved
                  </span>
                  <p className="text-xs text-muted-foreground">
                    Continuous opinion dynamics and persuasion tracking can now
                    stream live without freezing users.
                  </p>
                </div>
                <Link href="/">
                  <Button className="h-9 px-4 bg-teal-600 hover:bg-teal-700 text-white font-bold cursor-pointer gap-1.5 text-xs">
                    <span>Launch Live Arena</span>
                    <ArrowRight className="w-4 h-4" />
                  </Button>
                </Link>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Bottom Control Bar */}
      <footer className="h-14 border-t border-border/70 px-6 flex items-center justify-between bg-card/70 backdrop-blur-md shrink-0">
        <span className="text-xs text-muted-foreground font-mono">
          Navigate slides with keyboard:{" "}
          <kbd className="px-1.5 py-0.5 rounded bg-muted border border-border text-[11px]">
            ←
          </kbd>{" "}
          and{" "}
          <kbd className="px-1.5 py-0.5 rounded bg-muted border border-border text-[11px]">
            →
          </kbd>{" "}
          or{" "}
          <kbd className="px-2 py-0.5 rounded bg-muted border border-border text-[11px]">
            Space
          </kbd>
        </span>

        <div className="flex items-center gap-3">
          <Button
            size="sm"
            variant="outline"
            disabled={currentSlide === 0}
            onClick={() => setCurrentSlide((s) => Math.max(s - 1, 0))}
            className="h-9 px-4 text-xs cursor-pointer border-border font-medium"
          >
            Previous
          </Button>

          {currentSlide < totalSlides - 1 ? (
            <Button
              size="sm"
              onClick={() => setCurrentSlide((s) => s + 1)}
              className="h-9 px-4 text-xs bg-teal-600 hover:bg-teal-700 text-white font-medium cursor-pointer"
            >
              Next Slide
              <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          ) : (
            <Link href="/">
              <Button
                size="sm"
                className="h-9 px-4 text-xs bg-teal-600 hover:bg-teal-700 text-white font-medium cursor-pointer"
              >
                Return to Arena
                <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </Link>
          )}
        </div>
      </footer>
    </div>
  );
}
