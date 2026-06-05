import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { TabNav } from "@/components/ui/TabNav";
import { BatchJobMonitor } from "@/components/BatchJobMonitor";
import { AdminHeaderButton } from "@/components/AdminHeaderButton";
import { AudioLines } from "lucide-react";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Offline Thinking",
  description: "YouTube STT 변환 & AI 분석 도구",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className={`${geistSans.variable} ${geistMono.variable}`} suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased" suppressHydrationWarning>
        <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="max-w-6xl mx-auto flex items-center gap-3 px-6 py-4">
            <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary text-primary-foreground">
              <AudioLines className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <h1 className="text-lg font-semibold tracking-tight">Offline Thinking</h1>
              <p className="text-xs text-muted-foreground">STT 변환  &middot;  AI 분석</p>
            </div>
            <AdminHeaderButton />
          </div>
        </header>
        <TabNav />
        <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
        <BatchJobMonitor />
      </body>
    </html>
  );
}
