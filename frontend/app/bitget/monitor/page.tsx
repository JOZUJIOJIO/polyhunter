"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Radio, Bell, TrendingUp, TrendingDown } from "lucide-react";
import type { BitgetTicker, BitgetAlert, MonitorStatus } from "@/lib/types";
import { getBitgetTicker, getBitgetAlerts, getMonitorStatus } from "@/lib/api";

const SYMBOLS = ["BTCUSDT", "ETHUSDT"];

export default function MonitorPage() {
  const [tickers, setTickers] = useState<Record<string, BitgetTicker>>({});
  const [prevPrices, setPrevPrices] = useState<Record<string, number>>({});
  const [alerts, setAlerts] = useState<BitgetAlert[]>([]);
  const [monitor, setMonitor] = useState<MonitorStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [mon, alts] = await Promise.all([
        getMonitorStatus().catch(() => null),
        getBitgetAlerts(20).catch(() => []),
      ]);
      setMonitor(mon);
      setAlerts(alts);

      const newTickers: Record<string, BitgetTicker> = {};
      const newPrev: Record<string, number> = {};
      for (const sym of SYMBOLS) {
        try {
          const t = await getBitgetTicker(sym);
          newTickers[sym] = t;
          newPrev[sym] = tickers[sym]?.last_price || t.last_price;
        } catch {}
      }
      setPrevPrices(newPrev);
      setTickers(newTickers);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, 5000); // Refresh every 5s
    return () => clearInterval(timer);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-muted-foreground">Loading market data...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Radio className="h-6 w-6" /> 实时行情监控
        </h2>
        <div className="flex items-center gap-2">
          <div
            className={`h-2 w-2 rounded-full ${monitor?.running ? "bg-green-500 animate-pulse" : "bg-gray-400"}`}
          />
          <span className="text-sm text-muted-foreground">
            {monitor?.running ? `监控中: ${monitor.symbols.join(", ")}` : "监控未启动"}
          </span>
        </div>
      </div>

      {/* Live Prices */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {SYMBOLS.map((sym) => {
          const t = tickers[sym];
          if (!t) return null;
          const prev = prevPrices[sym] || t.last_price;
          const isUp = t.last_price >= prev;
          const dayChange = t.high_24h > 0 ? ((t.last_price - t.low_24h) / t.low_24h) * 100 : 0;

          return (
            <Card key={sym} className="overflow-hidden">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{sym.replace("USDT", "/USDT")}</CardTitle>
                  <Badge variant="outline" className="text-xs">
                    USDT-M
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-end gap-3 mb-4">
                  <span
                    className={`text-3xl font-bold font-mono ${isUp ? "text-green-600" : "text-red-600"}`}
                  >
                    ${t.last_price.toLocaleString()}
                  </span>
                  {isUp ? (
                    <TrendingUp className="h-5 w-5 text-green-600 mb-1" />
                  ) : (
                    <TrendingDown className="h-5 w-5 text-red-600 mb-1" />
                  )}
                </div>

                <div className="grid grid-cols-2 gap-y-2 text-sm">
                  <div>
                    <p className="text-muted-foreground">24h 最高</p>
                    <p className="font-mono">${t.high_24h.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">24h 最低</p>
                    <p className="font-mono">${t.low_24h.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Bid</p>
                    <p className="font-mono">${t.bid.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Ask</p>
                    <p className="font-mono">${t.ask.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">24h 成交量</p>
                    <p className="font-mono">{t.volume_24h.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">24h 波动</p>
                    <p className="font-mono">{dayChange.toFixed(2)}%</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Alerts */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Bell className="h-5 w-5" /> 价格预警
          </CardTitle>
        </CardHeader>
        <CardContent>
          {alerts.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">暂无预警记录</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>时间</TableHead>
                  <TableHead>品种</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead>详情</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {alerts.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(a.created_at).toLocaleString("zh-CN")}
                    </TableCell>
                    <TableCell className="font-medium">{a.symbol}</TableCell>
                    <TableCell>
                      <Badge
                        variant={a.type === "SURGE" ? "default" : "destructive"}
                        className="text-xs"
                      >
                        {a.type}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm">{a.message}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
