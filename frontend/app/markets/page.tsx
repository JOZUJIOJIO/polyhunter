"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Search } from "lucide-react";
import type { Market } from "@/lib/types";
import { getMarkets } from "@/lib/api";

export default function MarketsPage() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(true);
      getMarkets({ search: search || undefined, active: true, limit: 100 })
        .then(setMarkets)
        .catch(() => setMarkets([]))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">市场</h2>
        <div className="relative w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="搜索市场..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40%]">市场</TableHead>
                <TableHead>分类</TableHead>
                <TableHead className="text-right">YES</TableHead>
                <TableHead className="text-right">NO</TableHead>
                <TableHead className="text-right">24h 成交量</TableHead>
                <TableHead className="text-right">流动性</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">加载中...</TableCell>
                </TableRow>
              ) : markets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">未找到市场</TableCell>
                </TableRow>
              ) : (
                markets.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell>
                      <p className="font-medium text-sm truncate max-w-md">{m.question}</p>
                      {m.end_date && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          到期: {new Date(m.end_date).toLocaleDateString("zh-CN")}
                        </p>
                      )}
                    </TableCell>
                    <TableCell>
                      {m.category && <Badge variant="outline" className="text-xs">{m.category}</Badge>}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm text-green-600">
                      {m.last_price_yes != null ? `$${m.last_price_yes.toFixed(2)}` : "-"}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm text-red-600">
                      {m.last_price_no != null ? `$${m.last_price_no.toFixed(2)}` : "-"}
                    </TableCell>
                    <TableCell className="text-right text-sm">
                      {m.volume_24h != null ? `$${(m.volume_24h / 1000).toFixed(1)}K` : "-"}
                    </TableCell>
                    <TableCell className="text-right text-sm">
                      {m.liquidity != null ? `$${(m.liquidity / 1000).toFixed(1)}K` : "-"}
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
