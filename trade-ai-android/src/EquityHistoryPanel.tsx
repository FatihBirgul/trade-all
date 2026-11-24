import React, { useState } from "react";
import { useApp } from "./state";
import { useResource } from "./resource";
import {
  Card,
  Heading,
  Label,
  Row,
  Button,
  Choices,
  Loading,
  Failure,
  Empty,
  Disclosure,
} from "./ui";
import { EquityArchivePanel } from "./EquityArchivePanel";
import { MiniPriceChart } from "./MiniPriceChart";
import { money } from "./domain/safety";
export function EquityHistoryPanel() {
  const app = useApp();
  const [range, setRange] = useState("7 gün");
  const [period, setPeriod] = useState("Günlük");
  const supported =
    app.mode === "live" &&
    app.gatewayVerified &&
    !!app.sessionInfo?.capabilities?.includes("equity-history-v1") &&
    !!app.sessionInfo.accounts.includes(app.account) &&
    app.sessionInfo.scopes.includes("read");
  const q = useResource(async () => {
    if (!supported) return null;
    const now = Date.now(),
      days =
        range === "1 gün"
          ? 1
          : range === "7 gün"
            ? 7
            : range === "30 gün"
              ? 30
              : 0;
    return app.api.equityHistory(
      app.account,
      days ? now - days * 86400000 : 0,
      now,
      period === "Günlük" ? "day" : period === "Haftalık" ? "week" : "month",
    );
  }, [app.mode, app.account, app.connectionKey, app.config.session, range, period, supported].join("|"));
  if (!supported)
    return (
      <Card>
        <Heading>Özsermaye geçmişi</Heading>
        <Label>
          Doğrulanmış CANLI bağlantı, hesap okuma yetkisi ve güncel
          Backend/Gateway gerekir. Örnek eğri oluşturulmadı.
        </Label>
      </Card>
    );
  const data = q.data,
    last = data?.points[data.points.length - 1];
  const chart =
    data?.points.filter(
      (p) =>
        p.chart_eligible &&
        p.quality_status === "complete" &&
        typeof p.equity_quote === "string" &&
        /^\d+(\.\d+)?$/.test(p.equity_quote) &&
        Number.isFinite(Number(p.equity_quote)),
    ) || [];
  return (
    <Card>
      <Heading>Doğrulanabilir sanal özsermaye</Heading>
      <Choices
        values={["1 gün", "7 gün", "30 gün", "Tümü"]}
        value={range}
        onChange={setRange}
      />
      <Choices
        values={["Günlük", "Haftalık", "Aylık"]}
        value={period}
        onChange={setPeriod}
      />
      <EquityArchivePanel
        key={[app.account, range, app.connectionKey].join("|")}
        range={range}
      />
      <Button
        title="Özsermaye geçmişini yenile"
        disabled={q.loading}
        onPress={q.reload}
      />
      {q.error ? <Failure message={q.error} retry={q.reload} /> : null}
      {q.loading ? <Loading /> : null}
      {q.stale && data ? (
        <Label>Güncel değil · aşağıdaki kayıtlar son başarılı sorgudan.</Label>
      ) : null}
      {!q.loading && !last ? (
        <Empty text="Bu hesap ve dönemde kalıcı özsermaye gözlemi yok. Geçmiş değer üretilmedi." />
      ) : null}
      {last && data ? (
        <>
          <Label muted>
            Son tarihsel gözlem:{" "}
            {new Date(last.recorded_at_ms).toLocaleString("tr-TR")}. Güncel
            bakiye sorgusu veya backtest değildir.
          </Label>
          {chart.length >= 2 ? (
            <MiniPriceChart
              prices={chart.map((p) => p.equity_quote!)}
              accessibilityLabel="Sıralı gerçek sanal özsermaye gözlemleri"
            />
          ) : (
            <Label>Grafik için en az iki tam kaynaklı gözlem gerekir.</Label>
          )}
          <Label muted>
            {chart.length} grafik noktası / {data.points.length} gözlem.
            Noktalar kayıt sırasındadır; aralarında fiyat interpolasyonu
            yapılmaz.
          </Label>
          {data.points.some((p) => !p.chart_eligible) ? (
            <Label>
              Eski veya eksik mark içeren kayıtlar grafikten ve drawdown
              güncellemesinden çıkarıldı.
            </Label>
          ) : null}
          {data.has_more ? (
            <Label>
              Seçilen dönemin son 200 kaydı gösteriliyor; daha eski kayıtlar
              silinmedi.
            </Label>
          ) : null}
          <Row
            name="Özsermaye · son kayıt"
            value={
              last.equity_quote === null
                ? "Kaynak eksik"
                : money(last.equity_quote) + " USDT"
            }
          />
          <Row
            name="Nakit / rezerve"
            value={
              money(last.cash_quote) +
              " / " +
              money(last.reserved_cash_quote) +
              " USDT"
            }
          />
          <Row
            name="Gerçekleşmiş sanal PnL"
            value={money(last.realized_pnl_quote) + " USDT"}
          />
          <Row
            name="Gerçekleşmemiş sanal PnL"
            value={
              last.unrealized_pnl_quote === null
                ? "Kaynak eksik"
                : money(last.unrealized_pnl_quote) + " USDT"
            }
          />
          <Row
            name="Açık / kapalı / belirsizlik geçmişi"
            value={
              last.open_positions +
              " / " +
              last.closed_positions +
              " / " +
              last.ambiguous_positions
            }
          />
          <Row name="Ücret toplamı" value={money(last.fees_quote) + " USDT"} />
          <Row
            name="Gözlenen maksimum drawdown"
            value={
              money(last.maximum_drawdown_quote) +
              " USDT · " +
              last.maximum_drawdown_pct +
              "%"
            }
          />
          <Label muted>
            Drawdown, kayıt başlangıcından bu gözleme kadar tam kaynaklı
            noktaları kapsar; kesintisiz piyasa maksimumu değildir. Ücretler PnL
            içindedir; spread/slippage gerçekleşme fiyatına dahildir ve ayrı
            tutarları kaydedilmemiştir.
          </Label>
          {last.strategy_results.map((s, i) => (
            <Row
              key={i}
              name={String(s.strategy_id)}
              value={
                money(String(s.realized_pnl_quote)) +
                " USDT · ücret " +
                money(String(s.fees_quote))
              }
            />
          ))}
          <Disclosure title="Mark kaynakları ve zamanları">
            {!last.marks.length ? (
              <Label>
                Bu gözlemde açık miktar yok; fiyat markı gerektiren varlık
                bulunmuyor.
              </Label>
            ) : (
              last.marks.map((m, i) => (
                <Card key={i}>
                  <Row
                    name="Enstrüman / miktar"
                    value={
                      String(m.symbol ?? "Sembol yok") +
                      " / " +
                      String(m.quantity ?? "Miktar yok")
                    }
                  />
                  <Row
                    name="Mark fiyatı / maliyet bazı"
                    value={
                      String(m.mark_price ?? "Fiyat yok") +
                      " / " +
                      String(m.cost_basis_quote ?? "Maliyet yok") +
                      " USDT"
                    }
                  />
                  <Row
                    name="Kaynak mark zamanı"
                    value={
                      typeof m.mark_time_ms === "number" &&
                      Number.isSafeInteger(m.mark_time_ms)
                        ? new Date(m.mark_time_ms).toLocaleString("tr-TR")
                        : "Zaman eksik"
                    }
                  />
                  <Label muted>
                    Kalıcı olay:{" "}
                    {typeof m.event_id === "string"
                      ? m.event_id.slice(0, 12)
                      : "Kaynak doğrulanmadı"}
                  </Label>
                </Card>
              ))
            )}
          </Disclosure>
          <Heading>UTC işlem dönemleri</Heading>
          {data.period_status !== "complete" ? (
            <Label>
              Dönem özeti kaynak bütçesi veya zaman doğrulaması nedeniyle
              tamamlanamadı. Kısmi toplam gösterilmedi.
            </Label>
          ) : !data.period_totals.length ? (
            <Label>Bu UTC aralığında işlem yok.</Label>
          ) : (
            data.period_totals.map((p, i) => (
              <Row
                key={i}
                name={String(p.period)}
                value={
                  money(String(p.realized_pnl_quote)) +
                  " USDT · ücret " +
                  money(String(p.fees_quote))
                }
              />
            ))
          )}
          <Label muted>
            İşlem dönemleri gerçekleşme zamanına; grafik noktaları kaydedilme
            zamanına aittir.
          </Label>
          <Label muted>
            Kayıt başlangıcı:{" "}
            {new Date(data.coverage_started_at_ms).toLocaleString("tr-TR")}.
            Önceki geçmiş doldurulmadı.{" "}
            {last.proof_coverage === "domain_journal"
              ? "Olay zinciri kanıtı mevcut; bu ekran bağımsız audit çalıştırmaz."
              : "Yalnız kayıt checksum kontrolü; tam tarihsel audit kanıtı yok."}
          </Label>
        </>
      ) : null}
    </Card>
  );
}
