import React, { useRef, useState } from "react";
import { Alert, Switch, View } from "react-native";
import { Button, Card, Heading, Label, Row } from "../ui";
import { useTheme } from "../theme";
import { BotInput } from "./BotPage";
import { REAL_ACTION_NOTE, pnlText, pnlTone, priceText, rText } from "./presentation";
import type { BotApi } from "./client";
import type { BotPosition, PositionPatch } from "./types";

// "1,0972" ya da "1.0972" -> sayı. Boş -> undefined (alan gönderilmez). Geçersiz -> null.
export function parsePrice(text: string): number | undefined | null {
  const trimmed = text.trim();
  if (!trimmed) return undefined;
  if (!/^[0-9]{1,12}([.,][0-9]{1,8})?$/.test(trimmed)) return null;
  const value = Number(trimmed.replace(",", "."));
  return Number.isFinite(value) && value > 0 ? value : null;
}

// Yazım hatası süzgeci: "64.800" binlik ayraç sanılıp 64,8 olarak okunabilir, bir hane eksik
// yazılabilir. Fiyattan bu orandan fazla uzak bir seviye gönderilmez.
export const MAX_DISTANCE = 0.5;

export type LevelCheck = { ok: true; widens: boolean } | { ok: false; message: string };

// Yeni SL/TP seviyesinin yönünü ve akla yatkınlığını denetler. `reference`: anlık fiyat (yoksa giriş).
export function checkLevel(
  kind: "sl" | "tp",
  value: number,
  position: Pick<BotPosition, "side" | "sl" | "price" | "entry">,
): LevelCheck {
  const reference = position.price ?? position.entry;
  const name = kind === "sl" ? "SL" : "TP";
  if (Math.abs(value - reference) / reference > MAX_DISTANCE)
    return {
      ok: false,
      message:
        name +
        " " +
        priceText(value) +
        " anlık fiyattan (" +
        priceText(reference) +
        ") çok uzak. Yazım hatası olabilir: binlik ayraç kullanmayın, ondalık için virgül ya da nokta yazın.",
    };
  const buy = position.side === "BUY";
  // AL: SL fiyatın altında, TP üstünde. SAT: tersi.
  const below = kind === "sl" ? buy : !buy;
  if (below ? value >= reference : value <= reference)
    return {
      ok: false,
      message:
        name + " anlık fiyatın (" + priceText(reference) + ") " + (below ? "altında" : "üstünde") + " olmalı.",
    };
  const widens =
    kind === "sl" && position.sl != null && (buy ? value < position.sl : value > position.sl);
  return { ok: true, widens };
}

type Props = {
  position: BotPosition;
  currency: string | null | undefined;
  dryRun?: boolean;
  api: Pick<BotApi, "closePosition" | "patchPosition">;
  onChanged: () => void;
};

export function PositionCard({ position, currency, dryRun = false, api, onChanged }: Props) {
  const { colors } = useTheme();
  const [editing, setEditing] = useState(false);
  const [sl, setSl] = useState("");
  const [tp, setTp] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; bad: boolean } | null>(null);
  const running = useRef(false); // çift dokunuş aynı emri iki kez göndermesin
  const tone = pnlTone(position.unrealized_pnl);
  const pnlColor = tone === "ok" ? colors.green : tone === "bad" ? colors.red : colors.text;
  const real = dryRun ? "\n\n" + REAL_ACTION_NOTE : "";
  // Broker'daki kâr al emri son hedeftir (tp2); tp1 botun kısmi kâr aldığı ara seviyedir.
  const brokerTp = position.tp2;
  const r = rText(position.r_multiple);

  async function run(action: () => Promise<unknown>, done: string) {
    if (running.current) return false;
    running.current = true;
    setBusy(true);
    setNotice(null);
    try {
      await action();
      setNotice({ text: done, bad: false });
      return true;
    } catch (reason) {
      // 409/422: sunucunun kendi açıklaması; ağ hatası: "sonuç belirsiz" uyarısı.
      setNotice({ text: reason instanceof Error ? reason.message : "İşlem tamamlanamadı.", bad: true });
      return false;
    } finally {
      running.current = false;
      setBusy(false);
      onChanged();
    }
  }
  function confirmClose() {
    Alert.alert(
      position.symbol + " kapatılsın mı?",
      priceText(position.volume) + " lot piyasa fiyatından kapatılır. Bu işlem geri alınamaz." + real,
      [
        { text: "Vazgeç", style: "cancel" },
        {
          text: "Kapat",
          style: "destructive",
          onPress: () => void run(() => api.closePosition(position.position_id), "Kapama isteği gönderildi."),
        },
      ],
    );
  }
  function toggleManage(value: boolean) {
    const send = () =>
      void run(
        () => api.patchPosition(position.position_id, { manage: value }),
        value ? "Kademeli stop açıldı." : "Kademeli stop kapatıldı.",
      );
    if (value) return send();
    Alert.alert(
      "Kademeli stop kapatılsın mı?",
      "Bot bu pozisyonda zarar durdurmayı girişe çekmeyi, kısmi kâr almayı ve iz süren stopu bırakır. " +
        "Mevcut SL ve TP emirleri yerinde kalır.",
      [
        { text: "Vazgeç", style: "cancel" },
        { text: "Kapat", style: "destructive", onPress: send },
      ],
    );
  }
  function save() {
    const nextSl = parsePrice(sl);
    const nextTp = parsePrice(tp);
    if (nextSl === null || nextTp === null) {
      setNotice({ text: (nextSl === null ? "SL" : "TP") + " pozitif bir sayı olmalı.", bad: true });
      return;
    }
    const patch: PositionPatch = {};
    if (nextSl !== undefined && nextSl !== position.sl) patch.sl = nextSl;
    if (nextTp !== undefined && nextTp !== brokerTp) patch.tp = nextTp;
    if (patch.sl === undefined && patch.tp === undefined) {
      setNotice({ text: "Değişiklik yok.", bad: false });
      return;
    }
    let widens = false;
    for (const kind of ["sl", "tp"] as const) {
      const value = patch[kind];
      if (value === undefined) continue;
      const check = checkLevel(kind, value, position);
      if (!check.ok) {
        setNotice({ text: check.message, bad: true });
        return;
      }
      widens = widens || check.widens;
    }
    const lines = [
      patch.sl !== undefined ? "Zarar durdur (SL): " + priceText(position.sl) + " → " + priceText(patch.sl) : "",
      patch.tp !== undefined ? "Kâr al (TP): " + priceText(brokerTp) + " → " + priceText(patch.tp) : "",
      "Anlık fiyat: " + priceText(position.price ?? position.entry),
    ].filter(Boolean);
    const submit = async () => {
      if (await run(() => api.patchPosition(position.position_id, patch), "Değişiklik isteği gönderildi.")) {
        setEditing(false);
        setSl("");
        setTp("");
      }
    };
    // Her değişiklik eski → yeni değerle onaylatılır; riski büyüten değişiklik ayrıca uyarılır.
    Alert.alert(
      widens ? "Dikkat: zarar durdurma uzaklaşıyor" : position.symbol + " değişikliği onaylansın mı?",
      lines.join("\n") +
        (widens
          ? "\n\nYeni SL fiyattan daha uzak: bu pozisyonda kaybedebileceğiniz tutar BÜYÜR ve bot bu SL’yi geri çekmez."
          : "") +
        real,
      [
        { text: "Vazgeç", style: "cancel" },
        { text: widens ? "Riski büyüt ve kaydet" : "Kaydet", style: widens ? "destructive" : "default", onPress: () => void submit() },
      ],
    );
  }

  return (
    <Card>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <Heading>
          {position.symbol} · {position.side === "BUY" ? "AL" : "SAT"}
        </Heading>
        <Label muted style={{ fontSize: 12, fontWeight: "700" }}>
          {position.origin === "bot" ? "Bot" : "Elle"}
        </Label>
      </View>
      <Label style={{ color: pnlColor, fontWeight: "700", fontSize: 18, lineHeight: 24 }}>
        {pnlText(position.unrealized_pnl, currency)}
        {r ? "  ·  " + r : ""}
      </Label>
      <Row name="Lot" value={priceText(position.volume)} />
      <Row name="Giriş" value={priceText(position.entry)} />
      <Row name="Anlık fiyat" value={priceText(position.price)} />
      <Row name="Zarar durdur (SL)" value={priceText(position.sl)} />
      <Row name="Kâr al (TP)" value={priceText(brokerTp)} />
      {position.tp1 != null && !position.partial_done ? (
        <Row name="Kısmi kâr seviyesi" value={priceText(position.tp1)} />
      ) : null}
      {position.realized_pnl ? <Row name="Gerçekleşen (kısmi)" value={pnlText(position.realized_pnl, currency)} /> : null}
      {position.sl == null ? (
        <Label style={{ color: colors.red, fontWeight: "700" }}>
          Bu pozisyonda zarar durdurma görünmüyor. Hemen bir SL girin ya da pozisyonu kapatın.
        </Label>
      ) : null}
      {position.user_sl_override ? <Label muted>SL kullanıcı tarafından ayarlandı</Label> : null}
      {position.be_done ? <Label muted>SL giriş seviyesine çekildi</Label> : null}
      {position.partial_done ? <Label muted>Kısmi kâr alındı</Label> : null}
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", minHeight: 48 }}>
        <View style={{ flex: 1 }}>
          <Label>Kademeli stop</Label>
          <Label muted style={{ fontSize: 12 }}>
            Bot kâra geçince SL’yi girişe çeker, kısmi kâr alır.
          </Label>
        </View>
        <Switch
          accessibilityLabel={"Kademeli stop " + position.symbol}
          value={position.manage}
          disabled={busy}
          onValueChange={toggleManage}
        />
      </View>
      {editing ? (
        <>
          <BotInput
            accessibilityLabel={"Yeni SL " + position.symbol}
            placeholder={"Yeni SL (şimdiki: " + priceText(position.sl) + ")"}
            keyboardType="decimal-pad"
            editable={!busy}
            value={sl}
            onChangeText={setSl}
          />
          <BotInput
            accessibilityLabel={"Yeni TP " + position.symbol}
            placeholder={"Yeni TP (şimdiki: " + priceText(brokerTp) + ")"}
            keyboardType="decimal-pad"
            editable={!busy}
            value={tp}
            onChangeText={setTp}
          />
          <Label muted>
            Boş bıraktığınız alan değişmez. Binlik ayraç kullanmayın (64800 yazın, 64.800 değil). Buradan
            verdiğiniz SL’yi bot zarar yönüne geri almaz.
          </Label>
          <Button title="Kaydet" onPress={save} disabled={busy} />
          <Button title="Vazgeç" onPress={() => setEditing(false)} disabled={busy} variant="ghost" />
        </>
      ) : (
        <Button title="SL/TP düzenle" onPress={() => setEditing(true)} disabled={busy} secondary />
      )}
      <Button title="Kapat" onPress={confirmClose} disabled={busy} secondary />
      {notice ? <Label style={{ color: notice.bad ? colors.red : colors.muted }}>{notice.text}</Label> : null}
    </Card>
  );
}
