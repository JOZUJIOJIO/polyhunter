"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Briefcase } from "lucide-react";
import type { Position } from "@/lib/types";
import { getPositions } from "@/lib/api";

export default function PositionsPage() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPositions()
      .then(setPositions)
      .catch(() => setPositions([]))
      .finally(() => setLoading(false));
  }, []);

  const totalUnrealized = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0);
  const totalValue = positions.reduce((sum, p) => sum + p.current_price * p.size, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Briefcase className="h-6 w-6" /> 持仓
        </h2>
        <div className="flex gap-4 text-sm">
          <span>总价值: <strong className="font-mono">${totalValue.toFixed(2)}</strong></span>
          <span>
            浮动盈亏:{" "}
            <strong className={`font-mono ${totalUnrealized >= 0 ? "text-green-600" : "text-red-600"}`}>
              ${totalUnrealized.toFixed(2)}
            </strong>
          </span>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[35%]">市场</TableHead>
                <TableHead>方向</TableHead>
                <TableHead className="text-right">入场价</TableHead>
                <TableHead className="text-right">当前价</TableHead>
                <TableHead className="text-right">数量</TableHead>
                <TableHead className="text-right">市值</TableHead>
                <TableHead className="text-right">盈亏</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">加载中...</TableCell>
                </TableRow>
              ) : positions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">暂无持仓</TableCell>
                </TableRow>
              ) : (
                positions.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell>
                      <p className="text-sm font-medium truncate max-w-sm">{p.market_question}</p>
                    </TableCell>
                    <TableCell>
                      <Badge variant={p.side === "YES" ? "default" : "secondary"}>{p.side}</Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">${p.avg_entry_price.toFixed(2)}</TableCell>
                    <TableCell className="text-right font-mono text-sm">${p.current_price.toFixed(2)}</TableCell>
                    <TableCell className="text-right text-sm">{p.size}</TableCell>
                    <TableCell className="text-right font-mono text-sm">${(p.current_price * p.size).toFixed(2)}</TableCell>
                    <TableCell className={`text-right font-mono text-sm font-medium ${
                      p.unrealized_pnl >= 0 ? "text-green-600" : "text-red-600"
                    }`}>
                      {p.unrealized_pnl >= 0 ? "+" : ""}${p.unrealized_pnl.toFixed(2)}
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
