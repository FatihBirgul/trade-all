import React, { useRef, useState } from "react";
import { TextInput } from "react-native";
import * as Crypto from "expo-crypto";
import { router } from "expo-router";
import { useApp } from "./state";
import { useResource } from "./resource";
import { MarketCataloguePicker } from "./MarketCataloguePicker";
import { useTheme } from "./theme";
import { ApiError } from "./api/client";
import type { components } from "./api/schema";
import {
  activationReason,
  activationObservation,
} from "./domain/scannerReadiness";
import { userErrorText } from "./domain/presentation";
import {
  Button,
  Card,
  Choices,
  Disclosure,
  Heading,
  Label,
  Loading,
  Failure,
} from "./ui";
type M = components["schemas"];
type Mode = NonNullable<M["DiscoveryWrite"]["runtime_mode"]>;
type Frame = NonNullable<M["DiscoveryWrite"]["timeframe"]>;
const modes: Record<Mode, string> = {
  off: "Kapalı",
  selected_profile: "Yalnız seçili profil",
  supported_markets: "Desteklenen spot keşfi",
};
const frames = ["5m", "15m", "1H", "4H", "1D"] as const;
const noticeNames: Record<string, string> = {
  early: "Erken fırsat",
  confirmed: "Teyitli koşul",
  invalidated: "Geçersizleşme",
  expired: "Süre dolması",
  unavailable: "Kesinti / toparlanma",
};
export function ScannerConfiguration({
  view,
  reload,
  now,
}: {
  view: M["DiscoveryView"];
  reload: () => void;
  now: number;
}) {
  const app = useApp(),
    c = view.config,
    { colors } = useTheme();
  const observedActivation = activationObservation(view.runtime);
  const advanced =
    !!app.sessionInfo?.capabilities?.includes("scanner-activation-v1") &&
    observedActivation !== null;
  const profileSupport =
    app.sessionInfo?.capabilities?.includes("strategy-profiles-v1") === true;
  const [name, setName] = useState(
      typeof c.name === "string" ? c.name : "Tarama profili",
    ),
    [mode, setMode] = useState<Mode>((c.runtime_mode as Mode) ?? "off"),
    [tf, setTf] = useState<Frame>(c.timeframe as Frame),
    [profileId, setProfileId] = useState<string | null>(
      c.profile_id as string | null,
    ),
    [favorites, setFavorites] = useState<string[]>(
      Array.isArray(c.favorites) ? (c.favorites as string[]) : [],
    ),
    [interval, setInterval] = useState(String(c.interval_seconds)),
    [busy, setBusy] = useState(false),
    [uncertain, setUncertain] = useState(false),
    [error, setError] = useState("");
  const initialNotices = Object.fromEntries(
    Object.keys(noticeNames).map((k) => [k, c["notify_" + k] === true]),
  );
  const [notices, setNotices] =
    useState<Record<string, boolean>>(initialNotices);
  const pending = useRef<M["DiscoveryWrite"] | null>(null),
    lock = useRef(false);
  const writable =
      !!advanced && !!app.sessionInfo?.scopes.includes("discovery:write"),
    disabled = busy || uncertain || !writable;
  const scope = [app.account, app.connectionKey, app.config.session].join("|");
  const profiles = useResource(
    async () => (profileSupport ? app.api.profiles(app.account) : []),
    scope + "|profiles|" + profileSupport,
  );
  const frozen = useResource(
    async () =>
      profileSupport && c.profile_id
        ? app.api.profile(app.account, String(c.profile_id))
        : null,
    scope + "|frozen|" + c.profile_id + "|" + profileSupport,
  );
  const rows = [...(profiles.data ?? [])];
  if (
    frozen.data &&
    !rows.some((p) => p.profile_id === frozen.data?.profile_id)
  )
    rows.push(frozen.data);
  const selected = rows.find((p) => p.profile_id === profileId);
  const base = {
    name: typeof c.name === "string" ? c.name : "Tarama profili",
    mode: c.runtime_mode ?? "off",
    tf: c.timeframe,
    profileId: c.profile_id,
    favorites: c.favorites,
    interval: String(c.interval_seconds),
    notices: initialNotices,
  };
  const dirty =
    JSON.stringify({
      name,
      mode,
      tf,
      profileId,
      favorites,
      interval,
      notices,
    }) !== JSON.stringify(base);
  const activation = observedActivation;
  const profileReady =
    !profileId || (!!selected && selected.selection.setup_timeframe === tf);
  const canActivate =
    writable &&
    !dirty &&
    !busy &&
    !uncertain &&
    profileReady &&
    activation?.state === "ready_to_activate";
  function draft(): M["DiscoveryWrite"] {
    return {
      idempotency_key: Crypto.randomUUID(),
      expected_revision: Number(c.revision),
      name: name.trim(),
      runtime_mode: mode,
      enabled: false,
      discovery: mode === "supported_markets",
      favorites: favorites as ("BTCUSDT" | "ETHUSDT" | "SOLUSDT")[],
      interval_seconds: Number(interval),
      timeframe: tf,
      profile_id: profileId,
      ttl_seconds: Number(c.ttl_seconds),
      ...Object.fromEntries(
        Object.entries(notices).map(([k, v]) => ["notify_" + k, v]),
      ),
    };
  }
  async function write(action: "save" | "activate" | "pause") {
    if (lock.current || !writable || (action === "activate" && !canActivate))
      return;
    if (
      !pending.current &&
      action === "save" &&
      (!name.trim() || name.trim().length > 80 || !profileReady)
    ) {
      setError("Profil adı ve seçili zaman dilimi/revizyonunu kontrol edin.");
      return;
    }
    lock.current = true;
    setBusy(true);
    setError("");
    const body =
      pending.current ??
      (action === "save"
        ? draft()
        : {
            ...draft(),
            name: typeof c.name === "string" ? c.name : "Tarama profili",
            runtime_mode: (c.runtime_mode as Mode) ?? "off",
            enabled: action === "activate",
            discovery: c.discovery === true,
            favorites: c.favorites as ("BTCUSDT" | "ETHUSDT" | "SOLUSDT")[],
            interval_seconds: Number(c.interval_seconds),
            timeframe: c.timeframe as Frame,
            profile_id: c.profile_id as string | null,
            ...Object.fromEntries(
              Object.keys(noticeNames).map((k) => [
                "notify_" + k,
                c["notify_" + k] === true,
              ]),
            ),
          });
    pending.current = body;
    try {
      await app.api.configureMarketScanner(app.account, body);
      pending.current = null;
      setUncertain(false);
      reload();
    } catch (e) {
      const unknown = e instanceof ApiError && e.uncertain;
      setUncertain(unknown);
      if (!unknown) pending.current = null;
      setError(userErrorText(e));
      if (
        e instanceof ApiError &&
        [
          "DISCOVERY_REVISION_CONFLICT",
          "DISCOVERY_ACTIVATION_BLOCKED",
        ].includes(e.code)
      )
        reload();
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  if (!advanced)
    return (
      <Card>
        <Heading>Tarama profili</Heading>
        <Label>
          Bu düzenleyici için Backend ve Gateway güncellemesi gerekli. Eski
          tarama kaydı değiştirilmedi.
        </Label>
      </Card>
    );
  return (
    <Card>
      <Heading>
        {app.account} · tarama profili r{String(c.revision)}
      </Heading>
      <Label>
        Hesap başına tek etkin tarama yapılandırması; geçmiş revizyonlar
        korunur. Strateji profilleri ayrıca sürümlüdür.
      </Label>
      {!writable ? (
        <Label>
          Ayrı discovery:write yetkisi yok · salt okunur. Paper yetkisi
          verilmez.
        </Label>
      ) : null}
      <Label>Profil adı</Label>
      <TextInput
        accessibilityLabel="Tarama profili adı"
        value={name}
        maxLength={80}
        editable={!disabled}
        onChangeText={setName}
        style={{
          color: colors.text,
          borderColor: colors.border,
          borderWidth: 1,
          borderRadius: 10,
          padding: 12,
        }}
      />
      <Label>Çalışma modu</Label>
      <Choices
        values={Object.values(modes)}
        disabledValues={disabled ? Object.values(modes) : []}
        value={modes[mode]}
        onChange={(v) => {
          if (!disabled)
            setMode(
              (Object.keys(modes) as Mode[]).find((k) => modes[k] === v)!,
            );
        }}
      />
      <MarketCataloguePicker
        now={now}
        favorites={favorites}
        disabled={disabled}
        onToggle={(symbol) => {
          if (!disabled)
            setFavorites(
              favorites.includes(symbol)
                ? favorites.filter((s) => s !== symbol)
                : [...favorites, symbol],
            );
        }}
      />
      <Label>Kontrol aralığı (saniye)</Label>
      <Choices
        values={["60", "300", "900", "3600"]}
        disabledValues={disabled ? ["60", "300", "900", "3600"] : []}
        value={interval}
        onChange={(v) => {
          if (!disabled) setInterval(v);
        }}
      />
      <Label>Tekli analiz zaman dilimi</Label>
      <Choices
        values={frames}
        value={tf}
        disabledValues={disabled || !!profileId ? frames : []}
        onChange={(v) => {
          if (!disabled && !profileId) setTf(v as Frame);
        }}
      />
      <Disclosure title="Strateji / çoklu zaman dilimi bağlama">
        <Label>
          Mevcut strateji profili; üst/kurulum/tetik zaman dilimlerini ve
          filtreleri birlikte belirler. Eski revizyon kendiliğinden yenilenmez.
        </Label>
        <Button
          title="Profil bağını kaldır · tekli zaman dilimi"
          secondary
          disabled={disabled}
          onPress={() => setProfileId(null)}
        />
        {profiles.loading ? (
          <Loading />
        ) : profiles.error ? (
          <Failure message={profiles.error} retry={profiles.reload} />
        ) : null}
        {profileSupport && !profiles.loading && !rows.length ? (
          <Label>
            Bu hesapta strateji profili yok. Önce profil oluşturabilirsiniz.
          </Label>
        ) : null}
        {rows.map((p) => (
          <Button
            key={p.profile_id}
            title={
              (p.profile_id === profileId ? "✓ " : "") +
              "r" +
              p.revision +
              " · " +
              p.selection.bias_timeframe +
              " / " +
              p.selection.setup_timeframe +
              " / " +
              p.selection.trigger_timeframe +
              " · " +
              p.profile_id.slice(0, 8)
            }
            secondary
            disabled={
              disabled || !frames.includes(p.selection.setup_timeframe as Frame)
            }
            onPress={() => {
              setProfileId(p.profile_id);
              setTf(p.selection.setup_timeframe as Frame);
            }}
          />
        ))}
        <Label>
          İlk 20 kayıt gösterilir; bağlı eski revizyon ayrıca okunur. 1m
          kurulumlu profiller bu tarayıcıda seçilemez.
        </Label>
        <Button
          title="Strateji profili oluştur / düzenle"
          secondary
          disabled={!profileSupport}
          onPress={() => router.push("/strategy-profiles")}
        />
        {selected ? (
          <Label>
            Seçili sabit revizyon: r{selected.revision}. MTF:{" "}
            {selected.selection.bias_timeframe} /{" "}
            {selected.selection.setup_timeframe} /{" "}
            {selected.selection.trigger_timeframe}. Stratejiler:{" "}
            {(selected.selection.strategy_ids ?? []).join(", ")}. Teyit eşiği:{" "}
            {selected.selection.minimum_confirmations}. Filtreler:{" "}
            {(selected.selection.required_methods ?? []).join(", ")}. Profil bar
            sıklığı araştırma metadatasıdır; worker aralığı yukarıdaki saniye
            ayarıdır.
          </Label>
        ) : profileId ? (
          <Label>
            Bağlı revizyon henüz doğrulanmadı; etkinleştirme kapalı.
          </Label>
        ) : null}
      </Disclosure>
      <Disclosure title="Olay bildirim tercihleri · push değildir">
        {Object.entries(notices).map(([k, v]) => (
          <Button
            key={k}
            title={(v ? "✓ " : "○ ") + noticeNames[k]}
            secondary
            disabled={disabled}
            onPress={() => setNotices({ ...notices, [k]: !v })}
          />
        ))}
        <Label>
          Alıcı sahipliği ve bağımsız analiz kategorisi tercihi ayrıca gerekir.
        </Label>
      </Disclosure>
      <Label>
        Ayar kaydı hesabı pasif bırakır. Bu işlem worker sürecini başlatmaz;
        profil geçmişi silinmez.
      </Label>
      {error ? <Label>{error}</Label> : null}
      {uncertain ? (
        <Button
          title="Aynı isteği tekrar doğrula"
          disabled={busy || !writable}
          onPress={() => void write("save")}
        />
      ) : (
        <Button
          title="Yapılandırmayı kaydet"
          disabled={disabled}
          onPress={() => void write("save")}
        />
      )}
      <Heading>Hesap aktivasyonu</Heading>
      <Label>
        Kayıtlı durum: {c.enabled === true ? "Etkin istek" : "Pasif"}. Worker
        süreci ayrı ve açık runtime seçimi gerektirir.
      </Label>
      {activation?.reasons?.map((reason) => (
        <Label key={reason}>
          {activationReason[reason] ?? "Koşul doğrulanamadı."}
        </Label>
      ))}
      {dirty ? (
        <Label>Kaydedilmemiş değişiklikler var; önce pasif kaydedin.</Label>
      ) : null}
      <Button
        title="Bu hesabın taramasını etkinleştir"
        disabled={!canActivate}
        onPress={() => void write("activate")}
      />
      <Button
        title="Bu hesabın taramasını pasifleştir"
        secondary
        disabled={!writable || busy || uncertain || c.enabled !== true}
        onPress={() => void write("pause")}
      />
      <Label muted>
        Uygulamayı açmak, profil kaydetmek veya bağlantıyı yenilemek servis
        başlatmaz. Gerçek push, Windows autostart ve paper emir izni açılmaz.
      </Label>
    </Card>
  );
}
