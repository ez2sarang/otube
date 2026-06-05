"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Briefcase, Mic } from "lucide-react";
import { useAdmin } from "@/lib/auth-client";

const publicTabs = [
  { href: "/history", label: "대시보드", icon: LayoutDashboard },
  { href: "/tasks", label: "AI 작업", icon: Briefcase },
];

const adminTabs = [
  { href: "/stt", label: "분석 제출", icon: Mic },
];

export function TabNav() {
  const pathname = usePathname();
  const { isAdmin } = useAdmin();

  if (pathname.startsWith("/share/")) return null;

  const tabs = isAdmin ? [...publicTabs, ...adminTabs] : publicTabs;

  return (
    <nav className="border-b bg-background">
      <div className="max-w-6xl mx-auto flex gap-1 px-6">
        {tabs.map((tab) => {
          const active = pathname === tab.href;
          const Icon = tab.icon;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                active
                  ? "text-primary border-primary"
                  : "text-muted-foreground border-transparent hover:text-foreground hover:border-muted-foreground/30"
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
