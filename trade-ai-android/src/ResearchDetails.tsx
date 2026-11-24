/** Saved diagnostics only. This component never creates prices or trade levels. */
import React from "react";
import { reasonText } from "./domain/presentation";
import { Card, Heading, Label, Row, Disclosure } from "./ui";
import { object, field } from "./analysisView";
const text = (v: unknown) =>
  typeof v === "string" && v.length <= 300 ? v : "Veri yok";
const date = (v: unknown) =>
  typeof v === "number" &&
  Number.isSafeInteger(v) &&
  v > 0 &&
  v < 8640000000000000
    ? new Date(v).toLocaleString("tr-TR")
    : "Teyit kaydı yok";
const direction = (v: unknown) =>
  v === "bullish" ? "Yükseliş" : v === "bearish" ? "Düşüş" : "Nötr / belirsiz";
const chartNames: Record<string, string> = {
  ascending_triangle_boundary: "Yükselen üçgen sınırı",
  descending_triangle_boundary: "Alçalan üçgen sınırı",
  symmetrical_triangle_boundary: "Simetrik üçgen sınırı",
  rising_wedge_boundary: "Yükselen kama sınırı",
  falling_wedge_boundary: "Düşen kama sınırı",
  rectangle_boundary: "Yatay aralık sınırı",
  rising_channel_boundary: "Yükselen kanal sınırı",
  falling_channel_boundary: "Düşen kanal sınırı",
  rounding_bottom_geometry: "Yuvarlanan dip adayı",
  rounding_top_geometry: "Yuvarlanan tepe adayı",
  bull_flag: "Yükseliş bayrağı",
  bear_flag: "Düşüş bayrağı",
  bull_pennant: "Yükseliş flaması",
  bear_pennant: "Düşüş flaması",
  double_top_neckline: "Çift tepe · boyun çizgisi",
  double_bottom_neckline: "Çift dip · boyun çizgisi",
  head_and_shoulders_neckline: "Omuz baş omuz · boyun çizgisi",
  inverse_head_and_shoulders_neckline: "Ters omuz baş omuz · boyun çizgisi",
  failed_flag_breakout: "Bayrak kırılımı başarısız",
  failed_pennant_breakout: "Flama kırılımı başarısız",
  flag_retest: "Bayrak sınırı yeniden test edildi",
  pennant_retest: "Flama sınırı yeniden test edildi",
};
export function ResearchDetails({ methods }: { methods: unknown }) {
  const all = object(methods),
    context = object(all.research_context),
    control = object(all.profile_control);
  const patterns = object(context.patterns),
    technical = object(object(context.methods).methods);
  const items = Array.isArray(patterns.patterns)
    ? patterns.patterns.slice(-20).map(object)
    : [];
  const divergence = object(context.divergences);
  const divergenceEvents = Array.isArray(divergence.events)
    ? divergence.events.slice(-10).map(object)
    : [];
  const chart = object(context.charts);
  const charts = Array.isArray(chart.patterns)
    ? chart.patterns.slice(-20).map(object)
    : [];
  const session = object(context.session);
  const sessionVwap = object(session.session_vwap),
    anchored = object(session.anchored_vwap),
    orb = object(session.orb),
    volatility = object(session.volatility);
  return (
    <Card>
      <Heading>Gelişmiş analiz · kayıtlı araştırma</Heading>
      <Label muted>
        Bu açıklamalar işlem izni veya başarı olasılığı değildir. Yalnızca
        analizin değişmez fiyat kaydı kullanılır.
      </Label>
      {context.status !== "available" ? (
        <Label>
          Araştırma verisi eksik veya bu eski kayıtta bulunmuyor. Yeni fiyatla
          tamamlanmadı.
        </Label>
      ) : null}
      {Object.keys(control).length ? (
        <>
          <Row
            name="Profil filtresi"
            value={
              control.passes === true
                ? "Mevcut koşullar uygun"
                : "Uygun değil · BEKLE"
            }
          />
          <Label muted>{reasonText(text(control.reason))}</Label>
          <Label muted>
            Profil risk izni vermez; bağımsız risk ve WAIT kapıları korunur.
          </Label>
        </>
      ) : null}
      <Disclosure title="Mum formasyonları ve teyit zamanları">
        {!items.length ? (
          <Label>Bu kayıtta formasyon kanıtı yok.</Label>
        ) : (
          items.map((p, i) => (
            <Card key={i}>
              <Heading>{text(p.name || p.pattern_id)}</Heading>
              <Row
                name="Yön / zaman dilimi"
                value={direction(p.direction) + " · " + text(p.timeframe)}
              />
              <Row name="Oluşma" value={date(p.formed_at)} />
              <Row name="Teyit" value={date(p.confirmed_at)} />
              <Row name="Trend bağlamı" value={text(p.trend_context)} />
              <Row name="Kalite" value={text(p.quality_status)} />
              <Row
                name="Hacim teyidi"
                value={
                  object(p.volume_confirmation).confirmed === true
                    ? "Var"
                    : "Doğrulanmadı"
                }
              />
              <Label muted>{text(p.explanation)}</Label>
            </Card>
          ))
        )}
        {Array.isArray(patterns.patterns) && patterns.patterns.length > 20 ? (
          <Label muted>Son 20 bulgu gösteriliyor.</Label>
        ) : null}
      </Disclosure>
      <Disclosure title="Grafik yapıları ve gerçek teyit zamanı">
        <Label muted>
          Fiyat geometrisi sezgiseldir; kurumsal emir kanıtı, kazanma olasılığı
          veya işlem izni değildir. Son{" "}
          {typeof chart.source_window_bars === "number"
            ? chart.source_window_bars
            : "kayıtlı"}{" "}
          mumun kaynak penceresi kullanılır; ilk bilinebilir zaman bu pencereye
          aittir.
        </Label>
        {!charts.length ? (
          <Label>Bu kayıtta grafik yapısı kanıtı yok veya veri eksik.</Label>
        ) : (
          charts.map((p, i) => (
            <Card key={i}>
              <Heading>
                {chartNames[text(p.pattern_id)] || text(p.pattern_id)}
              </Heading>
              <Row name="Yapı yönü" value={direction(p.direction)} />
              {p.quality_status ? (
                <Row name="Araştırma durumu" value={text(p.quality_status)} />
              ) : null}
              {p.formation_start_at ? (
                <Row
                  name="Oluşum başlangıcı"
                  value={date(p.formation_start_at)}
                />
              ) : null}
              {p.invalidated_at ? (
                <Row name="Geçersizleşme" value={date(p.invalidated_at)} />
              ) : null}
              {p.interpretation ? (
                <Row
                  name="Kırılım yorumu"
                  value={
                    p.interpretation === "continuation"
                      ? "Önceki trend yönünde"
                      : p.interpretation === "reversal"
                        ? "Önceki trende karşı"
                        : "Teyit bekliyor"
                  }
                />
              ) : null}
              <Row name="Oluşma zamanı" value={date(p.formed_at)} />
              <Row name="İlk bilinebilir" value={date(p.known_at)} />
              <Row name="Kapanış / yapı teyidi" value={date(p.confirmed_at)} />
              <Label muted>{text(p.confirmation_scope || p.explanation)}</Label>
            </Card>
          ))
        )}
      </Disclosure>
      <Disclosure title="UTC kripto seans araştırması">
        <Label muted>
          Spot kripto 24/7 UTC günüdür; borsa açılışı veya Forex seansı
          değildir. VWAP gerçek hacimli OHLC tipik fiyat yaklaşımıdır,
          işlem/tick VWAP değildir.
        </Label>
        {session.status !== "available" ? (
          <Label>Seans kaynağı/takvimi eksik; değer üretilmedi.</Label>
        ) : (
          <>
            <Row
              name="Seans başlangıcı"
              value={date(session.session_started_at_ms)}
            />
            <Row
              name="Seans yüksek / düşük"
              value={
                text(session.session_high) + " / " + text(session.session_low)
              }
            />
            <Row
              name="Seans VWAP"
              value={
                sessionVwap.status === "available"
                  ? text(sessionVwap.value)
                  : "Gerçek hacim veya kaynak eksik"
              }
            />
            <Row
              name="Anchored VWAP"
              value={
                anchored.status === "available"
                  ? text(anchored.value)
                  : "Açık, doğrulanmış anchor seçilmedi"
              }
            />
            <Row
              name="Kapalı opening range"
              value={
                orb.status === "available"
                  ? text(orb.high) + " / " + text(orb.low)
                  : "15 dakikalık kapalı başlangıç aralığı yok"
              }
            />
            <Row
              name="Volatilite rejimi"
              value={
                volatility.status === "available"
                  ? {
                      expanding: "Genişleyen",
                      compressing: "Sıkışan",
                      normal: "Normal",
                    }[text(volatility.regime)] || "Belirsiz"
                  : "Kaynak yetersiz"
              }
            />
          </>
        )}
      </Disclosure>
      <Disclosure title="Teyitli RSI/MACD uyumsuzlukları">
        <Label muted>
          Fiyat pivotu sağındaki iki kapalı mumla teyit edilir. RSI14 basit
          ortalama, MACD12/26 çizgisi kullanılır; Wilder RSI veya histogram ile
          aynı tanım değildir. Backtest/forward doğrulaması değildir.
        </Label>
        {!divergenceEvents.length ? (
          <Label>
            Bu kayıtta teyitli momentum uyumsuzluğu kanıtı yok veya veri eksik.
          </Label>
        ) : (
          divergenceEvents.map((p, i) => (
            <Card key={i}>
              <Heading>
                {p.method_id === "legacy_rsi14_sma"
                  ? "RSI14 · SMA"
                  : p.method_id === "legacy_macd_line_12_26"
                    ? "MACD12/26 · çizgi"
                    : text(p.method_id)}
              </Heading>
              <Row name="Araştırma yönü" value={direction(p.direction)} />
              <Row name="İkinci fiyat pivotu" value={date(p.formed_at)} />
              <Row name="İlk bilinebilir / teyit" value={date(p.known_at)} />
              <Row
                name="Pivot fiyatları"
                value={
                  field(p.price_at_first_pivot) +
                  " → " +
                  field(p.price_at_second_pivot)
                }
              />
              <Row
                name="İndikatör değerleri"
                value={
                  field(p.indicator_at_first_pivot) +
                  " → " +
                  field(p.indicator_at_second_pivot)
                }
              />
              <Label muted>{text(p.explanation)}</Label>
            </Card>
          ))
        )}
      </Disclosure>
      <Disclosure title="Ek teknik indikatörler">
        {!Object.keys(technical).length ? (
          <Label>Doğrulanmış ek indikatör yok.</Label>
        ) : (
          Object.entries(technical)
            .slice(0, 12)
            .map(([name, value]) => {
              const v = object(value);
              return (
                <Card key={name}>
                  <Heading>{name}</Heading>
                  <Label>
                    {v.status === "available"
                      ? "Hesaplandı · araştırma"
                      : "Veri yok"}
                  </Label>
                  {Object.entries(v)
                    .filter(([k]) => !["status", "definition"].includes(k))
                    .slice(0, 8)
                    .map(([k, x]) => (
                      <Row key={k} name={k} value={field(x)} />
                    ))}
                  {v.definition ? (
                    <Label muted>{text(v.definition)}</Label>
                  ) : null}
                </Card>
              );
            })
        )}
      </Disclosure>
      <Label muted>
        Grafik formasyonu kaydı burada yoksa bir formasyon varsayılmaz. Koşullu
        SL/TP yalnız mevcut analiz seviyelerinde gösterilir.
      </Label>
    </Card>
  );
}
