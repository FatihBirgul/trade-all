import { useState } from "react";
// Account/session changes start from page zero immediately, before any request.
export function usePage(scope: string) {
  const [page, setPage] = useState({ scope, offset: 0 });
  const offset = page.scope === scope ? page.offset : 0;
  return {
    offset,
    previous: () => setPage({ scope, offset: Math.max(0, offset - 20) }),
    next: () => setPage({ scope, offset: offset + 20 }),
    reset: () => setPage({ scope, offset: 0 }),
  };
}
