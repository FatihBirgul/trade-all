import React, { useEffect, useRef, useState } from "react";
import { Pressable, View } from "react-native";
import * as Crypto from "expo-crypto";
import { parsePrice } from "../src/bot/levels";
import { PREVIEW_MAX_AGE_MS, RISK_PCT_MAX, RISK_PCT_MIN, clearPending, loadPending, previewMatches, resultNotice, sameRequest, savePending, type PendingTrade } from "../src/bot/manualTrade";
import { REAL_ACTION_NOTE, amountText, majorText, priceText } from "../src/bot/presentation";
import { useBot } from "../src/bot/state";
import type { BotSymbol, PreviewRequest, TradePreview, TradeRequest } from "../src/bot/types";
import { useConfirm } from "../src/ui/confirm";
import { DataGate } from "../src/ui/DataGate";
import { Button, Card, Empty, Failure, Field, Loading, Notice, Pill, Row, Segmented, T } from "../src/ui/kit";
import { Sub } from "../src/ui/Sub";
import { c } from "../src/ui/theme";
import { useResource } from "../src/ui/useResource";

const SIDES = { AL: "BUY", SAT: "SELL" } as const;
const SIDE_TEXT = { BUY: "AL", SELL: "SAT" } as const;

export default function ManualTrade() {
  const bot = useBot();
  const confirm = useConfirm();
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState<keyof typeof SIDES>("AL");
  const [sl, setSl] = useState("");
  const [tp, setTp] = useState("");
  const [lots, setLots] = useState("");
  const [risk, setRisk] = useState("");
  // Önizleme, hangi istek için ve ne zaman alındığıyla birlikte tutulur.
  const [preview, setPreview] = useState<{ data: TradePreview; trade: PreviewRequest; at: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; bad: boolean } | null>(null);
  // Sonucu bilinmeyen emir. Cihazda saklanır: ekran kapanıp açılsa da kilit kalkmaz.
  const [pending, setPending] = useState<PendingTrade | null>(null);
  const [restored, setRestored] = useState(false);
  const sending = useRef(false);
  const previewSeq = useRef(0);
  const api = bot.api;
  const query = useResource(() => api.symbols(), "symbols:" + (bot.config?.origin ?? ""), 5000); // fiyatlar 5 saniyede bir yenilenir
  const symbols: BotSymbol[] | null = query.data ?? null;
  const error = query.error ?? "";
  const load = query.reload;
  const locked = pending !== null || !restored;

  useEffect(() => {
    let alive = true;
    void loadPending().then((value) => {
      if (!alive) return;
      if (value) setPending(value);
      setRestored(true);
    });
    return () => {
      alive = false;
    };
  }, []);

  const tradable = (symbols ?? []).filter((row) => row.open && row.quoted);

  function request(): PreviewRequest | string {
    if (!symbol) return "Bir sembol seçin.";
    const slDistance = parsePrice(sl);
    if (slDistance === undefined || slDistance === null) return "Zarar durdurma mesafesi zorunludur (pozitif sayı).";
    const tpDistance = parsePrice(tp);
    if (tpDistance === null) return "Kâr al mesafesi pozitif bir sayı olmalı.";
    const volume = parsePrice(lots);
    if (volume === null) return "Lot pozitif bir sayı olmalı.";
    const riskPct = parsePrice(risk);
    if (riskPct === null || (riskPct !== undefined && (riskPct < RISK_PCT_MIN || riskPct > RISK_PCT_MAX)))
      return "Risk yüzdesi 0,05 ile 2 arasında olmalı.";
    if (volume !== undefined && riskPct !== undefined) return "Lot ya da risk yüzdesinden yalnızca birini girin.";
    return {
      symbol,
      side: SIDES[side],
      sl_distance: slDistance,
      ...(tpDistance !== undefined ? { tp_distance: tpDistance } : {}),
      ...(volume !== undefined ? { lots: volume } : {}),
      ...(riskPct !== undefined ? { risk_pct: riskPct } : {}),
    };
  }
  function edited<T>(setter: (value: T) => void) {
    return (value: T) => {
      if (busy) return; // istek sürerken girdiler değişmez
      setter(value);
      previewSeq.current += 1; // yoldaki önizleme yanıtı artık geçersiz
      setPreview(null); // önizleme yalnızca ekrandaki değerler için geçerlidir
    };
  }
  async function runPreview() {
    const trade = request();
    if (typeof trade === "string") return setNotice({ text: trade, bad: true });
    const seq = ++previewSeq.current;
    setBusy(true);
    setNotice(null);
    try {
      const data = await api.previewTrade(trade);
      if (seq !== previewSeq.current) return;
      if (!previewMatches(data, trade)) throw new Error("Önizleme başka bir işlem için geldi; yeniden deneyin.");
      setPreview({ data, trade, at: Date.now() });
    } catch (reason) {
      if (seq !== previewSeq.current) return;
      setPreview(null);
      setNotice({ text: reason instanceof Error ? reason.message : "Önizleme alınamadı.", bad: true });
    } finally {
      setBusy(false);
    }
  }
  async function send(order: TradeRequest) {
    if (sending.current) return; // çift dokunuş: kimlik üretilmeden önce durur, tek emir tek kimlik
    sending.current = true;
    setBusy(true);
    setNotice(null);
    const entry: PendingTrade = { id: Crypto.randomUUID(), trade: order, at: Date.now() };
    try {
      // Kimlik, istek gönderilmeden ÖNCE cihaza yazılır; yazılamazsa emir gönderilmez.
      await savePending(entry);
    } catch {
      sending.current = false;
      setBusy(false);
      setNotice({ text: "Emir kaydı cihaza yazılamadı; emir gönderilmedi.", bad: true });
      return;
    }
    setPending(entry);
    try {
      const result = await api.openTrade(order, entry.id);
      await clearPending();
      setPending(null);
      setPreview(null);
      setNotice(resultNotice(result, priceText(result.lots)));
    } catch (reason) {
      const unknown = reason instanceof Error && "uncertain" in reason && (reason as { uncertain: boolean }).uncertain;
      if (!unknown) {
        // Sunucu isteği açıkça reddetti (ör. doğrulama hatası): emir açılmadı.
        await clearPending();
        setPending(null);
      }
      setPreview(null);
      setNotice({ text: reason instanceof Error ? reason.message : "Emir gönderilemedi.", bad: true });
    } finally {
      sending.current = false;
      setBusy(false);
      void bot.refresh();
    }
  }
  // Sonucu bilinmeyen emri sunucuya sorar. Emir açmaz: sunucuda kayıt yoksa o kimliği geçersiz kılar, böylece
  // yolda kalmış istek sonradan ulaşsa bile emir açılmaz. Kilit yalnızca sunucunun KESİN yanıtıyla kalkar.
  async function resolve() {
    if (sending.current || !pending) return;
    sending.current = true;
    setBusy(true);
    setNotice(null);
    try {
      const result = await api.resolveTrade(pending.id);
      await clearPending();
      setPending(null);
      setNotice(
        result.found
          ? resultNotice({ state: result.state, lots: result.lots ?? 0, duplicate: true }, priceText(result.lots))
          : { text: "Emir sunucuya ulaşmamış: pozisyon AÇILMADI ve bu emir iptal edildi. İsterseniz yeniden önizleyip gönderin.", bad: false },
      );
    } catch (reason) {
      setNotice({
        text: "Sonuç öğrenilemedi (" + (reason instanceof Error ? reason.message : "bağlantı hatası") + "). Kilit sürüyor; biraz sonra yeniden deneyin.",
        bad: true,
      });
    } finally {
      sending.current = false;
      setBusy(false);
      void bot.refresh();
    }
  }
  async function confirmSend() {
    const trade = request();
    if (typeof trade === "string" || !preview || locked) return;
    if (!sameRequest(trade, preview.trade) || !previewMatches(preview.data, trade)) {
      setPreview(null);
      return setNotice({ text: "Değerler değişti; yeniden önizleyin.", bad: true });
    }
    if (Date.now() - preview.at > PREVIEW_MAX_AGE_MS) {
      setPreview(null);
      return setNotice({ text: "Önizleme eskidi (1 dakikadan eski); fiyat değişmiş olabilir. Yeniden önizleyin.", bad: true });
    }
    const shown = preview.data;
    // Onaylanan lot, önizlemede gösterilen lottur. Risk yüzdesi yalnızca öneri içindir; emirde lot gider.
    const order: TradeRequest = {
      symbol: trade.symbol,
      side: trade.side,
      sl_distance: trade.sl_distance,
      ...(trade.tp_distance !== undefined ? { tp_distance: trade.tp_distance } : {}),
      lots: shown.lots,
    };
    const message =
      [
        priceText(shown.lots) + " lot, piyasa fiyatından",
        "Zarar durdur: yaklaşık " + priceText(shown.sl) + " (girişten " + priceText(trade.sl_distance) + " uzakta; en çok yaklaşık −" + amountText(shown.loss, shown.currency) + ")",
        shown.tp != null ? "Kâr al: yaklaşık " + priceText(shown.tp) : "Kâr al yok",
        "Fiyat gönderim anında yeniden okunur; seviyeler mesafeye göre kayabilir.",
        ...shown.warnings.map((warning) => "⚠ " + warning),
      ].join("\n") + (bot.status?.dry_run ? "\n\n" + REAL_ACTION_NOTE : "\n\nBu emir GERÇEK hesapta açılır.");
    if (!(await confirm({ title: shown.symbol + " " + SIDE_TEXT[shown.side] + " emri gönderilsin mi?", message, confirm: "Emri gönder", danger: true }))) return;
    // Onay penceresi açık beklemiş olabilir: önizleme bu arada eskidiyse emir gönderilmez.
    if (Date.now() - preview.at > PREVIEW_MAX_AGE_MS) {
      setPreview(null);
      return setNotice({ text: "Önizleme eskidi (1 dakikadan eski); fiyat değişmiş olabilir. Yeniden önizleyin.", bad: true });
    }
    await send(order);
  }

  const [search, setSearch] = useState("");
  const matches = tradable.filter((row) => row.symbol.includes(search.trim().toUpperCase()));
  const chosen = tradable.find((row) => row.symbol === symbol) ?? null;

  return (
    <Sub title="Elle işlem" testID="screen-manual">
      <DataGate>
        {pending ? (
          <Card testID="pending-card" style={{ backgroundColor: c.downSoft, shadowOpacity: 0 }}>
            <T weight="800" size={16}>Sonucu bilinmeyen bir emir var</T>
            <T>{pending.trade.symbol} {SIDE_TEXT[pending.trade.side]} emrinin sunucuya ulaşıp ulaşmadığı bilinmiyor. Sonucu öğrenmeden yeni emir gönderilemez.</T>
            <Button testID="resolve" title="Sonucu sor" icon="help-circle" onPress={() => void resolve()} busy={busy} />
          </Card>
        ) : null}
        {symbols === null ? (
          error ? <Failure message={error} retry={() => void load()} /> : <Loading label="Semboller yükleniyor…" />
        ) : tradable.length === 0 ? (
          <Empty icon="moon" title="Şu an işlem yapılabilen sembol yok" text="Piyasa kapalı olabilir ya da fiyat akışı henüz gelmedi.">
            <Button title="Yenile" kind="tonal" icon="refresh" onPress={() => void load()} />
          </Empty>
        ) : (
          <>
            <Card testID="symbol-card">
              <T weight="800" size={16}>Sembol</T>
              {chosen ? (
                <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                  <View style={{ flex: 1 }}>
                    <T weight="900" size={22}>{chosen.symbol}</T>
                    <T muted size={13}>Alış {priceText(chosen.ask)} · Satış {priceText(chosen.bid)}</T>
                  </View>
                  <Button title="Değiştir" kind="tonal" onPress={() => edited(setSymbol)("")} />
                </View>
              ) : (
                <>
                  <Field label="Ara" placeholder="ör. EURUSD" value={search} onChangeText={setSearch} autoCapitalize="characters" />
                  <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                    {matches.slice(0, 40).map((row) => (
                      <Pressable key={row.symbol} testID={"symbol-" + row.symbol} accessibilityRole="button" accessibilityLabel={row.symbol} onPress={() => edited(setSymbol)(row.symbol)} style={{ backgroundColor: c.tint, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 10 }}>
                        <T weight="800" style={{ color: c.hero }}>{row.symbol}</T>
                      </Pressable>
                    ))}
                  </View>
                  {matches.length === 0 ? <T muted>Eşleşen sembol yok.</T> : null}
                </>
              )}
            </Card>
            <Card>
              <T weight="800" size={16}>Emir</T>
              <Segmented options={[["AL", "AL (alış)"], ["SAT", "SAT (satış)"]] as const} value={side} onChange={edited(setSide)} />
              <Field label="Zarar durdurma mesafesi (zorunlu)" placeholder="fiyat farkı, ör. 0,0020" value={sl} onChangeText={edited(setSl)} keyboardType="decimal-pad" hint="Girişten ne kadar uzakta stop olacağı. Stopsuz emir gönderilmez." />
              <Field label="Kâr al mesafesi" placeholder="boş bırakılabilir" value={tp} onChangeText={edited(setTp)} keyboardType="decimal-pad" />
              <View style={{ flexDirection: "row", gap: 10 }}>
                <View style={{ flex: 1 }}><Field label="Risk %" placeholder="ayardaki" value={risk} onChangeText={edited(setRisk)} keyboardType="decimal-pad" /></View>
                <View style={{ flex: 1 }}><Field label="ya da lot" placeholder="otomatik" value={lots} onChangeText={edited(setLots)} keyboardType="decimal-pad" /></View>
              </View>
              <Button testID="preview" title="Önizle" kind="tonal" icon="eye" onPress={() => void runPreview()} busy={busy && !preview} disabled={locked} />
            </Card>
            {preview ? (
              <Card testID="preview-card">
                <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                  <T weight="900" size={19} style={{ flex: 1 }}>{preview.data.symbol} {SIDE_TEXT[preview.data.side]}</T>
                  <Pill label={priceText(preview.data.lots) + " lot"} />
                </View>
                <Row name="Giriş (yaklaşık)" value={priceText(preview.data.entry)} />
                <Row name="Zarar durdur" value={priceText(preview.data.sl)} />
                <Row name="Kâr al" value={preview.data.tp == null ? "yok" : priceText(preview.data.tp)} />
                <Row name="En çok zarar" value={"−" + amountText(preview.data.loss, preview.data.currency) + (preview.data.loss_pct != null ? " (%" + priceText(Math.round(preview.data.loss_pct * 100) / 100) + ")" : "")} color={c.down} />
                {preview.data.profit != null ? <Row name="Hedefte kâr" value={"+" + amountText(preview.data.profit, preview.data.currency)} color={c.up} /> : null}
                {preview.data.rr != null ? <Row name="Kâr / zarar oranı" value={priceText(preview.data.rr)} /> : null}
                {majorText(preview.data.loss, preview.data.currency) ? <T testID="preview-major" muted size={13}>En çok zarar {majorText(preview.data.loss, preview.data.currency)}{preview.data.profit != null ? ", hedefte kâr " + majorText(preview.data.profit, preview.data.currency) : ""}.</T> : null}
                {preview.data.warnings.map((warning) => <Notice key={warning} text={warning} />)}
                <Button testID="send" title="Emri gönder" icon="send" onPress={() => void confirmSend()} busy={busy} disabled={locked} />
              </Card>
            ) : null}
          </>
        )}
        {notice ? <Notice testID="manual-notice" kind={notice.bad ? "bad" : "info"} text={notice.text} /> : null}
      </DataGate>
    </Sub>
  );
}
