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
} from "lucide-react";
import { Persona, DebateHistoryItem } from "@/types/simulation";
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
  personas: Persona[];
  topic: string;
  isRunning?: boolean;
  onNew?: () => void;
  onSelectTopic?: (topic: string) => void;
  onDeleteCurrentTopic?: () => void;
  onError?: (message: string) => void;
}

export const SidebarSetup: React.FC<SidebarSetupProps> = ({
  personas,
  topic,
  isRunning = false,
  onNew,
  onSelectTopic,
  onDeleteCurrentTopic,
  onError,
}) => {
  const [history, setHistory] = useState<DebateHistoryItem[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTopicDismissed, setActiveTopicDismissed] = useState(false);

  // Live Database Health State
  const [health, setHealth] = useState<HealthCheckResponse>({
    status: "healthy",
    neo4j: false,
    postgres: false,
  });
  const [isCheckingHealth, setIsCheckingHealth] = useState(true);

  const isDark = useSyncExternalStore(
    subscribeTheme,
    getThemeSnapshot,
    getServerSnapshot,
  );

  // Poll database health and fetch debate history
  useEffect(() => {
    let isMounted = true;

    const checkSystemHealth = () => {
      SimulationAPI.checkHealth()
        .then((res) => {
          if (isMounted) {
            setHealth(res);
            setIsCheckingHealth(false);
          }
        })
        .catch((err) => {
          if (isMounted) {
            setHealth({
              status: "unhealthy",
              neo4j: false,
              postgres: false,
              message: extractErrorMessage(err),
            });
            setIsCheckingHealth(false);
          }
        });
    };

    checkSystemHealth();
    const interval = setInterval(checkSystemHealth, 30000);

    SimulationAPI.getInitialHistory()
      .then((data) => {
        if (isMounted) setHistory(data);
      })
      .catch((err) => {
        console.error("Failed to load debate history:", err);
        onError?.(extractErrorMessage(err));
      });

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [onError]);

  const toggleTheme = (targetDark: boolean) => {
    if (targetDark) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  };

  const handleDeleteItem = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      await SimulationAPI.deleteHistoryItem(id);
      setHistory((prev) => prev.filter((item) => item.id !== id));
      if (selectedId === id) setSelectedId("");
    } catch (err) {
      onError?.(`Failed to delete topic: ${extractErrorMessage(err)}`);
    }
  };

  const filteredHistory = useMemo(() => {
    if (!searchQuery.trim()) return history;
    return history.filter((item) =>
      item.title.toLowerCase().includes(searchQuery.toLowerCase()),
    );
  }, [history, searchQuery]);

  const categories: Array<DebateHistoryItem["category"]> = [
    "Today",
    "Yesterday",
    "6 days ago",
    "Month ago",
    "Long time ago",
  ];

  return (
    <aside className="flex flex-col h-full border-r border-border/70 bg-sidebar text-sidebar-foreground select-none relative overflow-hidden transition-colors duration-200">
      {/* 1. Header & Branding */}
      <div className="p-3.5 border-b border-border/60 flex items-center justify-between gap-2 bg-sidebar">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="relative flex items-center justify-center h-8 w-8 rounded-lg bg-teal-600 dark:bg-teal-500 text-white shadow-sm ring-1 ring-teal-500/20 shrink-0">
            <Share2 className="w-4 h-4 rotate-45" />
          </div>
          <div className="truncate">
            <h1 className="text-xs font-bold tracking-tight text-foreground truncate">
              Qubeterra
            </h1>
            <p className="text-[10px] text-muted-foreground font-medium truncate">
              Multi-Agent Deliberation
            </p>
          </div>
        </div>

        <Button
          size="sm"
          variant="outline"
          className="h-7 px-2 text-xs border-teal-600/30 text-teal-700 dark:text-teal-300 hover:bg-teal-50 dark:hover:bg-teal-950/50 cursor-pointer"
          onClick={() => {
            setActiveTopicDismissed(false);
            setSelectedId("");
            onNew?.();
          }}
        >
          <Plus className="w-3.5 h-3.5 mr-1" />
          New
        </Button>
      </div>

      {/* 2. Search Bar */}
      <div className="px-3 pt-2.5 pb-1.5">
        <div className="relative flex items-center">
          <Search className="w-3.5 h-3.5 absolute left-2.5 text-muted-foreground/70 pointer-events-none" />
          <input
            type="text"
            placeholder="Search past debates..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-7 pl-8 pr-7 text-[11px] bg-background border border-border/80 rounded-md placeholder:text-muted-foreground/60 text-foreground focus:outline-none focus:ring-1 focus:ring-teal-500 transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-2 text-muted-foreground hover:text-foreground p-0.5 cursor-pointer"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* 3. Active Topic Preview */}
      {!activeTopicDismissed && topic && (
        <div className="px-3 py-1.5">
          <Card className="p-2.5 bg-card/80 dark:bg-card/50 border-teal-500/25 shadow-xs transition-all hover:border-teal-500/40">
            <div className="flex items-center justify-between gap-1 mb-1.5">
              <span className="text-[9px] uppercase tracking-wider font-bold text-teal-700 dark:text-teal-400 flex items-center gap-1">
                <Sparkles className="w-2.5 h-2.5 text-teal-500" />
                Active Topic
              </span>

              <div className="flex items-center gap-1.5">
                <Badge
                  variant="secondary"
                  className="text-[9px] px-1.5 py-0 h-4 bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300 border-none"
                >
                  {personas.length} Nodes
                </Badge>
                <button
                  onClick={() => {
                    setActiveTopicDismissed(true);
                    onDeleteCurrentTopic?.();
                  }}
                  className="text-muted-foreground hover:text-destructive p-1 rounded transition-colors"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>

            <p className="text-[11px] font-medium text-foreground/90 line-clamp-2 leading-relaxed">
              {topic}
            </p>

            {isRunning ? (
              <div className="mt-2 flex items-center gap-1.5 text-[10px] text-teal-600 dark:text-teal-400 font-medium">
                <Radio className="w-3 h-3 text-teal-500 animate-pulse" />
                <span>Live debate underway...</span>
              </div>
            ) : (
              <div className="mt-1.5 text-[10px] text-muted-foreground flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-teal-500/60" />
                <span>Ready in Arena</span>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* 4. Categorized History */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-3.5 scrollbar-thin">
        {categories.map((cat) => {
          const items = filteredHistory.filter((item) => item.category === cat);
          if (items.length === 0) return null;

          return (
            <div key={cat} className="space-y-1">
              <div className="px-2 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                <Clock className="w-3 h-3 text-teal-600/70 dark:text-teal-400/70" />
                <span>{cat}</span>
                <span className="text-[9px] opacity-60">({items.length})</span>
              </div>

              <div className="space-y-0.5">
                {items.map((item) => {
                  const isSelected = selectedId === item.id;
                  return (
                    <div
                      key={item.id}
                      onClick={() => {
                        setSelectedId(item.id);
                        onSelectTopic?.(item.title);
                      }}
                      className={`group relative w-full text-left px-2.5 py-2 rounded-md text-xs flex items-center justify-between cursor-pointer transition-all ${
                        isSelected
                          ? "bg-teal-50/90 dark:bg-teal-950/40 text-teal-950 dark:text-teal-200 font-medium border border-teal-500/25 shadow-2xs"
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
                          {item.title}
                        </span>
                      </div>

                      <div className="flex items-center gap-1 shrink-0 ml-1">
                        <button
                          onClick={(e) => handleDeleteItem(e, item.id)}
                          className="opacity-0 group-hover:opacity-100 hover:text-destructive p-1 rounded transition-all text-muted-foreground"
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

      {/* 5. Live Database Connection Health Footer */}
      <div className="p-2.5 border-t border-border/70 bg-sidebar/95 backdrop-blur space-y-2">
        <div className="rounded-md bg-muted/40 p-2 border border-border/50 space-y-1.5">
          <div className="flex items-center justify-between text-[10px]">
            <span className="font-semibold text-foreground flex items-center gap-1">
              <Database className="w-3 h-3 text-teal-600 dark:text-teal-400" />
              Databases
            </span>
            <span className="text-[9px] text-muted-foreground font-mono">
              {isCheckingHealth ? "Checking..." : health.status.toUpperCase()}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-1 text-[10px]">
            {/* PostgreSQL Indicator */}
            <div className="flex items-center gap-1.5 p-1 rounded bg-background/60 border border-border/40">
              <span
                className={`w-2 h-2 rounded-full ${
                  health.postgres
                    ? "bg-emerald-500 animate-pulse"
                    : "bg-rose-500"
                }`}
              />
              <span className="text-muted-foreground font-mono text-[9px]">
                Postgres
              </span>
            </div>

            {/* Neo4j Indicator */}
            <div className="flex items-center gap-1.5 p-1 rounded bg-background/60 border border-border/40">
              <span
                className={`w-2 h-2 rounded-full ${
                  health.neo4j ? "bg-emerald-500 animate-pulse" : "bg-rose-500"
                }`}
              />
              <span className="text-muted-foreground font-mono text-[9px]">
                Neo4j
              </span>
            </div>
          </div>
        </div>

        {/* Theme Toggle */}
        <div className="flex items-center p-0.5 rounded-lg bg-muted/60 border border-border/60">
          <button
            onClick={() => toggleTheme(false)}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1 text-[11px] font-medium rounded-md transition-all ${
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
            className={`flex-1 flex items-center justify-center gap-1.5 py-1 text-[11px] font-medium rounded-md transition-all ${
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
  );
};
