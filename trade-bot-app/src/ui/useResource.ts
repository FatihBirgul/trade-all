import { useCallback, useEffect, useRef, useState } from "react";

// Bir isteğin üç durumu: yükleniyor / hata / veri. Yeniden yüklerken eldeki veri ekranda kalır.
export type Resource<T> = { data: T | null; error: string; loading: boolean; reload: () => Promise<void> };

export function useResource<T>(load: (() => Promise<T>) | null, key: string, everyMs?: number): Resource<T> {
  const [state, setState] = useState<{ data: T | null; error: string; loading: boolean }>({ data: null, error: "", loading: load !== null });
  const latest = useRef(0);
  const loader = useRef(load);
  loader.current = load;
  const reload = useCallback(async () => {
    const run = loader.current;
    if (!run) return;
    const mine = ++latest.current;
    setState((current) => ({ ...current, loading: true }));
    try {
      const data = await run();
      if (mine === latest.current) setState({ data, error: "", loading: false });
    } catch (reason) {
      if (mine === latest.current)
        setState((current) => ({ data: current.data, error: reason instanceof Error ? reason.message : "Sunucuya ulaşılamadı.", loading: false }));
    }
  }, []);
  useEffect(() => {
    latest.current += 1; // anahtar değişti: eski yanıt yok sayılır
    setState({ data: null, error: "", loading: loader.current !== null });
    void reload();
    if (!everyMs) return;
    const timer = setInterval(() => void reload(), everyMs);
    return () => clearInterval(timer);
  }, [key, everyMs, reload]);
  return { ...state, reload };
}
