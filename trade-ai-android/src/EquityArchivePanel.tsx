import React, { useState } from "react";
import { useApp } from "./state";
import { useResource } from "./resource";
import { Button, Label, Choices, Loading, Failure, Empty } from "./ui";
import { MiniPriceChart } from "./MiniPriceChart";

/** Bounded single-page UI; never recalculates accounting or joins across accounts. */
export function EquityArchivePanel({ range }: { range: string }) {
  const app = useApp();
  const [selection, setSelection] = useState<{
    cutoff: number;
    cursor?: string;
    sampling: "raw" | "minmax";
  }>(() => ({ cutoff: Date.now(), sampling: "raw" }));
  const supported =
    app.mode === "live" &&
    app.gatewayVerified &&
    !!app.sessionInfo?.capabilities?.includes("equity-history-window-v1") &&
    app.sessionInfo.accounts.includes(app.account) &&
    app.sessionInfo.scopes.includes("read");
  const days =
    range === "1 gün" ? 1 : range === "7 gün" ? 7 : range === "30 gün" ? 30 : 0;
  const from = days ? selection.cutoff - days * 86400000 : 0;
  const q = useResource(
    async () =>
      supported
        ? app.api.equityWindow(
            app.account,
            from,
            selection.cutoff,
            selection.cursor,
            selection.sampling,
          )
        : null,
    [
      app.account,
      app.connectionKey,
      app.config.session,
      supported,
      from,
      selection.cutoff,
      selection.cursor,
      selection.sampling,
    ].join("|"),
  );
  if (!supported)
    return (
      <Label muted>
        Eski Gateway ile arşiv sayfalaması kapalı; son kayıt görünümü korunur.
      </Label>
    );
  const data = q.data;
  const points =
    data?.points.filter(
      (p) =>
        p.chart_eligible &&
        p.quality_status === "complete" &&
        p.equity_quote !== null &&
        /^\d+(\.\d+)?$/.test(p.equity_quote) &&
        Number.isFinite(Number(p.equity_quote)),
    ) || [];
  return (
    <>
      <Label>Arşiv · gerçek kayıtlar</Label>
      <Choices
        values={["Sayfalar", "Aralık özeti"]}
        value={selection.sampling === "raw" ? "Sayfalar" : "Aralık özeti"}
        onChange={(value) =>
          setSelection({
            cutoff: selection.cutoff,
            sampling: value === "Sayfalar" ? "raw" : "minmax",
          })
        }
      />
      <Button
        title="Arşivi baştan yenile"
        disabled={q.loading}
        onPress={() =>
          setSelection({ cutoff: Date.now(), sampling: selection.sampling })
        }
      />
      {q.loading ? <Loading /> : null}
      {q.error ? <Failure message={q.error} retry={q.reload} /> : null}
      {q.stale && data ? (
        <Label>Güncel değil · son başarılı arşiv sorgusu.</Label>
      ) : null}
      {data?.status === "incomplete_budget" ? (
        <Label>
          Aralık örnekleme bütçesini aşıyor. Kısmi grafik üretilmedi; tarih
          aralığını daraltın veya Sayfalar seçin.
        </Label>
      ) : null}
      {data?.status === "complete" && !points.length ? (
        <Empty text="Bu sayfada grafik için tam kaynaklı gözlem yok." />
      ) : null}
      {points.length >= 2 ? (
        <MiniPriceChart
          prices={points.map((p) => p.equity_quote!)}
          accessibilityLabel="Arşivdeki gerçek özsermaye gözlemleri"
        />
      ) : null}
      {data ? (
        <Label muted>
          {data.sampling === "minmax"
            ? "Min/max örnekleme: gerçek ilk/son ve bölüm uçları; ara hareketlerin tamamı değildir."
            : "Tek sayfa; kayıt sırası. Önceki sayfalar bellekte biriktirilmez."}{" "}
          {points.length} gösterilen / {data.observations_scanned} incelenen.
          Sabit üst kayıt: {data.watermark}. Örneklemede çıkarılan eksik
          kayıtlar: {data.excluded_incomplete}.
        </Label>
      ) : null}
      {data?.points.length ? (
        <Label muted>
          Sayfa UTC sınırları:{" "}
          {new Date(data.points[0].recorded_at_ms).toISOString()} –{" "}
          {new Date(
            data.points[data.points.length - 1].recorded_at_ms,
          ).toISOString()}
          . Kayıt saati geriye alınmışsa sıra, hesap sequence değeridir.
        </Label>
      ) : null}
      {data?.has_more && data.next_cursor ? (
        <Button
          title="Daha eski gözlemler"
          disabled={q.loading || q.stale}
          onPress={() =>
            setSelection({ ...selection, cursor: data.next_cursor! })
          }
        />
      ) : null}
    </>
  );
}
