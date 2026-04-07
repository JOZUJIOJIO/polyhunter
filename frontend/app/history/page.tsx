"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { History } from "lucide-react";
import type { Trade } from "@/lib/types";
import { getTrades } from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  FILLED: "已成交",
  CANCELLED: "已取消",
  PENDING: "待成交",
};

export default function HistoryPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTrades({ limit: 100 })
      .then(setTrades)
      .catch(() => setTrades([]))
      .finally(() => setLoading(false));
  }, []);

  const totalPnl = trades.reduce((sum, t) => sum + (t.pnl || 0), 0);
  const filledTrades = trades.filter((t) => t.status === "FILLED");
  const winningTrades = filledTrades.filter((t) => (t.pnl || 0) > 0);
  const winRate = filledTrades.length > 0 ? (winningTrades.length / filledTrades.length) * 100 : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <History className="h-6 w-6" /> 交易历史
        </h2>
        <div className="flex gap-4 text-sm">
          <span>总交易: <strong>{trades.length}</strong></span>
          <span>胜率: <strong>{winRate.toFixed(1)}%</strong></span>
          <span>
            总盈亏:{" "}
            <strong className={`font-mono ${totalPnl >= 0 ? "text-green-600" : "text-red-600"}`}>
              ${totalPnl.toFixed(2)}
            </strong>
          </span>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>时间</TableHead>
                <TableHead>方向</TableHead>
                <TableHead className="text-right">价格</TableHead>
                <TableHead className="text-right">数量</TableHead>
                <TableHead className="text-right">成本</TableHead>
                <TableHead>状态</TableHead>
                <TableHead className="text-right">盈亏</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">加载中...</TableCell>
                </TableRow>
              ) : trades.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">暂无交易记录</TableCell>
                </TableRow>
              ) : (
                trades.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="text-sm">
                      {t.created_at ? new Date(t.created_at).toLocaleString("zh-CN") : "-"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={t.side === "BUY" ? "default" : "secondary"}>
                        {t.side === "BUY" ? "买入" : "卖出"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">${t.price.toFixed(2)}</TableCell>
                    <TableCell className="text-right text-sm">{t.size}</TableCell>
                    <TableCell className="text-right font-mono text-sm">${t.cost.toFixed(2)}</TableCell>
                    <TableCell>
                      <Badge variant={
                        t.status === "FILLED" ? "default" :
                        t.status === "CANCELLED" ? "destructive" : "secondary"
                      }>
                        {STATUS_LABEL[t.status] || t.status}
                      </Badge>
                    </TableCell>
                    <TableCell className={`text-right font-mono text-sm font-medium ${
                      (t.pnl || 0) >= 0 ? "text-green-600" : "text-red-600"
                    }`}>
                      {t.pnl != null ? `${t.pnl >= 0 ? "+" : ""}$${t.pnl.toFixed(2)}` : "-"}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
