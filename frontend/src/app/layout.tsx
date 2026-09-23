import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { TooltipProvider } from "@/components/ui/tooltip";

const sansFont = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const monoFont = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Qubeterra — AI Regulation Deliberation Engine",
  description:
    "Autonomous multi-agent policy debate with real-time vector retrieval, topological consensus modeling, and opinion drift analytics.",
  keywords: [
    "AI Regulation",
    "Multi-Agent Debate",
    "Opinion Dynamics",
    "Autonomous Deliberation",
    "Graph Analytics",
  ],
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8fafb" },
    { media: "(prefers-color-scheme: dark)", color: "#0d1518" },
  ],
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${sansFont.variable} ${monoFont.variable}`}
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                const stored = localStorage.getItem('theme');
                const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                if (stored === 'dark' || (!stored && prefersDark)) {
                  document.documentElement.classList.add('dark');
                } else {
                  document.documentElement.classList.remove('dark');
                }
              } catch (_) {}
            `,
          }}
        />
      </head>
      <body
        suppressHydrationWarning
        className="font-sans bg-background text-foreground antialiased selection:bg-teal-500/25 selection:text-teal-900 dark:selection:text-teal-100 overflow-hidden"
      >
        <TooltipProvider delay={150}>{children}</TooltipProvider>
      </body>
    </html>
  );
}
