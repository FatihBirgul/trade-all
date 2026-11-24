import React, { useEffect, useState } from "react";
import { View } from "react-native";
import { useTheme } from "./theme";
import { Label, Row, Disclosure } from "./ui";
import {
  healthStatus,
  observeHealth,
  observedDuration,
  validTime,
  type HealthInput,
} from "./domain/scannerHealth";
const time = (v: unknown) =>
  validTime(v) ? new Date(v).toISOString() : "Doğrulanmadı";
export function useUiClock(scope: string, observedAt?: number | null) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const first = setTimeout(() => setNow(Date.now()), 0);
    const id = setInterval(() => setNow(Date.now()), 30000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, [scope, observedAt]);
  return now;
}
export function ScannerHealth({
  input,
  scope,
  lastVerifiedAt,
  now,
}: {
  input: Omit<HealthInput, "now">;
  scope: string;
  lastVerifiedAt?: number | null;
  now: number;
}) {
  const { colors } = useTheme();
  const failed =
    !!input.errorCode &&
    !["SCOPE_DENIED", "UNAUTHORIZED"].includes(input.errorCode);
  const succeeded =
    !!input.runtime &&
    !input.stale &&
    !input.errorCode &&
    input.gatewayVerified;
  const observationKey = [
    scope,
    failed,
    succeeded,
    input.observedAt ?? "none",
  ].join("|");
  const [observation, setObservation] = useState(() => ({
    key: observationKey,
    memory: observeHealth(
      { scope, failedSince: null, lastRecoveredAt: null },
      scope,
      now,
      failed,
      succeeded,
    ),
  }));
  if (observation.key !== observationKey)
    setObservation({
      key: observationKey,
      memory: observeHealth(observation.memory, scope, now, failed, succeeded),
    });
  const current =
    observation.memory.scope === scope
      ? observation.memory
      : { scope, failedSince: null, lastRecoveredAt: null };
  const health = healthStatus({ ...input, now });
  const tone =
    health.status === "ONLINE"
      ? colors.green
      : health.status === "UNAUTHORIZED"
        ? colors.red
        : colors.gold;
  return (
    <View style={{ gap: 8 }}>
      <View
        style={{
          alignSelf: "flex-start",
          borderWidth: 1,
          borderColor: tone,
          borderRadius: 10,
          paddingHorizontal: 12,
          paddingVertical: 6,
        }}
      >
        <Label style={{ color: tone, fontWeight: "700" }}>
          {health.status} · {health.title}
        </Label>
      </View>
      <Label>{health.detail}</Label>
      <Disclosure title="Bağlantı ve güncellik ayrıntıları">
        <Row name="Son başarılı bağlantı (UTC)" value={time(lastVerifiedAt)} />
        <Row
          name="Son doğrulanan tarama sağlığı (UTC)"
          value={time(input.observedAt)}
        />
        <Row
          name="Gözlem güncelliği"
          value={
            !input.stale &&
            validTime(input.observedAt) &&
            0 <= now - input.observedAt &&
            now - input.observedAt <= 120000
              ? "Son 2 dakika içinde doğrulandı"
              : "Eski veya bilinmiyor · yenileyin"
          }
        />
        {current.failedSince !== null ? (
          <Row
            name="İlk başarısız gözlemden beri (yaklaşık)"
            value={observedDuration(current.failedSince, now)}
          />
        ) : null}
        {current.lastRecoveredAt !== null ? (
          <Row
            name="Son toparlanma gözlemi (UTC)"
            value={time(current.lastRecoveredAt)}
          />
        ) : null}
        <Label muted>
          Süre bu ekranın ilk başarısız gözleminden başlar; gerçek kesinti
          başlangıcı değildir. Ekran saati 30 saniyede bir yenilenir. Dış izleme
          / telefon ağı sensörü kurulmadı.
        </Label>
      </Disclosure>
    </View>
  );
}
