export interface Market {
  id: string;
  condition_id: string;
  question: string;
  slug: string | null;
  category: string | null;
  end_date: string | null;
  active: boolean;
  last_price_yes: number | null;
  last_price_no: number | null;
  volume_24h: number | null;
  liquidity: number | null;
  updated_at: string | null;
}

export interface Signal {
  id: number;
  market_id: string;
  type: "ARBITRAGE" | "PRICE_ANOMALY" | "AI_PREDICTION";
  source_detail: string | null;
  current_price: number;
  fair_value: number | null;
  edge_pct: number;
  confidence: number;
  status: "NEW" | "ACTED" | "EXPIRED" | "DISMISSED";
  created_at: string | null;
  market_question: string | null;
}

export interface Trade {
  id: number;
  signal_id: number | null;
  market_id: string;
  token_id: string;
  side: "BUY" | "SELL";
  price: number;
  size: number;
  cost: number;
  status: "PENDING" | "FILLED" | "CANCELLED";
  order_id: string | null;
  pnl: number | null;
  created_at: string | null;
}

export interface Position {
  id: number;
  market_id: string;
  token_id: string;
  side: "YES" | "NO";
  avg_entry_price: number;
  size: number;
  current_price: number;
  unrealized_pnl: number;
  market_question: string | null;
  created_at: string | null;
}

export interface Overview {
  total_balance: number;
  unrealized_pnl: number;
  realized_pnl: number;
  active_positions: number;
  active_signals: number;
  today_trades: number;
  win_rate: number;
}

export interface TradeRequest {
  signal_id?: number;
  market_id: string;
  token_id: string;
  side: "BUY" | "SELL";
  price: number;
  size: number;
}
