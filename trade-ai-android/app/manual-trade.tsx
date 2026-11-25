import React, { useEffect, useRef, useState } from "react";
import { Alert } from "react-native";
import * as Crypto from "expo-crypto";
import { BotInput, BotPage, Disconnected } from "../src/bot/BotPage";
import { parsePrice } from "../src/bot/PositionCard";
import {
  PREVIEW_MAX_AGE_MS,
  RISK_PCT_MAX,
  RISK_PCT_MIN,
  clearPending,
  loadPending,
  previewMatches,
  resultNotice,
  sameRequest,
  savePending,
  type PendingTrade,
} from "../src/bot/manualTrade";
import { REAL_ACTION_NOTE, amountText, priceText } from "../src/bot/presentation";
import { useBot } from "../src/bot/state";
import { useResource } from "../src/resource";
import type { BotSymbol, PreviewRequest, TradePreview, TradeRequest } from "../src/bot/types";
import { useTheme } from "../src/theme";
import { Button, Card, Choices, Failure, Heading, Label, Loading, Row, ScreenHeader } from "../src/ui";

const SIDES = { AL: "BUY", SAT: "SELL" } as const;
const SIDE_TEXT = { BUY: "AL", SELL: "SAT" } as const;

export default function ManualTrade() {
  const bot = useBot();
  const { colors } = useTheme();
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
  const ready = bot.phase === "ready";
  const api = bot.api;
  const query = useResource(() => api.symbols(), "symbols:" + (bot.config?.origin ?? ""));
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
  function confirmSend() {
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
    Alert.alert(
      shown.symbol + " " + SIDE_TEXT[shown.side] + " emri gönderilsin mi?",
      [
        priceText(shown.lots) + " lot, piyasa fiyatından",
        "Zarar durdur: yaklaşık " + priceText(shown.sl) + " (girişten " + priceText(trade.sl_distance) + " uzakta; en çok yaklaşık −" + amountText(shown.loss, shown.currency) + ")",
        shown.tp != null ? "Kâr al: yaklaşık " + priceText(shown.tp) : "Kâr al yok",
        "Fiyat gönderim anında yeniden okunur; seviyeler mesafeye göre kayabilir.",
        ...shown.warnings.map((warning) => "⚠ " + warning),
      ].join("\n") + (bot.status?.dry_run ? "\n\n" + REAL_ACTION_NOTE : "\n\nBu emir GERÇEK hesapta açılır."),
      [
        { text: "Vazgeç", style: "cancel" },
        { text: "Emri gönder", style: "destructive", onPress: () => void send(order) },
      ],
    );
  }

  return (
    <BotPage>
      <ScreenHeader title="Elle işlem" badge="TRADE BOT" subtitle="Botun sınırlarına sayılmaz; lot hesabı gerçek varlığınızla yapılır." />
      <Disconnected />
      {ready ? (
        <>
          {error ? <Failure message={"Semboller alınamadı. " + error} retry={load} /> : null}
          {symbols === null ? (
            error ? null : <Loading />
          ) : tradable.length === 0 ? (
            <Card>
              <Label>Şu an işleme açık ve fiyatı güncel sembol yok.</Label>
            </Card>
          ) : (
            <Card>
              <Heading>Sembol</Heading>
              <Choices values={tradable.map((row) => row.symbol)} value={symbol} onChange={edited(setSymbol)} disabledValues={busy || locked ? tradable.map((row) => row.symbol) : []} />
              <Heading>Yön</Heading>
              <Choices values={Object.keys(SIDES) as (keyof typeof SIDES)[]} value={side} onChange={edited(setSide)} disabledValues={busy || locked ? (Object.keys(SIDES) as (keyof typeof SIDES)[]) : []} />
              <BotInput accessibilityLabel="Zarar durdurma mesafesi" placeholder="SL mesafesi (fiyat farkı, zorunlu)" keyboardType="decimal-pad" editable={!busy && !locked} value={sl} onChangeText={edited(setSl)} />
              <BotInput accessibilityLabel="Kâr al mesafesi" placeholder="TP mesafesi (isteğe bağlı)" keyboardType="decimal-pad" editable={!busy && !locked} value={tp} onChangeText={edited(setTp)} />
              <BotInput accessibilityLabel="Lot" placeholder="Lot (boşsa risk yüzdesine göre önerilir)" keyboardType="decimal-pad" editable={!busy && !locked} value={lots} onChangeText={edited(setLots)} />
              <BotInput accessibilityLabel="Risk yüzdesi" placeholder="Risk % (isteğe bağlı; boşsa ayardaki risk)" keyboardType="decimal-pad" editable={!busy && !locked} value={risk} onChangeText={edited(setRisk)} />
              <Button title="Önizle" onPress={() => void runPreview()} disabled={busy || locked} secondary />
            </Card>
          )}
          {preview ? (
            <Card>
              <Heading>Önizleme: {preview.data.symbol} {SIDE_TEXT[preview.data.side]}</Heading>
              <Row name="Lot" value={priceText(preview.data.lots) + (preview.data.lots !== preview.data.suggested_lots ? " (öneri: " + priceText(preview.data.suggested_lots) + ")" : "")} />
              <Row name="Giriş (yaklaşık)" value={priceText(preview.data.entry)} />
              <Row name="Zarar durdur (yaklaşık)" value={priceText(preview.data.sl)} />
              <Row name="Kâr al (yaklaşık)" value={priceText(preview.data.tp)} />
              <Row name="En çok zarar" value={"−" + amountText(preview.data.loss, preview.data.currency) + (preview.data.loss_pct != null ? " (%" + String(Number(preview.data.loss_pct.toFixed(2))).replace(".", ",") + ")" : "")} />
              <Row
                name="Hesabın yüzdesi"
                value={
                  (preview.data.loss_pct != null ? "%" + String(Number(preview.data.loss_pct.toFixed(2))).replace(".", ",") : "—") +
                  (preview.data.settings_risk_pct != null ? " (ayardaki sınır: %" + String(preview.data.settings_risk_pct).replace(".", ",") + ")" : "")
                }
              />
              <Row name="Olası kâr" value={preview.data.profit != null ? "+" + amountText(preview.data.profit, preview.data.currency) : "—"} />
              <Row name="Kâr/zarar oranı" value={preview.data.rr != null ? String(Number(preview.data.rr.toFixed(2))).replace(".", ",") : "—"} />
              {preview.data.warnings.map((warning) => (
                <Label key={warning} style={{ color: colors.red }}>⚠ {warning}</Label>
              ))}
              <Button title="Emri gönder" onPress={confirmSend} disabled={busy || locked} />
            </Card>
          ) : null}
          {pending && !busy ? (
            <Card elevated>
              <Label style={{ color: colors.red, fontWeight: "700" }}>Emrin sonucu bilinmiyor</Label>
              <Label muted>
                {pending.trade.symbol} {SIDE_TEXT[pending.trade.side]} emri gönderildi ama yanıt alınamadı. Sonucu öğrenmeden yeni emir gönderilemez.
                Aşağıdaki düğme yalnızca sorar, emir AÇMAZ: emir sunucuya ulaşmamışsa iptal edilir.
              </Label>
              <Button title="Sonucu kontrol et" onPress={() => void resolve()} disabled={busy} secondary />
            </Card>
          ) : null}
          {notice ? <Label style={{ color: notice.bad ? colors.red : colors.muted }}>{notice.text}</Label> : null}
        </>
      ) : null}
    </BotPage>
  );
}
