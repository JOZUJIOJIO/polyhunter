"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Zap, X, CheckCircle } from "lucide-react";
import type { Signal } from "@/lib/types";
import { getSignals, dismissSignal, createTrade } from "@/lib/api";

const SIGNAL_TYPE_LABEL: Record<string, string> = {
  ARBITRAGE: "套利",
  PRICE_ANOMALY: "价格异动",
  AI_PREDICTION: "AI 预测",
};

const STATUS_LABEL: Record<string, string> = {
  NEW: "新信号",
  ACTED: "已执行",
  EXPIRED: "已过期",
  DISMISSED: "已忽略",
};

function SignalCard({ signal, onAction }: { signal: Signal; onAction: () => void }) {
  const [showConfirm, setShowConfirm] = useState(false);
  const [executing, setExecuting] = useState(false);
  const detail = signal.source_detail ? JSON.parse(signal.source_detail) : {};

  const handleTrade = async () => {
    setExecuting(true);
    try {
      await createTrade({
        signal_id: signal.id,
        market_id: signal.market_id,
        token_id: "",
        side: "BUY",
        price: signal.current_price,
        size: 10,
      });
      setShowConfirm(false);
      onAction();
    } catch {
      // handle error
    } finally {
      setExecuting(false);
    }
  };

  const handleDismiss = async () => {
    await dismissSignal(signal.id);
    onAction();
  };

  const typeColor = signal.type === "ARBITRAGE" ? "bg-blue-100 text-blue-800" : "bg-orange-100 text-orange-800";

  return (
    <>
      <Card className="transition-shadow hover:shadow-md">
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <Badge className={typeColor}>{SIGNAL_TYPE_LABEL[signal.type] || signal.type}</Badge>
                <Badge variant="outline">置信度: {signal.confidence}%</Badge>
              </div>
              <p className="font-medium text-sm truncate">{signal.market_question}</p>
              <div className="mt-2 grid grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">当前价: </span>
                  <span className="font-mono">${signal.current_price.toFixed(2)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">公允价: </span>
                  <span className="font-mono">${signal.fair_value?.toFixed(2) ?? "-"}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">边际: </span>
                  <span className="font-mono text-green-600">{signal.edge_pct}%</span>
                </div>
              </div>
              {signal.type === "ARBITRAGE" && detail.strategy && (
                <p className="text-xs text-muted-foreground mt-2">
                  策略: {detail.strategy} | YES: ${detail.yes_price} + NO: ${detail.no_price} = ${detail.total_cost}
                </p>
              )}
              {signal.created_at && (
                <p className="text-xs text-muted-foreground mt-1">
                  {new Date(signal.created_at).toLocaleString("zh-CN")}
                </p>
              )}
            </div>
            {signal.status === "NEW" && (
              <div className="flex flex-col gap-2">
                <Button size="sm" onClick={() => setShowConfirm(true)}>
                  <CheckCircle className="h-4 w-4 mr-1" /> 下单
                </Button>
                <Button size="sm" variant="outline" onClick={handleDismiss}>
                  <X className="h-4 w-4 mr-1" /> 忽略
                </Button>
              </div>
            )}
            {signal.status !== "NEW" && (
              <Badge variant="secondary">{STATUS_LABEL[signal.status] || signal.status}</Badge>
            )}
          </div>
        </CardContent>
      </Card>

      <Dialog open={showConfirm} onOpenChange={setShowConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认下单</DialogTitle>
            <DialogDescription>{signal.market_question}</DialogDescription>
          </DialogHeader>
          <div className="space-y-2 text-sm">
            <p>类型: {SIGNAL_TYPE_LABEL[signal.type] || signal.type}</p>
            <p>价格: ${signal.current_price.toFixed(2)}</p>
            <p>边际: {signal.edge_pct}%</p>
            <p>置信度: {signal.confidence}%</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConfirm(false)}>取消</Button>
            <Button onClick={handleTrade} disabled={executing}>
              {executing ? "执行中..." : "确认下单"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default function SignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [filter, setFilter] = useState<string>("NEW");
  const [loading, setLoading] = useState(true);

  const loadSignals = () => {
    setLoading(true);
    getSignals({ status: filter || undefined, limit: 50 })
      .then(setSignals)
      .catch(() => setSignals([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadSignals(); }, [filter]);

  const filterLabels: Record<string, string> = { NEW: "新信号", ACTED: "已执行", DISMISSED: "已忽略", "": "全部" };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Zap className="h-6 w-6" /> 信号中心
        </h2>
        <div className="flex gap-2">
          {["NEW", "ACTED", "DISMISSED", ""].map((s) => (
            <Button key={s} size="sm" variant={filter === s ? "default" : "outline"} onClick={() => setFilter(s)}>
              {filterLabels[s]}
            </Button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="text-center text-muted-foreground py-8">加载中...</p>
      ) : signals.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">暂无信号</CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {signals.map((s) => (
            <SignalCard key={s.id} signal={s} onAction={loadSignals} />
          ))}
        </div>
      )}
    </div>
  );
}
