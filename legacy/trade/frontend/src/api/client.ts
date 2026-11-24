// Centralized API client. All network access goes through here.
// Backend base comes from env — never hard-coded.

const BASE = process.env.EXPO_PUBLIC_BACKEND_URL;

const url = (path: string) => `${BASE}/api${path}`;

async function request<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url(path), {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

export interface Market {
  symbol: string;
  base: string;
  quote: string;
  name: string;
  price?: number;
  change_24h_pct?: number;
  high_24h?: number;
  low_24h?: number;
  volume_24h?: number;
  available: boolean;
}

export const Api = {
  config: () => request("/config"),
  markets: () => request<{ markets: Market[]; provider: string }>("/markets"),
  marketDetail: (symbol: string, timeframe: string) =>
    request(`/markets/${symbol}?timeframe=${timeframe}`),
  technical: (symbol: string, timeframe: string) =>
    request(`/markets/${symbol}/technical?timeframe=${timeframe}`),
  createAnalysis: (payload: { symbol: string; timeframe: string; image_base64?: string }) =>
    request("/analysis", { method: "POST", body: JSON.stringify(payload) }),
  history: (limit = 50) => request<{ items: any[] }>(`/history?limit=${limit}`),
  historyDetail: (id: string) => request(`/history/${id}`),
  deleteHistory: (id: string) => request(`/history/${id}`, { method: "DELETE" }),
  evaluateAll: () => request<{ evaluated: number; performance: any }>("/history/evaluate-all", { method: "POST" }),
  performance: () => request("/performance"),
  news: (symbol?: string) => request(`/news${symbol ? `?symbol=${symbol}` : ""}`),
};
