"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, TrendingDown, Zap, Briefcase, BarChart3, Target } from "lucide-react";
import type { Overview, Signal, Position } from "@/lib/types";
import { getOverview, getSignals, getPositions } from "@/lib/api";

function StatCard({ title, value, icon: Icon, trend }: {
  title: string;
  value: string;
  icon: React.ElementType;
  trend?: "up" | "down" | "neutral";
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold ${
          trend === "up" ? "text-green-600" : trend === "down" ? "text-red-600" : ""
        }`}>
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

export default function OverviewPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    Promise.all([
      getOverview().catch(() => null),
      getSignals({ status: "NEW", limit: 5 }).catch(() => []),
      getPositions().catch(() => []),
    ]).then(([ov, sig, pos]) => {
      if (ov) setOverview(ov);
      setSignals(sig as Signal[]);
      setPositions(pos as Position[]);
    }).catch(() => setError("Failed to load dashboard data"));
  }, []);

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">{error}</p>
        <p className="text-sm text-muted-foreground mt-2">Make sure the backend is running on port 8000</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Overview</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Unrealized PnL"
          value={overview ? `$${overview.unrealized_pnl.toFixed(2)}` : "$0.00"}
          icon={overview && overview.unrealized_pnl >= 0 ? TrendingUp : TrendingDown}
          trend={overview ? (overview.unrealized_pnl >= 0 ? "up" : "down") : "neutral"}
        />
        <StatCard
          title="Realized PnL"
          value={overview ? `$${overview.realized_pnl.toFixed(2)}` : "$0.00"}
          icon={Target}
          trend={overview ? (overview.realized_pnl >= 0 ? "up" : "down") : "neutral"}
        />
        <StatCard
          title="Active Positions"
          value={overview ? String(overview.active_positions) : "0"}
          icon={Briefcase}
        />
        <StatCard
          title="Win Rate"
          value={overview ? `${(overview.win_rate * 100).toFixed(1)}%` : "0.0%"}
          icon={BarChart3}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Signals */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Zap className="h-5 w-5" /> Recent Signals
            </CardTitle>
          </CardHeader>
          <CardContent>
            {signals.length === 0 ? (
              <p className="text-sm text-muted-foreground">No active signals</p>
            ) : (
              <div className="space-y-3">
                {signals.map((s) => (
                  <div key={s.id} className="flex items-center justify-between border-b pb-2 last:border-0">
                    <div>
                      <p className="text-sm font-medium truncate max-w-xs">{s.market_question}</p>
                      <div className="flex gap-2 mt-1">
                        <Badge variant="outline" className="text-xs">{s.type}</Badge>
                        <span className="text-xs text-muted-foreground">Edge: {s.edge_pct}%</span>
                      </div>
                    </div>
                    <Badge className="text-xs">{s.confidence}%</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Active Positions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Briefcase className="h-5 w-5" /> Active Positions
            </CardTitle>
          </CardHeader>
          <CardContent>
            {positions.length === 0 ? (
              <p className="text-sm text-muted-foreground">No open positions</p>
            ) : (
              <div className="space-y-3">
                {positions.map((p) => (
                  <div key={p.id} className="flex items-center justify-between border-b pb-2 last:border-0">
                    <div>
                      <p className="text-sm font-medium truncate max-w-xs">{p.market_question}</p>
                      <span className="text-xs text-muted-foreground">
                        {p.side} @ ${p.avg_entry_price.toFixed(2)} x {p.size}
                      </span>
                    </div>
                    <span className={`text-sm font-medium ${
                      p.unrealized_pnl >= 0 ? "text-green-600" : "text-red-600"
                    }`}>
                      ${p.unrealized_pnl.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
