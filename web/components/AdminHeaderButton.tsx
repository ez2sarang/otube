"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { LogIn, LogOut } from "lucide-react";
import { useAdmin, invalidateAdminCache } from "@/lib/auth-client";

export function AdminHeaderButton() {
  const router = useRouter();
  const { isAdmin, loading } = useAdmin();

  if (loading) return null;

  async function handleLogout() {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
    });
    invalidateAdminCache();
    router.push("/");
    router.refresh();
  }

  if (isAdmin) {
    return (
      <Button
        variant="ghost"
        size="sm"
        onClick={handleLogout}
        className="gap-1.5 text-muted-foreground"
      >
        <LogOut className="w-4 h-4" />
        로그아웃
      </Button>
    );
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => router.push("/login")}
      className="gap-1.5 text-muted-foreground"
    >
      <LogIn className="w-4 h-4" />
      관리자 로그인
    </Button>
  );
}
