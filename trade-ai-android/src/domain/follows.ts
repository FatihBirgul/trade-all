import type { components } from "../api/schema";
import type { Account } from "./safety";
export type Follow = components["schemas"]["TrackingResponse"];
export type Notice = components["schemas"]["NotificationResponse"];
export function allowedFollows(rows: Follow[], accounts: Account[]) {
  if (
    rows.length > 100 ||
    rows.some(
      (r) => r.data_mode !== "live" || !accounts.includes(r.portfolio_id),
    )
  )
    throw new Error("Takip kayıtlarının hesap/veri modu doğrulanamadı.");
  return [...new Map(rows.map((r) => [r.tracking_id, r])).values()].sort(
    (a, b) =>
      Number(b.enabled) - Number(a.enabled) ||
      (b.last_checked_ms ?? 0) - (a.last_checked_ms ?? 0),
  );
}
export function latestFollowChange(
  rows: Notice[],
  follow: Follow,
): Notice | undefined {
  return rows
    .filter(
      (n) =>
        n.data_mode === "live" &&
        n.kind === "analysis" &&
        n.details.change_kind === "analysis_condition_changed" &&
        n.details.tracking_id === follow.tracking_id &&
        n.details.portfolio_id === follow.portfolio_id &&
        typeof n.details.analysis_id === "string" &&
        /^[a-f0-9]{64}$/.test(n.details.analysis_id),
    )
    .sort((a, b) => b.created_at_ms - a.created_at_ms)[0];
}
export async function loadFollowChanges(api: {
  notifications: (offset: number) => Promise<Notice[]>;
}) {
  const rows: Notice[] = [];
  for (let offset = 0; offset < 100; offset += 20) {
    const page = await api.notifications(offset);
    rows.push(...page.slice(0, 20));
    if (page.length < 20) break;
  }
  return [...new Map(rows.map((n) => [n.notification_id, n])).values()];
}
