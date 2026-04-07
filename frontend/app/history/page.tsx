"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { History } from "lucide-react";
import type { Trade } from "@/lib/types";
import { getTrades } from "@/lib/api";

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
          <History className="h-6 w-6" /> Trade History
        </h2>
        <div className="flex gap-4 text-sm">
          <span>Total Trades: <strong>{trades.length}</strong></span>
          <span>Win Rate: <strong>{winRate.toFixed(1)}%</strong></span>
          <span>
            Total PnL:{" "}
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
                <TableHead>Date</TableHead>
                <TableHead>Side</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead className="text-right">Size</TableHead>
                <TableHead className="text-right">Cost</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">PnL</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">Loading...</TableCell>
                </TableRow>
              ) : trades.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">No trades yet</TableCell>
                </TableRow>
              ) : (
                trades.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="text-sm">
                      {t.created_at ? new Date(t.created_at).toLocaleString() : "-"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={t.side === "BUY" ? "default" : "secondary"}>{t.side}</Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">${t.price.toFixed(2)}</TableCell>
                    <TableCell className="text-right text-sm">{t.size}</TableCell>
                    <TableCell className="text-right font-mono text-sm">${t.cost.toFixed(2)}</TableCell>
                    <TableCell>
                      <Badge variant={
                        t.status === "FILLED" ? "default" :
                        t.status === "CANCELLED" ? "destructive" : "secondary"
                      }>
                        {t.status}
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
