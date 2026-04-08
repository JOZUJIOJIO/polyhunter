import type { Market, Signal, Trade, Position, Overview, TradeRequest, AutoTradeSettings } from "./types";

const BASE = "/api";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// Overview
export async function getOverview(): Promise<Overview> {
  return fetchJson<Overview>("/overview");
}

// Markets
export async function getMarkets(params?: {
  active?: boolean;
  category?: string;
  search?: string;
  limit?: number;
}): Promise<Market[]> {
  const query = new URLSearchParams();
  if (params?.active !== undefined) query.set("active", String(params.active));
  if (params?.category) query.set("category", params.category);
  if (params?.search) query.set("search", params.search);
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return fetchJson<Market[]>(`/markets${qs ? `?${qs}` : ""}`);
}

export async function getMarket(id: string): Promise<Market> {
  return fetchJson<Market>(`/markets/${id}`);
}

// Signals
export async function getSignals(params?: {
  status?: string;
  signal_type?: string;
  limit?: number;
}): Promise<Signal[]> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.signal_type) query.set("signal_type", params.signal_type);
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return fetchJson<Signal[]>(`/signals${qs ? `?${qs}` : ""}`);
}

export async function dismissSignal(id: number): Promise<void> {
  await fetchJson(`/signals/${id}/dismiss`, { method: "POST" });
}

// Trades
export async function getTrades(params?: {
  market_id?: string;
  status?: string;
  limit?: number;
}): Promise<Trade[]> {
  const query = new URLSearchParams();
  if (params?.market_id) query.set("market_id", params.market_id);
  if (params?.status) query.set("status", params.status);
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return fetchJson<Trade[]>(`/trades${qs ? `?${qs}` : ""}`);
}

export async function createTrade(req: TradeRequest): Promise<Trade> {
  return fetchJson<Trade>("/trades", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// Positions
export async function getPositions(): Promise<Position[]> {
  return fetchJson<Position[]>("/positions");
}

// Auto Trade Settings
export async function getAutoTradeSettings(): Promise<AutoTradeSettings> {
  return fetchJson<AutoTradeSettings>("/auto-trade");
}

export async function updateAutoTradeSettings(settings: AutoTradeSettings): Promise<AutoTradeSettings> {
  return fetchJson<AutoTradeSettings>("/auto-trade", {
    method: "POST",
    body: JSON.stringify(settings),
  });
}
