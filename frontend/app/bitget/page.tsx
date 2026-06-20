"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  Shield,
} from "lucide-react";
import type { BitgetBalance, BitgetPosition, BitgetTicker, BitgetTrade, MonitorStatus } from "@/lib/types";
import { getBitgetBalance, getBitgetPositions, getBitgetTicker, getBitgetTrades, getMonitorStatus } from "@/lib/api";

function StatCard({
  title,
  value,
  icon: Icon,
  trend,
  subtitle,
}: {
  title: string;
  value: string;
  icon: React.ElementType;
  trend?: "up" | "down" | "neutral";
  subtitle?: string;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div
          className={`text-2xl font-bold font-mono ${
            trend === "up" ? "text-green-600" : trend === "down" ? "text-red-600" : ""
          }`}
        >
          {value}
        </div>
        {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
      </CardContent>
    </Card>
  );
}

export default function BitgetDashboard() {
  const [balance, setBalance] = useState<BitgetBalance>({});
  const [positions, setPositions] = useState<BitgetPosition[]>([]);
  const [tickers, setTickers] = useState<Record<string, BitgetTicker>>({});
  const [trades, setTrades] = useState<BitgetTrade[]>([]);
  const [monitor, setMonitor] = useState<MonitorStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = async () => {
    try {
      const [bal, pos, trds, mon] = await Promise.all([
        getBitgetBalance().catch(() => ({})),
        getBitgetPositions().catch(() => []),
        getBitgetTrades(10).catch(() => []),
        getMonitorStatus().catch(() => null),
      ]);
      setBalance(bal);
      setPositions(pos);
      setTrades(trds);
      setMonitor(mon);

      // Fetch tickers for symbols with positions
      const symbols = [...new Set(pos.map((p: BitgetPosition) => p.symbol))];
      if (symbols.length === 0) symbols.push("BTCUSDT", "ETHUSDT");
      const tickerResults: Record<string, BitgetTicker> = {};
      for (const sym of symbols) {
        try {
          tickerResults[sym] = await getBitgetTicker(sym);
        } catch {}
      }
      setTickers(tickerResults);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    const timer = setInterval(fetchAll, 10000); // Refresh every 10s
    return () => clearInterval(timer);
  }, []);

  const totalUnrealizedPnl = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0);
  const usdtBalance = balance["USDT"] || 0;
  const totalEquity = usdtBalance + positions.reduce((sum, p) => sum + p.size * p.current_price, 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-muted-foreground">Loading Bitget data...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Bitget 交易面板</h2>
          <p className="text-sm text-muted-foreground mt-1">USDT-M 合约 · 10x 杠杆</p>
        </div>
        <div className="flex items-center gap-2">
          <div
            className={`h-2 w-2 rounded-full ${monitor?.running ? "bg-green-500 animate-pulse" : "bg-muted-foreground"}`}
          />
          <span className="text-sm text-muted-foreground">
            {monitor?.running ? "监控运行中" : "监控未启动"}
          </span>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="可用余额"
          value={`$${usdtBalance.toFixed(2)}`}
          icon={Wallet}
          subtitle="USDT"
        />
        <StatCard
          title="未实现盈亏"
          value={`$${totalUnrealizedPnl.toFixed(4)}`}
          icon={totalUnrealizedPnl >= 0 ? TrendingUp : TrendingDown}
          trend={totalUnrealizedPnl >= 0 ? "up" : "down"}
          subtitle={positions.length > 0 ? `${positions.length} 个持仓` : "无持仓"}
        />
        <StatCard
          title="BTC"
          value={tickers["BTCUSDT"] ? `$${tickers["BTCUSDT"].last_price.toLocaleString()}` : "—"}
          icon={BarChart3}
          subtitle={
            tickers["BTCUSDT"]
              ? `24h: $${tickers["BTCUSDT"].low_24h.toLocaleString()} - $${tickers["BTCUSDT"].high_24h.toLocaleString()}`
              : ""
          }
        />
        <StatCard
          title="ETH"
          value={tickers["ETHUSDT"] ? `$${tickers["ETHUSDT"].last_price.toLocaleString()}` : "—"}
          icon={BarChart3}
          subtitle={
            tickers["ETHUSDT"]
              ? `24h: $${tickers["ETHUSDT"].low_24h.toLocaleString()} - $${tickers["ETHUSDT"].high_24h.toLocaleString()}`
              : ""
          }
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Positions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Activity className="h-5 w-5" /> 当前持仓
            </CardTitle>
          </CardHeader>
          <CardContent>
            {positions.length === 0 ? (
              <p className="text-sm text-muted-foreground">暂无持仓</p>
            ) : (
              <div className="space-y-4">
                {positions.map((p, i) => {
                  const pnlPct =
                    p.avg_entry_price > 0
                      ? ((p.current_price - p.avg_entry_price) / p.avg_entry_price) * 100
                      : 0;
                  const isProfit = p.unrealized_pnl >= 0;
                  const slPrice = p.avg_entry_price * 0.95;
                  const tpPrice = p.avg_entry_price * 1.1;

                  return (
                    <div key={i} className="border rounded-lg p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-bold">{p.symbol}</span>
                          <Badge variant={p.side === "long" ? "default" : "destructive"} className="text-xs">
                            {p.side === "long" ? "LONG" : "SHORT"} {p.leverage}x
                          </Badge>
                        </div>
                        <span
                          className={`text-lg font-bold font-mono ${isProfit ? "text-green-600" : "text-red-600"}`}
                        >
                          {isProfit ? "+" : ""}${p.unrealized_pnl.toFixed(4)}
                        </span>
                      </div>

                      <div className="grid grid-cols-3 gap-2 text-sm">
                        <div>
                          <p className="text-muted-foreground">入场价</p>
                          <p className="font-mono">${p.avg_entry_price.toLocaleString()}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">现价</p>
                          <p className="font-mono">${p.current_price.toLocaleString()}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">涨跌</p>
                          <p className={`font-mono ${isProfit ? "text-green-600" : "text-red-600"}`}>
                            {pnlPct >= 0 ? "+" : ""}
                            {pnlPct.toFixed(3)}%
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 text-xs">
                        <div className="flex items-center gap-1">
                          <Shield className="h-3 w-3 text-red-500" />
                          <span className="text-muted-foreground">止损</span>
                          <span className="font-mono">${slPrice.toFixed(2)}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <ArrowUpRight className="h-3 w-3 text-green-500" />
                          <span className="text-muted-foreground">止盈</span>
                          <span className="font-mono">${tpPrice.toFixed(2)}</span>
                        </div>
                        <div className="text-muted-foreground">
                          数量: <span className="font-mono">{p.size}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Trades */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <BarChart3 className="h-5 w-5" /> 最近交易
            </CardTitle>
          </CardHeader>
          <CardContent>
            {trades.length === 0 ? (
              <p className="text-sm text-muted-foreground">暂无交易记录</p>
            ) : (
              <div className="space-y-3">
                {trades.map((t) => (
                  <div key={t.id} className="flex items-center justify-between border-b pb-2 last:border-0">
                    <div>
                      <div className="flex items-center gap-2">
                        {t.side === "BUY" ? (
                          <ArrowUpRight className="h-4 w-4 text-green-600" />
                        ) : (
                          <ArrowDownRight className="h-4 w-4 text-red-600" />
                        )}
                        <span className="text-sm font-medium">{t.symbol}</span>
                        <Badge variant="outline" className="text-xs">
                          {t.strategy || t.order_type}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        {t.side} {t.size} @ ${t.price.toLocaleString()} · {new Date(t.created_at).toLocaleTimeString()}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-mono">${t.cost.toFixed(2)}</p>
                      {t.pnl !== null && (
                        <p className={`text-xs font-mono ${t.pnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(2)}
                        </p>
                      )}
                    </div>
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
