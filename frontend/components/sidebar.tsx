"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  BarChart3,
  Zap,
  Briefcase,
  History,
  Settings,
  Bitcoin,
  Radio,
  FileText,
} from "lucide-react";
import { Separator } from "@/components/ui/separator";

const polyNavItems = [
  { href: "/", label: "总览", icon: LayoutDashboard },
  { href: "/markets", label: "市场", icon: BarChart3 },
  { href: "/signals", label: "信号", icon: Zap },
  { href: "/positions", label: "持仓", icon: Briefcase },
  { href: "/history", label: "历史", icon: History },
];

const bitgetNavItems = [
  { href: "/bitget", label: "交易面板", icon: Bitcoin },
  { href: "/bitget/trades", label: "交易记录", icon: FileText },
  { href: "/bitget/monitor", label: "行情监控", icon: Radio },
];

const settingsNav = [
  { href: "/settings", label: "设置", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  const renderNavItem = (item: { href: string; label: string; icon: React.ElementType }) => {
    const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
    return (
      <Link
        key={item.href}
        href={item.href}
        className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
          isActive
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:text-foreground hover:bg-muted"
        }`}
      >
        <item.icon className="h-4 w-4" />
        {item.label}
      </Link>
    );
  };

  return (
    <aside className="w-64 border-r bg-muted/30 min-h-screen p-4 flex flex-col">
      <div className="mb-6 px-2">
        <h1 className="text-xl font-bold tracking-tight">PolyHunter</h1>
        <p className="text-xs text-muted-foreground mt-1">量化交易系统</p>
      </div>

      <nav className="space-y-1 flex-1">
        <p className="px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
          Polymarket
        </p>
        {polyNavItems.map(renderNavItem)}

        <Separator className="my-4" />

        <p className="px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
          Bitget
        </p>
        {bitgetNavItems.map(renderNavItem)}

        <Separator className="my-4" />

        {settingsNav.map(renderNavItem)}
      </nav>

      <div className="mt-auto px-2 py-4 text-xs text-muted-foreground">
        v0.2.0 · Bitget + Polymarket
      </div>
    </aside>
  );
}
