import { useSyncExternalStore } from "react";

// Son isteklerin kaydı (Tanı ekranı). Yalnızca yol, yanıt kodu ve süre tutulur; gövde ve anahtar tutulmaz.
export type RequestEntry = { at: number; method: string; path: string; status: number; ms: number; error: string | null };

const MAX = 40;
let entries: RequestEntry[] = [];
const listeners = new Set<() => void>();

export function recordRequest(entry: RequestEntry): void {
  entries = [entry, ...entries].slice(0, MAX);
  listeners.forEach((listener) => listener());
}
export function clearRequests(): void {
  entries = [];
  listeners.forEach((listener) => listener());
}
const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};
export const useRequestLog = (): RequestEntry[] => useSyncExternalStore(subscribe, () => entries, () => entries);
