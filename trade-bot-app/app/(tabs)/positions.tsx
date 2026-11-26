import React, { useRef, useState } from "react";
import { Pressable, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { checkLevel, parsePrice } from "../../src/bot/levels";
import { REAL_ACTION_NOTE, pnlText, priceText, rText } from "../../src/bot/presentation";
import { strategyName } from "../../src/bot/settingsForm";
import { useBot } from "../../src/bot/state";
import type { BotPosition, PositionPatch } from "../../src/bot/types";
import { useConfirm } from "../../src/ui/confirm";
import { DataGate } from "../../src/ui/DataGate";
import { Button, Card, Empty, Field, IconBubble, Notice, Pill, Screen, T, Toggle } from "../../src/ui/kit";
import { c, soft, tone } from "../../src/ui/theme";

const STAGES = ["İlk stop", "Başa baş", "İz süren"];
const stageOf = (p: BotPosition) => (p.partial_done ? 2 : p.be_done ? 1 : 0);
const lotText = (value: number) => priceText(value) + " lot";

function PositionCard({ position, dryRun }: { position: BotPosition; dryRun: boolean }) {
  const bot = useBot();
  const confirm = useConfirm();
  const [editing, setEditing] = useState(false);
  const [sl, setSl] = useState("");
  const [tp, setTp] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; bad: boolean } | null>(null);
  const running = useRef(false);
  const buy = position.side === "BUY";
  const stage = stageOf(position);
  const target = position.tp2; // Exness tarafındaki kâr al emri; tp1 botun kendi ara hedefidir

  async function run(action: () => Promise<unknown>, done: string) {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    setNotice(null);
    try {
      await action();
      setNotice({ text: done, bad: false });
      setEditing(false);
      setSl(""); // gönderilen değerler bir sonraki düzenlemede yeniden gönderilmesin
      setTp("");
    } catch (reason) {
      setNotice({ text: reason instanceof Error ? reason.message : "İşlem tamamlanamadı.", bad: true });
    } finally {
      running.current = false;
      setBusy(false);
      void bot.refresh();
    }
  }
  async function close() {
    const message = position.symbol + " " + (buy ? "alış" : "satış") + " pozisyonu (" + lotText(position.volume) + ") piyasa fiyatından kapatılır." + (dryRun ? "\n\n" + REAL_ACTION_NOTE : "");
    if (await confirm({ title: "Pozisyon kapatılsın mı?", message, confirm: "Kapat", danger: true }))
      await run(() => bot.api.closePosition(position.position_id), "Kapama isteği gönderildi.");
  }
  async function save() {
    const nextSl = parsePrice(sl);
    const nextTp = parsePrice(tp);
    if (nextSl === null || nextTp === null) return setNotice({ text: "Fiyatı rakamla yazın (ör. 1,0850).", bad: true });
    const patch: PositionPatch = {};
    const lines: string[] = [];
    let widens = false;
    for (const [kind, value, current, name] of [["sl", nextSl, position.sl, "Stop"], ["tp", nextTp, target, "Hedef"]] as const) {
      if (value === undefined || value === current) continue; // boş ya da değişmemiş alan gönderilmez
      const check = checkLevel(kind, value, position);
      if (!check.ok) return setNotice({ text: check.message, bad: true });
      widens = widens || check.widens;
      patch[kind] = value;
      lines.push(name + ": " + (current == null ? "yok" : priceText(current)) + " → " + priceText(value));
    }
    if (lines.length === 0) return setNotice({ text: "Değiştirmek istediğiniz seviyeyi yazın.", bad: true });
    // Her seviye değişikliği eski → yeni değerleriyle onaylatılır; stop uzaklaşıyorsa ayrıca uyarılır.
    const ok = await confirm({
      title: widens ? "Dikkat: stop uzaklaşıyor" : position.symbol + " seviyeleri değişsin mi?",
      message:
        lines.join("\n") + "\nAnlık fiyat: " + priceText(position.price ?? position.entry) +
        (widens ? "\n\nYeni stop şimdikinden daha uzak: olası zarar büyür." : "") +
        (patch.sl !== undefined && position.origin === "bot" ? "\n\nBot bu pozisyonda kademeli stopu sizin seviyenize göre sürdürür." : "") +
        (dryRun ? "\n\n" + REAL_ACTION_NOTE : ""),
      confirm: widens ? "Yine de kaydet" : "Kaydet",
      danger: widens,
    });
    if (ok) await run(() => bot.api.patchPosition(position.position_id, patch), "Seviye değişikliği gönderildi.");
  }
  async function setManage(value: boolean) {
    if (!value) {
      const ok = await confirm({ title: "Kademeli stop kapatılsın mı?", message: "Bot bu pozisyonda stopu başa başa çekmez, yarısını kapatmaz ve fiyatı izlemez. İlk stop Exness tarafında yerinde kalır." + (dryRun ? "\n\n" + REAL_ACTION_NOTE : ""), confirm: "Kademeli stopu kapat", danger: true });
      if (!ok) return;
    }
    await run(() => bot.api.patchPosition(position.position_id, { manage: value }), value ? "Kademeli stop açıldı." : "Kademeli stop kapatıldı; ilk stop yerinde kalır.");
  }

  return (
    <Card testID={"position-" + position.position_id}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
        <IconBubble icon={buy ? "arrow-up" : "arrow-down"} color={buy ? c.up : c.down} bg={buy ? c.upSoft : c.downSoft} />
        <View style={{ flex: 1 }}>
          <T weight="900" size={19}>{position.symbol}</T>
          <T muted size={13}>{buy ? "Alış" : "Satış"} · {lotText(position.volume)} · {position.origin === "bot" ? (position.strategy_id ? strategyName(position.strategy_id) : "Bot") : "Elle"}</T>
        </View>
        <View style={{ alignItems: "flex-end", gap: 4 }}>
          <T weight="900" size={20} style={{ color: tone(position.unrealized_pnl) }}>{pnlText(position.unrealized_pnl, null)}</T>
          {position.r_multiple != null ? <Pill label={rText(position.r_multiple)} color={tone(position.r_multiple)} bg={soft(position.r_multiple)} /> : null}
        </View>
      </View>
      <View style={{ flexDirection: "row", backgroundColor: c.bg, borderRadius: 16, padding: 12 }}>
        {([["Giriş", position.entry], ["Şimdi", position.price], ["Stop", position.sl], ["Hedef", target]] as const).map(([name, value]) => (
          <View key={name} style={{ flex: 1, gap: 2 }}>
            <T muted size={12}>{name}</T>
            <T weight="700" size={14} style={name === "Stop" && value == null ? { color: c.down } : undefined}>{value == null ? (name === "Stop" ? "YOK" : "—") : priceText(value)}</T>
          </View>
        ))}
      </View>
      {position.sl == null ? <Notice kind="bad" text="Bu pozisyonun zarar durdurma emri yok. Hemen bir stop girin ya da pozisyonu kapatın." /> : null}
      {position.tp1 != null && !position.partial_done ? <T muted size={13}>Ara hedef {priceText(position.tp1)}: bot burada pozisyonun yarısını kapatır.</T> : null}
      {position.user_sl_override ? <Pill label="Stop sizin belirlediğiniz seviyede" /> : null}
      {!position.manage ? (
        <Notice kind="info" text="Kademeli stop bu pozisyonda kapalı. İlk stop Exness tarafında durur." />
      ) : position.sl == null ? null : (
      <View testID={"stages-" + position.position_id} style={{ flexDirection: "row", alignItems: "center" }}>
        {STAGES.map((name, i) => (
          <React.Fragment key={name}>
            {i > 0 ? <View style={{ flex: 1, height: 3, backgroundColor: i <= stage ? c.hero : c.line }} /> : null}
            <View style={{ alignItems: "center", gap: 4 }}>
              <View style={{ width: 22, height: 22, borderRadius: 11, backgroundColor: i <= stage ? c.hero : c.line, alignItems: "center", justifyContent: "center" }}>
                {i <= stage ? <Ionicons name="checkmark" size={14} color={c.white} /> : null}
              </View>
              <T size={11} weight={i === stage ? "800" : "500"} muted={i > stage}>{name}</T>
            </View>
          </React.Fragment>
        ))}
      </View>
      )}
      {position.realized_pnl ? <T muted size={13}>Kısmi kapamadan gerçekleşen: {pnlText(position.realized_pnl, null)}</T> : null}
      {editing ? (
        <View style={{ gap: 12 }}>
          <Field label="Yeni stop (zarar durdur)" placeholder={position.sl == null ? "fiyat" : priceText(position.sl)} value={sl} onChangeText={setSl} keyboardType="decimal-pad" />
          <Field label="Yeni hedef (kâr al)" placeholder={target == null ? "fiyat" : priceText(target)} value={tp} onChangeText={setTp} keyboardType="decimal-pad" hint="Boş bıraktığınız seviye değişmez." />
          <Toggle label="Kademeli stop" hint="Kârda stopu başa başa çeker, yarısını kapatır, sonra fiyatı izler." value={position.manage} onChange={(value) => void setManage(value)} disabled={busy} />
          {dryRun ? <Notice text={REAL_ACTION_NOTE} /> : null}
          <View style={{ flexDirection: "row", gap: 10 }}>
            <Button title="Vazgeç" kind="tonal" onPress={() => setEditing(false)} style={{ flex: 1 }} />
            <Button testID={"save-" + position.position_id} title="Kaydet" onPress={() => void save()} busy={busy} style={{ flex: 1 }} />
          </View>
        </View>
      ) : (
        <View style={{ flexDirection: "row", gap: 10 }}>
          <Button testID={"edit-" + position.position_id} title="Stop / hedef" icon="create" kind="tonal" onPress={() => { setEditing(true); setNotice(null); }} style={{ flex: 1.3 }} />
          <Button testID={"close-" + position.position_id} title="Kapat" kind="danger" onPress={() => void close()} busy={busy} style={{ flex: 1 }} />
        </View>
      )}
      {notice ? <Notice kind={notice.bad ? "bad" : "info"} text={notice.text} /> : null}
    </Card>
  );
}

export default function Positions() {
  const bot = useBot();
  const known = bot.positions.every((position) => position.unrealized_pnl != null);
  const openPnl = bot.positions.reduce((sum, position) => sum + (position.unrealized_pnl ?? 0), 0);
  const ready = bot.phase === "ready" && bot.lastOkAt !== null;
  return (
    <Screen
      testID="screen-positions"
      title="Pozisyonlar"
      subtitle={ready ? (<T muted size={14}>{bot.positions.length} açık{bot.positions.length ? " · " : ""}{bot.positions.length ? (known ? <T weight="800" size={14} style={{ color: tone(openPnl) }}>{pnlText(openPnl, bot.status?.currency)}</T> : "anlık kâr/zarar bilinmiyor") : null}</T>) : undefined}
      right={
        <Pressable testID="new-trade" accessibilityRole="button" accessibilityLabel="Elle işlem aç" onPress={() => router.push("/manual-trade")} style={{ width: 50, height: 50, borderRadius: 25, backgroundColor: c.hero, alignItems: "center", justifyContent: "center" }}>
          <Ionicons name="add" size={28} color={c.white} />
        </Pressable>
      }
    >
      <DataGate>
        {bot.positions.length === 0 ? (
          <Empty icon="swap-vertical" title="Açık pozisyon yok" text={bot.status?.dry_run ? "Bot deneme modunda: piyasayı tarıyor ama emir göndermiyor. Sağ üstteki + ile elle işlem açabilirsiniz." : "Bot uygun bir kurulum bulduğunda ya da siz elle işlem açtığınızda burada görünür."} />
        ) : (
          bot.positions.map((position) => <PositionCard key={position.position_id} position={position} dryRun={bot.status?.dry_run ?? false} />)
        )}
      </DataGate>
    </Screen>
  );
}
