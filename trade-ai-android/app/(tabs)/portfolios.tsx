import React, { useState } from "react";
import { useApp } from "../../src/state";
import { usePage } from "../../src/usePage";
import {
  validatePortfolio,
  validateLedgerRows,
  decimal,
} from "../../src/domain/portfolio";
import { useResource } from "../../src/resource";
import { emptyPortfolio, money } from "../../src/domain/safety";
import {
  paperStatusText,
  transactionText,
} from "../../src/domain/presentation";
import {
  ScreenHeader,
  Disclosure,
  Button,
  Card,
  Choices,
  Empty,
  Failure,
  Heading,
  Loading,
  Page,
  Row,
  Label,
} from "../../src/ui";
const sections = [
  "Açık pozisyonlar",
  "Sanal emirler",
  "Kapanan pozisyonlar",
  "İşlem geçmişi",
] as const;
export default function Portfolios() {
  const app = useApp();
  const [section, setSection] = useState<(typeof sections)[number]>(
    sections[0],
  );
  const account = app.account;
  const page = usePage(
    [
      app.mode,
      app.connectionKey,
      app.config.origin,
      app.config.session,
      account,
      section,
      app.uiMode,
    ].join("|"),
  );
  const offset = page.offset;
  const query = useResource(async () => {
    if (app.mode === "demo")
      return {
        portfolio: emptyPortfolio(account),
        items: [] as { id: string; title: string; value: string }[],
        hasNext: false,
      };
    const portfolios = await app.api.portfolios();
    const portfolio = portfolios.find((p) => p.portfolio_id === account);
    if (!portfolio || portfolio.data_mode !== "live")
      throw new Error("Canlı hesap verisi doğrulanamadı.");
    validatePortfolio(portfolio, account);
    if (app.uiMode === "basic")
      return {
        portfolio,
        items: [] as { id: string; title: string; value: string }[],
        hasNext: false,
      };
    let items: { id: string; title: string; value: string }[] = [];
    let received = 0;
    if (section === "Sanal emirler") {
      const rows = validateLedgerRows(
        await app.api.orders(account, offset),
        account,
      );
      if (rows.some((o) => !decimal(o.quantity, true)))
        throw new Error("Emir miktarı doğrulanamadı.");
      received = rows.length;
      items = rows.map((o) => ({
        id: o.order_id,
        title: o.symbol + " · " + paperStatusText(o.status),
        value: o.quantity,
      }));
    } else if (section === "İşlem geçmişi") {
      const rows = validateLedgerRows(
        await app.api.transactions(account, offset),
        account,
      );
      if (rows.some((t) => !decimal(t.cash_delta_quote)))
        throw new Error("Defter tutarı doğrulanamadı.");
      received = rows.length;
      items = rows.map((t) => ({
        id: t.transaction_id,
        title: transactionText(t.kind),
        value: money(t.cash_delta_quote) + " USDT",
      }));
    } else {
      const rows = await app.api.positions(
        account,
        section === "Açık pozisyonlar",
        offset,
      );
      validateLedgerRows(rows, account);
      if (
        rows.some(
          (p) =>
            !decimal(p.quantity, true) ||
            !decimal(p.realized_pnl_quote) ||
            !decimal(p.unrealized_pnl_quote),
        )
      )
        throw new Error("Pozisyon verileri doğrulanamadı.");
      received = rows.length;
      items = rows
        .filter((p) =>
          section === "Açık pozisyonlar"
            ? Number(p.quantity) > 0
            : p.status === "closed",
        )
        .map((p) => ({
          id: p.position_id,
          title: p.symbol + " · " + paperStatusText(p.status),
          value:
            money(
              p.status === "closed"
                ? p.realized_pnl_quote
                : p.unrealized_pnl_quote,
            ) +
            " USDT · " +
            new Date(p.mark_time_ms).toLocaleString("tr-TR"),
        }));
    }
    return { portfolio, items, hasNext: received === 20 };
  }, [app.mode, app.config.origin, app.config.session, app.connectionKey, app.uiMode, account, section, offset].join("|"));
  const p = query.data?.portfolio;
  return (
    <Page mode={app.mode} connection={app}>
      <ScreenHeader
        title="Portföyler"
        badge={
          app.uiMode === "pro"
            ? "SANAL HESAPLAR / PRO"
            : "SANAL HESAPLAR / BASİT"
        }
        subtitle="AUTO ve MANUAL ayrı sanal hesaplardır; bakiyeler birleştirilmez."
      />
      <Choices
        values={["AUTO", "MANUAL"] as const}
        value={account}
        disabledValues={
          app.mode === "live"
            ? (["AUTO", "MANUAL"] as const).filter(
                (v) => !app.sessionInfo?.accounts.includes(v),
              )
            : []
        }
        onChange={(v) => {
          app.setAccount(v);
          page.reset();
        }}
      />
      {query.stale && p ? (
        <Label muted>
          Güncel değil · son başarılı hesap sorgusu:{" "}
          {query.loadedAt
            ? new Date(query.loadedAt).toLocaleString("tr-TR")
            : "Zaman yok"}
        </Label>
      ) : null}
      {query.error ? (
        <Failure message={query.error} retry={query.reload} />
      ) : null}
      {query.loading && !p ? (
        <Loading />
      ) : p ? (
        <>
          <Card elevated>
            <Label muted>TOPLAM SANAL VARLIK · {account}</Label>
            <Label muted>
              {app.mode === "demo"
                ? "Yerel DEMO · 10.000 USDT örnek başlangıç bakiyesi; backend bakiyesi değildir."
                : query.stale
                  ? "Önceden alınan backend kaydı · güncel değil"
                  : "Backend’den alınan sanal hesap kaydı"}
            </Label>
            <Label style={{ fontSize: 24, fontWeight: "800", lineHeight: 30 }}>
              {money(p.equity_quote)} USDT
            </Label>
            <Row
              name="Yeni risk"
              value={
                app.mode === "demo"
                  ? "DEMO · risk değerlendirmesi yapılmadı"
                  : p.paused
                    ? "Son sorguda duraklatılmış"
                    : "Son sorguda backend risk kontrolüne açık"
              }
            />
            <Row
              name="Kullanılabilir sanal bakiye"
              value={money(p.available_cash_quote) + " USDT"}
            />
            <Row
              name="Gerçekleşen PnL"
              value={money(p.realized_pnl_quote) + " USDT"}
            />
            <Row
              name="Açık pozisyon PnL"
              value={money(p.unrealized_pnl_quote) + " USDT"}
            />
            {app.uiMode !== "basic" ? (
              <Disclosure title="Bakiye ayrıntıları">
                <Row name="Nakit" value={money(p.cash_quote)} />
                <Row name="Rezerv" value={money(p.reserved_cash_quote)} />
                <Row
                  name="Günlük zarar"
                  value={money(p.realized_loss_today_quote)}
                />
              </Disclosure>
            ) : null}
            <Row
              name="Açık pozisyon / Bekleyen emir"
              value={p.open_positions + " / " + p.pending_orders}
            />
          </Card>
          {app.uiMode !== "basic" ? <Heading>Hesap hareketleri</Heading> : null}
        </>
      ) : null}
      {app.uiMode !== "basic" ? (
        <>
          <Choices
            values={sections}
            value={section}
            onChange={(v) => {
              setSection(v);
              page.reset();
            }}
          />
          {!query.loading &&
            !query.error &&
            (query.data?.items.length ? (
              query.data.items.map((i) => (
                <Card key={i.id}>
                  <Label>{i.title}</Label>
                  <Label muted>{i.value}</Label>
                </Card>
              ))
            ) : (
              <Empty
                text={
                  (app.mode === "demo"
                    ? "Yerel DEMO’da örnek hareket yok. "
                    : "Bu sayfada kayıt yok. ") +
                  account +
                  " · " +
                  section
                }
              />
            ))}
          {app.mode === "live" ? (
            <>
              <Button
                title="Önceki sayfa"
                secondary
                disabled={!offset}
                onPress={page.previous}
              />
              <Button
                title="Sonraki sayfa"
                secondary
                disabled={query.loading || !query.data?.hasNext}
                onPress={page.next}
              />
            </>
          ) : null}
        </>
      ) : null}
      <Label muted>
        Sanal emir oluşturma, iptal ve kapatma; gerçek cihazda kalıcılık,
        idempotency ve hesap izolasyonu doğrulanana kadar kapalı.
      </Label>
      <Button title="Yenile" secondary onPress={query.reload} />
    </Page>
  );
}
