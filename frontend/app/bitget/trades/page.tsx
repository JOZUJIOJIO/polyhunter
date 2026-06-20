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
import { ArrowUpRight, ArrowDownRight, History } from "lucide-react";
import type { BitgetTrade } from "@/lib/types";
import { getBitgetTrades } from "@/lib/api";

export default function BitgetTradesPage() {
  const [trades, setTrades] = useState<BitgetTrade[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getBitgetTrades(100)
      .then(setTrades)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const totalPnl = trades.reduce((sum, t) => sum + (t.pnl || 0), 0);
  const filledTrades = trades.filter((t) => t.status === "FILLED");
  const winTrades = filledTrades.filter((t) => t.pnl !== null && t.pnl > 0);
  const winRate = filledTrades.length > 0 ? (winTrades.length / filledTrades.length) * 100 : 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-muted-foreground">Loading trades...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <History className="h-6 w-6" /> Bitget 交易记录
        </h2>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-muted-foreground">
            总交易: <span className="font-bold text-foreground">{trades.length}</span>
          </span>
          <span className="text-muted-foreground">
            胜率: <span className="font-bold text-foreground">{winRate.toFixed(1)}%</span>
          </span>
          <span className={`font-bold font-mono ${totalPnl >= 0 ? "text-green-600" : "text-red-600"}`}>
            总盈亏: ${totalPnl.toFixed(2)}
          </span>
        </div>
      </div>

      <Card>
        <CardContent className="pt-6">
          {trades.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">暂无交易记录</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>时间</TableHead>
                  <TableHead>品种</TableHead>
                  <TableHead>方向</TableHead>
                  <TableHead>策略</TableHead>
                  <TableHead className="text-right">价格</TableHead>
                  <TableHead className="text-right">数量</TableHead>
                  <TableHead className="text-right">成本</TableHead>
                  <TableHead className="text-right">盈亏</TableHead>
                  <TableHead>状态</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trades.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(t.created_at).toLocaleString("zh-CN", {
                        month: "2-digit",
                        day: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })}
                    </TableCell>
                    <TableCell className="font-medium">{t.symbol}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {t.side === "BUY" ? (
                          <ArrowUpRight className="h-4 w-4 text-green-600" />
                        ) : (
                          <ArrowDownRight className="h-4 w-4 text-red-600" />
                        )}
                        <span className={t.side === "BUY" ? "text-green-600" : "text-red-600"}>
                          {t.side}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">
                        {t.strategy || "—"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono">${t.price.toLocaleString()}</TableCell>
                    <TableCell className="text-right font-mono">{t.size}</TableCell>
                    <TableCell className="text-right font-mono">${t.cost.toFixed(2)}</TableCell>
                    <TableCell className="text-right">
                      {t.pnl !== null ? (
                        <span className={`font-mono ${t.pnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          t.status === "FILLED" ? "default" : t.status === "CANCELLED" ? "destructive" : "outline"
                        }
                        className="text-xs"
                      >
                        {t.status}
                      </Badge>
                    </TableCell>
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
