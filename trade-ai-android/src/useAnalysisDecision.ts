import { useEffect, useState } from "react";
import { AppState } from "react-native";
import { safeDecision, type Analysis } from "./domain/safety";

// Expire visible levels even if the user leaves the detail screen open.
export function useAnalysisDecision(analysis?: Analysis) {
  const [, refresh] = useState(0);
  const expires = analysis?.expires_at_ms;
  useEffect(() => {
    const update = () => refresh((v) => v + 1);
    const remaining = (expires ?? 0) - Date.now();
    const timer =
      remaining > 0
        ? setTimeout(update, Math.min(remaining + 1, 2147483647))
        : undefined;
    const subscription = AppState.addEventListener("change", update);
    return () => {
      clearTimeout(timer);
      subscription.remove();
    };
  }, [expires]);
  return analysis ? safeDecision(analysis) : "WAIT";
}
