import { useCallback, useEffect, useRef, useState } from "react";
import type { Analysis } from "./domain/safety";
import { uniqueRecords } from "./domain/records";
import { userErrorText } from "./domain/presentation";
type State = {
  scope: string;
  rows: Analysis[];
  offset: number;
  loading: boolean;
  error?: string;
  hasMore: boolean;
};
const empty = (scope: string): State => ({
  scope,
  rows: [],
  offset: 0,
  loading: true,
  hasMore: true,
});
export function usePagedHistory(
  loader: (offset: number) => Promise<Analysis[]>,
  scope: string,
  accountFiltered = false,
) {
  const load = useRef(loader),
    generation = useRef(0),
    activeScope = useRef(scope),
    cursor = useRef(0),
    pending = useRef(false);
  const [revision, setRevision] = useState(0),
    [state, setState] = useState<State>(() => empty(scope));
  useEffect(() => {
    load.current = loader;
  }, [loader]);
  const read = useCallback(
    async (offset: number, append: boolean, expected: number) => {
      if (expected !== generation.current || activeScope.current !== scope)
        return;
      pending.current = true;
      setState((old) => ({
        ...empty(scope),
        rows: old.scope === scope ? old.rows : [],
        offset,
        loading: true,
      }));
      try {
        const rows = await load.current(offset);
        if (rows.length > 20)
          throw new Error("Geçmiş sayfa boyutu doğrulanamadı.");
        if (generation.current !== expected) return;
        cursor.current = offset + 20;
        setState((old) => ({
          scope,
          rows: uniqueRecords(
            append && old.scope === scope ? [...old.rows, ...rows] : rows,
            (a) => a.analysis_id,
          ),
          offset,
          loading: false,
          hasMore: offset + 20 < 400 && (rows.length === 20 || accountFiltered),
        }));
      } catch (error) {
        if (generation.current === expected)
          setState((old) => ({
            ...old,
            scope,
            loading: false,
            error: userErrorText(error),
            hasMore: true,
          }));
      } finally {
        if (generation.current === expected) pending.current = false;
      }
    },
    [scope, accountFiltered],
  );
  useEffect(() => {
    activeScope.current = scope;
    cursor.current = 0;
    const expected = ++generation.current;
    void read(0, false, expected);
    return () => {
      generation.current += 1;
    };
  }, [scope, revision, read]);
  return {
    ...(state.scope === scope ? state : empty(scope)),
    reload: () => {
      if (!pending.current) setRevision((v) => v + 1);
    },
    more: () => {
      if (!pending.current && cursor.current < 400)
        void read(cursor.current, true, generation.current);
    },
  };
}
