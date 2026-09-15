"use client";

import React, {
  useState,
  useEffect,
  useMemo,
  useSyncExternalStore,
} from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  MessageSquare,
  Plus,
  Sun,
  Moon,
  Clock,
  ChevronRight,
  Trash2,
  Search,
  Share2,
  X,
  Sparkles,
  Database,
  Radio,
  AlertTriangle,
  ExternalLink,
} from "lucide-react";
import { DebateHistoryItem } from "@/types/simulation";
import {
  SimulationAPI,
  HealthCheckResponse,
  extractErrorMessage,
} from "@/lib/api";

const subscribeTheme = (callback: () => void) => {
  const observer = new MutationObserver(callback);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
  window.addEventListener("storage", callback);
  return () => {
    observer.disconnect();
    window.removeEventListener("storage", callback);
  };
};
const getThemeSnapshot = () =>
  typeof document !== "undefined" &&
  document.documentElement.classList.contains("dark");
const getServerSnapshot = () => false;

export interface SidebarSetupProps {
  currentSimulationId?: string;
  activeTopic: string;
  agentsCount: number;
  isRunning?: boolean;
  onNewDebate: () => void;
  onSelectSimulation: (id: string) => void;
  onGoToActiveSession?: () => void;
  refreshTrigger?: number;
  onError?: (message: string) => void;
}

export const SidebarSetup: React.FC<SidebarSetupProps> = ({
  currentSimulationId,
  activeTopic,
  agentsCount,
  isRunning = false,
  onNewDebate,
  onSelectSimulation,
  onGoToActiveSession,
  refreshTrigger = 0,
  onError,
}) => {
  const [history, setHistory] = useState<DebateHistoryItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<DebateHistoryItem | null>(
    null,
  );
  const [isDeleting, setIsDeleting] = useState(false);

  const [health, setHealth] = useState<HealthCheckResponse>({
    status: "healthy",
    neo4j: false,
    postgres: false,
  });

  const isDark = useSyncExternalStore(
    subscribeTheme,
    getThemeSnapshot,
    getServerSnapshot,
  );

  const fetchHistory = () => {
    SimulationAPI.getInitialHistory()
      .then(setHistory)
      .catch((err) => onError?.(extractErrorMessage(err)));
  };

  useEffect(() => {
    fetchHistory();
    const check = () =>
      SimulationAPI.checkHealth()
        .then(setHealth)
        .catch(() => {});
    check();
    const timer = setInterval(check, 30000);
    return () => clearInterval(timer);
  }, [refreshTrigger]);

  const toggleTheme = (dark: boolean) => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await SimulationAPI.deleteHistoryItem(deleteTarget.id);
      setHistory((prev) => prev.filter((h) => h.id !== deleteTarget.id));
      if (currentSimulationId === deleteTarget.id) {
        onNewDebate();
      }
      setDeleteTarget(null);
    } catch (err) {
      onError?.(`Failed to delete: ${extractErrorMessage(err)}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const filteredHistory = useMemo(() => {
    if (!searchQuery.trim()) return history;
    return history.filter((h) =>
      (h.title || h.topic || "")
        .toLowerCase()
        .includes(searchQuery.toLowerCase()),
    );
  }, [history, searchQuery]);

  return (
    <>
      <aside className="flex flex-col h-full border-r border-border/70 bg-sidebar text-sidebar-foreground select-none relative overflow-hidden transition-colors duration-200">
        {/* Header & Branding */}
        <div className="p-3.5 border-b border-border/60 flex items-center justify-between gap-2 bg-sidebar">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-teal-600 dark:bg-teal-500 text-white shadow-sm shrink-0">
              <Share2 className="w-4 h-4 rotate-45" />
            </div>
            <div className="truncate">
              <h1 className="text-xs font-bold tracking-tight text-foreground truncate">
                Qubeterra
              </h1>
              <p className="text-[10px] text-muted-foreground font-medium truncate">
                Deliberation Engine
              </p>
            </div>
          </div>

          <Button
            size="sm"
            variant="outline"
            style={{ cursor: "pointer" }}
            className="h-7 px-2.5 text-xs border-teal-600/30 text-teal-700 dark:text-teal-300 hover:bg-teal-50 dark:hover:bg-teal-950/50 cursor-pointer"
            onClick={onNewDebate}
          >
            <Plus className="w-3.5 h-3.5 mr-1" />
            New
          </Button>
        </div>

        {/* Search */}
        <div className="px-3 pt-2.5 pb-1.5">
          <div className="relative flex items-center">
            <Search className="w-3.5 h-3.5 absolute left-2.5 text-muted-foreground/70 pointer-events-none" />
            <input
              type="text"
              placeholder="Search past debates..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full h-7 pl-8 pr-7 text-[11px] bg-background border border-border/80 rounded-md placeholder:text-muted-foreground/60 text-foreground focus:outline-none focus:ring-1 focus:ring-teal-500"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-2 text-muted-foreground p-0.5 cursor-pointer"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Clickable Active Session Card (Switches View back to Arena) */}
        {activeTopic && (
          <div className="px-3 py-1.5">
            <Card
              onClick={onGoToActiveSession}
              style={{ cursor: "pointer" }}
              className="p-2.5 bg-card/90 dark:bg-card/70 border-teal-500/40 shadow-xs cursor-pointer hover:border-teal-500 transition-all group"
            >
              <div className="flex items-center justify-between gap-1 mb-1">
                <span className="text-[9px] uppercase tracking-wider font-bold text-teal-700 dark:text-teal-400 flex items-center gap-1">
                  <Sparkles className="w-2.5 h-2.5 text-teal-500" />
                  Active Session
                </span>
                <div className="flex items-center gap-1">
                  <Badge
                    variant="secondary"
                    className="text-[9px] px-1.5 py-0 h-4 bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300 border-none"
                  >
                    {agentsCount} Nodes
                  </Badge>
                  <ExternalLink className="w-2.5 h-2.5 text-muted-foreground group-hover:text-teal-600 transition-colors" />
                </div>
              </div>
              <p className="text-[11px] font-medium text-foreground line-clamp-2 leading-relaxed">
                {activeTopic}
              </p>
              {isRunning ? (
                <div className="mt-1.5 flex items-center gap-1.5 text-[10px] text-teal-600 dark:text-teal-400 font-medium">
                  <Radio className="w-3 h-3 text-teal-500 animate-pulse" />
                  <span>Streaming turn in Arena...</span>
                </div>
              ) : (
                <div className="mt-1 flex items-center justify-between text-[9px] text-muted-foreground">
                  <span className="text-teal-600 dark:text-teal-400 font-semibold group-hover:underline">
                    Click to view Arena
                  </span>
                  <span className="w-1.5 h-1.5 rounded-full bg-teal-500" />
                </div>
              )}
            </Card>
          </div>
        )}

        {/* Past Simulations List */}
        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1 scrollbar-thin">
          <div className="px-2 py-1 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
            <Clock className="w-3 h-3 text-teal-600/70 dark:text-teal-400/70" />
            <span>Debate History</span>
            <span className="text-[9px] opacity-60">
              ({filteredHistory.length})
            </span>
          </div>

          {filteredHistory.map((item) => {
            const isSelected = currentSimulationId === item.id;
            return (
              <div
                key={item.id}
                onClick={() => onSelectSimulation(item.id)}
                style={{ cursor: "pointer" }}
                className={`group relative w-full text-left px-2.5 py-2 rounded-md text-xs flex items-center justify-between cursor-pointer transition-all ${
                  isSelected
                    ? "bg-teal-50/90 dark:bg-teal-950/50 text-teal-950 dark:text-teal-200 font-medium border border-teal-500/30 shadow-2xs"
                    : "text-foreground/80 hover:bg-accent/60 hover:text-foreground border border-transparent"
                }`}
              >
                <div className="flex items-center gap-2 min-w-0 pr-1">
                  <MessageSquare
                    className={`w-3.5 h-3.5 shrink-0 ${
                      isSelected
                        ? "text-teal-600 dark:text-teal-400"
                        : "text-muted-foreground/70 group-hover:text-teal-600"
                    }`}
                  />
                  <span className="truncate text-[11px] leading-snug">
                    {item.title || item.topic}
                  </span>
                </div>

                <div className="flex items-center gap-1 shrink-0 ml-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteTarget(item);
                    }}
                    style={{ cursor: "pointer" }}
                    className="opacity-0 group-hover:opacity-100 hover:text-destructive p-1 rounded transition-all text-muted-foreground cursor-pointer"
                    title="Delete debate"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                  <ChevronRight
                    className={`w-3 h-3 ${isSelected ? "text-teal-600 opacity-100" : "opacity-0 group-hover:opacity-40"}`}
                  />
                </div>
              </div>
            );
          })}

          {filteredHistory.length === 0 && (
            <div className="py-8 text-center px-4 text-muted-foreground space-y-1">
              <MessageSquare className="w-6 h-6 mx-auto opacity-30 text-teal-500" />
              <p className="text-xs font-medium">No past discussions</p>
            </div>
          )}
        </div>

        {/* Database Health & Theme Toggle Footer */}
        <div className="p-2.5 border-t border-border/70 bg-sidebar/95 backdrop-blur space-y-2">
          <div className="rounded-md bg-muted/40 p-2 border border-border/50 space-y-1.5">
            <div className="flex items-center justify-between text-[10px]">
              <span className="font-semibold text-foreground flex items-center gap-1">
                <Database className="w-3 h-3 text-teal-600 dark:text-teal-400" />
                Databases
              </span>
              <span className="text-[9px] text-muted-foreground font-mono">
                {health.status.toUpperCase()}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-1 text-[10px]">
              <div className="flex items-center gap-1.5 p-1 rounded bg-background/60 border border-border/40">
                <span
                  className={`w-2 h-2 rounded-full ${health.postgres ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`}
                />
                <span className="text-muted-foreground font-mono text-[9px]">
                  Postgres
                </span>
              </div>
              <div className="flex items-center gap-1.5 p-1 rounded bg-background/60 border border-border/40">
                <span
                  className={`w-2 h-2 rounded-full ${health.neo4j ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`}
                />
                <span className="text-muted-foreground font-mono text-[9px]">
                  Neo4j
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center p-0.5 rounded-lg bg-muted/60 border border-border/60">
            <button
              onClick={() => toggleTheme(false)}
              style={{ cursor: "pointer" }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-1 text-[11px] font-medium rounded-md transition-all cursor-pointer ${
                !isDark
                  ? "bg-background text-teal-700 shadow-2xs font-semibold"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Sun className="w-3 h-3 text-amber-500" />
              Light
            </button>
            <button
              onClick={() => toggleTheme(true)}
              style={{ cursor: "pointer" }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-1 text-[11px] font-medium rounded-md transition-all cursor-pointer ${
                isDark
                  ? "bg-card text-teal-300 shadow-2xs font-semibold"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Moon className="w-3 h-3 text-teal-400" />
              Dark
            </button>
          </div>
        </div>
      </aside>

      {/* Confirmation Modal for Permanent Deletion */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="max-w-md w-full rounded-xl bg-card border border-border p-5 shadow-lg space-y-4">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-full bg-rose-500/10 text-rose-600 dark:text-rose-400 shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-foreground">
                  Delete Deliberation Session?
                </h3>
                <p className="text-xs text-muted-foreground mt-1">
                  This will permanently delete{" "}
                  <span className="font-semibold text-foreground">
                    &quot;{deleteTarget.title || deleteTarget.topic}&quot;
                  </span>{" "}
                  and all associated agent opinion snapshots, graph vectors, and
                  discussion turns.
                </p>
                <p className="text-[11px] font-semibold text-rose-600 dark:text-rose-400 mt-2">
                  This action cannot be undone.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-border/50">
              <Button
                variant="outline"
                size="sm"
                disabled={isDeleting}
                onClick={() => setDeleteTarget(null)}
                style={{ cursor: "pointer" }}
                className="text-xs h-8 cursor-pointer"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                size="sm"
                disabled={isDeleting}
                onClick={handleConfirmDelete}
                style={{ cursor: "pointer" }}
                className="text-xs h-8 bg-rose-600 hover:bg-rose-700 text-white cursor-pointer"
              >
                {isDeleting ? "Deleting..." : "Permanently Delete"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
