"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Zap, X, CheckCircle } from "lucide-react";
import type { Signal } from "@/lib/types";
import { getSignals, dismissSignal, createTrade } from "@/lib/api";

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
                <Badge className={typeColor}>{signal.type.replace("_", " ")}</Badge>
                <Badge variant="outline">Confidence: {signal.confidence}%</Badge>
              </div>
              <p className="font-medium text-sm truncate">{signal.market_question}</p>
              <div className="mt-2 grid grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Price: </span>
                  <span className="font-mono">${signal.current_price.toFixed(2)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Fair Value: </span>
                  <span className="font-mono">${signal.fair_value?.toFixed(2) ?? "-"}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Edge: </span>
                  <span className="font-mono text-green-600">{signal.edge_pct}%</span>
                </div>
              </div>
              {signal.type === "ARBITRAGE" && detail.strategy && (
                <p className="text-xs text-muted-foreground mt-2">
                  Strategy: {detail.strategy} | YES: ${detail.yes_price} + NO: ${detail.no_price} = ${detail.total_cost}
                </p>
              )}
              {signal.created_at && (
                <p className="text-xs text-muted-foreground mt-1">
                  {new Date(signal.created_at).toLocaleString()}
                </p>
              )}
            </div>
            {signal.status === "NEW" && (
              <div className="flex flex-col gap-2">
                <Button size="sm" onClick={() => setShowConfirm(true)}>
                  <CheckCircle className="h-4 w-4 mr-1" /> Trade
                </Button>
                <Button size="sm" variant="outline" onClick={handleDismiss}>
                  <X className="h-4 w-4 mr-1" /> Dismiss
                </Button>
              </div>
            )}
            {signal.status !== "NEW" && (
              <Badge variant="secondary">{signal.status}</Badge>
            )}
          </div>
        </CardContent>
      </Card>

      <Dialog open={showConfirm} onOpenChange={setShowConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Trade</DialogTitle>
            <DialogDescription>
              {signal.market_question}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 text-sm">
            <p>Type: {signal.type}</p>
            <p>Price: ${signal.current_price.toFixed(2)}</p>
            <p>Edge: {signal.edge_pct}%</p>
            <p>Confidence: {signal.confidence}%</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConfirm(false)}>Cancel</Button>
            <Button onClick={handleTrade} disabled={executing}>
              {executing ? "Executing..." : "Confirm Order"}
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Zap className="h-6 w-6" /> Signals
        </h2>
        <div className="flex gap-2">
          {["NEW", "ACTED", "DISMISSED", ""].map((s) => (
            <Button
              key={s}
              size="sm"
              variant={filter === s ? "default" : "outline"}
              onClick={() => setFilter(s)}
            >
              {s || "All"}
            </Button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="text-center text-muted-foreground py-8">Loading...</p>
      ) : signals.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No signals found
          </CardContent>
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
