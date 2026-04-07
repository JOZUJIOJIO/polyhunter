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
} from "lucide-react";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/markets", label: "Markets", icon: BarChart3 },
  { href: "/signals", label: "Signals", icon: Zap },
  { href: "/positions", label: "Positions", icon: Briefcase },
  { href: "/history", label: "History", icon: History },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r bg-muted/30 min-h-screen p-4 flex flex-col">
      <div className="mb-8 px-2">
        <h1 className="text-xl font-bold tracking-tight">PolyHunter</h1>
        <p className="text-xs text-muted-foreground mt-1">Polymarket Trading</p>
      </div>
      <nav className="space-y-1 flex-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
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
        })}
      </nav>
      <div className="mt-auto px-2 py-4 text-xs text-muted-foreground">
        v0.1.0
      </div>
    </aside>
  );
}
