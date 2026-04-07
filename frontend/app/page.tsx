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
    }).catch(() => setError("加载数据失败"));
  }, []);

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">{error}</p>
        <p className="text-sm text-muted-foreground mt-2">请确保后端服务运行在 8000 端口</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">总览</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="浮动盈亏"
          value={overview ? `$${overview.unrealized_pnl.toFixed(2)}` : "$0.00"}
          icon={overview && overview.unrealized_pnl >= 0 ? TrendingUp : TrendingDown}
          trend={overview ? (overview.unrealized_pnl >= 0 ? "up" : "down") : "neutral"}
        />
        <StatCard
          title="已实现盈亏"
          value={overview ? `$${overview.realized_pnl.toFixed(2)}` : "$0.00"}
          icon={Target}
          trend={overview ? (overview.realized_pnl >= 0 ? "up" : "down") : "neutral"}
        />
        <StatCard
          title="活跃持仓"
          value={overview ? String(overview.active_positions) : "0"}
          icon={Briefcase}
        />
        <StatCard
          title="胜率"
          value={overview ? `${(overview.win_rate * 100).toFixed(1)}%` : "0.0%"}
          icon={BarChart3}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Zap className="h-5 w-5" /> 最新信号
            </CardTitle>
          </CardHeader>
          <CardContent>
            {signals.length === 0 ? (
              <p className="text-sm text-muted-foreground">暂无活跃信号</p>
            ) : (
              <div className="space-y-3">
                {signals.map((s) => (
                  <div key={s.id} className="flex items-center justify-between border-b pb-2 last:border-0">
                    <div>
                      <p className="text-sm font-medium truncate max-w-xs">{s.market_question}</p>
                      <div className="flex gap-2 mt-1">
                        <Badge variant="outline" className="text-xs">{s.type === "ARBITRAGE" ? "套利" : "异动"}</Badge>
                        <span className="text-xs text-muted-foreground">边际: {s.edge_pct}%</span>
                      </div>
                    </div>
                    <Badge className="text-xs">置信度 {s.confidence}%</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Briefcase className="h-5 w-5" /> 活跃持仓
            </CardTitle>
          </CardHeader>
          <CardContent>
            {positions.length === 0 ? (
              <p className="text-sm text-muted-foreground">暂无持仓</p>
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
