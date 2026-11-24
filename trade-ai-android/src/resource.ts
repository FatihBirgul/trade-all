import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api/client";
import { userErrorText } from "./domain/presentation";
type State<T> = {
  key: string;
  data?: T;
  error?: string;
  errorCode?: string;
  errorStatus?: number;
  loading: boolean;
  stale: boolean;
  loadedAt: number | null;
};
export function useResource<T>(load: () => Promise<T>, key: string) {
  const loader = useRef(load);
  const flight = useRef<{ key: string; running: boolean } | null>(null);
  useEffect(() => {
    loader.current = load;
  }, [load]);
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<State<T>>({
    key,
    loading: true,
    stale: false,
    loadedAt: null,
  });
  useEffect(() => {
    let alive = true;
    const pending = { key, running: true };
    flight.current = pending;
    void loader
      .current()
      .then((data) => {
        if (alive)
          setState({
            key,
            data,
            loading: false,
            stale: false,
            loadedAt: Date.now(),
          });
      })
      .catch((error: unknown) => {
        if (alive)
          setState((old) => ({
            key,
            data: old.key === key ? old.data : undefined,
            loadedAt: old.key === key ? old.loadedAt : null,
            error: userErrorText(error, "Veri alınamadı."),
            errorCode: error instanceof ApiError ? error.code : "UNKNOWN",
            errorStatus: error instanceof ApiError ? error.status : undefined,
            loading: false,
            stale: true,
          }));
      })
      .finally(() => {
        pending.running = false;
      });
    return () => {
      alive = false;
    };
  }, [key, revision]);
  const reload = useCallback(() => {
    if (flight.current?.key === key && flight.current.running) return;
    // Lock immediately, before React commits, to coalesce rapid taps.
    flight.current = { key, running: true };
    setState((old) => ({
      key,
      data: old.key === key ? old.data : undefined,
      loadedAt: old.key === key ? old.loadedAt : null,
      loading: true,
      stale: true,
    }));
    setRevision((r) => r + 1);
  }, [key]);
  return {
    ...(state.key === key
      ? state
      : { key, loading: true, stale: false, loadedAt: null }),
    reload,
  };
}
